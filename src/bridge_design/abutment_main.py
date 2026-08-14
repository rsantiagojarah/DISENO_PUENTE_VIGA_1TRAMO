"""Terminal entry point for cantilever abutment design."""

from dataclasses import replace
from math import ceil, sqrt
import sys

from bridge_design.cli.abutment_ascii_output import (
    format_abutment_footing_width_recommendation,
    format_abutment_design_result,
    format_abutment_reinforcement_option_tables,
    format_abutment_reinforcement_selection,
)
from bridge_design.cli.yaml_inputs import abutment_inputs_from_yaml, abutment_yaml_template
from bridge_design.cli.yaml_io import (
    YamlModeError,
    is_yaml_mode,
    load_yaml_file,
    print_yaml_mode_help,
    resolve_yaml_mode_path,
    save_yaml_file,
    select_yaml_open_path,
    select_yaml_save_path,
)
from bridge_design.cli.abutment_input_prompts import (
    abutment_reinforcement_selection_by_name,
    collect_abutment_inputs,
    collect_abutment_key,
    collect_abutment_reinforcement_selection,
)
from bridge_design.domain.abutment import (
    AbutmentDesignResult,
    AbutmentInputs,
    AbutmentKeyInputs,
    AbutmentLoadInputs,
    rankine_passive_coefficient,
    solve_abutment_design,
)


def run_abutment_design(
    *,
    inputs: AbutmentInputs | None = None,
    input_title: str = "DISENO DE ESTRIBO TIPO CANTILEVER - FRANJA DE 1.00 m",
    defaults_note: str = "Valores por defecto calibrados con docs/Diseno_estribo_rev.xlsx.",
    element_label: str = "estribo",
    load_defaults: AbutmentLoadInputs | None = None,
    load_title: str = "REACCIONES DEL TABLERO POR METRO LINEAL DE ESTRIBO",
    load_note: str = "Use Ton/m. PPL es peatonal vertical de tablero; PLL+IM es vehicular con impacto.",
    option_title: str = "SELECCION DE ACERO DE ESTRIBO",
    selection_title: str = "ACEROS SELECCIONADOS - ESTRIBO",
    report_title: str = "DISENO DE ESTRIBO TIPO CANTILEVER",
    primary_stability_title: str = "CON PUENTE",
    secondary_stability_title: str = "SIN PUENTE",
    include_bridge_inputs: bool = True,
    include_stem_reinforcement_cut: bool = True,
) -> None:
    """Run the cantilever retaining structure design workflow."""
    if inputs is None:
        inputs = collect_abutment_inputs(
            title=input_title,
            defaults_note=defaults_note,
            element_label=element_label,
            load_defaults=load_defaults,
            load_title=load_title,
            load_note=load_note,
            include_bridge_inputs=include_bridge_inputs,
            collect_key=False,
        )
    preliminary = solve_abutment_design(inputs)
    inputs, preliminary = _consider_footing_width_when_contact_fails(inputs, preliminary)
    inputs, preliminary = _consider_key_when_sliding_fails(inputs, preliminary)
    print()
    print(format_abutment_reinforcement_option_tables(preliminary, title=option_title))
    selected = collect_abutment_reinforcement_selection(preliminary, element_label=element_label)
    print(format_abutment_reinforcement_selection(selected, title=selection_title))
    result = solve_abutment_design(
        inputs,
        selected_reinforcement=abutment_reinforcement_selection_by_name(selected),
    )
    print(
        format_abutment_design_result(
            result,
            title=report_title,
            primary_stability_title=primary_stability_title,
            secondary_stability_title=secondary_stability_title,
            include_stem_reinforcement_cut=include_stem_reinforcement_cut,
        )
    )


def _consider_footing_width_when_contact_fails(
    inputs: AbutmentInputs,
    preliminary: AbutmentDesignResult,
) -> tuple[AbutmentInputs, AbutmentDesignResult]:
    """Ask to adopt the recommended footing width before reinforcement selection."""
    while preliminary.footing_width_recommendation is not None:
        recommendation = preliminary.footing_width_recommendation
        print()
        print("La zapata no cumple el criterio de presion del suelo con la condicion actual.")
        print("Presion admisible: Servicio I con Meyerhof; LRFD: Resistencia/Evento Extremo con Meyerhof.")
        print(format_abutment_footing_width_recommendation(preliminary))
        if not _prompt_yes_no(
            f"Adoptar B recomendado = {recommendation.recommended_width_m:.2f} m",
            default=True,
        ):
            print()
            print("No se puede continuar al diseno de acero mientras la presion Meyerhof no cumpla.")
            continue
        inputs = replace(
            inputs,
            geometry=replace(inputs.geometry, footing_width_m=recommendation.recommended_width_m),
        )
        preliminary = solve_abutment_design(inputs)
    return inputs, preliminary


