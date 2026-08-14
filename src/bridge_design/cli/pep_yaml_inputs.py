"""YAML template and loader for diseno-apoyos-PEP (modulo aislado)."""

from __future__ import annotations

from typing import Any

from bridge_design.domain.pep_bearing import (
    PepAnchorGroup,
    PepBearingInputs,
    PepConcreteSupport,
    PepExternalPlate,
    PepGeometry,
    PepServiceDemands,
    PepTemperature,
)

YamlMap = dict[str, Any]


def pep_yaml_template() -> YamlMap:
    """Spanish YAML template for PEP fixed/movable bearings."""
    return {
        "comando": "diseno-apoyos-PEP",
        "modo": "DISENAR",
        "tipo_apoyo": "MOVIL_PEP_CORTE",
        "recorrido_carga_fijo": "RESTRICCION_EXTERNA",
        "auto_placas": True,
        "auto_anclajes": True,
        "geometria_pep": {
            "largo_l_cm": 50.0,
            "ancho_w_cm": 50.0,
            "espesor_h_cm": 3.5,
        },
        "material": {
            "dureza_shore_a": 60,
            "g_especificado_kg_cm2": None,
            "fuente_epsilon": "curva_aashto",
        },
        "demandas": {
            "r_dc_tn": 40.0,
            "r_dw_tn": 4.0,
            "r_ll_tn": 20.0,
            "r_im_tn": 0.0,
            "r_min_tn": None,
            "h_long_tn": 5.0,
            "h_eq_long_tn": None,
            "delta_s_cm": None,
            "luz_tramo_m": 25.0,
            "zona_climatica_mtc": "costa",
            "temperatura_instalacion_c": 20.0,
            "retraccion_cm": 0.0,
            "pretensado_cm": 0.0,
            "gamma_tu": 1.2,
            "theta_total_rad": 0.0,
        },
        "demandas_adicionales": [],
        "sismo": {
            "pga": 0.20,
            "fpga": 1.00,
            "zona_sismica": 1,
            "mu_friccion": 0.20,
        },
        "placa_superior": {
            "incluir": False,
            "largo_cm": 70.0,
            "ancho_cm": 70.0,
            "espesor_cm": 2.5,
            "fy_kg_cm2": 2530.0,
            "fu_kg_cm2": 4080.0,
        },
        "placa_inferior": {
            "incluir": False,
            "largo_cm": 70.0,
            "ancho_cm": 70.0,
            "espesor_cm": 2.5,
            "fy_kg_cm2": 2530.0,
            "fu_kg_cm2": 4080.0,
        },
        "anclajes": {
            "incluir": False,
            "n_pernos": 4,
            "diametro_cm": 2.2,
            "fy_kg_cm2": 4220.0,
            "fu_kg_cm2": 6330.0,
            "longitud_anclaje_cm": 30.0,
            "nota_disposicion": "rectangular fuera del PEP",
            "excepcion_pernos_atraviesan_pep": False,
            "coordenadas_cm": [],
        },
        "concreto": {
            "verificar": True,
            "fc_kg_cm2": 210.0,
            "area_a2_cm2": None,
        },
    }


def _section(data: YamlMap, key: str) -> YamlMap:
    value = data.get(key, {})
    return value if isinstance(value, dict) else {}


def _value(section: YamlMap, key: str, default: Any) -> Any:
    if key not in section or section[key] is None:
        return default
    return section[key]


def _float_or_none(section: YamlMap, key: str) -> float | None:
    value = section.get(key)
    if value is None:
        return None
    return float(value)


def _bool(section: YamlMap, key: str, default: bool) -> bool:
    value = section.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "si", "s", "yes", "y"}
    return bool(value)


