import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from config.media_paths import MediaStorage
import services.pose.video_processor as video_processor_module
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


def test_video_processor_with_mongo_sink(temp_storage, sample_video):
    import mongomock
    from infra.database.repositories.event_repository import EventRepository
    from infra.database.repositories.session_repository import SessionRepository
    from services.pose.sinks import CompositeResultSink, FileResultSink, MongoResultSink

    mock_client = mongomock.MongoClient()
    db = mock_client["test_db"]
    session_repo = SessionRepository(collection=db["sessoes"])
    event_repo = EventRepository(collection=db["eventos"])

    composite_sink = CompositeResultSink([
        FileResultSink(media_storage=temp_storage),
        MongoResultSink(
            session_repository=session_repo,
            event_repository=event_repo,
            media_storage=temp_storage,
        ),
    ])

    processor = VideoPoseProcessor(media_storage=temp_storage, result_sink=composite_sink)
    run_id = "test_run_mongo_e2e"

    result = processor.process_video(
        video_path=sample_video,
        exercise_identifier="FISIO-001",
        run_id=run_id,
        side="auto",
        target_repetitions=5,
        generate_annotated_video=False,
        patient_id="PAC-TEST-01",
    )

    assert result.session_summary.case_id == "FISIO-001"

    # Confere arquivos gerados em disco
    assert temp_storage.analysis_json(run_id).is_file()
    assert temp_storage.telemetry_json(run_id).is_file()

    # Confere documentos salvos no MongoDB
    session_doc = session_repo.get_session(run_id)
    assert session_doc is not None
    assert session_doc.session_id == run_id
    assert session_doc.paciente_id == "PAC-TEST-01"
    assert session_doc.case_id == "FISIO-001"
    assert session_doc.exercicio_id == "KNEE_EXTENSION_SEATED"
    assert session_doc.status.value == "concluido"


def test_transcode_muxes_audio_from_original_video(tmp_path, monkeypatch):
    annotated_video = tmp_path / "annotated.mp4"
    original_video = tmp_path / "original.mp4"
    temp_h264 = tmp_path / "annotated.h264.mp4"
    annotated_video.write_bytes(b"video")
    original_video.write_bytes(b"video-with-audio")
    commands = []

    monkeypatch.setattr(video_processor_module.shutil, "which", lambda _: "ffmpeg")

    def fake_run(command, **kwargs):
        commands.append(command)
        temp_h264.write_bytes(b"video-with-audio")
        return type("Completed", (), {"returncode": 0, "stderr": b""})()

    monkeypatch.setattr(video_processor_module.subprocess, "run", fake_run)

    VideoPoseProcessor()._transcode_to_h264_if_available(
        annotated_video,
        audio_source_path=original_video,
    )

    command = commands[0]
    assert ["-map", "0:v:0", "-map", "1:a:0"] == command[
        command.index("-map"):command.index("-c:a")
    ]
    assert "-an" not in command
    assert "-c:a" in command
    assert annotated_video.read_bytes() == b"video-with-audio"
