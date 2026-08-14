"""ASCII report for elastomeric bearing Method A design (trazable paso a paso)."""

from __future__ import annotations

from math import sqrt

from bridge_design.cli.ascii_tables import audit_block_title, audit_subtitle, boxed_table
from bridge_design.domain.elastomeric_bearing import (
    DELTA_F_TH_CATEGORY_A_KG_CM2,
    HS_MIN_CM,
    JOINT_DEFLECTION_LIMIT_CM,
    METHOD_A_SI2_OVER_N_LIMIT,
    SIGMA_S_MAX_KG_CM2,
    ElastomericBearingDesignResult,
    compressive_strain,
    seismic_connection_force_factor,
)

_W = 112


def format_elastomeric_bearing_result(result: ElastomericBearingDesignResult) -> str:
    """Return an ASCII audit report for Method A elastomeric bearing design."""
    lines: list[str] = [
        "",
        *audit_block_title("A", "DISENO DE APOYOS ELASTOMERICOS - METODO A", _W),
        "Referencias: AASHTO LRFD 14.7.6 / 14.7.5.3.5 / 14.8.3 / 14.6.3.1 / 3.10.9 / 5.7.5;",
        "             Manual MTC 2018 2.10.4 / 2.4.3.11.8 / 2.8.1.4 / Tabla 2.4.3.9.2-1.",
        f"Designacion: {result.designation}",
        f"Estado global: {'CUMPLE' if result.overall_ok else 'NO CUMPLE'}",
    ]
    lines.extend(_format_inputs(result))
    lines.extend(_format_procedure(result))
    lines.extend(_format_checks_summary(result))
    lines.extend(_format_final_designation(result))
    return "\n".join(lines)


def _format_inputs(result: ElastomericBearingDesignResult) -> list[str]:
    inp = result.inputs
    mov = inp.movements
    temp = mov.temperature
    seis = inp.seismic
    grade = result.grade
    delta_t = (
        temp.contraction_delta_t_c if mov.use_install_to_min else temp.design_range_c
    )
    lines = [
        "",
        *audit_subtitle("A.1", "DATOS DE ENTRADA", _W),
    ]
    lines.extend(
        boxed_table(
            ("Parametro", "Valor", "Unidad", "Nota / Ref."),
            (
                ("PDC carga muerta", f"{inp.loads.dead_load_dc_tn:.3f}", "Tn", "Servicio"),
                ("PDW superficie rodadura", f"{inp.loads.wearing_surface_dw_tn:.3f}", "Tn", "Servicio"),
                ("PLL carga viva (sin IM)", f"{inp.loads.live_load_ll_tn:.3f}", "Tn", "Servicio"),
                ("PT = PDC+PDW+PLL", f"{inp.loads.total_service_tn:.3f}", "Tn", "Estado limite Servicio"),
                ("Luz del tramo L", f"{mov.span_length_m:.3f}", "m", "Longitud de viga"),
                ("Zona climatica (rango)", f"{temp.t_sup_c:.1f} / {temp.t_inf_c:.1f}", "C", "MTC Tabla 2.4.3.9.2-1"),
                ("Temperatura instalacion", f"{temp.t_install_c:.1f}", "C", "Entrada"),
                ("Delta T usada", f"{delta_t:.1f}", "C", "t_inst - t_inf" if mov.use_install_to_min else "t_sup - t_inf"),
                ("alpha concreto", f"{mov.alpha_per_c:.2e}", "1/C", "AASHTO 5.4.2.2"),
                ("Retraccion", f"{mov.shrinkage_cm:.3f}", "cm", "Entrada"),
                ("Acort. pretensado", f"{mov.prestress_shortening_cm:.3f}", "cm", "Entrada"),
                ("Otros mov. permanentes", f"{mov.other_permanent_cm:.3f}", "cm", "Entrada"),
                ("gamma_TU", f"{mov.gamma_tu:.2f}", "-", "Tabla 3.4.1-1"),
                ("Dureza Shore A", f"{inp.hardness}", "-", "Tabla 14.7.6.2-1"),
                ("G diseno (min)", f"{grade.g_min_kg_cm2:.2f}", "kg/cm2", "Art. 14.7.6.2"),
                ("G max", f"{grade.g_max_kg_cm2:.2f}", "kg/cm2", "Hu servicio / anclaje"),
                ("Cd creep", f"{grade.creep_ratio:.2f}", "-", "Tabla 14.7.6.2-1"),
                ("k forma", f"{grade.shape_factor_k:.2f}", "-", "eps = sigma/[3G(1+2kS^2)]"),
                ("Ancho viga / W", f"{inp.girder_width_cm:.2f}", "cm", "Planta transversal"),
                ("Fy zunchos", f"{inp.steel_fy_kg_cm2:.0f}", "kg/cm2", "Acero A36 tipico"),
                ("As sitio", f"{seis.site_acceleration_as:.3f}", "-", "MTC 2.4.3.11.8"),
                ("Zona sismica", f"{seis.seismic_zone}", "-", "1 a 4"),
                ("Puente 1 tramo", "si" if seis.is_single_span else "no", "-", "Factor conexion"),
                ("Tipo de apoyo", seis.bearing_role, "-", "expansion / fixed"),
                ("Restringido long.", "si" if seis.longitudinal_restrained else "no", "-", "F_EQ long."),
                ("Restringido transv.", "si" if seis.transverse_restrained else "no", "-", "F_EQ transv."),
                ("mu friccion", f"{seis.friction_coefficient:.3f}", "-", "C14.8.3.1"),
            ),
            aligns=("left", "right", "left", "left"),
            title="Entradas del modelo",
            max_width=_W,
        )
    )
    return lines


