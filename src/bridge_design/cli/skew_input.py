"""Single project angle, measured from the normal to the bridge axis."""

from bridge_design.validation.input_validators import require_range


def parse_skew_angle(value):
    """Normalize a console/YAML angle, rejecting booleans and non-finite values."""
    if isinstance(value, bool):
        raise ValueError("El angulo de esviaje debe ser numerico, no booleano.")
    try:
        angle = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("El angulo de esviaje debe ser numerico entre 0 y 60 grados.") from exc
    return require_range(angle, "Angulo de esviaje (grados)", 0, 60)


def collect_skew_angle():
    while True:
        raw = input("Angulo de esviaje respecto de la perpendicular al eje (grados, 0 a 60) [0]: ").strip()
        try:
            return parse_skew_angle(raw or "0")
        except ValueError as exc:
            print(f"Error: {exc}")
