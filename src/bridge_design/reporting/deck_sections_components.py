"""Barrier, overhang, diaphragm and reaction report sections."""

from __future__ import annotations

from reportlab.platypus import Spacer
from reportlab.lib.units import mm

from bridge_design.domain.diaphragm import combine_diaphragm_moments
from bridge_design.reporting.deck_charts import moment_shear_pair
from bridge_design.reporting.models import DeckReportData, selected_option
from bridge_design.reporting.pdf_style import data_table, formula_card, p


def barrier_story(data: DeckReportData, styles) -> list:
    result = data.barrier_result
    flexure = result.flexure
    yield_line = result.yield_line
    shear = result.shear_transfer
    development = result.development
    return [
        p("5. Barrera de concreto", styles["h1"]),
        p(
            "La resistencia transversal se evalua mediante un mecanismo de lineas de fluencia. "
            "La fuerza de impacto se distribuye en la longitud critica y se verifican flexion, "
            "transferencia por friccion-cortante, acero de conexion y anclaje del dowel.",
            styles["body"],
        ),
        formula_card(
            "Longitud critica y resistencia transversal",
            "Lc = Lt/2 + sqrt[(Lt/2)^2 + 8H(Mb+Mw)/Mc]; Rw = 2[8Mb+8Mw+Mc Lc^2/H]/(2Lc-Lt)",
            "H: altura; Lt: longitud de distribucion; Mb: momento adicional superior; Mw y Mc: resistencias longitudinal y transversal.",
            f"Mw={flexure.mw_tn_m:.3f} Tn.m; Mc={flexure.mc_tn_m:.3f} Tn.m; Lc={yield_line.critical_length_m:.3f} m",
            f"Rw={yield_line.nominal_transverse_resistance_tn:.3f} Tn >= Ft={yield_line.demand_transverse_force_tn:.3f} Tn: {yield_line.resistance_status}",
            f"Patron de impacto adoptado: {yield_line.impact_pattern}; se usa el mecanismo interior por segmentos cuando no hay extremo o junta.",
            "MTC 2018 / AASHTO LRFD 13.7.3, metodo de lineas de fluencia.",
            styles,
        ),
        formula_card(
            "Transferencia en la junta barrera-losa",
            "Vn = c Acv + mu(Avf fy + Pc), limitado por la resistencia maxima de la interfaz",
            "c y mu: cohesion y friccion; Acv: area de contacto; Avf: acero que cruza la interfaz; Pc: compresion permanente.",
            f"Vu={shear.acting_shear_tn_m:.3f} Tn/m; Acv={shear.contact_area_cm2_m:.1f} cm2/m; Avf={shear.provided_avf_cm2_m:.3f} cm2/m",
            f"Vn bruto={shear.nominal_shear_raw_tn_m:.3f}; limite={shear.nominal_shear_limit_tn_m:.3f}; Vn={shear.nominal_shear_tn_m:.3f} Tn/m: {shear.status}",
            "Se adopta el menor entre la expresion de friccion-cortante y el limite superior de la interfaz.",
            "MTC 2018 / AASHTO LRFD 5.8.4.",
            styles,
        ),
        formula_card(
            "Desarrollo del dowel",
            "ldh,req = max(lhb * factores * As,req/As,prov, ldh,min)",
            "lhb: longitud basica de gancho; los factores consideran recubrimiento, confinamiento y exceso de acero.",
            f"lhb={development.basic_lhb_cm:.2f} cm; factor exceso={development.excess_reinforcement_factor:.3f}; ldh mod={development.modified_ldh_cm:.2f} cm",
            f"ldh req={development.required_ldh_cm:.2f} cm <= disponible={development.available_length_cm:.2f} cm: {development.status}",
            "La longitud disponible se mide en la geometria real de la barrera y la losa.",
            "MTC 2018 2.9.11 / AASHTO LRFD 5.11.2.",
            styles,
        ),
    ]


