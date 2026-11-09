"""Independent normative example and full shear-demand propagation."""

from dataclasses import replace
from math import radians, tan

import pytest

from bridge_design.codes.skew import concrete_t_girder_skew_shear_correction
from bridge_design.cli.yaml_inputs import project_inputs_from_yaml, project_yaml_template
from bridge_design.cli.skew_input import collect_skew_angle
from bridge_design.domain.interior_girder import (
    solve_interior_girder_design, combine_interior_girder_shears,
    design_interior_girder_shear,
    design_interior_girder_reinforcement,
)
from bridge_design.domain.exterior_girder import (
    solve_exterior_girder_design, combine_exterior_girder_shears,
    design_exterior_girder_shear,
    design_exterior_girder_reinforcement,
)
from test_interior_girder import _geometry as interior_geometry, _materials
from test_exterior_girder import _geometry as exterior_geometry
from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel


def correction(angle=22, **changes):
    args = dict(angle_deg=angle, span_length_m=15, girder_spacing_m=2.1,
                slab_thickness_m=0.2, girder_depth_m=1.2, web_width_m=0.3,
                girder_count=4)
    args.update(changes)
    return concrete_t_girder_skew_shear_correction(**args)


def test_formula_against_independent_si_section_calculation():
    # Kg=I+A*eg^2 in m4. 12 L[ft] ts[in]^3 / Kg[in4] = L[m] ts[m]^3 / Kg[m4].
    kg_m4 = 0.3 * 1.2**3 / 12 + (0.3 * 1.2) * 0.7**2
    expected = 1 + 0.2 * (15 * 0.2**3 / kg_m4)**0.3 * tan(radians(22))
    assert correction().factor == pytest.approx(expected, rel=1e-12)
    assert correction(0).factor == 1
    assert correction(60).factor > correction(22).factor > 1


@pytest.mark.parametrize("angle", [-0.1, 60.001, float("nan"), float("inf"), True])
def test_invalid_angle_rejected(angle):
    with pytest.raises(ValueError, match="esviaje"):
        correction(angle)


@pytest.mark.parametrize("kwargs", [dict(girder_count=3), dict(girder_spacing_m=5),
                                    dict(span_length_m=5), dict(span_length_m=80)])
def test_table_applicability_rejected(kwargs):
    with pytest.raises(ValueError):
        correction(**kwargs)


def test_yaml_defaults_and_project_replacements_preserve_angle():
    template = project_yaml_template()
    assert template["angulo_esviaje_grados"] == 0
    template.pop("angulo_esviaje_grados")
    assert project_inputs_from_yaml(template).skew_angle_deg == 0
    template["angulo_esviaje_grados"] = 22
    project = project_inputs_from_yaml(template)
    for group in (project, replace(project, interior_girder_index=2), replace(project)):
        assert group.interior_girder.skew_angle_deg == group.exterior_girder.skew_angle_deg == 22
        assert group.exterior_girder.with_distribution_factors(group.live_loads.vehicular) == group.exterior_girder
    template["angulo_esviaje_grados"] = 61
    with pytest.raises(ValueError, match="esviaje"):
        project_inputs_from_yaml(template)


