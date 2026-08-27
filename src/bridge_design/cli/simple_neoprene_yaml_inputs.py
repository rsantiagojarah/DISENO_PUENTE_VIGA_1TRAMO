"""Plantilla y conversor YAML para apoyos de neopreno simple."""

from __future__ import annotations

from typing import Any

from bridge_design.domain.simple_neoprene_support import (
    ExternalSteelPlatePair,
    FixedBarGroup,
    SimpleNeopreneGeometry,
    SimpleSupportInputs,
    SimpleSupportType,
    SimpleSupportDemands,
    climate_temperature,
)

YamlMap = dict[str, Any]


def simple_neoprene_yaml_template() -> YamlMap:
    """Devuelve una plantilla completa para apoyo fijo o movil."""
    return {
        "version_esquema": 1,
        "comando": "diseno-apoyos-neopreno",
        "nota": (
            "Seleccione tipo_apoyo FIJO_BARRAS o MOVIL_PLACAS. "
            "La seccion no utilizada se conserva como referencia y no interviene en el calculo."
        ),
        "tipo_apoyo": "FIJO_BARRAS",
        "geometria_neopreno": {
            "largo_l_cm": 40.0,
            "ancho_w_cm": 40.0,
            "espesor_h_cm": 5.0,
        },
        "material_neopreno": {
            "dureza_shore_a": 60,
            "coeficiente_friccion_mu": 0.20,
        },
        "reacciones_verticales_por_apoyo": {
            "r_dc_tn": 20.0,
            "r_dw_tn": 1.20,
            "r_pl_peatonal_tn": 0.0,
            "r_ll_mas_im_tn": 29.40,
        },
        "acciones_horizontales": {
            "br_frenado_nominal_tn": 0.0,
            "pga": 0.48,
            "fpga": 1.08,
        },
        "movimiento_termico": {
            "luz_tramo_m": 15.0,
            "zona_climatica_mtc": "costa",
            "temperatura_instalacion_c": 20.0,
            "gamma_tu": 1.20,
            "coeficiente_dilatacion_por_c": 0.0000108,
        },
        "pasadores_apoyo_fijo": {
            "numero_barras": 4,
            "diametro_cm": 2.54,
            "separacion_longitudinal_cm": 20.0,
            "separacion_transversal_cm": 15.0,
            "fy_kg_cm2": 2500.0,
            "brazo_entre_contactos_cm": 5.0,
        },
        "planchas_apoyo_movil": {
            "espesor_superior_inferior_cm": 2.54,
            "fy_a36_kg_cm2": 2530.0,
            "fu_a36_kg_cm2": 4080.0,
        },
        "concreto": {
            "fc_pedestal_estribo_kg_cm2": 210.0,
        },
        # Debe permanecer como ultima seccion para que el esquema cierre la plantilla.
        "esquema_referencia": {
            "fijo_barras": (
                "ELEVACION - APOYO FIJO\n"
                "          VIGA / SUPERESTRUCTURA\n"
                "     ===========================\n"
                "          |    |    |    |       pasadores lisos\n"
                "          | [ NEOPRENO ] |\n"
                "     ===========================\n"
                "             PEDESTAL\n"
                "\n"
                "PLANTA L x W: los pasadores forman una grilla rectangular\n"
                "     o-----------o\n"
                "     |           |\n"
                "     o-----------o\n"
            ),
            "movil_placas": (
                "ELEVACION - APOYO MOVIL\n"
                "          VIGA / SUPERESTRUCTURA\n"
                "     ===========================  plancha superior A36\n"
                "             [ NEOPRENO ]          <--> movimiento\n"
                "     ===========================  plancha inferior A36\n"
                "             PEDESTAL\n"
            ),
            "nota": (
                "Esquema referencial no a escala. L es el largo longitudinal y W el ancho transversal."
            ),
        },
    }


