"""Regressions for the service, detailing and report audit of the bridge deck."""
from dataclasses import replace
from math import sqrt
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge_design.cli.yaml_inputs import project_inputs_from_yaml
from bridge_design.cli.yaml_io import load_yaml_file
from bridge_design.domain import exterior_girder as exterior
from bridge_design.domain import interior_girder as interior
from bridge_design.domain.crack_control import review_transverse_slab_crack_control
from bridge_design.domain.diaphragm import (
    combine_diaphragm_shears, design_diaphragm_reinforcement, solve_diaphragm_design,
)
from bridge_design.domain.rebar_catalog import custom_spacing_option
from bridge_design.domain.reinforcement import (
    SlabReinforcementParameters, design_transverse_slab_reinforcement,
)
from bridge_design.domain.transverse_slab import solve_transverse_slab_design
from bridge_design.reporting.deck_docx import _sectional_shear_calc_fields
from bridge_design.reporting.deck_docx_detail import crack_control_trace, exterior_g_factor_trace
from bridge_design.reporting.models import diaphragm_selection_with_skin


@pytest.fixture(scope="module")
def project():
    return project_inputs_from_yaml(load_yaml_file(
        Path(__file__).parent / "fixtures/soldeoro_20261005.yaml"
    ))


@pytest.fixture(scope="module", params=("interior", "exterior"))
def girder_case(project, request):
    kind = request.param
    module = interior if kind == "interior" else exterior
    geometry = getattr(project, f"{kind}_girder")
    analysis = getattr(module, f"solve_{kind}_girder_design")(geometry, project.materials, project.live_loads)
    reinforcement = getattr(module, f"design_{kind}_girder_reinforcement")(geometry, project.materials, analysis)
    selected = interior.custom_main_bar_placement_option(reinforcement.main.placement_options, '1"', 17)
    args = (geometry, project.materials, analysis, reinforcement, selected)
    return SimpleNamespace(
        kind=kind, geometry=geometry, reinforcement=reinforcement, selected=selected,
        analysis=analysis,
        service=getattr(module, f"verify_{kind}_girder_service_stresses")(*args),
        crack=getattr(module, f"review_{kind}_girder_crack_control")(*args).main,
        fatigue=getattr(module, f"review_{kind}_girder_fatigue")(*args),
    )


def test_multilayer_service_and_fatigue_use_one_effective_depth(project, girder_case):
    case = girder_case
    d = case.selected.effective_depth_cm
    assert case.selected.layers == 3
    # Six bars in each full layer and five in the last: area-weighted centroid.
    assert d == pytest.approx(110 - (6*6.27 + 6*13.762 + 5*21.254)/17)
    n = round(project.materials.steel.elastic_modulus_kg_cm2 / project.materials.concrete.elastic_modulus_kg_cm2)
    n_as = n * 85.0
    width = case.geometry.tributary_width_m * 100.0
    # Independent closed-form equilibrium, including a neutral axis below the flange.
    x = (sqrt(n_as**2 + 2 * width * n_as * d) - n_as) / width
    flange = case.geometry.slab_thickness_m * 100.0
    if x <= flange:
        concrete_inertia = width * x**3 / 3
    else:
        web = case.geometry.web_width_m * 100
        linear = width * flange + n_as
        constant = width * flange**2 / 2 - n_as * (d - flange)
        web_depth = (sqrt(linear**2 - 2*web*constant) - linear) / web
        x = flange + web_depth
        concrete_inertia = width * flange**3 / 12 + width * flange * (x-flange/2)**2 + web * web_depth**3 / 3
    inertia = concrete_inertia + n_as * (d - x)**2
    assert case.service.section.inertia_cm4 == pytest.approx(inertia)
    assert case.service.section.neutral_axis_depth_cm == pytest.approx(x)
    assert case.service.steel_tension_kg_cm2 == pytest.approx(n * case.service.service_moment_tn_m * 100000 * (d - x) / inertia)
    assert case.fatigue.section.inertia_cm4 == pytest.approx(inertia)
    assert case.fatigue.stress_range_kg_cm2 == pytest.approx(n * case.fatigue.fatigue_moment_tn_m * 100000 * (d - x) / inertia)
    assert case.fatigue.status == "CUMPLE"
    expected_stress = n * case.service.service_moment_tn_m * 100000 * (d-x) / inertia
    assert case.service.steel_status == (
        "CUMPLE" if expected_stress <= .60 * project.materials.steel.yield_strength_kg_cm2 else "NO CUMPLE")


