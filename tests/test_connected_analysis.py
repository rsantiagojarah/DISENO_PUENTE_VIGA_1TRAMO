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
        replace(data, left=replace(data.left, geometry=replace(data.left.geometry, bearing_seat_length_m=2)))


def test_asymmetric_geometry_offsets_and_mesh_refinement_converge(data):
    from bridge_design.domain.connected_design import analyze_connected_abutments
    modified = replace(data, left_transition_m=0.7, right_transition_m=1.2, section_offsets=True,
                       right=replace(data.right, geometry=replace(data.right.geometry, retained_height_m=8.0)))
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
