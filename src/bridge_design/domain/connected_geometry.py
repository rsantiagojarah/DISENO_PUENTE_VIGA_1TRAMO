"""Map existing cajuela geometry to reference axes of a continuous 2D FRAME."""

from dataclasses import dataclass
from math import ceil, isclose

from bridge_design.codes.mtc_2018 import calculate_concrete_elastic_modulus_kg_cm2
from bridge_design.domain.abutment import _stem_thickness_at_height_m
from bridge_design.domain.connected_2_inputs import is_connected_2
from bridge_design.domain.frame_types import FrameElement, FrameModel, FrameNode, VerticalSpring
from bridge_design.domain.wall_friction import _back_x
from bridge_design.domain.transverse_slab import kg_cm2_to_tn_m2


@dataclass(frozen=True)
class ConnectedMesh:
    frame: FrameModel
    foundation_count: int
    reference_node: int
    side_nodes: tuple[tuple[int, ...], tuple[int, ...]]
    side_elements: tuple[tuple[int, ...], tuple[int, ...]]


def elastic_modulus(materials):
    return kg_cm2_to_tn_m2(calculate_concrete_elastic_modulus_kg_cm2(
        materials.concrete_unit_weight_kg_m3 / 1000, materials.concrete_strength_kg_cm2))


def global_x(data, side_index, local_x):
    if side_index == 0:
        return data.left.geometry.footing_width_m - local_x
    return data.total_length_m - data.right.geometry.footing_width_m + local_x


def local_x(data, side_index, position):
    if side_index == 0:
        return data.left.geometry.footing_width_m - position
    return position - data.total_length_m + data.right.geometry.footing_width_m


def side_axis(data, side_index):
    geometry = (data.left, data.right)[side_index].geometry
    return global_x(data, side_index, geometry.toe_length_m + geometry.lower_stem_thickness_m / 2)


def stem_centroid(data, side_index, height):
    side = (data.left, data.right)[side_index]
    return global_x(data, side_index, _back_x(side.geometry, height)
                    - _stem_thickness_at_height_m(side, height) / 2)


def foundation_section(data, position):
    if is_connected_2(data):
        return data.left.geometry.footing_thickness_m, "Zapata combinada", data.left.materials
    left_end = data.left.geometry.footing_width_m
    right_start = data.total_length_m - data.right.geometry.footing_width_m
    if position < left_end:
        return data.left.geometry.footing_thickness_m, "Zapata izquierda", data.left.materials
    if position > right_start:
        return data.right.geometry.footing_thickness_m, "Zapata derecha", data.right.materials
    if data.left_transition_m and position < left_end + data.left_transition_m:
        ratio = (position - left_end) / data.left_transition_m
        thickness = data.left.geometry.footing_thickness_m * (1 - ratio) + data.slab_thickness_m * ratio
        return thickness, "Transicion izquierda", data.slab_materials
    if data.right_transition_m and position > right_start - data.right_transition_m:
        ratio = (right_start - position) / data.right_transition_m
        thickness = data.right.geometry.footing_thickness_m * (1 - ratio) + data.slab_thickness_m * ratio
        return thickness, "Transicion derecha", data.slab_materials
    return data.slab_thickness_m, "Losa central", data.slab_materials


def subdivide(boundaries, maximum):
    values = sorted(set(round(value, 10) for value in boundaries))
    result = [values[0]]
    for start, end in zip(values, values[1:]):
        count = max(1, ceil((end - start) / maximum))
        result.extend(start + (end - start) * step / count for step in range(1, count + 1))
    return result


def soil_intervals(side):
    geometry = side.geometry
    toe = geometry.toe_length_m
    back = toe + geometry.lower_stem_thickness_m
    body = geometry.stem_height_above_footing_m - geometry.seat_block_height_m - geometry.backwall_drop_m
    straight = body - geometry.backwall_taper_height_m
    front_height = max(0.0, geometry.front_soil_depth_m - geometry.footing_thickness_m)
    batter = front_height * (geometry.lower_stem_thickness_m - geometry.upper_stem_thickness_m) / straight
    return (0.0, toe, toe + batter, back, back + geometry.backfill_step_width_m, geometry.footing_width_m)


