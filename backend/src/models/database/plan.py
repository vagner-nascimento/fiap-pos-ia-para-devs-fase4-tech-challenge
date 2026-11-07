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
    dia_tratamento: Optional[int] = Field(
        default=None,
        ge=1,
        le=30,
        description="Dia específico de tratamento (1..N) quando prescrito para um único dia",
    )
    dias_prescritos: list[int] = Field(
        default_factory=list,
        description="Lista de dias do tratamento em que este exercício é prescrito (ex: [1, 3]). Vazio = todos os dias.",
    )
    instrucoes: Optional[str] = Field(default=None, description="Orientações específicas para o paciente")

    def applies_to_day(self, day: int) -> bool:
        """Retorna True se este exercício está prescrito para o dia informado (1..N)."""
        if self.dias_prescritos:
            return int(day) in [int(d) for d in self.dias_prescritos]
        if self.dia_tratamento is not None:
            return int(self.dia_tratamento) == int(day)
        return True

    def resolved_days(self, total_days: int = 3) -> list[int]:
        """Retorna a lista ordenada de dias (1..N) nos quais este exercício deve ser executado."""
        if self.dias_prescritos:
            return sorted({int(d) for d in self.dias_prescritos if int(d) >= 1})
        if self.dia_tratamento is not None:
            return [int(self.dia_tratamento)]
        return list(range(1, max(1, int(total_days)) + 1))


class PlanDocument(BaseModel):
    """Documento persistido na coleção 'planos' do MongoDB."""

    plano_id: str = Field(..., description="Identificador único do plano (ex: PLN-PAC-001)")
    paciente_id: str = Field(..., description="Identificador sintético do paciente vinculado")
    dias_tratamento: int = Field(
        default=3, ge=1, le=30, description="Quantidade de dias de tratamento previstos no plano"
    )
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
    avaliado_evolucao: bool = Field(
        default=False, description="Indica se o relatório final de evolução do plano foi avaliado pelo médico/fisioterapeuta"
    )
    observacoes_avaliacao_final: Optional[str] = Field(
        default=None, description="Parecer ou notas registradas pelo fisioterapeuta/médico na avaliação final"
    )
    ativo: bool = Field(default=True, description="Indica se este é o plano ativo do paciente")
    synthetic: bool = Field(default=True, description="Prescrição fictícia de demonstração")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Data e hora de criação"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Data e hora da última atualização"
    )

