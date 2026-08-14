"""Reporte ASCII trazable para apoyos PEP fijo/movil."""

from __future__ import annotations

from bridge_design.cli.ascii_tables import audit_block_title, audit_subtitle, boxed_table
from bridge_design.domain.pep_bearing import SIGMA_S_MAX_PEP_KG_CM2, PepBearingDesignResult

_W = 112


def format_pep_bearing_result(result: PepBearingDesignResult) -> str:
    """Return memoria de calculo paso a paso del apoyo PEP."""
    inp = result.inputs
    dem = inp.demands
    g = inp.geometry
    lines: list[str] = [
        "",
        *audit_block_title(
            "PEP",
            f"APOYO ELASTOMERICO PEP {inp.tipo_apoyo} - METODO A (SIN ZUNCHOS)",
            _W,
        ),
        "Referencias: MTC 2.10 / 2.10.4; AASHTO 14.7.5 / 14.7.6 / 14.6.3.1 / 14.8.3 / 5.7.5.",
        "IMPORTANTE: no hay laminas internas de acero; h = espesor total del neopreno simple.",
        "Las placas superior/inferior son externas y NO forman parte de h.",
        f"Designacion: {result.designation}",
        (
            f"Estado nucleo PEP: {'CUMPLE' if result.pep_core_ok else 'NO CUMPLE'} | "
            f"Estado aparato completo: {'CUMPLE' if result.overall_ok else 'NO CUMPLE'}"
        ),
    ]
    lines.extend(_section_geometry(result))
    lines.extend(_section_materials(result))
    lines.extend(_section_demands(result))
    lines.extend(_section_procedure(result))
    lines.extend(_section_checks(result))
    lines.extend(_section_final(result))
    return "\n".join(lines)


def _section_geometry(result: PepBearingDesignResult) -> list[str]:
    g = result.inputs.geometry
    return [
        "",
        *audit_subtitle("1", "DATOS GEOMETRICOS DEL PEP", _W),
        *boxed_table(
            ("Parametro", "Valor", "Unidad", "Nota"),
            (
                ("Tipo de apoyo", result.inputs.tipo_apoyo, "-", "FIJO / MOVIL_PEP_CORTE"),
                ("L (longitudinal)", f"{g.length_cm:.2f}", "cm", "paralelo al puente"),
                ("W (transversal)", f"{g.width_cm:.2f}", "cm", "transversal"),
                ("h (elastomero)", f"{g.thickness_cm:.2f}", "cm", "1 sola capa; sin zunchos"),
                ("A = L*W", f"{result.area_cm2:.1f}", "cm2", "area en planta"),
                ("S = LW/[2h(L+W)]", f"{result.shape_factor:.3f}", "-", "AASHTO 14.7.5.1-1"),
                ("Capas interiores", "1", "-", "hri = h"),
                ("Zunchos internos", "0", "-", "NO existen"),
            ),
            aligns=("left", "right", "left", "left"),
            title="Geometria PEP",
            max_width=_W,
        ),
    ]


def _section_materials(result: PepBearingDesignResult) -> list[str]:
    grade = result.grade
    up = result.inputs.upper_plate
    anc = result.inputs.anchors
    plate_note = _plate_material_label(up.fy_kg_cm2, up.fu_kg_cm2) if up else "auto-diseno o no ingresada"
    bolt_note = _bolt_material_label(anc.fy_kg_cm2, anc.fu_kg_cm2) if anc else "auto-diseno o no ingresado"
    return [
        "",
        *audit_subtitle("2", "MATERIALES", _W),
        *boxed_table(
            ("Parametro", "Valor", "Unidad", "Criterio"),
            (
                ("Dureza Shore A", f"{result.inputs.hardness}", "-", "Tabla 14.7.6.2-1"),
                ("Gmin", f"{grade.g_min_kg_cm2:.2f}", "kg/cm2", result.g_capacity_reason),
                ("Gmax", f"{grade.g_max_kg_cm2:.2f}", "kg/cm2", result.g_force_reason),
                ("G capacidad usado", f"{result.g_for_capacity_kg_cm2:.2f}", "kg/cm2", "compresion"),
                ("G fuerza usado", f"{result.g_for_force_kg_cm2:.2f}", "kg/cm2", "H_pad"),
                ("a_cr creep", f"{grade.creep_ratio:.2f}", "-", "Tabla 14.7.6.2-1"),
                ("k forma", f"{grade.shape_factor_k:.2f}", "-", "estimacion eps"),
                ("0.80 ksi", f"{SIGMA_S_MAX_PEP_KG_CM2:.2f}", "kg/cm2", "limite PEP"),
                ("Planchas", "Fy=2530; Fu=4080", "kg/cm2", "ASTM A36 asumido" if up is None else plate_note),
                ("Pernos", "Fy=4220; Fu=6330", "kg/cm2", "ASTM A325 asumido" if anc is None else bolt_note),
            ),
            aligns=("left", "right", "left", "left"),
            title="Neopreno / limites",
            max_width=_W,
        ),
    ]


