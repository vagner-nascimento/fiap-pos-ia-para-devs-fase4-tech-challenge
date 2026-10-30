"""FISIO-003 — Inclinação pélvica em decúbito dorsal (bilateral).

Métricas (decúbito dorsal sobre colchonete):
- Elevação vertical do quadril/pelve (deslocamento vertical relativo aos ombros e joelhos).
- Duração e velocidade do ciclo de inclinação.

Desvios mapeados (roteiros_e_rotulos.json):
- elevacao_pelve: elevar as nádegas/quadril transformando o movimento em ponte parcial.
- movimento_abrupto: velocidade excessiva ou tempo total de repetição muito curto (< 0.9s).
"""

import math

import numpy as np

from services.pose.base_analyzer import AnalysisContext, BaseExerciseAnalyzer, ExerciseConfig
from services.pose.geometry import midpoint
from services.pose.joint_mapper import BodySide, Landmark
from services.pose.models import DeviationEvent, DeviationSeverity, PoseFrame

PELVIS_ELEVATION = "pelvis_elevation"


class PelvicTiltAnalyzer(BaseExerciseAnalyzer):
    case_id = "FISIO-003"
    exercise_id = "SUPINE_PELVIC_TILT"
    bilateral = True
    primary_metric = PELVIS_ELEVATION
    default_config = ExerciseConfig(
        enter=0.25,
        exit=0.12,
        min_peak=0.3,
        thresholds={
            "target_tilt_px": 20.0,  # deslocamento vertical esperado de inclinação sutil
            "max_pelvis_bridge_px": 45.0,  # acima disso é elevação indevida das nádegas (ponte)
            "min_cycle_duration_seconds": 0.9,  # abaixo disso é movimento abrupto
        },
    )

    def __init__(self, *args, **kwargs):
        kwargs["side"] = BodySide.BOTH
        super().__init__(*args, **kwargs)
        self._baseline_pelvis_y = math.nan

    def compute_metrics(self, frame: PoseFrame, side: BodySide) -> dict[str, float]:
        # Em imagem: y cresce para baixo. Elevação significa y diminuir (subir em relação ao chão).
        r_hip = frame.point(Landmark.RIGHT_HIP)
        l_hip = frame.point(Landmark.LEFT_HIP)
        r_sh = frame.point(Landmark.RIGHT_SHOULDER)
        l_sh = frame.point(Landmark.LEFT_SHOULDER)

        hip_mid = midpoint(r_hip, l_hip)
        sh_mid = midpoint(r_sh, l_sh)

        # Distância vertical do quadril em relação aos ombros (como referência estável do solo)
        if not np.all(np.isnan(hip_mid)) and not np.all(np.isnan(sh_mid)):
            rel_elevation = sh_mid[1] - hip_mid[1]
        else:
            rel_elevation = math.nan

        return {
            PELVIS_ELEVATION: rel_elevation,
        }

    def calibrate(self, series: dict[str, np.ndarray]) -> None:
        elev = series.get(PELVIS_ELEVATION)
        valid = elev[~np.isnan(elev)] if elev is not None else []
        self._baseline_pelvis_y = float(np.median(valid)) if len(valid) else 0.0

    def progress(self, metrics: dict[str, float]) -> float:
        elev = metrics.get(PELVIS_ELEVATION, math.nan)
        target = self.config.thresholds["target_tilt_px"]
        if math.isnan(elev) or math.isnan(self._baseline_pelvis_y) or target <= 0:
            return math.nan
        # deslocamento positivo em relação ao repouso
        return abs(elev - self._baseline_pelvis_y) / target

    def detect_deviations(self, ctx: AnalysisContext) -> list[DeviationEvent]:
        elev = ctx.series.get(PELVIS_ELEVATION)
        if elev is None or not ctx.repetitions:
            return []

        th = ctx.config.thresholds
        deviations: list[DeviationEvent] = []

        for number, rep in enumerate(ctx.repetitions, start=1):
            s, p, e = rep.start_idx, rep.peak_idx, rep.end_idx

            # 1) Elevação excessiva da pelve (nádegas saem do colchonete em ponte)
            peak_displacement = abs(float(elev[p]) - self._baseline_pelvis_y)
            if peak_displacement > th["max_pelvis_bridge_px"]:
                deviations.append(
                    ctx.make_deviation(
                        "elevacao_pelve",
                        DeviationSeverity.MODERADA,
                        s,
                        e,
                        f"Elevação indevida das nádegas/pelve ({peak_displacement:.0f}px acima do neutro, limite {th['max_pelvis_bridge_px']:.0f}px)",
                        repetition_index=number,
                        evidence_idx=p,
                    )
                )

            # 2) Movimento abrupto (duração excessivamente rápida)
            dur = float(ctx.times[e] - ctx.times[s])
            if dur < th["min_cycle_duration_seconds"]:
                deviations.append(
                    ctx.make_deviation(
                        "movimento_abrupto",
                        DeviationSeverity.MODERADA,
                        s,
                        e,
                        f"Execução excessivamente rápida ({dur:.2f}s, esperado ≥ {th['min_cycle_duration_seconds']:.2f}s)",
                        repetition_index=number,
                        evidence_idx=p,
                    )
                )

        return deviations
