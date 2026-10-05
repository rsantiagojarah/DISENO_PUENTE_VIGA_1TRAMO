"""Signed force envelopes drawn on the complete connected FRAME geometry."""

from dataclasses import dataclass
from math import hypot

from PIL import Image, ImageDraw

from bridge_design.domain.frame_sections import section_force_at
from bridge_design.reporting.connected_case_groups import case_label
from bridge_design.reporting.connected_chart_geometry import (
    BLUE, GRAY, RED, draw_structure, font, structure_polygons,
)


@dataclass(frozen=True)
class EnvelopePoint:
    element: int
    station: float
    minimum: float
    maximum: float
    minimum_case: str
    maximum_case: str


def frame_envelope(result, field, case_names=None):
    if field not in ("axial", "shear", "moment"):
        raise ValueError("Diagrama desconocido: " + field)
    model = result.mesh.frame
    cases = {case.name: case for case in result.cases}
    included = [(case_label(row.name), row, cases[row.name]) for row in result.results
                if (row.name in case_names if case_names is not None else row.limit_state != "service")]
    if not included:
        raise ValueError("No hay casos seleccionados para los diagramas.")
    stations = {index: {0.0, 0.25, 0.5, 0.75, 1.0} for index in range(len(model.elements))}
    for _label, row, _case in included:
        for section in row.sections:
            stations[section.element].add(section.station)
    diagrams = []
    for index, element in enumerate(model.elements):
        first, last = model.nodes[element.start], model.nodes[element.end]
        length = hypot(last.x - first.x, last.y - first.y)
        points = []
        for station in sorted(stations[index]):
            values = [(getattr(section_force_at(index, row.end_forces[index], case.distributed[index],
                                               length, station), field), label)
                      for label, row, case in included]
            minimum, minimum_case = min(values, key=lambda entry: entry[0])
            maximum, maximum_case = max(values, key=lambda entry: entry[0])
            points.append(EnvelopePoint(index, station, minimum, maximum, minimum_case, maximum_case))
        diagrams.append(tuple(points))
    return tuple(diagrams)


def diagram_position(model, element_index, station, value=0.0, factor=0.0):
    """Draw signed ordinates on the reversed normal, preserving force values."""
    element = model.elements[element_index]
    first, last = model.nodes[element.start], model.nodes[element.end]
    delta_x, delta_y = last.x - first.x, last.y - first.y
    length = hypot(delta_x, delta_y)
    return (first.x + station * delta_x + delta_y / length * value * factor,
            first.y + station * delta_y - delta_x / length * value * factor)


def fitted_coordinates(vertices, box):
    left, top, right, bottom = box
    minimum_x, maximum_x = min(vertex[0] for vertex in vertices), max(vertex[0] for vertex in vertices)
    minimum_y, maximum_y = min(vertex[1] for vertex in vertices), max(vertex[1] for vertex in vertices)
    margin = max(0.8, 0.04 * max(maximum_x - minimum_x, maximum_y - minimum_y))
    minimum_x, maximum_x = minimum_x - margin, maximum_x + margin
    minimum_y, maximum_y = minimum_y - margin, maximum_y + margin
    scale = min((right - left) / (maximum_x - minimum_x), (bottom - top) / (maximum_y - minimum_y))
    origin_x = (left + right - (maximum_x + minimum_x) * scale) / 2
    origin_y = (top + bottom + (maximum_y + minimum_y) * scale) / 2
    return lambda position, height: (origin_x + position * scale, origin_y - height * scale)


def annotate_value(draw, position, text, color, occupied):
    horizontal, vertical = position
    width = draw.textlength(text, font=font(40)) + 16
    for shift_x, shift_y in ((12, -56), (12, 12), (-width - 12, -56), (-width - 12, 12),
                             (-width / 2, -100), (-width / 2, 66)):
        left = max(20, min(1980 - width, horizontal + shift_x))
        top = max(275, min(1178, vertical + shift_y))
        box = (left, top, left + width, top + 52)
        if not any(box[0] < other[2] + 8 and box[2] > other[0] - 8 and
                   box[1] < other[3] + 8 and box[3] > other[1] - 8 for other in occupied):
            break
    occupied.append(box)
    draw.line((position, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)), fill=color, width=1)
    draw.rectangle(box, fill="white")
    draw.text((box[0] + 8, box[1] + 2), text, font=font(40), fill=color)
    draw.ellipse((horizontal - 4, vertical - 4, horizontal + 4, vertical + 4), fill=color)