def _section_demands(result: PepBearingDesignResult) -> list[str]:
    dem = result.inputs.demands
    inp = result.inputs
    theta_note = "Sin dato: adoptado 0" if abs(result.theta_total_rad) <= 1e-12 else "Dato ingresado"
    delta_note = "Servicio"
    if dem.delta_s_cm is None and dem.temperature is not None:
        delta_note = "Calculado por temperatura"
    h_eq_note = (
        "PGA*Fpga*(R_DC+R_DW)"
        if inp.seismic_pga is not None and inp.seismic_fpga is not None
        else "As*(R_DC+R_DW)"
    )
    rows = [
        ("R_DC", f"{dem.r_dc_tn:.3f}", "Tn", "Servicio"),
        ("R_DW", f"{dem.r_dw_tn:.3f}", "Tn", "Servicio"),
        ("R_LL", f"{dem.r_ll_tn:.3f}", "Tn", "Servicio"),
        ("R_IM", f"{dem.r_im_tn:.3f}", "Tn", "Servicio"),
        ("R servicio", f"{dem.r_service_tn:.3f}", "Tn", "Servicio"),
        ("Rmin", f"{dem.r_min_tn if dem.r_min_tn is not None else '-'}", "Tn", "Servicio/uplift"),
        ("H_long", f"{dem.h_long_tn:.3f}", "Tn", "Servicio/resistencia"),
    ]
    if abs(dem.h_trans_tn) > 1e-12:
        rows.append(("H_trans", f"{dem.h_trans_tn:.3f}", "Tn", "Servicio/resistencia"))
    rows.append(("H_EQ_long", f"{dem.h_eq_long_tn:.3f}", "Tn", h_eq_note))
    if abs(dem.h_eq_trans_tn) > 1e-12:
        rows.append(("H_EQ_trans", f"{dem.h_eq_trans_tn:.3f}", "Tn", "Evento extremo"))
    rows.extend(
        [
            ("Delta_s", f"{result.delta_s_cm:.3f}", "cm", delta_note),
            ("theta_total", f"{result.theta_total_rad:.6f}", "rad", theta_note),
        ]
    )
    return [
        "",
        *audit_subtitle("3", "REACCIONES, MOVIMIENTOS Y ROTACIONES", _W),
        *boxed_table(
            ("Demanda", "Valor", "Unidad", "Caso"),
            rows,
            aligns=("left", "right", "left", "left"),
            title="Demandas del mismo caso/combinacion",
            max_width=_W,
        ),
    ]


