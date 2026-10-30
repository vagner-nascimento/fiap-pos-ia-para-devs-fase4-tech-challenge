"""Resolução centralizada dos caminhos de mídia (entradas e saídas).

Layout sob ``MEDIA_ROOT``::

    inputs/sessions/{session_id}/original.mp4
    outputs/{run_id}/pose/annotated.mp4
    outputs/{run_id}/pose/analysis.json
    outputs/{run_id}/pose/telemetry.json
    outputs/{run_id}/pose/evidence/*.jpg

Os clipes do dataset de referência ficam fora de ``MEDIA_ROOT`` (``DATASET_ROOT``,
somente leitura). Os valores persistidos devem ser sempre relativos a ``MEDIA_ROOT``
(ver :meth:`MediaStorage.relative`).
"""

import os
import re
from pathlib import Path
from typing import Optional


_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# Determina a raiz do repositório no host ou /app no container Docker
_FILE_PATH = Path(__file__).resolve()
_REPO_ROOT = _FILE_PATH.parents[3] if len(_FILE_PATH.parents) > 3 else Path("/app")
DEFAULT_MEDIA_ROOT = _REPO_ROOT / "data"


class MediaStorage:
    """Resolve todos os caminhos de mídia, impedindo saída de ``MEDIA_ROOT``."""

    def __init__(self, media_root: Path, dataset_root: Optional[Path] = None):
        self.media_root = Path(media_root).resolve()
        self.dataset_root = Path(dataset_root).resolve() if dataset_root else None

    @classmethod
    def from_env(cls) -> "MediaStorage":
        """Cria a instância a partir de ``MEDIA_ROOT`` e ``DATASET_ROOT``."""
        env_media = os.getenv("MEDIA_ROOT")
        media_root = Path(env_media) if env_media else DEFAULT_MEDIA_ROOT
        dataset_root = os.getenv("DATASET_ROOT")
        return cls(media_root, Path(dataset_root) if dataset_root else None)

    # ---- entradas -------------------------------------------------------

    def session_input(self, session_id: str) -> Path:
        """Vídeo original enviado em uma sessão."""
        return self._within(
            self.media_root, "inputs", "sessions", self._safe(session_id), "original.mp4"
        )

    def session_input_dir(self, session_id: str) -> Path:
        """Diretório da sessão de entrada (criado se não existir)."""
        path = self._within(self.media_root, "inputs", "sessions", self._safe(session_id))
        path.mkdir(parents=True, exist_ok=True)
        return path

    def dataset_clip(self, case_id: str, filename: str) -> Path:
        """Clipe de referência do dataset (somente leitura)."""
        if self.dataset_root is None:
            raise RuntimeError("DATASET_ROOT não configurado.")
        return self._within(self.dataset_root, self._safe(case_id), self._safe(filename))

    # ---- saídas ---------------------------------------------------------

    def pose_output_dir(self, run_id: str) -> Path:
        """Diretório de saída da análise de pose (criado se não existir)."""
        path = self._within(self.media_root, "outputs", self._safe(run_id), "pose")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def annotated_video(self, run_id: str) -> Path:
        return self.pose_output_dir(run_id) / "annotated.mp4"

    def analysis_json(self, run_id: str) -> Path:
        return self.pose_output_dir(run_id) / "analysis.json"

    def telemetry_json(self, run_id: str) -> Path:
        return self.pose_output_dir(run_id) / "telemetry.json"

    def evidence_dir(self, run_id: str) -> Path:
        path = self.pose_output_dir(run_id) / "evidence"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def evidence_frame(self, run_id: str, name: str) -> Path:
        """Frame de evidência de um desvio (``name`` sem extensão)."""
        return self.evidence_dir(run_id) / f"{self._safe(name)}.jpg"

    # ---- persistência ---------------------------------------------------

    def relative(self, path: Path) -> str:
        """Caminho relativo a ``MEDIA_ROOT`` (valor a ser guardado em resultados/banco)."""
        resolved = Path(path).resolve()
        try:
            return resolved.relative_to(self.media_root).as_posix()
        except ValueError as error:
            raise ValueError(f"Caminho fora de MEDIA_ROOT: {path}") from error

    def absolute(self, relative_path: str) -> Path:
        """Converte um caminho relativo guardado em caminho absoluto."""
        return self._within(self.media_root, *Path(relative_path).parts)

    # ---- internos -------------------------------------------------------

    @staticmethod
    def _safe(name: str) -> str:
        if not isinstance(name, str) or not _SAFE_NAME.match(name):
            raise ValueError(f"Nome inválido para caminho de mídia: {name!r}")
        return name

    @staticmethod
    def _within(root: Path, *parts: str) -> Path:
        path = root.joinpath(*parts).resolve()
        if path != root and root not in path.parents:
            raise ValueError("Caminho fora do diretório raiz permitido.")
        return path
