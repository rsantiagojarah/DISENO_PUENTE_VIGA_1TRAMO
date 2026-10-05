"""Export geometry and signed N,V,M/contact diagrams using Pillow."""

from pathlib import Path

from PIL import Image, ImageDraw

from bridge_design.reporting.connected_chart_geometry import BLUE, RED, GRAY, GREEN, draw_structure, font
from bridge_design.reporting.connected_frame_charts import frame_envelope_chart
from bridge_design.reporting.connected_report_charts import deformation_chart, reinforcement_chart
from bridge_design.reporting.connected_case_groups import combination_groups, foundation_combination_groups
from bridge_design.reporting.connected_contact_envelope import contact_envelope_chart
from bridge_design.reporting.connected_service_load_charts import save_service_load_charts


def panel(draw, box, title, series, x_label, y_label, limits=None):
    left, top, right, bottom = box
    positions = [point[0] for _label, _color, points in series for point in points]
    values = [point[1] for _label, _color, points in series for point in points]
    minimum_x, maximum_x = min(positions), max(positions)
    minimum_y, maximum_y = min(0.0, min(values)), max(0.0, max(values))
    if limits:
        minimum_y, maximum_y = min(minimum_y, limits[0]), max(maximum_y, limits[1])
    span_y = max(1e-6, maximum_y - minimum_y)
    minimum_y -= 0.08 * span_y
    maximum_y += 0.08 * span_y
    if maximum_x == minimum_x:
        maximum_x = minimum_x + 1

    def coordinates(position, value):
        return (left + (position - minimum_x) / (maximum_x - minimum_x) * (right - left),
                bottom - (value - minimum_y) / (maximum_y - minimum_y) * (bottom - top))

    draw.text((left, top - 48), title, font=font(30), fill=BLUE)
    for index in range(6):
        position = minimum_x + (maximum_x - minimum_x) * index / 5
        coordinate = coordinates(position, 0)[0]
        draw.line((coordinate, top, coordinate, bottom), fill="#e1e5e8", width=1)
        draw.text((coordinate - 20, bottom + 12), f"{position:.2f}", fill=GRAY, font=font(19))
        value = minimum_y + (maximum_y - minimum_y) * index / 5
        vertical = coordinates(minimum_x, value)[1]
        draw.line((left, vertical, right, vertical), fill="#e1e5e8", width=1)
        draw.text((left - 95, vertical - 10), f"{value:.2f}", fill=GRAY, font=font(19))
    draw.rectangle((left, top, right, bottom), outline=GRAY, width=2)
    zero = coordinates(minimum_x, 0)[1]
    draw.line((left, zero, right, zero), fill="#909aa2", width=2)
    for label, color, points in series:
        draw.line([coordinates(position, value) for position, value in points], fill=color, width=3)
    legend = left
    for label, color, _points in series:
        draw.text((legend, top - 17), label, fill=color, font=font(18))
        legend += int(draw.textlength(label, font=font(18))) + 36
    draw.text((right - 130, bottom + 45), x_label, fill=GRAY, font=font(20))
    draw.text((left - 94, top - 46), y_label, fill=GRAY, font=font(18))


def geometry_chart(result, path):
    data, mesh = result.inputs, result.mesh
    maximum_height = max(data.left.geometry.stem_height_above_footing_m,
                         data.right.geometry.stem_height_above_footing_m)
    scale = min(1480 / data.total_length_m, 660 / (maximum_height + 2))
    maximum_footing = max(data.left.geometry.footing_thickness_m, data.right.geometry.footing_thickness_m)
    base_y = 190 + maximum_height * scale
    canvas_height = int(base_y + maximum_footing * scale + 170)
    canvas = Image.new("RGB", (1800, canvas_height), "white")
    draw = ImageDraw.Draw(canvas)

    def point(position, height):
        return 130 + position * scale, base_y - height * scale

    draw.text((95, 40), "Estribos conectados con cimentacion continua", fill=BLUE, font=font(42))
    draw.text((95, 100), f"Franja 1.00 m | ks = {data.soil.subgrade_tn_m3:g} Tn/m3 | "
              f"{len(mesh.frame.springs)} resortes | Empuje activo en ambos lados",
              fill=GRAY, font=font(26))
    draw_structure(draw, data, mesh, point, axis_color=BLUE)
    horizontal, vertical = point(data.reference_position_m, 0)
    draw.ellipse((horizontal - 7, vertical - 7, horizontal + 7, vertical + 7), fill=RED)
    draw.text((horizontal - 85, vertical - 44), "Ux = 0", font=font(26), fill=RED)
    draw.text((100, canvas_height - 92), f"Longitud total = {data.total_length_m:.3f} m | Separacion libre = {data.clear_span_m:.3f} m | "
              f"Nodo de referencia x = {data.reference_position_m:.3f} m", fill=GRAY, font=font(25))
    draw.text((100, canvas_height - 50), "Linea azul: eje de referencia. Cimentacion con Uy sobre resortes y giro libre. Tablero aplicado como cargas.",
              fill=GRAY, font=font(23))
    canvas.save(path)


def contact_chart(result, path):
    canvas = Image.new("RGB", (1800, 960), "white")
    draw = ImageDraw.Draw(canvas)
    positions = [result.mesh.frame.nodes[spring.node].x for spring in result.mesh.frame.springs]
    service = [case for case in result.results if case.limit_state == "service"]
    minimum, maximum, settlement = [], [], []
    for index, (position, spring) in enumerate(zip(positions, result.mesh.frame.springs)):
        pressures = [case.spring_reactions[index] / spring.tributary_area for case in service]
        minimum.append((position, min(pressures)))
        maximum.append((position, max(pressures)))
        settlement.append((position, max(-1000 * case.displacements[3 * spring.node + 1] for case in service)))
    allowable = [(positions[0], result.inputs.soil.allowable_tn_m2), (positions[-1], result.inputs.soil.allowable_tn_m2)]
    panel(draw, (150, 110, 1710, 410), "Presiones de contacto en Servicio I",
          (("Minima", BLUE, minimum), ("Maxima", RED, maximum), ("Admisible", GREEN, allowable)), "x m", "Tn/m2")
    panel(draw, (150, 600, 1710, 850), "Envolvente de asentamientos en Servicio I",
          (("Asentamiento positivo hacia abajo", BLUE, settlement),), "x m", "mm")
    canvas.save(path)


def save_connected_charts(result, directory):
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {name: destination / f"{name}.png" for name in ("geometria", "contacto", "modelo_axial", "modelo_cortante", "modelo_momento",
                                                         "cargas", "deformada", "armado")}
    geometry_chart(result, paths["geometria"])
    contact_chart(result, paths["contacto"])
    for field, name in (("axial", "modelo_axial"), ("shear", "modelo_cortante"), ("moment", "modelo_momento")):
        frame_envelope_chart(result, field, paths[name], tuple(case.name for case in result.results),
                             "Envolvente general de todas las combinaciones")
    paths.update(save_service_load_charts(result, destination))
    deformation_chart(result, paths["deformada"])
    reinforcement_chart(result, paths["armado"])
    for index, group in enumerate(combination_groups(result), 1):
        for field in ("axial", "shear", "moment"):
            key = f"envolvente_{index}_{field}"
            paths[key] = destination / (key + ".png")
            frame_envelope_chart(result, field, paths[key], group.cases, group.name)
    for index, group in enumerate(foundation_combination_groups(result), 1):
        key = f"contacto_envolvente_{index}"
        paths[key] = destination / (key + ".png")
        contact_envelope_chart(result, group, paths[key])
    return paths
