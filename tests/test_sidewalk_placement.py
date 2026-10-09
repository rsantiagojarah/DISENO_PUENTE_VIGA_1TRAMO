"""Regression checks for sidewalks measured outward from traffic barriers."""

from dataclasses import replace

import pytest
import yaml

from bridge_design.cli.ascii_output import format_transverse_load_location_schemes
from bridge_design.cli.yaml_inputs import project_inputs_from_yaml, project_yaml_template
from bridge_design.domain import diaphragm, transverse_slab
from bridge_design.domain._cantilever_slab_loads import cantilever_load_effects
from bridge_design.domain.cantilever_slab import CantileverSlabParameters


def _project():
    data = project_yaml_template()
    data["ubicacion_cargas_modelo_transversal"].update(
        ancho_vereda_cada_lado_m=1.50,
        ubicacion_barrera_izquierda_m=1.65,
        ancho_barrera_m=0.375,
        ubicacion_baranda_izquierda_m=0.075,
        asfalto_inicio_m=2.03,
        asfalto_fin_m=5.92,
        recorrido_vehicular_inicio_m=2.03,
        recorrido_vehicular_fin_m=5.92,
    )
    return project_inputs_from_yaml(yaml.safe_load(yaml.safe_dump(data)))


def test_sidewalk_positions_and_loads_match_both_drawing_sides():
    project = _project()
    geometry = project.transverse_slab.geometry
    layout = project.transverse_slab.load_layout
    width = geometry.total_width_m
    expected = ((0.15, 1.65), (width - 1.65, width - 0.15))
    slab_dc = transverse_slab._dc_segments(geometry, project.materials, layout)[1:]
    slab_pl = transverse_slab._pl_segments(project.live_loads, layout, width)
    dia = diaphragm.diaphragm_geometry_from_transverse(
        geometry, thickness_m=0.25, height_m=1.10,
    )
    dia_dc = diaphragm._dc_segments(dia, project.materials, layout)[1:]
    dia_pl = diaphragm._pl_segments(dia, project.live_loads, layout)
    for segments in (slab_dc, slab_pl, dia_dc, dia_pl):
        for segment, interval in zip(segments, expected):
            assert (segment.start_m, segment.end_m) == pytest.approx(interval)
            assert segment.end_m - segment.start_m == pytest.approx(1.50)
    for slab, dia_segments in ((slab_dc, dia_dc), (slab_pl, dia_pl)):
        assert sum(s.q_tn_m * (s.end_m - s.start_m) for s in dia_segments) == pytest.approx(
            sum(s.q_tn_m * (s.end_m - s.start_m) for s in slab) * dia.load_tributary_length_m
        )
    # Symmetric pedestrian loading conserves the total applied load in reactions.
    solved = transverse_slab.solve_load_case(geometry, project.materials, "PL", slab_pl, ())
    reactions = [force for _, force in solved.support_reactions_tn]
    assert sum(reactions) == pytest.approx(3.0 * project.live_loads.pedestrian.load_tn_m2)
    assert reactions == pytest.approx(list(reversed(reactions)))


@pytest.mark.parametrize("root", [0.10, 0.825, 2.0])
def test_cantilever_uses_only_sidewalk_intersection_and_its_actual_lever_arm(root):
    project = _project()
    geometry = replace(project.transverse_slab.geometry, overhang_m=root)
    layout = project.transverse_slab.load_layout
    # Keep unrelated traffic inputs inside the deck even for the shortest overhang.
    layout = replace(layout, asphalt_end_m=4.0, vehicle_move_end_m=4.0)
    effects = cantilever_load_effects(
        geometry, project.materials, project.live_loads, layout, CantileverSlabParameters()
    )[0]
    by_label = {effect.label: effect for effect in effects}
    for label, q in (
        ("DC - vereda sobre volado", 2.4 * 0.20),
        ("PL - peatones sobre vereda", project.live_loads.pedestrian.load_tn_m2),
    ):
        if root <= 0.15:
            assert label not in by_label
        else:
            end = min(root, 1.65)
            length = end - 0.15
            effect = by_label[label]
            assert effect.load_tn == pytest.approx(q * length)
            assert effect.root_moment_tn_m == pytest.approx(-q * length * (root - (0.15 + end) / 2))


