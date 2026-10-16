"""Regressions for constructive spacing and calculation/report consistency."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from docx import Document

from bridge_design.cli.connected_2_yaml import connected_2_inputs_from_yaml, connected_2_yaml_template
from bridge_design.cli.connected_selection import _format_cut_alternatives
from bridge_design.domain.connected_cut_options import (
    BOTTOM_FOOTING, STEM_REGION, TOP_FOOTING, CutAlternative, _verified_cut_alternatives,
)
from bridge_design.domain.connected_design import solve_connected_abutments
from bridge_design.domain.connected_distributions import Distribution
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil
from bridge_design.domain.connected_options import area_options, check_region_choice
from bridge_design.domain.connected_reinforcement import (
    ConnectedBarChoice, ConnectedSteelChoice, SectionDemand, design_region, region_setup, validate_choice,
)
from bridge_design.domain.rebar_catalog import (
    REINFORCING_BAR_CATALOG, SpacingGrid, _minimum_center_spacing_m, reinforcing_bar_by_label,
)
from bridge_design.reporting.connected_audit import build_connected_audit
from bridge_design.reporting.connected_design_calculations import write_checks
from bridge_design.reporting.connected_distribution_report import governing_source
from bridge_design.reporting.deck_docx import _configure_document


DEMANDS = (SectionDemand("Prueba", "strength", 100, 0, 1, 1, 0, .5),)


def narrow_spacing_inputs(maximum=.30):
    data = ConnectedInputs(FoundationSoil(3000, .5, 26.7), mesh_size_m=1, include_without_bridge=False)
    side = replace(data.left, reinforcement=replace(
        data.left.reinforcement, minimum_spacing_m=.025, maximum_spacing_m=maximum))
    return replace(data, left=side, right=side)


@pytest.mark.parametrize("principal", [True, False])
@pytest.mark.parametrize("spacing", [.025, .05])
def test_custom_spacing_must_leave_catalog_clearance(principal, spacing):
    with pytest.raises(ValueError, match="espacio libre del catalogo"):
        validate_choice(ConnectedBarChoice('1"', spacing, True), SpacingGrid(minimum_m=.025),
                        7.5, DEMANDS, principal=principal)


@pytest.mark.parametrize("bar", REINFORCING_BAR_CATALOG, ids=lambda bar: bar.label)
def test_constructive_spacing_boundary_includes_small_distribution_bars(bar):
    grid = SpacingGrid(minimum_m=.025)
    spacing = _minimum_center_spacing_m(bar, grid.minimum_m)
    selected = ConnectedBarChoice(bar.label, spacing, True)
    area, actual_bar, actual_spacing = validate_choice(selected, grid, 7.5, DEMANDS, principal=False)
    assert actual_bar == bar and actual_spacing == spacing
    assert area == pytest.approx(bar.area_cm2 / spacing)
    with pytest.raises(ValueError, match="espacio libre del catalogo"):
        validate_choice(replace(selected, spacing_m=spacing-1e-6), grid, 7.5, DEMANDS, principal=False)


def test_recommendations_preserve_catalog_spacing_rejection():
    options = area_options(narrow_spacing_inputs(.05), STEM_REGION, DEMANDS)
    one_inch = next(o for o in options if o.bar_label == '1"')
    assert one_inch.area_per_face_cm2_m >= one_inch.required_as_cm2_m
    assert one_inch.spacing_m == .05
    assert not one_inch.is_compliant
    assert any(o.is_compliant for o in options)
    for option in options:
        if option.is_compliant:
            validate_choice(ConnectedBarChoice(option.bar_label, option.spacing_m),
                            SpacingGrid(minimum_m=.025, maximum_m=.05), 7.5, DEMANDS, principal=False)


def test_automatic_candidates_and_noncompliant_fallback_are_constructible():
    data = narrow_spacing_inputs(.05)
    demands = (replace(DEMANDS[0], moment=200),)
    _, _, grid, _, candidates = region_setup(data, STEM_REGION, demands)
    assert candidates
    assert all(spacing+1e-9 >= _minimum_center_spacing_m(bar, grid.minimum_m)
               for _, bar, spacing in candidates)
    assert not any(o.is_compliant for o in area_options(data, STEM_REGION, demands))
    distribution = Distribution(STEM_REGION, "Pantalla", "Relleno", "Vertical", "primary", demands)
    steel = design_region(data, None, STEM_REGION, demands, distribution=distribution)
    bar = reinforcing_bar_by_label(steel.bar_label)
    assert steel.spacing_m+1e-9 >= _minimum_center_spacing_m(bar, grid.minimum_m)
    assert steel.status == "NO CUMPLE"


def test_grid_with_no_constructible_candidate_is_rejected():
    with pytest.raises(ValueError, match="No existen opciones de acero compatibles"):
        region_setup(narrow_spacing_inputs(.025), STEM_REGION, DEMANDS)


def test_cut_candidates_do_not_bypass_constructive_spacing(monkeypatch):
    data = narrow_spacing_inputs(.15)
    seen = []

    def evaluate(demands, inputs, cover, bar, spacing):
        assert spacing+1e-9 >= _minimum_center_spacing_m(bar, inputs.reinforcement.minimum_spacing_m)
        seen.append((bar.label, spacing))
        return float("inf"), 0, 0, demands[0]

    monkeypatch.setattr("bridge_design.domain.connected_distributions.reinforcement_demands",
                        lambda *args: {STEM_REGION: DEMANDS})
    monkeypatch.setattr("bridge_design.domain.connected_reinforcement.evaluate_option", evaluate)
    result = SimpleNamespace(inputs=data, mesh=None, results=())
    assert _verified_cut_alternatives(result, STEM_REGION) == ()
    assert seen


@pytest.fixture(scope="module", params=[1, 2])
def analysis(request):
    if request.param == 1:
        data = ConnectedInputs(FoundationSoil(3000, .5, 26.7), mesh_size_m=1, include_without_bridge=False)
    else:
        raw = connected_2_yaml_template(example=True)
        raw["estribo"]["geometria"]["altura_parapeto_m"] = 1.22
        raw["estribo"]["materiales"].update(fc_concreto_kg_cm2=280, peso_unitario_relleno_tn_m3=2.038)
        raw["estribo"]["suelo_sismo"].update(angulo_friccion_relleno_grados=36.12, pga=.5, fpga=1)
        raw["suelo_cimentacion"].update(modulo_balasto_vertical_tn_m3=620, qadm_tn_m2=13.5)
        raw["cimentacion"]["cantidad_nudos_cimentacion"] = 82
        data = connected_2_inputs_from_yaml(raw)
    return solve_connected_abutments(data)


def test_final_selection_rejects_overlap_in_both_connected_modules(analysis):
    side = replace(analysis.inputs.left, reinforcement=replace(
        analysis.inputs.left.reinforcement, minimum_spacing_m=.025))
    result = replace(analysis, inputs=replace(analysis.inputs, left=side, right=side))
    choice = ConnectedBarChoice('1"', .025, True)
    with pytest.raises(ValueError, match="espacio libre del catalogo"):
        check_region_choice(result, STEM_REGION, ConnectedSteelChoice(choice, choice))


def test_word_uses_axial_from_shear_case_in_both_connected_modules(analysis):
    audit = build_connected_audit(analysis)
    differing = 0
    for steel in analysis.reinforcement:
        if steel.role != "primary":
            continue
        trace = audit["steel"][steel.region]
        shear_axial = trace["shear"]["demand"]["axial"]
        differing += abs(shear_axial-steel.governing_axial) > 1e-6
        document = Document()
        _configure_document(document)
        write_checks(document, steel, trace, governing_source)
        paragraphs = [p.text for p in document.paragraphs]
        axial_lines = [line for line in paragraphs if "incluido en beta de cortante" in line]
        assert axial_lines == [f"N={shear_axial:.3f} tn/m, correspondiente a esta sección e incluido en beta de cortante."]
        index = paragraphs.index(axial_lines[0])
        assert paragraphs[index-1] == "Sección gobernante de cortante: " + governing_source(trace["shear"])
        assert f"N={steel.governing_axial:.3f} tn, incluido en beta de cortante." not in paragraphs
        assert trace["flexure"]["flexure_ratio"] == pytest.approx(steel.flexural_utilization)
        assert trace["shear"]["shear_ratio"] == pytest.approx(steel.shear_utilization)
        assert trace["service"]["crack_ratio"] == pytest.approx(steel.crack_utilization)
    assert differing > 0


@pytest.mark.parametrize("region,note", [
    (STEM_REGION, "s menor desde la base hasta el corte; s mayor de alli a la coronacion."),
    (TOP_FOOTING, "s menor en el centro; s mayor en los dos extremos."),
    (BOTTOM_FOOTING, "s menor en los dos extremos; s mayor en el centro."),
])
def test_cut_table_maps_minor_spacing_to_heavy_zone(region, note):
    cut = CutAlternative("C1", '1"', .1, .2, 1, "1.000 m", None)
    lines = _format_cut_alternatives(SimpleNamespace(region=region, cuts=(cut,)))
    header = next(line for line in lines if "s menor (m)" in line)
    values = next(line for line in lines if "C1" in line)
    assert header.index("s menor (m)") < header.index("s mayor (m)")
    assert [cell.strip() for cell in values.split("|")][3:5] == ["0.100", "0.200"]
    assert note in lines
