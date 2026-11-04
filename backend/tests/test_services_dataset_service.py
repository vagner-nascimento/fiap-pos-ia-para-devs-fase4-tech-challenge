from pathlib import Path

import pytest

from services.dataset_service import DatasetError, DatasetService


def _create_clip(root: Path, case_id: str = "FISIO-001") -> Path:
    case_dir = root / case_id
    case_dir.mkdir(parents=True)
    clip = case_dir / f"{case_id}-teste.mp4"
    clip.write_bytes(b"video")
    return clip


def test_dataset_service_lists_only_supported_mp4_files(tmp_path):
    clip = _create_clip(tmp_path)
    (tmp_path / "FISIO-003").mkdir()
    (tmp_path / "FISIO-003" / "ignored.mp4").write_bytes(b"video")
    (tmp_path / "FISIO-001" / "ignored.txt").write_text("not a video")

    service = DatasetService(tmp_path)

    listed = service.list_clips()

    assert [item.filename for item in listed] == [clip.name]
    assert service.resolve_clip("FISIO-001", clip.name) == clip.resolve()


def test_dataset_service_rejects_unlisted_or_traversal_clip(tmp_path):
    _create_clip(tmp_path)
    service = DatasetService(tmp_path)

    for filename in ("missing.mp4", "../FISIO-001/FISIO-001-teste.mp4", "file.txt"):
        with pytest.raises(DatasetError, match="Clipe"):
            service.resolve_clip("FISIO-001", filename)
