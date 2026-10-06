"""Resultados compactos del apoyo Método A, con desarrollo opcional."""
from shutil import get_terminal_size
from bridge_design.cli.ascii_tables import audit_block_title, boxed_table
from bridge_design.reporting.bearing_a_labels import (
    CONTROL_IDS, compression_basis, conclusion, result_status, design_checks, number, status, title,
)


def format_bearing_a(result, *, detailed=False, width=None):
    width = max(72, min(112, width or get_terminal_size((100, 24)).columns))
    i, g = result.inputs, result.adopted
    lines = audit_block_title("", "APOYO ELASTOMÉRICO REFORZADO CON ACERO MÉTODO A", width)

    def table(name, headers, rows):
        lines.append("")
        lines.extend(audit_block_title("", name, width))
        lines.extend(boxed_table(headers, rows, max_width=width, row_separators=False))

    table("DISEÑO ADOPTADO", ("Concepto", "Resultado"), [
        ("Proyecto y apoyo", f"{i.project} / {i.bearing_id}"),
        (f"Estado global: {result_status(result)}", conclusion(result)),
        ("Planta y altura", f"{g.length_cm*10:g} × {g.width_cm*10:g} × {result.value('HEIGHT')*10:g} mm"),
        ("Elastómero", f"Shore A {i.hardness}; {g.interior_layers} capas interiores de {g.interior_cm*10:g} mm; 2 exteriores de {g.exterior_cm*10:g} mm"),
        ("Perforaciones pasantes", f"{g.hole_count} de diámetro {g.hole_diameter_cm*10:g} mm" if g.hole_count else "Sin perforaciones"),
        ("Zunchos", f"{g.interior_layers+1} de {g.steel_cm*10:g} mm"),
    ])
    a = i.actions
    table("ACCIONES Y DEFORMACIONES", ("Magnitud", "Resultado"), [
        ("DC / DW / LL / PL / IM", f"{a.dc_tn:g} / {a.dw_tn:g} / {a.ll_tn:g} / {a.pl_tn:g} / {a.im_tn:g} Tn"),
        ("Reacción de servicio", number(result.value("P"), "Tn")),
        ("Desplazamiento horizontal", number(result.value("DELTA"), "cm")),
        ("Área efectiva", number(result.value("AREA"), "cm²")),
        ("Factor de forma interior / exterior", f"{result.value('SI'):.4g} / {result.value('SE'):.4g}"),
        ("Compresión permanente / total / carga viva", " / ".join(number(result.step(k).value, "cm") for k in ("DEF_D", "DEF_T", "DEF_LL"))),
        ("Deflexión diferida por fluencia", number(result.step("CREEP").value, "cm")),
    ])
    rows = []
    for s in design_checks(result):
        percent = s.id == "STRAIN_CHECK"
        comparison = number(s.value, s.unit, percent=percent) + (" < " if s.strict else " ≤ ") + number(s.limit, s.unit, percent=percent)
        state = status(s)
        rows.append((title(s), comparison, state))
    table("VERIFICACIONES MTC Y SERQUÉN", ("Comprobación", "Comparación", "Estado"), rows)
    conditions = [("Dirección de giro principal", "Eje transversal" if g.principal_rotation_transverse else "Fuera del alcance del Método A")]
    if g.total_height_cm is not None:
        conditions.append(("Altura especificada", f"{g.total_height_cm*10:g} mm; {status(result.step('HEIGHT_TARGET'))}"))
    conditions.append(("Base de compresión", compression_basis(result)))
    conditions.append(("Criterios", "MTC 2018, 2.10.4; Serquén, problema 4.1. Junta y fricción: criterios de los comentarios AASHTO."))
    table("CONDICIONES DE DISEÑO", ("Concepto", "Criterio"), conditions)
    if detailed:
        for s in result.steps:
            if s.id in CONTROL_IDS:
                continue
            table(title(s), ("Concepto", "Desarrollo"), [
                ("Expresión", s.formula), ("Definiciones", s.legend),
                ("Sustitución", s.substitution), ("Referencia", s.reference),
            ])
    return "\n".join(lines)
