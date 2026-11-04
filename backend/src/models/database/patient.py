"""Modelos de documentos MongoDB para a coleção 'pacientes'."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class PatientDocument(BaseModel):
    """Documento persistido na coleção 'pacientes' do MongoDB (dados sintéticos)."""

    paciente_id: str = Field(..., description="Identificador único sintético do paciente (ex: PAC-001)")
    nome: str = Field(..., description="Nome fictício do paciente (ex: Marina T.)")
    idade: Optional[int] = Field(default=None, ge=0, le=120, description="Idade em anos (fictícia)")
    observacoes: Optional[str] = Field(default=None, description="Observações clínicas gerais")
    synthetic: bool = Field(default=True, description="Indica que os dados são 100% sintéticos (LGPD)")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Data e hora de criação"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Data e hora da última atualização"
    )

