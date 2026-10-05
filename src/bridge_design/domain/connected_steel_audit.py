"""Trace selected steel with independent governing sections for each check."""

from dataclasses import asdict
from functools import lru_cache

from bridge_design.codes.mtc_2018 import mtc_tension_development_length_cm
from bridge_design.domain.abutment import _cracking_moment_tn_m, _temperature_mtc_bounded
from bridge_design.domain.concrete_flexure import required_rectangular_steel_area_cm2
from bridge_design.domain.connected_section_checks import section_check
from bridge_design.domain.rebar_catalog import reinforcing_bar_by_label


@lru_cache(maxsize=8192)
def required_area(moment, effective, concrete, yield_strength, phi):
    try:
        return required_rectangular_steel_area_cm2(moment, 100.0, effective, concrete, yield_strength, phi)
    except ValueError:
        return float("inf")


def area_requirements(demands, inputs, cover, bar):
    candidates = {}
    for demand in demands:
        if demand.limit_state == "service":
            continue
        key = (demand.depth_cm, demand.limit_state, demand.flexural_phi_limit)
        if key not in candidates or abs(demand.moment) > abs(candidates[key].moment):
            candidates[key] = demand
    rows = []
    for demand in candidates.values():
        effective = demand.depth_cm - cover - bar.diameter_cm / 2
        minimum_moment = min(_cracking_moment_tn_m(demand.depth_cm, inputs),
                             inputs.reinforcement.minimum_flexural_capacity_multiplier * abs(demand.moment))
        arguments = (effective, inputs.materials.concrete_strength_kg_cm2,
                     inputs.materials.steel_yield_kg_cm2, demand.flexural_phi_limit if demand.flexural_phi_limit is not None
                     else inputs.reinforcement.flexural_phi)
        rows.append({"demand": asdict(demand), "effective": effective,
                     "flexural_area": required_area(abs(demand.moment), *arguments),
                     "minimum_area": required_area(minimum_moment, *arguments)})
    return rows


def region_audit(result, steel, demands):
    from bridge_design.domain.connected_reinforcement import region_setup
    from bridge_design.domain.connected_distributions import base_region

    inputs, cover, grid, _temperature, _candidates = region_setup(result.inputs, steel.region, demands)
    bar = reinforcing_bar_by_label(steel.bar_label)
    checks = [section_check(demand, inputs, cover, bar, steel.spacing_m) for demand in demands]
    strength = [row for row in checks if row["demand"]["limit_state"] != "service"]
    service = [row for row in checks if row["demand"]["limit_state"] == "service"]
    flexure = max(strength, key=lambda row: row["flexure_ratio"])
    shear = max(strength, key=lambda row: row["shear_ratio"])
    crack = max(service, key=lambda row: row["crack_ratio"]) if service else None
    areas = area_requirements(demands, inputs, cover, bar)
    for row in (flexure, shear, crack, *areas):
        if row is None:
            continue
        demand = row["demand"]
        element = result.mesh.frame.elements[demand["element"]]
        start, end = (result.mesh.frame.nodes[index] for index in (element.start, element.end))
        row["x"] = start.x + demand["station"] * (end.x - start.x)
        row["y"] = start.y + demand["station"] * (end.y - start.y)
        row["region"] = element.region
        row["section_location"] = "Interior / extremo de elemento"
        if element.region.startswith("Transicion"):
            row["section_location"] = "Transicion de espesor"
        elif steel.part:
            from bridge_design.domain.connected_geometry import local_x
            side_index = 0 if element.region.endswith("izquierda") else 1
            geometry = (result.inputs.left, result.inputs.right)[side_index].geometry
            face_x = geometry.toe_length_m + (geometry.lower_stem_thickness_m
                                               if steel.part == "talon" else 0)
            if abs(local_x(result.inputs, side_index, row["x"]) - face_x) < 1e-7:
                row["section_location"] = "Cara de pantalla, lado " + steel.part
        row["side"] = ("Izquierdo" if element.region.endswith("izquierda") else
                       "Derecho" if element.region.endswith("derecha") else "Losa central")
        positive = demand["moment"] >= 0
        row["face"] = (("Inferior" if positive else "Superior") if start.y == end.y else
                       "Hacia cauce" if positive == element.region.endswith("izquierda") else "Hacia relleno")
        if steel.base_region:
            row["face"] = steel.face
    from bridge_design.domain.connected_reinforcement import region_inputs, temperature_for_region
    panel_length = region_inputs(result.inputs, steel.region)[2]
    temperature = temperature_for_region(steel.region, demands, inputs, grid, panel_length)
    reinforcement = inputs.reinforcement
    factors = (reinforcement.development_location_factor, reinforcement.development_coating_factor,
               reinforcement.development_lightweight_factor, reinforcement.development_confinement_factor)
    _straight, basic = mtc_tension_development_length_cm(bar.diameter_cm,
        inputs.materials.steel_yield_kg_cm2, inputs.materials.concrete_strength_kg_cm2, *factors)
    return {"flexure": flexure, "shear": shear, "service": crack, "areas": areas,
            "available_anchor_cm": steel.available_anchor_cm, "anchor_source": steel.anchor_source,
            "anchor_geometry_note": steel.anchor_geometry_note,
            "temperature": asdict(temperature), "basic_anchor_cm": basic, "anchor_factors": factors,
            "concrete": inputs.materials.concrete_strength_kg_cm2,
            "yield_strength": inputs.materials.steel_yield_kg_cm2,
            "shear_phi": reinforcement.shear_phi, "bar_area": bar.area_cm2,
            "transverse_area": reinforcing_bar_by_label(steel.transverse_bar_label).area_cm2
                               / steel.transverse_spacing_m}
