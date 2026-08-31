"""MTC 2018 bridge manual formulas and default loads."""

from bridge_design.units.converters import (
    ft_to_m,
    inch_to_m,
    kg_cm2_to_ksi,
    kip_to_tn,
    ksf_to_tn_m2,
    m_to_ft,
    m_to_in,
    ksi_to_kg_cm2,
    psf_to_tn_m2,
    tn_m3_to_kcf,
    tn_m3_to_kgf_m3,
)
from bridge_design.validation.input_validators import require_positive, require_range

CM_PER_IN = 2.54

CONCRETE_EC_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.5.4.4 "
    "(5.4.2.4 AASHTO), Ec = 120000*K1*wc^2.0*(f'c)^0.33."
)
STEEL_REFERENCE = "Manual de Puentes MTC 2018, Art. 2.5.2.1 y 2.5.2.2."
PEDESTRIAN_SIDEWALK_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.4.3.6.1: 0.075 ksf sobre veredas."
)
PEDESTRIAN_BRIDGE_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.4.3.7: 90 psf en puentes peatonales."
)
HL93_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.4.3.2.2: carga viva HL-93."
)
DYNAMIC_LOAD_ALLOWANCE_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.4.3.3, Tabla 2.4.3.3-1 "
    "(3.6.2.1-1 AASHTO)."
)
MULTIPLE_PRESENCE_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.4.3.2.2.6, Tabla 2.4.3.2.2.6-1 "
    "(3.6.1.1.2-1 AASHTO)."
)
EQUIVALENT_STRIP_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.6.4.2.1.3, Tabla 2.6.4.2.1.3-1 "
    "(4.6.2.1.3-1 AASHTO)."
)
LOAD_COMBINATION_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.4.5.3.1, Tabla 2.4.5.3.1-1 "
    "(3.4.1-1 AASHTO): factores y combinaciones de carga LRFD."
)
DECK_OVERHANG_LIVE_LOAD_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.4.3.2.3.4 "
    "(3.6.1.3.4 AASHTO): carga para el voladizo del tablero."
)
FLEXURAL_STRENGTH_REFERENCE = (
    "Manual de Puentes MTC 2018, Seccion 2.9.4.2 "
    "(5.7.3 AASHTO): resistencia nominal a flexion de concreto armado."
)
TENSION_DEVELOPMENT_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.6.5.6.2.1 "
    "(5.11.2.1 AASHTO): longitud de desarrollo de barras deformadas en traccion."
)
TEMPERATURE_REINFORCEMENT_REFERENCE = (
    "Criterio minimo de refuerzo por retraccion y temperatura para losas "
    "de concreto armado, cuantia adoptada rho=0.0018."
)
ABUTMENT_TEMPERATURE_REINFORCEMENT_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.9.1.4.5.8 "
    "(AASHTO LRFD 5.10.8): refuerzo por temperatura y acortamiento de fragua."
)
TEMPERATURE_STEEL_MIN_CM2_M = 2.33
TEMPERATURE_STEEL_MAX_CM2_M = 12.70
THICK_MEMBER_SPACING_MAX_M = 0.30
THICK_MEMBER_SPACING_THRESHOLD_CM = 45.0
DISTRIBUTION_REINFORCEMENT_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.9.7.3.2 "
    "(9.7.3.2 AASHTO): acero de distribucion en losas."
)
CRACK_CONTROL_REINFORCEMENT_REFERENCE = (
    "Manual de Puentes MTC 2018, Seccion 2.9.4.4 "
    "(5.7.3.4 AASHTO): control de fisuracion por distribucion de armadura."
)
INTERIOR_GIRDER_LIVE_LOAD_DISTRIBUTION_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.6.4.2.2.2b, "
    "Tabla 2.6.4.2.2.2b-1 (4.6.2.2.2b-1 AASHTO): "
    "factor de distribucion de carga viva para momento en vigas interiores "
    "con tablero de concreto."
)
INTERIOR_GIRDER_LIVE_LOAD_SHEAR_DISTRIBUTION_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.6.4.2.2.3a, "
    "Tabla 2.6.4.2.2.3a-1 (4.6.2.2.3a-1 AASHTO): "
    "factor de distribucion de carga viva para corte en vigas interiores "
    "con tablero de concreto."
)
EXTERIOR_GIRDER_LIVE_LOAD_MOMENT_DISTRIBUTION_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.6.4.2.2.2d, "
    "Tabla 2.6.4.2.2.2d-1 (4.6.2.2.2d-1 AASHTO): "
    "factor de distribucion de carga viva para momento en vigas exteriores."
)
EXTERIOR_GIRDER_LIVE_LOAD_SHEAR_DISTRIBUTION_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.6.4.2.2.3b, "
    "Tabla 2.6.4.2.2.3b-1 (4.6.2.2.3b-1 AASHTO): "
    "factor de distribucion de carga viva para corte en vigas exteriores."
)

