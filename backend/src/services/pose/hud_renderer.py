"""Renderizador responsivo do HUD em vídeo com suporte a acentuação e UTF-8 via Pillow."""

import glob
import os
import textwrap
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from services.pose.models import DeviationEvent, DeviationSeverity, ExerciseAnalysisResult, PoseFrame

# Candidatos de fontes TrueType comuns no Linux / Docker
FONT_CANDIDATES = [
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/Lato-Regular.ttf",
]


def _find_system_font() -> Optional[str]:
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            return path
    # Busca genérica caso estejam em outro caminho
    matched = glob.glob("/usr/share/fonts/**/*[sS]ans*Regular*.ttf", recursive=True)
    if matched:
        return matched[0]
    return None


_SYSTEM_FONT_PATH = _find_system_font()


class HudRenderer:
    """Renderiza a barra superior HUD adaptada proporcionalmente à resolução do vídeo."""

    def __init__(self, font_path: Optional[str] = None):
        self.font_path = font_path or _SYSTEM_FONT_PATH

    def get_font(self, size: int) -> ImageFont.ImageFont:
        if self.font_path:
            try:
                return ImageFont.truetype(self.font_path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def draw_hud(
        self,
        frame: np.ndarray,
        pose_frame: PoseFrame,
        result: ExerciseAnalysisResult,
        active_deviations: list[DeviationEvent],
        width: int,
        height: int,
    ) -> None:
        """Desenha barra translúcida superior, métricas e alertas sem estourar as margens."""
        # 1. Definição responsiva de tamanhos com base na largura
        pad = max(10, int(width * 0.03))
        font_size_main = max(12, int(width * 0.032))
        font_size_alert = max(10, int(width * 0.026))

        font_main = self.get_font(font_size_main)
        font_alert = self.get_font(font_size_alert)

        # Prepara textos da linha superior
        case_txt = f"{result.session_summary.case_id} ({result.session_summary.side_evaluated})"
        rep_count = len([r for r in result.repetitions if r.start_time <= pose_frame.time])
        target_str = str(result.session_summary.target_repetitions or "-")
        rep_txt = f"Rep: {rep_count} / {target_str}"
        score_txt = f"Score: {result.session_summary.compliance_score:.0f}%"

        # Prepara texto e quebra de linha do alerta (se houver)
        alert_lines = []
        is_grave = False
        if active_deviations:
            descriptions = [d.description for d in active_deviations]
            is_grave = any(d.severity == DeviationSeverity.GRAVE for d in active_deviations)
            raw_alert = "ALERTA: " + " | ".join(descriptions)
            # Calcula quantos caracteres cabem por linha aproximadamente
            char_width_approx = max(6, int(font_size_alert * 0.58))
            max_chars = max(20, (width - 2 * pad - 20) // char_width_approx)
            alert_lines = textwrap.wrap(raw_alert, width=max_chars)

        # Altura dinâmica do HUD
        line_height_main = int(font_size_main * 1.3)
        line_height_alert = int(font_size_alert * 1.35)
        top_bar_h = pad + line_height_main + int(pad * 0.6)

        if alert_lines:
            alert_box_h = len(alert_lines) * line_height_alert + int(pad * 0.8)
            hud_total_h = top_bar_h + alert_box_h + int(pad * 0.4)
        else:
            alert_box_h = 0
            hud_total_h = top_bar_h

        hud_total_h = min(hud_total_h, int(height * 0.35))

        # 2. Fundo translúcido do HUD
        overlay = frame[:hud_total_h, :].copy()
        cv2.rectangle(overlay, (0, 0), (width, hud_total_h), (18, 26, 26), -1)
        cv2.addWeighted(overlay, 0.82, frame[:hud_total_h, :], 0.18, 0, frame[:hud_total_h, :])
        cv2.line(frame, (0, hud_total_h - 1), (width, hud_total_h - 1), (50, 70, 70), 1)

        # 3. Caixa destacada de alerta (se ativo)
        if alert_lines:
            alert_box_y1 = top_bar_h - int(pad * 0.2)
            alert_box_y2 = alert_box_y1 + alert_box_h
            bg_alert = (25, 25, 75) if not is_grave else (20, 20, 95)
            border_alert = (40, 180, 240) if not is_grave else (40, 50, 230)
            cv2.rectangle(frame, (pad, alert_box_y1), (width - pad, alert_box_y2), bg_alert, -1)
            cv2.rectangle(frame, (pad, alert_box_y1), (width - pad, alert_box_y2), border_alert, 1)

        # 4. Renderização do texto com Pillow na região do HUD (UTF-8 com acentos)
        hud_roi_rgb = cv2.cvtColor(frame[:hud_total_h, :], cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(hud_roi_rgb)
        draw = ImageDraw.Draw(pil_img)

        # Linha 1: Caso (esquerda)
        y_main = pad // 2
        draw.text((pad, y_main), case_txt, font=font_main, fill=(240, 245, 245))

        # Linha 1: Repetições (centro)
        rep_bbox = font_main.getbbox(rep_txt)
        rep_w = rep_bbox[2] - rep_bbox[0]
        x_rep = max(pad + 10, int(width * 0.5 - rep_w / 2))
        draw.text((x_rep, y_main), rep_txt, font=font_main, fill=(0, 240, 255))

        # Linha 1: Score (direita)
        score_bbox = font_main.getbbox(score_txt)
        score_w = score_bbox[2] - score_bbox[0]
        x_score = max(x_rep + rep_w + 10, width - pad - score_w)
        draw.text((x_score, y_main), score_txt, font=font_main, fill=(50, 220, 100))

        # Linha 2+: Linhas do alerta (com word wrap e acentos)
        if alert_lines:
            alert_text_color = (255, 220, 40) if not is_grave else (255, 80, 80)
            y_curr = alert_box_y1 + int(pad * 0.3)
            for line in alert_lines:
                draw.text((pad + 10, y_curr), line, font=font_alert, fill=alert_text_color)
                y_curr += line_height_alert

        # Retorna o ROI processado com PIL para o frame OpenCV BGR
        frame[:hud_total_h, :] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
