"""The second command designs one footing without losing demands or loads."""

from dataclasses import fields, replace

import pytest

from bridge_design.cli.connected_2_yaml import connected_2_inputs_from_yaml, connected_2_yaml_template
from bridge_design.domain.connected_anchorage import geometric_anchorage
from bridge_design.domain.connected_distributions import distribution_demands
from bridge_design.domain.connected_geometry import build_connected_mesh
from bridge_design.domain.connected_inputs import ConnectedInputs
from bridge_design.domain.connected_loads import gravity_builders
from bridge_design.domain.connected_options import area_options
from bridge_design.domain.connected_reinforcement import SectionDemand, region_setup, temperature_for_region
from bridge_design.domain.rebar_catalog import reinforcing_bar_by_label


@pytest.fixture
def model():
    data = connected_2_inputs_from_yaml(connected_2_yaml_template(example=True))
    return data, build_connected_mesh(data)


def demand_at(mesh, x, moment, case="Resistencia Ia"):
    for i, element in enumerate(mesh.frame.elements[:mesh.foundation_count-1]):
        a, b = mesh.frame.nodes[element.start], mesh.frame.nodes[element.end]
        if a.x <= x <= b.x:
            return SectionDemand(case, "strength", 150, 2, 10, moment, i, (x-a.x)/(b.x-a.x))
    raise AssertionError(f"Missing foundation station {x}")


@pytest.mark.parametrize("offsets", [False, True])
def test_all_load_components_match_legacy_partition(model, offsets):
    data, _ = model
    data = replace(data, section_offsets=offsets)
    legacy = ConnectedInputs(**{f.name: getattr(data, f.name) for f in fields(ConnectedInputs)})
    old_mesh, new_mesh = build_connected_mesh(legacy), build_connected_mesh(data)
    assert old_mesh.frame.nodes == new_mesh.frame.nodes
    old, new = gravity_builders(legacy, old_mesh), gravity_builders(data, new_mesh)
    assert old.keys() == new.keys()
    for key in old:
        assert old[key].nodal == new[key].nodal
        assert old[key].distributed == new[key].distributed
        assert old[key].vector() == new[key].vector()
    assert any(abs(v) > 0 for v in new["EV0"].vector())
    assert any(abs(v) > 0 for v in new["EV1"].vector())
    assert any(e.region == "Losa central" for e in old_mesh.frame.elements)
    assert all(e.region != "Losa central" for e in new_mesh.frame.elements)


@pytest.mark.parametrize("sign,face", [(-1, "superior"), (1, "inferior")])
@pytest.mark.parametrize("under_wall_x", [1.575, 15.825])
def test_under_wall_peak_governs_combined_options(model, sign, face, under_wall_x):
    data, mesh = model
    # Low demands in the heels and interior must not hide a peak under a wall.
    records = tuple(demand_at(mesh, x, sign*(500 if x == under_wall_x else 50))
                    for x in (.45, 1.575, 8.7, 15.825, 16.95))
    distributions = distribution_demands(data, mesh, {"Zapata combinada": records})
    assert len(distributions) == 4
    label = f"Zapata combinada - longitudinal {face}"
    chosen = next(d for d in distributions if d.label == label)
    assert len(chosen.demands) == len(records)
    assert {d.element for d in chosen.demands} == {d.element for d in records}
    assert max(abs(d.moment) for d in chosen.demands) == 500
    assert all(d.axial == 2 and d.shear == 10 for d in chosen.demands)
    assert all(d.flexural_phi_limit == data.left.reinforcement.footing_design_phi_for_as
               for d in chosen.demands)
    other = next(d for d in distributions if d.role == "primary" and d.label != label)
    assert all(d.moment == d.shear == 0 for d in other.demands)
    full = area_options(data, label, chosen.demands)
    interior = area_options(data, label, (chosen.demands[2],))
    assert all(a.required_as_cm2_m > b.required_as_cm2_m for a, b in zip(full, interior))


def test_temperature_uses_full_panel_and_common_footing_cover(model):
    data, mesh = model
    side = replace(data.left, reinforcement=replace(data.left.reinforcement, footing_cover_cm=10))
    data = replace(data, left=side, right=side)
    demands = (demand_at(mesh, 8.7, 50),)
    label = "Zapata combinada - longitudinal inferior"
    inputs, cover, grid, _, _ = region_setup(data, label, demands)
    temperature = temperature_for_region(label, demands, inputs, grid, data.total_length_m)
    assert cover == 10
    assert temperature.b_cm == 150
    assert temperature.h_cm == pytest.approx(1740)


def test_combined_straight_space_reuses_continuous_path(model):
    data, mesh = model
    demands = (demand_at(mesh, 8.7, 100), demand_at(mesh, 1.575, 200, "Evento extremo I"))
    available, note = geometric_anchorage(data, mesh, "Zapata combinada", demands,
        data.left, 7.5, reinforcing_bar_by_label('1"'), .2)
    assert available == pytest.approx((1.575-.075)*100)
    assert "Zapata combinada" in note
    assert "x critica=1.5750" in note
    assert "Losa central" not in note
