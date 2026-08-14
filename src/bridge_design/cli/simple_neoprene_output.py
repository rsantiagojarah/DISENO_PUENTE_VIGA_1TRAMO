"""Salida ASCII para apoyos de neopreno simple con detalles especificos."""

from __future__ import annotations

from bridge_design.cli.ascii_tables import audit_block_title, audit_subtitle, boxed_table
from bridge_design.domain.simple_neoprene_support import SimpleSupportResult

_W = 112


def format_simple_neoprene_result(result: SimpleSupportResult) -> str:
    inp = result.inputs
    g = inp.geometry
    lines: list[str] = [
        "",
        *audit_block_title(
            "NEOPRENO",
            f"APOYO {'FIJO PASADORES' if inp.support_type == 'FIJO_BARRAS' else 'MOVIL PLACAS'} - NEOPRENO SIMPLE",
            _W,
        ),
        "Detalle especifico independiente de diseno-apoyos-PEP.",
        f"Estado global: {'CONFORME' if result.overall_ok else 'NO CONFORME'}",
        "",
        *audit_subtitle("1", "GEOMETRIA Y DEMANDAS", _W),
        *boxed_table(
            ("Parametro", "Valor", "Unidad", "Nota"),
            (
                ("Tipo", inp.support_type, "-", "FIJO_BARRAS / MOVIL_PLACAS"),
                ("Neopreno L", f"{g.length_cm:.2f}", "cm", "planta"),
                ("Neopreno W", f"{g.width_cm:.2f}", "cm", "planta"),
                ("Neopreno h", f"{g.thickness_cm:.2f}", "cm", "espesor total"),
                ("Dureza", f"{inp.hardness}", "Shore A", "neopreno"),
                ("Gmin", f"{result.g_min_kg_cm2:.2f}", "kg/cm2", result.g_capacity_reason),
                ("Gmax", f"{result.g_max_kg_cm2:.2f}", "kg/cm2", result.g_force_reason),
                ("Area efectiva", f"{result.effective_area_cm2:.2f}", "cm2", "descuenta perforaciones de pasadores si aplica"),
                ("S", f"{result.shape_factor:.3f}", "-", "factor de forma usado"),
                ("R servicio", f"{inp.demands.r_service_tn:.3f}", "Tn", "DC+DW+PL+LL+IM"),
                ("BR nominal", f"{inp.demands.h_long_tn:.3f}", "Tn", "por apoyo; sin factor"),
                ("H_BR Resistencia I", f"{inp.demands.h_br_strength_tn:.3f}", "Tn", "1.75*BR"),
                ("H_EQ Evento Extremo I", f"{inp.demands.h_eq_long_tn:.3f}", "Tn", "PGA*Fpga*(DC+DW)"),
                ("Delta termico", f"{result.delta_thermal_cm:.3f}", "cm", "gamma_TU*alpha*L*Delta_T"),
            ),
            aligns=("left", "right", "left", "left"),
            title="Datos",
            max_width=_W,
        ),
    ]
    lines.extend(_detail_section(result))
    lines.extend(_procedure_section(result))
    lines.extend(_checks_section(result))
    lines.extend(_final_section(result))
    return "\n".join(lines)


def _detail_section(result: SimpleSupportResult) -> list[str]:
    inp = result.inputs
    rows = []
    if inp.support_type == "FIJO_BARRAS":
        bars = inp.fixed_bars
        assert bars is not None
        rows.extend(
            [
                ("Pasadores", f"{bars.n_bars} pasadores", "-", "redondos lisos ASTM A108 Gr. 1020; Fy=2500 kg/cm2"),
                ("Diametro pasador", f"{bars.diameter_cm:.2f}", "cm", f"{bars.diameter_cm/2.54:.2f} pulg"),
                ("Separacion long.", f"{bars.spacing_long_cm:.2f}", "cm", "planta"),
                ("Separacion trans.", f"{bars.spacing_trans_cm:.2f}", "cm", "planta"),
                ("Brazo e del pasador", f"{bars.moment_arm_cm:.2f}", "cm", "entre resultantes de contacto"),
            ]
        )
    else:
        plates = inp.plates
        assert plates is not None
        rows.extend(
            [
                ("Plancha superior", f"{inp.geometry.length_cm*10:.0f}x{inp.geometry.width_cm*10:.0f}x{plates.thickness_cm*10:.0f}", "mm", "ASTM A36"),
                ("Plancha inferior", f"{inp.geometry.length_cm*10:.0f}x{inp.geometry.width_cm*10:.0f}x{plates.thickness_cm*10:.0f}", "mm", "ASTM A36"),
                ("Movimiento", f"{result.delta_thermal_cm:.3f}", "cm", "por deformacion de corte del neopreno"),
                ("H_pad", f"{result.h_pad_tn:.3f}", "Tn", "fuerza horizontal del neopreno"),
            ]
        )
    return [
        "",
        *audit_subtitle("2", "DETALLE CONSTRUCTIVO", _W),
        *boxed_table(
            ("Elemento", "Valor", "Unidad", "Nota"),
            rows,
            aligns=("left", "right", "left", "left"),
            title="Configuracion",
            max_width=_W,
        ),
    ]


