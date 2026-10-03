"""Evaluated reinforcement alternatives and rechecking of user-selected bars."""

from dataclasses import dataclass, replace

from bridge_design.domain.connected_reinforcement import (
    ConnectedBarChoice, ConnectedSteelChoice, design_connected_reinforcement,
    design_region, evaluate_option, region_setup, section_demands,
)
from bridge_design.domain.rebar_catalog import generate_spacing_options


@dataclass(frozen=True)
class ConnectedRegionOptions:
    region: str
    principal: tuple
    transverse: object
    adopted: object


def choice_from_steel(steel):
    return ConnectedSteelChoice(ConnectedBarChoice(steel.bar_label, steel.spacing_m),
                                ConnectedBarChoice(steel.transverse_bar_label, steel.transverse_spacing_m))


def connected_reinforcement_options(result):
    grouped = section_demands(result.inputs, result.mesh, result.results)
    options = []
    for adopted in result.reinforcement:
        region = adopted.region
        demands = grouped[region]
        inputs, cover, grid, temperature, candidates = region_setup(result.inputs, region, demands)
        principal = []
        bars = sorted({candidate[1] for candidate in candidates}, key=lambda bar: bar.diameter_cm)
        for bar in bars:
            alternatives = sorted((candidate for candidate in candidates if candidate[1] == bar),
                                  key=lambda row: row[2], reverse=True)
            selected = alternatives[-1]
            for candidate in alternatives:
                if max(evaluate_option(demands, inputs, cover, bar, candidate[2])[:3]) <= 1 + 1e-8:
                    selected = candidate
                    break
            choice = ConnectedSteelChoice(ConnectedBarChoice(bar.label, selected[2]),
                                          choice_from_steel(adopted).transverse)
            principal.append(design_region(result.inputs, result.mesh, region, demands, choice))
        transverse = generate_spacing_options(f"{region} - transversal por cara", temperature, grid)
        transverse = replace(transverse, options=tuple(replace(option, is_recommended=(
            option.bar.label == adopted.transverse_bar_label and abs(option.spacing_m - adopted.transverse_spacing_m) < 1e-8
        )) for option in transverse.options))
        options.append(ConnectedRegionOptions(region, tuple(principal), transverse, adopted))
    return tuple(options)


def check_region_choice(result, region, choice):
    grouped = section_demands(result.inputs, result.mesh, result.results)
    if region not in grouped:
        raise ValueError(f"Region no reconocida: {region}.")
    return design_region(result.inputs, result.mesh, region, grouped[region], choice)


def apply_connected_selections(result, selections):
    steel = design_connected_reinforcement(result.inputs, result.mesh, result.results, selections)
    return replace(result, reinforcement=steel, selected_reinforcement=dict(selections))
