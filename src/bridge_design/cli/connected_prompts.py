"""Interactive paired-abutment inputs with the existing cajuela prompts."""

from dataclasses import replace

from bridge_design.cli.abutment_input_prompts import collect_abutment_inputs
from bridge_design.cli.input_prompts import prompt_float, prompt_non_negative_float
from bridge_design.domain.connected_defaults import (
    REFERENCE_CLEAR_SPAN_M, REFERENCE_SLAB_THICKNESS_M, REFERENCE_TRANSITION_M,
    connected_geometry_defaults, connected_load_defaults,
)
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil


def yes_no(label, default=True):
    while True:
        raw = input(f"{label} [{'S/n' if default else 's/N'}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("si", "s", "yes", "y"):
            return True
        if raw in ("no", "n"):
            return False
        print("Ingrese s o n.")


def collect_connected_inputs():
    note = ("Geometria inicial: MDOELO DE PUENTEl.pdf, editable. Pantalla 1.00 m y puntera 2.50 m "
            "confirmadas por el usuario. Use reacciones simultaneas del tablero. Empuje siempre activo. "
            "Cargas iniciales del tablero indicadas por el usuario, editables en ambos lados. "
            "Materiales, suelo y brazo adicional de frenado son referenciales, no datos del PDF.")
    left = collect_abutment_inputs(title="ESTRIBO IZQUIERDO CON CAJUELA", defaults_note=note,
                                   collect_key=False, geometry_defaults=connected_geometry_defaults(),
                                   load_defaults=connected_load_defaults())
    if yes_no("Usar los mismos datos para el estribo derecho"):
        right = replace(left)
    else:
        right = collect_abutment_inputs(title="ESTRIBO DERECHO CON CAJUELA", defaults_note=note,
                                        collect_key=False, geometry_defaults=connected_geometry_defaults(),
                                        load_defaults=connected_load_defaults())
    print("CIMENTACION CONTINUA - FRANJA DE 1.00 m")
    clear_span = prompt_float("Separacion libre entre caras interiores de pantallas en su base", "m", REFERENCE_CLEAR_SPAN_M)
    slab = prompt_float("Espesor de losa central", "m", REFERENCE_SLAB_THICKNESS_M)
    transition_left = prompt_non_negative_float("Longitud transicion izquierda (0 sin transicion)", "m", REFERENCE_TRANSITION_M)
    transition_right = prompt_non_negative_float("Longitud transicion derecha (0 sin transicion)", "m", REFERENCE_TRANSITION_M)
    step = prompt_float("Paso maximo de malla", "m", 0.50)
    offset = yes_no("Considerar offsets de centroides", False)
    position = None if yes_no("Restringir Ux en el centro de la longitud total") else prompt_non_negative_float(
        "Posicion x desde extremo izquierdo", "m")
    soil = FoundationSoil(
        prompt_float("Modulo de balasto vertical OBLIGATORIO", "Tn/m3"),
        prompt_non_negative_float("Coeficiente de friccion interfaz suelo-concreto", "adimensional"),
        prompt_float("Presion admisible de cimentacion", "Tn/m2"),
        prompt_float("FS para estimar capacidad portante nominal desde qadm", "adimensional", 3.0))
    return ConnectedInputs(soil, left, right, clear_span, slab, transition_left, transition_right, step,
                           offset, position, left.materials,
                           prompt_float("Recubrimiento losa central", "cm", 7.5),
                           include_without_bridge=yes_no("Incluir condicion sin tablero"))
