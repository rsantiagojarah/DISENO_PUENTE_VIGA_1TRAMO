"""Technical raster diagrams for the detailed abutment Word report."""

from __future__ import annotations

from pathlib import Path
from math import cos, radians, sin

from PIL import Image, ImageDraw, ImageFont

from bridge_design.domain.abutment import (
    AbutmentDesignResult,
    AbutmentInputs,
    StabilityStateResult,
    _stem_thickness_at_height_m,
    wall_backface_setback_m,
)
from bridge_design.domain.wall_friction import _back_x

INK = "#000000"
ACCENT = "#155E75"
RULE = "#AFC0C8"
CONCRETE = "#E6E9EB"
SOIL = "#F3E8D2"
PRESSURE = "#DCECF0"


def abutment_stem_faces(inputs: AbutmentInputs) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Front and back faces, ascending from the footing top, in meters from the toe."""
    geometry = inputs.geometry
    height = geometry.stem_height_above_footing_m
    body = height - geometry.seat_block_height_m - geometry.backwall_drop_m
    levels = sorted({
        0.0,
        body - geometry.backwall_taper_height_m,
        body,
        height - geometry.seat_block_height_m,
        height,
    })
    back_face: list[tuple[float, float]] = []
    front_face: list[tuple[float, float]] = []
    for level in levels:
        bounded = min(max(level, 0.0), height)
        for shift in (-1e-7, 1e-7):
            sample = min(max(bounded + shift, 0.0), height)
            back = _back_x(geometry, sample)
            front = back - _stem_thickness_at_height_m(inputs, sample)
            elevation = geometry.footing_thickness_m + sample
            back_face.append((back, elevation))
            front_face.append((front, elevation))
    return _without_repeated_points(front_face), _without_repeated_points(back_face)


def abutment_stem_outline(inputs: AbutmentInputs) -> list[tuple[float, float]]:
    """Closed stem outline in meters, from the toe edge and the footing bottom.

    Vertices follow the same back face and thickness used by the abutment model,
    including the front batter, the backfill step, the seat block and the parapet.
    """
    front_face, back_face = abutment_stem_faces(inputs)
    return _without_repeated_points([front_face[0], *back_face, *reversed(front_face)])


def _without_repeated_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cleaned: list[tuple[float, float]] = []
    for point in points:
        if cleaned and abs(cleaned[-1][0] - point[0]) <= 1e-6 and abs(cleaned[-1][1] - point[1]) <= 1e-6:
            continue
        cleaned.append(point)
    if len(cleaned) > 1 and abs(cleaned[0][0] - cleaned[-1][0]) <= 1e-6 and abs(cleaned[0][1] - cleaned[-1][1]) <= 1e-6:
        cleaned.pop()
    return cleaned


def save_abutment_geometry(result: AbutmentDesignResult, output_path: str | Path) -> Path:
    """Draw the adopted abutment cross-section and its principal dimensions."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1800, 980), "white")
    draw = ImageDraw.Draw(image)
    regular = _font(31)
    small = _font(27)
    bold = _font(34, bold=True)
    g = result.inputs.geometry

    draw.text(
        (70, 35),
        "Sección transversal adoptada del muro"
        if result.inputs.is_pure_wall
        else "Sección transversal adoptada del estribo",
        font=bold,
        fill=INK,
    )
    left, right, top, base = 170, 1620, 145, 760
    width = right - left
    height = base - top

    def sx(value: float) -> float:
        return left + value / g.footing_width_m * width

    def sy(value: float) -> float:
        return base - value / g.retained_height_m * height

    footing_top = sy(g.footing_thickness_m)
    draw.rectangle((left, footing_top, right, base), fill=CONCRETE, outline=INK, width=4)
    stem_left_base = sx(g.toe_length_m)
    stem_right_base = sx(g.toe_length_m + g.lower_stem_thickness_m)
    if result.inputs.is_pure_wall:
        stem_left_top = sx(g.toe_length_m + g.lower_stem_thickness_m - g.upper_stem_thickness_m)
        setback = wall_backface_setback_m(g, result.inputs.soil.wall_backface_angle_deg)
        stem_left_top -= setback / g.footing_width_m * width
        stem_right_top = stem_right_base - setback / g.footing_width_m * width
        stem = [
            (stem_left_base, footing_top),
            (stem_right_base, footing_top),
            (stem_right_top, sy(g.retained_height_m)),
            (stem_left_top, sy(g.retained_height_m)),
        ]
        draw.polygon(stem, fill=CONCRETE, outline=INK)
        draw.line(stem + [stem[0]], fill=INK, width=4)
        soil_left = stem_right_top
        draw.polygon(
            [
                (soil_left, sy(g.retained_height_m)),
                (right, sy(g.retained_height_m)),
                (right, footing_top),
                (stem_right_base, footing_top),
            ],
            fill=SOIL,
            outline=RULE,
        )
        draw.text((sx(g.toe_length_m + g.lower_stem_thickness_m + g.heel_length_m / 2) - 80, top + 55), "Relleno", font=regular, fill=INK)
        draw.text((stem_left_top - 145, top + 75), "Pantalla", font=small, fill=INK)
    else:
        setback = 0.0
        front_face, back_face = abutment_stem_faces(result.inputs)
        outline = _without_repeated_points([front_face[0], *back_face, *reversed(front_face)])
        stem = [(sx(x), sy(y)) for x, y in outline]
        crown = back_face[-1]
        soil = (
            [(sx(x), sy(y)) for x, y in reversed(back_face)]
            + [(right, footing_top), (right, sy(g.retained_height_m))]
        )
        draw.polygon(soil, fill=SOIL, outline=RULE)
        draw.polygon(stem, fill=CONCRETE, outline=INK)
        draw.line(stem + [stem[0]], fill=INK, width=4)
        draw.text((sx((crown[0] + g.footing_width_m) / 2) - 50, top + 55), "Relleno", font=regular, fill=INK)
        stem_mid = g.stem_height_above_footing_m * 0.35
        screen_front = sx(_back_x(g, stem_mid) - _stem_thickness_at_height_m(result.inputs, stem_mid))
        draw.text((screen_front - 145, sy(g.footing_thickness_m + stem_mid)), "Pantalla", font=small, fill=INK)
    if g.toe_length_m > 0.0:
        draw.text((left + 15, footing_top + 25), "Puntera", font=small, fill=INK)
    draw.text((sx(g.toe_length_m + g.lower_stem_thickness_m) + 20, footing_top + 25), "Talón", font=small, fill=INK)

    if result.key is not None:
        key_center = (stem_left_base + stem_right_base) / 2.0
        key_half = max(result.inputs.key.width_m * width / g.footing_width_m / 2.0, 28)
        key_depth = result.inputs.key.height_m / g.retained_height_m * height
        draw.rectangle(
            (key_center - key_half, base, key_center + key_half, base + key_depth),
            fill=CONCRETE,
            outline=INK,
            width=4,
        )
        draw.text((key_center + key_half + 12, base + 8), "Dentellón", font=small, fill=INK)

    _dimension(draw, (left, 890), (right, 890), f"B = {g.footing_width_m:.2f} m", regular, horizontal=True)
    _dimension(draw, (105, base), (105, top), f"H = {g.retained_height_m:.2f} m", regular, horizontal=False)
    if g.toe_length_m > 0.0:
        _dimension(draw, (left, 835), (stem_left_base, 835), f"Lp = {g.toe_length_m:.2f} m", small, horizontal=True)
    else:
        draw.text((left, 800), "Sin puntera (Lp = 0.00 m)", font=small, fill=INK)
    _dimension(draw, (stem_right_base, 835), (right, 835), f"Lt = {g.heel_length_m:.2f} m", small, horizontal=True)

    alpha = radians(result.pressures.stem_force_angle_deg)
    for index in range(7):
        y = top + 70 + index * (footing_top - top - 140) / 6
        fraction = (footing_top - y) / (footing_top - top)
        if result.inputs.is_pure_wall:
            pressure_x = stem_right_base - fraction * setback / g.footing_width_m * width + 8
        else:
            model_y = (base - y) / height * g.retained_height_m
            above_footing = min(max(model_y - g.footing_thickness_m, 0.0), g.stem_height_above_footing_m)
            pressure_x = sx(_back_x(g, above_footing)) + 8
        length = 45 + index * 16
        dx, dy = length * cos(alpha), -length * sin(alpha) * (height / g.retained_height_m) / (width / g.footing_width_m)
        draw.line((pressure_x + dx, y + dy, pressure_x, y), fill=ACCENT, width=4)
        draw.polygon([(pressure_x, y), (pressure_x + 14, y - 8), (pressure_x + 14, y + 8)], fill=ACCENT)
    pressure_label_x = stem_right_base + 160
    if not result.inputs.is_pure_wall:
        pressure_label_x = sx(_back_x(g, g.stem_height_above_footing_m * 0.55)) + 24
    draw.text((pressure_label_x, top + height / 2 + 40), "Empuje sobre pantalla", font=small, fill=ACCENT)
    if result.inputs.is_pure_wall:
        draw.text((70, 85), f"Trasdós real: θ = {result.inputs.soil.wall_backface_angle_deg:.4f}°; relleno a la derecha", font=small, fill=INK)
    image.save(path, dpi=(220, 220), optimize=True)
    return path


