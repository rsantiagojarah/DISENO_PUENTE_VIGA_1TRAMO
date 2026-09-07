"""Cover, inputs, slab and longitudinal-girder report sections."""

from __future__ import annotations

from datetime import datetime

from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Spacer

from bridge_design.domain.exterior_girder import combine_exterior_girder_moments
from bridge_design.domain.interior_girder import combine_interior_girder_moments
from bridge_design.domain.load_combinations import combine_transverse_slab_moments
from bridge_design.reporting.deck_charts import moment_shear_pair
from bridge_design.reporting.models import DeckReportData, selected_option
from bridge_design.reporting.pdf_style import data_table, formula_card, p


def cover_story(data: DeckReportData, styles) -> list:
    geometry = data.project_inputs.transverse_slab.geometry
    return [
        Spacer(1, 31 * mm),
        p("MEMORIA DE CALCULO", styles["cover_subtitle"]),
        p("DISENO ESTRUCTURAL DEL TABLERO", styles["cover_title"]),
        p("Puente de concreto armado tipo viga-losa de un tramo", styles["cover_subtitle"]),
        Spacer(1, 18 * mm),
        data_table(
            ("Parametro", "Valor adoptado"),
            [
                ("Luz del puente", f"{data.project_inputs.interior_girder.span_length_m:.3f} m"),
                ("Ancho total", f"{geometry.total_width_m:.3f} m"),
                ("Numero de vigas", geometry.girder_count),
                ("Separacion entre vigas", f"{geometry.girder_spacing_m:.3f} m"),
                ("Normativa base", "Manual de Puentes MTC 2018 / AASHTO LRFD"),
                ("Fecha de emision", datetime.now().strftime("%d/%m/%Y %H:%M")),
            ],
            [57 * mm, 113 * mm],
            styles,
        ),
        Spacer(1, 32 * mm),
        p(
            "Documento generado automaticamente con los valores adoptados durante la ejecucion. "
            "Las sustituciones numericas y verificaciones corresponden a esta corrida de calculo.",
            styles["small"],
        ),
        PageBreak(),
    ]


def input_story(data: DeckReportData, styles) -> list:
    inputs = data.project_inputs
    g = inputs.transverse_slab.geometry
    c = inputs.materials.concrete
    v = inputs.live_loads.vehicular
    story = [
        p("1. Alcance, criterios y datos de entrada", styles["h1"]),
        p(
            "El tablero se modela con losa transversal continua sobre las vigas principales, "
            "vigas longitudinales simplemente apoyadas, barreras de concreto, voladizos y "
            "diafragmas. Los calculos usan Tn, m, cm y kg/cm2, con conversion explicita cuando "
            "la ecuacion normativa esta expresada en unidades inglesas.",
            styles["body"],
        ),
        p("1.1 Geometria y materiales adoptados", styles["h2"]),
        data_table(
            ("Magnitud", "Valor", "Uso"),
            [
                ("Espesor de losa", f"{g.slab_thickness_m:.3f} m", "Peso propio y seccion resistente"),
                ("Altura de viga", f"{g.girder_total_height_m:.3f} m", "Rigidez y seccion T"),
                ("Ancho de alma", f"{g.girder_width_m:.3f} m", "Flexion y cortante"),
                ("f'c", f"{c.compressive_strength_kg_cm2:.1f} kg/cm2", "Resistencia del concreto"),
                ("Ec", f"{c.elastic_modulus_kg_cm2:.1f} kg/cm2", "Rigidez EI"),
                ("fy", f"{inputs.materials.steel.yield_strength_kg_cm2:.1f} kg/cm2", "Acero de refuerzo"),
                ("Vehiculo", v.name, "Envolvente LL+IM"),
            ],
            [43 * mm, 42 * mm, 85 * mm],
            styles,
        ),
        Spacer(1, 3 * mm),
        formula_card(
            "Modulo de elasticidad del concreto",
            "Ec = 120000 K1 wc^2 (f'c)^0.33",
            "K1: factor de agregado; wc: peso unitario en kcf; f'c y Ec: ksi.",
            f"K1={c.aggregate_correction_factor:.3f}; wc={c.specific_weight_tn_m3:.3f} Tn/m3; f'c={c.compressive_strength_kg_cm2:.1f} kg/cm2",
            f"Ec={c.elastic_modulus_kg_cm2:.1f} kg/cm2",
            "Se verifica el rango de densidad y resistencia antes de efectuar la conversion.",
            "MTC 2018, Art. 2.5.4.4; AASHTO LRFD 5.4.2.4.",
            styles,
        ),
    ]
    return story


