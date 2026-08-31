"""Traceable formula and substitution builders for the abutment Word memory."""

from __future__ import annotations

from math import atan, cos, degrees, radians, sin, sqrt

from bridge_design.codes.mtc_2018 import (
    TEMPERATURE_STEEL_MAX_CM2_M,
    TEMPERATURE_STEEL_MIN_CM2_M,
)
from bridge_design.domain.abutment import (
    AbutmentDesignResult,
    AbutmentSecondaryReinforcementCase,
    AbutmentStemReinforcementCut,
    DEFAULT_MAX_AGGREGATE_SIZE_IN,
    LoadComponent,
    LoadFactors,
    REF_SEISMIC_PAPIR,
    REF_SHEAR_BETA,
    SEISMIC_PAPIR_COMBO_A,
    SEISMIC_PAPIR_COMBO_B,
    SIMPLIFIED_SHEAR_BETA,
    STEEL_ELASTIC_MODULUS_KG_CM2,
    StabilityStateResult,
    StructuralDesignCase,
    _bar_by_label,
    _cover_for_case,
    _footing_temperature_result,
    _section_depth_cm,
    _stem_design_demands,
    _stem_temperature_result,
    _upper_concrete_weight_and_arm,
    equivalent_vehicular_surcharge_height_m,
)
from bridge_design.domain.rebar_catalog import REINFORCING_BAR_CATALOG

KG_CM2_TO_MPA = 0.0980665


def _factor_for_type(factors: LoadFactors, load_type: str, *, horizontal: bool) -> float:
    mapping = {
        "DC": factors.dc,
        "DW": factors.dw,
        "EV": factors.ev,
        "LL": factors.ll,
        "LS": factors.ls_horizontal if horizontal else factors.ls_vertical,
        "EH": factors.eh,
        "EQ": factors.eq,
        "BR": factors.br,
    }
    return mapping[load_type]


def factors_for_state(result: AbutmentDesignResult, state: StabilityStateResult) -> LoadFactors:
    for factors in result.load_factors:
        if factors.name == state.name:
            return factors
    # Estados extremos renombrados por combinación MTC PAE/PIR.
    if "Evento Extremo" in state.name or state.seismic_papir_combination:
        for factors in result.load_factors:
            if factors.limit_state == "extreme":
                return factors
    raise KeyError(f"No hay factores LRFD para el estado {state.name}.")


def horizontal_components_for_state(
    result: AbutmentDesignResult,
    state: StabilityStateResult,
    *,
    with_bridge: bool,
) -> tuple[LoadComponent, ...]:
    """Return the unfactored horizontal inventory matching the seismic combo of ``state``."""
    if state.seismic_papir_combination == SEISMIC_PAPIR_COMBO_B:
        return (
            result.components.horizontal_with_bridge_seismic_b
            if with_bridge
            else result.components.horizontal_without_bridge_seismic_b
        )
    return (
        result.components.horizontal_with_bridge
        if with_bridge
        else result.components.horizontal_without_bridge
    )


def surcharge_height_trace(result: AbutmentDesignResult) -> tuple[str, str, str, str, str]:
    g = result.inputs.geometry
    soil = result.inputs.soil
    h = g.retained_height_m
    h_eq = result.pressures.live_surcharge_height_m
    if soil.vehicular_surcharge_height_m is not None:
        formula = "h' = h's,ingresada"
        substitution = f"h' = {soil.vehicular_surcharge_height_m:.3f} m (dato de entrada)"
        comment = "Se adopta la altura equivalente ingresada por el usuario."
    else:
        default = equivalent_vehicular_surcharge_height_m(h)
        formula = "h' = f(H) según tabla de altura equivalente (H≤1.5→1.20; 3.0→0.90; ≥6.0→0.60 m)"
        substitution = (
            f"H = {h:.3f} m → interpolación/tabla AASHTO-MTC → h' = {default:.3f} m"
        )
        comment = (
            "La altura equivalente de sobrecarga vehicular se toma de la tabla normativa "
            "en función de la altura retenida."
        )
    legend = (
        "h': altura equivalente de sobrecarga vehicular; H: altura retenida del relleno activo."
    )
    result_text = f"Se adopta h' = {h_eq:.3f} m."
    return formula, legend, substitution, result_text, comment


def coulomb_ka_trace(result: AbutmentDesignResult) -> tuple[str, str, str, str, str]:
    soil = result.inputs.soil
    ka = result.pressures.ka
    phi = radians(soil.friction_angle_deg)
    delta = radians(soil.wall_soil_friction_deg)
    beta = radians(soil.backfill_slope_deg)
    theta = radians(soil.wall_backface_angle_deg)
    root_term = sqrt(
        sin(phi + delta)
        * sin(phi - beta)
        / (sin(theta - delta) * sin(theta + beta))
    )
    numerator = sin(theta + phi) ** 2.0
    denominator = (
        (1.0 + root_term) ** 2.0
        * sin(theta) ** 2.0
        * sin(theta - delta)
    )
    formula = (
        "Ka = sin²(θ+φ)/[sin²θ·sin(θ−δ)·(1+√[sin(φ+δ)·sin(φ−β)/(sin(θ−δ)·sin(θ+β))])²]"
    )
    legend = (
        "Ka: coeficiente activo de Coulomb; φ: fricción interna; δ: fricción muro-suelo; "
        "β: pendiente del relleno; θ: ángulo de la cara posterior desde la horizontal."
    )
    substitution = (
        f"φ = {soil.friction_angle_deg:.3f}°; δ = {soil.wall_soil_friction_deg:.3f}°; "
        f"β = {soil.backfill_slope_deg:.3f}°; θ = {soil.wall_backface_angle_deg:.3f}°\n"
        f"√[...] = {root_term:.6f}\n"
        f"Numerador = sin²(θ+φ) = {numerator:.6f}\n"
        f"Denominador = {denominator:.6f}\n"
        f"Ka = {numerator:.6f}/{denominator:.6f} = {ka:.5f}"
    )
    result_text = f"Se adopta Ka = {ka:.5f}."
    comment = (
        "El coeficiente conserva los ángulos ingresados; para cara vertical y relleno "
        "horizontal reproduce el caso activo convencional."
    )
    return formula, legend, substitution, result_text, comment


def seismic_angle_trace(result: AbutmentDesignResult) -> tuple[str, str, str, str, str]:
    soil = result.inputs.soil
    as_coeff = soil.fpga * soil.pga
    kh = 0.5 * as_coeff
    kv = 0.0
    psi = result.pressures.seismic_angle_deg
    formula = "As = Fpga·PGA ; kh = 0.5·As ; ψ = arctan(kh/(1−kv))"
    legend = (
        "As: coeficiente sísmico del sitio; Fpga: factor de amplificación; PGA: aceleración pico; "
        "kh: coeficiente horizontal; kv: coeficiente vertical (adoptado nulo); ψ: ángulo sísmico."
    )
    substitution = (
        f"As = {soil.fpga:.3f}·{soil.pga:.3f} = {as_coeff:.4f}\n"
        f"kh = 0.5·{as_coeff:.4f} = {kh:.4f}\n"
        f"kv = {kv:.1f}\n"
        f"ψ = arctan({kh:.4f}/(1−{kv:.1f})) = {psi:.3f}°"
    )
    result_text = f"Se utiliza kh = {kh:.4f} y un ángulo sísmico ψ = {psi:.3f}°."
    comment = (
        "El ángulo sísmico inclina la resultante peso–inercia e interviene en Mononobe-Okabe "
        "y en las fuerzas inerciales del estribo y la superestructura."
    )
    return formula, legend, substitution, result_text, comment


