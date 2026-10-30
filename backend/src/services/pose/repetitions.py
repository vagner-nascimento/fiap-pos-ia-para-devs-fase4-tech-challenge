"""Tratamento de sinais e segmentação de repetições (máquina de estados com histerese)."""

from dataclasses import dataclass

import numpy as np


def fill_gaps(values: np.ndarray, max_gap: int) -> np.ndarray:
    """Interpola linearmente lacunas de ``NaN`` com até ``max_gap`` amostras.

    Lacunas maiores permanecem ``NaN`` ("sem dado"), assim como bordas sem referência.
    """
    out = np.asarray(values, dtype=float).copy()
    n = len(out)
    i = 0
    while i < n:
        if not np.isnan(out[i]):
            i += 1
            continue
        j = i
        while j < n and np.isnan(out[j]):
            j += 1
        gap = j - i
        if i > 0 and j < n and gap <= max_gap:
            out[i:j] = np.linspace(out[i - 1], out[j], gap + 2)[1:-1]
        i = j
    return out


def smooth(values: np.ndarray, window: int) -> np.ndarray:
    """Média móvel centrada que preserva as posições ``NaN``."""
    arr = np.asarray(values, dtype=float)
    if window <= 1 or len(arr) == 0:
        return arr.copy()
    if window % 2 == 0:
        window += 1
    mask = np.isnan(arr)
    if mask.all():
        return arr.copy()
    idx = np.arange(len(arr))
    filled = np.interp(idx, idx[~mask], arr[~mask])
    pad = window // 2
    padded = np.pad(filled, pad, mode="edge")
    smoothed = np.convolve(padded, np.ones(window) / window, mode="valid")
    smoothed[mask] = np.nan
    return smoothed


@dataclass
class RawRepetition:
    """Repetição segmentada, em índices de amostra."""

    start_idx: int
    peak_idx: int
    end_idx: int
    peak_progress: float
    completed: bool = True


class RepetitionDetector:
    """Segmenta repetições sobre um sinal de *progresso* normalizado (0 = repouso, 1 = alvo).

    Uma repetição começa quando o progresso cruza ``enter`` e termina quando volta a ``exit``
    (``exit < enter`` dá histerese contra ruído). Excursões cujo pico não alcança ``min_peak``
    ou que duram menos que ``min_duration`` são descartadas. Repetições com amplitude parcial
    (acima de ``min_peak``) **são contadas**, para que o desvio de amplitude possa ser reportado
    em vez de a repetição desaparecer.
    """

    def __init__(
        self,
        enter: float = 0.2,
        exit: float = 0.1,
        min_peak: float = 0.25,
        min_duration: float = 0.3,
    ):
        if exit >= enter:
            raise ValueError("exit deve ser menor que enter")
        self.enter = enter
        self.exit = exit
        self.min_peak = min_peak
        self.min_duration = min_duration

    def detect(self, times: np.ndarray, progress: np.ndarray) -> list[RawRepetition]:
        times = np.asarray(times, dtype=float)
        progress = np.asarray(progress, dtype=float)
        reps: list[RawRepetition] = []

        active = False
        start_idx = peak_idx = 0
        peak = 0.0
        last_valid = -1

        def close(end_idx: int, completed: bool) -> None:
            if peak < self.min_peak:
                return
            if times[end_idx] - times[start_idx] < self.min_duration:
                return
            reps.append(RawRepetition(start_idx, peak_idx, end_idx, float(peak), completed))

        for i, value in enumerate(progress):
            if np.isnan(value):
                continue
            last_valid = i
            if not active:
                if value >= self.enter:
                    j = i
                    while j > 0 and not np.isnan(progress[j - 1]) and progress[j - 1] > self.exit:
                        j -= 1
                    start_idx, peak_idx, peak, active = j, i, float(value), True
            else:
                if value > peak:
                    peak, peak_idx = float(value), i
                if value <= self.exit:
                    close(i, True)
                    active = False

        if active and last_valid >= 0:
            close(last_valid, False)
        return reps
