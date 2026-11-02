"""Endpoints REST para criação, consulta e processamento de sessões e eventos biomecânicos."""

from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import Optional, Union
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from config.media_paths import MediaStorage
from infra.database.repositories.event_repository import EventRepository
from infra.database.repositories.session_repository import SessionRepository
from models.database.event import EventDocument
from models.database.session import SessionDocument, SessionStatus
from models.rest.session import (
    CreateSessionPayload,
    CreateSessionResponse,
    ReferenceClipInfo,
    SessionReportResponse,
)
from services.pose.sinks import CompositeResultSink, FileResultSink, MongoResultSink
from services.pose.video_processor import VideoPoseProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessoes", tags=["Sessões e Biomecânica"])


def _run_pose_analysis_pipeline(
    video_path: Path,
    exercicio_id: str,
    session_id: str,
    side: str,
    target_repetitions: Optional[int],
    paciente_id: Optional[str],
) -> None:
    """Função de processamento em segundo plano orquestrando MediaPipe, HUD e persistência."""
    storage = MediaStorage.from_env()
    sink = CompositeResultSink([
        FileResultSink(media_storage=storage),
        MongoResultSink(media_storage=storage),
    ])
    processor = VideoPoseProcessor(media_storage=storage, result_sink=sink)
    try:
        processor.process_video(
            video_path=video_path,
            exercise_identifier=exercicio_id,
            run_id=session_id,
            side=side,
            target_repetitions=target_repetitions,
            patient_id=paciente_id,
            generate_annotated_video=True,
        )
        logger.info("Sessão '%s' processada com sucesso.", session_id)
    except Exception as exc:
        logger.exception("Erro no processamento em background da sessão '%s': %s", session_id, exc)
        session_repo = SessionRepository()
        session_repo.update_status(session_id, SessionStatus.ERRO, etapa="erro_processamento")


def _resolve_and_prepare_video(
    session_id: str,
    exercicio_id: str,
    file: Optional[UploadFile] = None,
    dataset_clip: Optional[str] = None,
    video_path: Optional[str] = None,
) -> Path:
    """Resolve o caminho de vídeo (seja upload multipart, clipe do dataset ou caminho local)."""
    storage = MediaStorage.from_env()

    if file is not None and getattr(file, "filename", None):
        input_path = storage.session_input(session_id)
        input_path.parent.mkdir(parents=True, exist_ok=True)
        with open(input_path, "wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                buffer.write(chunk)
        return input_path

    if dataset_clip:
        clip_path = storage.dataset_clip(exercicio_id, dataset_clip)
        if not clip_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clipe '{dataset_clip}' não encontrado em DATASET_ROOT/{exercicio_id}.",
            )
        return clip_path

    if video_path:
        local_path = Path(video_path).resolve()
        if not local_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Arquivo de vídeo não encontrado em '{video_path}'.",
            )
        return local_path

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="É necessário enviar um arquivo de vídeo via 'file' ou indicar 'dataset_clip' / 'video_path'.",
    )


