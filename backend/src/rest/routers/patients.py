"""Endpoints REST para cadastro de pacientes, laudos médicos e planos de prescrição (Issue #3)."""

from datetime import datetime, timezone
import logging
from typing import Optional
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from infra.database.repositories.medical_report_repository import MedicalReportRepository
from infra.database.repositories.patient_repository import PatientRepository
from infra.database.repositories.plan_repository import PlanRepository
from infra.database.repositories.session_repository import SessionRepository
from models.database.medical_report import MedicalReportDocument
from models.database.patient import PatientDocument
from models.database.plan import PlanDocument, PrescribedExerciseItem
from models.database.session import SessionDocument
from models.rest.patient import (
    CreateOrUpdatePatientRequest,
    ExtractReportPreviewRequest,
    ExtractReportPreviewResponse,
    PatientClinicalBundleResponse,
    SaveMedicalReportRequest,
    SavePlanRequest,
)
from models.rest.session import ExerciseOption
from services.clinical_extractor import extract_medical_report_entities, parse_amplitude_range
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
                ),
                PrescribedExerciseItem(
                    slot_id="SLOT-2",
                    exercicio_id="FISIO-004",
                    exercicio_nome="Rotação controlada dos joelhos",
                    equipamento="colchonete",
                    lado="ambos",
                    series=2,
                    repeticoes=8,
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

        prescribed_items.append(
            PrescribedExerciseItem(
                slot_id=slot_id,
                exercicio_id=case_id,
                exercicio_nome=cat.nome if cat else case_id,
                equipamento=equip,
                lado=lado,
                series=item.series,
                repeticoes=item.repeticoes,
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

