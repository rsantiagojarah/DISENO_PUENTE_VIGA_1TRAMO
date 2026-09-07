"""Traceable numerical detail builders for the deck Word memory report."""

from __future__ import annotations

from bridge_design.codes.mtc_2018 import (
    DEFAULT_CRACK_CONTROL_EXPOSURE_FACTOR,
    DEFAULT_SERVICE_STRESS_LEVER_ARM_FACTOR,
    DEFAULT_SHRINKAGE_TEMPERATURE_RATIO,
    _concrete_t_girder_longitudinal_stiffness_in4,
    _distribution_stiffness_term,
    _interior_concrete_t_girder_moment_one_lane_g,
    _limited_exterior_de_ft,
    mtc_exterior_lever_rule_distribution_factor,
    mtc_exterior_rigid_cross_section_distribution_factor,
    mtc_interior_concrete_t_girder_live_load_distribution_factor,
    mtc_interior_concrete_t_girder_live_load_shear_distribution_factor,
)
from bridge_design.domain.interior_girder import FATIGUE_I_LOAD_FACTOR
from bridge_design.units.converters import m_to_ft, m_to_in


KG_CM2_TO_MPA = 0.0980665


def flexural_as_min_trace(
    *,
    strip: bool,
    design,
    concrete,
    steel,
    option_text: str,
    compliance_comment: str,
) -> tuple[str, str, str, str, str]:
    """Return (formula, legend, substitution, result, comment) for flexure."""
    width = 100.0 if strip else getattr(design, "section_width_cm", getattr(design, "flange_width_cm", 100.0))
    strength_area = getattr(design, "strength_area_cm2_m", getattr(design, "strength_area_cm2", 0.0))
    minimum_area = getattr(design, "minimum_area_cm2_m", getattr(design, "minimum_area_cm2", 0.0))
    required_area = getattr(design, "required_area_cm2_m", getattr(design, "required_area_cm2", 0.0))
    d = design.effective_depth_cm
    fy = steel.yield_strength_kg_cm2
    fc = concrete.compressive_strength_kg_cm2
    a = strength_area * fy / (0.85 * fc * width) if strength_area > 0 else 0.0
    units = "cm²/m" if strip else "cm²"
    phi_mn = 0.90 * strength_area * fy * (d - a / 2.0) / 100000.0 if strength_area > 0 else 0.0
    position_m = getattr(design, "position_m", 0.0)

    if strip:
        rho = DEFAULT_SHRINKAGE_TEMPERATURE_RATIO
        h_cm = getattr(design, "slab_height_cm", None)
        if h_cm is None and rho > 0 and minimum_area > 0:
            h_cm = minimum_area / (rho * 100.0)
        h_txt = f"{h_cm:.2f}" if h_cm is not None else "h"
        min_legend = (
            "As,min: acero mínimo por temperatura/retracción ρ·b·h; ρ = 0.0018; "
            "b = 100 cm por franja de 1 m; h = espesor de losa."
        )
        min_lines = (
            f"As,min = {rho:.4f}·100·{h_txt} = {minimum_area:.3f} {units}"
        )
    else:
        bw = getattr(design, "web_width_cm", width)
        ratio1 = 0.8 * fc**0.5 / fy
        ratio2 = 14.0 / fy
        ratio = max(ratio1, ratio2)
        min_legend = (
            "As,min = max(0.8√f'c/fy; 14/fy)·bw·d; bw: ancho de alma; d: peralte efectivo."
        )
        min_lines = (
            f"ρmin = max(0.8·√{fc:.1f}/{fy:.0f}; 14/{fy:.0f}) = max({ratio1:.6f}; {ratio2:.6f}) = {ratio:.6f}\n"
            f"As,min = {ratio:.6f}·{bw:.2f}·{d:.2f} = {minimum_area:.3f} {units}"
        )

    formula = (
        "a = As·fy/(0.85·f'c·b)  ;  φMn = φ·As·fy·(d − a/2)  ;  "
        "As,req = max(As,res; As,min)"
    )
    legend = (
        "a: bloque equivalente; As: acero a tracción; b: ancho resistente; d: peralte efectivo; "
        "φ = 0.90; As,res: acero por resistencia φMn ≥ Mu; As,min: acero mínimo; "
        + min_legend
    )
    substitution = (
        f"Mu = {design.design_moment_tn_m:.3f} Tn·m\n"
        f"x = {position_m:.3f} m\n"
        f"d = {d:.2f} cm\n"
        f"b = {width:.2f} cm\n"
        f"fy = {fy:.0f} kg/cm²\n"
        f"f'c = {fc:.1f} kg/cm²\n"
        f"As,res = {strength_area:.3f} {units}\n"
        f"a = {strength_area:.3f}·{fy:.0f}/(0.85·{fc:.1f}·{width:.2f}) = {a:.3f} cm\n"
        f"φMn = 0.90·{strength_area:.3f}·{fy:.0f}·({d:.2f} − {a:.3f}/2)/100000 = {phi_mn:.3f} Tn·m\n"
        f"{min_lines}"
    )
    result = (
        f"As,res = {strength_area:.3f} {units}; As,min = {minimum_area:.3f} {units}; "
        f"As,req = max({strength_area:.3f}; {minimum_area:.3f}) = {required_area:.3f} {units}. "
        f"Se adopta {option_text}."
    )
    return formula, legend, substitution, result, compliance_comment


