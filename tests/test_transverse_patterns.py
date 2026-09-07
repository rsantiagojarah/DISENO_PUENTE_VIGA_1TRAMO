import pytest

from bridge_design.codes.mtc_2018 import mtc_design_lanes
from bridge_design.domain.loads import VehicleLoadModel
from bridge_design.domain.transverse_patterns import (
    TRANSVERSE_WHEEL_CLEARANCE_M, TransverseLaneGeometryError,
    lane_positions, wheel_patterns, positions, validate_lane_geometry,
)


@pytest.mark.parametrize("width,count,lane_width", [
    (5.9, 1, 3.6), (6.0, 2, 3.0), (6.3, 2, 3.15),
    (7.2, 2, 3.6), (9.5, 2, 3.6), (10.8, 3, 3.6), (14.4, 4, 3.6),
])
def test_lane_count_and_exception(width, count, lane_width):
    actual_count, actual_width = mtc_design_lanes(width)
    assert actual_count == count
    assert actual_width == pytest.approx(lane_width)


def test_hl93_keeps_design_lane_separate_from_loaded_width():
    vehicle = VehicleLoadModel.mtc_hl93_default()
    assert vehicle.design_lane_width_m == 3.6
    assert vehicle.lane_load_width_m == 3.0
    assert vehicle.wheel_transverse_spacing_m == 1.8
    assert TRANSVERSE_WHEEL_CLEARANCE_M == 0.6


def test_independent_wheels_and_mirrored_patterns():
    patterns = set(wheel_patterns(0.0, 7.2, 2, 0.5, 1.8288))
    assert len({round(b - a, 6) for a, b in patterns}) > 1
    for pattern in patterns:
        assert tuple(round(7.2 - 1.8288 - x, 10) for x in reversed(pattern)) in patterns
        assert pattern[0] >= TRANSVERSE_WHEEL_CLEARANCE_M
        assert pattern[-1] + 1.8288 <= 7.2 - TRANSVERSE_WHEEL_CLEARANCE_M + 1e-9


@pytest.mark.parametrize("width", [6.0, 6.05, 6.0959])
def test_rounded_metric_exception_does_not_silently_shrink_imperial_loads(width):
    with pytest.raises(TransverseLaneGeometryError, match="convencion dimensional"):
        validate_lane_geometry(width, 1.8288, 3.048)


@pytest.mark.parametrize("width", [6.0, 6.05, 6.096, 6.10, 6.3, 7.2])
def test_two_lanes_fit_at_metric_threshold(width):
    assert validate_lane_geometry(width, 1.8, 3.0)[0] == 2
    patterns = list(wheel_patterns(0, width, 2, 0.1, 1.8))
    assert patterns
    assert all(p[0] >= TRANSVERSE_WHEEL_CLEARANCE_M - 1e-9 for p in patterns)
    assert all(p[-1] + 1.8 <= width - TRANSVERSE_WHEEL_CLEARANCE_M + 1e-9 for p in patterns)
    if width == 6.0:
        assert patterns == [(0.6, 3.6)]


@pytest.mark.parametrize("step", [0, -0.1])
def test_invalid_step_is_rejected_instead_of_looping_forever(step):
    with pytest.raises(ValueError):
        list(positions(0.0, 1.0, step))


def test_three_lanes_fit_and_four_are_rejected_at_10_8_m():
    assert list(lane_positions(0.0, 10.8, 3, 0.5)) == [(0.0, 3.6, 7.2)]
    assert list(lane_positions(0.0, 10.8, 4, 0.5)) == []
