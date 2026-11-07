"""Endpoints REST para cadastro de pacientes, laudos médicos e planos de prescrição (Issue #3)."""

from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from infra.database.repositories.alert_repository import AlertRepository
from infra.database.repositories.medical_report_repository import MedicalReportRepository
from infra.database.repositories.patient_repository import PatientRepository
from infra.database.repositories.plan_repository import PlanRepository
from infra.database.repositories.session_repository import SessionRepository
from models.database.alert import AlertDocument, AlertSeverity, AlertStatus
from models.database.medical_report import MedicalReportDocument
from models.database.patient import PatientDocument
from models.database.plan import PlanDocument, PrescribedExerciseItem
from models.database.session import RiskClassification, SessionDocument, SessionStatus
from models.rest.patient import (
    CreateOrUpdatePatientRequest,
    EvaluateEvolutionRequest,
    ExtractReportPreviewRequest,
    ExtractReportPreviewResponse,
    PatientClinicalBundleResponse,
    PatientEvolutionReportResponse,
    SaveMedicalReportRequest,
    SavePlanRequest,
)
from models.rest.session import ExerciseOption
from services.clinical_extractor import extract_medical_report_entities, parse_amplitude_range
from services.evolution_service import build_patient_evolution_report
from services.pose.registry import canonical_case_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pacientes", tags=["Pacientes, Planos e Laudos"])


# Catálogo completo dos 7 exercícios clínicos do dataset sintético (PRD seção 8.1)
CLINICAL_EXERCISE_CATALOG: list[ExerciseOption] = [
    ExerciseOption(
        case_id="FISIO-001",
        exercise_id="KNEE_EXTENSION_SEATED",
        nome="Extensão de joelho sentado",
        lado_padrao="direito",
        requisitos=["Nenhum"],
    ),
    ExerciseOption(
        case_id="FISIO-002",
        exercise_id="SHOULDER_PENDULUM",
        nome="Exercício pendular do ombro",
        lado_padrao="esquerdo",
        requisitos=["mesa ou apoio estável"],
    ),
    ExerciseOption(
        case_id="FISIO-003",
        exercise_id="PELVIC_TILT_SUPINE",
        nome="Inclinação pélvica em decúbito dorsal",
        lado_padrao="ambos",
        requisitos=["colchonete"],
    ),
    ExerciseOption(
        case_id="FISIO-004",
        exercise_id="KNEE_ROLLS_SUPINE",
        nome="Rotação controlada dos joelhos",
        lado_padrao="ambos",
        requisitos=["colchonete"],
    ),
    ExerciseOption(
        case_id="FISIO-005",
        exercise_id="SHOULDER_FLEXION_STICK",
        nome="Flexão de ombro com bastão leve",
        lado_padrao="ambos",
        requisitos=["bastão de PVC"],
    ),
    ExerciseOption(
        case_id="FISIO-006",
        exercise_id="SHOULDER_ABDUCTION_BAND",
        nome="Abdução de ombro com faixa elástica",
        lado_padrao="direito",
        requisitos=["faixa elástica leve"],
        objeto_deteccao="faixa elástica",
    ),
    ExerciseOption(
        case_id="FISIO-007",
        exercise_id="ELBOW_FLEXION_LIGHT_DUMBBELL",
        nome="Flexão de cotovelo com halter leve",
        lado_padrao="direito",
        requisitos=["halter leve"],
        objeto_deteccao="halter",
    ),
]

_CATALOG_BY_CASE: dict[str, ExerciseOption] = {item.case_id: item for item in CLINICAL_EXERCISE_CATALOG}