def _section_procedure(result: PepBearingDesignResult) -> list[str]:
    g = result.inputs.geometry
    dem = result.inputs.demands
    if dem.delta_s_cm is None and dem.temperature is not None:
        delta_formula = "gamma_TU*alpha*L*Delta_T"
        delta_substitution = (
            f"{dem.gamma_tu:.2f}*{dem.alpha_per_c:.8f}*{dem.span_length_m*100:.1f}*"
            f"{dem.temperature.contraction_delta_t_c:.1f}"
        )
    else:
        delta_formula = "movimiento servicio"
        delta_substitution = "Servicio"
    rows = [
        (
            "Area",
            "A = L*W",
            f"{g.length_cm:.2f}*{g.width_cm:.2f}",
            f"{result.area_cm2:.1f} cm2",
        ),
        (
            "Factor de forma",
            "S = L*W/[2*h*(L+W)]",
            f"{g.length_cm:.2f}*{g.width_cm:.2f}/[2*{g.thickness_cm:.2f}*({g.length_cm:.2f}+{g.width_cm:.2f})]",
            f"{result.shape_factor:.3f}",
        ),
        (
            "sigma_s",
            "R/A",
            f"{dem.r_service_tn*1000:.0f}/{result.area_cm2:.1f}",
            f"{result.sigma_s_kg_cm2:.2f} kg/cm2",
        ),
        (
            "G*S",
            "Gmin*S",
            f"{result.g_for_capacity_kg_cm2:.2f}*{result.shape_factor:.3f}",
            f"{result.sigma_gs_kg_cm2:.2f} kg/cm2",
        ),
        (
            "sigma_adm",
            "min(G*S, 0.80ksi)",
            f"min({result.sigma_gs_kg_cm2:.2f}, {SIGMA_S_MAX_PEP_KG_CM2:.2f})",
            f"{result.sigma_adm_kg_cm2:.2f} kg/cm2",
        ),
        (
            "eps_perm / eps_tot",
            "manual o estimacion",
            result.epsilon_note[:48],
            f"{result.epsilon_permanent:.5f} / {result.epsilon_total:.5f}",
        ),
        (
            "delta_DC / delta_LL",
            "eps*h",
            f"h={g.thickness_cm:.2f}",
            f"{result.delta_dead_cm:.4f} / {result.delta_live_cm:.4f} cm",
        ),
        (
            "creep / largo plazo",
            "a_cr*delta_DC ; delta_lt",
            f"a_cr={result.grade.creep_ratio:.2f}",
            f"{result.delta_creep_cm:.4f} / {result.delta_long_term_cm:.4f} cm",
        ),
        (
            "Delta_s",
            delta_formula,
            delta_substitution,
            f"{result.delta_s_cm:.3f} cm",
        ),
        (
            "Momento rotacion",
            result.moment_formula,
            f"theta={result.theta_total_rad:.6f}",
            f"{result.moment_tn_m:.4f} Tn-m",
        ),
        (
            "H_pad",
            "Gmax*A*Delta/h",
            f"{result.g_for_force_kg_cm2:.2f}*{result.area_cm2:.1f}*{result.delta_s_cm:.3f}/{g.thickness_cm:.2f}",
            f"{result.h_pad_service_tn:.3f} Tn",
        ),
        (
            "Estabilidad",
            "h <= min(L/3,W/3)",
            f"min({g.length_cm/3:.2f},{g.width_cm/3:.2f})",
            f"h={g.thickness_cm:.2f} cm",
        ),
    ]
    if result.inputs.tipo_apoyo == "FIJO":
        rows.append(
            (
                "H fija long.",
                "100% H_long al sistema de restriccion",
                "sin reducir por friccion",
                f"{result.h_fixed_long_tn:.3f} Tn",
            )
        )
        if result.h_fixed_trans_tn > 1e-12:
            rows.append(
                (
                    "H fija trans.",
                    "100% H_trans al sistema de restriccion",
                    "sin reducir por friccion",
                    f"{result.h_fixed_trans_tn:.3f} Tn",
                )
            )
    else:
        rows.append(
            (
                "Anclaje EE reportado",
                "max(H_EE - capacidad_pad/friccion, 0)",
                f"H_EE={result.h_eq_gov_tn:.3f}",
                f"{result.h_anchor_report_tn:.3f} Tn",
            )
        )
    return [
        "",
        *audit_subtitle("4", "PROCEDIMIENTO PASO A PASO", _W),
        *boxed_table(
            ("Paso", "Formula", "Sustitucion", "Resultado"),
            rows,
            aligns=("left", "left", "left", "right"),
            title="Calculo PEP",
            max_width=_W,
        ),
    ]


def _section_checks(result: PepBearingDesignResult) -> list[str]:
    lines = [
        "",
        *audit_subtitle("5", "VERIFICACIONES NORMATIVAS", _W),
        *boxed_table(
            ("Verificacion", "EL", "Demanda", "Limite", "Ratio", "Estado", "Ref."),
            tuple(
                (
                    check.name,
                    check.estado_limite,
                    f"{check.demand:.3f} {check.unit}",
                    f"{check.limit:.3f} {check.unit}",
                    f"{check.ratio:.3f}" if check.ratio is not None else "-",
                    check.status,
                    check.articulo_aashto,
                )
                for check in result.checks
            ),
            aligns=("left", "left", "right", "right", "right", "center", "left"),
            title="Checks auditables",
            max_width=_W,
        ),
    ]
    detail_rows = [
        (
            check.name,
            check.formula,
            check.substitution,
            f"{check.status} | MTC:{check.articulo_mtc}",
        )
        for check in result.checks
    ]
    lines.extend(
        [
            "",
            *boxed_table(
                ("Verificacion", "Formula", "Sustitucion", "Estado / MTC"),
                detail_rows,
                aligns=("left", "left", "left", "left"),
                title="Detalle formula / sustitucion",
                max_width=_W,
            ),
        ]
    )
    if result.pending_components:
        lines.append("Componentes pendientes:")
        lines.extend(f"- {item}" for item in result.pending_components)
    notes = [c.notes for c in result.checks if c.notes]
    if notes:
        lines.append("Notas:")
        lines.extend(f"- {note}" for note in notes)
    return lines


