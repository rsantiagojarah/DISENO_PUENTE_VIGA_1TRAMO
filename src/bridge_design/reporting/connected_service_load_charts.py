"""Unweighted actions, sampled from the same builders used by the solver."""

from PIL import Image, ImageDraw

from bridge_design.domain.connected_cases import paired_cases
from bridge_design.domain.connected_earth import earth_builder, surcharge_weight
from bridge_design.domain.connected_geometry import global_x
from bridge_design.domain.connected_loads import LoadBuilder, gravity_builders
from bridge_design.domain.frame_elements import element_geometry, polynomial
from bridge_design.domain.wall_friction import _back_x
from bridge_design.reporting.connected_chart_geometry import BLUE, RED, GRAY, GREEN, font, structure_polygons
from bridge_design.reporting.connected_frame_charts import fitted_coordinates
from bridge_design.reporting.connected_report_charts import arrow


def combined(model, parts):
    builder = LoadBuilder(model)
    for part, scale in parts:
        builder.add(part, scale)
    return builder


def global_density(model, index, load, station):
    _, cosine, sine = element_geometry(model, model.elements[index])
    axial, transverse = polynomial(load.axial, station), polynomial(load.transverse, station)
    return (cosine * axial - sine * transverse,
            sine * axial + cosine * transverse, polynomial(load.couple, station))


def action_panels(result):
    """Each entry is a base action, never a factored FRAME combination."""
    data, mesh = result.inputs, result.mesh
    model = mesh.frame
    gravity = gravity_builders(data, mesh)
    merge = lambda parts: combined(model, parts)
    panels = [
        ("DC peso propio del concreto", merge([(gravity[k], 1) for k in ("DC0", "DC1", "DCs")]), False),
        ("EV peso del relleno sobre las zapatas", merge([(gravity[k], 1) for k in ("EV0", "EV1")]), False),
        ("EH empuje estatico en la cara real", merge([(earth_builder(data, mesh, i, "EH"), 1) for i in (0, 1)]), True),
    ]
    # Occupancy multipliers describe the supplied simultaneous condition; they
    # are not LRFD factors. Retain zero/asymmetric occupancy exactly as solved.
    for n, pair in enumerate(paired_cases(data), 1):
        scales = (pair.left_surcharge, pair.right_surcharge)
        for kind, title in (("LS", "LS horizontal"), ("LSv", "LS vertical")):
            parts = [(earth_builder(data, mesh, i, "LS") if kind == "LS" else surcharge_weight(data, mesh, i), scales[i])
                     for i in (0, 1)]
            panels.append((f"{title} / {pair.name}", merge(parts), kind == "LS"))
    return panels


