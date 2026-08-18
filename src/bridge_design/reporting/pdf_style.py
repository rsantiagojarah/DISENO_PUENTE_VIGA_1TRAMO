"""A4 document theme and reusable ReportLab components."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#20262E")
MUTED = colors.HexColor("#64707D")
ACCENT = colors.HexColor("#1E596D")
PALE = colors.HexColor("#EAF1F3")
RULE = colors.HexColor("#B8C3C9")
WHITE = colors.white


def register_arial_narrow() -> str:
    """Register Arial Narrow and return the regular family name."""
    candidates = (
        (
            Path("C:/Windows/Fonts/ARIALN.TTF"),
            Path("C:/Windows/Fonts/ARIALNB.TTF"),
            Path("C:/Windows/Fonts/ARIALNI.TTF"),
            Path("C:/Windows/Fonts/ARIALNBI.TTF"),
        ),
    )
    for regular, bold, italic, bold_italic in candidates:
        if all(path.exists() for path in (regular, bold, italic, bold_italic)):
            if "ArialNarrow" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("ArialNarrow", str(regular)))
                pdfmetrics.registerFont(TTFont("ArialNarrow-Bold", str(bold)))
                pdfmetrics.registerFont(TTFont("ArialNarrow-Italic", str(italic)))
                pdfmetrics.registerFont(TTFont("ArialNarrow-BoldItalic", str(bold_italic)))
                pdfmetrics.registerFontFamily(
                    "ArialNarrow",
                    normal="ArialNarrow",
                    bold="ArialNarrow-Bold",
                    italic="ArialNarrow-Italic",
                    boldItalic="ArialNarrow-BoldItalic",
                )
            return "ArialNarrow"
    return "Helvetica"


def report_styles() -> dict[str, ParagraphStyle]:
    font = register_arial_narrow()
    bold = "ArialNarrow-Bold" if font == "ArialNarrow" else "Helvetica-Bold"
    italic = "ArialNarrow-Italic" if font == "ArialNarrow" else "Helvetica-Oblique"
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Title"], fontName=bold, fontSize=24,
            leading=27, textColor=INK, alignment=TA_LEFT, spaceAfter=8 * mm,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle", parent=base["Normal"], fontName=font, fontSize=12,
            leading=15, textColor=ACCENT, spaceAfter=4 * mm,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontName=bold, fontSize=15,
            leading=18, textColor=ACCENT, spaceBefore=5 * mm, spaceAfter=3 * mm,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName=bold, fontSize=11.5,
            leading=14, textColor=INK, spaceBefore=4 * mm, spaceAfter=2 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName=font, fontSize=8.8,
            leading=11.2, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=2.2 * mm,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName=font, fontSize=7.4,
            leading=9.2, textColor=MUTED, spaceAfter=1.4 * mm,
        ),
        "formula": ParagraphStyle(
            "Formula", parent=base["BodyText"], fontName=font, fontSize=8.2,
            leading=10.4, textColor=INK, leftIndent=3 * mm, rightIndent=3 * mm,
        ),
        "formula_title": ParagraphStyle(
            "FormulaTitle", parent=base["BodyText"], fontName=bold, fontSize=8.4,
            leading=10.5, textColor=ACCENT,
        ),
        "caption": ParagraphStyle(
            "Caption", parent=base["BodyText"], fontName=italic, fontSize=7.5,
            leading=9.2, textColor=MUTED, alignment=TA_CENTER, spaceAfter=3 * mm,
        ),
        "table": ParagraphStyle(
            "Table", parent=base["BodyText"], fontName=font, fontSize=7.2,
            leading=8.5, textColor=INK,
        ),
        "table_header": ParagraphStyle(
            "TableHeader", parent=base["BodyText"], fontName=bold, fontSize=7.2,
            leading=8.5, textColor=WHITE, alignment=TA_CENTER,
        ),
    }


class DeckReportDocument(SimpleDocTemplate):
    """A4 report document with formal margins and metadata."""

    def __init__(self, filename: str, **kwargs) -> None:
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=16 * mm,
            topMargin=18 * mm,
            bottomMargin=17 * mm,
            title="Memoria de calculo - Diseno de tablero",
            author="bridge-design",
            **kwargs,
        )


def page_frame(canvas, document) -> None:
    """Draw restrained header, footer and page number."""
    canvas.saveState()
    font = register_arial_narrow()
    bold = "ArialNarrow-Bold" if font == "ArialNarrow" else "Helvetica-Bold"
    width, height = A4
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.45)
    canvas.line(18 * mm, height - 12 * mm, width - 16 * mm, height - 12 * mm)
    canvas.setFont(bold, 7.2)
    canvas.setFillColor(ACCENT)
    canvas.drawString(18 * mm, height - 9.2 * mm, "MEMORIA DE CALCULO - DISENO DE TABLERO")
    canvas.setFont(font, 7)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(width - 16 * mm, 9.2 * mm, f"Pagina {document.page}")
    canvas.line(18 * mm, 12.5 * mm, width - 16 * mm, 12.5 * mm)
    canvas.restoreState()


def p(text: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def formula_card(
    title: str,
    formula: str,
    legend: str,
    substitution: str,
    result: str,
    criterion: str,
    reference: str,
    styles: dict[str, ParagraphStyle],
) -> KeepTogether:
    """Return a compact formula, replacement and engineering-decision block."""
    rows = [
        [p(title, styles["formula_title"])],
        [p(f"Formula general: {formula}", styles["formula"])],
        [p(f"Leyenda: {legend}", styles["formula"])],
        [p(f"Sustitucion: {substitution}", styles["formula"])],
        [p(f"Resultado: {result}", styles["formula"])],
        [p(f"Criterio adoptado: {criterion}", styles["formula"])],
        [p(f"Referencia: {reference}", styles["small"])],
    ]
    table = Table(rows, colWidths=[170 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
        ("BOX", (0, 0), (-1, -1), 0.55, RULE),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return KeepTogether([table, Spacer(1, 2.5 * mm)])


def data_table(
    headers: tuple[str, ...],
    rows: list[tuple[object, ...]],
    widths: list[float],
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Return a minimal table reserved for values that benefit from comparison."""
    content = [[p(value, styles["table_header"]) for value in headers]]
    content.extend([p(value, styles["table"]) for value in row] for row in rows)
    table = Table(content, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("GRID", (0, 0), (-1, -1), 0.35, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#F7F9FA")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def section_break() -> PageBreak:
    return PageBreak()