def _section_final(result: PepBearingDesignResult) -> list[str]:
    g = result.inputs.geometry
    up = result.inputs.upper_plate
    low = result.inputs.lower_plate
    anc = result.inputs.anchors
    theta_note = "Sin dato: adoptado 0" if abs(result.theta_total_rad) <= 1e-12 else "Dato ingresado"
    plate_status = _component_status(result, ("Placa superior", "Placa inferior"))
    anchor_status = _component_status(result, ("Perno:", "Soldadura", "Anclaje:"))
    rows = [
        ("Estado diseno/verificacion", "CONFORME" if result.overall_ok else "NO CONFORME", "-", "aparato completo"),
        ("APOYO", result.inputs.tipo_apoyo, "-", _cell_note(result.designation)),
        (
            "PEP LxWxh",
            f"{g.length_cm*10:.0f}x{g.width_cm*10:.0f}x{g.thickness_cm*10:.0f}",
            "mm",
            f"Shore {result.inputs.hardness}; S={result.shape_factor:.2f}",
        ),
        (
            "Placa superior",
            (
                f"{up.length_cm*10:.0f}x{up.width_cm*10:.0f}x{up.thickness_cm*10:.0f}"
                if up
                else "no ingresada"
            ),
            "mm",
            (
                f"{_plate_material_label(up.fy_kg_cm2, up.fu_kg_cm2)}; {plate_status}"
                if up
                else "pendiente"
            ),
        ),
        (
            "Placa inferior",
            (
                f"{low.length_cm*10:.0f}x{low.width_cm*10:.0f}x{low.thickness_cm*10:.0f}"
                if low
                else "no ingresada"
            ),
            "mm",
            (
                f"{_plate_material_label(low.fy_kg_cm2, low.fu_kg_cm2)}; {plate_status}"
                if low
                else "pendiente"
            ),
        ),
        (
            "Pernos requeridos",
            f"{anc.n_bolts} pernos" if anc else "no ingresados",
            "-",
            (
                f"{_bolt_material_label(anc.fy_kg_cm2, anc.fu_kg_cm2)}; {anchor_status}"
                if anc
                else "pendiente"
            ),
        ),
        (
            "Detalle pernos",
            f"d={anc.diameter_cm*10:.0f} mm; hef={anc.embedment_cm:.1f} cm" if anc else "no ingresado",
            "-",
            anc.layout_note if anc else "pendiente",
        ),
        ("Rmax servicio", f"{result.inputs.demands.r_service_tn:.3f}", "Tn", "Servicio"),
        ("Delta_s", f"{result.delta_s_cm:.3f}", "cm", "Servicio"),
        ("theta", f"{result.theta_total_rad:.6f}", "rad", theta_note),
        ("Nucleo PEP", "CUMPLE" if result.pep_core_ok else "NO CUMPLE", "-", "elastomero"),
        ("Aparato completo", "CUMPLE" if result.overall_ok else "NO CUMPLE", "-", "incluye placas/anclajes"),
    ]
    return [
        "",
        *audit_subtitle("6", "SALIDA FINAL", _W),
        *boxed_table(
            ("Elemento", "Dimension / valor final", "Unidad", "Material / estado"),
            rows,
            aligns=("left", "left", "left", "left"),
            title="Resumen constructivo final",
            max_width=_W,
        ),
    ]


def _plate_material_label(fy_kg_cm2: float, fu_kg_cm2: float) -> str:
    if abs(fy_kg_cm2 - 2530.0) <= 1.0 and abs(fu_kg_cm2 - 4080.0) <= 1.0:
        return "ASTM A36 (Fy=2530; Fu=4080 kg/cm2)"
    return f"Fy={fy_kg_cm2:.0f}; Fu={fu_kg_cm2:.0f} kg/cm2"


def _bolt_material_label(fy_kg_cm2: float, fu_kg_cm2: float) -> str:
    if abs(fy_kg_cm2 - 4220.0) <= 1.0 and abs(fu_kg_cm2 - 6330.0) <= 1.0:
        return "ASTM A325 (Fy=4220; Fu=6330 kg/cm2)"
    return f"Fy={fy_kg_cm2:.0f}; Fu={fu_kg_cm2:.0f} kg/cm2"


def _component_status(result: PepBearingDesignResult, prefixes: tuple[str, ...]) -> str:
    checks = [check for check in result.checks if check.name.startswith(prefixes)]
    if not checks:
        return "NO VERIFICADO"
    return "CONFORME" if all(check.ok for check in checks) else "NO CONFORME"


def _cell_note(value: str) -> str:
    return value.replace("|", ";")
