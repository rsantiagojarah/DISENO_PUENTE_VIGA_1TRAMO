"""Dependent choices and Word must use the principal reinforcement just chosen."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from docx import Document

from bridge_design import main
from bridge_design.cli.yaml_inputs import project_inputs_from_yaml
from bridge_design.cli.yaml_io import load_yaml_file
from bridge_design.domain.adopted_reinforcement import (
    adopt_diaphragm_reinforcement, adopt_slab_reinforcement, refresh_stirrup_option,
)
from bridge_design.domain.crack_control import review_transverse_slab_crack_control
from bridge_design.domain.diaphragm import design_diaphragm_reinforcement, solve_diaphragm_design
from bridge_design.domain.interior_girder import custom_main_bar_placement_option
from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel
from bridge_design.domain.reinforcement import design_transverse_slab_reinforcement
from bridge_design.domain.transverse_slab import solve_transverse_slab_design
from bridge_design.reporting import deck_docx as word
from test_diaphragm import _geometry, _layout, _materials


@pytest.fixture(scope="module")
def slab():
    project = project_inputs_from_yaml(load_yaml_file(
        Path(__file__).parent / "fixtures/soldeoro_20261005.yaml"))
    geometry = replace(project.transverse_slab.geometry, slab_thickness_m=.18)
    project = replace(project, transverse_slab=replace(project.transverse_slab, geometry=geometry))
    analysis = solve_transverse_slab_design(
        geometry, project.materials, project.live_loads, project.transverse_slab.load_layout)
    steel = design_transverse_slab_reinforcement(geometry, project.materials, analysis)
    return project, analysis, steel


@pytest.mark.parametrize("mode", ("numeric", "custom", "stale_distribution", "custom_distribution", "default"))
def test_slab_refreshes_distribution_before_prompt(slab, monkeypatch, capsys, mode):
    project, analysis, steel = slab
    geometry = project.transverse_slab.geometry
    updates = []

    def refresh(chosen):
        updated, _ = adopt_slab_reinforcement(geometry, project.materials, steel, chosen)
        updates.append((chosen, updated))
        return updated

    if mode == "default":
        answers = iter(("",))
    else:
        positive = ("p", '1"', ".30") if mode == "custom" else ("7",)
        distribution = {
            "stale_distribution": ("p", '1/2"', ".20", "", ""),
            "custom_distribution": ("p", '1/2"', ".15"),
        }.get(mode, ("",))
        answers = iter(("s", "", *positive, "", *distribution))

    def answer(prompt):
        if "Acero distribucion" in prompt:
            assert len(updates) == 1, "Refresh must precede the dependent prompt"
        return next(answers)

    monkeypatch.setattr("builtins.input", answer)
    selected = main.collect_reinforcement_spacing_selection(steel, refresh_for_main=refresh)
    assert len(updates) == 1
    chosen, updated = updates[0]
    assert selected[:2] == chosen
    final, checked = adopt_slab_reinforcement(geometry, project.materials, steel, selected)
    assert all(option.is_compliant for _, option in checked)
    assert final.distribution == updated.distribution
    assert selected[3][1].required_area_cm2_m == pytest.approx(final.distribution.required_area_cm2_m)
    assert selected[3][1].provided_area_cm2_m >= final.distribution.required_area_cm2_m
    if mode != "default":
        assert selected[1][1].bar.label == '1"'
        assert final.distribution.required_area_cm2_m == pytest.approx(6.6431966867)
        assert steel.distribution.spacing_options.recommended.provided_area_cm2_m == pytest.approx(6.45)
        assert selected[3][1].provided_area_cm2_m > 6.45
        output = capsys.readouterr().out
        assert "TABLA ACTUALIZADA DE DISTRIBUCION CON EL ACERO POSITIVO ELEGIDO" in output
        assert "As req = 6.643 cm2/m" in output
        if mode == "stale_distribution":
            assert "Configuracion personalizada no valida" in output
        if mode == "custom_distribution":
            assert selected[3][1].is_custom
            assert selected[3][1].bar.label == '1/2"'
            assert selected[3][1].spacing_m == .15

    # Inspect the actual Word section in memory; no report file is generated.
    crack = review_transverse_slab_crack_control(
        geometry, project.materials, analysis, final, checked[0][1], checked[1][1])
    context = SimpleNamespace(project_inputs=project, transverse_result=analysis,
        slab_reinforcement=final, slab_selected=checked, slab_crack=crack)
    monkeypatch.setattr(word, "save_strength_chart", lambda *args, **kwargs: Path("unused.png"))
    monkeypatch.setattr(word, "_picture", lambda *args, **kwargs: None)
    document = Document()
    word._configure_document(document)
    word._transverse_slab(document, context, Path("."))
    text = "".join(document.element.xpath('//*[local-name()="t"]/text()'))
    distribution_text = text.split("Acero longitudinal de distribución", 1)[1].split("2.6 Control", 1)[0]
    assert f"= {final.distribution.required_area_cm2_m:.3f} cm²/m" in distribution_text
    assert word._option_text(checked[3][1]) in distribution_text
    assert "NO CUMPLE" not in distribution_text.upper()


@pytest.fixture(scope="module")
def diaphragm():
    geometry = replace(_geometry(), height_m=.4)
    materials = _materials()
    loads = LiveLoads(pedestrian=PedestrianLoad.mtc_sidewalk_default(),
                      vehicular=VehicleLoadModel.mtc_hl93_default())
    analysis = solve_diaphragm_design(geometry, materials, loads, _layout())
    steel = design_diaphragm_reinforcement(geometry, materials, analysis)
    return geometry, materials, analysis, steel


@pytest.mark.parametrize("side", ("negative", "positive"))
@pytest.mark.parametrize("mode", ("numeric", "custom", "stale_stirrup", "custom_stirrup", "default"))
def test_diaphragm_refreshes_shear_before_prompt(diaphragm, monkeypatch, capsys, side, mode):
    geometry, materials, analysis, steel = diaphragm
    catalog = getattr(steel, side).placement_options
    chosen_main = next(o for o in catalog.options if o.bar_label == '1/2"' and o.bar_count == 5)
    updates = []

    def refresh(chosen):
        updated, _ = adopt_diaphragm_reinforcement(geometry, materials, analysis, steel, chosen)
        updates.append((chosen, updated))
        return updated

    if mode == "default":
        answers = iter(("",))
    else:
        principal = ("p", '1/2"', "5") if mode == "custom" else (str(chosen_main.item),)
        mains = (*principal, "") if side == "negative" else ("", *principal)
        stirrup = {
            "stale_stirrup": ("p", "8 mm", "2", ".375", "", "", ""),
            "custom_stirrup": ("p", "8 mm", "2", ".15"),
        }.get(mode, ("",))
        answers = iter(("s", *mains, "", *stirrup))

    def answer(prompt):
        if "Temperatura" in prompt or "Estribos por corte" in prompt:
            assert len(updates) == 1, "Refresh must precede the dependent prompt"
        return next(answers)

    monkeypatch.setattr("builtins.input", answer)
    selected = main.collect_diaphragm_reinforcement_selection(steel, refresh_for_main=refresh)
    assert len(updates) == 1
    chosen, updated = updates[0]
    assert selected[:2] == chosen
    final, checked = adopt_diaphragm_reinforcement(geometry, materials, analysis, steel, selected)
    assert all(option.is_compliant for _, option in checked)
    assert final.shear == updated.shear
    stirrup = selected[3][1]
    assert refresh_stirrup_option(stirrup, final.shear).is_compliant
    if mode != "default":
        assert getattr(final, side).effective_depth_cm == pytest.approx(51.619)
        assert final.shear.maximum_spacing_m == pytest.approx(.3716568)
        assert not refresh_stirrup_option(steel.shear.recommended, final.shear).is_compliant
        output = capsys.readouterr().out
        assert "TABLAS ACTUALIZADAS CON EL ARMADO PRINCIPAL ELEGIDO - DIAFRAGMA" in output
        assert "s max = 0.372 m" in output
        if mode == "stale_stirrup":
            assert "Configuracion personalizada no valida" in output
        if mode == "custom_stirrup":
            assert stirrup.is_custom
            assert (stirrup.bar_label, stirrup.legs, stirrup.spacing_m) == ("8 mm", 2, .15)
    trace = word._sectional_shear_calc_fields(final.shear, checked[3][1])
    assert "NO CUMPLE" not in trace[3]
    assert f"smax = {final.shear.maximum_spacing_m:.3f} m" in trace[3]
    assert f"φVn,prov = {stirrup.phi_vn_tn:.3f}" in trace[3]


def test_diaphragm_refreshes_minimum_shear_and_skin(monkeypatch, capsys):
    geometry = replace(_geometry(), height_m=.8)
    materials = _materials()
    loads = LiveLoads(pedestrian=PedestrianLoad.mtc_sidewalk_default(),
                      vehicular=VehicleLoadModel.mtc_hl93_default())
    analysis = solve_diaphragm_design(geometry, materials, loads, _layout())
    steel = design_diaphragm_reinforcement(geometry, materials, analysis)
    chosen = custom_main_bar_placement_option(steel.negative.placement_options, '1"', 6)
    answers = iter(("s", "p", chosen.bar_label, str(chosen.bar_count), "", "", "", ""))
    monkeypatch.setattr("builtins.input", lambda *args: next(answers))
    refresh = lambda selected: adopt_diaphragm_reinforcement(
        geometry, materials, analysis, steel, selected)[0]
    selected = main.collect_diaphragm_reinforcement_selection(
        steel, element_name="diafragma de extremo", refresh_for_main=refresh)
    final, checked = adopt_diaphragm_reinforcement(geometry, materials, analysis, steel, selected)
    assert steel.shear.required_av_cm2_m == 0
    assert final.shear.required_av_cm2_m == pytest.approx(2.639100748, rel=1e-7)
    assert not refresh_stirrup_option(steel.shear.recommended, final.shear).is_compliant
    assert len(checked) == 5
    assert all(option.is_compliant for _, option in checked)
    assert selected[4][1] == final.skin.spacing_options.recommended
    assert selected[4][1].required_area_cm2_m == final.skin.required_area_cm2_m_per_face
    assert "DIAFRAGMA DE EXTREMO" in capsys.readouterr().out
