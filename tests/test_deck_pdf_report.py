from __future__ import annotations

import builtins
from pathlib import Path

from bridge_design.main import run_bridge_design
from bridge_design.reporting import deck_docx
from test_ascii_output import _project_inputs


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
        xml = package.read("word/document.xml").decode("utf-8")
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
    assert "Arial Narrow" in styles
    assert 'w:sz w:val="22"' in styles
    assert 'w:sz w:val="44"' in xml
    assert 'w:color w:val="000000"' in styles
    assert 'w:line="360"' in styles
    assert 'w:top="1440"' in xml
    assert 'w:right="1440"' in xml
    assert 'w:bottom="1440"' in xml
    assert 'w:left="1440"' in xml


def test_cancelled_save_dialog_does_not_write_a_report(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(deck_docx, "select_deck_docx_save_path", lambda: None)
    assert deck_docx.generate_deck_docx_with_dialog(object()) is None
    assert list(tmp_path.iterdir()) == []
