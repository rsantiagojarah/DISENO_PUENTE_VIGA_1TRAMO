"""Trazas de fórmulas y sustituciones para la memoria Word de neopreno simple."""

from __future__ import annotations

from bridge_design.domain.simple_neoprene_support import (
    SIGMA_S_MAX_PEP_KG_CM2,
    BRAKING_FACTOR_STRENGTH_I,
    PIN_PHI_FLEXURE,
    PIN_PHI_SHEAR,
    SimpleSupportResult,
    SupportCheck,
)

TraceTuple = tuple[str, str, str, str, str]

CHECK_REFERENCES: dict[str, str] = {
    "Compresion neopreno": "Manual de Puentes MTC 2018, Art. 2.10.4.3.2; AASHTO LRFD 14.7.6.3.2.",
    "Deflexion por compresion": "Manual de Puentes MTC 2018, Art. 2.10.4.3.3; AASHTO LRFD 14.7.6.3.3.",
    "Estabilidad h <= L/3": "Manual de Puentes MTC 2018, Art. 2.10.4.3.6; AASHTO LRFD 14.7.6.3.6.",
    "Estabilidad h <= W/3": "Manual de Puentes MTC 2018, Art. 2.10.4.3.6; AASHTO LRFD 14.7.6.3.6.",
    "Aplastamiento concreto bajo apoyo": "AASHTO LRFD 5.7.5.",
    "Relacion de perforaciones": "Criterio constructivo interno del módulo diseno-apoyos-neopreno.",
    "Area neta con perforaciones": "Geometría del apoyo fijo con pasadores pasantes.",
    "Borde de pasadores dentro del neopreno": "Detalle constructivo de pasadores en neopreno simple.",
    "Separacion de pasadores": "Detalle constructivo de pasadores en neopreno simple.",
    "Interaccion pasador corte-flexion": "AASHTO LRFD 6.13.1.",
    "Cortante por movimiento termico": "Manual de Puentes MTC 2018, Art. 2.10.4.3.4; AASHTO LRFD 14.7.6.3.4-1.",
    "Deformacion angular del neopreno": "Manual de Puentes MTC 2018, Art. 2.10.4.3.4; AASHTO LRFD 14.7.6.3.4-1.",
    "Fuerza H_pad movil": "Manual de Puentes MTC 2018, Art. 2.10.2.1.1; AASHTO LRFD 14.6.3.1.",
    "Friccion disponible": "AASHTO LRFD 14.8.3 / C14.8.3.1.",
    "Espesor planchas superior/inferior": "Detalle constructivo ASTM A36.",
    "Compresion en planchas A36": "ASTM A36; AASHTO LRFD criterios de compresión en planchas.",
}


def check_reference(check_name: str) -> str:
    return CHECK_REFERENCES.get(
        check_name,
        "Manual de Puentes MTC 2018, Art. 2.10.4; AASHTO LRFD 14.7.6.",
    )


def support_check_trace(check: SupportCheck) -> TraceTuple:
    """Convierte una verificación del dominio al formato trazable de la memoria Word."""
    legend = _legend_for_check(check.name)
    substitution = check.substitution.replace("; ", "\n")
    ratio = check.ratio
    ratio_text = f"; ratio = {ratio:.3f}" if ratio is not None else ""
    if check.status == "OK":
        result_text = (
            f"Demanda = {check.demand:.3f} {check.unit} "
            f"≤ Límite = {check.limit:.3f} {check.unit}{ratio_text}: CUMPLE."
        )
        comment = check.notes or "La verificación cumple con el criterio adoptado."
    else:
        result_text = (
            f"Demanda = {check.demand:.3f} {check.unit} "
            f"> Límite = {check.limit:.3f} {check.unit}{ratio_text}: NO CUMPLE."
        )
        comment = (
            check.notes
            + " La verificación no cumple; debe incrementarse la capacidad o reducirse "
            "la demanda y repetirse el cálculo antes de emitir el diseño."
        ).strip()
    return check.formula, legend, substitution, result_text, comment


def gross_area_trace(result: SimpleSupportResult) -> TraceTuple:
    geom = result.inputs.geometry
    formula = "A_g = L · W"
    legend = "A_g: área bruta en planta; L: largo del neopreno; W: ancho del neopreno."
    substitution = f"A_g = {geom.length_cm:.2f} · {geom.width_cm:.2f} = {result.gross_area_cm2:.2f} cm²"
    result_text = f"El área bruta del neopreno es A_g = {result.gross_area_cm2:.2f} cm²."
    comment = "El área bruta define la geometría inicial antes de descontar perforaciones de pasadores."
    return formula, legend, substitution, result_text, comment


