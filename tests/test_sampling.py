import pytest

from bridge_design.domain.sampling import interpolate_sorted_samples


def test_interpolate_sorted_samples_preserves_boundaries_and_linear_values():
    samples = ((0.0, 2.0), (0.3, 5.0), (1.0, -2.0))

    assert interpolate_sorted_samples(samples, -1.0) == pytest.approx(2.0)
    assert interpolate_sorted_samples(samples, 0.0) == pytest.approx(2.0)
    assert interpolate_sorted_samples(samples, 0.15) == pytest.approx(3.5)
    assert interpolate_sorted_samples(samples, 0.3) == pytest.approx(5.0)
    assert interpolate_sorted_samples(samples, 0.65) == pytest.approx(1.5)
    assert interpolate_sorted_samples(samples, 2.0) == pytest.approx(-2.0)


def test_interpolate_sorted_samples_rejects_an_empty_sequence():
    with pytest.raises(ValueError, match="Sin resultados"):
        interpolate_sorted_samples((), 0.0, empty_message="Sin resultados")


def test_interpolate_sorted_samples_preserves_degenerate_interval_behavior():
    samples = ((0.0, 1.0), (0.5, 3.0), (0.5, 8.0), (1.0, 4.0))

    assert interpolate_sorted_samples(samples, 0.5, tolerance=1e-9) == pytest.approx(3.0)