def crack_control_trace(crack, *, slab_thickness_cm: float | None = None) -> tuple[str, str, str, str, str]:
    """Return detailed crack-control substitution strings."""
    gamma_e = DEFAULT_CRACK_CONTROL_EXPOSURE_FACTOR
    jd = DEFAULT_SERVICE_STRESS_LEVER_ARM_FACTOR
    dc = crack.dc_cm
    h = slab_thickness_cm
    if h is None:
        beta = crack.beta_s
        denom = beta - 1.0
        h = dc + dc / (0.7 * denom) if denom > 1e-9 else dc * 2.0
    d = h - dc
    mserv = crack.service_moment_tn_m
    as_prov = crack.provided_area_cm2_m
    fs = crack.steel_stress_kg_cm2
    fs_used = crack.steel_stress_used_kg_cm2
    beta_s = crack.beta_s
    combo = getattr(crack, "service_combination_name", "SERVICIO I")
    fs_mpa = fs_used * KG_CM2_TO_MPA
    term1 = 123000.0 * gamma_e / (beta_s * fs_mpa) if beta_s * fs_mpa > 0 else 0.0
    term2 = 2.0 * dc * 10.0
    smax_mm = term1 - term2

    formula = "smax = 123000·γe/(βs·fs) − 2·dc  ;  sprov ≤ smax"
    legend = (
        f"Mserv: momento de {combo} (factores 1.0); "
        f"fs = Mserv/(As,prov·{jd:.2f}·d); "
        "βs = 1 + dc/[0.7(h − dc)]; dc = c + db/2; "
        "γe: factor de exposición (1.0 ambiente normal); "
        "fs usada = min(fs; 0.60·fy)."
    )
    substitution = (
        f"Mserv = {mserv:.3f} Tn·m ({combo})\n"
        f"barra = {crack.bar_label}\n"
        f"As,prov = {as_prov:.3f} cm²/m\n"
        f"dc = {dc:.2f} cm\n"
        f"h = {h:.2f} cm\n"
        f"d = h − dc = {d:.2f} cm\n"
        f"fs = ({mserv:.3f}·100000)/({as_prov:.3f}·{jd:.2f}·{d:.2f}) = {fs:.1f} kg/cm²\n"
        f"fs usada = {fs_used:.1f} kg/cm²\n"
        f"βs = 1 + {dc:.2f}/[0.7·({h:.2f} − {dc:.2f})] = {beta_s:.3f}\n"
        f"smax = 123000·{gamma_e:.2f}/({beta_s:.3f}·{fs_mpa:.1f}) − 2·{dc:.2f}·10 "
        f"= {term1:.1f} − {term2:.1f} = {smax_mm:.1f} mm = {crack.maximum_spacing_m:.3f} m"
    )
    result = (
        f"smax = {crack.maximum_spacing_m:.3f} m; sprov = {crack.provided_spacing_m:.3f} m: {crack.status}."
    )
    comment = (
        "El espaciamiento adoptado limita el ancho de fisura bajo la combinación de servicio."
        if crack.status == "CUMPLE"
        else "El espaciamiento adoptado no satisface el límite de control de fisuración."
    )
    return formula, legend, substitution, result, comment


