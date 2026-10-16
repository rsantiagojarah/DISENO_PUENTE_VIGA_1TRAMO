"""Regressions for per-diameter overhang design and partial girder layers."""

from dataclasses import MISSING, fields, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from docx import Document

from bridge_design import main
from bridge_design.cli.yaml_inputs import project_inputs_from_yaml
from bridge_design.cli.yaml_io import load_yaml_file
from bridge_design.domain.adopted_reinforcement import (
    adopt_cantilever_reinforcement, flexural_capacity, flexural_design_for_option,
)
from bridge_design.domain.cantilever_slab import design_cantilever_slab
from bridge_design.domain.common_reinforcement import common_cantilever_reinforcement
from bridge_design.domain.girder_detailing import _bar_layer_counts
from bridge_design.domain.interior_girder import (
    InteriorGirderReinforcementParameters, generate_main_bar_placement_options,
)
from bridge_design.domain.rebar_catalog import custom_spacing_option
from bridge_design.domain.reinforcement import flexural_steel_area_cm2
from bridge_design.reporting import deck_docx as word
from bridge_design.reporting.common_design import cantilever_checks


@pytest.fixture(scope="module")
def project():
    return project_inputs_from_yaml(load_yaml_file(
        Path(__file__).parent / "fixtures/soldeoro_20261005.yaml"))


def overhang(project, length=2.258, thickness=.20):
    geometry = replace(project.transverse_slab.geometry, overhang_m=length, slab_thickness_m=thickness)
    result = design_cantilever_slab(geometry, project.materials, project.live_loads,
                                  project.transverse_slab.load_layout)
    return geometry, result


@pytest.mark.parametrize("kind", ("interior", "exterior"))
@pytest.mark.parametrize("count", (2, 6, 12, 17, 18, 20))
def test_girder_centroid_matches_actual_layer_counts(project, kind, count):
    geometry = getattr(project, kind + "_girder")
    params = InteriorGirderReinforcementParameters()
    catalog = generate_main_bar_placement_options("Test", 80, geometry, params)
    bar = next(o for o in catalog.options if o.bar_label == '1"' and o.bar_count == count)
    counts = _bar_layer_counts(bar)
    pitch = bar.bar_diameter_cm + max(params.minimum_clear_bar_spacing_cm, bar.clear_spacing_cm)
    first = params.concrete_cover_cm + bar.bar_diameter_cm / 2
    centroid = sum(n * (first + layer * pitch) for layer, n in enumerate(counts)) / count
    assert sum(counts) == count
    assert bar.steel_centroid_from_tension_face_cm == pytest.approx(centroid)
    assert bar.effective_depth_cm == pytest.approx(geometry.total_t_section_depth_m * 100 - centroid)
    if count == 20:
        assert counts == (6, 6, 6, 2)
        assert centroid == pytest.approx(15.2604)


@pytest.mark.parametrize("length", (1.0, 2.258, 2.637, 2.65))
def test_overhang_table_checks_each_diameter_and_recommendation(project, length):
    geometry, result = overhang(project, length)
    flex = result.flexural_steel
    for option in flex.spacing_options.options:
        depth = geometry.slab_thickness_m * 100 - result.parameters.concrete_cover_cm - option.bar.diameter_cm / 2
        required = max(flex.minimum_area_cm2_m, flexural_steel_area_cm2(
            flex.minimum_capacity_moment_tn_m, 100, depth, 280, 4200))
        assert option.required_area_cm2_m == pytest.approx(required)
        actual = flexural_design_for_option(flex, option, project.materials.concrete, project.materials.steel)
        if option.is_compliant:
            assert flexural_capacity(actual, option.provided_area_cm2_m,
                project.materials.concrete, project.materials.steel) >= flex.minimum_capacity_moment_tn_m - 1e-8
    recommended = flex.spacing_options.recommended
    assert recommended is not None and recommended.is_compliant
    assert flex.bar_diameter_cm == recommended.bar.diameter_cm
    assert flex.required_area_cm2_m == recommended.required_area_cm2_m
    if length == 2.65:
        inch = next(o for o in flex.spacing_options.options if o.bar.label == '1"')
        assert inch.required_area_cm2_m == pytest.approx(16.923991872762397)
        assert inch.spacing_m < .30
        with pytest.raises(ValueError, match="As provisto"):
            custom_spacing_option(flex.spacing_options, '1"', .30)


