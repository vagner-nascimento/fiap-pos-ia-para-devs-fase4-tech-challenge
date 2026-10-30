"""Índices do MediaPipe Pose e resolução dinâmica do lado do corpo."""

from enum import Enum, IntEnum
from typing import Optional


class Landmark(IntEnum):
    """Os 33 landmarks do MediaPipe Pose."""

    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


class BodySide(str, Enum):
    """Lado do corpo avaliado. Nunca é fixo: vem da prescrição ou é detectado (``AUTO``)."""

    RIGHT = "direito"
    LEFT = "esquerdo"
    AUTO = "auto"
    BOTH = "ambos"

    @classmethod
    def from_text(cls, value: Optional[str]) -> "BodySide":
        """Converte texto livre (``direito``, ``left``, ``esq``...) em ``BodySide``.

        ``None`` ou vazio resulta em ``AUTO``.
        """
        if value is None:
            return cls.AUTO
        text = str(value).strip().lower()
        if text in ("", "auto"):
            return cls.AUTO
        if text in ("direito", "direita", "dir", "right", "r"):
            return cls.RIGHT
        if text in ("esquerdo", "esquerda", "esq", "left", "l"):
            return cls.LEFT
        if text in ("ambos", "ambas", "both", "bilateral"):
            return cls.BOTH
        raise ValueError(f"Lado inválido: {value!r}")

    @property
    def opposite(self) -> "BodySide":
        if self is BodySide.RIGHT:
            return BodySide.LEFT
        if self is BodySide.LEFT:
            return BodySide.RIGHT
        raise ValueError(f"{self.value} não possui lado oposto")


_RIGHT = {
    "shoulder": Landmark.RIGHT_SHOULDER,
    "elbow": Landmark.RIGHT_ELBOW,
    "wrist": Landmark.RIGHT_WRIST,
    "hip": Landmark.RIGHT_HIP,
    "knee": Landmark.RIGHT_KNEE,
    "ankle": Landmark.RIGHT_ANKLE,
}
_LEFT = {
    "shoulder": Landmark.LEFT_SHOULDER,
    "elbow": Landmark.LEFT_ELBOW,
    "wrist": Landmark.LEFT_WRIST,
    "hip": Landmark.LEFT_HIP,
    "knee": Landmark.LEFT_KNEE,
    "ankle": Landmark.LEFT_ANKLE,
}


class JointMapper:
    """Resolve os landmarks das articulações de um lado (``RIGHT`` ou ``LEFT``).

    ``opposite`` dá acesso ao lado contrário (apoio, referência de tronco etc.).
    """

    def __init__(self, side: BodySide):
        if side not in (BodySide.RIGHT, BodySide.LEFT):
            raise ValueError("JointMapper exige lado RIGHT ou LEFT já resolvido")
        self.side = side
        self._own = _RIGHT if side is BodySide.RIGHT else _LEFT
        self._other = _LEFT if side is BodySide.RIGHT else _RIGHT

    @property
    def opposite(self) -> "JointMapper":
        return JointMapper(self.side.opposite)

    @property
    def shoulder(self) -> int:
        return int(self._own["shoulder"])

    @property
    def elbow(self) -> int:
        return int(self._own["elbow"])

    @property
    def wrist(self) -> int:
        return int(self._own["wrist"])

    @property
    def hip(self) -> int:
        return int(self._own["hip"])

    @property
    def knee(self) -> int:
        return int(self._own["knee"])

    @property
    def ankle(self) -> int:
        return int(self._own["ankle"])