def slab_story(data: DeckReportData, styles) -> list:
    result = data.transverse_result
    reinforcement = data.slab_reinforcement
    materials = data.project_inputs.materials
    rows = combine_transverse_slab_moments(result)
    strength = [row for row in rows if row.combination_name == "RESISTENCIA I"]
    positive = max((row for row in strength if row.direction == "M+"), key=lambda row: row.combined_moment_tn_m)
    negative = min((row for row in strength if row.direction == "M-"), key=lambda row: row.combined_moment_tn_m)
    selected_negative = selected_option(data.slab_selected, "A.")
    selected_positive = selected_option(data.slab_selected, "B.")
    story = [
        p("2. Losa transversal entre vigas", styles["h1"]),
        p(
            "Se analiza una franja longitudinal de 1.00 m como viga continua con nodos en los "
            "ejes de las vigas. El peso propio, superficie, peatones y accesorios se aplican en "
            "sus posiciones reales. Las ruedas HL-93 recorren la zona vehicular y se retiene la "
            "envolvente que produce el efecto mas desfavorable.",
            styles["body"],
        ),
        formula_card(
            "Ecuacion matricial de la losa",
            "K u = F;  k_e = (EI/L^3) [[12,6L,-12,6L], ...]",
            "K: rigidez global; u: giros y desplazamientos; F: cargas nodales; E: modulo; I: inercia de la franja; L: longitud del elemento.",
            f"E={materials.concrete.elastic_modulus_kg_cm2:.1f} kg/cm2; I={data.project_inputs.transverse_slab.geometry.slab_inertia_m4:.8f} m4; S={data.project_inputs.transverse_slab.geometry.girder_spacing_m:.3f} m",
            "Momentos y reacciones obtenidos por equilibrio del sistema ensamblado.",
            "Modelo elastico lineal de viga Euler-Bernoulli; apoyos verticales en ejes de vigas.",
            "Procedimiento matricial; anchos equivalentes MTC/AASHTO 4.6.2.1.3.",
            styles,
        ),
        formula_card(
            "Combinacion de diseno de la losa - Resistencia I",
            "Mu = 1.25 MDC + 1.50 MDW + 1.75 MPL + 1.75 MLL+IM",
            "MDC: cargas permanentes; MDW: superficie; MPL: peatonal; MLL+IM: ruedas con impacto. Las acciones favorables variables se omiten.",
            f"M+ @ x={positive.position_m:.3f}: 1.25({positive.dc_moment_tn_m:.3f}) + 1.50({positive.dw_moment_tn_m:.3f}) + 1.75({positive.pl_moment_tn_m:.3f}) + 1.75({positive.ll_im_moment_tn_m:.3f})",
            f"Mu+={positive.combined_moment_tn_m:.3f} Tn.m/m; Mu-={negative.combined_moment_tn_m:.3f} Tn.m/m",
            f"IM={result.dynamic_load_allowance:.2f}; E+={result.equivalent_strip_width_positive_m:.3f} m; E-={result.equivalent_strip_width_negative_m:.3f} m.",
            "MTC 2018 Tabla 2.4.5.3.1-1; AASHTO LRFD Tabla 3.4.1-1.",
            styles,
        ),
    ]
    story.extend(moment_shear_pair(result, title="Losa transversal", include_pl=True, transverse=True))
    story.append(p("Figura 2.1. Envolventes factorizadas empleadas en el diseno de la losa.", styles["caption"]))
    for steel, adopted, label in (
        (reinforcement.positive, selected_positive, "Acero positivo"),
        (reinforcement.negative, selected_negative, "Acero negativo"),
    ):
        adopted_text = (
            f"{adopted.bar.label} @ {adopted.spacing_m:.3f} m; As prov={adopted.provided_area_cm2_m:.3f} cm2/m"
            if adopted is not None else "opcion recomendada por el catalogo"
        )
        story.append(formula_card(
            label,
            "phi As fy [d - As fy/(2*0.85 f'c b)] >= Mu; As,req = max(As,flex, As,min)",
            "phi: reduccion de resistencia; b: 100 cm; d: peralte efectivo; As: acero por metro.",
            f"Mu={steel.design_moment_tn_m:.3f} Tn.m; phi={reinforcement.parameters.flexural_resistance_factor:.2f}; d={steel.effective_depth_cm:.2f} cm; f'c={materials.concrete.compressive_strength_kg_cm2:.1f}; fy={materials.steel.yield_strength_kg_cm2:.1f}",
            f"As flex={steel.strength_area_cm2_m:.3f}; As min={steel.minimum_area_cm2_m:.3f}; As req={steel.required_area_cm2_m:.3f} cm2/m; adoptado: {adopted_text}",
            "Se adopta el mayor entre resistencia y minimo reglamentario, y luego una separacion constructiva no mayor que la permitida.",
            "MTC 2018 2.9.4.2; AASHTO LRFD 5.7.3.",
            styles,
        ))
    story.extend(_crack_cards(data.slab_crack, styles))
    return story


