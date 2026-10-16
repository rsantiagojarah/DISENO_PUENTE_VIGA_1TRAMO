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


def surcharge_geometry_factor(inputs: "AbutmentInputs") -> float:
    """Uniform vertical surcharge per horizontal area on the real sloping face.

    For any Coulomb wedge, its soil area is h*(1+s*tan(beta))/2 times
    the horizontal loaded width; s=tan(90-theta). Thus Pq=Ka*q*h/(1+s*tan(beta)).
    This reduces to Ka*q*h for a vertical backface or horizontal backfill.
    """
    s = tan(radians(90.0 - inputs.soil.wall_backface_angle_deg))
    return 1.0 / (1.0 + s * tan(radians(inputs.soil.backfill_slope_deg)))


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
    ls = ka * q * h * surcharge_geometry_factor(inputs)
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
    """Incremental heel load relative to the established vertical smooth-face model."""
    parts = heel_transfer_breakdown(inputs, state)
    return parts["vertical"], parts["moment"]


def heel_transfer_breakdown(inputs: "AbutmentInputs", state) -> dict[str, float]:
    """Correction about the heel root, positive vertical force downward.

    Compare the real face with a vertical smooth reference at the heel root,
    reaching the SAME fill surface (h0=h+b*tan(beta)). Common virtual-plane
    forces and heel-soil inertia cancel. Only the additional soil above the
    battered face contributes incremental inertia. This preserves the existing
    vertical-wall heel model and makes the theta -> 90 limit continuous.
    """
    from bridge_design.domain.abutment import _soil_pressures, SEISMIC_PAPIR_COMBO_B
    g, soil, f = inputs.geometry, inputs.soil, state.load_factors
    p = _soil_pressures(inputs, 0.0, 0.0, 0.0, 0.0)
    h = g.stem_height_above_footing_m
    alpha = radians(p.stem_force_angle_deg)
    slope = tan(radians(90.0 - soil.wall_backface_angle_deg))
    setback = h * slope
    fill_slope = tan(radians(soil.backfill_slope_deg))
    reference_height = h + setback * fill_slope
    gamma = inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    q = gamma * p.live_surcharge_height_m + soil.pedestrian_surcharge_tn_m2
    wedge = gamma * setback * h / 2.0
    slope_wedge = gamma * setback**2 * fill_slope / 2.0
    soil_vertical = f.ev * (wedge + slope_wedge)
    surcharge_vertical = f.ls_vertical * q * setback
    soil_moment = -soil_vertical * setback / 3.0
    surcharge_moment = -surcharge_vertical * setback / 2.0
    face_vertical = face_moment = 0.0

    def transfer(actual: float, reference: float, y: float, reference_y: float, factor: float) -> None:
        nonlocal face_vertical, face_moment
        face_vertical -= factor * actual * sin(alpha)
        face_moment += factor * (actual * (cos(alpha) + sin(alpha) * slope) * y - reference * reference_y)

    transfer(p.stem_ka * q * h * surcharge_geometry_factor(inputs), p.ka * q * reference_height,
             h / 2.0, reference_height / 2.0, f.ls_horizontal)
    eh, pae = 0.5 * p.stem_ka * gamma * h**2, 0.5 * p.stem_k_ae * gamma * h**2
    vh, vae = 0.5 * p.ka * gamma * reference_height**2, 0.5 * p.k_ae * gamma * reference_height**2
    if state.seismic_papir_combination == SEISMIC_PAPIR_COMBO_B:
        actual, virtual = max(0.5 * pae, eh), max(0.5 * vae, vh)
        ay = h / 3.0 if actual <= eh + 1e-12 else h / 2.0
        vy = reference_height / 3.0 if virtual <= vh + 1e-12 else reference_height / 2.0
        transfer(actual, virtual, ay, vy, 1.0)
        inertia_factor = 1.0
    else:
        transfer(eh, vh, h / 3.0, reference_height / 3.0, f.eh)
        transfer(pae - eh, vae - vh, h / 2.0, reference_height / 2.0, f.eq)
        inertia_factor = 0.5
    soil_first_y = wedge * 2.0 * h / 3.0 + slope_wedge * (h + setback * fill_slope / 3.0)
    inertia_moment = -f.eq * inertia_factor * 0.5 * soil.fpga * soil.pga * soil_first_y
    return {
        "reference_height": reference_height, "wedge_weight": wedge, "slope_wedge_weight": slope_wedge,
        "soil_vertical": soil_vertical, "surcharge_vertical": surcharge_vertical, "face_vertical": face_vertical,
        "soil_moment": soil_moment, "surcharge_moment": surcharge_moment,
        "face_moment": face_moment, "inertia_moment": inertia_moment,
        "vertical": soil_vertical + surcharge_vertical + face_vertical,
        "moment": soil_moment + surcharge_moment + face_moment + inertia_moment,
    }
