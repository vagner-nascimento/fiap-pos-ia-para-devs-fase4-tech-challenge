"""Detect the expected object in each training video using the trained YOLO model."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = ROOT / "runs" / "yolo_training" / "two_objects" / "weights" / "best.pt"
DEFAULT_VIDEOS_DIR = ROOT / "videos"
DEFAULT_OUTPUT_DIR = ROOT / "videos" / "detection_out"
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
ELASTIC_BAND_CLASS_ID = 0
HALTER_CLASS_ID = 1


def detection_config(video_path: Path) -> tuple[int, str, str, str]:
    """Return the class and status labels expected for a video group."""
    if video_path.stem.startswith("FISIO-006"):
        return (
            ELASTIC_BAND_CLASS_ID,
            "faixa elástica",
            "faixa elástica presente",
            "faixa elástica ausente",
        )
    if video_path.stem.startswith("FISIO-007"):
        return HALTER_CLASS_ID, "halter", "halter presente", "halter ausente"
    raise ValueError(
        f"Unsupported video group: {video_path.name}. "
        "Expected a FISIO-006 or FISIO-007 video."
    )


def load_font(
    size: int,
) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    """Load a font that supports accented Portuguese characters."""
    candidates = (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for font_path in candidates:
        if font_path.is_file():
            return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def draw_status(
    frame,
    present: bool,
    font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont],
    present_text: str,
    absent_text: str,
):
    """Draw the detection status on the upper-left corner of a BGR frame."""
    text = present_text if present else absent_text
    color = (0, 170, 0) if present else (0, 0, 220)

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(frame_rgb)
    draw = ImageDraw.Draw(image)
    left, top = 20, 20
    text_box = draw.textbbox((left, top), text, font=font)
    draw.rectangle(
        (text_box[0] - 10, text_box[1] - 8, text_box[2] + 10, text_box[3] + 8),
        fill=(255, 255, 255),
    )
    draw.text((left, top), text, font=font, fill=(color[2], color[1], color[0]))
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def detect_video(
    model_path: Path,
    video_path: Path,
    output_dir: Path,
    confidence: float,
    model: Optional[YOLO] = None,
) -> Path:
    """Detect elastic bands and write an annotated copy of the input video."""
    if not model_path.is_file():
        raise FileNotFoundError(f"Trained model not found: {model_path}")
    if not video_path.is_file():
        raise FileNotFoundError(f"Input video not found: {video_path}")

    class_id_to_detect, object_name, present_text, absent_text = detection_config(
        video_path
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{video_path.stem}_detection.mp4"
    detector = model if model is not None else YOLO(str(model_path))
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open input video: {video_path}")

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"Could not create output video: {output_path}")

    font = load_font(max(20, round(height / 30)))
    try:
        while True:
            success, frame = capture.read()
            if not success:
                break

            result = detector.predict(frame, conf=confidence, verbose=False)[0]
            object_present = False
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                if class_id != class_id_to_detect:
                    continue
                object_present = True
                x1, y1, x2, y2 = (int(value) for value in box.xyxy[0].tolist())
                score = float(box.conf[0].item())
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
                cv2.putText(
                    frame,
                    f"{object_name} {score:.2f}",
                    (x1, max(y1 - 8, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 200, 0),
                    2,
                    cv2.LINE_AA,
                )

            frame = draw_status(
                frame,
                object_present,
                font,
                present_text,
                absent_text,
            )
            writer.write(frame)
    finally:
        capture.release()
        writer.release()

    return output_path


def detect_videos(
    model_path: Path,
    videos_dir: Path,
    output_dir: Path,
    confidence: float,
) -> list[Path]:
    """Detect the expected object in every supported video in a directory."""
    if not model_path.is_file():
        raise FileNotFoundError(f"Trained model not found: {model_path}")
    if not videos_dir.is_dir():
        raise FileNotFoundError(f"Videos directory not found: {videos_dir}")

    video_paths = sorted(
        path
        for path in videos_dir.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
    )
    if not video_paths:
        raise FileNotFoundError(f"No supported videos found in {videos_dir}")

    detector = YOLO(str(model_path))
    output_paths = []
    for video_path in video_paths:
        output_paths.append(
            detect_video(
                model_path=model_path,
                video_path=video_path,
                output_dir=output_dir,
                confidence=confidence,
                model=detector,
            )
        )
    return output_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--videos-dir", type=Path, default=DEFAULT_VIDEOS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--confidence", type=float, default=0.25)
    args = parser.parse_args()
    if not 0 < args.confidence <= 1:
        parser.error("--confidence must be greater than 0 and at most 1")
    return args


if __name__ == "__main__":
    arguments = parse_args()
    outputs = detect_videos(
        model_path=arguments.model,
        videos_dir=arguments.videos_dir,
        output_dir=arguments.output_dir,
        confidence=arguments.confidence,
    )
    for output in outputs:
        print(f"Annotated video saved to: {output}")