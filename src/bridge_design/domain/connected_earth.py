"""Active Coulomb/M-O face pressures and equilibrium transfer to soil on heels.

Uses the existing distinction between the actual stepped face and the external
vertical plane through the heel. Face friction is internal to wall plus heel
soil; its equal/opposite transfer avoids counting soil weight twice.
"""

from dataclasses import replace
from math import cos, radians, sin

from bridge_design.domain.abutment import _soil_pressures, mononobe_okabe_active_coefficient
from bridge_design.domain.connected_geometry import global_x, local_x
from bridge_design.domain.connected_loads import LoadBuilder
from bridge_design.domain.frame_solver import global_resultant
from bridge_design.domain.wall_friction import _back_x


def pressure_profile(ka, kae, gamma, height, kind):
    """Uniform positive seismic increment as existing abutments; reductions triangular."""
    static = 0.5 * ka * gamma * height**2
    seismic = 0.5 * kae * gamma * height**2
    if kind == "EH":
        return ka * gamma * height, 0.0
    if kind == "A":
        if seismic >= static:
            addition = (seismic - static) / height
            return ka * gamma * height + addition, addition
        return kae * gamma * height, 0.0
    if 0.5 * seismic <= static:
        return ka * gamma * height, 0.0
    return 0.5 * seismic / height, 0.5 * seismic / height


def heel_transfer(data, mesh, side_index, builder, target):
    actual = global_resultant(mesh.frame, builder.vector())
    correction = tuple(expected - current for expected, current in zip(target, actual))
    side = (data.left, data.right)[side_index]
    back = side.geometry.toe_length_m + side.geometry.lower_stem_thickness_m
    selected = []
    for spring in mesh.frame.springs:
        coordinate = local_x(data, side_index, mesh.frame.nodes[spring.node].x)
        if back - 1e-8 <= coordinate <= side.geometry.footing_width_m + 1e-8:
            selected.append(spring)
    if not selected:
        raise ValueError("La malla no contiene nodos de talon para la transferencia de relleno.")
    total_area = sum(spring.tributary_area for spring in selected)
    centre = sum(mesh.frame.nodes[spring.node].x * spring.tributary_area for spring in selected) / total_area
    free_couple = correction[2] - centre * correction[1]
    for spring in selected:
        fraction = spring.tributary_area / total_area
        builder.point(spring.node, correction[0] * fraction, correction[1] * fraction,
                      couple=free_couple * fraction)


def earth_builder(data, mesh, side_index, kind, seismic_direction=1):
    side = (data.left, data.right)[side_index]
    geometry = side.geometry
    direction = 1 if side_index == 0 else -1
    height = geometry.stem_height_above_footing_m
    gamma = side.materials.soil_unit_weight_kg_m3 / 1000
    pressures = _soil_pressures(side, 0, 0, 0, 0)
    signed_direction = seismic_direction * direction
    face_kae = mononobe_okabe_active_coefficient(side, horizontal_direction=signed_direction)[0]
    smooth = replace(side, soil=replace(side.soil, wall_soil_friction_deg=0.0))
    global_kae = mononobe_okabe_active_coefficient(smooth, horizontal_direction=signed_direction)[0]
    angle = radians(pressures.stem_force_angle_deg)
    if kind == "LS":
        surcharge = gamma * pressures.live_surcharge_height_m + side.soil.pedestrian_surcharge_tn_m2
        base = top = pressures.stem_ka * surcharge
    else:
        base, top = pressure_profile(pressures.stem_ka, face_kae, gamma, height, kind)
    builder = LoadBuilder(mesh.frame)
    for index in mesh.side_elements[side_index]:
        element = mesh.frame.elements[index]
        first, last = mesh.frame.nodes[element.start], mesh.frame.nodes[element.end]
        centroid = first.x - element.offset

        def density(station):
            level = first.y + station * (last.y - first.y)
            pressure = base + (top - base) * level / height
            horizontal = direction * cos(angle) * pressure
            vertical = -sin(angle) * pressure
            position = global_x(data, side_index, _back_x(geometry, level))
            return horizontal, vertical, (position - centroid) * vertical

        builder.add_density(index, density)
    full_height = geometry.retained_height_m
    if kind == "LS":
        global_base = global_top = pressures.ka * surcharge
    else:
        global_base, global_top = pressure_profile(pressures.ka, global_kae, gamma, full_height, kind)
    resultant = direction * (global_base + global_top) * full_height / 2
    moment_from_bottom = direction * full_height**2 * (global_base + 2 * global_top) / 6
    target = (resultant, 0.0, -moment_from_bottom + geometry.footing_thickness_m * resultant)
    heel_transfer(data, mesh, side_index, builder, target)
    return builder


def surcharge_weight(data, mesh, side_index):
    side = (data.left, data.right)[side_index]
    pressures = _soil_pressures(side, 0, 0, 0, 0)
    intensity = side.materials.soil_unit_weight_kg_m3 / 1000 * pressures.live_surcharge_height_m
    intensity += side.soil.pedestrian_surcharge_tn_m2
    geometry = side.geometry
    start = geometry.toe_length_m + geometry.lower_stem_thickness_m + geometry.backfill_step_width_m
    builder = LoadBuilder(mesh.frame)
    for index in range(mesh.foundation_count - 1):
        element = mesh.frame.elements[index]
        midpoint = (mesh.frame.nodes[element.start].x + mesh.frame.nodes[element.end].x) / 2
        coordinate = local_x(data, side_index, midpoint)
        if start < coordinate < geometry.footing_width_m:
            builder.add_density(index, lambda station: (0.0, -intensity, 0.0))
    return builder