def simple_neoprene_inputs_from_yaml(data: YamlMap) -> SimpleSupportInputs:
    """Construye y valida los datos de apoyo desde una plantilla YAML."""
    geometry = _section(data, "geometria_neopreno")
    material = _section(data, "material_neopreno")
    vertical = _section(data, "reacciones_verticales_por_apoyo")
    horizontal = _section(data, "acciones_horizontales")
    thermal = _section(data, "movimiento_termico")
    fixed = _section(data, "pasadores_apoyo_fijo")
    movable = _section(data, "planchas_apoyo_movil")
    concrete = _section(data, "concreto")

    support_type = _support_type(_value(data, "tipo_apoyo", "FIJO_BARRAS"))
    zone = str(_value(thermal, "zona_climatica_mtc", "costa")).strip().lower()
    if zone not in {"costa", "sierra", "selva"}:
        raise ValueError("zona_climatica_mtc debe ser costa, sierra o selva.")
    temperature_installation = float(
        _value(thermal, "temperatura_instalacion_c", 20.0)
    )

    fixed_bars = None
    plates = None
    if support_type == "FIJO_BARRAS":
        fixed_bars = FixedBarGroup(
            n_bars=int(_value(fixed, "numero_barras", 4)),
            diameter_cm=float(_value(fixed, "diametro_cm", 2.54)),
            spacing_long_cm=float(
                _value(fixed, "separacion_longitudinal_cm", 20.0)
            ),
            spacing_trans_cm=float(
                _value(fixed, "separacion_transversal_cm", 15.0)
            ),
            fy_kg_cm2=float(_value(fixed, "fy_kg_cm2", 2500.0)),
            moment_arm_cm=float(
                _value(fixed, "brazo_entre_contactos_cm", 5.0)
            ),
        )
    else:
        plates = ExternalSteelPlatePair(
            thickness_cm=float(
                _value(movable, "espesor_superior_inferior_cm", 2.54)
            ),
            fy_kg_cm2=float(_value(movable, "fy_a36_kg_cm2", 2530.0)),
            fu_kg_cm2=float(_value(movable, "fu_a36_kg_cm2", 4080.0)),
        )

    return SimpleSupportInputs(
        support_type=support_type,
        geometry=SimpleNeopreneGeometry(
            length_cm=float(_value(geometry, "largo_l_cm", 40.0)),
            width_cm=float(_value(geometry, "ancho_w_cm", 40.0)),
            thickness_cm=float(_value(geometry, "espesor_h_cm", 5.0)),
        ),
        demands=SimpleSupportDemands(
            r_dc_tn=float(_value(vertical, "r_dc_tn", 20.0)),
            r_dw_tn=float(_value(vertical, "r_dw_tn", 1.20)),
            r_pl_tn=float(_value(vertical, "r_pl_peatonal_tn", 0.0)),
            r_ll_im_tn=float(_value(vertical, "r_ll_mas_im_tn", 29.40)),
            h_long_tn=float(
                _value(horizontal, "br_frenado_nominal_tn", 0.0)
            ),
            pga=float(_value(horizontal, "pga", 0.48)),
            fpga=float(_value(horizontal, "fpga", 1.08)),
            span_length_m=float(_value(thermal, "luz_tramo_m", 15.0)),
            temperature=climate_temperature(zone, temperature_installation),
            gamma_tu=float(_value(thermal, "gamma_tu", 1.20)),
            alpha_per_c=float(
                _value(thermal, "coeficiente_dilatacion_por_c", 0.0000108)
            ),
        ),
        hardness=int(_value(material, "dureza_shore_a", 60)),
        fixed_bars=fixed_bars,
        plates=plates,
        fc_kg_cm2=float(
            _value(concrete, "fc_pedestal_estribo_kg_cm2", 210.0)
        ),
        friction_coefficient=float(
            _value(material, "coeficiente_friccion_mu", 0.20)
        ),
    )


def _section(data: YamlMap, key: str) -> YamlMap:
    value = data.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"La seccion '{key}' debe ser un mapa YAML.")
    return value


def _value(data: YamlMap, key: str, default: Any) -> Any:
    value = data.get(key, default)
    return default if value is None else value


def _support_type(value: Any) -> SimpleSupportType:
    normalized = str(value).strip().upper().replace("-", "_")
    aliases = {
        "FIJO": "FIJO_BARRAS",
        "FIJO_BARRAS": "FIJO_BARRAS",
        "MOVIL": "MOVIL_PLACAS",
        "MOVIL_PLACAS": "MOVIL_PLACAS",
    }
    if normalized not in aliases:
        raise ValueError("tipo_apoyo debe ser FIJO_BARRAS o MOVIL_PLACAS.")
    return aliases[normalized]  # type: ignore[return-value]
