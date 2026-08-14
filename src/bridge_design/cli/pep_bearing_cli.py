"""CLI interactivo para diseno-apoyos-PEP (modulo aislado)."""

from __future__ import annotations

import sys

from bridge_design.cli.input_prompts import (
    prompt_float,
    prompt_int,
    prompt_non_negative_float,
)
from bridge_design.cli.pep_bearing_output import format_pep_bearing_result
from bridge_design.cli.pep_yaml_inputs import pep_inputs_from_yaml, pep_yaml_template
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
from bridge_design.domain.pep_bearing import (
    ALPHA_CONCRETE_PER_C,
    PepAnchorGroup,
    PepBearingInputs,
    PepConcreteSupport,
    PepExternalPlate,
    PepGeometry,
    PepServiceDemands,
    PepTemperature,
    design_pep_bearing,
)
from bridge_design.domain.pep_normative_matrix import format_pep_normative_matrix


def _prompt_choice(label: str, options: dict[str, str], default: str) -> str:
    keys = "/".join(options)
    while True:
        raw = input(f"{label} ({keys}) [{default}]: ").strip().lower()
        if not raw:
            return default
        if raw in options:
            return raw
        print(f"Opciones validas: {keys}")


def _prompt_yes_no(label: str, default: bool = True) -> bool:
    default_txt = "s" if default else "n"
    while True:
        raw = input(f"{label} (s/n) [{default_txt}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"s", "si", "y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Ingrese s o n.")


def _prompt_optional_signed_float(label: str, unit: str) -> float | None:
    while True:
        raw = input(f"{label} ({unit}, Enter = no considerar): ").strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            print("Ingrese un numero valido.")


def _prompt_plate(label: str, default_l: float, default_w: float) -> PepExternalPlate | None:
    if not _prompt_yes_no(f"Incluir {label}", default=True):
        return None
    return PepExternalPlate(
        length_cm=prompt_float(f"{label} - L", "cm", default_l),
        width_cm=prompt_float(f"{label} - W", "cm", default_w),
        thickness_cm=prompt_float(f"{label} - t", "cm", 2.0),
        fy_kg_cm2=prompt_float(f"{label} - Fy", "kg/cm2", 2530.0),
        fu_kg_cm2=prompt_float(f"{label} - Fu", "kg/cm2", 4080.0),
    )


def collect_pep_bearing_inputs() -> PepBearingInputs:
    """Captura interactiva de datos PEP fijo/movil."""
    print()
    print("=== DISENO DE APOYOS ELASTOMERICOS PEP (SIN ZUNCHOS) - METODO A ===")
    print("Comando: diseno-apoyos-PEP | MTC 2.10.4 / AASHTO 14.7.6")
    print("MOVIL_PEP_PTFE queda preparado para el futuro (no implementado ahora).")
    print("Matriz normativa disponible con: diseno-apoyos-PEP matriz")

    mode = _prompt_choice(
        "Modo",
        {"disenar": "DISENAR", "verificar": "VERIFICAR"},
        "disenar",
    )
    mode_value = "DISENAR" if mode == "disenar" else "VERIFICAR"

    tipo_raw = _prompt_choice(
        "Tipo de apoyo",
        {"fijo": "FIJO", "movil": "MOVIL_PEP_CORTE"},
        "movil",
    )
    tipo = "FIJO" if tipo_raw == "fijo" else "MOVIL_PEP_CORTE"
    path = "RESTRICCION_EXTERNA"
    if tipo == "FIJO":
        path_raw = _prompt_choice(
            "Recorrido de carga horizontal del fijo",
            {"externa": "RESTRICCION_EXTERNA", "elastomero": "CORTE_EN_ELASTOMERO"},
            "externa",
        )
        path = "CORTE_EN_ELASTOMERO" if path_raw == "elastomero" else "RESTRICCION_EXTERNA"

    print()
    print("-- Geometria del PEP (neopreno simple) --")
    design_suffix = " minimo" if mode_value == "DISENAR" else ""
    length = prompt_float(f"Largo{design_suffix} L", "cm", 30.0)
    width = prompt_float(f"Ancho{design_suffix} W", "cm", 40.0)
    thickness_default = 2.0 if mode_value == "DISENAR" else 4.0
    thickness = prompt_float(
        f"Espesor{design_suffix} h del neopreno (sin placas)",
        "cm",
        thickness_default,
    )
    hardness = prompt_int("Dureza Shore A (50/60/70)", 60, minimum=50)
    if hardness not in (50, 60, 70):
        print("Dureza no tipica; se usara 60.")
        hardness = 60
    g_spec = None

    print()
    print("-- Demandas por apoyo --")
    combo = "ENVOLVENTE_PEP"
    case = "SERVICIO_Y_EVENTO_EXTREMO"
    pos = "POS_1"
    bid = "APOYO_1"
    r_dc = prompt_float("R_DC", "Tn", 40.0)
    r_dw = prompt_non_negative_float("R_DW", "Tn", 4.0)
    r_ll = prompt_non_negative_float("R_LL", "Tn", 20.0)
    r_im = prompt_non_negative_float("R_IM", "Tn", 0.0)
    r_min = _prompt_optional_signed_float("Rmin para uplift", "Tn")
    h_long = prompt_non_negative_float("H longitudinal (servicio/resistencia)", "Tn", 5.0)
    pga = prompt_non_negative_float("PGA", "-", 0.20)
    fpga = prompt_float("Fpga", "-", 1.00)
    a_s = pga * fpga
    h_trans = 0.0
    h_eq_l = a_s * (r_dc + r_dw)
    h_eq_t = 0.0
    print(f"As calculado = PGA*Fpga = {pga:.3f}*{fpga:.3f} = {a_s:.3f}.")
    print(f"H_EQ longitudinal calculado = {a_s:.3f}*({r_dc:.3f}+{r_dw:.3f}) = {h_eq_l:.3f} Tn.")
    print("H transversal y H_EQ transversal no considerados: se adoptan 0.000 Tn.")

    print()
    print("-- Movimientos --")
    delta_s = None
    span = prompt_float("Luz del tramo para movimiento termico", "m", 25.0)
    zone = _prompt_choice(
        "Zona climatica MTC",
        {"costa": "costa", "sierra": "sierra", "selva": "selva"},
        "costa",
    )
    t_inst = prompt_float("Temperatura de instalacion", "C", 20.0)
    shrink = 0.0
    prestress = 0.0
    gamma_tu = 1.2
    temperature = PepTemperature.mtc_default(zone, t_inst)  # type: ignore[arg-type]
    delta_temp = ALPHA_CONCRETE_PER_C * span * 100.0 * temperature.contraction_delta_t_c
    print(
        "Delta_s termico calculado = "
        f"{gamma_tu:.3f}*{ALPHA_CONCRETE_PER_C:.8f}*{span*100.0:.1f}*"
        f"{temperature.contraction_delta_t_c:.1f} = {gamma_tu*delta_temp:.3f} cm."
    )

    th_i = th_dc = th_dw = th_ll = th_o = 0.0
    print("Rotaciones no solicitadas: theta_total = 0.000000 rad.")

    eps_source = "curva_aashto"
    eps_p = None
    eps_t = None

    zone_seis = 1
    mu = 0.20

    auto_plates = mode_value == "DISENAR"
    auto_anchors = mode_value == "DISENAR"
    upper = None
    lower = None
    anchors = None
    bolts_exception = False
    if mode_value == "VERIFICAR" and _prompt_yes_no(
        "Ingresar placas/anclajes existentes para verificar aparato completo",
        default=True,
    ):
        upper = _prompt_plate("placa superior", length + 10.0, width + 10.0)
        lower = _prompt_plate("placa inferior", length + 10.0, width + 10.0)
        if _prompt_yes_no("Ingresar grupo de anclajes manualmente", default=True):
            anchors = PepAnchorGroup(
                n_bolts=prompt_int("n pernos", 4, minimum=1),
                diameter_cm=prompt_float("diametro", "cm", 2.2),
                fy_kg_cm2=prompt_float("Fy perno", "kg/cm2", 4220.0),
                fu_kg_cm2=prompt_float("Fu perno", "kg/cm2", 6330.0),
                embedment_cm=prompt_float("longitud anclaje", "cm", 30.0),
                layout_note="fuera del PEP",
            )

    print()
    print("-- Concreto --")
    concrete = PepConcreteSupport(
        fc_kg_cm2=prompt_float("f'c", "kg/cm2", 210.0),
        support_area_cm2=None,
    )

    return PepBearingInputs(
        tipo_apoyo=tipo,
        geometry=PepGeometry(length, width, thickness),
        demands=PepServiceDemands(
            combination_id=combo,
            load_case_id=case,
            position_id=pos,
            bearing_id=bid,
            r_dc_tn=r_dc,
            r_dw_tn=r_dw,
            r_ll_tn=r_ll,
            r_im_tn=r_im,
            r_min_tn=r_min,
            h_long_tn=h_long,
            h_trans_tn=h_trans,
            h_eq_long_tn=h_eq_l,
            h_eq_trans_tn=h_eq_t,
            delta_s_cm=delta_s,
            span_length_m=span,
            shrinkage_cm=shrink,
            prestress_cm=prestress,
            gamma_tu=gamma_tu,
            temperature=temperature,
            theta_initial_rad=th_i,
            theta_dc_rad=th_dc,
            theta_dw_rad=th_dw,
            theta_ll_rad=th_ll,
            theta_other_rad=th_o,
        ),
        hardness=hardness,  # type: ignore[arg-type]
        g_specified_kg_cm2=g_spec,
        fixed_restraint_load_path=path,  # type: ignore[arg-type]
        epsilon_source=eps_source,  # type: ignore[arg-type]
        epsilon_permanent=eps_p,
        epsilon_total=eps_t,
        friction_coefficient=mu,
        site_acceleration_as=a_s,
        seismic_pga=pga,
        seismic_fpga=fpga,
        seismic_zone=zone_seis,
        upper_plate=upper,
        lower_plate=lower,
        anchors=anchors,
        concrete_support=concrete,
        bolts_through_pep_exception=bolts_exception,
        mode=mode_value,  # type: ignore[arg-type]
        design_plates_auto=auto_plates,
        design_anchors_auto=auto_anchors,
    )


def run_pep_bearing_design(inputs: PepBearingInputs | None = None) -> None:
    """Ejecuta el flujo PEP y muestra la memoria."""
    if inputs is None:
        inputs = collect_pep_bearing_inputs()
    result = design_pep_bearing(inputs)
    print(format_pep_bearing_result(result))


def _run_yaml_mode(args: list[str]) -> bool:
    if not is_yaml_mode(args):
        return False
    if args[0] == "output":
        path = resolve_yaml_mode_path(args, mode="output") or select_yaml_save_path(
            "Guardar plantilla YAML PEP",
            "modelo_apoyos_pep.yaml",
        )
        save_yaml_file(path, pep_yaml_template())
        print(f"Plantilla YAML PEP guardada en: {path}")
        return True
    path = resolve_yaml_mode_path(args, mode="input") or select_yaml_open_path(
        "Seleccionar YAML de apoyos PEP"
    )
    run_pep_bearing_design(pep_inputs_from_yaml(load_yaml_file(path)))
    return True


def main(argv: list[str] | None = None) -> None:
    """Entry point del comando diseno-apoyos-PEP."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"-h", "--help", "help"}:
        print_yaml_mode_help("diseno-apoyos-PEP")
        print()
        print("Tipos: FIJO | MOVIL_PEP_CORTE (MOVIL_PEP_PTFE futuro)")
        print("Modos: VERIFICAR | DISENAR")
        return
    if args and args[0] in {"matriz", "matrix"}:
        print(format_pep_normative_matrix())
        return
    try:
        if _run_yaml_mode(args):
            return
    except (YamlModeError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    run_pep_bearing_design()


if __name__ == "__main__":
    main()