def _format_procedure(result: ElastomericBearingDesignResult) -> list[str]:
    lines = [
        "",
        *audit_subtitle("A.2", "PROCEDIMIENTO PASO A PASO DEL CALCULO", _W),
    ]
    lines.extend(_step_area(result))
    lines.extend(_step_shear_displacement(result))
    lines.extend(_step_required_thickness(result))
    lines.extend(_step_shape_and_layers(result))
    lines.extend(_step_steel_plates(result))
    lines.extend(_step_total_height(result))
    lines.extend(_step_compression_deflections(result))
    lines.extend(_step_horizontal_forces(result))
    lines.extend(_step_seismic(result))
    lines.extend(_step_concrete_bearing(result))
    return lines


def _step_table(title: str, rows: list[tuple[str, str, str, str]]) -> list[str]:
    return [
        "",
        *boxed_table(
            ("Paso", "Formula", "Sustitucion", "Resultado"),
            rows,
            aligns=("left", "left", "left", "right"),
            title=title,
            max_width=_W,
        ),
    ]


def _step_area(result: ElastomericBearingDesignResult) -> list[str]:
    loads = result.inputs.loads
    pt_kg = loads.total_service_kg
    w = result.width_cm
    l_req = result.required_area_cm2 / w if w > 0 else 0.0
    rows = [
        (
            "Cargas a kg",
            "P = P_Tn * 1000",
            (
                f"PDC={loads.dead_load_dc_tn:.3f}*1000; "
                f"PDW={loads.wearing_surface_dw_tn:.3f}*1000; "
                f"PLL={loads.live_load_ll_tn:.3f}*1000"
            ),
            (
                f"PDC={loads.dead_load_dc_kg:.0f} kg; "
                f"PDW={loads.wearing_surface_dw_tn * 1000.0:.0f} kg; "
                f"PLL={loads.live_load_ll_tn * 1000.0:.0f} kg"
            ),
        ),
        (
            "Carga total servicio",
            "PT = PDC + PDW + PLL",
            f"{loads.dead_load_dc_kg:.0f}+{loads.wearing_surface_dw_tn * 1000.0:.0f}+{loads.live_load_ll_tn * 1000.0:.0f}",
            f"{pt_kg:.0f} kg = {loads.total_service_tn:.3f} Tn",
        ),
        (
            "Area requerida",
            "A_req = PT / 87.9",
            f"{pt_kg:.0f} / {SIGMA_S_MAX_KG_CM2:.1f}",
            f"{result.required_area_cm2:.2f} cm2",
        ),
        (
            "Ancho adoptado W",
            "W = ancho viga (o adoptado)",
            f"{w:.2f}",
            f"{w:.2f} cm",
        ),
        (
            "Largo teorico",
            "L_teo = A_req / W",
            f"{result.required_area_cm2:.2f} / {w:.2f}",
            f"{l_req:.2f} cm",
        ),
        (
            "Largo adoptado L",
            "L >= L_teo (redondeo practico)",
            f"L={result.length_cm:.2f}; A=L*W={result.length_cm:.2f}*{w:.2f}",
            f"{result.length_cm:.2f} cm; A={result.area_cm2:.1f} cm2",
        ),
        (
            "Esfuerzo total sigma_s",
            "sigma_s = PT / A",
            f"{pt_kg:.0f} / {result.area_cm2:.1f}",
            f"{result.sigma_s_kg_cm2:.2f} kg/cm2",
        ),
        (
            "Esfuerzo permanente",
            "sigma_perm = (PDC+PDW) / A",
            f"{loads.permanent_kg:.0f} / {result.area_cm2:.1f}",
            f"{result.sigma_permanent_kg_cm2:.2f} kg/cm2",
        ),
        (
            "Esfuerzo LL",
            "sigma_LL = PLL / A",
            f"{loads.live_load_kg:.0f} / {result.area_cm2:.1f}",
            f"{result.sigma_live_kg_cm2:.2f} kg/cm2",
        ),
        (
            "Check sigma_s",
            "sigma_s <= 87.9",
            f"{result.sigma_s_kg_cm2:.2f} <= {SIGMA_S_MAX_KG_CM2:.1f}",
            _ok(result.sigma_s_kg_cm2 <= SIGMA_S_MAX_KG_CM2 + 1e-9),
        ),
    ]
    return _step_table("1. AREA EN PLANTA (Art. 14.7.6.3.2-8)", rows)


