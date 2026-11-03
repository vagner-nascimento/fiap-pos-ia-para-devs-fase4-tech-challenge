"""Detecção dos objetos obrigatórios dos exercícios com o modelo YOLO treinado."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

MODEL_PATH = Path(__file__).resolve().parents[2] / "yolo" / "best.pt"
DEFAULT_CONFIDENCE = 0.25
FULL_DETECTION_CONFIDENCE = 0.5


@dataclass(frozen=True)
class ObjectDetectionConfig:
    class_id: int
    class_name: str
    display_name: str
    fully_detected_label: str
    partially_detected_label: str
    not_detected_label: str


@dataclass(frozen=True)
class ObjectDetection:
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float


OBJECT_DETECTION_CONFIGS: dict[str, ObjectDetectionConfig] = {
    "FISIO-006": ObjectDetectionConfig(
        0,
        "faixa_elastica",
        "faixa elástica",
        "faixa elástica totalmente detectada",
        "faixa elástica parcialmente detectada",
        "faixa elástica não detectada",
    ),
    "FISIO-007": ObjectDetectionConfig(
        1,
        "halter",
        "halter",
        "halter totalmente detectado",
        "halter parcialmente detectado",
        "halter não detectado",
    ),
}


def detection_config(case_id: str) -> Optional[ObjectDetectionConfig]:
    """Retorna a configuração do objeto exigido pelo exercício, quando houver."""
    return OBJECT_DETECTION_CONFIGS.get(case_id.strip().upper())


class ObjectDetector:
    """Executa inferência YOLO e filtra a classe esperada pelo exercício."""

    def __init__(
        self,
        config: ObjectDetectionConfig,
        model_path: Path = MODEL_PATH,
        confidence: float = DEFAULT_CONFIDENCE,
        model: Any = None,
    ):
        if not 0 < confidence <= 1:
            raise ValueError("O limiar de confiança deve estar entre 0 e 1.")
        if model is None and not model_path.is_file():
            raise FileNotFoundError(f"Modelo YOLO não encontrado: {model_path}")

        self.config = config
        self.confidence = confidence
        if model is not None:
            self.model = model
        else:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise RuntimeError(
                    "A dependência 'ultralytics' é necessária para detectar objetos."
                ) from exc
            self.model = YOLO(str(model_path))

    def detect(self, frame: np.ndarray) -> list[ObjectDetection]:
        """Detecta somente o objeto esperado no frame."""
        result = self.model.predict(
            frame,
            conf=self.confidence,
            device="cpu",
            verbose=False,
        )[0]
        detections: list[ObjectDetection] = []
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            if class_id != self.config.class_id:
                continue
            x1, y1, x2, y2 = (int(value) for value in box.xyxy[0].tolist())
            detections.append(
                ObjectDetection(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    confidence=float(box.conf[0].item()),
                )
            )
        return detections


def detection_summary(
    config: ObjectDetectionConfig,
    total_frames: int,
    detected_frames: int,
    confidence: float,
    not_detected_frames: int = 0,
    partially_detected_frames: int = 0,
    fully_detected_frames: int = 0,
) -> dict[str, object]:
    """Cria o resumo serializável da detecção para os artefatos da sessão."""
    percentage = detected_frames / total_frames * 100 if total_frames else 0.0
    if total_frames and not_detected_frames + partially_detected_frames + fully_detected_frames == 0:
        not_detected_frames = total_frames - detected_frames
        fully_detected_frames = detected_frames
    percentage_of = lambda count: round(count / total_frames * 100, 1) if total_frames else 0.0
    return {
        "object_name": config.display_name,
        "class_name": config.class_name,
        "detected": detected_frames > 0,
        "detection_percentage": round(percentage, 1),
        "total_frames": total_frames,
        "frames_detected": detected_frames,
        "not_detected_percentage": percentage_of(not_detected_frames),
        "partially_detected_percentage": percentage_of(partially_detected_frames),
        "fully_detected_percentage": percentage_of(fully_detected_frames),
        "confidence_threshold": confidence,
    }


def frame_detection_status(
    config: ObjectDetectionConfig,
    detections: list[ObjectDetection],
) -> tuple[str, tuple[int, int, int]]:
    """Retorna o texto e a cor correspondentes somente ao frame atual."""
    if not detections:
        return config.not_detected_label, (220, 30, 30)

    max_confidence = max(detection.confidence for detection in detections)
    if max_confidence >= FULL_DETECTION_CONFIDENCE:
        return config.fully_detected_label, (0, 210, 0)
    return config.partially_detected_label, (220, 150, 0)


def frame_detection_category(detections: list[ObjectDetection]) -> str:
    """Classifica o frame para o resumo percentual do equipamento."""
    if not detections:
        return "not_detected"
    return "fully_detected" if max(
        detection.confidence for detection in detections
    ) >= FULL_DETECTION_CONFIDENCE else "partially_detected"
