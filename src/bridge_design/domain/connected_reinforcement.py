"""Design continuous strips for flexure and shear using individual-abutment checks."""

from dataclasses import dataclass, replace
from math import isfinite
from bridge_design.domain.anchorage_status import anchorage_status
from bridge_design.codes.mtc_2018 import mtc_tension_development_length_cm
from bridge_design.domain.abutment import (
    AbutmentStemReinforcementCut, _single_stem_reinforcement_cut,
    _hooked_development_length_cm, _temperature_mtc_bounded, _stem_temperature_result, _footing_temperature_result,
)
from bridge_design.domain.connected_geometry import foundation_section, stem_centroid
from bridge_design.domain.abutment import _stem_thickness_at_height_m
from bridge_design.domain.connected_section_checks import section_check
from bridge_design.domain.connected_steel_audit import area_requirements
from bridge_design.domain.rebar_catalog import REINFORCING_BAR_CATALOG, SpacingGrid, reinforcing_bar_by_label


DESIGN_SCOPE_NOTE = (
    "Diseno simplificado por flexion y cortante; sin verificacion de interaccion axial-momento. "
    "N se incluye en beta de cortante; no se verifica interaccion N-M ni su efecto en fisuracion. "
    "OK se limita a las comprobaciones realizadas y no certifica la capacidad frente a carga axial."
)


@dataclass(frozen=True)
class ConnectedBarChoice:
    bar_label: str
    spacing_m: float
    is_custom: bool = False


@dataclass(frozen=True)
class ConnectedSteelChoice:
    principal: ConnectedBarChoice
    transverse: ConnectedBarChoice


@dataclass(frozen=True)
class SectionDemand:
    case: str
    limit_state: str
    depth_cm: float
    axial: float
    shear: float
    moment: float
    element: int
    station: float
    shear_method: str = "general"
    flexural_phi_limit: float | None = None
    # Compatibility with saved demands; ignored by the corrected MTC check.
    capacity_multiplier: float = 1.0


@dataclass(frozen=True)
class ConnectedSteel:
    region: str
    bar_label: str
    spacing_m: float
    area_per_face_cm2_m: float
    temperature_cm2_m: float
    transverse_bar_label: str
    transverse_spacing_m: float
    flexural_utilization: float
    shear_utilization: float
    crack_utilization: float
    governing_case: str
    governing_axial: float
    governing_shear: float
    governing_moment: float
    governing_depth_cm: float
    governing_element: int
    governing_station: float
    required_straight_anchor_cm: float
    required_hook_anchor_cm: float
    hook_extension_cm: float
    available_anchor_cm: float | None
    anchor_status: str
    status: str
    minimum_utilization: float = 0.0
    transverse_utilization: float = 0.0
    flexural_as_cm2_m: float = 0.0
    capacity_minimum_as_cm2_m: float = 0.0
    required_as_cm2_m: float = 0.0
    anchor_source: str = "Longitud ingresada"
    anchor_geometry_note: str = ""
    base_region: str = ""
    face: str = "Ambas caras"
    direction: str = "Longitudinal"
    role: str = "primary"
    part: str = ""
    stem_reinforcement_cut: AbutmentStemReinforcementCut | None = None


def region_inputs(data, region):
    from bridge_design.domain.connected_distributions import base_region
    region = base_region(region)
    if region in ("Losa central", "Transicion izquierda", "Transicion derecha"):
        from dataclasses import replace
        return replace(data.left, materials=data.slab_materials), data.slab_cover_cm, data.connector_length_m
    side = data.right if region.endswith("derecha") else data.left
    footing = region.startswith("Zapata")
    return side, (side.reinforcement.footing_cover_cm if footing else side.reinforcement.stem_cover_cm), (
        side.geometry.footing_width_m if footing else side.geometry.seat_block_height_m
        if region.startswith("Parapeto") else side.geometry.stem_height_above_footing_m)


