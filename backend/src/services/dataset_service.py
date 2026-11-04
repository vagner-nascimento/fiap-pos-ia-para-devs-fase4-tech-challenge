"""Gerenciamento local do dataset oficial de vídeos de fisioterapia."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from threading import Lock
from typing import Optional

from config.media_paths import MediaStorage
from models.rest.session import ReferenceClipInfo


DATASET_REPOSITORY_URL = "https://github.com/vagner-nascimento/fiap-pos-ia-para-devs-fase4-tech-challenge-datasets.git"
DATASET_REF = os.getenv("DATASET_REF", "main")
SUPPORTED_CASES = {"FISIO-001", "FISIO-002", "FISIO-006", "FISIO-007"}
CASE_TO_EXERCISE = {
    "FISIO-001": ("KNEE_EXTENSION_SEATED", "Extensão de joelho sentado"),
    "FISIO-002": ("SHOULDER_PENDULUM", "Pêndulo de ombro de Codman"),
    "FISIO-006": ("SHOULDER_ABDUCTION_BAND", "Abdução de ombro com faixa elástica"),
    "FISIO-007": ("ELBOW_FLEXION_LIGHT_DUMBBELL", "Flexão de cotovelo com halter leve"),
}
_download_lock = Lock()
_download_state = {"status": "not_downloaded", "message": None}


class DatasetError(RuntimeError):
    """Falha operacional ao preparar ou ler o dataset."""


class DatasetService:
    def __init__(self, root: Optional[Path] = None):
        storage = MediaStorage.from_env()
        configured_root = os.getenv("DATASET_ROOT")
        self.root = Path(root or configured_root or storage.media_root / "datasets" / "fisio").resolve()

    def status(self) -> dict:
        clips = self.list_clips()
        if clips:
            _download_state.update(status="ready", message=None)
        elif self.root.exists() and (self.root / ".git").exists():
            _download_state.update(status="error", message="Dataset clonado, mas sem vídeos MP4 válidos.")
        elif _download_state["status"] != "downloading":
            _download_state.update(status="not_downloaded", message=None)
        return {
            "status": _download_state["status"],
            "message": _download_state["message"],
            "case_count": len({clip.case_id for clip in clips}),
            "clip_count": len(clips),
        }

    def list_clips(self) -> list[ReferenceClipInfo]:
        clips: list[ReferenceClipInfo] = []
        if not self.root.is_dir():
            return clips
        for case_dir in sorted(self.root.iterdir()):
            if not case_dir.is_dir() or case_dir.name not in SUPPORTED_CASES:
                continue
            exercise_id, exercise_name = CASE_TO_EXERCISE[case_dir.name]
            for path in sorted(case_dir.glob("*.mp4")):
                kind = "correto" if "correto" in path.name.lower() else "desvio"
                description = (
                    "Execução padrão correta"
                    if kind == "correto"
                    else f"Variação motora com desvio ({path.name})"
                )
                clips.append(
                    ReferenceClipInfo(
                        case_id=case_dir.name,
                        exercicio_id=exercise_id,
                        exercicio_nome=exercise_name,
                        filename=path.name,
                        tipo=kind,
                        descricao=description,
                    )
                )
        return clips

    def resolve_clip(self, case_id: str, filename: str) -> Path:
        if case_id not in SUPPORTED_CASES or Path(filename).name != filename or not filename.endswith(".mp4"):
            raise DatasetError("Clipe de dataset inválido.")
        candidate = (self.root / case_id / filename).resolve()
        if candidate.parent != (self.root / case_id).resolve() or not candidate.is_file():
            raise DatasetError(f"Clipe '{filename}' não encontrado no dataset.")
        if not any(clip.filename == filename and clip.case_id == case_id for clip in self.list_clips()):
            raise DatasetError(f"Clipe '{filename}' não está catalogado.")
        return candidate

    def download(self) -> dict:
        if self.list_clips():
            return self.status()
        if not _download_lock.acquire(blocking=False):
            return self.status()
        try:
            if self.list_clips():
                return self.status()
            _download_state.update(status="downloading", message=None)
            self.root.parent.mkdir(parents=True, exist_ok=True)
            temporary_root = self.root.with_name(f"{self.root.name}.download")
            if temporary_root.exists():
                shutil.rmtree(temporary_root)
            command = [
                "git", "clone", "--depth", "1", "--branch", DATASET_REF,
                DATASET_REPOSITORY_URL, str(temporary_root),
            ]
            try:
                completed = subprocess.run(
                    command, check=False, capture_output=True, text=True, timeout=600
                )
            except (OSError, subprocess.SubprocessError) as error:
                raise DatasetError(f"Não foi possível executar o download do dataset: {error}") from error
            if completed.returncode != 0:
                detail = completed.stderr.strip() or "git clone retornou erro."
                raise DatasetError(detail)
            if not any(
                list((temporary_root / case).glob("*.mp4"))
                for case in SUPPORTED_CASES
                if (temporary_root / case).is_dir()
            ):
                raise DatasetError("O repositório não contém a estrutura esperada.")
            if self.root.exists():
                shutil.rmtree(self.root)
            temporary_root.replace(self.root)
            if not self.list_clips():
                raise DatasetError("O dataset baixado não contém vídeos MP4 válidos.")
            return self.status()
        except DatasetError as error:
            _download_state.update(status="error", message=str(error))
            if self.root.with_name(f"{self.root.name}.download").exists():
                shutil.rmtree(self.root.with_name(f"{self.root.name}.download"))
            return self.status()
        finally:
            _download_lock.release()

    def request_download(self) -> dict:
        """Marca um download solicitado sem bloquear a resposta HTTP."""
        current = self.status()
        if current["status"] == "ready":
            return current
        _download_state.update(status="downloading", message=None)
        return self.status()