def removed_area_trace(result: SimpleSupportResult) -> TraceTuple:
    bars = result.inputs.fixed_bars
    if bars is None:
        formula = "A_h = 0"
        legend = "A_h: área descontada por perforaciones; no aplica en apoyo móvil."
        substitution = "Sin pasadores interiores: A_h = 0 cm²"
        result_text = "No se descuenta área por perforaciones."
        comment = "El apoyo móvil conserva el área bruta completa del neopreno."
        return formula, legend, substitution, result_text, comment
    formula = "A_h = n · π · d² / 4"
    legend = "A_h: área total de huecos; n: número de pasadores; d: diámetro del pasador."
    substitution = (
        f"A_h = {bars.n_bars} · π · {bars.diameter_cm:.2f}² / 4 "
        f"= {result.removed_area_cm2:.2f} cm²"
    )
    result_text = f"El área descontada por pasadores es A_h = {result.removed_area_cm2:.2f} cm²."
    comment = "Los pasadores lisos atraviesan el neopreno y reducen el área efectiva en compresión."
    return formula, legend, substitution, result_text, comment


def effective_area_trace(result: SimpleSupportResult) -> TraceTuple:
    formula = "A_eff = A_g − A_h"
    legend = "A_eff: área neta en compresión; A_g: área bruta; A_h: área de huecos."
    substitution = (
        f"A_eff = {result.gross_area_cm2:.2f} − {result.removed_area_cm2:.2f} "
        f"= {result.effective_area_cm2:.2f} cm²"
    )
    result_text = f"El área efectiva adoptada es A_eff = {result.effective_area_cm2:.2f} cm²."
    comment = "La compresión del neopreno y el aplastamiento del concreto usan A_eff."
    return formula, legend, substitution, result_text, comment


def free_area_trace(result: SimpleSupportResult) -> TraceTuple:
    geom = result.inputs.geometry
    bars = result.inputs.fixed_bars
    perimeter = f"2 · h · (L + W)"
    if bars is None:
        formula = f"A_libre = {perimeter}"
        legend = "A_libre: área libre lateral; h: espesor; L y W: dimensiones en planta."
        substitution = (
            f"A_libre = 2 · {geom.thickness_cm:.2f} · ({geom.length_cm:.2f} + {geom.width_cm:.2f}) "
            f"= {result.free_area_cm2:.2f} cm²"
        )
    else:
        formula = f"A_libre = 2 · h · (L + W) + n · π · d · h"
        legend = (
            "A_libre: área libre para bulbo de compresión; incluye perímetro lateral "
            "y desarrollo alrededor de cada pasador."
        )
        substitution = (
            f"A_libre = 2 · {geom.thickness_cm:.2f} · ({geom.length_cm:.2f} + {geom.width_cm:.2f}) "
            f"+ {bars.n_bars} · π · {bars.diameter_cm:.2f} · {geom.thickness_cm:.2f} "
            f"= {result.free_area_cm2:.2f} cm²"
        )
    result_text = f"El área libre calculada es A_libre = {result.free_area_cm2:.2f} cm²."
    comment = "El factor de forma S relaciona el área efectiva con el área libre lateral."
    return formula, legend, substitution, result_text, comment


def shape_factor_trace(result: SimpleSupportResult) -> TraceTuple:
    formula = "S = A_eff / A_libre"
    legend = "S: factor de forma; A_eff: área neta; A_libre: área libre lateral."
    substitution = (
        f"S = {result.effective_area_cm2:.2f} / {result.free_area_cm2:.2f} "
        f"= {result.shape_factor:.3f}"
    )
    result_text = f"El factor de forma adoptado es S = {result.shape_factor:.3f}."
    comment = "AASHTO 14.7.5.1-1 para una sola capa de neopreno simple sin zunchos internos."
    return formula, legend, substitution, result_text, comment


def service_reaction_trace(result: SimpleSupportResult) -> TraceTuple:
    dem = result.inputs.demands
    formula = "R = R_DC + R_DW + R_PL + R_LL+IM"
    legend = (
        "R: reacción de servicio por apoyo; R_DC: carga permanente estructural; "
        "R_DW: superficie de rodadura; R_PL: peatonal; R_LL+IM: vehicular con impacto."
    )
    substitution = (
        f"R = {dem.r_dc_tn:.3f} + {dem.r_dw_tn:.3f} + {dem.r_pl_tn:.3f} + {dem.r_ll_im_tn:.3f} "
        f"= {dem.r_service_tn:.3f} Tn"
    )
    result_text = f"La reacción de servicio es R = {dem.r_service_tn:.3f} Tn."
    comment = "Las reacciones se introducen sin factor; los estados límite se aplican en cada verificación."
    return formula, legend, substitution, result_text, comment