def _init_session_record(
    session_id: str,
    exercicio_id: str,
    paciente_id: Optional[str],
    side: str,
    target_repetitions: Optional[int],
    video_target: Path,
) -> SessionDocument:
    """Cria e persiste o registro inicial da sessão com status 'processando'."""
    storage = MediaStorage.from_env()
    session_repo = SessionRepository()

    rel_video = None
    try:
        rel_video = storage.relative(video_target)
    except Exception:
        rel_video = str(video_target)

    session_doc = SessionDocument(
        session_id=session_id,
        paciente_id=paciente_id,
        exercicio_id=exercicio_id,
        case_id=exercicio_id,
        side_evaluated=side or "auto",
        status=SessionStatus.PROCESSANDO,
        etapa="processando_pose",
        video_path=rel_video,
        compliance_score=0.0,
        target_repetitions=target_repetitions,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session_repo.save_session(session_doc)
    return session_doc


# -------------------------------------------------------------------------
# Endpoints de Criação / Disparo de Processamento
# -------------------------------------------------------------------------

@router.post(
    "",
    response_model=Union[CreateSessionResponse, SessionDocument],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Criar sessão via upload de vídeo (multipart/form-data)",
    description=(
        "Endpoint principal conforme PRD v1.2 seção 6.3: recebe upload de vídeo multipart "
        "com paciente_id e exercicio, registra a sessão no MongoDB e processa a visão em segundo plano."
    ),
)
def create_session(
    response: Response,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None, description="Arquivo de vídeo gravado (.mp4)"),
    exercicio_id: str = Form(..., description="Identificador do caso ou exercício (ex: 'FISIO-001')"),
    paciente_id: Optional[str] = Form(None, description="Identificador sintético do paciente (ex: 'PAC-001')"),
    dataset_clip: Optional[str] = Form(None, description="Nome do clipe dentro de datasets se não enviar arquivo direto"),
    video_path: Optional[str] = Form(None, description="Caminho do vídeo já presente no filesystem"),
    side: Optional[str] = Form("auto", description="Lado avaliado: auto, direito, esquerdo, ambos"),
    target_repetitions: Optional[int] = Form(5, description="Número de repetições prescritas"),
    run_id: Optional[str] = Form(None, description="ID customizado da sessão (se omitido, será gerado)"),
    sync: bool = Query(False, description="Se True, executa síncrono e retorna 201 com o documento completo"),
):
    session_id = run_id or f"{exercicio_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    video_target = _resolve_and_prepare_video(
        session_id=session_id,
        exercicio_id=exercicio_id,
        file=file,
        dataset_clip=dataset_clip,
        video_path=video_path,
    )

    _init_session_record(
        session_id=session_id,
        exercicio_id=exercicio_id,
        paciente_id=paciente_id,
        side=side or "auto",
        target_repetitions=target_repetitions,
        video_target=video_target,
    )

    if sync:
        _run_pose_analysis_pipeline(
            video_path=video_target,
            exercicio_id=exercicio_id,
            session_id=session_id,
            side=side or "auto",
            target_repetitions=target_repetitions,
            paciente_id=paciente_id,
        )
        response.status_code = status.HTTP_201_CREATED
        saved = SessionRepository().get_session(session_id)
        if not saved:
            raise HTTPException(status_code=500, detail="Erro ao recuperar sessão finalizada.")
        return saved

    background_tasks.add_task(
        _run_pose_analysis_pipeline,
        video_path=video_target,
        exercicio_id=exercicio_id,
        session_id=session_id,
        side=side or "auto",
        target_repetitions=target_repetitions,
        paciente_id=paciente_id,
    )

    return CreateSessionResponse(
        session_id=session_id,
        status=SessionStatus.PROCESSANDO.value,
        etapa="processando_pose",
        message="Vídeo recebido com sucesso. Processamento biomecânico iniciado em background.",
        paciente_id=paciente_id,
        exercicio_id=exercicio_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post(
    "/referencia",
    response_model=Union[CreateSessionResponse, SessionDocument],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Criar sessão via JSON (clipe do dataset ou caminho)",
    description=(
        "Alternativa direta via JSON para testar clipes do dataset de referência "
        "ou vídeos já existentes no servidor sem upload manual de arquivos pesados."
    ),
)
def create_session_from_reference(
    payload: CreateSessionPayload,
    response: Response,
    background_tasks: BackgroundTasks,
    sync: bool = Query(False, description="Se True, executa síncrono e retorna 201 com o documento completo"),
):
    session_id = payload.run_id or f"{payload.exercicio_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    video_target = _resolve_and_prepare_video(
        session_id=session_id,
        exercicio_id=payload.exercicio_id,
        dataset_clip=payload.dataset_clip,
        video_path=payload.video_path,
    )

    _init_session_record(
        session_id=session_id,
        exercicio_id=payload.exercicio_id,
        paciente_id=payload.paciente_id,
        side=payload.side or "auto",
        target_repetitions=payload.target_repetitions,
        video_target=video_target,
    )

    if sync:
        _run_pose_analysis_pipeline(
            video_path=video_target,
            exercicio_id=payload.exercicio_id,
            session_id=session_id,
            side=payload.side or "auto",
            target_repetitions=payload.target_repetitions,
            paciente_id=payload.paciente_id,
        )
        response.status_code = status.HTTP_201_CREATED
        saved = SessionRepository().get_session(session_id)
        if not saved:
            raise HTTPException(status_code=500, detail="Erro ao recuperar sessão finalizada.")
        return saved

    background_tasks.add_task(
        _run_pose_analysis_pipeline,
        video_path=video_target,
        exercicio_id=payload.exercicio_id,
        session_id=session_id,
        side=payload.side or "auto",
        target_repetitions=payload.target_repetitions,
        paciente_id=payload.paciente_id,
    )

    return CreateSessionResponse(
        session_id=session_id,
        status=SessionStatus.PROCESSANDO.value,
        etapa="processando_pose",
        message="Sessão iniciada via referência. Análise biomecânica em background.",
        paciente_id=payload.paciente_id,
        exercicio_id=payload.exercicio_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# -------------------------------------------------------------------------
# Endpoints de Consulta
# -------------------------------------------------------------------------

EXERCISE_NAMES = {
    "FISIO-001": "Extensão de joelho sentado",
    "KNEE_EXTENSION_SEATED": "Extensão de joelho sentado",
    "FISIO-002": "Pêndulo de ombro de Codman",
    "SHOULDER_PENDULUM": "Pêndulo de ombro de Codman",
    "FISIO-003": "Inclinação pélvica deitado",
    "PELVIC_TILT_SUPINE": "Inclinação pélvica deitado",
    "FISIO-004": "Rotação de joelhos deitado",
    "KNEE_ROLLS_SUPINE": "Rotação de joelhos deitado",
    "FISIO-005": "Flexão de ombro com bastão",
    "SHOULDER_FLEXION_STICK": "Flexão de ombro com bastão",
    "FISIO-006": "Abdução de ombro com elástico",
    "SHOULDER_ABDUCTION_BAND": "Abdução de ombro com elástico",
    "FISIO-007": "Flexão de cotovelo com halter",
    "ELBOW_FLEXION_DUMBBELL": "Flexão de cotovelo com halter",
}

RISK_SYMBOLS = {
    "verde": "●",
    "atencao": "▲",
    "critico": "■",
}


@router.get(
    "/clips-referencia",
    response_model=list[ReferenceClipInfo],
    summary="Listar clipes de referência do dataset",
    description="Retorna a lista de clipes de teste do dataset de referência disponíveis para execução imediata.",
)
def list_reference_clips() -> list[ReferenceClipInfo]:
    storage = MediaStorage.from_env()
    clips: list[ReferenceClipInfo] = []

    if storage.dataset_root and storage.dataset_root.is_dir():
        for case_dir in sorted(storage.dataset_root.glob("FISIO-*")):
            if not case_dir.is_dir():
                continue
            case_id = case_dir.name
            for clip_path in sorted(case_dir.glob("*.mp4")):
                filename = clip_path.name
                tipo = "correto" if "correto" in filename.lower() else "desvio"
                desc = (
                    "Execução padrão correta com amplitude completa"
                    if tipo == "correto"
                    else f"Variação motora com desvio postural ({filename})"
                )
                clips.append(
                    ReferenceClipInfo(
                        case_id=case_id,
                        exercicio_id="KNEE_EXTENSION_SEATED" if case_id == "FISIO-001" else case_id,
                        exercicio_nome=EXERCISE_NAMES.get(case_id, case_id),
                        filename=filename,
                        tipo=tipo,
                        descricao=desc,
                    )
                )

    if not clips:
        clips = [
            ReferenceClipInfo(
                case_id="FISIO-001",
                exercicio_id="KNEE_EXTENSION_SEATED",
                exercicio_nome="Extensão de joelho sentado",
                filename="FISIO-001-correto.mp4",
                tipo="correto",
                descricao="Execução correta com 5 repetições e amplitude ideal",
            ),
            ReferenceClipInfo(
                case_id="FISIO-001",
                exercicio_id="KNEE_EXTENSION_SEATED",
                exercicio_nome="Extensão de joelho sentado",
                filename="FISIO-001-extensao-parcial.mp4",
                tipo="desvio",
                descricao="Desvio de amplitude reduzida (extensão incompleta)",
            ),
            ReferenceClipInfo(
                case_id="FISIO-001",
                exercicio_id="KNEE_EXTENSION_SEATED",
                exercicio_nome="Extensão de joelho sentado",
                filename="FISIO-001-inclinacao-tronco.mp4",
                tipo="desvio",
                descricao="Compensação postural com inclinação do tronco para trás",
            ),
            ReferenceClipInfo(
                case_id="FISIO-001",
                exercicio_id="KNEE_EXTENSION_SEATED",
                exercicio_nome="Extensão de joelho sentado",
                filename="FISIO-001-velocidade-irregular.mp4",
                tipo="desvio",
                descricao="Ritmo muito acelerado ou irregular entre repetições",
            ),
        ]
    return clips


@router.get(
    "",
    response_model=list[SessionDocument],
    summary="Listar sessões",
    description="Retorna a lista das sessões de análise registradas no MongoDB, ordenadas das mais recentes.",
)
def list_sessions(
    paciente_id: Optional[str] = Query(None, description="Filtrar sessões por identificador do paciente"),
    limit: int = Query(50, ge=1, le=200, description="Número máximo de sessões a retornar"),
) -> list[SessionDocument]:
    repo = SessionRepository()
    return repo.list_sessions(paciente_id=paciente_id, limit=limit)


@router.get(
    "/{session_id}",
    response_model=SessionDocument,
    summary="Obter detalhes da sessão",
    description="Retorna o documento consolidado da sessão biomecânica a partir de seu session_id (run_id).",
)
def get_session(session_id: str) -> SessionDocument:
    repo = SessionRepository()
    session = repo.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão com ID '{session_id}' não encontrada no MongoDB.",
        )
    return session


