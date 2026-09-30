"""Real inclined stem free body, separate from wall/heel-soil stability.

Coulomb and Mononobe-Okabe: FHWA NHI-10-024 Eq. 7-6.
MTC 2018 Art. 2.8.1.1.14.1: envelope PAE+0.5PIR / max(0.5PAE,EH)+PIR.
MTC 2018 Art. 2.4.4.1.5.3 and Appendix A.11.3.1 include wall friction.
Downward vertical pressure is compression; force and geometry angles differ.
Its eccentric moment is included, without crediting axial compression in capacity.
"""

from math import cos, radians, sin, tan
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bridge_design.domain.abutment import AbutmentInputs, SoilPressureResult


def stem_actions(inputs: "AbutmentInputs", pressures: "SoilPressureResult", cut_m: float = 0.0) -> dict[str, float]:
    """Integrate loads above a horizontal cut; moments about its section centre.

    Positive moment bends the stem toward the toe. Vertical load is positive down.
    For each earth force, M = Px*y - Py*(x_face - x_section). All lengths are m.
    """
    g = inputs.geometry
    height = g.stem_height_above_footing_m
    cut = min(max(cut_m, 0.0), height)
    h = height - cut
    taper = (g.lower_stem_thickness_m - g.upper_stem_thickness_m) / height
    thickness = g.lower_stem_thickness_m - taper * cut
    angle = radians(pressures.stem_force_angle_deg)
    slope = tan(radians(90.0 - inputs.soil.wall_backface_angle_deg))
    gamma_s = inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    gamma_c = inputs.materials.concrete_unit_weight_kg_m3 / 1000.0
    q = gamma_s * pressures.live_surcharge_height_m + inputs.soil.pedestrian_surcharge_tn_m2
    ka, kae = pressures.stem_ka, pressures.stem_k_ae
    ls = ka * q * h
    eh = 0.5 * ka * gamma_s * h * h
    pae = 0.5 * kae * gamma_s * h * h
    eq = pae - eh

    def moment(force: float, y: float) -> float:
        return force * (cos(angle) * y - sin(angle) * (thickness / 2.0 - slope * y))

    # Exact first moment of the linearly tapered concrete above the cut.
    area = (thickness + g.upper_stem_thickness_m) * h / 2.0
    first_y = thickness * h * h / 2.0 - taper * h**3 / 3.0
    weight = gamma_c * area
    # Do not credit a favourable self-weight moment in the stem design.
    weight_moment = max(-gamma_c * (taper / 2.0 - slope) * first_y, 0.0)
    kh = 0.5 * inputs.soil.fpga * inputs.soil.pga
    pir = kh * weight
    pir_moment = kh * gamma_c * first_y
    ls_m, eh_m, eq_m = moment(ls, h / 2.0), moment(eh, h / 3.0), moment(eq, h / 2.0)
    earth_b = max(0.5 * pae, eh)
    earth_b_m = eh_m if earth_b <= eh + 1e-12 else moment(earth_b, h / 2.0)
    gamma_eq = inputs.gamma_eq
    mu_a = gamma_eq * ls_m + eh_m + eq_m + 0.5 * pir_moment + weight_moment
    mu_b = gamma_eq * ls_m + earth_b_m + pir_moment + weight_moment
    vu_a = (gamma_eq * ls + pae) * cos(angle) + 0.5 * pir
    vu_b = (gamma_eq * ls + earth_b) * cos(angle) + pir
    return {
        "strength_mu": max(abs(1.75 * ls_m + 1.5 * eh_m + f * weight_moment) for f in (0.9, 1.25)),
        "extreme_mu": max(abs(mu_a), abs(mu_b)),
        "extreme_mu_a": abs(mu_a), "extreme_mu_b": abs(mu_b),
        "strength_vu": (1.75 * ls + 1.5 * eh) * cos(angle),
        "extreme_vu": max(vu_a, vu_b), "extreme_vu_a": vu_a, "extreme_vu_b": vu_b,
        "service_mu": abs(ls_m + eh_m + weight_moment),
        "eh_horizontal": eh * cos(angle), "eh_vertical": eh * sin(angle),
        "ls_horizontal": ls * cos(angle), "ls_vertical": ls * sin(angle),
        "eq_horizontal": eq * cos(angle), "eq_vertical": eq * sin(angle),
        "eh_moment": eh_m, "ls_moment": ls_m, "eq_moment": eq_m,
        "weight_moment": weight_moment, "pir_moment": pir_moment,
    }


def heel_transfer(inputs: "AbutmentInputs", state) -> tuple[float, float]:
    """Additional heel load from equilibrium of the soil above an inclined stem.

Return vertical force and moment about the back of the stem base, positive down.
Subtract the real stem reaction, retain the virtual-plane force, and include soil
inertia. This prevents counting wedge weight and the stem vertical thrust twice.
"""
    from bridge_design.domain.abutment import _soil_pressures, SEISMIC_PAPIR_COMBO_B
    g, soil, f = inputs.geometry, inputs.soil, state.load_factors
    p = _soil_pressures(inputs, 0.0, 0.0, 0.0, 0.0)
    h = g.stem_height_above_footing_m
    alpha = radians(p.stem_force_angle_deg)
    slope = tan(radians(90.0 - soil.wall_backface_angle_deg))
    setback = h * slope
    gamma = inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    q = gamma * p.live_surcharge_height_m + soil.pedestrian_surcharge_tn_m2
    wedge = gamma * setback * h / 2.0
    vertical = f.ev * wedge + f.ls_vertical * q * setback
    moment = -f.ev * wedge * setback / 3.0 - f.ls_vertical * q * setback**2 / 2.0

    def transfer(actual: float, virtual: float, y: float, factor: float) -> None:
        nonlocal vertical, moment
        vertical -= factor * actual * sin(alpha)
        moment += factor * ((actual * cos(alpha) - virtual) * y + actual * sin(alpha) * slope * y)

    transfer(p.stem_ka * q * h, p.ka * q * h, h / 2.0, f.ls_horizontal)
    eh, pae = 0.5 * p.stem_ka * gamma * h**2, 0.5 * p.stem_k_ae * gamma * h**2
    vh, vae = 0.5 * p.ka * gamma * h**2, 0.5 * p.k_ae * gamma * h**2
    if state.seismic_papir_combination == SEISMIC_PAPIR_COMBO_B:
        actual, virtual = max(0.5 * pae, eh), max(0.5 * vae, vh)
        ay = h / 3.0 if actual <= eh + 1e-12 else h / 2.0
        vy = h / 3.0 if virtual <= vh + 1e-12 else h / 2.0
        vertical -= actual * sin(alpha)
        moment += actual * (cos(alpha) + sin(alpha) * slope) * ay - virtual * vy
        inertia_factor = 1.0
    else:
        transfer(eh, vh, h / 3.0, f.eh)
        transfer(pae - eh, vae - vh, h / 2.0, f.eq)
        inertia_factor = 0.5
    soil_first_y = gamma * g.heel_length_m * h**2 / 2.0 + wedge * 2.0 * h / 3.0
    # The vertical-face reference already uses its established heel model.
    # For that geometry this routine transfers only the change in face loads;
    # do not introduce a delta-independent inertia jump at delta -> 0.
    if soil.wall_backface_angle_deg < 90.0 - 1e-9:
        moment -= f.eq * inertia_factor * 0.5 * soil.fpga * soil.pga * soil_first_y
    return vertical, moment
