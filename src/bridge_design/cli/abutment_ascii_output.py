"""ASCII report for cantilever abutment design."""

import re
from math import radians, tan

from bridge_design.cli.ascii_tables import audit_block_title, audit_subtitle, boxed_table, key_value_box
from bridge_design.domain.abutment import (
    ABUTMENT_KEY_REFERENCE,
    AbutmentDesignResult,
    LoadComponent,
    StabilityStateResult,
    StructuralDesignCase,
)
from bridge_design.domain.rebar_catalog import ReinforcementCaseOptions, ReinforcementSpacingOption


def format_abutment_design_result(
    result: AbutmentDesignResult,
    title: str = "DISENO DE ESTRIBO TIPO CANTILEVER",
    primary_stability_title: str = "CON PUENTE",
    secondary_stability_title: str = "SIN PUENTE",
    include_stem_reinforcement_cut: bool = True,
) -> str:
    """Return a complete terminal report for abutment design."""
    lines: list[str] = []
    lines.extend(audit_block_title("E", title, 112))
    lines.extend(_format_section_title("DATOS INGRESADOS Y CONSIDERADOS"))
    lines.extend(_format_input_summary(result))

    lines.extend(_format_section_title("ESTRIBO CON PUENTE" if not result.inputs.is_pure_wall else primary_stability_title))
    lines.extend(_format_section_title("CARGAS VERTICALES"))
    lines.extend(_format_weight_procedure(result))
    lines.extend(_format_section_title("CARGAS HORIZONTALES"))
    lines.extend(_format_horizontal_loads(primary_stability_title, result.components.horizontal_with_bridge))
    lines.extend(_format_pressures(result))
    factor_title = (
        "ESTADOS LIMITES APLICABLES Y COMBINACIONES DE CARGAS - MURO CANTILEVER"
        if result.inputs.is_pure_wall
        else "ESTADOS LIMITES APLICABLES Y COMBINACIONES DE CARGAS - ESTRIBO CON PUENTE"
    )
    lines.extend(_format_factors(factor_title, result))
    lines.extend(_format_contact_criteria())
    lines.extend(_format_stability(
        "CHEQUEO DE ESTABILIDAD Y ESFUERZOS - " + primary_stability_title,
        result,
        result.with_bridge + result.service_with_bridge,
    ))

    if not result.inputs.is_pure_wall:
        lines.extend(_format_section_title("ESTRIBO SIN PUENTE"))
        lines.extend(_format_factors("ESTADOS LIMITES APLICABLES Y COMBINACIONES DE CARGA - ESTRIBO SIN PUENTE", result))
        lines.extend(_format_contact_criteria())
        lines.extend(_format_stability(
            "CHEQUEO DE ESTABILIDAD Y ESFUERZOS - " + secondary_stability_title,
            result,
            result.without_bridge + result.service_without_bridge,
        ))
    lines.extend(_format_footing_width_recommendation(result))
    lines.extend(_format_section_title("DENTELLON Y DESLIZAMIENTO"))
    lines.extend(_format_key(result))
    lines.extend(_format_section_title("CALCULO DE ACERO"))
    lines.extend(_format_section_title("DISENO DE PANTALLA"))
    lines.extend(_format_structural_design(result, case_filter={"Pantalla"}))
    if include_stem_reinforcement_cut:
        lines.extend(_format_stem_reinforcement_cut(result))
    lines.extend(_format_section_title("DISENO DE CIMENTACION"))
    lines.extend(_format_structural_design(result, case_filter={"Zapata - talon superior", "Zapata - puntera inferior", "Diente de concreto"}))
    lines.extend(_format_secondary_reinforcement(result))
    lines.extend(_format_crack_checks(result))
    lines.extend(_format_development_checks(result))
    lines.extend(_format_bar_details(result))
    lines.append("=" * 112)
    return "\n".join(_enumerate_audit_titles(lines))


def _format_section_title(title: str) -> list[str]:
    return ["", *audit_subtitle("", title, 112)]


def format_abutment_reinforcement_option_tables(
    result: AbutmentDesignResult,
    title: str = "SELECCION DE ACERO DE ESTRIBO",
) -> str:
    """Return option tables for selecting abutment reinforcement before final checks."""
    lines: list[str] = []
    lines.extend(audit_block_title("E", title, 112))
    for case_options in _abutment_reinforcement_case_options(result):
        lines.append("")
        lines.extend(_format_spacing_option_table(case_options))
        if case_options.label == "Pantalla":
            lines.extend(_format_stem_reinforcement_cut_option(result))
    return "\n".join(_enumerate_audit_titles(lines))


def format_abutment_reinforcement_selection(
    selected: tuple[tuple[str, ReinforcementSpacingOption], ...],
    title: str = "ACEROS SELECCIONADOS - ESTRIBO",
) -> str:
    """Return selected abutment reinforcement distributions."""
    return "\n".join(
        _enumerate_audit_titles([""] + boxed_table(
            ("Caso", "Origen", "Barra", "s", "As req", "As prov", "Estado"),
            (
                (
                    label,
                    "USUARIO" if option.is_custom else "TABLA",
                    option.bar.label,
                    f"{option.spacing_m:.3f}",
                    f"{option.required_area_cm2_m:.3f}",
                    f"{option.provided_area_cm2_m:.3f}",
                    "OK" if option.is_compliant else "NO",
                )
                for label, option in selected
            ),
            aligns=("left", "center", "center", "right", "right", "right", "center"),
            title=title,
        ))
    )


def format_abutment_footing_width_recommendation(result: AbutmentDesignResult) -> str:
    """Return the footing width recommendation table, if applicable."""
    return "\n".join(_enumerate_audit_titles(_format_footing_width_recommendation(result)))


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _enumerate_audit_titles(lines: list[str]) -> list[str]:
    numbered = list(lines)
    counters = [0, 0, 0, 0]
    current_level2 = ""
    current_level3 = ""
    for index in range(1, len(numbered) - 1):
        previous_visible = _visible_text(numbered[index - 1])
        current_visible = _visible_text(numbered[index])
        next_visible = _visible_text(numbered[index + 1])
        if not (
            _is_single_cell_border(previous_visible)
            and _is_single_cell_title(current_visible)
            and _is_single_cell_border(next_visible)
            and len(previous_visible) == len(current_visible) == len(next_visible)
        ):
            continue

        raw_title = current_visible[1:-1].strip()
        if not raw_title:
            continue

        prefix, _, suffix = _split_ansi_wrapped_line(numbered[index])
        inner_width = len(current_visible) - 2
        clean_title = _strip_existing_title_code(raw_title)
        level = _title_hierarchy_level(clean_title, previous_visible, current_level2, current_level3)
        counters[level - 1] += 1
        for counter_index in range(level, len(counters)):
            counters[counter_index] = 0
        code = ".".join(str(value) for value in counters[:level] if value > 0)
        title = f"{code}. {clean_title}"
        title_text = title[:inner_width]
        if "=" in previous_visible:
            title_text = title_text.center(inner_width)
        else:
            title_text = title_text.ljust(inner_width)
        numbered[index] = f"{prefix}|{title_text}|{suffix}"
        if level == 2:
            current_level2 = clean_title
            current_level3 = ""
        elif level == 3:
            current_level3 = clean_title
    return numbered


