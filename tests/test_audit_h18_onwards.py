"""Independent equilibrium and regression checks for the remaining audit findings."""

from dataclasses import replace
from math import sqrt

import pytest

import bridge_design.domain.abutment as a
from bridge_design.domain.barrier import BarrierDesignInputs, BarrierGeometry, design_concrete_barrier
from bridge_design.domain.elastomeric_bearing import BearingMovements, TemperatureRange, DesignCheck
from bridge_design.domain.global_reactions import global_live_reaction_cases
from bridge_design.domain.loads import VehicleLoadModel
from bridge_design.domain.pep_strain_curves import compressive_strain_from_curve
from bridge_design.domain.simple_neoprene_support import SimpleSupportDemands


@pytest.mark.parametrize("delta,theta", [(0, 75), (10, 90)])
def test_h24_rejects_unresolved_force_geometry(delta, theta):
    with pytest.raises(ValueError, match="modelo de empujes"):
        a.AbutmentSoilInputs(wall_soil_friction_deg=delta, wall_backface_angle_deg=theta)


def test_h24_zero_acceleration_recovers_static_coefficient():
    data = a.AbutmentInputs(soil=a.AbutmentSoilInputs(pga=0))
    kae, _ = a.mononobe_okabe_active_coefficient(data)
    assert kae == pytest.approx(1 / 3)


def test_h25_triangular_key_pressure_moment_by_equilibrium():
    data = a.AbutmentInputs(key=a.AbutmentKeyInputs(enabled=True))
    key = replace(a._passive_key(data), top_pressure_tn_m2=0, bottom_pressure_tn_m2=12)
    height = data.key.height_m
    resultant = 12 * height / 2
    assert a._key_base_moment_tn_m(data, key) == pytest.approx(resultant * 2 * height / 3)


def test_h26_wall_triangle_centroid():
    data = a.pure_wall_inputs()
    g = data.geometry
    triangle = next(c for c in a._concrete_components(data) if c.name == "Ensanche de pantalla")
    assert triangle.arm_m == pytest.approx(g.toe_length_m + 2 * (g.lower_stem_thickness_m - g.upper_stem_thickness_m) / 3)


def test_h27_abutment_uses_piecewise_stem_geometry():
    data = a.AbutmentInputs()
    g = data.geometry
    transition = g.stem_height_above_footing_m - g.seat_block_height_m - g.backwall_drop_m - g.backwall_taper_height_m
    assert a._stem_thickness_at_height_m(data, 0) == pytest.approx(g.lower_stem_thickness_m)
    assert a._stem_thickness_at_height_m(data, transition) == pytest.approx(g.upper_stem_thickness_m)
    assert a._stem_thickness_at_height_m(data, g.stem_height_above_footing_m) == pytest.approx(g.seat_wall_width_m)


def test_h28_selva_expansion_governs():
    temperature = TemperatureRange.mtc_default("selva")
    simple = SimpleSupportDemands(20, 0, 0, 0, temperature=temperature)
    movements = BearingMovements(15, temperature)
    assert simple.thermal_delta_cm() == pytest.approx(0.5832)
    assert movements.service_shear_displacement_cm == pytest.approx(0.5832)
    # Opposite signs: shrinkage adds to contraction and subtracts from expansion.
    assert replace(movements, shrinkage_cm=0.4).service_shear_displacement_cm == pytest.approx(1.2 * (0.162 + 0.4))


def test_h29_separate_service_and_strength():
    demands = SimpleSupportDemands(20, 3, 2, 10)
    assert demands.r_service_tn == 35
    assert demands.r_strength_tn == pytest.approx(25 + 4.5 + 21)


def test_h33_anchor_requirement_is_not_verified_resistance():
    assert not DesignCheck("Anclaje", 20, 0, "Tn", "ANCLAR", "MTC").ok


def test_h32_origin_monotonicity_and_traceability():
    assert compressive_strain_from_curve(60, 5, 0).epsilon == 0
    values = [compressive_strain_from_curve(60, s, 40).epsilon for s in (3, 5, 6, 8, 11.25, 12)]
    assert values == sorted(values, reverse=True)
    lookup = compressive_strain_from_curve(50, 3, 50)
    assert lookup.extrapolated  # Above this column, even if below global max.
    assert not lookup.verified_source
    assert lookup.status.startswith("PENDIENTE")
    assert compressive_strain_from_curve(60, 5, 10).extrapolated


@pytest.mark.parametrize("sigma", [float("nan"), float("inf"), -1])
def test_h32_invalid_stress(sigma):
    with pytest.raises(ValueError):
        compressive_strain_from_curve(60, 5, sigma)


def test_h34_all_cases_balance_force_and_moment():
    span = 15.0
    cases = global_live_reaction_cases(span, 7.2, VehicleLoadModel.mtc_hl93_default())
    assert cases[0].total_load_tn == 0
    for row in cases:
        assert row.left_tn + row.right_tn == pytest.approx(row.total_load_tn)
        applied_moment = row.lane_load_tn_m * span**2 / 2 + sum(x * p for x, p in row.axles)
        assert row.right_tn * span == pytest.approx(applied_moment)
    peak = max(cases, key=lambda row: row.left_tn)
    assert peak.left_tn > peak.right_tn  # Not two simultaneous maxima.


