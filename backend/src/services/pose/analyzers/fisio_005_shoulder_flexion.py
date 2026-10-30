"""FISIO-005 — Flexão de ombro com bastão leve (bilateral).

Métricas:
- Elevação frontal dos braços (ângulo quadril - ombro - cotovelo) para ambos os lados.
- Assimetria angular entre o braço direito e o esquerdo (|elevação_dir - elevação_esq|).
- Distância euclidiana entre os dois punhos (normalizada pela largura dos ombros).

Desvios mapeados (roteiros_e_rotulos.json):
- objeto_nao_utilizado (assimetria): elevar apenas um braço ou assimetria bilateral excessiva.
- pegada_alterada: soltar uma das mãos ou variação brusca da distância entre os punhos.
- amplitude_reduzida: elevação máxima insuficiente.
"""

import math

import numpy as np

from services.pose.base_analyzer import AnalysisContext, BaseExerciseAnalyzer, ExerciseConfig
from services.pose.geometry import angle_between, distance
from services.pose.joint_mapper import BodySide, Landmark
from services.pose.models import DeviationEvent, DeviationSeverity, PoseFrame

ELEVATION_RIGHT = "elevation_right"
ELEVATION_LEFT = "elevation_left"
ELEVATION_MEAN = "elevation_mean"
ASYMMETRY = "asymmetry"
WRIST_DISTANCE = "wrist_distance"


class ShoulderFlexionStickAnalyzer(BaseExerciseAnalyzer):
    case_id = "FISIO-005"
    exercise_id = "SHOULDER_FLEXION_WITH_STICK"
    bilateral = True
    primary_metric = ELEVATION_MEAN
    default_config = ExerciseConfig(
        enter=0.25,
        exit=0.12,
        min_peak=0.35,
        thresholds={
            "rest_elevation_angle": 25.0,
            "target_elevation_angle": 90.0,
            "min_peak_elevation": 70.0,
            "max_asymmetry_deg": 18.0,  # diferença tolerada entre os dois braços
            "wrist_dist_change_ratio": 0.35,  # variação da distância entre punhos para alertar pegada alterada
        },
    )

    def __init__(self, *args, **kwargs):
        kwargs["side"] = BodySide.BOTH
        super().__init__(*args, **kwargs)
        self._rest_elevation = math.nan
        self._baseline_wrist_dist = math.nan

    def compute_metrics(self, frame: PoseFrame, side: BodySide) -> dict[str, float]:
        # Braço direito
        r_hip = frame.point(Landmark.RIGHT_HIP)
        r_sh = frame.point(Landmark.RIGHT_SHOULDER)
        r_elb = frame.point(Landmark.RIGHT_ELBOW)
        elev_r = angle_between(r_hip, r_sh, r_elb)

        # Braço esquerdo
        l_hip = frame.point(Landmark.LEFT_HIP)
        l_sh = frame.point(Landmark.LEFT_SHOULDER)
        l_elb = frame.point(Landmark.LEFT_ELBOW)
        elev_l = angle_between(l_hip, l_sh, l_elb)

        # Média e assimetria
        elev_mean = (elev_r + elev_l) / 2.0 if not math.isnan(elev_r) and not math.isnan(elev_l) else (elev_r if not math.isnan(elev_r) else elev_l)
        asym = abs(elev_r - elev_l) if not math.isnan(elev_r) and not math.isnan(elev_l) else math.nan

        # Distância entre punhos
        r_w = frame.point(Landmark.RIGHT_WRIST)
        l_w = frame.point(Landmark.LEFT_WRIST)
        w_dist = distance(r_w, l_w)

        return {
            ELEVATION_RIGHT: elev_r,
            ELEVATION_LEFT: elev_l,
            ELEVATION_MEAN: elev_mean,
            ASYMMETRY: asym,
            WRIST_DISTANCE: w_dist,
        }

    def calibrate(self, series: dict[str, np.ndarray]) -> None:
        mean_elev = series.get(ELEVATION_MEAN)
        valid_elev = mean_elev[~np.isnan(mean_elev)] if mean_elev is not None else []
        self._rest_elevation = float(np.percentile(valid_elev, 10)) if len(valid_elev) else self.config.thresholds["rest_elevation_angle"]

        w_dist = series.get(WRIST_DISTANCE)
        valid_dist = w_dist[~np.isnan(w_dist)] if w_dist is not None else []
        self._baseline_wrist_dist = float(np.median(valid_dist)) if len(valid_dist) else math.nan

    def progress(self, metrics: dict[str, float]) -> float:
        elev = metrics.get(ELEVATION_MEAN, math.nan)
        target = self.config.thresholds["target_elevation_angle"]
        span = target - self._rest_elevation
        if math.isnan(elev) or math.isnan(span) or span <= 0:
            return math.nan
        return (elev - self._rest_elevation) / span

    def detect_deviations(self, ctx: AnalysisContext) -> list[DeviationEvent]:
        elev_mean = ctx.series.get(ELEVATION_MEAN)
        asym = ctx.series.get(ASYMMETRY)
        w_dist = ctx.series.get(WRIST_DISTANCE)
        if elev_mean is None or not ctx.repetitions:
            return []

        th = ctx.config.thresholds
        deviations: list[DeviationEvent] = []

        for number, rep in enumerate(ctx.repetitions, start=1):
            s, p, e = rep.start_idx, rep.peak_idx, rep.end_idx

            # 1) Amplitude reduzida na elevação
            peak_val = float(elev_mean[p])
            if peak_val < th["min_peak_elevation"]:
                deviations.append(
                    ctx.make_deviation(
                        "amplitude_reduzida",
                        DeviationSeverity.MODERADA,
                        s,
                        e,
                        f"Elevação máxima média de {peak_val:.0f}° (esperado ≥ {th['min_peak_elevation']:.0f}°)",
                        repetition_index=number,
                        evidence_idx=p,
                    )
                )

            # 2) Assimetria / Objeto não utilizado bilateralmente
            if asym is not None:
                max_asym = float(np.nanmax(asym[s : e + 1]))
                if max_asym > th["max_asymmetry_deg"]:
                    deviations.append(
                        ctx.make_deviation(
                            "objeto_nao_utilizado",
                            DeviationSeverity.MODERADA,
                            s,
                            e,
                            f"Assimetria excessiva de {max_asym:.0f}° entre os braços durante a elevação com bastão",
                            repetition_index=number,
                            evidence_idx=s + int(np.nanargmax(asym[s : e + 1])),
                        )
                    )

            # 3) Pegada alterada (variação abrupta da distância entre punhos)
            if w_dist is not None and not math.isnan(self._baseline_wrist_dist) and self._baseline_wrist_dist > 0:
                dist_ratios = np.abs(w_dist[s : e + 1] - self._baseline_wrist_dist) / self._baseline_wrist_dist
                worst_ratio = float(np.nanmax(dist_ratios))
                if worst_ratio > th["wrist_dist_change_ratio"]:
                    deviations.append(
                        ctx.make_deviation(
                            "pegada_alterada",
                            DeviationSeverity.MODERADA,
                            s,
                            e,
                            f"Alteração ou perda de contato na pegada do bastão (variação de {worst_ratio*100:.0f}%)",
                            repetition_index=number,
                            evidence_idx=s + int(np.nanargmax(dist_ratios)),
                        )
                    )

        return deviations