def _step_shear_displacement(result: ElastomericBearingDesignResult) -> list[str]:
    mov = result.inputs.movements
    temp = mov.temperature
    length_cm = mov.span_length_m * 100.0
    delta_t = (
        temp.contraction_delta_t_c if mov.use_install_to_min else temp.design_range_c
    )
    d_temp = mov.thermal_displacement_cm
    d_unfact = mov.unfactored_permanent_displacement_cm
    rows = [
        (
            "Delta T",
            "t_inst - t_inf" if mov.use_install_to_min else "t_sup - t_inf",
            (
                f"{temp.t_install_c:.1f} - ({temp.t_inf_c:.1f})"
                if mov.use_install_to_min
                else f"{temp.t_sup_c:.1f} - {temp.t_inf_c:.1f}"
            ),
            f"{delta_t:.1f} C",
        ),
        (
            "Movimiento termico",
            "Dtemp = alpha * L * DeltaT",
            f"{mov.alpha_per_c:.2e} * {length_cm:.1f} * {delta_t:.1f}",
            f"{d_temp:.3f} cm",
        ),
        (
            "Mov. permanentes",
            "Dperm = Dtemp + Dretrac + Dpret + Dotros",
            (
                f"{d_temp:.3f}+{mov.shrinkage_cm:.3f}+"
                f"{mov.prestress_shortening_cm:.3f}+{mov.other_permanent_cm:.3f}"
            ),
            f"{d_unfact:.3f} cm",
        ),
        (
            "Delta_s servicio",
            "Ds = gamma_TU * Dperm",
            f"{mov.gamma_tu:.2f} * {d_unfact:.3f}",
            f"{result.delta_s_cm:.3f} cm",
        ),
    ]
    return _step_table("2. DESPLAZAMIENTO POR CORTE Ds (Art. 14.7.6.3.4)", rows)


def _step_required_thickness(result: ElastomericBearingDesignResult) -> list[str]:
    rows = [
        (
            "Espesor elastomero req.",
            "hrt_req = 2 * Ds",
            f"2 * {result.delta_s_cm:.3f}",
            f"{result.required_hrt_cm:.3f} cm",
        ),
        (
            "Espesor elastomero adopt.",
            "hrt = n*hri + 2*hre",
            (
                f"{result.interior_layers}*{result.interior_layer_cm:.2f} + "
                f"2*{result.exterior_layer_cm:.2f}"
            ),
            f"{result.total_elastomer_cm:.3f} cm",
        ),
        (
            "Check corte",
            "hrt >= 2*Ds",
            f"{result.total_elastomer_cm:.3f} >= {result.required_hrt_cm:.3f}",
            _ok(result.total_elastomer_cm + 1e-9 >= result.required_hrt_cm),
        ),
    ]
    return _step_table("3. ESPESOR TOTAL DE ELASTOMERO (Art. 14.7.6.3.4-1)", rows)