def _panel(draw, result, box, title, builder, face=False):
    left, top, right, bottom = box
    draw.text((left, top), title, fill=BLUE, font=font(36))
    model, mesh, data = result.mesh.frame, result.mesh, result.inputs
    vertices = [v for polygon in structure_polygons(data, mesh) for v in polygon]
    point = fitted_coordinates(vertices, (left + 190, top + 100, right - 190, bottom - 165))
    for polygon in structure_polygons(data, mesh):
        draw.polygon([point(*v) for v in polygon], fill="#edf0f2", outline=GRAY, width=2)
    samples = []
    for index, (element, load) in enumerate(zip(model.elements, builder.distributed)):
        a, b = model.nodes[element.start], model.nodes[element.end]
        group = next((i for i in (0, 1) if index in mesh.side_elements[i]), None)
        row = []
        for step in range(5):
            station = step / 4
            x, z = a.x + station * (b.x - a.x), a.y + station * (b.y - a.y)
            if face and group is not None:
                x = global_x(data, group, _back_x((data.left, data.right)[group].geometry, z))
            row.append((x, z, *global_density(model, index, load, station)))
        samples.append(row)
    peaks = [max(1e-9, *(abs(v[2 + component]) for row in samples for v in row)) for component in (0, 1)]
    # Connect ordinates within each element, preserving jumps at section changes.
    for row in samples:
        for component, color in ((0, BLUE), (1, RED)):
            if max(abs(v[2 + component]) for v in row) < 1e-8:
                continue
            tips, tails = [], []
            for x, z, fx, fz, couple in row:
                tip = point(x, z)
                value = (fx, fz)[component]
                offset = value / peaks[component] * 110
                tail = (tip[0] - offset, tip[1]) if component == 0 else (tip[0], tip[1] + offset)
                tips.append(tip)
                tails.append(tail)
            draw.polygon(tips + list(reversed(tails)), fill="#e4eef7" if component == 0 else "#fae9e6")
            draw.line(tails, fill=color, width=3)
            # One arrow per element; the continuous outline shows the full shape.
            arrow(draw, tails[2], tips[2], color)
    for index, node in enumerate(model.nodes):
        fx, fz, moment = builder.nodal[3 * index:3 * index + 3]
        tip = point(node.x, node.y)
        for value, color, horizontal in ((fx, BLUE, True), (fz, RED, False)):
            if abs(value) > 1e-8:
                shift = 40 if value > 0 else -40
                tail = (tip[0] - shift, tip[1]) if horizontal else (tip[0], tip[1] + shift)
                arrow(draw, tail, tip, color)
        if abs(moment) > 1e-8:
            draw.arc((tip[0]-12, tip[1]-12, tip[0]+12, tip[1]+12), 30, 320, fill=GREEN, width=2)
    for side_index, label in ((0, "Izq."), (1, "Der.")):
        indices = mesh.side_elements[side_index] if face else range(len(model.elements))
        values = [v for i in indices for v in samples[i]
                  if (face or (v[0] <= data.total_length_m/2) == (side_index == 0))]
        fx = [v[2] for v in values] or [0]
        fz = [v[3] for v in values] or [0]
        draw.text((left, bottom - 120 + side_index * 34),
                  f"{label} qx={min(fx):+.3f} a {max(fx):+.3f}; qz={min(fz):+.3f} a {max(fz):+.3f} tn/m",
                  fill=GRAY, font=font(32))
    couples = [v[4] for row in samples for v in row]
    nodal_m = builder.nodal[2::3]
    draw.text((left, bottom - 48),
              f"m distribuido={min(couples):+.3f} a {max(couples):+.3f} tn m/m; M nodal={min(nodal_m):+.3f} a {max(nodal_m):+.3f} tn m",
              fill=GREEN, font=font(30))


