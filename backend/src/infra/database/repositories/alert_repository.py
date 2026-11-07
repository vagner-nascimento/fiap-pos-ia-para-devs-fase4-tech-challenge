"""Repositório MongoDB para a coleção 'alertas'."""

import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo.collection import Collection

from infra.database.mongodb_client import get_collection
from models.database.alert import AlertDocument, AlertSeverity, AlertStatus

logger = logging.getLogger(__name__)


class AlertRepository:
    """Acesso e persistência a documentos na coleção 'alertas'."""

    COLLECTION_NAME = "alertas"

    def __init__(self, collection: Optional[Collection] = None):
        self._collection = collection

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._collection = get_collection(self.COLLECTION_NAME)
        return self._collection

    def count_alerts(self) -> int:
        """Retorna o total de documentos cadastrados na coleção 'alertas'."""
        return int(self.collection.count_documents({}))

    def save_alert(self, alert: AlertDocument) -> AlertDocument:
        """Insere ou atualiza (upsert) um alerta pelo alerta_id."""
        doc = alert.model_dump(mode="json")
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        self.collection.update_one(
            {"alerta_id": alert.alerta_id},
            {"$set": doc},
            upsert=True,
        )
        logger.info("Alerta '%s' (%s) persistido na coleção 'alertas'.", alert.alerta_id, alert.severidade.value)
        return self.get_alert(alert.alerta_id) or alert

    def get_alert(self, alerta_id: str) -> Optional[AlertDocument]:
        """Recupera um alerta pelo seu alerta_id."""
        doc = self.collection.find_one({"alerta_id": alerta_id}, {"_id": 0})
        if not doc:
            return None
        return AlertDocument.model_validate(doc)

    def list_alerts(
        self,
        paciente_id: Optional[str] = None,
        severidade: Optional[AlertSeverity | str] = None,
        estado: Optional[AlertStatus | str] = None,
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[AlertDocument]:
        """Lista os alertas mais recentes com filtros opcionais."""
        query: dict = {}
        if paciente_id:
            query["paciente_id"] = paciente_id
        if severidade:
            query["severidade"] = severidade.value if isinstance(severidade, AlertSeverity) else severidade
        if estado:
            query["estado"] = estado.value if isinstance(estado, AlertStatus) else estado
        if session_id:
            query["session_id"] = session_id

        cursor = self.collection.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        return [AlertDocument.model_validate(doc) for doc in cursor]

    def update_alert_status(
        self, alerta_id: str, estado: AlertStatus | str
    ) -> Optional[AlertDocument]:
        """Atualiza o estado operacional de um alerta ('novo', 'lido' ou 'tratado')."""
        estado_val = estado.value if isinstance(estado, AlertStatus) else str(estado)
        now = datetime.now(timezone.utc).isoformat()
        result = self.collection.update_one(
            {"alerta_id": alerta_id},
            {"$set": {"estado": estado_val, "updated_at": now}},
        )
        if result.matched_count == 0:
            return None
        return self.get_alert(alerta_id)

    def mark_session_alerts_treated(self, session_id: str) -> int:
        """Marca todos os alertas associados a uma sessão como 'tratado'."""
        now = datetime.now(timezone.utc).isoformat()
        result = self.collection.update_many(
            {"session_id": session_id},
            {"$set": {"estado": AlertStatus.TRATADO.value, "updated_at": now}},
        )
        return int(result.modified_count)

    def mark_patient_alerts_treated(self, paciente_id: str) -> int:
        """Marca todos os alertas pendentes de um paciente como 'tratado'."""
        now = datetime.now(timezone.utc).isoformat()
        result = self.collection.update_many(
            {"paciente_id": paciente_id},
            {"$set": {"estado": AlertStatus.TRATADO.value, "updated_at": now}},
        )
        return int(result.modified_count)