def mononobe_okabe_trace(result: AbutmentDesignResult) -> tuple[str, str, str, str, str]:
    soil = result.inputs.soil
    p = result.pressures
    as_coeff = soil.fpga * soil.pga
    kh = 0.5 * as_coeff
    kv = 0.0
    psi = atan(kh / (1.0 - kv))
    phi = radians(soil.friction_angle_deg)
    delta = radians(soil.wall_soil_friction_deg)
    beta = radians(soil.backfill_slope_deg)
    theta = radians(0.0)  # M-O del modelo: inclinación desde la vertical (=0 muro vertical)
    numerator = cos(phi - psi - theta) ** 2.0
    inner = (
        sin(phi + delta)
        * sin(phi - psi - beta)
        / (cos(delta + theta + psi) * cos(beta - theta))
    )
    denominator = (
        cos(psi)
        * cos(theta) ** 2.0
        * cos(delta + theta + psi)
        * (1.0 + sqrt(inner)) ** 2.0
    )
    formula = (
        "kAE = cos²(φ−θ−ψ)/{cosψ·cos²θ·cos(δ+θ+ψ)·[1+√(sin(φ+δ)·sin(φ−ψ−β)"
        "/(cos(δ+θ+ψ)·cos(β−θ)))]²}"
    )
    legend = (
        "kAE: coeficiente activo sísmico Mononobe-Okabe; φ: fricción interna; δ: fricción muro-suelo; "
        "β: pendiente del relleno; θ: inclinación del muro desde la vertical (0° = vertical); "
        "ψ: ángulo sísmico."
    )
    substitution = (
        f"φ = {soil.friction_angle_deg:.3f}°; δ = {soil.wall_soil_friction_deg:.3f}°; "
        f"β = {soil.backfill_slope_deg:.3f}°; θ = 0.000°; ψ = {degrees(psi):.3f}°\n"
        f"√[...] = {sqrt(inner):.6f}\n"
        f"Numerador = cos²(φ−θ−ψ) = {numerator:.6f}\n"
        f"Denominador = {denominator:.6f}\n"
        f"kAE = {numerator:.6f}/{denominator:.6f} = {p.k_ae:.5f}"
    )
    result_text = f"Se obtiene kAE = {p.k_ae:.5f}."
    comment = (
        "Para muro vertical el modelo adopta θ = 0° medido desde la vertical "
        "(equivalente a cara posterior a 90° desde la horizontal)."
    )
    return formula, legend, substitution, result_text, comment


def peq_trace(result: AbutmentDesignResult) -> tuple[str, str, str, str, str]:
    loads = result.inputs.loads
    soil = result.inputs.soil
    g = result.inputs.geometry
    as_coeff = soil.fpga * soil.pga
    peq = result.pressures.peq_tn_m
    arm = g.retained_height_m - g.seat_block_height_m / 2.0
    formula = "PEQ = (PDC + PDW)·As ; yPEQ = H − hc/2"
    legend = (
        "PEQ: fuerza inercial de la superestructura; PDC, PDW: cargas permanentes del tablero; "
        "As = Fpga·PGA; yPEQ: brazo desde la base del relleno; hc: altura de cajuela."
    )
    substitution = (
        f"As = {soil.fpga:.3f}·{soil.pga:.3f} = {as_coeff:.4f}\n"
        f"PEQ = ({loads.pdc_tn_m:.3f} + {loads.pdw_tn_m:.3f})·{as_coeff:.4f} = {peq:.3f} Tn/m\n"
        f"yPEQ = {g.retained_height_m:.3f} − {g.seat_block_height_m:.3f}/2 = {arm:.3f} m"
    )
    result_text = f"La fuerza inercial de superestructura es PEQ = {peq:.3f} Tn/m, con brazo {arm:.3f} m."
    comment = "PEQ actúa solo en Evento Extremo I, a la cota del bloque de asiento."
    return formula, legend, substitution, result_text, comment


def pir_trace(result: AbutmentDesignResult) -> tuple[str, str, str, str, str]:
    soil = result.inputs.soil
    p = result.pressures
    kh = 0.5 * soil.fpga * soil.pga
    w_dc = result.dc_self_weight_tn_m
    w_ev = result.ev_weight_tn_m
    pir_arm = (w_dc * result.dc_self_y_m + w_ev * result.ev_y_m) / (w_dc + w_ev)
    earth_b = max(0.5 * p.pae_tn_m, p.eh_tn_m)
    formula = (
        "PIR = kh·(WDC + WEV) ; Combo A: PAE + 0.5·PIR ; "
        "Combo B: max(0.5·PAE, EH) + PIR"
    )
    legend = (
        "PIR: fuerza inercial de la masa del estribo y relleno; kh: coeficiente horizontal; "
        "WDC, WEV: pesos propios; PAE: empuje activo sísmico total; EH: empuje estático; "
        "las dos combinaciones siguen MTC Art. 2.8.1.1.14.1."
    )
    substitution = (
        f"PIR = {kh:.4f}·({w_dc:.3f} + {w_ev:.3f}) = {p.pir_tn_m:.3f} Tn/m\n"
        f"0.5·PIR = 0.5·{p.pir_tn_m:.3f} = {p.half_pir_tn_m:.3f} Tn/m\n"
        f"yPIR = ({w_dc:.3f}·{result.dc_self_y_m:.3f} + {w_ev:.3f}·{result.ev_y_m:.3f})"
        f"/({w_dc:.3f}+{w_ev:.3f}) = {pir_arm:.3f} m\n"
        f"Combo A: PAE + 0.5·PIR = {p.pae_tn_m:.3f} + {p.half_pir_tn_m:.3f} = "
        f"{p.pae_tn_m + p.half_pir_tn_m:.3f} Tn/m\n"
        f"max(0.5·PAE, EH) = max({0.5*p.pae_tn_m:.3f}, {p.eh_tn_m:.3f}) = {earth_b:.3f} Tn/m\n"
        f"Combo B: max(0.5·PAE, EH) + PIR = {earth_b:.3f} + {p.pir_tn_m:.3f} = "
        f"{earth_b + p.pir_tn_m:.3f} Tn/m"
    )
    governing = result.with_bridge[2].seismic_papir_combination or SEISMIC_PAPIR_COMBO_A
    result_text = (
        f"Se revisan ambas combinaciones MTC; gobierna {governing} "
        f"(Hu = {result.with_bridge[2].hu_tn_m:.3f} Tn/m)."
    )
    comment = REF_SEISMIC_PAPIR
    return formula, legend, substitution, result_text, comment


