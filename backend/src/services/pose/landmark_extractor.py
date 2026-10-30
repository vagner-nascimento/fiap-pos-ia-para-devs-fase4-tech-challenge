"""Extração de landmarks do MediaPipe Pose a partir de um arquivo de vídeo."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import cv2
import mediapipe as mp
import numpy as np

from services.pose.models import PoseFrame

logger = logging.getLogger(__name__)


@dataclass
class ExtractedVideo:
    frames: list[PoseFrame]
    fps: float  # fps original do vídeo
    width: int
    height: int
    total_frames: int  # frames lidos do vídeo (antes da amostragem)
    stride: int = 1

    @property
    def effective_fps(self) -> float:
        """fps após a amostragem; é o que deve ser passado aos analisadores."""
        return self.fps / self.stride


def extract_pose_frames(
    video_path: Path,
    model_complexity: int = 1,
    max_fps: float = 30.0,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> ExtractedVideo:
    """Roda o MediaPipe Pose nos frames do vídeo, amostrando para no máximo ~``max_fps``.

    Os landmarks saem em **pixels** (``x*largura``, ``y*altura``), com ``visibility`` na 4ª coluna.
    Frames sem pessoa detectada têm ``landmarks=None``. ``PoseFrame.index`` e ``time`` referem-se
    ao vídeo original, então continuam válidos para localizar o frame real.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Vídeo não encontrado: {video_path}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Não foi possível abrir o vídeo: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    stride = max(1, round(fps / max_fps))
    frames: list[PoseFrame] = []
    pose = mp.solutions.pose.Pose(
        static_image_mode=False,
        model_complexity=model_complexity,
        smooth_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    try:
        index = 0
        while True:
            if index % stride != 0:
                if not cap.grab():
                    break
                index += 1
                continue
            ok, bgr = cap.read()
            if not ok:
                break
            result = pose.process(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
            landmarks = None
            if result.pose_landmarks:
                landmarks = np.array(
                    [
                        [lm.x * width, lm.y * height, lm.z * width, lm.visibility]
                        for lm in result.pose_landmarks.landmark
                    ],
                    dtype=float,
                )
            frames.append(PoseFrame(index=index, time=index / fps, landmarks=landmarks))
            index += 1
            if on_progress and len(frames) % 30 == 0:
                on_progress(index, total)
    finally:
        pose.close()
        cap.release()

    logger.info(
        "Extraídos %d frames de %s (%.1f fps, passo %d)", len(frames), video_path.name, fps, stride
    )
    return ExtractedVideo(frames, fps, width, height, index, stride)