def _title_hierarchy_level(
    title: str,
    previous_border: str,
    current_level2: str,
    current_level3: str,
) -> int:
    if "=" in previous_border:
        return 1
    if title in {
        "DATOS INGRESADOS Y CONSIDERADOS",
        "ESTRIBO CON PUENTE",
        "MURO PURO",
        "ESTRIBO SIN PUENTE",
        "DENTELLON Y DESLIZAMIENTO",
        "CALCULO DE ACERO",
    }:
        return 2
    if title.startswith("OPCION DE CORTE") and current_level2.startswith("OPCIONES - Pantalla"):
        return 3
    if title.startswith("OPCIONES - ") or title.startswith("OPCION DE CORTE"):
        return 2
    if current_level2 in {"ESTRIBO CON PUENTE", "MURO PURO", "ESTRIBO SIN PUENTE"}:
        if (
            title in {"CARGAS VERTICALES", "CARGAS HORIZONTALES"}
            or title.startswith("ESTADOS LIMITES")
            or title in {"CRITERIO DE CONTACTO SUELO-ZAPATA", "CRITERIO GEOTECNICO Y ESTRUCTURAL DE ZAPATA"}
            or title.startswith("CHEQUEO DE ESTABILIDAD")
        ):
            return 3
        return 4
    if current_level2 == "CALCULO DE ACERO":
        if title in {
            "DISENO DE PANTALLA",
            "DISENO DE CIMENTACION",
            "ACERO SECUNDARIO Y TRANSVERSAL MINIMO",
            "CONTROL DE FISURACION",
            "DESARROLLO Y ANCLAJE DE BARRAS",
            "CUADRO DE DETALLE DE ACERO",
        }:
            return 3
        return 4
    if current_level2 in {"DATOS INGRESADOS Y CONSIDERADOS", "DENTELLON Y DESLIZAMIENTO"}:
        return 3
    if current_level3:
        return 4
    return 3


def _visible_text(line: str) -> str:
    return _ANSI_RE.sub("", line)


def _split_ansi_wrapped_line(line: str) -> tuple[str, str, str]:
    prefix_match = re.match(r"(?:\x1b\[[0-9;]*m)*", line)
    prefix = prefix_match.group(0) if prefix_match else ""
    without_prefix = line[len(prefix):]
    suffix_match = re.search(r"(?:\x1b\[[0-9;]*m)*$", without_prefix)
    suffix = suffix_match.group(0) if suffix_match else ""
    visible = without_prefix[: len(without_prefix) - len(suffix)] if suffix else without_prefix
    return prefix, visible, suffix


def _is_single_cell_border(line: str) -> bool:
    return (
        len(line) >= 3
        and line.startswith("+")
        and line.endswith("+")
        and line.count("+") == 2
        and all(character in "+-=" for character in line)
    )


def _is_single_cell_title(line: str) -> bool:
    return line.startswith("|") and line.endswith("|") and line.count("|") == 2


def _strip_existing_title_code(title: str) -> str:
    return re.sub(r"^(?:[A-Z]|\d+(?:\.\d+)*)\.\s+", "", title).strip()


def _abutment_reinforcement_case_options(
    result: AbutmentDesignResult,
) -> tuple[ReinforcementCaseOptions, ...]:
    primary = [result.stem_design, result.heel_design, result.toe_design]
    if result.key_design is not None:
        primary.append(result.key_design)
    options = [case.spacing_options for case in primary] + [
        case.spacing_options for case in result.secondary_reinforcement
    ]
    return tuple(sorted(options, key=lambda case_options: _reinforcement_group_rank(case_options.label)))


def _reinforcement_group_rank(label: str) -> int:
    if label.startswith("Pantalla"):
        return 0
    if label.startswith("Zapata"):
        return 1
    return 2


def _format_spacing_option_table(case_options: ReinforcementCaseOptions) -> list[str]:
    return boxed_table(
        ("Item", "Barra", "s (m)", "As req", "As prov", "Exceso", "Estado", "Uso"),
        (
            (
                option.item,
                option.bar.label,
                f"{option.spacing_m:.3f}",
                f"{option.required_area_cm2_m:.3f}",
                f"{option.provided_area_cm2_m:.3f}",
                f"{option.excess_percent:.1f}%",
                "OK" if option.is_compliant else "NO",
                "RECOM." if option.is_recommended else "",
            )
            for option in case_options.options
        ),
        aligns=("right", "center", "right", "right", "right", "right", "center", "center"),
        title=f"OPCIONES - {case_options.label}",
    )


def _format_stem_reinforcement_cut_option(result: AbutmentDesignResult) -> list[str]:
    cut = result.stem_reinforcement_cut
    if cut is None:
        return [
            "",
            *key_value_box(
                "OPCION DE CORTE DE ACERO PRINCIPAL DE PANTALLA",
                (
                    ("Estado", "NO APLICA"),
                    ("Criterio", "El acero de pantalla no permite una reduccion practica con un solo corte."),
                ),
                width=112,
            ),
        ]
    return [
        "",
        *key_value_box(
            "OPCION DE CORTE DE ACERO PRINCIPAL DE PANTALLA",
            (
                ("Acero inferior", f"{cut.lower_bar_label} @ {cut.lower_spacing_m:.3f} m"),
                ("Acero continuo superior", f"{cut.upper_bar_label} @ {cut.upper_spacing_m:.3f} m"),
                ("Patron constructivo", f"Continua 1 de cada {cut.continuous_every_n_bars} barras inferiores"),
                ("Altura teorica de corte", f"{cut.theoretical_cut_height_m:.3f} m sobre zapata"),
                ("Altura constructiva de corte", f"{cut.constructive_cut_height_m:.3f} m sobre zapata"),
                ("Longitud barras cortadas", f"{cut.lower_cut_bar_length_m:.3f} m"),
                ("Longitud barras continuas", f"{cut.continuous_bar_length_m:.3f} m"),
                ("Estado", cut.status),
            ),
            width=112,
        ),
    ]


def _format_input_summary(result: AbutmentDesignResult) -> list[str]:
    data = result.inputs
    g = data.geometry
    loads = data.loads
    soil = data.soil
    values = [
        ("Franja longitudinal de diseno", f"{g.strip_width_m:.2f} m"),
        (
            "Altura total desde fondo de zapata" if data.is_pure_wall else "H activo desde fondo de zapata",
            f"{g.retained_height_m:.3f} m",
        ),
        ("B zapata", f"{g.footing_width_m:.3f} m"),
        ("D zapata", f"{g.footing_thickness_m:.3f} m"),
        ("Puntera", f"{g.toe_length_m:.3f} m"),
        ("Talon", f"{g.heel_length_m:.3f} m"),
        ("e inferior pantalla", f"{g.lower_stem_thickness_m:.3f} m"),
        ("e superior pantalla", f"{g.upper_stem_thickness_m:.3f} m"),
        ("Altura frontal", f"{g.front_soil_depth_m:.3f} m"),
    ]
    if not data.is_pure_wall:
        values.extend(
            [
                ("t1 transicion frontal superior", f"{g.small_batter_width_m:.3f} m"),
                ("t2 retiro superior relleno", f"{g.backfill_step_width_m:.3f} m"),
                ("cajuela longitud horizontal", f"{g.bearing_seat_length_m:.3f} m"),
                ("e parapeto", f"{g.seat_wall_width_m:.3f} m"),
                ("altura cajuela", f"{g.seat_block_height_m:.3f} m"),
                ("altura bloque cajuela", f"{g.backwall_drop_m:.3f} m"),
                ("altura transicion", f"{g.backwall_taper_height_m:.3f} m"),
                ("PDC tablero", f"{loads.pdc_tn_m:.3f} Ton/m"),
                ("PDW asfalto", f"{loads.pdw_tn_m:.3f} Ton/m"),
                ("PPL peatonal tablero", f"{loads.ppl_tn_m:.3f} Ton/m"),
                ("PLL+IM vehicular", f"{loads.pll_im_tn_m:.3f} Ton/m"),
            ]
        )
    values.append(("Sobrecarga peatonal en relleno", f"{soil.pedestrian_surcharge_tn_m2:.3f} Ton/m2"))
    return [
        "",
        *key_value_box(
            "DATOS PRINCIPALES",
            tuple(values),
            width=112,
        ),
    ]