def cantilever_story(data: DeckReportData, styles) -> list:
    result = data.cantilever_result
    steel = result.flexural_steel
    shear = result.shear
    crack = result.crack_control
    development = result.development
    adopted = selected_option(data.cantilever_selected, "A.")
    adopted_text = (
        f"{adopted.bar.label} @ {adopted.spacing_m:.3f} m, As prov={adopted.provided_area_cm2_m:.3f} cm2/m"
        if adopted is not None else "opcion recomendada"
    )
    combination = result.controlling_strength
    story = [
        p("6. Losa en voladizo", styles["h1"]),
        p(
            "El voladizo se verifica en la raiz, medida en el eje de la viga exterior. Se incluyen "
            "peso propio, vereda, baranda, barrera, superficie, peatones y la cuchilla vehicular "
            "cuando su posicion es aplicable. La colision se revisa como Evento Extremo II.",
            styles["body"],
        ),
        formula_card(
            "Momento de cada carga en la raiz",
            "M_raiz = integral[q(x)(x-xr) dx] + sum[P_i(x_i-xr)]",
            "q: carga distribuida; P_i: carga concentrada equivalente; xr: eje de la viga exterior.",
            f"Cara de trafico={result.traffic_face_from_edge_m:.3f} m; linea vehicular={result.vehicular_line_from_edge_m:.3f} m",
            f"Combinacion controlante={combination.combination_name}; Mu={combination.combined_moment_tn_m:.3f} Tn.m/m",
            "Los momentos negativos representan traccion superior en la raiz del voladizo.",
            "MTC 2018 / AASHTO LRFD 3.6.1.3.4 y Tabla 3.4.1-1.",
            styles,
        ),
        formula_card(
            "Acero superior del voladizo",
            "phi As fy[d-As fy/(2*0.85 f'c b)] >= |Mu|; As,req=max(As,flex,As,min)",
            "b=100 cm por franja; d: peralte efectivo; Mu incluye la condicion controlante aplicable.",
            f"Mu={steel.design_moment_tn_m:.3f} Tn.m/m; d={steel.effective_depth_cm:.2f} cm",
            f"As flex={steel.strength_area_cm2_m:.3f}; As min={steel.minimum_area_cm2_m:.3f}; As req={steel.required_area_cm2_m:.3f} cm2/m; adoptado: {adopted_text}",
            "Si Evento Extremo II gobierna, el acero se dimensiona con ese momento en lugar de Resistencia I.",
            steel.reference,
            styles,
        ),
        formula_card(
            "Cortante en la raiz del voladizo",
            "Vu = 1.25VDC + 1.50VDW + 1.75VPL + 1.75VLL+IM; phi Vc >= Vu",
            "Los efectos se obtienen por equilibrio de todas las cargas situadas fuera de la seccion de raiz.",
            f"Vu={shear.combined_shear_tn:.3f} Tn/m; dv={shear.effective_shear_depth_cm:.2f} cm; Vc={shear.vc_tn:.3f} Tn/m",
            f"phi Vc={shear.phi_vc_tn:.3f} Tn/m: {shear.status}",
            "Se verifica como cortante unidireccional sin aporte de acero transversal de la losa.",
            shear.reference,
            styles,
        ),
        formula_card(
            "Servicio, fisuracion y desarrollo",
            "fs = Ms/(As z); s_prov <= s_max; Lbarra = Lproyeccion + ld",
            "z: brazo interno; s_max: limite de fisuracion; ld: longitud de desarrollo reducida por exceso de acero cuando corresponde.",
            f"Ms={crack.service_moment_tn_m:.3f} Tn.m; fs={crack.steel_stress_kg_cm2:.1f} kg/cm2; s prov={crack.provided_spacing_m:.3f} m; s max={crack.maximum_spacing_m:.3f} m",
            f"Fisuracion={crack.status}; ld req={development.required_development_length_cm:.2f} cm; L barra adicional={development.total_additional_bar_length_m:.3f} m: {development.status}",
            "La barra se prolonga mas alla del corte teorico al menos la extension constructiva reglamentaria.",
            development.reference,
            styles,
        ),
    ]
    if result.barrier_collision is not None:
        collision = result.barrier_collision
        story.append(formula_card(
            "Colision de barrera transmitida al voladizo",
            "M_EEII = M_colision + gamma_p M_permanente; M_colision = Ft H/Lt",
            "Ft: fuerza transversal; H: brazo; Lt: longitud efectiva de transferencia.",
            f"Ft={collision.transverse_force_tn:.3f} Tn; H={collision.barrier_height_m:.3f} m; Lt={collision.transfer_length_m:.3f} m",
            f"M colision={collision.collision_moment_tn_m:.3f}; Mu EEII={collision.design_moment_tn_m:.3f} Tn.m/m",
            "La accion horizontal de colision no se combina con la sobrecarga vehicular vertical ordinaria.",
            collision.reference,
            styles,
        ))
    return story


