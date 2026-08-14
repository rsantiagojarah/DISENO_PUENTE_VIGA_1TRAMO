"""CLI interactivo para diseño de apoyos elastoméricos Método A."""

from __future__ import annotations

import sys

from bridge_design.cli.bearing_output import format_elastomeric_bearing_result
from bridge_design.cli.input_prompts import (
    prompt_float,
    prompt_int,
    prompt_non_negative_float,
)
from bridge_design.cli.yaml_inputs import bearing_inputs_from_yaml, bearing_yaml_template
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
from bridge_design.domain.elastomeric_bearing import (
    BearingLoads,
    BearingMovements,
    ConcreteBearingSupport,
    ElastomericBearingInputs,
    HardnessShoreA,
    SeismicBearingInputs,
    TemperatureRange,
    design_elastomeric_bearing_method_a,
    recommend_bearing_plan,
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


def _confirm_plan_dimensions(
    loads: BearingLoads,
    girder_width_cm: float,
) -> tuple[float, float]:
    """Propone W y L; el usuario confirma o modifica el largo (y opcionalmente W)."""
    print()
    print("-- Planta del apoyo (L longitudinal x W transversal) --")
    width_cm = prompt_float(
        "Ancho del apoyo W (confirmar o modificar; tipico = ancho de viga)",
        "cm",
        girder_width_cm,
    )
    plan = recommend_bearing_plan(loads, width_cm)
    print(
        f"PT = {loads.total_service_tn:.3f} Tn = {loads.total_service_kg:.0f} kg | "
        f"A_req = PT/87.9 = {plan.required_area_cm2:.2f} cm2"
    )
    print(
        f"Con W = {plan.width_cm:.2f} cm -> L teorico = A_req/W = "
        f"{plan.theoretical_length_cm:.2f} cm"
    )
    print(
        f"L propuesto (redondeo al cm superior) = {plan.recommended_length_cm:.0f} cm | "
        f"A = {plan.recommended_area_cm2:.1f} cm2"
    )
    print("Presione Enter para aceptar el L propuesto, o escriba otro largo en cm.")
    length_cm = prompt_float(
        "Largo del apoyo L (confirmar o modificar)",
        "cm",
        plan.recommended_length_cm,
    )
    if length_cm + 1e-9 < plan.theoretical_length_cm:
        print(
            f"Aviso: L={length_cm:.2f} cm < L teorico={plan.theoretical_length_cm:.2f} cm; "
            "el area puede no satisfacer sigma_s <= 87.9 kg/cm2."
        )
    elif abs(length_cm - plan.recommended_length_cm) > 1e-9:
        area = length_cm * width_cm
        print(
            f"L modificado por el usuario: {length_cm:.2f} cm | "
            f"A = L*W = {area:.1f} cm2 (A_req = {plan.required_area_cm2:.2f} cm2)"
        )
    else:
        print(f"L aceptado: {length_cm:.0f} cm")
    return width_cm, length_cm


def collect_elastomeric_bearing_inputs() -> ElastomericBearingInputs:
    """Captura datos de terminal para diseño Método A."""
    print()
    print("=== DISENO DE APOYOS ELASTOMERICOS - METODO A (AASHTO 14.7.6 / MTC 2.10.4) ===")
    print("Unidades: fuerzas en Tn, longitudes en m o cm segun se indique.")
    print()

    print("-- Cargas de servicio por apoyo --")
    pdc = prompt_float("Carga muerta DC", "Tn", 48.0)
    pdw = prompt_non_negative_float("Carga DW asfalto", "Tn", 4.0)
    pll = prompt_non_negative_float("Carga viva LL (sin impacto)", "Tn", 28.0)
    loads = BearingLoads(pdc, pdw, pll)

    print()
    print("-- Movimientos horizontales --")
    span = prompt_float("Luz del tramo", "m", 25.0)
    zone = _prompt_choice(
        "Zona climatica MTC",
        {"costa": "costa", "sierra": "sierra", "selva": "selva"},
        "costa",
    )
    t_install = prompt_float("Temperatura de instalacion", "C", 20.0)
    temperature = TemperatureRange.mtc_default(zone, t_install_c=t_install)
    shrinkage = prompt_non_negative_float("Retraccion del concreto", "cm", 0.8)
    prestress = prompt_non_negative_float(
        "Acortamiento por pretensado/postensado (0 si no aplica)",
        "cm",
        0.0,
    )
    other = prompt_non_negative_float("Otros movimientos permanentes", "cm", 0.0)
    gamma_tu = prompt_float("Factor gamma_TU", "-", 1.2)
    movements = BearingMovements(
        span_length_m=span,
        temperature=temperature,
        shrinkage_cm=shrinkage,
        prestress_shortening_cm=prestress,
        other_permanent_cm=other,
        gamma_tu=gamma_tu,
    )

    print()
    print("-- Material y geometria --")
    hardness_raw = prompt_int("Dureza Shore A (50/60/70)", 60, minimum=50)
    if hardness_raw not in (50, 60, 70):
        print("Dureza no tipica; se usara 60.")
        hardness: HardnessShoreA = 60
    else:
        hardness = hardness_raw  # type: ignore[assignment]
    girder_w = prompt_float("Ancho de viga / apoyo W", "cm", 40.0)
    fy = prompt_float("Fy acero de zunchos", "kg/cm2", 2530.0)
    adopted_w, adopted_l = _confirm_plan_dimensions(loads, girder_w)

    print()
    print("-- Sismo (MTC 2.4.3.11.8) --")
    a_s = prompt_non_negative_float("Coeficiente As del sitio", "-", 0.20)
    zone_seis = prompt_int("Zona sismica (1-4)", 1, minimum=1)
    if zone_seis > 4:
        zone_seis = 4
    single = _prompt_yes_no("Puente de un solo tramo", default=True)
    role = _prompt_choice(
        "Tipo de apoyo",
        {"expansion": "expansion", "fixed": "fixed"},
        "expansion",
    )
    long_rest = _prompt_yes_no("Restringido longitudinalmente", default=False)
    trans_rest = _prompt_yes_no("Restringido transversalmente", default=True)
    p_long = None
    if long_rest:
        p_long = prompt_float(
            "Carga permanente tributaria longitudinal (tramo o apoyo)",
            "Tn",
            loads.permanent_tn,
        )
    mu = prompt_float("Coeficiente de friccion mu", "-", 0.2)
    seismic = SeismicBearingInputs(
        site_acceleration_as=a_s,
        seismic_zone=zone_seis,  # type: ignore[arg-type]
        is_single_span=single,
        bearing_role=role,  # type: ignore[arg-type]
        longitudinal_restrained=long_rest,
        transverse_restrained=trans_rest,
        tributary_permanent_longitudinal_tn=p_long,
        friction_coefficient=mu,
    )

    print()
    concrete_support = None
    if _prompt_yes_no("Verificar aplastamiento del concreto bajo el apoyo", default=True):
        fc = prompt_float("f'c del pedestal/estribo", "kg/cm2", 210.0)
        a2 = None
        if _prompt_yes_no("Indicar area A2 del pedestal (si no, A2=A1)", default=False):
            a2 = prompt_float("Area A2", "cm2", girder_w * 50.0)
        concrete_support = ConcreteBearingSupport(fc_kg_cm2=fc, support_area_cm2=a2)

    return ElastomericBearingInputs(
        loads=loads,
        movements=movements,
        seismic=seismic,
        hardness=hardness,
        girder_width_cm=girder_w,
        steel_fy_kg_cm2=fy,
        adopted_length_cm=adopted_l,
        adopted_width_cm=adopted_w,
        concrete_support=concrete_support,
    )


def run_bearing_design(inputs: ElastomericBearingInputs | None = None) -> None:
    """Ejecuta el flujo completo de diseño de apoyos."""
    if inputs is None:
        inputs = collect_elastomeric_bearing_inputs()
    result = design_elastomeric_bearing_method_a(inputs)
    print(format_elastomeric_bearing_result(result))


def _run_yaml_mode(args: list[str]) -> bool:
    if not is_yaml_mode(args):
        return False
    if args[0] == "output":
        path = resolve_yaml_mode_path(args, mode="output") or select_yaml_save_path(
            "Guardar plantilla YAML de apoyos",
            "modelo_apoyos.yaml",
        )
        save_yaml_file(path, bearing_yaml_template())
        print(f"Plantilla YAML guardada en: {path}")
        return True
    path = resolve_yaml_mode_path(args, mode="input") or select_yaml_open_path(
        "Seleccionar YAML de apoyos"
    )
    run_bearing_design(bearing_inputs_from_yaml(load_yaml_file(path)))
    return True


def main(argv: list[str] | None = None) -> None:
    """Entry point del comando bridge-design-apoyos."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"-h", "--help", "help"}:
        print_yaml_mode_help("diseno-apoyos")
        return
    try:
        if _run_yaml_mode(args):
            return
    except (YamlModeError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    run_bearing_design()


if __name__ == "__main__":
    main()