def mtc_seismic_envelope_trace(result: AbutmentDesignResult) -> tuple[str, str, str, str, str]:
    a_with, b_with = result.extreme_seismic_with_bridge
    a_without, b_without = result.extreme_seismic_without_bridge
    formula = "Adoptar max{verificación(Combo A), verificación(Combo B)}"
    legend = (
        "Combo A = PAE+0.5·PIR; Combo B = max(0.5·PAE, EH)+PIR; "
        "la más desfavorable se define por el mayor índice de utilización "
        "(vuelco, deslizamiento o presión Meyerhof)."
    )
    substitution = (
        f"Con puente — A: Hu={a_with.hu_tn_m:.3f} Tn/m; e={a_with.eccentricity_m:.3f} m; "
        f"qM={a_with.geotechnical_pressure_kg_cm2:.3f} kg/cm²; vuelco={a_with.overturning_status}; "
        f"desliz.={a_with.sliding_with_key_status or a_with.sliding_status}; "
        f"q={a_with.bearing_status}\n"
        f"Con puente — B: Hu={b_with.hu_tn_m:.3f} Tn/m; e={b_with.eccentricity_m:.3f} m; "
        f"qM={b_with.geotechnical_pressure_kg_cm2:.3f} kg/cm²; vuelco={b_with.overturning_status}; "
        f"desliz.={b_with.sliding_with_key_status or b_with.sliding_status}; "
        f"q={b_with.bearing_status}\n"
        f"Sin puente — A: Hu={a_without.hu_tn_m:.3f}; B: Hu={b_without.hu_tn_m:.3f} Tn/m"
    )
    result_text = (
        f"Con puente gobierna {result.with_bridge[2].seismic_papir_combination}; "
        f"sin puente gobierna {result.without_bridge[2].seismic_papir_combination}."
    )
    return formula, legend, substitution, result_text, REF_SEISMIC_PAPIR


def pressure_arms_trace(result: AbutmentDesignResult) -> tuple[str, str, str, str, str]:
    g = result.inputs.geometry
    h = g.retained_height_m
    formula = "yEH = H/3 ; yLSx = H/2 ; yEQterr = H/2 ; yBR = H + hb"
    legend = (
        "yEH: brazo del empuje estático triangular; yLSx, yEQterr: brazos de diagramas uniformes/"
        "incremento sísmico; yBR: brazo del frenado; hb: altura asiento–apoyo."
    )
    substitution = (
        f"yEH = {h:.3f}/3 = {h/3.0:.3f} m\n"
        f"yLSx = {h:.3f}/2 = {h/2.0:.3f} m\n"
        f"yEQterr = {h:.3f}/2 = {h/2.0:.3f} m\n"
        f"yBR = {h:.3f} + {g.bridge_seat_to_bearing_height_m:.3f} = "
        f"{h + g.bridge_seat_to_bearing_height_m:.3f} m"
    )
    result_text = "Los brazos se miden desde la base del diagrama de relleno (fondo de zapata en el modelo)."
    comment = (
        "Estos brazos se usan en MHu = Σ(Hi·yi) y en el inventario de componentes horizontales."
    )
    return formula, legend, substitution, result_text, comment


def concrete_geometry_rows(result: AbutmentDesignResult) -> tuple[tuple[str, ...], ...]:
    """Return (componente, expresión Ai, Ai, xi) for the concrete breakdown table."""
    g = result.inputs.geometry
    gamma = result.inputs.materials.concrete_unit_weight_kg_m3 / 1000.0
    rows: list[tuple[str, ...]] = []
    for component in result.concrete_components:
        area = component.value_tn_m / gamma if gamma else 0.0
        expr = _concrete_area_expression(component.name, g)
        rows.append((component.name, expr, f"{area:.3f}", f"{component.arm_m:.3f}"))
    return tuple(rows)


def _concrete_area_expression(name: str, g) -> str:
    mapping = {
        "1 Parapeto": "ep·hc",
        "2 Cajuela": "hb·(Lc+ep)",
        "3 Transicion t1": "t1·ht/2",
        "4 Pantalla e superior": "es·Hp'",
        "5 Transicion t2": "t2·ht/2",
        "6 Ensanche inferior": "(ei−es)·He/2",
        "7 Zapata": "B·D",
        "Pantalla rectangular": "es·Hp",
        "Ensanche de pantalla": "(ei−es)·Hp/2",
        "Zapata - puntera": "Lp·D",
        "Zapata - bajo pantalla": "ei·D",
        "Zapata - talon": "Lt·D",
    }
    return mapping.get(name, "Ai")


def eccentricity_limit_trace(
    result: AbutmentDesignResult,
    state: StabilityStateResult,
) -> tuple[str, str, str, str, str]:
    factors = factors_for_state(result, state)
    b = result.inputs.geometry.footing_width_m
    ratio = state.minimum_contact_length_ratio
    if factors.limit_state == "service":
        criterion = "Servicio: Lc,min/B = 1 (contacto completo)"
    elif factors.limit_state == "extreme":
        criterion = "Evento extremo: Lc,min/B = 1/3"
    else:
        criterion = "Resistencia: Lc,min/B = 1/2"
    formula = "e_lím = B·(1/2 − Lc,min/(3B)) = B·(0.5 − rmin/3)"
    legend = (
        "e_lím: excentricidad máxima admisible; B: ancho de zapata; "
        "rmin = Lc,min/B: fracción mínima de contacto del estado límite."
    )
    substitution = (
        f"{criterion}\n"
        f"rmin = {ratio:.4f}\n"
        f"e_lím = {b:.3f}·(0.5 − {ratio:.4f}/3) = {state.eccentricity_limit_m:.3f} m"
    )
    result_text = (
        f"|e| = {abs(state.eccentricity_m):.3f} m ≤ e_lím = {state.eccentricity_limit_m:.3f} m: "
        f"{state.overturning_status}."
    )
    comment = "El límite de excentricidad garantiza la longitud de contacto mínima del estado analizado."
    return formula, legend, substitution, result_text, comment


def allowable_bearing_trace(
    result: AbutmentDesignResult,
    state: StabilityStateResult,
) -> tuple[str, str, str, str, str]:
    factors = factors_for_state(result, state)
    soil = result.inputs.soil
    qadm = soil.allowable_bearing_kg_cm2
    fs = soil.bearing_capacity_factor_fs
    if factors.limit_state == "service":
        formula = "qlím = qadm"
        substitution = f"qlím = {qadm:.3f} kg/cm² (Servicio I)"
        legend = "qlím: presión límite del estado; qadm: presión admisible de servicio."
    else:
        phi_b = 0.80 if factors.limit_state == "extreme" else 0.55
        formula = "qlím = φb·FS·qadm"
        substitution = (
            f"φb = {phi_b:.2f}; FS = {fs:.2f}; qadm = {qadm:.3f} kg/cm²\n"
            f"qlím = {phi_b:.2f}·{fs:.2f}·{qadm:.3f} = {state.q_allow_kg_cm2:.3f} kg/cm²"
        )
        legend = (
            "qlím: presión geotécnica límite factorizada; φb: factor de resistencia de cimentación "
            "(0.55 resistencia; 0.80 evento extremo); FS: factor de seguridad nominal; qadm: admisible."
        )
    result_text = (
        f"qM = {state.geotechnical_pressure_kg_cm2:.3f} kg/cm² ≤ qlím = {state.q_allow_kg_cm2:.3f} kg/cm²: "
        f"{state.bearing_status}."
    )
    comment = "La verificación geotécnica compara la presión Meyerhof con qlím del estado límite."
    return formula, legend, substitution, result_text, comment