def test_h22_capacity_uses_reported_dv():
    result = a.solve_abutment_design()
    for case in (result.stem_design, result.heel_design, result.toe_design):
        expected = result.inputs.reinforcement.shear_phi * 0.265 * case.shear_beta * sqrt(result.inputs.materials.concrete_strength_kg_cm2) * 100 * case.shear_effective_depth_cm / 1000
        assert case.shear_resistance_tn_m == pytest.approx(expected)


def test_h23_general_crack_spacing_bounds():
    for dv, expected in ((5, 12), (500, 80)):
        beta, strain, sx, sxe, mu = a._general_shear_beta(10, 2, 20, dv)
        assert sxe == expected


def test_h20_heel_same_case_equilibrium_on_pure_wall():
    result = a.solve_abutment_design(a.AbutmentInputs(is_pure_wall=True))
    g = result.inputs.geometry
    for state in result.with_bridge[:2] + result.extreme_seismic_with_bridge:
        f = state.load_factors
        width = g.heel_length_m
        gamma_soil = result.inputs.materials.soil_unit_weight_kg_m3 / 1000
        pressure = (f.dc * 2.4 * g.footing_thickness_m + f.ev * gamma_soil * g.stem_height_above_footing_m
                    + f.ls_vertical * result.pressures.live_surcharge_height_m * gamma_soil)
        reaction, reaction_moment = a._contact_pressure_resultant_over_interval(g, state, g.footing_width_m-width, g.footing_width_m, g.footing_width_m-width)
        moment, shear = a._heel_design_demands(result.inputs, state)
        assert moment + reaction_moment == pytest.approx(pressure * width**2 / 2)
        assert shear + reaction == pytest.approx(pressure * width)


def test_h19_rejects_mismatched_barrier_profile():
    with pytest.raises(ValueError, match="fuera de alcance"):
        BarrierDesignInputs(geometry=BarrierGeometry(height_m=1.2))


def test_h18_collision_uses_capacity_and_adds_axial_steel():
    from test_cantilever_slab import _materials, _geometry, _layout
    from bridge_design.domain.cantilever_slab import design_cantilever_slab
    from bridge_design.domain.loads import LiveLoads, PedestrianLoad
    from bridge_design.domain._cantilever_slab_calculations import design_flexural_steel
    materials = _materials()
    barrier = design_concrete_barrier(BarrierDesignInputs(), materials)
    result = design_cantilever_slab(_geometry(), materials,
                                   LiveLoads(PedestrianLoad.mtc_sidewalk_default(), VehicleLoadModel.mtc_hl93_default()),
                                   _layout(), barrier)
    collision = result.barrier_collision
    assert collision.transverse_force_tn >= barrier.yield_line.nominal_transverse_resistance_tn
    assert collision.collision_moment_tn_m >= barrier.flexure.mc_tn_m
    assert collision.axial_tension_tn_m == pytest.approx(collision.transverse_force_tn / collision.transfer_length_m)
    without_axial = design_flexural_steel(_geometry(), materials, result.parameters, result.controlling_strength,
                                        replace(collision, axial_tension_tn_m=0))
    assert result.flexural_steel.required_area_cm2_m > without_axial.required_area_cm2_m
    assert collision.status == "OK"
    assert {case.name for case in collision.cases} == {
        "Caso 1 - colision horizontal A-A", "Caso 2 - colision vertical",
        "Caso 3 - carga muerta + viva", "Caso 1 - seccion B-B", "Caso 1 - seccion C-C",
    }
    assert all(case.status == "OK" for case in collision.cases)
    assert all(check == "OK" for check in collision.connection_checks)
    assert result.overall_ok


def test_h30_thermal_movement_cannot_reduce_seismic_restraint():
    from test_elastomeric_bearing import _base_inputs
    from bridge_design.domain.elastomeric_bearing import design_elastomeric_bearing_method_a
    inputs = _base_inputs()
    first = design_elastomeric_bearing_method_a(inputs)
    second = design_elastomeric_bearing_method_a(replace(inputs, movements=replace(inputs.movements, shrinkage_cm=0.5)))
    assert first.anchor_force_required_tn >= first.seismic_governing_tn
    assert second.anchor_force_required_tn >= first.anchor_force_required_tn
    assert not first.overall_ok


def test_h29_concrete_uses_strength_reaction():
    from test_elastomeric_bearing import _base_inputs
    from bridge_design.domain.elastomeric_bearing import design_elastomeric_bearing_method_a
    inputs = _base_inputs()
    result = design_elastomeric_bearing_method_a(inputs)
    concrete = next(c for c in result.checks if c.name == "Aplastamiento concreto")
    assert concrete.demand == pytest.approx(inputs.loads.strength_i_tn * 1000)
    assert concrete.demand > inputs.loads.total_service_kg


def test_h21_reverse_moments_have_two_face_reinforcement():
    result = a.solve_abutment_design()
    states = result.with_bridge[:2] + result.without_bridge[:2] + result.extreme_seismic_with_bridge + result.extreme_seismic_without_bridge
    moments = [a._heel_design_demands(result.inputs, s)[0] for s in states]
    assert result.heel_design.signed_moment_envelope_tn_m_m == pytest.approx((min(moments), max(moments)))
    assert result.heel_design.controlling_moment_tn_m_m == pytest.approx(max(map(abs, moments)))
    details = [row for row in result.bar_details if row.element.startswith("Zapata -")]
    assert any(row.face == "Ambas caras talon" for row in details)
    assert any(row.face == "Ambas caras puntera" for row in details)
