"""Adapt the shared stem cutoff engine to connected FRAME demand envelopes."""

from dataclasses import replace
from math import isclose

from bridge_design.domain.abutment import _single_stem_reinforcement_cut, _stem_thickness_at_height_m
from bridge_design.domain.connected_2_inputs import is_connected_2
from bridge_design.domain.connected_section_checks import section_check
from bridge_design.domain.connected_steel_audit import area_requirements
from bridge_design.domain.rebar_catalog import SpacingGrid, reinforcing_bar_by_label


# Requested continuous upper grid for command 2; the original command is unchanged.
CONNECTED_2_CONTINUOUS_STEM_SPACING_M = 0.20


def connected_stem_reinforcement_cut(data, mesh, steel, demands):
    """Adapt FRAME envelopes by face to the individual-abutment cutoff engine.

    Retain whole elements at a proposed cut. Check every recovered extremum at
    the thinnest section of its element, so the search cannot discard a peak or
    rely on monotone bending. Heights stop at the transition to the cajuela.
    """
    if steel.region != "Pantalla - vertical relleno" or steel.status != "OK":
        return None
    bar = reinforcing_bar_by_label(steel.bar_label)
    records = []
    for demand in demands:
        element = mesh.frame.elements[demand.element]
        first, last = (mesh.frame.nodes[n] for n in (element.start, element.end))
        side = data.right if element.region.endswith("derecha") else data.left
        start, end = sorted((first.y, last.y))
        # One-sided geometric values retain the correct thickness at steps.
        depth = 100 * min(_stem_thickness_at_height_m(side, y)
                          for y in (start + 1e-8, end - 1e-8))
        records.append((end, side, replace(demand, depth_cm=depth)))
    if not records:
        return None
    height = min(max(end for end, side, _ in records if side is inputs)
                 for inputs in (data.left, data.right)
                 if any(side is inputs for _, side, _ in records))
    inputs = data.left
    cache = {}

    def checked(area):
        if area not in cache:
            spacing = bar.area_cm2 / area
            cache[area] = [(end, side, demand, section_check(
                demand, side, side.reinforcement.stem_cover_cm, bar, spacing))
                for end, side, demand in records]
        return cache[area]

    def remaining(y, area):
        rows = [row for row in checked(area) if row[0] > y + 1e-9]
        # At the upper limit retain terminal-element checks: no empty envelope.
        return rows or [row for row in checked(area) if abs(row[0] - height) < 1e-8]

    def satisfies(y, area, diameter):
        return area + 1e-9 >= steel.temperature_cm2_m and all(
            max(row[3][key] for key in ("flexure_ratio", "shear_ratio", "crack_ratio")) <= 1 + 1e-8
            for row in remaining(y, area))

    grid = SpacingGrid(inputs.reinforcement.spacing_step_m,
                       inputs.reinforcement.minimum_spacing_m,
                       min(0.30, inputs.reinforcement.maximum_spacing_m))
    maximum_spacing = grid.maximum_m
    if is_connected_2(data):
        target = CONNECTED_2_CONTINUOUS_STEM_SPACING_M
        every = round(target / steel.spacing_m)
        if (target > grid.maximum_m + 1e-9 or every < 2
                or not isclose(every * steel.spacing_m, target, abs_tol=1e-9)
                or bar.area_cm2 / target + 1e-9 < steel.temperature_cm2_m):
            return None
        maximum_spacing = target

    def governing(y, area):
        rows = [row for row in remaining(y, area) if row[2].limit_state != "service"]
        return max(rows, key=lambda row: row[3]["flexure_ratio"])

    def design_at_height(y, diameter, area):
        _, side, demand, values = governing(y, area)
        areas = area_requirements((demand,), side, side.reinforcement.stem_cover_cm, bar)[0]
        minimum = max(steel.temperature_cm2_m, areas["minimum_area"])
        return (abs(demand.moment), values["effective"], areas["flexural_area"], minimum,
                max(minimum, areas["flexural_area"]), values["required_moment"])

    cut = _single_stem_reinforcement_cut(
        inputs, steel.bar_label, steel.spacing_m, steel.area_per_face_cm2_m,
        steel.temperature_cm2_m, steel.required_straight_anchor_cm / 100.0,
        height, satisfies, design_at_height, maximum_spacing_m=maximum_spacing,
        resistance_at_height=lambda y, area, diameter: governing(y, area)[3]["capacity"],
    )
    if cut is None:
        return None
    if is_connected_2(data) and not isclose(cut.upper_spacing_m, maximum_spacing, abs_tol=1e-9):
        return None
    _, _, demand, _ = governing(cut.theoretical_cut_height_m, cut.upper_provided_as_cm2_m)
    source_region = mesh.frame.elements[demand.element].region
    return replace(cut, thickness_at_cut_cm=demand.depth_cm,
        notes=cut.notes + " Envolvente FRAME de ambos lados por cara: flexion, cortante, servicio y minimos. "
        f"Comprobacion de flexion del tramo superior: {source_region}; {demand.case}; "
        f"elemento {demand.element}; s/L={demand.station:.3f}, con espesor minimo del elemento. "
        "Corte conservador por elementos completos; longitudes hasta el inicio de transicion de cajuela. "
        "La opcion no sustituye el armado uniforme seleccionado ni el detalle de union con la cajuela.")
