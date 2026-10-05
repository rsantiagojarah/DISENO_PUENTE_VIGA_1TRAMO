"""Compact geometry schema; delegate all other input parsing to connected YAML."""

from copy import deepcopy

from bridge_design.cli.connected_yaml import (
    connected_inputs_from_yaml, connected_yaml_template, mapping, number,
)
from bridge_design.domain.connected_2_inputs import Connected2Geometry, connected_2_inputs


COMMAND = "diseno-estribos-conectados-2"
# One source for YAML keys, console prompts and defaults. Every independent
# dimension is editable; the three redundant span/width dimensions are derived.
GEOMETRY_FIELDS = (
    ("luz_libre_superior_m", "upper_clear_span_m", "Luz libre entre caras interiores al nivel del asiento"),
    ("altura_pantalla_hasta_asiento_m", "stem_body_height_m", "Altura de pantalla desde cara superior de base hasta asiento"),
    ("altura_parapeto_m", "parapet_height_m", "Altura del parapeto sobre el asiento"),
    ("espesor_parapeto_m", "parapet_thickness_m", "Espesor del parapeto"),
    ("longitud_asiento_m", "seat_length_m", "Longitud horizontal del asiento del tablero"),
    ("espesor_inferior_pantalla_m", "stem_base_thickness_m", "Espesor inferior de pantalla"),
    ("longitud_talon_exterior_m", "outer_heel_m", "Longitud del talon exterior"),
    ("espesor_cimentacion_m", "foundation_thickness_m", "Espesor uniforme de toda la cimentacion"),
    ("altura_adicional_frenado_m", "bearing_extra_height_m", "Altura adicional sobre coronacion para el brazo de frenado"),
)


def connected_2_yaml_template(*, example=False):
    data = connected_yaml_template(example=example)
    geometry = Connected2Geometry()
    data["comando"] = COMMAND
    data["nota"] = (
        "Geometria inicial editable de ver_2l.pdf. Ambos estribos son iguales; base uniforme, "
        "trasdos vertical y cara interior inclinada. Relleno hasta coronacion del parapeto; "
        "sin relleno interior. Ingrese solo dimensiones independientes. Espesor superior = "
        "asiento + parapeto; luz inferior = luz superior - 2*(espesor inferior - superior); "
        "ancho total = luz inferior + 2*(espesor inferior + talon). "
        "Cargas iniciales conservadas del comando original, editables. Materiales, suelo y "
        "altura adicional de frenado son referenciales, no datos del PDF. "
        "Reacciones izquierda/derecha del mismo posicionamiento del tablero."
    )
    data["estribo"]["geometria"] = {key: getattr(geometry, attr) for key, attr, _ in GEOMETRY_FIELDS}
    data["estribo"]["suelo_sismo"].pop("theta_cara_posterior_desde_horizontal_grados")
    # Let the shared parser recalculate h' from the edited total height.
    data["estribo"]["suelo_sismo"]["h_sobrecarga_vehicular_equivalente_m"] = None
    for key in ("separacion_libre_entre_caras_interiores_m", "espesor_losa_central_m",
                "transicion_izquierda_m", "transicion_derecha_m"):
        data["cimentacion"].pop(key)
    return data


def connected_2_inputs_from_yaml(raw):
    if raw.get("comando", COMMAND) != COMMAND:
        raise ValueError(f"El YAML no corresponde a {COMMAND}.")
    side = mapping(raw, "estribo", True)
    values = mapping(side, "geometria")
    unknown = set(values) - {key for key, _, _ in GEOMETRY_FIELDS}
    if unknown:
        raise ValueError("Dimensiones no admitidas en estribos conectados 2: " + ", ".join(sorted(unknown)))
    defaults = Connected2Geometry()
    geometry = Connected2Geometry(**{
        attr: number(values, key, getattr(defaults, attr)) for key, attr, _ in GEOMETRY_FIELDS
    })
    foundation = mapping(raw, "cimentacion", True)
    allowed = {"cantidad_nudos_cimentacion", "paso_malla_m", "offsets_seccion", "nodo_referencia_x_m"}
    if set(foundation) - allowed:
        raise ValueError("cimentacion solo admite controles de malla, offsets y nodo de referencia; "
                         "las dimensiones se ingresan una vez en estribo.geometria.")
    adapted = deepcopy(raw)
    adapted["comando"] = "diseno-estribos-conectados"
    adapted["estribo"]["geometria"] = {}
    adapted["cimentacion"] = {
        **foundation, "separacion_libre_entre_caras_interiores_m": geometry.lower_clear_span_m,
        "espesor_losa_central_m": geometry.foundation_thickness_m,
        "transicion_izquierda_m": 0.0, "transicion_derecha_m": 0.0,
    }
    return connected_2_inputs(connected_inputs_from_yaml(
        adapted, geometry_defaults=geometry.abutment_geometry()))
