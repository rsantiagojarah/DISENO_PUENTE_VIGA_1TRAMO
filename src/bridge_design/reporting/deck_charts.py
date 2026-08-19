"""Design-envelope diagrams for the deck PDF report."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from reportlab.graphics.shapes import Drawing, Line, PolyLine, String
from reportlab.lib import colors
from reportlab.lib.units import mm

from bridge_design.domain.load_combinations import LoadFactor
from bridge_design.domain.sampling import interpolate_sorted_samples
from bridge_design.reporting.pdf_style import ACCENT, INK, MUTED, RULE, register_arial_narrow

Sample = tuple[float, float]

UPPER_ENVELOPE = ACCENT
LOWER_ENVELOPE = colors.HexColor("#8A4F3D")
STRENGTH_DC = LoadFactor(1.25, 0.90)
STRENGTH_DW = LoadFactor(1.50, 0.65)
STRENGTH_VARIABLE = LoadFactor(1.75, omit_when_favorable=True)


@dataclass(frozen=True)
class StrengthEnvelopeDiagrams:
    """Factored upper and lower diagram series for one component."""

    moment_upper: tuple[Sample, ...]
    moment_lower: tuple[Sample, ...] | None
    shear_upper: tuple[Sample, ...]
    shear_lower: tuple[Sample, ...] | None


def _sample_at(samples: tuple[Sample, ...], position: float) -> float:
    return interpolate_sorted_samples(samples, position)


def strength_envelopes(
    result,
    *,
    include_pl: bool,
    transverse: bool = False,
) -> tuple[tuple[Sample, ...], tuple[Sample, ...]]:
    """Return upper Strength I moment and shear envelopes."""
    diagrams = strength_diagram_envelopes(
        result,
        include_pl=include_pl,
        transverse=transverse,
    )
    return diagrams.moment_upper, diagrams.shear_upper


def strength_moment_envelopes(
    result,
    *,
    include_pl: bool,
    transverse: bool = False,
) -> tuple[tuple[Sample, ...], tuple[Sample, ...] | None, tuple[Sample, ...]]:
    """Compatibility wrapper returning moment pairs and upper shear."""
    diagrams = strength_diagram_envelopes(
        result,
        include_pl=include_pl,
        transverse=transverse,
    )
    return diagrams.moment_upper, diagrams.moment_lower, diagrams.shear_upper


def strength_diagram_envelopes(
    result,
    *,
    include_pl: bool,
    transverse: bool = False,
) -> StrengthEnvelopeDiagrams:
    """Return separate upper/lower Strength I moment and shear envelopes."""
    try:
        hash(result)
    except TypeError:
        return _build_strength_diagram_envelopes(result, include_pl, transverse)
    return _cached_strength_diagram_envelopes(result, include_pl, transverse)


@lru_cache(maxsize=8)
def _cached_strength_diagram_envelopes(
    result,
    include_pl: bool,
    transverse: bool,
) -> StrengthEnvelopeDiagrams:
    return _build_strength_diagram_envelopes(result, include_pl, transverse)


def _build_strength_diagram_envelopes(
    result,
    include_pl: bool,
    transverse: bool,
) -> StrengthEnvelopeDiagrams:
    cases = [result.dc, result.dw]
    if include_pl:
        cases.append(result.pl)
    cases.append(result.ll_im_envelope)
    ll_case = result.ll_im_envelope
    upper_ll = _moment_samples_for_target(ll_case, "max")
    lower_ll = _moment_samples_for_target(ll_case, "min")
    positions = sorted(
        {x for case in cases for x, _ in case.moment_samples_tn_m}
        | {x for x, _ in upper_ll}
        | {x for x, _ in lower_ll}
    )
    has_lower_moment = _has_lower_moment_envelope(ll_case)
    moment_upper: list[Sample] = []
    moment_lower: list[Sample] = []
    for x in positions:
        moment_upper.append(
            (x, _strength_effect_at(result, x, upper_ll, "max", include_pl, "moment_samples_tn_m"))
        )
        if has_lower_moment:
            moment_lower.append(
                (x, _strength_effect_at(result, x, lower_ll, "min", include_pl, "moment_samples_tn_m"))
            )

    shear_upper: list[Sample] = []
    shear_lower: list[Sample] = []
    shear_cases = [
        case
        for case in cases
        if getattr(case, "shear_samples_tn", ())
    ]
    has_lower_shear = bool(shear_cases) and _has_lower_shear_envelope(ll_case)
    if shear_cases:
        upper_ll_shear = _shear_samples_for_target(ll_case, "max")
        lower_ll_shear = _shear_samples_for_target(ll_case, "min")
        shear_positions = sorted(
            {x for case in shear_cases for x, _ in case.shear_samples_tn}
            | {x for x, _ in upper_ll_shear}
            | {x for x, _ in lower_ll_shear}
        )
        for x in shear_positions:
            shear_upper.append(
                (x, _strength_effect_at(result, x, upper_ll_shear, "max", include_pl, "shear_samples_tn"))
            )
            if has_lower_shear:
                shear_lower.append(
                    (x, _strength_effect_at(result, x, lower_ll_shear, "min", include_pl, "shear_samples_tn"))
                )
    return StrengthEnvelopeDiagrams(
        moment_upper=tuple(moment_upper),
        moment_lower=tuple(moment_lower) if has_lower_moment else None,
        shear_upper=tuple(shear_upper),
        shear_lower=tuple(shear_lower) if has_lower_shear else None,
    )


def _has_lower_moment_envelope(case) -> bool:
    return (
        getattr(case, "min_moment_envelope_tn_m", None) is not None
        or getattr(case, "min_moment_samples_tn_m", None) is not None
    )


def _moment_samples_for_target(case, target: str) -> tuple[Sample, ...]:
    if target == "max":
        return getattr(case, "max_moment_envelope_tn_m", None) or case.moment_samples_tn_m
    return (
        getattr(case, "min_moment_envelope_tn_m", None)
        or getattr(case, "min_moment_samples_tn_m", None)
        or case.moment_samples_tn_m
    )


def _has_lower_shear_envelope(case) -> bool:
    return getattr(case, "min_shear_samples_tn", None) is not None


def _shear_samples_for_target(case, target: str) -> tuple[Sample, ...]:
    samples = (
        getattr(case, "max_shear_samples_tn", None)
        if target == "max"
        else getattr(case, "min_shear_samples_tn", None)
    )
    return samples or case.shear_samples_tn


def _strength_effect_at(
    result,
    position: float,
    live_samples: tuple[Sample, ...],
    target: str,
    include_pl: bool,
    sample_attribute: str,
) -> float:
    """Combine effects at one station with sign-sensitive Strength I factors."""
    dc = _sample_at(getattr(result.dc, sample_attribute), position)
    dw = _sample_at(getattr(result.dw, sample_attribute), position)
    pl = _sample_at(getattr(result.pl, sample_attribute), position) if include_pl else 0.0
    ll_im = _sample_at(live_samples, position)
    return (
        STRENGTH_DC.for_effect(dc, target) * dc
        + STRENGTH_DW.for_effect(dw, target) * dw
        + STRENGTH_VARIABLE.for_effect(pl, target) * pl
        + STRENGTH_VARIABLE.for_effect(ll_im, target) * ll_im
    )


def envelope_diagram(
    samples: Iterable[Sample],
    *,
    title: str,
    y_label: str,
    lower_samples: Iterable[Sample] | None = None,
    legend_symbol: str = "M",
    width: float = 170 * mm,
    height: float = 62 * mm,
) -> Drawing:
    """Draw one diagram, optionally with separate upper and lower envelopes."""
    values = tuple(samples)
    lower_values = tuple(lower_samples or ())
    drawing = Drawing(width, height)
    font = register_arial_narrow()
    bold = "ArialNarrow-Bold" if font == "ArialNarrow" else "Helvetica-Bold"
    left, right, bottom = 17 * mm, 5 * mm, 12 * mm
    top = 15 * mm if lower_values else 9 * mm
    plot_w, plot_h = width - left - right, height - bottom - top
    drawing.add(String(0, height - 4 * mm, title, fontName=bold, fontSize=9, fillColor=INK))
    if not values:
        drawing.add(String(left, height / 2, "No hay muestras disponibles.", fontName=font, fontSize=8))
        return drawing
    all_values = values + lower_values
    xs = [item[0] for item in all_values]
    ys = [item[1] for item in all_values]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(min(ys), 0.0), max(max(ys), 0.0)
    if abs(ymax - ymin) < 1e-12:
        ymax, ymin = 1.0, -1.0

    def sx(value: float) -> float:
        return left + (value - xmin) / max(xmax - xmin, 1e-12) * plot_w

    def sy(value: float) -> float:
        return bottom + (value - ymin) / (ymax - ymin) * plot_h

    zero_y = sy(0.0)
    drawing.add(Line(left, zero_y, left + plot_w, zero_y, strokeColor=RULE, strokeWidth=0.7))
    drawing.add(Line(left, bottom, left, bottom + plot_h, strokeColor=RULE, strokeWidth=0.7))
    _add_curve(drawing, values, sx, sy, UPPER_ENVELOPE)
    if lower_values:
        _add_curve(drawing, lower_values, sx, sy, LOWER_ENVELOPE)
        legend_y = height - 9 * mm
        drawing.add(Line(left, legend_y, left + 8 * mm, legend_y, strokeColor=UPPER_ENVELOPE, strokeWidth=1.25))
        drawing.add(String(left + 10 * mm, legend_y - 2, f"{legend_symbol}max - superior", fontName=font, fontSize=6.5, fillColor=MUTED))
        legend_x = left + 52 * mm
        drawing.add(Line(legend_x, legend_y, legend_x + 8 * mm, legend_y, strokeColor=LOWER_ENVELOPE, strokeWidth=1.25))
        drawing.add(String(legend_x + 10 * mm, legend_y - 2, f"{legend_symbol}min - inferior", fontName=font, fontSize=6.5, fillColor=MUTED))
    drawing.add(String(left, 2 * mm, f"0.00", fontName=font, fontSize=6.5, fillColor=MUTED))
    drawing.add(String(left + plot_w - 12 * mm, 2 * mm, f"{xmax:.2f} m", fontName=font, fontSize=6.5, fillColor=MUTED))
    drawing.add(String(0, bottom + plot_h - 1 * mm, y_label, fontName=font, fontSize=6.5, fillColor=MUTED))
    if lower_values:
        _add_extreme_label(drawing, max(values, key=lambda item: item[1]), sx, sy, font)
        _add_extreme_label(drawing, min(lower_values, key=lambda item: item[1]), sx, sy, font)
    else:
        value_ys = [item[1] for item in values]
        for index in {value_ys.index(max(value_ys)), value_ys.index(min(value_ys))}:
            _add_extreme_label(drawing, values[index], sx, sy, font)
    return drawing


def _add_curve(drawing: Drawing, values, sx, sy, color) -> None:
    points: list[float] = []
    for x, y in values:
        points.extend((sx(x), sy(y)))
    drawing.add(PolyLine(points, strokeColor=color, strokeWidth=1.25))


def _add_extreme_label(drawing: Drawing, value: Sample, sx, sy, font: str) -> None:
    x, y = value
    if abs(y) <= 1e-9:
        return
    drawing.add(Line(sx(x), sy(y) - 1.4, sx(x), sy(y) + 1.4, strokeColor=INK, strokeWidth=1.0))
    label_y = sy(y) + (3 if y >= 0 else -8)
    drawing.add(String(sx(x) + 2, label_y, f"{y:.2f}", fontName=font, fontSize=6.5, fillColor=INK))


def moment_shear_pair(result, *, title: str, include_pl: bool, transverse: bool = False) -> list:
    """Return the moment and shear Strength I diagrams for one component."""
    diagrams = strength_diagram_envelopes(
        result,
        include_pl=include_pl,
        transverse=transverse,
    )
    flowables = [
        envelope_diagram(
            diagrams.moment_upper,
            lower_samples=diagrams.moment_lower,
            title=f"{title} - envolventes de momento Resistencia I",
            y_label="M (Tn.m)",
            legend_symbol="M",
        ),
    ]
    if diagrams.shear_upper:
        flowables.append(
            envelope_diagram(
                diagrams.shear_upper,
                lower_samples=diagrams.shear_lower,
                title=f"{title} - envolventes de cortante Resistencia I",
                y_label="V (Tn)",
                legend_symbol="V",
            )
        )
    return flowables
