"""Terminal prompts for cantilever abutment design."""

from dataclasses import replace

from bridge_design.cli.input_prompts import prompt_float, prompt_non_negative_float
from bridge_design.domain.abutment import (
    AbutmentDesignResult,
    AbutmentGeometryInputs,
    AbutmentInputs,
    AbutmentKeyInputs,
    AbutmentLoadInputs,
    AbutmentMaterialInputs,
    AbutmentSoilInputs,
    GAMMA_EQ_DEFAULT,
    equivalent_vehicular_surcharge_height_m,
)
from bridge_design.domain.cantilever_wall import cantilever_wall_geometry_inputs, cantilever_wall_load_inputs
from bridge_design.domain.rebar_catalog import (
    REINFORCING_BAR_CATALOG,
    ReinforcementCaseOptions,
    ReinforcementSpacingOption,
    custom_spacing_option,
)


def collect_abutment_inputs(
    title: str = "DISENO DE ESTRIBO TIPO CANTILEVER - FRANJA DE 1.00 m",
    defaults_note: str = "Valores por defecto calibrados con docs/Diseno_estribo_rev.xlsx.",
    element_label: str = "estribo",
    load_defaults: AbutmentLoadInputs | None = None,
    load_title: str = "REACCIONES DEL TABLERO POR METRO LINEAL DE ESTRIBO",
    load_note: str = "Use Ton/m. PPL es peatonal vertical de tablero; PLL+IM es vehicular con impacto.",
    include_bridge_inputs: bool = True,
    collect_key: bool = True,
) -> AbutmentInputs:
    """Collect abutment design inputs from terminal."""
    print("=" * 72)
    print(title)
    print("=" * 72)
    print(defaults_note)

    geometry = _collect_geometry(include_bridge_inputs=include_bridge_inputs)
    materials = _collect_materials()
    if include_bridge_inputs:
        loads = _collect_loads(load_defaults, load_title, load_note)
    else:
        loads = cantilever_wall_load_inputs()
    soil = _collect_soil(geometry, element_label)
    gamma_eq = _prompt_gamma_eq(GAMMA_EQ_DEFAULT)
    key = (
        collect_abutment_key(default_passive_soil_height_m=geometry.front_soil_depth_m)
        if include_bridge_inputs and collect_key
        else AbutmentKeyInputs(
            enabled=False,
            passive_soil_height_m=geometry.front_soil_depth_m,
        )
    )
    return AbutmentInputs(
        materials=materials,
        geometry=geometry,
        loads=loads,
        soil=soil,
        key=key,
        is_pure_wall=not include_bridge_inputs,
        gamma_eq=gamma_eq,
    )


