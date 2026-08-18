"""Professional Word and legacy PDF reports for bridge-design workflows."""

from bridge_design.reporting.abutment_docx import (
    generate_abutment_docx,
    generate_abutment_docx_with_dialog,
)

from bridge_design.reporting.deck_docx import (
    generate_deck_docx,
    generate_deck_docx_with_dialog,
)

from bridge_design.reporting.deck_pdf import (
    generate_deck_pdf,
    generate_deck_pdf_with_dialog,
)
from bridge_design.reporting.models import DeckReportData

__all__ = [
    "DeckReportData",
    "generate_abutment_docx",
    "generate_abutment_docx_with_dialog",
    "generate_deck_docx",
    "generate_deck_docx_with_dialog",
    "generate_deck_pdf",
    "generate_deck_pdf_with_dialog",
]