DYNAMIC_LOAD_ALLOWANCE_OTHER_LIMIT_STATES = 0.33
DEFAULT_FLEXURAL_RESISTANCE_FACTOR = 0.90
DEFAULT_SHRINKAGE_TEMPERATURE_RATIO = 0.0018
MAX_DISTRIBUTION_REINFORCEMENT_PERCENT = 67.0
DEFAULT_CRACK_CONTROL_EXPOSURE_FACTOR = 1.00
DEFAULT_SERVICE_STRESS_LEVER_ARM_FACTOR = 0.90

MIN_CONCRETE_DENSITY_KGF_M3 = 1440.0
MAX_CONCRETE_DENSITY_KGF_M3 = 2500.0
MAX_CONCRETE_FC_KSI = 15.0

MIN_DISTRIBUTION_GIRDER_SPACING_FT = 3.5
MAX_DISTRIBUTION_GIRDER_SPACING_FT = 16.0
MIN_DISTRIBUTION_SLAB_THICKNESS_IN = 4.5
MAX_DISTRIBUTION_SLAB_THICKNESS_IN = 12.0
MIN_DISTRIBUTION_SPAN_FT = 20.0
MAX_DISTRIBUTION_SPAN_FT = 240.0
MIN_DISTRIBUTION_LONGITUDINAL_STIFFNESS_IN4 = 10000.0
MAX_DISTRIBUTION_LONGITUDINAL_STIFFNESS_IN4 = 7000000.0
MIN_DISTRIBUTION_GIRDER_COUNT = 4
MIN_EXTERIOR_DE_FT = -1.0
MAX_EXTERIOR_DE_FT = 5.5
DEFAULT_WHEEL_CLEARANCE_TO_TRAFFIC_BARRIER_M = ft_to_m(2.0)
DEFAULT_DECK_OVERHANG_WHEEL_CLEARANCE_TO_RAIL_M = ft_to_m(1.0)
MAX_DECK_OVERHANG_KNIFE_LOAD_APPLICABILITY_M = ft_to_m(6.0)


def calculate_concrete_elastic_modulus_kg_cm2(
    specific_weight_tn_m3: float,
    compressive_strength_kg_cm2: float,
    aggregate_correction_factor: float = 1.0,
) -> float:
    """Return concrete elastic modulus Ec in kgf/cm2.

    Units:
        specific_weight_tn_m3: Tn/m3.
        compressive_strength_kg_cm2: kgf/cm2.
        aggregate_correction_factor: dimensionless K1.
        return: kgf/cm2.

    Reference:
        Manual de Puentes MTC 2018, Art. 2.5.4.4 (5.4.2.4 AASHTO).
        The formula is Ec = 120000*K1*wc^2.0*(f'c)^0.33 in ksi, with
        wc in kcf and f'c in ksi.
    """
    require_positive(specific_weight_tn_m3, "Pec")
    require_positive(compressive_strength_kg_cm2, "f'c")
    require_positive(aggregate_correction_factor, "K1")

    density_kgf_m3 = tn_m3_to_kgf_m3(specific_weight_tn_m3)
    if not MIN_CONCRETE_DENSITY_KGF_M3 <= density_kgf_m3 <= MAX_CONCRETE_DENSITY_KGF_M3:
        raise ValueError(
            "Pec esta fuera del rango de aplicacion del MTC 2018 "
            f"({MIN_CONCRETE_DENSITY_KGF_M3:g} a "
            f"{MAX_CONCRETE_DENSITY_KGF_M3:g} kgf/m3)."
        )

    compressive_strength_ksi = kg_cm2_to_ksi(compressive_strength_kg_cm2)
    if compressive_strength_ksi > MAX_CONCRETE_FC_KSI:
        raise ValueError(
            "f'c excede el limite de aplicacion de la formula MTC 2018 "
            f"({MAX_CONCRETE_FC_KSI:g} ksi)."
        )

    concrete_density_kcf = tn_m3_to_kcf(specific_weight_tn_m3)
    elastic_modulus_ksi = (
        120000.0
        * aggregate_correction_factor
        * concrete_density_kcf**2.0
        * compressive_strength_ksi**0.33
    )
    return ksi_to_kg_cm2(elastic_modulus_ksi)


def default_sidewalk_pedestrian_load_tn_m2() -> float:
    """Return MTC sidewalk pedestrian load PL in Tn/m2."""
    return ksf_to_tn_m2(0.075)


def mtc_dynamic_load_allowance_for_slab() -> float:
    """Return IM for concrete slab design outside fatigue and deck joints."""
    return DYNAMIC_LOAD_ALLOWANCE_OTHER_LIMIT_STATES


def mtc_deck_overhang_knife_load_tn_m() -> float:
    """Return the optional deck-overhang wheel-row load, in Tn/m.

    MTC/AASHTO permits replacing the exterior wheel row by a uniformly
    distributed line load of 1.0 kip/ft for qualifying concrete deck overhangs.
    """
    return kip_to_tn(1.0) / ft_to_m(1.0)


