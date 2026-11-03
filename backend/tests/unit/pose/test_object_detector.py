import numpy as np

from services.pose.object_detector import (
    ObjectDetector,
    ObjectDetectionConfig,
    ObjectDetection,
    detection_config,
    frame_detection_status,
    detection_summary,
)


class _Value:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value

    def tolist(self):
        return self.value


class _Box:
    def __init__(self, class_id, confidence, coordinates):
        self.cls = [_Value(class_id)]
        self.conf = [_Value(confidence)]
        self.xyxy = [_Value(coordinates)]


class _Result:
    def __init__(self, boxes):
        self.boxes = boxes


class _Model:
    def __init__(self, result):
        self.result = result

    def predict(self, frame, conf, device, verbose):
        return [self.result]


def test_detection_config_only_exists_for_object_exercises():
    assert detection_config("FISIO-006").display_name == "faixa elástica"
    assert detection_config("FISIO-007").display_name == "halter"
    assert detection_config("FISIO-001") is None


def test_detector_filters_to_expected_class():
    config = ObjectDetectionConfig(
        1,
        "halter",
        "halter",
        "halter totalmente detectado",
        "halter parcialmente detectado",
        "halter não detectado",
    )
    model = _Model(
        _Result(
            [
                _Box(0, 0.91, [1, 2, 30, 40]),
                _Box(1, 0.88, [10, 20, 50, 60]),
            ]
        )
    )
    detector = ObjectDetector(config=config, model=model)

    detections = detector.detect(np.zeros((80, 80, 3), dtype=np.uint8))

    assert len(detections) == 1
    assert detections[0].confidence == 0.88
    assert (detections[0].x1, detections[0].y1) == (10, 20)


def test_detection_summary_reports_not_detected():
    config = ObjectDetectionConfig(
        0,
        "faixa_elastica",
        "faixa elástica",
        "faixa elástica totalmente detectada",
        "faixa elástica parcialmente detectada",
        "faixa elástica não detectada",
    )

    summary = detection_summary(config, total_frames=30, detected_frames=0, confidence=0.25)

    assert summary["detected"] is False
    assert summary["detection_percentage"] == 0.0
    assert summary["object_name"] == "faixa elástica"


def test_detection_summary_calculates_frame_percentage():
    config = ObjectDetectionConfig(
        0,
        "faixa_elastica",
        "faixa elástica",
        "faixa elástica totalmente detectada",
        "faixa elástica parcialmente detectada",
        "faixa elástica não detectada",
    )

    summary = detection_summary(config, total_frames=30, detected_frames=15, confidence=0.25)

    assert summary["detected"] is True
    assert summary["detection_percentage"] == 50.0


def test_frame_detection_status_is_not_detected_without_current_frame_detection():
    config = detection_config("FISIO-006")

    text, color = frame_detection_status(config, [])

    assert text == "faixa elástica não detectada"
    assert color == (220, 30, 30)


def test_frame_detection_status_uses_current_detection_confidence():
    config = detection_config("FISIO-006")

    text, color = frame_detection_status(
        config,
        [ObjectDetection(1, 2, 30, 40, 0.8)],
    )

    assert text == "faixa elástica totalmente detectada"
    assert color == (0, 210, 0)

    text, color = frame_detection_status(
        config,
        [ObjectDetection(1, 2, 30, 40, 0.3)],
    )

    assert text == "faixa elástica parcialmente detectada"
    assert color == (220, 150, 0)
