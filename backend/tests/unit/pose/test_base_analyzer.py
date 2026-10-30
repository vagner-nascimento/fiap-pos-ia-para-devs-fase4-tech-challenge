import math

import numpy as np
import pytest

from services.pose.base_analyzer import (
    AnalysisContext,
    BaseExerciseAnalyzer,
    ExerciseConfig,
)
from services.pose.joint_mapper import BodySide, Landmark
from services.pose.models import DeviationSeverity, PoseFrame

FPS = 30.0
RIGHT_LM = int(Landmark.RIGHT_WRIST)
LEFT_LM = int(Landmark.LEFT_WRIST)


class DummyAnalyzer(BaseExerciseAnalyzer):
    """Lê o 'ângulo' da coordenada x do punho do lado avaliado (0 = repouso, 100 = alvo)."""

    case_id = "TEST-001"
    exercise_id = "DUMMY"
    primary_metric = "angle"
    default_config = ExerciseConfig(thresholds={"min_peak_progress": 0.8})

    def _lm(self, side):
        return RIGHT_LM if side is BodySide.RIGHT else LEFT_LM

    def compute_metrics(self, frame, side):
        return {"angle": float(frame.landmarks[self._lm(side), 0])}

    def progress(self, metrics):
        return metrics["angle"] / 100.0

    def visibility_landmarks(self, side):
        return [self._lm(side)]

    def detect_deviations(self, ctx: AnalysisContext):
        out = []
        for number, rep in enumerate(ctx.repetitions, start=1):
            if rep.peak_progress < ctx.threshold("min_peak_progress"):
                out.append(
                    ctx.make_deviation(
                        "amplitude_reduzida",
                        DeviationSeverity.MODERADA,
                        rep.start_idx,
                        rep.end_idx,
                        f"Pico {rep.peak_progress * 100:.0f}% do alvo",
                        repetition_index=number,
                    )
                )
        return out


def _signal(peaks, rest=15, period=30):
    out = [0.0] * rest
    for peak in peaks:
        half = period // 2
        out += list(np.linspace(0, peak, half)) + list(np.linspace(peak, 0, half))
        out += [0.0] * rest
    return np.array(out) * 100.0


def _frames(right=None, left=None, n=None):
    n = n or len(right if right is not None else left)
    frames = []
    for i in range(n):
        lm = np.zeros((33, 4))
        lm[:, 3] = 1.0
        lm[RIGHT_LM, 0] = right[i] if right is not None else 0.0
        lm[LEFT_LM, 0] = left[i] if left is not None else 0.0
        frames.append(PoseFrame(index=i, time=i / FPS, landmarks=lm))
    return frames


def test_counts_repetitions_and_marks_valid():
    frames = _frames(right=_signal([1.0] * 5))
    result = DummyAnalyzer(BodySide.RIGHT, target_repetitions=5).analyze(frames, FPS)
    s = result.session_summary
    assert s.completed_repetitions == 5
    assert s.valid_repetitions == 5
    assert s.compliance_score == 100.0
    assert s.side_evaluated == "direito"
    assert result.deviations == []
    assert all(r.is_valid for r in result.repetitions)
    # o pico suavizado fica ligeiramente abaixo do pico bruto (média móvel)
    assert result.repetitions[0].peak_angle == pytest.approx(100.0, abs=8)


def test_deviation_attached_to_repetition():
    frames = _frames(right=_signal([1.0, 0.5, 1.0]))
    result = DummyAnalyzer(BodySide.RIGHT, target_repetitions=3).analyze(frames, FPS)
    assert [r.is_valid for r in result.repetitions] == [True, False, True]
    assert result.repetitions[1].deviations == ["amplitude_reduzida"]
    dev = result.deviations[0]
    assert dev.repetition_index == 2
    assert dev.start_time < dev.end_time
    assert result.session_summary.valid_repetitions == 2
    assert result.session_summary.compliance_score == pytest.approx(66.7)


def test_auto_picks_side_that_moves_right():
    frames = _frames(right=np.zeros(150), left=_signal([1.0] * 3))
    result = DummyAnalyzer(BodySide.AUTO).analyze(frames, FPS)
    assert result.session_summary.side_evaluated == "esquerdo"
    assert result.session_summary.completed_repetitions == 3


def test_auto_picks_right_when_right_moves():
    frames = _frames(right=_signal([1.0] * 3), left=np.zeros(150))
    result = DummyAnalyzer("auto").analyze(frames, FPS)
    assert result.session_summary.side_evaluated == "direito"


def test_auto_prefers_visible_side():
    frames = _frames(right=_signal([1.0] * 3), left=_signal([1.0] * 3))
    for f in frames:
        f.landmarks[RIGHT_LM, 3] = 0.1  # pouco visível
    # visibilidade baixa só pontua; ambos se movem igual => esquerdo vence
    result = DummyAnalyzer(BodySide.AUTO).analyze(frames, FPS)
    assert result.session_summary.side_evaluated == "esquerdo"


def test_auto_without_movement_falls_back_with_limitation():
    frames = _frames(right=np.zeros(60), left=np.zeros(60))
    result = DummyAnalyzer(BodySide.AUTO).analyze(frames, FPS)
    s = result.session_summary
    assert s.side_evaluated == "direito"
    assert s.completed_repetitions == 0
    assert any("lado" in m for m in s.limitations)
    assert any("Nenhuma repetição" in m for m in s.limitations)


def test_frames_without_pose_are_no_data_and_reported():
    signal = _signal([1.0] * 5)
    frames = _frames(right=signal)
    for f in frames[50:200]:
        f.landmarks = None
    result = DummyAnalyzer(BodySide.RIGHT).analyze(frames, FPS)
    s = result.session_summary
    assert s.frames_without_pose == 150
    assert any("sem pessoa" in m for m in s.limitations)
    gap = [p for p in result.telemetry if 3.0 < p.timestamp < 6.0]
    assert gap and all(p.progress is None for p in gap)


def test_telemetry_sampling_and_phases():
    frames = _frames(right=_signal([1.0] * 2))
    result = DummyAnalyzer(BodySide.RIGHT).analyze(frames, FPS)
    assert result.telemetry[1].timestamp - result.telemetry[0].timestamp == pytest.approx(0.1)
    phases = {p.phase for p in result.telemetry}
    assert {"repouso", "concentrica", "excentrica", "pico"} <= phases
    assert all(not math.isnan(p.progress) for p in result.telemetry if p.progress is not None)


def test_result_serializes_to_json():
    frames = _frames(right=_signal([1.0] * 2))
    result = DummyAnalyzer(BodySide.RIGHT).analyze(frames, FPS)
    text = result.model_dump_json()
    assert "session_summary" in text and "NaN" not in text


def test_empty_frames_raise():
    with pytest.raises(ValueError):
        DummyAnalyzer().analyze([], FPS)