def component_factor_rows(
    components: tuple[LoadComponent, ...],
    factors: LoadFactors,
    *,
    horizontal: bool,
) -> tuple[tuple[str, ...], ...]:
    rows: list[tuple[str, ...]] = []
    for component in components:
        gamma = _factor_for_type(factors, component.load_type, horizontal=horizontal)
        factored = component.value_tn_m * gamma
        factored_moment = component.moment_tn_m_m * gamma
        rows.append(
            (
                component.name,
                component.load_type,
                f"{component.value_tn_m:.3f}",
                f"{component.arm_m:.3f}",
                f"{gamma:.2f}",
                f"{factored:.3f}",
                f"{factored_moment:.3f}",
            )
        )
    return tuple(rows)


def stem_demand_trace(result: AbutmentDesignResult) -> tuple[str, str, str, str, str]:
    demands = _stem_design_demands(result.inputs, result.pressures)
    case = result.stem_design
    g = result.inputs.geometry
    gamma_soil = result.inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    height = g.stem_height_above_footing_m
    p = result.pressures
    ka = p.ka
    k_ae = p.k_ae
    kh = 0.5 * result.inputs.soil.fpga * result.inputs.soil.pga
    upper_w, _pir_arm = _upper_concrete_weight_and_arm(result.inputs)
    pir = kh * upper_w
    ls_force = ka * p.live_surcharge_height_m * gamma_soil * height + p.pedestrian_lsx_tn_m * height / g.retained_height_m
    eh_force = 0.5 * ka * gamma_soil * height**2.0
    eq_force = 0.5 * (k_ae - ka) * height * gamma_soil * height
    peq = p.peq_tn_m
    br = result.inputs.loads.braking_tn_m
    ls_m = ls_force * height / 2.0
    eh_m = eh_force * height / 3.0
    eq_m = eq_force * height / 2.0
    peq_m = peq * (height - g.seat_block_height_m / 2.0)
    br_m = br * (height + g.bridge_seat_to_bearing_height_m)
    controlling = "Resistencia I" if demands["strength_mu"] >= demands["extreme_mu"] else "Evento Extremo I"
    formula = (
        "Mu,R = 1.75·MLS + 1.50·MEH + 1.75·MBR ; "
        "Mu,E = max(Mu,E-A, Mu,E-B) ; "
        "Mu,E-A = 0.50·MLS + MEH + MEQ + 0.5·MPIR + MPEQ + 0.50·MBR ; "
        "Mu,E-B = 0.50·MLS + M[max(0.5PAE,EH)] + MPIR + MPEQ + 0.50·MBR"
    )
    legend = (
        "MLS, MEH, MEQ, MPIR, MPEQ, MBR: momentos en la base de pantalla; "
        "Mu,E-A y Mu,E-B: combinaciones MTC Art. 2.8.1.1.14.1; Mu = max(Mu,R, Mu,E)."
    )
    substitution = (
        f"Hp = {height:.3f} m; Ka = {ka:.5f}; kAE = {k_ae:.5f}\n"
        f"FLS = {ls_force:.3f} Tn/m; FEH = {eh_force:.3f} Tn/m; FEQ = {eq_force:.3f} Tn/m; "
        f"0.5PIR = {0.5*pir:.3f} Tn/m; PIR = {pir:.3f} Tn/m; PEQ = {peq:.3f} Tn/m; BR = {br:.3f} Tn/m\n"
        f"MLS = {ls_m:.3f}; MEH = {eh_m:.3f}; MEQ = {eq_m:.3f}; MPEQ = {peq_m:.3f}; MBR = {br_m:.3f} Tn·m/m\n"
        f"Mu,R = {demands['strength_mu']:.3f} Tn·m/m\n"
        f"Mu,E-A = {demands['extreme_mu_a']:.3f} Tn·m/m; Mu,E-B = {demands['extreme_mu_b']:.3f} Tn·m/m\n"
        f"Vu,R = {demands['strength_vu']:.3f}; Vu,E-A = {demands['extreme_vu_a']:.3f}; "
        f"Vu,E-B = {demands['extreme_vu_b']:.3f} Tn/m\n"
        f"Gobierna {controlling}: Mu = {case.controlling_moment_tn_m_m:.3f} Tn·m/m; "
        f"Vu = {case.shear_demand_tn_m:.3f} Tn/m"
    )
    result_text = (
        f"Para pantalla gobierna {controlling} con Mu = {case.controlling_moment_tn_m_m:.3f} Tn·m/m "
        f"y Vu = {case.shear_demand_tn_m:.3f} Tn/m."
    )
    comment = (
        "El Evento Extremo de pantalla envuelve las dos combinaciones MTC PAE/PIR; "
        "el PIR de pantalla usa la masa de concreto sobre zapata."
    )
    return formula, legend, substitution, result_text, comment


def heel_toe_demand_trace(
    result: AbutmentDesignResult,
    case: StructuralDesignCase,
) -> tuple[str, str, str, str, str] | None:
    if case.name == "Zapata - talon superior":
        formula = (
            "Mu = |Σ(γi·Wi·xi) − Msuelo| ; Vu = |Σ(γi·Wi) − Vsuelo| ; "
            "envolvente sobre estados con puente"
        )
        legend = (
            "Wi: pesos de zapata/relleno/LSy sobre el talón; Msuelo, Vsuelo: resultante de la "
            "presión de contacto bajo el talón en cada estado."
        )
        substitution = (
            f"Mu gobernante = {case.controlling_moment_tn_m_m:.3f} Tn·m/m\n"
            f"Vu gobernante = {case.shear_demand_tn_m:.3f} Tn/m\n"
            "Pesos factorizados típicos: γDC = 1.25; γEV = 1.35; γLS = 1.75 "
            "(menos reacción de suelo del estado correspondiente)."
        )
        result_text = (
            f"Para el talón Mu = {case.controlling_moment_tn_m_m:.3f} Tn·m/m y "
            f"Vu = {case.shear_demand_tn_m:.3f} Tn/m."
        )
        comment = case.notes or "Envolvente de estados con puente."
        return formula, legend, substitution, result_text, comment
    if case.name == "Zapata - puntera inferior":
        g = result.inputs.geometry
        d_m = case.effective_depth_cm / 100.0
        formula = (
            "Mu = Lp²/6·(qcara + 2·qmax) ; Vu = 0.5·(qcrit + qmax)·(Lp − d)"
        )
        legend = (
            "Lp: longitud de puntera; qmax: presión en el borde de puntera; qcara: presión en la "
            "cara del muro; qcrit: presión a distancia d de la cara; d: peralte efectivo."
        )
        substitution = (
            f"Lp = {g.toe_length_m:.3f} m; d = {d_m:.3f} m\n"
            f"Mu gobernante = {case.controlling_moment_tn_m_m:.3f} Tn·m/m\n"
            f"Vu gobernante = {case.shear_demand_tn_m:.3f} Tn/m"
        )
        result_text = (
            f"Para la puntera Mu = {case.controlling_moment_tn_m_m:.3f} Tn·m/m y "
            f"Vu = {case.shear_demand_tn_m:.3f} Tn/m."
        )
        comment = case.notes or "Envolvente con diagrama de contacto adoptado."
        return formula, legend, substitution, result_text, comment
    if case.name == "Diente de concreto":
        formula = "Mu,diente = f(pp,sup, pp,inf, hd) ; Vu asociado al empuje pasivo del dentellón"
        legend = "pp,sup/pp,inf: presiones pasivas en extremos del dentellón; hd: altura del diente."
        substitution = (
            f"Mu = {case.controlling_moment_tn_m_m:.3f} Tn·m/m; "
            f"Vu = {case.shear_demand_tn_m:.3f} Tn/m"
        )
        result_text = (
            f"Para el dentellón Mu = {case.controlling_moment_tn_m_m:.3f} Tn·m/m y "
            f"Vu = {case.shear_demand_tn_m:.3f} Tn/m."
        )
        comment = "La demanda proviene del diagrama pasivo movilizado sobre la cara del diente."
        return formula, legend, substitution, result_text, comment
    return None


