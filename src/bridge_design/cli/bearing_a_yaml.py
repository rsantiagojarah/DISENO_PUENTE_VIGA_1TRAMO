"""Esquema YAML estricto y ejemplos reproducibles de diseno-apoyos-A."""

from bridge_design.domain.bearing_method_a import (
    BearingAActions, BearingAConnections, BearingAGeometry, BearingAInputs, CompressionCurve,
)
from bridge_design.domain.elastomeric_bearing import BearingMovements, TemperatureRange


def bearing_a_template() -> dict:
    return {
        "proyecto": "Diseño de apoyo elastomérico Método A",
        "identificador": "A1",
        "alcance": "completo",
        "acciones": {
            "dc_tn": 65.0, "dw_tn": 5.0, "ll_sin_im_tn": 22.0, "pl_tn": 0.0,
            "im_tn": 0.0, "reaccion_minima_tn": None,
            "fuente": "Indicar modelo, combinación, apoyo y revisión de las reacciones",
        },
        "movimientos": {
            "longitud_expansion_m": 30.0, "zona_climatica": "sierra",
            "temperatura_instalacion_c": 25.0,
            "temperatura_minima_c": None, "temperatura_maxima_c": None,
            "retraccion_cm": 0.9, "postensado_cm": 0.0, "otros_cm": 0.0,
            "gamma_tu": 1.2, "alpha_por_c": 10.8e-6,
            "usar_rango_completo": False,
        },
        "geometria": {
            "ancho_cm": 45.0, "largo_cm": 30.0, "altura_total_cm": None,
            "seleccion": "medida", "recubrimiento_lateral_cm": 0.0, "rotacion_catalogo_rad": None,
            "capa_interior_cm": 1.5, "capa_exterior_cm": 0.8,
            "numero_capas_interiores": 4, "zuncho_cm": 0.2,
            "largo_maximo_busqueda_cm": 120.0, "maximo_capas_busqueda": 20,
            "casi_cuadrado": False, "rotacion_principal_eje_transversal": True,
        },
        "materiales": {"shore_a": 60, "fy_zuncho_kg_cm2": 2530.0},
        "concreto": {"fc_kg_cm2": 210.0, "area_a2_cm2": None, "phi": 0.70},
        "conexiones": {
            "as_sitio": 0.20, "un_solo_tramo": True,
            "restriccion_longitudinal": False, "restriccion_transversal": True,
            "permanente_tributaria_longitudinal_tn": None,
            "eq_longitudinal_analisis_tn": None, "eq_transversal_analisis_tn": None,
            "envolvente_resistencia_i_longitudinal_tn": 0.0,
            "envolvente_resistencia_i_transversal_tn": 0.0,
            "resistencia_diseno_longitudinal_tn": None,
            "resistencia_diseno_transversal_tn": None, "fuente_resistencia": "", "mu": 0.2,
        },
        "compresion": {"metodo": "serquen", "fuente": "", "tipo": "fabricante", "shore_a": 60, "puntos": []},
        "junta_limite_cm": 0.3175,
    }


def bearing_a_reference_example() -> dict:
    """APOYOS.pdf pp. 234-239, ejercicio académico, sin sismo definido en fuente."""
    data = bearing_a_template()
    data["proyecto"] = "Comprobación del problema 4 1 de APOYOS pdf"
    data["identificador"] = "EJEMPLO_REFERENCIAL"
    data["movimientos"]["postensado_cm"] = 1.0  # Solo regresión académica del ejemplo original.
    data["acciones"]["fuente"] = "APOYOS.pdf p. 234, problema 4.1, Arturo Rodríguez Serquén"
    data["conexiones"]["as_sitio"] = 0.0
    data["conexiones"]["restriccion_transversal"] = False
    data["compresion"] = {
        "fuente": "APOYOS.pdf p. 238 (página 16 del archivo), tabla de deformaciones del problema 4.1; lectura gráfica aproximada para este ejemplo, no certificado de producto",
        "tipo": "referencia", "shore_a": 60,
        "puntos": [
            [6.0, 0.0, 0.0], [6.0, 70000/1350, 0.036], [6.0, 92000/1350, 0.0445],
            [11.25, 0.0, 0.0], [11.25, 70000/1350, 0.029], [11.25, 92000/1350, 0.035],
        ],
    }
    return data


def _section(data: dict, name: str, defaults: dict) -> dict:
    raw = data.get(name, {})
    if not isinstance(raw, dict):
        raise ValueError(f"{name} debe ser un mapa YAML.")
    extra = raw.keys() - defaults.keys()
    if extra:
        raise ValueError(f"Campos desconocidos en {name}: {', '.join(sorted(extra))}")
    return defaults | raw


def _float(data: dict, key: str, optional: bool = False) -> float | None:
    value = data[key]
    if optional and value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{key} debe ser un número.")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} debe ser un número{' o null' if optional else ''}.") from exc


def _bool(data: dict, key: str) -> bool:
    if type(data[key]) is not bool:
        raise ValueError(f"{key} requiere true o false, sin comillas.")
    return data[key]


def _int(data: dict, key: str, optional: bool = False) -> int | None:
    v = data[key]
    if optional and v is None:
        return None
    if type(v) is not int:
        raise ValueError(f"{key} requiere un entero.")
    return v


