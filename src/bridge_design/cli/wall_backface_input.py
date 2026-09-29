"""Resolve a wall backface angle from geometry or an explicit input."""

from math import isfinite

from bridge_design.domain.abutment import AbutmentGeometryInputs, wall_vertical_front_angle_deg


def resolve_wall_backface_angle(
    value: float | str | None,
    geometry: AbutmentGeometryInputs,
    *,
    allow_auto: bool,
) -> float:
    """Automatic means exposed face vertical, taper entirely on the soil side."""
    automatic = value is None or (
        isinstance(value, str) and value.strip().lower() in {"", "auto", "automatico", "automático"}
    )
    if automatic:
        if not allow_auto:
            raise ValueError("El calculo automatico de theta se admite solo en diseno-muros.")
        return wall_vertical_front_angle_deg(geometry)
    try:
        if isinstance(value, bool):
            raise ValueError
        angle = float(value)
        if not isfinite(angle) or angle <= 0.0:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("Ingrese theta como numero positivo, o auto para calcularlo con los espesores.") from None
    return angle