def _plate(section: YamlMap) -> PepExternalPlate | None:
    if not _bool(section, "incluir", False):
        return None
    return PepExternalPlate(
        length_cm=float(_value(section, "largo_cm", 40.0)),
        width_cm=float(_value(section, "ancho_cm", 50.0)),
        thickness_cm=float(_value(section, "espesor_cm", 2.0)),
        fy_kg_cm2=float(_value(section, "fy_kg_cm2", 2530.0)),
        fu_kg_cm2=float(_value(section, "fu_kg_cm2", 4080.0)),
    )


def _demands_from_section(dem: YamlMap, site_acceleration_as: float = 0.20) -> PepServiceDemands:
    zone = str(_value(dem, "zona_climatica_mtc", "costa")).lower()
    temperature = PepTemperature.mtc_default(
        zone,  # type: ignore[arg-type]
        t_install_c=float(_value(dem, "temperatura_instalacion_c", 20.0)),
    )
    r_dc = float(_value(dem, "r_dc_tn", 40.0))
    r_dw = float(_value(dem, "r_dw_tn", 4.0))
    h_eq_long = _float_or_none(dem, "h_eq_long_tn")
    if h_eq_long is None:
        h_eq_long = site_acceleration_as * (r_dc + r_dw)
    theta_total = _float_or_none(dem, "theta_total_rad")
    if theta_total is None:
        theta_initial = float(_value(dem, "theta_inicial_rad", 0.0))
        theta_dc = float(_value(dem, "theta_dc_rad", 0.0))
        theta_dw = float(_value(dem, "theta_dw_rad", 0.0))
        theta_ll = float(_value(dem, "theta_ll_rad", 0.0))
        theta_other = float(_value(dem, "theta_otros_rad", 0.0))
    else:
        theta_initial = theta_total
        theta_dc = theta_dw = theta_ll = theta_other = 0.0
    return PepServiceDemands(
        combination_id=str(_value(dem, "combination_id", "SERVICIO_I")),
        load_case_id=str(_value(dem, "load_case_id", "DC+DW+LL")),
        position_id=str(_value(dem, "position_id", "POS_1")),
        bearing_id=str(_value(dem, "bearing_id", "APOYO_1")),
        r_dc_tn=r_dc,
        r_dw_tn=r_dw,
        r_ll_tn=float(_value(dem, "r_ll_tn", 20.0)),
        r_im_tn=float(_value(dem, "r_im_tn", 0.0)),
        r_min_tn=_float_or_none(dem, "r_min_tn"),
        h_long_tn=float(_value(dem, "h_long_tn", 0.0)),
        h_trans_tn=float(_value(dem, "h_trans_tn", 0.0)),
        h_eq_long_tn=h_eq_long,
        h_eq_trans_tn=float(_value(dem, "h_eq_trans_tn", 0.0)),
        delta_s_cm=_float_or_none(dem, "delta_s_cm"),
        delta_plus_cm=_float_or_none(dem, "delta_plus_cm"),
        delta_minus_cm=_float_or_none(dem, "delta_minus_cm"),
        span_length_m=float(_value(dem, "luz_tramo_m", 25.0)),
        shrinkage_cm=float(_value(dem, "retraccion_cm", 0.0)),
        prestress_cm=float(_value(dem, "pretensado_cm", 0.0)),
        creep_cm=float(_value(dem, "creep_cm", 0.0)),
        settlement_cm=float(_value(dem, "asentamiento_cm", 0.0)),
        other_perm_cm=float(_value(dem, "otros_perm_cm", 0.0)),
        gamma_tu=float(_value(dem, "gamma_tu", 1.2)),
        temperature=temperature,
        theta_initial_rad=theta_initial,
        theta_dc_rad=theta_dc,
        theta_dw_rad=theta_dw,
        theta_ll_rad=theta_ll,
        theta_other_rad=theta_other,
    )


