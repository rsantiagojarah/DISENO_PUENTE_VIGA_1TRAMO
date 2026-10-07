from __future__ import annotations

import builtins
from pathlib import Path
from types import SimpleNamespace

from lxml import etree

from bridge_design.main import run_bridge_design
from bridge_design.reporting import deck_docx
from test_ascii_output import _project_inputs


def test_legend_items_preserve_semicolons_inside_equations() -> None:
    legend = (
        "γe: factor de exposición (1.0 ambiente normal); "
        "fss = min(fs,real; 0.60·fy) para la ecuación de separación."
    )

    assert deck_docx._legend_items(legend) == (
        "γe: factor de exposición (1.0 ambiente normal)",
        "fss = min(fs,real; 0.60·fy) para la ecuación de separación",
    )


def generate_sample_report(output_path: Path) -> Path:
    """Run the real deck workflow with every recommended reinforcement option."""
    original_input = builtins.input
    original_selector = deck_docx.select_deck_docx_save_path
    builtins.input = lambda _prompt="": ""
    deck_docx.select_deck_docx_save_path = lambda: output_path
    try:
        run_bridge_design(_project_inputs())
    finally:
        builtins.input = original_input
        deck_docx.select_deck_docx_save_path = original_selector
    return output_path


def test_deck_command_generates_detailed_word_memory_automatically(tmp_path) -> None:
    output = generate_sample_report(tmp_path / "memoria_tablero.docx")
    payload = output.read_bytes()

    assert payload.startswith(b"PK")
    assert len(payload) > 100_000
    assert b"word/document.xml" in payload

    from zipfile import ZipFile

    with ZipFile(output) as package:
        document_xml = package.read("word/document.xml")
        xml = document_xml.decode("utf-8")
        styles = package.read("word/styles.xml").decode("utf-8")
    assert "Para desarrollar esta verificación se emplea la siguiente expresión" in xml
    assert "Reemplazando los valores correspondientes" in xml
    assert "Donde:" in xml
    assert "Por lo tanto" in xml
    assert "H34:" not in xml
    assert "Comentario técnico" not in xml
    assert "Referencia normativa" in xml
    assert "páginas PDF" not in xml
    assert "página PDF" not in xml
    for operational_text in (
        "selección personalizada del usuario", "este módulo", "módulo receptor",
        "Archivo de consulta", "carpeta docs", "Archivo: docs/", "PENDIENTE",
        "antes de emitir", "deberían continuarse", "altura ingresada",
        "sustitucion automatica", "requiere el modelo global", "no certifica",
    ):
        assert operational_text not in xml
    assert "m:oMath" in xml
    assert "m:f" in xml
    assert "Cargas permanentes distribuidas sobre la viga" in xml
    assert "Peralte resistente de la viga principal interior" in xml
    assert "Peralte resistente de la viga principal exterior" in xml
    assert "Máx. apoyo izquierdo (Tn)" in xml
    assert "envolventes locales independientes de reacción máxima" in xml
    assert "31.146" in xml
    assert "21.963" in xml
    assert "Vn,max" in xml
    assert "φVn,max" in xml
    assert "0.25 f'c bv dv" in xml
    assert "Resistencia nominal por líneas de fluencia" in xml
    assert "resistencia flexional de la pared como voladizo respecto de su base" in xml
    assert "ASTM A615 Grado 60" in xml
    assert "Mobjetivo" in xml
    assert "FLUYE" in xml
    assert "La compatibilidad confirma que el acero requerido fluye" in xml
    assert "Arial Narrow" in styles
    assert 'w:sz w:val="22"' in styles
    assert 'w:sz w:val="44"' in xml
    assert 'w:color w:val="000000"' in styles
    assert 'w:line="360"' in styles
    assert 'w:top="1440"' in xml
    assert 'w:right="1440"' in xml
    assert 'w:bottom="1440"' in xml
    assert 'w:left="1440"' in xml

    root = etree.fromstring(document_xml)
    namespaces = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    }
    equation_lines = [
        "".join(paragraph.xpath(".//m:t/text()", namespaces=namespaces))
        for paragraph in root.xpath("//w:p[m:oMath]", namespaces=namespaces)
    ]
    assert "E₊ = 0.660 + 0.55·S" in equation_lines
    assert "E₋ = 1.220 + 0.25·S" in equation_lines
    assert equation_lines.count("h = 1.200 + 0.200 = 1.400 m") >= 2
    assert sum(line.startswith("d = 140.00 − 5.00 − 2.540") and line.endswith("= 133.73 cm") for line in equation_lines) >= 2
    assert any(line.startswith("E₊ = 0.660 + 0.55·2.100") for line in equation_lines)
    assert any(line.startswith("E₋ = 1.220 + 0.25·2.100") for line in equation_lines)
    assert not any("E₊" in line and "E₋" in line for line in equation_lines)
    assert any("min[67; 3840/" in line for line in equation_lines)
    assert "Rw = 2·[k·Mb + k·Mw + Mc·Lc²/H](2·Lc − Lt)" in equation_lines
    assert any(line.startswith("Rw = 2·[8·") and line.endswith("= 28.232 Tn") for line in equation_lines)
    assert any(line.startswith("Mcr = γ3·γ1·fr·S") for line in equation_lines)
    assert any(line.startswith("1.33·Mu = 1.33·") for line in equation_lines)
    assert any(line.startswith("εy = 4200 ÷ 2000000") for line in equation_lines)
    assert any("εs,prov" in line and "FLUYE" in line for line in equation_lines)


