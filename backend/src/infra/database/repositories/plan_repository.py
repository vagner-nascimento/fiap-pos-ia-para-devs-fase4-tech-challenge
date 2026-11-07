"""Repositório MongoDB para a coleção 'planos'."""

import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo.collection import Collection

from infra.database.mongodb_client import get_collection
from models.database.plan import PlanDocument

logger = logging.getLogger(__name__)


class PlanRepository:
    """Acesso e persistência a documentos na coleção 'planos'."""

    COLLECTION_NAME = "planos"

    def __init__(self, collection: Optional[Collection] = None):
        self._collection = collection

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._collection = get_collection(self.COLLECTION_NAME)
        return self._collection

    def save_plan(self, plan: PlanDocument) -> PlanDocument:
        """Insere ou atualiza (upsert) o plano de prescrição de exercícios do paciente."""
        doc = plan.model_dump(mode="json")
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()

        self.collection.update_one(
            {"paciente_id": plan.paciente_id},
            {"$set": doc},
            upsert=True,
        )
        logger.info(
            "Plano '%s' do paciente '%s' (%d exercícios) persistido na coleção 'planos'.",
            plan.plano_id,
            plan.paciente_id,
            len(plan.exercicios),
        )
        return self.get_plan_by_patient(plan.paciente_id) or plan

    def get_plan_by_patient(self, paciente_id: str) -> Optional[PlanDocument]:
        """Recupera o plano de exercícios ativo associado ao paciente_id."""
        doc = self.collection.find_one({"paciente_id": paciente_id}, {"_id": 0})
        if not doc:
            return None
        return PlanDocument.model_validate(doc)

    def mark_evolution_evaluated(
        self,
        paciente_id: str,
        avaliado: bool = True,
        observacoes: Optional[str] = None,
    ) -> Optional[PlanDocument]:
        """Registra a avaliação final do médico/fisioterapeuta sobre a evolução do plano."""
        now = datetime.now(timezone.utc).isoformat()
        update_fields: dict = {
            "avaliado_evolucao": avaliado,
            "updated_at": now,
        }
        if observacoes is not None:
            update_fields["observacoes_avaliacao_final"] = observacoes
        result = self.collection.update_one(
            {"paciente_id": paciente_id},
            {"$set": update_fields},
        )
        if result.matched_count == 0:
            return None
        return self.get_plan_by_patient(paciente_id)

