"""Complete numerical audit appendix based on the terminal-format trace."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle, XPreformatted

from bridge_design.reporting.pdf_style import PALE, RULE, p, register_arial_narrow


def audit_appendix(sections: tuple[tuple[str, str], ...], styles) -> list:
    """Render every calculation trace without repeating decorative ASCII borders."""
    story = [
        p("Anexo A. Trazabilidad numerica completa", styles["h1"]),
        p(
            "Este anexo reproduce la salida numerica completa del motor: casos sin factor, "
            "combinaciones, opciones de acero, verificaciones de servicio, fatiga, desarrollo y "
            "detalle constructivo. Es parte integral de la memoria.",
            styles["body"],
        ),
    ]
    for index, (title, text) in enumerate(sections, start=1):
        story.append(p(f"A.{index} {title}", styles["h2"]))
        story.extend(_trace_blocks(text, styles))
    return story


def _trace_blocks(text: str, styles) -> list:
    font = register_arial_narrow()
    mono_style = styles["small"].clone("AuditTrace")
    mono_style.fontName = font
    mono_style.fontSize = 5.8
    mono_style.leading = 6.8
    lines = [line.rstrip() for line in text.splitlines()]
    blocks: list = []
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or (stripped and set(stripped) <= {"-", "="}):
            if current:
                blocks.append(_trace_table(current, mono_style))
                current = []
            continue
        if "|" in line or "+" in line:
            current.append(line)
            if len(current) >= 28:
                blocks.append(_trace_table(current, mono_style))
                current = []
            continue
        if current:
            blocks.append(_trace_table(current, mono_style))
            current = []
        if stripped.isupper() and len(stripped) < 120:
            blocks.append(p(stripped, styles["formula_title"]))
        else:
            blocks.append(p(stripped, styles["small"]))
    if current:
        blocks.append(_trace_table(current, mono_style))
    blocks.append(Spacer(1, 2 * mm))
    return blocks


def _trace_table(lines: list[str], style) -> KeepTogether:
    content = XPreformatted("\n".join(lines), style)
    table = Table([[content]], colWidths=[170 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F9FA")),
        ("BOX", (0, 0), (-1, -1), 0.35, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return KeepTogether([table, Spacer(1, 1.5 * mm)])
