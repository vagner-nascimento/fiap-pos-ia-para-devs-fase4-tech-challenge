"""FISIO-001 — Extensão de joelho sentado (lado dinâmico).

Métricas (lado ativo, vista lateral): ângulo do joelho (quadril-joelho-tornozelo) e inclinação do
tronco (ombro-quadril vs. vertical).

Limiares calibrados com os 4 clipes do dataset (amostrados a ~30 fps):

==========================  ==========  ==========================================
Medida                      Correto     Desvio rotulado
==========================  ==========  ==========================================
Pico de extensão            152–156°    extensão parcial: 137–149°
Excursão do tronco          ≤ 2,6°      inclinação do tronco: 8,5–24,9°
Tempo de retorno            0,73–0,83s  ritmo irregular: 0,30–0,33s (e 1,2–2,0s)
Vel. máx. de retorno        ≤ 137°/s    ritmo irregular: 287–310°/s
Picos de extensão por rep.  1           ritmo irregular: 2
==========================  ==========  ==========================================
"""

import math

import numpy as np
from scipy.signal import find_peaks

from services.pose.base_analyzer import AnalysisContext, BaseExerciseAnalyzer, ExerciseConfig
from services.pose.geometry import angle_between, segment_angle_from_vertical
from services.pose.joint_mapper import BodySide, JointMapper
from services.pose.models import DeviationEvent, DeviationSeverity, PoseFrame

KNEE_ANGLE = "knee_angle"
TRUNK_ANGLE = "trunk_angle"


