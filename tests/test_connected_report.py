from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from bridge_design.domain.connected_design import solve_connected_abutments
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil
from bridge_design.reporting.connected_charts import save_connected_charts
from bridge_design.reporting.connected_docx import write_connected_docx


def test_connected_memory_preserves_inputs_results_and_correct_header(tmp_path):
    inputs = ConnectedInputs(FoundationSoil(3000, 0.50, 26.7), mesh_size_m=1.0,
                             include_without_bridge=False)
    result = solve_connected_abutments(inputs)
    charts = save_connected_charts(result, tmp_path)
    destination = write_connected_docx(result, tmp_path / "memoria.docx", charts)
    document = Document(destination)
    paragraphs = "\n".join(paragraph.text for paragraph in document.paragraphs)
    tables = "\n".join(cell.text for table in document.tables for row in table.rows for cell in row.cells)
    assert "ESTRIBOS CONECTADOS" in document.sections[0].header.paragraphs[0].text
    assert "TABLERO DE PUENTE" not in document.sections[0].header.paragraphs[0].text
    assert "Módulo de balasto vertical" in tables
    assert "3000.000 Tn/m³" in tables
    assert "Longitud horizontal de cajuela" in tables
    assert "PENDIENTE DETALLE" in paragraphs
    assert result.results[-1].name in paragraphs
    assert len(document.inline_shapes) == 5
    assert "Envolvente axial N sobre la estructura completa" in paragraphs
    assert "Envolvente de cortante V sobre la estructura completa" in paragraphs
    assert "Envolvente de momento M sobre la estructura completa" in paragraphs
    assert "Envolventes N V M del estribo" not in paragraphs
    section = document.sections[0]
    assert round(section.page_width.mm) == 210
    assert round(section.page_height.mm) == 297
    assert abs(section.left_margin.mm - 25.4) < 0.05
    title = next(paragraph for paragraph in document.paragraphs if paragraph.style.name == "Title")
    assert title.alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert title.style.element.get_or_add_pPr().find(qn("w:pBdr")) is None
    assert all(run.font.size.pt == 22 for run in title.runs)
    assert "Contenido" in paragraphs
    assert "8. Cuadro de detalle y resumen del diseño adoptado" in paragraphs
    assert "9. Referencias normativas" in paragraphs
    assert "Reemplazando los valores correspondientes:" in paragraphs
    for paragraph in document.paragraphs:
        if paragraph.style.name == "Title":
            continue
        if paragraph.text.strip():
            assert paragraph.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY
        assert paragraph.paragraph_format.line_spacing == 1.5
        assert all(run.font.name == "Arial Narrow" and run.font.size.pt == 11 for run in paragraph.runs)
    assert all(table.rows[0]._tr.trPr.find(qn("w:tblHeader")) is not None for table in document.tables)
    assert any(table.cell(0, 0).text == "Acción" and len(table.columns) == 5 for table in document.tables)
    assert all(steel.area_per_face_cm2_m >= steel.temperature_cm2_m for steel in result.reinforcement)
    failed = [steel for steel in result.reinforcement if steel.status != "OK"]
    assert failed
    assert "NO CUMPLE" in tables
    assert all(max(steel.axial_moment_utilization, steel.shear_utilization,
                   steel.crack_utilization) > 1 for steel in failed)