def ensure_seed_clinical_data(
    patient_repo: Optional[PatientRepository] = None,
    report_repo: Optional[MedicalReportRepository] = None,
    plan_repo: Optional[PlanRepository] = None,
) -> None:
    """
    Popula pacientes, laudos (LAU-A a LAU-D do PRD seção 8.3) e prescrições sintéticas
    iniciais caso a coleção 'pacientes' esteja vazia.
    """
    p_repo = patient_repo or PatientRepository()
    if p_repo.count_patients() > 0:
        return

    r_repo = report_repo or MedicalReportRepository()
    pl_repo = plan_repo or PlanRepository()

    now = datetime.now(timezone.utc)

    # 1. PAC-001: Marina T. (Mock 1 + LAU-A: Tendinopatia de ombro)
    p_repo.save_patient(
        PatientDocument(
            paciente_id="PAC-001",
            nome="Marina T.",
            idade=38,
            observacoes="Reabilitação de ombro direito — dados sintéticos de demonstração.",
            created_at=now,
            updated_at=now,
        )
    )
    r_repo.save_report(
        MedicalReportDocument(
            laudo_id="LAU-A",
            paciente_id="PAC-001",
            texto_original="Tendinopatia de ombro direito. Evitar elevação acima de 90° sem controle.",
            regiao="ombro direito",
            lesao="tendinopatia",
            movimentos_restritos=["elevação > 90°"],
            limite_amplitude_max=90.0,
            extraido_automaticamente=True,
            revisado_profissional=True,
            created_at=now,
            updated_at=now,
        )
    )
    pl_repo.save_plan(
        PlanDocument(
            plano_id="PLN-PAC-001",
            paciente_id="PAC-001",
            dias_tratamento=3,
            dor_maxima_aceitavel=4,
            amplitude_esperada_min=60.0,
            amplitude_esperada_max=90.0,
            amplitude_esperada_texto="60 – 90",
            exercicios=[
                PrescribedExerciseItem(
                    slot_id="SLOT-1",
                    exercicio_id="FISIO-006",
                    exercicio_nome="Abdução de ombro com faixa elástica",
                    equipamento="faixa elástica leve",
                    lado="direito",
                    series=3,
                    repeticoes=10,
                    instrucoes="Elevar até 90° sem inclinar o tronco.",
                ),
                PrescribedExerciseItem(
                    slot_id="SLOT-2",
                    exercicio_id="FISIO-005",
                    exercicio_nome="Flexão de ombro com bastão leve",
                    equipamento="bastão de PVC",
                    lado="ambos",
                    series=3,
                    repeticoes=8,
                    instrucoes="Manter ombros alinhados durante a elevação.",
                ),
                PrescribedExerciseItem(
                    slot_id="SLOT-3",
                    exercicio_id="FISIO-002",
                    exercicio_nome="Exercício pendular do ombro",
                    equipamento="mesa ou apoio estável",
                    lado="esquerdo",
                    series=2,
                    repeticoes=12,
                    instrucoes="Braço relaxado com oscilação pendular suave.",
                ),
            ],
            created_at=now,
            updated_at=now,
        )
    )

    # 2. PAC-002: Roberto S. (LAU-B: Pós-LCA / Osteoartrite de joelho - FISIO-001)
    p_repo.save_patient(
        PatientDocument(
            paciente_id="PAC-002",
            nome="Roberto S.",
            idade=62,
            observacoes="Pós-operatório / reabilitação de joelho direito — dados sintéticos.",
            created_at=now,
            updated_at=now,
        )
    )
    r_repo.save_report(
        MedicalReportDocument(
            laudo_id="LAU-B",
            paciente_id="PAC-002",
            texto_original=(
                "Pós-LCA e osteoartrite no joelho direito. Evitar extensão forçada com dor "
                "e evitar compensação de tronco."
            ),
            regiao="joelho direito",
            lesao="pós-LCA",
            movimentos_restritos=["extensão forçada", "compensação de tronco"],
            limite_amplitude_max=175.0,
            extraido_automaticamente=True,
            revisado_profissional=True,
            created_at=now,
            updated_at=now,
        )
    )
    pl_repo.save_plan(
        PlanDocument(
            plano_id="PLN-PAC-002",
            paciente_id="PAC-002",
            dias_tratamento=3,
            dor_maxima_aceitavel=3,
            amplitude_esperada_min=150.0,
            amplitude_esperada_max=175.0,
            amplitude_esperada_texto="150 – 175",
            exercicios=[
                PrescribedExerciseItem(
                    slot_id="SLOT-1",
                    exercicio_id="FISIO-001",
                    exercicio_nome="Extensão de joelho sentado",
                    equipamento="Nenhum",
                    lado="direito",
                    series=3,
                    repeticoes=5,
                    instrucoes="Estender lentamente o joelho direito mantendo o tronco estável.",
                ),
            ],
            created_at=now,
            updated_at=now,
        )
    )

    # 3. PAC-003: Cláudia M. (LAU-C: Lombalgia - FISIO-003, FISIO-004)
    p_repo.save_patient(
        PatientDocument(
            paciente_id="PAC-003",
            nome="Cláudia M.",
            idade=45,
            observacoes="Controle motor lombar e pélvico — dados sintéticos.",
            created_at=now,
            updated_at=now,
        )
    )
    r_repo.save_report(
        MedicalReportDocument(
            laudo_id="LAU-C",
            paciente_id="PAC-003",
            texto_original="Lombalgia mecânica na coluna lombar e pelve. Evitar rotação lombar ampla sob carga.",
            regiao="coluna lombar e pelve",
            lesao="lombalgia",
            movimentos_restritos=["rotação lombar ampla sob carga"],
            limite_amplitude_max=45.0,
            extraido_automaticamente=True,
            revisado_profissional=True,
            created_at=now,
            updated_at=now,
        )
    )
    pl_repo.save_plan(
        PlanDocument(
            plano_id="PLN-PAC-003",
            paciente_id="PAC-003",
            dias_tratamento=3,
            dor_maxima_aceitavel=3,
            amplitude_esperada_min=15.0,
            amplitude_esperada_max=45.0,
            amplitude_esperada_texto="15 – 45",
            exercicios=[
                PrescribedExerciseItem(
                    slot_id="SLOT-1",
                    exercicio_id="FISIO-003",
                    exercicio_nome="Inclinação pélvica em decúbito dorsal",
                    equipamento="colchonete",
                    lado="ambos",
                    series=2,
                    repeticoes=8,
                    dias_prescritos=[1, 2, 3],
                ),
                PrescribedExerciseItem(
                    slot_id="SLOT-2",
                    exercicio_id="FISIO-004",
                    exercicio_nome="Rotação controlada dos joelhos",
                    equipamento="colchonete",
                    lado="ambos",
                    series=2,
                    repeticoes=8,
                    dias_prescritos=[2, 3],
                ),
            ],
            created_at=now,
            updated_at=now,
        )
    )

    # 4. PAC-004: Fernando L. (LAU-D: Epicondilite lateral - FISIO-007)
    p_repo.save_patient(
        PatientDocument(
            paciente_id="PAC-004",
            nome="Fernando L.",
            idade=34,
            observacoes="Fortalecimento leve de cotovelo direito — dados sintéticos.",
            created_at=now,
            updated_at=now,
        )
    )
    r_repo.save_report(
        MedicalReportDocument(
            laudo_id="LAU-D",
            paciente_id="PAC-004",
            texto_original="Epicondilite lateral em cotovelo direito. Evitar carga acima do limite e balanço do tronco.",
            regiao="cotovelo direito",
            lesao="epicondilite lateral",
            movimentos_restritos=["carga acima do limite"],
            limite_amplitude_max=145.0,
            extraido_automaticamente=True,
            revisado_profissional=True,
            created_at=now,
            updated_at=now,
        )
    )
    pl_repo.save_plan(
        PlanDocument(
            plano_id="PLN-PAC-004",
            paciente_id="PAC-004",
            dor_maxima_aceitavel=4,
            amplitude_esperada_min=45.0,
            amplitude_esperada_max=145.0,
            amplitude_esperada_texto="45 – 145",
            exercicios=[
                PrescribedExerciseItem(
                    slot_id="SLOT-1",
                    exercicio_id="FISIO-007",
                    exercicio_nome="Flexão de cotovelo com halter leve",
                    equipamento="halter leve",
                    lado="direito",
                    series=3,
                    repeticoes=10,
                ),
            ],
            created_at=now,
            updated_at=now,
        )
    )


