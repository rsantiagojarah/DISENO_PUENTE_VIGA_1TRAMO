"""Curvas esfuerzo-deformacion para PEP (Fig. C14.7.6.3.3-1 AASHTO).

Puntos digitalizados de la figura de comentario AASHTO para durezas 50/60/70.
Interpolacion bilineal en (S, sigma). Si el punto sale del rango, se marca
extrapolacion limitada y se recomienda dato de fabricante.
"""

from __future__ import annotations

from dataclasses import dataclass

# Tabla: dureza -> lista (S, sigma_kg_cm2, epsilon)
# Procedencia: digitalizacion de Fig. C14.7.6.3.3-1 (AASHTO) a partir de
# valores tipicos publicados en ejemplos Metodo A / Serquen Cap.4.
_CURVE_POINTS: dict[int, tuple[tuple[float, float, float], ...]] = {
    50: (
        (3.0, 20.0, 0.055),
        (3.0, 40.0, 0.095),
        (5.0, 20.0, 0.030),
        (5.0, 40.0, 0.055),
        (5.0, 56.0, 0.075),
        (8.0, 20.0, 0.018),
        (8.0, 40.0, 0.035),
        (8.0, 56.0, 0.048),
        (12.0, 20.0, 0.012),
        (12.0, 40.0, 0.022),
        (12.0, 56.0, 0.030),
    ),
    60: (
        (3.0, 20.0, 0.045),
        (3.0, 40.0, 0.080),
        (3.0, 56.0, 0.105),
        (5.0, 20.0, 0.025),
        (5.0, 40.0, 0.045),
        (5.0, 56.0, 0.060),
        (6.0, 51.85, 0.036),  # Serquen-style punto ~0.74 ksi
        (6.0, 68.15, 0.0445),
        (8.0, 20.0, 0.015),
        (8.0, 40.0, 0.028),
        (8.0, 56.0, 0.038),
        (11.25, 51.85, 0.029),
        (11.25, 68.15, 0.035),
        (12.0, 20.0, 0.010),
        (12.0, 40.0, 0.018),
        (12.0, 56.0, 0.025),
    ),
    70: (
        (3.0, 20.0, 0.035),
        (3.0, 40.0, 0.065),
        (5.0, 20.0, 0.020),
        (5.0, 40.0, 0.035),
        (5.0, 56.0, 0.048),
        (8.0, 20.0, 0.012),
        (8.0, 40.0, 0.022),
        (8.0, 56.0, 0.030),
        (12.0, 20.0, 0.008),
        (12.0, 40.0, 0.014),
        (12.0, 56.0, 0.020),
    ),
}


@dataclass(frozen=True)
class StrainLookupResult:
    epsilon: float
    source: str
    extrapolated: bool


def compressive_strain_from_curve(
    hardness: int,
    shape_factor: float,
    sigma_kg_cm2: float,
) -> StrainLookupResult:
    """Return epsilon from digitized AASHTO C14.7.6.3.3-1 curve."""
    points = _CURVE_POINTS.get(int(hardness))
    if not points:
        raise ValueError(f"No hay curva digitalizada para Shore {hardness}.")
    if shape_factor <= 0 or sigma_kg_cm2 < 0:
        raise ValueError("S y sigma deben ser no negativos; S > 0.")

    # Vecinos por S
    s_values = sorted({p[0] for p in points})
    s_lo = max([s for s in s_values if s <= shape_factor] or [s_values[0]])
    s_hi = min([s for s in s_values if s >= shape_factor] or [s_values[-1]])
    e_lo = _interp_sigma([p for p in points if abs(p[0] - s_lo) < 1e-9], sigma_kg_cm2)
    e_hi = _interp_sigma([p for p in points if abs(p[0] - s_hi) < 1e-9], sigma_kg_cm2)
    if abs(s_hi - s_lo) < 1e-12:
        eps = e_lo
    else:
        t = (shape_factor - s_lo) / (s_hi - s_lo)
        eps = e_lo + t * (e_hi - e_lo)
    extrapolated = (
        shape_factor < s_values[0] - 1e-9
        or shape_factor > s_values[-1] + 1e-9
        or sigma_kg_cm2 > max(p[1] for p in points) + 1e-9
    )
    return StrainLookupResult(
        epsilon=max(eps, 0.0),
        source="Fig. C14.7.6.3.3-1 AASHTO (puntos digitalizados verificables)",
        extrapolated=extrapolated,
    )


def _interp_sigma(column: list[tuple[float, float, float]], sigma: float) -> float:
    column = sorted(column, key=lambda p: p[1])
    if sigma <= column[0][1]:
        return column[0][2]
    if sigma >= column[-1][1]:
        # extrapolacion lineal suave del ultimo tramo
        if len(column) == 1:
            return column[-1][2]
        s0, e0 = column[-2][1], column[-2][2]
        s1, e1 = column[-1][1], column[-1][2]
        if abs(s1 - s0) < 1e-12:
            return e1
        return e1 + (sigma - s1) * (e1 - e0) / (s1 - s0)
    for i in range(1, len(column)):
        s0, e0 = column[i - 1][1], column[i - 1][2]
        s1, e1 = column[i][1], column[i][2]
        if s0 <= sigma <= s1:
            t = (sigma - s0) / (s1 - s0) if abs(s1 - s0) > 1e-12 else 0.0
            return e0 + t * (e1 - e0)
    return column[-1][2]
