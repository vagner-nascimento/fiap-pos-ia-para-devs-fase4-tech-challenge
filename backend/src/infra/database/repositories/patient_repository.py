"""Repositório MongoDB para a coleção 'pacientes'."""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from pymongo.collection import Collection

from infra.database.mongodb_client import get_collection
from models.database.patient import PatientDocument

logger = logging.getLogger(__name__)


class PatientRepository:
    """Acesso e persistência a documentos na coleção 'pacientes'."""

    COLLECTION_NAME = "pacientes"

    def __init__(self, collection: Optional[Collection] = None):
        self._collection = collection

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._collection = get_collection(self.COLLECTION_NAME)
        return self._collection

    def save_patient(self, patient: PatientDocument) -> PatientDocument:
        """Insere ou atualiza (upsert) um paciente com base no paciente_id."""
        doc = patient.model_dump(mode="json")
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        self.collection.update_one(
            {"paciente_id": patient.paciente_id},
            {"$set": doc},
            upsert=True,
        )
        logger.info("Paciente '%s' (%s) persistido na coleção 'pacientes'.", patient.paciente_id, patient.nome)
        return self.get_patient(patient.paciente_id) or patient

    def get_patient(self, paciente_id: str) -> Optional[PatientDocument]:
        """Recupera um paciente pelo paciente_id."""
        doc = self.collection.find_one({"paciente_id": paciente_id}, {"_id": 0})
        if not doc:
            return None
        return PatientDocument.model_validate(doc)

    def list_patients(self, nome_query: Optional[str] = None, limit: int = 100) -> list[PatientDocument]:
        """Lista pacientes cadastrados, com filtro opcional insensível a maiúsculas por nome ou ID."""
        query: dict = {}
        if nome_query and nome_query.strip():
            escaped = re.escape(nome_query.strip())
            query = {
                "$or": [
                    {"nome": {"$regex": escaped, "$options": "i"}},
                    {"paciente_id": {"$regex": escaped, "$options": "i"}},
                ]
            }
        cursor = self.collection.find(query, {"_id": 0}).sort("paciente_id", 1).limit(limit)
        return [PatientDocument.model_validate(doc) for doc in cursor]

    def count_patients(self) -> int:
        """Retorna o total de pacientes na coleção."""
        return self.collection.count_documents({})

