from dataclasses import replace

import pytest

from bridge_design.domain.barrier import BarrierDesignInputs, design_concrete_barrier
from bridge_design.domain.cantilever_slab import design_cantilever_slab
from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel
from bridge_design.domain.transverse_slab import PointMoment, solve_load_case
from bridge_design.domain.reinforcement import flexural_steel_area_cm2
from test_cantilever_slab import _geometry, _layout, _materials


def _result(level="TL-4", overhang=1.0):
    g = replace(_geometry(), overhang_m=overhang, girder_spacing_m=2.56,
                girder_width_m=.5, girder_count=5)
    layout = replace(_layout(), barrier_left_m=overhang+.7, barrier_width_m=.375)
    inputs = BarrierDesignInputs()
    inputs = replace(inputs, impact_load=replace(inputs.impact_load, test_level=level))
    barrier = design_concrete_barrier(inputs, _materials())
    live = LiveLoads(PedestrianLoad.mtc_sidewalk_default(), VehicleLoadModel.mtc_hl93_default())
    return g, design_cantilever_slab(g, _materials(), live, layout, barrier), barrier


def test_point_couple_matches_simply_supported_closed_form():
    g = replace(_geometry(), girder_count=2, overhang_m=0, girder_spacing_m=4)
    result = solve_load_case(g, _materials(), "couple", (), (),
                             point_moments=(PointMoment(1.5, 8, "couple"),))
    assert [r for _, r in result.support_reactions_tn] == pytest.approx([2, -2])
    assert [m for x, m in result.moment_samples_tn_m if x == 1.5] == pytest.approx([3, -5])
    assert result.moment_samples_tn_m[-1][1] == pytest.approx(0, abs=1e-10)


def test_interior_cases_conserve_equilibrium_and_mirror_without_combining():
    _, result, barrier = _result()
    local = result.interior_collision
    assert result.barrier_collision is None
    assert len(local.cases) == 8
    assert local.transfer_length_m == pytest.approx(barrier.yield_line.critical_length_m + 2*barrier.geometry.height_m)
    assert local.interface_moment_tn_m_m == pytest.approx(barrier.flexure.mc_tn_m)
    for case in local.cases:
        assert abs(case.vertical_equilibrium_error_tn_m) < 1e-9
        assert abs(case.moment_equilibrium_error_tn_m_m) < 1e-9
        if "vertical" in case.name:
            assert case.axial_tension_tn_m == case.applied_moment_tn_m_m == 0
        else:
            assert case.applied_vertical_tn_m == 0
            assert case.axial_tension_tn_m > 0
    for left, right in zip(local.cases[:4], local.cases[4:]):
        assert [r for _, r in left.reactions_tn_m] == pytest.approx([r for _, r in reversed(right.reactions_tn_m)])
    assert "PENDIENTE: verificar transferencia" not in " ".join(result.applicability_notes)
    assert not result.overall_ok  # A local strip cannot certify the global bridge.


def test_vertical_collision_uses_test_level_not_default():
    _, tl4, _ = _result()
    _, tl5, _ = _result("TL-5")
    v4 = tl4.interior_collision.cases[1].applied_vertical_tn_m
    v5 = tl5.interior_collision.cases[1].applied_vertical_tn_m
    assert v5/v4 == pytest.approx((80/40)/(18/18))


def test_selected_steel_is_verified_with_its_actual_diameter():
    g, result, _ = _result()
    for face in result.interior_collision.faces:
        option = face.option
        assert option is not None
        d = 100*g.slab_thickness_m - result.parameters.concrete_cover_cm - option.bar.diameter_cm/2
        required = flexural_steel_area_cm2(face.moment_tn_m_m, 100, d, 280, 4200, phi=.9)
        required += face.tension_tn_m*1000/(.75*4200)
        assert option.provided_area_cm2_m >= required
        if face.development_length_m > face.development_available_m:
            assert face.status == "NO CUMPLE"


def test_report_contains_demands_steel_reactions_and_real_status():
    from bridge_design.cli.ascii_output import format_cantilever_slab_design_result
    _, result, _ = _result()
    text = format_cantilever_slab_design_result(result)
    for expected in (
        "TRANSFERENCIA DE COLISION A LOSA INTERIOR",
        "Acero transversal requerido por colision",
        "Reacciones verticales incrementales",
        "As req",
        "ld req",
        "Conexion barrera-losa",
        "Resultado local:",
    ):
        assert expected in text
    applicability = text.split("Notas de aplicabilidad:", 1)[1]
    assert "EEII horizontal" not in applicability


def test_unknown_level_is_rejected_instead_of_assuming_tl4():
    with pytest.raises(ValueError, match="Nivel de ensayo"):
        _result("unknown")


def test_capacity_anchorage_does_not_reuse_reduced_barrier_check():
    _, result, barrier = _result()
    hook = barrier.development
    full = max(hook.minimum_ldh_cm, hook.modified_ldh_cm/hook.excess_reinforcement_factor)
    if hook.available_length_cm < full:
        assert result.interior_collision.connection_status == "NO CUMPLE"
        assert result.interior_collision.status == "NO CUMPLE"


def test_word_and_pdf_sections_include_interior_transfer():
    from types import SimpleNamespace
    from docx import Document
    from bridge_design.reporting.deck_docx import _cantilever, _configure_document
    from bridge_design.reporting.deck_sections_components import cantilever_story
    from bridge_design.reporting import pdf_style
    g, result, _ = _result()
    data = SimpleNamespace(cantilever_result=result, cantilever_selected=(),
        cantilever_crack=result.crack_control, cantilever_development=result.development,
        project_inputs=SimpleNamespace(transverse_slab=SimpleNamespace(geometry=g), materials=_materials()))
    document = Document()
    _configure_document(document)
    _cantilever(document, data)
    text = document._element.xml
    assert "Transferencia local a la losa interior" in text
    assert "Control" in text
    assert "Acero transversal por colisión" in text
    # Use the production style factory rather than mocking report paragraphs.
    story = cantilever_story(data, pdf_style.report_styles())
    paragraphs = " ".join(getattr(item, "text", "") for item in story)
    assert "Transferencia de colision a la losa interior" in paragraphs
    assert "Acero transversal requerido por colision" in paragraphs