def _step_shape_and_layers(result: ElastomericBearingDesignResult) -> list[str]:
    g = result.design_g_kg_cm2
    si_min = result.sigma_s_kg_cm2 / (1.25 * g) if g > 0 else 0.0
    l = result.length_cm
    w = result.width_cm
    hri = result.interior_layer_cm
    hre = result.exterior_layer_cm
    hri_max = (l * w) / (2.0 * si_min * (l + w)) if si_min > 0 else 0.0
    n_raw = (result.required_hrt_cm - 2.0 * hre) / hri if hri > 0 else 0.0
    si2_n = (result.shape_factor_interior**2) / result.n_for_shape_limit
    limit_1_25 = 1.25 * g * result.shape_factor_interior
    rows = [
        (
            "G diseno",
            "G = Gmin (dureza)",
            f"Shore {result.inputs.hardness}",
            f"{g:.2f} kg/cm2",
        ),
        (
            "Si minimo",
            "Si_min = sigma_s / (1.25 G)",
            f"{result.sigma_s_kg_cm2:.2f} / (1.25*{g:.2f})",
            f"{si_min:.3f}",
        ),
        (
            "hri maximo teorico",
            "hri <= L W / [2 Si_min (L+W)]",
            f"{l:.2f}*{w:.2f} / [2*{si_min:.3f}*({l:.2f}+{w:.2f})]",
            f"{hri_max:.3f} cm",
        ),
        (
            "hri adoptado",
            "catalogo comercial <= hri_max",
            f"hri={hri:.2f}",
            f"{hri:.2f} cm = {hri * 10.0:.0f} mm",
        ),
        (
            "Si capa interior",
            "Si = L W / [2 hri (L+W)]",
            f"{l:.2f}*{w:.2f} / [2*{hri:.2f}*({l:.2f}+{w:.2f})]",
            f"{result.shape_factor_interior:.3f}",
        ),
        (
            "Check Si",
            "Si >= Si_min",
            f"{result.shape_factor_interior:.3f} >= {si_min:.3f}",
            _ok(result.shape_factor_interior + 1e-9 >= si_min),
        ),
        (
            "Check 1.25 G Si",
            "sigma_s <= 1.25 G Si",
            f"{result.sigma_s_kg_cm2:.2f} <= {limit_1_25:.2f}",
            _ok(result.sigma_s_kg_cm2 <= limit_1_25 + 1e-9),
        ),
        (
            "hre limite",
            "hre <= 0.70 hri",
            f"0.70*{hri:.2f}",
            f"{0.70 * hri:.3f} cm",
        ),
        (
            "hre adoptado",
            "catalogo comercial",
            f"hre={hre:.2f}",
            f"{hre:.2f} cm = {hre * 10.0:.0f} mm",
        ),
        (
            "Se capa exterior",
            "Se = L W / [2 hre (L+W)]",
            f"{l:.2f}*{w:.2f} / [2*{hre:.2f}*({l:.2f}+{w:.2f})]",
            f"{result.shape_factor_exterior:.3f}",
        ),
        (
            "Check hre",
            "hre <= 0.70 hri",
            f"{hre:.2f} <= {0.70 * hri:.3f}",
            _ok(hre <= 0.70 * hri + 1e-9),
        ),
        (
            "n teorico",
            "n = (hrt_req - 2 hre) / hri",
            f"({result.required_hrt_cm:.3f} - 2*{hre:.2f}) / {hri:.2f}",
            f"{n_raw:.3f} -> n={result.interior_layers}",
        ),
        (
            "n para Si^2/n",
            "n_shape = n (+1 si hre>=0.5 hri)",
            f"n={result.interior_layers}; hre/hri={hre / hri:.3f}",
            f"{result.n_for_shape_limit:.0f}",
        ),
        (
            "Limite Metodo A",
            "Si^2 / n_shape <= 22",
            f"({result.shape_factor_interior:.3f})^2 / {result.n_for_shape_limit:.0f}",
            f"{si2_n:.3f} <= {METHOD_A_SI2_OVER_N_LIMIT:.1f} -> {_ok(si2_n <= METHOD_A_SI2_OVER_N_LIMIT + 1e-9)}",
        ),
    ]
    return _step_table(
        "4. FACTOR DE FORMA Y CAPAS (Art. 14.7.5.1 / 14.7.6.1 / 14.7.6.3.2-7)",
        rows,
    )


