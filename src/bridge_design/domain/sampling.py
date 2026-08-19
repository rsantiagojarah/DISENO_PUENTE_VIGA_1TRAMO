"""Fast interpolation helpers for ordered structural response samples."""

from __future__ import annotations

from collections.abc import Sequence

Sample = tuple[float, float]


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
