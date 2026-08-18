"""Generate the complete A4 PDF report for ``diseno-tablero``."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.platypus import PageBreak

from bridge_design.reporting.deck_appendix import audit_appendix
from bridge_design.reporting.deck_sections_components import (
    barrier_story,
    cantilever_story,
    diaphragm_story,
    reactions_story,
)
from bridge_design.reporting.deck_sections_primary import (
    cover_story,
    girder_story,
    input_story,
    slab_story,
)
from bridge_design.reporting.models import DeckReportData
from bridge_design.reporting.pdf_style import (
    DeckReportDocument,
    page_frame,
    register_arial_narrow,
    report_styles,
)


def generate_deck_pdf(data: DeckReportData, output_path: str | Path) -> Path:
    """Write the complete calculation report and return its absolute path."""
    path = Path(output_path).expanduser().resolve()
    if path.suffix.lower() != ".pdf":
        path = path.with_suffix(".pdf")
    path.parent.mkdir(parents=True, exist_ok=True)
    register_arial_narrow()
    styles = report_styles()
    story = []
    story.extend(cover_story(data, styles))
    story.extend(input_story(data, styles))
    story.extend(slab_story(data, styles))
    story.append(PageBreak())
    story.extend(girder_story(data, styles, exterior=False))
    story.extend(girder_story(data, styles, exterior=True))
    story.extend(barrier_story(data, styles))
    story.extend(cantilever_story(data, styles))
    story.extend(diaphragm_story(data, styles))
    story.extend(reactions_story(data, styles))
    if data.audit_sections:
        story.append(PageBreak())
        story.extend(audit_appendix(data.audit_sections, styles))
    document = DeckReportDocument(str(path))
    document.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return path


def select_deck_pdf_save_path() -> Path | None:
    """Open a native save dialog and return the selected PDF path."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise RuntimeError("Tkinter no esta disponible para seleccionar el destino del PDF.") from exc
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    default_name = f"MEMORIA_CALCULO_TABLERO_{datetime.now():%Y%m%d_%H%M}.pdf"
    try:
        selected = filedialog.asksaveasfilename(
            parent=root,
            title="Guardar memoria de calculo del tablero",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=(("Documento PDF", "*.pdf"),),
        )
    finally:
        root.destroy()
    return Path(selected) if selected else None


def generate_deck_pdf_with_dialog(data: DeckReportData) -> Path | None:
    """Ask for a destination and generate the report when one is selected."""
    path = select_deck_pdf_save_path()
    if path is None:
        print("Generacion del reporte PDF cancelada por el usuario.")
        return None
    generated = generate_deck_pdf(data, path)
    print(f"Reporte PDF guardado en: {generated}")
    return generated
