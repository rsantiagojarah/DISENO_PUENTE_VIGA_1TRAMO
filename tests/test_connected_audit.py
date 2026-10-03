import pytest

from bridge_design.cli.connected_audit_output import format_connected_audit
from bridge_design.cli.connected_output import format_connected_result
from bridge_design.domain.abutment import _moment_resistance_tn_m
from bridge_design.domain.connected_design import solve_connected_abutments
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil
from bridge_design.domain.connected_reinforcement import SectionDemand, design_region
from bridge_design.domain.connected_steel_audit import region_audit
from bridge_design.reporting.connected_audit import build_connected_audit
from bridge_design.reporting.connected_steel_trace import steel_steps


@pytest.fixture(scope="module")
def analysis():
    return solve_connected_abutments(ConnectedInputs(FoundationSoil(3000, 0.5, 26.7),
                                      mesh_size_m=1.0, include_without_bridge=False))


@pytest.fixture(scope="module")
def audit(analysis):
    return build_connected_audit(analysis)


def test_load_trace_exactly_reconstructs_frame_applied_resultants(analysis):
    for case, result in zip(analysis.cases, analysis.results):
        assert case.load_trace
        reconstructed = tuple(sum(row[1] * row[column] for row in case.load_trace) for column in (2, 3, 4))
        assert reconstructed == pytest.approx(result.applied_resultant, abs=1e-7)
    assert any(row[1] < 0 for case in analysis.cases for row in case.load_trace)


def test_each_region_audit_matches_actual_design_indices(analysis, audit):
    for steel in analysis.reinforcement:
        trace = audit["steel"][steel.region]
        assert trace["flexure"]["flexure_ratio"] == pytest.approx(steel.flexural_utilization)
        assert trace["shear"]["shear_ratio"] == pytest.approx(steel.shear_utilization)
        assert trace["service"]["crack_ratio"] == pytest.approx(steel.crack_utilization)
        assert trace["temperature"]["required_as_cm2_m"] == pytest.approx(steel.temperature_cm2_m)
        assert steel.required_as_cm2_m == max(steel.flexural_as_cm2_m,
                                             steel.capacity_minimum_as_cm2_m, steel.temperature_cm2_m)


def test_audit_identifies_different_governing_cases_and_positions(analysis):
    demands = (
        SectionDemand("Flexion", "strength", 150, 0, 1, 50, 0, 0.1),
        SectionDemand("Corte", "extreme", 150, 0, 30, 1, 0, 0.8),
        SectionDemand("Servicio", "service", 150, 0, 1, 25, 0, 0.4),
    )
    steel = design_region(analysis.inputs, analysis.mesh, "Zapata izquierda", demands)
    trace = region_audit(analysis, steel, demands)
    assert trace["flexure"]["demand"]["case"] == "Flexion"
    assert trace["shear"]["demand"]["case"] == "Corte"
    assert trace["service"]["demand"]["case"] == "Servicio"
    assert trace["flexure"]["x"] != trace["shear"]["x"]


def test_required_steel_is_inversion_of_the_actual_resistance(analysis, audit):
    for steel in analysis.reinforcement:
        trace = audit["steel"][steel.region]
        for row in trace["areas"]:
            capacity = _moment_resistance_tn_m(row["flexural_area"], 100, row["effective"],
                trace["concrete"], trace["yield_strength"], 0.90)
            assert capacity == pytest.approx(abs(row["demand"]["moment"]), rel=1e-6, abs=1e-7)


def test_contact_tables_reproduce_pressure_and_settlement_at_each_node(analysis, audit):
    for table, result in zip(audit["foundation"], analysis.results):
        for row, spring, reaction in zip(table.rows, analysis.mesh.frame.springs, result.spring_reactions):
            assert float(row[5]) == pytest.approx(reaction / spring.tributary_area, rel=1e-5)
            assert float(row[6]) == pytest.approx(-1000 * result.displacements[3 * spring.node + 1], rel=1e-5)


def test_terminal_contains_shared_formulas_substitutions_and_governing_sources(analysis, audit):
    output = format_connected_audit(analysis, audit)
    assert "4. DESARROLLO DEL DISENO DEL ACERO ADOPTADO" in output
    assert "secciones gobernantes independientes" in output
    assert "Sin longitud disponible no se aprueba el anclaje" in " ".join(output.replace("|", " ").split())
    assert "Mcr = 1.1*2.01" in output
    assert "N-M" not in output
    for steel in analysis.reinforcement:
        steps = tuple(steel_steps(steel, audit["steel"][steel.region]))
        assert len(steps) == 7
        assert all(step.formula and step.substitution and step.result and step.reference for step in steps)


def test_terminal_result_is_compact_and_keeps_decision_tables(analysis):
    output = format_connected_result(analysis)
    assert "CONTACTO Y ESTABILIDAD GLOBAL" in output
    assert "ARMADURA PRINCIPAL POR CARA" in output
    assert "TEMPERATURA Y DESARROLLO" in output
    assert "IDENTIFICACION DE COMBINACIONES" in output
    assert "Propiedades FRAME por elemento" not in output
    assert "Accion / lado" not in output
    assert "contacto, presion y asentamiento" not in output
    assert "DESARROLLO DEL DISENO DEL ACERO ADOPTADO" not in output


def test_word_equations_preserve_effective_depth_and_beta_grouping(analysis, audit):
    from docx import Document
    from bridge_design.reporting.deck_docx import _add_native_equation, _configure_document

    steel = analysis.reinforcement[0]
    steps = tuple(steel_steps(steel, audit["steel"][steel.region]))
    document = Document()
    _configure_document(document)
    depth = steps[0].formula.split(";")[0]
    paragraph = _add_native_equation(document, depth)
    assert "h - r - (db/2)" in "".join(paragraph._p.xpath(".//m:t/text()"))
    assert not paragraph._p.xpath(".//m:f")
    beta = next(expression for expression in steps[3].formula.split(";") if expression.strip().startswith("beta ="))
    paragraph = _add_native_equation(document, beta)
    fractions = paragraph._p.xpath(".//m:f")
    assert len(fractions) == 1
    assert "".join(paragraph._p.xpath(".//m:f/m:num//m:t/text()")) == "4.8*51"
    assert "".join(paragraph._p.xpath(".//m:f/m:den//m:t/text()")) == "((1+750*eps_s)*(39+sxe))"