def section_demands(data, mesh, results):
    grouped = {}
    for result in results:
        for row in result.sections:
            element = mesh.frame.elements[row.element]
            first, last = mesh.frame.nodes[element.start], mesh.frame.nodes[element.end]
            fraction = min(max(row.station, 1e-8), 1 - 1e-8)
            if first.y == last.y:
                position = first.x + fraction * (last.x - first.x)
                depth = foundation_section(data, position)[0]
                real_offset = -depth / 2
            else:
                side_index = 0 if element.region.endswith("izquierda") else 1
                side = (data.left, data.right)[side_index]
                height = first.y + fraction * (last.y - first.y)
                depth = _stem_thickness_at_height_m(side, height)
                real_offset = first.x - stem_centroid(data, side_index, height)
            moment = row.moment
            if data.section_offsets:
                moment += (real_offset - element.offset) * row.axial
            grouped.setdefault(element.region, []).append(SectionDemand(
                result.name, result.limit_state, round(100 * depth, 5), row.axial, row.shear, moment,
                row.element, row.station))
    return grouped


def evaluate_option(demands, inputs, cover, bar, spacing, full=False):
    flexural_ratio = shear_ratio = crack_ratio = 0.0
    governing = demands[0]
    for demand in demands:
        values = section_check(demand, inputs, cover, bar, spacing)
        if not isfinite(values["flexure_ratio"]):
            return float("inf"), float("inf"), float("inf"), demand
        if demand.limit_state != "service" and values["flexure_ratio"] >= flexural_ratio:
            flexural_ratio, governing = values["flexure_ratio"], demand
        shear_ratio = max(shear_ratio, values["shear_ratio"])
        crack_ratio = max(crack_ratio, values["crack_ratio"])
        if not full and max(flexural_ratio, shear_ratio, crack_ratio) > 1 + 1e-8:
            return flexural_ratio, shear_ratio, crack_ratio, governing
    return flexural_ratio, shear_ratio, crack_ratio, governing


def region_setup(data, region, demands):
    inputs, cover, panel_length = region_inputs(data, region)
    reinforcement = inputs.reinforcement
    grid = SpacingGrid(reinforcement.spacing_step_m, reinforcement.minimum_spacing_m,
                       min(0.30, reinforcement.maximum_spacing_m))
    temperature = temperature_for_region(region, demands, inputs, grid, panel_length).required_as_cm2_m
    count = int((grid.maximum_m - grid.minimum_m) / grid.step_m + 1e-6)
    spacings = [grid.maximum_m - index * grid.step_m for index in range(count + 1)]
    spacings.append(grid.minimum_m)
    candidates = sorted(((bar.area_cm2 / spacing, bar, spacing) for bar in REINFORCING_BAR_CATALOG
                         if bar.diameter_cm >= 1.27 for spacing in sorted(set(spacings))
                         if bar.area_cm2 / spacing >= temperature), key=lambda row: (row[0], row[1].diameter_cm))
    if not candidates:
        raise ValueError(f"No existen opciones de acero compatibles con la malla de separaciones: {region}.")
    return inputs, cover, grid, temperature, candidates


def temperature_for_region(region, demands, inputs, grid, panel_length):
    if region.startswith("Pantalla"):
        return _stem_temperature_result(inputs)
    if region.startswith("Zapata"):
        return _footing_temperature_result(inputs)
    return max((_temperature_mtc_bounded(d.depth_cm, panel_length*100,
               inputs.materials.steel_yield_kg_cm2, grid) for d in demands),
               key=lambda t: (t.required_as_cm2_m, t.raw_as_cm2_m))


def validate_choice(choice, grid, cover, demands, *, principal=True):
    bar = reinforcing_bar_by_label(choice.bar_label)
    spacing = choice.spacing_m
    if isinstance(spacing, bool) or not isinstance(spacing, (int, float)) or not isfinite(spacing):
        raise ValueError("La separacion debe ser numerica y finita.")
    if not grid.minimum_m - 1e-9 <= spacing <= grid.maximum_m + 1e-9:
        raise ValueError(f"La separacion debe estar entre {grid.minimum_m:g} y {grid.maximum_m:g} m.")
    if principal and bar.diameter_cm < 1.27:
        raise ValueError('La armadura principal de este modelo utiliza barras desde 1/2".')
    if min(demand.depth_cm for demand in demands) <= 2 * (cover + bar.diameter_cm / 2):
        raise ValueError("El espesor no admite la barra con los recubrimientos ingresados.")
    return bar.area_cm2 / spacing, bar, spacing


