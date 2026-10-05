from dataclasses import replace

import pytest

from bridge_design.domain.abutment import _concrete_components, _soil_components
from bridge_design.domain.connected_cases import connected_load_cases
from bridge_design.domain.connected_earth import earth_builder
from bridge_design.domain.connected_geometry import build_connected_mesh
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil
from bridge_design.domain.connected_loads import gravity_builders
from bridge_design.domain.frame_solver import FrameSolver, global_resultant


@pytest.fixture
def data():
    return ConnectedInputs(FoundationSoil(3000, 0.50, 26.7), mesh_size_m=1.0, include_without_bridge=False)


def test_geometry_springs_centre_and_rigid_connections(data):
    mesh = build_connected_mesh(data)
    assert mesh.frame.nodes[mesh.reference_node].x == pytest.approx(data.total_length_m / 2)
    assert mesh.frame.fixed_dofs == (3 * mesh.reference_node,)
    assert sum(spring.stiffness for spring in mesh.frame.springs) == pytest.approx(3000 * data.total_length_m)
    assert mesh.side_nodes[0][0] < mesh.foundation_count
    assert mesh.side_nodes[1][0] < mesh.foundation_count
    assert min(element.depth for element in mesh.frame.elements if element.region == "Losa central") == 0.75


def test_global_combinations_with_and_without_bridge_have_expected_sequence(data):
    inputs = replace(data, include_without_bridge=True)
    cases = list(connected_load_cases(inputs, build_connected_mesh(inputs)))
    assert len(cases) == 17
    assert cases[0].name == "Par simultaneo ingresado / Resistencia Ia BR-1"
    assert cases[1].name == "Par simultaneo ingresado / Resistencia Ia BR+1"
    assert cases[2].name == "Par simultaneo ingresado / Resistencia Ib BR-1"
    assert cases[3].name == "Par simultaneo ingresado / Resistencia Ib BR+1"
    assert cases[4].name == "Par simultaneo ingresado / Servicio I BR-1"
    assert cases[5].name == "Par simultaneo ingresado / Servicio I BR+1"
    assert cases[10].name == "Sin tablero / Resistencia Ia"
    assert cases[11].name == "Sin tablero / Resistencia Ib"
    assert cases[12].name == "Sin tablero / Servicio I"
    assert cases[13].name == "Sin tablero / Evento Extremo I A EQ-1"
    assert cases[16].name == "Sin tablero / Evento Extremo I B EQ+1"
    for case in cases[10:]:
        assert " BR" not in case.name
        braking = [row for row in case.load_trace if row[0].endswith(" / BR")]
        assert len(braking) == 2
        assert all(row[2:] == (0.0, 0.0, 0.0) for row in braking)


def test_strength_factor_sets_are_global_not_crossed_by_region(data):
    from itertools import product
    from bridge_design.domain.abutment import abutment_load_factors

    cases = list(connected_load_cases(data, build_connected_mesh(data)))
    factors = abutment_load_factors(data.left.gamma_eq)
    assert len({case.name for case in cases}) == len(cases)
    strength = [case for case in cases if case.limit_state == "strength"]
    assert len(strength) == 4
    for case, (factor, direction) in zip(strength, product(factors[:2], (-1, 1))):
        assert "Mixta" not in case.name
        assert factor.name in case.name
        assert case.name.endswith(f"BR{direction:+d}")
        trace = {row[0]: row[1] for row in case.load_trace}
        assert trace["Izquierda / DC"] == trace["Derecha / DC"] == trace["Losa y transiciones / DC"] == factor.dc
        for side in ("Izquierda", "Derecha"):
            assert trace[f"{side} / BDC"] == factor.dc
            assert trace[f"{side} / EV"] == factor.ev
            assert trace[f"{side} / LL"] == factor.ll
            assert trace[f"{side} / BR"] == direction * factor.br


