"""Selected steel, design checks and Word substitutions must describe one section."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from docx import Document

from bridge_design import main
from bridge_design.cli.yaml_inputs import project_inputs_from_yaml
from bridge_design.cli.yaml_io import load_yaml_file
from bridge_design.domain import exterior_girder as exterior, interior_girder as interior
from bridge_design.domain.adopted_reinforcement import (
    adopt_diaphragm_reinforcement, adopt_slab_reinforcement,
    flexural_capacity, flexural_design_for_option, refresh_stirrup_option,
)
from bridge_design.domain.diaphragm import solve_diaphragm_design, design_diaphragm_reinforcement
from bridge_design.domain.rebar_catalog import custom_spacing_option
from bridge_design.domain.reinforcement import design_transverse_slab_reinforcement, flexural_steel_area_cm2
from bridge_design.domain.transverse_slab import solve_transverse_slab_design
from bridge_design.reporting import deck_docx as word, deck_docx_detail as trace
from bridge_design.reporting.common_design import make_girder_family
from bridge_design.reporting.models import GirderReportGroup


@pytest.fixture(scope="module")
def project():
    return project_inputs_from_yaml(load_yaml_file(Path(__file__).parent / "fixtures/soldeoro_20261005.yaml"))


@pytest.fixture(scope="module", params=("interior", "exterior"))
def girder(project, request):
    kind = request.param
    module = exterior if kind == "exterior" else interior
    geometry = getattr(project, kind + "_girder")
    analysis = getattr(module, "solve_" + kind + "_girder_design")(geometry, project.materials, project.live_loads)
    reinforcement = getattr(module, "design_" + kind + "_girder_reinforcement")(geometry, project.materials, analysis)
    shear = getattr(module, "design_" + kind + "_girder_shear")(geometry, project.materials, analysis, reinforcement)
    chosen = interior.custom_main_bar_placement_option(reinforcement.main.placement_options, '1"', 20)
    selected = (("A. Principal", chosen), ("B. Temperatura", reinforcement.temperature.spacing_options.recommended),
                ("C. Ask", reinforcement.skin.spacing_options.recommended), ("D. Estribos", shear.recommended))
    return SimpleNamespace(kind=kind, geometry=geometry, analysis=analysis,
        reinforcement=reinforcement, shear=shear, selected=selected, module=module)


@pytest.fixture
def adopted(project, girder, monkeypatch):
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)
    result = getattr(main, "_run_" + girder.kind + "_girder")(
        project, prepared=(girder.analysis, girder.reinforcement, girder.shear), selected=girder.selected,
    )
    return GirderReportGroup((0 if girder.kind == "exterior" else 1,), girder.kind == "exterior", project, *result[:8])


def test_girder_selection_updates_all_depth_dependent_checks(project, girder, adopted):
    chosen = adopted.selected[0][1]
    design = adopted.reinforcement.main
    assert chosen.bar_count == 20
    assert chosen.effective_depth_cm == pytest.approx(94.7396)
    assert design.effective_depth_cm == chosen.effective_depth_cm
    assert design.required_area_cm2 == chosen.required_area_cm2
    assert design.required_area_cm2 > girder.reinforcement.main.required_area_cm2
    dv = max(.9 * chosen.effective_depth_cm, .72 * girder.geometry.total_t_section_depth_m * 100)
    assert adopted.shear.effective_shear_depth_cm == pytest.approx(dv)
    x = adopted.shear.controlling_shear.position_m
    assert min(x, girder.geometry.span_length_m-x) == pytest.approx(dv / 100)
    sample = lambda case: abs(interior._sample_at(case.shear_samples_tn, x)) if case else 0
    expected_vu = (1.25*sample(girder.analysis.dc) + 1.5*sample(girder.analysis.dw)
                   + 1.75*sample(girder.analysis.ll_im_envelope) + 1.75*sample(girder.analysis.pl))
    assert adopted.shear.controlling_shear.combined_shear_tn == pytest.approx(expected_vu)
    assert expected_vu > girder.shear.controlling_shear.combined_shear_tn
    assert adopted.crack.main.effective_depth_cm == design.effective_depth_cm
    assert adopted.fatigue.section.inertia_cm4 == adopted.service.section.inertia_cm4
    assert adopted.fatigue.section.neutral_axis_depth_cm == adopted.service.section.neutral_axis_depth_cm
    assert max(s.required_area_cm2 for s in adopted.detail.envelope) == pytest.approx(design.required_area_cm2)
    stirrup = adopted.selected[3][1]
    expected_capacity = adopted.shear.phi * min(adopted.shear.nominal_shear_limit_tn,
        adopted.shear.vc_tn + stirrup.provided_av_cm2_m / 100 * project.materials.steel.yield_strength_kg_cm2 / 1000 * dv)
    assert stirrup.phi_vn_tn == pytest.approx(expected_capacity)
    fields = word._sectional_shear_calc_fields(adopted.shear, stirrup)
    assert f"dv = {dv:.2f} cm" in fields[2]
    assert f"φVn,prov = {expected_capacity:.3f}" in fields[3]


def test_recommended_shear_station_already_uses_multilayer_depth(girder):
    x = girder.shear.controlling_shear.position_m
    assert min(x, girder.geometry.span_length_m-x) == pytest.approx(girder.shear.effective_shear_depth_cm / 100)


def test_direct_detail_call_uses_selected_depth(project, girder, adopted):
    from bridge_design.domain.girder_detailing import detail_interior_girder, detail_exterior_girder
    detail_fn = detail_exterior_girder if girder.kind == "exterior" else detail_interior_girder
    detail = detail_fn("Prueba", girder.geometry, project.materials, girder.analysis,
                      girder.reinforcement, girder.selected[0][1], adopted.selected[3][1])
    assert detail.envelope == adopted.detail.envelope
    assert detail.longitudinal_cuts == adopted.detail.longitudinal_cuts
    assert detail.stirrup_zones == adopted.detail.stirrup_zones


def test_common_family_retains_adopted_section(project, girder, adopted):
    family = make_girder_family((adopted,), girder.reinforcement, girder.selected)
    assert family.reinforcement.main == adopted.reinforcement.main
    assert family.selected[0][1].required_area_cm2 == adopted.reinforcement.main.required_area_cm2
    assert family.detail.selected_stirrup.phi_vn_tn == adopted.selected[3][1].phi_vn_tn
    assert family.checks


def test_word_recalculates_direct_and_adopted_flexure_identically(project, girder, adopted, monkeypatch):
    blocks = []
    monkeypatch.setattr(word, "_calc", lambda *args: blocks.append(args))
    chosen = adopted.selected[0][1]
    for design in (girder.reinforcement.main, adopted.reinforcement.main):
        word._flexural_calc(None, "Flexion", design, chosen, project.materials.concrete,
                           project.materials.steel, strip=False)
    assert blocks[0] == blocks[1]
    assert "d = 94.74 cm" in blocks[0][4]
    capacity = flexural_capacity(adopted.reinforcement.main, chosen.provided_area_cm2,
                                project.materials.concrete, project.materials.steel)
    assert f"φMn = {capacity:.3f} Tn·m" in blocks[0][5]


@pytest.fixture(scope="module")
def slab(project):
    geometry = project.transverse_slab.geometry
    analysis = solve_transverse_slab_design(geometry, project.materials, project.live_loads, project.transverse_slab.load_layout)
    return design_transverse_slab_reinforcement(geometry, project.materials, analysis)


def test_slab_updates_selected_diameter_required_steel_and_distribution(project, slab):
    selected = (("A. Negativo", custom_spacing_option(slab.negative.spacing_options, '1"', .30)),
                ("B. Positivo", custom_spacing_option(slab.positive.spacing_options, '1"', .30)),
                ("C. Temperatura", slab.temperature.spacing_options.recommended),
                ("D. Distribucion", slab.distribution.spacing_options.recommended))
    changed, options = adopt_slab_reinforcement(project.transverse_slab.geometry, project.materials, slab, selected)
    assert changed.negative.effective_depth_cm == pytest.approx(13.73)
    assert changed.negative.required_area_cm2_m == pytest.approx(11.27163019099)
    assert options[0][1].required_area_cm2_m == changed.negative.required_area_cm2_m
    assert changed.distribution.positive_main_area_cm2_m == changed.positive.required_area_cm2_m
    assert changed.distribution.required_area_cm2_m != slab.distribution.required_area_cm2_m
    assert options[3][1].required_area_cm2_m == changed.distribution.required_area_cm2_m
    assert [o.spacing_m for _, o in options] == [o.spacing_m for _, o in selected]
    assert adopt_slab_reinforcement(project.transverse_slab.geometry, project.materials, changed, options) == (changed, options)
    # Check the actual Word XML, including native equations, rather than just a formatter.
    doc = Document()
    word._configure_document(doc)
    word._flexural_calc(doc, "Acero negativo", slab.negative, selected[0][1],
                       project.materials.concrete, project.materials.steel, strip=True)
    text = "".join(doc.element.xpath('//*[local-name()="t"]/text()'))
    assert "13.73" in text and "11.272" in text and "7.723" in text
    assert "14.21" not in text and "8.023" not in text


@pytest.fixture(scope="module")
def diaphragm(project):
    analysis = solve_diaphragm_design(project.diaphragm, project.materials, project.live_loads, project.transverse_slab.load_layout)
    return analysis, design_diaphragm_reinforcement(project.diaphragm, project.materials, analysis)


def test_diaphragm_adopts_each_face_and_checks_shear_at_smaller_depth(project, diaphragm):
    analysis, reinforcement = diaphragm
    chosen = interior.custom_main_bar_placement_option(reinforcement.negative.placement_options, '1/2"', 8)
    selected = (("A. Negativo", chosen), ("B. Positivo", reinforcement.positive.placement_options.recommended),
                ("C. Temperatura", reinforcement.temperature.spacing_options.recommended),
                ("D. Estribos", reinforcement.shear.recommended), ("E. Ask", reinforcement.skin.spacing_options.recommended))
    updated, options = adopt_diaphragm_reinforcement(project.diaphragm, project.materials, analysis, reinforcement, selected)
    assert updated.negative.effective_depth_cm == pytest.approx(82.1403125)
    assert updated.positive.effective_depth_cm == pytest.approx(84.205)
    assert updated.shear.effective_shear_depth_cm == pytest.approx(.9 * chosen.effective_depth_cm)
    expected_strength = flexural_steel_area_cm2(updated.negative.minimum_capacity_moment_tn_m,
        updated.negative.section_width_cm, chosen.effective_depth_cm,
        project.materials.concrete.compressive_strength_kg_cm2, project.materials.steel.yield_strength_kg_cm2)
    assert updated.negative.strength_area_cm2 == pytest.approx(expected_strength)
    assert options[0][1].required_area_cm2 == updated.negative.required_area_cm2
    assert options[3][1].spacing_m == selected[3][1].spacing_m
    assert adopt_diaphragm_reinforcement(project.diaphragm, project.materials, analysis, updated, options) == (updated, options)


def test_failed_recheck_is_preserved_and_does_not_crash_family(girder, adopted):
    weak = replace(adopted.shear, required_av_cm2_m=1000, maximum_spacing_m=.025)
    original = adopted.selected[3][1]
    failed = refresh_stirrup_option(original, weak)
    assert not failed.is_compliant
    assert (failed.bar_label, failed.legs, failed.spacing_m) == (original.bar_label, original.legs, original.spacing_m)
    member = replace(adopted, shear=weak, selected=(*adopted.selected[:3], ("D. Estribos", failed)))
    family = make_girder_family((member,), adopted.reinforcement, member.selected)
    assert family.status == "NO CUMPLE"
    assert any(row[-1] == "NO CUMPLE" for row in family.checks)
    fields = word._sectional_shear_calc_fields(weak, original)
    assert "Armado adoptado (resistencia, cuantía y separación): NO CUMPLE" in fields[3]


def test_report_inequalities_follow_actual_values(project, adopted):
    service = replace(adopted.service, steel_tension_kg_cm2=3000, steel_status="NO CUMPLE")
    assert "3000.0 > 2520.0: NO CUMPLE" in trace.service_stress_trace(service, project.materials.concrete, project.materials.steel)[3]
    crack = replace(adopted.crack.main, provided_spacing_m=.25, maximum_spacing_m=.238,
                    spacing_status="NO CUMPLE", status="NO CUMPLE")
    assert "0.250 > 0.238" in trace.crack_control_trace(crack)[3]
    fatigue = replace(adopted.fatigue, factored_stress_range_kg_cm2=3000,
                      allowable_stress_range_kg_cm2=2000, status="NO CUMPLE")
    assert "3000.0 kg/cm² > ΔfTH = 2000.0" in trace.fatigue_trace(fatigue, project.materials.steel)[3]
    assert trace.upper_limit_symbol(2, 2) == "≤"
    assert trace.upper_limit_symbol(1, 2) == "≤"


def test_word_honors_configured_phi_limit(project, girder):
    design = replace(girder.reinforcement.main, flexural_resistance_factor=.75)
    option = girder.selected[0][1]
    design = flexural_design_for_option(design, option, project.materials.concrete, project.materials.steel)
    blocks = trace.flexural_as_min_trace(strip=False, design=design, concrete=project.materials.concrete,
        steel=project.materials.steel, option_text=word._option_text(option),
        provided_area=option.provided_area_cm2, compliance_comment="OK")
    assert "φprov = 0.750" in blocks[2]
    expected = flexural_capacity(design, option.provided_area_cm2, project.materials.concrete, project.materials.steel)
    assert f"φMn = {expected:.3f}" in blocks[3]


@pytest.mark.parametrize("retry_collision", [False, True])
def test_command_passes_adopted_slab_and_both_diaphragms_to_report(project, diaphragm, monkeypatch, retry_collision):
    analysis, initial = diaphragm
    # Reuse the analysed geometry for both types, but exercise both CLI branches.
    project = replace(project, end_diaphragm=project.diaphragm)
    monkeypatch.setattr(main, "solve_diaphragm_design", lambda **kwargs: analysis)
    original_slab = main.collect_reinforcement_spacing_selection
    original_diaphragm = main.collect_diaphragm_reinforcement_selection
    slab_choices = []
    def choose_slab(reinforcement, **kwargs):
        assert callable(kwargs["refresh_for_main"])
        selected = list(original_slab(reinforcement, **kwargs))
        label, spacing = ('5/8"', .15) if slab_choices else ('1"', .30)
        selected[0] = (selected[0][0], custom_spacing_option(reinforcement.negative.spacing_options, label, spacing))
        slab_choices.append(tuple(selected))
        return tuple(selected)
    def choose_diaphragm(reinforcement, **kwargs):
        assert callable(kwargs["refresh_for_main"])
        selected = list(original_diaphragm(reinforcement, **kwargs))
        selected[0] = (selected[0][0], interior.custom_main_bar_placement_option(
            reinforcement.negative.placement_options, '1/2"', 8))
        return tuple(selected)
    captured = []
    collision_questions = []
    def answer(prompt=""):
        if "verificar nuevamente la colision" in prompt:
            collision_questions.append(prompt)
            return "s" if retry_collision and len(collision_questions) == 1 else ""
        return ""
    from unittest.mock import Mock
    overhang_menu = Mock(wraps=main.collect_cantilever_reinforcement_selection)
    slab_tables = Mock(wraps=main.format_slab_reinforcement_options)
    monkeypatch.setattr(main, "collect_cantilever_reinforcement_selection", overhang_menu)
    monkeypatch.setattr(main, "format_slab_reinforcement_options", slab_tables)
    monkeypatch.setattr("builtins.input", answer)
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "collect_reinforcement_spacing_selection", choose_slab)
    monkeypatch.setattr(main, "collect_diaphragm_reinforcement_selection", choose_diaphragm)
    monkeypatch.setattr("bridge_design.reporting.generate_deck_docx_with_dialog", captured.append)
    main.run_bridge_design(project)
    assert len(captured) == 1
    data = captured[0]
    assert len(slab_choices) == (2 if retry_collision else 1)
    assert collision_questions
    assert overhang_menu.call_count == 1
    assert slab_tables.call_count == (1 if retry_collision else 0)
    upper = data.slab_selected[0][1]
    assert upper.bar.label == ('5/8"' if retry_collision else '1"')
    assert data.slab_reinforcement.negative.effective_depth_cm == pytest.approx(15 - upper.bar.diameter_cm/2)
    for group in data.cantilever_groups:
        for face, (_, chosen) in zip(group.result.interior_collision.faces, data.slab_selected[:2]):
            assert (face.option.bar, face.option.spacing_m) == (chosen.bar, chosen.spacing_m)
        assert group.result.interior_collision.faces[0].development_status == ("OK" if retry_collision else "NO CUMPLE")
    for reinforcement, selected in (
        (data.diaphragm_reinforcement, data.diaphragm_selected),
        (data.end_diaphragm_reinforcement, data.end_diaphragm_selected),
    ):
        assert reinforcement.negative.effective_depth_cm == selected[0][1].effective_depth_cm
        assert reinforcement.negative.effective_depth_cm == pytest.approx(82.1403125)
        assert reinforcement.shear.effective_shear_depth_cm < initial.shear.effective_shear_depth_cm


def test_skin_result_does_not_claim_compliance_for_failed_selection(girder):
    skin = girder.reinforcement.skin
    assert skin.required_area_cm2_m_per_face > 0
    fields = trace.skin_steel_trace(skin, '6 mm @ 0.30 m', "No cumple", is_compliant=False)
    assert "NO CUMPLE" in fields[3]
    assert "satisface" not in fields[3]
