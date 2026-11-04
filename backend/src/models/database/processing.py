"""Contrato compartilhado das etapas reais do processamento de uma sessão."""

from pydantic import BaseModel


class ProcessingStep(BaseModel):
    """Descrição estável de uma etapa exposta para a interface."""

    id: str
    label: str
    description: str = ""


PROCESSING_STEPS = (
    ProcessingStep(
        id="video_received",
        label="Vídeo recebido",
        description="Arquivo salvo e sessão criada para processamento.",
    ),
    ProcessingStep(
        id="pose_extraction",
        label="Extração de pose e landmarks",
        description="Landmarks corporais estão sendo extraídos frame a frame.",
    ),
    ProcessingStep(
        id="biomechanical_analysis",
        label="Análise biomecânica do movimento",
        description="Repetições, fases e desvios estão sendo analisados.",
    ),
    ProcessingStep(
        id="audio_transcription",
        label="Transcrição de áudio e fala de dor",
        description="O áudio está sendo transcrito e classificado.",
    ),
    ProcessingStep(
        id="artifact_generation",
        label="Vídeo anotado e evidências",
        description="Vídeo anotado e evidências visuais estão sendo gerados.",
    ),
    ProcessingStep(
        id="result_persistence",
        label="Persistência e relatório",
        description="Resultados finais estão sendo gravados para o relatório.",
    ),
)

STEP_INDEX_BY_ID = {step.id: index for index, step in enumerate(PROCESSING_STEPS)}


def default_processing_steps() -> list[ProcessingStep]:
    """Retorna cópias das definições para uso como valor padrão Pydantic."""
    return [step.model_copy(deep=True) for step in PROCESSING_STEPS]


def step_id_for_progress(stage: str) -> str:
    """Converte o nome interno do processador na etapa pública correspondente."""
    mapping = {
        "extraindo_landmarks": "pose_extraction",
        "analisando_movimento": "biomechanical_analysis",
        "transcrevendo_audio": "audio_transcription",
        "gerando_artefatos": "artifact_generation",
        "renderizando_video": "artifact_generation",
        "persistindo_resultados": "result_persistence",
        "concluido": "result_persistence",
    }
    return mapping.get(stage, "result_persistence" if stage == "concluido" else "pose_extraction")


def progress_step_index(stage: str) -> int:
    """Retorna o índice público da etapa correspondente ao evento do processador."""
    return STEP_INDEX_BY_ID[step_id_for_progress(stage)]


def progress_percent(stage: str, raw_percent: float) -> float:
    """Converte o progresso global do processador para percentual seguro."""
    if stage == "concluido":
        return 100.0
    return max(0.0, min(99.0, round(raw_percent * 100, 1)))
