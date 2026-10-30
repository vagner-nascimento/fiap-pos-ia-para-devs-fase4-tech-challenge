"""FISIO-007 — Flexão de cotovelo com halter leve (lado dinâmico).

Métricas:
- Ângulo do cotovelo (ombro - cotovelo - punho) do lado ativo.
  Em repouso/extensão: ~150°-170°. Em pico de flexão: ~40°-60°.
  Progresso normalizado calculado sobre a flexão (180° - ângulo do cotovelo).
- Inclinação do tronco (ombro - quadril vs. vertical).

Desvios mapeados (roteiros_e_rotulos.json):
- balanco_tronco: oscilação anteroposterior do tronco > limiar durante a flexão.
- retorno_incompleto: não retornar à posição de extensão completa antes da próxima repetição.
- cotovelo_deslocado / amplitude_reduzida: flexão insuficiente no pico.
"""

import math

import numpy as np

from services.pose.base_analyzer import AnalysisContext, BaseExerciseAnalyzer, ExerciseConfig
from services.pose.geometry import angle_between, segment_angle_from_vertical
from services.pose.joint_mapper import BodySide, JointMapper
from services.pose.models import DeviationEvent, DeviationSeverity, PoseFrame

ELBOW_ANGLE = "elbow_angle"
TRUNK_ANGLE = "trunk_angle"


class ElbowFlexionAnalyzer(BaseExerciseAnalyzer):
    case_id = "FISIO-007"
    exercise_id = "ELBOW_FLEXION_LIGHT_DUMBBELL"
    primary_metric = ELBOW_ANGLE
    default_config = ExerciseConfig(
        enter=0.3,
        exit=0.15,
        min_peak=0.4,
        thresholds={
            "rest_elbow_angle": 155.0,  # ângulo estendido de repouso esperado
            "target_flexion_angle": 55.0,  # pico esperado de flexão máxima
            "min_flexion_peak_angle": 75.0,  # se pico > 75° de cotovelo (flexão < 105°), amplitude reduzida
            "trunk_max_deg": 10.0,  # balanço de tronco tolerado na repetição
            "incomplete_return_angle": 130.0,  # se ao fim da repetição o cotovelo não abrir além disso: retorno incompleto
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rest_angle = math.nan

    def compute_metrics(self, frame: PoseFrame, side: BodySide) -> dict[str, float]:
        m = JointMapper(side)
        return {
            ELBOW_ANGLE: angle_between(frame.point(m.shoulder), frame.point(m.elbow), frame.point(m.wrist)),
            TRUNK_ANGLE: segment_angle_from_vertical(frame.point(m.shoulder), frame.point(m.hip)),
        }

    def visibility_landmarks(self, side: BodySide) -> list[int]:
        m = JointMapper(side)
        return [m.shoulder, m.elbow, m.wrist]

    def calibrate(self, series: dict[str, np.ndarray]) -> None:
        elbow = series.get(ELBOW_ANGLE)
        valid = elbow[~np.isnan(elbow)] if elbow is not None else []
        # repouso é quando o braço está estendido (percentil 90 dos maiores ângulos)
        self._rest_angle = float(np.percentile(valid, 90)) if len(valid) else self.config.thresholds["rest_elbow_angle"]

    def progress(self, metrics: dict[str, float]) -> float:
        elbow = metrics.get(ELBOW_ANGLE, math.nan)
        target = self.config.thresholds["target_flexion_angle"]
        span = self._rest_angle - target
        if math.isnan(elbow) or math.isnan(span) or span <= 0:
            return math.nan
        # progresso cresce conforme o ângulo do cotovelo diminui (flexiona)
        return (self._rest_angle - elbow) / span

    def detect_deviations(self, ctx: AnalysisContext) -> list[DeviationEvent]:
        elbow = ctx.series.get(ELBOW_ANGLE)
        trunk = ctx.series.get(TRUNK_ANGLE)
        if elbow is None or trunk is None or not ctx.repetitions:
            return []

        th = ctx.config.thresholds
        trunk_baseline = self._trunk_baseline(ctx, trunk)
        deviations: list[DeviationEvent] = []

        for number, rep in enumerate(ctx.repetitions, start=1):
            s, p, e = rep.start_idx, rep.peak_idx, rep.end_idx

            # 1) Amplitude reduzida (flexão incompleta no pico)
            peak_angle = float(elbow[p])
            if peak_angle > th["min_flexion_peak_angle"]:
                deficit = peak_angle - th["min_flexion_peak_angle"]
                severity = (
                    DeviationSeverity.LEVE
                    if deficit <= 10
                    else DeviationSeverity.MODERADA
                    if deficit <= 25
                    else DeviationSeverity.GRAVE
                )
                deviations.append(
                    ctx.make_deviation(
                        "amplitude_reduzida",
                        severity,
                        s,
                        e,
                        f"Flexão máxima atingiu apenas cotovelo a {peak_angle:.0f}° (esperado ≤ {th['min_flexion_peak_angle']:.0f}°)",
                        repetition_index=number,
                        evidence_idx=p,
                    )
                )

            # 2) Balanço de tronco durante a repetição
            deviation_trunk = np.abs(trunk[s : e + 1] - trunk_baseline)
            if not np.all(np.isnan(deviation_trunk)):
                worst = int(np.nanargmax(deviation_trunk))
                excursion = float(deviation_trunk[worst])
                if excursion > th["trunk_max_deg"]:
                    severity = (
                        DeviationSeverity.LEVE
                        if excursion < 15
                        else DeviationSeverity.MODERADA
                        if excursion < 25
                        else DeviationSeverity.GRAVE
                    )
                    deviations.append(
                        ctx.make_deviation(
                            "balanco_tronco",
                            severity,
                            s,
                            e,
                            f"Balanço compensatório do tronco de {excursion:.0f}° (limite {th['trunk_max_deg']:.0f}°)",
                            repetition_index=number,
                            evidence_idx=s + worst,
                        )
                    )

            # 3) Retorno incompleto (cotovelo não estendeu de volta ao finalizar)
            end_angle = float(elbow[e])
            if rep.completed and end_angle < th["incomplete_return_angle"]:
                deviations.append(
                    ctx.make_deviation(
                        "retorno_incompleto",
                        DeviationSeverity.MODERADA,
                        s,
                        e,
                        f"Retorno incompleto: cotovelo estendeu apenas até {end_angle:.0f}° (esperado ≥ {th['incomplete_return_angle']:.0f}°)",
                        repetition_index=number,
                        evidence_idx=e,
                    )
                )

        return deviations

    @staticmethod
    def _trunk_baseline(ctx: AnalysisContext, trunk: np.ndarray) -> float:
        mask = ~np.isnan(trunk) & (ctx.progress < ctx.config.exit)
        for rep in ctx.repetitions:
            mask[rep.start_idx : rep.end_idx + 1] = False
        values = trunk[mask] if mask.any() else trunk[~np.isnan(trunk)]
        return float(np.median(values)) if len(values) else 0.0