def test_cancelled_save_dialog_does_not_write_a_report(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(deck_docx, "select_deck_docx_save_path", lambda: None)
    assert deck_docx.generate_deck_docx_with_dialog(object()) is None
    assert list(tmp_path.iterdir()) == []


def test_formal_deck_text_preserves_custom_steel_and_failed_checks() -> None:
    option = SimpleNamespace(is_custom=True, is_compliant=False, bar_count=4,
                             bar_label='1"', layers=2, provided_area_cm2=20.0)
    assert deck_docx._option_text(option) == '4 barras de 1" distribuidas en 2 capas, As = 20.000 cm²'
    assert deck_docx._option_status(option) == "REVISAR"
    assert "no cumple" in deck_docx._compliance_comment(option, "CUMPLE")
    assert not deck_docx._looks_compliant(deck_docx._status_comment("NO CUMPLE", "CUMPLE"))


def test_shared_deck_notes_describe_only_the_calculated_scope() -> None:
    from bridge_design.reporting.deck_report_notes import (
        formal_cantilever_notes, formal_interior_collision_notes,
    )

    result = SimpleNamespace(applicability_notes=(
        "Colision local de barrera sobre voladizo: NO APLICABLE. PENDIENTE: verificar transferencia.",
        "Demanda de barrera conservada: Ft=25.000 Tn; Anclaje: NO CUMPLE.",
    ))
    notes = formal_cantilever_notes(result)
    assert "acciones directas" in notes[0]
    assert notes[1] == result.applicability_notes[1]
    assert "PENDIENTE" not in " ".join(notes)
    collision = SimpleNamespace(notes=(
        "Armadura indicada: minimo TOTAL por colision. Adoptar la MAYOR demanda.",
        "Alcance: transferencia LOCAL; requiere el modelo global.",
    ))
    notes = formal_interior_collision_notes(collision)
    assert "minimo total por colision" in notes[0]
    assert "transferencia local barrera-losa" in notes[1]


def test_formal_pdf_appendix_retains_numerical_rows_and_failed_results() -> None:
    from bridge_design.reporting.deck_report_notes import formal_audit_line
    from bridge_design.reporting.deck_appendix import audit_appendix
    from bridge_design.reporting.pdf_style import report_styles

    row = "  | Viga interior | Mu=125.000 | Mr=100.000 | NO CUMPLE |"
    assert formal_audit_line(row) == row
    note = "Alcance: transferencia LOCAL barrera-losa. La distribucion horizontal requiere el modelo global."
    assert "transferencia local barrera-losa" in formal_audit_line(note)
    assert "requiere" not in formal_audit_line(note)
    story = audit_appendix((("Viga interior", row + "\n\n" + note),), report_styles())
    assert story
    assert "motor" not in story[1].getPlainText()
    assert "verificaciones de servicio, fatiga, desarrollo" in story[1].getPlainText()
