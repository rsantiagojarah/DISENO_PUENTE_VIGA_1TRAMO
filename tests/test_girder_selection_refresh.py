"""Dependent reinforcement choices must use the main steel just selected."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge_design import main
from bridge_design.cli.common_design import refresh_girder_for_main, run_girder_families
from bridge_design.cli.yaml_inputs import project_inputs_from_yaml
from bridge_design.cli.yaml_io import load_yaml_file
from bridge_design.domain import interior_girder as ig, exterior_girder as eg
from bridge_design.domain.adopted_reinforcement import refresh_stirrup_option
from bridge_design.domain.common_reinforcement import validate_girder_selection
from bridge_design.reporting.deck_docx import _sectional_shear_calc_fields


@pytest.fixture(scope="module")
def project():
    return project_inputs_from_yaml(load_yaml_file(
        Path(__file__).parent / "fixtures/soldeoro_20261005.yaml"))


@pytest.fixture(scope="module", params=(False, True), ids=("interior", "exterior"))
def girder(project, request):
    exterior = request.param
    prefix = "exterior" if exterior else "interior"
    module = eg if exterior else ig
    geometry = replace(getattr(project, prefix+"_girder"), span_length_m=7,
        girder_total_height_m=.5, web_width_m=.4, diaphragms=(),
        live_load_distribution_factor_g=None, live_load_shear_distribution_factor_g=None)
    analysis = getattr(module, "solve_"+prefix+"_girder_design")(
        geometry, project.materials, project.live_loads)
    steel = getattr(module, "design_"+prefix+"_girder_reinforcement")(
        geometry, project.materials, analysis)
    shear = getattr(module, "design_"+prefix+"_girder_shear")(
        geometry, project.materials, analysis, steel)
    context = SimpleNamespace(materials=project.materials, **{prefix+"_girder": geometry})
    selected_main = ig.custom_main_bar_placement_option(
        steel.main.placement_options, '5/8"', 18 if exterior else 20)
    return context, exterior, (analysis, steel, shear), selected_main


@pytest.mark.parametrize("mode", ("numeric", "custom", "stale_stirrup", "default"))
def test_girder_selector_refreshes_before_remaining_prompts(girder, monkeypatch, capsys, mode):
    project, exterior, values, chosen = girder
    prefix = "exterior" if exterior else "interior"
    _analysis, steel, shear = values
    updates = []

    def refresh(option):
        updated = refresh_girder_for_main(main, project, exterior, values, option)
        updates.append((option, updated))
        return updated[1:]

    if mode == "default":
        answers = iter(("",))
    else:
        catalog_option = next(o for o in steel.main.placement_options.options
                              if (o.bar_label, o.bar_count) == (chosen.bar_label, chosen.bar_count))
        principal = (("p", chosen.bar_label, str(chosen.bar_count))
                     if mode == "custom" else (str(catalog_option.item),))
        stirrup = (("p", shear.recommended.bar_label, "", str(shear.recommended.spacing_m), "", "", "")
                   if mode == "stale_stirrup" else ("",))
        answers = iter(("s", *principal, "", "", *stirrup))

    def answer(prompt):
        if "Temperatura" in prompt or "Estribos por corte" in prompt:
            assert len(updates) == 1, "Recalculation must precede the dependent choices"
        return next(answers)

    monkeypatch.setattr("builtins.input", answer)
    selected = getattr(main, "collect_"+prefix+"_girder_reinforcement_selection")(
        steel, shear, refresh_for_main=refresh)
    assert len(updates) == 1
    _main, (_analysis, updated_steel, updated_shear) = updates[0]
    assert selected[0][1] == _main  # no silent change to the chosen main steel
    assert all(option.is_compliant for _, option in selected)
    assert refresh_stirrup_option(selected[3][1], updated_shear).is_compliant
    validate_girder_selection(selected, updated_steel, updated_shear)
    if mode != "default":
        assert not refresh_stirrup_option(shear.recommended, updated_shear).is_compliant
        output = capsys.readouterr().out
        assert "TABLAS ACTUALIZADAS CON EL ARMADO LONGITUDINAL ELEGIDO" in output
        assert f"d = {chosen.effective_depth_cm:.3f}" in output
        assert f"Av/s req = {updated_shear.required_av_cm2_m:.3f}" in output
        if mode == "stale_stirrup":
            assert "Configuracion personalizada no valida" in output
    trace = _sectional_shear_calc_fields(updated_shear, selected[3][1])
    assert "NO CUMPLE" not in trace[3]
    assert f"φVn,prov = {selected[3][1].phi_vn_tn:.3f}" in trace[3]


def test_standalone_girder_workflow_supplies_refresh_context(girder, monkeypatch):
    project, exterior, values, chosen = girder
    prefix = "exterior" if exterior else "interior"
    monkeypatch.setattr(main, "format_"+prefix+"_girder_analysis_result", lambda *args: "")
    answers = iter(("s", "p", chosen.bar_label, str(chosen.bar_count), "", "", ""))
    monkeypatch.setattr("builtins.input", lambda *args: next(answers))
    result = getattr(main, "_run_"+prefix+"_girder")(project, prepared=values)
    shear, selected = result[2:4]
    assert selected[0][1].bar_count == chosen.bar_count
    assert selected[3][1].is_compliant
    assert refresh_stirrup_option(selected[3][1], shear).is_compliant


@pytest.mark.parametrize("custom", (False, True))
def test_family_selection_checks_every_member_after_choice(project, monkeypatch, custom):
    from bridge_design.domain.pipe_load import PipeLoad
    geometry = dict(span_length_m=7, girder_total_height_m=.5, web_width_m=.4,
                    diaphragms=(), live_load_distribution_factor_g=None,
                    live_load_shear_distribution_factor_g=None)
    project = replace(project, end_diaphragm=None,
        interior_girder=replace(project.interior_girder, **geometry),
        exterior_girder=replace(project.exterior_girder, **geometry),
        transverse_slab=replace(project.transverse_slab,
            load_layout=replace(project.transverse_slab.load_layout, pipe=PipeLoad(180, .4))))
    responses = (("s", "p", '5/8"', "20", "", "", "", "s", "p", '5/8"', "18", "", "", "")
                 if custom else ("", ""))
    answers = iter(responses)
    monkeypatch.setattr("builtins.input", lambda *args: next(answers))
    groups, families, *_ = run_girder_families(main, project)
    assert len(groups) > 2  # asymmetric load: more than one independent member per family
    for family in families:
        stirrup = family.selected[3][1]
        assert stirrup.is_compliant
        for member in family.members:
            validate_girder_selection(family.selected, member.reinforcement, member.shear)
            assert refresh_stirrup_option(stirrup, member.shear).is_compliant
            assert member.selected[0][1].effective_depth_cm == family.selected[0][1].effective_depth_cm


def test_no_shear_recommendation_stops_before_prompt(girder, monkeypatch):
    shear = girder[2][2]
    shear = replace(shear, options=tuple(replace(o, is_recommended=False, is_compliant=False)
                                         for o in shear.options))
    monkeypatch.setattr("builtins.input", lambda *args: pytest.fail("No valid stirrup to prompt"))
    with pytest.raises(ValueError, match="Ninguna opcion de estribos cumple"):
        main._prompt_shear_stirrup_option(shear)
