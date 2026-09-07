import pytest

from bridge_design.domain.concrete_flexure import (
    mtc_flexural_resistance_factor,
    rectangular_flexural_response,
)
from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel
from bridge_design.domain.materials import (
    ConcreteProperties,
    LinearWeightProperties,
    MaterialProperties,
    SteelProperties,
    SurfaceLayerProperties,
)
from bridge_design.domain.crack_control import (
    crack_control_compliance_statuses,
    maximum_crack_control_spacing_m,
    review_transverse_slab_crack_control,
)
from bridge_design.domain.rebar_catalog import (
    REINFORCING_BAR_CATALOG,
    SpacingGrid,
    custom_spacing_option,
    generate_spacing_options,
)
from bridge_design.domain.reinforcement import (
    SlabReinforcementParameters,
    design_transverse_slab_reinforcement,
    flexural_steel_area_cm2,
    mtc_cracking_moment_tn_m,
    mtc_minimum_flexural_moment_tn_m,
)
from bridge_design.domain.transverse_slab import (
    TransverseLoadLayout,
    TransverseSlabGeometry,
    solve_transverse_slab_design,
)


def _materials() -> MaterialProperties:
    return MaterialProperties(
        concrete=ConcreteProperties.from_inputs(
            specific_weight_tn_m3=2.4,
            compressive_strength_kg_cm2=280.0,
        ),
        steel=SteelProperties(),
        asphalt=SurfaceLayerProperties("asfalto", 2.2, 0.05),
        sidewalk=SurfaceLayerProperties("vereda", 2.4, 0.20),
        railing=LinearWeightProperties("baranda", 100.0),
        barrier=LinearWeightProperties("barrera", 500.0),
    )


def test_flexural_steel_area_solves_rectangular_section() -> None:
    steel_area = flexural_steel_area_cm2(
        design_moment_tn_m=10.0,
        strip_width_cm=100.0,
        effective_depth_cm=15.0,
        concrete_strength_kg_cm2=280.0,
        steel_yield_kg_cm2=4200.0,
    )

    assert round(steel_area, 3) == 19.986


def test_mtc_minimum_flexural_capacity_uses_cracking_moment() -> None:
    cracking = mtc_cracking_moment_tn_m(
        section_modulus_cm3=100.0 * 20.0**2 / 6.0,
        concrete_strength_kg_cm2=280.0,
    )

    assert cracking == pytest.approx(2.466, abs=0.002)
    assert mtc_minimum_flexural_moment_tn_m(2.0, cracking) == pytest.approx(cracking)
    assert mtc_minimum_flexural_moment_tn_m(2.0, 4.0) == pytest.approx(2.66)


def test_reinforcing_bar_catalog_contains_project_bars() -> None:
    assert tuple((bar.label, bar.area_cm2) for bar in REINFORCING_BAR_CATALOG) == (
        ("6 mm", 0.28),
        ("8 mm", 0.50),
        ('3/8"', 0.71),
        ('1/2"', 1.29),
        ('5/8"', 2.00),
        ('3/4"', 2.84),
        ('1"', 5.00),
    )


def test_spacing_options_round_down_to_025_m_grid() -> None:
    options = generate_spacing_options(
        "Acero prueba",
        required_area_cm2_m=4.0,
        spacing_grid=SpacingGrid(step_m=0.025, minimum_m=0.10, maximum_m=0.30),
    )
    by_bar = {option.bar.label: option for option in options.options}

    assert by_bar["6 mm"].spacing_m == 0.10
    assert by_bar["6 mm"].is_compliant is False
    assert by_bar["8 mm"].spacing_m == 0.125
    assert by_bar["8 mm"].provided_area_cm2_m == 4.0
    assert options.recommended == by_bar["8 mm"]


def test_spacing_catalog_has_no_recommendation_when_no_constructible_option_exists() -> None:
    options = generate_spacing_options(
        "Acero imposible",
        required_area_cm2_m=200.0,
        spacing_grid=SpacingGrid(step_m=0.025, minimum_m=0.10, maximum_m=0.30),
    )

    assert options.recommended is None
    assert not any(option.is_compliant for option in options.options)


def test_spacing_options_cap_low_required_steel_at_maximum_spacing() -> None:
    options = generate_spacing_options(
        "Ask longitudinal por cara",
        required_area_cm2_m=0.659,
        spacing_grid=SpacingGrid(step_m=0.025, minimum_m=0.10, maximum_m=0.30),
    )
    by_bar = {option.bar.label: option for option in options.options}

    assert by_bar["6 mm"].spacing_m == 0.30
    assert by_bar["6 mm"].provided_area_cm2_m == pytest.approx(0.933333)
    assert by_bar['1"'].spacing_m == 0.30
    assert by_bar['1"'].provided_area_cm2_m == pytest.approx(16.666667)
    assert options.recommended == by_bar["6 mm"]


def test_custom_spacing_can_use_a_compliant_value_outside_the_table_grid() -> None:
    options = generate_spacing_options(
        "Acero personalizado",
        required_area_cm2_m=4.0,
        spacing_grid=SpacingGrid(step_m=0.025, minimum_m=0.10, maximum_m=0.30),
    )

    selected = custom_spacing_option(options, '1/2"', 0.180)

    assert selected.item == 0
    assert selected.is_custom is True
    assert selected.is_compliant is True
    assert selected.spacing_m == pytest.approx(0.180)
    assert selected.provided_area_cm2_m == pytest.approx(1.29 / 0.180)
    assert all(option.spacing_m != pytest.approx(0.180) for option in options.options)


