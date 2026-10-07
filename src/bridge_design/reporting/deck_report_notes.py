"""Technical scope statements shared by the deck Word and PDF reports."""

from types import SimpleNamespace


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
