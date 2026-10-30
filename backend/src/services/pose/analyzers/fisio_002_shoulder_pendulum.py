"""FISIO-002 — Exercício pendular do ombro (lado dinâmico / pendente).

Métricas:
- Ângulo de oscilação do braço pendente em relação à vertical (ombro - cotovelo/punho).
- Ângulo do cotovelo do braço pendente (ombro - cotovelo - punho). Braço relaxado tem cotovelo estendido (~160°-180°).
- Elevação vertical do ombro pendente (diferença vertical entre ombro e quadril).

Desvios mapeados (roteiros_e_rotulos.json):
- elevacao_ativa: elevar o ombro ativamente (encolher ombro) durante a oscilação.
- amplitude_excessiva: oscilação ampla além do limiar suave de pêndulo (> 35° da vertical).
- braco_rigido: flexão e rigidez do cotovelo (< 145°) sem relaxamento pendular.
"""

import math

import numpy as np

from services.pose.base_analyzer import AnalysisContext, BaseExerciseAnalyzer, ExerciseConfig
from services.pose.geometry import angle_between, segment_angle_from_vertical
from services.pose.joint_mapper import BodySide, JointMapper
from services.pose.models import DeviationEvent, DeviationSeverity, PoseFrame

PENDULUM_ANGLE = "pendulum_angle"
ELBOW_ANGLE = "elbow_angle"
SHOULDER_ELEVATION = "shoulder_elevation"


class ShoulderPendulumAnalyzer(BaseExerciseAnalyzer):
    case_id = "FISIO-002"
    exercise_id = "SHOULDER_PENDULUM"
    primary_metric = PENDULUM_ANGLE
    default_config = ExerciseConfig(
        enter=0.25,
        exit=0.12,
        min_peak=0.35,
        thresholds={
            "target_pendulum_angle": 25.0,  # oscilação suave ideal em torno da vertical
            "max_pendulum_angle": 38.0,  # acima disso: amplitude excessiva
            "min_elbow_relaxed_angle": 145.0,  # abaixo disso: braço rígido / flexionado
            "max_shoulder_elevation_px": 25.0,  # elevação do ombro em pixels acima do repouso
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shoulder_rest_y = math.nan

    def compute_metrics(self, frame: PoseFrame, side: BodySide) -> dict[str, float]:
        m = JointMapper(side)
        # oscilação pendular com a vertical
        pendulum = abs(segment_angle_from_vertical(frame.point(m.wrist), frame.point(m.shoulder)))
        # extensão do cotovelo
        elbow = angle_between(frame.point(m.shoulder), frame.point(m.elbow), frame.point(m.wrist))
        # altura relativa do ombro
        sh_pt = frame.point(m.shoulder)
        hip_pt = frame.point(m.hip)
        elevation = (hip_pt[1] - sh_pt[1]) if not np.isnan(sh_pt[1]) and not np.isnan(hip_pt[1]) else math.nan

        return {
            PENDULUM_ANGLE: pendulum,
            ELBOW_ANGLE: elbow,
            SHOULDER_ELEVATION: elevation,
        }

    def visibility_landmarks(self, side: BodySide) -> list[int]:
        m = JointMapper(side)
        return [m.shoulder, m.elbow, m.wrist]

    def calibrate(self, series: dict[str, np.ndarray]) -> None:
        elev = series.get(SHOULDER_ELEVATION)
        valid = elev[~np.isnan(elev)] if elev is not None else []
        self._shoulder_rest_y = float(np.median(valid)) if len(valid) else math.nan

    def progress(self, metrics: dict[str, float]) -> float:
        pendulum = metrics.get(PENDULUM_ANGLE, math.nan)
        target = self.config.thresholds["target_pendulum_angle"]
        if math.isnan(pendulum) or target <= 0:
            return math.nan
        return pendulum / target

    def detect_deviations(self, ctx: AnalysisContext) -> list[DeviationEvent]:
        pendulum = ctx.series.get(PENDULUM_ANGLE)
        elbow = ctx.series.get(ELBOW_ANGLE)
        elev = ctx.series.get(SHOULDER_ELEVATION)
        if pendulum is None or not ctx.repetitions:
            return []

        th = ctx.config.thresholds
        deviations: list[DeviationEvent] = []

        for number, rep in enumerate(ctx.repetitions, start=1):
            s, p, e = rep.start_idx, rep.peak_idx, rep.end_idx

            # 1) Amplitude excessiva
            peak_angle = float(pendulum[p])
            if peak_angle > th["max_pendulum_angle"]:
                deviations.append(
                    ctx.make_deviation(
                        "amplitude_excessiva",
                        DeviationSeverity.MODERADA,
                        s,
                        e,
                        f"Oscilação pendular excessiva de {peak_angle:.0f}° (limite recomendado {th['max_pendulum_angle']:.0f}°)",
                        repetition_index=number,
                        evidence_idx=p,
                    )
                )

            # 2) Braço rígido (cotovelo contraído sem relaxamento)
            if elbow is not None:
                min_elbow = float(np.nanmin(elbow[s : e + 1]))
                if min_elbow < th["min_elbow_relaxed_angle"]:
                    deviations.append(
                        ctx.make_deviation(
                            "braco_rigido",
                            DeviationSeverity.LEVE if min_elbow > 130 else DeviationSeverity.MODERADA,
                            s,
                            e,
                            f"Cotovelo contraído a {min_elbow:.0f}° durante o pêndulo (esperado braço relaxado ≥ {th['min_elbow_relaxed_angle']:.0f}°)",
                            repetition_index=number,
                            evidence_idx=s + int(np.nanargmin(elbow[s : e + 1])),
                        )
                    )

            # 3) Elevação ativa do ombro
            if elev is not None and not math.isnan(self._shoulder_rest_y):
                delta_elev = np.nanmax(elev[s : e + 1] - self._shoulder_rest_y)
                if delta_elev > th["max_shoulder_elevation_px"]:
                    deviations.append(
                        ctx.make_deviation(
                            "elevacao_ativa",
                            DeviationSeverity.MODERADA,
                            s,
                            e,
                            f"Elevação ativa indevida do ombro durante o movimento pendular",
                            repetition_index=number,
                            evidence_idx=p,
                        )
                    )

        return deviations
