"""Fast interpolation helpers for ordered structural response samples."""

from __future__ import annotations

from collections.abc import Sequence

Sample = tuple[float, float]


def envelope_sorted_samples(curves, positions, target, *, tolerance=0.0):
    """Interpolate each ordered curve in one pass, retaining every output station."""
    xs = tuple(positions)
    upper = target == "max"
    result = [float('-inf') if upper else float('inf')] * len(xs)
    for samples in curves:
        if not samples:
            raise ValueError("No hay muestras disponibles.")
        right = 1
        last = len(samples) - 1
        first_x, first_y = samples[0]
        last_x, last_y = samples[-1]
        for index, x in enumerate(xs):
            if x <= first_x:
                value = first_y
            elif x >= last_x:
                value = last_y
            else:
                while right < last and samples[right][0] < x:
                    right += 1
                left_x, left_y = samples[right - 1]
                right_x, right_y = samples[right]
                delta = right_x - left_x
                value = left_y if abs(delta) <= tolerance else (
                    left_y + (x - left_x) / delta * (right_y - left_y)
                )
            if (value > result[index]) if upper else (value < result[index]):
                result[index] = value
    return tuple(zip(xs, result))


def interpolate_sorted_samples(
    samples: Sequence[Sample],
    position: float,
    *,
    tolerance: float = 0.0,
    empty_message: str = "No hay muestras disponibles.",
) -> float:
    """Return an interpolated value using a binary interval search.

    Boundary handling and linear interpolation are identical to the former
    sequential searches; only the interval lookup is more efficient.
    """
    if not samples:
        raise ValueError(empty_message)
    if position <= samples[0][0]:
        return samples[0][1]
    if position >= samples[-1][0]:
        return samples[-1][1]

    left_index = 0
    right_index = len(samples) - 1
    while right_index - left_index > 1:
        middle = (left_index + right_index) // 2
        if position <= samples[middle][0]:
            right_index = middle
        else:
            left_index = middle

    left_x, left_value = samples[left_index]
    right_x, right_value = samples[right_index]
    delta = right_x - left_x
    if abs(delta) <= tolerance:
        return left_value
    ratio = (position - left_x) / delta
    return left_value + ratio * (right_value - left_value)
