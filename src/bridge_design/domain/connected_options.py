"""Evaluated reinforcement alternatives and rechecking of user-selected bars."""

from dataclasses import dataclass, replace

from bridge_design.domain.connected_reinforcement import (
    ConnectedBarChoice, ConnectedSteelChoice, design_connected_reinforcement,
    design_region, region_has_reinforcement_design, region_setup, section_demands, validate_choice,
)
from bridge_design.domain.connected_steel_audit import area_requirements
from bridge_design.domain.connected_distributions import reinforcement_demands, distribution_demands
from bridge_design.domain.rebar_catalog import generate_spacing_options, REINFORCING_BAR_CATALOG


@dataclass(frozen=True)
class ConnectedRegionOptions:
    region: str
    principal: tuple
    transverse: object
    adopted: object


def area_options(data, region, demands):
    inputs, cover, grid, temperature, _ = region_setup(data, region, demands)
    options = []
    for bar in REINFORCING_BAR_CATALOG:
        if min(d.depth_cm for d in demands) <= 2*(cover+bar.diameter_cm/2):
            continue
        area = _area_option(demands, inputs, cover, bar, grid.maximum_m, temperature)
        candidate = next(o for o in generate_spacing_options(region, area.required_as_cm2_m, grid).options
                         if o.bar == bar)
        options.append(_area_option(demands, inputs, cover, bar, candidate.spacing_m, temperature))
    if not options:
        raise ValueError(f"El espesor y recubrimiento no admiten barras del catalogo: {region}.")
    return tuple(options)


@dataclass(frozen=True)
class ConnectedPrincipalOption:
    bar_label: str
    spacing_m: float
    required_as_cm2_m: float
    area_per_face_cm2_m: float
    is_compliant: bool


def _area_option(demands, inputs, cover, bar, spacing, temperature):
    rows = area_requirements(demands, inputs, cover, bar)
    required = max([temperature] + [max(row["flexural_area"], row["minimum_area"]) for row in rows])
    provided = bar.area_cm2/spacing
    return ConnectedPrincipalOption(bar.label, spacing, required, provided, provided+1e-8 >= required)


def check_principal_area_choice(result, region, choice):
    if not region_has_reinforcement_design(region):
        raise ValueError(f"Region excluida del diseno de acero: {region}.")
    demands = reinforcement_demands(result.inputs, result.mesh, result.results)[region]
    inputs, cover, grid, temperature, _ = region_setup(result.inputs, region, demands)
    _, bar, spacing = validate_choice(choice, grid, cover, demands, principal=False)
    return _area_option(demands, inputs, cover, bar, spacing, temperature)


def choice_from_steel(steel):
    cut = steel.foundation_reinforcement_cut
    continuous = (ConnectedBarChoice(steel.bar_label, cut.requested_continuous_spacing_m)
                  if cut and cut.requested_continuous_spacing_m is not None else None)
    return ConnectedSteelChoice(ConnectedBarChoice(steel.bar_label, steel.spacing_m),
                                ConnectedBarChoice(steel.transverse_bar_label, steel.transverse_spacing_m), continuous)


def connected_reinforcement_options(result):
    grouped = reinforcement_demands(result.inputs, result.mesh, result.results)
    options = []
    for adopted in result.reinforcement:
        region = adopted.region
        demands = grouped[region]
        principal = area_options(result.inputs, region, demands)
        options.append(ConnectedRegionOptions(region, principal, None, adopted))
    return tuple(options)


def check_region_choice(result, region, choice):
    grouped = reinforcement_demands(result.inputs, result.mesh, result.results)
    if region not in grouped or not region_has_reinforcement_design(region):
        raise ValueError(f"Region no reconocida: {region}.")
    definition = next(item for item in distribution_demands(result.inputs, result.mesh,
        section_demands(result.inputs, result.mesh, result.results)) if item.label == region)
    return design_region(result.inputs, result.mesh, region, grouped[region], choice, distribution=definition)


def apply_connected_selections(result, selections):
    steel = design_connected_reinforcement(result.inputs, result.mesh, result.results, selections)
    return replace(result, reinforcement=steel, selected_reinforcement=dict(selections))
