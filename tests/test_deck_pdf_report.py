from __future__ import annotations

import builtins
from pathlib import Path

from bridge_design.main import run_bridge_design
from bridge_design.reporting import deck_pdf
from test_ascii_output import _project_inputs


def generate_sample_report(output_path: Path) -> Path:
    """Run the real deck workflow with every recommended reinforcement option."""
    original_input = builtins.input
    original_selector = deck_pdf.select_deck_pdf_save_path
    builtins.input = lambda _prompt="": ""
    deck_pdf.select_deck_pdf_save_path = lambda: output_path
    try:
        run_bridge_design(_project_inputs())
    finally:
        builtins.input = original_input
        deck_pdf.select_deck_pdf_save_path = original_selector
    return output_path


def test_deck_command_generates_complete_a4_pdf_automatically(tmp_path) -> None:
    output = generate_sample_report(tmp_path / "memoria_tablero.pdf")
    payload = output.read_bytes()

    assert payload.startswith(b"%PDF-")
    assert len(payload) > 50_000
    assert payload.count(b"/Type /Page") >= 8
    assert b"ArialNarrow" in payload


def test_cancelled_save_dialog_does_not_write_a_report(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(deck_pdf, "select_deck_pdf_save_path", lambda: None)
    assert deck_pdf.generate_deck_pdf_with_dialog(object()) is None
    assert list(tmp_path.iterdir()) == []
