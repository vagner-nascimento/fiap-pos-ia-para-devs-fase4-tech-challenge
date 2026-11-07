"""Modelos de documentos MongoDB para a coleção 'sessoes'."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from models.database.processing import (
    PROCESSING_STEPS,
    ProcessingStep,
    default_processing_steps,
)
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
    slot_id: Optional[str] = Field(default=None, description="Identificador do slot na prescrição (ex: SLOT-1)")
    dia_tratamento: int = Field(
        default=1, ge=1, le=30, description="Dia de tratamento na jornada do plano (1..D)"
    )
    series_prescritas: int = Field(
        default=1, ge=1, le=20, description="Quantidade de séries prescritas para o exercício"
    )
    repeticoes_por_serie: int = Field(
        default=5, ge=1, le=50, description="Meta de repetições por série"
    )
    serie_index: Optional[int] = Field(
        default=None, description="Índice da série quando enviado por série individual"
    )
    exercicio_id: str = Field(..., description="Identificador do exercício (ex: FISIO-001)")
    case_id: str = Field(..., description="Identificador do caso clínico de referência")
    side_evaluated: str = Field(..., description="Lado avaliado: direito, esquerdo ou ambos")
    lgpd_aceite: bool = Field(
        default=True, description="Indica se o paciente aceitou o termo de consentimento LGPD (imagem e voz)"
    )
    original_filename: Optional[str] = Field(
        default=None, description="Nome original do arquivo de vídeo ou clipe enviado"
    )
    file_size_bytes: Optional[int] = Field(
        default=None, ge=0, description="Tamanho do arquivo de vídeo enviado em bytes"
    )
    status: SessionStatus = Field(default=SessionStatus.CONCLUIDO, description="Status do processamento da sessão")
    etapa: str = Field(default="result_persistence", description="Etapa atual da esteira de IA")
    processing_steps: list[ProcessingStep] = Field(
        default_factory=default_processing_steps,
        description="Etapas reais disponíveis para acompanhamento do processamento",
    )
    current_step: str = Field(default="video_received", description="Identificador da etapa atual")
    current_step_index: int = Field(default=0, ge=0, description="Índice da etapa atual")
    total_steps: int = Field(default=len(PROCESSING_STEPS), ge=1, description="Total de etapas reais")
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Progresso global da sessão")
    progress_message: Optional[str] = Field(default=None, description="Mensagem da etapa atual")
    error_message: Optional[str] = Field(default=None, description="Mensagem do erro de processamento")
    risk_classification: RiskClassification = Field(
        default=RiskClassification.VERDE, description="Classificação clínica de risco/conformidade"
    )
    video_path: Optional[str] = Field(default=None, description="Caminho relativo do vídeo original")
    annotated_video_path: Optional[str] = Field(default=None, description="Caminho relativo do vídeo com HUD")
    analysis_path: Optional[str] = Field(default=None, description="Caminho relativo do analysis.json")
    telemetry_path: Optional[str] = Field(default=None, description="Caminho relativo do telemetry.json")
    compliance_score: Optional[float] = Field(
        default=None, description="Score percentual de conformidade (0-100%)"
    )
    amplitude_maxima: Optional[float] = Field(
        default=None, description="Amplitude máxima atingida na sessão em graus"
    )
    amplitude_media: Optional[float] = Field(
        default=None, description="Amplitude média das repetições da sessão em graus"
    )
    consistencia_score: Optional[float] = Field(
        default=None, description="Score de consistência biomecânica e regularidade entre séries (0-100%)"
    )
    dor_score_0_10: float = Field(
        default=0.0, ge=0.0, le=10.0, description="Nível de dor consolidado da sessão na escala 0-10"
    )
    dor_percentual_tempo: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Percentual de tempo do vídeo com dor"
    )
    series_breakdown: list[dict[str, Any]] = Field(
        default_factory=list, description="Detalhamento das métricas por série (Série 1..N)"
    )
    avaliado_fisioterapeuta: bool = Field(
        default=False, description="Indica se a sessão foi avaliada pelo fisioterapeuta"
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
