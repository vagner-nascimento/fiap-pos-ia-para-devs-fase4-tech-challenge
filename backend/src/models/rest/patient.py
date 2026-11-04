"""Modelos Pydantic de requisição e resposta REST para pacientes, planos e laudos."""

from typing import Optional
from pydantic import BaseModel, Field

from models.database.medical_report import MedicalReportDocument
from models.database.patient import PatientDocument
from models.database.plan import PlanDocument, PrescribedExerciseItem


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
    lado: Optional[str] = Field(default=None, description="Lado prescrito: direito, esquerdo, ambos ou auto")
    equipamento: Optional[str] = Field(default=None, description="Equipamento associado ao exercício")
    instrucoes: Optional[str] = Field(default=None, description="Instruções específicas para execução")


class SavePlanRequest(BaseModel):
    """Payload para criar ou atualizar o plano de exercícios de um paciente."""

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
    """Visão consolidada do paciente com seu laudo e plano de prescrição ativos."""

    patient: PatientDocument
    laudo: Optional[MedicalReportDocument] = None
    plano: Optional[PlanDocument] = None

