"""Raster envelope charts embedded in the detailed deck DOCX report."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from bridge_design.reporting.deck_charts import strength_diagram_envelopes

INK = "#153746"
MUTED = "#667985"
RULE = "#AFC0C8"
UPPER = "#155E75"
LOWER = "#984F37"
TEXT = "#000000"


def save_strength_chart(
    result,
    output_path: str | Path,
    *,
    title: str,
    kind: str,
    include_pl: bool,
    transverse: bool = False,
) -> Path:
    """Write a sharp moment or shear envelope chart and return its path."""
    if kind not in {"moment", "shear"}:
        raise ValueError("El tipo de diagrama debe ser 'moment' o 'shear'.")
    diagrams = strength_diagram_envelopes(
        result,
        include_pl=include_pl,
        transverse=transverse,
    )
    upper = diagrams.moment_upper if kind == "moment" else diagrams.shear_upper
    lower = diagrams.moment_lower if kind == "moment" else diagrams.shear_lower
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGB", (1800, 650), "white")
    draw = ImageDraw.Draw(image)
    regular = _font(34)
    small = _font(34)
    bold = _font(34, bold=True)
    left, right, top, bottom = 150, 70, 135, 100
    plot_width = image.width - left - right
    plot_height = image.height - top - bottom
    values = tuple(upper) + tuple(lower or ())
    if not values:
        draw.text((left, top), "No hay muestras disponibles.", font=regular, fill=TEXT)
        image.save(path, dpi=(220, 220))
        return path

    xs = [item[0] for item in values]
    ys = [item[1] for item in values]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(min(ys), 0.0), max(max(ys), 0.0)
    if abs(ymax - ymin) < 1e-12:
        ymin, ymax = -1.0, 1.0

    def sx(value: float) -> float:
        return left + (value - xmin) / max(xmax - xmin, 1e-12) * plot_width

    def sy(value: float) -> float:
        return top + (ymax - value) / (ymax - ymin) * plot_height

    draw.text((70, 42), title, font=bold, fill=TEXT)
    draw.line((left, sy(0.0), left + plot_width, sy(0.0)), fill=RULE, width=3)
    draw.line((left, top, left, top + plot_height), fill=RULE, width=3)
    _polyline(draw, upper, sx, sy, UPPER)
    if lower:
        _polyline(draw, lower, sx, sy, LOWER)

    symbol = "M" if kind == "moment" else "V"
    unit = "Tn.m" if kind == "moment" else "Tn"
    draw.text((70, top - 5), f"{symbol} ({unit})", font=small, fill=TEXT)
    draw.line((left + 40, 100, left + 115, 100), fill=UPPER, width=5)
    draw.text((left + 130, 82), f"{symbol}max - superior", font=small, fill=TEXT)
    if lower:
        draw.line((left + 520, 100, left + 595, 100), fill=LOWER, width=5)
        draw.text((left + 610, 82), f"{symbol}min - inferior", font=small, fill=TEXT)
    draw.text((left, image.height - 70), f"{xmin:.2f}", font=small, fill=TEXT)
    end_label = f"{xmax:.2f} m"
    bbox = draw.textbbox((0, 0), end_label, font=small)
    draw.text((left + plot_width - (bbox[2] - bbox[0]), image.height - 70), end_label, font=small, fill=TEXT)

    upper_extreme = max(upper, key=lambda item: item[1])
    _label_extreme(draw, upper_extreme, sx, sy, small, UPPER, above=True)
    if lower:
        lower_extreme = min(lower, key=lambda item: item[1])
        _label_extreme(draw, lower_extreme, sx, sy, small, LOWER, above=False)
    image.save(path, dpi=(220, 220), optimize=True)
    return path


def _polyline(draw, samples, sx, sy, color: str) -> None:
    points = [(round(sx(x)), round(sy(y))) for x, y in samples]
    if len(points) > 1:
        draw.line(points, fill=color, width=5, joint="curve")


def _label_extreme(draw, sample, sx, sy, font, color: str, *, above: bool) -> None:
    x, value = sample
    label = f"{value:.2f}"
    px, py = sx(x), sy(value)
    bbox = draw.textbbox((0, 0), label, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    label_x = min(max(px - width / 2, 150), 1730 - width)
    label_y = py + 12 if above else py - height - 12
    text_box = draw.textbbox((label_x, label_y), label, font=font)
    draw.rectangle(
        (text_box[0] - 4, text_box[1] - 2, text_box[2] + 4, text_box[3] + 2),
        fill="white",
    )
    draw.text((label_x, label_y), label, font=font, fill=TEXT)


def _font(size: int, *, bold: bool = False):
    candidates = (
        Path("C:/Windows/Fonts/ARIALNB.TTF") if bold else Path("C:/Windows/Fonts/ARIALN.TTF"),
        Path("C:/Windows/Fonts/arialbd.ttf") if bold else Path("C:/Windows/Fonts/arial.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default(size=size)
