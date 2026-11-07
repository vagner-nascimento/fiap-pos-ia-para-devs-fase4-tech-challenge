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
from infra.database.repositories.medical_report_repository import MedicalReportRepository
from infra.database.repositories.plan_repository import PlanRepository
from infra.database.repositories.session_repository import SessionRepository
from models.database.event import EventDocument
from models.database.processing import (
    PROCESSING_STEPS,
    STEP_INDEX_BY_ID,
    progress_percent,
    progress_step_index,
    step_id_for_progress,
)
from models.database.session import SessionDocument, SessionStatus
from models.rest.session import (
    CreateSessionPayload,
    CreateSessionResponse,
    ExerciseOption,
    PainAnalysisSummary,
    PainLevelSummary,
    ReferenceClipInfo,
    SessionReportResponse,
)
from services.pose.registry import canonical_case_id
from services.dataset_service import DatasetError, DatasetService
from services.pose.object_detector import detection_config
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
    session_repo = SessionRepository()
    last_progress = (-1, -1.0)

    def publish_progress(stage: str, raw_percent: float) -> None:
        nonlocal last_progress
        step_id = step_id_for_progress(stage)
        step_index = progress_step_index(stage)
        percent = progress_percent(stage, raw_percent)
        if (step_index, percent) <= last_progress:
            return
        last_progress = (step_index, percent)
        step = PROCESSING_STEPS[STEP_INDEX_BY_ID[step_id]]
        session_repo.update_progress(
            session_id,
            status=SessionStatus.CONCLUIDO if stage == "concluido" else SessionStatus.PROCESSANDO,
            etapa=step_id,
            current_step=step_id,
            current_step_index=step_index,
            progress_percent=percent,
            progress_message=step.description,
        )

    try:
        processor.process_video(
            video_path=video_path,
            exercise_identifier=exercicio_id,
            run_id=session_id,
            side=side,
            target_repetitions=target_repetitions,
            patient_id=paciente_id,
            generate_annotated_video=True,
            on_progress=publish_progress,
        )
        logger.info("Sessão '%s' processada com sucesso.", session_id)
    except Exception as exc:
        logger.exception("Erro no processamento em background da sessão '%s': %s", session_id, exc)
        session_repo.update_progress(
            session_id,
            status=SessionStatus.ERRO,
            etapa=(
                PROCESSING_STEPS[last_progress[0]].id
                if last_progress[0] >= 0
                else PROCESSING_STEPS[0].id
            ),
            current_step=(
                PROCESSING_STEPS[last_progress[0]].id
                if last_progress[0] >= 0
                else PROCESSING_STEPS[0].id
            ),
            current_step_index=last_progress[0] if last_progress[0] >= 0 else 0,
            progress_percent=last_progress[1] if last_progress[1] >= 0 else 0.0,
            progress_message="O processamento falhou nesta etapa.",
            error_message=str(exc),
        )


ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # Limite de 200 MB (DESIGN.md seção 4 / PRD seção 7)


def _resolve_and_prepare_video(
    session_id: str,
    exercicio_id: str,
    file: Optional[UploadFile] = None,
    dataset_clip: Optional[str] = None,
    video_path: Optional[str] = None,
) -> tuple[Path, Optional[str], Optional[int]]:
    """Resolve o caminho de vídeo (seja upload multipart, clipe do dataset ou caminho local)."""
    storage = MediaStorage.from_env()

    if file is not None and getattr(file, "filename", None):
        raw_filename = Path(file.filename).name
        ext = Path(raw_filename).suffix.lower()
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Formato de arquivo inválido ('{ext or raw_filename}'). "
                    "Envie um arquivo de vídeo válido (.mp4, .mov, .webm)."
                ),
            )

        input_path = storage.session_input(session_id)
        input_path.parent.mkdir(parents=True, exist_ok=True)
        total_bytes = 0
        try:
            with open(input_path, "wb") as buffer:
                while chunk := file.file.read(1024 * 1024):
                    total_bytes += len(chunk)
                    if total_bytes > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="O arquivo de vídeo excede o limite máximo permitido de 200 MB.",
                        )
                    buffer.write(chunk)
        except HTTPException:
            input_path.unlink(missing_ok=True)
            raise

        if total_bytes == 0:
            input_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O arquivo de vídeo enviado está vazio.",
            )
        return input_path, raw_filename, total_bytes

    if dataset_clip:
        try:
            clip_path = DatasetService().resolve_clip(exercicio_id, dataset_clip)
            size_bytes = clip_path.stat().st_size if clip_path.exists() else None
            return clip_path, Path(dataset_clip).name, size_bytes
        except DatasetError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    if video_path:
        local_path = Path(video_path).resolve()
        if not local_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Arquivo de vídeo não encontrado em '{video_path}'.",
            )
        return local_path, local_path.name, local_path.stat().st_size

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="É necessário enviar um arquivo de vídeo via 'file' ou indicar 'dataset_clip' / 'video_path'.",
    )