def thermal_movement_trace(result: SimpleSupportResult) -> TraceTuple:
    dem = result.inputs.demands
    temp = dem.temperature
    delta_t = temp.contraction_delta_t_c if temp is not None else 0.0
    formula = "Δ_s = γ_TU · α · L · ΔT"
    legend = (
        "Δ_s: movimiento térmico de contracción; γ_TU: factor de temperatura; "
        "α: coeficiente de dilatación del concreto; L: luz del tramo; ΔT: T_inst − T_inf."
    )
    substitution = (
        f"ΔT = {temp.t_install_c:.1f} − {temp.t_inf_c:.1f} = {delta_t:.1f} °C\n"
        f"Δ_s = {dem.gamma_tu:.2f} · {dem.alpha_per_c:.8f} · {dem.span_length_m * 100:.1f} · {delta_t:.1f} "
        f"= {result.delta_thermal_cm:.3f} cm"
    )
    result_text = f"El movimiento térmico de contracción es Δ_s = {result.delta_thermal_cm:.3f} cm."
    comment = "El movimiento gobierna el corte del apoyo móvil y la verificación h ≥ 2·Δ_s."
    return formula, legend, substitution, result_text, comment


def horizontal_demand_trace(result: SimpleSupportResult) -> TraceTuple:
    dem = result.inputs.demands
    formula = "H = max(H_BR,RI ; H_EQ,EE-I)"
    legend = (
        f"H_BR,RI = {BRAKING_FACTOR_STRENGTH_I:.2f} · BR; "
        "H_EQ,EE-I = PGA · Fpga · (R_DC + R_DW); H: demanda horizontal de diseño del apoyo fijo."
    )
    substitution = (
        f"As = PGA · Fpga = {dem.pga:.3f} · {dem.fpga:.3f} = {dem.as_coeff:.3f}\n"
        f"H_BR,RI = {BRAKING_FACTOR_STRENGTH_I:.2f} · {dem.h_long_tn:.3f} = {dem.h_br_strength_tn:.3f} Tn\n"
        f"H_EQ,EE-I = {dem.as_coeff:.3f} · ({dem.r_dc_tn:.3f} + {dem.r_dw_tn:.3f}) = {dem.h_eq_long_tn:.3f} Tn\n"
        f"H = max({dem.h_br_strength_tn:.3f}, {dem.h_eq_long_tn:.3f}) = {result.h_design_tn:.3f} Tn"
    )
    result_text = (
        f"La demanda horizontal gobernante es H = {result.h_design_tn:.3f} Tn "
        f"({result.h_design_case})."
    )
    comment = "La demanda se reparte entre pasadores en el apoyo fijo con barras interiores."
    return formula, legend, substitution, result_text, comment


def pin_interaction_trace(result: SimpleSupportResult) -> TraceTuple:
    bars = result.inputs.fixed_bars
    assert bars is not None
    v_pin = result.h_design_tn / bars.n_bars
    m_pin = v_pin * 1000.0 * bars.moment_arm_cm
    flexure = 6.0 * m_pin / (PIN_PHI_FLEXURE * bars.diameter_cm**3 * bars.fy_kg_cm2)
    shear = (2.2 * v_pin * 1000.0 / (PIN_PHI_SHEAR * bars.diameter_cm**2 * bars.fy_kg_cm2)) ** 2
    interaction = flexure + shear
    formula = "6·Mu / (φ_f·D³·Fy) + [2.2·Vu / (φ_v·D²·Fy)]² ≤ 0.95"
    legend = (
        "Vu: corte por pasador; Mu: momento en la sección crítica; D: diámetro; "
        "Fy: fluencia ASTM A108 Gr. 1020; φ_f = φ_v = 1.00."
    )
    substitution = (
        f"Vu = H / n = {result.h_design_tn:.3f} / {bars.n_bars} = {v_pin:.3f} Tn\n"
        f"Mu = Vu · e = {v_pin * 1000:.1f} · {bars.moment_arm_cm:.2f} = {m_pin:.1f} kg·cm\n"
        f"Término flexión = {flexure:.3f}\n"
        f"Término corte = {shear:.3f}\n"
        f"Interacción = {flexure:.3f} + {shear:.3f} = {interaction:.3f}"
    )
    status = "CUMPLE" if interaction <= 0.95 else "NO CUMPLE"
    result_text = f"La interacción corte-flexión del pasador es I = {interaction:.3f} ≤ 0.95: {status}."
    comment = "AASHTO LRFD 6.13.1 evalúa Vu y Mu en la misma sección crítica del pasador liso."
    return formula, legend, substitution, result_text, comment


