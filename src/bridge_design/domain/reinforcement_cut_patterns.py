"""Partial cutoffs on the actual selected bar grid, per one-metre strip."""

from dataclasses import dataclass
from math import floor


@dataclass(frozen=True)
class BarCutPattern:
    cycle_bars: int
    continuing_bars: int
    equivalent_spacing_m: float
    maximum_gap_m: float
    remaining_area_cm2_m: float


def partial_cut_patterns(bar, selected_spacing_m, minimum_area, maximum_spacing_m):
    """Cut one bar in each cycle, retaining all other bars at their positions.

    MTC 2.6.5.6.1.2.1: no adjacent terminations and at most 50% at a section.
    Practical cycles fit within the model's one-metre transverse strip. Area
    uses average spacing; crack control must use the largest actual gap (2s).
    A sparse selected grid cannot be reduced by inventing a new uniform grid.
    """
    gap = 2 * selected_spacing_m
    if gap > maximum_spacing_m + 1e-9:
        return ()
    patterns = []
    for cycle in range(2, floor(1.0 / selected_spacing_m + 1e-9) + 1):
        equivalent = selected_spacing_m * cycle / (cycle - 1)
        area = bar.area_cm2 / equivalent
        if area + 1e-9 >= minimum_area:
            patterns.append(BarCutPattern(cycle, cycle-1, equivalent, gap, area))
    return tuple(patterns)
