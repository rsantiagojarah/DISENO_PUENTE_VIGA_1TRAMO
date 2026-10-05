"""Nine independent dimensions, then the shared materials/load/soil workflow."""

from bridge_design.cli.abutment_input_prompts import _collect_materials, _collect_loads, _collect_soil, _prompt_gamma_eq
from bridge_design.cli.connected_2_yaml import GEOMETRY_FIELDS
from bridge_design.cli.connected_prompts import collect_connected_inputs
from bridge_design.cli.input_prompts import prompt_float, prompt_non_negative_float
from bridge_design.domain.abutment import AbutmentInputs, AbutmentKeyInputs, GAMMA_EQ_DEFAULT
from bridge_design.domain.connected_2_inputs import Connected2Geometry, connected_2_inputs
from bridge_design.domain.connected_defaults import connected_load_defaults


def collect_connected_2_inputs():
    print("DISENO DE ESTRIBOS CONECTADOS 2 - BASE UNIFORME - FRANJA DE 1.00 m")
    print("Dimensiones de ver_2l.pdf editables. Enter conserva el valor mostrado.")
    print("Una geometria comun: trasdos vertical, relleno hasta el parapeto y sin relleno interior.")
    print("Materiales, suelo y altura adicional de frenado son referenciales, no datos del PDF.")
    defaults = Connected2Geometry()
    values = {}
    for _, attr, label in GEOMETRY_FIELDS:
        prompt = prompt_non_negative_float if attr == "bearing_extra_height_m" else prompt_float
        values[attr] = prompt(label, "m", getattr(defaults, attr))
    geometry = Connected2Geometry(**values)
    g = geometry.abutment_geometry()
    print(f"Dimensiones calculadas: espesor superior={g.upper_stem_thickness_m:.3f} m; "
          f"luz inferior={geometry.lower_clear_span_m:.3f} m; "
          f"ancho total={geometry.lower_clear_span_m + 2*g.footing_width_m:.3f} m; "
          f"altura total de relleno={g.retained_height_m:.3f} m.")
    materials = _collect_materials()
    loads = _collect_loads(connected_load_defaults(), "REACCIONES DEL TABLERO - ESTRIBO IZQUIERDO")
    soil = _collect_soil(g, fixed_backface_angle=90.0)
    side = AbutmentInputs(geometry=g, materials=materials, loads=loads, soil=soil,
                         key=AbutmentKeyInputs(enabled=False), gamma_eq=_prompt_gamma_eq(GAMMA_EQ_DEFAULT))
    return connected_2_inputs(collect_connected_inputs(
        side=side, collect_detailing=False,
        foundation_geometry=(geometry.lower_clear_span_m, g.footing_thickness_m, 0.0, 0.0)))