def mtc_multiple_presence_factor(loaded_lanes: int) -> float:
    """Return the MTC/AASHTO multiple presence factor m."""
    if loaded_lanes < 1:
        raise ValueError("El numero de vias cargadas debe ser al menos 1.")
    if loaded_lanes == 1:
        return 1.20
    if loaded_lanes == 2:
        return 1.00
    if loaded_lanes == 3:
        return 0.85
    return 0.65


def mtc_interior_concrete_t_girder_live_load_distribution_factor(
    span_length_m: float,
    girder_spacing_m: float,
    slab_thickness_m: float,
    girder_total_height_m: float,
    web_width_m: float,
    girder_count: int,
) -> float:
    """Return the live-load distribution factor g for interior T-girder moment.

    Units:
        span_length_m: simple span length, m.
        girder_spacing_m: spacing between interior girders, m.
        slab_thickness_m: concrete deck thickness, m.
        girder_total_height_m: non-composite girder stem depth below slab, m.
        web_width_m: non-composite girder stem width, m.
        girder_count: number of girders in the bridge cross-section.
        return: dimensionless distribution factor g, lanes/girder.

    Reference:
        Manual de Puentes MTC 2018, Art. 2.6.4.2.2.2b, Tabla
        2.6.4.2.2.2b-1 (4.6.2.2.2b-1 AASHTO). The selected value is the
        governing value between one loaded design lane and two or more loaded
        design lanes for concrete deck / concrete T-beam interior girders.
    """
    require_positive(span_length_m, "L")
    require_positive(girder_spacing_m, "S")
    require_positive(slab_thickness_m, "ts")
    require_positive(girder_total_height_m, "altura de viga")
    require_positive(web_width_m, "ancho de alma")
    if girder_count < MIN_DISTRIBUTION_GIRDER_COUNT:
        raise ValueError(
            "El factor g para vigas interiores de tablero de concreto requiere "
            f"al menos {MIN_DISTRIBUTION_GIRDER_COUNT} vigas."
        )

    span_ft = m_to_ft(span_length_m)
    spacing_ft = m_to_ft(girder_spacing_m)
    slab_thickness_in = m_to_in(slab_thickness_m)
    web_width_in = m_to_in(web_width_m)
    girder_depth_in = m_to_in(girder_total_height_m)
    longitudinal_stiffness_in4 = _concrete_t_girder_longitudinal_stiffness_in4(
        web_width_in,
        girder_depth_in,
        m_to_in(girder_total_height_m / 2.0 + slab_thickness_m / 2.0),
    )

    require_range(
        spacing_ft,
        "S para factor g",
        MIN_DISTRIBUTION_GIRDER_SPACING_FT,
        MAX_DISTRIBUTION_GIRDER_SPACING_FT,
    )
    require_range(
        slab_thickness_in,
        "ts para factor g",
        MIN_DISTRIBUTION_SLAB_THICKNESS_IN,
        MAX_DISTRIBUTION_SLAB_THICKNESS_IN,
    )
    require_range(
        span_ft,
        "L para factor g",
        MIN_DISTRIBUTION_SPAN_FT,
        MAX_DISTRIBUTION_SPAN_FT,
    )
    require_range(
        longitudinal_stiffness_in4,
        "Kg para factor g",
        MIN_DISTRIBUTION_LONGITUDINAL_STIFFNESS_IN4,
        MAX_DISTRIBUTION_LONGITUDINAL_STIFFNESS_IN4,
    )

    one_lane = _interior_concrete_t_girder_moment_one_lane_g(
        spacing_ft,
        span_ft,
        slab_thickness_in,
        longitudinal_stiffness_in4,
    )
    multiple_lanes = (
        0.075
        + (spacing_ft / 9.5) ** 0.6
        * (spacing_ft / span_ft) ** 0.2
        * _distribution_stiffness_term(
            longitudinal_stiffness_in4,
            span_ft,
            slab_thickness_in,
        )
    )
    return max(one_lane, multiple_lanes)


