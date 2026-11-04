import mongomock

from infra.database.repositories.session_repository import SessionRepository
from models.database.processing import (
    PROCESSING_STEPS,
    progress_percent,
    progress_step_index,
    step_id_for_progress,
)
from models.database.session import SessionDocument, SessionStatus


def test_processing_contract_contains_only_real_pipeline_steps():
    step_ids = [step.id for step in PROCESSING_STEPS]

    assert len(step_ids) == 6
    assert "facial_expression" not in step_ids
    assert step_ids == [
        "video_received",
        "pose_extraction",
        "biomechanical_analysis",
        "audio_transcription",
        "artifact_generation",
        "result_persistence",
    ]


def test_internal_progress_stage_maps_to_public_step():
    assert step_id_for_progress("extraindo_landmarks") == "pose_extraction"
    assert step_id_for_progress("renderizando_video") == "artifact_generation"
    assert progress_step_index("persistindo_resultados") == 5
    assert progress_percent("concluido", 0.7) == 100.0


def test_repository_does_not_regress_progress():
    client = mongomock.MongoClient()
    repository = SessionRepository(collection=client["test"]["sessoes"])
    repository.save_session(
        SessionDocument(
            session_id="progress-1",
            exercicio_id="FISIO-001",
            case_id="FISIO-001",
            side_evaluated="auto",
            status=SessionStatus.PROCESSANDO,
        )
    )

    assert repository.update_progress(
        "progress-1",
        status=SessionStatus.PROCESSANDO,
        etapa="biomechanical_analysis",
        current_step="biomechanical_analysis",
        current_step_index=2,
        progress_percent=55.0,
        progress_message="Analisando",
    )
    assert not repository.update_progress(
        "progress-1",
        status=SessionStatus.PROCESSANDO,
        etapa="pose_extraction",
        current_step="pose_extraction",
        current_step_index=1,
        progress_percent=40.0,
        progress_message="Atrasado",
    )

    saved = repository.get_session("progress-1")
    assert saved is not None
    assert saved.current_step == "biomechanical_analysis"
    assert saved.progress_percent == 55.0
