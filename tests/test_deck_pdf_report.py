from __future__ import annotations

import builtins
from pathlib import Path

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
    assert "Comentario técnico" not in xml
    assert "Referencia normativa" in xml
    assert "páginas PDF" not in xml
    assert "página PDF" not in xml
    assert "m:oMath" in xml
    assert "m:f" in xml
    assert "Cargas permanentes distribuidas sobre la viga" in xml
    assert "Vn,max" in xml
    assert "φVn,max" in xml
    assert "0.25 f'c bv dv" in xml
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
    assert any(line.startswith("E₊ = 0.660 + 0.55·2.100") for line in equation_lines)
    assert any(line.startswith("E₋ = 1.220 + 0.25·2.100") for line in equation_lines)
    assert not any("E₊" in line and "E₋" in line for line in equation_lines)
    assert any("min[67; 3840/" in line for line in equation_lines)


def test_cancelled_save_dialog_does_not_write_a_report(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(deck_docx, "select_deck_docx_save_path", lambda: None)
    assert deck_docx.generate_deck_docx_with_dialog(object()) is None
    assert list(tmp_path.iterdir()) == []