def mtc_interior_concrete_t_girder_fatigue_live_load_moment_distribution_factor(
    span_length_m: float,
    girder_spacing_m: float,
    slab_thickness_m: float,
    girder_total_height_m: float,
    web_width_m: float,
    girder_count: int,
) -> float:
    """Return interior T-girder moment g for Fatigue I.

    MTC/AASHTO fatigue uses one design truck and excludes multiple presence.
    The one-lane approximate distribution factor is therefore divided by 1.20.
    """
    require_positive(span_length_m, "L")
    require_positive(girder_spacing_m, "S")
    require_positive(slab_thickness_m, "ts")
    require_positive(girder_total_height_m, "altura de viga")
    require_positive(web_width_m, "ancho de alma")
    if girder_count < MIN_DISTRIBUTION_GIRDER_COUNT:
        raise ValueError(
            "El factor g de fatiga para vigas interiores requiere "
            f"al menos {MIN_DISTRIBUTION_GIRDER_COUNT} vigas."
        )

    span_ft = m_to_ft(span_length_m)
    spacing_ft = m_to_ft(girder_spacing_m)
    slab_thickness_in = m_to_in(slab_thickness_m)
    web_width_in = m_to_in(web_width_m)
    girder_depth_in = m_to_in(girder_total_height_m)
    longitudinal_stiffness_in4 = _concrete_t_girder_longitudinal_stiffness_in4(
        web_width_in,
        girder_depth_in,
        m_to_in(girder_total_height_m / 2.0 + slab_thickness_m / 2.0),
    )
    require_range(
        spacing_ft,
        "S para factor g fatiga",
        MIN_DISTRIBUTION_GIRDER_SPACING_FT,
        MAX_DISTRIBUTION_GIRDER_SPACING_FT,
    )
    require_range(
        slab_thickness_in,
        "ts para factor g fatiga",
        MIN_DISTRIBUTION_SLAB_THICKNESS_IN,
        MAX_DISTRIBUTION_SLAB_THICKNESS_IN,
    )
    require_range(
        span_ft,
        "L para factor g fatiga",
        MIN_DISTRIBUTION_SPAN_FT,
        MAX_DISTRIBUTION_SPAN_FT,
    )
    require_range(
        longitudinal_stiffness_in4,
        "Kg para factor g fatiga",
        MIN_DISTRIBUTION_LONGITUDINAL_STIFFNESS_IN4,
        MAX_DISTRIBUTION_LONGITUDINAL_STIFFNESS_IN4,
    )
    return _interior_concrete_t_girder_moment_one_lane_g(
        spacing_ft,
        span_ft,
        slab_thickness_in,
        longitudinal_stiffness_in4,
    ) / mtc_multiple_presence_factor(1)


def mtc_interior_concrete_t_girder_live_load_shear_distribution_factor(
    span_length_m: float,
    girder_spacing_m: float,
    slab_thickness_m: float,
    girder_count: int,
) -> float:
    """Return the live-load distribution factor g for interior T-girder shear.

    Reference:
        Manual de Puentes MTC 2018, Art. 2.6.4.2.2.3a, Tabla
        2.6.4.2.2.3a-1 (4.6.2.2.3a-1 AASHTO). The selected value is the
        governing value between one loaded design lane and two or more loaded
        design lanes for concrete deck / concrete T-beam interior girders.
    """
    require_positive(span_length_m, "L")
    require_positive(girder_spacing_m, "S")
    require_positive(slab_thickness_m, "ts")
    if girder_count < MIN_DISTRIBUTION_GIRDER_COUNT:
        raise ValueError(
            "El factor g para corte en vigas interiores requiere "
            f"al menos {MIN_DISTRIBUTION_GIRDER_COUNT} vigas."
        )

    span_ft = m_to_ft(span_length_m)
    spacing_ft = m_to_ft(girder_spacing_m)
    slab_thickness_in = m_to_in(slab_thickness_m)
    require_range(
        spacing_ft,
        "S para factor g de corte",
        MIN_DISTRIBUTION_GIRDER_SPACING_FT,
        MAX_DISTRIBUTION_GIRDER_SPACING_FT,
    )
    require_range(
        slab_thickness_in,
        "ts para factor g de corte",
        MIN_DISTRIBUTION_SLAB_THICKNESS_IN,
        MAX_DISTRIBUTION_SLAB_THICKNESS_IN,
    )
    require_range(
        span_ft,
        "L para factor g de corte",
        MIN_DISTRIBUTION_SPAN_FT,
        MAX_DISTRIBUTION_SPAN_FT,
    )

    one_lane = 0.36 + spacing_ft / 25.0
    multiple_lanes = 0.20 + spacing_ft / 12.0 - (spacing_ft / 35.0) ** 2.0
    return max(one_lane, multiple_lanes)


def mtc_interior_concrete_t_girder_fatigue_live_load_shear_distribution_factor(
    span_length_m: float,
    girder_spacing_m: float,
    slab_thickness_m: float,
    girder_count: int,
) -> float:
    """Return interior T-girder shear g for Fatigue I without multiple presence."""
    require_positive(span_length_m, "L")
    require_positive(girder_spacing_m, "S")
    require_positive(slab_thickness_m, "ts")
    if girder_count < MIN_DISTRIBUTION_GIRDER_COUNT:
        raise ValueError(
            "El factor g de corte por fatiga requiere "
            f"al menos {MIN_DISTRIBUTION_GIRDER_COUNT} vigas."
        )

    span_ft = m_to_ft(span_length_m)
    spacing_ft = m_to_ft(girder_spacing_m)
    slab_thickness_in = m_to_in(slab_thickness_m)
    require_range(
        spacing_ft,
        "S para factor g corte fatiga",
        MIN_DISTRIBUTION_GIRDER_SPACING_FT,
        MAX_DISTRIBUTION_GIRDER_SPACING_FT,
    )
    require_range(
        slab_thickness_in,
        "ts para factor g corte fatiga",
        MIN_DISTRIBUTION_SLAB_THICKNESS_IN,
        MAX_DISTRIBUTION_SLAB_THICKNESS_IN,
    )
    require_range(
        span_ft,
        "L para factor g corte fatiga",
        MIN_DISTRIBUTION_SPAN_FT,
        MAX_DISTRIBUTION_SPAN_FT,
    )
    return (0.36 + spacing_ft / 25.0) / mtc_multiple_presence_factor(1)


