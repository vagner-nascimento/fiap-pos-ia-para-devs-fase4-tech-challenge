"""Modelos de documentos MongoDB para a coleção 'eventos'."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    REPETICAO = "repeticao"
    DESVIO = "desvio"
    DOR_FACIAL = "dor_facial"
    FALA_DOR = "fala_dor"
    INCONSISTENCIA = "inconsistencia"


class EventDocument(BaseModel):
    """Documento persistido na coleção 'eventos' do MongoDB."""

    session_id: str = Field(..., description="ID da sessão vinculada a este evento")
    tipo: EventType = Field(..., description="Tipo de evento detectado")
    instante_inicio: float = Field(..., description="Timestamp de início em segundos")
    instante_fim: float = Field(..., description="Timestamp de fim em segundos")
    instante_pico: Optional[float] = Field(default=None, description="Timestamp de pico de esforço/desvio")
    duracao: Optional[float] = Field(default=None, description="Duração do evento em segundos")
    valores: dict[str, Any] = Field(
        default_factory=dict, description="Valores numéricos e métricas (ângulos, frames, flags)"
    )
    evidencia: dict[str, Any] = Field(
        default_factory=dict, description="Dados de evidência (caminho do frame snapshot, transcrição)"
    )
    descricao: Optional[str] = Field(default=None, description="Descrição legível para o fisioterapeuta")
    severidade: Optional[str] = Field(default=None, description="Severidade do desvio (leve, moderada, grave)")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Timestamp de gravação do evento"
    )