def save_action_chart(result, path, panels, title="Cargas iniciales sin factorizar"):
    canvas = Image.new("RGB", (2000, 180 + 1010 * len(panels)), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((70, 24), title, fill=BLUE, font=font(43))
    draw.text((70, 83), "Franja 1 m | Azul Fx hacia +x | Rojo Fz hacia +z | Verde momentos equivalentes", fill=GRAY, font=font(32))
    draw.text((70, 126), "Perfiles proporcionales por componente y panel; fuerzas nodales simbolicas. Valores con signo.", fill=GRAY, font=font(32))
    for index, (label, builder, face) in enumerate(panels):
        _panel(draw, result, (70, 185 + index*1010, 1930, 1185 + index*1010), label, builder, face)
    canvas.save(path)


def save_service_load_charts(result, destination):
    panels = action_panels(result)
    paths = {"cargas": destination / "cargas.png", "cargas_pesos": destination / "cargas_pesos.png"}
    save_action_chart(result, paths["cargas"], [panels[2]], "Empuje estatico sin factorizar")
    save_action_chart(result, paths["cargas_pesos"], panels[:2])
    for index, pair in enumerate(paired_cases(result.inputs), 1):
        key = f"cargas_sobrecarga_{index}"
        paths[key] = destination / f"{key}.png"
        save_action_chart(result, paths[key], panels[3 + 2*(index-1):5 + 2*(index-1)])
        key = f"cargas_tablero_{index}"
        paths[key] = destination / f"{key}.png"
        bridge_action_chart(result, pair, paths[key])
    for direction in (-1, 1):
        for kind in ("A", "B"):
            key = f"cargas_sismo_{kind}_{'menos' if direction < 0 else 'mas'}"
            paths[key] = destination / f"{key}.png"
            builder = combined(result.mesh.frame, [(earth_builder(result.inputs, result.mesh, i, kind, direction), 1) for i in (0, 1)])
            save_action_chart(result, paths[key], [(f"Empuje {kind} EQ{direction:+d} / perfil completo adoptado", builder, True)],
                              "Empuje sismico base sin ponderacion LRFD")
    gravity = gravity_builders(result.inputs, result.mesh)
    key = "cargas_inercia"
    paths[key] = destination / f"{key}.png"
    save_action_chart(result, paths[key], [("PIR sentido +x / antes del coeficiente de alternativa A o B",
                      combined(result.mesh.frame, [(gravity[k], 1) for k in ("PIR0", "PIR1", "PIRs")]), False)])
    return paths


def bridge_action_chart(result, pair, path):
    data, mesh = result.inputs, result.mesh
    vertices = [v for polygon in structure_polygons(data, mesh) for v in polygon]
    canvas = Image.new("RGB", (2000, 1400), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((70, 25), "Reacciones del tablero sin factorizar", fill=BLUE, font=font(43))
    draw.text((70, 85), pair.name, fill=GRAY, font=font(29))
    point = fitted_coordinates(vertices + [(0, max(s.geometry.stem_height_above_footing_m + s.geometry.bridge_seat_to_bearing_height_m for s in (data.left, data.right)))],
                               (260, 190, 1740, 1100))
    for polygon in structure_polygons(data, mesh):
        draw.polygon([point(*v) for v in polygon], fill="#edf0f2", outline=GRAY, width=2)
    for index, (side, loads) in enumerate(zip((data.left, data.right), (pair.left, pair.right))):
        g = side.geometry
        x = global_x(data, index, g.superstructure_load_x_m)
        z = g.stem_height_above_footing_m - g.seat_block_height_m
        vertical = loads.pdc_tn_m + loads.pdw_tn_m + loads.pll_im_tn_m + loads.ppl_tn_m
        tip = point(x, z)
        if vertical:
            arrow(draw, (tip[0], tip[1]-95), tip, RED)
        z_br = g.stem_height_above_footing_m + g.bridge_seat_to_bearing_height_m
        z_eq = g.stem_height_above_footing_m - g.seat_block_height_m/2
        for value, level, color, label in ((loads.braking_tn_m, z_br, BLUE, "BR"),
                ((loads.pdc_tn_m+loads.pdw_tn_m)*side.soil.pga*side.soil.fpga, z_eq, GREEN, "PEQ")):
            location = point(x, level)
            if value:
                arrow(draw, (location[0]-85, location[1]), location, color)
            draw.text((location[0] + (20 if index == 0 else -200), location[1]-30), f"{label}={value:.3f}", fill=color, font=font(27))
        column = 70 + index*970
        draw.text((column, 1140), f"{'Izquierda' if index == 0 else 'Derecha'}: x={x:.3f} m; z apoyo={z:.3f} m", fill=GRAY, font=font(32))
        draw.text((column, 1182), f"DC={loads.pdc_tn_m:.3f}; DW={loads.pdw_tn_m:.3f} tn", fill=RED, font=font(32))
        draw.text((column, 1224), f"LL+IM={loads.pll_im_tn_m:.3f}; PL={loads.ppl_tn_m:.3f} tn", fill=RED, font=font(32))
        draw.text((column, 1266), f"z BR={z_br:.3f} m; z PEQ={z_eq:.3f} m", fill=GRAY, font=font(32))
    draw.text((70, 1330), "Flechas simbolicas | BR y PEQ se revisan tambien hacia -x | PEQ solo en evento sismico", fill=GRAY, font=font(32))
    canvas.save(path)
