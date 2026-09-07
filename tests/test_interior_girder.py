import pytest

from bridge_design.cli.ascii_output import _format_shear_section_limit
from bridge_design.reporting.deck_docx import _sectional_shear_calc_fields
from bridge_design.domain.interior_girder import (
    DiaphragmGeometry,
    InteriorGirderGeometry,
    _generate_shear_stirrup_options,
    _nominal_shear_upper_limit_tn,
    design_interior_girder_reinforcement,
    solve_interior_girder_design,
    t_beam_flexural_steel_area_cm2,
    review_interior_girder_crack_control,
    combine_interior_girder_moments,
    design_interior_girder_shear,
    review_interior_girder_fatigue,
    verify_interior_girder_service_stresses,
)
from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel
from bridge_design.domain.materials import (
    ConcreteProperties,
    LinearWeightProperties,
    MaterialProperties,
    SteelProperties,
    SurfaceLayerProperties,
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


def _geometry() -> InteriorGirderGeometry:
    return InteriorGirderGeometry(
        span_length_m=15.0,
        girder_spacing_m=2.10,
        slab_thickness_m=0.20,
        girder_total_height_m=1.20,
        web_width_m=0.30,
        girder_count=4,
        diaphragms=(
            DiaphragmGeometry(3.75, 0.25, 1.10, 2.10),
            DiaphragmGeometry(7.50, 0.25, 1.10, 2.10),
            DiaphragmGeometry(11.25, 0.25, 1.10, 2.10),
        ),
        moving_load_step_m=0.50,
        moment_sample_step_m=0.50,
    )


def _assert_samples_are_symmetric(
    samples: tuple[tuple[float, float], ...],
    span_length_m: float,
) -> None:
    by_position = {round(position, 10): value for position, value in samples}
    for position, value in samples:
        mirrored_position = round(span_length_m - position, 10)
        assert mirrored_position in by_position
        assert abs(value - by_position[mirrored_position]) <= 1e-9


def test_interior_girder_calculates_live_load_distribution_factor() -> None:
    assert round(_geometry().live_load_distribution_factor_g, 3) == 0.666


def test_t_beam_flexural_area_returns_positive_area() -> None:
    area, neutral_axis = t_beam_flexural_steel_area_cm2(
        design_moment_tn_m=120.0,
        flange_width_cm=210.0,
        flange_thickness_cm=20.0,
        web_width_cm=30.0,
        effective_depth_cm=133.7,
        concrete_strength_kg_cm2=280.0,
        steel_yield_kg_cm2=4200.0,
    )

    assert area > 0.0
    assert neutral_axis > 0.0


def test_interior_girder_solves_loads_combinations_and_reinforcement() -> None:
    analysis = solve_interior_girder_design(
        geometry=_geometry(),
        materials=_materials(),
        live_loads=LiveLoads(
            pedestrian=PedestrianLoad.mtc_sidewalk_default(),
            vehicular=VehicleLoadModel.mtc_hl93_default(),
        ),
    )

    assert analysis.dc.max_positive_moment_tn_m > 0.0
    assert analysis.dw.max_positive_moment_tn_m > 0.0
    assert analysis.truck_ll_im.max_positive_moment_tn_m > 0.0
    assert analysis.tandem_ll_im.max_positive_moment_tn_m > 0.0
    assert analysis.ll_im_envelope.max_positive_moment_tn_m >= analysis.truck_ll_im.max_positive_moment_tn_m
    assert analysis.truck_ll_im.support_reactions_tn[0][1] > 0.0
    assert analysis.fatigue_truck.max_positive_moment_tn_m > 0.0
    assert analysis.ll_im_envelope.max_shear_tn > 0.0
    assert analysis.ll_im_envelope.min_moment_samples_tn_m is not None
    assert analysis.ll_im_envelope.max_shear_samples_tn is not None
    assert analysis.ll_im_envelope.min_shear_samples_tn is not None
    assert max(value for _, value in analysis.ll_im_envelope.max_shear_samples_tn) > 0.0
    assert min(value for _, value in analysis.ll_im_envelope.min_shear_samples_tn) < 0.0
    assert round(analysis.fatigue_truck.distribution_factor_g, 3) == 0.420
    assert analysis.fatigue_truck.distribution_factor_g < analysis.distribution_factor_g
    reactions = dict(analysis.truck_ll_im.support_reactions_tn)
    assert round(reactions["Fijo"], 3) == 19.765
    assert round(reactions["Movil"], 3) == 22.702

    combined = combine_interior_girder_moments(analysis)
    strength = next(row for row in combined if row.combination_name == "RESISTENCIA I")
    assert strength.combined_moment_tn_m > analysis.dc.max_positive_moment_tn_m

    reinforcement = design_interior_girder_reinforcement(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
    )
    assert reinforcement.main.required_area_cm2 > 0.0
    assert reinforcement.main.placement_options.recommended is not None
    assert reinforcement.temperature.required_area_cm2_m_per_face > 0.0
    assert reinforcement.skin.required_area_cm2_m_per_face > 0.0

    crack_review = review_interior_girder_crack_control(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
    )
    assert crack_review.main.maximum_spacing_m > 0.0

    fatigue = review_interior_girder_fatigue(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
    )
    assert fatigue.stress_range_kg_cm2 > 0.0
    assert fatigue.allowable_stress_range_kg_cm2 > 0.0

    stresses = verify_interior_girder_service_stresses(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
    )
    assert stresses.concrete_compression_kg_cm2 > 0.0
    assert stresses.steel_tension_kg_cm2 > 0.0

    shear = design_interior_girder_shear(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
    )
    assert shear.controlling_shear.combined_shear_tn > 0.0
    assert shear.vc_tn > 0.0
    assert shear.required_av_cm2_m >= shear.minimum_av_cm2_m
    assert shear.recommended is not None
    section_limit = _format_shear_section_limit(shear)
    assert f"Vn,max={shear.nominal_shear_limit_tn:.3f} Tn" in section_limit
    assert f"phiVn,max={shear.phi * shear.nominal_shear_limit_tn:.3f} Tn" in section_limit
    assert "Estado=OK" in section_limit
    formula, _legend, substitution, result, comment = _sectional_shear_calc_fields(
        shear,
        shear.recommended,
    )
    assert "Vn,max = 0.25 f'c bv dv" in formula
    assert f"Vn,max = 0.25 f'c bv dv = {shear.nominal_shear_limit_tn:.3f} Tn" in substitution
    assert f"φVn,max = {shear.phi:.3f}·{shear.nominal_shear_limit_tn:.3f}" in substitution
    assert "CUMPLE" in result
    assert "φVn,max" in comment or "alma" in comment


def test_shear_options_reject_demand_above_nominal_section_limit() -> None:
    materials = _materials()
    nominal_limit = _nominal_shear_upper_limit_tn(
        concrete_strength_kg_cm2=280.0,
        web_width_cm=30.0,
        effective_shear_depth_cm=120.0,
    )
    options = _generate_shear_stirrup_options(
        required_av_cm2_m=46.17,
        max_spacing_m=0.30,
        legs=2,
        vu_tn=238.14,
        vc_tn=31.91,
        nominal_limit_tn=nominal_limit,
        materials=materials,
        effective_shear_depth_cm=120.0,
        phi=0.90,
    )

    assert nominal_limit == pytest.approx(252.0)
    assert 0.90 * nominal_limit == pytest.approx(226.8)
    assert any(option.provided_av_cm2_m >= 46.17 for option in options)
    assert all(option.phi_vn_tn < 238.14 for option in options)
    assert not any(option.is_compliant for option in options)
    assert not any(option.is_recommended for option in options)


def test_shear_options_accept_capacity_equal_to_demand() -> None:
    materials = _materials()
    nominal_limit = _nominal_shear_upper_limit_tn(
        concrete_strength_kg_cm2=280.0,
        web_width_cm=30.0,
        effective_shear_depth_cm=120.0,
    )
    options = _generate_shear_stirrup_options(
        required_av_cm2_m=46.17,
        max_spacing_m=0.30,
        legs=2,
        vu_tn=0.90 * nominal_limit,
        vc_tn=31.91,
        nominal_limit_tn=nominal_limit,
        materials=materials,
        effective_shear_depth_cm=120.0,
        phi=0.90,
    )

    assert any(option.is_compliant for option in options)
    assert sum(option.is_recommended for option in options) == 1


def test_interior_girder_live_load_envelope_is_symmetric_for_both_vehicle_directions() -> None:
    geometry = _geometry()
    analysis = solve_interior_girder_design(
        geometry=geometry,
        materials=_materials(),
        live_loads=LiveLoads(
            pedestrian=PedestrianLoad.mtc_sidewalk_default(),
            vehicular=VehicleLoadModel.mtc_hl93_default(),
        ),
    )

    _assert_samples_are_symmetric(
        analysis.ll_im_envelope.moment_samples_tn_m,
        geometry.span_length_m,
    )
    _assert_samples_are_symmetric(
        analysis.ll_im_envelope.shear_samples_tn,
        geometry.span_length_m,
    )