def effective_depth_trace(
    result: AbutmentDesignResult,
    case: StructuralDesignCase,
    gross_depth_cm: float,
) -> tuple[str, str, str, str, str]:
    cover = _cover_for_case(result.inputs, case.name)
    bar = _bar_by_label(case.selected_bar_label)
    formula = "d = h − rec − db/2"
    legend = (
        "d: peralte efectivo; h: espesor total; rec: recubrimiento a la cara traccionada; "
        "db: diámetro de la barra principal."
    )
    substitution = (
        f"h = {gross_depth_cm:.2f} cm; rec = {cover:.2f} cm; db = {bar.diameter_cm:.3f} cm\n"
        f"d = {gross_depth_cm:.2f} − {cover:.2f} − {bar.diameter_cm:.3f}/2 = {case.effective_depth_cm:.2f} cm"
    )
    result_text = f"El peralte efectivo utilizado es d = {case.effective_depth_cm:.2f} cm."
    comment = "El recubrimiento y el diámetro corresponden a la cara traccionada del elemento."
    return formula, legend, substitution, result_text, comment


def cracking_and_temperature_trace(
    result: AbutmentDesignResult,
    case: StructuralDesignCase,
    gross_depth_cm: float,
) -> tuple[str, str, str, str, str]:
    fc = result.inputs.materials.concrete_strength_kg_cm2
    fr = 2.01 * sqrt(fc)
    s_mod = 100.0 * gross_depth_cm**2.0 / 6.0
    mult = result.inputs.reinforcement.minimum_flexural_capacity_multiplier
    fy = result.inputs.materials.steel_yield_kg_cm2
    if case.name == "Pantalla":
        temperature = _stem_temperature_result(result.inputs)
        b_cm = temperature.b_cm
        h_cm = temperature.h_cm
        b_label = (
            f"(ei+es)/2 = ({result.inputs.geometry.lower_stem_thickness_m*100:.1f}+"
            f"{result.inputs.geometry.upper_stem_thickness_m*100:.1f})/2"
        )
        h_label = "Hp" if result.inputs.is_pure_wall else "Hp'"
    elif case.name == "Diente de concreto":
        b_cm = result.inputs.key.width_m * 100.0
        h_cm = result.inputs.key.height_m * 100.0
        b_label = "ancho del diente"
        h_label = "altura del diente"
        raw = 7.65 * b_cm * h_cm / (2.0 * (b_cm + h_cm) * fy) * 100.0
        temperature = None
    else:
        temperature = _footing_temperature_result(result.inputs)
        b_cm = temperature.b_cm
        h_cm = temperature.h_cm
        b_label = "B"
        h_label = "D"
    if temperature is not None:
        raw = temperature.raw_as_cm2_m
        bounded = temperature.required_as_cm2_m
    else:
        bounded = max(TEMPERATURE_STEEL_MIN_CM2_M, min(TEMPERATURE_STEEL_MAX_CM2_M, raw))
    temp_expr = (
        f"As,temp = 7.65·b·h/(2(b+h)·fy)·100 con b = {b_label} = {b_cm:.1f} cm, "
        f"h = {h_label} = {h_cm:.1f} cm\n"
        f"As,calc = {raw:.3f} cm²/m; "
        f"As,temp = max({TEMPERATURE_STEEL_MIN_CM2_M:.2f}, min({TEMPERATURE_STEEL_MAX_CM2_M:.2f}, As,calc)) "
        f"= {bounded:.3f} cm²/m"
    )
    formula = (
        "fr = 2.01·√f'c ; S = b·h²/6 ; Mcr = 1.1·fr·S ; "
        f"Mmin = min(Mcr, {mult:.2f}·Mu) ; As,req = max(As,flex, As,temp, As,cap)"
    )
    legend = (
        "fr: módulo de rotura; S: módulo de sección bruta; Mcr: momento de fisuración; "
        "Mmin: capacidad mínima; As,temp: acero por temperatura MTC 2.9.1.4.5.8; As,cap: acero para Mmin."
    )
    substitution = (
        f"fr = 2.01·√{fc:.1f} = {fr:.3f} kg/cm²\n"
        f"S = 100·{gross_depth_cm:.2f}²/6 = {s_mod:.1f} cm³\n"
        f"Mcr = 1.1·{fr:.3f}·{s_mod:.1f}/1e5 = {case.cracking_moment_tn_m_m:.3f} Tn·m/m\n"
        f"{mult:.2f}·Mu = {case.multiplier_minimum_moment_tn_m_m:.3f} Tn·m/m\n"
        f"Mmin = {case.minimum_capacity_moment_tn_m_m:.3f} Tn·m/m\n"
        f"fy = {fy:.1f} kg/cm²\n"
        f"{temp_expr}\n"
        f"As,cap = {case.capacity_minimum_as_cm2_m:.3f} cm²/m; "
        f"As,flex = {case.strength_as_cm2_m:.3f} cm²/m; "
        f"As,req = {case.required_as_cm2_m:.3f} cm²/m"
    )
    result_text = f"Gobierna As,req = {case.required_as_cm2_m:.3f} cm²/m."
    comment = (
        "El refuerzo adoptado no puede ser menor que los controles de resistencia, "
        "temperatura y capacidad mínima."
    )
    return formula, legend, substitution, result_text, comment