def diaphragm_story(data: DeckReportData, styles) -> list:
    result = data.diaphragm_result
    reinforcement = data.diaphragm_reinforcement
    rows = combine_diaphragm_moments(result)
    strength = [row for row in rows if row.combination_name == "RESISTENCIA I"]
    positive = max((row for row in strength if row.direction == "M+"), key=lambda row: row.combined_moment_tn_m)
    negative = min((row for row in strength if row.direction == "M-"), key=lambda row: row.combined_moment_tn_m)
    story = [
        p("7. Diafragmas", styles["h1"]),
        p(
            "El diafragma se analiza transversalmente entre vigas con voladizos extremos. Las "
            "cargas permanentes y peatonales actuan en su ubicacion fisica; las ruedas se desplazan "
            "en ambos sentidos, de izquierda a derecha y de derecha a izquierda, invirtiendo "
            "fisicamente su disposicion transversal dentro del carril. Cada posicion se resuelve "
            "estructuralmente y se adopta la envolvente de uno o dos carriles que controla cada "
            "estacion; no se refleja artificialmente el resultado grafico.",
            styles["body"],
        ),
        formula_card(
            "Envolvente de momentos del diafragma",
            "Mu(x)=1.25MDC(x)+1.50MDW(x)+1.75MPL(x)+1.75MLL+IM(x)",
            "Todos los efectos se combinan en la misma estacion x; se forman envolventes positiva y negativa.",
            f"M+ en x={positive.position_m:.3f} m; M- en x={negative.position_m:.3f} m",
            f"Mu+={positive.combined_moment_tn_m:.3f} Tn.m; Mu-={negative.combined_moment_tn_m:.3f} Tn.m",
            "Se dimensiona acero independiente para traccion inferior y superior.",
            "MTC 2018 Tabla 2.4.5.3.1-1; AASHTO LRFD Tabla 3.4.1-1.",
            styles,
        ),
    ]
    story.extend(moment_shear_pair(result, title="Diafragma", include_pl=True, transverse=True))
    story.append(p("Figura 7.1. Envolventes factorizadas empleadas en el diseno del diafragma.", styles["caption"]))
    story.extend([
        formula_card(
            "Acero a flexion del diafragma",
            "phi As fy[d-As fy/(2*0.85 f'c b)] >= |Mu|",
            "b: espesor longitudinal del diafragma; d: peralte efectivo; se verifica acero minimo.",
            f"M+={reinforcement.positive.design_moment_tn_m:.3f}; M-={reinforcement.negative.design_moment_tn_m:.3f} Tn.m; d={reinforcement.positive.effective_depth_cm:.2f} cm",
            f"As+ req={reinforcement.positive.required_area_cm2:.3f}; As- req={reinforcement.negative.required_area_cm2:.3f} cm2",
            "Se conservan barras continuas y se detallan ambas caras según el signo de la envolvente.",
            "MTC 2018 2.9.4.2; AASHTO LRFD 5.7.3.",
            styles,
        ),
        formula_card(
            "Cortante del diafragma",
            "phi(Vc+Vs) >= Vu; Vs = Av fy dv/s",
            "Vu es la maxima envolvente absoluta de Resistencia I; Av/s se compara con el minimo.",
            f"Vu={reinforcement.shear.controlling_shear.combined_shear_tn:.3f} Tn; Vc={reinforcement.shear.vc_tn:.3f} Tn; dv={reinforcement.shear.effective_shear_depth_cm:.2f} cm",
            f"Av/s req={reinforcement.shear.required_av_cm2_m:.3f} cm2/m; s max={reinforcement.shear.maximum_spacing_m:.3f} m",
            "Los estribos se eligen en la grilla del proyecto y su separacion se redondea hacia abajo.",
            "MTC 2018 2.9.5; AASHTO LRFD 5.8.",
            styles,
        ),
    ])
    return story


def reactions_story(data: DeckReportData, styles) -> list:
    gcount = data.project_inputs.interior_girder.girder_count
    width = data.project_inputs.transverse_slab.geometry.total_width_m
    interior_count = max(gcount - 2, 0)
    cases = (
        ("PDC", data.interior_result.dc, data.exterior_result.dc),
        ("PDW", data.interior_result.dw, data.exterior_result.dw),
        ("PPL", None, data.exterior_result.pl),
        ("PLL+IM", data.interior_result.ll_im_envelope, data.exterior_result.ll_im_envelope),
    )
    rows = []
    for label, interior, exterior in cases:
        ri = _maximum_reaction(interior) if interior is not None else 0.0
        re = _maximum_reaction(exterior)
        total = interior_count * ri + 2 * re
        rows.append((label, f"{ri:.3f}", f"{re:.3f}", f"{total:.3f}", f"{total / width:.3f}"))
    return [
        p("8. Reacciones para apoyos y estribos", styles["h1"]),
        p(
            "Las reacciones se reportan sin factor para que los modulos de apoyos y estribos "
            "apliquen la combinacion correspondiente. Se suman dos vigas exteriores y las vigas "
            "interiores restantes; luego se divide entre el ancho del estribo.",
            styles["body"],
        ),
        formula_card(
            "Carga lineal transferida al estribo",
            "P_lineal = [n_i R_i + 2 R_e]/B",
            "n_i: numero de vigas interiores; Ri y Re: reacciones por viga; B: ancho total del tablero.",
            f"n_i={interior_count}; B={width:.3f} m; numero total de vigas={gcount}",
            "Valores por caso en la tabla siguiente, expresados en Tn/m.",
            "PL se conserva separado de LL+IM; no se aplica impacto a la carga peatonal.",
            "Transferencia de acciones sin factor hacia el diseno de la subestructura.",
            styles,
        ),
        data_table(
            ("Caso", "R interior", "R exterior", "Total", "Tn/m"),
            rows,
            [25 * mm, 33 * mm, 33 * mm, 35 * mm, 30 * mm],
            styles,
        ),
        Spacer(1, 3 * mm),
        p(
            "Conclusión: el reporte conserva las acciones por naturaleza de carga. La adopcion "
            "definitiva del apoyo y del estribo debe realizarse en sus comandos especializados.",
            styles["body"],
        ),
    ]


def _maximum_reaction(case) -> float:
    """Return the largest reaction from scalar or (position, reaction) storage."""
    values = case.support_reactions_tn
    if values and isinstance(values[0], tuple):
        return max(value for _, value in values)
    return max(values)
