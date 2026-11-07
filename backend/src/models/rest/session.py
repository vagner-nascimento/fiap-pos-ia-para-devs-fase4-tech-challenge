from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class CreateSessionResponse(BaseModel):
    """Resposta ao criar ou enfileirar uma sessão para processamento."""

    session_id: str = Field(..., description="ID único gerado para a sessão")
    status: str = Field(..., description="Status atual ('processando', 'concluido' ou 'enviado')")
    etapa: str = Field(..., description="Etapa atual do fluxo de processamento")
    message: str = Field(..., description="Mensagem informativa sobre o processamento")
    paciente_id: Optional[str] = Field(default=None, description="ID do paciente vinculado")
    slot_id: Optional[str] = Field(default=None, description="Identificador do slot na prescrição (ex: 'SLOT-1')")
    dia_tratamento: int = Field(default=1, ge=1, description="Dia de tratamento na jornada do plano (1..D)")
    series_prescritas: int = Field(default=1, ge=1, description="Séries prescritas para o exercício")
    repeticoes_por_serie: int = Field(default=5, ge=1, description="Repetições por série")
    serie_index: Optional[int] = Field(default=None, description="Índice da série quando enviado individualmente")
    exercicio_id: str = Field(..., description="Exercício selecionado")
    lgpd_aceite: bool = Field(default=True, description="Registro de aceite do termo LGPD")
    created_at: str = Field(..., description="Timestamp de criação")


class CreateSessionPayload(BaseModel):
    """Payload JSON para criar uma sessão a partir de clipe do dataset ou caminho local."""

    exercicio_id: str = Field(..., description="Identificador do caso ou exercício (ex: 'FISIO-001')")
    paciente_id: Optional[str] = Field(None, description="Identificador sintético do paciente (ex: 'PAC-001')")
    slot_id: Optional[str] = Field(None, description="Identificador do slot da prescrição (ex: 'SLOT-1')")
    dia_tratamento: int = Field(1, ge=1, le=30, description="Dia de tratamento na jornada do plano (1..D)")
    series_prescritas: int = Field(1, ge=1, le=20, description="Quantidade de séries prescritas")
    repeticoes_por_serie: int = Field(5, ge=1, le=50, description="Meta de repetições por série")
    serie_index: Optional[int] = Field(None, description="Índice da série quando enviado por série individual")
    dataset_clip: Optional[str] = Field(
        None, description="Nome do clipe de referência do dataset (ex: 'FISIO-001-correto.mp4')"
    )
    side: Optional[str] = Field("auto", description="Lado do exercício: 'auto', 'direito', 'esquerdo', 'ambos'")
    target_repetitions: Optional[int] = Field(5, description="Número de repetições prescritas (alvo)")
    lgpd_aceite: bool = Field(True, description="Confirmação do termo de consentimento LGPD")
    run_id: Optional[str] = Field(None, description="ID customizado opcional para a sessão")


class ReferenceClipInfo(BaseModel):
    """Metadados de clipe de teste do dataset de referência."""

    case_id: str
    exercicio_id: str
    exercicio_nome: str
    filename: str
    tipo: str
    descricao: str


class DatasetStatusResponse(BaseModel):
    status: str
    message: Optional[str] = None
    case_count: int = 0
    clip_count: int = 0


class ExerciseOption(BaseModel):
    """Exercício disponível para seleção antes do processamento do vídeo."""

    case_id: str
    exercise_id: str
    nome: str
    lado_padrao: str
    requisitos: list[str] = Field(default_factory=list)
    objeto_deteccao: Optional[str] = Field(
        default=None,
        description="Objeto YOLO obrigatório, quando aplicável ao exercício",
    )


class PainLevelSummary(BaseModel):
    """Resumo da ocorrência de um nível de dor durante o vídeo."""

    duracao_segundos: float = 0.0
    percentual_video: float = 0.0
    ocorrencias: int = 0


class PainAnalysisSummary(BaseModel):
    """Resumo temporal da dor e da ausência de dor na sessão."""

    duracao_video_segundos: float = 0.0
    duracao_com_dor_segundos: float = 0.0
    percentual_com_dor: float = 0.0
    duracao_sem_dor_segundos: float = 0.0
    percentual_sem_dor: float = 100.0
    por_nivel: dict[str, PainLevelSummary] = Field(default_factory=dict)
    indeterminado_incluido_como_sem_dor: bool = True


class EquipmentAnalysisSummary(BaseModel):
    """Resumo da detecção do equipamento exigido pelo exercício."""

    possui_equipamento: bool = False
    nome: str = "Nenhum"
    percentual_total: Optional[float] = None
    percentual_nao_detectado: Optional[float] = None
    percentual_parcialmente_detectado: Optional[float] = None
    percentual_totalmente_detectado: Optional[float] = None


class SessionReportResponse(BaseModel):
    """Relatório individual da sessão estruturado para a interface e impressão de laudo."""

    session_id: str
    paciente_id: Optional[str] = None
    slot_id: Optional[str] = None
    dia_tratamento: int = 1
    series_prescritas: int = 1
    repeticoes_por_serie: int = 5
    serie_index: Optional[int] = None
    lgpd_aceite: bool = True
    avaliado_fisioterapeuta: bool = False
    exercicio_id: str
    exercicio_nome: str
    case_id: Optional[str] = None
    side_evaluated: Optional[str] = None
    created_at: Optional[str | datetime] = None
    status: str
    compliance_score: Optional[float] = None
    amplitude_maxima: Optional[float] = None
    amplitude_media: Optional[float] = None
    consistencia_score: Optional[float] = None
    dor_score_0_10: float = 0.0
    series_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    risk_classification: Optional[str] = None
    risk_symbol: Optional[str] = None
    justificativas: list[str] = Field(default_factory=list)
    target_repetitions: Optional[int] = None
    valid_repetitions: int = 0
    invalid_repetitions: int = 0
    total_deviations: int = 0
    annotated_video_url: Optional[str] = None
    analysis_json_url: Optional[str] = None
    telemetry_json_url: Optional[str] = None
    evidence_urls: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    analise_dor: PainAnalysisSummary = Field(default_factory=PainAnalysisSummary)
    equipamento: EquipmentAnalysisSummary = Field(default_factory=EquipmentAnalysisSummary)
    comparacao_clinica: dict = Field(default_factory=dict)
    aviso_legal: str = "Apoio à decisão, não diagnóstico."
