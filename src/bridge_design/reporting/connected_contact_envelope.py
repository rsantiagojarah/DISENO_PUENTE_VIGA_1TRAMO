"""Pointwise pressure and signed settlement envelopes from solved spring cases."""

from PIL import Image, ImageDraw
from bridge_design.reporting.connected_chart_geometry import BLUE, RED, GREEN, GRAY, font
from bridge_design.reporting.connected_case_groups import case_label


def contact_envelope(result, group):
    cases = [row for row in result.results if row.name in group.cases]
    points = []
    for index, spring in enumerate(result.mesh.frame.springs):
        pressures = [(row.spring_reactions[index]/spring.tributary_area, row.name) for row in cases]
        settlements = [(-1000*row.displacements[3*spring.node+1], row.name) for row in cases]
        pmin, pmax = min(pressures), max(pressures)
        smin, smax = min(settlements), max(settlements)
        points.append(dict(node=spring.node, x=result.mesh.frame.nodes[spring.node].x,
                           q_min=pmin[0], q_max=pmax[0], q_case=pmax[1],
                           s_min=smin[0], s_max=smax[0], s_case=smax[1]))
    return points


def contact_envelope_chart(result, group, path):
    from bridge_design.reporting.connected_charts import panel
    points = contact_envelope(result, group)
    checks = [row for row in result.foundation_checks if row.case in group.cases]
    limits = {round(row.pressure_limit, 9) for row in checks}
    if len(limits) != 1:
        raise ValueError(f"{group.name}: los casos de la familia deben compartir q límite")
    limit = checks[0].pressure_limit
    canvas = Image.new("RGB", (1800, 1120), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((150, 25), f"Envolvente de suelo — {group.name}", fill=BLUE, font=font(32))
    panel(draw, (150, 170, 1710, 440), "Presiones de contacto",
          (("Mínima", BLUE, [(p['x'], p['q_min']) for p in points]),
           ("Máxima", RED, [(p['x'], p['q_max']) for p in points]),
           ("q límite", GREEN, [(points[0]['x'], limit), (points[-1]['x'], limit)])), "x m", "tn/m²")
    panel(draw, (150, 660, 1710, 900), "Asentamientos del suelo",
          (("Mínimo", BLUE, [(p['x'], p['s_min']) for p in points]),
           ("Máximo", RED, [(p['x'], p['s_max']) for p in points])), "x m", "mm")
    critical = max(points, key=lambda p:p['q_max'])
    draw.text((150, 510), f"q máximo = {critical['q_max']:.4f} tn/m² | x = {critical['x']:.3f} m | nudo {critical['node']}",
              fill=GRAY, font=font(24))
    draw.text((150, 550), "Caso gobernante: " + case_label(critical['q_case']), fill=GRAY, font=font(23))
    draw.text((150, 980), "Asentamiento positivo hacia abajo; valores negativos corresponden a levantamiento.",
              fill=GRAY, font=font(24))
    draw.text((150, 1025), "Envolventes punto a punto de todos los casos de la familia, con y sin tablero.",
              fill=GRAY, font=font(23))
    canvas.save(path)
