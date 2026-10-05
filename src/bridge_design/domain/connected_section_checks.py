"""Shared numeric checks for connected design and its calculation trace."""

from dataclasses import asdict
from functools import lru_cache

from bridge_design.domain.abutment import (
    _concrete_shear_resistance_tn, _cracking_moment_tn_m,
    _shear_beta_detail, _service_steel_stress_kg_cm2,
)
from bridge_design.domain.concrete_flexure import rectangular_flexural_response
from bridge_design.domain.crack_control import maximum_crack_control_spacing_m
from bridge_design.domain.reinforcement import mtc_minimum_flexural_moment_tn_m


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
        if abs(demand.moment) <= 1e-10:
            # No flexural tension: the crack-spacing equation has no finite limit.
            # Keep a finite general detailing limit for exports; it is not s_crack.
            values.update(service_tension=False, stress=0.0,
                          stress_limit=0.60 * inputs.materials.steel_yield_kg_cm2,
                          stress_used=0.0, maximum_spacing=min(0.30, inputs.reinforcement.maximum_spacing_m),
                          beta_service=1 + axis / (0.7 * (depth - axis)),
                          stress_ratio=0.0, spacing_ratio=0.0, crack_ratio=0.0)
            return values
        stress = _service_steel_stress_kg_cm2(abs(demand.moment), area, effective)
        limit = 0.60 * inputs.materials.steel_yield_kg_cm2
        stress_used = min(stress, limit)
        maximum_spacing, beta = maximum_crack_control_spacing_m(max(stress_used, 1e-9), axis, depth)
        values.update(service_tension=True, stress=stress, stress_limit=limit, stress_used=stress_used, maximum_spacing=maximum_spacing, beta_service=beta,
                      stress_ratio=stress / limit, spacing_ratio=spacing / max(maximum_spacing, 1e-12),
                      crack_ratio=max(stress / limit, spacing / max(maximum_spacing, 1e-12)))
        return values
    response = flexural_response(area, effective, inputs.materials.concrete_strength_kg_cm2,
                                 inputs.materials.steel_yield_kg_cm2)
    phi = min(demand.flexural_phi_limit if demand.flexural_phi_limit is not None
              else inputs.reinforcement.flexural_phi, response.resistance_factor)
    capacity = phi * response.nominal_moment_tn_m
    cracking = _cracking_moment_tn_m(depth, inputs)
    multiplier = inputs.reinforcement.minimum_flexural_capacity_multiplier
    required = mtc_minimum_flexural_moment_tn_m(abs(demand.moment), cracking, multiplier)
    # Share the individual-abutment method selection, including its fallback
    # until the actual zero-shear location establishes simplified eligibility.
    shear_detail = _shear_beta_detail(
        abs(demand.moment), abs(demand.shear), area, effective, depth,
        demand.shear_method, inputs=inputs, axial_tn_m=demand.axial)
    shear_depth = shear_detail["dv_cm"]
    beta = shear_detail["beta"]
    shear_capacity = _concrete_shear_resistance_tn(shear_depth, inputs, inputs.reinforcement.shear_phi, beta)
    values.update(response=asdict(response), phi=phi, capacity=capacity, cracking=cracking,
                  shear_method=shear_detail["method"],
                  multiplier=multiplier, required_moment=required, shear_depth=shear_depth,
                  beta=beta, shear_strain=shear_detail["epsilon_s"],
                  spacing_x_in=shear_detail["s_x_in"], spacing_xe_in=shear_detail["s_xe_in"],
                  shear_moment_used=shear_detail["mu_used_tn_m_m"], shear_capacity=shear_capacity,
                  flexure_ratio=required / max(capacity, 1e-10),
                  shear_ratio=abs(demand.shear) / shear_capacity)
    return values
