"""Modelos Pydantic de requisição e resposta REST para pacientes, planos, laudos, evolução e alertas."""

from typing import Any, Optional
from pydantic import BaseModel, Field

from models.database.alert import AlertDocument
from models.database.medical_report import MedicalReportDocument
from models.database.patient import PatientDocument
from models.database.plan import PlanDocument, PrescribedExerciseItem
from models.database.session import SessionDocument


class CreateOrUpdatePatientRequest(BaseModel):
    """Payload para criar ou atualizar um paciente sintético."""

    paciente_id: Optional[str] = Field(
        default=None, description="ID sintético do paciente (ex: PAC-001). Se omitido, será gerado automaticamente."
    )
    nome: str = Field(..., min_length=2, description="Nome fictício do paciente (ex: Marina T.)")
    idade: Optional[int] = Field(default=None, ge=0, le=120, description="Idade fictícia em anos")
    observacoes: Optional[str] = Field(default=None, description="Observações gerais do paciente")


class ExtractReportPreviewRequest(BaseModel):
    """Payload para extrair automaticamente entidades a partir do texto do laudo."""

    texto_original: str = Field(..., description="Texto livre do laudo clínico")


class ExtractReportPreviewResponse(BaseModel):
    """Resposta da extração automática de entidades do laudo."""

    texto_original: str
    regiao: Optional[str] = None
    lesao: Optional[str] = None
    movimentos_restritos: list[str] = Field(default_factory=list)
    limite_amplitude_max: Optional[float] = None


class SaveMedicalReportRequest(BaseModel):
    """Payload para salvar ou atualizar o laudo de um paciente."""

    texto_original: str = Field(..., min_length=3, description="Texto livre do laudo médico")
    regiao: Optional[str] = Field(
        default=None, description="Região anatômica revisada (se omitida, usa a extraída automaticamente)"
    )
    lesao: Optional[str] = Field(
        default=None, description="Lesão/condição revisada (se omitida, usa a extraída automaticamente)"
    )
    movimentos_restritos: Optional[list[str]] = Field(
        default=None, description="Lista de movimentos restritos revisados (se omitida, usa a extraída)"
    )
    limite_amplitude_max: Optional[float] = Field(
        default=None, description="Limite angular máximo seguro em graus"
    )
    observacoes_restricao: Optional[str] = Field(default=None, description="Notas complementares de restrição")
    revisado_profissional: bool = Field(
        default=False, description="Indica se o profissional confirmou/editou os campos extraídos"
    )


class PrescribedExerciseInput(BaseModel):
    """Item de exercício enviado ao criar/atualizar um plano de tratamento."""

    slot_id: Optional[str] = Field(default=None, description="Identificador do slot (gerado se omitido)")
    exercicio_id: str = Field(..., description="Código do caso/exercício (ex: FISIO-006)")
    series: int = Field(default=3, ge=1, le=20, description="Número de séries prescritas")
    repeticoes: int = Field(default=10, ge=1, le=50, description="Meta de repetições por série")
    dia_tratamento: Optional[int] = Field(
        default=None, ge=1, le=30, description="Dia específico do tratamento (1..N) quando vinculado a um único dia"
    )
    dias_prescritos: Optional[list[int]] = Field(
        default=None, description="Lista de dias do tratamento em que este exercício é prescrito (ex: [1, 2, 3] ou [1, 3])"
    )
    lado: Optional[str] = Field(default=None, description="Lado prescrito: direito, esquerdo, ambos ou auto")
    equipamento: Optional[str] = Field(default=None, description="Equipamento associado ao exercício")
    instrucoes: Optional[str] = Field(default=None, description="Instruções específicas para execução")


class SavePlanRequest(BaseModel):
    """Payload para criar ou atualizar o plano de exercícios de um paciente."""

    dias_tratamento: int = Field(
        default=3, ge=1, le=30, description="Quantidade de dias de tratamento previstos no plano"
    )
    dor_maxima_aceitavel: int = Field(
        default=4, ge=0, le=10, description="Limite máximo de dor aceitável (0 a 10)"
    )
    amplitude_esperada_texto: str = Field(
        default="60 – 90", description="Faixa de amplitude esperada em graus (ex: '60 – 90')"
    )
    amplitude_esperada_min: Optional[float] = Field(default=None, description="Amplitude mínima em graus")
    amplitude_esperada_max: Optional[float] = Field(default=None, description="Amplitude máxima em graus")
    exercicios: list[PrescribedExerciseInput] = Field(
        default_factory=list, description="Lista de exercícios prescritos para o paciente"
    )


class PatientClinicalBundleResponse(BaseModel):
    """Visão consolidada do paciente com seu laudo, plano de prescrição e sessões recentes."""

    patient: PatientDocument
    laudo: Optional[MedicalReportDocument] = None
    plano: Optional[PlanDocument] = None
    sessoes_recentes: list[SessionDocument] = Field(
        default_factory=list,
        description="Histórico de sessões recentes enviadas ou concluídas pelo paciente",
    )


class ExerciseSessionPoint(BaseModel):
    """Ponto evolutivo de uma sessão/dia dentro de um exercício prescrito."""

    session_id: str
    dia_tratamento: int = 1
    created_at: Optional[str] = None
    status: str = "concluido"
    series_prescritas: int = 1
    repeticoes_por_serie: int = 5
    target_repetitions: int = 5
    completed_repetitions: int = 0
    valid_repetitions: int = 0
    invalid_repetitions: int = 0
    total_deviations: int = 0
    amplitude_media: float = 0.0
    amplitude_maxima: float = 0.0
    consistencia_score: float = 0.0
    compliance_score: float = 0.0
    dor_score_0_10: float = 0.0
    dor_percentual_tempo: float = 0.0
    risk_classification: str = "verde"
    risk_symbol: str = "●"
    series_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    avaliado_fisioterapeuta: bool = False