# -------------------------------------------------------------------------
# Rotas Estáticas / Utilitárias (declaradas antes de /{paciente_id})
# -------------------------------------------------------------------------

@router.get(
    "/catalogo-exercicios",
    response_model=list[ExerciseOption],
    summary="Listar catálogo completo dos 7 exercícios clínicos para prescrição",
)
def list_clinical_exercise_catalog() -> list[ExerciseOption]:
    return CLINICAL_EXERCISE_CATALOG


@router.post(
    "/laudo/extrair",
    response_model=ExtractReportPreviewResponse,
    summary="Extrair automaticamente entidades estruturadas do texto do laudo",
    description=(
        "Aplica regras determinísticas de domínio em pt-BR sobre o texto livre do laudo "
        "para sugerir região anatômica, lesão e movimentos restritos."
    ),
)
def extract_report_preview(payload: ExtractReportPreviewRequest) -> ExtractReportPreviewResponse:
    extracted = extract_medical_report_entities(payload.texto_original)
    return ExtractReportPreviewResponse(
        texto_original=payload.texto_original,
        regiao=extracted.regiao,
        lesao=extracted.lesao,
        movimentos_restritos=extracted.movimentos_restritos,
        limite_amplitude_max=extracted.limite_amplitude_max,
    )


# -------------------------------------------------------------------------
# Cadastro e Consulta de Pacientes
# -------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[PatientDocument],
    summary="Listar pacientes cadastrados",
)
def list_patients(
    nome: Optional[str] = Query(None, description="Filtro opcional por nome ou ID do paciente"),
) -> list[PatientDocument]:
    patient_repo = PatientRepository()
    ensure_seed_clinical_data(patient_repo=patient_repo)
    return patient_repo.list_patients(nome_query=nome)