def _step_steel_plates(result: ElastomericBearingDesignResult) -> list[str]:
    hri = result.interior_layer_cm
    fy = result.inputs.steel_fy_kg_cm2
    hs_service = 3.0 * hri * result.sigma_s_kg_cm2 / fy
    hs_fatigue = 2.0 * hri * result.sigma_live_kg_cm2 / DELTA_F_TH_CATEGORY_A_KG_CM2
    hs_req = max(hs_service, hs_fatigue, HS_MIN_CM)
    rows = [
        (
            "Servicio",
            "hs >= 3 hri sigma_s / Fy",
            f"3*{hri:.2f}*{result.sigma_s_kg_cm2:.2f}/{fy:.0f}",
            f"{hs_service:.4f} cm",
        ),
        (
            "Fatiga Cat. A",
            "hs >= 2 hri sigma_LL / DeltaF_TH",
            f"2*{hri:.2f}*{result.sigma_live_kg_cm2:.2f}/{DELTA_F_TH_CATEGORY_A_KG_CM2:.0f}",
            f"{hs_fatigue:.4f} cm",
        ),
        (
            "Minimo normativo",
            "hs >= 1/16 in",
            f"{HS_MIN_CM:.4f}",
            f"{HS_MIN_CM:.4f} cm",
        ),
        (
            "hs requerido",
            "max(servicio, fatiga, min)",
            f"max({hs_service:.4f}, {hs_fatigue:.4f}, {HS_MIN_CM:.4f})",
            f"{hs_req:.4f} cm",
        ),
        (
            "hs adoptado",
            "placa comercial",
            f"hs={result.steel_plate_cm:.2f}",
            f"{result.steel_plate_cm:.2f} cm = {result.steel_plate_cm * 10.0:.0f} mm",
        ),
        (
            "N zunchos",
            "N = n + 1",
            f"{result.interior_layers} + 1",
            f"{result.steel_plates}",
        ),
        (
            "Check zuncho",
            "hs_adopt >= hs_req",
            f"{result.steel_plate_cm:.4f} >= {hs_req:.4f}",
            _ok(result.steel_plate_cm + 1e-12 >= hs_req),
        ),
    ]
    return _step_table("5. ZUNCHOS DE ACERO (Art. 14.7.5.3.5)", rows)


def _step_total_height(result: ElastomericBearingDesignResult) -> list[str]:
    h = result.total_height_cm
    rows = [
        (
            "Altura total H",
            "H = hrt + N*hs",
            f"{result.total_elastomer_cm:.3f} + {result.steel_plates}*{result.steel_plate_cm:.2f}",
            f"{h:.3f} cm = {h * 10.0:.0f} mm",
        ),
        (
            "Estabilidad L",
            "H <= L/3",
            f"{h:.3f} <= {result.length_cm:.2f}/3 = {result.length_cm / 3.0:.3f}",
            _ok(h <= result.length_cm / 3.0 + 1e-9),
        ),
        (
            "Estabilidad W",
            "H <= W/3",
            f"{h:.3f} <= {result.width_cm:.2f}/3 = {result.width_cm / 3.0:.3f}",
            _ok(h <= result.width_cm / 3.0 + 1e-9),
        ),
    ]
    return _step_table("6. ALTURA TOTAL Y ESTABILIDAD (Art. 14.7.6.3.6)", rows)