def h_pad_trace(result: SimpleSupportResult) -> TraceTuple:
    geom = result.inputs.geometry
    formula = "H_pad = G_max · A_g · Δ_s / h / 1000"
    legend = (
        "H_pad: fuerza horizontal por corte del neopreno; G_max: módulo máximo del elastómero; "
        "A_g: área bruta; Δ_s: movimiento; h: espesor total."
    )
    substitution = (
        f"H_pad = {result.g_max_kg_cm2:.2f} · {geom.gross_area_cm2:.1f} · {result.delta_thermal_cm:.3f} "
        f"/ {geom.thickness_cm:.2f} / 1000 = {result.h_pad_tn:.3f} Tn"
    )
    result_text = f"La fuerza horizontal por corte del pad es H_pad = {result.h_pad_tn:.3f} Tn."
    comment = "G_max maximiza la fuerza transferida al sistema de planchas y fricción."
    return formula, legend, substitution, result_text, comment


def modulus_trace(result: SimpleSupportResult) -> TraceTuple:
    formula = "σ_adm = min(G_min · S ; 0.80 ksi)"
    legend = (
        "G_min: módulo mínimo del elastómero para capacidad; G_max: módulo máximo para fuerza horizontal; "
        f"S: factor de forma; límite absoluto = {SIGMA_S_MAX_PEP_KG_CM2:.2f} kg/cm²."
    )
    substitution = (
        f"G_min = {result.g_min_kg_cm2:.2f} kg/cm² ({result.g_capacity_reason})\n"
        f"G_max = {result.g_max_kg_cm2:.2f} kg/cm² ({result.g_force_reason})\n"
        f"G_min · S = {result.g_min_kg_cm2:.2f} · {result.shape_factor:.3f} = {result.sigma_gs_kg_cm2:.2f} kg/cm²\n"
        f"σ_adm = min({result.sigma_gs_kg_cm2:.2f}, {SIGMA_S_MAX_PEP_KG_CM2:.2f}) = {result.sigma_adm_kg_cm2:.2f} kg/cm²"
    )
    result_text = f"El límite gobernante de compresión es σ_adm = {result.sigma_adm_kg_cm2:.2f} kg/cm²."
    comment = "Para neopreno simple sin zunchos no se usa 1.25·G·S ni 1.25 ksi."
    return formula, legend, substitution, result_text, comment


def _legend_for_check(name: str) -> str:
    legends = {
        "Compresion neopreno": "σ: esfuerzo de compresión; R: reacción de servicio; A_eff: área neta.",
        "Deflexion por compresion": "δ: deflexión total; ε: deformación unitaria; h: espesor del neopreno.",
        "Estabilidad h <= L/3": "h: espesor; L: largo en planta.",
        "Estabilidad h <= W/3": "h: espesor; W: ancho en planta.",
        "Aplastamiento concreto bajo apoyo": "φ = 0.70; f'c: resistencia del concreto del pedestal o estribo.",
        "Relacion de perforaciones": "Relación entre el área de huecos y el área bruta del neopreno.",
        "Area neta con perforaciones": "Verificación de que la perforación no elimina el área resistente.",
        "Borde de pasadores dentro del neopreno": "e: distancia del borde al eje del pasador; d: diámetro.",
        "Separacion de pasadores": "s: separación mínima entre ejes de pasadores; d: diámetro.",
        "Interaccion pasador corte-flexion": "Vu y Mu en la misma sección crítica del pasador liso.",
        "Cortante por movimiento termico": "Δ_s: movimiento térmico; h: espesor del neopreno.",
        "Deformacion angular del neopreno": "γ: deformación angular de corte; Δ_s: movimiento; h: espesor.",
        "Fuerza H_pad movil": "H_pad: fuerza horizontal por deformación de corte del elastómero.",
        "Friccion disponible": "μ: coeficiente de fricción; R_DC: reacción permanente estructural.",
        "Espesor planchas superior/inferior": "t: espesor mínimo constructivo de planchas ASTM A36.",
        "Compresion en planchas A36": "σ: esfuerzo de compresión en plancha; Fy: fluencia A36.",
    }
    return legends.get(name, "Parámetros definidos en la leyenda del apoyo de neopreno simple.")