def _collect_geometry(include_bridge_inputs: bool = True) -> AbutmentGeometryInputs:
    default = AbutmentGeometryInputs() if include_bridge_inputs else cantilever_wall_geometry_inputs()
    print()
    print("GEOMETRIA")
    retained_height_label = (
        "H activo - altura de relleno posterior desde fondo de zapata"
        if include_bridge_inputs
        else "Altura total del muro desde fondo de zapata"
    )
    retained_height = prompt_float(retained_height_label, "m", default.retained_height_m)
    bridge_length = (
        prompt_float("L - Luz del puente tributaria", "m", default.bridge_length_m)
        if include_bridge_inputs
        else default.bridge_length_m
    )
    footing_width = prompt_float("B - Ancho total de zapata", "m", default.footing_width_m)
    footing_thickness = prompt_float("D - Espesor de zapata", "m", default.footing_thickness_m)
    front_soil_default = default.front_soil_depth_m if include_bridge_inputs else footing_thickness
    geometry_kwargs = {
        "retained_height_m": retained_height,
        "bridge_length_m": bridge_length,
        "footing_width_m": footing_width,
        "footing_thickness_m": footing_thickness,
        "toe_length_m": prompt_float("Longitud de puntera", "m", default.toe_length_m),
        "lower_stem_thickness_m": prompt_float("Espesor inferior de pantalla", "m", default.lower_stem_thickness_m),
        "upper_stem_thickness_m": prompt_float("Espesor superior de pantalla", "m", default.upper_stem_thickness_m),
        "backfill_step_width_m": 0.0,
        "front_soil_depth_m": prompt_non_negative_float(
            "h frontal - altura de suelo frontal desde fondo de zapata",
            "m",
            front_soil_default,
        ),
    }
    if not include_bridge_inputs:
        geometry_kwargs.update(
            {
                "seat_block_height_m": 0.0,
                "seat_wall_width_m": 0.0,
                "bearing_seat_length_m": 0.0,
                "backwall_drop_m": 0.0,
                "backwall_taper_height_m": 0.0,
                "top_step_thickness_m": 0.0,
                "small_batter_width_m": 0.0,
                "bridge_seat_to_bearing_height_m": 0.0,
            }
        )
    if include_bridge_inputs:
        geometry_kwargs.update(
            {
                "small_batter_width_m": prompt_non_negative_float("t1 - Transicion frontal superior", "m", default.small_batter_width_m),
                "backfill_step_width_m": prompt_non_negative_float("t2 - Retiro superior del relleno", "m", default.backfill_step_width_m),
                "bearing_seat_length_m": prompt_non_negative_float("cajuela - Longitud horizontal de apoyo", "m", default.bearing_seat_length_m),
                "seat_wall_width_m": prompt_non_negative_float("e parapeto - Espesor parapeto posterior", "m", default.seat_wall_width_m),
                "seat_block_height_m": prompt_non_negative_float("altura cajuela - Altura del parapeto superior", "m", default.seat_block_height_m),
                "backwall_drop_m": prompt_non_negative_float("altura bloque cajuela", "m", default.backwall_drop_m),
                "backwall_taper_height_m": prompt_non_negative_float("altura transicion", "m", default.backwall_taper_height_m),
            }
        )
    geometry = replace(
        default,
        **geometry_kwargs,
    )
    return geometry


def _collect_materials() -> AbutmentMaterialInputs:
    default = AbutmentMaterialInputs()
    print()
    print("MATERIALES")
    concrete_strength = prompt_float("f'c concreto", "kg/cm2", default.concrete_strength_kg_cm2)
    steel_yield = prompt_float("fy acero", "kg/cm2", default.steel_yield_kg_cm2)
    concrete_unit_weight_tn_m3 = prompt_float(
        "Peso unitario concreto",
        "Tn/m3",
        default.concrete_unit_weight_kg_m3 / 1000.0,
    )
    soil_unit_weight_tn_m3 = prompt_float(
        "Peso unitario relleno",
        "Tn/m3",
        default.soil_unit_weight_kg_m3 / 1000.0,
    )
    return AbutmentMaterialInputs(
        concrete_strength_kg_cm2=concrete_strength,
        steel_yield_kg_cm2=steel_yield,
        concrete_unit_weight_kg_m3=concrete_unit_weight_tn_m3 * 1000.0,
        soil_unit_weight_kg_m3=soil_unit_weight_tn_m3 * 1000.0,
    )


def _collect_loads(
    default: AbutmentLoadInputs | None = None,
    title: str = "REACCIONES DEL TABLERO POR METRO LINEAL DE ESTRIBO",
    note: str = "Use Ton/m. PPL es peatonal vertical de tablero; PLL+IM es vehicular con impacto.",
) -> AbutmentLoadInputs:
    if default is None:
        default = AbutmentLoadInputs()
    print()
    print(title)
    print(note)
    return AbutmentLoadInputs(
        pdc_tn_m=prompt_non_negative_float("PDC - carga muerta tablero", "Ton/m", default.pdc_tn_m),
        pdw_tn_m=prompt_non_negative_float("PDW - asfalto/superficie", "Ton/m", default.pdw_tn_m),
        ppl_tn_m=prompt_non_negative_float("PPL - carga peatonal tablero", "Ton/m", default.ppl_tn_m),
        pll_im_tn_m=prompt_non_negative_float("PLL+IM - carga viva vehicular", "Ton/m", default.pll_im_tn_m),
        braking_tn_m=prompt_non_negative_float("BR - fuerza de frenado", "Ton/m", default.braking_tn_m),
    )