def test_selected_overhang_updates_engine_terminal_and_word(project, capsys):
    geometry, result = overhang(project)
    candidate = next(o for o in result.flexural_steel.spacing_options.options if o.bar.label == '3/4"')
    # Replay the old, incorrectly accepted selection; do not silently replace it.
    option = replace(candidate, spacing_m=.275, provided_area_cm2_m=2.84/.275,
                     is_compliant=True, is_custom=True)
    selected = (("A. Superior", option), ("B. Temperatura", result.temperature_steel.spacing_options.recommended))
    context = SimpleNamespace(transverse_slab=SimpleNamespace(geometry=geometry), materials=project.materials)
    computed = main._run_cantilever(context, None, prepared=result, selected=selected)
    adopted, choices, crack, development = computed[:4]
    assert choices[0][1].bar == option.bar and choices[0][1].spacing_m == .275
    assert not choices[0][1].is_compliant
    assert adopted.flexural_steel.effective_depth_cm == pytest.approx(14.045)
    assert 20 - crack.dc_cm == pytest.approx(adopted.flexural_steel.effective_depth_cm)
    assert development.required_area_cm2_m == adopted.flexural_steel.required_area_cm2_m
    assert adopt_cantilever_reinforcement(geometry, project.materials, adopted, choices) == (adopted, choices)
    assert "Mr = 5.127" in computed[-1] and "NO CUMPLE" in computed[-1]
    assert "d = 14.045" in capsys.readouterr().out
    member = SimpleNamespace(result=adopted, selected=choices, crack=crack, project_inputs=project)
    check = next(row for row in cantilever_checks(member) if row[0] == "Flexion: capacidad")
    assert check[1] == pytest.approx(5.178061071125759)
    assert check[2] == pytest.approx(5.127041755566359)
    # Test direct and already-adopted report paths, including native Word equations.
    texts = []
    for design in (result.flexural_steel, adopted.flexural_steel):
        doc = Document()
        word._configure_document(doc)
        word._flexural_calc(doc, "Voladizo", design, option,
                           project.materials.concrete, project.materials.steel, strip=True)
        texts.append("".join(doc.element.xpath('//*[local-name()="t"]/text()')))
    assert texts[0] == texts[1]
    assert "5.127" in texts[0] and "NO CUMPLE" in texts[0]
    assert "5.252" not in texts[0]


def test_selected_overhang_updates_shear_and_development(project):
    geometry, result = overhang(project, thickness=.40)
    option = custom_spacing_option(result.flexural_steel.spacing_options, '1"', .20)
    selected = (("A. Superior", option), ("B. Temperatura", result.temperature_steel.spacing_options.recommended))
    adopted, _ = adopt_cantilever_reinforcement(geometry, project.materials, result, selected)
    expected_d = 40 - 5 - 2.54/2
    assert adopted.flexural_steel.effective_depth_cm == pytest.approx(expected_d)
    assert adopted.shear.effective_shear_depth_cm == pytest.approx(max(.9*expected_d, .72*40))
    assert adopted.shear.phi_vc_tn != result.shear.phi_vc_tn
    assert adopted.development.bar_diameter_cm == 2.54


