import numpy as np
import pytest

from services.pose.repetitions import RepetitionDetector, fill_gaps, smooth


def _cycles(n_cycles, peak, period=30, rest=15):
    """Sinal: repouso, depois n ciclos de subida/descida até ``peak``."""
    out = [0.0] * rest
    for _ in range(n_cycles):
        half = period // 2
        out += list(np.linspace(0, peak, half)) + list(np.linspace(peak, 0, half))
        out += [0.0] * rest
    return np.array(out)


def _times(signal, fps=30):
    return np.arange(len(signal)) / fps


def test_counts_five_full_repetitions():
    p = _cycles(5, 1.0)
    reps = RepetitionDetector().detect(_times(p), p)
    assert len(reps) == 5
    assert all(r.completed for r in reps)
    assert all(r.peak_progress == pytest.approx(1.0) for r in reps)
    assert all(r.start_idx < r.peak_idx < r.end_idx for r in reps)


def test_partial_amplitude_is_still_counted():
    p = _cycles(3, 0.5)
    reps = RepetitionDetector().detect(_times(p), p)
    assert len(reps) == 3
    assert all(r.peak_progress == pytest.approx(0.5) for r in reps)


def test_noise_below_min_peak_is_ignored():
    p = _cycles(3, 0.15)
    assert RepetitionDetector().detect(_times(p), p) == []


def test_too_short_excursion_is_ignored():
    p = _cycles(1, 1.0, period=4, rest=10)
    assert RepetitionDetector(min_duration=0.3).detect(_times(p), p) == []


def test_open_repetition_at_end_is_incomplete():
    p = np.concatenate([_cycles(1, 1.0), np.linspace(0, 0.8, 20)])
    reps = RepetitionDetector().detect(_times(p), p)
    assert len(reps) == 2
    assert reps[0].completed
    assert not reps[1].completed


def test_nan_gap_does_not_split_repetition():
    p = _cycles(1, 1.0)
    mid = len(p) // 2
    p[mid - 2 : mid + 2] = np.nan
    reps = RepetitionDetector().detect(_times(p), p)
    assert len(reps) == 1


def test_hysteresis_prevents_double_count():
    # oscila perto do limiar de entrada, sem voltar abaixo de exit
    p = np.array([0, 0, 0.3, 0.18, 0.3, 0.18, 0.6, 0.3, 0.0, 0.0] * 1, dtype=float)
    p = np.repeat(p, 5)
    reps = RepetitionDetector().detect(_times(p), p)
    assert len(reps) == 1


def test_exit_must_be_below_enter():
    with pytest.raises(ValueError):
        RepetitionDetector(enter=0.1, exit=0.2)


def test_fill_gaps_interpolates_short_gaps_only():
    v = np.array([0, np.nan, np.nan, 3, np.nan, np.nan, np.nan, np.nan, 8.0])
    out = fill_gaps(v, max_gap=2)
    assert out[1:3].tolist() == [1, 2]
    assert np.isnan(out[4:8]).all()


def test_fill_gaps_keeps_edges_nan():
    out = fill_gaps(np.array([np.nan, 1.0, 2.0, np.nan]), max_gap=5)
    assert np.isnan(out[0]) and np.isnan(out[3])


def test_smooth_preserves_nan_and_reduces_noise():
    rng = np.random.default_rng(0)
    base = np.sin(np.linspace(0, 6, 100))
    noisy = base + rng.normal(0, 0.2, 100)
    noisy[40:45] = np.nan
    out = smooth(noisy, 7)
    assert np.isnan(out[40:45]).all()
    valid = ~np.isnan(out)
    assert np.abs(out[valid] - base[valid]).mean() < np.abs(noisy[valid] - base[valid]).mean()