class KneeExtensionAnalyzer(BaseExerciseAnalyzer):
    case_id = "FISIO-001"
    exercise_id = "KNEE_EXTENSION_SEATED"
    primary_metric = KNEE_ANGLE
    default_config = ExerciseConfig(
        enter=0.3,
        exit=0.15,
        min_peak=0.4,
        thresholds={
            "target_angle": 150.0,  # extensão de referência (normaliza o progresso)
            "min_peak_angle": 150.0,  # abaixo disso: amplitude reduzida
            "trunk_max_deg": 8.0,  # excursão máxima do tronco dentro da repetição
            "min_return_seconds": 0.45,  # retorno mais rápido que isso: abrupto
            "max_return_velocity": 250.0,  # °/s
            "peak_prominence": 8.0,  # ° para contar um pico de extensão
            "max_peaks": 1,
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rest_angle = math.nan

    # ---- métricas -------------------------------------------------------

    def compute_metrics(self, frame: PoseFrame, side: BodySide) -> dict[str, float]:
        m = JointMapper(side)
        return {
            KNEE_ANGLE: angle_between(frame.point(m.hip), frame.point(m.knee), frame.point(m.ankle)),
            TRUNK_ANGLE: segment_angle_from_vertical(
                frame.point(m.shoulder), frame.point(m.hip)
            ),
        }

    def visibility_landmarks(self, side: BodySide) -> list[int]:
        m = JointMapper(side)
        return [m.hip, m.knee, m.ankle]

    def calibrate(self, series: dict[str, np.ndarray]) -> None:
        knee = series.get(KNEE_ANGLE)
        valid = knee[~np.isnan(knee)] if knee is not None else []
        self._rest_angle = float(np.percentile(valid, 10)) if len(valid) else math.nan

    def progress(self, metrics: dict[str, float]) -> float:
        knee = metrics.get(KNEE_ANGLE, math.nan)
        span = self.config.thresholds["target_angle"] - self._rest_angle
        if math.isnan(knee) or math.isnan(span) or span <= 0:
            return math.nan
        return (knee - self._rest_angle) / span

    # ---- desvios --------------------------------------------------------

    def detect_deviations(self, ctx: AnalysisContext) -> list[DeviationEvent]:
        knee = ctx.series.get(KNEE_ANGLE)
        trunk = ctx.series.get(TRUNK_ANGLE)
        if knee is None or trunk is None or not ctx.repetitions:
            return []

        th = ctx.config.thresholds
        trunk_baseline = self._trunk_baseline(ctx, trunk)
        velocity = np.gradient(knee, ctx.times) if len(ctx.times) > 1 else np.zeros_like(knee)
        deviations: list[DeviationEvent] = []

        for number, rep in enumerate(ctx.repetitions, start=1):
            s, p, e = rep.start_idx, rep.peak_idx, rep.end_idx

            # 1) amplitude reduzida
            peak_angle = float(knee[p])
            if peak_angle < th["min_peak_angle"]:
                deficit = th["min_peak_angle"] - peak_angle
                severity = (
                    DeviationSeverity.LEVE
                    if deficit <= 8
                    else DeviationSeverity.MODERADA
                    if deficit <= 20
                    else DeviationSeverity.GRAVE
                )
                deviations.append(
                    ctx.make_deviation(
                        "amplitude_reduzida",
                        severity,
                        s,
                        e,
                        f"Extensão máxima de {peak_angle:.0f}° (esperado ≥ {th['min_peak_angle']:.0f}°)",
                        repetition_index=number,
                        evidence_idx=p,
                    )
                )

            # 2) compensação de tronco (apenas dentro da repetição)
            deviation_trunk = np.abs(trunk[s : e + 1] - trunk_baseline)
            if not np.all(np.isnan(deviation_trunk)):
                worst = int(np.nanargmax(deviation_trunk))
                excursion = float(deviation_trunk[worst])
                if excursion > th["trunk_max_deg"]:
                    severity = (
                        DeviationSeverity.LEVE
                        if excursion < 12
                        else DeviationSeverity.MODERADA
                        if excursion < 20
                        else DeviationSeverity.GRAVE
                    )
                    deviations.append(
                        ctx.make_deviation(
                            "compensacao_tronco",
                            severity,
                            s,
                            e,
                            f"Tronco deslocou {excursion:.0f}° da posição inicial durante a extensão "
                            f"(limite {th['trunk_max_deg']:.0f}°)",
                            repetition_index=number,
                            evidence_idx=s + worst,
                        )
                    )

            # 3) ritmo acelerado / irregular
            reasons: list[str] = []
            return_time = float(ctx.times[e] - ctx.times[p])
            if return_time < th["min_return_seconds"]:
                reasons.append(f"retorno abrupto ({return_time:.2f} s)")
            fall = float(np.nanmin(velocity[p : e + 1]))
            if -fall > th["max_return_velocity"]:
                reasons.append(f"velocidade de retorno de {-fall:.0f}°/s")
            segment = self._fill(knee[s : e + 1])
            peaks, _ = find_peaks(segment, prominence=th["peak_prominence"])
            if len(peaks) > th["max_peaks"]:
                reasons.append(f"{len(peaks)} picos de extensão na mesma repetição")
            if reasons:
                deviations.append(
                    ctx.make_deviation(
                        "ritmo_acelerado",
                        DeviationSeverity.GRAVE if len(reasons) >= 2 else DeviationSeverity.MODERADA,
                        s,
                        e,
                        "Ritmo irregular: " + "; ".join(reasons),
                        repetition_index=number,
                        evidence_idx=p,
                    )
                )
        return deviations

    @staticmethod
    def _fill(values: np.ndarray) -> np.ndarray:
        mask = np.isnan(values)
        if mask.all():
            return np.zeros_like(values)
        idx = np.arange(len(values))
        return np.interp(idx, idx[~mask], values[~mask])

    @staticmethod
    def _trunk_baseline(ctx: AnalysisContext, trunk: np.ndarray) -> float:
        """Inclinação típica do tronco em repouso (fora das repetições)."""
        mask = ~np.isnan(trunk) & (ctx.progress < ctx.config.exit)
        for rep in ctx.repetitions:
            mask[rep.start_idx : rep.end_idx + 1] = False
        values = trunk[mask] if mask.any() else trunk[~np.isnan(trunk)]
        return float(np.median(values)) if len(values) else 0.0