def test_common_overhang_preserves_each_diameter_demand(project):
    results = (overhang(project, 2.258)[1], overhang(project, 2.65)[1])
    common = common_cantilever_reinforcement(results)
    for option in common.flexural_steel.spacing_options.options:
        expected = max(next(o.required_area_cm2_m for o in r.flexural_steel.spacing_options.options
                            if o.bar == option.bar) for r in results)
        assert option.required_area_cm2_m == expected
        if option.is_compliant:
            for result in results:
                actual = flexural_design_for_option(result.flexural_steel, option,
                    project.materials.concrete, project.materials.steel)
                assert flexural_capacity(actual, option.provided_area_cm2_m,
                    project.materials.concrete, project.materials.steel) >= actual.minimum_capacity_moment_tn_m - 1e-8
    with pytest.raises(ValueError, match="As provisto"):
        custom_spacing_option(common.flexural_steel.spacing_options, '1"', .30)


def test_overhang_selection_preserves_axial_cases(project):
    from bridge_design.domain.cantilever_slab import CantileverFlexuralCase
    from bridge_design.reporting.deck_docx_detail import flexural_as_min_trace
    _, result = overhang(project, 1.0)
    # Same additive model, with concurrent M and N kept together in each case.
    design = replace(result.flexural_steel, load_cases=(
        CantileverFlexuralCase("Resistencia", 3.0),
        CantileverFlexuralCase("Colision", 2.0, 15.0),
    ))
    option = next(o for o in design.spacing_options.options if o.bar.label == '1"')
    updated = flexural_design_for_option(design, option, project.materials.concrete, project.materials.steel)
    axial = 15000/(.9*4200)
    expected = flexural_steel_area_cm2(updated.minimum_capacity_moment_tn_m, 100, 13.73, 280, 4200) + axial
    assert updated.controlling_combination_name == "Colision"
    assert updated.axial_area_cm2_m == pytest.approx(axial)
    assert updated.strength_area_cm2_m == pytest.approx(expected)
    trace = flexural_as_min_trace(strip=True, design=updated, concrete=project.materials.concrete,
        steel=project.materials.steel, option_text="Test", provided_area=option.provided_area_cm2_m,
        compliance_comment="Test")
    capacity = flexural_capacity(updated, option.provided_area_cm2_m, project.materials.concrete, project.materials.steel)
    assert "As,N" in trace[0] and "As,flex,prov" in trace[2]
    assert f"φMn = {capacity:.3f}" in trace[3]


def test_common_workflow_and_word_context_use_adopted_bar(project, monkeypatch):
    from bridge_design.cli.common_design import run_cantilever_family
    from bridge_design.reporting.models import DeckReportData

    def choose(result):
        return (("A. Superior", custom_spacing_option(result.flexural_steel.spacing_options, '1/2"', .20)),
                ("B. Temperatura", result.temperature_steel.spacing_options.recommended))

    monkeypatch.setattr(main, "collect_cantilever_reinforcement_selection", choose)
    members, family, _ = run_cantilever_family(main, project, None)
    assert family.reinforcement.flexural_steel.effective_depth_cm == pytest.approx(14.365)
    for member in members:
        assert member.result.flexural_steel.effective_depth_cm == pytest.approx(14.365)
        assert member.selected[0][1].bar.label == '1/2"'
        assert member.selected[0][1].spacing_m == .20
    # Only the overhang chapter needs populated inputs in this isolated report.
    empty = DeckReportData(**{field.name: None for field in fields(DeckReportData) if field.default is MISSING})
    context = family.report_context(empty)
    assert context.cantilever_result.flexural_steel == family.reinforcement.flexural_steel
    assert context.cantilever_selected == family.selected
    label, principal = family.selected[0]
    failed = replace(family, selected=((label, replace(principal, is_compliant=False)), *family.selected[1:]))
    assert failed.status == "NO CUMPLE"
    doc = Document()
    word._configure_document(doc)
    word._cantilever(doc, context)
    text = "".join(doc.element.xpath('//*[local-name()="t"]/text()'))
    assert '1/2" @ 0.200' in text
    assert "Flexion: capacidad" in text
    assert "d = 14.60" not in text