def _collect_soil(
    geometry: AbutmentGeometryInputs,
    element_label: str = "estribo",
) -> AbutmentSoilInputs:
    default = AbutmentSoilInputs()
    default_h_eq = equivalent_vehicular_surcharge_height_m(geometry.retained_height_m)
    print()
    print("SUELO, SOBRECARGA EN RELLENO Y SISMO")
    print(f"h' vehicular no es siempre 0.60 m; se interpola segun la altura del {element_label}.")
    vehicular_surcharge_height = prompt_non_negative_float(
        "h' sobrecarga vehicular equivalente",
        "m",
        default_h_eq,
    )
    allowable_bearing = prompt_float(
        "qadm capacidad portante admisible",
        "kg/cm2",
        default.allowable_bearing_kg_cm2,
    )
    friction_angle = prompt_float("Angulo de friccion del relleno", "grados", default.friction_angle_deg)
    wall_soil_friction = prompt_non_negative_float("delta muro-suelo", "grados", default.wall_soil_friction_deg)
    backfill_slope = prompt_non_negative_float("beta pendiente del relleno", "grados", default.backfill_slope_deg)
    wall_backface_angle = _prompt_wall_backface_angle(
        friction_angle,
        wall_soil_friction,
        backfill_slope,
        default.wall_backface_angle_deg,
    )
    return AbutmentSoilInputs(
        vehicular_surcharge_height_m=vehicular_surcharge_height,
        allowable_bearing_kg_cm2=allowable_bearing,
        friction_angle_deg=friction_angle,
        wall_soil_friction_deg=wall_soil_friction,
        backfill_slope_deg=backfill_slope,
        wall_backface_angle_deg=wall_backface_angle,
        bearing_capacity_factor_fs=prompt_float("FS capacidad portante nominal", "-", default.bearing_capacity_factor_fs),
        pga=prompt_non_negative_float("PGA", "-", default.pga),
        fpga=prompt_float("Fpga", "-", default.fpga),
        pedestrian_surcharge_tn_m2=prompt_non_negative_float(
            "Sobrecarga peatonal en relleno/acceso",
            "Ton/m2",
            default.pedestrian_surcharge_tn_m2,
        ),
    )


def _prompt_gamma_eq(default: float) -> float:
    while True:
        value = prompt_non_negative_float(
            "gamma_EQ factor de carga viva con sismo (0 a 1; 0=sin viva, 1=viva completa)",
            "-",
            default,
        )
        if value <= 1.0:
            return value
        print("gamma_EQ debe estar entre 0 y 1.")


def _prompt_wall_backface_angle(
    friction_angle_deg: float,
    wall_soil_friction_deg: float,
    backfill_slope_deg: float,
    default: float,
) -> float:
    """Prompt Coulomb wall-back angle measured from horizontal."""
    while True:
        angle = prompt_float(
            "theta cara posterior desde horizontal; vertical=90",
            "grados",
            default,
        )
        try:
            AbutmentSoilInputs(
                friction_angle_deg=friction_angle_deg,
                wall_soil_friction_deg=wall_soil_friction_deg,
                backfill_slope_deg=backfill_slope_deg,
                wall_backface_angle_deg=angle,
            )
        except ValueError as exc:
            print(str(exc))
            continue
        return angle


def collect_abutment_key(
    default_passive_soil_height_m: float | None = None,
    default_height_m: float | None = None,
) -> AbutmentKeyInputs:
    default = AbutmentKeyInputs()
    passive_soil_height = (
        default.passive_soil_height_m
        if default_passive_soil_height_m is None
        else default_passive_soil_height_m
    )
    key_height = default.height_m if default_height_m is None else default_height_m
    print()
    print("DIENTE DE CONCRETO EN BASE")
    enabled = _prompt_yes_no("Considerar diente si falla deslizamiento", default.enabled)
    if not enabled:
        return AbutmentKeyInputs(
            enabled=False,
            passive_soil_height_m=passive_soil_height,
        )
    consider_upper_front_passive = (
        _prompt_yes_no("Considerar empuje pasivo del relleno frontal superior", default.consider_upper_front_passive)
        if passive_soil_height > 0.0
        else False
    )
    return AbutmentKeyInputs(
        enabled=True,
        height_m=prompt_float("h die - altura de diente", "m", key_height),
        width_m=prompt_float("b die - ancho de diente", "m", default.width_m),
        passive_soil_height_m=passive_soil_height,
        consider_upper_front_passive=consider_upper_front_passive,
    )


def _collect_key() -> AbutmentKeyInputs:
    return collect_abutment_key()