def secondary_temperature_trace(
    case: AbutmentSecondaryReinforcementCase,
) -> tuple[str, str, str, str, str]:
    formula = (
        "As,temp = 7.65·b·h/(2(b+h)·fy)·100 ; "
        f"{TEMPERATURE_STEEL_MIN_CM2_M:.2f} ≤ As,temp ≤ {TEMPERATURE_STEEL_MAX_CM2_M:.2f} ; "
        "As,adic = max(0, As,temp − As,princ) ; As,prov = Ab/s ≥ As,adic ; s ≤ smax"
    )
    legend = (
        "As,temp: mínimo normativo por temperatura y retracción en cada cara y dirección; "
        "As,princ: acero estructural principal ya colocado en la misma cara/dirección; "
        "As,adic: acero adicional requerido; smax = 30 cm cuando el espesor > 45 cm."
    )
    primary_text = (
        f"As,princ = {case.primary_steel_as_cm2_m:.3f} cm²/m\n"
        if case.primary_steel_as_cm2_m > 0.0
        else "As,princ = 0.000 cm²/m (no hay acero principal en esta cara/dirección)\n"
    )
    substitution = (
        f"b = {case.temperature_b_cm:.1f} cm; h = {case.temperature_h_cm:.1f} cm\n"
        f"As,calc = {case.raw_temperature_as_cm2_m:.3f} cm²/m\n"
        f"As,temp = {case.temperature_required_as_cm2_m:.3f} cm²/m\n"
        f"{primary_text}"
        f"As,adic = max(0, {case.temperature_required_as_cm2_m:.3f} − "
        f"{case.primary_steel_as_cm2_m:.3f}) = {case.required_as_cm2_m:.3f} cm²/m\n"
        f"Se adopta {case.selected_bar_label} @ {case.selected_spacing_m:.3f} m → "
        f"As,prov = {case.provided_as_cm2_m:.3f} cm²/m\n"
        f"smax = {case.maximum_spacing_m*100:.1f} cm"
    )
    if case.required_as_cm2_m <= 0.0:
        result_text = (
            f"As,temp = {case.temperature_required_as_cm2_m:.3f} cm²/m y "
            f"As,adic = 0.000 cm²/m porque el acero principal ya cubre el mínimo: OK."
        )
    else:
        result_text = (
            f"As,prov = {case.provided_as_cm2_m:.3f} cm²/m ≥ As,adic = {case.required_as_cm2_m:.3f} cm²/m; "
            f"s = {case.selected_spacing_m*100:.1f} cm ≤ smax = {case.maximum_spacing_m*100:.1f} cm: "
            f"{case.status}."
        )
    comment = (
        "La verificación se realiza por cara y dirección según MTC 2.9.1.4.5.8. "
        "Cuando As,adic = 0 el requerimiento normativo As,temp sigue siendo "
        f"{case.temperature_required_as_cm2_m:.3f} cm²/m, satisfecho por el acero principal."
    )
    return formula, legend, substitution, result_text, comment


def shear_beta_trace(
    result: AbutmentDesignResult,
    case: StructuralDesignCase,
) -> tuple[str, str, str, str, str]:
    phi_v = result.inputs.reinforcement.shear_phi
    fc = result.inputs.materials.concrete_strength_kg_cm2
    gross_depth_cm = _section_depth_cm(result.inputs, case.name)
    ag = DEFAULT_MAX_AGGREGATE_SIZE_IN
    if case.shear_beta_method == "general":
        formula = (
            "Mu,usado = max(Mu, Vu·dv) ; εs = 1000·(Mu,usado/dv + Vu)/(Es·As,prov) ; "
            "dv = max(0.9d, 0.72h) ; sx = dv ; sxe = sx·1.38/(ag + 0.63) ; "
            "β = 4.8/(1 + 750·εs)·51/(39 + sxe) ; Vr = φv·0.265·β·√f'c·b·d"
        )
        legend = (
            "Procedimiento general MTC 2.9.1.5.6.3.4.2 / AASHTO 5.7.3.4.2 sin estribos transversales; "
            "εs: deformación longitudinal media; sx y sxe: espaciamiento de fisuras y valor efectivo (in); "
            "ag: tamaño máximo de agregado (= 3/4\" adoptado); Es = 2 000 000 kg/cm²; b = 100 cm."
        )
        substitution = (
            f"d = {case.effective_depth_cm:.2f} cm; h = {gross_depth_cm:.2f} cm\n"
            f"dv = max(0.9·{case.effective_depth_cm:.2f}, 0.72·{gross_depth_cm:.2f}) "
            f"= {case.shear_effective_depth_cm:.2f} cm\n"
            f"Mu = {case.controlling_moment_tn_m_m:.3f} Tn·m/m; Vu = {case.shear_demand_tn_m:.3f} Tn/m\n"
            f"Mu,usado = max({case.controlling_moment_tn_m_m:.3f}, "
            f"{case.shear_demand_tn_m:.3f}·{case.shear_effective_depth_cm/100:.3f}) "
            f"= {case.shear_controlling_moment_tn_m_m:.3f} Tn·m/m\n"
            f"εs = 1000·({case.shear_controlling_moment_tn_m_m:.3f}/{case.shear_effective_depth_cm/100:.3f} "
            f"+ {case.shear_demand_tn_m:.3f})/({STEEL_ELASTIC_MODULUS_KG_CM2:.0f}·{case.provided_as_cm2_m:.3f}) "
            f"= {case.shear_longitudinal_strain:.6f}\n"
            f"sx = {case.shear_crack_spacing_in:.3f} in; ag = {ag:.2f} in\n"
            f"sxe = {case.shear_crack_spacing_in:.3f}·1.38/({ag:.2f} + 0.63) "
            f"= {case.shear_effective_crack_spacing_in:.3f} in\n"
            f"β = 4.8/(1 + 750·{case.shear_longitudinal_strain:.6f})·51/(39 + {case.shear_effective_crack_spacing_in:.3f}) "
            f"= {case.shear_beta:.6f}\n"
            f"Vr = {phi_v:.3f}·0.265·{case.shear_beta:.6f}·√{fc:.1f}·100·{case.effective_depth_cm:.2f}/1000 "
            f"= {case.shear_resistance_tn_m:.3f} Tn/m"
        )
        comment = (
            "β se calcula con el acero principal adoptado (As,prov) porque la deformación longitudinal "
            f"depende del refuerzo suministrado. Referencia: {REF_SHEAR_BETA}"
        )
    else:
        formula = (
            "dv = max(0.9d, 0.72h) ; β = 2 (procedimiento simplificado, θ = 45°) ; "
            "Vr = φv·0.265·β·√f'c·b·d"
        )
        legend = (
            "Procedimiento simplificado MTC 2.9.1.5.6.3.4.1 / AASHTO 5.7.3.4.1 cuando la sección crítica "
            "está a menos de 3·dv de la cara del muro; b = 100 cm; d: peralte efectivo."
        )
        substitution = (
            f"d = {case.effective_depth_cm:.2f} cm; h = {gross_depth_cm:.2f} cm\n"
            f"dv = max(0.9·{case.effective_depth_cm:.2f}, 0.72·{gross_depth_cm:.2f}) "
            f"= {case.shear_effective_depth_cm:.2f} cm\n"
            f"Distancia cortante nula (cara muro < 3·dv): se adopta β = {SIMPLIFIED_SHEAR_BETA:.1f}\n"
            f"Vr = {phi_v:.3f}·0.265·{case.shear_beta:.1f}·√{fc:.1f}·100·{case.effective_depth_cm:.2f}/1000 "
            f"= {case.shear_resistance_tn_m:.3f} Tn/m\n"
            f"Vu = {case.shear_demand_tn_m:.3f} Tn/m"
        )
        comment = (
            "Zapata y dentellón verifican corte con el procedimiento simplificado porque la sección crítica "
            f"queda junto a la cara del muro. Referencia: {REF_SHEAR_BETA}"
        )
    result_text = (
        f"Vu = {case.shear_demand_tn_m:.3f} Tn/m ≤ Vr = {case.shear_resistance_tn_m:.3f} Tn/m: "
        f"{case.shear_status}."
    )
    return formula, legend, substitution, result_text, comment