def interior_g_factor_trace(geometry) -> tuple[str, str, str, str, str]:
    """Build gM / gV calculation detail for an interior girder."""
    L = geometry.span_length_m
    S = geometry.girder_spacing_m
    ts = geometry.slab_thickness_m
    h = geometry.girder_total_height_m
    bw = geometry.web_width_m
    n_g = geometry.girder_count
    span_ft = m_to_ft(L)
    spacing_ft = m_to_ft(S)
    ts_in = m_to_in(ts)
    bw_in = m_to_in(bw)
    h_in = m_to_in(h)
    eg_in = m_to_in(h / 2.0 + ts / 2.0)
    kg = _concrete_t_girder_longitudinal_stiffness_in4(bw_in, h_in, eg_in)
    stiff = _distribution_stiffness_term(kg, span_ft, ts_in)
    g_m1 = _interior_concrete_t_girder_moment_one_lane_g(spacing_ft, span_ft, ts_in, kg)
    g_m2 = (
        0.075
        + (spacing_ft / 9.5) ** 0.6
        * (spacing_ft / span_ft) ** 0.2
        * stiff
    )
    g_v1 = 0.36 + spacing_ft / 25.0
    g_v2 = 0.20 + spacing_ft / 12.0 - (spacing_ft / 35.0) ** 2.0
    g_m_api = mtc_interior_concrete_t_girder_live_load_distribution_factor(
        L, S, ts, h, bw, n_g
    )
    g_v_api = mtc_interior_concrete_t_girder_live_load_shear_distribution_factor(L, S, ts, n_g)

    formula = (
        "gM = max(gM,1; gM,≥2)  ;  gV = max(gV,1; gV,≥2)  ;  "
        "Kg = I + A·eg²  ;  (Kg/(12·L·ts³))^0.1"
    )
    legend = (
        "S, L en ft; ts en in; Kg en in⁴; "
        "gM,1 = 0.06+(S/14)^0.4·(S/L)^0.3·Kg-term; "
        "gM,≥2 = 0.075+(S/9.5)^0.6·(S/L)^0.2·Kg-term; "
        "gV,1 = 0.36+S/25; gV,≥2 = 0.20+S/12−(S/35)²."
    )
    substitution = (
        f"L = {L:.3f} m = {span_ft:.3f} ft\n"
        f"S = {S:.3f} m = {spacing_ft:.3f} ft\n"
        f"ts = {ts:.3f} m = {ts_in:.3f} in\n"
        f"bw = {bw:.3f} m\n"
        f"h = {h:.3f} m\n"
        f"eg = h/2 + ts/2 = {eg_in:.3f} in\n"
        f"Kg = {kg:,.1f} in⁴\n"
        f"(Kg/(12·L·ts³))^0.1 = {stiff:.6f}\n"
        f"gM,1 = {g_m1:.5f}\n"
        f"gM,≥2 = {g_m2:.5f}\n"
        f"gM = max({g_m1:.5f}; {g_m2:.5f}) = {g_m_api:.5f}\n"
        f"gV,1 = {g_v1:.5f}\n"
        f"gV,≥2 = {g_v2:.5f}\n"
        f"gV = max({g_v1:.5f}; {g_v2:.5f}) = {g_v_api:.5f}"
    )
    result = (
        f"Se adoptan gM = {g_m_api:.5f} y gV = {g_v_api:.5f} "
        f"(máximo entre 1 carril y 2 o más carriles)."
    )
    comment = (
        "Los factores se aplican solo a LL+IM; DC y DW se asignan por ancho tributario sin g."
    )
    return formula, legend, substitution, result, comment


def exterior_g_factor_trace(geometry, vehicle) -> tuple[str, str, str, str, str]:
    """Build gM / gV detail for an exterior girder."""
    de = geometry.exterior_web_to_traffic_barrier_m
    g_m = float(geometry.live_load_distribution_factor_g)
    g_v = float(geometry.live_load_shear_distribution_factor_g)
    interior_g = mtc_interior_concrete_t_girder_live_load_distribution_factor(
        geometry.span_length_m,
        geometry.girder_spacing_m,
        geometry.slab_thickness_m,
        geometry.girder_total_height_m,
        geometry.web_width_m,
        geometry.girder_count,
    )
    de_ft = _limited_exterior_de_ft(de)
    multi = (0.77 + de_ft / 9.1) * interior_g
    lever = mtc_exterior_lever_rule_distribution_factor(
        girder_spacing_m=geometry.girder_spacing_m,
        exterior_web_to_traffic_barrier_m=de,
        wheel_transverse_spacing_m=vehicle.wheel_transverse_spacing_m,
    )
    rigid = mtc_exterior_rigid_cross_section_distribution_factor(
        girder_spacing_m=geometry.girder_spacing_m,
        girder_count=geometry.girder_count,
        exterior_web_to_traffic_barrier_m=de,
        wheel_transverse_spacing_m=vehicle.wheel_transverse_spacing_m,
        design_lane_width_m=vehicle.design_lane_width_m,
    )
    formula = (
        "gM,ext = max(regla de palanca; (0.77+de/9.1)·gM,int; sección rígida)  ;  "
        "gV,ext análogo con gV,int"
    )
    legend = (
        "de: distancia del alma exterior a la cara de tráfico de la barrera (ft, acotada); "
        "gM,int: factor de viga interior; la regla de palanca y la sección rígida son alternativas AASHTO/MTC."
    )
    substitution = (
        f"de = {de:.3f} m = {de_ft:.3f} ft (acotado)\n"
        f"gM,int = {interior_g:.5f}\n"
        f"(0.77 + de/9.1)·gM,int = {multi:.5f}\n"
        f"regla de palanca = {lever:.5f}\n"
        f"sección rígida = {rigid:.5f}\n"
        f"gM = max(...) = {g_m:.5f}\n"
        f"gV = {g_v:.5f}"
    )
    result = f"Se adoptan gM = {g_m:.5f} y gV = {g_v:.5f} para la viga exterior."
    comment = "El valor gobernante es el máximo entre las alternativas normativas aplicables."
    return formula, legend, substitution, result, comment