@router.post(
    "",
    response_model=PatientDocument,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar ou atualizar paciente sintético",
)
def create_or_update_patient(payload: CreateOrUpdatePatientRequest) -> PatientDocument:
    patient_repo = PatientRepository()
    ensure_seed_clinical_data(patient_repo=patient_repo)

    raw_id = (payload.paciente_id or "").strip().upper()
    if not raw_id:
        count = patient_repo.count_patients() + 1
        raw_id = f"PAC-{count:03d}"
        while patient_repo.get_patient(raw_id) is not None:
            count += 1
            raw_id = f"PAC-{count:03d}"

    now = datetime.now(timezone.utc)
    existing = patient_repo.get_patient(raw_id)
    doc = PatientDocument(
        paciente_id=raw_id,
        nome=payload.nome.strip(),
        idade=payload.idade,
        observacoes=payload.observacoes.strip() if payload.observacoes else None,
        synthetic=True,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
    return patient_repo.save_patient(doc)


@router.get(
    "/{paciente_id}",
    response_model=PatientClinicalBundleResponse,
    summary="Obter dados consolidados do paciente (cadastro, laudo e plano)",
)
def get_patient_bundle(paciente_id: str) -> PatientClinicalBundleResponse:
    patient_repo = PatientRepository()
    report_repo = MedicalReportRepository()
    plan_repo = PlanRepository()
    ensure_seed_clinical_data(patient_repo, report_repo, plan_repo)

    patient = patient_repo.get_patient(paciente_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paciente '{paciente_id}' não encontrado.",
        )

    laudo = report_repo.get_report_by_patient(paciente_id)
    plano = plan_repo.get_plan_by_patient(paciente_id)
    sessoes = SessionRepository().list_sessions(paciente_id=paciente_id, limit=50)
    return PatientClinicalBundleResponse(
        patient=patient,
        laudo=laudo,
        plano=plano,
        sessoes_recentes=sessoes,
    )


@router.get(
    "/{paciente_id}/sessoes",
    response_model=list[SessionDocument],
    summary="Listar histórico de sessões do paciente",
    description=(
        "Retorna as sessões de exercícios enviadas/concluídas pelo paciente, "
        "ordenadas da mais recente para a mais antiga (PRD v1.2 seção 6.3)."
    ),
)
def list_patient_sessions(
    paciente_id: str,
    limit: int = Query(50, ge=1, le=200, description="Número máximo de sessões a retornar"),
) -> list[SessionDocument]:
    patient_repo = PatientRepository()
    ensure_seed_clinical_data(patient_repo=patient_repo)

    if not patient_repo.get_patient(paciente_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paciente '{paciente_id}' não encontrado.",
        )

    session_repo = SessionRepository()
    return session_repo.list_sessions(paciente_id=paciente_id, limit=limit)


# -------------------------------------------------------------------------
# Inserção e Consulta de Laudo Médico por Paciente
# -------------------------------------------------------------------------

@router.post(
    "/{paciente_id}/laudo",
    response_model=MedicalReportDocument,
    summary="Inserir ou atualizar laudo médico estruturado do paciente",
)
def save_patient_medical_report(
    paciente_id: str,
    payload: SaveMedicalReportRequest,
) -> MedicalReportDocument:
    patient_repo = PatientRepository()
    report_repo = MedicalReportRepository()
    ensure_seed_clinical_data(patient_repo=patient_repo, report_repo=report_repo)

    if not patient_repo.get_patient(paciente_id):
        # Cria registro sintético básico do paciente se ainda não existir
        patient_repo.save_patient(
            PatientDocument(
                paciente_id=paciente_id,
                nome=f"Paciente {paciente_id}",
            )
        )

    extracted = extract_medical_report_entities(payload.texto_original)

    regiao_final = (
        payload.regiao.strip()
        if payload.regiao is not None and payload.regiao.strip()
        else extracted.regiao
    )
    lesao_final = (
        payload.lesao.strip()
        if payload.lesao is not None and payload.lesao.strip()
        else extracted.lesao
    )
    if payload.movimentos_restritos is not None:
        restritos_final = [m.strip() for m in payload.movimentos_restritos if m and m.strip()]
    else:
        restritos_final = extracted.movimentos_restritos

    limite_max_final = (
        payload.limite_amplitude_max
        if payload.limite_amplitude_max is not None
        else extracted.limite_amplitude_max
    )

    existing = report_repo.get_report_by_patient(paciente_id)
    now = datetime.now(timezone.utc)
    doc = MedicalReportDocument(
        laudo_id=existing.laudo_id if existing else f"LAU-{paciente_id}",
        paciente_id=paciente_id,
        texto_original=payload.texto_original.strip(),
        regiao=regiao_final,
        lesao=lesao_final,
        movimentos_restritos=restritos_final,
        limite_amplitude_max=limite_max_final,
        observacoes_restricao=payload.observacoes_restricao,
        extraido_automaticamente=True,
        revisado_profissional=payload.revisado_profissional,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
    return report_repo.save_report(doc)


@router.get(
    "/{paciente_id}/laudo",
    response_model=MedicalReportDocument,
    summary="Obter laudo médico do paciente",
)
def get_patient_medical_report(paciente_id: str) -> MedicalReportDocument:
    patient_repo = PatientRepository()
    report_repo = MedicalReportRepository()
    ensure_seed_clinical_data(patient_repo=patient_repo, report_repo=report_repo)

    report = report_repo.get_report_by_patient(paciente_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Laudo médico não encontrado para o paciente '{paciente_id}'.",
        )
    return report


# -------------------------------------------------------------------------
# Inserção e Consulta de Plano de Prescrição por Paciente
# -------------------------------------------------------------------------

@router.post(
    "/{paciente_id}/plano",
    response_model=PlanDocument,
    summary="Inserir ou atualizar plano de prescrição de exercícios do paciente",
)
def save_patient_plan(
    paciente_id: str,
    payload: SavePlanRequest,
) -> PlanDocument:
    patient_repo = PatientRepository()
    plan_repo = PlanRepository()
    ensure_seed_clinical_data(patient_repo=patient_repo, plan_repo=plan_repo)

    if not patient_repo.get_patient(paciente_id):
        patient_repo.save_patient(
            PatientDocument(
                paciente_id=paciente_id,
                nome=f"Paciente {paciente_id}",
            )
        )

    prescribed_items: list[PrescribedExerciseItem] = []
    for idx, item in enumerate(payload.exercicios, start=1):
        try:
            case_id = canonical_case_id(item.exercicio_id)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        cat = _CATALOG_BY_CASE.get(case_id)
        equip = (
            item.equipamento.strip()
            if item.equipamento and item.equipamento.strip()
            else (cat.requisitos[0] if cat and cat.requisitos else "Nenhum")
        )
        lado = (
            item.lado.strip().lower()
            if item.lado and item.lado.strip()
            else (cat.lado_padrao if cat else "auto")
        )
        slot_id = item.slot_id.strip() if item.slot_id and item.slot_id.strip() else f"SLOT-{idx}"
        if item.dias_prescritos:
            dias_prescritos = sorted({int(d) for d in item.dias_prescritos if int(d) >= 1})
            dia_tratamento = dias_prescritos[0] if len(dias_prescritos) == 1 else item.dia_tratamento
        elif item.dia_tratamento is not None:
            dia_tratamento = int(item.dia_tratamento)
            dias_prescritos = [dia_tratamento]
        else:
            dia_tratamento = None
            dias_prescritos = []

        prescribed_items.append(
            PrescribedExerciseItem(
                slot_id=slot_id,
                exercicio_id=case_id,
                exercicio_nome=cat.nome if cat else case_id,
                equipamento=equip,
                lado=lado,
                series=item.series,
                repeticoes=item.repeticoes,
                dia_tratamento=dia_tratamento,
                dias_prescritos=dias_prescritos,
                instrucoes=item.instrucoes,
            )
        )

    parsed_min, parsed_max = parse_amplitude_range(payload.amplitude_esperada_texto)
    amp_min = payload.amplitude_esperada_min if payload.amplitude_esperada_min is not None else parsed_min
    amp_max = payload.amplitude_esperada_max if payload.amplitude_esperada_max is not None else parsed_max

    existing = plan_repo.get_plan_by_patient(paciente_id)
    now = datetime.now(timezone.utc)
    doc = PlanDocument(
        plano_id=existing.plano_id if existing else f"PLN-{paciente_id}_{uuid.uuid4().hex[:4].upper()}",
        paciente_id=paciente_id,
        dor_maxima_aceitavel=payload.dor_maxima_aceitavel,
        amplitude_esperada_min=amp_min,
        amplitude_esperada_max=amp_max,
        amplitude_esperada_texto=payload.amplitude_esperada_texto.strip() or "60 – 90",
        exercicios=prescribed_items,
        ativo=True,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
    doc.dias_tratamento = payload.dias_tratamento
    return plan_repo.save_plan(doc)


@router.get(
    "/{paciente_id}/plano",
    response_model=PlanDocument,
    summary="Obter plano de exercícios prescritos do paciente",
)
def get_patient_plan(paciente_id: str) -> PlanDocument:
    patient_repo = PatientRepository()
    plan_repo = PlanRepository()
    ensure_seed_clinical_data(patient_repo=patient_repo, plan_repo=plan_repo)

    plan = plan_repo.get_plan_by_patient(paciente_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plano de exercícios não encontrado para o paciente '{paciente_id}'.",
        )
    return plan


# -------------------------------------------------------------------------
# Seed Multi-Dias e Relatório Final de Evolução Longitudinal (Issue #7)
# -------------------------------------------------------------------------

def _make_synthetic_series_breakdown(
    series_count: int,
    reps_per_series: int,
    total_completed: int,
    total_valid: int,
    amp_media: float,
    amp_max: float,
) -> list[dict]:
    """Constrói detalhamento por série (Série 1..N) realista para sessões sintéticas de evolução."""
    breakdown = []
    rem_comp = total_completed
    rem_val = total_valid
    for s_idx in range(1, max(1, series_count) + 1):
        comp_s = min(reps_per_series, rem_comp) if s_idx < series_count else rem_comp
        val_s = min(comp_s, rem_val)
        rem_comp = max(0, rem_comp - comp_s)
        rem_val = max(0, rem_val - val_s)
        # Pequena variação fisiológica entre a 1ª e a última série
        offset = (series_count - s_idx) * 1.2 - 1.0
        s_amp_med = round(max(10.0, amp_media + offset), 1)
        s_amp_max = round(max(s_amp_med, amp_max - (s_idx - 1) * 0.8), 1)
        breakdown.append({
            "serie_index": s_idx,
            "label": f"Série {s_idx}",
            "repeticoes_alvo": reps_per_series,
            "repeticoes_completadas": comp_s,
            "repeticoes_validas": val_s,
            "amplitude_media": s_amp_med,
            "amplitude_maxima": s_amp_max,
            "desvios_count": max(0, comp_s - val_s),
            "consistencia_serie": round((val_s / comp_s) * 100.0, 1) if comp_s > 0 else 0.0,
            "concluida": comp_s >= reps_per_series,
        })
    return breakdown


def ensure_seed_alerts(alert_repo: Optional[AlertRepository] = None) -> None:
    """Popula alertas clínicos iniciais no Painel de Alertas caso a coleção esteja vazia."""
    a_repo = alert_repo or AlertRepository()
    if a_repo.count_alerts() > 0:
        return

    now = datetime.now(timezone.utc)
    seed_alerts = [
        AlertDocument(
            alerta_id="ALT-SEED-001",
            paciente_id="PAC-001",
            paciente_nome="Marina T.",
            session_id="SEED-EVO-PAC-001-D1-SLOT-1",
            slot_id="SLOT-1",
            exercicio_id="FISIO-006",
            dia_tratamento=1,
            severidade=AlertSeverity.CRITICO,
            tipo="dor_acima_limite",
            titulo="Marina T. · dor 5,8/10 na região da lesão (acima do limite 4/10)",
            motivo=(
                "Relato de dor 6/10 na 3ª série de Abdução de ombro com faixa elástica (Dia 1), "
                "superando o limite de dor aceitável do plano (4/10) na região de tendinopatia."
            ),
            evidencia_resumo="Dia 1 · Fala “deu uma fisgada no ombro, uns 6 de 10” · 28% do vídeo com dor",
            estado=AlertStatus.NOVO,
            created_at=now - timedelta(days=2, hours=2),
            updated_at=now - timedelta(days=2, hours=2),
        ),
        AlertDocument(
            alerta_id="ALT-SEED-002",
            paciente_id="PAC-001",
            paciente_nome="Marina T.",
            session_id="SEED-EVO-PAC-001-D1-SLOT-2",
            slot_id="SLOT-2",
            exercicio_id="FISIO-005",
            dia_tratamento=1,
            severidade=AlertSeverity.ATENCAO,
            tipo="baixa_consistencia",
            titulo="Marina T. · compensação postural na 3ª série de FISIO-005 (Dia 1)",
            motivo=(
                "Detectada assimetria de ombros nas repetições finais da 3ª série de Flexão com bastão, "
                "reduzindo a consistência biomecânica para 75,5%."
            ),
            evidencia_resumo="Dia 1 · Consistência 75,5% (19/24 reps válidas) · Dor 4,5/10",
            estado=AlertStatus.NOVO,
            created_at=now - timedelta(days=2, hours=1),
            updated_at=now - timedelta(days=2, hours=1),
        ),
        AlertDocument(
            alerta_id="ALT-SEED-003",
            paciente_id="PAC-002",
            paciente_nome="Roberto S.",
            session_id="SEED-EVO-PAC-002-D1-SLOT-1",
            slot_id="SLOT-1",
            exercicio_id="FISIO-001",
            dia_tratamento=1,
            severidade=AlertSeverity.ATENCAO,
            tipo="queda_amplitude",
            titulo="Roberto S. · amplitude reduzida (148°) e dor 4,2/10 em FISIO-001 (Dia 1)",
            motivo=(
                "Amplitude média de extensão de joelho (148,0°) ficou abaixo da faixa esperada do plano "
                "(150–175°), acompanhada de relato de desconforto acima do limite (3/10)."
            ),
            evidencia_resumo="Dia 1 · Amplitude 148,0° · Consistência 72,0% · Dor 4,2/10",
            estado=AlertStatus.NOVO,
            created_at=now - timedelta(days=1, hours=4),
            updated_at=now - timedelta(days=1, hours=4),
        ),
        AlertDocument(
            alerta_id="ALT-SEED-004",
            paciente_id="PAC-001",
            paciente_nome="Marina T.",
            session_id="SEED-EVO-PAC-001-D3-SLOT-1",
            slot_id="SLOT-1",
            exercicio_id="FISIO-006",
            dia_tratamento=3,
            severidade=AlertSeverity.VERDE,
            tipo="evolucao_favoravel",
            titulo="Marina T. · evolução consolidada no Dia 3 (amplitude 84,8° e dor 1,5/10)",
            motivo=(
                "Ganho de +21,3° em amplitude e +24,0 p.p. em consistência ao longo dos 3 dias de tratamento, "
                "com remissão da dor para 1,5/10 (abaixo do limite de 4/10)."
            ),
            evidencia_resumo="Dia 3 · 3 séries × 10 reps concluídas (95,2% consistência) · Revisado",
            estado=AlertStatus.TRATADO,
            created_at=now - timedelta(hours=3),
            updated_at=now - timedelta(hours=2),
        ),
    ]
    for alert in seed_alerts:
        a_repo.save_alert(alert)


def seed_patient_multi_day_evolution(paciente_id: str) -> int:
    """
    Popula o histórico multi-dias (Dia 1, Dia 2 e Dia 3) com execução de todos os exercícios
    prescritos no plano (N séries x M repetições/série) para demonstração imediata do Relatório Final.
    """
    plan_repo = PlanRepository()
    session_repo = SessionRepository()
    ensure_seed_clinical_data(plan_repo=plan_repo)
    ensure_seed_alerts()

    plano = plan_repo.get_plan_by_patient(paciente_id)
    if not plano or not plano.exercicios:
        return 0

    now = datetime.now(timezone.utc)
    dias_total = plano.dias_tratamento or 3

    # Perfis evolutivos por dia (Dia 1 -> Dia 2 -> Dia 3) demonstrando ganho de amplitude,
    # aumento de consistência entre séries e redução progressiva do nível de dor
    if paciente_id == "PAC-001":
        # Marina T.: 3 exercícios (FISIO-006 3x10, FISIO-005 3x8, FISIO-002 2x12)
        day_profiles = {
            (1, "SLOT-1"): {"comp": 26, "val": 21, "devs": 5, "amp_med": 63.5, "amp_max": 68.0, "cons": 71.2, "dor": 5.8, "dor_pct": 28.0, "risk": RiskClassification.ATENCAO},
            (1, "SLOT-2"): {"comp": 22, "val": 19, "devs": 3, "amp_med": 66.0, "amp_max": 71.0, "cons": 75.5, "dor": 4.5, "dor_pct": 18.0, "risk": RiskClassification.ATENCAO},
            (1, "SLOT-3"): {"comp": 24, "val": 22, "devs": 2, "amp_med": 68.0, "amp_max": 72.0, "cons": 86.0, "dor": 2.5, "dor_pct": 8.0, "risk": RiskClassification.VERDE},
            (2, "SLOT-1"): {"comp": 29, "val": 26, "devs": 3, "amp_med": 75.4, "amp_max": 80.0, "cons": 84.6, "dor": 3.6, "dor_pct": 12.0, "risk": RiskClassification.VERDE},
            (2, "SLOT-2"): {"comp": 24, "val": 22, "devs": 2, "amp_med": 77.2, "amp_max": 82.0, "cons": 88.0, "dor": 3.0, "dor_pct": 9.0, "risk": RiskClassification.VERDE},
            (2, "SLOT-3"): {"comp": 24, "val": 24, "devs": 0, "amp_med": 74.0, "amp_max": 78.0, "cons": 94.5, "dor": 1.5, "dor_pct": 4.0, "risk": RiskClassification.VERDE},
            (3, "SLOT-1"): {"comp": 30, "val": 29, "devs": 1, "amp_med": 84.8, "amp_max": 88.5, "cons": 95.2, "dor": 1.5, "dor_pct": 4.0, "risk": RiskClassification.VERDE},
            (3, "SLOT-2"): {"comp": 24, "val": 24, "devs": 0, "amp_med": 85.5, "amp_max": 89.0, "cons": 96.8, "dor": 1.0, "dor_pct": 2.0, "risk": RiskClassification.VERDE},
            (3, "SLOT-3"): {"comp": 24, "val": 24, "devs": 0, "amp_med": 79.5, "amp_max": 83.0, "cons": 97.5, "dor": 0.0, "dor_pct": 0.0, "risk": RiskClassification.VERDE},
        }
    elif paciente_id == "PAC-002":
        # Roberto S.: FISIO-001 (3x5 = 15 reps)
        day_profiles = {
            (1, "SLOT-1"): {"comp": 13, "val": 10, "devs": 3, "amp_med": 148.0, "amp_max": 154.0, "cons": 72.0, "dor": 4.2, "dor_pct": 22.0, "risk": RiskClassification.ATENCAO},
            (2, "SLOT-1"): {"comp": 15, "val": 13, "devs": 2, "amp_med": 159.5, "amp_max": 165.0, "cons": 85.0, "dor": 2.5, "dor_pct": 10.0, "risk": RiskClassification.VERDE},
            (3, "SLOT-1"): {"comp": 15, "val": 15, "devs": 0, "amp_med": 168.5, "amp_max": 173.0, "cons": 94.0, "dor": 1.0, "dor_pct": 3.0, "risk": RiskClassification.VERDE},
        }
    else:
        day_profiles = {}

    created_count = 0
    amp_min_plan = plano.amplitude_esperada_min or 40.0
    amp_max_plan = plano.amplitude_esperada_max or 90.0

    for d in range(1, dias_total + 1):
        day_time = now - timedelta(days=(dias_total - d))
        for idx, item in enumerate(plano.exercicios, start=1):
            if not item.applies_to_day(d):
                continue
            slot_key = item.slot_id or f"SLOT-{idx}"
            target_total = item.series * item.repeticoes
            prof = day_profiles.get((d, slot_key))
            if not prof:
                ratio = d / max(1, dias_total)
                amp_med = round(amp_min_plan + (amp_max_plan - amp_min_plan) * (0.45 + 0.45 * ratio), 1)
                amp_max = round(min(amp_max_plan, amp_med + 4.5), 1)
                comp = target_total if d >= 2 else max(1, target_total - 2)
                val = comp if d == dias_total else max(1, comp - (dias_total - d + 1))
                devs = max(0, comp - val)
                cons = round(72.0 + 11.0 * (d - 1), 1)
                dor = round(max(0.5, float(plano.dor_maxima_aceitavel) + 1.2 - 1.5 * (d - 1)), 1)
                dor_pct = round(max(0.0, dor * 4.0), 1)
                risk = RiskClassification.ATENCAO if d == 1 else RiskClassification.VERDE
            else:
                comp = prof["comp"]
                val = prof["val"]
                devs = prof["devs"]
                amp_med = prof["amp_med"]
                amp_max = prof["amp_max"]
                cons = prof["cons"]
                dor = prof["dor"]
                dor_pct = prof["dor_pct"]
                risk = prof["risk"]

            sess_id = f"SEED-EVO-{paciente_id}-D{d}-{slot_key}"
            breakdown = _make_synthetic_series_breakdown(
                series_count=item.series,
                reps_per_series=item.repeticoes,
                total_completed=comp,
                total_valid=val,
                amp_media=amp_med,
                amp_max=amp_max,
            )
            compliance = round(min(100.0, (val / max(1, target_total)) * 100.0), 1)
            session_doc = SessionDocument(
                session_id=sess_id,
                paciente_id=paciente_id,
                slot_id=slot_key,
                dia_tratamento=d,
                series_prescritas=item.series,
                repeticoes_por_serie=item.repeticoes,
                exercicio_id=item.exercicio_id,
                case_id=item.exercicio_id,
                side_evaluated=item.lado or "auto",
                lgpd_aceite=True,
                original_filename=f"dia{d}_{slot_key.lower()}_{item.exercicio_id.lower()}.mp4",
                file_size_bytes=28_500_000 + d * 1_200_000,
                status=SessionStatus.CONCLUIDO,
                etapa="pose_concluida",
                progress_percent=100.0,
                risk_classification=risk,
                compliance_score=compliance,
                amplitude_media=amp_med,
                amplitude_maxima=amp_max,
                consistencia_score=cons,
                dor_score_0_10=dor,
                dor_percentual_tempo=dor_pct,
                series_breakdown=breakdown,
                target_repetitions=target_total,
                completed_repetitions=comp,
                valid_repetitions=val,
                invalid_repetitions=max(0, comp - val),
                total_deviations=devs,
                justificativas=[
                    f"Dia {d} ({slot_key}): {val}/{target_total} repetições válidas ao longo de {item.series} séries × {item.repeticoes} reps.",
                    f"Amplitude articular média de {amp_med:.1f}° (pico {amp_max:.1f}°), consistência de {cons:.1f}% e dor {dor:.1f}/10.",
                ],
                created_at=day_time + timedelta(minutes=idx * 15),
                updated_at=day_time + timedelta(minutes=idx * 15 + 5),
            )
            session_repo.save_session(session_doc)
            created_count += 1

    return created_count


@router.get(
    "/{paciente_id}/relatorio-evolucao",
    response_model=PatientEvolutionReportResponse,
    summary="Obter Relatório Final de Evolução Longitudinal do Paciente (Issue #7)",
    description=(
        "Avalia a evolução do paciente ao longo dos dias de tratamento e dos vários exercícios prescritos "
        "(N séries x M repetições/série), consolidando Amplitude, Consistência e Nível de Dor."
    ),
)
def get_patient_evolution_report(
    paciente_id: str,
    auto_seed: bool = Query(
        True,
        description="Se True e o paciente sintético padrão ainda não possuir sessões, popula a jornada multi-dias de demonstração",
    ),
) -> PatientEvolutionReportResponse:
    patient_repo = PatientRepository()
    report_repo = MedicalReportRepository()
    plan_repo = PlanRepository()
    session_repo = SessionRepository()
    alert_repo = AlertRepository()

    ensure_seed_clinical_data(patient_repo, report_repo, plan_repo)
    ensure_seed_alerts(alert_repo)

    patient = patient_repo.get_patient(paciente_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paciente '{paciente_id}' não encontrado.",
        )

    sessions = session_repo.list_sessions(paciente_id=paciente_id, limit=200)
    if auto_seed and not sessions and paciente_id in {"PAC-001", "PAC-002", "PAC-003", "PAC-004"}:
        seed_patient_multi_day_evolution(paciente_id)
        sessions = session_repo.list_sessions(paciente_id=paciente_id, limit=200)

    laudo = report_repo.get_report_by_patient(paciente_id)
    plano = plan_repo.get_plan_by_patient(paciente_id)
    alerts = alert_repo.list_alerts(paciente_id=paciente_id, limit=100)

    return build_patient_evolution_report(
        patient=patient,
        laudo=laudo,
        plano=plano,
        sessions=sessions,
        alerts=alerts,
    )


@router.post(
    "/{paciente_id}/seed-evolucao",
    response_model=PatientEvolutionReportResponse,
    summary="Simular/popular jornada multi-dias completa para demonstração do Relatório Final",
)
def trigger_seed_patient_evolution(paciente_id: str) -> PatientEvolutionReportResponse:
    patient_repo = PatientRepository()
    report_repo = MedicalReportRepository()
    plan_repo = PlanRepository()
    session_repo = SessionRepository()
    alert_repo = AlertRepository()

    ensure_seed_clinical_data(patient_repo, report_repo, plan_repo)
    if not patient_repo.get_patient(paciente_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paciente '{paciente_id}' não encontrado.",
        )

    seed_patient_multi_day_evolution(paciente_id)
    patient = patient_repo.get_patient(paciente_id)
    laudo = report_repo.get_report_by_patient(paciente_id)
    plano = plan_repo.get_plan_by_patient(paciente_id)
    sessions = session_repo.list_sessions(paciente_id=paciente_id, limit=200)
    alerts = alert_repo.list_alerts(paciente_id=paciente_id, limit=100)

    return build_patient_evolution_report(
        patient=patient,
        laudo=laudo,
        plano=plano,
        sessions=sessions,
        alerts=alerts,
    )


@router.post(
    "/{paciente_id}/avaliar-evolucao",
    response_model=PatientEvolutionReportResponse,
    summary="Registrar avaliação médica/fisioterapêutica sobre o Relatório Final de Evolução",
)
def evaluate_patient_evolution(
    paciente_id: str,
    payload: EvaluateEvolutionRequest,
) -> PatientEvolutionReportResponse:
    patient_repo = PatientRepository()
    report_repo = MedicalReportRepository()
    plan_repo = PlanRepository()
    session_repo = SessionRepository()
    alert_repo = AlertRepository()

    ensure_seed_clinical_data(patient_repo, report_repo, plan_repo)
    patient = patient_repo.get_patient(paciente_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paciente '{paciente_id}' não encontrado.",
        )

    plan_repo.mark_evolution_evaluated(
        paciente_id=paciente_id,
        avaliado=payload.avaliado,
        observacoes=payload.observacoes,
    )
    if payload.avaliado:
        alert_repo.mark_patient_alerts_treated(paciente_id)

    laudo = report_repo.get_report_by_patient(paciente_id)
    plano = plan_repo.get_plan_by_patient(paciente_id)
    sessions = session_repo.list_sessions(paciente_id=paciente_id, limit=200)
    alerts = alert_repo.list_alerts(paciente_id=paciente_id, limit=100)

    return build_patient_evolution_report(
        patient=patient,
        laudo=laudo,
        plano=plano,
        sessions=sessions,
        alerts=alerts,
    )

