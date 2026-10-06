"""Console reinforcement selection with the same item/custom workflow as abutments."""

from bridge_design.cli.abutment_input_prompts import _prompt_spacing_option
from bridge_design.cli.abutment_ascii_output import _format_spacing_option_table, _format_stem_reinforcement_cut_option
from bridge_design.cli.ascii_tables import audit_block_title, boxed_table
from bridge_design.cli.connected_prompts import yes_no
from bridge_design.domain.connected_2_inputs import is_connected_2
from bridge_design.domain.connected_cut_options import BOTTOM_FOOTING, STEM_REGION, TOP_FOOTING
from bridge_design.domain.connected_options import check_principal_area_choice, choice_from_steel
from bridge_design.domain.connected_reinforcement import ConnectedBarChoice, ConnectedSteelChoice, DESIGN_SCOPE_NOTE
from bridge_design.reporting.connected_cut_report import format_foundation_cut
from bridge_design.domain.rebar_catalog import (
    REINFORCING_BAR_CATALOG, ReinforcementCaseOptions, ReinforcementSpacingOption,
    reinforcing_bar_by_label,
)


def format_connected_options(groups):
    lines = [*audit_block_title("2", "SELECCION DE ACERO DE ESTRIBOS CONECTADOS", 112),
             DESIGN_SCOPE_NOTE,
             "Un unico armado por cara y direccion para ambos estribos, con la envolvente de los dos lados. "
             "As req y As prov en cm2/m.",
             "Estado de opciones: solo area requerida por flexion y minimos frente al area proporcionada.",
             "Cortante, fisuracion y anclaje se verifican con la distribucion elegida en el resumen final."]
    if any(group.offer_cuts for group in groups):
        lines.append("C1, C2... eligen un corte de 1 de cada 2 ya verificado en pantalla del relleno y en la zapata longitudinal. "
                     "El item numerico conserva ese acero en toda la longitud.")
    for group in groups:
        options = []
        for item, steel in enumerate(group.principal, 1):
            adopted = steel.bar_label == group.adopted.bar_label and abs(steel.spacing_m - group.adopted.spacing_m) < 1e-8
            options.append(ReinforcementSpacingOption(item, reinforcing_bar_by_label(steel.bar_label),
                steel.spacing_m, steel.required_as_cm2_m, steel.area_per_face_cm2_m, steel.is_compliant, adopted))
        principal = ReinforcementCaseOptions(group.region, 0.0, tuple(options))
        lines.extend(["", *_format_spacing_option_table(principal)])
        if not any(option.is_compliant for option in options):
            lines.append("Sin distribucion que cumpla el area requerida dentro del catalogo y separaciones actuales.")
        if group.offer_cuts:
            lines.extend(_format_cut_alternatives(group))
        elif group.region == "Pantalla - vertical relleno" and group.adopted.role == "primary":
            lines.append(f"Propuesta de corte para {group.region}: {group.adopted.bar_label} @ {group.adopted.spacing_m:.3f} m")
            lines.extend(_format_stem_reinforcement_cut_option(group.adopted))
            if group.adopted.stem_reinforcement_cut:
                lines.append(group.adopted.stem_reinforcement_cut.notes)
        if group.transverse is not None:
            lines.extend(["", *_format_spacing_option_table(group.transverse)])
        if not group.offer_cuts:
            lines.extend(format_foundation_cut(group.adopted))
    return "\n".join(lines)


def _format_cut_alternatives(group):
    if group.region == STEM_REGION:
        note = "s mayor desde la base hasta el corte; s menor de alli a la coronacion."
        place = "Altura sobre base"
    elif group.region == TOP_FOOTING:
        note = "s mayor en el centro; s menor en los dos extremos."
        place = "Desde cara interior"
    elif group.region == BOTTOM_FOOTING:
        note = "s mayor en los dos extremos; s menor en el centro."
        place = "Desde cara interior"
    else:
        return []
    lines = ["", note, "Solo se listan cortes de 1 de cada 2 que cumplen flexion, cortante, fisuracion y minimos."]
    if not group.cuts:
        lines.append("Sin corte utilizable para esta cara.")
        return lines
    rows = tuple((cut.code, cut.bar_label, f"{cut.heavy_spacing_m:.3f}", f"{cut.light_spacing_m:.3f}", cut.location_text)
                 for cut in group.cuts)
    lines.extend(boxed_table(("Corte", "Barra", "s mayor (m)", "s menor (m)", place), rows,
                             aligns=("center", "center", "right", "right", "left"),
                             title=f"CORTES - {group.region}"))
    return lines


