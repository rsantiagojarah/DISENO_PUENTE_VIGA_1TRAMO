"""Discrete independent transverse placements, including interval endpoints."""

from bridge_design.codes.mtc_2018 import mtc_design_lanes, DEFAULT_WHEEL_CLEARANCE_TO_TRAFFIC_BARRIER_M
from itertools import product
from bridge_design.validation.input_validators import require_positive

TRANSVERSE_WHEEL_CLEARANCE_M = DEFAULT_WHEEL_CLEARANCE_TO_TRAFFIC_BARRIER_M


class TransverseLaneGeometryError(ValueError):
    """The selected lane geometry cannot accommodate the specified HL-93 model."""


def validate_lane_geometry(roadway_width, wheel_spacing, loaded_width=0.0,
                           clearance=TRANSVERSE_WHEEL_CLEARANCE_M):
    count, width = mtc_design_lanes(roadway_width)
    required = max(wheel_spacing + 2.0 * clearance, loaded_width)
    if width < required - 1e-9:
        raise TransverseLaneGeometryError(
            f"Calzada de {roadway_width:.4f} m: {count} carril(es) de {width:.4f} m, "
            f"pero el modelo HL-93 requiere {required:.4f} m por carril "
            f"(ruedas {wheel_spacing:.4f} m, retiros {clearance:.4f} m). "
            "No se reducen dimensiones ni se omiten carriles automaticamente. "
            "Revise la geometria y la convencion dimensional del vehiculo."
        )
    return count, width


def positions(start: float, end: float, step: float):
    require_positive(step, "paso transversal")
    if end < start - 1e-9:
        return
    index = 0
    samples = {round(start, 10), round(end, 10)}
    while start + index * step < end - 1e-9:
        samples.add(round(start + index * step, 10))
        samples.add(round(end - index * step, 10))
        index += 1
    yield from sorted(samples)


def lane_positions(start: float, end: float, count: int, step: float):
    """Place nonoverlapping design lanes independently within the clear roadway."""
    limit, width = mtc_design_lanes(end - start)
    if not 1 <= count <= limit:
        return

    def visit(left, remaining, placed):
        if remaining == 0:
            yield placed
            return
        for origin in positions(left, end - remaining * width, step):
            yield from visit(origin + width, remaining - 1, placed + (origin,))

    seen = set()
    for lanes in visit(start, count, ()):
        for pattern in (lanes, tuple(round(start + end - width - x, 10) for x in reversed(lanes))):
            if pattern not in seen:
                seen.add(pattern)
                yield pattern


def wheel_patterns(start, end, count, step, wheel_spacing, clearance=TRANSVERSE_WHEEL_CLEARANCE_M):
    limit, width = validate_lane_geometry(end - start, wheel_spacing, clearance=clearance)
    if not 1 <= count <= limit:
        return
    offsets = tuple(positions(clearance, width - clearance - wheel_spacing, step))
    if not offsets:
        raise ValueError("El carril no admite las ruedas y sus retiros; revise la geometria de circulacion.")
    seen = set()
    for lanes in lane_positions(start, end, count, step):
        for shifts in product(offsets, repeat=count):
            wheels = tuple(round(lane + shift, 10) for lane, shift in zip(lanes, shifts))
            if wheels not in seen:
                seen.add(wheels)
                yield wheels
