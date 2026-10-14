"""Technical scope statements shared by the deck Word and PDF reports."""

from types import SimpleNamespace


def cantilever_notes_for_side(result, geometry, layout, side: str) -> tuple[str, ...]:
    """Identify the physical pipe position and the overhang's local origin."""
    notes = [f"Volado {side}: coordenadas locales desde el borde exterior {side}."]
    pipe = layout.pipe
    for note in result.applicability_notes:
        if pipe is not None and note.startswith("DW - tuberia llena no genera momento de voladizo:"):
            global_x = (geometry.total_width_m - pipe.x_from_left_m
                        if side == "derecho" else pipe.x_from_left_m)
            if global_x <= geometry.overhang_m:
                location = "en el volado izquierdo"
            elif global_x >= geometry.total_width_m - geometry.overhang_m:
                location = "en el volado derecho"
            else:
                location = "entre los ejes de las vigas exteriores"
            note = (
                f"La tuberia se ubica {location}, a {global_x:.3f} m del borde exterior izquierdo. "
                f"Para comprobar el volado {side}, su coordenada local es "
                f"{pipe.x_from_left_m:.3f} m desde el borde exterior {side}; "
                f"el eje de la viga exterior esta a {geometry.overhang_m:.3f} m de ese borde. "
                f"Por ello, la tuberia no carga directamente el volado {side}."
            )
        notes.append(note)
    return tuple(notes)


def formal_audit_line(line: str) -> str:
    """Retain numerical traces while giving operational notes a technical wording."""
    text = line.strip()
    if text.startswith("Sin colision local aplicada al voladizo. Consultar geometria"):
        return "El calculo del voladizo comprende las acciones directas aplicadas a su geometria."
    text = formal_cantilever_notes(SimpleNamespace(applicability_notes=(text,)))[0]
    text = formal_interior_collision_notes(SimpleNamespace(notes=(text,)))[0]
    for original, replacement in (
        ("RESUMEN DE DATOS INGRESADOS", "PARAMETROS ADOPTADOS"),
        ("Recorrido vehicular ingresado", "Recorrido vehicular adoptado"),
        ("recorrido libre ingresado", "recorrido libre adoptado"),
        ("Diafragmas ingresados", "Diafragmas adoptados"),
    ):
        text = text.replace(original, replacement)
    return text if text != line.strip() else line


def formal_cantilever_notes(result) -> tuple[str, ...]:
    notes = []
    for note in result.applicability_notes:
        if note.startswith("Colision local de barrera sobre voladizo: NO APLICABLE"):
            notes.append(
                "El calculo del voladizo comprende las acciones directas aplicadas a su geometria. "
                "La barrera se encuentra fuera del voladizo; se presentan sus demandas y los "
                "resultados de anclaje y dowel por separado."
            )
        elif note.startswith("Colision local sobre voladizo: NO APLICABLE"):
            notes.append(
                "La barrera transmite la colision a la losa interior. Se desarrolla su "
                "transferencia local y el refuerzo correspondiente por cara."
            )
        else:
            notes.append(note)
    return tuple(notes)


def formal_interior_collision_notes(collision) -> tuple[str, ...]:
    notes = []
    for note in collision.notes:
        if note.startswith("Armadura indicada:"):
            notes.append(
                "La armadura indicada corresponde al minimo total por colision en cada cara "
                "de la losa interior. Las demandas de colision y del diseno ordinario se "
                "presentan por separado, con sus longitudes de anclaje."
            )
        elif note.startswith("Alcance: transferencia LOCAL"):
            notes.append(
                "El analisis desarrollado comprende la transferencia local barrera-losa "
                "y las demandas verticales transmitidas a las vigas."
            )
        else:
            notes.append(note)
    return tuple(notes)
