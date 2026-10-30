"""Processamento completo de vídeo com MediaPipe, renderização de HUD/esqueleto e extração de evidências."""

import json
import logging
from pathlib import Path
from typing import Callable, Optional

import cv2
import mediapipe as mp
import numpy as np

from config.media_paths import MediaStorage
from services.pose.base_analyzer import BaseExerciseAnalyzer
from services.pose.joint_mapper import BodySide, JointMapper
from services.pose.landmark_extractor import extract_pose_frames
from services.pose.models import DeviationSeverity, ExerciseAnalysisResult, PoseFrame
from services.pose.registry import get_analyzer

from services.pose.hud_renderer import HudRenderer

logger = logging.getLogger(__name__)

# Conexões principais para desenhar o esqueleto do corpo
POSE_CONNECTIONS = mp.solutions.pose.POSE_CONNECTIONS

# Cores BGR para o esqueleto
COLOR_GREEN = (40, 200, 80)
COLOR_YELLOW = (0, 215, 255)
COLOR_RED = (50, 50, 235)


class VideoPoseProcessor:
    """Orquestra a análise de vídeo: extração, detecção de desvios, renderização anotada e salvamento."""

    def __init__(self, media_storage: Optional[MediaStorage] = None, hud_renderer: Optional[HudRenderer] = None):
        self.storage = media_storage or MediaStorage.from_env()
        self.hud_renderer = hud_renderer or HudRenderer()

    def process_video(
        self,
        video_path: Path,
        exercise_identifier: str,
        run_id: str,
        side: BodySide | str | None = BodySide.AUTO,
        target_repetitions: Optional[int] = None,
        generate_annotated_video: bool = True,
        on_progress: Optional[Callable[[str, float], None]] = None,
    ) -> ExerciseAnalysisResult:
        """Processa um vídeo de ponta a ponta e grava os artefatos de saída."""
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Vídeo de entrada não encontrado: {video_path}")

        if on_progress:
            on_progress("extraindo_landmarks", 0.0)

        # 1. Extração dos frames via MediaPipe
        extracted = extract_pose_frames(
            video_path,
            max_fps=30.0,
            on_progress=(
                (lambda cur, tot: on_progress("extraindo_landmarks", min(0.5, 0.5 * cur / max(1, tot))))
                if on_progress
                else None
            ),
        )

        if on_progress:
            on_progress("analisando_movimento", 0.55)

        # 2. Execução da análise biomecânica com o analisador correspondente
        analyzer = get_analyzer(
            exercise_identifier,
            side=side,
            target_repetitions=target_repetitions,
        )
        result = analyzer.analyze(extracted.frames, extracted.effective_fps)

        if on_progress:
            on_progress("gerando_artefatos", 0.70)

        # 3. Preparação das pastas de saída
        out_dir = self.storage.pose_output_dir(run_id)
        evidence_dir = self.storage.evidence_dir(run_id)

        # 4. Renderização do vídeo anotado e snapshots de evidência
        annotated_video_path = None
        if generate_annotated_video:
            annotated_video_path = self.storage.annotated_video(run_id)
            self._render_annotated_video_and_evidence(
                video_path=video_path,
                extracted_frames=extracted.frames,
                result=result,
                output_video_path=annotated_video_path,
                evidence_dir=evidence_dir,
                run_id=run_id,
                fps=extracted.effective_fps,
                width=extracted.width,
                height=extracted.height,
                on_progress=on_progress,
            )
            result.annotated_video_path = self.storage.relative(annotated_video_path)

        # 5. Salva analysis.json e telemetry.json
        analysis_json_path = self.storage.analysis_json(run_id)
        with open(analysis_json_path, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))

        telemetry_json_path = self.storage.telemetry_json(run_id)
        with open(telemetry_json_path, "w", encoding="utf-8") as f:
            json.dump([pt.model_dump() for pt in result.telemetry], f, indent=2)

        if on_progress:
            on_progress("concluido", 1.0)

        logger.info(
            "Processamento de vídeo concluído para run_id=%s. Repetições: %d/%d, Válidas: %d, Desvios: %d",
            run_id,
            result.session_summary.completed_repetitions,
            result.session_summary.target_repetitions or 0,
            result.session_summary.valid_repetitions,
            len(result.deviations),
        )
        return result

    def _render_annotated_video_and_evidence(
        self,
        video_path: Path,
        extracted_frames: list[PoseFrame],
        result: ExerciseAnalysisResult,
        output_video_path: Path,
        evidence_dir: Path,
        run_id: str,
        fps: float,
        width: int,
        height: int,
        on_progress: Optional[Callable[[str, float], None]] = None,
    ) -> None:
        """Lê os frames amostrados originais, desenha esqueleto e HUD e grava em output_video_path."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(output_video_path), fourcc, fps, (width, height))

        # Mapa de desvios ativos por frame original
        frame_deviations: dict[int, list] = {}
        evidence_frames_to_save: dict[int, list] = {}

        for dev in result.deviations:
            for f_idx in range(dev.start_frame, dev.end_frame + 1):
                frame_deviations.setdefault(f_idx, []).append(dev)
            target_ev = dev.evidence_frame if dev.evidence_frame is not None else dev.start_frame
            evidence_frames_to_save.setdefault(target_ev, []).append(dev)

        frame_idx_to_pose = {f.index: f for f in extracted_frames}
        total = len(extracted_frames)

        try:
            for seq_idx, pose_frame in enumerate(extracted_frames):
                cap.set(cv2.CAP_PROP_POS_FRAMES, pose_frame.index)
                ok, frame = cap.read()
                if not ok:
                    break

                devs_now = frame_deviations.get(pose_frame.index, [])
                has_dev = len(devs_now) > 0
                max_sev = (
                    max([d.severity for d in devs_now], key=lambda s: 2 if s == DeviationSeverity.GRAVE else 1)
                    if has_dev
                    else None
                )

                # Cor dos landmarks conforme severidade
                skel_color = (
                    COLOR_GREEN
                    if not has_dev
                    else COLOR_RED
                    if max_sev == DeviationSeverity.GRAVE
                    else COLOR_YELLOW
                )

                # Desenha esqueleto
                if pose_frame.has_pose:
                    self._draw_skeleton(frame, pose_frame, skel_color)

                # Desenha painel HUD
                self._draw_hud(frame, pose_frame, result, devs_now, width, height)

                writer.write(frame)

                # Se for frame de evidência, salva snapshot
                if pose_frame.index in evidence_frames_to_save:
                    for dev in evidence_frames_to_save[pose_frame.index]:
                        ev_name = f"rep{dev.repetition_index or 0:02d}_{dev.deviation_type}"
                        ev_path = self.storage.evidence_frame(run_id, ev_name)
                        cv2.imwrite(str(ev_path), frame)
                        dev.evidence_frame_path = self.storage.relative(ev_path)

                if on_progress and seq_idx % 20 == 0:
                    on_progress("renderizando_video", 0.70 + 0.28 * seq_idx / max(1, total))
        finally:
            cap.release()
            writer.release()

    def _draw_skeleton(self, frame: np.ndarray, pose_frame: PoseFrame, color: tuple[int, int, int]) -> None:
        """Desenha pontos e conexões do esqueleto."""
        lm = pose_frame.landmarks
        if lm is None:
            return

        for p1_idx, p2_idx in POSE_CONNECTIONS:
            if lm[p1_idx, 3] > 0.4 and lm[p2_idx, 3] > 0.4:
                pt1 = (int(lm[p1_idx, 0]), int(lm[p1_idx, 1]))
                pt2 = (int(lm[p2_idx, 0]), int(lm[p2_idx, 1]))
                cv2.line(frame, pt1, pt2, color, 3, cv2.LINE_AA)

        for i in range(33):
            if lm[i, 3] > 0.4:
                pt = (int(lm[i, 0]), int(lm[i, 1]))
                cv2.circle(frame, pt, 5, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(frame, pt, 3, color, -1, cv2.LINE_AA)

    def _draw_hud(
        self,
        frame: np.ndarray,
        pose_frame: PoseFrame,
        result: ExerciseAnalysisResult,
        devs_now: list,
        width: int,
        height: int,
    ) -> None:
        """Desenha barra translúcida superior responsiva com métricas e alertas."""
        self.hud_renderer.draw_hud(frame, pose_frame, result, devs_now, width, height)

