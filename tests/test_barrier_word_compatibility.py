"""The barrier's published operations must reproduce compatible resistance."""

from dataclasses import replace
import re

import pytest
from docx import Document

from bridge_design.domain.barrier import BarrierDesignInputs, design_concrete_barrier
from bridge_design.domain.concrete_flexure import rectangular_flexural_response
from bridge_design.reporting import deck_docx as word
from bridge_design.reporting.deck_docx_detail import barrier_mw_mc_trace
from test_barrier import _materials


@pytest.mark.parametrize("area", (1.775, 20.0))
@pytest.mark.parametrize("spacing", (.17, .025))
@pytest.mark.parametrize("modulus", (1_000_000., 2_000_000.))
def test_barrier_word_uses_compatible_stress_for_mw_and_mc(area, spacing, modulus):
    materials = _materials()
    materials = replace(materials, steel=replace(materials.steel, elastic_modulus_kg_cm2=modulus))
    inputs = BarrierDesignInputs()
    section = inputs.section_model
    inputs = replace(inputs, section_model=replace(section, dowel_spacing_m=spacing,
        mw_segments=(replace(section.mw_segments[0], steel_area_cm2=area), *section.mw_segments[1:])))
    result = design_concrete_barrier(inputs, materials)
    trace = barrier_mw_mc_trace(result.flexure, materials.concrete, materials.steel)
    assert "As·fs" in trace[0] and "As·fy" not in trace[0]
    components = (*result.flexure.mw_components, *result.flexure.mc_components)
    operations = [line for line in trace[2].splitlines() if line.startswith("Mn = ")]
    assert len(operations) == len(components)
    for component, operation in zip(components, operations):
        response = rectangular_flexural_response(component.steel_area_cm2, component.concrete_width_cm,
            component.effective_depth_cm, materials.concrete.compressive_strength_kg_cm2,
            materials.steel.yield_strength_kg_cm2, modulus)
        assert f"·{response.steel_stress_kg_cm2:.3f}·" in operation
        assert f"= {component.nominal_moment_tn_m:.3f}" in operation
        # Evaluate the actual rounded numbers printed in Word, not just its result.
        match = re.fullmatch(r"Mn = ([\d.]+)·([\d.]+)·\(([\d.]+) − ([\d.]+)/2\)/100000 = ([\d.]+) Tn·m(?:/m)?", operation)
        assert match is not None
        as_printed, stress, depth, block, moment = map(float, match.groups())
        assert as_printed * stress * (depth-block/2) / 100000 == pytest.approx(moment, abs=.002)
    if area == 20:
        assert "NO FLUYE" in trace[2]
    if area == 20 and modulus == 2_000_000:
        assert result.flexure.mw_components[0].nominal_moment_tn_m == pytest.approx(5.000219317877121)
        assert "3260.049" in trace[2]
    doc = Document()
    word._configure_document(doc)
    word._calc(doc, "Resistencia de barrera", *trace, "Modelo del programa")
    xml_text = "".join(doc.element.xpath('//*[local-name()="t"]/text()'))
    assert f"Mw = {result.flexure.mw_tn_m:.3f}" in xml_text
    assert f"Mc = {result.flexure.mc_tn_m:.3f}" in xml_text
    assert result == design_concrete_barrier(inputs, materials)  # report never changes the engine
