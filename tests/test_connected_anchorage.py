from dataclasses import replace

import pytest

from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil
from bridge_design.domain.connected_geometry import build_connected_mesh
from bridge_design.domain.connected_reinforcement import SectionDemand
from bridge_design.domain.connected_anchorage import straight_space, _clip_segment, geometric_anchorage
from bridge_design.domain.abutment import _available_development_length_cm
from bridge_design.domain.rebar_catalog import reinforcing_bar_by_label


@pytest.fixture
def model():
    data = ConnectedInputs(FoundationSoil(3000, 0, 26.7), foundation_node_count=41)
    return data, build_connected_mesh(data)


def demand_at_x(mesh, x, moment, depth=150):
    for i, element in enumerate(mesh.frame.elements):
        a, b = mesh.frame.nodes[element.start], mesh.frame.nodes[element.end]
        if a.y == b.y == 0 and a.x <= x <= b.x:
            return SectionDemand("Resistencia Ia", "strength", depth, 0, 1, moment,
                                 i, (x-a.x)/(b.x-a.x))
    raise AssertionError("Station not found")


def test_bottom_bar_stops_at_depth_change_but_top_bar_can_continue(model):
    data, mesh = model
    positive = demand_at_x(mesh, 4, 20)
    bottom, note = straight_space(data, mesh, "Zapata izquierda", positive, 7.5, 2.54)
    top, _ = straight_space(data, mesh, "Zapata izquierda", replace(positive, moment=-20), 7.5, 2.54)
    assert bottom == pytest.approx(100, abs=1e-5)
    assert top == pytest.approx(392.5, abs=1e-5)
    assert "x critica=4.0000" in note


def test_vertical_stem_bar_has_straight_embedment_into_footing(model):
    data, mesh = model
    element = mesh.side_elements[0][0]
    demand = SectionDemand("Resistencia Ia", "strength", 100, 0, 1, 30, element, 0)
    available, note = straight_space(data, mesh, "Pantalla izquierda", demand, 7.5, 2.54)
    assert available == pytest.approx(142.5, abs=1e-5)
    assert "y critica=0.0000" in note


def test_bar_at_outer_end_has_no_development_space_on_outer_side(model):
    data, mesh = model
    demand = demand_at_x(mesh, 0, -10)
    available, _ = straight_space(data, mesh, "Zapata izquierda", demand, 7.5, 1.27)
    assert available == 0


def test_linear_clearance_clipping_solves_exact_intersection():
    assert _clip_segment(0, 2, (-1, 4), (3, 2)) == pytest.approx((.5, 2))
    assert _clip_segment(0, 2, (-1,), (-2,)) is None


@pytest.mark.parametrize("region", ("Pantalla izquierda", "Pantalla derecha", "Zapata izquierda", "Zapata derecha"))
def test_continuous_detail_lengths_for_shared_regions(model, region):
    data, mesh = model
    side = data.left if region.endswith("izquierda") else data.right
    available, note = geometric_anchorage(data, mesh, region, (), side, 7.5,
                                          reinforcing_bar_by_label('3/4"'), .15)
    if region.startswith("Pantalla"):
        expected = _available_development_length_cm(side, "Pantalla")
    else:
        expected = min(side.geometry.toe_length_m+side.geometry.lower_stem_thickness_m,
                       side.geometry.heel_length_m+side.geometry.lower_stem_thickness_m)*100-7.5
    assert available == expected
    assert "Detalle continuo definido" in note


@pytest.mark.parametrize("part,expected", (("talon", 342.5), ("puntera", 242.5)))
def test_footing_bars_develop_through_stem_to_opposite_edge(model, part, expected):
    data, mesh = model
    available, note = geometric_anchorage(data, mesh, "Zapata", (), data.left, 7.5,
                                          reinforcing_bar_by_label('3/4"'), .15, part=part)
    assert available == pytest.approx(expected)
    assert "cruza la pantalla" in note


@pytest.mark.parametrize("face", ("superior", "inferior"))
def test_slab_develops_across_footing_width_independent_of_taper(model, face):
    data, mesh = model
    available, note = geometric_anchorage(data, mesh, "Losa central - longitudinal "+face,
        (), data.left, 7.5, reinforcing_bar_by_label('3/4"'), .15)
    assert available == pytest.approx(492.5)
    assert "dentro de las zapatas" in note


@pytest.mark.parametrize("face", ("relleno", "exterior"))
def test_parapet_bars_use_full_abutment_height_for_both_faces(model, face):
    data, mesh = model
    available, note = geometric_anchorage(data, mesh, "Parapeto - vertical "+face,
        (), data.left, 7.5, reinforcing_bar_by_label('8 mm'), .20)
    assert available == pytest.approx(1062.5)
    assert "desde fondo de zapata" in note
