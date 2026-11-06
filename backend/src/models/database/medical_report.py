"""Modelos de documentos MongoDB para a coleção 'laudos'."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class MedicalReportDocument(BaseModel):
    """Documento persistido na coleção 'laudos' do MongoDB."""

    laudo_id: str = Field(..., description="Identificador único do laudo (ex: LAU-PAC-001)")
    paciente_id: str = Field(..., description="Identificador sintético do paciente vinculado")
    texto_original: str = Field(..., description="Texto original do laudo clínico inserido pelo profissional")
    regiao: Optional[str] = Field(default=None, description="Região anatômica afetada (ex: ombro direito)")
    lesao: Optional[str] = Field(default=None, description="Condição ou lesão identificada (ex: tendinopatia)")
    movimentos_restritos: list[str] = Field(
        default_factory=list, description="Lista de restrições de movimento (ex: ['elevação > 90°'])"
    )
    limite_amplitude_max: Optional[float] = Field(
        default=None, description="Limite angular máximo seguro extraído ou configurado (em graus)"
    )
    observacoes_restricao: Optional[str] = Field(
        default=None, description="Notas complementares sobre restrições clínicas"
    )
    extraido_automaticamente: bool = Field(
        default=True, description="Indica se houve extração automática de entidades do texto"
    )
    revisado_profissional: bool = Field(
        default=False, description="Indica se os campos extraídos foram conferidos/ajustados pelo fisioterapeuta"
    )
    synthetic: bool = Field(default=True, description="Documento fictício de demonstração")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Data e hora de criação"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Data e hora da última atualização"
    )

