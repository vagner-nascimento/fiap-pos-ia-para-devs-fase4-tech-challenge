"""Funções geométricas puras (sem dependência de MediaPipe).

Convenção: pontos são pares ``(x, y)`` em **pixels** (x para a direita, y para baixo, como na
imagem). Trabalhar em pixels, e não em coordenadas normalizadas, evita distorcer ângulos em
vídeos que não são quadrados. Qualquer entrada com ``NaN`` produz ``NaN``.
"""

import math
from typing import Sequence

import numpy as np

Point = Sequence[float] | np.ndarray


def _xy(p: Point) -> np.ndarray:
    return np.asarray(p, dtype=float)[:2]


def distance(a: Point, b: Point) -> float:
    """Distância euclidiana entre dois pontos."""
    return float(np.linalg.norm(_xy(a) - _xy(b)))


def midpoint(a: Point, b: Point) -> np.ndarray:
    """Ponto médio entre dois pontos."""
    return (_xy(a) + _xy(b)) / 2.0


def angle_between(a: Point, b: Point, c: Point) -> float:
    """Ângulo em graus (0 a 180) no vértice ``b`` formado por ``a-b-c``."""
    ba = _xy(a) - _xy(b)
    bc = _xy(c) - _xy(b)
    norm = np.linalg.norm(ba) * np.linalg.norm(bc)
    if not np.isfinite(norm) or norm == 0:
        return math.nan
    cos = float(np.clip(np.dot(ba, bc) / norm, -1.0, 1.0))
    return math.degrees(math.acos(cos))


def segment_angle_from_vertical(top: Point, bottom: Point) -> float:
    """Inclinação (graus, com sinal) do segmento ``bottom -> top`` em relação à vertical.

    0 = segmento vertical; positivo = ``top`` inclinado para a direita da imagem;
    negativo = para a esquerda.
    """
    v = _xy(top) - _xy(bottom)
    if not np.all(np.isfinite(v)) or np.linalg.norm(v) == 0:
        return math.nan
    return math.degrees(math.atan2(v[0], -v[1]))


def segment_angle_from_horizontal(start: Point, end: Point) -> float:
    """Inclinação (graus, com sinal, -90 a 90) do segmento ``start -> end`` vs. a horizontal.

    Positivo quando ``end`` está acima de ``start`` na imagem.
    """
    v = _xy(end) - _xy(start)
    if not np.all(np.isfinite(v)) or np.linalg.norm(v) == 0:
        return math.nan
    angle = math.degrees(math.atan2(-v[1], v[0]))
    if angle > 90:
        angle -= 180
    elif angle < -90:
        angle += 180
    return angle
