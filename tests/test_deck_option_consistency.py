"""Each offered layout and each reported collision case must match the engine."""

from dataclasses import MISSING, fields, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from docx import Document

from bridge_design.cli.ascii_output import _format_main_placement_table
from bridge_design.cli.yaml_inputs import project_inputs_from_yaml
from bridge_design.cli.yaml_io import load_yaml_file
from bridge_design.domain import interior_girder as ig, exterior_girder as eg
from bridge_design.domain.adopted_reinforcement import (
    adopt_girder_reinforcement, flexural_capacity, flexural_design_for_option,
    refresh_main_option,
)
from bridge_design.domain.common_reinforcement import common_girder_reinforcement
from bridge_design.reporting import deck_docx as word
from bridge_design.reporting.models import DeckReportData


@pytest.fixture(scope="module")
def project():
    return project_inputs_from_yaml(load_yaml_file(
        Path(__file__).parent / "fixtures/soldeoro_20261005.yaml"))


@pytest.fixture(scope="module")
def short_girder(project):
    geometry = replace(project.interior_girder, span_length_m=7,
        girder_total_height_m=.5, web_width_m=.4, diaphragms=(),
        live_load_distribution_factor_g=None, live_load_shear_distribution_factor_g=None)
    analysis = ig.solve_interior_girder_design(geometry, project.materials, project.live_loads)
    return geometry, ig.design_interior_girder_reinforcement(geometry, project.materials, analysis)


def test_girder_table_rejects_old_false_ok_and_preserves_adopted_failure(project, short_girder):
    geometry, reinforcement = short_girder
    case = reinforcement.main.placement_options
    option = next(o for o in case.options if o.bar_label == '5/8"' and o.bar_count == 19)
    assert option.required_area_cm2 == pytest.approx(39.290481096965365)
    assert not option.is_compliant and not option.is_recommended
    assert case.recommended is not None and case.recommended.is_compliant
    with pytest.raises(ValueError, match="As provisto"):
        ig.custom_main_bar_placement_option(case, '5/8"', 19)
    table = "\n".join(_format_main_placement_table(case))
    assert "As req por disposicion" in table and "d (cm)" in table
    assert not any('|   41 |' in row for row in table.splitlines())
    # Replay a previously accepted selection: report the failure, never replace it.
    adopted = adopt_girder_reinforcement(geometry, project.materials, reinforcement, option)
    checked = refresh_main_option(option, adopted.main, project.materials, adopted.parameters)
    assert checked.bar_count == 19 and checked.bar_label == '5/8"'
    assert not checked.is_compliant
    doc = Document()
    word._configure_document(doc)
    word._flexural_calc(doc, "Viga", adopted.main, checked,
        project.materials.concrete, project.materials.steel, strip=False)
    text = "".join(doc.element.xpath('//*[local-name()="t"]/text()'))
    assert "81.322" in text and "84.018" in text and "NO CUMPLE" in text


@pytest.mark.parametrize("kind", ("interior", "exterior"))
@pytest.mark.parametrize("small", (False, True))
def test_every_girder_option_matches_its_own_depth(project, kind, small):
    module = ig if kind == "interior" else eg
    geometry = getattr(project, kind + "_girder")
    if small:
        geometry = replace(geometry, span_length_m=7, girder_total_height_m=.5,
            web_width_m=.4, diaphragms=(), live_load_distribution_factor_g=None,
            live_load_shear_distribution_factor_g=None)
    analysis = getattr(module, 'solve_' + kind + '_girder_design')(
        geometry, project.materials, project.live_loads)
    reinforcement = getattr(module, 'design_' + kind + '_girder_reinforcement')(
        geometry, project.materials, analysis)
    case = reinforcement.main.placement_options
    assert case.recommended is not None and case.recommended.is_compliant
    for option in case.options:
        actual = flexural_design_for_option(reinforcement.main, option,
            project.materials.concrete, project.materials.steel)
        assert option.required_area_cm2 == pytest.approx(actual.required_area_cm2)
        checked = refresh_main_option(option, actual, project.materials, reinforcement.parameters)
        assert option.is_compliant == checked.is_compliant
    assert case.required_area_cm2 == pytest.approx(case.recommended.required_area_cm2)


def test_common_girder_table_keeps_per_layout_requirements(project, short_girder):
    geometry, reinforcement = short_girder
    other_geometry = replace(geometry, span_length_m=8,
        live_load_distribution_factor_g=None, live_load_shear_distribution_factor_g=None)
    analysis = ig.solve_interior_girder_design(other_geometry, project.materials, project.live_loads)
    other = ig.design_interior_girder_reinforcement(other_geometry, project.materials, analysis)
    common = common_girder_reinforcement((reinforcement, other))
    for option in common.main.placement_options.options:
        matches = [next(o for o in r.main.placement_options.options
                        if (o.bar_label, o.bar_count) == (option.bar_label, option.bar_count))
                   for r in (reinforcement, other)]
        assert option.required_area_cm2 == max(o.required_area_cm2 for o in matches)
        assert option.is_compliant == all(o.is_compliant for o in matches)
    assert common.main.placement_options.recommended.is_compliant


