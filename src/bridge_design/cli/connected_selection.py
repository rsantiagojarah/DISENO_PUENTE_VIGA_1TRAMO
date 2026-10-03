"""Console reinforcement selection with the same item/custom workflow as abutments."""

from bridge_design.cli.abutment_input_prompts import _prompt_spacing_option
from bridge_design.cli.ascii_tables import boxed_table
from bridge_design.cli.connected_prompts import yes_no
from bridge_design.domain.connected_options import check_region_choice, choice_from_steel
from bridge_design.domain.connected_reinforcement import ConnectedBarChoice, ConnectedSteelChoice, DESIGN_SCOPE_NOTE
from bridge_design.domain.rebar_catalog import REINFORCING_BAR_CATALOG


def format_connected_options(groups):
    lines = ["SELECCION DE ACERO DE ESTRIBOS CONECTADOS",
             DESIGN_SCOPE_NOTE,
             "Armadura principal simetrica por cara; * identifica la propuesta inicial.",
             "Indices <= 1 cumplen. NO CUMPLE no es una recomendacion de armado."]
    for group in groups:
        rows = []
        for item, steel in enumerate(group.principal, 1):
            adopted = steel.bar_label == group.adopted.bar_label and abs(steel.spacing_m - group.adopted.spacing_m) < 1e-8
            rows.append((str(item) + ("*" if adopted else ""), steel.bar_label, f"{steel.spacing_m:.3f}",
                         f"{steel.required_as_cm2_m:.3f}", f"{steel.area_per_face_cm2_m:.3f}", f"{steel.flexural_utilization:.3f}",
                         f"{steel.shear_utilization:.3f}", f"{steel.crack_utilization:.3f}", steel.status))
        lines.extend(boxed_table(("Item", "Barra", "s m", "As req", "As prov/cara", "Flexion", "Corte", "Fisura", "Estado"),
                                 rows, title=group.region.upper() + " - PRINCIPAL", row_separators=False))
        lines.extend(boxed_table(("Item", "Barra", "s m", "As/cara cm2/m", "Estado"),
            ((str(option.item) + ("*" if option.is_recommended else ""), option.bar.label,
              f"{option.spacing_m:.3f}", f"{option.provided_area_cm2_m:.3f}",
              "OK" if option.is_compliant else "NO CUMPLE") for option in group.transverse.options),
            title=group.region.upper() + " - TRANSVERSAL", row_separators=False))
    return "\n".join(lines)


def _principal_choice(result, group):
    default = choice_from_steel(group.adopted)
    while True:
        raw = input(f"{group.region} - principal, elija item (Enter=propuesta; P=personalizado): ").strip()
        if not raw:
            return default.principal
        try:
            if raw.lower() in ("p", "personalizado", "personalizada"):
                print("Barras: " + ", ".join(bar.label for bar in REINFORCING_BAR_CATALOG if bar.diameter_cm >= 1.27))
                label = input(f"Barra [{default.principal.bar_label}]: ").strip() or default.principal.bar_label
                raw_spacing = input(f"Separacion en m [{default.principal.spacing_m:.3f}]: ").strip()
                spacing = float(raw_spacing.replace(",", ".")) if raw_spacing else default.principal.spacing_m
                chosen = ConnectedBarChoice(label, spacing)
            else:
                item = int(raw)
                if not 1 <= item <= len(group.principal):
                    raise ValueError("El item no existe para esta region.")
                chosen = choice_from_steel(group.principal[item - 1]).principal
            checked = check_region_choice(result, group.region, ConnectedSteelChoice(chosen, default.transverse))
            print(f"Flexion={checked.flexural_utilization:.3f}; corte={checked.shear_utilization:.3f}; "
                  f"fisura={checked.crack_utilization:.3f}; minimo={checked.minimum_utilization:.3f}: {checked.status}")
            if checked.status != "OK" and not yes_no("NO CUMPLE. Conservar solo para revision", False):
                continue
            return ConnectedBarChoice(checked.bar_label, checked.spacing_m)
        except (ValueError, TypeError) as error:
            print(f"Configuracion no valida: {error}")


def collect_connected_selection(result, groups):
    if not yes_no("Desea seleccionar o cambiar las distribuciones de acero de los estribos conectados", False):
        return {group.region: choice_from_steel(group.adopted) for group in groups}
    selected = {}
    for group in groups:
        print(f"\n{group.region.upper()} - ARMADURA POR CARA")
        if group.adopted.status != "OK":
            print("La propuesta inicial NO CUMPLE. Enter la conserva para revision, no la aprueba.")
        principal = _principal_choice(result, group)
        transverse = _prompt_spacing_option(group.transverse)
        selected[group.region] = ConnectedSteelChoice(principal,
            ConnectedBarChoice(transverse.bar.label, transverse.spacing_m))
    return selected
