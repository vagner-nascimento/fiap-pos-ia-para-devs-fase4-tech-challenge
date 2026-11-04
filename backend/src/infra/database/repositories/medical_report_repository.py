"""Repositório MongoDB para a coleção 'laudos'."""

import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo.collection import Collection

from infra.database.mongodb_client import get_collection
from models.database.medical_report import MedicalReportDocument

logger = logging.getLogger(__name__)


class MedicalReportRepository:
    """Acesso e persistência a documentos na coleção 'laudos'."""

    COLLECTION_NAME = "laudos"

    def __init__(self, collection: Optional[Collection] = None):
        self._collection = collection

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._collection = get_collection(self.COLLECTION_NAME)
        return self._collection

    def save_report(self, report: MedicalReportDocument) -> MedicalReportDocument:
        """Insere ou atualiza (upsert) o laudo médico de um paciente (por paciente_id)."""
        doc = report.model_dump(mode="json")
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        self.collection.update_one(
            {"paciente_id": report.paciente_id},
            {"$set": doc},
            upsert=True,
        )
        logger.info(
            "Laudo '%s' do paciente '%s' persistido na coleção 'laudos'.",
            report.laudo_id,
            report.paciente_id,
        )
        return self.get_report_by_patient(report.paciente_id) or report

    def get_report_by_patient(self, paciente_id: str) -> Optional[MedicalReportDocument]:
        """Recupera o laudo médico mais recente associado ao paciente_id."""
        doc = self.collection.find_one({"paciente_id": paciente_id}, {"_id": 0})
        if not doc:
            return None
        return MedicalReportDocument.model_validate(doc)