def mtc_exterior_concrete_t_girder_live_load_moment_distribution_factor(
    span_length_m: float,
    girder_spacing_m: float,
    slab_thickness_m: float,
    girder_total_height_m: float,
    web_width_m: float,
    girder_count: int,
    exterior_web_to_traffic_barrier_m: float,
    wheel_transverse_spacing_m: float,
    design_lane_width_m: float,
    wheel_clearance_to_traffic_barrier_m: float = DEFAULT_WHEEL_CLEARANCE_TO_TRAFFIC_BARRIER_M,
) -> float:
    """Return the live-load distribution factor g for exterior T-girder moment.

    ``exterior_web_to_traffic_barrier_m`` is the MTC/AASHTO ``de`` parameter:
    positive when the exterior web centerline is inside the traffic curb/barrier
    face, negative when it is outside.
    """
    interior_g = mtc_interior_concrete_t_girder_live_load_distribution_factor(
        span_length_m=span_length_m,
        girder_spacing_m=girder_spacing_m,
        slab_thickness_m=slab_thickness_m,
        girder_total_height_m=girder_total_height_m,
        web_width_m=web_width_m,
        girder_count=girder_count,
    )
    de_ft = _limited_exterior_de_ft(exterior_web_to_traffic_barrier_m)
    multiple_lanes = (0.77 + de_ft / 9.1) * interior_g
    one_lane = mtc_exterior_lever_rule_distribution_factor(
        girder_spacing_m=girder_spacing_m,
        exterior_web_to_traffic_barrier_m=exterior_web_to_traffic_barrier_m,
        wheel_transverse_spacing_m=wheel_transverse_spacing_m,
        wheel_clearance_to_traffic_barrier_m=wheel_clearance_to_traffic_barrier_m,
    )
    rigid = mtc_exterior_rigid_cross_section_distribution_factor(
        girder_spacing_m=girder_spacing_m,
        girder_count=girder_count,
        exterior_web_to_traffic_barrier_m=exterior_web_to_traffic_barrier_m,
        wheel_transverse_spacing_m=wheel_transverse_spacing_m,
        design_lane_width_m=design_lane_width_m,
        wheel_clearance_to_traffic_barrier_m=wheel_clearance_to_traffic_barrier_m,
    )
    return max(one_lane, multiple_lanes, rigid)


def mtc_exterior_concrete_t_girder_fatigue_live_load_moment_distribution_factor(
    girder_spacing_m: float,
    girder_count: int,
    exterior_web_to_traffic_barrier_m: float,
    wheel_transverse_spacing_m: float,
    design_lane_width_m: float,
    wheel_clearance_to_traffic_barrier_m: float = DEFAULT_WHEEL_CLEARANCE_TO_TRAFFIC_BARRIER_M,
) -> float:
    """Return exterior T-girder moment g for Fatigue I without multiple presence."""
    lever = mtc_exterior_lever_rule_distribution_factor(
        girder_spacing_m=girder_spacing_m,
        exterior_web_to_traffic_barrier_m=exterior_web_to_traffic_barrier_m,
        wheel_transverse_spacing_m=wheel_transverse_spacing_m,
        wheel_clearance_to_traffic_barrier_m=wheel_clearance_to_traffic_barrier_m,
    ) / mtc_multiple_presence_factor(1)
    rigid = mtc_exterior_rigid_cross_section_one_lane_distribution_factor(
        girder_spacing_m=girder_spacing_m,
        girder_count=girder_count,
        exterior_web_to_traffic_barrier_m=exterior_web_to_traffic_barrier_m,
        wheel_transverse_spacing_m=wheel_transverse_spacing_m,
        design_lane_width_m=design_lane_width_m,
        wheel_clearance_to_traffic_barrier_m=wheel_clearance_to_traffic_barrier_m,
    )
    return max(lever, rigid)