def _format_unfactored_components(result: AbutmentDesignResult) -> list[str]:
    rows = []
    for component in result.components.vertical_with_bridge:
        rows.append(_component_row(component))
    rows.append(("HORIZONTAL", "", "", ""))
    for component in result.components.horizontal_with_bridge:
        rows.append(_component_row(component))
    return [
        "",
        *boxed_table(
            ("Componente", "Tipo", "Carga", "Brazo"),
            rows,
            aligns=("left", "center", "right", "right"),
            title="CARGAS SIN FACTORAR POR METRO LINEAL",
        ),
    ]


def _component_row(component: LoadComponent) -> tuple[str, str, str, str]:
    if component.load_type:
        return (
            component.name,
            component.load_type,
            f"{component.value_tn_m:.3f} Ton/m",
            f"{component.arm_m:.3f} m",
        )
    return (component.name, "", "", "")


def _format_horizontal_loads(title: str, components: tuple[LoadComponent, ...]) -> list[str]:
    rows = [
        (
            component.name,
            component.load_type,
            f"{component.value_tn_m:.3f} Tn/m",
            f"{component.arm_m:.3f} m",
            f"{component.moment_tn_m_m:.3f} Tn*m/m",
        )
        for component in components
        if component.value_tn_m > 0.0
    ]
    return [
        "",
        *boxed_table(
            ("Componente", "Tipo", "H", "y", "Mh=H*y"),
            rows,
            aligns=("left", "center", "right", "right", "right"),
            title=f"CARGAS HORIZONTALES - {title}",
        ),
    ]


def _format_calculation_procedure(result: AbutmentDesignResult) -> list[str]:
    lines = [""]
    lines.extend(audit_subtitle("", "PROCEDIMIENTO PASO A PASO DEL CALCULO", 112))
    lines.extend(_format_geometry_procedure(result))
    lines.extend(_format_weight_procedure(result))
    lines.extend(_format_soil_pressure_procedure(result))
    lines.extend(_format_stability_procedure(result))
    lines.extend(_format_key_procedure(result))
    lines.extend(_format_structural_procedure(result))
    return lines


def _format_geometry_procedure(result: AbutmentDesignResult) -> list[str]:
    g = result.inputs.geometry
    rows = [
        ("Altura libre de pantalla", "H - D", f"{g.retained_height_m:.3f} - {g.footing_thickness_m:.3f}", f"{g.stem_height_above_footing_m:.3f} m"),
        (
            "Longitud de talon",
            "B - puntera - espesor inferior",
            f"{g.footing_width_m:.3f} - {g.toe_length_m:.3f} - {g.lower_stem_thickness_m:.3f}",
            f"{g.heel_length_m:.3f} m",
        ),
        ("Franja de diseno", "b", f"{g.strip_width_m:.3f}", f"{g.strip_width_m:.3f} m"),
    ]
    return [
        "",
        *boxed_table(
            ("Paso", "Formula", "Sustitucion", "Resultado"),
            rows,
            aligns=("left", "left", "left", "right"),
            title="1. GEOMETRIA DERIVADA",
        ),
    ]


def _format_weight_procedure(result: AbutmentDesignResult) -> list[str]:
    data = result.inputs
    gamma_concrete = data.materials.concrete_unit_weight_kg_m3 / 1000.0
    gamma_soil = data.materials.soil_unit_weight_kg_m3 / 1000.0
    dc_rows = [_weight_component_row(component, gamma_concrete) for component in result.concrete_components]
    if not data.is_pure_wall:
        pdc_component = LoadComponent(
            "PDC tablero",
            "DC",
            data.loads.pdc_tn_m,
            data.geometry.superstructure_load_x_m,
        )
        dc_rows.append(_direct_load_component_row(pdc_component, "DC"))
    dc_bridge_weight = result.dc_self_weight_tn_m + (0.0 if data.is_pure_wall else data.loads.pdc_tn_m)
    dc_bridge_moment = result.dc_self_weight_tn_m * result.dc_self_x_m
    if not data.is_pure_wall:
        dc_bridge_moment += data.loads.pdc_tn_m * data.geometry.superstructure_load_x_m
    dc_bridge_x = dc_bridge_moment / dc_bridge_weight if dc_bridge_weight > 0.0 else 0.0
    dc_rows.append(
        _resultant_row(
            "Subtotal DC muro" if data.is_pure_wall else "Subtotal DC estribo",
            "DC",
            result.dc_self_weight_tn_m,
            result.dc_self_x_m,
            result.dc_self_weight_tn_m * result.dc_self_x_m,
        )
    )
    dc_rows.append(_resultant_row("Resultante DC", "DC", dc_bridge_weight, dc_bridge_x, dc_bridge_moment))

    ev_rows = [_weight_component_row(component, gamma_soil) for component in result.soil_components]
    ev_rows.append(
        _resultant_row(
            "Resultante EV",
            "EV",
            result.ev_weight_tn_m,
            result.ev_x_m,
            result.ev_weight_tn_m * result.ev_x_m,
        )
    )

    dw_rows = _vertical_group_rows(result, "DW")
    ll_im_rows = _vertical_group_rows(result, "LL+IM")
    ls_rows = _vertical_group_rows(result, "LS")
    lines = [""]
    lines.extend(_weight_table("CARGAS DC", dc_rows))
    if dw_rows:
        lines.append("")
        lines.extend(_weight_table("CARGAS DW", dw_rows))
    lines.append("")
    lines.extend(_weight_table("CARGAS EV", ev_rows))
    if ll_im_rows:
        lines.append("")
        lines.extend(_weight_table("CARGAS LL+IM", ll_im_rows))
    if ls_rows:
        lines.append("")
        lines.extend(_weight_table("CARGAS LS", ls_rows))
    return lines


def _weight_component_row(component: LoadComponent, gamma_tn_m3: float) -> tuple[str, str, str, str, str, str, str]:
    area = component.value_tn_m / gamma_tn_m3 if gamma_tn_m3 > 0.0 else 0.0
    return (
        component.name,
        component.load_type,
        f"{area:.3f} m2",
        f"{gamma_tn_m3:.3f} Tn/m3",
        f"{component.value_tn_m:.3f} Tn/m",
        f"{component.arm_m:.3f} m",
        f"{component.moment_tn_m_m:.3f} Tn*m/m",
    )


