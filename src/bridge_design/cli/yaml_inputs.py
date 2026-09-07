"""Spanish YAML templates and converters for design commands."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from bridge_design.cli.input_prompts import _default_diaphragm_positions
from bridge_design.domain.abutment import (
    AbutmentGeometryInputs,
    AbutmentInputs,
    AbutmentKeyInputs,
    AbutmentLoadInputs,
    AbutmentMaterialInputs,
    AbutmentSoilInputs,
    GAMMA_EQ_DEFAULT,
    equivalent_vehicular_surcharge_height_m,
)
from bridge_design.domain.cantilever_wall import cantilever_wall_geometry_inputs, cantilever_wall_load_inputs
from bridge_design.domain.barrier import (
    BarrierDesignInputs,
    BarrierGeometry,
    BarrierImpactLoad,
    BarrierSectionModel,
)
from bridge_design.domain.diaphragm import DiaphragmBeamGeometry
from bridge_design.domain.elastomeric_bearing import (
    BearingLoads,
    BearingMovements,
    ConcreteBearingSupport,
    ElastomericBearingInputs,
    SeismicBearingInputs,
    TemperatureRange,
)
from bridge_design.domain.exterior_girder import (
    ExteriorGirderGeometry,
    exterior_asphalt_tributary_width_m,
)
from bridge_design.domain.interior_girder import (
    DiaphragmGeometry,
    InteriorGirderGeometry,
)
from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel
from bridge_design.domain.materials import (
    ConcreteProperties,
    LinearWeightProperties,
    MaterialProperties,
    SteelProperties,
    SurfaceLayerProperties,
)
from bridge_design.domain.project_inputs import ProjectInputs
from bridge_design.domain.transverse_slab import (
    TransverseLoadLayout,
    TransverseSlabDesignInputs,
    TransverseSlabGeometry,
    validate_layout_inside_geometry,
)

YamlMap = dict[str, Any]


def _section(data: YamlMap, key: str) -> YamlMap:
    value = data.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"La seccion '{key}' debe ser un mapa YAML.")
    return value


def _value(data: YamlMap, key: str, default: Any) -> Any:
    return data.get(key, default)


def _bool(data: YamlMap, key: str, default: bool) -> bool:
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"s", "si", "true", "verdadero", "1", "yes", "y"}:
            return True
        if raw in {"n", "no", "false", "falso", "0"}:
            return False
    raise ValueError(f"El campo '{key}' debe ser verdadero/falso.")


def _float_or_none(data: YamlMap, key: str, default: float | None) -> float | None:
    value = data.get(key, default)
    if value is None:
        return None
    return float(value)


def _template_header(command: str) -> YamlMap:
    return {
        "version_esquema": 1,
        "comando": command,
        "nota": "Complete o modifique los valores. Las unidades estan indicadas en cada clave.",
    }


def abutment_yaml_template(*, pure_wall: bool = False) -> YamlMap:
    """Return a Spanish YAML template for abutment or cantilever wall inputs."""
    g = cantilever_wall_geometry_inputs() if pure_wall else AbutmentGeometryInputs()
    m = AbutmentMaterialInputs()
    loads = cantilever_wall_load_inputs() if pure_wall else AbutmentLoadInputs()
    soil = AbutmentSoilInputs()
    front_soil_depth_m = g.footing_thickness_m if pure_wall else g.front_soil_depth_m
    geometry: YamlMap = {
        "altura_relleno_activo_m": g.retained_height_m,
    }
    if not pure_wall:
        geometry["luz_puente_m"] = g.bridge_length_m
    geometry.update(
        {
            "ancho_zapata_m": g.footing_width_m,
            "espesor_zapata_m": g.footing_thickness_m,
            "longitud_puntera_m": g.toe_length_m,
            "espesor_inferior_pantalla_m": g.lower_stem_thickness_m,
            "espesor_superior_pantalla_m": g.upper_stem_thickness_m,
            "altura_suelo_frontal_m": front_soil_depth_m,
        }
    )
    if not pure_wall:
        geometry.update(
            {
                "transicion_frontal_superior_t1_m": g.small_batter_width_m,
                "retiro_superior_relleno_t2_m": g.backfill_step_width_m,
                "longitud_cajuela_m": g.bearing_seat_length_m,
                "espesor_parapeto_posterior_m": g.seat_wall_width_m,
                "altura_cajuela_m": g.seat_block_height_m,
                "altura_bloque_cajuela_m": g.backwall_drop_m,
                "altura_transicion_m": g.backwall_taper_height_m,
            }
        )
    data = _template_header("diseno-muros" if pure_wall else "diseno-estribos")
    data.update(
        {
            "geometria": geometry,
            "materiales": {
                "fc_concreto_kg_cm2": m.concrete_strength_kg_cm2,
                "fy_acero_kg_cm2": m.steel_yield_kg_cm2,
                "peso_unitario_concreto_tn_m3": m.concrete_unit_weight_kg_m3 / 1000.0,
                "peso_unitario_relleno_tn_m3": m.soil_unit_weight_kg_m3 / 1000.0,
            },
            "suelo_sismo": {
                "h_sobrecarga_vehicular_equivalente_m": equivalent_vehicular_surcharge_height_m(g.retained_height_m),
                "qadm_capacidad_portante_kg_cm2": soil.allowable_bearing_kg_cm2,
                "angulo_friccion_relleno_grados": soil.friction_angle_deg,
                "delta_muro_suelo_grados": soil.wall_soil_friction_deg,
                "beta_pendiente_relleno_grados": soil.backfill_slope_deg,
                "theta_cara_posterior_desde_horizontal_grados": soil.wall_backface_angle_deg,
                "fs_capacidad_portante_nominal": soil.bearing_capacity_factor_fs,
                "pga": soil.pga,
                "fpga": soil.fpga,
                "gamma_eq": GAMMA_EQ_DEFAULT,
                "sobrecarga_peatonal_relleno_tn_m2": soil.pedestrian_surcharge_tn_m2,
            },
        }
    )
    if not pure_wall:
        data = {
            **{key_name: data[key_name] for key_name in ("version_esquema", "comando", "nota", "geometria", "materiales")},
            "cargas_tablero": {
                "pdc_carga_muerta_tablero_tn_m": loads.pdc_tn_m,
                "pdw_superficie_tn_m": loads.pdw_tn_m,
                "ppl_peatonal_tablero_tn_m": loads.ppl_tn_m,
                "pll_im_vehicular_tn_m": loads.pll_im_tn_m,
                "br_frenado_tn_m": loads.braking_tn_m,
            },
            "suelo_sismo": data["suelo_sismo"],
        }
    return data


def abutment_inputs_from_yaml(data: YamlMap, *, pure_wall: bool = False) -> AbutmentInputs:
    """Build abutment or wall inputs from Spanish YAML data."""
    g0 = AbutmentGeometryInputs()
    if pure_wall:
        g0 = cantilever_wall_geometry_inputs(g0)
    m0 = AbutmentMaterialInputs()
    l0 = cantilever_wall_load_inputs() if pure_wall else AbutmentLoadInputs()
    s0 = AbutmentSoilInputs()
    g = _section(data, "geometria")
    m = _section(data, "materiales")
    loads = _section(data, "cargas_tablero")
    soil = _section(data, "suelo_sismo")

    geometry = AbutmentGeometryInputs(
        retained_height_m=float(_value(g, "altura_relleno_activo_m", g0.retained_height_m)),
        bridge_length_m=float(_value(g, "luz_puente_m", g0.bridge_length_m)),
        seat_block_height_m=float(_value(g, "altura_cajuela_m", 0.0 if pure_wall else g0.seat_block_height_m)),
        seat_wall_width_m=float(_value(g, "espesor_parapeto_posterior_m", 0.0 if pure_wall else g0.seat_wall_width_m)),
        bearing_seat_length_m=float(_value(g, "longitud_cajuela_m", 0.0 if pure_wall else g0.bearing_seat_length_m)),
        backwall_drop_m=float(_value(g, "altura_bloque_cajuela_m", 0.0 if pure_wall else g0.backwall_drop_m)),
        backwall_taper_height_m=float(_value(g, "altura_transicion_m", 0.0 if pure_wall else g0.backwall_taper_height_m)),
        backfill_step_width_m=float(_value(g, "retiro_superior_relleno_t2_m", 0.0 if pure_wall else g0.backfill_step_width_m)),
        top_step_thickness_m=g0.top_step_thickness_m,
        small_batter_width_m=float(_value(g, "transicion_frontal_superior_t1_m", 0.0 if pure_wall else g0.small_batter_width_m)),
        upper_stem_thickness_m=float(_value(g, "espesor_superior_pantalla_m", g0.upper_stem_thickness_m)),
        lower_stem_thickness_m=float(_value(g, "espesor_inferior_pantalla_m", g0.lower_stem_thickness_m)),
        footing_width_m=float(_value(g, "ancho_zapata_m", g0.footing_width_m)),
        footing_thickness_m=float(_value(g, "espesor_zapata_m", g0.footing_thickness_m)),
        toe_length_m=float(_value(g, "longitud_puntera_m", g0.toe_length_m)),
        front_soil_depth_m=float(_value(g, "altura_suelo_frontal_m", g0.footing_thickness_m if pure_wall else g0.front_soil_depth_m)),
        bridge_seat_to_bearing_height_m=float(_value(g, "altura_apoyo_a_cajuela_m", g0.bridge_seat_to_bearing_height_m)),
        strip_width_m=float(_value(g, "franja_analisis_m", g0.strip_width_m)),
    )
    materials = AbutmentMaterialInputs(
        concrete_strength_kg_cm2=float(_value(m, "fc_concreto_kg_cm2", m0.concrete_strength_kg_cm2)),
        steel_yield_kg_cm2=float(_value(m, "fy_acero_kg_cm2", m0.steel_yield_kg_cm2)),
        concrete_unit_weight_kg_m3=float(_value(m, "peso_unitario_concreto_tn_m3", m0.concrete_unit_weight_kg_m3 / 1000.0)) * 1000.0,
        soil_unit_weight_kg_m3=float(_value(m, "peso_unitario_relleno_tn_m3", m0.soil_unit_weight_kg_m3 / 1000.0)) * 1000.0,
    )
    if pure_wall:
        geometry = cantilever_wall_geometry_inputs(geometry)
        load_inputs = cantilever_wall_load_inputs()
    else:
        load_inputs = AbutmentLoadInputs(
            pdc_tn_m=float(_value(loads, "pdc_carga_muerta_tablero_tn_m", l0.pdc_tn_m)),
            pdw_tn_m=float(_value(loads, "pdw_superficie_tn_m", l0.pdw_tn_m)),
            ppl_tn_m=float(_value(loads, "ppl_peatonal_tablero_tn_m", l0.ppl_tn_m)),
            pll_im_tn_m=float(_value(loads, "pll_im_vehicular_tn_m", l0.pll_im_tn_m)),
            braking_tn_m=float(_value(loads, "br_frenado_tn_m", l0.braking_tn_m)),
        )
    soil_inputs = AbutmentSoilInputs(
        allowable_bearing_kg_cm2=float(_value(soil, "qadm_capacidad_portante_kg_cm2", s0.allowable_bearing_kg_cm2)),
        friction_angle_deg=float(_value(soil, "angulo_friccion_relleno_grados", s0.friction_angle_deg)),
        wall_soil_friction_deg=float(_value(soil, "delta_muro_suelo_grados", s0.wall_soil_friction_deg)),
        backfill_slope_deg=float(_value(soil, "beta_pendiente_relleno_grados", s0.backfill_slope_deg)),
        wall_backface_angle_deg=float(_value(soil, "theta_cara_posterior_desde_horizontal_grados", s0.wall_backface_angle_deg)),
        bearing_capacity_factor_fs=float(_value(soil, "fs_capacidad_portante_nominal", s0.bearing_capacity_factor_fs)),
        pga=float(_value(soil, "pga", s0.pga)),
        fpga=float(_value(soil, "fpga", s0.fpga)),
        vehicular_surcharge_height_m=_float_or_none(
            soil,
            "h_sobrecarga_vehicular_equivalente_m",
            equivalent_vehicular_surcharge_height_m(geometry.retained_height_m),
        ),
        pedestrian_surcharge_tn_m2=float(_value(soil, "sobrecarga_peatonal_relleno_tn_m2", s0.pedestrian_surcharge_tn_m2)),
    )
    key_inputs = AbutmentKeyInputs(enabled=False, passive_soil_height_m=geometry.front_soil_depth_m)
    return AbutmentInputs(
        materials=materials,
        geometry=geometry,
        loads=load_inputs,
        soil=soil_inputs,
        key=key_inputs,
        is_pure_wall=pure_wall,
        gamma_eq=float(_value(soil, "gamma_eq", GAMMA_EQ_DEFAULT)),
    )


def cantilever_wall_yaml_template() -> YamlMap:
    """Return a Spanish YAML template for cantilever wall inputs."""
    return abutment_yaml_template(pure_wall=True)


def cantilever_wall_inputs_from_yaml(data: YamlMap) -> AbutmentInputs:
    """Build cantilever wall inputs from Spanish YAML data."""
    return abutment_inputs_from_yaml(data, pure_wall=True)


def bearing_yaml_template() -> YamlMap:
    """Return a Spanish YAML template for elastomeric bearing inputs."""
    data = _template_header("diseno-apoyos")
    data.update(
        {
            "cargas_servicio_por_apoyo": {
                "dc_carga_muerta_tn": 48.0,
                "dw_superficie_tn": 4.0,
                "ll_carga_viva_sin_impacto_tn": 28.0,
            },
            "movimientos": {
                "luz_tramo_m": 25.0,
                "zona_climatica_mtc": "costa",
                "temperatura_instalacion_c": 20.0,
                "retraccion_concreto_cm": 0.8,
                "acortamiento_pretensado_cm": 0.0,
                "otros_movimientos_permanentes_cm": 0.0,
                "gamma_tu": 1.2,
            },
            "material_geometria": {
                "dureza_shore_a": 60,
                "ancho_viga_apoyo_cm": 40.0,
                "fy_acero_zunchos_kg_cm2": 2530.0,
                # true: usa ancho_adoptado_w_cm y largo_adoptado_l_cm
                # false: W = ancho_viga; L se calcula automaticamente (A_req/W, redondeo)
                "adoptar_dimensiones_planta_manualmente": False,
                "ancho_adoptado_w_cm": 40.0,
                "largo_adoptado_l_cm": 30.0,
            },
            "sismo": {
                "as_sitio": 0.20,
                "zona_sismica": 1,
                "puente_un_solo_tramo": True,
                "tipo_apoyo": "expansion",
                "restringido_longitudinalmente": False,
                "restringido_transversalmente": True,
                "carga_permanente_tributaria_longitudinal_tn": None,
                "coeficiente_friccion_mu": 0.2,
            },
            "aplastamiento_concreto": {
                "verificar": True,
                "fc_pedestal_estribo_kg_cm2": 210.0,
                "indicar_area_a2_pedestal": False,
                "area_a2_pedestal_cm2": None,
            },
        }
    )
    return data


def bearing_inputs_from_yaml(data: YamlMap) -> ElastomericBearingInputs:
    """Build elastomeric bearing inputs from Spanish YAML data."""
    loads = _section(data, "cargas_servicio_por_apoyo")
    movements = _section(data, "movimientos")
    mat = _section(data, "material_geometria")
    seismic = _section(data, "sismo")
    concrete = _section(data, "aplastamiento_concreto")
    zone = str(_value(movements, "zona_climatica_mtc", "costa")).lower()
    t_install = float(_value(movements, "temperatura_instalacion_c", 20.0))
    temperature = TemperatureRange.mtc_default(zone, t_install_c=t_install)  # type: ignore[arg-type]
    bearing_loads = BearingLoads(
        dead_load_dc_tn=float(_value(loads, "dc_carga_muerta_tn", 48.0)),
        wearing_surface_dw_tn=float(_value(loads, "dw_superficie_tn", 4.0)),
        live_load_ll_tn=float(_value(loads, "ll_carga_viva_sin_impacto_tn", 28.0)),
    )
    concrete_support = None
    if _bool(concrete, "verificar", True):
        support_area = (
            _float_or_none(concrete, "area_a2_pedestal_cm2", None)
            if _bool(concrete, "indicar_area_a2_pedestal", False)
            else None
        )
        concrete_support = ConcreteBearingSupport(
            fc_kg_cm2=float(_value(concrete, "fc_pedestal_estribo_kg_cm2", 210.0)),
            support_area_cm2=support_area,
        )
    adopt_dimensions = _bool(mat, "adoptar_dimensiones_planta_manualmente", False)
    return ElastomericBearingInputs(
        loads=bearing_loads,
        movements=BearingMovements(
            span_length_m=float(_value(movements, "luz_tramo_m", 25.0)),
            temperature=temperature,
            shrinkage_cm=float(_value(movements, "retraccion_concreto_cm", 0.8)),
            prestress_shortening_cm=float(_value(movements, "acortamiento_pretensado_cm", 0.0)),
            other_permanent_cm=float(_value(movements, "otros_movimientos_permanentes_cm", 0.0)),
            gamma_tu=float(_value(movements, "gamma_tu", 1.2)),
        ),
        seismic=SeismicBearingInputs(
            site_acceleration_as=float(_value(seismic, "as_sitio", 0.20)),
            seismic_zone=int(_value(seismic, "zona_sismica", 1)),  # type: ignore[arg-type]
            is_single_span=_bool(seismic, "puente_un_solo_tramo", True),
            bearing_role=str(_value(seismic, "tipo_apoyo", "expansion")),  # type: ignore[arg-type]
            longitudinal_restrained=_bool(seismic, "restringido_longitudinalmente", False),
            transverse_restrained=_bool(seismic, "restringido_transversalmente", True),
            tributary_permanent_longitudinal_tn=_float_or_none(
                seismic,
                "carga_permanente_tributaria_longitudinal_tn",
                None,
            ),
            friction_coefficient=float(_value(seismic, "coeficiente_friccion_mu", 0.2)),
        ),
        hardness=int(_value(mat, "dureza_shore_a", 60)),  # type: ignore[arg-type]
        girder_width_cm=float(_value(mat, "ancho_viga_apoyo_cm", 40.0)),
        steel_fy_kg_cm2=float(_value(mat, "fy_acero_zunchos_kg_cm2", 2530.0)),
        adopted_length_cm=_float_or_none(mat, "largo_adoptado_l_cm", 30.0) if adopt_dimensions else None,
        adopted_width_cm=_float_or_none(mat, "ancho_adoptado_w_cm", 40.0) if adopt_dimensions else None,
        concrete_support=concrete_support,
    )


def project_yaml_template() -> YamlMap:
    """Return a Spanish YAML template for the full bridge/deck workflow."""
    geometry = TransverseSlabGeometry(
        girder_spacing_m=2.10,
        overhang_m=0.825,
        girder_count=4,
        slab_thickness_m=0.20,
        girder_total_height_m=1.20,
        girder_width_m=0.30,
    )
    width = geometry.total_width_m
    sidewalk_width = geometry.overhang_m
    barrier_width = 0.25
    barrier_left = sidewalk_width
    asphalt_start = barrier_left + barrier_width
    asphalt_end = width - barrier_left - barrier_width
    layout = TransverseLoadLayout(
        asphalt_start_m=asphalt_start,
        asphalt_end_m=asphalt_end,
        sidewalk_width_m=sidewalk_width,
        railing_left_m=0.13,
        barrier_left_m=barrier_left,
        barrier_width_m=barrier_width,
        vehicle_move_start_m=asphalt_start,
        vehicle_move_end_m=asphalt_end,
        vehicle_step_m=0.10,
    )
    span = 15.0
    diaphragm_positions = _default_diaphragm_positions(span, 3)
    exterior_de = geometry.overhang_m - (layout.barrier_left_m + layout.barrier_width_m)
    data = _template_header("diseno-tablero")
    data.update(
        {
            "modelo_transversal_losa": {
                "separacion_vigas_m": geometry.girder_spacing_m,
                "volado_losa_m": geometry.overhang_m,
                "numero_vigas": geometry.girder_count,
                "espesor_losa_m": geometry.slab_thickness_m,
                "altura_total_viga_m": geometry.girder_total_height_m,
                "ancho_viga_m": geometry.girder_width_m,
            },
            "materiales": {
                "concreto": {
                    "peso_especifico_tn_m3": 2.4,
                    "fc_kg_cm2": 280.0,
                },
                "asfalto": {
                    "peso_especifico_tn_m3": 2.2,
                    "espesor_m": 0.05,
                },
                "vereda": {
                    "peso_especifico_tn_m3": 2.4,
                    "espesor_m": 0.20,
                },
                "baranda": {"peso_lineal_kg_m": 100.0},
                "barrera": {"peso_lineal_kg_m": 500.0},
            },
            "barrera_concreto": {
                "geometria": {
                    "altura_total_m": 0.85,
                    "ancho_base_m": 0.375,
                    "area_seccion_m2": 0.202875,
                    "longitud_disponible_anclaje_cm": 17.5,
                    "momento_adicional_superior_tn_m": 0.0,
                },
                "impacto": {
                    "nivel_ensayo": "TL-4",
                    "fuerza_transversal_tn": 24.47,
                    "longitud_distribucion_m": 1.07,
                    "patron": "segmento",
                },
                "seccion": {
                    "separacion_dowel_m": 0.17,
                },
            },
            "cargas_vivas": {
                "peatonal_veredas_tn_m2": PedestrianLoad.mtc_sidewalk_default().load_tn_m2,
            },
            "ubicacion_cargas_modelo_transversal": {
                "ancho_vereda_cada_lado_m": layout.sidewalk_width_m,
                "ancho_barrera_m": layout.barrier_width_m,
                "ubicacion_barrera_izquierda_m": layout.barrier_left_m,
                "asfalto_inicio_m": layout.asphalt_start_m,
                "asfalto_fin_m": layout.asphalt_end_m,
                "ubicacion_baranda_izquierda_m": layout.railing_left_m,
                "recorrido_vehicular_inicio_m": layout.vehicle_move_start_m,
                "recorrido_vehicular_fin_m": layout.vehicle_move_end_m,
                "paso_movimiento_vehicular_m": layout.vehicle_step_m,
            },
            "viga_interior": {
                "luz_puente_m": span,
                "diafragmas": [
                    {
                        "ubicacion_m": position,
                        "espesor_longitudinal_m": 0.25,
                        "altura_m": max(geometry.girder_total_height_m - 0.10, 0.10),
                        "ancho_tributario_transversal_m": geometry.girder_spacing_m,
                    }
                    for position in diaphragm_positions
                ],
                "paso_carga_movil_m": 0.10,
                "paso_muestreo_momentos_m": 0.10,
            },
            "viga_exterior": {
                "de_alma_exterior_a_cara_interior_barrera_m": exterior_de,
            },
            "diafragma": {
                "espesor_longitudinal_m": 0.25,
                "altura_resistente_m": max(geometry.girder_total_height_m - 0.10, 0.10),
                "longitud_tributaria_cargas_m": 0.25,
                "paso_vehicular_m": 0.10,
            },
        }
    )
    return data


def project_inputs_from_yaml(data: YamlMap) -> ProjectInputs:
    """Build full bridge project inputs from Spanish YAML data."""
    materials = _section(data, "materiales")
    concrete = _section(materials, "concreto")
    steel = _section(materials, "acero")
    asphalt = _section(materials, "asfalto")
    sidewalk = _section(materials, "vereda")
    railing = _section(materials, "baranda")
    barrier_weight = _section(materials, "barrera")
    material_inputs = MaterialProperties(
        concrete=ConcreteProperties.from_inputs(
            specific_weight_tn_m3=float(_value(concrete, "peso_especifico_tn_m3", 2.4)),
            compressive_strength_kg_cm2=float(_value(concrete, "fc_kg_cm2", 280.0)),
        ),
        steel=SteelProperties(
            yield_strength_kg_cm2=float(_value(steel, "fy_kg_cm2", 4200.0)),
            elastic_modulus_kg_cm2=float(_value(steel, "modulo_elasticidad_kg_cm2", 2000000.0)),
        ),
        asphalt=SurfaceLayerProperties(
            name="asfalto",
            specific_weight_tn_m3=float(_value(asphalt, "peso_especifico_tn_m3", 2.2)),
            thickness_m=float(_value(asphalt, "espesor_m", 0.05)),
        ),
        sidewalk=SurfaceLayerProperties(
            name="vereda",
            specific_weight_tn_m3=float(_value(sidewalk, "peso_especifico_tn_m3", 2.4)),
            thickness_m=float(_value(sidewalk, "espesor_m", 0.20)),
        ),
        railing=LinearWeightProperties(name="baranda", weight_kg_m=float(_value(railing, "peso_lineal_kg_m", 100.0))),
        barrier=LinearWeightProperties(name="barrera", weight_kg_m=float(_value(barrier_weight, "peso_lineal_kg_m", 500.0))),
    )
    live = _section(data, "cargas_vivas")
    live_loads = LiveLoads(
        pedestrian=PedestrianLoad(load_tn_m2=float(_value(live, "peatonal_veredas_tn_m2", PedestrianLoad.mtc_sidewalk_default().load_tn_m2))),
        vehicular=VehicleLoadModel.mtc_hl93_default(),
    )
    slab = _section(data, "losa_transversal")
    slab_g = _section(data, "modelo_transversal_losa") if "modelo_transversal_losa" in data else _section(slab, "geometria")
    geometry = TransverseSlabGeometry(
        girder_spacing_m=float(_value(slab_g, "separacion_vigas_m", 2.10)),
        overhang_m=float(_value(slab_g, "volado_losa_m", 0.825)),
        girder_count=int(_value(slab_g, "numero_vigas", 4)),
        slab_thickness_m=float(_value(slab_g, "espesor_losa_m", 0.20)),
        girder_total_height_m=float(_value(slab_g, "altura_total_viga_m", 1.20)),
        girder_width_m=float(_value(slab_g, "ancho_viga_m", 0.30)),
    )
    layout_data = (
        _section(data, "ubicacion_cargas_modelo_transversal")
        if "ubicacion_cargas_modelo_transversal" in data
        else _section(slab, "ubicacion_cargas")
    )
    barrier_left = float(_value(layout_data, "ubicacion_barrera_izquierda_m", geometry.overhang_m))
    barrier_width = float(_value(layout_data, "ancho_barrera_m", 0.25))
    asphalt_start = float(_value(layout_data, "asfalto_inicio_m", barrier_left + barrier_width))
    asphalt_end = float(_value(layout_data, "asfalto_fin_m", geometry.total_width_m - barrier_left - barrier_width))
    layout = TransverseLoadLayout(
        asphalt_start_m=asphalt_start,
        asphalt_end_m=asphalt_end,
        sidewalk_width_m=float(_value(layout_data, "ancho_vereda_cada_lado_m", geometry.overhang_m)),
        railing_left_m=float(_value(layout_data, "ubicacion_baranda_izquierda_m", 0.13)),
        barrier_left_m=barrier_left,
        barrier_width_m=barrier_width,
        vehicle_move_start_m=float(_value(layout_data, "recorrido_vehicular_inicio_m", asphalt_start)),
        vehicle_move_end_m=float(_value(layout_data, "recorrido_vehicular_fin_m", asphalt_end)),
        vehicle_step_m=float(_value(layout_data, "paso_movimiento_vehicular_m", 0.10)),
    )
    validate_layout_inside_geometry(geometry, layout)

    barrier_data = _section(data, "barrera_concreto")
    barrier_geometry = _section(barrier_data, "geometria")
    barrier_impact = _section(barrier_data, "impacto")
    barrier_section = _section(barrier_data, "seccion")
    pattern = str(_value(barrier_impact, "patron", "segmento")).lower()
    impact_pattern = "end" if pattern in {"extremo", "junta", "end", "e"} else "segment"
    section_model = replace(
        BarrierSectionModel.new_jersey_image_default(),
        dowel_spacing_m=float(_value(barrier_section, "separacion_dowel_m", 0.17)),
    )
    barrier_inputs = BarrierDesignInputs(
        geometry=BarrierGeometry(
            height_m=float(_value(barrier_geometry, "altura_total_m", 0.85)),
            base_width_m=float(_value(barrier_geometry, "ancho_base_m", 0.375)),
            cross_section_area_m2=float(_value(barrier_geometry, "area_seccion_m2", 0.202875)),
            available_development_length_cm=float(_value(barrier_geometry, "longitud_disponible_anclaje_cm", 17.5)),
            top_additional_moment_tn_m=float(_value(barrier_geometry, "momento_adicional_superior_tn_m", 0.0)),
        ),
        section_model=section_model,
        impact_load=BarrierImpactLoad(
            test_level=str(_value(barrier_impact, "nivel_ensayo", "TL-4")),
            transverse_force_tn=float(_value(barrier_impact, "fuerza_transversal_tn", 24.47)),
            distribution_length_m=float(_value(barrier_impact, "longitud_distribucion_m", 1.07)),
            pattern=impact_pattern,  # type: ignore[arg-type]
        ),
    )

    interior_data = _section(data, "viga_interior")
    span = float(_value(interior_data, "luz_puente_m", 15.0))
    diaphragms_raw = interior_data.get("diafragmas")
    if diaphragms_raw is None:
        diaphragms_raw = [
            {"ubicacion_m": position}
            for position in _default_diaphragm_positions(span, 3)
        ]
    if not isinstance(diaphragms_raw, list):
        raise ValueError("La seccion 'viga_interior.diafragmas' debe ser una lista.")
    diaphragms = tuple(
        DiaphragmGeometry(
            position_m=float(_value(item, "ubicacion_m", 0.0)),
            thickness_m=float(_value(item, "espesor_longitudinal_m", 0.25)),
            height_m=float(_value(item, "altura_m", max(geometry.girder_total_height_m - 0.10, 0.10))),
            tributary_width_m=float(_value(item, "ancho_tributario_transversal_m", geometry.girder_spacing_m)),
        )
        for item in diaphragms_raw
    )
    interior_girder = InteriorGirderGeometry(
        span_length_m=span,
        girder_spacing_m=geometry.girder_spacing_m,
        slab_thickness_m=geometry.slab_thickness_m,
        girder_total_height_m=geometry.girder_total_height_m,
        web_width_m=geometry.girder_width_m,
        girder_count=geometry.girder_count,
        diaphragms=diaphragms,
        moving_load_step_m=float(_value(interior_data, "paso_carga_movil_m", 0.10)),
        moment_sample_step_m=float(_value(interior_data, "paso_muestreo_momentos_m", 0.10)),
    )
    exterior_data = _section(data, "viga_exterior")
    exterior_tributary_width = geometry.overhang_m + geometry.girder_spacing_m / 2.0
    exterior_diaph = tuple(
        DiaphragmGeometry(
            position_m=diaphragm.position_m,
            thickness_m=diaphragm.thickness_m,
            height_m=diaphragm.height_m,
            tributary_width_m=exterior_tributary_width,
        )
        for diaphragm in interior_girder.diaphragms
    )
    exterior_girder = ExteriorGirderGeometry(
        span_length_m=interior_girder.span_length_m,
        girder_spacing_m=geometry.girder_spacing_m,
        deck_overhang_m=geometry.overhang_m,
        slab_thickness_m=geometry.slab_thickness_m,
        girder_total_height_m=geometry.girder_total_height_m,
        web_width_m=geometry.girder_width_m,
        exterior_web_to_traffic_barrier_m=float(
            _value(
                exterior_data,
                "de_alma_exterior_a_cara_interior_barrera_m",
                geometry.overhang_m - (layout.barrier_left_m + layout.barrier_width_m),
            )
        ),
        sidewalk_width_m=layout.sidewalk_width_m,
        asphalt_tributary_width_m=exterior_asphalt_tributary_width_m(
            deck_overhang_m=geometry.overhang_m,
            girder_spacing_m=geometry.girder_spacing_m,
            asphalt_start_m=layout.asphalt_start_m,
            asphalt_end_m=layout.asphalt_end_m,
        ),
        girder_count=geometry.girder_count,
        diaphragms=exterior_diaph,
        moving_load_step_m=interior_girder.moving_load_step_m,
        moment_sample_step_m=interior_girder.moment_sample_step_m,
    ).with_distribution_factors(live_loads.vehicular)

    diaphragm_data = _section(data, "diafragma")
    diaphragm = DiaphragmBeamGeometry(
        girder_spacing_m=geometry.girder_spacing_m,
        girder_count=geometry.girder_count,
        deck_overhang_m=geometry.overhang_m,
        thickness_m=float(_value(diaphragm_data, "espesor_longitudinal_m", 0.25)),
        height_m=float(_value(diaphragm_data, "altura_resistente_m", max(geometry.girder_total_height_m - 0.10, 0.10))),
        slab_thickness_m=geometry.slab_thickness_m,
        load_tributary_length_m=float(_value(diaphragm_data, "longitud_tributaria_cargas_m", 0.25)),
        vehicle_step_m=float(_value(diaphragm_data, "paso_vehicular_m", 0.10)),
    )
    transverse_slab = TransverseSlabDesignInputs(geometry=geometry, load_layout=layout)
    return ProjectInputs(
        materials=material_inputs,
        live_loads=live_loads,
        barrier=barrier_inputs,
        transverse_slab=transverse_slab,
        interior_girder=interior_girder,
        exterior_girder=exterior_girder,
        diaphragm=diaphragm,
    )