def ll_im_with_g_trace(
    *,
    analysis,
    strength_moment,
    critical_shear,
    g_m: float,
    g_v: float,
) -> tuple[str, str, str, str, str]:
    """Show MHL93/VHL93 before g and the factored LL+IM used in Strength I."""
    m_ll = strength_moment.ll_im_moment_tn_m
    v_ll = critical_shear.ll_im_shear_tn
    m_before = m_ll / g_m if abs(g_m) > 1e-12 else 0.0
    v_before = v_ll / g_v if abs(g_v) > 1e-12 else 0.0
    x_m = strength_moment.position_m
    x_v = critical_shear.position_m
    formula = (
        "Mᵥᵢgₐ = gM·MHL93  ;  Vᵥᵢgₐ = gV·VHL93  ;  "
        "Mu incluye γLL·Mᵥᵢgₐ  ;  Vu incluye γLL·Vᵥᵢgₐ"
    )
    legend = (
        "MHL93, VHL93: efecto de un carril HL-93 (+IM y carril) antes de distribuir; "
        "Mᵥᵢgₐ, Vᵥᵢgₐ: efectos ya asignados a la viga (envolvente LL+IM); "
        "g no se vuelve a aplicar en la combinación."
    )
    substitution = (
        f"x,momento = {x_m:.3f} m\n"
        f"MHL93 ≈ {m_before:.3f} Tn·m\n"
        f"M(LL+IM) = {g_m:.5f}·{m_before:.3f} = {m_ll:.3f} Tn·m\n"
        f"x,cortante = {x_v:.3f} m\n"
        f"VHL93 ≈ {v_before:.3f} Tn\n"
        f"V(LL+IM) = {g_v:.5f}·{v_before:.3f} = {v_ll:.3f} Tn\n"
        f"contribución LL en Mu = {strength_moment.ll_im_factor:.2f}·({m_ll:.3f})\n"
        f"contribución LL en Vu = {critical_shear.ll_im_factor:.2f}·({v_ll:.3f})"
    )
    result = (
        "Los términos LL+IM de la combinación ya incorporan gM y gV; "
        "DC y DW no se multiplican por g."
    )
    comment = (
        "g se aplica posición a posición al barrer el camión/tándem; "
        "la envolvente conserva el máximo ya distribuido."
    )
    return formula, legend, substitution, result, comment


def skin_steel_trace(skin_design, option_text: str, compliance: str) -> tuple[str, str, str, str, str]:
    dl = skin_design.effective_depth_cm
    ask = skin_design.required_area_cm2_m_per_face
    if dl > 90.0:
        sub_req = (
            f"dl = {dl:.2f} cm > 90 cm\n"
            f"Ask,base = 0.1·({dl:.2f} − 76.2) = "
            f"{skin_design.uncapped_required_area_cm2_m_per_face:.3f} cm²/m por cara\n"
            f"hdistrib = dl/2 = {skin_design.distribution_height_m:.3f} m\n"
            f"Ask,total = min(Ask,base·hdistrib, As/4) = "
            f"min({skin_design.uncapped_required_area_cm2_m_per_face:.3f}·"
            f"{skin_design.distribution_height_m:.3f}, "
            f"{skin_design.maximum_total_area_cm2_per_face:.3f}) = "
            f"{skin_design.required_total_area_cm2_per_face:.3f} cm² por cara\n"
            f"Ask,req = Ask,total/hdistrib = {ask:.3f} cm²/m por cara"
        )
    else:
        sub_req = (
            f"dl = {dl:.2f} cm ≤ 90 cm\n"
            f"Ask,req = 0 cm²/m\n"
            f"valor reportado Ask,req = {ask:.3f} cm²/m"
        )
    formula = (
        "Ask,base = 0.1·(dl − 76.2) cm²/m si dl > 90 cm  ;  "
        "hdistrib = dl/200 m  ;  "
        "Ask,total = min(Ask,base·hdistrib, (As+Aps)/4)  ;  "
        "Ask,req = Ask,total/hdistrib  ;  smax = min(dl/6, 300 mm)"
    )
    legend = (
        "Ask: acero longitudinal por cara del alma (cm²/m de altura); "
        "dl: distancia a la barra extrema de tracción; As y Aps: acero de tracción "
        "no pretensado y pretensado; smax: separación vertical máxima."
    )
    substitution = (
        f"{sub_req}\n"
        f"smax = {skin_design.maximum_spacing_m:.3f} m\n"
        f"opción adoptada: {option_text}"
    )
    result = "El acero de piel adoptado satisface simultáneamente cuantía y separación."
    return formula, legend, substitution, result, compliance


