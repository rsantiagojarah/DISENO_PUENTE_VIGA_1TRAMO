from dataclasses import replace

import pytest

from bridge_design.cli.connected_yaml import connected_inputs_from_yaml, connected_yaml_template
from bridge_design.domain.connected_design import analyze_connected_abutments
from bridge_design.domain.connected_geometry import build_connected_mesh, side_axis
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil


@pytest.mark.parametrize("count", [4, 5, 10, 41, 80])
def test_exact_spring_count_uniform_intervals_and_mandatory_positions(count):
    data = ConnectedInputs(FoundationSoil(3000, .5, 26.7), foundation_node_count=count)
    mesh = build_connected_mesh(data)
    positions = [mesh.frame.nodes[spring.node].x for spring in mesh.frame.springs]
    assert len(positions) == count
    assert positions == sorted(set(positions))
    anchors = [0, side_axis(data, 0), side_axis(data, 1), data.total_length_m]
    for anchor in anchors:
        assert any(abs(position - anchor) < 1e-8 for position in positions)
    for first, last in zip(anchors, anchors[1:]):
        points = [position for position in positions if first - 1e-8 <= position <= last + 1e-8]
        gaps = [b - a for a, b in zip(points, points[1:])]
        assert max(gaps) == pytest.approx(min(gaps), abs=1e-8)
    assert positions == pytest.approx([data.total_length_m - x for x in reversed(positions)], abs=1e-8)
    springs = mesh.frame.springs
    assert sum(spring.tributary_area for spring in springs) == pytest.approx(data.total_length_m)
    assert sum(spring.stiffness for spring in springs) == pytest.approx(3000 * data.total_length_m)
    for index, spring in enumerate(springs):
        left = (positions[index] - positions[index - 1]) / 2 if index else 0
        right = (positions[index + 1] - positions[index]) / 2 if index + 1 < count else 0
        assert spring.tributary_area == pytest.approx(left + right)


def test_geometry_and_reference_nodes_do_not_add_springs():
    raw = connected_yaml_template(example=True)
    raw["cimentacion"]["cantidad_nudos_cimentacion"] = 12
    raw["cimentacion"]["nodo_referencia_x_m"] = 8.123
    raw["estribo"]["geometria"]["ancho_zapata_m"] = 5.4
    data = connected_inputs_from_yaml(raw)
    mesh = build_connected_mesh(data)
    assert len(mesh.frame.springs) == 12
    assert mesh.foundation_count > 12
    assert mesh.frame.nodes[mesh.reference_node].x == pytest.approx(8.123)
    for nodes in mesh.side_nodes:
        assert any(spring.node == nodes[0] for spring in mesh.frame.springs)
    for side_index, side in enumerate((data.left, data.right)):
        tip = 0 if side_index == 0 else data.total_length_m
        assert any(mesh.frame.nodes[spring.node].x == pytest.approx(tip) for spring in mesh.frame.springs)


@pytest.mark.parametrize("value", [None, True, 3, 4.5, "41"])
def test_yaml_rejects_invalid_node_counts(value):
    raw = connected_yaml_template(example=True)
    raw["cimentacion"]["cantidad_nudos_cimentacion"] = value
    with pytest.raises(ValueError, match="cantidad_nudos_cimentacion"):
        connected_inputs_from_yaml(raw)


def test_legacy_spacing_is_supported_and_count_takes_precedence():
    raw = connected_yaml_template(example=True)
    del raw["cimentacion"]["cantidad_nudos_cimentacion"]
    raw["cimentacion"]["paso_malla_m"] = 1
    legacy = connected_inputs_from_yaml(raw)
    assert legacy.foundation_node_count is None
    assert legacy.mesh_size_m == 1
    raw["cimentacion"]["cantidad_nudos_cimentacion"] = 25
    raw["cimentacion"]["paso_malla_m"] = None
    assert len(build_connected_mesh(connected_inputs_from_yaml(raw)).frame.springs) == 25


def test_new_spring_layout_preserves_symmetric_response_and_global_equilibrium():
    data = connected_inputs_from_yaml(connected_yaml_template(example=True))
    data = replace(data, include_without_bridge=False,
                   left=replace(data.left, loads=replace(data.left.loads, braking_tn_m=0)),
                   right=replace(data.right, loads=replace(data.right.loads, braking_tn_m=0)))
    result = analyze_connected_abutments(data)
    assert len(result.mesh.frame.springs) == 41
    service = next(row for row in result.results if row.limit_state == "service")
    assert service.spring_reactions == pytest.approx(tuple(reversed(service.spring_reactions)), abs=1e-6)
    for row in result.results:
        force_scale = max(1, sum(abs(value) for value in row.spring_reactions))
        normalized = max(abs(row.equilibrium_error[0]), abs(row.equilibrium_error[1]),
                         abs(row.equilibrium_error[2]) / data.total_length_m)
        assert normalized < 1e-7 * force_scale
        assert min(row.spring_reactions) >= -1e-6