def test_service_and_earthquake_are_simultaneous_global_cases(data):
    cases = list(connected_load_cases(data, build_connected_mesh(data)))
    assert len([case for case in cases if case.limit_state == "service"]) == 2
    extreme = [case for case in cases if case.limit_state == "extreme"]
    assert len(extreme) == 4
    for case in cases:
        trace = {row[0]: row[1] for row in case.load_trace}
        assert trace["Izquierda / DC"] == trace["Derecha / DC"] == trace["Losa y transiciones / DC"]
        if case.limit_state == "extreme":
            direction = -1 if case.name.endswith("EQ-1") else 1
            inertia = 0.5 if "Evento Extremo I A" in case.name else 1.0
            assert trace["Izquierda / PIR"] == trace["Derecha / PIR"] == trace["Losa y transiciones / PIR"] == direction * inertia
            assert any(row[0].startswith("Izquierda / Empuje") and row[2] > 0 for row in case.load_trace)
            assert any(row[0].startswith("Derecha / Empuje") and row[2] < 0 for row in case.load_trace)


def test_global_factors_preserve_asymmetric_simultaneous_bridge_reactions(data):
    from bridge_design.domain.connected_inputs import PairedBridgeCase

    paired = PairedBridgeCase("Asimetrico", replace(data.left.loads, pdc_tn_m=10),
                             replace(data.right.loads, pdc_tn_m=20))
    inputs = replace(data, cases=(paired,))
    cases = list(connected_load_cases(inputs, build_connected_mesh(inputs)))
    assert len(cases) == 10
    for case in cases:
        trace = {row[0]: row for row in case.load_trace}
        assert trace["Izquierda / BDC"][1] == trace["Derecha / BDC"][1]
        assert trace["Izquierda / BDC"][3] == -10
        assert trace["Derecha / BDC"][3] == -20


@pytest.mark.parametrize("left_braking,right_braking", [(0, 0), (1.33, 0), (0, 1.33)])
def test_braking_labels_follow_actual_loads_on_either_side(data, left_braking, right_braking):
    inputs = replace(data, left=replace(data.left, loads=replace(data.left.loads, braking_tn_m=left_braking)),
                     right=replace(data.right, loads=replace(data.right.loads, braking_tn_m=right_braking)))
    cases = list(connected_load_cases(inputs, build_connected_mesh(inputs)))
    service = [case for case in cases if case.limit_state == "service"]
    if left_braking or right_braking:
        assert len(cases) == 10
        assert [case.name.rsplit(" / ", 1)[1] for case in service] == ["Servicio I BR-1", "Servicio I BR+1"]
    else:
        assert len(cases) == 7
        assert service[0].name == "Par simultaneo ingresado / Servicio I"
        assert all(" BR" not in case.name for case in cases)


def test_gravity_reuses_existing_weights_and_centroids(data):
    mesh = build_connected_mesh(data)
    builders = gravity_builders(data, mesh)
    for index, side in enumerate((data.left, data.right)):
        for name, components in (("DC", _concrete_components(side)), ("EV", _soil_components(side))):
            resultant = global_resultant(mesh.frame, builders[name + str(index)].vector())
            assert -resultant[1] == pytest.approx(sum(row.value_tn_m for row in components), rel=1e-7)
            expected = sum(row.value_tn_m * ((side.geometry.footing_width_m - row.arm_m) if index == 0
                           else (data.total_length_m - side.geometry.footing_width_m + row.arm_m)) for row in components)
            assert -resultant[2] == pytest.approx(expected, rel=1e-7)


def test_wall_friction_transfer_preserves_global_earth_resultant(data):
    rough = replace(data, left=replace(data.left, soil=replace(data.left.soil, wall_soil_friction_deg=15)))
    for inputs in (data, rough):
        mesh = build_connected_mesh(inputs)
        builder = earth_builder(inputs, mesh, 0, "EH")
        force = global_resultant(mesh.frame, builder.vector())
        assert force[0] == pytest.approx(0.5 / 3 * 1.925 * inputs.left.geometry.retained_height_m**2)
        assert force[1] == pytest.approx(0, abs=1e-8)