def pep_inputs_from_yaml(data: YamlMap) -> PepBearingInputs:
    """Build PEP inputs from Spanish YAML."""
    geom = _section(data, "geometria_pep")
    mat = _section(data, "material")
    dem = _section(data, "demandas")
    seis = _section(data, "sismo")
    conc = _section(data, "concreto")
    anc = _section(data, "anclajes")
    pga = _float_or_none(seis, "pga")
    fpga = _float_or_none(seis, "fpga")
    if pga is not None or fpga is not None:
        pga = 0.20 if pga is None else pga
        fpga = 1.00 if fpga is None else fpga
        site_acceleration_as = pga * fpga
    else:
        site_acceleration_as = float(_value(seis, "as_sitio", 0.20))
    primary = _demands_from_section(dem, site_acceleration_as)
    extra_raw = data.get("demandas_adicionales", [])
    extra: list[PepServiceDemands] = []
    if isinstance(extra_raw, list):
        for item in extra_raw:
            if isinstance(item, dict):
                merged = dict(dem)
                merged.update(item)
                extra.append(_demands_from_section(merged, site_acceleration_as))
    concrete = None
    if _bool(conc, "verificar", True):
        concrete = PepConcreteSupport(
            fc_kg_cm2=float(_value(conc, "fc_kg_cm2", 210.0)),
            support_area_cm2=_float_or_none(conc, "area_a2_cm2"),
        )
    anchors = None
    if _bool(anc, "incluir", False):
        coords_raw = anc.get("coordenadas_cm") or []
        coords: tuple[tuple[float, float], ...] = ()
        if isinstance(coords_raw, list) and coords_raw:
            coords = tuple((float(p[0]), float(p[1])) for p in coords_raw)
        anchors = PepAnchorGroup(
            n_bolts=int(_value(anc, "n_pernos", 4)),
            diameter_cm=float(_value(anc, "diametro_cm", 1.9)),
            fy_kg_cm2=float(_value(anc, "fy_kg_cm2", 4220.0)),
            fu_kg_cm2=float(_value(anc, "fu_kg_cm2", 6330.0)),
            embedment_cm=float(_value(anc, "longitud_anclaje_cm", 30.0)),
            layout_note=str(_value(anc, "nota_disposicion", "fuera del PEP")),
            coordinates_cm=coords,
        )
    return PepBearingInputs(
        tipo_apoyo=str(_value(data, "tipo_apoyo", "MOVIL_PEP_CORTE")),  # type: ignore[arg-type]
        geometry=PepGeometry(
            length_cm=float(_value(geom, "largo_l_cm", 30.0)),
            width_cm=float(_value(geom, "ancho_w_cm", 40.0)),
            thickness_cm=float(_value(geom, "espesor_h_cm", 4.0)),
        ),
        demands=primary,
        hardness=int(_value(mat, "dureza_shore_a", 60)),  # type: ignore[arg-type]
        g_specified_kg_cm2=_float_or_none(mat, "g_especificado_kg_cm2"),
        fixed_restraint_load_path=str(_value(data, "recorrido_carga_fijo", "RESTRICCION_EXTERNA")),  # type: ignore[arg-type]
        epsilon_source=str(_value(mat, "fuente_epsilon", "curva_aashto")),  # type: ignore[arg-type]
        epsilon_permanent=_float_or_none(mat, "epsilon_permanente"),
        epsilon_total=_float_or_none(mat, "epsilon_total"),
        friction_coefficient=float(_value(seis, "mu_friccion", 0.20)),
        site_acceleration_as=site_acceleration_as,
        seismic_pga=pga,
        seismic_fpga=fpga,
        seismic_zone=int(_value(seis, "zona_sismica", 1)),
        upper_plate=_plate(_section(data, "placa_superior")),
        lower_plate=_plate(_section(data, "placa_inferior")),
        anchors=anchors,
        concrete_support=concrete,
        bolts_through_pep_exception=_bool(anc, "excepcion_pernos_atraviesan_pep", False),
        mode=str(_value(data, "modo", "DISENAR")),  # type: ignore[arg-type]
        design_plates_auto=_bool(data, "auto_placas", True),
        design_anchors_auto=_bool(data, "auto_anclajes", True),
        demand_cases=tuple(extra),
    )
