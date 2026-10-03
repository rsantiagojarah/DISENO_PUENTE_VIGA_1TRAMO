"""Shared numeric checks for connected design and its calculation trace."""

from dataclasses import asdict
from functools import lru_cache

from bridge_design.domain.abutment import (
    _concrete_shear_resistance_tn, _cracking_moment_tn_m, _effective_shear_depth_cm,
    _general_shear_beta, _service_steel_stress_kg_cm2,
)
from bridge_design.domain.concrete_flexure import rectangular_flexural_response
from bridge_design.domain.crack_control import maximum_crack_control_spacing_m


@lru_cache(maxsize=4096)
def flexural_response(area, effective, concrete, yield_strength):
    return rectangular_flexural_response(area, 100.0, effective, concrete, yield_strength)


def section_check(demand, inputs, cover, bar, spacing):
    area = bar.area_cm2 / spacing
    axis = cover + bar.diameter_cm / 2
    depth = demand.depth_cm
    effective = depth - axis
    values = {"demand": asdict(demand), "area": area, "axis": axis, "effective": effective,
              "cover": cover, "diameter": bar.diameter_cm, "spacing": spacing,
              "flexure_ratio": 0.0, "shear_ratio": 0.0, "crack_ratio": 0.0}
    if depth <= 2 * axis:
        values.update(flexure_ratio=float("inf"), shear_ratio=float("inf"), crack_ratio=float("inf"))
        return values
    if demand.limit_state == "service":
        stress = _service_steel_stress_kg_cm2(abs(demand.moment), area, effective)
        maximum_spacing, beta = maximum_crack_control_spacing_m(max(stress, 1e-9), axis, depth)
        limit = 0.60 * inputs.materials.steel_yield_kg_cm2
        values.update(stress=stress, stress_limit=limit, maximum_spacing=maximum_spacing, beta_service=beta,
                      stress_ratio=stress / limit, spacing_ratio=spacing / max(maximum_spacing, 1e-12),
                      crack_ratio=max(stress / limit, spacing / max(maximum_spacing, 1e-12)))
        return values
    response = flexural_response(area, effective, inputs.materials.concrete_strength_kg_cm2,
                                 inputs.materials.steel_yield_kg_cm2)
    phi = min(inputs.reinforcement.flexural_phi, response.resistance_factor)
    capacity = phi * response.nominal_moment_tn_m
    cracking = _cracking_moment_tn_m(depth, inputs)
    multiplier = inputs.reinforcement.minimum_flexural_capacity_multiplier
    required = max(abs(demand.moment), min(cracking, multiplier * abs(demand.moment)))
    shear_depth = _effective_shear_depth_cm(effective, depth)
    beta, strain, spacing_x, spacing_xe, moment_used = _general_shear_beta(
        abs(demand.moment), abs(demand.shear), area, shear_depth)
    shear_capacity = _concrete_shear_resistance_tn(shear_depth, inputs, inputs.reinforcement.shear_phi, beta)
    values.update(response=asdict(response), phi=phi, capacity=capacity, cracking=cracking,
                  multiplier=multiplier, required_moment=required, shear_depth=shear_depth,
                  beta=beta, shear_strain=strain, spacing_x_in=spacing_x, spacing_xe_in=spacing_xe,
                  shear_moment_used=moment_used, shear_capacity=shear_capacity,
                  flexure_ratio=required / max(capacity, 1e-10),
                  shear_ratio=abs(demand.shear) / shear_capacity)
    return values
