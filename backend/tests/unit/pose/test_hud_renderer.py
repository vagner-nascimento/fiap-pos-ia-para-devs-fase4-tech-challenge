import numpy as np
import pytest

from services.pose.hud_renderer import HudRenderer
from services.pose.models import (
    DeviationEvent,
    DeviationSeverity,
    ExerciseAnalysisResult,
    PoseFrame,
    RepetitionEvent,
    SessionSummary,
)


def _make_dummy_result(deviations=None):
    summary = SessionSummary(
        exercise_id="KNEE_EXTENSION_SEATED",
        case_id="FISIO-001",
        side_evaluated="direito",
        target_repetitions=5,
        completed_repetitions=1,
        valid_repetitions=0,
        invalid_repetitions=1,
        duration_seconds=10.0,
        fps=30.0,
        total_frames=300,
        frames_without_pose=0,
        compliance_score=0.0,
    )
    return ExerciseAnalysisResult(
        session_summary=summary,
        repetitions=[
            RepetitionEvent(
                index=1,
                start_time=1.0,
                peak_time=2.0,
                end_time=3.0,
                duration=2.0,
                peak_progress=0.7,
                completed=True,
                is_valid=False,
            )
        ],
        deviations=deviations or [],
        telemetry=[],
    )


def test_hud_draws_on_vertical_low_res_frame():
    # Vídeo vertical estreito (478x850)
    w, h = 478, 850
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    renderer = HudRenderer()
    pose_frame = PoseFrame(index=30, time=1.0, landmarks=np.zeros((33, 4)))

    dev = DeviationEvent(
        deviation_type="amplitude_reduzida",
        severity=DeviationSeverity.MODERADA,
        repetition_index=1,
        start_time=1.0,
        end_time=3.0,
        start_frame=30,
        end_frame=90,
        description="Extensão máxima de 138° (esperado ≥ 150°)",
    )
    res = _make_dummy_result(deviations=[dev])

    renderer.draw_hud(frame, pose_frame, res, [dev], w, h)

    # Confere que pixels foram desenhados na área do HUD
    assert np.any(frame[:100, :] > 0)


def test_hud_draws_without_deviations():
    w, h = 640, 480
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    renderer = HudRenderer()
    pose_frame = PoseFrame(index=0, time=0.0, landmarks=np.zeros((33, 4)))
    res = _make_dummy_result(deviations=[])

    renderer.draw_hud(frame, pose_frame, res, [], w, h)
    assert np.any(frame[:70, :] > 0)