def test_girder_cracking_and_report_match_service_section(girder_case):
    case = girder_case
    assert case.crack.steel_stress_kg_cm2 == case.service.steel_tension_kg_cm2
    assert case.crack.effective_depth_cm == case.selected.effective_depth_cm
    assert case.crack.section_inertia_cm4 == case.service.section.inertia_cm4
    assert case.crack.stress_status == case.service.steel_status
    # dc is still the cover to the nearest bar, not the centroid of all layers.
    assert case.crack.dc_cm == pytest.approx(5 + 2.54 / 2)
    trace = crack_control_trace(case.crack)
    assert "fs = n" in trace[1]
    assert "96.68 cm" in trace[2]
    assert "103.73" not in trace[2]
    assert case.crack.status in trace[3]


def test_exterior_distribution_factor_is_refreshed_after_layout_normalization(project):
    stale = replace(project.exterior_girder, exterior_web_to_traffic_barrier_m=-0.25).with_distribution_factors(project.live_loads.vehicular)
    assert stale.live_load_distribution_factor_g == pytest.approx(0.6453125)
    layout = replace(project.transverse_slab.load_layout, barrier_left_m=1.0, sidewalk_width_m=1.0)
    changed = replace(project, exterior_girder=stale, transverse_slab=replace(project.transverse_slab, load_layout=layout))
    geometry = changed.exterior_girder
    assert geometry.exterior_web_to_traffic_barrier_m == pytest.approx(-0.375)
    assert geometry.live_load_distribution_factor_g == pytest.approx(0.62578125)
    # A direct report call must also ignore a stale cached factor.
    direct_stale = replace(geometry, live_load_distribution_factor_g=stale.live_load_distribution_factor_g)
    trace = " ".join(exterior_g_factor_trace(direct_stale, project.live_loads.vehicular))
    assert "gM = max(...) = 0.62578" in trace
    assert "0.64531" not in trace


def test_girder_shear_keeps_pedestrians_separate(project, girder_case):
    designer = (exterior.design_exterior_girder_shear if girder_case.kind == "exterior"
                else interior.design_interior_girder_shear)
    shear = designer(
        girder_case.geometry, project.materials, girder_case.analysis, girder_case.reinforcement,
    )
    row = shear.controlling_shear
    if girder_case.kind == "exterior":
        assert row.pl_shear_tn > 0
        assert row.pl_factor == 1.75
    else:
        assert row.pl_shear_tn == 0
    assert row.combined_shear_tn == pytest.approx(
        row.dc_factor * row.dc_shear_tn + row.dw_factor * row.dw_shear_tn
        + row.ll_im_factor * row.ll_im_shear_tn + row.pl_factor * row.pl_shear_tn
    )


@pytest.fixture(scope="module")
def slab_case(project):
    geometry = project.transverse_slab.geometry
    analysis = solve_transverse_slab_design(geometry, project.materials, project.live_loads, project.transverse_slab.load_layout)
    reinforcement = design_transverse_slab_reinforcement(geometry, project.materials, analysis)
    return geometry, analysis, reinforcement


def test_slab_recommendations_pass_cracking_without_overriding_custom_steel(project, slab_case):
    geometry, analysis, reinforcement = slab_case
    review = review_transverse_slab_crack_control(geometry, project.materials, analysis, reinforcement)
    assert review.negative_main.is_compliant
    assert review.positive_main.is_compliant
    three_quarter = next(option for option in reinforcement.negative.spacing_options.options if option.bar.label == '3/4"')
    assert three_quarter.spacing_m == pytest.approx(0.225)
    assert three_quarter.crack_control_status == "CUMPLE"
    selected = custom_spacing_option(reinforcement.negative.spacing_options, '3/4"', 0.25)
    adopted_review = review_transverse_slab_crack_control(
        geometry, project.materials, analysis, reinforcement, negative_spacing=selected,
    )
    assert selected.spacing_m == 0.25
    assert adopted_review.negative_main.spacing_status == "NO CUMPLE"
    for steel in (reinforcement.negative, reinforcement.positive):
        option = steel.spacing_options.recommended
        assert steel.effective_depth_cm == pytest.approx(20 - 5 - option.bar.diameter_cm / 2)
        assert option.provided_area_cm2_m >= option.required_area_cm2_m
        for candidate in steel.spacing_options.options:
            if candidate.is_compliant:
                custom = custom_spacing_option(steel.spacing_options, candidate.bar.label, candidate.spacing_m)
                assert custom.required_area_cm2_m == candidate.required_area_cm2_m


