"""Efficient input of equal interleaved continuous/additional bar families."""

from bridge_design.cli.connected_prompts import yes_no
from bridge_design.domain.connected_2_inputs import is_connected_2
from bridge_design.domain.connected_foundation_zones import foundation_zone_choice
from bridge_design.domain.connected_options import check_region_choice
from bridge_design.domain.connected_reinforcement import ConnectedBarChoice
from bridge_design.reporting.connected_cut_report import format_foundation_cut


def allows_foundation_zones(result, group):
    return (is_connected_2(result.inputs) and group.adopted.base_region == "Zapata combinada"
            and group.adopted.role == "primary")


def prompt_foundation_zones(result, group):
    print("Acero continuo y adicional del mismo diametro, intercalados: s continuo + s adicional = s/2 total.")
    print("El adicional se coloca en el centro arriba y en ambos extremos abajo; su longitud se calcula.")
    print("Los sectores con solo acero continuo se verifican con sus esfuerzos locales.")
    cut = group.adopted.foundation_reinforcement_cut
    previous = cut.requested_continuous_spacing_m if cut else None
    default_bar = group.adopted.bar_label if previous else '1"'
    default_spacing = previous or .20
    label = input(f"Barra continua y adicional [{default_bar}]: ").strip() or default_bar
    raw = input(f"Separacion de cada familia en m [{default_spacing:.3f}]: ").strip()
    spacing = float(raw.replace(",", ".")) if raw else default_spacing
    choice = foundation_zone_choice(ConnectedBarChoice(label, spacing, is_custom=True))
    steel = check_region_choice(result, group.region, choice)
    print("\n".join(format_foundation_cut(steel)))
    if steel.foundation_reinforcement_cut.status != "APLICA" and not yes_no(
        "La propuesta por zonas no aplica. Conservar armado total continuo solo para revision", False
    ):
        raise ValueError("Elija otro armado o use la seleccion uniforme P.")
    return choice
