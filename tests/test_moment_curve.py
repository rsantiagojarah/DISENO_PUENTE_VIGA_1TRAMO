import pytest

from bridge_design.domain.moment_curve import MomentCurve, combine_moment_curves, load_moment_curve
from bridge_design.domain.transverse_slab import LoadSegment, PointLoad, _bending_moment_at


@pytest.mark.parametrize("operation", ["min", "max", "sum"])
def test_quadratic_crossings_and_extrema(operation):
    first = MomentCurve((4.0,), ((-1.0, 4.0, 0.0),))
    second = MomentCurve((1.5, 4.0), ((0.0, 0.0, 3.0), (0.0, 0.0, 3.0)))
    curve = combine_moment_curves(first, second, operation)
    select = {"min": min, "max": max, "sum": sum}[operation]
    for i in range(401):
        x = i / 100
        assert curve.value(x) == pytest.approx(select((first.value(x), second.value(x))), abs=1e-12)
    if operation == "max":
        assert 1.0 in curve.ends and 3.0 in curve.ends
        assert (2.0, 4.0) in curve.samples(())


def test_load_curve_matches_equilibrium_at_every_station():
    segments = (LoadSegment(0.3, 3.8, 2.1, "q"),)
    points = (PointLoad(1.27, 4.8, "P"),)
    reactions = ((0.0, 4.0), (4.0, 8.15))
    curve = load_moment_curve(4.0, segments, points, reactions)
    for i in range(401):
        x = i / 100
        assert curve.value(x) == pytest.approx(
            _bending_moment_at(x, segments, points, reactions), abs=1e-12
        )