def mtc_exterior_concrete_t_girder_live_load_shear_distribution_factor(
    span_length_m: float,
    girder_spacing_m: float,
    slab_thickness_m: float,
    girder_count: int,
    exterior_web_to_traffic_barrier_m: float,
    wheel_transverse_spacing_m: float,
    design_lane_width_m: float,
    wheel_clearance_to_traffic_barrier_m: float = DEFAULT_WHEEL_CLEARANCE_TO_TRAFFIC_BARRIER_M,
) -> float:
    """Return the live-load distribution factor g for exterior T-girder shear."""
    interior_g = mtc_interior_concrete_t_girder_live_load_shear_distribution_factor(
        span_length_m=span_length_m,
        girder_spacing_m=girder_spacing_m,
        slab_thickness_m=slab_thickness_m,
        girder_count=girder_count,
    )
    de_ft = _limited_exterior_de_ft(exterior_web_to_traffic_barrier_m)
    multiple_lanes = (0.60 + de_ft / 10.0) * interior_g
    one_lane = mtc_exterior_lever_rule_distribution_factor(
        girder_spacing_m=girder_spacing_m,
        exterior_web_to_traffic_barrier_m=exterior_web_to_traffic_barrier_m,
        wheel_transverse_spacing_m=wheel_transverse_spacing_m,
        wheel_clearance_to_traffic_barrier_m=wheel_clearance_to_traffic_barrier_m,
    )
    rigid = mtc_exterior_rigid_cross_section_distribution_factor(
        girder_spacing_m=girder_spacing_m,
        girder_count=girder_count,
        exterior_web_to_traffic_barrier_m=exterior_web_to_traffic_barrier_m,
        wheel_transverse_spacing_m=wheel_transverse_spacing_m,
        design_lane_width_m=design_lane_width_m,
        wheel_clearance_to_traffic_barrier_m=wheel_clearance_to_traffic_barrier_m,
    )
    return max(one_lane, multiple_lanes, rigid)


def mtc_exterior_concrete_t_girder_fatigue_live_load_shear_distribution_factor(
    girder_spacing_m: float,
    girder_count: int,
    exterior_web_to_traffic_barrier_m: float,
    wheel_transverse_spacing_m: float,
    design_lane_width_m: float,
    wheel_clearance_to_traffic_barrier_m: float = DEFAULT_WHEEL_CLEARANCE_TO_TRAFFIC_BARRIER_M,
) -> float:
    """Return exterior T-girder shear g for Fatigue I without multiple presence."""
    return mtc_exterior_concrete_t_girder_fatigue_live_load_moment_distribution_factor(
        girder_spacing_m=girder_spacing_m,
        girder_count=girder_count,
        exterior_web_to_traffic_barrier_m=exterior_web_to_traffic_barrier_m,
        wheel_transverse_spacing_m=wheel_transverse_spacing_m,
        design_lane_width_m=design_lane_width_m,
        wheel_clearance_to_traffic_barrier_m=wheel_clearance_to_traffic_barrier_m,
    )


def mtc_exterior_lever_rule_distribution_factor(
    girder_spacing_m: float,
    exterior_web_to_traffic_barrier_m: float,
    wheel_transverse_spacing_m: float,
    wheel_clearance_to_traffic_barrier_m: float = DEFAULT_WHEEL_CLEARANCE_TO_TRAFFIC_BARRIER_M,
) -> float:
    """Return one-lane exterior-girder g by lever rule.

    The exterior girder is at x=0 and the first interior girder at x=S. The
    nearest wheel line is placed 2 ft inside the traffic curb/barrier face.
    The one-lane multiple presence factor m=1.20 is applied because the
    MTC/AASHTO article allows it when the lever rule is used.
    """
    require_positive(girder_spacing_m, "S")
    require_positive(wheel_transverse_spacing_m, "separacion transversal de ruedas")
    require_positive(
        wheel_clearance_to_traffic_barrier_m,
        "separacion rueda-cordon/barrera",
    )
    nearest_wheel_x_m = (
        -exterior_web_to_traffic_barrier_m + wheel_clearance_to_traffic_barrier_m
    )
    far_wheel_x_m = nearest_wheel_x_m + wheel_transverse_spacing_m
    reaction = (
        _exterior_reaction_fraction(girder_spacing_m, nearest_wheel_x_m)
        + _exterior_reaction_fraction(girder_spacing_m, far_wheel_x_m)
    ) / 2.0
    return mtc_multiple_presence_factor(1) * reaction


