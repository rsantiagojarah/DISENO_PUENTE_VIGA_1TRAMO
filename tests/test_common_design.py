"""Construction families retain independent demands and cover every member."""
from dataclasses import replace

import pytest

from bridge_design.domain.common_reinforcement import common_spacing, validate_girder_selection
from bridge_design.domain.rebar_catalog import SpacingGrid, generate_spacing_options
from bridge_design.reporting.common_design import make_girder_family
from bridge_design.reporting.deck_charts import family_strength_diagrams, strength_diagram_envelopes
from test_pipe_load import project


@pytest.fixture(scope='module', params=[0, 180])
def report(request):
    from bridge_design.main import run_bridge_design
    from unittest.mock import patch
    from contextlib import redirect_stdout
    from io import StringIO
    captured = []
    output = StringIO()
    with patch('builtins.input', return_value=''), patch(
            'bridge_design.reporting.generate_deck_docx_with_dialog', captured.append), redirect_stdout(output):
        run_bridge_design(project(q=request.param, x=.40))
    assert len(captured) == 1
    assert "COLISION CON ARMADO DE LOSA ADOPTADO - LADO IZQUIERDO" in output.getvalue()
    assert "COLISION CON ARMADO DE LOSA ADOPTADO - LADO DERECHO" in output.getvalue()
    assert "COLISION: VERIFICACION DEL ARMADO DE LOSA" in output.getvalue()
    return captured[0]


def test_single_selection_and_independent_results(report):
    assert [f.indices for f in report.girder_families] == [(1, 2, 3), (0, 4)]
    assert [m.side for m in report.cantilever_family.members] == ['izquierdo', 'derecho']
    for f in report.girder_families:
        for m in f.members:
            # Physical steel is common; requirements and capacities belong to
            # each member and must be refreshed after the user adopts it.
            for (_, local), (_, common) in zip(m.selected, f.selected):
                if hasattr(local, 'bar_count'):
                    assert (local.bar_label, local.bar_count, local.effective_depth_cm) == (
                        common.bar_label, common.bar_count, common.effective_depth_cm)
                    assert local.required_area_cm2 == m.reinforcement.main.required_area_cm2
                    assert common.required_area_cm2 >= local.required_area_cm2
                elif hasattr(local, 'legs'):
                    assert (local.bar_label, local.legs, local.spacing_m) == (
                        common.bar_label, common.legs, common.spacing_m)
                    assert local.required_av_cm2_m == m.shear.required_av_cm2_m
                    assert common.phi_vn_tn <= local.phi_vn_tn
                else:
                    assert (local.bar, local.spacing_m) == (common.bar, common.spacing_m)
            validate_girder_selection(f.selected, m.reinforcement, m.shear)
    for m in report.cantilever_groups:
        for (_, local), (_, common) in zip(m.selected, report.cantilever_family.selected):
            assert (local.bar, local.spacing_m) == (common.bar, common.spacing_m)
            assert common.required_area_cm2_m >= local.required_area_cm2_m
        assert m.result.flexural_steel.required_area_cm2_m == m.selected[0][1].required_area_cm2_m
    left, right = report.cantilever_groups
    delta = left.result.controlling_strength.design_moment_tn_m - right.result.controlling_strength.design_moment_tn_m
    pipe = report.project_inputs.transverse_slab.load_layout.pipe
    assert delta == pytest.approx(.162 if pipe else 0)


def test_common_cuts_and_stirrups_cover_all_members(report):
    for f in report.girder_families:
        detail = f.detail
        assert sum(c.bar_count for c in detail.longitudinal_cuts) == detail.selected_main_bar.bar_count
        for m in f.members:
            for station in m.detail.envelope:
                provided = sum(c.bar_count for c in detail.longitudinal_cuts
                               if c.detail_start_m-1e-3 <= station.x_m <= c.detail_end_m+1e-3)
                assert provided >= station.required_bar_count
            for common, individual in zip(detail.stirrup_zones, m.detail.stirrup_zones):
                assert common.spacing_m <= individual.spacing_m+1e-9
                assert common.provided_av_cm2_m >= individual.required_av_cm2_m-1e-9
                assert common.phi_vn_tn >= individual.maximum_vu_tn-1e-9
    family = report.cantilever_family
    for m in family.members:
        assert family.development.interior_anchor_length_m >= m.development.interior_anchor_length_m
        assert family.development.exterior_projection_length_m >= m.development.exterior_projection_length_m


