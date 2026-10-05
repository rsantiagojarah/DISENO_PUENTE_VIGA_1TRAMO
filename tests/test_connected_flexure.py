from dataclasses import replace

import pytest

from bridge_design.domain.abutment import (
    _concrete_shear_resistance_tn, _cracking_moment_tn_m,
    _effective_shear_depth_cm, _general_shear_beta,
)
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil
from bridge_design.domain.connected_reinforcement import SectionDemand, design_region, evaluate_option
from bridge_design.domain.crack_control import maximum_crack_control_spacing_m
from bridge_design.domain.rebar_catalog import reinforcing_bar_by_label
from bridge_design.domain.connected_section_checks import section_check


def sample_demands():
    return (
        SectionDemand("Resistencia", "strength", 75, 0, 20, 25, 0, 0.5),
        SectionDemand("Servicio", "service", 75, 0, 12, -18, 0, 0.5),
    )


@pytest.mark.parametrize("axial", [-1000, 0, 1000])
def test_axial_changes_shear_but_not_flexure_or_service_for_fixed_steel(axial):
    inputs = ConnectedInputs(FoundationSoil(3000, 0.5, 26.7)).left
    bar = reinforcing_bar_by_label('3/4"')
    for demand in sample_demands():
        original = section_check(demand, inputs, 7.5, bar, .15)
        actual = section_check(replace(demand, axial=axial), inputs, 7.5, bar, .15)
        assert actual["flexure_ratio"] == original["flexure_ratio"]
        assert actual["crack_ratio"] == original["crack_ratio"]
        if demand.limit_state != "service":
            if axial > 0:
                assert actual["shear_ratio"] > original["shear_ratio"]
            elif axial < 0:
                assert actual["shear_ratio"] < original["shear_ratio"]
            else:
                assert actual["shear_ratio"] == original["shear_ratio"]


@pytest.mark.parametrize("sign", [-1, 1])
def test_flexural_capacity_and_shear_match_individual_abutment_procedure(sign):
    inputs = ConnectedInputs(FoundationSoil(3000, 0.5, 26.7)).left
    bar = reinforcing_bar_by_label('3/4"')
    spacing = 0.15
    area = bar.area_cm2 / spacing
    depth = 75
    effective = depth - 7.5 - bar.diameter_cm / 2
    concrete = inputs.materials.concrete_strength_kg_cm2
    steel = inputs.materials.steel_yield_kg_cm2
    block_depth = area * steel / (0.85 * concrete * 100)
    capacity = 0.90 * area * steel * (effective - block_depth / 2) / 100000
    moment = sign * 25
    demand = SectionDemand("Resistencia", "strength", depth, -500, 20, moment, 0, 0)
    flexure, shear, crack, governing = evaluate_option(
        (demand,), inputs, 7.5, bar, spacing, full=True)
    required = max(abs(moment), min(_cracking_moment_tn_m(depth, inputs), 1.33 * abs(moment)))
    assert flexure == pytest.approx(required / capacity)
    shear_depth = _effective_shear_depth_cm(effective, depth)
    beta, *_details = _general_shear_beta(abs(moment), 20, area, shear_depth, axial_tn_m=demand.axial)
    assert shear == pytest.approx(20 / _concrete_shear_resistance_tn(shear_depth, inputs, 0.90, beta))
    assert crack == 0
    assert governing == demand


def test_service_uses_individual_abutment_stress_estimate_without_axial():
    inputs = ConnectedInputs(FoundationSoil(3000, 0.5, 26.7)).left
    bar = reinforcing_bar_by_label('3/4"')
    area = bar.area_cm2 / 0.15
    axis = 7.5 + bar.diameter_cm / 2
    stress = 18 * 100000 / (area * 0.90 * (75 - axis))
    maximum_spacing, _beta = maximum_crack_control_spacing_m(stress, axis, 75)
    demand = replace(sample_demands()[1], axial=1000)
    flexure, shear, crack, _governing = evaluate_option(
        (demand,), inputs, 7.5, bar, 0.15, full=True)
    assert flexure == shear == 0
    assert crack == pytest.approx(max(stress / (0.60 * inputs.materials.steel_yield_kg_cm2),
                                    0.15 / maximum_spacing))


@pytest.mark.parametrize("depth", [75, 150])
def test_legacy_simplified_request_uses_general_without_zero_shear_eligibility(depth):
    inputs = ConnectedInputs(FoundationSoil(3000, 0.5, 26.7)).left
    bar = reinforcing_bar_by_label('1"')
    demand = SectionDemand("Resistencia", "strength", depth, 0, 59.746, 85, 0, 0.5)
    general = section_check(demand, inputs, 7.5, bar, .10)
    legacy = section_check(replace(demand, shear_method="simplified"), inputs, 7.5, bar, .10)
    assert legacy["shear_method"] == "general"
    assert legacy["beta"] != pytest.approx(2)
    for key in ("beta", "shear_strain", "spacing_x_in", "spacing_xe_in", "shear_capacity", "shear_ratio"):
        assert legacy[key] == pytest.approx(general[key])


def test_insufficient_steel_fails_flexure_without_axial_check():
    inputs = ConnectedInputs(FoundationSoil(3000, 0.5, 26.7)).left
    bar = reinforcing_bar_by_label('1/2"')
    demand = replace(sample_demands()[0], moment=100)
    ratios = evaluate_option((demand,), inputs, 7.5, bar, 0.30, full=True)
    assert ratios[0] > 1


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("moment,expected", [(100, 100), (55, 62.970132926807764), (20, 26.6)])
def test_minimum_capacity_is_conditional_even_for_legacy_amplified_demands(sign, moment, expected):
    from bridge_design.domain.abutment import AbutmentInputs
    from bridge_design.domain.connected_steel_audit import area_requirements
    from bridge_design.reporting.connected_steel_trace import moment_demand_expression

    inputs = AbutmentInputs()
    bar = reinforcing_bar_by_label('1"')
    demand = SectionDemand("Resistencia", "strength", 110, 0, 1, sign*moment, 0, 0.5)
    legacy = replace(demand, capacity_multiplier=1.33)
    original = section_check(demand, inputs, 7.5, bar, .175)
    actual = section_check(legacy, inputs, 7.5, bar, .175)
    assert actual["required_moment"] == pytest.approx(expected)
    assert actual["flexure_ratio"] == pytest.approx(original["flexure_ratio"])
    assert moment_demand_expression(actual) == 'max(abs(Mu), min(Mcr, 1.33*abs(Mu)))'
    assert area_requirements((legacy,), inputs, 7.5, bar)[0]["flexural_area"] == pytest.approx(
        area_requirements((demand,), inputs, 7.5, bar)[0]["flexural_area"])
