"""Applied loads, service nodal deformation and adopted reinforcement sketches."""

from math import hypot, ceil
from PIL import Image, ImageDraw

from bridge_design.reporting.connected_case_groups import case_label
from bridge_design.reporting.connected_chart_geometry import BLUE, RED, GRAY, GREEN, draw_structure, font
from bridge_design.reporting.connected_frame_charts import fitted_coordinates, structure_polygons


def arrow(draw, first, last, color):
    draw.line((first, last), fill=color, width=3)
    dx, dy = last[0]-first[0], last[1]-first[1]
    length = hypot(dx, dy)
    if length < 1e-6:
        return
    ux, uy = dx/length, dy/length
    draw.polygon((last, (last[0]-12*ux+5*uy, last[1]-12*uy-5*ux),
                  (last[0]-12*ux-5*uy, last[1]-12*uy+5*ux)), fill=color)


def load_chart(result, path):
    """Static base earth action, without LRFD factors."""
    from bridge_design.reporting.connected_service_load_charts import action_panels, save_action_chart
    save_action_chart(result, path, [action_panels(result)[2]], "Empuje estatico sin factorizar")


def deformation_chart(result, path):
    services = [r for r in result.results if r.limit_state == "service"]
    row = max(services, key=lambda r:max(abs(u) for u in r.displacements[1::3]))
    model = result.mesh.frame
    peak = max(1e-12, *(hypot(row.displacements[3*i], row.displacements[3*i+1]) for i in range(len(model.nodes))))
    factor = .07*result.inputs.total_length_m/peak
    moved = [(n.x+factor*row.displacements[3*i], n.y+factor*row.displacements[3*i+1]) for i, n in enumerate(model.nodes)]
    vertices = [v for polygon in structure_polygons(result.inputs, result.mesh) for v in polygon]+moved
    point = fitted_coordinates(vertices, (170, 250, 1830, 1180))
    canvas = Image.new("RGB", (2000, 1450), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((80, 35), "Deformada nodal en servicio", font=font(44), fill=BLUE)
    draw.text((80, 95), case_label(row.name), font=font(27), fill=GRAY)
    draw.text((80, 140), f"Amplificación {factor:.1f} veces | Gris geometría inicial | Rojo deformada", font=font(27), fill=GRAY)
    draw_structure(draw, result.inputs, result.mesh, point)
    for element in model.elements:
        draw.line((point(*moved[element.start]), point(*moved[element.end])), fill=RED, width=4)
    draw.text((80, 1260), "Representación de desplazamientos de nudos; líneas rectas entre nudos sin interpolación de curvatura.",
              fill=GRAY, font=font(25))
    draw.text((80, 1305), f"Desplazamiento vectorial máximo {peak*1000:.4f} mm. Los giros se conservan en nodos.csv.",
              fill=GRAY, font=font(25))
    canvas.save(path)


def reinforcement_chart(result, path):
    rows = ceil(len(result.reinforcement)/2)
    canvas = Image.new("RGB", (2000, 180+rows*230), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((80, 30), "Armadura adoptada por cara", font=font(44), fill=BLUE)
    draw.text((80, 90), "Esquemas de panel sin escala | Ambas caras iguales | Sin doblados ni empalmes", font=font(27), fill=GRAY)
    for i, steel in enumerate(result.reinforcement):
        x, y = 80+(i%2)*970, 170+(i//2)*230
        draw.text((x, y), steel.region, fill=BLUE, font=font(30))
        draw.rectangle((x, y+50, x+220, y+170), outline=GRAY, width=2)
        for line in range(6):
            draw.line((x+20+36*line, y+60, x+20+36*line, y+160), fill=RED, width=3)
        for line in range(4):
            draw.line((x+10, y+65+28*line, x+210, y+65+28*line), fill=GREEN, width=2)
        draw.text((x+250, y+55), f"Principal {steel.bar_label} @ {steel.spacing_m:.3f} m", fill=RED, font=font(26))
        draw.text((x+250, y+95), f"Transversal {steel.transverse_bar_label} @ {steel.transverse_spacing_m:.3f} m", fill=GREEN, font=font(26))
        draw.text((x+250, y+135), f"As por cara {steel.area_per_face_cm2_m:.3f} cm2/m", fill=GRAY, font=font(26))
    canvas.save(path)
