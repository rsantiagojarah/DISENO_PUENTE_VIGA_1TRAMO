"""Shared true-scale geometry, reference axes and support symbols for connected plots."""

from PIL import ImageFont

from bridge_design.domain.abutment import _stem_thickness_at_height_m
from bridge_design.domain.connected_geometry import foundation_section, global_x
from bridge_design.domain.wall_friction import _back_x


BLUE = "#155a86"
RED = "#b44335"
GRAY = "#637381"
GREEN = "#227558"


def font(size):
    for name in ("C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def structure_polygons(data, mesh):
    floor = [(0, 0), (data.total_length_m, 0)]
    positions = [mesh.frame.nodes[index].x for index in range(mesh.foundation_count)]
    for position in reversed(positions):
        for shift in (1e-7, -1e-7):
            inside = min(max(position + shift, 1e-7), data.total_length_m - 1e-7)
            floor.append((position, -foundation_section(data, inside)[0]))
    polygons = [floor]
    for side_index, side in enumerate((data.left, data.right)):
        height = side.geometry.stem_height_above_footing_m
        levels = sorted({0.0, height, *(mesh.frame.nodes[index].y for index in mesh.side_nodes[side_index])})
        vertices = []
        for level in levels:
            for shift in (-1e-7, 1e-7):
                sample = min(max(level + shift, 0), height)
                vertices.append((global_x(data, side_index, _back_x(side.geometry, sample)), sample))
        for level in reversed(levels):
            for shift in (1e-7, -1e-7):
                sample = min(max(level + shift, 0), height)
                front = _back_x(side.geometry, sample) - _stem_thickness_at_height_m(side, sample)
                vertices.append((global_x(data, side_index, front), sample))
        polygons.append(vertices)
    return polygons


def draw_structure(draw, data, mesh, point, *, axis_color=GRAY):
    for vertices in structure_polygons(data, mesh):
        draw.polygon([point(*vertex) for vertex in vertices], fill="#e9edf0", outline=GRAY)
    for element in mesh.frame.elements:
        first, last = mesh.frame.nodes[element.start], mesh.frame.nodes[element.end]
        draw.line((point(first.x, first.y), point(last.x, last.y)), fill=axis_color, width=3)
    jump = max(1, mesh.foundation_count // 25)
    for index in range(0, mesh.foundation_count, jump):
        position = mesh.frame.nodes[index].x
        inside = min(max(position, 1e-7), data.total_length_m - 1e-7)
        horizontal, vertical = point(position, -foundation_section(data, inside)[0])
        draw.line(((horizontal, vertical), (horizontal, vertical + 5),
                   (horizontal - 5, vertical + 10), (horizontal + 5, vertical + 17),
                   (horizontal - 5, vertical + 24), (horizontal, vertical + 30),
                   (horizontal, vertical + 35)), fill=GREEN, width=2)
        draw.line((horizontal - 8, vertical + 35, horizontal + 8, vertical + 35), fill=GREEN, width=2)
    horizontal, vertical = point(data.reference_position_m, 0)
    draw.ellipse((horizontal - 6, vertical - 6, horizontal + 6, vertical + 6), fill=GRAY)

