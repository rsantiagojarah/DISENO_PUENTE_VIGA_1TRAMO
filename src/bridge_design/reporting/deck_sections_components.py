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
            "peso propio, vereda, baranda, barrera, superficie y peatones. La cuchilla vehicular "
            "solo se incluye cuando queda sobre el voladizo y cumple su limite de aplicacion; "
            "si queda hacia el interior de la viga, las ruedas se consideran en el analisis "
            "transversal de la losa. La colision se revisa como Evento Extremo II.",
            styles["body"],
        ),
        formula_card(
            "Momento de cada carga en la raiz",
            "M_raiz = integral[q(x)(x-xr) dx] + sum[P_i(x_i-xr)]",
            "q: carga distribuida; P_i: carga concentrada equivalente; xr: eje de la viga exterior.",
            f"Cara de trafico={result.traffic_face_from_edge_m:.3f} m; linea vehicular={result.vehicular_line_from_edge_m:.3f} m; D cara-viga={result.traffic_face_to_exterior_girder_m:.3f} m",
            f"Combinacion controlante={combination.combination_name}; Mu={combination.combined_moment_tn_m:.3f} Tn.m/m",
            f"Metodo vehicular: {result.vehicular_load_method}. Los momentos negativos representan traccion superior en la raiz del voladizo.",
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
    story.extend(p(note, styles["body"]) for note in result.applicability_notes)
    if result.barrier_collision is not None:
        collision = result.barrier_collision
        story.append(formula_card(
            "Colision de barrera transmitida al voladizo",
            "N = max(Ft,Rw)/(Lc+2H); M_colision = max(Mc,N H); As = As(M)+N/(phi fy)",
            "Ft: fuerza transversal; H: brazo; Lt: longitud efectiva de transferencia.",
            f"Ft={collision.transverse_force_tn:.3f} Tn; H={collision.barrier_height_m:.3f} m; Lt={collision.transfer_length_m:.3f} m",
            f"M colision={collision.collision_moment_tn_m:.3f}; Mu EEII={collision.design_moment_tn_m:.3f} Tn.m/m",
            f"N simultanea={collision.axial_tension_tn_m:.3f} Tn/m. {collision.status}: {collision.scope_note}",
            collision.reference,
            styles,
        ))
        story.append(data_table(
            ("Caso", "M Tn.m/m", "N Tn/m", "V Tn/m", "Estado"),
            tuple((case.name, f"{case.moment_tn_m:.3f}", f"{case.axial_tension_tn_m:.3f}", f"{case.vertical_force_tn_m:.3f}", case.status) for case in collision.cases),
            [57 * mm, 27 * mm, 27 * mm, 27 * mm, 25 * mm], styles,
        ))
    elif result.interior_collision is not None:
        story.extend(_interior_collision_story(result.interior_collision, styles))
    return story


def _interior_collision_story(collision, styles) -> list:
    story = [
        p("Transferencia de colision a la losa interior", styles["h2"]),
        formula_card(
            "Demanda transmitida por la barrera",
            "F=max(Ft,Rw); L=Lc+2H; N=F/L; Minterfaz=Mc max(1,Ft/Rw)",
            "Ft: fuerza de ensayo; Rw: resistencia de lineas de fluencia; N: traccion por metro.",
            f"F={collision.horizontal_force_tn:.3f} Tn; L={collision.transfer_length_m:.3f} m; "
            f"N={collision.horizontal_force_tn/collision.transfer_length_m:.3f} Tn/m",
            f"Minterfaz={collision.interface_moment_tn_m_m:.3f} Tn.m/m",
            "Las acciones horizontal y vertical se analizan independientemente en ambos bordes de las dos barreras.",
            "MTC 2018 2.4.3.5.1.2, Tabla 2.4.3.6.3-1 y 2.4.5.3.",
            styles,
        ),
        data_table(
            ("Caso independiente", "x", "M", "Fv", "N"),
            tuple(
                (
                    case.name,
                    f"{case.position_m:.3f}",
                    f"{case.applied_moment_tn_m_m:.3f}",
                    f"{case.applied_vertical_tn_m:.3f}",
                    f"{case.axial_tension_tn_m:.3f}",
                )
                for case in collision.cases
            ),
            [74 * mm, 21 * mm, 25 * mm, 25 * mm, 25 * mm],
            styles,
        ),
    ]
    reaction_headers = (
        "Caso",
        *(label for label, _ in collision.cases[0].reactions_tn_m),
        "Err F",
        "Err M",
    )
    reaction_width = 112 * mm / (len(reaction_headers) - 1)
    story.append(
        data_table(
            reaction_headers,
            tuple(
                (
                    case.name,
                    *(f"{reaction:.3f}" for _, reaction in case.reactions_tn_m),
                    f"{case.vertical_equilibrium_error_tn_m:.1e}",
                    f"{case.moment_equilibrium_error_tn_m_m:.1e}",
                )
                for case in collision.cases
            ),
            [58 * mm] + [reaction_width] * (len(reaction_headers) - 1),
            styles,
        )
    )
    story.extend(
        [
            p("Acero transversal requerido por colision", styles["h2"]),
            data_table(
                ("Cara", "Caso gobernante", "x", "M", "N", "gDC", "gDW"),
                tuple(
                    (
                        face.face,
                        face.case_name,
                        f"{face.position_m:.3f}",
                        f"{face.moment_tn_m_m:.3f}",
                        f"{face.tension_tn_m:.3f}",
                        f"{face.dc_factor:.2f}",
                        f"{face.dw_factor:.2f}",
                    )
                    for face in collision.faces
                ),
                [20 * mm, 62 * mm, 18 * mm, 20 * mm, 20 * mm, 15 * mm, 15 * mm],
                styles,
            ),
            data_table(
                ("Cara", "As req", "Acero", "As prov", "ld req", "ld disp", "Estado"),
                tuple(
                    (
                        face.face,
                        f"{face.option.required_area_cm2_m:.3f}" if face.option else "-",
                        f"{face.option.bar.label} @ {face.option.spacing_m:.3f} m" if face.option else "Sin opcion",
                        f"{face.option.provided_area_cm2_m:.3f}" if face.option else "-",
                        f"{face.development_length_m:.3f} m",
                        f"{face.development_available_m:.3f} m",
                        face.status,
                    )
                    for face in collision.faces
                ),
                [20 * mm, 22 * mm, 37 * mm, 23 * mm, 24 * mm, 24 * mm, 20 * mm],
                styles,
            ),
            formula_card(
                "Cortante de la franja interior",
                "phi Vc = phi 0.265 beta sqrt(f'c) b dv",
                "beta: factor general con traccion; b=100 cm; dv: peralte efectivo de corte.",
                f"Vu={collision.shear_demand_tn_m:.3f} Tn/m; beta={collision.shear_beta:.3f}",
                f"phi Vc={collision.shear_capacity_tn_m:.3f} Tn/m: {collision.shear_status}",
                "La comprobacion corresponde a cortante sin estribos en la franja local.",
                "Manual de Puentes MTC 2018, Art. 2.9.1.5.6.",
                styles,
            ),
            data_table(
                ("Control de conexion", "Demanda", "Capacidad", "Estado"),
                tuple(
                    (
                        check.control,
                        f"{check.demand:.3f} {check.unit}",
                        f"{check.capacity:.3f} {check.unit}",
                        check.status,
                    )
                    for check in collision.connection_checks
                ),
                [65 * mm, 38 * mm, 42 * mm, 25 * mm],
                styles,
            ),
            p(
                f"Resultado local: {collision.status}. Conexion barrera-losa: "
                f"{collision.connection_status}.",
                styles["h2"],
            ),
        ]
    )
    story.extend(p(note, styles["small"]) for note in collision.notes)
    return story


def diaphragm_story(data: DeckReportData, styles) -> list:
    geometry = data.project_inputs.diaphragm
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
            "alturas ingresadas corresponden al concreto bajo la losa y el peralte resistente "
            "incluye el espesor de la losa monolitica. Las "
            "cargas permanentes y peatonales actuan en su ubicacion fisica; las ruedas se desplazan "
            "en ambos sentidos, de izquierda a derecha y de derecha a izquierda, invirtiendo "
            "fisicamente su disposicion transversal dentro del carril. Cada posicion se resuelve "
            "estructuralmente y se adopta la envolvente de uno o dos carriles que controla cada "
            "estacion; no se refleja artificialmente el resultado grafico.",
            styles["body"],
        ),
        formula_card(
            "Peralte resistente del diafragma",
            "h=hbajo+tlosa; d=h-rec-db/2",
            "hbajo: altura bajo la losa; tlosa: espesor de losa; d: peralte efectivo inicial.",
            f"h={geometry.height_m:.3f}+{geometry.slab_thickness_m:.3f}="
            f"{geometry.total_depth_m:.3f} m",
            f"b={geometry.thickness_m:.3f} m; d adoptado="
            f"{reinforcement.positive.effective_depth_cm:.2f} cm",
            "El peso adicional usa hbajo y la losa se contabiliza separadamente.",
            "Convencion geometrica del modelo de diafragma monolitico.",
            styles,
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
    story.append(
        formula_card(
            "Acero a flexion del diafragma",
            "phi As fy[d-As fy/(2*0.85 f'c b)] >= |Mu|",
            "b: espesor longitudinal del diafragma; d: peralte efectivo; se verifica acero minimo.",
            f"M+={reinforcement.positive.design_moment_tn_m:.3f}; M-={reinforcement.negative.design_moment_tn_m:.3f} Tn.m; d={reinforcement.positive.effective_depth_cm:.2f} cm",
            f"As+ req={reinforcement.positive.required_area_cm2:.3f}; As- req={reinforcement.negative.required_area_cm2:.3f} cm2",
            "Se conservan barras continuas y se detallan ambas caras según el signo de la envolvente.",
            "MTC 2018 2.9.4.2; AASHTO LRFD 5.7.3.",
            styles,
        )
    )
    if reinforcement.skin.required_area_cm2_m_per_face > 0.0:
        story.append(
            formula_card(
                "Acero longitudinal superficial Ask del diafragma",
                "s <= min(dl/6, 300 mm); Ask por cara segun d_l y As/flexion",
                "Se exige cuando d_l > 900 mm y se distribuye en ambas caras dentro de d_l/2 desde la cara traccionada.",
                f"d_l={reinforcement.skin.effective_depth_cm:.2f} cm; "
                f"d_l/2={reinforcement.skin.distribution_height_m:.3f} m; "
                f"s max={reinforcement.skin.maximum_spacing_m:.3f} m",
                f"Ask req={reinforcement.skin.required_area_cm2_m_per_face:.3f} cm2/m por cara",
                "La armadura principal lateral solo se cuenta como Ask si se verifica explicitamente su ubicacion y compatibilidad.",
                "MTC 2018 Art. 2.9.1.4.4.3; AASHTO LRFD 5.7.3.4.",
                styles,
            )
        )
    else:
        story.append(
            p(
                f"Ask del diafragma: NO APLICA porque d_l="
                f"{reinforcement.skin.effective_depth_cm:.2f} cm <= 90.00 cm. "
                "El acero lateral por temperatura se verifica independientemente.",
                styles["body"],
            )
        )
    story.append(
        formula_card(
            "Cortante del diafragma",
            "phi(Vc+Vs) >= Vu; Vs = Av fy dv/s",
            "Vu es la maxima envolvente absoluta de Resistencia I; Av/s se compara con el minimo.",
            f"Vu={reinforcement.shear.controlling_shear.combined_shear_tn:.3f} Tn; Vc={reinforcement.shear.vc_tn:.3f} Tn; dv={reinforcement.shear.effective_shear_depth_cm:.2f} cm",
            f"Av/s req={reinforcement.shear.required_av_cm2_m:.3f} cm2/m; s max={reinforcement.shear.maximum_spacing_m:.3f} m",
            "Los estribos se eligen en la grilla del proyecto y su separacion se redondea hacia abajo.",
            "MTC 2018 2.9.5; AASHTO LRFD 5.8.",
            styles,
        )
    )
    return story


def reactions_story(data: DeckReportData, styles) -> list:
    from bridge_design.domain.global_reactions import project_live_reaction_cases
    gcount = data.project_inputs.interior_girder.girder_count
    width = data.project_inputs.transverse_slab.geometry.total_width_m
    interior_count = max(gcount - 2, 0)
    cases = (
        ("PDC", data.interior_result.dc, data.exterior_result.dc),
        ("PDW", data.interior_result.dw, data.exterior_result.dw),
        ("PPL", None, data.exterior_result.pl),
    )
    rows = []
    for label, interior, exterior in cases:
        ri = _maximum_reaction(interior) if interior is not None else 0.0
        re = _maximum_reaction(exterior)
        total = interior_count * ri + 2 * re
        rows.append((label, f"{ri:.3f}", f"{re:.3f}", f"{total:.3f}", f"{total / width:.3f}"))
    live_cases = project_live_reaction_cases(data.project_inputs)
    live_left = max(row.left_tn for row in live_cases)
    live_right = max(row.right_tn for row in live_cases)
    local_live_interior = _maximum_reaction(data.interior_result.ll_im_envelope)
    local_live_exterior = _maximum_reaction(data.exterior_result.ll_im_envelope)
    rows.append(
        (
            "PLL+IM local máx.",
            f"{local_live_interior:.3f}",
            f"{local_live_exterior:.3f}",
            "No sumar",
            "—",
        )
    )
    rows.append(("PLL+IM global", "—", "—", f"{live_left:.3f}", f"{live_left / width:.3f}"))
    dc_pair = _global_pair(data.interior_result.dc, data.exterior_result.dc, interior_count)
    dw_pair = _global_pair(data.interior_result.dw, data.exterior_result.dw, interior_count)
    pl_ext = _support_pair(data.exterior_result.pl)
    pl_pair = (2 * pl_ext[0], 2 * pl_ext[1])
    service_pair = tuple(sum(values) for values in (dc_pair, dw_pair, pl_pair, (live_left, live_right)))
    strength_pair = tuple(1.25 * dc_pair[i] + 1.50 * dw_pair[i] + 1.75 * pl_pair[i] + 1.75 * (live_left, live_right)[i] for i in (0, 1))
    return [
        p("8. Reacciones por viga para apoyos y cargas globales para estribos", styles["h1"]),
        p(
            "Las reacciones máximas locales por viga sirven para los apoyos. En LL+IM cada extremo "
            "se maximiza independientemente con IM y gV; por simetría ambos extremos tienen la misma "
            "envolvente, aunque corresponden a posiciones vehiculares reflejadas. Para el estribo se "
            "usan las filas globales de servicio y Resistencia I, obtenidas por equilibrio global.",
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
        data_table(
            ("Carga global para estribo", "R fijo", "R movil", "q fijo", "q movil"),
            [
                ("DC", f"{dc_pair[0]:.3f}", f"{dc_pair[1]:.3f}", f"{dc_pair[0] / width:.3f}", f"{dc_pair[1] / width:.3f}"),
                ("DW", f"{dw_pair[0]:.3f}", f"{dw_pair[1]:.3f}", f"{dw_pair[0] / width:.3f}", f"{dw_pair[1] / width:.3f}"),
                ("PL", f"{pl_pair[0]:.3f}", f"{pl_pair[1]:.3f}", f"{pl_pair[0] / width:.3f}", f"{pl_pair[1] / width:.3f}"),
                ("LL+IM", f"{live_left:.3f}", f"{live_right:.3f}", f"{live_left / width:.3f}", f"{live_right / width:.3f}"),
                ("Servicio I", f"{service_pair[0]:.3f}", f"{service_pair[1]:.3f}", f"{service_pair[0] / width:.3f}", f"{service_pair[1] / width:.3f}"),
                ("Resistencia I", f"{strength_pair[0]:.3f}", f"{strength_pair[1]:.3f}", "—", "—"),
            ],
            [38 * mm, 29 * mm, 29 * mm, 30 * mm, 30 * mm],
            styles,
        ),
        Spacer(1, 3 * mm),
        data_table(("Caso HL-93", "R fijo", "R movil", "Carga total"),
                   [(row.name, f"{row.left_tn:.3f}", f"{row.right_tn:.3f}", f"{row.total_load_tn:.3f}") for row in live_cases],
                   [66 * mm, 30 * mm, 30 * mm, 30 * mm], styles),
        p(
            "Conclusión: la tabla por viga se usa para apoyos y la tabla global de servicio y "
            "Resistencia I se usa para el diseño del estribo. Las máximas LL+IM locales no se suman "
            "entre vigas porque no corresponden a un único posicionamiento simultáneo.",
            styles["body"],
        ),
    ]


def _maximum_reaction(case) -> float:
    """Return the largest reaction from scalar or (position, reaction) storage."""
    values = case.maximum_support_reactions_tn or case.support_reactions_tn
    if values and isinstance(values[0], tuple):
        return max(value for _, value in values)
    return max(values)


def _support_pair(case) -> tuple[float, float]:
    values = case.support_reactions_tn
    if values and isinstance(values[0], tuple):
        return float(values[0][1]), float(values[-1][1])
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return float(values[0]), float(values[0])
    return float(values[0]), float(values[-1])


def _global_pair(interior_case, exterior_case, interior_count: int) -> tuple[float, float]:
    interior = _support_pair(interior_case)
    exterior = _support_pair(exterior_case)
    return interior_count * interior[0] + 2 * exterior[0], interior_count * interior[1] + 2 * exterior[1]