def stem_cut_continuous_pattern_trace(
    result: AbutmentDesignResult,
    cut: AbutmentStemReinforcementCut,
) -> tuple[str, str, str, str, str]:
    bar = _bar_by_label(cut.lower_bar_label)
    formula = (
        "smax,pat = Ab/As,temp ; n = ⌊smax,pat/sinf⌋ ; ssup = n·sinf ; "
        "As,sup = Ab/ssup ; As,sup ≥ As,temp"
    )
    legend = (
        "smax,pat: espaciamiento máximo compatible con el mínimo por temperatura; "
        "n: número de barras inferiores entre barras superiores continuas; "
        "sinf y ssup: espaciamientos inferior y superior; Ab: área de barra."
    )
    substitution = (
        f"As,temp = {cut.minimum_as_cm2_m:.3f} cm²/m\n"
        f"Ab = {bar.area_cm2:.3f} cm² ({cut.lower_bar_label})\n"
        f"smax,pat = {bar.area_cm2:.3f}/{cut.minimum_as_cm2_m:.3f} = {cut.upper_spacing_limit_m:.3f} m\n"
        f"sinf = {cut.lower_spacing_m:.3f} m\n"
        f"n = ⌊{cut.upper_spacing_limit_m:.3f}/{cut.lower_spacing_m:.3f}⌋ = {cut.continuous_every_n_bars}\n"
        f"ssup = {cut.continuous_every_n_bars}·{cut.lower_spacing_m:.3f} = {cut.upper_spacing_m:.3f} m\n"
        f"As,sup = {bar.area_cm2:.3f}/{cut.upper_spacing_m:.3f} = {cut.upper_provided_as_cm2_m:.3f} cm²/m"
    )
    result_text = (
        f"As,sup = {cut.upper_provided_as_cm2_m:.3f} cm²/m ≥ As,temp = {cut.minimum_as_cm2_m:.3f} cm²/m: "
        f"{'OK' if cut.upper_provided_as_cm2_m + 1e-9 >= cut.minimum_as_cm2_m else 'NO'}."
    )
    comment = (
        "El acero superior continuo reutiliza la misma barra de la parrilla inferior, "
        f"continuando 1 de cada {cut.continuous_every_n_bars} barras para respetar el mínimo por temperatura."
    )
    return formula, legend, substitution, result_text, comment


def stem_cut_theoretical_height_trace(
    result: AbutmentDesignResult,
    cut: AbutmentStemReinforcementCut,
) -> tuple[str, str, str, str, str]:
    g = result.inputs.geometry
    phi = result.inputs.reinforcement.stem_design_phi_for_as
    bar = _bar_by_label(cut.lower_bar_label)
    cover = result.inputs.reinforcement.stem_cover_cm
    formula = (
        "Mu(h) = envolvente Resistencia/Evento Extremo sobre relleno remanente ; "
        "d(h) = t(h) − rec − db/2 ; As,req(h) = max(As,flex, As,min) ; "
        "Mr(h) = φ·As,sup·fy·(d − a/2) ; ht = min{h | Mr(h) ≥ max(Mu(h), Mmin(h)) y As,sup ≥ As,req(h)}"
    )
    legend = (
        "h: cota sobre la zapata; t(h): espesor de pantalla en h; Mu(h): momento factorizado "
        "del tramo de relleno superior; As,sup: acero continuo superior; ht: altura teórica de corte."
    )
    substitution = (
        f"Hp = {g.stem_height_above_footing_m:.3f} m\n"
        f"ht = {cut.theoretical_cut_height_m:.3f} m; t(ht) = {cut.thickness_at_cut_cm:.2f} cm\n"
        f"d(ht) = {cut.thickness_at_cut_cm:.2f} − {cover:.2f} − {bar.diameter_cm/2:.3f} "
        f"= {cut.effective_depth_at_cut_cm:.2f} cm\n"
        f"Mu(ht) = {cut.controlling_moment_at_cut_tn_m_m:.3f} Tn·m/m\n"
        f"As,flex = {cut.strength_as_at_cut_cm2_m:.3f} cm²/m; As,min = {cut.minimum_as_at_cut_cm2_m:.3f} cm²/m\n"
        f"As,req(ht) = {cut.required_as_at_cut_cm2_m:.3f} cm²/m; As,sup = {cut.upper_provided_as_cm2_m:.3f} cm²/m\n"
        f"Mreq = max(Mu, Mmin) = {cut.required_moment_at_cut_tn_m_m:.3f} Tn·m/m\n"
        f"Mr(ht) = {cut.moment_resistance_at_cut_tn_m_m:.3f} Tn·m/m (φ = {phi:.2f})"
    )
    capacity_ok = cut.moment_resistance_at_cut_tn_m_m + 1e-9 >= cut.required_moment_at_cut_tn_m_m
    steel_ok = cut.upper_provided_as_cm2_m + 1e-9 >= cut.required_as_at_cut_cm2_m
    result_text = (
        f"En ht = {cut.theoretical_cut_height_m:.3f} m: Mr = {cut.moment_resistance_at_cut_tn_m_m:.3f} Tn·m/m "
        f"≥ Mreq = {cut.required_moment_at_cut_tn_m_m:.3f} Tn·m/m y As,sup ≥ As,req(ht): "
        f"{'OK' if capacity_ok and steel_ok else 'NO'}."
    )
    comment = (
        "ht se obtiene por búsqueda en [0, Hp]: es la cota más baja desde la que el acero superior "
        "continuo puede resistir el momento remanente del relleno."
    )
    return formula, legend, substitution, result_text, comment


def stem_cut_constructive_length_trace(
    result: AbutmentDesignResult,
    cut: AbutmentStemReinforcementCut,
) -> tuple[str, str, str, str, str]:
    g = result.inputs.geometry
    formula = (
        "hc = ht + ld ; Lcort = hc + ld ; Lcont = Hp + ld"
    )
    legend = (
        "hc: altura constructiva de terminación de barras cortadas sobre la zapata; "
        "ht: altura teórica de corte; ld: longitud de desarrollo de la sección 7.2; "
        "Lcort: longitud de barras cortadas; Lcont: longitud de barras continuas; Hp: altura de pantalla."
    )
    substitution = (
        f"ht = {cut.theoretical_cut_height_m:.3f} m; ld = {cut.development_extension_m:.3f} m\n"
        f"hc = {cut.theoretical_cut_height_m:.3f} + {cut.development_extension_m:.3f} "
        f"= {cut.constructive_cut_height_m:.3f} m sobre la zapata\n"
        f"Lcort = {cut.constructive_cut_height_m:.3f} + {cut.development_extension_m:.3f} "
        f"= {cut.lower_cut_bar_length_m:.3f} m\n"
        f"Hp = {g.stem_height_above_footing_m:.3f} m\n"
        f"Lcont = {g.stem_height_above_footing_m:.3f} + {cut.development_extension_m:.3f} "
        f"= {cut.continuous_bar_length_m:.3f} m"
    )
    result_text = (
        f"Barras cortadas ({cut.lower_bar_label} @ {cut.lower_spacing_m:.3f} m): L = {cut.lower_cut_bar_length_m:.3f} m; "
        f"barras continuas (1 de cada {cut.continuous_every_n_bars}, {cut.upper_bar_label} @ "
        f"{cut.upper_spacing_m:.3f} m): L = {cut.continuous_bar_length_m:.3f} m."
    )
    comment = (
        "Las barras cortadas se prolongan ld por debajo de hc para desarrollo en zapata; "
        "las continuas llegan hasta la coronación con ld adicional de anclaje."
    )
    return formula, legend, substitution, result_text, comment