def _direct_load_component_row(
    component: LoadComponent,
    load_type: str | None = None,
) -> tuple[str, str, str, str, str, str, str]:
    display_type = load_type or _display_load_type(component)
    return (
        component.name,
        display_type,
        "",
        "",
        f"{component.value_tn_m:.3f} Tn/m",
        f"{component.arm_m:.3f} m",
        f"{component.moment_tn_m_m:.3f} Tn*m/m",
    )


def _resultant_row(
    name: str,
    load_type: str,
    weight_tn_m: float,
    arm_m: float,
    moment_tn_m_m: float,
) -> tuple[str, str, str, str, str, str, str]:
    return (
        name,
        load_type,
        "",
        "",
        f"{weight_tn_m:.3f} Tn/m",
        f"{arm_m:.3f} m",
        f"{moment_tn_m_m:.3f} Tn*m/m",
    )


def _weight_table(title: str, rows: list[tuple[str, str, str, str, str, str, str]]) -> list[str]:
    return boxed_table(
        ("Componente", "Tipo", "Area", "gamma", "W", "x", "Mx=W*x"),
        rows,
        aligns=("left", "center", "right", "right", "right", "right", "right"),
        title=title,
    )


def _vertical_group_rows(
    result: AbutmentDesignResult,
    group_type: str,
) -> list[tuple[str, str, str, str, str, str, str]]:
    components = [
        component
        for component in result.components.vertical_with_bridge
        if _display_load_type(component) == group_type and component.value_tn_m > 0.0
    ]
    rows = [_direct_load_component_row(component) for component in components]
    total = sum(component.value_tn_m for component in components)
    if total <= 0.0:
        return rows
    moment = sum(component.moment_tn_m_m for component in components)
    rows.append(_resultant_row(f"Resultante {group_type}", group_type, total, moment / total, moment))
    return rows


def _display_load_type(component: LoadComponent) -> str:
    if component.load_type == "LL":
        return "LL+IM"
    return component.load_type


def _format_soil_pressure_procedure(result: AbutmentDesignResult) -> list[str]:
    data = result.inputs
    g = data.geometry
    soil = data.soil
    p = result.pressures
    gamma = data.materials.soil_unit_weight_kg_m3 / 1000.0
    effective_heel = g.heel_length_m - g.backfill_step_width_m
    as_coeff = soil.fpga * soil.pga
    kh = 0.5 * as_coeff
    rows = [
        ("Ka Coulomb", "f(phi, delta, beta, theta)", f"phi={soil.friction_angle_deg:.3f}; delta={soil.wall_soil_friction_deg:.3f}; beta={soil.backfill_slope_deg:.3f}; theta={soil.wall_backface_angle_deg:.3f}", f"{p.ka:.4f}"),
        ("h' vehicular", "valor ingresado o interpolado por H", f"H={g.retained_height_m:.3f}", f"{p.live_surcharge_height_m:.3f} m"),
        ("LSy vehicular", "Btalon* h' * gamma", f"{effective_heel:.3f}*{p.live_surcharge_height_m:.3f}*{gamma:.3f}", f"{p.lsy_tn_m:.3f} Tn/m"),
        ("LSx vehicular", "Ka * h' * gamma * H", f"{p.ka:.4f}*{p.live_surcharge_height_m:.3f}*{gamma:.3f}*{g.retained_height_m:.3f}", f"{p.lsx_tn_m - p.pedestrian_lsx_tn_m:.3f} Tn/m"),
        ("LS peatonal vertical", "qpeat * Btalon", f"{soil.pedestrian_surcharge_tn_m2:.3f}*{effective_heel:.3f}", f"{p.pedestrian_lsy_tn_m:.3f} Tn/m"),
        ("LS peatonal horizontal", "Ka * qpeat * H", f"{p.ka:.4f}*{soil.pedestrian_surcharge_tn_m2:.3f}*{g.retained_height_m:.3f}", f"{p.pedestrian_lsx_tn_m:.3f} Tn/m"),
        ("EH terreno", "0.5 * Ka * gamma * H^2", f"0.5*{p.ka:.4f}*{gamma:.3f}*{g.retained_height_m:.3f}^2", f"{p.eh_tn_m:.3f} Tn/m"),
        ("As", "Fpga * PGA", f"{soil.fpga:.3f}*{soil.pga:.3f}", f"{as_coeff:.4f}"),
        ("kh", "0.5 * As", f"0.5*{as_coeff:.4f}", f"{kh:.4f}"),
        ("kAE", "Mononobe-Okabe", f"angulo sismico={p.seismic_angle_deg:.3f} grados", f"{p.k_ae:.4f}"),
        ("PAE", "0.5 * kAE * gamma * H^2", f"0.5*{p.k_ae:.4f}*{gamma:.3f}*{g.retained_height_m:.3f}^2", f"{p.pae_tn_m:.3f} Tn/m"),
        ("EQterr", "PAE - EH", f"{p.pae_tn_m:.3f} - {p.eh_tn_m:.3f}", f"{p.eq_terr_tn_m:.3f} Tn/m"),
        ("PIR", "kh * (DC + EV)", f"{kh:.4f}*({result.dc_self_weight_tn_m:.3f}+{result.ev_weight_tn_m:.3f})", f"{p.pir_tn_m:.3f} Tn/m"),
    ]
    return [
        "",
        *boxed_table(
            ("Paso", "Formula", "Sustitucion", "Resultado"),
            rows,
            aligns=("left", "left", "left", "right"),
            title="3. EMPUJES DE SUELO, SOBRECARGA Y SISMO",
        ),
    ]


def _format_stability_procedure(result: AbutmentDesignResult) -> list[str]:
    g = result.inputs.geometry
    soil = result.inputs.soil
    tan_phi = tan(radians(soil.friction_angle_deg))
    rows = []
    states = (
        result.with_bridge + result.service_with_bridge
        if result.inputs.is_pure_wall
        else result.without_bridge + result.service_without_bridge
    )
    for state in states:
        abs_e = abs(state.eccentricity_m)
        qmax_formula = "2*Vu/Lc/10" if state.contact_type != "Completo" else "Vu/B*(1 + 6|e|/B)/10"
        qmax_substitution = (
            f"2*{state.vu_tn_m:.3f}/{state.contact_length_m:.3f}/10 = {state.qmax_kg_cm2:.3f} kg/cm2"
            if state.contact_type != "Completo"
            else f"{state.vu_tn_m:.3f}/{g.footing_width_m:.3f}*(1+6*{abs_e:.3f}/{g.footing_width_m:.3f})/10 = {state.qmax_kg_cm2:.3f} kg/cm2"
        )
        rows.extend(
            [
                (state.name, "Vu", "sum(gamma_i * P_i vertical)", f"{state.vu_tn_m:.3f} Tn/m"),
                (state.name, "MVu", "sum(gamma_i * P_i * x_i)", f"{state.stabilizing_moment_tn_m_m:.3f} Tn*m/m"),
                (state.name, "Hu", "sum(gamma_i * P_i horizontal)", f"{state.hu_tn_m:.3f} Tn/m"),
                (state.name, "MHu", "sum(gamma_i * P_i * y_i)", f"{state.overturning_moment_tn_m_m:.3f} Tn*m/m"),
                (state.name, "xR", "(MVu - MHu) / Vu", f"{state.resultant_x_m:.3f} m"),
                (state.name, "e", "B/2 - xR", f"{g.footing_width_m / 2.0:.3f} - {state.resultant_x_m:.3f} = {state.eccentricity_m:.3f} m"),
                (state.name, "Ff", "Vu * tan(phi)", f"{state.vu_tn_m:.3f}*tan({soil.friction_angle_deg:.3f}) = {state.friction_resistance_tn_m:.3f} Tn/m"),
                (state.name, "Contacto", "segun estado limite", f"{state.contact_type}; Lc/B={state.contact_length_ratio:.3f}"),
                (state.name, "B' Meyerhof", "B - 2|e|", f"{state.effective_width_m:.3f} m"),
                (state.name, "q Meyerhof", "Vu/B'/10", f"{state.geotechnical_pressure_kg_cm2:.3f} kg/cm2"),
                (state.name, "qmax estructural", qmax_formula, qmax_substitution),
                (state.name, "qmin estructural", "presion minima adoptada", f"{state.qmin_kg_cm2:.3f} kg/cm2"),
                (state.name, "q limite", _bearing_limit_formula(state, result), f"{state.q_allow_kg_cm2:.3f} kg/cm2"),
            ]
        )
        zero_distance = _zero_pressure_distance_from_toe(state, g.footing_width_m)
        if zero_distance is not None:
            rows.append(
                (
                    state.name,
                    "x(q=0) desde punta",
                    "distancia donde inicia/termina contacto",
                    f"{zero_distance:.3f} m",
                )
            )
    return [
        "",
        *boxed_table(
            ("Estado", "Control", "Formula", "Resultado"),
            rows,
            aligns=("left", "left", "left", "right"),
            title="4. DESARROLLO DE ESTABILIDAD",
        ),
    ]