def _normalize_exercise_id(exercicio_id: Optional[str]) -> str:
    if not exercicio_id or not exercicio_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="É obrigatório informar 'exercicio_id' ou 'exercicio'.",
        )
    try:
        return canonical_case_id(exercicio_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _validate_lgpd_consent(lgpd_aceite: bool) -> None:
    if not lgpd_aceite:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="É obrigatório aceitar o termo de consentimento LGPD (imagem e voz) para enviar a sessão.",
        )


def _init_session_record(
    session_id: str,
    exercicio_id: str,
    paciente_id: Optional[str],
    side: str,
    target_repetitions: Optional[int],
    video_target: Path,
    slot_id: Optional[str] = None,
    lgpd_aceite: bool = True,
    original_filename: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
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
        slot_id=slot_id,
        exercicio_id=exercicio_id,
        case_id=exercicio_id,
        side_evaluated=side or "auto",
        lgpd_aceite=lgpd_aceite,
        original_filename=original_filename,
        file_size_bytes=file_size_bytes,
        status=SessionStatus.PROCESSANDO,
        etapa="video_received",
        current_step="video_received",
        current_step_index=0,
        total_steps=len(PROCESSING_STEPS),
        progress_percent=0.0,
        progress_message=PROCESSING_STEPS[0].description,
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
        "com paciente_id e exercicio (ou exercicio_id), registra a sessão no MongoDB e processa a visão em segundo plano."
    ),
)
def create_session(
    response: Response,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None, description="Arquivo de vídeo gravado (.mp4)"),
    exercicio_id: Optional[str] = Form(None, description="Identificador do caso ou exercício (ex: 'FISIO-001')"),
    exercicio: Optional[str] = Form(None, description="Alias do identificador do exercício conforme PRD v1.2"),
    paciente_id: Optional[str] = Form(None, description="Identificador sintético do paciente (ex: 'PAC-001')"),
    slot_id: Optional[str] = Form(None, description="Identificador do slot na prescrição (ex: 'SLOT-1')"),
    lgpd_aceite: bool = Form(True, description="Aceite do termo de consentimento LGPD para imagem e voz"),
    dataset_clip: Optional[str] = Form(None, description="Nome do clipe dentro de datasets se não enviar arquivo direto"),
    video_path: Optional[str] = Form(None, description="Caminho do vídeo já presente no filesystem"),
    side: Optional[str] = Form("auto", description="Lado avaliado: auto, direito, esquerdo, ambos"),
    target_repetitions: Optional[int] = Form(5, description="Número de repetições prescritas"),
    run_id: Optional[str] = Form(None, description="ID customizado da sessão (se omitido, será gerado)"),
    sync: bool = Query(False, description="Se True, executa síncrono e retorna 201 com o documento completo"),
):
    _validate_lgpd_consent(lgpd_aceite)
    resolved_exercise_id = _normalize_exercise_id(exercicio_id or exercicio)
    session_id = run_id or f"{resolved_exercise_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    video_target, orig_name, size_bytes = _resolve_and_prepare_video(
        session_id=session_id,
        exercicio_id=resolved_exercise_id,
        file=file,
        dataset_clip=dataset_clip,
        video_path=video_path,
    )

    _init_session_record(
        session_id=session_id,
        exercicio_id=resolved_exercise_id,
        paciente_id=paciente_id,
        side=side or "auto",
        target_repetitions=target_repetitions,
        video_target=video_target,
        slot_id=slot_id,
        lgpd_aceite=lgpd_aceite,
        original_filename=orig_name,
        file_size_bytes=size_bytes,
    )

    if sync:
        _run_pose_analysis_pipeline(
            video_path=video_target,
            exercicio_id=resolved_exercise_id,
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
        exercicio_id=resolved_exercise_id,
        session_id=session_id,
        side=side or "auto",
        target_repetitions=target_repetitions,
        paciente_id=paciente_id,
    )

    return CreateSessionResponse(
        session_id=session_id,
        status=SessionStatus.PROCESSANDO.value,
        etapa="video_received",
        message="Vídeo recebido com sucesso. Processamento biomecânico iniciado em background.",
        paciente_id=paciente_id,
        slot_id=slot_id,
        exercicio_id=resolved_exercise_id,
        lgpd_aceite=lgpd_aceite,
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
    _validate_lgpd_consent(payload.lgpd_aceite)
    payload.exercicio_id = _normalize_exercise_id(payload.exercicio_id)
    session_id = payload.run_id or f"{payload.exercicio_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    video_target, orig_name, size_bytes = _resolve_and_prepare_video(
        session_id=session_id,
        exercicio_id=payload.exercicio_id,
        dataset_clip=payload.dataset_clip,
    )

    _init_session_record(
        session_id=session_id,
        exercicio_id=payload.exercicio_id,
        paciente_id=payload.paciente_id,
        side=payload.side or "auto",
        target_repetitions=payload.target_repetitions,
        video_target=video_target,
        slot_id=payload.slot_id,
        lgpd_aceite=payload.lgpd_aceite,
        original_filename=orig_name,
        file_size_bytes=size_bytes,
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
        etapa="video_received",
        message="Sessão iniciada via referência. Análise biomecânica em background.",
        paciente_id=payload.paciente_id,
        slot_id=payload.slot_id,
        exercicio_id=payload.exercicio_id,
        lgpd_aceite=payload.lgpd_aceite,
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
    "ELBOW_FLEXION_LIGHT_DUMBBELL": "Flexão de cotovelo com halter",
}

