"""Modelos de documentos MongoDB para a coleção 'planos'."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class PrescribedExerciseItem(BaseModel):
    """Item de exercício prescrito dentro do plano de tratamento do paciente."""

    slot_id: str = Field(..., description="Identificador único do slot na prescrição (ex: SLOT-1)")
    exercicio_id: str = Field(..., description="Código do caso/exercício (ex: FISIO-006)")
    exercicio_nome: str = Field(..., description="Nome amigável do exercício")
    equipamento: Optional[str] = Field(default=None, description="Equipamento requerido pelo exercício")
    lado: str = Field(default="auto", description="Lado prescrito: direito, esquerdo, ambos ou auto")
    series: int = Field(default=3, ge=1, le=20, description="Quantidade de séries prescritas")
    repeticoes: int = Field(default=10, ge=1, le=50, description="Meta de repetições por série")
    instrucoes: Optional[str] = Field(default=None, description="Orientações específicas para o paciente")


class PlanDocument(BaseModel):
    """Documento persistido na coleção 'planos' do MongoDB."""

    plano_id: str = Field(..., description="Identificador único do plano (ex: PLN-PAC-001)")
    paciente_id: str = Field(..., description="Identificador sintético do paciente vinculado")
    dor_maxima_aceitavel: int = Field(
        default=4, ge=0, le=10, description="Limite de dor aceitável na escala 0-10"
    )
    amplitude_esperada_min: Optional[float] = Field(
        default=None, description="Amplitude articular mínima esperada em graus"
    )
    amplitude_esperada_max: Optional[float] = Field(
        default=None, description="Amplitude articular máxima esperada em graus"
    )
    amplitude_esperada_texto: str = Field(
        default="60 – 90", description="Representação textual da faixa de amplitude esperada (ex: '60 – 90')"
    )
    exercicios: list[PrescribedExerciseItem] = Field(
        default_factory=list, description="Lista ordenada de exercícios prescritos (slots)"
    )
    ativo: bool = Field(default=True, description="Indica se este é o plano ativo do paciente")
    synthetic: bool = Field(default=True, description="Prescrição fictícia de demonstração")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Data e hora de criação"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Data e hora da última atualização"
    )