def test_symmetric_pressure_case_has_zero_horizontal_reaction_and_axial_force(data):
    quiet = replace(data, left=replace(data.left, loads=replace(data.left.loads, braking_tn_m=0)),
                    right=replace(data.right, loads=replace(data.right.loads, braking_tn_m=0)))
    mesh = build_connected_mesh(quiet)
    case = next(case for case in connected_load_cases(quiet, mesh) if case.limit_state == "service")
    result = FrameSolver(mesh.frame).solve(case)
    assert result.reactions[3 * mesh.reference_node] == pytest.approx(0, abs=1e-7)
    assert result.spring_reactions == pytest.approx(tuple(reversed(result.spring_reactions)), abs=1e-6)
    axial = [row.axial for row in result.sections if mesh.frame.elements[row.element].region == "Losa central"]
    assert min(axial) < -1.0
    assert result.equilibrium_error == pytest.approx((0, 0, 0), abs=1e-6)


def test_global_braking_and_seismic_directions_do_not_cancel(data):
    mesh = build_connected_mesh(data)
    solver = FrameSolver(mesh.frame)
    cases = list(connected_load_cases(data, mesh))
    service = [solver.solve(case) for case in cases if case.limit_state == "service"]
    total_braking = data.left.loads.braking_tn_m + data.right.loads.braking_tn_m
    assert sorted(result.reactions[3 * mesh.reference_node] for result in service) == pytest.approx([-total_braking, total_braking])
    seismic = [solver.solve(case) for case in cases if case.limit_state == "extreme"]
    assert all(abs(result.reactions[3 * mesh.reference_node]) > 1 for result in seismic)
    assert all(min(result.spring_reactions) >= -1e-6 for result in seismic)


def test_invalid_geometry_and_missing_geotechnical_data_are_rejected(data):
    with pytest.raises(ValueError, match="positivo"):
        FoundationSoil(0, 0.5, 26.7)
    with pytest.raises(ValueError, match="losa central"):
        replace(data, clear_span_m=2)
    with pytest.raises(ValueError, match="cajuela"):
        side = replace(data.left, geometry=replace(data.left.geometry, bearing_seat_length_m=2))
        replace(data, left=side, right=side)


def test_asymmetric_transitions_offsets_and_mesh_refinement_converge(data):
    from bridge_design.domain.connected_design import analyze_connected_abutments
    modified = replace(data, left_transition_m=0.7, right_transition_m=1.2, section_offsets=True)
    coarse = analyze_connected_abutments(modified)
    fine = analyze_connected_abutments(replace(modified, mesh_size_m=0.5))
    for coarse_check, fine_check in zip(coarse.foundation_checks, fine.foundation_checks):
        assert coarse_check.horizontal_reaction == pytest.approx(fine_check.horizontal_reaction, abs=1e-5)
        assert coarse_check.maximum_pressure == pytest.approx(fine_check.maximum_pressure, rel=0.12)
    assert all(result.equilibrium_error == pytest.approx((0, 0, 0), abs=1e-5) for result in fine.results)


def test_relocating_reference_keeps_global_horizontal_balance(data):
    from bridge_design.domain.connected_design import analyze_connected_abutments
    first = analyze_connected_abutments(data)
    shifted = analyze_connected_abutments(replace(data, reference_x_m=data.total_length_m * 0.4))
    for original, other in zip(first.foundation_checks, shifted.foundation_checks):
        assert original.horizontal_reaction == pytest.approx(other.horizontal_reaction, abs=1e-5)


def test_signed_mononobe_okabe_preserves_original_and_opposite_direction(data):
    from bridge_design.domain.abutment import mononobe_okabe_active_coefficient, coulomb_active_coefficient
    positive, positive_angle = mononobe_okabe_active_coefficient(data.left)
    negative, negative_angle = mononobe_okabe_active_coefficient(data.left, horizontal_direction=-1)
    static = coulomb_active_coefficient(30, 0, 0, 90)
    assert positive > static > negative > 0
    assert positive_angle == -negative_angle