def _format_key_procedure(result: AbutmentDesignResult) -> list[str]:
    if result.key is None:
        return [
            "",
            *audit_subtitle("", "5. DENTELLON: NO CONSIDERADO EN EL MODELO", 112),
        ]
    data = result.inputs
    key = result.key
    gamma = data.materials.soil_unit_weight_kg_m3 / 1000.0
    phi = data.soil.friction_angle_deg
    h_front = data.geometry.front_soil_depth_m
    rows = [
        ("k'p", "tan^2(45 + phi/2)", f"tan^2(45+{phi:.3f}/2)", f"{key.passive_coefficient_prime:.3f}"),
        ("kp", "k'p", f"{key.passive_coefficient_prime:.3f}", f"{key.kp:.3f}"),
        ("h frontal", "suelo frontal sobre cabeza del diente", "-", f"{h_front:.3f} m"),
        (
            "Empuje superior",
            "0.5*kp*gamma*h frontal^2 si se considera",
            (
                f"0.5*{key.kp:.3f}*{gamma:.3f}*{h_front:.3f}^2"
                if data.key.consider_upper_front_passive
                else "No considerado"
            ),
            f"{key.upper_front_passive_resistance_tn_m:.3f} Tn/m",
        ),
        ("Presion superior", "kp * gamma * h frontal", f"{key.kp:.3f}*{gamma:.3f}*{h_front:.3f}", f"{key.top_pressure_tn_m2:.3f} Tn/m2"),
        ("Presion inferior", "kp * gamma * (h frontal + h diente)", f"{key.kp:.3f}*{gamma:.3f}*({h_front:.3f}+{data.key.height_m:.3f})", f"{key.bottom_pressure_tn_m2:.3f} Tn/m2"),
        ("Rep", "0.5*(psup+pinf)*h diente", f"0.5*({key.top_pressure_tn_m2:.3f}+{key.bottom_pressure_tn_m2:.3f})*{data.key.height_m:.3f}", f"{key.passive_resistance_tn_m:.3f} Tn/m"),
        ("Rep total", "Empuje superior + Rep diente", f"{key.upper_front_passive_resistance_tn_m:.3f}+{key.passive_resistance_tn_m:.3f}", f"{key.total_passive_resistance_tn_m:.3f} Tn/m"),
        ("phi_ep Rep total", "phi_ep * Rep total", f"{data.key.passive_resistance_factor:.3f}*{key.total_passive_resistance_tn_m:.3f}", f"{key.factored_passive_tn_m:.3f} Tn/m"),
    ]
    return [
        "",
        *boxed_table(
            ("Paso", "Formula", "Sustitucion", "Resultado"),
            rows,
            aligns=("left", "left", "left", "right"),
            title="5. DESARROLLO DEL DIENTE O DENTELLON",
        ),
    ]


def _format_structural_procedure(result: AbutmentDesignResult) -> list[str]:
    rows = []
    cases = [result.stem_design, result.heel_design, result.toe_design]
    if result.key_design is not None:
        cases.append(result.key_design)
    for case in cases:
        rows.extend(
            [
                (case.name, "Mu", "maximo de combinaciones aplicables", f"{case.controlling_moment_tn_m_m:.3f} Tn*m/m"),
                (case.name, "d", "peralte - recubrimiento - db/2", f"{case.effective_depth_cm:.2f} cm"),
                (case.name, "As flex", "area por resistencia a flexion", f"{case.strength_as_cm2_m:.3f} cm2/m"),
                (case.name, "As min", "maximo entre minimo y control de fisuracion/capacidad", f"{case.minimum_as_cm2_m:.3f} cm2/m"),
                (case.name, "As req", "max(As flex, As min)", f"{case.required_as_cm2_m:.3f} cm2/m"),
                (case.name, "As prov", "Abarra / separacion", f"{case.provided_as_cm2_m:.3f} cm2/m"),
                (case.name, "Mr", "phi * As * fy * (d - a/2)", f"{case.moment_resistance_tn_m_m:.3f} Tn*m/m"),
                (case.name, "Corte", "Vu <= Vr concreto", f"{case.shear_demand_tn_m:.3f} <= {case.shear_resistance_tn_m:.3f} Tn/m"),
            ]
        )
    return [
        "",
        *boxed_table(
            ("Elemento", "Paso", "Criterio/Formula", "Resultado"),
            rows,
            aligns=("left", "left", "left", "right"),
            title="6. DESARROLLO DEL DISENO ESTRUCTURAL",
        ),
    ]