@pytest.fixture(scope="module")
def collision_context():
    from test_cantilever_slab import _materials, _geometry, _layout
    from bridge_design.domain.barrier import BarrierDesignInputs, design_concrete_barrier
    from bridge_design.domain.cantilever_slab import design_cantilever_slab
    from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel

    materials, geometry = _materials(), _geometry()
    layout = replace(_layout(), barrier_left_m=.1, sidewalk_width_m=.1)
    result = design_cantilever_slab(geometry, materials,
        LiveLoads(PedestrianLoad.mtc_sidewalk_default(), VehicleLoadModel.mtc_hl93_default()),
        layout, design_concrete_barrier(BarrierDesignInputs(), materials))
    assert result.flexural_steel.design_moment_tn_m == pytest.approx(5.6980576686483735)
    empty = DeckReportData(**{f.name: None for f in fields(DeckReportData) if f.default is MISSING})
    context = replace(empty,
        project_inputs=SimpleNamespace(materials=materials,
            transverse_slab=SimpleNamespace(geometry=geometry, load_layout=layout)),
        cantilever_result=result,
        cantilever_selected=(("A. Superior", result.flexural_steel.spacing_options.recommended),
                            ("B. Temperatura", result.temperature_steel.spacing_options.recommended)),
        cantilever_crack=result.crack_control, cantilever_development=result.development)
    return context


def test_collision_word_distinguishes_interface_and_adopted_root(collision_context):
    doc = Document()
    word._configure_document(doc)
    word._cantilever(doc, collision_context)
    text = "".join(doc.element.xpath('//*[local-name()="t"]/text()'))
    assert "Interfaz A-A" in text and "Raíz B-B" in text
    assert "M = 5.698 Tn·m/m; N = 5.865 Tn/m" in text
    assert "M,A-A = 6.984" in text and "N,A-A = 7.378" in text
    assert "El diseño flexional adopta Mu = max" not in text
    assert "N simultanea=7.378" not in text


@pytest.mark.parametrize("moment, collision_governs", ((6.0, True), (8.0, False)))
def test_collision_trace_uses_governing_steel_case_not_largest_moment(
        collision_context, moment, collision_governs):
    from bridge_design.domain._cantilever_slab_calculations import design_flexural_steel
    from bridge_design.reporting.deck_docx_detail import cantilever_collision_trace

    context = collision_context
    result = context.cantilever_result
    control = replace(result.controlling_strength, combined_moment_tn_m=-moment)
    flexural = design_flexural_steel(context.project_inputs.transverse_slab.geometry,
        context.project_inputs.materials, result.parameters, control, result.barrier_collision)
    adopted = next(c for c in flexural.load_cases
                   if c.combination_name == flexural.controlling_combination_name)
    assert (adopted.axial_tension_tn_m > 0) == collision_governs
    trace = cantilever_collision_trace(result.barrier_collision, control, flexural)
    assert f"M = {adopted.moment_tn_m:.3f} Tn·m/m; N = {adopted.axial_tension_tn_m:.3f} Tn/m" in trace[3]
    if collision_governs:
        assert adopted.moment_tn_m < control.design_moment_tn_m


@pytest.mark.parametrize("moment", (15, 60))
@pytest.mark.parametrize("modulus", (1e6, 2e6))
def test_diaphragm_catalog_matches_adopted_section(project, moment, modulus):
    from test_diaphragm import _geometry
    from bridge_design.domain.diaphragm import _design_flexural_steel

    geometry = replace(_geometry(), height_m=.7, thickness_m=.35)
    materials = replace(project.materials,
        steel=replace(project.materials.steel, elastic_modulus_kg_cm2=modulus))
    params = ig.InteriorGirderReinforcementParameters()
    row = SimpleNamespace(combination_name="RESISTENCIA I", position_m=2.0,
                          combined_moment_tn_m=moment)
    design = _design_flexural_steel("Diafragma", "M+", row, geometry, materials, params)
    recommended = design.placement_options.recommended
    assert recommended is not None and recommended.is_compliant
    assert design.effective_depth_cm == recommended.effective_depth_cm
    assert design.required_area_cm2 == pytest.approx(recommended.required_area_cm2)
    for option in design.placement_options.options:
        actual = flexural_design_for_option(design, option, materials.concrete, materials.steel)
        assert option.required_area_cm2 == pytest.approx(actual.required_area_cm2)
        assert option.is_compliant == refresh_main_option(option, actual, materials, params).is_compliant
