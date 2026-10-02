"""Connected report front matter and summary using the abutment Word house style."""

from dataclasses import replace
from datetime import datetime

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt

from bridge_design.reporting.abutment_docx import _configure_abutment_header_footer, _labels, _references
from bridge_design.reporting.deck_docx import (
    GRAY, TEAL, _body, _bottom_border, _configure_document, _format_run, _table,
)


SECTIONS = (
    "Bases de diseño y datos de entrada", "Rigidez y contacto",
    "Cargas de ambos estribos y combinaciones", "Presiones y deslizamiento",
    "Solicitaciones del FRAME", "Diseño de armaduras y detalle",
    "Verificación numérica y trazabilidad", "Cuadro de detalle y resumen del diseño adoptado",
    "Referencias normativas",
)


def connected_front_matter(document, result):
    _configure_document(document)
    title_properties = document.styles["Title"].element.get_or_add_pPr()
    title_border = title_properties.find(qn("w:pBdr"))
    if title_border is not None:
        title_properties.remove(title_border)
    labels = replace(_labels(is_pure_wall=False), header="MEMORIA DE CÁLCULO · ESTRIBOS CONECTADOS")
    _configure_abutment_header_footer(document, labels)
    data = result.inputs
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(34)
    _format_run(paragraph.add_run("INGENIERÍA ESTRUCTURAL"), 11, bold=True, color=TEAL)
    _bottom_border(paragraph, TEAL, 16)
    paragraph = document.add_paragraph(style="Title")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.paragraph_format.space_before = Pt(42)
    paragraph.add_run("Memoria de cálculo\nde estribos conectados")
    document.add_paragraph("Geometría · empujes · contacto · diseño estructural · detalle", style="Subtitle")
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(32)
    paragraph.paragraph_format.space_after = Pt(4)
    _format_run(paragraph.add_run("DOCUMENTO TÉCNICO DE DISEÑO"), 11, bold=True, color=TEAL)
    _table(document, ("Dato", "Descripción"), (
        ("Sistema", "Dos estribos con cajuela y cimentación continua, FRAME 2D de franja 1,00 m"),
        ("Separación libre", f"{data.clear_span_m:.2f} m"),
        ("Longitud de cimentación", f"{data.total_length_m:.2f} m"),
        ("Módulo de balasto", f"{data.soil.subgrade_tn_m3:.3f} Tn/m³"),
        ("Presión admisible", f"{data.soil.allowable_tn_m2:.3f} Tn/m²"),
        ("Norma principal", "Manual de Puentes MTC 2018"),
        ("Fecha de emisión", datetime.now().strftime("%d/%m/%Y")),
    ), widths=(42, 125), accent=True)
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(30)
    _format_run(paragraph.add_run(
        "La presente memoria conserva las hipótesis, verificaciones y armaduras adoptadas. "
        "Los estados NO CUMPLE y los anclajes pendientes no constituyen aprobación del diseño."
    ), 11, italic=True, color=GRAY)
    document.add_page_break()
    document.add_heading("Contenido", level=1)
    _body(document, "La memoria sigue la secuencia del cálculo y presenta las armaduras adoptadas al finalizar la selección.")
    _table(document, ("Sección", "Contenido desarrollado"),
           ((str(index), label) for index, label in enumerate(SECTIONS, 1)), widths=(25, 142), accent=True)
    document.add_page_break()


def connected_summary_and_references(document, result):
    document.add_heading("8. " + SECTIONS[7], level=1)
    _table(document, ("Región", "Principal por cara", "Transversal por cara", "Estado"),
           ((steel.region, f"{steel.bar_label} @ {steel.spacing_m:.3f} m",
             f"{steel.transverse_bar_label} @ {steel.transverse_spacing_m:.3f} m", steel.status)
            for steel in result.reinforcement), widths=(52, 40, 40, 26), accent=True)
    _body(document, "Las áreas y verificaciones corresponden a las barras y separaciones efectivamente adoptadas. "
          "Si una verificación indica NO CUMPLE, deben revisarse geometría, cargas o armado antes de emitir planos. "
          "El contacto y el deslizamiento no sustituyen la comprobación de asentamientos admisibles. "
          "Los anclajes con estado PENDIENTE DETALLE requieren revisión de sus longitudes útiles y acomodo.")
    _references(document)