def _format_pressures(result: AbutmentDesignResult) -> list[str]:
    p = result.pressures
    data = result.inputs
    g = data.geometry
    soil = data.soil
    gamma = data.materials.soil_unit_weight_kg_m3 / 1000.0
    effective_heel = g.heel_length_m - g.backfill_step_width_m
    as_coeff = soil.fpga * soil.pga
    kh = 0.5 * as_coeff
    values = [
        ("Ka Coulomb", f"Coulomb(phi={soil.friction_angle_deg:.3f}, delta={soil.wall_soil_friction_deg:.3f}, beta={soil.backfill_slope_deg:.3f}, theta={soil.wall_backface_angle_deg:.3f})", f"{p.ka:.4f}"),
        ("h' vehicular adoptado", f"h'({g.retained_height_m:.3f})", f"{p.live_surcharge_height_m:.3f} m"),
        ("LSy vehicular", f"{effective_heel:.3f}*{p.live_surcharge_height_m:.3f}*{gamma:.3f}", f"{p.lsy_tn_m:.3f} Ton/m"),
        ("LSx vehicular + peatonal", f"{p.ka:.4f}*{p.live_surcharge_height_m:.3f}*{gamma:.3f}*{g.retained_height_m:.3f} + {p.ka:.4f}*{soil.pedestrian_surcharge_tn_m2:.3f}*{g.retained_height_m:.3f}", f"{p.lsx_tn_m:.3f} Ton/m"),
        ("EH terreno", f"0.5*{p.ka:.4f}*{gamma:.3f}*{g.retained_height_m:.3f}^2", f"{p.eh_tn_m:.3f} Ton/m"),
        ("kAE sismico", f"Mononobe-Okabe(kh={kh:.4f})", f"{p.k_ae:.4f}"),
        ("PAE", f"0.5*{p.k_ae:.4f}*{gamma:.3f}*{g.retained_height_m:.3f}^2", f"{p.pae_tn_m:.3f} Ton/m"),
        ("EQterr = PAE - EH", f"{p.pae_tn_m:.3f} - {p.eh_tn_m:.3f}", f"{p.eq_terr_tn_m:.3f} Ton/m"),
        ("PIR", f"{kh:.4f}*({result.dc_self_weight_tn_m:.3f}+{result.ev_weight_tn_m:.3f})", f"{p.pir_tn_m:.3f} Ton/m"),
    ]
    if not result.inputs.is_pure_wall:
        values.append(("PEQ superestructura", f"({data.loads.pdc_tn_m:.3f}+{data.loads.pdw_tn_m:.3f})*{as_coeff:.4f}", f"{p.peq_tn_m:.3f} Ton/m"))
    return [
        "",
        *boxed_table(
            ("Concepto", "Operacion matematica", "Valor"),
            tuple(values),
            aligns=("left", "left", "right"),
            title="EMPUJES DE RELLENO, SOBRECARGAS Y SISMO",
        ),
    ]


def _format_factors(title: str, result: AbutmentDesignResult) -> list[str]:
    return [
        "",
        *boxed_table(
            ("Estado", "DC", "DW", "EV", "LL", "LSv", "LSh", "EH", "EQ", "BR"),
            (
                (
                    factor.name,
                    f"{factor.dc:.2f}",
                    f"{factor.dw:.2f}",
                    f"{factor.ev:.2f}",
                    f"{factor.ll:.2f}",
                    f"{factor.ls_vertical:.2f}",
                    f"{factor.ls_horizontal:.2f}",
                    f"{factor.eh:.2f}",
                    f"{factor.eq:.2f}",
                    f"{factor.br:.2f}",
                )
                for factor in result.load_factors
            ),
            aligns=("left", "right", "right", "right", "right", "right", "right", "right", "right", "right"),
            title=title,
        ),
    ]


def _format_contact_criteria() -> list[str]:
    rows = (
        (
            "Presion admisible",
            "Servicio I",
            "Meyerhof: q = V/B' <= qadm",
        ),
        (
            "Capacidad portante LRFD",
            "Resistencia I y Evento Extremo I",
            "Meyerhof: qu = Vu/B' <= phi*qn; qn=FS*qadm",
        ),
        (
            "Diseno estructural zapata",
            "Resistencia I y Evento Extremo I",
            "Presion lineal trapezoidal/triangular para Mu y Vu",
        ),
        (
            "Fisuracion",
            "Servicio I",
            "Presion lineal trapezoidal/triangular de servicio",
        ),
    )
    return [
        "",
        *boxed_table(
            ("Uso", "Combinacion", "Metodo"),
            rows,
            aligns=("left", "left", "left"),
            title="CRITERIO GEOTECNICO Y ESTRUCTURAL DE ZAPATA",
        ),
    ]


def _format_stability(title: str, result: AbutmentDesignResult, states: tuple[StabilityStateResult, ...]) -> list[str]:
    lines = ["", *audit_subtitle("", title, 112)]
    data = result.inputs
    b = data.geometry.footing_width_m
    phi = data.soil.friction_angle_deg
    bearing_fs = data.soil.bearing_capacity_factor_fs
    q_allow = data.soil.allowable_bearing_kg_cm2
    for state in states:
        abs_e = abs(state.eccentricity_m)
        qmax_operation = (
            f"2*{state.vu_tn_m:.3f}/{state.contact_length_m:.3f}/10"
            if state.contact_type != "Completo"
            else f"{state.vu_tn_m:.3f}/{b:.3f}*(1+6*{abs_e:.3f}/{b:.3f})/10"
        )
        rows = [
            ("Vu", "sum(gamma_i*P_i vertical)", f"{state.vu_tn_m:.3f} Tn/m"),
            ("MVu estabilizante", "sum(gamma_i*P_i*x_i)", f"{state.stabilizing_moment_tn_m_m:.3f} Tn*m/m"),
            ("Hu", "sum(gamma_i*H_i horizontal)", f"{state.hu_tn_m:.3f} Tn/m"),
            ("MHu volcador", "sum(gamma_i*H_i*y_i)", f"{state.overturning_moment_tn_m_m:.3f} Tn*m/m"),
            ("x resultante", f"({state.stabilizing_moment_tn_m_m:.3f}-{state.overturning_moment_tn_m_m:.3f})/{state.vu_tn_m:.3f}", f"{state.resultant_x_m:.3f} m"),
            ("Excentricidad e", f"{b:.3f}/2 - {state.resultant_x_m:.3f}", f"{state.eccentricity_m:.3f} m"),
            ("Limite emax", f"contacto minimo Lc/B={state.minimum_contact_length_ratio:.3f}; B={b:.3f}", f"{state.eccentricity_limit_m:.3f} m"),
            ("Resistencia por friccion Ff", f"{state.vu_tn_m:.3f}*tan({phi:.3f})", f"{state.friction_resistance_tn_m:.3f} Tn/m"),
            ("B' Meyerhof", f"{b:.3f} - 2*|{state.eccentricity_m:.3f}|", f"{state.effective_width_m:.3f} m"),
            ("q Meyerhof", f"{state.vu_tn_m:.3f}/{state.effective_width_m:.3f}/10", f"{state.geotechnical_pressure_kg_cm2:.3f} kg/cm2"),
            ("q limite suelo", _bearing_limit_formula(state, result), f"{state.q_allow_kg_cm2:.3f} kg/cm2"),
            ("Tipo de contacto", "completo o parcial triangular", state.contact_type),
            ("Longitud comprimida Lc", f"{state.contact_length_m:.3f}/{b:.3f}", f"{state.contact_length_ratio:.3f} B"),
            ("qmax estructural", qmax_operation, f"{state.qmax_kg_cm2:.3f} kg/cm2"),
            ("qmin estructural adoptado", "suelo sin traccion", f"{state.qmin_kg_cm2:.3f} kg/cm2"),
            ("Vuelco", f"{abs_e:.3f} <= {state.eccentricity_limit_m:.3f}", state.overturning_status),
            ("Deslizamiento sin diente", f"{state.friction_resistance_tn_m:.3f} >= {state.hu_tn_m:.3f}", state.sliding_status),
        ]
        zero_distance = _zero_pressure_distance_from_toe(state, b)
        if zero_distance is not None:
            rows.insert(
                -2,
                (
                    "x(q=0) desde punta",
                    "distancia donde inicia/termina contacto",
                    f"{zero_distance:.3f} m",
                ),
            )
        if state.key_resistance_tn_m is not None:
            rows.append(
                (
                    "Deslizamiento con diente",
                    f"{state.key_resistance_tn_m:.3f} >= {state.hu_tn_m:.3f}",
                    state.sliding_with_key_status or "-",
                )
            )
        rows.append(
            (
                "Presion de contacto",
                f"q={state.geotechnical_pressure_kg_cm2:.3f} <= {state.q_allow_kg_cm2:.3f}",
                state.bearing_status,
            )
        )
        lines.extend(
            [
                "",
                *boxed_table(
                    ("Concepto", "Operacion matematica", "Valor"),
                    tuple(rows),
                    aligns=("left", "left", "right"),
                    title=state.name,
                ),
            ]
        )
    return lines