class ExerciseEvolutionSeries(BaseModel):
    """Evolução longitudinal de um exercício específico prescrito no plano (SLOT-1..N)."""

    slot_id: str
    exercicio_id: str
    exercicio_nome: str
    lado: str = "auto"
    equipamento: Optional[str] = None
    series_prescritas: int = 3
    repeticoes_por_serie: int = 10
    total_repeticoes_dia: int = 30
    dias_prescritos: list[int] = Field(default_factory=list)
    dias_executados: int = 0
    dias_previstos: int = 3
    amplitude_inicial: Optional[float] = None
    amplitude_atual: Optional[float] = None
    amplitude_delta: float = 0.0
    amplitude_tendencia: str = "estavel"
    consistencia_inicial: Optional[float] = None
    consistencia_atual: Optional[float] = None
    consistencia_delta: float = 0.0
    consistencia_tendencia: str = "estavel"
    dor_inicial: Optional[float] = None
    dor_atual: Optional[float] = None
    dor_delta: float = 0.0
    dor_tendencia: str = "estavel"
    status_evolucao: str = "ok"
    resumo_exercicio: str = ""
    sessoes: list[ExerciseSessionPoint] = Field(default_factory=list)


class DayEvolutionSummary(BaseModel):
    """Resumo consolidado de todos os exercícios executados pelo paciente em um Dia de Tratamento (1..D)."""

    dia_tratamento: int
    label: str
    exercicios_concluidos: int = 0
    exercicios_prescritos: int = 0
    total_repeticoes_prescritas: int = 0
    total_repeticoes_realizadas: int = 0
    total_repeticoes_validas: int = 0
    amplitude_media_dia: float = 0.0
    amplitude_maxima_dia: float = 0.0
    consistencia_media_dia: float = 0.0
    dor_media_dia_0_10: float = 0.0
    dor_maxima_dia_0_10: float = 0.0
    total_desvios_dia: int = 0
    risk_classification: str = "verde"
    risk_symbol: str = "●"
    concluido: bool = False


class EvolutionGlobalMetrics(BaseModel):
    """KPIs globais da evolução do paciente em Amplitude, Consistência e Nível de Dor."""

    dias_previstos: int = 3
    dias_concluidos: int = 0
    total_sessoes_concluidas: int = 0
    total_sessoes_previstas: int = 0
    percentual_adesao_plano: float = 0.0

    amplitude_inicial: float = 0.0
    amplitude_atual: float = 0.0
    amplitude_maxima_atingida: float = 0.0
    amplitude_delta: float = 0.0
    amplitude_tendencia: str = "estavel"
    amplitude_status_plano: str = "ok"
    amplitude_status_laudo: str = "ok"

    consistencia_inicial: float = 0.0
    consistencia_atual: float = 0.0
    consistencia_media_global: float = 0.0
    consistencia_delta: float = 0.0
    consistencia_tendencia: str = "estavel"

    dor_inicial_0_10: float = 0.0
    dor_atual_0_10: float = 0.0
    dor_maxima_registrada_0_10: float = 0.0
    dor_delta_0_10: float = 0.0
    dor_tendencia: str = "estavel"
    dor_acima_limite_ocorrencias: int = 0

    classificacao_geral: str = "verde"
    simbolo_geral: str = "●"
    label_geral: str = "Evolução favorável"


class PatientEvolutionReportResponse(BaseModel):
    """Relatório Final de Evolução Longitudinal do Paciente (Issue #7)."""

    patient: PatientDocument
    laudo: Optional[MedicalReportDocument] = None
    plano: Optional[PlanDocument] = None
    metricas_globais: EvolutionGlobalMetrics
    evolucao_por_dia: list[DayEvolutionSummary] = Field(default_factory=list)
    evolucao_por_exercicio: list[ExerciseEvolutionSeries] = Field(default_factory=list)
    parecer_clinico: list[str] = Field(default_factory=list)
    recomendacoes_plano: list[str] = Field(default_factory=list)
    alertas_paciente: list[AlertDocument] = Field(default_factory=list)
    avaliado_evolucao: bool = False
    observacoes_avaliacao_final: Optional[str] = None
    aviso_legal: str = "Apoio à decisão clínica longitudinal, não diagnóstico médico."


class EvaluateEvolutionRequest(BaseModel):
    """Payload para registrar a avaliação médica/fisioterapêutica do relatório final de evolução."""

    avaliado: bool = True
    observacoes: Optional[str] = Field(
        default=None, description="Parecer final ou observações clínicas registradas pelo profissional"
    )


class AlertSummaryCounters(BaseModel):
    """Contadores consolidados de alertas para o cabeçalho do Painel de Alertas."""

    total: int = 0
    novos: int = 0
    lidos: int = 0
    tratados: int = 0
    criticos: int = 0
    atencao: int = 0
    verdes: int = 0


class AlertsListResponse(BaseModel):
    """Resposta do Painel de Alertas (Tela 6 — Mock 05-Painel-Alertas.dc.html)."""

    contadores: AlertSummaryCounters
    alertas: list[AlertDocument] = Field(default_factory=list)


class UpdateAlertStatusRequest(BaseModel):
    """Payload para atualizar o estado de um alerta ('novo', 'lido' ou 'tratado')."""

    estado: str = Field(..., description="Novo estado operacional: 'novo', 'lido' ou 'tratado'")

