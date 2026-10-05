"""Reusable physical load assembly with actual cajuela arms; Tn and m per unit strip."""

from bridge_design.domain.abutment import _stem_thickness_at_height_m
from bridge_design.domain.connected_geometry import (
    foundation_section, global_x, local_x, soil_intervals, stem_centroid,
)
from bridge_design.domain.frame_elements import (
    consistent_load, distributed_from_function, element_matrices, matvec, transpose,
)
from bridge_design.domain.frame_types import ElementLoad, FrameCase


class LoadBuilder:
    def __init__(self, model):
        self.model = model
        self.nodal = [0.0] * (3 * len(model.nodes))
        self.distributed = [ElementLoad() for _ in model.elements]

    def add_density(self, index, density):
        load = distributed_from_function(self.model, self.model.elements[index], density)
        self.distributed[index] = self.distributed[index].plus(load)

    def point(self, node_index, horizontal=0.0, vertical=0.0, x=None, y=None, couple=0.0):
        node = self.model.nodes[node_index]
        self.nodal[3 * node_index] += horizontal
        self.nodal[3 * node_index + 1] += vertical
        self.nodal[3 * node_index + 2] += couple + ((node.x if x is None else x) - node.x) * vertical
        self.nodal[3 * node_index + 2] -= ((node.y if y is None else y) - node.y) * horizontal

    def add(self, other, factor=1.0):
        self.nodal = [current + factor * added for current, added in zip(self.nodal, other.nodal)]
        self.distributed = [current.plus(added.scaled(factor))
                            for current, added in zip(self.distributed, other.distributed)]

    def vector(self):
        vector = list(self.nodal)
        for index, element in enumerate(self.model.elements):
            _local, transform, _matrix, dofs, length = element_matrices(self.model, element)
            for dof, value in zip(dofs, matvec(transpose(transform), consistent_load(self.distributed[index], length))):
                vector[dof] += value
        return vector

    def case(self, name, limit_state):
        return FrameCase(name, tuple(self.nodal), tuple(self.distributed), limit_state)


def soil_density(side, position):
    """Vertical soil weight and its height above footing, matching _soil_components."""
    geometry = side.geometry
    height = geometry.stem_height_above_footing_m
    _zero, toe, batter_end, back, step_end, outer = soil_intervals(side)
    body = height - geometry.seat_block_height_m - geometry.backwall_drop_m
    front_height = max(0.0, geometry.front_soil_depth_m - geometry.footing_thickness_m)
    if step_end < position < outer:
        return height, height / 2
    if back < position < step_end:
        soil_height = body - geometry.backwall_taper_height_m
        soil_height += geometry.backwall_taper_height_m * (position - back) / (step_end - back)
        return soil_height, soil_height / 2
    if 0 < position < toe:
        return front_height, front_height / 2
    if toe < position < batter_end:
        ratio = (position - toe) / (batter_end - toe)
        return front_height * (1 - ratio), front_height * (1 + ratio) / 2
    return 0.0, 0.0


def gravity_builders(data, mesh):
    model = mesh.frame
    parts = {name: LoadBuilder(model) for name in (
        "DC0", "DC1", "DCs", "EV0", "EV1", "PIR0", "PIR1", "PIRs")}
    kh = 0.5 * data.left.soil.pga * data.left.soil.fpga
    for index in range(mesh.foundation_count - 1):
        element = model.elements[index]
        first, last = model.nodes[element.start], model.nodes[element.end]
        middle = (first.x + last.x) / 2
        _thickness, _region, materials = foundation_section(data, middle)
        # Load ownership follows position, independently of reinforcement regions.
        # The combined footing still carries exterior backfill at both ends.
        owner = ("0" if middle < data.left.geometry.footing_width_m else
                 "1" if middle > data.total_length_m-data.right.geometry.footing_width_m else "s")

        def foundation_weight(station):
            position = first.x + station * (last.x - first.x)
            inside = min(max(position, first.x + 1e-9), last.x - 1e-9)
            thickness = foundation_section(data, inside)[0]
            return thickness * materials.concrete_unit_weight_kg_m3 / 1000

        parts["DC" + owner].add_density(index, lambda station: (0.0, -foundation_weight(station), 0.0))
        centroid_y = element.offset

        def foundation_inertia(station):
            weight = foundation_weight(station)
            real_y = -weight / (materials.concrete_unit_weight_kg_m3 / 1000) / 2
            return kh * weight, 0.0, -(real_y - centroid_y) * kh * weight

        parts["PIR" + owner].add_density(index, foundation_inertia)
        if owner == "s":
            continue
        side_index = int(owner)
        side = (data.left, data.right)[side_index]

        def soil_at(station):
            position = first.x + station * (last.x - first.x)
            position = min(max(position, first.x + 1e-8), last.x - 1e-8)
            height, centre = soil_density(side, local_x(data, side_index, position))
            return height * side.materials.soil_unit_weight_kg_m3 / 1000, centre

        parts["EV" + owner].add_density(index, lambda station: (0.0, -soil_at(station)[0], 0.0))
        parts["PIR" + owner].add_density(index, lambda station: (
            kh * soil_at(station)[0], 0.0,
            -(soil_at(station)[1] - centroid_y) * kh * soil_at(station)[0]))
    for side_index, side in enumerate((data.left, data.right)):
        owner = str(side_index)
        for index in mesh.side_elements[side_index]:
            element = model.elements[index]
            first, last = model.nodes[element.start], model.nodes[element.end]
            centroid_x = first.x - element.offset

            def stem_at(station):
                height = first.y + station * (last.y - first.y)
                height = min(max(height, first.y + 1e-9), last.y - 1e-9)
                weight = _stem_thickness_at_height_m(side, height) * side.materials.concrete_unit_weight_kg_m3 / 1000
                return weight, stem_centroid(data, side_index, height)

            parts["DC" + owner].add_density(index, lambda station: (
                0.0, -stem_at(station)[0], -(stem_at(station)[1] - centroid_x) * stem_at(station)[0]))
            parts["PIR" + owner].add_density(index, lambda station: (kh * stem_at(station)[0], 0.0, 0.0))
    return parts


def bridge_builders(data, mesh, paired):
    parts = {}
    for side_index, (side, loads) in enumerate(zip((data.left, data.right), (paired.left, paired.right))):
        geometry = side.geometry
        seat_y = geometry.stem_height_above_footing_m - geometry.seat_block_height_m
        node = min(mesh.side_nodes[side_index], key=lambda index: abs(mesh.frame.nodes[index].y - seat_y))
        position = global_x(data, side_index, geometry.superstructure_load_x_m)
        owner = str(side_index)
        for kind, value in (("BDC", loads.pdc_tn_m), ("DW", loads.pdw_tn_m),
                            ("LL", loads.pll_im_tn_m + loads.ppl_tn_m)):
            builder = LoadBuilder(mesh.frame)
            builder.point(node, vertical=-value, x=position)
            parts[kind + owner] = builder
        braking = LoadBuilder(mesh.frame)
        braking.point(node, horizontal=loads.braking_tn_m,
                      y=geometry.stem_height_above_footing_m + geometry.bridge_seat_to_bearing_height_m)
        parts["BR" + owner] = braking
        seismic = LoadBuilder(mesh.frame)
        seismic.point(node, horizontal=(loads.pdc_tn_m + loads.pdw_tn_m) * side.soil.pga * side.soil.fpga,
                      y=geometry.stem_height_above_footing_m - geometry.seat_block_height_m / 2)
        parts["PEQ" + owner] = seismic
    return parts
