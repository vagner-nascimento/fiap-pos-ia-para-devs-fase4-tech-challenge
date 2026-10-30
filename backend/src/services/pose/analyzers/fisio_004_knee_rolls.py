"""FISIO-004 — Rotação controlada dos joelhos em decúbito dorsal (bilateral).

Métricas (decúbito dorsal, pernas flexionadas):
- Ângulo de rotação lateral dos joelhos (inclinação da linha média de quadril aos joelhos).
- Distância entre joelho direito e esquerdo (normalizada pela largura dos quadris).
- Inclinação da linha escapular (ombro direito - ombro esquerdo) para verificar se os ombros permanecem apoiados.

Desvios mapeados (roteiros_e_rotulos.json):
- joelhos_separados: distância entre os joelhos aumenta expressivamente durante a rotação.
- ombros_elevados: elevação/descolamento do ombro oposto do colchonete.
- retorno_incompleto: alternar para o outro lado sem passar pelo centro neutro (|rotação| < limiar).
"""

import math

import numpy as np

from services.pose.base_analyzer import AnalysisContext, BaseExerciseAnalyzer, ExerciseConfig
from services.pose.geometry import distance, midpoint, segment_angle_from_vertical
from services.pose.joint_mapper import BodySide, Landmark
from services.pose.models import DeviationEvent, DeviationSeverity, PoseFrame

KNEE_ROLL_ANGLE = "knee_roll_angle"
KNEE_SEPARATION = "knee_separation"
SHOULDER_TILT = "shoulder_tilt"


class KneeRollsAnalyzer(BaseExerciseAnalyzer):
    case_id = "FISIO-004"
    exercise_id = "SUPINE_KNEE_ROLLS"
    bilateral = True
    primary_metric = KNEE_ROLL_ANGLE
    default_config = ExerciseConfig(
        enter=0.25,
        exit=0.12,
        min_peak=0.35,
        thresholds={
            "target_roll_angle": 35.0,  # rotação lateral confortável
            "max_knee_separation_ratio": 1.4,  # aumento relativo da distância entre joelhos
            "max_shoulder_tilt_deg": 14.0,  # rotação escapular máxima tolerada
            "neutral_center_angle": 12.0,  # limite da faixa neutra central
        },
    )

    def __init__(self, *args, **kwargs):
        kwargs["side"] = BodySide.BOTH
        super().__init__(*args, **kwargs)
        self._baseline_knee_dist = math.nan

    def compute_metrics(self, frame: PoseFrame, side: BodySide) -> dict[str, float]:
        r_hip = frame.point(Landmark.RIGHT_HIP)
        l_hip = frame.point(Landmark.LEFT_HIP)
        r_knee = frame.point(Landmark.RIGHT_KNEE)
        l_knee = frame.point(Landmark.LEFT_KNEE)
        r_sh = frame.point(Landmark.RIGHT_SHOULDER)
        l_sh = frame.point(Landmark.LEFT_SHOULDER)

        hip_mid = midpoint(r_hip, l_hip)
        knee_mid = midpoint(r_knee, l_knee)

        # Ângulo de rotação lateral dos joelhos
        roll = abs(segment_angle_from_vertical(knee_mid, hip_mid))

        # Distância entre joelhos
        knee_dist = distance(r_knee, l_knee)

        # Inclinação escapular (ombro a ombro)
        if not np.all(np.isnan(r_sh)) and not np.all(np.isnan(l_sh)):
            sh_diff_y = abs(r_sh[1] - l_sh[1])
            sh_width = distance(r_sh, l_sh)
            sh_tilt = math.degrees(math.asin(min(1.0, sh_diff_y / sh_width))) if sh_width > 0 else 0.0
        else:
            sh_tilt = math.nan

        return {
            KNEE_ROLL_ANGLE: roll,
            KNEE_SEPARATION: knee_dist,
            SHOULDER_TILT: sh_tilt,
        }

    def calibrate(self, series: dict[str, np.ndarray]) -> None:
        dist = series.get(KNEE_SEPARATION)
        valid = dist[~np.isnan(dist)] if dist is not None else []
        self._baseline_knee_dist = float(np.percentile(valid, 20)) if len(valid) else math.nan

    def progress(self, metrics: dict[str, float]) -> float:
        roll = metrics.get(KNEE_ROLL_ANGLE, math.nan)
        target = self.config.thresholds["target_roll_angle"]
        if math.isnan(roll) or target <= 0:
            return math.nan
        return roll / target

    def detect_deviations(self, ctx: AnalysisContext) -> list[DeviationEvent]:
        roll = ctx.series.get(KNEE_ROLL_ANGLE)
        sep = ctx.series.get(KNEE_SEPARATION)
        sh_tilt = ctx.series.get(SHOULDER_TILT)
        if roll is None or not ctx.repetitions:
            return []

        th = ctx.config.thresholds
        deviations: list[DeviationEvent] = []

        for number, rep in enumerate(ctx.repetitions, start=1):
            s, p, e = rep.start_idx, rep.peak_idx, rep.end_idx

            # 1) Joelhos separados
            if sep is not None and not math.isnan(self._baseline_knee_dist) and self._baseline_knee_dist > 0:
                sep_ratios = sep[s : e + 1] / self._baseline_knee_dist
                worst_ratio = float(np.nanmax(sep_ratios))
                if worst_ratio > th["max_knee_separation_ratio"]:
                    deviations.append(
                        ctx.make_deviation(
                            "joelhos_separados",
                            DeviationSeverity.MODERADA,
                            s,
                            e,
                            f"Separação excessiva entre os joelhos durante a rotação ({worst_ratio:.1f}x acima do neutro)",
                            repetition_index=number,
                            evidence_idx=s + int(np.nanargmax(sep_ratios)),
                        )
                    )

            # 2) Ombros elevados (perda de contato escapular com o colchonete)
            if sh_tilt is not None:
                max_tilt = float(np.nanmax(sh_tilt[s : e + 1]))
                if max_tilt > th["max_shoulder_tilt_deg"]:
                    deviations.append(
                        ctx.make_deviation(
                            "ombros_elevados",
                            DeviationSeverity.MODERADA,
                            s,
                            e,
                            f"Elevação indevida dos ombros durante a rotação (inclinação escapular de {max_tilt:.0f}°)",
                            repetition_index=number,
                            evidence_idx=s + int(np.nanargmax(sh_tilt[s : e + 1])),
                        )
                    )

            # 3) Retorno incompleto ao centro antes da próxima repetição
            if rep.completed and number < len(ctx.repetitions):
                end_roll = float(roll[e])
                if end_roll > th["neutral_center_angle"]:
                    deviations.append(
                        ctx.make_deviation(
                            "retorno_incompleto",
                            DeviationSeverity.MODERADA,
                            s,
                            e,
                            f"Não retornou completamente ao centro neutro antes de mudar de lado ({end_roll:.0f}° residual)",
                            repetition_index=number,
                            evidence_idx=e,
                        )
                    )

        return deviations
