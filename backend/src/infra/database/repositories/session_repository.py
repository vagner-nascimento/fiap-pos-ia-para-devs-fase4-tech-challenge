"""Repositório MongoDB para a coleção 'sessoes'."""

import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo.collection import Collection

from infra.database.mongodb_client import get_collection
from models.database.session import SessionDocument, SessionStatus

logger = logging.getLogger(__name__)


class SessionRepository:
    """Acesso e persistência a documentos na coleção 'sessoes'."""

    COLLECTION_NAME = "sessoes"

    def __init__(self, collection: Optional[Collection] = None):
        self._collection = collection

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._collection = get_collection(self.COLLECTION_NAME)
        return self._collection

    def save_session(self, session: SessionDocument) -> str:
        """Insere ou atualiza (upsert) a sessão com base no session_id."""
        doc = session.model_dump(mode="json")
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        self.collection.update_one(
            {"session_id": session.session_id},
            {"$set": doc},
            upsert=True,
        )
        logger.info("Sessão '%s' persistida com sucesso na coleção 'sessoes'.", session.session_id)
        return session.session_id

    def get_session(self, session_id: str) -> Optional[SessionDocument]:
        """Recupera uma sessão pelo session_id."""
        doc = self.collection.find_one({"session_id": session_id}, {"_id": 0})
        if not doc:
            return None
        return SessionDocument.model_validate(doc)

    def list_sessions(self, paciente_id: Optional[str] = None, limit: int = 50) -> list[SessionDocument]:
        """Lista as sessões mais recentes, com filtro opcional por paciente."""
        query = {"paciente_id": paciente_id} if paciente_id else {}
        cursor = self.collection.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        return [SessionDocument.model_validate(doc) for doc in cursor]

    def update_status(self, session_id: str, status: SessionStatus, etapa: Optional[str] = None) -> bool:
        """Atualiza o status e etapa de processamento da sessão."""
        update_fields: dict = {
            "status": status.value if isinstance(status, SessionStatus) else status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if etapa is not None:
            update_fields["etapa"] = etapa

        result = self.collection.update_one(
            {"session_id": session_id},
            {"$set": update_fields},
        )
        return result.matched_count > 0

    def delete_session(self, session_id: str) -> bool:
        """Remove uma sessão pelo seu ID."""
        result = self.collection.delete_one({"session_id": session_id})
        return result.deleted_count > 0