def _principal_choice(result, group):
    default = choice_from_steel(group.adopted)
    default_item = next((item for item, option in enumerate(group.principal, 1)
                         if option.bar_label == default.principal.bar_label
                         and abs(option.spacing_m-default.principal.spacing_m) < 1e-8), None)
    while True:
        modes = "C#=corte, P=personalizado" if group.offer_cuts else "P=personalizado"
        raw = input(f"{group.region} - elija item [{default_item}] ({modes}): ").strip()
        if not raw:
            return default if default.foundation_continuous else default.principal
        try:
            if group.offer_cuts and raw.lower().startswith("c") and raw[1:].isdigit():
                chosen_cut = next((cut for cut in group.cuts if cut.code.lower() == raw.lower()), None)
                if chosen_cut is None:
                    raise ValueError("Ese corte no esta en la tabla.")
                return chosen_cut.choice
            if raw.lower() in ("p", "personalizado", "personalizada"):
                print("Barras: " + ", ".join(bar.label for bar in REINFORCING_BAR_CATALOG))
                label = input(f"Barra [{default.principal.bar_label}]: ").strip() or default.principal.bar_label
                raw_spacing = input(f"Separacion en m [{default.principal.spacing_m:.3f}]: ").strip()
                spacing = float(raw_spacing.replace(",", ".")) if raw_spacing else default.principal.spacing_m
                chosen = ConnectedBarChoice(label, spacing, is_custom=True)
            else:
                item = int(raw)
                if not 1 <= item <= len(group.principal):
                    raise ValueError("El item no existe para esta region.")
                option = group.principal[item - 1]
                if not option.is_compliant:
                    raise ValueError("El item no aparece en la tabla de opciones que cumplen el area requerida.")
                chosen = ConnectedBarChoice(option.bar_label, option.spacing_m)
            checked = check_principal_area_choice(result, group.region, chosen)
            print(f"As requerido={checked.required_as_cm2_m:.3f}; As proporcionado={checked.area_per_face_cm2_m:.3f} cm2/m. "
                  "Las verificaciones finales se realizan despues de la seleccion.")
            if not checked.is_compliant and not yes_no("NO CUMPLE el area requerida. Conservar solo para revision", False):
                continue
            return ConnectedBarChoice(checked.bar_label, checked.spacing_m, chosen.is_custom)
        except (ValueError, TypeError) as error:
            print(f"Configuracion no valida: {error}")


def collect_connected_selection(result, groups):
    if not yes_no("Desea seleccionar o cambiar las distribuciones de acero de los estribos conectados", True):
        return {group.region: choice_from_steel(group.adopted) for group in groups}
    selected = {}
    for group in groups:
        print(f"\n{group.region.upper()}")
        print("Enter conserva la propuesta; el cumplimiento final se verifica despues de elegir las distribuciones.")
        principal = _principal_choice(result, group)
        if isinstance(principal, ConnectedSteelChoice):
            selected[group.region] = principal
            continue
        if group.transverse is None:
            selected[group.region] = ConnectedSteelChoice(principal, principal)
            continue
        transverse = _prompt_spacing_option(group.transverse)
        transverse_choice = ConnectedBarChoice(transverse.bar.label, transverse.spacing_m, transverse.is_custom)
        initial = choice_from_steel(group.adopted).transverse
        if not transverse_choice.is_custom and transverse_choice.bar_label == initial.bar_label and abs(transverse_choice.spacing_m-initial.spacing_m) < 1e-8:
            transverse_choice = initial
        selected[group.region] = ConnectedSteelChoice(principal,
            transverse_choice)
    return selected


def format_connected_selection(result):
    rows = []
    for steel in result.reinforcement:
        selected = result.selected_reinforcement.get(steel.region)
        if steel.base_region:
            choice = selected.principal if selected else None
            rows.append((steel.region, "USUARIO" if choice and choice.is_custom else "TABLA", steel.bar_label,
                f"{steel.spacing_m:.3f}", f"{steel.required_as_cm2_m:.3f}", f"{steel.area_per_face_cm2_m:.3f}",
                "OK" if steel.area_per_face_cm2_m+1e-8 >= steel.required_as_cm2_m else "NO"))
            continue
        for direction, label, spacing, required, provided, choice in (
            ("principal por cara", steel.bar_label, steel.spacing_m, steel.required_as_cm2_m,
             steel.area_per_face_cm2_m, selected.principal if selected else None),
            ("transversal por cara", steel.transverse_bar_label, steel.transverse_spacing_m,
             steel.temperature_cm2_m, reinforcing_bar_by_label(steel.transverse_bar_label).area_cm2/steel.transverse_spacing_m,
             selected.transverse if selected else None),
        ):
            rows.append((f"{steel.region} - {direction}", "USUARIO" if choice and choice.is_custom else "TABLA",
                         label, f"{spacing:.3f}", f"{required:.3f}", f"{provided:.3f}",
                         "OK" if provided+1e-8 >= required else "NO"))
    lines = boxed_table(
        ("Caso", "Origen", "Barra", "s (m)", "As req", "As prov", "Estado"), rows,
        aligns=("left", "center", "center", "right", "right", "right", "center"),
        title="ACEROS SELECCIONADOS - ESTRIBOS COMBINADOS")
    if is_connected_2(result.inputs):
        for steel in result.reinforcement:
            cut = steel.foundation_reinforcement_cut
            if cut is not None and cut.status == "APLICA" and cut.pattern is not None and cut.pattern.cycle_bars == 2:
                sense = "hacia el centro" if cut.distance_from_inner_face_m >= 0 else "hacia el talon"
                lines.append(f"{steel.region}: {steel.bar_label}; s mayor {steel.spacing_m:.3f} m; "
                             f"s menor {cut.pattern.equivalent_spacing_m:.3f} m; "
                             f"corte a {abs(cut.distance_from_inner_face_m):.3f} m de cada cara interior, {sense}.")
            stem = steel.stem_reinforcement_cut
            if steel.region == STEM_REGION and stem is not None and stem.status == "OK" and stem.continuous_every_n_bars == 2:
                lines.append(f"{steel.region}: {stem.lower_bar_label}; s mayor {stem.lower_spacing_m:.3f} m; "
                             f"s menor {stem.upper_spacing_m:.3f} m; "
                             f"corte a {stem.constructive_cut_height_m:.3f} m sobre la base.")
    elif any(c.foundation_continuous for c in result.selected_reinforcement.values()):
        lines.append("En el armado por zonas, esta tabla muestra el TOTAL donde coinciden continuo y adicional. "
                     "Las tablas de cortes identifican cada familia y verifican los tramos con solo acero continuo.")
    return "\n".join(lines)