def region_has_reinforcement_design(region):
    return not region.startswith(("Transicion", "Cajuela"))


def design_region(data, mesh, region, demands, selection=None, *, distribution=None):
    if not region_has_reinforcement_design(region):
        raise ValueError(f"Region excluida del diseno de acero: {region}.")
    inputs, cover, grid, temperature, candidates = region_setup(data, region, demands)
    reinforcement = inputs.reinforcement
    selected = candidates[-1]
    if distribution is not None and selection is None:
        # Recommendations check required area only; final shear/service/anchor
        # checks consume the distribution selected by the user.
        from bridge_design.domain.connected_options import area_options
        options = area_options(data, region, demands)
        compliant = [o for o in options if o.is_compliant]
        option = min(compliant, key=lambda o: (o.area_per_face_cm2_m/o.required_as_cm2_m-1,
                     reinforcing_bar_by_label(o.bar_label).diameter_cm)) if compliant else options[-1]
        selected = (option.area_per_face_cm2_m, reinforcing_bar_by_label(option.bar_label), option.spacing_m)
    elif selection is None:
        for candidate in candidates:
            _area, bar, spacing = candidate
            ratios = evaluate_option(demands, inputs, cover, bar, spacing)
            if max(ratios[:3]) <= 1 + 1e-8:
                selected = candidate
                break
    else:
        selected = validate_choice(selection.principal, grid, cover, demands, principal=distribution is None)
    area, bar, spacing = selected
    flexure, shear, crack, governing = evaluate_option(demands, inputs, cover, bar, spacing, True)
    transverse = min(candidates, key=lambda row: (row[0], row[1].diameter_cm))
    if selection is not None:
        transverse = validate_choice(selection.transverse, grid, cover, demands, principal=False)
    if distribution is not None:
        transverse = selected  # One independently selected distribution per record.
    straight, _basic = mtc_tension_development_length_cm(
        bar.diameter_cm, inputs.materials.steel_yield_kg_cm2, inputs.materials.concrete_strength_kg_cm2,
        location_factor=reinforcement.development_location_factor,
        coating_factor=reinforcement.development_coating_factor,
        lightweight_factor=reinforcement.development_lightweight_factor,
        confinement_factor=reinforcement.development_confinement_factor,
        excess_reinforcement_factor=1.0)
    hooked, extension = _hooked_development_length_cm(bar.diameter_cm, inputs.materials.concrete_strength_kg_cm2,
                                                    inputs.materials.steel_yield_kg_cm2, 1.0)
    from bridge_design.domain.connected_distributions import base_region
    available_m = data.anchor_lengths_m.get(region, data.anchor_lengths_m.get(base_region(region)))
    legacy_anchor = False
    if available_m is None and base_region(region) in ("Pantalla", "Zapata", "Parapeto"):
        # Existing YAML overrides still apply, conservatively, to the shared
        # design. A common override takes precedence over the legacy labels.
        suffix = region[len(base_region(region)):]
        lengths = [data.anchor_lengths_m.get(base_region(region)+" "+side+suffix,
                   data.anchor_lengths_m.get(base_region(region)+" "+side))
                   for side in ("izquierda", "derecha")]
        if any(length is not None for length in lengths):
            legacy_anchor = True
            from bridge_design.domain.connected_anchorage import geometric_anchorage
            for index, side in enumerate(("izquierda", "derecha")):
                if lengths[index] is not None or mesh is None:
                    continue
                physical_demands = tuple(d for d in demands if
                    mesh.frame.elements[d.element].region.endswith(side))
                side_inputs = data.left if index == 0 else data.right
                available, _ = geometric_anchorage(data, mesh, base_region(region)+" "+side,
                    physical_demands, side_inputs, cover, bar, spacing,
                    part=distribution.part if distribution else "")
                lengths[index] = available/100 if available is not None else None
            if all(length is not None for length in lengths):
                available_m = min(lengths)
    if available_m is None:
        from bridge_design.domain.connected_anchorage import geometric_anchorage
        from bridge_design.domain.connected_distributions import base_region
        if mesh is None:
            available_cm, anchor_note = None, "Sin geometria FRAME para inferir la longitud de anclaje."
        else:
            available_cm, anchor_note = geometric_anchorage(data, mesh, base_region(region), demands,
                inputs, cover, bar, spacing, part=distribution.part if distribution else "")
        anchor_source = "Detalle continuo definido para estribos conectados"
    else:
        available_cm, anchor_note = available_m*100, "Longitud util proporcionada por el usuario."
        anchor_source = "Longitud ingresada"
        if legacy_anchor:
            anchor_source = "Longitudes por lado y geometria"
            anchor_note = "Menor longitud disponible entre los dos estribos; el lado sin longitud ingresada utiliza la geometria."
    anchor = anchorage_status(available_cm, straight, hooked)
    minimum = temperature / area
    transverse_ratio = temperature / transverse[0]
    status = "OK" if max(flexure, shear, crack, minimum, transverse_ratio) <= 1 + 1e-8 else "NO CUMPLE"
    requirements = area_requirements(demands, inputs, cover, bar)
    flexural_area = max((row["flexural_area"] for row in requirements), default=0.0)
    minimum_area = max((row["minimum_area"] for row in requirements), default=0.0)
    steel = ConnectedSteel(region, bar.label, spacing, area, temperature, transverse[1].label, transverse[2],
                          flexure, shear, crack, governing.case, governing.axial, governing.shear,
                          governing.moment, governing.depth_cm, governing.element, governing.station,
                          straight, hooked, extension, available_cm,
                          anchor, status, minimum, transverse_ratio, flexural_area, minimum_area,
                          max(flexural_area, minimum_area, temperature), anchor_source, anchor_note)
    if distribution is not None:
        from dataclasses import replace
        steel = replace(steel, base_region=distribution.region, face=distribution.face,
                        direction=distribution.direction, role=distribution.role, part=distribution.part)
        if distribution.role == "temperature":
            steel = replace(steel, flexural_utilization=0.0, shear_utilization=0.0, crack_utilization=0.0,
                required_straight_anchor_cm=0.0, required_hook_anchor_cm=0.0, hook_extension_cm=0.0,
                available_anchor_cm=None, anchor_status="NO APLICA",
                anchor_source="Acero minimo de temperatura/distribucion", anchor_geometry_note="")
    if mesh is not None and steel.region == "Pantalla - vertical relleno" and steel.role == "primary":
        steel = replace(steel, stem_reinforcement_cut=connected_stem_reinforcement_cut(data, mesh, steel, demands))
    return steel


