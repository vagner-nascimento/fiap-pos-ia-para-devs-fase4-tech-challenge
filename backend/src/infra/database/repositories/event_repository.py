"""Repositório MongoDB para a coleção 'eventos'."""

import logging
from typing import Optional

from pymongo.collection import Collection

from infra.database.mongodb_client import get_collection
from models.database.event import EventDocument, EventType

logger = logging.getLogger(__name__)


class EventRepository:
    """Acesso e persistência a documentos na coleção 'eventos'."""

    COLLECTION_NAME = "eventos"

    def __init__(self, collection: Optional[Collection] = None):
        self._collection = collection

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._collection = get_collection(self.COLLECTION_NAME)
        return self._collection

    def save_events(self, events: list[EventDocument]) -> int:
        """Salva uma lista de eventos da sessão em lote (batch insert)."""
        if not events:
            return 0

        docs = [event.model_dump(mode="json") for event in events]
        result = self.collection.insert_many(docs)
        inserted_count = len(result.inserted_ids)
        logger.info("%d eventos salvos com sucesso na coleção 'eventos'.", inserted_count)
        return inserted_count

    def list_events_by_session(
        self, session_id: str, tipo: Optional[EventType | str] = None
    ) -> list[EventDocument]:
        """Lista todos os eventos de uma determinada sessão, com filtro opcional por tipo."""
        query: dict = {"session_id": session_id}
        if tipo is not None:
            query["tipo"] = tipo.value if isinstance(tipo, EventType) else tipo

        cursor = self.collection.find(query, {"_id": 0}).sort("instante_inicio", 1)
        return [EventDocument.model_validate(doc) for doc in cursor]

    def delete_events_by_session(self, session_id: str) -> int:
        """Remove todos os eventos vinculados a uma sessão."""
        result = self.collection.delete_many({"session_id": session_id})
        return result.deleted_count