def test_collision_detail_and_summary_use_the_selected_slab_on_both_sides(report):
    from docx import Document
    from bridge_design.reporting.deck_docx import _configure_document, _conclusions
    chosen = {label[:2]: option for label, option in report.slab_selected}
    for member in report.cantilever_groups:
        collision = member.result.interior_collision
        assert collision is not None
        for face in collision.faces:
            option = chosen["A." if face.face == "superior" else "B."]
            assert (face.option.bar, face.option.spacing_m, face.option.provided_area_cm2_m) == (
                option.bar, option.spacing_m, option.provided_area_cm2_m)
    document = Document()
    _configure_document(document)
    _conclusions(document, report)
    rows = [[cell.text for cell in row.cells] for table in document.tables for row in table.rows]
    local_rows = [row for row in rows if row[0].startswith("Losa interior") and "cara" in row[1]]
    assert len(local_rows) == 4
    for row, face in zip(local_rows, [face for member in report.cantilever_groups
                                    for face in member.result.interior_collision.faces]):
        assert "Armado de losa verificado por colision" in row[1]
        assert f'{face.option.bar.label} @ {face.option.spacing_m:.3f} m' in row[2]
        assert row[3] == face.status


def test_family_plots_envelope_complete_combinations(report):
    for family in report.girder_families:
        diagram = family_strength_diagrams(family.members)
        individual = [strength_diagram_envelopes(m.result, include_pl=m.result.pl is not None) for m in family.members]
        for name in ('moment_upper', 'moment_lower', 'shear_upper', 'shear_lower'):
            samples = [getattr(d, name) for d in individual]
            if samples[0] is None:
                assert getattr(diagram, name) is None
                continue
            select = min if name.endswith('lower') else max
            for x, value in getattr(diagram, name):
                assert value == pytest.approx(select(dict(s)[x] for s in samples))


def test_fatigue_and_service_governors_are_not_assumed_to_follow_moment(report):
    family = report.girder_families[1]
    first = family.members[0]
    weak = replace(first, indices=(999,), fatigue=replace(first.fatigue,
        factored_stress_range_kg_cm2=first.fatigue.allowable_stress_range_kg_cm2*1.2),
        service=replace(first.service, steel_tension_kg_cm2=first.service.steel_tension_limit_kg_cm2*1.1))
    synthetic = make_girder_family((first, weak), family.reinforcement, family.selected)
    checks = {row[0]: row for row in synthetic.checks}
    assert checks['Flexion'][1].startswith(first.label)
    assert checks['Fatiga'][1] == 'V1000'
    assert checks['Servicio: acero'][1] == 'V1000'
    assert synthetic.status == 'NO CUMPLE'
    context = synthetic.report_context(report)
    assert context.exterior_fatigue is weak.fatigue
    assert len(synthetic.service_members) == 2


def test_common_spacing_uses_area_and_spacing_limits_from_different_members():
    high_area = generate_spacing_options('Acero', 6, SpacingGrid(maximum_m=.30))
    tight_spacing = generate_spacing_options('Acero', 4, SpacingGrid(maximum_m=.15))
    result = common_spacing((high_area, tight_spacing))
    assert result.required_area_cm2_m == 6
    assert result.maximum_spacing_m == .15
    assert result.recommended.provided_area_cm2_m >= 6
    assert result.recommended.spacing_m <= .15


def test_right_pipe_selects_right_basis_even_when_minimum_steel_controls(monkeypatch):
    from bridge_design import main
    from bridge_design.cli.common_design import run_cantilever_family
    from unittest.mock import Mock
    p = project(q=180, x=11.84)
    monkeypatch.setattr('builtins.input', lambda prompt='': '')
    selection = Mock(wraps=main.collect_cantilever_reinforcement_selection)
    monkeypatch.setattr(main, 'collect_cantilever_reinforcement_selection', selection)
    barrier = main.design_concrete_barrier(p.barrier, p.materials)
    members, family, _ = run_cantilever_family(main, p, barrier)
    assert selection.call_count == 1
    assert family.basis.side == 'derecho'
    assert family.reinforcement.controlling_strength == members[1].result.controlling_strength
    assert [(o.bar, o.spacing_m) for _, o in members[0].selected] == [
        (o.bar, o.spacing_m) for _, o in members[1].selected]
    assert members[1].result.controlling_strength.design_moment_tn_m == pytest.approx(1.3449093136125)