def service_stress_trace(service, concrete, steel) -> tuple[str, str, str, str, str]:
    n = service.section.modular_ratio
    kd = service.section.neutral_axis_depth_cm
    icr = service.section.inertia_cm4
    m = service.service_moment_tn_m
    m_kg = m * 100000.0
    fs = service.steel_tension_kg_cm2
    ys = fs * icr / (n * m_kg) if n * m_kg > 0 else 0.0
    d = kd + ys
    fc = service.concrete_compression_kg_cm2
    fc_lim = service.concrete_compression_limit_kg_cm2
    fs_lim = service.steel_tension_limit_kg_cm2
    es = steel.elastic_modulus_kg_cm2
    ec = concrete.elastic_modulus_kg_cm2
    formula = (
        "n = round(Es/Ec)  ;  fc = Mserv·kd/Icr  ;  fs = n·Mserv·(d − kd)/Icr  ;  "
        "fc ≤ 0.45·f'c  ;  fs ≤ 0.60·fy"
    )
    legend = (
        "Mserv: momento SERVICIO I; Icr: inercia fisurada transformada; "
        "kd: eje neutro desde la fibra superior; d: peralte al acero."
    )
    section_state = "fisurada" if service.section.is_cracked else "no fisurada"
    substitution = (
        f"Es = {es:,.0f} kg/cm²\n"
        f"Ec = {ec:,.0f} kg/cm²\n"
        f"n = round({es:,.0f}/{ec:,.0f}) = {n}\n"
        f"Mserv = {m:.3f} Tn·m\n"
        f"x = {service.position_m:.3f} m\n"
        f"sección = {section_state}\n"
        f"kd = {kd:.2f} cm\n"
        f"d ≈ {d:.2f} cm\n"
        f"ys = d − kd = {ys:.2f} cm\n"
        f"Icr = {icr:,.0f} cm⁴\n"
        f"fc = ({m:.3f}·100000)·{kd:.2f}/{icr:,.0f} = {fc:.2f} kg/cm²\n"
        f"fs = {n}·({m:.3f}·100000)·{ys:.2f}/{icr:,.0f} = {fs:.1f} kg/cm²\n"
        f"límite concreto = 0.45·{concrete.compressive_strength_kg_cm2:.1f} = {fc_lim:.2f} kg/cm²\n"
        f"límite acero = 0.60·{steel.yield_strength_kg_cm2:.0f} = {fs_lim:.1f} kg/cm²"
    )
    result = (
        f"fc,serv = {fc:.2f} ≤ {fc_lim:.2f}: {service.concrete_status}; "
        f"fs,serv = {fs:.1f} ≤ {fs_lim:.1f}: {service.steel_status}."
    )
    comment = (
        "Las tensiones elásticas se mantienen dentro de los límites de Servicio I."
        if service.concrete_status == "CUMPLE" and service.steel_status == "CUMPLE"
        else "Alguna tensión de servicio supera el límite reglamentario."
    )
    return formula, legend, substitution, result, comment


def fatigue_trace(fatigue, steel) -> tuple[str, str, str, str, str]:
    gamma = FATIGUE_I_LOAD_FACTOR
    mf = fatigue.fatigue_moment_tn_m
    fmin = fatigue.minimum_stress_kg_cm2
    delta = fatigue.stress_range_kg_cm2
    delta_f = fatigue.factored_stress_range_kg_cm2
    allow = fatigue.allowable_stress_range_kg_cm2
    fy = steel.yield_strength_kg_cm2
    from bridge_design.units.converters import kg_cm2_to_ksi

    fy_ksi = max(60.0, min(100.0, kg_cm2_to_ksi(fy)))
    fmin_ksi = kg_cm2_to_ksi(fmin)
    allow_ksi = 24.0 - 20.0 * fmin_ksi / fy_ksi
    fmax = fmin + delta
    formula = (
        "Δf = fmax − fmin = n·Mf·ys/Icr  ;  ΔfF = γF·Δf  ;  "
        "(ΔF)TH = 24 − 20·fmin/fy  (ksi)  ;  ΔfF ≤ ΔfTH"
    )
    legend = (
        "Mf: momento del camión de fatiga (IM = 15 %, sin carga de carril, g de fatiga); "
        "fmin: tensión por DC+DW en la misma estación; "
        f"γF = {gamma:.2f} (Fatiga I); ΔfTH: rango admisible para barras rectas."
    )
    substitution = (
        f"Mf = {mf:.3f} Tn·m\n"
        f"x = {fatigue.fatigue_position_m:.3f} m\n"
        f"Mperm = {fatigue.permanent_moment_tn_m:.3f} Tn·m\n"
        f"fmin = {fmin:.1f} kg/cm²\n"
        f"fmax ≈ {fmax:.1f} kg/cm²\n"
        f"Δf = {delta:.1f} kg/cm²\n"
        f"ΔfF = {gamma:.2f}·{delta:.1f} = {delta_f:.1f} kg/cm²\n"
        f"(ΔF)TH = 24 − 20·({fmin_ksi:.3f}/{fy_ksi:.1f}) = {allow_ksi:.3f} ksi = {allow:.1f} kg/cm²"
    )
    result = f"ΔfF = {delta_f:.1f} kg/cm² ≤ ΔfTH = {allow:.1f} kg/cm²: {fatigue.status}."
    comment = (
        "El rango de tensión de las barras rectas adoptadas no gobierna el dimensionamiento."
        if fatigue.status == "CUMPLE"
        else "El rango de fatiga supera el límite admisible."
    )
    return formula, legend, substitution, result, comment


