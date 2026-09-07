import random

import pytest

from bridge_design.domain.sampling import envelope_sorted_samples, interpolate_sorted_samples


@pytest.mark.parametrize('target', ['min', 'max'])
def test_batch_envelope_exactly_matches_scalar_interpolation(target):
    rng = random.Random(2026)
    curves = [tuple((x, rng.uniform(-20, 20)) for x in sorted(
        rng.sample(range(100), 25)
    )) for _ in range(12)]
    curves.extend([((0.0, 2.0),), ((0.0, 0.0), (1e-9, 3.0), (1.0, -5.0))])
    xs = sorted({-1.0, 100.0, 1e-10, 1e-9, *[i / 10 for i in range(1000)],
                 *[x for curve in curves for x, _ in curve]})
    select = min if target == 'min' else max
    expected = tuple((x, select(interpolate_sorted_samples(c, x, tolerance=1e-8)
                                for c in curves)) for x in xs)
    assert envelope_sorted_samples(curves, xs, target, tolerance=1e-8) == expected