def _bearing_limit_formula(state: StabilityStateResult, result: AbutmentDesignResult) -> str:
    soil = result.inputs.soil
    if state.name == "Servicio I":
        return f"qadm={soil.allowable_bearing_kg_cm2:.3f}"
    phi = state.q_allow_kg_cm2 / (soil.bearing_capacity_factor_fs * soil.allowable_bearing_kg_cm2)
    return f"{phi:.2f}*{soil.bearing_capacity_factor_fs:.3f}*{soil.allowable_bearing_kg_cm2:.3f}"


def _zero_pressure_distance_from_toe(state: StabilityStateResult, footing_width_m: float) -> float | None:
    if state.contact_type == "Completo":
        return None
    if state.resultant_x_m <= footing_width_m / 2.0:
        return state.contact_length_m
    return footing_width_m - state.contact_length_m


def _format_footing_width_recommendation(result: AbutmentDesignResult) -> list[str]:
    recommendation = result.footing_width_recommendation
    if recommendation is None:
        return []
    status = "OK" if recommendation.found_compliant_width else "REVISAR vuelco/q Meyerhof"
    if recommendation.found_compliant_width:
        width_criterion = f"incrementos de {recommendation.increment_step_m:.2f} m recalculando cargas"
        width_value = f"{recommendation.recommended_width_m:.3f} m"
    else:
        width_criterion = (
            f"incrementos de {recommendation.increment_step_m:.2f} m hasta "
            f"{recommendation.search_max_width_m:.2f} m"
        )
        width_value = "no se encontro B que cumpla"
    rows = (
        ("Ancho ingresado B", "-", f"{recommendation.current_width_m:.3f} m"),
        ("Caso critico", "estado que no cumple vuelco o presion Meyerhof/capacidad", recommendation.controlling_case),
        ("q Meyerhof actual", "presion geotecnica del caso critico", f"{recommendation.current_geotechnical_pressure_kg_cm2:.3f} kg/cm2"),
        ("qmin lineal actual", "diagnostico para diagrama estructural", f"{recommendation.current_min_qmin_kg_cm2:.3f} kg/cm2"),
        (
            "Ancho recomendado B",
            width_criterion,
            width_value,
        ),
        ("q Meyerhof con B recomendado", "maximo de todos los estados", f"{recommendation.recommended_max_geotechnical_pressure_kg_cm2:.3f} kg/cm2"),
        ("qmin estructural con B recomendado", "minimo de todos los estados", f"{recommendation.recommended_min_qmin_kg_cm2:.3f} kg/cm2"),
        ("qmax estructural con B recomendado", "maximo de todos los estados", f"{recommendation.recommended_max_qmax_kg_cm2:.3f} kg/cm2"),
        ("Estado con B recomendado", "vuelco y Meyerhof/capacidad por estado limite", status),
    )
    return [
        "",
        *boxed_table(
            ("Concepto", "Criterio", "Valor"),
            rows,
            aligns=("left", "left", "right"),
            title="RECOMENDACION DE ANCHO DE ZAPATA",
        ),
    ]


def _format_key(result: AbutmentDesignResult) -> list[str]:
    if result.key is None:
        return ["", *audit_subtitle("", "DIENTE DE CONCRETO NO CONSIDERADO", 112)]
    rows = []
    key_states = result.with_bridge if result.inputs.is_pure_wall else result.without_bridge
    for state in key_states:
        rows.append(
            (
                state.name,
                f"{state.friction_resistance_tn_m:.3f}",
                f"{state.hu_tn_m:.3f}",
                state.sliding_status,
                f"{state.key_resistance_tn_m:.3f}",
                state.sliding_with_key_status or "-",
            )
        )
    return [
        "",
        *key_value_box(
            "RESISTENCIA PASIVA DEL DIENTE",
            (
                ("k'p = tan^2(45 + phi/2)", f"{result.key.passive_coefficient_prime:.3f}"),
                ("kp = k'p", f"{result.key.kp:.3f}"),
                ("h frontal sobre cabeza del diente", f"{result.inputs.geometry.front_soil_depth_m:.3f} m"),
                (
                    "Empuje pasivo relleno frontal superior",
                    "SI" if result.inputs.key.consider_upper_front_passive else "NO",
                ),
                ("Rep superior", f"{result.key.upper_front_passive_resistance_tn_m:.3f} Ton/m"),
                ("Presion superior", f"{result.key.top_pressure_tn_m2:.3f} Ton/m2"),
                ("Presion inferior", f"{result.key.bottom_pressure_tn_m2:.3f} Ton/m2"),
                ("Rep diente", f"{result.key.passive_resistance_tn_m:.3f} Ton/m"),
                ("Rep total", f"{result.key.total_passive_resistance_tn_m:.3f} Ton/m"),
                ("phi_ep Rep total", f"{result.key.factored_passive_tn_m:.3f} Ton/m"),
                ("Referencia", ABUTMENT_KEY_REFERENCE),
            ),
            width=112,
        ),
        "",
        *boxed_table(
            ("Estado" if result.inputs.is_pure_wall else "Estado sin puente", "Ff", "Hu", "Sin diente", "Ff+phiEpRep", "Con diente"),
            rows,
            aligns=("left", "right", "right", "center", "right", "center"),
            title="APLICACION DEL DIENTE EN DESLIZAMIENTO",
        ),
    ]


def _format_structural_design(
    result: AbutmentDesignResult,
    case_filter: set[str] | None = None,
) -> list[str]:
    lines: list[str] = []
    cases = [result.stem_design, result.heel_design, result.toe_design]
    if result.key_design is not None:
        cases.append(result.key_design)
    for case in cases:
        if case_filter is not None and case.name not in case_filter:
            continue
        lines.extend(
            [
                "",
                *key_value_box(
                    f"DISENO ESTRUCTURAL - {case.name}",
                    (
                        ("Momento ultimo Mu", f"{case.controlling_moment_tn_m_m:.3f} Tn*m/m"),
                        ("Peralte efectivo d", f"{case.effective_depth_cm:.2f} cm"),
                        ("As por flexion", f"{case.strength_as_cm2_m:.3f} cm2/m"),
                        (
                            "Mcr",
                            f"{case.cracking_moment_tn_m_m:.3f} Tn*m/m",
                        ),
                        (
                            "1.33Mu",
                            f"{case.multiplier_minimum_moment_tn_m_m:.3f} Tn*m/m",
                        ),
                        (
                            "Momento minimo adoptado",
                            "min(Mcr, 1.33Mu) = "
                            f"{case.minimum_capacity_moment_tn_m_m:.3f} Tn*m/m",
                        ),
                        (
                            "As por capacidad minima",
                            f"{case.capacity_minimum_as_cm2_m:.3f} cm2/m",
                        ),
                        ("As temperatura", f"{case.temperature_as_cm2_m:.3f} cm2/m"),
                        (
                            "Operacion As requerido",
                            "max(As flexion, As temperatura, As capacidad minima)",
                        ),
                        ("As requerido", f"{case.required_as_cm2_m:.3f} cm2/m"),
                        ("Control As requerido", _required_as_control(case)),
                        ("As provisto", f"{case.provided_as_cm2_m:.3f} cm2/m"),
                        ("Acero seleccionado", f"{case.selected_bar_label} @ {case.selected_spacing_m:.3f} m"),
                        ("Origen del acero", "USUARIO" if case.is_custom_selection else "TABLA"),
                        ("Momento resistente Mr", f"{case.moment_resistance_tn_m_m:.3f} Tn*m/m"),
                        ("Estado a flexion", case.moment_status),
                        ("Cortante ultimo Vu", f"{case.shear_demand_tn_m:.3f} Tn/m"),
                        ("Resistencia cortante Vr", f"{case.shear_resistance_tn_m:.3f} Tn/m"),
                        ("Estado a corte", case.shear_status),
                        ("Criterio", case.notes),
                    ),
                    width=112,
                ),
            ]
        )
    return lines


