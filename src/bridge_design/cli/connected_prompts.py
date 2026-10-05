"""Interactive paired-abutment inputs with the existing cajuela prompts."""

from dataclasses import replace

from bridge_design.cli.abutment_input_prompts import collect_abutment_inputs, _collect_loads
from bridge_design.cli.input_prompts import prompt_float, prompt_non_negative_float, prompt_int
from bridge_design.domain.connected_defaults import (
    REFERENCE_CLEAR_SPAN_M, REFERENCE_SLAB_THICKNESS_M, REFERENCE_TRANSITION_M,
    connected_geometry_defaults, connected_load_defaults,
)
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil
from bridge_design.domain.transverse_slab import kg_cm2_to_tn_m2


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


def collect_connected_inputs(*, side=None, foundation_geometry=None, collect_detailing=True):
    print("1. INGRESO DE DATOS DE ESTRIBOS COMBINADOS")
    note = ("Geometria inicial: MDOELO DE PUENTEl.pdf, editable. Pantalla 1.00 m y puntera 2.50 m "
            "confirmadas por el usuario. Use reacciones simultaneas del tablero. Empuje siempre activo. "
            "Cargas iniciales del tablero indicadas por el usuario, editables en ambos lados. "
            "qadm y FS se ingresan una sola vez y se comparten en toda la cimentacion. "
            "Materiales, suelo y brazo adicional de frenado son referenciales, no datos del PDF.")
    print("Geometria, materiales y armado comunes para los dos estribos.")
    left = side if side is not None else collect_abutment_inputs(title="ESTRIBO COMUN CON CAJUELA", defaults_note=note,
                                   load_title="REACCIONES DEL TABLERO - ESTRIBO IZQUIERDO",
                                   collect_key=False, geometry_defaults=connected_geometry_defaults(),
                                   load_defaults=connected_load_defaults())
    if collect_detailing:
        left = _collect_connected_detailing(left, "comun")
    right = replace(left)
    if not yes_no("Usar las mismas reacciones del tablero en ambos estribos"):
        right = replace(left, loads=_collect_loads(left.loads,
            "REACCIONES DEL TABLERO - ESTRIBO DERECHO",
            "Ingrese las reacciones simultaneas con las del izquierdo, en tn/m."))
    print("CIMENTACION CONTINUA - FRANJA DE 1.00 m")
    allowable = kg_cm2_to_tn_m2(left.soil.allowable_bearing_kg_cm2)
    print(f"qadm comun: {left.soil.allowable_bearing_kg_cm2:g} kg/cm2 = {allowable:g} Tn/m2 | "
          f"FS capacidad portante nominal: {left.soil.bearing_capacity_factor_fs:g} (datos ya ingresados)")
    if foundation_geometry is None:
        clear_span = prompt_float("Separacion libre entre caras interiores de pantallas en su base", "m", REFERENCE_CLEAR_SPAN_M)
        slab = prompt_float("Espesor de losa central", "m", REFERENCE_SLAB_THICKNESS_M)
        transition_left = prompt_non_negative_float("Longitud transicion izquierda (0 sin transicion)", "m", REFERENCE_TRANSITION_M)
        transition_right = prompt_non_negative_float("Longitud transicion derecha (0 sin transicion)", "m", REFERENCE_TRANSITION_M)
    else:
        clear_span, slab, transition_left, transition_right = foundation_geometry
    count = prompt_int("Cantidad total de nudos con resorte en cimentacion", 41, minimum=4)
    print("Resortes equidistantes por tramo, incluyendo ambos extremos de talon y ambos ejes de estribo.")
    offset = yes_no("Considerar offsets de centroides", False)
    position = None if yes_no("Restringir Ux en el centro de la longitud total") else prompt_non_negative_float(
        "Posicion x desde extremo izquierdo", "m")
    print("Materiales comunes para ambos estribos y la zapata combinada: los ingresados al inicio."
          if foundation_geometry is not None else
          "Materiales comunes para ambos estribos, zapatas y losa: los ingresados al inicio.")
    soil = FoundationSoil(
        prompt_float("Modulo de balasto vertical OBLIGATORIO", "Tn/m3"),
        0.0,  # Compatibility field; sliding is outside the reported verification scope.
        allowable, left.soil.bearing_capacity_factor_fs)
    return ConnectedInputs(soil, left, right, clear_span, slab, transition_left, transition_right,
                           section_offsets=offset, reference_x_m=position, slab_materials=left.materials,
                           foundation_node_count=count,
                           include_without_bridge=yes_no("Incluir condicion sin tablero"))


def _collect_connected_detailing(side, label):
    print(f"APOYO DEL TABLERO - ESTRIBO {label.upper()}")
    geometry = replace(side.geometry, bridge_seat_to_bearing_height_m=prompt_non_negative_float(
        "Altura adicional del apoyo sobre la cajuela para el brazo de frenado", "m",
        side.geometry.bridge_seat_to_bearing_height_m))
    return replace(side, geometry=geometry)