@pytest.mark.parametrize("tributary, expected", [(0.10, 0.0), (1.0, 0.85), (2.0, 1.50)])
def test_exterior_girder_clips_the_shifted_sidewalk_to_its_tributary_width(tributary, expected):
    exterior = _project().exterior_girder
    assert exterior.sidewalk_start_m == pytest.approx(0.15)
    exterior = replace(exterior, deck_overhang_m=0.0, girder_spacing_m=2.0 * tributary)
    assert exterior.sidewalk_tributary_width_m == pytest.approx(expected)


def test_sidewalk_rejects_off_deck_or_overlapping_sides():
    project = _project()
    layout = project.transverse_slab.load_layout
    with pytest.raises(ValueError, match="sale del tablero"):
        replace(layout, barrier_left_m=1.40)
    with pytest.raises(ValueError, match="no caben"):
        layout.sidewalk_intervals(3.90)


def test_yaml_anchors_sidewalk_to_barrier_without_extra_inputs():
    data = project_yaml_template()
    layout_data = data["ubicacion_cargas_modelo_transversal"]
    assert "ancho_pedestal_baranda_m" not in layout_data
    layout_data["ubicacion_barrera_izquierda_m"] += 0.15
    project = project_inputs_from_yaml(data)
    assert project.transverse_slab.load_layout.sidewalk_start_m == pytest.approx(0.15)
    assert project.exterior_girder.sidewalk_start_m == pytest.approx(0.15)


def test_project_keeps_exterior_girder_in_sync_when_layout_changes():
    project = _project()
    layout = replace(
        project.transverse_slab.load_layout,
        barrier_left_m=1.85, sidewalk_width_m=1.60,
    )
    updated = replace(project, transverse_slab=replace(project.transverse_slab, load_layout=layout))
    assert updated.exterior_girder.sidewalk_start_m == pytest.approx(0.25)
    assert updated.exterior_girder.sidewalk_width_m == pytest.approx(1.60)


def test_console_report_prints_the_shifted_intervals():
    project = _project()
    report = format_transverse_load_location_schemes(project)
    width = project.transverse_slab.geometry.total_width_m
    assert "0.150 a 1.650 m" in report
    assert f"{width - 1.65:.3f} a {width - 0.15:.3f} m" in report


def test_railing_load_position_is_independent_of_sidewalk():
    project = _project()
    geometry = project.transverse_slab.geometry
    layout = project.transverse_slab.load_layout
    moved = replace(layout, railing_left_m=0.12)
    assert moved.sidewalk_intervals(geometry.total_width_m) == layout.sidewalk_intervals(geometry.total_width_m)
    points = transverse_slab._dc_points(geometry, project.materials, moved)
    railing_points = [point for point in points if "baranda" in point.label]
    assert [point.position_m for point in railing_points] == pytest.approx(
        [0.12, geometry.total_width_m - 0.12]
    )


def test_console_uses_existing_inputs_without_pedestal_prompt(monkeypatch):
    from bridge_design.cli.input_prompts import collect_transverse_load_layout

    answers = iter(["1.50", "0.375", "1.65", "", "", "0.075", "", "", ""])
    prompts = []

    def answer(prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", answer)
    layout = collect_transverse_load_layout(_project().transverse_slab.geometry)
    assert layout.sidewalk_start_m == pytest.approx(0.15)
    assert layout.sidewalk_end_m == pytest.approx(1.65)
    assert layout.railing_left_m == pytest.approx(0.075)
    assert not any("pedestal" in prompt.lower() for prompt in prompts)
