"""Base dos analisadores de exercício: métricas por frame, lado dinâmico, repetições e resultado."""

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import ClassVar, Optional

import numpy as np

from services.pose.joint_mapper import BodySide
from services.pose.models import (
    DeviationEvent,
    DeviationSeverity,
    ExerciseAnalysisResult,
    PoseFrame,
    RepetitionEvent,
    SessionSummary,
    TelemetryPoint,
)
from services.pose.repetitions import RawRepetition, RepetitionDetector, fill_gaps, smooth

logger = logging.getLogger(__name__)

PHASE_REST = "repouso"
PHASE_CONCENTRIC = "concentrica"
PHASE_PEAK = "pico"
PHASE_ECCENTRIC = "excentrica"

MAX_FRAMES_WITHOUT_POSE_RATIO = 0.2


@dataclass(frozen=True)
class ExerciseConfig:
    """Parâmetros ajustáveis de um exercício (limiares ficam aqui, não espalhados no código)."""

    # Segmentação de repetições sobre o progresso normalizado (0..1)
    enter: float = 0.2
    exit: float = 0.1
    min_peak: float = 0.25
    min_duration: float = 0.3
    # Tratamento de sinal (em segundos, para não depender do fps do vídeo)
    smoothing_seconds: float = 0.1
    max_gap_seconds: float = 0.25
    # Saída
    telemetry_hz: float = 10.0
    target_repetitions: Optional[int] = None
    # Limiares específicos de cada exercício (angle_min, trunk_max_deg, ...)
    thresholds: dict[str, float] = field(default_factory=dict)


@dataclass
class AnalysisContext:
    """Dados já tratados entregues ao analisador para detectar desvios."""

    frames: list[PoseFrame]
    times: np.ndarray
    fps: float
    side: BodySide
    series: dict[str, np.ndarray]
    progress: np.ndarray
    repetitions: list[RawRepetition]
    config: ExerciseConfig

    def threshold(self, name: str) -> float:
        return self.config.thresholds[name]

    def rep_number(self, idx: int) -> Optional[int]:
        """Número (1..n) da repetição que contém a amostra ``idx``, se houver."""
        for number, rep in enumerate(self.repetitions, start=1):
            if rep.start_idx <= idx <= rep.end_idx:
                return number
        return None

    def make_deviation(
        self,
        deviation_type: str,
        severity: DeviationSeverity,
        start_idx: int,
        end_idx: int,
        description: str,
        repetition_index: Optional[int] = None,
        evidence_idx: Optional[int] = None,
    ) -> DeviationEvent:
        if repetition_index is None:
            repetition_index = self.rep_number(start_idx)
        peak_frame = self.frames[evidence_idx].index if evidence_idx is not None else None
        return DeviationEvent(
            deviation_type=deviation_type,
            severity=severity,
            repetition_index=repetition_index,
            start_time=float(self.times[start_idx]),
            end_time=float(self.times[end_idx]),
            start_frame=self.frames[start_idx].index,
            end_frame=self.frames[end_idx].index,
            evidence_frame=peak_frame,
            description=description,
        )


@dataclass
class _SideSignals:
    side: BodySide
    series: dict[str, np.ndarray]
    progress: np.ndarray
    score: float