def _crack_cards(review, styles) -> list:
    cards = []
    for check in (review.positive_main, review.negative_main):
        cards.append(formula_card(
            f"Control de fisuracion - {check.direction}",
            "s_max = 123000 gamma_e/(beta_s f_ss) - 2 dc; beta_s = 1 + dc/[0.7(h-dc)]",
            "s_max y dc en mm; fss en MPa; gamma_e: exposicion; beta_s: relacion geometrica.",
            (
                f"fs={check.steel_stress_kg_cm2:.1f} <= "
                f"{check.steel_stress_limit_kg_cm2:.1f} kg/cm2: {check.stress_status}; "
                f"fss={check.steel_stress_used_kg_cm2:.1f} kg/cm2; "
                f"beta_s={check.beta_s:.3f}; dc={check.dc_cm:.2f} cm"
            ),
            (
                f"s prov={check.provided_spacing_m:.3f} m <= "
                f"s max={check.maximum_spacing_m:.3f} m: {check.spacing_status}; "
                f"resultado: {check.status}"
            ),
            "El esfuerzo real y el espaciamiento se verifican por separado para Servicio I.",
            check.reference,
            styles,
        ))
    return cards


def girder_story(data: DeckReportData, styles, *, exterior: bool) -> list:
    result = data.exterior_result if exterior else data.interior_result
    reinforcement = data.exterior_reinforcement if exterior else data.interior_reinforcement
    shear = data.exterior_shear if exterior else data.interior_shear
    selected = data.exterior_selected if exterior else data.interior_selected
    geometry = data.project_inputs.exterior_girder if exterior else data.project_inputs.interior_girder
    rows = combine_exterior_girder_moments(result) if exterior else combine_interior_girder_moments(result)
    strength = max((row for row in rows if row.combination_name == "RESISTENCIA I"), key=lambda row: row.combined_moment_tn_m)
    main = reinforcement.main
    adopted = selected_option(selected, "A.")
    name = "Viga exterior" if exterior else "Viga interior"
    components = (
        f"1.25({strength.dc_moment_tn_m:.3f}) + 1.50({strength.dw_moment_tn_m:.3f}) + "
        + (f"1.75({strength.pl_moment_tn_m:.3f}) + " if exterior else "")
        + f"1.75({strength.ll_im_moment_tn_m:.3f})"
    )
    story = [
        p(f"{'4' if exterior else '3'}. {name}", styles["h1"]),
        p(
            "La viga se idealiza simplemente apoyada. Se desplazan el camion y el tandem junto "
            "con la carga de carril; en cada estacion se retiene el mayor efecto. Los factores de "
            "distribucion convierten la accion del carril en demanda de la viga analizada.",
            styles["body"],
        ),
        formula_card(
            f"Momento ultimo - {name.lower()}",
            "Mu = gamma_DC MDC + gamma_DW MDW + gamma_PL MPL + gamma_LL MLL+IM",
            "gamma: factor LRFD; M: momento sin factor en la misma estacion critica.",
            f"x={strength.position_m:.3f} m: {components}",
            f"Mu={strength.combined_moment_tn_m:.3f} Tn.m",
            f"Modelo simplemente apoyado; IM={result.dynamic_load_allowance:.2f}; gM={result.distribution_factor_g:.3f}.",
            "MTC 2018/AASHTO LRFD 3.4.1 y 4.6.2.2.",
            styles,
        ),
    ]
    story.extend(moment_shear_pair(result, title=name, include_pl=exterior))
    story.append(p(f"Figura. Envolventes Resistencia I empleadas en flexion y cortante de {name.lower()}.", styles["caption"]))
    adopted_text = (
        f"{adopted.bar_count} barras {adopted.bar_label}, {adopted.layers} capa(s), As prov={adopted.provided_area_cm2:.3f} cm2"
        if adopted is not None else "opcion recomendada"
    )
    story.extend([
        formula_card(
            f"Acero longitudinal - {name.lower()}",
            "phi Mn >= Mu; Mn = Cw(d-a/2) + Cf(d-af/2); As = (Cw+Cf)/fy",
            "Cw: compresion del alma; Cf: compresion adicional del ala; a: bloque equivalente; d: peralte efectivo.",
            f"Mu={main.design_moment_tn_m:.3f} Tn.m; bf={main.flange_width_cm:.2f} cm; hf={main.flange_thickness_cm:.2f} cm; bw={main.web_width_cm:.2f} cm; d={main.effective_depth_cm:.2f} cm",
            f"a={main.neutral_axis_block_depth_cm:.3f} cm; As flex={main.strength_area_cm2:.3f}; As min={main.minimum_area_cm2:.3f}; As req={main.required_area_cm2:.3f} cm2; adoptado: {adopted_text}",
            "La profundidad del bloque se resuelve iterativamente y se comprueba si queda en el ala o penetra el alma.",
            "MTC 2018 2.9.4.2; AASHTO LRFD 5.7.3.",
            styles,
        ),
        formula_card(
            f"Diseno por cortante - {name.lower()}",
            "Vu = 1.25 VDC + 1.50 VDW + 1.75 VPL + 1.75 VLL+IM; phi(Vc+Vs) >= Vu",
            "Vc: aporte del concreto; Vs=Av fy dv/s; dv: peralte efectivo de cortante.",
            f"Vu={shear.controlling_shear.combined_shear_tn:.3f} Tn; phi={shear.phi:.2f}; Vc={shear.vc_tn:.3f} Tn; dv={shear.effective_shear_depth_cm:.2f} cm",
            f"Vs req={shear.required_vs_tn:.3f} Tn; Av/s req={shear.required_av_cm2_m:.3f} cm2/m; s max={shear.maximum_spacing_m:.3f} m",
            "Se exige refuerzo transversal minimo cuando Vu supera 0.5 phi Vc y se limita el espaciamiento por nivel de demanda.",
            "MTC 2018 2.9.5; AASHTO LRFD 5.8.",
            styles,
        ),
    ])
    return story
