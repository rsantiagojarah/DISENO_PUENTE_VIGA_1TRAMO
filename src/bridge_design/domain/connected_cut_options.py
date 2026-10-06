"""Verified one-in-two cutoff choices for connected abutments, command 2.

Only the fill-side stem and the two longitudinal footing faces are offered.
Each row uses one bar diameter: the heavy spacing is s and the light spacing
is 2s. A row is listed only when flexure, shear, crack control and minimum
steel pass in every zone.
"""

from dataclasses import dataclass

from bridge_design.domain.connected_2_inputs import is_connected_2
from bridge_design.domain.rebar_catalog import REINFORCING_BAR_CATALOG, reinforcing_bar_by_label


STEM_REGION = "Pantalla - vertical relleno"
TOP_FOOTING = "Zapata combinada - longitudinal superior"
BOTTOM_FOOTING = "Zapata combinada - longitudinal inferior"
CUT_REGIONS = (STEM_REGION, TOP_FOOTING, BOTTOM_FOOTING)
_CUT_CACHE = {}


@dataclass(frozen=True)
class CutAlternative:
    code: str
    bar_label: str
    heavy_spacing_m: float
    light_spacing_m: float
    location_m: float
    location_text: str
    choice: object


def offers_cut_table(data, region, role):
    return is_connected_2(data) and role == "primary" and region in CUT_REGIONS


def spacing_pairs(grid):
    heavy = grid.minimum_m
    pairs = []
    while 2 * heavy <= grid.maximum_m + 1e-9:
        pairs.append((round(heavy, 10), round(2 * heavy, 10)))
        heavy = round(heavy + grid.step_m, 10)
    return tuple(pairs)


def verified_cut_alternatives(result, region):
    key = (id(result.inputs), id(result.mesh), id(result.results), region)
    if key not in _CUT_CACHE:
        _CUT_CACHE[key] = _verified_cut_alternatives(result, region)
    return _CUT_CACHE[key]


def _verified_cut_alternatives(result, region):
    from types import SimpleNamespace

    from bridge_design.codes.mtc_2018 import mtc_tension_development_length_cm
    from bridge_design.domain.connected_distributions import reinforcement_demands
    from bridge_design.domain.connected_foundation_cut import connected_foundation_reinforcement_cut
    from bridge_design.domain.connected_foundation_zones import foundation_zone_checks, foundation_zone_choice
    from bridge_design.domain.connected_reinforcement import (
        ConnectedBarChoice, ConnectedSteelChoice, evaluate_option, region_setup,
    )
    from bridge_design.domain.connected_stem_cut import connected_stem_reinforcement_cut

    demands = reinforcement_demands(result.inputs, result.mesh, result.results)[region]
    if not demands:
        return ()
    inputs, cover, grid, temperature, _ = region_setup(result.inputs, region, demands)
    found = []
    for bar in REINFORCING_BAR_CATALOG:
        if bar.diameter_cm < 1.27 or min(demand.depth_cm for demand in demands) <= 2 * (cover + bar.diameter_cm / 2):
            continue
        anchor = mtc_tension_development_length_cm(
            bar.diameter_cm, inputs.materials.steel_yield_kg_cm2, inputs.materials.concrete_strength_kg_cm2,
            location_factor=inputs.reinforcement.development_location_factor,
            coating_factor=inputs.reinforcement.development_coating_factor,
            lightweight_factor=inputs.reinforcement.development_lightweight_factor,
            confinement_factor=inputs.reinforcement.development_confinement_factor,
            excess_reinforcement_factor=1.0)[0]
        for heavy, light in spacing_pairs(grid):
            area = bar.area_cm2 / heavy
            ratios = evaluate_option(demands, inputs, cover, bar, heavy)
            if max(*ratios[:3], temperature / area) > 1 + 1e-8:
                continue
            if region == STEM_REGION:
                choice = ConnectedSteelChoice(ConnectedBarChoice(bar.label, heavy), ConnectedBarChoice(bar.label, heavy))
                probed = SimpleNamespace(region=region, status="OK", bar_label=bar.label, spacing_m=heavy,
                    area_per_face_cm2_m=area, temperature_cm2_m=temperature, required_straight_anchor_cm=anchor)
                cut = connected_stem_reinforcement_cut(result.inputs, result.mesh, probed, demands)
                steel = SimpleNamespace(bar_label=bar.label, spacing_m=heavy, stem_reinforcement_cut=cut,
                                        foundation_reinforcement_cut=None, status="OK")
            else:
                choice = foundation_zone_choice(ConnectedBarChoice(bar.label, light))
                probed = SimpleNamespace(status="OK", face="Superior" if region == TOP_FOOTING else "Inferior",
                    flexural_utilization=ratios[0], shear_utilization=ratios[1], crack_utilization=ratios[2],
                    minimum_utilization=temperature / area, bar_label=bar.label, spacing_m=heavy,
                    temperature_cm2_m=temperature, required_straight_anchor_cm=anchor)
                cut = connected_foundation_reinforcement_cut(
                    result.inputs, result.mesh, probed, demands, continuous=SimpleNamespace(spacing_m=light))
                if cut.status == "APLICA":
                    cut = replace_zones(cut, foundation_zone_checks(result.inputs, result.mesh, probed, demands, cut))
                steel = SimpleNamespace(status="OK", bar_label=bar.label, spacing_m=heavy,
                                        foundation_reinforcement_cut=cut, stem_reinforcement_cut=None)
            row = _accepted(region, steel, heavy, light, choice)
            if row is not None:
                found.append(row)
    found.sort(key=lambda row: (reinforcing_bar_by_label(row[0]).diameter_cm, row[1]))
    return tuple(CutAlternative(f"C{index}", *row) for index, row in enumerate(found, 1))


def replace_zones(cut, zones):
    from dataclasses import replace
    return replace(cut, zones=zones)


def _accepted(region, steel, heavy, light, choice):
    if region == STEM_REGION:
        cut = steel.stem_reinforcement_cut
        if (cut is None or cut.status != "OK" or cut.continuous_every_n_bars != 2
                or abs(cut.lower_spacing_m - heavy) > 1e-8 or abs(cut.upper_spacing_m - light) > 1e-8):
            return None
        return (steel.bar_label, heavy, light, cut.constructive_cut_height_m,
                f"{cut.constructive_cut_height_m:.3f} m sobre la base", choice)
    cut = steel.foundation_reinforcement_cut
    if (steel.status != "OK" or cut is None or cut.status != "APLICA" or cut.pattern is None
            or cut.pattern.cycle_bars != 2 or not cut.zones or any(zone.status != "OK" for zone in cut.zones)
            or abs(steel.spacing_m - heavy) > 1e-8 or abs(cut.pattern.equivalent_spacing_m - light) > 1e-8):
        return None
    sense = "hacia el centro" if cut.distance_from_inner_face_m >= 0 else "hacia el talon"
    distance = abs(cut.distance_from_inner_face_m)
    return (steel.bar_label, heavy, light, distance, f"{distance:.3f} m {sense}", choice)
