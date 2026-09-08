"""Simultaneous global HL-93 reactions for a simple span.

MTC 2.4.3.2: whole vehicles, lane loading and multiple presence. Girder
distribution factors do not enter global vertical equilibrium. Each maximum
retains the other support reaction from the same physical load placement.
"""

from dataclasses import dataclass

from bridge_design.codes.mtc_2018 import mtc_design_lanes, mtc_multiple_presence_factor, mtc_dynamic_load_allowance_for_slab
from bridge_design.domain.loads import VehicleLoadModel
from bridge_design.validation.input_validators import require_positive


@dataclass(frozen=True)
class GlobalReactionCase:
    name: str
    loaded_lanes: int
    left_tn: float
    right_tn: float
    total_load_tn: float
    axles: tuple[tuple[float, float], ...]
    lane_load_tn_m: float


def global_live_reaction_cases(span_m: float, roadway_width_m: float,
                               vehicle: VehicleLoadModel) -> tuple[GlobalReactionCase, ...]:
    """Return empty traffic plus exact reaction extrema and companion reactions.

    Reaction influence lines are linear. Extrema occur when an axle reaches
    an end. Minimum truck spacing governs this positive simple-span influence
    line. Cases for each support are separate, never simultaneous maxima.
    """
    require_positive(span_m, "luz")
    lanes, _ = mtc_design_lanes(roadway_width_m)
    rows = [GlobalReactionCase("Sin vehiculos", 0, 0.0, 0.0, 0.0, (), 0.0)]
    first, variable = vehicle.design_truck_spacings_m
    configurations = (
        ("Camion", vehicle.design_truck_axles_tn, (0.0, first, first + min(variable))),
        ("Tandem", vehicle.design_tandem_axles_tn, (0.0, vehicle.design_tandem_spacing_m)),
    )
    impact = 1.0 + mtc_dynamic_load_allowance_for_slab()
    for count in range(1, lanes + 1):
        factor = count * mtc_multiple_presence_factor(count)
        lane = factor * vehicle.lane_load_tn_m
        for name, loads, offsets in configurations:
            candidates = []
            for ordered_loads in (loads, tuple(reversed(loads))):
                # Reverse the spacings as well to preserve the vehicle geometry.
                oriented_offsets = offsets if ordered_loads is loads else tuple(offsets[-1] - x for x in reversed(offsets))
                for base in {-x for x in oriented_offsets} | {span_m - x for x in oriented_offsets}:
                    axles = tuple((max(0.0, min(span_m, base + x)), p * impact * factor)
                                  for x, p in zip(oriented_offsets, ordered_loads)
                                  if -1e-9 <= base + x <= span_m + 1e-9)
                    total = lane * span_m + sum(p for _, p in axles)
                    left = lane * span_m / 2.0 + sum(p * (span_m - x) / span_m for x, p in axles)
                    candidates.append(GlobalReactionCase(name, count, left, total - left, total, axles, lane))
            for side in ("left", "right"):
                best = max(candidates, key=lambda row: getattr(row, side + "_tn"))
                rows.append(GlobalReactionCase(f"{name}, {count} carriles, max {side}", count,
                                              best.left_tn, best.right_tn, best.total_load_tn, best.axles, lane))
    return tuple(rows)


def project_live_reaction_cases(project):
    layout = project.transverse_slab.load_layout
    return global_live_reaction_cases(project.interior_girder.span_length_m,
                                     layout.vehicle_move_end_m - layout.vehicle_move_start_m,
                                     project.live_loads.vehicular)


def project_live_reaction_row(project):
    cases = project_live_reaction_cases(project)
    left = max(row.left_tn for row in cases)
    right = max(row.right_tn for row in cases)
    width = project.transverse_slab.geometry.total_width_m
    return ("PLL+IM", "Envolvente global HL-93", f"{left:.3f}", f"{right:.3f}",
            f"{left / width:.3f}", f"{right / width:.3f}")
