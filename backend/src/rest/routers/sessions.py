"""Endpoints REST para consulta de sessões e eventos biomecânicos."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from infra.database.repositories.event_repository import EventRepository
from infra.database.repositories.session_repository import SessionRepository
from models.database.event import EventDocument
from models.database.session import SessionDocument

router = APIRouter(prefix="/sessoes", tags=["Sessões e Biomecânica"])


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
    # Valida existência da sessão
    session_repo = SessionRepository()
    if not session_repo.get_session(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão com ID '{session_id}' não encontrada.",
        )

    event_repo = EventRepository()
    return event_repo.list_events_by_session(session_id=session_id, tipo=tipo)
