import pytest

from bridge_design.domain.concrete_flexure import rectangular_flexural_response
from bridge_design.domain.frame_concrete import interaction_curve, moment_capacity, service_tension_stress


def test_interaction_has_pure_tension_and_compression_limits():
    curve = interaction_curve(80, 6, 20, 210, 4200)
    assert curve[0] == pytest.approx((-0.9 * 40 * 4200 / 1000, 0))
    assert curve[-1] == pytest.approx((0.8 * 0.75 * (0.85 * 210 * (8000 - 40) + 40 * 4200) / 1000, 0))
    assert moment_capacity(curve, curve[-1][0] + 1) == -1
    assert moment_capacity(curve, curve[0][0] - 1) == -1
    assert moment_capacity(curve, 0) > 0


def test_two_face_flexure_is_close_to_shared_single_face_solution():
    reference = rectangular_flexural_response(20, 100, 74, 210, 4200)
    resistance = moment_capacity(interaction_curve(80, 6, 20, 210, 4200), 0)
    assert resistance == pytest.approx(reference.resistance_factor * reference.nominal_moment_tn_m, rel=0.05)


def test_cracked_service_pure_tension_and_sign_reversal():
    tension = service_tension_stress(80, 6, 20, 250000, -40, 0)
    assert tension == pytest.approx((1000, 1000))
    positive = service_tension_stress(80, 6, 20, 250000, 0, 20)
    negative = service_tension_stress(80, 6, 20, 250000, 0, -20)
    assert positive == pytest.approx(tuple(reversed(negative)))
    assert min(positive) == 0
    assert max(positive) > 0
