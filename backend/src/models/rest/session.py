"""Modelos REST para requisições e respostas de sessões."""

from typing import Optional
from pydantic import BaseModel, Field


class CreateSessionResponse(BaseModel):
    """Resposta ao criar ou enfileirar uma sessão para processamento."""

    session_id: str = Field(..., description="ID único gerado para a sessão")
    status: str = Field(..., description="Status atual ('processando', 'concluido' ou 'enviado')")
    etapa: str = Field(..., description="Etapa atual do fluxo de processamento")
    message: str = Field(..., description="Mensagem informativa sobre o processamento")
    paciente_id: Optional[str] = Field(default=None, description="ID do paciente vinculado")
    exercicio_id: str = Field(..., description="Exercício selecionado")
    created_at: str = Field(..., description="Timestamp de criação")


class CreateSessionPayload(BaseModel):
    """Payload JSON para criar uma sessão a partir de clipe do dataset ou caminho local."""

    exercicio_id: str = Field(..., description="Identificador do caso ou exercício (ex: 'FISIO-001')")
    paciente_id: Optional[str] = Field(None, description="Identificador sintético do paciente (ex: 'PAC-001')")
    dataset_clip: Optional[str] = Field(
        None, description="Nome do clipe de referência do dataset (ex: 'FISIO-001-correto.mp4')"
    )
    video_path: Optional[str] = Field(None, description="Caminho do arquivo de vídeo no host ou container")
    side: Optional[str] = Field("auto", description="Lado do exercício: 'auto', 'direito', 'esquerdo', 'ambos'")
    target_repetitions: Optional[int] = Field(5, description="Número de repetições prescritas (alvo)")
    run_id: Optional[str] = Field(None, description="ID customizado opcional para a sessão")