def save_contact_pressure_diagrams(
    result: AbutmentDesignResult,
    output_path: str | Path,
) -> Path:
    """Draw the structural contact-pressure diagrams for the bridge-present states."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1800, 1050), "white")
    draw = ImageDraw.Draw(image)
    regular = _font(29)
    small = _font(25)
    bold = _font(34, bold=True)
    if result.inputs.is_pure_wall:
        states = result.without_bridge + result.service_without_bridge
        chart_title = "Diagramas de presión de contacto - condición del muro"
    else:
        states = result.with_bridge + result.service_with_bridge
        chart_title = "Diagramas de presión de contacto - condición con puente"
    draw.text((70, 35), chart_title, font=bold, fill=INK)
    boxes = ((80, 130, 860, 540), (940, 130, 1720, 540), (80, 600, 860, 1010), (940, 600, 1720, 1010))
    for state, box in zip(states, boxes):
        _draw_pressure_panel(draw, state, result.inputs.geometry.footing_width_m, box, regular, small)
    image.save(path, dpi=(220, 220), optimize=True)
    return path


def _draw_pressure_panel(draw, state: StabilityStateResult, footing_width_m: float, box, regular, small) -> None:
    x0, y0, x1, y1 = box
    draw.rectangle(box, outline=RULE, width=3)
    draw.text((x0 + 22, y0 + 18), state.name, font=regular, fill=INK)
    baseline_y = y1 - 75
    left = x0 + 65
    right = x1 - 45
    draw.line((left, baseline_y, right, baseline_y), fill=INK, width=4)
    draw.text((left, baseline_y + 18), "0.00", font=small, fill=INK)
    end = f"{footing_width_m:.2f} m"
    end_box = draw.textbbox((0, 0), end, font=small)
    draw.text((right - (end_box[2] - end_box[0]), baseline_y + 18), end, font=small, fill=INK)
    qmax = max(state.qmax_kg_cm2, 1e-9)
    max_height = 205
    qmin_height = max_height * max(state.qmin_kg_cm2, 0.0) / qmax
    if state.contact_type == "Completo":
        polygon = [(left, baseline_y), (left, baseline_y - max_height), (right, baseline_y - qmin_height), (right, baseline_y)]
    elif state.resultant_x_m <= footing_width_m / 2.0:
        contact_right = left + (right - left) * state.contact_length_m / footing_width_m
        polygon = [(left, baseline_y), (left, baseline_y - max_height), (contact_right, baseline_y)]
    else:
        contact_left = right - (right - left) * state.contact_length_m / footing_width_m
        polygon = [(contact_left, baseline_y), (right, baseline_y - max_height), (right, baseline_y)]
    draw.polygon(polygon, fill=PRESSURE, outline=ACCENT)
    draw.line(polygon + [polygon[0]], fill=ACCENT, width=4)
    draw.text((left, baseline_y - max_height - 38), f"qmax = {state.qmax_kg_cm2:.3f} kg/cm²", font=small, fill=INK)
    draw.text((left, baseline_y - max_height + 4), f"qmin = {state.qmin_kg_cm2:.3f} kg/cm²", font=small, fill=INK)
    draw.text((left, y1 - 35), f"Contacto: {state.contact_type}; Lc/B = {state.contact_length_ratio:.3f}", font=small, fill=INK)


def _dimension(draw, start, end, label: str, font, *, horizontal: bool) -> None:
    draw.line((*start, *end), fill=INK, width=3)
    if horizontal:
        for x, y, direction in ((start[0], start[1], 1), (end[0], end[1], -1)):
            draw.polygon([(x, y), (x + 14 * direction, y - 8), (x + 14 * direction, y + 8)], fill=INK)
        bbox = draw.textbbox((0, 0), label, font=font)
        draw.text(((start[0] + end[0] - (bbox[2] - bbox[0])) / 2, start[1] - 42), label, font=font, fill=INK)
    else:
        for x, y, direction in ((start[0], start[1], -1), (end[0], end[1], 1)):
            draw.polygon([(x, y), (x - 8, y + 14 * direction), (x + 8, y + 14 * direction)], fill=INK)
        draw.text((start[0] - 72, (start[1] + end[1]) / 2 - 18), label, font=font, fill=INK)


def _font(size: int, *, bold: bool = False):
    candidates = (
        Path("C:/Windows/Fonts/ARIALNB.TTF") if bold else Path("C:/Windows/Fonts/ARIALN.TTF"),
        Path("C:/Windows/Fonts/arialbd.ttf") if bold else Path("C:/Windows/Fonts/arial.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default(size=size)