def _step_compression_deflections(result: ElastomericBearingDesignResult) -> list[str]:
    grade = result.grade
    g = result.design_g_kg_cm2
    k = grade.shape_factor_k
    si = result.shape_factor_interior
    se = result.shape_factor_exterior
    hri = result.interior_layer_cm
    hre = result.exterior_layer_cm
    n = result.interior_layers
    eps_perm_i = result.epsilon_permanent
    eps_tot_i = result.epsilon_total
    eps_perm_e = compressive_strain(result.sigma_permanent_kg_cm2, g, se, k)
    eps_tot_e = compressive_strain(result.sigma_s_kg_cm2, g, se, k)
    delta_ll_creep = result.delta_live_cm + result.delta_creep_cm
    e_mod_i = 3.0 * g * (1.0 + 2.0 * k * si**2)
    e_mod_e = 3.0 * g * (1.0 + 2.0 * k * se**2)
    rows = [
        (
            "Modulo capa int.",
            "E = 3G(1+2k Si^2)",
            f"3*{g:.2f}*(1+2*{k:.2f}*{si:.3f}^2)",
            f"{e_mod_i:.2f} kg/cm2",
        ),
        (
            "eps_perm interior",
            "eps = sigma_perm / E",
            f"{result.sigma_permanent_kg_cm2:.2f} / {e_mod_i:.2f}",
            f"{eps_perm_i:.5f}",
        ),
        (
            "eps_total interior",
            "eps = sigma_s / E",
            f"{result.sigma_s_kg_cm2:.2f} / {e_mod_i:.2f}",
            f"{eps_tot_i:.5f}",
        ),
        (
            "Modulo capa ext.",
            "E = 3G(1+2k Se^2)",
            f"3*{g:.2f}*(1+2*{k:.2f}*{se:.3f}^2)",
            f"{e_mod_e:.2f} kg/cm2",
        ),
        (
            "eps_perm exterior",
            "eps = sigma_perm / E",
            f"{result.sigma_permanent_kg_cm2:.2f} / {e_mod_e:.2f}",
            f"{eps_perm_e:.5f}",
        ),
        (
            "eps_total exterior",
            "eps = sigma_s / E",
            f"{result.sigma_s_kg_cm2:.2f} / {e_mod_e:.2f}",
            f"{eps_tot_e:.5f}",
        ),
        (
            "delta total",
            "d = n*eps_i*hri + 2*eps_e*hre",
            f"{n}*{eps_tot_i:.5f}*{hri:.2f} + 2*{eps_tot_e:.5f}*{hre:.2f}",
            f"{result.delta_dead_cm + result.delta_live_cm:.4f} cm",
        ),
        (
            "delta DC",
            "dDC = n*eps_perm_i*hri + 2*eps_perm_e*hre",
            f"{n}*{eps_perm_i:.5f}*{hri:.2f} + 2*{eps_perm_e:.5f}*{hre:.2f}",
            f"{result.delta_dead_cm:.4f} cm",
        ),
        (
            "delta LL",
            "dLL = d_total - dDC",
            f"{result.delta_dead_cm + result.delta_live_cm:.4f} - {result.delta_dead_cm:.4f}",
            f"{result.delta_live_cm:.4f} cm",
        ),
        (
            "delta creep",
            "dcreep = Cd * dDC",
            f"{grade.creep_ratio:.2f} * {result.delta_dead_cm:.4f}",
            f"{result.delta_creep_cm:.4f} cm",
        ),
        (
            "LL + creep",
            "dLL + dcreep",
            f"{result.delta_live_cm:.4f} + {result.delta_creep_cm:.4f}",
            f"{delta_ll_creep:.4f} cm",
        ),
        (
            "Check junta",
            "dLL+dcreep <= 1/8 in",
            f"{delta_ll_creep:.4f} <= {JOINT_DEFLECTION_LIMIT_CM:.4f}",
            _ok(delta_ll_creep <= JOINT_DEFLECTION_LIMIT_CM + 1e-9),
        ),
        (
            "Check eps interior",
            "eps_total_i <= 0.09",
            f"{eps_tot_i:.5f} <= 0.09",
            _ok(eps_tot_i <= 0.09 + 1e-9),
        ),
    ]
    return _step_table(
        "7. DEFLEXIONES POR COMPRESION (Art. 14.7.6.3.3 / 14.7.5.3.6)",
        rows,
    )


