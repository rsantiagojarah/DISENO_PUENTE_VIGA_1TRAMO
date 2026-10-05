"""Numbered terminal development from the same trace used in Word."""

from bridge_design.cli.ascii_tables import audit_block_title, audit_subtitle, boxed_table
from bridge_design.reporting.connected_steel_trace import steel_steps, steel_tables


def format_audit_table(table):
    return [*boxed_table(table.headers, table.rows, title=table.title, row_separators=False), table.note]


def format_audit_step(step, code):
    return [*audit_subtitle(code, step.title, 112), *boxed_table(("Desarrollo", "Expresion / valor"), (
        ("Formula", step.formula), ("Variables y unidades", step.legend),
        ("Sustitucion", step.substitution), ("Resultado", step.result),
        ("Verificacion", step.comment), ("Referencia", step.reference)))]


def format_connected_audit(result, audit):
    lines = []
    for index, (key, title) in enumerate((("inputs", "DATOS Y MODELO"), ("loads", "CARGAS Y COMBINACIONES"),
                                         ("foundation", "CONTACTO Y CAPACIDAD PORTANTE")), 1):
        lines.extend(audit_block_title(str(index), title, 112))
        if key == "loads":
            for step_index, step in enumerate(audit["earth"], 1):
                lines.extend(format_audit_step(step, f"2.{step_index}"))
        for table in audit[key]:
            lines.extend(format_audit_table(table))
    lines.extend(audit_block_title("4", "DESARROLLO DEL DISENO DEL ACERO ADOPTADO", 112))
    for index, steel in enumerate(result.reinforcement, 1):
        lines.extend(audit_subtitle(f"4.{index}", steel.region.upper(), 112))
        origin = "USUARIO / SELECCION CONFIRMADA" if steel.region in result.selected_reinforcement else "PROPUESTA AUTOMATICA"
        lines.append(f"Origen del armado: {origin}")
        detail = audit["steel"][steel.region]
        if steel.role == "temperature":
            lines.extend(boxed_table(("Criterio", "Valor"), (
                ("Area minima por temperatura cm2/m", f"{steel.temperature_cm2_m:.4f}"),
                ("Acero elegido", f"{steel.bar_label} @ {steel.spacing_m:.3f} m"),
                ("Area proporcionada cm2/m", f"{steel.area_per_face_cm2_m:.4f}"),
                ("Estado", steel.status))))
            for step in steel_steps(steel, detail):
                if step.title.startswith("Temperatura"):
                    lines.extend(format_audit_step(step, f"4.{index}.1"))
            continue
        for table in steel_tables(steel, detail):
            lines.extend(format_audit_table(table))
        for step_index, step in enumerate(steel_steps(steel, detail), 1):
            lines.extend(format_audit_step(step, f"4.{index}.{step_index}"))
    lines.extend(audit_block_title("5", "RESUMEN DE RESULTADOS Y ARMADURAS", 112))
    return "\n".join(lines)
