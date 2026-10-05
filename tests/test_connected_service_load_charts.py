from dataclasses import replace

import pytest

from bridge_design.domain.connected_cases import connected_load_cases
from bridge_design.domain.connected_earth import earth_builder
from bridge_design.domain.connected_geometry import build_connected_mesh
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil, PairedBridgeCase
from bridge_design.domain.connected_loads import gravity_builders
from bridge_design.reporting.connected_service_load_charts import action_panels, global_density


def test_base_panels_keep_exact_unweighted_loads_and_nonuniform_profiles():
    data = ConnectedInputs(FoundationSoil(3000, 0.5, 26.7), include_without_bridge=False)
    mesh = build_connected_mesh(data)
    result = type("ChartInput", (), {"inputs": data, "mesh": mesh})()
    panels = action_panels(result)
    gravity = gravity_builders(data, mesh)
    actual = panels[0][1].vector()
    expected = [sum(v) for v in zip(*(gravity[k].vector() for k in ("DC0", "DC1", "DCs")))]
    assert actual == pytest.approx(expected)
    earth = panels[2][1]
    expected = [sum(v) for v in zip(*(earth_builder(data, mesh, i, "EH").vector() for i in (0, 1)))]
    assert earth.vector() == pytest.approx(expected)
    base_index, top_index = mesh.side_elements[0][0], mesh.side_elements[0][-1]
    assert abs(global_density(mesh.frame, base_index, earth.distributed[base_index], 0)[0]) > 0
    assert global_density(mesh.frame, top_index, earth.distributed[top_index], 1)[0] == pytest.approx(0, abs=1e-7)
    # The report must not accidentally use the first resistance combination.
    first_combination = next(connected_load_cases(data, mesh))
    assert earth.nodal != list(first_combination.nodal)


def test_zero_and_asymmetric_surcharge_occupancy_is_preserved():
    data = ConnectedInputs(FoundationSoil(3000, 0.5, 26.7), include_without_bridge=False)
    pair = PairedBridgeCase("Ocupacion derecha", data.left.loads, data.right.loads, 0, 0.4)
    data = replace(data, cases=(pair,))
    mesh = build_connected_mesh(data)
    result = type("ChartInput", (), {"inputs": data, "mesh": mesh})()
    panels = action_panels(result)
    assert panels[3][1].vector() == pytest.approx([0.4*v for v in earth_builder(data, mesh, 1, "LS").vector()])
    for index in mesh.side_elements[0]:
        assert global_density(mesh.frame, index, panels[3][1].distributed[index], 0.5) == pytest.approx((0, 0, 0))
