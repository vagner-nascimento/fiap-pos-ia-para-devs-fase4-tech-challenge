import pytest

from services.pose.joint_mapper import BodySide, JointMapper, Landmark


@pytest.mark.parametrize(
    "text,expected",
    [
        (None, BodySide.AUTO),
        ("", BodySide.AUTO),
        ("auto", BodySide.AUTO),
        ("direito", BodySide.RIGHT),
        ("Direita", BodySide.RIGHT),
        ("right", BodySide.RIGHT),
        ("esquerdo", BodySide.LEFT),
        (" ESQ ", BodySide.LEFT),
        ("left", BodySide.LEFT),
        ("ambos", BodySide.BOTH),
    ],
)
def test_from_text(text, expected):
    assert BodySide.from_text(text) is expected


def test_from_text_invalid():
    with pytest.raises(ValueError):
        BodySide.from_text("frente")


def test_opposite():
    assert BodySide.RIGHT.opposite is BodySide.LEFT
    assert BodySide.LEFT.opposite is BodySide.RIGHT
    with pytest.raises(ValueError):
        BodySide.AUTO.opposite


def test_right_mapping():
    m = JointMapper(BodySide.RIGHT)
    assert (m.shoulder, m.elbow, m.wrist) == (12, 14, 16)
    assert (m.hip, m.knee, m.ankle) == (24, 26, 28)


def test_left_mapping():
    m = JointMapper(BodySide.LEFT)
    assert (m.shoulder, m.elbow, m.wrist) == (11, 13, 15)
    assert (m.hip, m.knee, m.ankle) == (23, 25, 27)


def test_opposite_mapper():
    assert JointMapper(BodySide.RIGHT).opposite.knee == Landmark.LEFT_KNEE


@pytest.mark.parametrize("side", [BodySide.AUTO, BodySide.BOTH])
def test_mapper_requires_resolved_side(side):
    with pytest.raises(ValueError):
        JointMapper(side)
