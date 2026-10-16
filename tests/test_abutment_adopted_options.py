"""Regressions for diameter-specific recommendations, sliding and stem cuts."""

from dataclasses import replace

import pytest

from bridge_design import abutment_main as workflow
from bridge_design.cli.abutment_ascii_output import format_abutment_reinforcement_option_tables
from bridge_design.domain import abutment
from bridge_design.domain.rebar_catalog import custom_spacing_option


@pytest.fixture(scope="module", params=[False, True], ids=["abutment", "wall"])
def preliminary(request):
    return abutment.solve_abutment_design(abutment.AbutmentInputs(is_pure_wall=request.param))


@pytest.mark.parametrize("attribute", ["stem_design", "heel_design", "toe_design", "key_design"])
def test_each_diameter_matches_final_design(preliminary, attribute):
    case = getattr(preliminary, attribute)
    assert case is not None
    recommended = case.spacing_options.recommended
    assert recommended is not None
    for option in case.spacing_options.options:
        result = abutment.solve_abutment_design(preliminary.inputs, {case.name: option})
        actual = getattr(result, attribute)
        assert actual.required_as_cm2_m == pytest.approx(option.required_area_cm2_m)
        assert actual.provided_as_cm2_m == pytest.approx(option.provided_area_cm2_m)
        assert actual.selected_spacing_m == option.spacing_m
        gross = abutment._section_depth_cm(preliminary.inputs, case.name)
        r = preliminary.inputs.reinforcement
        cover = r.stem_cover_cm if attribute == "stem_design" else r.footing_cover_cm
        assert actual.effective_depth_cm == pytest.approx(gross - cover - option.bar.diameter_cm / 2)
        if option.is_compliant:
            assert actual.provided_as_cm2_m + 1e-9 >= actual.required_as_cm2_m
            assert actual.moment_status == "OK"
        # Adopting one option must not change the requirements for other bars.
        assert actual.spacing_options.options == case.spacing_options.options


def test_reported_707m_false_recommendation_is_fixed():
    inputs = abutment.AbutmentInputs()
    inputs = replace(inputs, geometry=replace(inputs.geometry, retained_height_m=7.07))
    preliminary = abutment.solve_abutment_design(inputs)
    options = preliminary.stem_design.spacing_options
    inch = next(o for o in options.options if o.bar.label == '1"')
    assert inch.required_area_cm2_m == pytest.approx(25.078568173908618)
    assert inch.spacing_m == .175
    assert inch.is_compliant
    recommended = options.recommended
    assert recommended.bar.label == '3/4"'
    assert recommended.spacing_m == .1
    actual = abutment.solve_abutment_design(inputs, {"Pantalla": recommended}).stem_design
    assert actual.moment_status == "OK"
    assert actual.moment_resistance_tn_m_m >= actual.controlling_moment_tn_m_m
    with pytest.raises(ValueError, match="25.079"):
        custom_spacing_option(options, '1"', .2)
    custom = custom_spacing_option(options, '1"', .175)
    assert custom.required_area_cm2_m == inch.required_area_cm2_m
    assert abutment.solve_abutment_design(inputs, {"Pantalla": custom}).stem_design.moment_status == "OK"
    table = format_abutment_reinforcement_option_tables(preliminary)
    assert "25.079" in table
    assert "peralte efectivo de cada alternativa" in table
    assert "Cortante, servicio y anclaje se verifican por separado" in table


def test_infeasible_diameter_is_not_recommended_or_allowed_as_custom():
    # A depth with a feasible flexural solution can become infeasible when
    # the largest diameter moves the reinforcement centroid inward.
    inputs = abutment.AbutmentInputs()
    inputs = replace(inputs, key=replace(inputs.key, width_m=.2))
    grid = abutment.SpacingGrid()

    def build(depth, option):
        return abutment._reinforced_case(
            "Diente de concreto", 8.5, depth, 1.0, 1.0, inputs, grid,
            .9, '3/4"', 1.0, option, shear_method="simplified",
        )

    selected = abutment.generate_spacing_options("Diente de concreto", 1.0, grid).options[5]
    result = abutment._reinforce_at_adopted_depth(build, 20.0, 7.5, 1.91, selected)
    inch = next(o for o in result.spacing_options.options if o.bar.label == '1"')
    assert not inch.is_compliant
    assert not inch.is_recommended
    assert inch.required_area_cm2_m == float("inf")
    with pytest.raises(ValueError, match="solucion de flexion viable"):
        custom_spacing_option(result.spacing_options, '1"', .1)


@pytest.fixture(scope="module")
def bridge_sliding_failure():
    inputs = abutment.AbutmentInputs()
    inputs = replace(
        inputs,
        geometry=replace(inputs.geometry, footing_width_m=5.50),
        loads=replace(inputs.loads, braking_tn_m=5.0),
        soil=replace(inputs.soil, foundation_interface_friction_deg=25.0),
    )
    return abutment.solve_abutment_design(inputs)


def test_bridge_sliding_failure_is_not_hidden_by_without_bridge(bridge_sliding_failure):
    result = bridge_sliding_failure
    assert result.footing_width_recommendation is None
    assert all(s.sliding_with_key_status == "OK" for s in result.without_bridge)
    assert result.with_bridge[0].hu_tn_m == pytest.approx(37.0475)
    assert result.with_bridge[0].key_resistance_tn_m == pytest.approx(35.08457589455161)
    assert workflow._has_effective_sliding_failure(result)
    assert workflow._recommended_key_height_m(result.inputs, result) == pytest.approx(.75)


