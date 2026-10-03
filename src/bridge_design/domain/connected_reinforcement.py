"""Design continuous strips for flexure and shear using individual-abutment checks."""

from dataclasses import dataclass
from math import isfinite
from bridge_design.codes.mtc_2018 import mtc_tension_development_length_cm
from bridge_design.domain.abutment import (
    _hooked_development_length_cm, _temperature_mtc_bounded,
)
from bridge_design.domain.connected_geometry import foundation_section, stem_centroid
from bridge_design.domain.abutment import _stem_thickness_at_height_m
from bridge_design.domain.connected_section_checks import section_check
from bridge_design.domain.connected_steel_audit import area_requirements
from bridge_design.domain.rebar_catalog import REINFORCING_BAR_CATALOG, SpacingGrid, reinforcing_bar_by_label


DESIGN_SCOPE_NOTE = (
    "Diseno simplificado por flexion y cortante; sin verificacion de interaccion axial-momento. "
    "N se conserva como resultado del FRAME, pero se omite su efecto directo en resistencia y fisuracion. "
    "OK se limita a las comprobaciones realizadas y no certifica la capacidad frente a carga axial."
)


@dataclass(frozen=True)
class ConnectedBarChoice:
    bar_label: str
    spacing_m: float


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


def region_inputs(data, region):
    if region in ("Losa central", "Transicion izquierda", "Transicion derecha"):
        from dataclasses import replace
        return replace(data.left, materials=data.slab_materials), data.slab_cover_cm, data.connector_length_m
    side = data.left if region.endswith("izquierda") else data.right
    footing = region.startswith("Zapata")
    return side, (side.reinforcement.footing_cover_cm if footing else side.reinforcement.stem_cover_cm), (
        side.geometry.footing_width_m if footing else side.geometry.stem_height_above_footing_m)


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
    temperature = max(_temperature_mtc_bounded(demand.depth_cm, panel_length * 100,
                      inputs.materials.steel_yield_kg_cm2, grid).required_as_cm2_m for demand in demands)
    count = int((grid.maximum_m - grid.minimum_m) / grid.step_m + 1e-6)
    spacings = [grid.maximum_m - index * grid.step_m for index in range(count + 1)]
    spacings.append(grid.minimum_m)
    candidates = sorted(((bar.area_cm2 / spacing, bar, spacing) for bar in REINFORCING_BAR_CATALOG
                         if bar.diameter_cm >= 1.27 for spacing in sorted(set(spacings))
                         if bar.area_cm2 / spacing >= temperature), key=lambda row: (row[0], row[1].diameter_cm))
    if not candidates:
        raise ValueError(f"No existen opciones de acero compatibles con la malla de separaciones: {region}.")
    return inputs, cover, grid, temperature, candidates


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


def design_region(data, mesh, region, demands, selection=None):
    inputs, cover, grid, temperature, candidates = region_setup(data, region, demands)
    reinforcement = inputs.reinforcement
    selected = candidates[-1]
    if selection is None:
        for candidate in candidates:
            _area, bar, spacing = candidate
            ratios = evaluate_option(demands, inputs, cover, bar, spacing)
            if max(ratios[:3]) <= 1 + 1e-8:
                selected = candidate
                break
    else:
        selected = validate_choice(selection.principal, grid, cover, demands)
    area, bar, spacing = selected
    flexure, shear, crack, governing = evaluate_option(demands, inputs, cover, bar, spacing, True)
    transverse = min(candidates, key=lambda row: (row[0], row[1].diameter_cm))
    if selection is not None:
        transverse = validate_choice(selection.transverse, grid, cover, demands, principal=False)
    straight, _basic = mtc_tension_development_length_cm(
        bar.diameter_cm, inputs.materials.steel_yield_kg_cm2, inputs.materials.concrete_strength_kg_cm2,
        location_factor=reinforcement.development_location_factor,
        coating_factor=reinforcement.development_coating_factor,
        lightweight_factor=reinforcement.development_lightweight_factor,
        confinement_factor=reinforcement.development_confinement_factor,
        excess_reinforcement_factor=1.0)
    hooked, extension = _hooked_development_length_cm(bar.diameter_cm, inputs.materials.concrete_strength_kg_cm2,
                                                    inputs.materials.steel_yield_kg_cm2, 1.0)
    available = data.anchor_lengths_m.get(region)
    anchor = "PENDIENTE DETALLE" if available is None else "OK RECTO" if available * 100 >= straight else "NO"
    minimum = temperature / area
    transverse_ratio = temperature / transverse[0]
    status = "OK" if max(flexure, shear, crack, minimum, transverse_ratio) <= 1 + 1e-8 else "NO CUMPLE"
    requirements = area_requirements(demands, inputs, cover, bar)
    flexural_area = max((row["flexural_area"] for row in requirements), default=0.0)
    minimum_area = max((row["minimum_area"] for row in requirements), default=0.0)
    return ConnectedSteel(region, bar.label, spacing, area, temperature, transverse[1].label, transverse[2],
                          flexure, shear, crack, governing.case, governing.axial, governing.shear,
                          governing.moment, governing.depth_cm, governing.element, governing.station,
                          straight, hooked, extension, None if available is None else available * 100,
                          anchor, status, minimum, transverse_ratio, flexural_area, minimum_area,
                          max(flexural_area, minimum_area, temperature))


def design_connected_reinforcement(data, mesh, results, selections=None):
    grouped = section_demands(data, mesh, results)
    selections = selections or {}
    unknown = set(selections) - set(grouped)
    if unknown:
        raise ValueError(f"Regiones de acero no reconocidas: {', '.join(sorted(unknown))}.")
    return tuple(design_region(data, mesh, region, demands, selections.get(region))
                 for region, demands in grouped.items())
