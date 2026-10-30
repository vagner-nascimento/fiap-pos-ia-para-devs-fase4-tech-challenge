import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from config.media_paths import MediaStorage
from services.pose.video_processor import VideoPoseProcessor


@pytest.fixture
def temp_storage(tmp_path):
    media = tmp_path / "data"
    dataset = tmp_path / "datasets"
    media.mkdir()
    dataset.mkdir()
    return MediaStorage(media, dataset)


@pytest.fixture
def sample_video(tmp_path):
    """Cria um vídeo MP4 curto e sintético de 1 segundo a 30fps."""
    video_path = tmp_path / "dummy.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (320, 240))
    for i in range(30):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        # desenha um ponto branco no centro
        cv2.circle(frame, (160, 120), 10, (255, 255, 255), -1)
        out.write(frame)
    out.release()
    return video_path


def test_video_processor_e2e_synthesizes_files(temp_storage, sample_video):
    processor = VideoPoseProcessor(media_storage=temp_storage)
    run_id = "test_run_123"

    result = processor.process_video(
        video_path=sample_video,
        exercise_identifier="FISIO-001",
        run_id=run_id,
        side="auto",
        target_repetitions=5,
        generate_annotated_video=True,
    )

    assert result.session_summary.case_id == "FISIO-001"

    # Confere a geração dos arquivos em disco
    analysis_file = temp_storage.analysis_json(run_id)
    telemetry_file = temp_storage.telemetry_json(run_id)
    video_file = temp_storage.annotated_video(run_id)

    assert analysis_file.is_file()
    assert telemetry_file.is_file()
    assert video_file.is_file()

    with open(analysis_file, "r") as f:
        data = json.load(f)
        assert data["session_summary"]["case_id"] == "FISIO-001"