def test_key_prompt_retries_until_bridge_condition_also_passes(monkeypatch, bridge_sliding_failure):
    result = bridge_sliding_failure
    calls = []

    def enter_key(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return result.inputs.key  # Still insufficient with the bridge.
        assert len(calls) == 2
        return replace(result.inputs.key, height_m=kwargs["default_height_m"])

    monkeypatch.setattr(workflow, "collect_abutment_key", enter_key)
    inputs, actual = workflow._consider_key_when_sliding_fails(result.inputs, result)
    assert len(calls) == 2
    assert inputs.key.height_m == pytest.approx(.75)
    assert not workflow._has_effective_sliding_failure(actual)
    assert all(s.sliding_with_key_status == "OK" for s in workflow._sliding_states(actual))


@pytest.mark.parametrize("with_key", [False, True])
@pytest.mark.parametrize("condition", ["with_bridge", "without_bridge"])
def test_unselected_seismic_alternative_is_checked(bridge_sliding_failure, with_key, condition):
    original = bridge_sliding_failure
    safe = replace(
        original.with_bridge[0], hu_tn_m=1.0, friction_resistance_tn_m=10.0,
        sliding_status="OK", sliding_with_key_status="OK", key_resistance_tn_m=11.0,
    )
    failed = replace(safe, hu_tn_m=30.0, sliding_status="NO", sliding_with_key_status="NO")
    result = replace(
        original, with_bridge=(safe,), without_bridge=(safe,),
        extreme_seismic_with_bridge=(safe, safe),
        extreme_seismic_without_bridge=(safe, safe),
        key=original.key if with_key else None,
    )
    result = replace(result, **{f"extreme_seismic_{condition}": (safe, failed)})
    assert workflow._has_sliding_failure(result)
    assert workflow._has_effective_sliding_failure(result)
    assert workflow._recommended_key_height_m(result.inputs, result) > .4


def test_wall_does_not_use_duplicate_bridge_condition():
    result = abutment.solve_abutment_design(abutment.AbutmentInputs(is_pure_wall=True))
    assert workflow._sliding_states(result) == (
        result.with_bridge + result.extreme_seismic_with_bridge
    )


def test_cut_minimum_capacity_uses_gross_thickness_not_initial_diameter():
    inputs = abutment.AbutmentInputs()
    depth = 100.0 - inputs.reinforcement.stem_cover_cm - 2.54 / 2
    legacy_thickness = depth + inputs.reinforcement.stem_cover_cm + inputs.reinforcement.stem_main_bar_diameter_cm / 2
    real_mcr = abutment._cracking_moment_tn_m(100.0, inputs)
    legacy_mcr = abutment._cracking_moment_tn_m(legacy_thickness, inputs)
    assert real_mcr == pytest.approx(52.0414321709)
    assert legacy_mcr == pytest.approx(51.7114936868)
    area = abutment._flexural_steel_area_workbook_cm2_m(
        (real_mcr + legacy_mcr) / 2, 100.0, depth,
        inputs.materials.concrete_strength_kg_cm2,
        inputs.materials.steel_yield_kg_cm2, inputs.reinforcement.flexural_phi,
    )
    moments = {"strength_mu": 40.0, "extreme_mu": 0.0}
    assert abutment._stem_provided_steel_satisfies_limit_states(
        inputs, area, depth, moments, gross_depth_cm=legacy_thickness,
    )
    assert not abutment._stem_provided_steel_satisfies_limit_states(
        inputs, area, depth, moments, gross_depth_cm=100.0,
    )


@pytest.mark.parametrize("diameter", [1.27, 1.91, 2.54])
def test_cut_passes_actual_thickness_in_every_interval(monkeypatch, preliminary, diameter):
    checks = []
    real_check = abutment._stem_provided_steel_satisfies_limit_states

    def checked(inputs, area, depth, moments, *, gross_depth_cm):
        checks.append((depth, gross_depth_cm))
        return real_check(inputs, area, depth, moments, gross_depth_cm=gross_depth_cm)

    monkeypatch.setattr(abutment, "_stem_provided_steel_satisfies_limit_states", checked)
    abutment._stem_cut_upper_steel_satisfies(
        preliminary.inputs, preliminary.pressures, 1.0, 50.0, diameter,
    )
    assert checks
    for depth, gross in checks:
        assert gross - depth == pytest.approx(preliminary.inputs.reinforcement.stem_cover_cm + diameter / 2)


def test_selected_cut_is_independent_of_initial_bar_diameter():
    inputs = abutment.AbutmentInputs(
        geometry=abutment.AbutmentGeometryInputs(
            retained_height_m=8.30, footing_width_m=6.0, footing_thickness_m=1.0,
            toe_length_m=2.0, lower_stem_thickness_m=1.0, upper_stem_thickness_m=.5,
            front_soil_depth_m=1.0,
        ),
        is_pure_wall=True,
    )
    preliminary = abutment.solve_abutment_design(inputs)
    selected = custom_spacing_option(preliminary.stem_design.spacing_options, '1"', .1)
    first = abutment.solve_abutment_design(inputs, {"Pantalla": selected})
    changed = replace(inputs, reinforcement=replace(inputs.reinforcement, stem_main_bar_diameter_cm=1.27))
    second = abutment.solve_abutment_design(changed, {"Pantalla": selected})
    assert first.stem_reinforcement_cut is not None
    assert first.stem_reinforcement_cut == second.stem_reinforcement_cut
