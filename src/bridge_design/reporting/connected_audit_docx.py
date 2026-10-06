"""Word rendering of the common calculation trace, preserving the house style."""

from dataclasses import astuple

from bridge_design.reporting.connected_steel_trace import steel_steps, steel_tables
from bridge_design.reporting.deck_docx import _body, _calc, _table


def write_audit_table(document, table):
    document.add_heading(table.title, level=3)
    count = len(table.headers)
    widths = (36, 100, 24) if table.headers[1] in ("Origen y ubicacion", "Caso y seccion") else None
    if widths is None:
        first = 62 if count <= 3 else 45 if count <= 6 else 20
        widths = (first, *((160 - first) / (count - 1) for _ in range(count - 1)))
    _table(document, table.headers, table.rows, widths=widths, font_size=10)
    if table.note:
        _body(document, table.note)


def write_steel_audit(document, steel, audit, selected):
    _body(document, f"Armado adoptado: {steel.bar_label} @ {steel.spacing_m:.3f} m.")
    for table in steel_tables(steel, audit):
        write_audit_table(document, table)
    for step in steel_steps(steel, audit):
        _calc(document, *astuple(step))