def mtc_exterior_rigid_cross_section_distribution_factor(
    girder_spacing_m: float,
    girder_count: int,
    exterior_web_to_traffic_barrier_m: float,
    wheel_transverse_spacing_m: float,
    design_lane_width_m: float,
    wheel_clearance_to_traffic_barrier_m: float = DEFAULT_WHEEL_CLEARANCE_TO_TRAFFIC_BARRIER_M,
) -> float:
    """Return exterior live-load g by rigid cross-section equilibrium.

    This implements the MTC/AASHTO exterior-girder lower bound for slab-girder
    systems with diaphragms or transverse frames. Girders are equally spaced;
    loaded design lanes are placed from the traffic barrier inward to maximize
    the exterior girder reaction. Multiple presence factors are applied because
    the exterior-girder article explicitly invokes them for this check.
    """
    require_positive(girder_spacing_m, "S")
    require_positive(wheel_transverse_spacing_m, "separacion transversal de ruedas")
    require_positive(design_lane_width_m, "ancho de carril de diseno")
    require_positive(
        wheel_clearance_to_traffic_barrier_m,
        "separacion rueda-cordon/barrera",
    )
    if girder_count < 2:
        raise ValueError("La seccion rigida requiere al menos dos vigas.")

    roadway_width_m = (girder_count - 1) * girder_spacing_m + 2.0 * exterior_web_to_traffic_barrier_m
    loaded_lane_limit = max(1, int(roadway_width_m // design_lane_width_m))
    loaded_lane_limit = min(loaded_lane_limit, girder_count)
    beam_positions = tuple(index * girder_spacing_m for index in range(girder_count))
    centroid = sum(beam_positions) / girder_count
    sum_x2 = sum((position - centroid) ** 2.0 for position in beam_positions)
    require_positive(sum_x2, "sumatoria x2 seccion rigida")

    exterior_x = beam_positions[0] - centroid
    barrier_x_m = -exterior_web_to_traffic_barrier_m
    governing = 0.0
    for loaded_lanes in range(1, loaded_lane_limit + 1):
        exterior_share = 0.0
        for lane_index in range(loaded_lanes):
            nearest_wheel = (
                barrier_x_m
                + wheel_clearance_to_traffic_barrier_m
                + lane_index * design_lane_width_m
            )
            far_wheel = nearest_wheel + wheel_transverse_spacing_m
            exterior_share += 0.5 * _rigid_exterior_reaction_fraction(
                nearest_wheel,
                centroid,
                exterior_x,
                sum_x2,
                girder_count,
            )
            exterior_share += 0.5 * _rigid_exterior_reaction_fraction(
                far_wheel,
                centroid,
                exterior_x,
                sum_x2,
                girder_count,
            )
        governing = max(governing, mtc_multiple_presence_factor(loaded_lanes) * exterior_share)
    return governing


def mtc_exterior_rigid_cross_section_one_lane_distribution_factor(
    girder_spacing_m: float,
    girder_count: int,
    exterior_web_to_traffic_barrier_m: float,
    wheel_transverse_spacing_m: float,
    design_lane_width_m: float,
    wheel_clearance_to_traffic_barrier_m: float = DEFAULT_WHEEL_CLEARANCE_TO_TRAFFIC_BARRIER_M,
) -> float:
    """Return one-lane exterior rigid-section g without multiple presence."""
    require_positive(girder_spacing_m, "S")
    require_positive(wheel_transverse_spacing_m, "separacion transversal de ruedas")
    require_positive(design_lane_width_m, "ancho de carril de diseno")
    require_positive(
        wheel_clearance_to_traffic_barrier_m,
        "separacion rueda-cordon/barrera",
    )
    if girder_count < 2:
        raise ValueError("La seccion rigida requiere al menos dos vigas.")

    beam_positions = tuple(index * girder_spacing_m for index in range(girder_count))
    centroid = sum(beam_positions) / girder_count
    sum_x2 = sum((position - centroid) ** 2.0 for position in beam_positions)
    require_positive(sum_x2, "sumatoria x2 seccion rigida")

    exterior_x = beam_positions[0] - centroid
    barrier_x_m = -exterior_web_to_traffic_barrier_m
    nearest_wheel = barrier_x_m + wheel_clearance_to_traffic_barrier_m
    far_wheel = nearest_wheel + wheel_transverse_spacing_m
    return 0.5 * (
        _rigid_exterior_reaction_fraction(
            nearest_wheel,
            centroid,
            exterior_x,
            sum_x2,
            girder_count,
        )
        + _rigid_exterior_reaction_fraction(
            far_wheel,
            centroid,
            exterior_x,
            sum_x2,
            girder_count,
        )
    )


def _limited_exterior_de_ft(exterior_web_to_traffic_barrier_m: float) -> float:
    de_ft = m_to_ft(exterior_web_to_traffic_barrier_m)
    if de_ft < MIN_EXTERIOR_DE_FT:
        return MIN_EXTERIOR_DE_FT
    require_range(
        de_ft,
        "de para factor g exterior",
        MIN_EXTERIOR_DE_FT,
        MAX_EXTERIOR_DE_FT,
    )
    return de_ft


def _exterior_reaction_fraction(girder_spacing_m: float, wheel_x_m: float) -> float:
    return max((girder_spacing_m - wheel_x_m) / girder_spacing_m, 0.0)


def _rigid_exterior_reaction_fraction(
    load_x_m: float,
    centroid_m: float,
    exterior_x_m: float,
    sum_x2_m2: float,
    girder_count: int,
) -> float:
    return 1.0 / girder_count + exterior_x_m * (load_x_m - centroid_m) / sum_x2_m2


def _distribution_stiffness_term(
    longitudinal_stiffness_in4: float,
    span_ft: float,
    slab_thickness_in: float,
) -> float:
    return (
        longitudinal_stiffness_in4 / (12.0 * span_ft * slab_thickness_in**3.0)
    ) ** 0.1


def _interior_concrete_t_girder_moment_one_lane_g(
    spacing_ft: float,
    span_ft: float,
    slab_thickness_in: float,
    longitudinal_stiffness_in4: float,
) -> float:
    stiffness_term = _distribution_stiffness_term(
        longitudinal_stiffness_in4,
        span_ft,
        slab_thickness_in,
    )
    return (
        0.06
        + (spacing_ft / 14.0) ** 0.4
        * (spacing_ft / span_ft) ** 0.3
        * stiffness_term
    )


def _concrete_t_girder_longitudinal_stiffness_in4(
    web_width_in: float,
    girder_depth_in: float,
    girder_to_deck_centroid_distance_in: float,
) -> float:
    """Return Kg = n(I + A*eg^2) for monolithic concrete T-girders."""
    web_area_in2 = web_width_in * girder_depth_in
    web_inertia_in4 = web_width_in * girder_depth_in**3.0 / 12.0
    return web_inertia_in4 + web_area_in2 * girder_to_deck_centroid_distance_in**2.0


def mtc_cast_in_place_slab_equivalent_strip_widths_m(
    support_spacing_m: float,
) -> tuple[float, float]:
    """Return equivalent strip widths for cast-in-place concrete slab.

    Returns:
        (positive_moment_width_m, negative_moment_width_m).

    MTC Table 2.6.4.2.1.3-1, SI formulas:
        +M: E = 660 + 0.55 S, in mm.
        -M: E = 1220 + 0.25 S, in mm.
    """
    require_positive(support_spacing_m, "S")
    positive_width_m = 0.660 + 0.55 * support_spacing_m
    negative_width_m = 1.220 + 0.25 * support_spacing_m
    return positive_width_m, negative_width_m


def mtc_tension_development_length_cm(
    bar_diameter_cm: float,
    steel_yield_kg_cm2: float,
    concrete_strength_kg_cm2: float,
    location_factor: float = 1.0,
    coating_factor: float = 1.0,
    lightweight_factor: float = 1.0,
    confinement_factor: float = 1.0,
    excess_reinforcement_factor: float = 1.0,
) -> tuple[float, float]:
    """Return (required_ld, basic_ldb) for deformed bars in tension, in cm.

    The basic length uses AASHTO customary units:
    ldb = 2.4*db*fy/sqrt(f'c), with db in inches and stresses in ksi. The
    returned required length includes modification factors and the 12 in
    minimum for tension development.
    """
    require_positive(bar_diameter_cm, "db")
    require_positive(steel_yield_kg_cm2, "fy")
    require_positive(concrete_strength_kg_cm2, "f'c")
    require_positive(location_factor, "lambda ubicacion")
    require_positive(coating_factor, "lambda recubrimiento")
    require_positive(lightweight_factor, "lambda concreto ligero")
    require_positive(confinement_factor, "lambda confinamiento")
    require_positive(excess_reinforcement_factor, "lambda acero excedente")
    if excess_reinforcement_factor > 1.0:
        raise ValueError("lambda de acero excedente no debe exceder 1.0.")

    db_in = bar_diameter_cm / CM_PER_IN
    fy_ksi = kg_cm2_to_ksi(steel_yield_kg_cm2)
    fc_ksi = kg_cm2_to_ksi(concrete_strength_kg_cm2)
    basic_in = 2.4 * db_in * fy_ksi / fc_ksi**0.5
    modified_in = basic_in * (
        location_factor
        * coating_factor
        * lightweight_factor
        * confinement_factor
        * excess_reinforcement_factor
    )
    required_cm = max(modified_in * CM_PER_IN, 12.0 * CM_PER_IN)
    return required_cm, basic_in * CM_PER_IN


def mtc_distribution_reinforcement_percent_for_transverse_primary(
    effective_span_m: float,
) -> float:
    """Return distribution steel percentage for slabs with transverse main steel.

    Units:
        effective_span_m: effective slab span in m.
        return: percentage of positive main reinforcement.

    Reference:
        Manual de Puentes MTC 2018, Art. 2.9.7.3.2 (9.7.3.2 AASHTO).
        For primary reinforcement perpendicular to traffic:
        porcentaje = 3840 / sqrt(S), with S in mm, limited to 67%.
    """
    require_positive(effective_span_m, "S efectivo")
    span_mm = effective_span_m * 1000.0
    return min(MAX_DISTRIBUTION_REINFORCEMENT_PERCENT, 3840.0 / span_mm**0.5)


def default_pedestrian_bridge_load_tn_m2() -> float:
    """Return MTC pedestrian bridge live load in Tn/m2."""
    return psf_to_tn_m2(90.0)


def default_hl93_vehicle_load_data() -> dict[str, object]:
    """Return the MTC HL-93 default vehicle load data in project units."""
    return {
        "name": "HL-93",
        "reference": HL93_REFERENCE,
        "design_truck_axles_tn": [
            kip_to_tn(8.0),
            kip_to_tn(32.0),
            kip_to_tn(32.0),
        ],
        "design_truck_spacings_m": [
            ft_to_m(14.0),
            (ft_to_m(14.0), ft_to_m(30.0)),
        ],
        "design_tandem_axles_tn": [kip_to_tn(25.0), kip_to_tn(25.0)],
        "design_tandem_spacing_m": ft_to_m(4.0),
        "lane_load_tn_m": 0.954,
        "design_lane_width_m": ft_to_m(10.0),
        "wheel_transverse_spacing_m": ft_to_m(6.0),
        "tire_contact_width_m": inch_to_m(20.0),
        "tire_contact_length_m": inch_to_m(10.0),
    }
