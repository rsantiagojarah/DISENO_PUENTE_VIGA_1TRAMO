"""Recover N,V,M, including exact internal extrema for polynomial member loads."""

from bridge_design.domain.frame_types import SectionForce


def integral(values, station):
    return sum(value * station**(index + 1) / (index + 1) for index, value in enumerate(values))


def value_at(values, station):
    return sum(value * station**index for index, value in enumerate(values))


def roots_in_unit_interval(values):
    coefficients = list(values)
    while len(coefficients) > 1 and abs(coefficients[-1]) < 1e-12:
        coefficients.pop()
    if len(coefficients) <= 1:
        return []
    if len(coefficients) == 2:
        root = -coefficients[0] / coefficients[1]
        return [root] if 0 < root < 1 else []
    derivative = [index * coefficients[index] for index in range(1, len(coefficients))]
    divisions = [0.0, *roots_in_unit_interval(derivative), 1.0]
    roots = [point for point in divisions[1:-1] if abs(value_at(coefficients, point)) < 1e-10]
    for lower, upper in zip(divisions, divisions[1:]):
        low_value = value_at(coefficients, lower)
        if low_value * value_at(coefficients, upper) >= 0:
            continue
        for _ in range(45):
            middle = (lower + upper) / 2
            if low_value * value_at(coefficients, middle) <= 0:
                upper = middle
            else:
                lower = middle
                low_value = value_at(coefficients, lower)
        roots.append((lower + upper) / 2)
    return sorted(set(roots))


def section_force_at(index, end_forces, load, length, station):
    axial = -end_forces[0] - length * integral(load.axial, station)
    shear = end_forces[1] + length * integral(load.transverse, station)
    moment = -end_forces[2] + end_forces[1] * length * station
    moment += length**2 * sum(value * station**(power + 2) / ((power + 1) * (power + 2))
                              for power, value in enumerate(load.transverse))
    moment -= length * integral(load.couple, station)
    return SectionForce(index, station, axial, shear, moment)


def member_sections(index, end_forces, load, length):
    derivative = [end_forces[1] - load.couple[0],
                  length * load.transverse[0] - load.couple[1],
                  length * load.transverse[1] / 2 - load.couple[2],
                  length * load.transverse[2] / 3]
    stations = sorted({0.0, 0.25, 0.5, 0.75, 1.0,
                       *roots_in_unit_interval(derivative),
                       *roots_in_unit_interval(load.axial),
                       *roots_in_unit_interval(load.transverse)})
    return [section_force_at(index, end_forces, load, length, station) for station in stations]
