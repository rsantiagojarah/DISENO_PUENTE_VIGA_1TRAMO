"""Terminal entry point for bridge design inputs."""

from __future__ import annotations

import sys

from bridge_design.cli.ascii_output import (
    format_barrier_design_result,
    format_cantilever_slab_design_result,
    format_crack_control_review,
    format_diaphragm_design_result,
    format_exterior_girder_analysis_result,
    format_abutment_reaction_summary,
    format_girder_detailing_result,
    format_interior_girder_analysis_result,
    format_interior_girder_crack_control_review,
    format_input_summary,
    format_transverse_load_location_schemes,
    format_transverse_analysis_result,
)
from bridge_design.cli.ascii_tables import boxed_table
from bridge_design.domain.barrier import design_concrete_barrier
from bridge_design.domain.cantilever_slab import design_cantilever_slab
from bridge_design.cli.input_prompts import collect_project_inputs
from bridge_design.cli.yaml_inputs import project_inputs_from_yaml, project_yaml_template
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
from bridge_design.domain.crack_control import review_transverse_slab_crack_control
from bridge_design.domain.diaphragm import (
    DiaphragmReinforcementDesign,
    design_diaphragm_reinforcement,
    solve_diaphragm_design,
)
from bridge_design.domain.exterior_girder import (
    design_exterior_girder_reinforcement,
    design_exterior_girder_shear,
    review_exterior_girder_crack_control,
    review_exterior_girder_fatigue,
    solve_exterior_girder_design,
    verify_exterior_girder_service_stresses,
)
from bridge_design.domain.girder_detailing import (
    detail_exterior_girder,
    detail_interior_girder,
)
from bridge_design.domain.interior_girder import (
    InteriorGirderReinforcementDesign,
    LongitudinalBarPlacementOption,
    ShearStirrupOption,
    custom_main_bar_placement_option,
    custom_shear_stirrup_option,
    design_interior_girder_reinforcement,
    design_interior_girder_shear,
    review_interior_girder_crack_control,
    review_interior_girder_fatigue,
    solve_interior_girder_design,
    verify_interior_girder_service_stresses,
)
from bridge_design.domain.rebar_catalog import (
    REINFORCING_BAR_CATALOG,
    ReinforcementCaseOptions,
    ReinforcementSpacingOption,
    custom_spacing_option,
)
from bridge_design.domain.reinforcement import (
    design_transverse_slab_reinforcement,
)
from bridge_design.domain.transverse_slab import solve_transverse_slab_design