class BaseExerciseAnalyzer(ABC):
    """Template de análise. Cada exercício implementa apenas métricas, progresso e desvios."""

    case_id: ClassVar[str]
    exercise_id: ClassVar[str]
    bilateral: ClassVar[bool] = False
    primary_metric: ClassVar[Optional[str]] = None
    default_config: ClassVar[ExerciseConfig] = ExerciseConfig()

    def __init__(
        self,
        side: BodySide | str | None = BodySide.AUTO,
        config: Optional[ExerciseConfig] = None,
        target_repetitions: Optional[int] = None,
    ):
        self.side = side if isinstance(side, BodySide) else BodySide.from_text(side)
        self.config = config or self.default_config
        if target_repetitions is not None:
            self.config = replace(self.config, target_repetitions=target_repetitions)

    # ---- pontos de extensão --------------------------------------------

    @abstractmethod
    def compute_metrics(self, frame: PoseFrame, side: BodySide) -> dict[str, float]:
        """Métricas do frame (ângulos, inclinações...) para o lado dado. ``NaN`` = sem dado."""

    @abstractmethod
    def progress(self, metrics: dict[str, float]) -> float:
        """Converte as métricas suavizadas em progresso: 0 = repouso, 1 = amplitude alvo."""

    @abstractmethod
    def detect_deviations(self, ctx: AnalysisContext) -> list[DeviationEvent]:
        """Detecta desvios a partir do contexto tratado."""

    def visibility_landmarks(self, side: BodySide) -> list[int]:
        """Landmarks cuja visibilidade pontua o lado na detecção automática."""
        return []

    def calibrate(self, series: dict[str, np.ndarray]) -> None:
        """Ajusta referências do vídeo (ex.: ângulo de repouso) antes de calcular o progresso."""

    # ---- análise --------------------------------------------------------

    def analyze(self, frames: list[PoseFrame], fps: float) -> ExerciseAnalysisResult:
        if not frames:
            raise ValueError("Nenhum frame para analisar")

        cfg = self.config
        times = np.array([f.time for f in frames], dtype=float)
        limitations: list[str] = []

        candidates = self._candidate_sides()
        signals = [self._side_signals(frames, s, fps) for s in candidates]

        if len(signals) == 1:
            chosen = signals[0]
        else:
            chosen = max(signals, key=lambda s: s.score)
            if chosen.score <= 0:
                limitations.append(
                    "Não foi possível determinar o lado do exercício automaticamente; "
                    "assumido lado direito."
                )
                chosen = next(s for s in signals if s.side is BodySide.RIGHT)

        detector = RepetitionDetector(cfg.enter, cfg.exit, cfg.min_peak, cfg.min_duration)
        raw_reps = detector.detect(times, chosen.progress)

        ctx = AnalysisContext(
            frames=frames,
            times=times,
            fps=fps,
            side=chosen.side,
            series=chosen.series,
            progress=chosen.progress,
            repetitions=raw_reps,
            config=cfg,
        )
        deviations = self.detect_deviations(ctx)

        repetitions = self._build_repetitions(ctx, deviations)

        without_pose = sum(1 for f in frames if not f.has_pose)
        if without_pose / len(frames) > MAX_FRAMES_WITHOUT_POSE_RATIO:
            limitations.append(
                f"{without_pose} de {len(frames)} frames sem pessoa detectada; "
                "resultado pode estar incompleto."
            )
        if not raw_reps:
            limitations.append("Nenhuma repetição detectada.")

        summary = self._build_summary(
            ctx, repetitions, fps, without_pose, limitations
        )
        telemetry = self._build_telemetry(ctx, fps)
        return ExerciseAnalysisResult(
            session_summary=summary,
            repetitions=repetitions,
            deviations=deviations,
            telemetry=telemetry,
        )

    # ---- internos -------------------------------------------------------

    def _candidate_sides(self) -> list[BodySide]:
        if self.bilateral:
            return [BodySide.BOTH]
        if self.side in (BodySide.RIGHT, BodySide.LEFT):
            return [self.side]
        return [BodySide.RIGHT, BodySide.LEFT]

    def _side_signals(self, frames: list[PoseFrame], side: BodySide, fps: float) -> _SideSignals:
        cfg = self.config
        window = max(1, round(cfg.smoothing_seconds * fps))
        max_gap = max(1, round(cfg.max_gap_seconds * fps))
        n = len(frames)
        raw: dict[str, np.ndarray] = {}
        for i, frame in enumerate(frames):
            if not frame.has_pose:
                continue
            for name, value in self.compute_metrics(frame, side).items():
                raw.setdefault(name, np.full(n, np.nan))[i] = value

        series = {
            name: smooth(fill_gaps(values, max_gap), window) for name, values in raw.items()
        }
        if series:
            self.calibrate(series)

        progress = np.full(n, np.nan)
        for i in range(n):
            metrics = {name: float(values[i]) for name, values in series.items()}
            if metrics:
                progress[i] = self.progress(metrics)

        landmarks = self.visibility_landmarks(side)
        if landmarks:
            visibility = float(
                np.mean([np.mean([f.visibility(lm) for f in frames]) for lm in landmarks])
            )
        else:
            visibility = 1.0
        valid = progress[~np.isnan(progress)]
        amplitude = float(np.ptp(valid)) if len(valid) else 0.0
        return _SideSignals(side, series, progress, visibility * amplitude)

    @staticmethod
    def _phases(ctx: AnalysisContext) -> list[str]:
        phases = [PHASE_REST] * len(ctx.times)
        for rep in ctx.repetitions:
            for i in range(rep.start_idx, rep.end_idx + 1):
                phases[i] = PHASE_CONCENTRIC if i < rep.peak_idx else PHASE_ECCENTRIC
            for i in range(rep.start_idx, rep.end_idx + 1):
                value = ctx.progress[i]
                if not math.isnan(value) and value >= 0.9 * rep.peak_progress:
                    phases[i] = PHASE_PEAK
        return phases

    def _build_repetitions(
        self, ctx: AnalysisContext, deviations: list[DeviationEvent]
    ) -> list[RepetitionEvent]:
        events: list[RepetitionEvent] = []
        for number, rep in enumerate(ctx.repetitions, start=1):
            names = sorted(
                {d.deviation_type for d in deviations if d.repetition_index == number}
            )
            peak_angle = None
            if self.primary_metric and self.primary_metric in ctx.series:
                value = ctx.series[self.primary_metric][rep.peak_idx]
                peak_angle = None if math.isnan(value) else float(value)
            start, peak, end = (float(ctx.times[i]) for i in (rep.start_idx, rep.peak_idx, rep.end_idx))
            events.append(
                RepetitionEvent(
                    index=number,
                    start_time=start,
                    peak_time=peak,
                    end_time=end,
                    duration=end - start,
                    peak_angle=peak_angle,
                    peak_progress=rep.peak_progress,
                    completed=rep.completed,
                    is_valid=rep.completed and not names,
                    deviations=names,
                )
            )
        return events

    def _build_summary(
        self,
        ctx: AnalysisContext,
        repetitions: list[RepetitionEvent],
        fps: float,
        without_pose: int,
        limitations: list[str],
    ) -> SessionSummary:
        detected = len(repetitions)
        valid = sum(1 for r in repetitions if r.is_valid)
        target = self.config.target_repetitions
        denominator = target if target else detected
        score = min(100.0, 100.0 * valid / denominator) if denominator else 0.0
        duration = float(ctx.times[-1] - ctx.times[0])
        if fps > 0:
            duration += 1.0 / fps
        return SessionSummary(
            exercise_id=self.exercise_id,
            case_id=self.case_id,
            side_evaluated=ctx.side.value,
            target_repetitions=target,
            completed_repetitions=detected,
            valid_repetitions=valid,
            invalid_repetitions=detected - valid,
            duration_seconds=duration,
            fps=fps,
            total_frames=len(ctx.frames),
            frames_without_pose=without_pose,
            compliance_score=round(score, 1),
            limitations=limitations,
        )

    def _build_telemetry(self, ctx: AnalysisContext, fps: float) -> list[TelemetryPoint]:
        step = max(1, round(fps / self.config.telemetry_hz)) if fps > 0 else 1
        phases = self._phases(ctx)

        def clean(value: float) -> Optional[float]:
            return None if math.isnan(value) else round(float(value), 2)

        points: list[TelemetryPoint] = []
        for i in range(0, len(ctx.times), step):
            points.append(
                TelemetryPoint(
                    timestamp=round(float(ctx.times[i]), 3),
                    progress=clean(ctx.progress[i]),
                    phase=phases[i],
                    metrics={name: clean(values[i]) for name, values in ctx.series.items()},
                )
            )
        return points
