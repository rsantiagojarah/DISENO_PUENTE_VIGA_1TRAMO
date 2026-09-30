"""Wall-friction actions on the stepped abutment and reaction on its heel.

MTC 2018 Art. 2.4.4.1.5.3 (Coulomb), A.11.3.1 (M-O), and
2.8.1.1.14.1 (PAE/PIR envelope). The abutment retains its equivalent
vertical pressure-face model (theta=90); the real stepped section supplies
the lever arms. This is not a separate Coulomb wedge for each step.
Positive vertical force is downward. No axial-capacity benefit is taken.
"""
from dataclasses import replace
from math import cos, radians, sin, sqrt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bridge_design.domain.abutment import (
        AbutmentGeometryInputs, AbutmentInputs, SoilPressureResult, StabilityStateResult,
    )



def _back_x(g: "AbutmentGeometryInputs", y: float) -> float:
    """Back of the actual stepped section, measured from the toe."""
    x = g.toe_length_m + g.lower_stem_thickness_m
    body = g.stem_height_above_footing_m - g.seat_block_height_m - g.backwall_drop_m
    start = body - g.backwall_taper_height_m
    if y <= start:
        return x
    if y < body and g.backwall_taper_height_m > 0:
        return x + g.backfill_step_width_m * (y - start) / g.backwall_taper_height_m
    return x + g.backfill_step_width_m


def earth_actions(inputs: "AbutmentInputs", p: "SoilPressureResult", cut: float = 0.0) -> dict[str, dict[str, float]]:
    """Exact integration of linear pressures and piecewise-linear backface."""
    from bridge_design.domain.abutment import _stem_thickness_at_height_m
    g = inputs.geometry
    height = g.stem_height_above_footing_m
    cut = min(max(cut, 0.0), height)
    h = height - cut
    angle = radians(p.stem_force_angle_deg)
    root = g.toe_length_m + g.lower_stem_thickness_m
    centre = _back_x(g, cut) - _stem_thickness_at_height_m(inputs, cut) / 2
    gamma = inputs.materials.soil_unit_weight_kg_m3 / 1000
    q = gamma * p.live_surcharge_height_m + inputs.soil.pedestrian_surcharge_tn_m2
    body = height - g.seat_block_height_m - g.backwall_drop_m
    boundaries = sorted({cut, height, *(
        y for y in (body-g.backwall_taper_height_m, body) if cut < y < height
    )})

    def row(force, triangular=False):
        # Integrate the eccentricity relative to the heel root; two Gauss
        # points integrate the quadratic pressure*x polynomial exactly.
        eccentricity = 0.0
        if h > 0:
            for low, high in zip(boundaries, boundaries[1:]):
                mid, half = (low+high)/2, (high-low)/2
                for sign in (-1, 1):
                    y = mid + sign*half/sqrt(3)
                    density = 2*(height-y)/h**2 if triangular else 1/h
                    eccentricity += half*density*(_back_x(g,y)-root)
        horizontal, vertical = force*cos(angle), force*sin(angle)
        arm = h/3 if triangular else h/2
        root_moment = horizontal*arm - vertical*eccentricity
        return {
            "horizontal": horizontal, "vertical": vertical,
            "moment": root_moment - vertical*(root-centre),
            "root_moment": root_moment,
        }

    eh = 0.5*p.stem_ka*gamma*h*h
    pae = 0.5*p.stem_k_ae*gamma*h*h
    return {
        "ls": row(p.stem_ka*q*h),
        "eh": row(eh, True),
        "eq": row(pae-eh),
        "b": row(max(0.5*pae, eh), 0.5*pae <= eh+1e-12),
    }


def abutment_actions(inputs: "AbutmentInputs", p: "SoilPressureResult", cut: float = 0.0) -> dict[str, float]:
    """Actual face forces for service, strength, seismic A/B and bar cuts."""
    from bridge_design.domain.abutment import _upper_concrete_weight_and_arm
    g = inputs.geometry
    height = g.stem_height_above_footing_m
    cut = min(max(cut, 0.0), height)
    h = height-cut
    rows = earth_actions(inputs,p,cut)
    ls, eh, eq, b = (rows[k] for k in ("ls","eh","eq","b"))
    weight, arm = _upper_concrete_weight_and_arm(inputs)
    pir = 0.5*inputs.soil.fpga*inputs.soil.pga*weight if h > 0 else 0.0
    # Preserve the established abutment inertia distribution at bar cuts.
    pir_m = pir*arm*h/height
    peq = p.peq_tn_m if h > 0 else 0.0
    peq_m = peq*max(h-g.seat_block_height_m/2,0)
    br = inputs.loads.braking_tn_m if h > 0 else 0.0
    br_m = br*(h+g.bridge_seat_to_bearing_height_m)
    ge = inputs.gamma_eq
    mu_a = ge*ls["moment"]+eh["moment"]+eq["moment"]+0.5*pir_m+peq_m+ge*br_m
    mu_b = ge*ls["moment"]+b["moment"]+pir_m+peq_m+ge*br_m
    vu_a = ge*ls["horizontal"]+eh["horizontal"]+eq["horizontal"]+0.5*pir+peq+ge*br
    vu_b = ge*ls["horizontal"]+b["horizontal"]+pir+peq+ge*br
    result = {
        "strength_mu": abs(1.75*ls["moment"]+1.5*eh["moment"]+1.75*br_m),
        "extreme_mu": max(abs(mu_a),abs(mu_b)),
        "extreme_mu_a": abs(mu_a), "extreme_mu_b": abs(mu_b),
        "strength_vu": 1.75*ls["horizontal"]+1.5*eh["horizontal"]+1.75*br,
        "extreme_vu": max(vu_a,vu_b), "extreme_vu_a": vu_a, "extreme_vu_b": vu_b,
        "service_mu": abs(ls["moment"]+eh["moment"]+br_m),
        "weight_moment": 0.0, "pir_moment": pir_m,
        "peq_moment": peq_m, "br_moment": br_m,
    }
    for name in ("ls","eh","eq"):
        for field in ("horizontal","vertical","moment"):
            result[name+"_"+field] = rows[name][field]
    return result


def abutment_heel_transfer(inputs: "AbutmentInputs", state: "StabilityStateResult") -> tuple[float, float]:
    """Change from the smooth-face reference; global face loads stay internal."""
    from bridge_design.domain.abutment import _soil_pressures, SEISMIC_PAPIR_COMBO_B
    p = _soil_pressures(inputs,0,0,0,0)
    smooth = replace(p,stem_ka=p.ka,stem_k_ae=p.k_ae,stem_force_angle_deg=0)
    actual, reference = earth_actions(inputs,p), earth_actions(inputs,smooth)
    f = state.load_factors
    factors = [("ls",f.ls_horizontal)]
    if state.seismic_papir_combination == SEISMIC_PAPIR_COMBO_B:
        factors.append(("b",f.eq))
    else:
        factors.extend((("eh",f.eh),("eq",f.eq)))
    vertical = -sum(factor*actual[name]["vertical"] for name,factor in factors)
    moment = sum(factor*(actual[name]["root_moment"]-reference[name]["root_moment"])
                 for name,factor in factors)
    return vertical,moment