def barrier_mw_mc_trace(flex, concrete, steel) -> tuple[str, str, str, str, str]:
    fy = steel.yield_strength_kg_cm2
    fc = concrete.compressive_strength_kg_cm2
    lines: list[str] = ["Componentes Mw:"]
    for comp in flex.mw_components:
        a = comp.compression_block_depth_cm
        lines.extend(
            (
                f"Mw-{comp.label}: As = {comp.steel_area_cm2:.3f} cm²",
                f"b = {comp.concrete_width_cm:.2f} cm",
                f"d = {comp.effective_depth_cm:.2f} cm",
                f"a = {comp.steel_area_cm2:.3f}·{fy:.0f}/(0.85·{fc:.1f}·{comp.concrete_width_cm:.2f}) = {a:.3f} cm",
                f"Mn = {comp.steel_area_cm2:.3f}·{fy:.0f}·({comp.effective_depth_cm:.2f} − {a:.3f}/2)/100000 "
                f"= {comp.nominal_moment_tn_m:.3f} Tn·m",
            )
        )
    lines.append(f"Mw = Σ = {flex.mw_tn_m:.3f} Tn·m")
    lines.append("Componentes Mc:")
    for comp in flex.mc_components:
        a = comp.compression_block_depth_cm
        lines.extend(
            (
                f"Mc-{comp.label}: As = {comp.steel_area_cm2:.3f} cm²/m",
                f"d = {comp.effective_depth_cm:.2f} cm",
                f"a = {a:.3f} cm",
                f"Mn = {comp.nominal_moment_tn_m:.3f} Tn·m/m",
            )
        )
    lines.append(f"Mc (promedio ponderado) = {flex.mc_tn_m:.3f} Tn·m/m")
    formula = "a = As·fy/(0.85·f'c·b)  ;  Mn = As·fy·(d − a/2)  ;  Mw = Σ Mn  ;  Mc = Σ(hi·Mni)/Σ hi"
    legend = (
        "Mw: resistencia flexional horizontal del paño; Mc: resistencia vertical por metro "
        "(promedio ponderado por altura de segmentos)."
    )
    substitution = "\n".join(lines)
    result = f"Se adoptan Mw = {flex.mw_tn_m:.3f} Tn·m y Mc = {flex.mc_tn_m:.3f} Tn·m/m en el mecanismo."
    comment = "La subdivisión reproduce la geometría y el refuerzo de la barrera New Jersey adoptada."
    return formula, legend, substitution, result, comment