def main(argv: list[str] | None = None) -> None:
    """Run the terminal input workflow or a module subcommand."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"tablero", "deck", "losa"}:
        _run_deck_command(args[1:])
        return
    if args and args[0] in {"apoyos", "bearings", "bearing"}:
        from bridge_design.cli.bearing_cli import main as run_bearing_command

        run_bearing_command(args[1:]) if len(args) > 1 else run_bearing_command()
        return
    if args and args[0] in {"apoyos-neopreno", "neopreno", "simple-neoprene"}:
        from bridge_design.cli.simple_neoprene_cli import main as run_simple_neoprene_command

        run_simple_neoprene_command(args[1:]) if len(args) > 1 else run_simple_neoprene_command()
        return
    if args and args[0] in {"muro", "muros", "wall", "walls", "cantilever-wall"}:
        from bridge_design.cantilever_wall_main import main as run_wall_design

        run_wall_design(args[1:]) if len(args) > 1 else run_wall_design()
        return
    if args and is_yaml_mode(args):
        _run_deck_command(args)
        return
    if args and args[0] in {"-h", "--help", "help"}:
        print(
            "Uso:\n"
            "  bridge-design              Flujo completo del puente\n"
            "  bridge-design tablero      Diseno de tablero y memoria de calculo Word automatica\n"
            "  bridge-design apoyos       Diseno de apoyos elastomericos Metodo A\n"
            "  bridge-design apoyos-neopreno  Apoyos neopreno simple: fijo con barras / movil con placas\n"
            "  bridge-design muro         Diseno de muro de concreto armado en cantilever con sismo\n"
            "  diseno-tablero             Comando simple para tablero completo\n"
            "                              Al finalizar solicita donde guardar el documento Word\n"
            "  diseno-estribos            Comando simple para estribos\n"
            "  diseno-apoyos              Comando simple para apoyos\n"
            "  diseno-apoyos-neopreno     Comando simple para apoyos de neopreno con detalles fijo/movil\n"
            "  diseno-muros               Comando simple para muros cantilever\n"
            "  diseno-tablero input       Elegir YAML de tablero con ventana\n"
            "  diseno-tablero input archivo.yaml\n"
            "  diseno-tablero output      Guardar plantilla YAML con ventana\n"
            "  diseno-tablero output modelo.yaml\n"
            "  bridge-cantilever-wall-design  Comando directo del modulo de muro cantilever\n"
            "  bridge-design-apoyos       Comando directo del modulo de apoyos"
        )
        return

    run_bridge_design()


def _run_deck_command(args: list[str]) -> None:
    if args and args[0] in {"-h", "--help", "help"}:
        print_yaml_mode_help("diseno-tablero")
        return
    try:
        if args and is_yaml_mode(args):
            if args[0] == "output":
                path = resolve_yaml_mode_path(args, mode="output") or select_yaml_save_path(
                    "Guardar plantilla YAML de tablero",
                    "modelo_tablero.yaml",
                )
                save_yaml_file(path, project_yaml_template())
                print(f"Plantilla YAML guardada en: {path}")
                return
            path = resolve_yaml_mode_path(args, mode="input") or select_yaml_open_path(
                "Seleccionar YAML de tablero"
            )
            run_bridge_design(project_inputs_from_yaml(load_yaml_file(path)))
            return
    except (YamlModeError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    run_bridge_design()


def run_bridge_design(project_inputs=None) -> None:
    """Run the full slab, girder, barrier and diaphragm design workflow."""
    if project_inputs is None:
        project_inputs = collect_project_inputs()
    print()
    input_report = format_input_summary(project_inputs)
    load_scheme_report = format_transverse_load_location_schemes(project_inputs)
    print(input_report)
    print(load_scheme_report)

    result = solve_transverse_slab_design(
        geometry=project_inputs.transverse_slab.geometry,
        materials=project_inputs.materials,
        live_loads=project_inputs.live_loads,
        layout=project_inputs.transverse_slab.load_layout,
    )
    transverse_report = format_transverse_analysis_result(result, project_inputs)
    print(transverse_report)
    reinforcement = design_transverse_slab_reinforcement(
        geometry=project_inputs.transverse_slab.geometry,
        materials=project_inputs.materials,
        analysis=result,
    )
    selected = collect_reinforcement_spacing_selection(reinforcement)
    slab_selection_report = format_reinforcement_spacing_selection(selected)
    print(slab_selection_report)
    crack_review = review_transverse_slab_crack_control(
        geometry=project_inputs.transverse_slab.geometry,
        materials=project_inputs.materials,
        analysis=result,
        reinforcement=reinforcement,
        negative_spacing=_selected_spacing(selected, "A."),
        positive_spacing=_selected_spacing(selected, "B."),
    )
    slab_crack_report = format_crack_control_review(crack_review)
    print(slab_crack_report)

    girder_result = solve_interior_girder_design(
        geometry=project_inputs.interior_girder,
        materials=project_inputs.materials,
        live_loads=project_inputs.live_loads,
    )
    interior_analysis_report = format_interior_girder_analysis_result(
        girder_result,
        project_inputs,
    )
    print(interior_analysis_report)
    girder_reinforcement = design_interior_girder_reinforcement(
        geometry=project_inputs.interior_girder,
        materials=project_inputs.materials,
        analysis=girder_result,
    )
    girder_shear = design_interior_girder_shear(
        geometry=project_inputs.interior_girder,
        materials=project_inputs.materials,
        analysis=girder_result,
        reinforcement=girder_reinforcement,
    )
    girder_selected = collect_interior_girder_reinforcement_selection(
        girder_reinforcement,
        girder_shear,
    )
    interior_selection_report = format_interior_girder_reinforcement_selection(
        girder_selected
    )
    print(interior_selection_report)
    girder_crack_review = review_interior_girder_crack_control(
        geometry=project_inputs.interior_girder,
        materials=project_inputs.materials,
        analysis=girder_result,
        reinforcement=girder_reinforcement,
        main_placement=_selected_main_placement(girder_selected),
    )
    interior_crack_report = format_interior_girder_crack_control_review(
        girder_crack_review
    )
    print(interior_crack_report)
    selected_girder_main = _selected_main_placement(girder_selected)
    girder_fatigue_review = review_interior_girder_fatigue(
        geometry=project_inputs.interior_girder,
        materials=project_inputs.materials,
        analysis=girder_result,
        reinforcement=girder_reinforcement,
        main_placement=selected_girder_main,
    )
    girder_service_review = verify_interior_girder_service_stresses(
        geometry=project_inputs.interior_girder,
        materials=project_inputs.materials,
        analysis=girder_result,
        reinforcement=girder_reinforcement,
        main_placement=selected_girder_main,
    )
    interior_service_report = format_interior_girder_selected_main_reviews(
        geometry=project_inputs.interior_girder,
        materials=project_inputs.materials,
        analysis=girder_result,
        reinforcement=girder_reinforcement,
        main_placement=selected_girder_main,
        fatigue_review=girder_fatigue_review,
        service_review=girder_service_review,
    )
    print(interior_service_report)
    interior_detail = detail_interior_girder(
        label="Viga interior",
        geometry=project_inputs.interior_girder,
        materials=project_inputs.materials,
        analysis=girder_result,
        reinforcement=girder_reinforcement,
        selected_main_bar=selected_girder_main,
        selected_stirrup=_selected_shear_stirrup(girder_selected),
    )
    interior_detail_report = format_girder_detailing_result(interior_detail, "2.F")
    print(interior_detail_report)

    exterior_result = solve_exterior_girder_design(
        geometry=project_inputs.exterior_girder,
        materials=project_inputs.materials,
        live_loads=project_inputs.live_loads,
    )
    exterior_analysis_report = format_exterior_girder_analysis_result(
        exterior_result,
        project_inputs,
    )
    print(exterior_analysis_report)
    exterior_reinforcement = design_exterior_girder_reinforcement(
        geometry=project_inputs.exterior_girder,
        materials=project_inputs.materials,
        analysis=exterior_result,
    )
    exterior_shear = design_exterior_girder_shear(
        geometry=project_inputs.exterior_girder,
        materials=project_inputs.materials,
        analysis=exterior_result,
        reinforcement=exterior_reinforcement,
    )
    exterior_selected = collect_exterior_girder_reinforcement_selection(
        exterior_reinforcement,
        exterior_shear,
    )
    exterior_selection_report = format_exterior_girder_reinforcement_selection(
        exterior_selected
    )
    print(exterior_selection_report)
    selected_main = _selected_main_placement(exterior_selected)
    exterior_crack_review = review_exterior_girder_crack_control(
        geometry=project_inputs.exterior_girder,
        materials=project_inputs.materials,
        analysis=exterior_result,
        reinforcement=exterior_reinforcement,
        main_placement=selected_main,
    )
    exterior_fatigue_review = review_exterior_girder_fatigue(
        geometry=project_inputs.exterior_girder,
        materials=project_inputs.materials,
        analysis=exterior_result,
        reinforcement=exterior_reinforcement,
        main_placement=selected_main,
    )
    exterior_service_stresses = verify_exterior_girder_service_stresses(
        geometry=project_inputs.exterior_girder,
        materials=project_inputs.materials,
        analysis=exterior_result,
        reinforcement=exterior_reinforcement,
        main_placement=selected_main,
    )
    exterior_service_report = format_exterior_girder_selected_main_reviews(
        geometry=project_inputs.exterior_girder,
        materials=project_inputs.materials,
        analysis=exterior_result,
        reinforcement=exterior_reinforcement,
        main_placement=selected_main,
        crack_review=exterior_crack_review,
        fatigue_review=exterior_fatigue_review,
        service_review=exterior_service_stresses,
    )
    print(exterior_service_report)
    exterior_detail = detail_exterior_girder(
        label="Viga exterior",
        geometry=project_inputs.exterior_girder,
        materials=project_inputs.materials,
        analysis=exterior_result,
        reinforcement=exterior_reinforcement,
        selected_main_bar=selected_main,
        selected_stirrup=_selected_shear_stirrup(exterior_selected),
    )
    exterior_detail_report = format_girder_detailing_result(exterior_detail, "3.F")
    print(exterior_detail_report)

    barrier_result = design_concrete_barrier(
        inputs=project_inputs.barrier,
        materials=project_inputs.materials,
    )
    barrier_report = format_barrier_design_result(barrier_result)
    print(barrier_report)

    cantilever_result = design_cantilever_slab(
        geometry=project_inputs.transverse_slab.geometry,
        materials=project_inputs.materials,
        live_loads=project_inputs.live_loads,
        layout=project_inputs.transverse_slab.load_layout,
        barrier_result=barrier_result,
    )
    cantilever_report = format_cantilever_slab_design_result(cantilever_result)
    print(cantilever_report)
    cantilever_selected = collect_cantilever_reinforcement_selection(cantilever_result)
    cantilever_selection_report = format_cantilever_reinforcement_selection(
        cantilever_selected
    )
    print(cantilever_selection_report)
    from bridge_design.domain._cantilever_slab_calculations import design_development
    from bridge_design.domain._cantilever_slab_checks import review_crack_control

    selected_cantilever_flexural = _selected_spacing(cantilever_selected, "A.")
    cantilever_development = design_development(
        geometry=project_inputs.transverse_slab.geometry,
        materials=project_inputs.materials,
        params=cantilever_result.parameters,
        flexural=cantilever_result.flexural_steel,
        selected_spacing=selected_cantilever_flexural,
    )
    cantilever_crack = review_crack_control(
        geometry=project_inputs.transverse_slab.geometry,
        materials=project_inputs.materials,
        params=cantilever_result.parameters,
        combinations=cantilever_result.combinations,
        flexural=cantilever_result.flexural_steel,
        selected_spacing=selected_cantilever_flexural,
    )
    cantilever_review_report = format_cantilever_selected_reviews(
        geometry=project_inputs.transverse_slab.geometry,
        materials=project_inputs.materials,
        cantilever=cantilever_result,
        selected=cantilever_selected,
        development_review=cantilever_development,
        crack_review=cantilever_crack,
    )
    print(cantilever_review_report)

    diaphragm_result = solve_diaphragm_design(
        geometry=project_inputs.diaphragm,
        materials=project_inputs.materials,
        live_loads=project_inputs.live_loads,
        layout=project_inputs.transverse_slab.load_layout,
    )
    diaphragm_report = format_diaphragm_design_result(
        diaphragm_result,
        project_inputs,
    )
    print(diaphragm_report)
    diaphragm_reinforcement = design_diaphragm_reinforcement(
        geometry=project_inputs.diaphragm,
        materials=project_inputs.materials,
        analysis=diaphragm_result,
    )
    diaphragm_selected = collect_diaphragm_reinforcement_selection(
        diaphragm_reinforcement,
    )
    diaphragm_selection_report = format_diaphragm_reinforcement_selection(
        diaphragm_selected
    )
    print(diaphragm_selection_report)
    reaction_report = format_abutment_reaction_summary(
        interior_result=girder_result,
        exterior_result=exterior_result,
        project_inputs=project_inputs,
    )
    print(reaction_report)

    from bridge_design.reporting import DeckReportData, generate_deck_docx_with_dialog

    report_data = DeckReportData(
        project_inputs=project_inputs,
        transverse_result=result,
        slab_reinforcement=reinforcement,
        slab_selected=selected,
        slab_crack=crack_review,
        interior_result=girder_result,
        interior_reinforcement=girder_reinforcement,
        interior_shear=girder_shear,
        interior_selected=girder_selected,
        interior_detail=interior_detail,
        interior_crack=girder_crack_review,
        interior_fatigue=girder_fatigue_review,
        interior_service=girder_service_review,
        exterior_result=exterior_result,
        exterior_reinforcement=exterior_reinforcement,
        exterior_shear=exterior_shear,
        exterior_selected=exterior_selected,
        exterior_detail=exterior_detail,
        exterior_crack=exterior_crack_review,
        exterior_fatigue=exterior_fatigue_review,
        exterior_service=exterior_service_stresses,
        barrier_result=barrier_result,
        cantilever_result=cantilever_result,
        cantilever_selected=cantilever_selected,
        cantilever_crack=cantilever_crack,
        cantilever_development=cantilever_development,
        diaphragm_result=diaphragm_result,
        diaphragm_reinforcement=diaphragm_reinforcement,
        diaphragm_selected=diaphragm_selected,
        audit_sections=(
            ("Datos generales", input_report),
            ("Ubicacion de cargas", load_scheme_report),
            ("Losa transversal", transverse_report),
            ("Acero seleccionado de losa", slab_selection_report),
            ("Fisuracion de losa", slab_crack_report),
            ("Viga interior", interior_analysis_report),
            ("Acero seleccionado de viga interior", interior_selection_report),
            ("Servicio y fisuracion de viga interior", interior_crack_report + "\n" + interior_service_report),
            ("Detalle constructivo de viga interior", interior_detail_report),
            ("Viga exterior", exterior_analysis_report),
            ("Acero y servicio de viga exterior", exterior_selection_report + "\n" + exterior_service_report),
            ("Detalle constructivo de viga exterior", exterior_detail_report),
            ("Barrera", barrier_report),
            ("Losa en voladizo", cantilever_report + "\n" + cantilever_selection_report + "\n" + cantilever_review_report),
            ("Diafragma", diaphragm_report + "\n" + diaphragm_selection_report),
            ("Reacciones para estribos", reaction_report),
        ),
    )
    try:
        generate_deck_docx_with_dialog(report_data)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"No se pudo generar la memoria Word: {exc}")


def collect_reinforcement_spacing_selection(reinforcement) -> tuple[
    tuple[str, ReinforcementSpacingOption],
    ...,
]:
    """Allow the user to keep or change recommended reinforcement spacing."""
    cases = (
        ("A", reinforcement.negative.spacing_options),
        ("B", reinforcement.positive.spacing_options),
        ("C", reinforcement.temperature.spacing_options),
        ("D", reinforcement.distribution.spacing_options),
    )
    answer = input(
        "\nDesea seleccionar o cambiar las distribuciones recomendadas? [s/N]: "
    ).strip().lower()
    if answer not in ("s", "si", "y", "yes"):
        return _default_reinforcement_spacing_selection(cases)

    selected: list[tuple[str, ReinforcementSpacingOption]] = []
    for code, case_options in cases:
        if case_options is None:
            continue
        selected.append((f"{code}. {case_options.label}", _prompt_spacing_option(case_options)))
    return tuple(selected)


def _default_reinforcement_spacing_selection(
    cases: tuple[tuple[str, ReinforcementCaseOptions | None], ...],
) -> tuple[tuple[str, ReinforcementSpacingOption], ...]:
    selected: list[tuple[str, ReinforcementSpacingOption]] = []
    for code, case_options in cases:
        if case_options is None:
            continue
        recommended = case_options.recommended or case_options.options[-1]
        selected.append((f"{code}. {case_options.label}", recommended))
    return tuple(selected)


def _selected_spacing(
    selected: tuple[tuple[str, ReinforcementSpacingOption], ...],
    code_prefix: str,
) -> ReinforcementSpacingOption | None:
    for label, option in selected:
        if label.startswith(code_prefix):
            return option
    return None


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


def format_reinforcement_spacing_selection(
    selected: tuple[tuple[str, ReinforcementSpacingOption], ...],
) -> str:
    """Return an ASCII summary of selected reinforcement spacing."""
    return "\n".join(
        [""] + _selected_reinforcement_table(
            "DISTRIBUCIONES DE ACERO SELECCIONADAS",
            selected,
        )
    )


def collect_interior_girder_reinforcement_selection(
    reinforcement: InteriorGirderReinforcementDesign,
    shear,
) -> tuple[
    tuple[str, LongitudinalBarPlacementOption | ReinforcementSpacingOption | ShearStirrupOption],
    ...,
]:
    """Allow the user to keep or change recommended girder reinforcement."""
    answer = input(
        "\nDesea seleccionar o cambiar las opciones recomendadas de la viga interior? [s/N]: "
    ).strip().lower()
    cases = (
        ("A. Acero principal longitudinal", reinforcement.main.placement_options),
        ("B. Temperatura caras laterales", reinforcement.temperature.spacing_options),
        ("C. Ask longitudinal por cara", reinforcement.skin.spacing_options),
    )
    if answer not in ("s", "si", "y", "yes"):
        recommended_shear = _recommended_shear_option_or_raise(shear)
        selected = []
        for label, case_options in cases:
            recommended = case_options.recommended or case_options.options[-1]
            selected.append((label, recommended))
        selected.append(("D. Estribos por corte interior", recommended_shear))
        return tuple(selected)

    selected: list[tuple[str, LongitudinalBarPlacementOption | ReinforcementSpacingOption]] = []
    selected.append(
        (
            cases[0][0],
            _prompt_main_placement_option(reinforcement.main.placement_options),
        )
    )
    for label, case_options in cases[1:]:
        selected.append((label, _prompt_spacing_option(case_options)))
    selected.append(("D. Estribos por corte interior", _prompt_shear_stirrup_option(shear)))
    return tuple(selected)


def _prompt_main_placement_option(case_options) -> LongitudinalBarPlacementOption:
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
            return _prompt_custom_main_placement(case_options)
        try:
            item = int(raw_value)
        except ValueError:
            print("Ingrese un item numerico de la tabla.")
            continue
        if item not in valid_items:
            print("El item no existe para este caso.")
            continue
        return valid_items[item]


def _prompt_custom_main_placement(case_options) -> LongitudinalBarPlacementOption:
    recommended = case_options.recommended or case_options.options[-1]
    labels = ", ".join(bar.label for bar in REINFORCING_BAR_CATALOG if bar.diameter_cm >= 1.27)
    print(f"Barras principales disponibles: {labels}")
    while True:
        bar_label = input(
            f"{case_options.label} - barra principal personalizada [{recommended.bar_label}]: "
        ).strip() or recommended.bar_label
        raw_count = input(
            f"{case_options.label} - cantidad total de barras [{recommended.bar_count}]: "
        ).strip()
        try:
            bar_count = recommended.bar_count if not raw_count else int(raw_count)
            return custom_main_bar_placement_option(case_options, bar_label, bar_count)
        except ValueError as exc:
            print(f"Configuracion personalizada no valida: {exc}")


def _prompt_shear_stirrup_option(
    design,
) -> ShearStirrupOption:
    options = design.options
    recommended = next((option for option in options if option.is_recommended), None)
    default_item = recommended.item if recommended is not None else options[-1].item
    valid_items = {option.item: option for option in options}
    while True:
        raw_value = input(
            f"Estribos por corte - elija item [{default_item}] (P=personalizado): "
        ).strip()
        if not raw_value:
            option = valid_items[default_item]
            if option.is_compliant:
                return option
            print("La opcion no cumple phiVn >= Vu; seleccione una opcion conforme o personalizada.")
            continue
        if raw_value.lower() in ("p", "personalizado", "personalizada"):
            return _prompt_custom_shear_stirrup(design)
        try:
            item = int(raw_value)
        except ValueError:
            print("Ingrese un item numerico de la tabla.")
            continue
        if item not in valid_items:
            print("El item no existe para esta tabla.")
            continue
        option = valid_items[item]
        if not option.is_compliant:
            print("La opcion no cumple los requisitos de area, separacion y resistencia al corte.")
            continue
        return option


def _recommended_shear_option_or_raise(design) -> ShearStirrupOption:
    recommended = design.recommended
    if recommended is not None:
        return recommended
    demand = design.controlling_shear.combined_shear_tn
    maximum_resistance = design.phi * design.nominal_shear_limit_tn
    raise ValueError(
        "Ninguna opcion de estribos cumple: "
        f"Vu = {demand:.3f} Tn y resistencia maxima phiVn = {maximum_resistance:.3f} Tn. "
        "Revise la seccion de concreto."
    )


def _prompt_custom_shear_stirrup(design) -> ShearStirrupOption:
    recommended = design.recommended or design.options[-1]
    labels = ", ".join(bar.label for bar in REINFORCING_BAR_CATALOG)
    print(f"Barras para estribos disponibles: {labels}")
    while True:
        bar_label = input(
            f"Barra personalizada del estribo [{recommended.bar_label}]: "
        ).strip() or recommended.bar_label
        raw_legs = input(
            f"Numero de ramas [{recommended.legs}]: "
        ).strip()
        raw_spacing = input(
            f"Separacion personalizada de estribos en m [{recommended.spacing_m:.3f}]: "
        ).strip()
        try:
            legs = recommended.legs if not raw_legs else int(raw_legs)
            spacing_m = recommended.spacing_m if not raw_spacing else float(raw_spacing.replace(",", "."))
            return custom_shear_stirrup_option(design, bar_label, legs, spacing_m)
        except ValueError as exc:
            print(f"Configuracion personalizada no valida: {exc}")


def _selected_main_placement(
    selected: tuple[
        tuple[
            str,
            LongitudinalBarPlacementOption
            | ReinforcementSpacingOption
            | ShearStirrupOption,
        ],
        ...,
    ],
) -> LongitudinalBarPlacementOption | None:
    for label, option in selected:
        if label.startswith("A.") and isinstance(option, LongitudinalBarPlacementOption):
            return option
    return None


def _selected_shear_stirrup(
    selected: tuple[
        tuple[
            str,
            LongitudinalBarPlacementOption
            | ReinforcementSpacingOption
            | ShearStirrupOption,
        ],
        ...,
    ],
) -> ShearStirrupOption | None:
    for label, option in selected:
        if label.startswith("D.") and isinstance(option, ShearStirrupOption):
            return option
    return None


def format_interior_girder_reinforcement_selection(
    selected: tuple[
        tuple[str, LongitudinalBarPlacementOption | ReinforcementSpacingOption | ShearStirrupOption],
        ...,
    ],
) -> str:
    """Return an ASCII summary of selected interior girder reinforcement."""
    return "\n".join(
        [""] + _selected_reinforcement_table(
            "ACEROS SELECCIONADOS - VIGA PRINCIPAL INTERIOR",
            selected,
        )
    )


def format_interior_girder_selected_main_reviews(
    geometry,
    materials,
    analysis,
    reinforcement: InteriorGirderReinforcementDesign,
    main_placement: LongitudinalBarPlacementOption | None,
    fatigue_review=None,
    service_review=None,
) -> str:
    """Return service/fatigue checks using selected interior main bars."""
    fatigue = fatigue_review or review_interior_girder_fatigue(
        geometry=geometry,
        materials=materials,
        analysis=analysis,
        reinforcement=reinforcement,
        main_placement=main_placement,
    )
    stresses = service_review or verify_interior_girder_service_stresses(
        geometry=geometry,
        materials=materials,
        analysis=analysis,
        reinforcement=reinforcement,
        main_placement=main_placement,
    )
    return "\n".join(
        [""] + boxed_table(
            ("Verificacion", "Demanda", "Limite", "Estado"),
            (
                (
                    "Fatiga acero",
                    f"{fatigue.factored_stress_range_kg_cm2:.0f} kg/cm2",
                    f"{fatigue.allowable_stress_range_kg_cm2:.0f} kg/cm2",
                    fatigue.status,
                ),
                (
                    "Servicio I concreto",
                    f"{stresses.concrete_compression_kg_cm2:.1f} kg/cm2",
                    f"{stresses.concrete_compression_limit_kg_cm2:.1f} kg/cm2",
                    stresses.concrete_status,
                ),
                (
                    "Servicio I acero",
                    f"{stresses.steel_tension_kg_cm2:.0f} kg/cm2",
                    f"{stresses.steel_tension_limit_kg_cm2:.0f} kg/cm2",
                    stresses.steel_status,
                ),
            ),
            aligns=("left", "right", "right", "center"),
            title="REVISIONES CON ACERO PRINCIPAL SELECCIONADO - VIGA INTERIOR",
        )
    )


def collect_diaphragm_reinforcement_selection(
    reinforcement: DiaphragmReinforcementDesign,
) -> tuple[
    tuple[
        str,
        LongitudinalBarPlacementOption
        | ReinforcementSpacingOption
        | ShearStirrupOption,
    ],
    ...,
]:
    """Allow the user to keep or change recommended diaphragm reinforcement."""
    answer = input(
        "\nDesea seleccionar o cambiar el acero de la viga diafragma? [s/N]: "
    ).strip().lower()
    recommended_negative = (
        reinforcement.negative.placement_options.recommended
        or reinforcement.negative.placement_options.options[-1]
    )
    recommended_positive = (
        reinforcement.positive.placement_options.recommended
        or reinforcement.positive.placement_options.options[-1]
    )
    recommended_temperature = (
        reinforcement.temperature.spacing_options.recommended
        or reinforcement.temperature.spacing_options.options[-1]
    )
    if answer not in ("s", "si", "y", "yes"):
        recommended_shear = _recommended_shear_option_or_raise(reinforcement.shear)
        return (
            ("A. Acero principal negativo diafragma", recommended_negative),
            ("B. Acero principal positivo diafragma", recommended_positive),
            ("C. Temperatura caras laterales diafragma", recommended_temperature),
            ("D. Estribos por corte diafragma", recommended_shear),
        )
    return (
        (
            "A. Acero principal negativo diafragma",
            _prompt_main_placement_option(reinforcement.negative.placement_options),
        ),
        (
            "B. Acero principal positivo diafragma",
            _prompt_main_placement_option(reinforcement.positive.placement_options),
        ),
        (
            "C. Temperatura caras laterales diafragma",
            _prompt_spacing_option(reinforcement.temperature.spacing_options),
        ),
        (
            "D. Estribos por corte diafragma",
            _prompt_shear_stirrup_option(reinforcement.shear),
        ),
    )


def format_diaphragm_reinforcement_selection(
    selected: tuple[
        tuple[
            str,
            LongitudinalBarPlacementOption
            | ReinforcementSpacingOption
            | ShearStirrupOption,
        ],
        ...,
    ],
) -> str:
    """Return an ASCII summary of selected diaphragm reinforcement."""
    return "\n".join(
        [""] + _selected_reinforcement_table(
            "ACEROS SELECCIONADOS - VIGA DIAFRAGMA",
            selected,
        )
    )


def collect_cantilever_reinforcement_selection(cantilever) -> tuple[
    tuple[str, ReinforcementSpacingOption],
    ...,
]:
    """Allow the user to keep or change overhang slab steel distributions."""
    cases = (
        ("A", cantilever.flexural_steel.spacing_options),
        ("B", cantilever.temperature_steel.spacing_options),
    )
    answer = input(
        "\nDesea seleccionar o cambiar las distribuciones del voladizo? [s/N]: "
    ).strip().lower()
    if answer not in ("s", "si", "y", "yes"):
        return _default_reinforcement_spacing_selection(cases)

    selected: list[tuple[str, ReinforcementSpacingOption]] = []
    for code, case_options in cases:
        selected.append((f"{code}. {case_options.label}", _prompt_spacing_option(case_options)))
    return tuple(selected)


def format_cantilever_reinforcement_selection(
    selected: tuple[tuple[str, ReinforcementSpacingOption], ...],
) -> str:
    """Return selected overhang slab reinforcement."""
    return "\n".join(
        [""] + _selected_reinforcement_table(
            "ACEROS SELECCIONADOS - LOSA EN VOLADIZO",
            selected,
        )
    )


def format_cantilever_selected_reviews(
    geometry,
    materials,
    cantilever,
    selected: tuple[tuple[str, ReinforcementSpacingOption], ...],
    development_review=None,
    crack_review=None,
) -> str:
    """Return development and crack checks using selected overhang top steel."""
    from bridge_design.domain._cantilever_slab_calculations import design_development
    from bridge_design.domain._cantilever_slab_checks import review_crack_control

    selected_flexural = _selected_spacing(selected, "A.")
    development = development_review or design_development(
        geometry=geometry,
        materials=materials,
        params=cantilever.parameters,
        flexural=cantilever.flexural_steel,
        selected_spacing=selected_flexural,
    )
    crack = crack_review or review_crack_control(
        geometry=geometry,
        materials=materials,
        params=cantilever.parameters,
        combinations=cantilever.combinations,
        flexural=cantilever.flexural_steel,
        selected_spacing=selected_flexural,
    )
    return "\n".join(
        [""] + boxed_table(
            ("Verificacion", "Parametro", "Demanda", "Limite/Longitud", "Estado"),
            (
                (
                    "Desarrollo",
                    development.bar_label,
                    f"ld req = {development.required_development_length_cm:.2f} cm",
                    f"L adicional = {development.total_additional_bar_length_m:.3f} m",
                    development.status,
                ),
                (
                    "Fisuracion",
                    f"fs = {crack.steel_stress_kg_cm2:.0f} kg/cm2",
                    f"s prov = {crack.provided_spacing_m:.3f} m",
                    f"s max = {crack.maximum_spacing_m:.3f} m",
                    crack.status,
                ),
            ),
            aligns=("left", "left", "right", "right", "center"),
            title="REVISIONES CON ACERO SELECCIONADO - LOSA EN VOLADIZO",
        )
    )


def collect_exterior_girder_reinforcement_selection(
    reinforcement: InteriorGirderReinforcementDesign,
    shear,
) -> tuple[
    tuple[str, LongitudinalBarPlacementOption | ReinforcementSpacingOption | ShearStirrupOption],
    ...,
]:
    """Allow the user to keep or change exterior girder reinforcement."""
    answer = input(
        "\nDesea seleccionar o cambiar el acero de la viga exterior? [s/N]: "
    ).strip().lower()
    recommended_main = reinforcement.main.placement_options.recommended
    if recommended_main is None:
        recommended_main = reinforcement.main.placement_options.options[-1]
    recommended_temperature = (
        reinforcement.temperature.spacing_options.recommended
        or reinforcement.temperature.spacing_options.options[-1]
    )
    recommended_skin = (
        reinforcement.skin.spacing_options.recommended
        or reinforcement.skin.spacing_options.options[-1]
    )
    if answer not in ("s", "si", "y", "yes"):
        recommended_shear = _recommended_shear_option_or_raise(shear)
        return (
            ("A. Acero principal longitudinal exterior", recommended_main),
            ("B. Temperatura caras laterales exterior", recommended_temperature),
            ("C. Ask longitudinal exterior por cara", recommended_skin),
            ("D. Estribos por corte exterior", recommended_shear),
        )
    return (
        (
            "A. Acero principal longitudinal exterior",
            _prompt_main_placement_option(reinforcement.main.placement_options),
        ),
        (
            "B. Temperatura caras laterales exterior",
            _prompt_spacing_option(reinforcement.temperature.spacing_options),
        ),
        (
            "C. Ask longitudinal exterior por cara",
            _prompt_spacing_option(reinforcement.skin.spacing_options),
        ),
        (
            "D. Estribos por corte exterior",
            _prompt_shear_stirrup_option(shear),
        ),
    )


def format_exterior_girder_reinforcement_selection(
    selected: tuple[
        tuple[str, LongitudinalBarPlacementOption | ReinforcementSpacingOption | ShearStirrupOption],
        ...,
    ],
) -> str:
    """Return an ASCII summary of selected exterior girder reinforcement."""
    return "\n".join(
        [""] + _selected_reinforcement_table(
            "ACEROS SELECCIONADOS - VIGA PRINCIPAL EXTERIOR",
            selected,
        )
    )


def format_exterior_girder_selected_main_reviews(
    geometry,
    materials,
    analysis,
    reinforcement: InteriorGirderReinforcementDesign,
    main_placement: LongitudinalBarPlacementOption | None,
    crack_review=None,
    fatigue_review=None,
    service_review=None,
) -> str:
    """Return service/fatigue/crack checks using selected exterior main bars."""
    crack = crack_review or review_exterior_girder_crack_control(
        geometry=geometry,
        materials=materials,
        analysis=analysis,
        reinforcement=reinforcement,
        main_placement=main_placement,
    )
    fatigue = fatigue_review or review_exterior_girder_fatigue(
        geometry=geometry,
        materials=materials,
        analysis=analysis,
        reinforcement=reinforcement,
        main_placement=main_placement,
    )
    stresses = service_review or verify_exterior_girder_service_stresses(
        geometry=geometry,
        materials=materials,
        analysis=analysis,
        reinforcement=reinforcement,
        main_placement=main_placement,
    )
    return "\n".join(
        [""] + boxed_table(
            ("Verificacion", "Demanda", "Limite", "Estado"),
            (
                (
                    "Fisuracion",
                    f"s prov = {crack.main.provided_spacing_m:.3f} m; fs = {crack.main.steel_stress_kg_cm2:.0f} kg/cm2",
                    f"s max = {crack.main.maximum_spacing_m:.3f} m",
                    crack.main.status,
                ),
                (
                    "Fatiga acero",
                    f"{fatigue.factored_stress_range_kg_cm2:.0f} kg/cm2",
                    f"{fatigue.allowable_stress_range_kg_cm2:.0f} kg/cm2",
                    fatigue.status,
                ),
                (
                    "Servicio I concreto",
                    f"{stresses.concrete_compression_kg_cm2:.1f} kg/cm2",
                    f"{stresses.concrete_compression_limit_kg_cm2:.1f} kg/cm2",
                    stresses.concrete_status,
                ),
                (
                    "Servicio I acero",
                    f"{stresses.steel_tension_kg_cm2:.0f} kg/cm2",
                    f"{stresses.steel_tension_limit_kg_cm2:.0f} kg/cm2",
                    stresses.steel_status,
                ),
            ),
            aligns=("left", "right", "right", "center"),
            title="REVISIONES CON ACERO PRINCIPAL SELECCIONADO - VIGA EXTERIOR",
        )
    )


def _selected_reinforcement_table(
    title: str,
    selected: tuple[
        tuple[
            str,
            LongitudinalBarPlacementOption
            | ReinforcementSpacingOption
            | ShearStirrupOption,
        ],
        ...,
    ],
) -> list[str]:
    rows = [_selected_reinforcement_row(label, option) for label, option in selected]
    return boxed_table(
        (
            "Caso",
            "Item/Origen",
            "Barra/Estribo",
            "N/Ramas",
            "s (m)",
            "As/Av req",
            "As/Av prov",
            "Capas",
            "Estado",
        ),
        rows,
        aligns=(
            "left",
            "right",
            "right",
            "right",
            "right",
            "right",
            "right",
            "right",
            "center",
        ),
        title=title,
    )


def _selected_reinforcement_row(
    label: str,
    option: LongitudinalBarPlacementOption | ReinforcementSpacingOption | ShearStirrupOption,
) -> tuple[str, object, str, object, str, str, str, str, str]:
    state = "OK" if option.is_compliant else "NO"
    item = "P" if getattr(option, "is_custom", False) else option.item
    if isinstance(option, LongitudinalBarPlacementOption):
        return (
            label,
            item,
            option.bar_label,
            option.bar_count,
            "-",
            "-",
            f"{option.provided_area_cm2:.3f} cm2",
            str(option.layers),
            state,
        )
    if isinstance(option, ShearStirrupOption):
        return (
            label,
            item,
            option.bar_label,
            option.legs,
            f"{option.spacing_m:.3f}",
            f"{option.required_av_cm2_m:.3f} cm2/m",
            f"{option.provided_av_cm2_m:.3f} cm2/m",
            "-",
            state,
        )
    return (
        label,
        item,
        option.bar.label,
        "-",
        f"{option.spacing_m:.3f}",
        f"{option.required_area_cm2_m:.3f} cm2/m",
        f"{option.provided_area_cm2_m:.3f} cm2/m",
        "-",
        state,
    )


if __name__ == "__main__":
    main()