def _checks_section(result: SimpleSupportResult) -> list[str]:
    return [
        "",
        *audit_subtitle("4", "VERIFICACIONES", _W),
        *boxed_table(
            ("Verificacion", "Demanda", "Limite", "Ratio", "Estado", "Formula"),
            tuple(
                (
                    check.name,
                    f"{check.demand:.3f} {check.unit}",
                    f"{check.limit:.3f} {check.unit}",
                    f"{check.ratio:.3f}" if check.ratio is not None else "-",
                    check.status,
                    check.formula,
                )
                for check in result.checks
            ),
            aligns=("left", "right", "right", "right", "center", "left"),
            title="Checks",
            max_width=_W,
        ),
        "",
        *boxed_table(
            ("Verificacion", "Sustitucion", "Nota"),
            tuple((check.name, check.substitution, check.notes) for check in result.checks),
            aligns=("left", "left", "left"),
            title="Sustitucion",
            max_width=_W,
        ),
    ]


def _final_section(result: SimpleSupportResult) -> list[str]:
    inp = result.inputs
    g = inp.geometry
    rows = [
        ("Estado", "CONFORME" if result.overall_ok else "NO CONFORME", "-", "todas las verificaciones"),
        ("Neopreno", f"{g.length_cm*10:.0f}x{g.width_cm*10:.0f}x{g.thickness_cm*10:.0f}", "mm", f"Shore {inp.hardness}"),
        ("R servicio", f"{inp.demands.r_service_tn:.3f}", "Tn", "DC+DW+PL+LL+IM"),
    ]
    if inp.support_type == "FIJO_BARRAS":
        bars = inp.fixed_bars
        assert bars is not None
        rows.extend(
            [
                ("Detalle fijo", f"{bars.n_bars} pasadores lisos d={bars.diameter_cm/2.54:.2f} pulg", "-", "pasantes; ASTM A108 Gr. 1020"),
                ("Separacion pasadores", f"{bars.spacing_long_cm:.0f} x {bars.spacing_trans_cm:.0f}", "cm", "planta"),
                ("H diseno pasadores", f"{result.h_design_tn:.3f}", "Tn", result.h_design_case),
            ]
        )
    else:
        plates = inp.plates
        assert plates is not None
        rows.extend(
            [
                ("Planchas A36", f"{g.length_cm*10:.0f}x{g.width_cm*10:.0f}x{plates.thickness_cm*10:.0f}", "mm", "superior e inferior"),
                ("H_pad", f"{result.h_pad_tn:.3f}", "Tn", "por corte del neopreno"),
            ]
        )
    return [
        "",
        *audit_subtitle("5", "SALIDA FINAL", _W),
        *boxed_table(
            ("Elemento", "Valor final", "Unidad", "Nota"),
            rows,
            aligns=("left", "left", "left", "left"),
            title="Resumen final",
            max_width=_W,
        ),
    ]


