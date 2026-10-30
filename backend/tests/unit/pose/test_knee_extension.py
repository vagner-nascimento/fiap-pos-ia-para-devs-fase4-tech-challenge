import math

import numpy as np
import pytest

from services.pose.joint_mapper import BodySide, JointMapper
from services.pose.models import PoseFrame
from services.pose.registry import get_analyzer, supported_exercises

FPS = 30.0
BASE_TRUNK = -10.0


def _signals(reps, lead=1.0, gap=0.8, tail=1.0, stand_up=0.0):
    """Gera séries (joelho, tronco) em FPS a partir de especificações de repetição.

    Cada rep: dict(peak, up, down, lean) ou ``keys`` (lista de (dt, joelho)) para formas livres.
    """
    knee_pts, trunk_pts = [(0.0, 90.0)], [(0.0, BASE_TRUNK)]
    t = lead
    knee_pts.append((t, 90.0))
    trunk_pts.append((t, BASE_TRUNK))
    for r in reps:
        if "keys" in r:
            for dt, value in r["keys"]:
                knee_pts.append((t + dt, value))
            span = r["keys"][-1][0]
            mid = t + r["keys"][len(r["keys"]) // 2][0]
            trunk_pts += [(t, BASE_TRUNK), (mid, BASE_TRUNK + r.get("lean", 0)), (t + span, BASE_TRUNK)]
            t += span
        else:
            up, down = r.get("up", 0.8), r.get("down", 0.8)
            knee_pts += [(t + up, r["peak"]), (t + up + down, 90.0)]
            trunk_pts += [(t + up, BASE_TRUNK + r.get("lean", 0.0)), (t + up + down, BASE_TRUNK)]
            t += up + down
        t += gap
        knee_pts.append((t, 90.0))
        trunk_pts.append((t, BASE_TRUNK))
    if stand_up:
        trunk_pts += [(t + stand_up / 2, BASE_TRUNK + 30), (t + stand_up, BASE_TRUNK)]
        t += stand_up
    t += tail
    knee_pts.append((t, 90.0))
    trunk_pts.append((t, BASE_TRUNK))
    times = np.arange(0, t, 1 / FPS)
    knee = np.interp(times, *zip(*knee_pts))
    trunk = np.interp(times, *zip(*sorted(trunk_pts)))
    return times, knee, trunk


def _frames(times, knee, trunk, active=BodySide.RIGHT):
    """Monta frames em vista lateral. O lado inativo fica quase parado e menos visível."""
    other = active.opposite
    frames = []
    for i, (t, k, tr) in enumerate(zip(times, knee, trunk)):
        lm = np.zeros((33, 4))
        for side, theta, vis in ((active, k, 1.0), (other, 95.0, 0.6)):
            m = JointMapper(side)
            hip = np.array([200.0, 300.0])
            kn = np.array([400.0, 300.0])
            th = math.radians(theta)
            ankle = kn + 200 * np.array([-math.cos(th), math.sin(th)])
            phi = math.radians(tr if side is active else BASE_TRUNK)
            shoulder = hip + 250 * np.array([math.sin(phi), -math.cos(phi)])
            for idx, pt in ((m.hip, hip), (m.knee, kn), (m.ankle, ankle), (m.shoulder, shoulder)):
                lm[idx] = [pt[0], pt[1], 0.0, vis]
        frames.append(PoseFrame(i, float(t), lm))
    return frames


def _run(reps, side="auto", active=BodySide.RIGHT, **kw):
    times, knee, trunk = _signals(reps, **kw)
    analyzer = get_analyzer("FISIO-001", side, target_repetitions=len(reps))
    return analyzer.analyze(_frames(times, knee, trunk, active), FPS)


GOOD = {"peak": 155.0}


def test_correct_execution_has_no_deviations():
    r = _run([GOOD] * 5)
    s = r.session_summary
    assert (s.completed_repetitions, s.valid_repetitions) == (5, 5)
    assert s.compliance_score == 100.0
    assert r.deviations == []
    assert s.side_evaluated == "direito"
    assert all(rep.peak_angle == pytest.approx(155, abs=3) for rep in r.repetitions)


@pytest.mark.parametrize("active,expected", [(BodySide.RIGHT, "direito"), (BodySide.LEFT, "esquerdo")])
def test_auto_side_follows_the_exercising_leg(active, expected):
    r = _run([GOOD] * 3, active=active)
    assert r.session_summary.side_evaluated == expected
    assert r.session_summary.completed_repetitions == 3
    assert r.deviations == []


def test_explicit_side_is_honored():
    r = _run([GOOD] * 3, side="esquerdo", active=BodySide.LEFT)
    assert r.session_summary.side_evaluated == "esquerdo"
    assert r.session_summary.completed_repetitions == 3


def test_reduced_amplitude():
    r = _run([GOOD, {"peak": 135.0}, GOOD])
    assert [d.deviation_type for d in r.deviations] == ["amplitude_reduzida"]
    d = r.deviations[0]
    assert d.repetition_index == 2
    assert d.severity.value == "moderada"
    assert "135" in d.description or "134" in d.description
    assert [rep.is_valid for rep in r.repetitions] == [True, False, True]


def test_trunk_compensation():
    r = _run([GOOD, {"peak": 155.0, "lean": 15.0}, GOOD])
    kinds = [d.deviation_type for d in r.deviations]
    assert kinds == ["compensacao_tronco"]
    d = r.deviations[0]
    assert d.repetition_index == 2
    assert d.severity.value == "moderada"
    rep = r.repetitions[1]
    assert d.evidence_frame is not None
    assert rep.start_time <= d.evidence_frame / FPS <= rep.end_time


def test_small_trunk_motion_is_tolerated():
    r = _run([{"peak": 155.0, "lean": 4.0}] * 3)
    assert r.deviations == []


def test_abrupt_return_is_flagged_as_rhythm():
    r = _run([GOOD, {"peak": 155.0, "down": 0.25}, GOOD])
    assert [d.deviation_type for d in r.deviations] == ["ritmo_acelerado"]
    assert r.deviations[0].repetition_index == 2


def test_double_peak_is_flagged_as_rhythm():
    double = {"keys": [(0.0, 90.0), (0.6, 155.0), (1.0, 120.0), (1.5, 155.0), (2.3, 90.0)]}
    r = _run([GOOD, double, GOOD])
    kinds = [(d.deviation_type, d.repetition_index) for d in r.deviations]
    assert kinds == [("ritmo_acelerado", 2)]
    assert "picos" in r.deviations[0].description


def test_trunk_motion_outside_repetitions_is_ignored():
    r = _run([GOOD] * 3, stand_up=1.5)
    assert r.deviations == []
    assert r.session_summary.valid_repetitions == 3


def test_reports_in_json():
    r = _run([GOOD, {"peak": 135.0}])
    text = r.model_dump_json()
    assert "amplitude_reduzida" in text and "NaN" not in text
    assert {"knee_angle", "trunk_angle"} <= set(r.telemetry[0].metrics)


def test_registry_lookup():
    assert "FISIO-001" in supported_exercises()
    assert type(get_analyzer("fisio-001")).__name__ == "KneeExtensionAnalyzer"
    assert type(get_analyzer("KNEE_EXTENSION_SEATED")).__name__ == "KneeExtensionAnalyzer"
    with pytest.raises(KeyError):
        get_analyzer("FISIO-999")
