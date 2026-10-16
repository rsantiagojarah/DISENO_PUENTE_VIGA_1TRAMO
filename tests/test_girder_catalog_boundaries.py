"""Impossible bar layouts must not prevent selection or controlled input revision."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge_design import main
from bridge_design.cli.ascii_output import _format_main_placement_table
from bridge_design.cli.common_design import prepare_girder
from bridge_design.cli.yaml_inputs import project_inputs_from_yaml
from bridge_design.cli.yaml_io import load_yaml_file
from bridge_design.domain import interior_girder as ig, exterior_girder as eg


FIXTURE = Path(__file__).parent / "fixtures/soldeoro_20261005.yaml"


@pytest.fixture(scope="module")
def project():
    return project_inputs_from_yaml(load_yaml_file(FIXTURE))


@pytest.fixture(scope="module")
def narrow_geometry(project):
    return replace(project.interior_girder, span_length_m=6.1, girder_spacing_m=2.1,
        girder_total_height_m=.5, web_width_m=.25, diaphragms=(),
        asphalt_tributary_width_m=None, live_load_distribution_factor_g=None,
        live_load_shear_distribution_factor_g=None)


def test_narrow_girder_keeps_valid_layout_and_omits_impossible_one(project, narrow_geometry):
    geometry = narrow_geometry
    analysis = ig.solve_interior_girder_design(geometry, project.materials, project.live_loads)
    reinforcement = ig.design_interior_girder_reinforcement(geometry, project.materials, analysis)
    case = reinforcement.main.placement_options
    assert not any(o.bar_label == '1"' and o.bar_count == 23 for o in case.options)
    option = ig.custom_main_bar_placement_option(case, '3/4"', 10)
    assert option.is_compliant and option.layers == 4
    assert reinforcement.main.design_moment_tn_m == pytest.approx(58.564831454511065)
    response = ig.t_beam_flexural_response(option.provided_area_cm2, 210, 20, 25,
                                         option.effective_depth_cm, 280, 4200)
    capacity = min(.9, response.resistance_factor) * response.nominal_moment_tn_m
    assert capacity == pytest.approx(59.04115526117647)
    assert case.recommended is not None and case.recommended.is_compliant
    params = reinforcement.parameters
    for candidate in case.options:
        pitch = candidate.bar_diameter_cm + max(params.minimum_clear_bar_spacing_cm,
                                                candidate.clear_spacing_cm)
        occupied = 2*params.concrete_cover_cm + candidate.bar_diameter_cm + (candidate.layers-1)*pitch
        assert occupied <= geometry.total_t_section_depth_m*100 + 1e-9
        assert candidate.effective_depth_cm > 0


def test_skipped_layouts_do_not_renumber_retained_items(narrow_geometry):
    params = ig.InteriorGirderReinforcementParameters()
    small = ig.generate_main_bar_placement_options("Test", 30, narrow_geometry, params)
    tall = ig.generate_main_bar_placement_options("Test", 30,
        replace(narrow_geometry, girder_total_height_m=2), params)
    original = {(o.bar_label, o.bar_count): o.item for o in tall.options}
    assert len(small.options) < len(tall.options)
    assert all(o.item == original[o.bar_label, o.bar_count] for o in small.options)


@pytest.mark.parametrize("width,height", ((.12, .5), (.25, .01)))
def test_empty_physical_catalog_is_reported_without_index_error(narrow_geometry, width, height):
    geometry = replace(narrow_geometry, web_width_m=width, girder_total_height_m=height,
                       slab_thickness_m=.10)
    params = ig.InteriorGirderReinforcementParameters()
    case = ig.generate_main_bar_placement_options("Sin espacio", 30, geometry, params)
    assert case.recommended is None
    # Very shallow sections may retain only undersized layouts, but never a false REC.
    assert all(not o.is_compliant for o in case.options)
    assert "No hay disposicion admisible" in "\n".join(_format_main_placement_table(case))
    with pytest.raises(ig.NoAdmissibleMainReinforcementError, match="No hay disposicion admisible"):
        ig.require_admissible_main_placement(case)


def test_empty_exterior_catalog_does_not_try_max_of_empty_sequence(project):
    geometry = replace(project.exterior_girder, web_width_m=.12)
    params = ig.InteriorGirderReinforcementParameters()
    returned_params, case = eg._main_placement_options_with_required_layers(
        "Exterior", 30, geometry, params, moment_tn_m=60, materials=project.materials)
    assert returned_params == params
    assert case.options == () and case.recommended is None


def test_prepare_girder_requests_revision_when_no_layout_resists(project, narrow_geometry):
    geometry = replace(narrow_geometry, span_length_m=7, girder_spacing_m=2.56,
        live_load_distribution_factor_g=None, live_load_shear_distribution_factor_g=None)
    context = SimpleNamespace(interior_girder=geometry, materials=project.materials,
                              live_loads=project.live_loads)
    with pytest.raises(ig.NoAdmissibleMainReinforcementError, match="Revise la seccion"):
        prepare_girder(main, context, False)


@pytest.mark.parametrize("selector", (
    main._prompt_main_placement_option, main._prompt_custom_main_placement,
    lambda c: main.collect_interior_girder_reinforcement_selection(SimpleNamespace(main=SimpleNamespace(placement_options=c)), None),
    lambda c: main.collect_exterior_girder_reinforcement_selection(SimpleNamespace(main=SimpleNamespace(placement_options=c)), None),
    lambda c: main.collect_diaphragm_reinforcement_selection(SimpleNamespace(negative=SimpleNamespace(placement_options=c))),
))
@pytest.mark.parametrize("empty", (True, False))
def test_selectors_never_adopt_last_rejected_option(monkeypatch, narrow_geometry, selector, empty):
    case = ig.generate_main_bar_placement_options("Sin solucion", 1000,
        narrow_geometry, ig.InteriorGirderReinforcementParameters(), maximum_bar_count=8)
    if empty:
        case = replace(case, options=())
    monkeypatch.setattr('builtins.input', lambda *args: pytest.fail("An impossible selection must not be prompted"))
    with pytest.raises(ig.NoAdmissibleMainReinforcementError):
        selector(case)


def test_numeric_selection_rejects_hidden_invalid_item(monkeypatch, narrow_geometry, capsys):
    case = ig.generate_main_bar_placement_options("Test", 30, narrow_geometry,
        ig.InteriorGirderReinforcementParameters())
    rejected = next(o for o in case.options if not o.is_compliant)
    answers = iter((str(rejected.item), "9999", str(case.recommended.item)))
    monkeypatch.setattr('builtins.input', lambda *args: next(answers))
    assert main._prompt_main_placement_option(case) == case.recommended
    assert capsys.readouterr().out.count("no es una disposicion admisible") == 2


def test_interior_default_never_uses_a_rejected_recommendation(monkeypatch, narrow_geometry):
    case = ig.generate_main_bar_placement_options("Test", 30, narrow_geometry,
        ig.InteriorGirderReinforcementParameters())
    valid = case.recommended
    rejected = next(o for o in case.options if not o.is_compliant)
    case = replace(case, options=tuple(
        replace(o, is_recommended=o.item == rejected.item) for o in case.options))
    spacing = SimpleNamespace(recommended=object())
    reinforcement = SimpleNamespace(main=SimpleNamespace(placement_options=case),
        temperature=SimpleNamespace(spacing_options=spacing),
        skin=SimpleNamespace(spacing_options=spacing))
    monkeypatch.setattr('builtins.input', lambda *args: "")
    monkeypatch.setattr(main, '_recommended_shear_option_or_raise', lambda shear: object())
    selected = main.collect_interior_girder_reinforcement_selection(reinforcement, None)
    assert selected[0][1].item == valid.item
    assert selected[0][1].is_compliant


@pytest.mark.parametrize("mode", ("i", "y", "s"))
def test_no_layout_workflow_retries_only_explicitly_revised_inputs(monkeypatch, project, mode, capsys):
    calls = []
    revised = replace(project, interior_girder_index=2)

    def calculate(inputs):
        calls.append(inputs)
        if len(calls) == 1:
            raise ig.NoAdmissibleMainReinforcementError("No hay disposicion admisible para viga interior.")

    monkeypatch.setattr(main, '_run_bridge_design_once', calculate)
    monkeypatch.setattr(main, 'collect_project_inputs', lambda: revised)
    answers = iter((mode, f'"{FIXTURE}"'))
    monkeypatch.setattr('builtins.input', lambda *args: next(answers))
    main.run_bridge_design(project)
    assert len(calls) == (1 if mode == 's' else 2)
    if mode == 'i':
        assert calls[1] is revised
    elif mode == 'y':
        assert calls[1] == project
    output = capsys.readouterr().out
    assert "DISENO PENDIENTE" in output
    assert "No se genera una memoria completa" in output
    assert ("Calculo cancelado" in output) == (mode == 's')


def test_revision_menu_handles_bad_path_and_eof(monkeypatch, capsys):
    answers = iter(("invalid", "y", "no_existe_revision.yaml"))

    def answer(*args):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr('builtins.input', answer)
    assert main._revised_deck_inputs() is None
    output = capsys.readouterr().out
    assert "Ingrese Y, I o S" in output
    assert "No se pudieron cargar los datos revisados" in output