def _procedure_section(result: SimpleSupportResult) -> list[str]:
    inp = result.inputs
    geom = inp.geometry
    dem = inp.demands
    rows = [
        (
            "Area bruta",
            "A_g = L*W",
            f"{geom.length_cm:.2f}*{geom.width_cm:.2f}",
            f"{result.gross_area_cm2:.2f} cm2",
        ),
        (
            "Area descontada",
            "A_h = n*pi*d^2/4",
            _removed_area_substitution(result),
            f"{result.removed_area_cm2:.2f} cm2",
        ),
        (
            "Area efectiva",
            "A_eff = A_g - A_h",
            f"{result.gross_area_cm2:.2f}-{result.removed_area_cm2:.2f}",
            f"{result.effective_area_cm2:.2f} cm2",
        ),
        (
            "Area libre",
            "A_libre = perimetro*h (+ huecos)",
            _free_area_substitution(result),
            f"{result.free_area_cm2:.2f} cm2",
        ),
        (
            "Factor de forma",
            "S = A_eff/A_libre",
            f"{result.effective_area_cm2:.2f}/{result.free_area_cm2:.2f}",
            f"{result.shape_factor:.3f}",
        ),
        (
            "Reaccion servicio",
            "R = DC+DW+PL+LL+IM",
            f"{dem.r_dc_tn:.3f}+{dem.r_dw_tn:.3f}+{dem.r_pl_tn:.3f}+{dem.r_ll_im_tn:.3f}",
            f"{dem.r_service_tn:.3f} Tn",
        ),
        (
            "Esfuerzo compresion",
            "sigma = R/A_eff",
            f"{dem.r_service_tn*1000:.0f}/{result.effective_area_cm2:.2f}",
            f"{result.sigma_service_kg_cm2:.2f} kg/cm2",
        ),
        (
            "Limite compresion",
            "sigma_adm = min(G*S,0.80ksi)",
            f"min({result.g_min_kg_cm2:.2f}*{result.shape_factor:.3f}, 56.25)",
            f"{result.sigma_adm_kg_cm2:.2f} kg/cm2",
        ),
        (
            "Deflexion vertical",
            "delta_c = eps*h",
            f"{result.epsilon_total:.5f}*{geom.thickness_cm:.2f}",
            f"{result.delta_compression_cm:.3f} cm",
        ),
        (
            "Movimiento termico",
            "Delta_s = gamma*alpha*L*Delta_T",
            _thermal_substitution(result),
            f"{result.delta_thermal_cm:.3f} cm",
        ),
        (
            "Sismo longitudinal EE-I",
            "H_EQ = PGA*Fpga*(DC+DW)",
            f"{dem.pga:.3f}*{dem.fpga:.3f}*({dem.r_dc_tn:.3f}+{dem.r_dw_tn:.3f})",
            f"{dem.h_eq_long_tn:.3f} Tn",
        ),
    ]
    if inp.support_type == "FIJO_BARRAS":
        bars = inp.fixed_bars
        assert bars is not None
        v_pin = result.h_design_tn / bars.n_bars
        m_pin = v_pin * 1000.0 * bars.moment_arm_cm
        flexure_term = 6.0 * m_pin / (bars.diameter_cm**3 * bars.fy_kg_cm2)
        shear_term = (2.2 * v_pin * 1000.0 / (bars.diameter_cm**2 * bars.fy_kg_cm2)) ** 2
        rows.extend(
            [
                (
                    "Frenado Resistencia I",
                    "H_BR = 1.75*BR",
                    f"1.75*{dem.h_long_tn:.3f}",
                    f"{dem.h_br_strength_tn:.3f} Tn",
                ),
                (
                    "H diseno fijo",
                    "H = max(H_BR,RI; H_EQ,EE-I)",
                    f"max({dem.h_br_strength_tn:.3f},{dem.h_eq_long_tn:.3f})",
                    f"{result.h_design_tn:.3f} Tn ({result.h_design_case})",
                ),
                (
                    "Corte por pasador",
                    "Vu = H/n",
                    f"{result.h_design_tn:.3f}/{bars.n_bars}",
                    f"{v_pin:.3f} Tn",
                ),
                (
                    "Momento de pasador",
                    "Mu = Vu*e",
                    f"{v_pin*1000:.1f}*{bars.moment_arm_cm:.2f}",
                    f"{m_pin:.1f} kg-cm",
                ),
                (
                    "Interaccion pasador",
                    "I = 6Mu/(D^3Fy)+[2.2Vu/(D^2Fy)]^2",
                    f"{flexure_term:.3f}+{shear_term:.3f}",
                    f"{flexure_term + shear_term:.3f} <= 0.95",
                ),
            ]
        )
    else:
        rows.extend(
            [
                (
                    "H_pad movil",
                    "H = Gmax*A*Delta_s/h",
                    f"Gmax={result.g_max_kg_cm2:.2f}; A={geom.gross_area_cm2:.1f}; Delta={result.delta_thermal_cm:.3f}; h={geom.thickness_cm:.2f}",
                    f"{result.h_pad_tn:.3f} Tn",
                ),
                (
                    "Friccion",
                    "F_f = mu*R_DC",
                    f"{inp.friction_coefficient:.2f}*{dem.r_dc_tn:.3f}",
                    f"{result.friction_capacity_tn:.3f} Tn",
                ),
            ]
        )
    return [
        "",
        *audit_subtitle("3", "PROCEDIMIENTO PASO A PASO", _W),
        *boxed_table(
            ("Paso", "Formula", "Sustitucion", "Resultado"),
            rows,
            aligns=("left", "left", "left", "right"),
            title="Desarrollo numerico",
            max_width=_W,
        ),
    ]


def _removed_area_substitution(result: SimpleSupportResult) -> str:
    bars = result.inputs.fixed_bars
    if bars is None:
        return "sin perforaciones"
    return f"{bars.n_bars}*pi*{bars.diameter_cm:.2f}^2/4"


def _free_area_substitution(result: SimpleSupportResult) -> str:
    geom = result.inputs.geometry
    bars = result.inputs.fixed_bars
    base = f"2*{geom.thickness_cm:.2f}*({geom.length_cm:.2f}+{geom.width_cm:.2f})"
    if bars is None:
        return base
    return f"{base}+{bars.n_bars}*pi*{bars.diameter_cm:.2f}*{geom.thickness_cm:.2f}"


def _thermal_substitution(result: SimpleSupportResult) -> str:
    dem = result.inputs.demands
    temp = dem.temperature
    delta_t = temp.contraction_delta_t_c if temp is not None else 0.0
    return f"{dem.gamma_tu:.2f}*{dem.alpha_per_c:.8f}*{dem.span_length_m*100:.1f}*{delta_t:.1f}"
