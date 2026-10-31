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
from models.rest.session import CreateSessionPayload, CreateSessionResponse
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
