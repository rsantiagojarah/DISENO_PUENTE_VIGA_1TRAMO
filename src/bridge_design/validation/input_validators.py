"""Reusable validation helpers for terminal inputs and domain models."""

from math import isfinite
from numbers import Real


def require_finite(value: float, field_name: str) -> float:
    """Reject invalid numeric inputs before comparisons or arithmetic."""
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
        raise ValueError(f"{field_name} debe ser numerico y finito.")
    return value


def require_positive(value: float, field_name: str) -> float:
    """Return value if it is greater than zero."""
    require_finite(value, field_name)
    if value <= 0:
        raise ValueError(f"{field_name} debe ser mayor que cero.")
    return value


def require_non_negative(value: float, field_name: str) -> float:
    """Return value if it is zero or greater."""
    require_finite(value, field_name)
    if value < 0:
        raise ValueError(f"{field_name} no debe ser negativo.")
    return value


def require_range(
    value: float,
    field_name: str,
    minimum: float,
    maximum: float,
) -> float:
    """Return value if it is within the inclusive range."""
    require_finite(value, field_name)
    if value < minimum or value > maximum:
        raise ValueError(
            f"{field_name} debe estar entre {minimum:g} y {maximum:g}."
        )
    return value
