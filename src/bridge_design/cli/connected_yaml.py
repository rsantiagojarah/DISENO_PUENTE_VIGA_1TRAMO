"""Spanish YAML for paired abutments, reusing the individual abutment schema."""

from copy import deepcopy
from dataclasses import replace
from math import isfinite

from bridge_design.cli.yaml_inputs import abutment_inputs_from_yaml, abutment_yaml_template
from bridge_design.domain.connected_defaults import (
    REFERENCE_CLEAR_SPAN_M, REFERENCE_SLAB_THICKNESS_M, REFERENCE_TRANSITION_M,
    connected_geometry_defaults, connected_load_defaults,
)
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil, PairedBridgeCase
from bridge_design.domain.transverse_slab import kg_cm2_to_tn_m2


def connected_yaml_template(*, example=False):
    geometry = connected_geometry_defaults()
    side = abutment_yaml_template(geometry_defaults=geometry, load_defaults=connected_load_defaults())
    for name in ("version_esquema", "comando", "nota"):
        side.pop(name, None)
    for name in ("qadm_capacidad_portante_kg_cm2", "fs_capacidad_portante_nominal"):
        side["suelo_sismo"].pop(name)
    side["geometria"]["altura_apoyo_a_cajuela_m"] = geometry.bridge_seat_to_bearing_height_m
    side["armadura"] = {
        "paso_separacion_m": 0.025, "separacion_minima_m": 0.10, "separacion_maxima_m": 0.30,
    }
    return {
        "version_esquema": 1, "comando": "diseno-estribos-conectados",
        "nota": "Geometria inicial editable de MDOELO DE PUENTEl.pdf. "
                "Pantalla 1.00 m y puntera 2.50 m confirmadas por el usuario. "
                "Cargas iniciales del tablero indicadas por el usuario, editables en ambos lados. "
                "Materiales, suelo y brazo adicional de frenado son REFERENCIALES, no datos del PDF. "
                "Presion siempre activa. "
                "Cargas izquierda/derecha son un par simultaneo, no maximos independientes. "
                "Longitud cajuela + espesor parapeto = espesor superior + t1 + t2.",
        "cimentacion": {
            "separacion_libre_entre_caras_interiores_m": REFERENCE_CLEAR_SPAN_M,
            "espesor_losa_central_m": REFERENCE_SLAB_THICKNESS_M,
            "transicion_izquierda_m": REFERENCE_TRANSITION_M, "transicion_derecha_m": REFERENCE_TRANSITION_M,
            "cantidad_nudos_cimentacion": 41, "offsets_seccion": False, "nodo_referencia_x_m": None,
        },
        "suelo_cimentacion": {
            "modulo_balasto_vertical_tn_m3": 3000.0 if example else None,
            "qadm_tn_m2": 26.7, "fs_capacidad_nominal": 3.0,
            "phi_deslizamiento_resistencia": 0.80, "phi_deslizamiento_extremo": 1.0,
        },
        "estribo": side,
        "cargas_tablero_derecho": {},
        "nota_estribo": "Geometria, materiales y criterios de armado comunes a ambos lados. "
                         "Las cargas_tablero de estribo corresponden al izquierdo y, por defecto, al derecho. "
                         "cargas_tablero_derecho permite cambiar solo las reacciones del derecho.",
        "incluir_sin_tablero": True,
        "casos_simultaneos": [],
        "nota_casos": "Lista vacia usa el par de cargas ingresado en los estribos. Para varios casos: "
                      "nombre, cargas_izquierda, cargas_derecha (claves de cargas_tablero), "
                      "factor_sobrecarga_izquierda, factor_sobrecarga_derecha. "
                      "Cada caso debe contener las reacciones del mismo posicionamiento del tablero.",
        "longitudes_rectas_anclaje_disponibles_m": {},
        "nota_anclajes": "Longitudes utiles verificadas por distribucion comun, por ejemplo 'Pantalla - vertical relleno'. "
                         "Si faltan, se infieren desde la geometria de ambos lados. Los ganchos se reportan sin aprobar "
                         "su acomodo automaticamente.",
    }


def mapping(data, name, required=False):
    value = data.get(name)
    if value is None and not required:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} debe ser un bloque YAML" + (" obligatorio." if required else "."))
    return value


def number(data, name, default=None):
    value = data.get(name, default)
    if value is None or isinstance(value, bool):
        raise ValueError(f"Falta el dato numerico obligatorio: {name}.")
    try:
        result = float(value)
    except (ValueError, TypeError) as error:
        raise ValueError(f"{name} debe ser numerico.") from error
    if not isfinite(result):
        raise ValueError(f"{name} debe ser finito.")
    return result


def boolean(data, name, default):
    value = data.get(name, default)
    if not isinstance(value, bool):
        raise ValueError(f"{name} debe ser true o false, sin comillas.")
    return value


