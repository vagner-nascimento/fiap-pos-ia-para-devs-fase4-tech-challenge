"""Processamento completo de vídeo com MediaPipe, renderização de HUD/esqueleto e extração de evidências."""

import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable, Optional

import cv2
import mediapipe as mp
import numpy as np

from config.media_paths import MediaStorage
from services.audio_transcription import (
    SpeechSegment,
    relevant_speech_segments,
    transcribe_video,
)
from services.pose.base_analyzer import BaseExerciseAnalyzer
from services.pose.joint_mapper import BodySide, JointMapper
from services.pose.landmark_extractor import extract_pose_frames
from services.pose.models import DeviationSeverity, ExerciseAnalysisResult, PoseFrame
from services.pose.object_detector import (
    ObjectDetection,
    ObjectDetector,
    detection_config,
    frame_detection_category,
    frame_detection_status,
    detection_summary,
)
from services.pose.registry import get_analyzer

from services.pose.hud_renderer import HudRenderer
from services.pose.sinks import FileResultSink, ResultSink

logger = logging.getLogger(__name__)

# Conexões principais para desenhar o esqueleto do corpo
POSE_CONNECTIONS = mp.solutions.pose.POSE_CONNECTIONS

# Cores BGR para o esqueleto
COLOR_GREEN = (40, 200, 80)
COLOR_YELLOW = (0, 215, 255)
COLOR_RED = (50, 50, 235)


class VideoPoseProcessor:
    """Orquestra a análise de vídeo: extração, detecção de desvios, renderização anotada e salvamento."""

    def __init__(
        self,
        media_storage: Optional[MediaStorage] = None,
        hud_renderer: Optional[HudRenderer] = None,
        result_sink: Optional[ResultSink] = None,
    ):
        self.storage = media_storage or MediaStorage.from_env()
        self.hud_renderer = hud_renderer or HudRenderer()
        self.result_sink = result_sink or FileResultSink(self.storage)

    def process_video(
        self,
        video_path: Path,
        exercise_identifier: str,
        run_id: str,
        side: BodySide | str | None = BodySide.AUTO,
        target_repetitions: Optional[int] = None,
        generate_annotated_video: bool = True,
        patient_id: Optional[str] = None,
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
            on_progress("transcrevendo_audio", 0.65)

        speech_segments: list[SpeechSegment] = []
        out_dir = self.storage.pose_output_dir(run_id)
        audio_path = out_dir / "session-audio.wav"
        try:
            all_speech_segments = transcribe_video(video_path, audio_path)
            result.extra["speech_transcription"] = [
                segment.as_dict() for segment in all_speech_segments
            ]
            speech_segments = relevant_speech_segments(all_speech_segments)
            result.extra["speech_transcription_status"] = "concluido"
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            result.extra["speech_transcription_status"] = "indisponivel"
            logger.warning(
                "Transcrição de áudio indisponível para run_id=%s: %s",
                run_id,
                exc,
            )
        finally:
            audio_path.unlink(missing_ok=True)

        if on_progress:
            on_progress("gerando_artefatos", 0.70)

        # 3. Preparação das pastas de saída
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

        # 5. Salva os resultados através do ResultSink (arquivos e/ou MongoDB)
        if on_progress:
            on_progress("persistindo_resultados", 0.99)

        self.result_sink.save(
            result=result,
            run_id=run_id,
            video_path=str(video_path),
            paciente_id=patient_id,
            speech_segments=speech_segments,
        )

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
        object_config = detection_config(result.session_summary.case_id)
        object_detector = ObjectDetector(object_config) if object_config else None
        object_detections: dict[int, list[ObjectDetection]] = {}
        detected_frames = 0
        detection_categories = {
            "not_detected": 0,
            "partially_detected": 0,
            "fully_detected": 0,
        }

        if object_detector:
            for pose_frame in extracted_frames:
                cap.set(cv2.CAP_PROP_POS_FRAMES, pose_frame.index)
                ok, source_frame = cap.read()
                if not ok:
                    break
                detections = object_detector.detect(source_frame)
                object_detections[pose_frame.index] = detections
                if detections:
                    detected_frames += 1
                detection_categories[frame_detection_category(detections)] += 1
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            result.extra["object_detection"] = detection_summary(
                config=object_config,
                total_frames=len(extracted_frames),
                detected_frames=detected_frames,
                confidence=object_detector.confidence,
                not_detected_frames=detection_categories["not_detected"],
                partially_detected_frames=detection_categories["partially_detected"],
                fully_detected_frames=detection_categories["fully_detected"],
            )

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
                if object_detector and object_config:
                    for detection in object_detections.get(pose_frame.index, []):
                        cv2.rectangle(
                            frame,
                            (detection.x1, detection.y1),
                            (detection.x2, detection.y2),
                            (0, 200, 0),
                            2,
                        )
                        cv2.putText(
                            frame,
                            f"{object_config.display_name} {detection.confidence:.2f}",
                            (detection.x1, max(detection.y1 - 8, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 200, 0),
                            2,
                            cv2.LINE_AA,
                        )
                    status, status_color = frame_detection_status(
                        object_config,
                        object_detections.get(pose_frame.index, []),
                    )
                    self.hud_renderer.draw_object_detection_status(
                        frame, status, width, height, status_color
                    )

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

        # Converte o vídeo de 'mp4v' para 'H.264' (avc1) via ffmpeg para suporte em browsers
        self._transcode_to_h264_if_available(
            output_video_path,
            audio_source_path=video_path,
        )

    def _transcode_to_h264_if_available(
        self,
        video_path: Path,
        audio_source_path: Optional[Path] = None,
    ) -> None:
        """Transcodifica o vídeo e muxa o áudio original quando disponível."""
        if not shutil.which("ffmpeg"):
            return
        temp_h264 = video_path.with_suffix(".h264.mp4")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
        ]
        if audio_source_path is not None:
            cmd.extend([
                "-i",
                str(audio_source_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-shortest",
            ])
        else:
            cmd.extend(["-map", "0:v:0"])
        cmd.extend([
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(temp_h264),
        ])
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            if res.returncode == 0 and temp_h264.exists() and temp_h264.stat().st_size > 0:
                temp_h264.replace(video_path)
                logger.info(
                    "Vídeo transcodificado para H.264%s: %s",
                    " com áudio original" if audio_source_path is not None else "",
                    video_path,
                )
            else:
                if audio_source_path is not None:
                    fallback_cmd = [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(video_path),
                        "-map",
                        "0:v:0",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-movflags",
                        "+faststart",
                        str(temp_h264),
                    ]
                    res = subprocess.run(
                        fallback_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=120,
                    )
                if res.returncode == 0 and temp_h264.exists() and temp_h264.stat().st_size > 0:
                    temp_h264.replace(video_path)
                    logger.warning(
                        "Vídeo transcodificado sem áudio: a fonte não possui trilha compatível."
                    )
                else:
                    logger.warning(
                        "Falha na transcodificação ffmpeg (rc=%s): %s",
                        res.returncode,
                        res.stderr.decode()[:200],
                    )
                    if temp_h264.exists():
                        temp_h264.unlink()
        except Exception as exc:
            logger.warning("Exceção ao transcodificar vídeo via ffmpeg: %s", exc)
            if temp_h264.exists():
                temp_h264.unlink()

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
