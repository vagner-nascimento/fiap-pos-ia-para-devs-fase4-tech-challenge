"""Modelos de documentos MongoDB para a coleção 'alertas'."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    CRITICO = "critico"
    ATENCAO = "atencao"
    VERDE = "verde"


class AlertStatus(str, Enum):
    NOVO = "novo"
    LIDO = "lido"
    TRATADO = "tratado"


class AlertDocument(BaseModel):
    """Documento persistido na coleção 'alertas' do MongoDB (PRD v1.2 seção 6.4)."""

    alerta_id: str = Field(..., description="Identificador único do alerta (ex: ALT-001)")
    paciente_id: str = Field(..., description="Identificador do paciente vinculado")
    paciente_nome: Optional[str] = Field(default=None, description="Nome fictício do paciente")
    session_id: Optional[str] = Field(default=None, description="Sessão associada ao alerta")
    slot_id: Optional[str] = Field(default=None, description="Slot da prescrição (ex: SLOT-1)")
    exercicio_id: Optional[str] = Field(default=None, description="Código do exercício (ex: FISIO-006)")
    dia_tratamento: Optional[int] = Field(default=None, description="Dia de tratamento associado")
    severidade: AlertSeverity = Field(
        default=AlertSeverity.ATENCAO, description="Severidade clínica: critico, atencao ou verde"
    )
    tipo: str = Field(
        default="anomalia_execucao",
        description="Categoria do alerta (dor_acima_limite, violacao_laudo, queda_amplitude, desvio_grave, evolucao)",
    )
    titulo: str = Field(..., description="Título curto do alerta para o fisioterapeuta")
    motivo: str = Field(..., description="Explicação clínica detalhada que originou o alerta")
    evidencia_resumo: Optional[str] = Field(
        default=None, description="Resumo da evidência (frame, fala transcrita, variação angular)"
    )
    estado: AlertStatus = Field(
        default=AlertStatus.NOVO, description="Estado operacional: novo, lido ou tratado"
    )
    canais_enviados: list[str] = Field(
        default_factory=lambda: ["painel_alertas"],
        description="Canais pelos quais o alerta foi disponibilizado",
    )
    synthetic: bool = Field(default=True, description="Indica dado sintético de demonstração")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Data e hora de geração"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Data e hora da última atualização"
    )