def test_slab_leaves_recommendation_empty_when_no_candidate_passes_service(project, slab_case, monkeypatch):
    from bridge_design.domain import crack_control
    geometry, analysis, _ = slab_case
    monkeypatch.setattr(crack_control, "review_slab_spacing_crack_control", lambda *args, **kwargs: SimpleNamespace(
        is_compliant=False, status="NO CUMPLE",
    ))
    reinforcement = design_transverse_slab_reinforcement(geometry, project.materials, analysis)
    for steel in (reinforcement.negative, reinforcement.positive):
        assert steel.spacing_options.recommended is None
        assert all(not option.is_recommended for option in steel.spacing_options.options)


def test_slab_never_marks_failing_candidate_recommended(project, slab_case):
    geometry, analysis, _ = slab_case
    reinforcement = design_transverse_slab_reinforcement(
        geometry, project.materials, analysis,
        SlabReinforcementParameters(minimum_spacing_m=0.30, maximum_spacing_m=0.30),
    )
    for steel in (reinforcement.negative, reinforcement.positive):
        for option in steel.spacing_options.options:
            if option.is_recommended:
                assert option.is_compliant and option.crack_control_status == "CUMPLE"


@pytest.fixture(scope="module")
def diaphragm_case():
    from test_diaphragm import _geometry, _materials, _layout
    from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel
    geometry, materials, layout = _geometry(), _materials(), _layout()
    analysis = solve_diaphragm_design(geometry, materials, LiveLoads(PedestrianLoad.mtc_sidewalk_default(), VehicleLoadModel.mtc_hl93_default()), layout)
    reinforcement = design_diaphragm_reinforcement(geometry, materials, analysis)
    return geometry, analysis, reinforcement


def test_diaphragm_shear_and_low_demand_exception_are_reported(diaphragm_case):
    geometry, analysis, reinforcement = diaphragm_case
    shear = reinforcement.shear
    row = shear.controlling_shear
    source = max(combine_diaphragm_shears(analysis), key=lambda candidate: candidate.combined_shear_tn)
    assert row.ll_im_shear_tn == source.ll_im_shear_tn
    assert row.pl_shear_tn == source.pl_shear_tn
    assert row.pl_factor == source.pl_factor
    assert row.combined_shear_tn == source.combined_shear_tn
    assert not shear.transverse_required
    assert shear.recommended.provided_av_cm2_m < shear.minimum_av_cm2_m
    trace = _sectional_shear_calc_fields(shear, shear.recommended)
    assert "0.5" in trace[2]
    assert "no activa" in trace[4]
    assert f"x={row.position_m:.3f}" in trace[4]
    assert "distancia dv" not in trace[4]


def test_diaphragm_ask_is_kept_for_custom_and_legacy_report_inputs(diaphragm_case):
    _, _, reinforcement = diaphragm_case
    legacy = diaphragm_selection_with_skin(reinforcement, ())
    assert legacy[0][1] == reinforcement.skin.spacing_options.recommended
    custom = custom_spacing_option(reinforcement.skin.spacing_options, '1/2"', 0.125)
    selected = (("E. Ask longitudinal por cara", custom),)
    assert diaphragm_selection_with_skin(reinforcement, selected) == selected


def test_diaphragm_pdf_uses_selected_ask_and_actual_station(diaphragm_case, monkeypatch):
    from bridge_design.reporting.deck_sections_components import diaphragm_story
    from bridge_design.reporting.pdf_style import report_styles
    from bridge_design.reporting import deck_sections_components
    geometry, analysis, reinforcement = diaphragm_case
    custom = custom_spacing_option(reinforcement.skin.spacing_options, '1/2"', 0.125)
    data = SimpleNamespace(
        project_inputs=SimpleNamespace(diaphragm=geometry), diaphragm_result=analysis,
        diaphragm_reinforcement=reinforcement, diaphragm_selected=(("E. Ask", custom),),
    )
    monkeypatch.setattr(deck_sections_components, "moment_shear_pair", lambda *args, **kwargs: [])
    story = diaphragm_story(data, report_styles())
    # formula_card returns a table whose cells contain Paragraphs.
    def texts(item):
        if hasattr(item, "text"):
            yield item.text
        for child in getattr(item, "_content", ()):
            yield from texts(child)
        for child in getattr(item, "_cellvalues", ()):
            for cell in child:
                for entry in cell if isinstance(cell, (tuple, list)) else (cell,):
                    yield from texts(entry)
    text = " ".join(part for item in story for part in texts(item))
    assert "0.125 m" in text
    assert f"x={reinforcement.shear.controlling_shear.position_m:.3f} m" in text
    assert "no se exige el minimo" in text