def design_connected_reinforcement(data, mesh, results, selections=None):
    grouped = section_demands(data, mesh, results)
    selections = selections or {}
    from bridge_design.domain.connected_distributions import distribution_demands
    distributions = distribution_demands(data, mesh, grouped)
    designed_regions = {item.label for item in distributions}
    unknown = set(selections) - designed_regions
    if unknown:
        raise ValueError(f"Regiones de acero no reconocidas: {', '.join(sorted(unknown))}.")
    return tuple(design_region(data, mesh, item.label, item.demands, selections.get(item.label), distribution=item)
                 for item in distributions)


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
        height, satisfies, design_at_height, maximum_spacing_m=grid.maximum_m,
        resistance_at_height=lambda y, area, diameter: governing(y, area)[3]["capacity"],
    )
    if cut is None:
        return None
    _, _, demand, _ = governing(cut.theoretical_cut_height_m, cut.upper_provided_as_cm2_m)
    source_region = mesh.frame.elements[demand.element].region
    return replace(cut, thickness_at_cut_cm=demand.depth_cm,
        notes=cut.notes + " Envolvente FRAME de ambos lados por cara: flexion, cortante, servicio y minimos. "
        f"Comprobacion de flexion del tramo superior: {source_region}; {demand.case}; "
        f"elemento {demand.element}; s/L={demand.station:.3f}, con espesor minimo del elemento. "
        "Corte conservador por elementos completos; longitudes hasta el inicio de transicion de cajuela. "
        "La opcion no sustituye el armado uniforme seleccionado ni el detalle de union con la cajuela.")