def frame_envelope_chart(result, field, path, case_names=None, group_name=None):
    labels = {"axial": ("Fuerza axial N", "Tn"), "shear": ("Cortante V", "Tn"),
              "moment": ("Momento flector M", "Tn m")}
    label, units = labels[field]
    diagrams = frame_envelope(result, field, case_names)
    rows = [row for points in diagrams for row in points]
    minimum = min(rows, key=lambda row: row.minimum)
    maximum = max(rows, key=lambda row: row.maximum)
    peak = max(abs(minimum.minimum), abs(maximum.maximum))
    data, mesh = result.inputs, result.mesh
    amplitude = min(data.total_length_m, max(node.y for node in mesh.frame.nodes)) * 0.23
    factor = amplitude / peak if peak > 1e-10 else 0.0
    polygons = structure_polygons(data, mesh)
    vertices = [vertex for polygon in polygons for vertex in polygon]
    for row in rows:
        vertices.extend(diagram_position(mesh.frame, row.element, row.station, value, factor)
                        for value in (row.minimum, row.maximum))
    vertices.append((data.reference_position_m, min(vertex[1] for vertex in vertices) - 0.7))
    point = fitted_coordinates(vertices, (120, 330, 1880, 1190))
    canvas = Image.new("RGB", (2000, 1450), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((80, 35), label + " | Estructura completa", fill=BLUE, font=font(44))
    draw.text((80, 96), group_name or "Resistencia y evento extremo con y sin tablero", fill=GRAY, font=font(36))
    for y, text, color in ((151, f"Minimo global: {minimum.minimum:+.3f} {units} ({minimum.minimum_case})", BLUE),
                           (205, f"Maximo global: {maximum.maximum:+.3f} {units} ({maximum.maximum_case})", RED)):
        words, line, lines = text.split(), "", []
        for word in words:
            candidate = (line + " " + word).strip()
            if line and draw.textlength(candidate, font=font(36)) > 1840:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        for j, line in enumerate(lines):
            draw.text((80, y+37*j), line, fill=color, font=font(36))
    draw_structure(draw, data, mesh, point)
    for points in diagrams:
        for attribute, color, pale in (("minimum", BLUE, "#b0cada"), ("maximum", RED, "#ddbbb6")):
            curve = [point(*diagram_position(mesh.frame, row.element, row.station, getattr(row, attribute), factor))
                     for row in points]
            for row, vertex in zip(points, curve):
                if row.station in (0.0, 0.5, 1.0):
                    draw.line((point(*diagram_position(mesh.frame, row.element, row.station)), vertex), fill=pale, width=1)
            draw.line(curve, fill=color, width=4)
    occupied = []
    groups = (range(mesh.foundation_count - 1), *mesh.side_elements)
    for members in groups:
        group_rows = [row for member in members for row in diagrams[member]]
        for attribute, color, selector in (("minimum", BLUE, min), ("maximum", RED, max)):
            extreme = selector(group_rows, key=lambda row: getattr(row, attribute))
            value = getattr(extreme, attribute)
            if abs(value) < 1e-8:
                value = 0.0
            position = point(*diagram_position(mesh.frame, extreme.element, extreme.station, value, factor))
            annotate_value(draw, position, f"{value:+.2f}", color, occupied)
    draw.text((80, 1240), "Azul: minimo | Rojo: maximo | Gris: geometria y eje FRAME | Resortes: apoyo vertical",
              fill=GRAY, font=font(28))
    scale_note = f"1.00 m de ordenada = {1 / factor:.3f} {units}" if factor else "Esfuerzos nulos"
    draw.text((80, 1280), f"Escala: {scale_note}. Geometria x/y a igual escala. Ux = 0 en x = {data.reference_position_m:.3f} m.",
              fill=GRAY, font=font(28))
    draw.text((80, 1320), "Ordenada positiva: abajo en cimentacion; derecha en pantallas. N positivo a traccion.",
              fill=GRAY, font=font(28))
    draw.text((80, 1360), "Envolvente de los casos indicados. Los extremos pueden proceder de casos distintos y no son simultaneos.",
              fill=GRAY, font=font(28))
    canvas.save(path)
