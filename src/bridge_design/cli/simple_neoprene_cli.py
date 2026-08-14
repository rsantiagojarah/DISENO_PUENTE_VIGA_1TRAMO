"""CLI para apoyos de neopreno simple con barras fijas o planchas moviles."""

from __future__ import annotations

import sys

from bridge_design.cli.input_prompts import prompt_float, prompt_int, prompt_non_negative_float
from bridge_design.cli.simple_neoprene_output import format_simple_neoprene_result
from bridge_design.domain.simple_neoprene_support import (
    ExternalSteelPlatePair,
    FixedBarGroup,
    SimpleNeopreneGeometry,
    SimpleSupportDemands,
    SimpleSupportInputs,
    climate_temperature,
    design_simple_neoprene_support,
)


def _prompt_choice(label: str, options: dict[str, str], default: str) -> str:
    keys = "/".join(options)
    while True:
        raw = input(f"{label} ({keys}) [{default}]: ").strip().lower()
        if not raw:
            return default
        if raw in options:
            return raw
        print(f"Opciones validas: {keys}")


def _prompt_bar_count() -> int:
    while True:
        value = prompt_int("Numero de barras (4/6/8)", 4, minimum=4)
        if value in (4, 6, 8):
            return value
        print("Ingrese 4, 6 u 8 barras.")


def collect_simple_neoprene_inputs() -> SimpleSupportInputs:
    print()
    print("=== DISENO DE APOYOS DE NEOPRENO SIMPLE - FIJO PASADORES / MOVIL PLACAS ===")
    print("Comando: diseno-apoyos-neopreno")
    print("Detalles: fijo_barras (pasadores lisos interiores) | movil_placas (planchas A36 superior/inferior)")

    kind_raw = _prompt_choice(
        "Tipo de apoyo",
        {"fijo": "FIJO_BARRAS", "movil": "MOVIL_PLACAS"},
        "fijo",
    )
    support_type = "FIJO_BARRAS" if kind_raw == "fijo" else "MOVIL_PLACAS"

    print()
    print("-- Geometria del neopreno --")
    length = prompt_float("Largo L", "cm", 40.0)
    width = prompt_float("Ancho W", "cm", 40.0)
    thickness = prompt_float("Espesor h", "cm", 5.0)
    hardness = prompt_int("Dureza Shore A (50/60/70)", 60, minimum=50)
    if hardness not in (50, 60, 70):
        print("Dureza no tipica; se usara 60.")
        hardness = 60

    print()
    print("-- Reacciones verticales por apoyo --")
    r_dc = prompt_float("R_DC", "Tn", 20.0)
    r_dw = prompt_non_negative_float("R_DW", "Tn", 1.2)
    r_pl = prompt_non_negative_float("R_PL peatonal", "Tn", 0.0)
    r_ll_im = prompt_non_negative_float("R_LL+IM vehicular", "Tn", 29.4)

    print()
    print("-- Acciones horizontales longitudinales --")
    h_long = 0.0
    if support_type == "FIJO_BARRAS":
        h_long = prompt_non_negative_float("BR frenado nominal por apoyo", "Tn", 0.0)
        print(f"H_BR Resistencia I = 1.75*BR = {1.75*h_long:.3f} Tn.")
    pga = prompt_non_negative_float("PGA", "-", 0.48 if support_type == "FIJO_BARRAS" else 0.0)
    fpga = prompt_float("Fpga", "-", 1.08)
    print(f"As = PGA*Fpga = {pga:.3f}*{fpga:.3f} = {pga*fpga:.3f}.")
    print(f"H_EQ Evento Extremo I = As*(R_DC+R_DW) = {pga*fpga*(r_dc+r_dw):.3f} Tn.")

    print()
    print("-- Movimiento termico --")
    span = prompt_float("Luz del tramo", "m", 15.0)
    zone = _prompt_choice(
        "Zona climatica MTC",
        {"costa": "costa", "sierra": "sierra", "selva": "selva"},
        "costa",
    )
    t_install = prompt_float("Temperatura de instalacion", "C", 20.0)

    bars = None
    plates = None
    if support_type == "FIJO_BARRAS":
        print()
        print("-- Pasadores lisos del apoyo fijo --")
        bars = FixedBarGroup(
            n_bars=_prompt_bar_count(),
            diameter_cm=prompt_float("Diametro pasador liso", "cm", 2.54),
            spacing_long_cm=prompt_float("Separacion longitudinal pasadores", "cm", 20.0),
            spacing_trans_cm=prompt_float("Separacion transversal pasadores", "cm", 15.0),
            moment_arm_cm=prompt_float("Brazo e entre contactos del pasador", "cm", 5.0),
        )
    else:
        print()
        print("-- Planchas del apoyo movil --")
        plates = ExternalSteelPlatePair(
            thickness_cm=prompt_float("Espesor plancha superior/inferior", "cm", 2.54),
        )

    print()
    print("-- Concreto --")
    fc = prompt_float("f'c", "kg/cm2", 210.0)

    return SimpleSupportInputs(
        support_type=support_type,  # type: ignore[arg-type]
        geometry=SimpleNeopreneGeometry(length, width, thickness),
        demands=SimpleSupportDemands(
            r_dc_tn=r_dc,
            r_dw_tn=r_dw,
            r_pl_tn=r_pl,
            r_ll_im_tn=r_ll_im,
            h_long_tn=h_long,
            pga=pga,
            fpga=fpga,
            span_length_m=span,
            temperature=climate_temperature(zone, t_install),
        ),
        hardness=hardness,
        fixed_bars=bars,
        plates=plates,
        fc_kg_cm2=fc,
    )


def run_simple_neoprene_design(inputs: SimpleSupportInputs | None = None) -> None:
    if inputs is None:
        inputs = collect_simple_neoprene_inputs()
    print(format_simple_neoprene_result(design_simple_neoprene_support(inputs)))


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"-h", "--help", "help"}:
        print("Uso: diseno-apoyos-neopreno")
        print("Tipos: fijo_barras | movil_placas")
        return
    run_simple_neoprene_design()


if __name__ == "__main__":
    main()