def _consider_key_when_sliding_fails(
    inputs: AbutmentInputs,
    preliminary: AbutmentDesignResult,
) -> tuple[AbutmentInputs, AbutmentDesignResult]:
    """Ask for a base key before reinforcement selection when sliding fails."""
    if not _has_effective_sliding_failure(preliminary):
        return inputs, preliminary
    while True:
        print()
        print("El muro no cumple deslizamiento con la condicion actual.")
        print("Ingrese un diente en la base o ajuste la geometria para continuar con un modelo estable.")
        recommended_height = _recommended_key_height_m(inputs, preliminary)
        print(f"Altura recomendada de dentellon: {recommended_height:.2f} m")
        key = collect_abutment_key(
            default_height_m=recommended_height,
            default_passive_soil_height_m=inputs.geometry.front_soil_depth_m,
        )
        if not key.enabled:
            print()
            print("No se puede continuar al diseno de acero mientras falle deslizamiento.")
            continue
        updated_inputs = replace(inputs, key=key)
        updated_result = solve_abutment_design(updated_inputs)
        if not _has_effective_sliding_failure(updated_result):
            return updated_inputs, updated_result
        print()
        print("El diente/dentellon ingresado aun no alcanza para deslizamiento.")
        print("Aumente sus dimensiones o cambie la geometria del muro.")


def _has_sliding_failure(result: AbutmentDesignResult) -> bool:
    states = result.with_bridge if result.inputs.is_pure_wall else result.without_bridge
    return any(state.sliding_status == "NO" for state in states)


def _has_effective_sliding_failure(result: AbutmentDesignResult) -> bool:
    states = result.with_bridge if result.inputs.is_pure_wall else result.without_bridge
    if result.key is None:
        return any(state.sliding_status == "NO" for state in states)
    return any(state.sliding_with_key_status != "OK" for state in states)


def _recommended_key_height_m(inputs: AbutmentInputs, result: AbutmentDesignResult) -> float:
    """Return a practical key height that covers the controlling sliding deficit."""
    states = result.with_bridge if inputs.is_pure_wall else result.without_bridge
    required_passive_tn_m = max(
        (state.hu_tn_m - state.friction_resistance_tn_m for state in states),
        default=0.0,
    )
    if required_passive_tn_m <= 0.0:
        return AbutmentKeyInputs().height_m

    key_defaults = AbutmentKeyInputs()
    gamma_soil = inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    kp = rankine_passive_coefficient(inputs.soil.friction_angle_deg)
    phi_ep = key_defaults.passive_resistance_factor
    h_passive = inputs.geometry.front_soil_depth_m
    required_nominal = required_passive_tn_m / phi_ep

    height = -h_passive + sqrt(h_passive**2.0 + 2.0 * required_nominal / (kp * gamma_soil))
    return max(key_defaults.height_m, ceil(height / 0.05) * 0.05)


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


def _run_yaml_mode(args: list[str]) -> bool:
    if not is_yaml_mode(args):
        return False
    if args[0] == "output":
        path = resolve_yaml_mode_path(args, mode="output") or select_yaml_save_path(
            "Guardar plantilla YAML de estribo",
            "modelo_estribo.yaml",
        )
        save_yaml_file(path, abutment_yaml_template(pure_wall=False))
        print(f"Plantilla YAML guardada en: {path}")
        return True
    path = resolve_yaml_mode_path(args, mode="input") or select_yaml_open_path(
        "Seleccionar YAML de estribo"
    )
    inputs = abutment_inputs_from_yaml(load_yaml_file(path), pure_wall=False)
    run_abutment_design(inputs=inputs)
    return True


def main(argv: list[str] | None = None) -> None:
    """Run the abutment design workflow."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"-h", "--help", "help"}:
        print_yaml_mode_help("diseno-estribos")
        return
    try:
        if _run_yaml_mode(args):
            return
    except (YamlModeError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    run_abutment_design()


if __name__ == "__main__":
    main()