def side_inputs(data, foundation_soil, *, geometry_defaults=None):
    shared_soil = dict(mapping(data, "suelo_sismo"))
    shared_soil.update(
        qadm_capacidad_portante_kg_cm2=foundation_soil.allowable_tn_m2 / kg_cm2_to_tn_m2(1.0),
        fs_capacidad_portante_nominal=foundation_soil.nominal_bearing_fs)
    try:
        side = abutment_inputs_from_yaml({**data, "suelo_sismo": shared_soil}, geometry_defaults=geometry_defaults or connected_geometry_defaults(),
                                         load_defaults=connected_load_defaults())
    except (TypeError, ValueError) as error:
        raise ValueError(f"Datos de estribo invalidos: {error}") from error
    raw = mapping(data, "armadura")
    reinforcement = replace(side.reinforcement,
        spacing_step_m=number(raw, "paso_separacion_m", 0.025),
        minimum_spacing_m=number(raw, "separacion_minima_m", 0.10),
        maximum_spacing_m=number(raw, "separacion_maxima_m", 0.30))
    return replace(side, reinforcement=reinforcement)


def connected_inputs_from_yaml(raw, *, geometry_defaults=None):
    if raw.get("comando", "diseno-estribos-conectados") != "diseno-estribos-conectados":
        raise ValueError("El YAML no corresponde a diseno-estribos-conectados.")
    if raw.get("version_esquema", 1) != 1:
        raise ValueError("Version de esquema no soportada.")
    foundation = mapping(raw, "cimentacion", True)
    count = foundation.get("cantidad_nudos_cimentacion", None if "paso_malla_m" in foundation else 41)
    if "cantidad_nudos_cimentacion" in foundation and (
        isinstance(count, bool) or not isinstance(count, int) or count < 4
    ):
        raise ValueError("cantidad_nudos_cimentacion debe ser un entero >= 4.")
    soil = mapping(raw, "suelo_cimentacion", True)
    foundation_soil = FoundationSoil(
        number(soil, "modulo_balasto_vertical_tn_m3"),
        number(soil, "coeficiente_friccion_interfaz") if soil.get("coeficiente_friccion_interfaz") is not None else 0.0,
        number(soil, "qadm_tn_m2"), number(soil, "fs_capacidad_nominal", 3.0),
        number(soil, "phi_deslizamiento_resistencia", 0.80), number(soil, "phi_deslizamiento_extremo", 1.0))
    if "estribo" in raw:
        if "estribo_izquierdo" in raw or "estribo_derecho" in raw:
            raise ValueError("Use el bloque comun estribo o los bloques antiguos, sin mezclarlos.")
        left_raw = mapping(raw, "estribo", True)
        right_raw = deepcopy(left_raw)
        overrides = mapping(raw, "cargas_tablero_derecho")
        right_raw["cargas_tablero"] = {**mapping(left_raw, "cargas_tablero"), **overrides}
    else:
        # Read previous files without changing their simultaneous reactions;
        # ConnectedInputs rejects incompatible geometry/materials/detailing.
        left_raw, right_raw = mapping(raw, "estribo_izquierdo", True), mapping(raw, "estribo_derecho", True)
    left, right = (side_inputs(side, foundation_soil, geometry_defaults=geometry_defaults)
                   for side in (left_raw, right_raw))
    materials_raw = mapping(foundation, "materiales_losa")
    materials = abutment_inputs_from_yaml({"materiales": materials_raw}).materials if materials_raw else left.materials
    paired = []
    raw_cases = raw.get("casos_simultaneos", [])
    if not isinstance(raw_cases, list):
        raise ValueError("casos_simultaneos debe ser una lista.")
    for entry in raw_cases:
        if not isinstance(entry, dict):
            raise ValueError("Cada caso simultaneo debe ser un bloque YAML.")
        for name in ("cargas_izquierda", "cargas_derecha"):
            loads_raw = mapping(entry, name, True)
            for key in ("pdc_carga_muerta_tablero_tn_m", "pdw_superficie_tn_m", "ppl_peatonal_tablero_tn_m",
                        "pll_im_vehicular_tn_m", "br_frenado_tn_m"):
                number(loads_raw, key)
        loads_left = abutment_inputs_from_yaml({"cargas_tablero": entry["cargas_izquierda"]}).loads
        loads_right = abutment_inputs_from_yaml({"cargas_tablero": entry["cargas_derecha"]}).loads
        paired.append(PairedBridgeCase(str(entry.get("nombre", "")), loads_left, loads_right,
                                      number(entry, "factor_sobrecarga_izquierda", 1.0),
                                      number(entry, "factor_sobrecarga_derecha", 1.0)))
    return ConnectedInputs(
        soil=foundation_soil,
        left=left, right=right,
        clear_span_m=number(foundation, "separacion_libre_entre_caras_interiores_m"),
        slab_thickness_m=number(foundation, "espesor_losa_central_m"),
        left_transition_m=number(foundation, "transicion_izquierda_m", REFERENCE_TRANSITION_M),
        right_transition_m=number(foundation, "transicion_derecha_m", REFERENCE_TRANSITION_M),
        mesh_size_m=number(foundation, "paso_malla_m", 0.50) if count is None else 0.50,
        foundation_node_count=count,
        section_offsets=boolean(foundation, "offsets_seccion", False),
        reference_x_m=None if foundation.get("nodo_referencia_x_m") is None else number(foundation, "nodo_referencia_x_m"),
        slab_materials=materials,
        cases=tuple(paired), include_without_bridge=boolean(raw, "incluir_sin_tablero", True),
        anchor_lengths_m={name: number(mapping(raw, "longitudes_rectas_anclaje_disponibles_m"), name)
                          for name in mapping(raw, "longitudes_rectas_anclaje_disponibles_m")})