def _required_as_control(case: StructuralDesignCase) -> str:
    controls = (
        ("As flexion", case.strength_as_cm2_m),
        ("As temperatura", case.temperature_as_cm2_m),
        ("As capacidad minima", case.capacity_minimum_as_cm2_m),
    )
    label, value = max(controls, key=lambda item: item[1])
    return f"{label} = {value:.3f} cm2/m"


def _format_stem_reinforcement_cut(result: AbutmentDesignResult) -> list[str]:
    cut = result.stem_reinforcement_cut
    if cut is None:
        return [
            "",
            *key_value_box(
                "CORTE DE ACERO PRINCIPAL DE PANTALLA",
                (
                    ("Estado", "NO APLICA"),
                    ("Criterio", "El acero seleccionado no permite una reduccion practica con un solo corte."),
                ),
                width=112,
            ),
        ]
    return [
        "",
        *key_value_box(
            "CORTE DE ACERO PRINCIPAL DE PANTALLA",
            (
                ("Acero inferior de diseno", f"{cut.lower_bar_label} @ {cut.lower_spacing_m:.3f} m"),
                ("As inferior provisto", f"{cut.lower_provided_as_cm2_m:.3f} cm2/m"),
                ("Acero continuo superior", f"{cut.upper_bar_label} @ {cut.upper_spacing_m:.3f} m"),
                ("As superior provisto", f"{cut.upper_provided_as_cm2_m:.3f} cm2/m"),
                ("Patron constructivo", f"Continua 1 de cada {cut.continuous_every_n_bars} barras inferiores"),
                ("As minimo adoptado", f"{cut.minimum_as_cm2_m:.3f} cm2/m"),
                ("Altura teorica de corte", f"{cut.theoretical_cut_height_m:.3f} m sobre zapata"),
                ("Prolongacion por desarrollo", f"{cut.development_extension_m:.3f} m"),
                ("Altura constructiva de corte", f"{cut.constructive_cut_height_m:.3f} m sobre zapata"),
                ("Longitud barras cortadas", f"{cut.lower_cut_bar_length_m:.3f} m"),
                ("Longitud barras continuas", f"{cut.continuous_bar_length_m:.3f} m"),
                ("Mu en corte teorico", f"{cut.controlling_moment_at_cut_tn_m_m:.3f} Tn*m/m"),
                ("As requerido en corte", f"{cut.required_as_at_cut_cm2_m:.3f} cm2/m"),
                ("Estado", cut.status),
                ("Criterio", cut.notes),
            ),
            width=112,
        ),
    ]


def _format_secondary_reinforcement(result: AbutmentDesignResult) -> list[str]:
    lines = ["", *audit_subtitle("", "ACERO SECUNDARIO Y TRANSVERSAL MINIMO", 112)]
    for case in result.secondary_reinforcement:
        lines.extend(
            [
                "",
                *key_value_box(
                    case.name,
                    (
                        ("Elemento", case.element),
                        ("Cara", case.face),
                        ("Direccion", case.direction),
                        ("As requerido", f"{case.required_as_cm2_m:.3f} cm2/m"),
                        ("As provisto", f"{case.provided_as_cm2_m:.3f} cm2/m"),
                        ("Acero seleccionado", f"{case.selected_bar_label} @ {case.selected_spacing_m:.3f} m"),
                        ("Origen del acero", "USUARIO" if case.is_custom_selection else "TABLA"),
                        ("Estado", case.status),
                        ("Criterio", case.notes),
                    ),
                    width=96,
                ),
            ]
        )
    lines.extend(
        [
            "",
            (
                "Referencia: "
                "Manual de Puentes MTC 2018 / AASHTO LRFD, refuerzo minimo "
                "por retraccion y temperatura adoptado en el proyecto."
            ),
        ]
    )
    return lines


def _format_crack_checks(result: AbutmentDesignResult) -> list[str]:
    return [
        "",
        *boxed_table(
            ("Elemento", "Ms serv", "fs", "fs usado", "dc", "beta_s", "s prov", "s max", "Estado"),
            (
                (
                    check.element,
                    f"{check.service_moment_tn_m_m:.3f}",
                    f"{check.steel_stress_kg_cm2:.0f}",
                    f"{check.steel_stress_used_kg_cm2:.0f}",
                    f"{check.dc_cm:.2f}",
                    f"{check.beta_s:.3f}",
                    f"{check.provided_spacing_m:.3f}",
                    f"{check.maximum_spacing_m:.3f}",
                    check.status,
                )
                for check in result.crack_checks
            ),
            aligns=("left", "right", "right", "right", "right", "right", "right", "right", "center"),
            title="CONTROL DE FISURACION",
        ),
    ]


def _format_development_checks(result: AbutmentDesignResult) -> list[str]:
    return [
        "",
        *boxed_table(
            ("Elemento", "Barra", "ldb", "ld recto", "ld gancho", "ext gancho", "ld disp", "Tipo", "Estado"),
            (
                (
                    check.element,
                    check.bar_label,
                    f"{check.basic_ld_cm:.2f}",
                    f"{check.required_ld_cm:.2f}",
                    f"{check.required_hooked_ld_cm:.2f}",
                    f"{check.hook_extension_cm:.2f}",
                    f"{check.available_length_cm:.2f}",
                    check.anchorage_type,
                    check.status,
                )
                for check in result.development_checks
            ),
            aligns=("left", "center", "right", "right", "right", "right", "right", "center", "center"),
            title="DESARROLLO Y ANCLAJE DE BARRAS",
        ),
    ]


def _format_bar_details(result: AbutmentDesignResult) -> list[str]:
    return [
        "",
        *boxed_table(
            ("Marca", "Elemento", "Cara/ubicacion", "Barra", "s", "L barra", "Anclaje"),
            (
                (
                    detail.mark,
                    detail.element,
                    detail.face,
                    detail.bar_label,
                    f"{detail.spacing_m:.3f}",
                    f"{detail.length_m:.3f}",
                    f"{detail.anchorage_m:.3f}",
                )
                for detail in result.bar_details
            ),
            aligns=("center", "left", "left", "center", "right", "right", "right"),
            title="CUADRO DE DETALLE DE ACERO",
        ),
    ]