def _step_horizontal_forces(result: ElastomericBearingDesignResult) -> list[str]:
    area = result.area_cm2
    g_max = result.max_g_kg_cm2
    hrt = result.total_elastomer_cm
    ds = result.delta_s_cm
    mu = result.inputs.seismic.friction_coefficient
    pdc = result.inputs.loads.dead_load_dc_tn
    hu = result.shear_force_service_tn
    ff = result.friction_capacity_tn
    rows = [
        (
            "Fuerza corte Hu",
            "Hu = Gmax * A * Ds / hrt",
            f"{g_max:.2f}*{area:.1f}*{ds:.3f}/{hrt:.3f} / 1000",
            f"{hu:.3f} Tn",
        ),
        (
            "Friccion Ff",
            "Ff = mu * PDC",
            f"{mu:.3f} * {pdc:.3f}",
            f"{ff:.3f} Tn",
        ),
        (
            "Anclaje servicio",
            "si Hu > Ff => ANCLAR",
            f"{hu:.3f} ? {ff:.3f}",
            "OK (sin anclar)" if hu <= ff + 1e-9 else f"ANCLAR (Hu-Ff={hu - ff:.3f} Tn)",
        ),
    ]
    return _step_table("8. FUERZA HORIZONTAL Y FRICCION (Art. 14.6.3.1 / 14.8.3)", rows)


def _step_seismic(result: ElastomericBearingDesignResult) -> list[str]:
    seis = result.inputs.seismic
    factor = seismic_connection_force_factor(seis)
    p_perm = result.inputs.loads.permanent_tn
    p_long = (
        seis.tributary_permanent_longitudinal_tn
        if seis.tributary_permanent_longitudinal_tn is not None
        else p_perm
    )
    pad_cap = result.shear_force_service_tn
    if seis.bearing_role == "expansion":
        horiz_cap = max(pad_cap, result.friction_capacity_tn)
        capacity_note = f"max(Hu_pad={pad_cap:.3f}, Ff={result.friction_capacity_tn:.3f})"
    else:
        horiz_cap = pad_cap
        capacity_note = f"Hu_pad={pad_cap:.3f} (apoyo fijo)"
    rows = [
        (
            "Factor conexion",
            "F = As (1 tramo) u otro criterio",
            (
                f"As={seis.site_acceleration_as:.3f}; "
                f"1tramo={'si' if seis.is_single_span else 'no'}; "
                f"zona={seis.seismic_zone}"
            ),
            f"{factor:.3f}",
        ),
        (
            "F_EQ transversal",
            "F_EQ,t = F * Pperm (si restringido)",
            (
                f"{factor:.3f}*{p_perm:.3f}"
                if seis.transverse_restrained
                else "no restringido -> 0"
            ),
            f"{result.seismic_force_transverse_tn:.3f} Tn",
        ),
        (
            "F_EQ longitudinal",
            "F_EQ,l = F * P_long (si restringido)",
            (
                f"{factor:.3f}*{p_long:.3f}"
                if seis.longitudinal_restrained
                else "no restringido -> 0"
            ),
            f"{result.seismic_force_longitudinal_tn:.3f} Tn",
        ),
        (
            "F_EQ gobernante",
            "max(F_EQ,t ; F_EQ,l)",
            (
                f"max({result.seismic_force_transverse_tn:.3f}, "
                f"{result.seismic_force_longitudinal_tn:.3f})"
            ),
            f"{result.seismic_governing_tn:.3f} Tn",
        ),
        (
            "Capacidad horizontal",
            "capacidad del pad/friccion",
            capacity_note,
            f"{horiz_cap:.3f} Tn",
        ),
        (
            "Anclaje sismico",
            "Ancl = max(F_EQ - capacidad, 0)",
            f"max({result.seismic_governing_tn:.3f} - {horiz_cap:.3f}, 0)",
            (
                "OK (sin anclar)"
                if result.anchor_force_required_tn <= 1e-9
                else f"ANCLAR {result.anchor_force_required_tn:.3f} Tn"
            ),
        ),
    ]
    return _step_table("9. SISMO Y FUERZA DE UNION (MTC 2.4.3.11.8 / 2.10.3.3.7)", rows)


