"""Terminal entry point for reinforced concrete cantilever wall design."""

import sys

from bridge_design.abutment_main import run_abutment_design
from bridge_design.cli.yaml_inputs import cantilever_wall_inputs_from_yaml, cantilever_wall_yaml_template
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
from bridge_design.domain.cantilever_wall import cantilever_wall_load_inputs


def _run_wall_design(inputs=None) -> None:
    run_abutment_design(
        inputs=inputs,
        input_title=(
            "DISENO DE MURO DE CONCRETO ARMADO EN CANTILEVER - "
            "FRANJA DE 1.00 m"
        ),
        defaults_note=(
            "Normativa base: Manual de Puentes MTC 2018 / AASHTO LRFD. "
            "Incluye empuje sismico Mononobe-Okabe y Evento Extremo I."
        ),
        element_label="muro",
        load_defaults=cantilever_wall_load_inputs(),
        option_title="SELECCION DE ACERO DE MURO CANTILEVER",
        selection_title="ACEROS SELECCIONADOS - MURO CANTILEVER",
        report_title="DISENO DE MURO DE CONCRETO ARMADO EN CANTILEVER",
        primary_stability_title="MURO PURO",
        include_bridge_inputs=False,
        generate_word_report=True,
    )


def _run_yaml_mode(args: list[str]) -> bool:
    if not is_yaml_mode(args):
        return False
    if args[0] == "output":
        path = resolve_yaml_mode_path(args, mode="output") or select_yaml_save_path(
            "Guardar plantilla YAML de muro",
            "modelo_muro.yaml",
        )
        save_yaml_file(path, cantilever_wall_yaml_template())
        print(f"Plantilla YAML guardada en: {path}")
        return True
    path = resolve_yaml_mode_path(args, mode="input") or select_yaml_open_path(
        "Seleccionar YAML de muro"
    )
    inputs = cantilever_wall_inputs_from_yaml(load_yaml_file(path))
    _run_wall_design(inputs=inputs)
    return True


def main(argv: list[str] | None = None) -> None:
    """Run the seismic cantilever wall design workflow."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"-h", "--help", "help"}:
        print_yaml_mode_help("diseno-muros")
        return
    try:
        if _run_yaml_mode(args):
            return
    except (YamlModeError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    _run_wall_design()


if __name__ == "__main__":
    main()