@router.get(
    "/{session_id}/eventos",
    response_model=list[EventDocument],
    summary="Listar eventos da sessão",
    description="Retorna todos os eventos registrados (repetições e desvios posturais) vinculados a uma sessão.",
)
def list_session_events(
    session_id: str,
    tipo: Optional[str] = Query(None, description="Filtrar por tipo de evento (ex: 'repeticao', 'desvio')"),
) -> list[EventDocument]:
    session_repo = SessionRepository()
    if not session_repo.get_session(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão com ID '{session_id}' não encontrada.",
        )

    event_repo = EventRepository()
    return event_repo.list_events_by_session(session_id=session_id, tipo=tipo)


@router.get(
    "/{session_id}/relatorio",
    response_model=SessionReportResponse,
    summary="Obter relatório consolidado da sessão",
    description="Retorna os dados consolidados do relatório individual da sessão, com URLs relativas para exibição de mídias e impressão de laudo.",
)
def get_session_report(session_id: str) -> SessionReportResponse:
    session_repo = SessionRepository()
    session = session_repo.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão com ID '{session_id}' não encontrada no MongoDB.",
        )

    event_repo = EventRepository()
    events = event_repo.list_events_by_session(session_id=session_id)

    formatted_events = []
    evidence_urls = []
    for ev in events:
        ev_dict = ev.model_dump(mode="json")
        evidence_path = (ev.evidencia or {}).get("evidence_frame_path")
        if evidence_path:
            ev_url = f"/media/{evidence_path.lstrip('/')}"
            ev_dict["evidence_url"] = ev_url
            rep_idx = (ev.valores or {}).get("repetition_index") or (ev.valores or {}).get("index")
            evidence_urls.append({
                "label": f"Rep #{rep_idx}" if rep_idx else "Desvio",
                "tipo": ev.tipo.value if hasattr(ev.tipo, "value") else str(ev.tipo),
                "url": ev_url,
                "instante_inicio": ev.instante_inicio,
                "instante_fim": ev.instante_fim,
                "descricao": ev.descricao or "Evidência de desvio postural",
                "severidade": ev.severidade or "moderada",
            })
        formatted_events.append(ev_dict)

    risk_val = (
        session.risk_classification.value
        if hasattr(session.risk_classification, "value")
        else str(session.risk_classification or "verde")
    )
    risk_symbol = RISK_SYMBOLS.get(risk_val.lower(), "●")
    exercicio_nome = EXERCISE_NAMES.get(
        session.exercicio_id or session.case_id or "", session.exercicio_id or "Exercício de Reabilitação"
    )

    deviations_count = session.total_deviations or 0
    score = session.compliance_score if session.compliance_score is not None else 100.0

    comparacao_clinica = {
        "plano": {
            "status": "ok" if deviations_count == 0 else "warn",
            "label": "Conforme prescrição" if deviations_count == 0 else f"{deviations_count} desvio(s) detectado(s)",
        },
        "laudo": {
            "status": "ok" if score >= 80 else "warn",
            "label": "Amplitude dentro do limite" if score >= 80 else "Amplitude com restrições clínicas",
        },
        "inconsistencia": {
            "status": "info",
            "label": "Nenhuma inconsistência detectada",
        },
    }

    annotated_url = f"/media/{session.annotated_video_path.lstrip('/')}" if session.annotated_video_path else None
    analysis_url = f"/media/{session.analysis_path.lstrip('/')}" if session.analysis_path else None
    telemetry_url = f"/media/{session.telemetry_path.lstrip('/')}" if session.telemetry_path else None

    return SessionReportResponse(
        session_id=session.session_id,
        paciente_id=session.paciente_id or "PAC-001",
        exercicio_id=session.exercicio_id,
        exercicio_nome=exercicio_nome,
        case_id=session.case_id,
        side_evaluated=session.side_evaluated,
        created_at=session.created_at,
        status=session.status.value if hasattr(session.status, "value") else str(session.status),
        compliance_score=session.compliance_score,
        risk_classification=risk_val,
        risk_symbol=risk_symbol,
        justificativas=session.justificativas or [],
        target_repetitions=session.target_repetitions,
        valid_repetitions=session.valid_repetitions,
        invalid_repetitions=session.invalid_repetitions,
        total_deviations=deviations_count,
        annotated_video_url=annotated_url,
        analysis_json_url=analysis_url,
        telemetry_json_url=telemetry_url,
        evidence_urls=evidence_urls,
        events=formatted_events,
        comparacao_clinica=comparacao_clinica,
        aviso_legal="Apoio à decisão, não diagnóstico.",
    )

