import pytest

from config.media_paths import MediaStorage


@pytest.fixture
def storage(tmp_path):
    media = tmp_path / "data"
    dataset = tmp_path / "datasets"
    media.mkdir()
    dataset.mkdir()
    return MediaStorage(media, dataset)


def test_session_input_path(storage):
    path = storage.session_input("sess-1")
    assert path == storage.media_root / "inputs" / "sessions" / "sess-1" / "original.mp4"


def test_pose_outputs_created_under_run(storage):
    video = storage.annotated_video("run-1")
    assert video == storage.media_root / "outputs" / "run-1" / "pose" / "annotated.mp4"
    assert video.parent.is_dir()
    assert storage.analysis_json("run-1").name == "analysis.json"
    assert storage.telemetry_json("run-1").name == "telemetry.json"


def test_evidence_frame(storage):
    frame = storage.evidence_frame("run-1", "rep02_amplitude_reduzida")
    assert frame.name == "rep02_amplitude_reduzida.jpg"
    assert frame.parent.name == "evidence"


def test_dataset_clip(storage):
    clip = storage.dataset_clip("FISIO-001", "FISIO-001-correto.mp4")
    assert clip == storage.dataset_root / "FISIO-001" / "FISIO-001-correto.mp4"


def test_dataset_clip_requires_root(tmp_path):
    with pytest.raises(RuntimeError):
        MediaStorage(tmp_path).dataset_clip("FISIO-001", "a.mp4")


@pytest.mark.parametrize("bad", ["../x", "a/b", "", ".hidden", "..", "a\\b"])
def test_rejects_unsafe_names(storage, bad):
    with pytest.raises(ValueError):
        storage.session_input(bad)
    with pytest.raises(ValueError):
        storage.pose_output_dir(bad)


def test_relative_and_absolute_roundtrip(storage):
    path = storage.evidence_frame("run-1", "ev")
    rel = storage.relative(path)
    assert rel == "outputs/run-1/pose/evidence/ev.jpg"
    assert storage.absolute(rel) == path


def test_relative_rejects_outside_path(storage, tmp_path):
    with pytest.raises(ValueError):
        storage.relative(tmp_path / "other" / "file.jpg")


def test_absolute_rejects_traversal(storage):
    with pytest.raises(ValueError):
        storage.absolute("../../etc/passwd")


def test_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "m"))
    monkeypatch.setenv("DATASET_ROOT", str(tmp_path / "d"))
    storage = MediaStorage.from_env()
    assert storage.media_root == (tmp_path / "m").resolve()
    assert storage.dataset_root == (tmp_path / "d").resolve()