CASE_TO_EXERCISE_ID = {
    "FISIO-001": "KNEE_EXTENSION_SEATED",
    "FISIO-002": "SHOULDER_PENDULUM",
    "FISIO-006": "SHOULDER_ABDUCTION_BAND",
    "FISIO-007": "ELBOW_FLEXION_LIGHT_DUMBBELL",
}

RISK_SYMBOLS = {
    "verde": "●",
    "atencao": "▲",
    "critico": "■",
}

_PAIN_LEVELS = ("muita_dor", "dor", "desconforto")


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Une intervalos sobrepostos para que uma fala não seja contada duas vezes."""
    valid_intervals = sorted(
        (max(0.0, start), max(0.0, end))
        for start, end in intervals
        if end > start
    )
    merged: list[tuple[float, float]] = []
    for start, end in valid_intervals:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _interval_duration(intervals: list[tuple[float, float]]) -> float:
    return sum(end - start for start, end in _merge_intervals(intervals))


def _build_pain_analysis(session: SessionDocument, events: list[EventDocument]) -> PainAnalysisSummary:
    """Calcula a proporção temporal de dor, tratando silêncio e indeterminado como sem dor."""
    video_duration = max(float(session.summary.duration_seconds), 0.0) if session.summary else 0.0
    pain_events = [
        event for event in events
        if event.tipo.value == "fala_dor"
        and (event.valores or {}).get("nivel") in _PAIN_LEVELS
    ]
    if video_duration <= 0:
        video_duration = max((event.instante_fim for event in events), default=0.0)
    video_duration = max(video_duration, 0.0)

    pain_intervals = [
        (event.instante_inicio, min(event.instante_fim, video_duration))
        for event in pain_events
    ]
    pain_duration = min(_interval_duration(pain_intervals), video_duration)
    no_pain_duration = max(video_duration - pain_duration, 0.0)

    by_level: dict[str, PainLevelSummary] = {}
    for level in _PAIN_LEVELS:
        level_events = [
            event for event in pain_events
            if (event.valores or {}).get("nivel") == level
        ]
        level_duration = min(
            _interval_duration([
                (event.instante_inicio, min(event.instante_fim, video_duration))
                for event in level_events
            ]),
            video_duration,
        )
        by_level[level] = PainLevelSummary(
            duracao_segundos=round(level_duration, 2),
            percentual_video=round(level_duration / video_duration * 100, 1) if video_duration else 0.0,
            ocorrencias=len(level_events),
        )

    return PainAnalysisSummary(
        duracao_video_segundos=round(video_duration, 2),
        duracao_com_dor_segundos=round(pain_duration, 2),
        percentual_com_dor=round(pain_duration / video_duration * 100, 1) if video_duration else 0.0,
        duracao_sem_dor_segundos=round(no_pain_duration, 2),
        percentual_sem_dor=round(no_pain_duration / video_duration * 100, 1) if video_duration else 100.0,
        por_nivel=by_level,
    )


EXERCISE_OPTIONS = [
    ExerciseOption(
        case_id="FISIO-001",
        exercise_id="KNEE_EXTENSION_SEATED",
        nome="Extensão de joelho sentado",
        lado_padrao="direito",
        requisitos=[],
    ),
    ExerciseOption(
        case_id="FISIO-002",
        exercise_id="SHOULDER_PENDULUM",
        nome="Pêndulo de ombro de Codman",
        lado_padrao="esquerdo",
        requisitos=["apoio estável"],
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


@router.get(
    "/exercicios",
    response_model=list[ExerciseOption],
    summary="Listar exercícios disponíveis para análise",
)
def list_exercises() -> list[ExerciseOption]:
    return EXERCISE_OPTIONS


@router.get(
    "/clips-referencia",
    response_model=list[ReferenceClipInfo],
    summary="Listar clipes de referência do dataset",
    description="Retorna a lista de clipes de teste do dataset de referência disponíveis para execução imediata.",
)
def list_reference_clips() -> list[ReferenceClipInfo]:
    return DatasetService().list_clips()


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
    analise_dor = _build_pain_analysis(session, events)
    equipment_config = detection_config(session.case_id or "")
    object_detection = (session.extra or {}).get("object_detection")
    equipamento = {
        "possui_equipamento": equipment_config is not None,
        "nome": equipment_config.display_name if equipment_config else "Nenhum",
    }
    if equipment_config:
        equipamento.update(
            percentual_total=(object_detection or {}).get("detection_percentage", 0.0),
            percentual_nao_detectado=(object_detection or {}).get("not_detected_percentage", 0.0),
            percentual_parcialmente_detectado=(object_detection or {}).get(
                "partially_detected_percentage", 0.0
            ),
            percentual_totalmente_detectado=(object_detection or {}).get(
                "fully_detected_percentage", 0.0
            ),
        )

    plano_doc = PlanRepository().get_plan_by_patient(session.paciente_id) if session.paciente_id else None
    laudo_doc = MedicalReportRepository().get_report_by_patient(session.paciente_id) if session.paciente_id else None

    plano_label = "Conforme prescrição" if deviations_count == 0 else f"{deviations_count} desvio(s) detectado(s)"
    if plano_doc:
        plano_label = (
            f"{plano_label} (Dor máx: {plano_doc.dor_maxima_aceitavel}/10 · "
            f"Amp: {plano_doc.amplitude_esperada_texto}°)"
        )

    laudo_label = "Amplitude dentro do limite" if score >= 80 else "Amplitude com restrições clínicas"
    if laudo_doc and laudo_doc.lesao:
        restricao_str = f" — {', '.join(laudo_doc.movimentos_restritos)}" if laudo_doc.movimentos_restritos else ""
        laudo_label = f"{laudo_label} ({laudo_doc.lesao}{restricao_str})"

    comparacao_clinica = {
        "plano": {
            "status": "ok" if deviations_count == 0 else "warn",
            "label": plano_label,
        },
        "laudo": {
            "status": "ok" if score >= 80 else "warn",
            "label": laudo_label,
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
        slot_id=session.slot_id,
        lgpd_aceite=session.lgpd_aceite if session.lgpd_aceite is not None else True,
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
        analise_dor=analise_dor,
        equipamento=equipamento,
        comparacao_clinica=comparacao_clinica,
        aviso_legal="Apoio à decisão, não diagnóstico.",
    )
