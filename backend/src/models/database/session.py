"""Modelos de documentos MongoDB para a coleção 'sessoes'."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from services.pose.models import SessionSummary


class SessionStatus(str, Enum):
    ENVIADO = "enviado"
    PROCESSANDO = "processando"
    CONCLUIDO = "concluido"
    ERRO = "erro"


class RiskClassification(str, Enum):
    VERDE = "verde"
    ATENCAO = "atencao"
    CRITICO = "critico"


class SessionDocument(BaseModel):
    """Documento persistido na coleção 'sessoes' do MongoDB."""

    session_id: str = Field(..., description="Identificador único da sessão (run_id)")
    paciente_id: Optional[str] = Field(default=None, description="Identificador sintético do paciente")
    exercicio_id: str = Field(..., description="Identificador do exercício (ex: FISIO-001)")
    case_id: str = Field(..., description="Identificador do caso clínico de referência")
    side_evaluated: str = Field(..., description="Lado avaliado: direito, esquerdo ou ambos")
    status: SessionStatus = Field(default=SessionStatus.CONCLUIDO, description="Status do processamento da sessão")
    etapa: str = Field(default="pose_concluida", description="Etapa atual da esteira de IA")
    risk_classification: RiskClassification = Field(
        default=RiskClassification.VERDE, description="Classificação clínica de risco/conformidade"
    )
    video_path: Optional[str] = Field(default=None, description="Caminho relativo do vídeo original")
    annotated_video_path: Optional[str] = Field(default=None, description="Caminho relativo do vídeo com HUD")
    analysis_path: Optional[str] = Field(default=None, description="Caminho relativo do analysis.json")
    compliance_score: Optional[float] = Field(
        default=None, description="Score percentual de conformidade (0-100%)"
    )
    target_repetitions: Optional[int] = Field(default=None, description="Meta de repetições prescritas")
    completed_repetitions: int = Field(default=0, description="Total de repetições completadas")
    valid_repetitions: int = Field(default=0, description="Repetições sem desvios graves")
    invalid_repetitions: int = Field(default=0, description="Repetições com desvios")
    total_deviations: int = Field(default=0, description="Total de desvios posturais detectados")
    summary: Optional[SessionSummary] = Field(default=None, description="Resumo técnico biomecânico da sessão")
    justificativas: list[str] = Field(
        default_factory=list, description="Justificativas clínicas explicáveis da classificação"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Data e hora de criação"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Data e hora da última atualização"
    )
    extra: dict[str, Any] = Field(default_factory=dict, description="Metadados adicionais da sessão")
