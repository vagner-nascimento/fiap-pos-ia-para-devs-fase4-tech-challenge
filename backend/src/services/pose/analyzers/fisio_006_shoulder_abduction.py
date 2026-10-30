"""FISIO-006 — Abdução de ombro com faixa elástica leve (lado dinâmico).

Métricas:
- Ângulo de abdução do ombro (quadril - ombro - cotovelo) do lado ativo.
  Em repouso: braço junto ao corpo (~15°-25°).
  No pico de abdução alvo: ~75°-90°.
- Inclinação lateral do tronco (linha entre ombros ou ombro-quadril vs. vertical/horizontal).

Desvios mapeados (roteiros_e_rotulos.json):
- inclinacao_tronco: inclinação lateral do tronco para compensar a elevação.
- amplitude_reduzida: não atinge a amplitude de abdução prescrita.
- baixa_visibilidade / faixa_fora_de_quadro: visibilidade insuficiente dos landmarks do braço/mão.
"""

import math

import numpy as np

from services.pose.base_analyzer import AnalysisContext, BaseExerciseAnalyzer, ExerciseConfig
from services.pose.geometry import angle_between, segment_angle_from_vertical
from services.pose.joint_mapper import BodySide, JointMapper
from services.pose.models import DeviationEvent, DeviationSeverity, PoseFrame

ABDUCTION_ANGLE = "abduction_angle"
TRUNK_LATERAL_ANGLE = "trunk_lateral_angle"


class ShoulderAbductionBandAnalyzer(BaseExerciseAnalyzer):
    case_id = "FISIO-006"
    exercise_id = "SHOULDER_ABDUCTION_BAND"
    primary_metric = ABDUCTION_ANGLE
    default_config = ExerciseConfig(
        enter=0.3,
        exit=0.15,
        min_peak=0.4,
        thresholds={
            "rest_abduction_angle": 20.0,
            "target_abduction_angle": 80.0,
            "min_peak_angle": 65.0,  # se pico < 65°, amplitude reduzida
            "trunk_lateral_max_deg": 10.0,  # inclinação lateral compensatória tolerada
            "min_hand_visibility": 0.4,  # visibilidade mínima para declarar membros fora de quadro
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rest_angle = math.nan

    def compute_metrics(self, frame: PoseFrame, side: BodySide) -> dict[str, float]:
        m = JointMapper(side)
        # abdução: ângulo quadril-ombro-cotovelo do lado ativo
        abduction = angle_between(frame.point(m.hip), frame.point(m.shoulder), frame.point(m.elbow))
        # inclinação lateral: inclinação da linha ombro-quadril em relação à vertical
        trunk_lat = segment_angle_from_vertical(frame.point(m.shoulder), frame.point(m.hip))
        return {
            ABDUCTION_ANGLE: abduction,
            TRUNK_LATERAL_ANGLE: trunk_lat,
        }

    def visibility_landmarks(self, side: BodySide) -> list[int]:
        m = JointMapper(side)
        return [m.shoulder, m.elbow, m.wrist]

    def calibrate(self, series: dict[str, np.ndarray]) -> None:
        abd = series.get(ABDUCTION_ANGLE)
        valid = abd[~np.isnan(abd)] if abd is not None else []
        self._rest_angle = float(np.percentile(valid, 10)) if len(valid) else self.config.thresholds["rest_abduction_angle"]

    def progress(self, metrics: dict[str, float]) -> float:
        abd = metrics.get(ABDUCTION_ANGLE, math.nan)
        target = self.config.thresholds["target_abduction_angle"]
        span = target - self._rest_angle
        if math.isnan(abd) or math.isnan(span) or span <= 0:
            return math.nan
        return (abd - self._rest_angle) / span

    def detect_deviations(self, ctx: AnalysisContext) -> list[DeviationEvent]:
        abd = ctx.series.get(ABDUCTION_ANGLE)
        trunk = ctx.series.get(TRUNK_LATERAL_ANGLE)
        if abd is None or trunk is None or not ctx.repetitions:
            return []

        th = ctx.config.thresholds
        trunk_baseline = self._trunk_baseline(ctx, trunk)
        m = JointMapper(ctx.side)
        deviations: list[DeviationEvent] = []

        for number, rep in enumerate(ctx.repetitions, start=1):
            s, p, e = rep.start_idx, rep.peak_idx, rep.end_idx

            # 1) Amplitude reduzida
            peak_angle = float(abd[p])
            if peak_angle < th["min_peak_angle"]:
                deficit = th["min_peak_angle"] - peak_angle
                severity = (
                    DeviationSeverity.LEVE
                    if deficit <= 8
                    else DeviationSeverity.MODERADA
                    if deficit <= 18
                    else DeviationSeverity.GRAVE
                )
                deviations.append(
                    ctx.make_deviation(
                        "amplitude_reduzida",
                        severity,
                        s,
                        e,
                        f"Abdução máxima de {peak_angle:.0f}° (esperado ≥ {th['min_peak_angle']:.0f}°)",
                        repetition_index=number,
                        evidence_idx=p,
                    )
                )

            # 2) Inclinação lateral compensatória do tronco
            dev_trunk = np.abs(trunk[s : e + 1] - trunk_baseline)
            if not np.all(np.isnan(dev_trunk)):
                worst = int(np.nanargmax(dev_trunk))
                excursion = float(dev_trunk[worst])
                if excursion > th["trunk_lateral_max_deg"]:
                    severity = (
                        DeviationSeverity.LEVE
                        if excursion < 15
                        else DeviationSeverity.MODERADA
                        if excursion < 25
                        else DeviationSeverity.GRAVE
                    )
                    deviations.append(
                        ctx.make_deviation(
                            "inclinacao_tronco",
                            severity,
                            s,
                            e,
                            f"Inclinação lateral do tronco de {excursion:.0f}° para compensar elevação (limite {th['trunk_lateral_max_deg']:.0f}°)",
                            repetition_index=number,
                            evidence_idx=s + worst,
                        )
                    )

            # 3) Visibilidade do braço / mão fora de quadro
            visibilities = [
                ctx.frames[i].visibility(m.wrist) for i in range(s, e + 1) if ctx.frames[i].has_pose
            ]
            if visibilities and float(np.mean(visibilities)) < th["min_hand_visibility"]:
                deviations.append(
                    ctx.make_deviation(
                        "faixa_fora_de_quadro",
                        DeviationSeverity.MODERADA,
                        s,
                        e,
                        "Membro ou faixa elástica parcialmente fora do enquadramento da câmera durante o movimento",
                        repetition_index=number,
                        evidence_idx=p,
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