def crack_control_trace(result: AbutmentDesignResult, check) -> tuple[str, str, str, str, str]:
    section_depth = (
        result.inputs.geometry.lower_stem_thickness_m * 100.0
        if check.element == "Pantalla"
        else (
            result.inputs.key.width_m * 100.0
            if check.element == "Diente de concreto"
            else result.inputs.geometry.footing_thickness_m * 100.0
        )
    )
    gamma_e = 1.0
    fss_mpa = check.steel_stress_used_kg_cm2 * KG_CM2_TO_MPA
    formula = (
        "fs = Ms/(As·0.90·d) ; βs = 1 + dc/(0.7·(h−dc)) ; "
        "smax = 123000·γe/(βs·fss) − 2·dc  (MPa, mm)"
    )
    legend = (
        "Ms: momento de servicio; fs: esfuerzo en acero; fss: esfuerzo usado (≤0.60fy); "
        "dc: distancia a la fibra extrema; βs: factor de fisuración; γe: factor de exposición (=1)."
    )
    substitution = (
        f"Ms = {check.service_moment_tn_m_m:.3f} Tn·m/m\n"
        f"fs = {check.steel_stress_kg_cm2:.1f} kg/cm²; fss = {check.steel_stress_used_kg_cm2:.1f} kg/cm² "
        f"= {fss_mpa:.3f} MPa\n"
        f"h = {section_depth:.2f} cm; dc = {check.dc_cm:.2f} cm\n"
        f"βs = 1 + {check.dc_cm:.2f}/(0.7·({section_depth:.2f}−{check.dc_cm:.2f})) = {check.beta_s:.4f}\n"
        f"smax = 123000·{gamma_e:.1f}/({check.beta_s:.4f}·{fss_mpa:.3f}) − 2·{check.dc_cm:.2f}·10 "
        f"= {check.maximum_spacing_m*1000:.1f} mm = {check.maximum_spacing_m:.3f} m"
    )
    result_text = (
        f"sprov = {check.provided_spacing_m:.3f} m ≤ smax = {check.maximum_spacing_m:.3f} m: "
        f"{check.status}."
    )
    comment = "El espaciamiento máximo controla el ancho de fisura en servicio según MTC/AASHTO."
    return formula, legend, substitution, result_text, comment


def development_trace(result: AbutmentDesignResult, check) -> tuple[str, str, str, str, str]:
    r = result.inputs.reinforcement
    bar = _bar_by_label(check.bar_label)
    fc = result.inputs.materials.concrete_strength_kg_cm2
    fy = result.inputs.materials.steel_yield_kg_cm2
    formula = (
        "ldb = 2.4·db·fy/√f'c  (db in, fy y f'c en ksi) ; "
        "ld = max(ldb·λu·λr·λc·λcf·λexc ; 12 in)"
    )
    legend = (
        "ldb: longitud básica de desarrollo; λu, λr, λc, λcf: factores de ubicación, "
        "recubrimiento, concreto ligero y confinamiento; λexc = As,req/As,prov (≥0.4)."
    )
    required = (
        check.required_hooked_ld_cm if check.anchorage_type == "GANCHO" else check.required_ld_cm
    )
    substitution = (
        f"db = {bar.diameter_cm:.3f} cm; fy = {fy:.1f} kg/cm²; f'c = {fc:.1f} kg/cm²\n"
        f"λu = {r.development_location_factor:.2f}; λr = {r.development_coating_factor:.2f}; "
        f"λc = {r.development_lightweight_factor:.2f}; λcf = {r.development_confinement_factor:.2f}\n"
        f"λexc = As,req/As,prov = {check.excess_reinforcement_factor:.4f}\n"
        f"ldb = {check.basic_ld_cm:.2f} cm; ld recto = {check.required_ld_cm:.2f} cm; "
        f"ld gancho = {check.required_hooked_ld_cm:.2f} cm\n"
        f"ldisp = {check.available_length_cm:.2f} cm"
    )
    result_text = (
        f"Se adopta anclaje {check.anchorage_type}; ldisp = {check.available_length_cm:.2f} cm "
        f"y longitud requerida = {required:.2f} cm: {check.status}."
    )
    comment = "Si la longitud recta disponible no alcanza ldb, se verifica anclaje con gancho estándar."
    return formula, legend, substitution, result_text, comment


def passive_key_height_trace(result: AbutmentDesignResult) -> tuple[str, str, str, str, str] | None:
    if result.key is None:
        return None
    g = result.inputs.geometry
    key_in = result.inputs.key
    key = result.key
    h = g.front_soil_depth_m
    formula = "h = hf ; pp,sup = Kp·γs·h ; pp,inf = Kp·γs·(h+hd) ; Rk = φep·Rep"
    legend = (
        "h: altura de suelo frontal sobre el extrados del dentellón; hf: suelo frontal; "
        "hd: altura del dentellón; φep: factor de resistencia pasiva; Rep: resistencia pasiva total."
    )
    substitution = (
        f"h = hf = {h:.3f} m; hd = {key_in.height_m:.3f} m\n"
        f"pp,sup = {key.kp:.5f}·{result.inputs.materials.soil_unit_weight_kg_m3/1000:.3f}·{h:.3f} "
        f"= {key.top_pressure_tn_m2:.3f} Tn/m²\n"
        f"pp,inf = {key.bottom_pressure_tn_m2:.3f} Tn/m²\n"
        f"Rep = {key.total_passive_resistance_tn_m:.3f} Tn/m\n"
        f"φep = {key_in.passive_resistance_factor:.3f}\n"
        f"Rk = {key_in.passive_resistance_factor:.3f}·{key.total_passive_resistance_tn_m:.3f} "
        f"= {key.factored_passive_tn_m:.3f} Tn/m"
    )
    result_text = f"El aporte pasivo factorizado del dentellón es Rk = {key.factored_passive_tn_m:.3f} Tn/m."
    comment = (
        "La resistencia pasiva factorizada se suma a la fricción en la verificación al deslizamiento "
        "cuando el dentellón está habilitado."
    )
    return formula, legend, substitution, result_text, comment


def _bar_by_label(label: str):
    normalized = label.strip().replace("Ø", "").strip()
    for bar in REINFORCING_BAR_CATALOG:
        if bar.label == normalized:
            return bar
    raise ValueError(f"No existe la barra {label} en el catálogo.")
