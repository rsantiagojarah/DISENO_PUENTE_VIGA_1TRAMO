"""Reusable validation helpers for terminal inputs and domain models."""


def require_positive(value: float, field_name: str) -> float:
    """Return value if it is greater than zero."""
    if value <= 0:
        raise ValueError(f"{field_name} debe ser mayor que cero.")
    return value


def require_non_negative(value: float, field_name: str) -> float:
    """Return value if it is zero or greater."""
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
    if value < minimum or value > maximum:
        raise ValueError(
            f"{field_name} debe estar entre {minimum:g} y {maximum:g}."
        )
    return value