def foundation_spring_positions(data):
    """Exact spring count; uniform spacing between ends and stem axes.

    Geometry/load boundaries remain separate FRAME nodes, without adding springs.
    Allocate matching end intervals together to preserve symmetric supports.
    """
    anchors = (0.0, side_axis(data, 0), side_axis(data, 1), data.total_length_m)
    lengths = [last - first for first, last in zip(anchors, anchors[1:])]
    divisions = [1, 1, 1]
    remaining = data.foundation_node_count - len(anchors)
    while remaining:
        index = max(range(3), key=lambda i: lengths[i] / divisions[i])
        if index in (0, 2) and isclose(lengths[0], lengths[2], abs_tol=1e-9) and divisions[0] == divisions[2]:
            if remaining >= 2:
                divisions[0] += 1
                divisions[2] += 1
                remaining -= 2
            else:
                divisions[1] += 1
                remaining -= 1
        else:
            divisions[index] += 1
            remaining -= 1
    positions = [anchors[0]]
    for first, last, count in zip(anchors, anchors[1:], divisions):
        positions.extend(first + (last - first) * step / count for step in range(1, count + 1))
    return positions


def build_connected_mesh(data):
    left_end = data.left.geometry.footing_width_m
    right_start = data.total_length_m - data.right.geometry.footing_width_m
    boundaries = [0.0, left_end, left_end + data.left_transition_m,
                  right_start - data.right_transition_m, right_start, data.total_length_m,
                  data.reference_position_m, side_axis(data, 0), side_axis(data, 1)]
    for side_index, side in enumerate((data.left, data.right)):
        boundaries.extend(global_x(data, side_index, position) for position in soil_intervals(side))
    if data.foundation_node_count is None:
        positions = subdivide(boundaries, data.mesh_size_m)
        spring_positions = positions
    else:
        spring_positions = foundation_spring_positions(data)
        positions = subdivide([*boundaries, *spring_positions], data.effective_mesh_size_m)
    nodes = [FrameNode(position, 0.0) for position in positions]
    foundation_count = len(nodes)
    elements = []
    for index in range(foundation_count - 1):
        midpoint = (positions[index] + positions[index + 1]) / 2
        thickness, region, materials = foundation_section(data, midpoint)
        elements.append(FrameElement(index, index + 1, thickness, thickness**3 / 12,
                                     elastic_modulus(materials), region, thickness,
                                     -thickness / 2 if data.section_offsets else 0.0))
    side_nodes, side_elements = [], []
    for side_index, side in enumerate((data.left, data.right)):
        geometry = side.geometry
        height = geometry.stem_height_above_footing_m
        body = height - geometry.seat_block_height_m - geometry.backwall_drop_m
        levels = subdivide([0.0, body - geometry.backwall_taper_height_m, body,
                            height - geometry.seat_block_height_m, height], data.effective_mesh_size_m)
        axis = side_axis(data, side_index)
        base = min(range(foundation_count), key=lambda index: abs(positions[index] - axis))
        identifiers = [base]
        members = []
        label = "izquierda" if side_index == 0 else "derecha"
        for lower, upper in zip(levels, levels[1:]):
            midpoint = (lower + upper) / 2
            thickness = _stem_thickness_at_height_m(side, midpoint)
            if midpoint < body - geometry.backwall_taper_height_m:
                region = "Pantalla " + label
            elif midpoint < body:
                region = "Transicion cajuela " + label
            elif midpoint < height - geometry.seat_block_height_m:
                region = "Cajuela " + label
            else:
                region = "Parapeto " + label
            end = len(nodes)
            nodes.append(FrameNode(axis, upper))
            members.append(len(elements))
            elements.append(FrameElement(identifiers[-1], end, thickness, thickness**3 / 12,
                                         elastic_modulus(side.materials), region, thickness,
                                         axis - stem_centroid(data, side_index, midpoint)
                                         if data.section_offsets else 0.0))
            identifiers.append(end)
        side_nodes.append(tuple(identifiers))
        side_elements.append(tuple(members))
    reference = min(range(foundation_count), key=lambda index: abs(positions[index] - data.reference_position_m))
    areas = [0.0] * len(spring_positions)
    for index, (first, last) in enumerate(zip(spring_positions, spring_positions[1:])):
        areas[index] += (last - first) / 2
        areas[index + 1] += (last - first) / 2
    node_at = {round(position, 10): index for index, position in enumerate(positions)}
    springs = tuple(VerticalSpring(node_at[round(position, 10)], area * data.soil.subgrade_tn_m3, area,
                                   data.soil.allowable_tn_m2)
                    for position, area in zip(spring_positions, areas))
    frame = FrameModel(tuple(nodes), tuple(elements), springs, (3 * reference,))
    return ConnectedMesh(frame, foundation_count, reference, tuple(side_nodes), tuple(side_elements))