def barrier_interface_trace(inputs, materials, shear) -> tuple[str, str, str, str, str]:
    sf = inputs.shear_friction
    geom = inputs.geometry
    c = sf.cohesion_kg_cm2
    mu = sf.friction_factor
    k1 = sf.concrete_limit_factor
    k2 = sf.absolute_limit_kg_cm2
    acv = shear.contact_area_cm2_m
    avf = shear.provided_avf_cm2_m
    pc = shear.permanent_compression_kg_m
    fy = materials.steel.yield_strength_kg_cm2
    fc = materials.concrete.compressive_strength_kg_cm2
    gamma = materials.concrete.specific_weight_tn_m3
    lim1 = k1 * fc * acv
    lim2 = k2 * acv
    formula = (
        "Acv = bbase·100·100  ;  Pc = Ag·γc·1000  ;  "
        "Vn,bruto = [c·Acv + μ(Avf·fy + Pc)]/1000  ;  "
        "Vn = min(Vn,bruto; K1·f'c·Acv/1000; K2·Acv/1000)  ;  "
        "Vact = Rw/(Lc + 2H)"
    )
    legend = (
        "c: cohesión de la interfaz (kg/cm²); μ: coeficiente de fricción; "
        "Acv: área de contacto por metro (cm²/m); Avf: acero de dowels (cm²/m); "
        "Pc: compresión permanente (kg/m); K1, K2: límites de corte-fricción; "
        "Rw, Lc, H: del mecanismo de líneas de fluencia."
    )
    substitution = (
        f"c = {c:.2f} kg/cm²\n"
        f"μ = {mu:.2f}\n"
        f"K1 = {k1:.2f}\n"
        f"K2 = {k2:.2f} kg/cm²\n"
        f"Acv = {geom.base_width_m:.3f}·100·100 = {acv:.1f} cm²/m\n"
        f"Avf = {avf:.3f} cm²/m\n"
        f"Pc = {geom.cross_section_area_m2:.6f}·{gamma:.3f}·1000 = {pc:.1f} kg/m\n"
        f"Vn,bruto = [{c:.2f}·{acv:.1f} + {mu:.2f}·({avf:.3f}·{fy:.0f} + {pc:.1f})]/1000 "
        f"= {shear.nominal_shear_raw_tn_m:.3f} Tn/m\n"
        f"Vn,límite = min({lim1/1000:.3f}; {lim2/1000:.3f}) = {shear.nominal_shear_limit_tn_m:.3f} Tn/m\n"
        f"Vn = {shear.nominal_shear_tn_m:.3f} Tn/m\n"
        f"Vact = {shear.acting_shear_tn_m:.3f} Tn/m"
    )
    result = f"Vact = {shear.acting_shear_tn_m:.3f} ≤ Vn = {shear.nominal_shear_tn_m:.3f}: {shear.status}."
    comment = (
        "La interfaz puede transferir el esfuerzo longitudinal asociado al mecanismo de impacto."
        if shear.status == "OK" or shear.status == "CUMPLE"
        else "La interfaz no alcanza la demanda de transferencia del impacto."
    )
    return formula, legend, substitution, result, comment


def cantilever_collision_trace(collision, control, geom_height: float | None = None) -> tuple[str, str, str, str, str]:
    ft = collision.transverse_force_tn
    ltr = collision.transfer_length_m
    h = collision.barrier_height_m
    lc = ltr - 2.0 * h
    vct = collision.interface_shear_tn_m
    mcol = collision.collision_moment_tn_m
    mperm = collision.permanent_moment_tn_m
    mu_ee = collision.design_moment_tn_m
    mu_ri = control.design_moment_tn_m
    formula = (
        "Ltr = Lc + 2H  ;  Vct = Ft/Ltr  ;  Mcol = Vct·H  ;  "
        "Mperm = |γDC·MDC + γDW·MDW|  ;  Mu,EE-II = Mcol + Mperm"
    )
    legend = (
        "Ft: fuerza transversal TL (YAML/impacto); Lc: longitud crítica del yield-line de la barrera; "
        "H: altura de la barrera; Mperm: permanentes factorizados de Resistencia I en el voladizo "
        "(sin PL ni LL)."
    )
    substitution = (
        f"Ft = {ft:.3f} Tn\n"
        f"H = {h:.3f} m\n"
        f"Lc = Ltr − 2H = {ltr:.3f} − 2·{h:.3f} = {lc:.3f} m\n"
        f"Ltr = {lc:.3f} + 2·{h:.3f} = {ltr:.3f} m\n"
        f"Vct = {ft:.3f}/{ltr:.3f} = {vct:.3f} Tn/m\n"
        f"Mcol = {vct:.3f}·{h:.3f} = {mcol:.3f} Tn·m/m\n"
        f"Mperm = {mperm:.3f} Tn·m/m\n"
        f"Mu,EE-II = {mcol:.3f} + {mperm:.3f} = {mu_ee:.3f} Tn·m/m\n"
        f"Mu,RI = {mu_ri:.3f} Tn·m/m"
    )
    design = max(mu_ri, mu_ee)
    result = f"El diseño flexional adopta Mu = max({mu_ri:.3f}; {mu_ee:.3f}) = {design:.3f} Tn·m/m."
    comment = (
        "El Evento Extremo II gobierna el acero superior; por ello el momento de Resistencia I "
        "no se utiliza para dimensionar la armadura final."
        if mu_ee >= mu_ri - 1e-9
        else "Resistencia I gobierna frente al Evento Extremo II en este voladizo."
    )
    return formula, legend, substitution, result, comment


