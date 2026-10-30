"""Estruturas de dados da análise de pose: frame de entrada e resultado de saída."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, Field

MIN_VISIBILITY = 0.5


@dataclass
class PoseFrame:
    """Landmarks de um frame.

    ``landmarks`` tem shape ``(33, 4)`` com colunas ``x, y`` (pixels), ``z`` e ``visibility``.
    ``None`` indica frame sem pessoa detectada ("sem dado", nunca "correto").
    """

    index: int
    time: float
    landmarks: Optional[np.ndarray] = None

    @property
    def has_pose(self) -> bool:
        return self.landmarks is not None

    def visibility(self, landmark: int) -> float:
        if self.landmarks is None:
            return 0.0
        return float(self.landmarks[int(landmark), 3])

    def point(self, landmark: int, min_visibility: float = MIN_VISIBILITY) -> np.ndarray:
        """Ponto ``(x, y)`` do landmark, ou ``(nan, nan)`` se ausente/pouco visível."""
        if self.landmarks is None or self.visibility(landmark) < min_visibility:
            return np.array([np.nan, np.nan])
        return self.landmarks[int(landmark), :2].astype(float)


class DeviationSeverity(str, Enum):
    LEVE = "leve"
    MODERADA = "moderada"
    GRAVE = "grave"


class RepetitionEvent(BaseModel):
    index: int
    start_time: float
    peak_time: float
    end_time: float
    duration: float
    peak_angle: Optional[float] = None
    peak_progress: float
    completed: bool = True
    is_valid: bool = True
    deviations: list[str] = Field(default_factory=list)


class DeviationEvent(BaseModel):
    deviation_type: str
    severity: DeviationSeverity
    repetition_index: Optional[int] = None
    start_time: float
    end_time: float
    start_frame: int
    end_frame: int
    evidence_frame: Optional[int] = None
    description: str
    evidence_frame_path: Optional[str] = None


class TelemetryPoint(BaseModel):
    timestamp: float
    progress: Optional[float] = None
    phase: str = "repouso"
    metrics: dict[str, Optional[float]] = Field(default_factory=dict)


class SessionSummary(BaseModel):
    exercise_id: str
    case_id: str
    side_evaluated: str
    target_repetitions: Optional[int] = None
    completed_repetitions: int
    valid_repetitions: int
    invalid_repetitions: int
    duration_seconds: float
    fps: float
    total_frames: int
    frames_without_pose: int
    compliance_score: float
    status: str = "concluido"
    limitations: list[str] = Field(default_factory=list)


class ExerciseAnalysisResult(BaseModel):
    session_summary: SessionSummary
    repetitions: list[RepetitionEvent]
    deviations: list[DeviationEvent]
    telemetry: list[TelemetryPoint]
    annotated_video_path: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)
