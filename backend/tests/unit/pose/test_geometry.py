import math

import numpy as np
import pytest

from services.pose.geometry import (
    angle_between,
    distance,
    midpoint,
    segment_angle_from_horizontal,
    segment_angle_from_vertical,
)


def test_angle_right():
    assert angle_between((0, 1), (0, 0), (1, 0)) == pytest.approx(90)


def test_angle_straight_line():
    assert angle_between((-1, 0), (0, 0), (1, 0)) == pytest.approx(180)


def test_angle_zero_when_overlapping_direction():
    assert angle_between((1, 0), (0, 0), (2, 0)) == pytest.approx(0, abs=1e-6)


def test_angle_degenerate_is_nan():
    assert math.isnan(angle_between((0, 0), (0, 0), (1, 0)))


def test_angle_nan_input_is_nan():
    assert math.isnan(angle_between((np.nan, np.nan), (0, 0), (1, 0)))


def test_angle_ignores_extra_columns():
    assert angle_between((0, 1, 9), (0, 0, 9), (1, 0, 9)) == pytest.approx(90)


def test_distance_and_midpoint():
    assert distance((0, 0), (3, 4)) == pytest.approx(5)
    assert midpoint((0, 0), (2, 4)).tolist() == [1, 2]


def test_vertical_segment_has_zero_angle():
    # y cresce para baixo: topo em y menor
    assert segment_angle_from_vertical((0, 0), (0, 10)) == pytest.approx(0)


def test_vertical_angle_sign():
    assert segment_angle_from_vertical((10, 0), (0, 10)) == pytest.approx(45)
    assert segment_angle_from_vertical((-10, 0), (0, 10)) == pytest.approx(-45)


def test_horizontal_angle():
    assert segment_angle_from_horizontal((0, 0), (10, 0)) == pytest.approx(0)
    assert segment_angle_from_horizontal((0, 10), (10, 0)) == pytest.approx(45)
    # independe do sentido do segmento
    assert segment_angle_from_horizontal((10, 0), (0, 10)) == pytest.approx(45)


def test_segment_degenerate_is_nan():
    assert math.isnan(segment_angle_from_vertical((1, 1), (1, 1)))
    assert math.isnan(segment_angle_from_horizontal((1, 1), (1, 1)))