def bearing_a_from_yaml(data: dict) -> BearingAInputs:
    defaults = bearing_a_template()
    if not isinstance(data, dict) or data.keys()-defaults.keys():
        raise ValueError("Raíz YAML inválida o campos desconocidos para diseno-apoyos-A.")
    required = {
        "acciones": ("dc_tn", "dw_tn", "ll_sin_im_tn"),
        "movimientos": ("longitud_expansion_m", "zona_climatica", "temperatura_instalacion_c"),
        "geometria": ("ancho_cm",), "materiales": ("shore_a",), "concreto": ("fc_kg_cm2",),
    }
    scope = data.get("alcance", "completo")
    if scope not in {"completo", "neopreno"}:
        raise ValueError("alcance: completo o neopreno.")
    if scope == "neopreno":
        required.pop("concreto")
    for section, keys in required.items():
        if not isinstance(data.get(section), dict) or any(k not in data[section] for k in keys):
            raise ValueError(f"Faltan datos obligatorios en {section}: {', '.join(keys)}")
    sections = {k:_section(data,k,v) for k,v in defaults.items() if isinstance(v,dict)}
    a,m,g,c,mat,con,curve = (sections[k] for k in ("acciones","movimientos","geometria","conexiones","materiales","concreto","compresion"))
    zone = str(m["zona_climatica"]).lower()
    if zone not in {"costa","sierra","selva"}:
        raise ValueError("zona_climatica: costa, sierra o selva.")
    ti = _float(m,"temperatura_instalacion_c")
    tmin,tmax = _float(m,"temperatura_minima_c",True),_float(m,"temperatura_maxima_c",True)
    if (tmin is None) != (tmax is None):
        raise ValueError("Indique ambas temperaturas extremas o deje ambas en null.")
    temp = TemperatureRange.mtc_default(zone,ti) if tmin is None else TemperatureRange(tmax,tmin,ti)
    points = curve["puntos"]
    if not isinstance(points,list):
        raise ValueError("compresion.puntos requiere lista de [S, sigma_kg_cm2, epsilon_decimal].")
    parsed_points = []
    for row in points:
        if not isinstance(row,(list,tuple)) or len(row)!=3 or any(isinstance(v,bool) for v in row):
            raise ValueError("Cada punto de compresión necesita [S, sigma, epsilon].")
        parsed_points.append(tuple(float(v) for v in row))
    if curve["tipo"] not in {"fabricante", "referencia"}:
        raise ValueError("compresion.tipo: fabricante o referencia.")
    compression = CompressionCurve(str(curve["fuente"]),_int(curve,"shore_a"),tuple(parsed_points),str(curve["tipo"])) if points else None
    return BearingAInputs(
        neoprene_only=scope == "neopreno",
        compression_method=str(curve["metodo"]),
        actions=BearingAActions(*(_float(a,k) for k in ("dc_tn","dw_tn","ll_sin_im_tn","pl_tn","im_tn")),_float(a,"reaccion_minima_tn",True),str(a["fuente"])),
        movements=BearingMovements(
            span_length_m=_float(m,"longitud_expansion_m"),temperature=temp,
            shrinkage_cm=_float(m,"retraccion_cm"),prestress_shortening_cm=_float(m,"postensado_cm"),
            other_permanent_cm=_float(m,"otros_cm"),gamma_tu=_float(m,"gamma_tu"),
            alpha_per_c=_float(m,"alpha_por_c"),use_install_to_min=not _bool(m,"usar_rango_completo"),
        ),
        geometry=BearingAGeometry(
            total_height_cm=_float(g,"altura_total_cm",True),
            selection_mode=str(g["seleccion"]), cover_cm=_float(g,"recubrimiento_lateral_cm"),
            catalog_rotation_rad=_float(g,"rotacion_catalogo_rad",True),
            width_cm=_float(g,"ancho_cm"),length_cm=_float(g,"largo_cm",True),
            interior_cm=_float(g,"capa_interior_cm",True),exterior_cm=_float(g,"capa_exterior_cm",True),
            interior_layers=_int(g,"numero_capas_interiores",True),steel_cm=_float(g,"zuncho_cm",True),
            max_length_cm=_float(g,"largo_maximo_busqueda_cm"),max_layers=_int(g,"maximo_capas_busqueda"),
            nearly_square=_bool(g,"casi_cuadrado"),principal_rotation_transverse=_bool(g,"rotacion_principal_eje_transversal"),
        ),
        connections=BearingAConnections(
            as_site=_float(c,"as_sitio"),single_span=_bool(c,"un_solo_tramo"),
            restrained_longitudinal=_bool(c,"restriccion_longitudinal"),restrained_transverse=_bool(c,"restriccion_transversal"),
            permanent_longitudinal_tn=_float(c,"permanente_tributaria_longitudinal_tn",True),
            eq_longitudinal_tn=_float(c,"eq_longitudinal_analisis_tn",True),eq_transverse_tn=_float(c,"eq_transversal_analisis_tn",True),
            strength_longitudinal_tn=_float(c,"envolvente_resistencia_i_longitudinal_tn"),strength_transverse_tn=_float(c,"envolvente_resistencia_i_transversal_tn"),
            resistance_longitudinal_tn=_float(c,"resistencia_diseno_longitudinal_tn",True),resistance_transverse_tn=_float(c,"resistencia_diseno_transversal_tn",True),
            resistance_source=str(c["fuente_resistencia"]),friction_mu=_float(c,"mu"),
        ),
        hardness=_int(mat,"shore_a"),fy_kg_cm2=_float(mat,"fy_zuncho_kg_cm2"),
        fc_kg_cm2=_float(con,"fc_kg_cm2"),concrete_a2_cm2=_float(con,"area_a2_cm2",True),concrete_phi=_float(con,"phi"),
        compression_curve=compression,joint_limit_cm=float(data.get("junta_limite_cm",defaults["junta_limite_cm"])),
        project=str(data.get("proyecto",defaults["proyecto"])),bearing_id=str(data.get("identificador",defaults["identificador"])),
    )