def test_custom_spacing_rejects_insufficient_area_and_spacing_limits() -> None:
    options = generate_spacing_options(
        "Acero personalizado",
        required_area_cm2_m=4.0,
        spacing_grid=SpacingGrid(step_m=0.025, minimum_m=0.10, maximum_m=0.30),
    )

    with pytest.raises(ValueError, match="menor que As requerido"):
        custom_spacing_option(options, '3/8"', 0.300)
    with pytest.raises(ValueError, match="menor que 0.100"):
        custom_spacing_option(options, '1"', 0.090)
    with pytest.raises(ValueError, match="exceder 0.300"):
        custom_spacing_option(options, '1"', 0.310)


def test_crack_control_spacing_limit_uses_aashto_expression() -> None:
    maximum_spacing_m, beta_s = maximum_crack_control_spacing_m(
        steel_stress_kg_cm2=2520.0,
        dc_cm=5.95,
        slab_thickness_cm=20.0,
    )

    assert round(beta_s, 3) == 1.605
    assert round(maximum_spacing_m, 3) == 0.191


def test_crack_control_rejects_excessive_stress_even_if_spacing_passes() -> None:
    stress_status, spacing_status, status = crack_control_compliance_statuses(
        steel_stress_kg_cm2=3500.0,
        steel_stress_limit_kg_cm2=2520.0,
        provided_spacing_m=0.10,
        maximum_spacing_m=0.20,
    )

    assert stress_status == "NO CUMPLE"
    assert spacing_status == "CUMPLE"
    assert status == "NO CUMPLE"


def test_flexural_steel_area_rejects_unreachable_moment() -> None:
    with pytest.raises(ValueError, match="excede la capacidad"):
        flexural_steel_area_cm2(
            design_moment_tn_m=100.0,
            strip_width_cm=100.0,
            effective_depth_cm=15.0,
            concrete_strength_kg_cm2=280.0,
            steel_yield_kg_cm2=4200.0,
        )


def test_flexural_steel_area_rejects_algebraic_but_incompatible_solution() -> None:
    with pytest.raises(ValueError, match="capacidad compatible"):
        flexural_steel_area_cm2(
            design_moment_tn_m=40.0,
            strip_width_cm=100.0,
            effective_depth_cm=20.0,
            concrete_strength_kg_cm2=280.0,
            steel_yield_kg_cm2=4200.0,
            phi=0.90,
        )


def test_rectangular_response_does_not_assume_yield_for_deep_neutral_axis() -> None:
    response = rectangular_flexural_response(
        steel_area_cm2=84.152876,
        concrete_width_cm=100.0,
        effective_depth_cm=20.0,
        concrete_strength_kg_cm2=280.0,
        steel_yield_kg_cm2=4200.0,
    )

    assert response.steel_stress_kg_cm2 < 4200.0
    assert response.extreme_tensile_strain < 0.002
    assert response.resistance_factor == pytest.approx(0.75)


def test_mtc_phi_interpolates_from_compression_to_tension_control() -> None:
    assert mtc_flexural_resistance_factor(0.002) == pytest.approx(0.75)
    assert mtc_flexural_resistance_factor(0.0035) == pytest.approx(0.825)
    assert mtc_flexural_resistance_factor(0.005) == pytest.approx(0.90)


def test_transverse_slab_reinforcement_returns_requested_steel_groups() -> None:
    geometry = TransverseSlabGeometry(
        girder_spacing_m=2.10,
        overhang_m=0.825,
        girder_count=4,
        slab_thickness_m=0.20,
        girder_total_height_m=1.20,
        girder_width_m=0.30,
    )
    layout = TransverseLoadLayout(
        asphalt_start_m=1.075,
        asphalt_end_m=6.875,
        sidewalk_width_m=0.825,
        railing_left_m=0.13,
        barrier_left_m=0.825,
        barrier_width_m=0.25,
        vehicle_move_start_m=0.825,
        vehicle_move_end_m=7.125,
        vehicle_step_m=0.50,
    )
    analysis = solve_transverse_slab_design(
        geometry=geometry,
        materials=_materials(),
        live_loads=LiveLoads(
            pedestrian=PedestrianLoad.mtc_sidewalk_default(),
            vehicular=VehicleLoadModel.mtc_hl93_default(),
        ),
        layout=layout,
    )

    reinforcement = design_transverse_slab_reinforcement(
        geometry=geometry,
        materials=_materials(),
        analysis=analysis,
        parameters=SlabReinforcementParameters(),
    )

    assert reinforcement.negative.required_area_cm2_m > 0.0
    assert reinforcement.positive.required_area_cm2_m > 0.0
    assert round(reinforcement.temperature.required_area_cm2_m, 3) == 3.600
    assert round(reinforcement.distribution.percent_of_positive_steel, 1) == 67.0
    assert reinforcement.distribution.required_area_cm2_m == pytest.approx(
        0.67 * reinforcement.positive.required_area_cm2_m
    )

    crack_review = review_transverse_slab_crack_control(
        geometry=geometry,
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
    )

    assert crack_review.negative_main.label == "E.1 Acero principal negativo"
    assert crack_review.positive_main.label == "E.2 Acero principal positivo"
    assert crack_review.negative_main.maximum_spacing_m > 0.0
    assert crack_review.positive_main.maximum_spacing_m > 0.0
    assert crack_review.negative_main.status == (
        "CUMPLE"
        if (
            crack_review.negative_main.stress_status == "CUMPLE"
            and crack_review.negative_main.spacing_status == "CUMPLE"
        )
        else "NO CUMPLE"
    )