def _step_concrete_bearing(result: ElastomericBearingDesignResult) -> list[str]:
    support = result.inputs.concrete_support
    if support is None:
        return [
            "",
            *audit_subtitle("", "10. APLASTAMIENTO DEL CONCRETO: NO SOLICITADO", _W),
        ]
    a1 = result.area_cm2
    a2 = support.support_area_cm2 if support.support_area_cm2 is not None else a1
    m = min(sqrt(a2 / a1), 2.0) if a1 > 0 else 0.0
    pn = 0.85 * support.fc_kg_cm2 * a1 * m
    phi_pn = support.phi * pn
    demand = result.inputs.loads.total_service_kg
    rows = [
        (
            "Areas",
            "A1 = L*W; A2 pedestal",
            f"A1={a1:.1f}; A2={a2:.1f}",
            f"A1={a1:.1f} cm2",
        ),
        (
            "Factor m",
            "m = min(sqrt(A2/A1), 2)",
            f"min(sqrt({a2:.1f}/{a1:.1f}), 2)",
            f"{m:.3f}",
        ),
        (
            "Resistencia nominal",
            "Pn = 0.85 f'c A1 m",
            f"0.85*{support.fc_kg_cm2:.1f}*{a1:.1f}*{m:.3f}",
            f"{pn:.0f} kg",
        ),
        (
            "Resistencia diseno",
            "phi Pn",
            f"{support.phi:.2f} * {pn:.0f}",
            f"{phi_pn:.0f} kg",
        ),
        (
            "Demanda",
            "PT servicio (piso)",
            f"{demand:.0f}",
            f"{demand:.0f} kg",
        ),
        (
            "Check aplastamiento",
            "PT <= phi Pn",
            f"{demand:.0f} <= {phi_pn:.0f}",
            _ok(demand <= phi_pn + 1e-9),
        ),
    ]
    return _step_table("10. APLASTAMIENTO DEL CONCRETO (AASHTO 5.7.5 / MTC 2.8.1.4)", rows)


def _format_checks_summary(result: ElastomericBearingDesignResult) -> list[str]:
    lines = [
        "",
        *audit_subtitle("A.3", "RESUMEN DE VERIFICACIONES NORMATIVAS", _W),
    ]
    lines.extend(
        boxed_table(
            ("Verificacion", "Demanda", "Limite", "Ref.", "Estado"),
            tuple(
                (
                    check.name,
                    f"{check.demand:.3f} {check.unit}",
                    f"{check.limit:.3f} {check.unit}",
                    check.reference,
                    check.status,
                )
                for check in result.checks
            ),
            aligns=("left", "right", "right", "left", "center"),
            title="Checks Metodo A + sismo + aplastamiento",
            max_width=_W,
        )
    )
    notes = [check.notes for check in result.checks if check.notes]
    if notes:
        lines.append("Notas de verificacion:")
        lines.extend(f"- {note}" for note in notes)
    lines.append(
        "Nota: el diseno por rotacion esta implicito en geometria y esfuerzos del Metodo A "
        "(C14.7.6.1); no se requieren calculos adicionales de rotacion."
    )
    return lines


def _format_final_designation(result: ElastomericBearingDesignResult) -> list[str]:
    rows = [
        (
            "Designacion",
            result.designation,
            "-",
            "CUMPLE" if result.overall_ok else "NO CUMPLE",
        ),
        (
            "Planta L x W",
            f"{result.length_cm * 10.0:.0f} x {result.width_cm * 10.0:.0f}",
            "mm",
            f"A={result.area_cm2:.1f} cm2",
        ),
        (
            "Altura total H",
            f"{result.total_height_cm * 10.0:.0f}",
            "mm",
            f"hrt={result.total_elastomer_cm * 10.0:.0f} mm",
        ),
        (
            "Capas elastomero",
            f"{result.interior_layers} int @ {result.interior_layer_cm * 10.0:.0f} mm + "
            f"2 ext @ {result.exterior_layer_cm * 10.0:.0f} mm",
            "-",
            f"Shore {result.inputs.hardness}",
        ),
        (
            "Zunchos",
            f"{result.steel_plates} @ {result.steel_plate_cm * 10.0:.0f} mm",
            "-",
            f"Fy={result.inputs.steel_fy_kg_cm2:.0f} kg/cm2",
        ),
        (
            "Anclaje sismico",
            f"{result.anchor_force_required_tn:.3f}",
            "Tn",
            "0 = no requiere por sismo",
        ),
    ]
    return [
        "",
        *audit_subtitle("A.4", "DESIGNACION FINAL DEL APOYO", _W),
        *boxed_table(
            ("Concepto", "Valor", "Unidad", "Estado / Nota"),
            rows,
            aligns=("left", "left", "left", "left"),
            title="Resumen constructivo",
            max_width=_W,
        ),
    ]


def _ok(condition: bool) -> str:
    return "OK" if condition else "NO"
