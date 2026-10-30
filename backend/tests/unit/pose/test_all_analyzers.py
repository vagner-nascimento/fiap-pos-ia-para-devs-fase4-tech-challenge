import numpy as np
import pytest

from services.pose.joint_mapper import BodySide, Landmark
from services.pose.models import PoseFrame
from services.pose.registry import get_analyzer, supported_exercises

FPS = 30.0


def test_all_seven_exercises_are_supported():
    expected = [
        "FISIO-001",
        "FISIO-002",
        "FISIO-003",
        "FISIO-004",
        "FISIO-005",
        "FISIO-006",
        "FISIO-007",
    ]
    assert supported_exercises() == expected


def _dummy_frames(n=60):
    frames = []
    for i in range(n):
        lm = np.zeros((33, 4))
        lm[:, :2] = 100.0
        lm[:, 3] = 1.0
        frames.append(PoseFrame(i, i / FPS, lm))
    return frames


@pytest.mark.parametrize("case_id", supported_exercises())
def test_all_analyzers_instantiate_and_analyze_empty_motion(case_id):
    analyzer = get_analyzer(case_id, side=BodySide.AUTO, target_repetitions=5)
    frames = _dummy_frames(30)
    result = analyzer.analyze(frames, FPS)
    s = result.session_summary
    assert s.case_id == case_id
    assert s.target_repetitions == 5
    assert s.completed_repetitions == 0
    assert result.repetitions == []