def test_prompt_reprompts_and_accepts_zero_and_sixty(monkeypatch):
    answers = iter(["nan", "-1", "61", "60", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert collect_skew_angle() == 60
    assert collect_skew_angle() == 0


@pytest.mark.parametrize("value", [True, False, "nan", "inf", "texto", -1, 61])
def test_bad_yaml_angle(value):
    template = project_yaml_template()
    template["angulo_esviaje_grados"] = value
    with pytest.raises(ValueError, match="esviaje"):
        project_inputs_from_yaml(template)


@pytest.mark.parametrize("exterior", [False, True])
@pytest.mark.parametrize("angle", [0, 22, 60])
def test_correction_reaches_envelopes_combinations_and_stirrup_design(exterior, angle):
    geometry = (exterior_geometry if exterior else interior_geometry)()
    solve = solve_exterior_girder_design if exterior else solve_interior_girder_design
    combine = combine_exterior_girder_shears if exterior else combine_interior_girder_shears
    design = design_exterior_girder_shear if exterior else design_interior_girder_shear
    reinforcement = design_exterior_girder_reinforcement if exterior else design_interior_girder_reinforcement
    materials = _materials()
    loads = LiveLoads(PedestrianLoad.mtc_sidewalk_default(), VehicleLoadModel.mtc_hl93_default())
    skewed = replace(geometry, skew_angle_deg=angle)
    straight = solve(geometry, materials, loads)
    result = solve(skewed, materials, loads)
    factor = skewed.skew_correction.factor
    if angle == 0:
        assert result == straight
    assert (result.dc, result.dw, result.pl) == (straight.dc, straight.dw, straight.pl)
    for name in ("truck_ll_im", "tandem_ll_im", "fatigue_truck", "ll_im_envelope"):
        a, b = getattr(straight, name), getattr(result, name)
        assert b.moment_samples_tn_m == a.moment_samples_tn_m
        assert b.min_moment_samples_tn_m == a.min_moment_samples_tn_m
        assert b.shear_distribution_factor_g == pytest.approx(a.shear_distribution_factor_g * factor)
        for attr in ("shear_samples_tn", "max_shear_samples_tn", "min_shear_samples_tn"):
            for old, new in zip(getattr(a, attr), getattr(b, attr)):
                assert new == pytest.approx((old[0], factor * old[1]))
        for old, new in zip(a.maximum_support_reactions_tn, b.maximum_support_reactions_tn):
            assert new[1] == pytest.approx(old[1] * factor)
    for old, new in zip(combine(geometry, straight), combine(skewed, result)):
        expected = old.combined_shear_tn + old.ll_im_factor * old.ll_im_shear_tn * (factor - 1)
        assert new.combined_shear_tn == pytest.approx(expected)
    before = design(geometry, materials, straight, reinforcement(geometry, materials, straight))
    after = design(skewed, materials, result, reinforcement(skewed, materials, result))
    assert after.controlling_shear.combined_shear_tn >= before.controlling_shear.combined_shear_tn
    assert after.required_av_cm2_m >= before.required_av_cm2_m


def test_ascii_and_word_trace_use_actual_corrected_factor():
    from bridge_design.cli.ascii_output import format_input_summary
    from bridge_design.reporting.skew import skew_shear_trace
    from bridge_design.reporting.deck_docx import _calc, _configure_document
    from bridge_design.codes.skew import SKEW_SHEAR_REFERENCE
    from docx import Document

    project = replace(project_inputs_from_yaml(project_yaml_template()), skew_angle_deg=22)
    geometry = project.interior_girder
    result = solve_interior_girder_design(geometry, project.materials, project.live_loads)
    summary = format_input_summary(project)
    assert summary.isascii() and "22.000" in summary and "Cv=" in summary
    trace = skew_shear_trace(geometry, result)
    assert f"gV aplicado={result.shear_distribution_factor_g:.6f}" in trace[3]
    document = Document()
    _configure_document(document)
    _calc(document, "Correccion del cortante por esviaje", *trace, SKEW_SHEAR_REFERENCE)
    xml = document._element.xml
    assert "2.6.4.2.2.3c" in xml
    assert f"{result.shear_distribution_factor_g:.6f}" in xml


@pytest.mark.parametrize("angle", [0, 22])
def test_complete_deck_workflow_exports_skew_in_word(tmp_path, monkeypatch, capsys, angle):
    import test_deck_pdf_report as report_test
    from bridge_design.reporting import deck_docx, deck_sections_primary
    from bridge_design.reporting.pdf_style import report_styles
    from test_ascii_output import _project_inputs
    from zipfile import ZipFile

    project = replace(_project_inputs(), skew_angle_deg=angle)
    monkeypatch.setattr(report_test, "_project_inputs", lambda: project)
    captured = []
    original = deck_docx.generate_deck_docx

    def capture(data, path):
        captured.append(data)
        return original(data, path)

    monkeypatch.setattr(deck_docx, "generate_deck_docx", capture)
    path = report_test.generate_sample_report(tmp_path / "tablero.docx")
    console = capsys.readouterr().out.lower()
    with ZipFile(path) as package:
        xml = package.read("word/document.xml").decode("utf-8")
    titles = []
    original_card = deck_sections_primary.formula_card

    def capture_card(title, *args):
        titles.append(title)
        return original_card(title, *args)

    monkeypatch.setattr(deck_sections_primary, "formula_card", capture_card)
    for exterior in (False, True):
        deck_sections_primary.girder_story(captured[0], report_styles(), exterior=exterior)
    assert any("esviaje" in title for title in titles) == bool(angle)
    if not angle:
        assert "esviaje" not in xml.lower()
        assert "esviaje" not in console
        assert "2.6.4.2.2.3c" not in xml
        return
    assert "Correccion del cortante por esviaje" in xml
    assert "22.000" in xml
    assert f"{project.interior_girder.skew_correction.factor:.6f}" in xml
    assert "2.6.4.2.2.3c" in xml
    assert "ambos extremos y toda la luz" in xml


@pytest.mark.parametrize("explicit_zero", [False, True])
def test_zero_or_missing_yaml_angle_has_no_console_mentions(explicit_zero):
    from bridge_design.cli.ascii_output import format_input_summary

    template = project_yaml_template()
    if not explicit_zero:
        template.pop("angulo_esviaje_grados")
    project = project_inputs_from_yaml(template)
    summary = format_input_summary(project)
    assert "esviaje" not in summary.lower()
    assert "Cv=" not in summary
