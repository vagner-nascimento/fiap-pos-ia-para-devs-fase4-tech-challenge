"""Registro dos analisadores por ``case_id`` ou ``exercise_id``."""

from typing import Optional, Type

from services.pose.analyzers.fisio_001_knee_extension import KneeExtensionAnalyzer
from services.pose.analyzers.fisio_002_shoulder_pendulum import ShoulderPendulumAnalyzer
from services.pose.analyzers.fisio_003_pelvic_tilt import PelvicTiltAnalyzer
from services.pose.analyzers.fisio_004_knee_rolls import KneeRollsAnalyzer
from services.pose.analyzers.fisio_005_shoulder_flexion import ShoulderFlexionStickAnalyzer
from services.pose.analyzers.fisio_006_shoulder_abduction import ShoulderAbductionBandAnalyzer
from services.pose.analyzers.fisio_007_elbow_flexion import ElbowFlexionAnalyzer
from services.pose.base_analyzer import BaseExerciseAnalyzer
from services.pose.joint_mapper import BodySide

_ANALYZERS: list[Type[BaseExerciseAnalyzer]] = [
    KneeExtensionAnalyzer,
    ShoulderPendulumAnalyzer,
    PelvicTiltAnalyzer,
    KneeRollsAnalyzer,
    ShoulderFlexionStickAnalyzer,
    ShoulderAbductionBandAnalyzer,
    ElbowFlexionAnalyzer,
]

_BY_ID: dict[str, Type[BaseExerciseAnalyzer]] = {}
for _cls in _ANALYZERS:
    _BY_ID[_cls.case_id.upper()] = _cls
    _BY_ID[_cls.exercise_id.upper()] = _cls


def supported_exercises() -> list[str]:
    return sorted({cls.case_id for cls in _ANALYZERS})


def get_analyzer(
    identifier: str,
    side: BodySide | str | None = BodySide.AUTO,
    target_repetitions: Optional[int] = None,
) -> BaseExerciseAnalyzer:
    """Instancia o analisador de um exercício (``FISIO-001`` ou ``KNEE_EXTENSION_SEATED``)."""
    cls = _BY_ID.get(identifier.strip().upper())
    if cls is None:
        raise KeyError(
            f"Exercício não suportado: {identifier!r}. Disponíveis: {', '.join(supported_exercises())}"
        )
    return cls(side=side, target_repetitions=target_repetitions)