def cantilever_arm_trace(effects, overhang_m: float) -> tuple[str, str, str, str, str]:
    formula = "brazo = a − x  ;  Mraíz = −P·brazo  ;  xG = xinicio + L/2 (cargas uniformes)"
    legend = (
        "a: volado hasta el eje de la viga exterior (raíz); "
        "x: posición desde el borde libre; "
        "para cargas repartidas, x = centroide del tramo que intersecta el volado."
    )
    lines = [f"a = {overhang_m:.3f} m (eje de viga exterior / raíz)"]
    for effect in effects:
        lines.extend(
            (
                f"{effect.label}:",
                f"P = {effect.load_tn:.3f} Tn",
                f"x = {effect.centroid_from_edge_m:.3f} m",
                f"brazo = {overhang_m:.3f} − {effect.centroid_from_edge_m:.3f} = {effect.arm_to_root_m:.3f} m",
                f"M = −{effect.load_tn:.3f}·{effect.arm_to_root_m:.3f} = {effect.root_moment_tn_m:.3f} Tn·m",
            )
        )
    substitution = "\n".join(lines)
    result = "Los momentos en raíz se suman por grupo (DC, DW, PL, LL+IM) antes de factorizar."
    comment = (
        "Solo las cargas con x ≤ a generan momento de voladizo; "
        "barrera o cuchilla interiores al eje exterior no aportan brazo."
    )
    return formula, legend, substitution, result, comment


def cantilever_shear_trace(shear) -> tuple[str, str, str, str, str]:
    formula = (
        "Vu = 1.25·VDC + 1.50·VDW + 1.75·VPL + 1.75·VLL+IM  ;  "
        "Vc = 0.083·β·√f'c·bv·dv  ;  Vu ≤ φVc"
    )
    legend = (
        "V*: resultantes de carga en la raíz (iguales a las P del voladizo); "
        "β: parámetro seccional; bv: ancho de franja; dv: peralte efectivo de corte."
    )
    substitution = (
        f"VDC = {shear.dc_shear_tn:.3f} Tn\n"
        f"VDW = {shear.dw_shear_tn:.3f} Tn\n"
        f"VPL = {shear.pl_shear_tn:.3f} Tn\n"
        f"VLL+IM = {shear.ll_im_shear_tn:.3f} Tn\n"
        f"Vu = {shear.dc_factor:.2f}·{shear.dc_shear_tn:.3f} + {shear.dw_factor:.2f}·{shear.dw_shear_tn:.3f} + "
        f"{shear.pl_factor:.2f}·{shear.pl_shear_tn:.3f} + {shear.ll_im_factor:.2f}·{shear.ll_im_shear_tn:.3f} "
        f"= {shear.combined_shear_tn:.3f} Tn\n"
        f"dv = {shear.effective_shear_depth_cm:.2f} cm\n"
        f"β = {shear.beta:.3f}\n"
        f"Vc = {shear.vc_tn:.3f} Tn\n"
        f"φ = {shear.phi:.3f}\n"
        f"φVc = {shear.phi_vc_tn:.3f} Tn"
    )
    result = f"Estado: {shear.status}."
    comment = (
        "No se requiere refuerzo transversal independiente en la franja de voladizo."
        if shear.status == "CUMPLE"
        else "El cortante de la raíz supera φVc."
    )
    return formula, legend, substitution, result, comment


def cantilever_development_trace(dev, overhang_m: float, cover_cm: float = 5.0) -> tuple[str, str, str, str, str]:
    formula = (
        "ld = max[ldb·λ·(As,req/As,prov); 30.48 cm]  ;  "
        "Lext = a − c  ;  Lint = ld  ;  Ladic = Lext + Lint"
    )
    legend = (
        "ld: longitud de desarrollo desde la raíz hacia el interior del tablero; "
        "Lext: proyección hacia el borde libre; "
        "Lint: anclaje interior mínimo (= ld); "
        "ldb: longitud básica; As,req/As,prov: reducción por exceso de acero."
    )
    substitution = (
        f"barra = {dev.bar_label}\n"
        f"As,prov = {dev.provided_area_cm2_m:.3f} cm²/m\n"
        f"As,req = {dev.required_area_cm2_m:.3f} cm²/m\n"
        f"factor exceso = {dev.excess_reinforcement_factor:.3f}\n"
        f"ldb = {dev.basic_development_length_cm:.2f} cm\n"
        f"ld = {dev.required_development_length_cm:.2f} cm\n"
        f"Lext = {overhang_m:.3f} − {cover_cm/100:.3f} = {dev.exterior_projection_length_m:.3f} m\n"
        f"Lint = ld = {dev.interior_anchor_length_m:.3f} m"
    )
    result = (
        f"Longitud adicional total = {dev.exterior_projection_length_m:.3f} + "
        f"{dev.interior_anchor_length_m:.3f} = {dev.total_additional_bar_length_m:.3f} m; "
        f"estado: {dev.status}."
    )
    comment = (
        "La prolongación interior (ld desde la raíz) y la extensión exterior desarrollan el acero superior adoptado."
    )
    return formula, legend, substitution, result, comment