def _prompt_yes_no(label: str, default: bool) -> bool:
    suffix = "S/n" if default else "s/N"
    while True:
        raw = input(f"{label} [{suffix}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("s", "si", "y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("Ingrese si o no.")


def collect_abutment_reinforcement_selection(
    result: AbutmentDesignResult,
    element_label: str = "estribo",
) -> tuple[tuple[str, ReinforcementSpacingOption], ...]:
    """Allow the user to keep or change abutment reinforcement distributions."""
    cases = _abutment_reinforcement_cases(result)
    answer = input(
        f"\nDesea seleccionar o cambiar las distribuciones de acero del {element_label}? [s/N]: "
    ).strip().lower()
    if answer not in ("s", "si", "y", "yes"):
        return _default_abutment_reinforcement_selection(cases)

    selected: list[tuple[str, ReinforcementSpacingOption]] = []
    for code, case_options in cases:
        selected.append((f"{code}. {case_options.label}", _prompt_spacing_option(case_options)))
    return tuple(selected)


def abutment_reinforcement_selection_by_name(
    selected: tuple[tuple[str, ReinforcementSpacingOption], ...],
) -> dict[str, ReinforcementSpacingOption]:
    """Return selected reinforcement keyed by abutment design case name."""
    return {
        label.partition(". ")[2]: option
        for label, option in selected
    }


def _abutment_reinforcement_cases(
    result: AbutmentDesignResult,
) -> tuple[tuple[str, ReinforcementCaseOptions], ...]:
    options = [
        result.stem_design.spacing_options,
        result.heel_design.spacing_options,
        result.toe_design.spacing_options,
    ]
    if result.key_design is not None:
        options.append(result.key_design.spacing_options)
    for secondary in result.secondary_reinforcement:
        options.append(secondary.spacing_options)

    return tuple(
        (chr(ord("A") + index), case_options)
        for index, case_options in enumerate(
            sorted(options, key=lambda case_options: _reinforcement_group_rank(case_options.label))
        )
    )


def _reinforcement_group_rank(label: str) -> int:
    if label.startswith("Pantalla"):
        return 0
    if label.startswith("Zapata"):
        return 1
    return 2


def _default_abutment_reinforcement_selection(
    cases: tuple[tuple[str, ReinforcementCaseOptions], ...],
) -> tuple[tuple[str, ReinforcementSpacingOption], ...]:
    selected: list[tuple[str, ReinforcementSpacingOption]] = []
    for code, case_options in cases:
        recommended = case_options.recommended or case_options.options[-1]
        selected.append((f"{code}. {case_options.label}", recommended))
    return tuple(selected)


def _prompt_spacing_option(
    case_options: ReinforcementCaseOptions,
) -> ReinforcementSpacingOption:
    recommended = case_options.recommended
    default_item = recommended.item if recommended is not None else case_options.options[-1].item
    valid_items = {option.item: option for option in case_options.options}
    while True:
        raw_value = input(
            f"{case_options.label} - elija item [{default_item}] (P=personalizado): "
        ).strip()
        if not raw_value:
            return valid_items[default_item]
        if raw_value.lower() in ("p", "personalizado", "personalizada"):
            return _prompt_custom_spacing_option(case_options)
        try:
            item = int(raw_value)
        except ValueError:
            print("Ingrese un item numerico de la tabla.")
            continue
        if item not in valid_items:
            print("El item no existe para este caso.")
            continue
        return valid_items[item]


def _prompt_custom_spacing_option(
    case_options: ReinforcementCaseOptions,
) -> ReinforcementSpacingOption:
    recommended = case_options.recommended or case_options.options[-1]
    labels = ", ".join(bar.label for bar in REINFORCING_BAR_CATALOG)
    print(f"Barras disponibles: {labels}")
    while True:
        bar_label = input(
            f"{case_options.label} - barra personalizada [{recommended.bar.label}]: "
        ).strip() or recommended.bar.label
        raw_spacing = input(
            f"{case_options.label} - separacion personalizada en m "
            f"[{recommended.spacing_m:.3f}]: "
        ).strip()
        try:
            spacing_m = recommended.spacing_m if not raw_spacing else float(raw_spacing.replace(",", "."))
            return custom_spacing_option(case_options, bar_label, spacing_m)
        except ValueError as exc:
            print(f"Configuracion personalizada no valida: {exc}")
