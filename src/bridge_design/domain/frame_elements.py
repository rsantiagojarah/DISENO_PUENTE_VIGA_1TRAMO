"""Elastic FRAME matrices, rigid section offsets and consistent distributed loads.

Reference: Euler-Bernoulli virtual work, OpenSees elasticBeamColumn/Linear.
The section centroid lies offset meters along the local positive normal.
"""

from math import hypot, sqrt

from bridge_design.domain.frame_types import ElementLoad
from bridge_design.domain.transverse_slab import _beam_element_stiffness


def matvec(matrix, vector):
    return [sum(value * vector[column] for column, value in enumerate(row)) for row in matrix]


def transpose(matrix):
    return [list(column) for column in zip(*matrix)]


def multiply(left, right):
    columns = transpose(right)
    return [[sum(first * second for first, second in zip(row, column))
             for column in columns] for row in left]


def element_geometry(model, element):
    first, last = model.nodes[element.start], model.nodes[element.end]
    length = hypot(last.x - first.x, last.y - first.y)
    if length <= 1e-9:
        raise ValueError("Elemento FRAME de longitud nula.")
    return length, (last.x - first.x) / length, (last.y - first.y) / length


def element_matrices(model, element):
    length, cosine, sine = element_geometry(model, element)
    local = [[0.0] * 6 for _ in range(6)]
    axial = element.modulus * element.area / length
    local[0][0] = local[3][3] = axial
    local[0][3] = local[3][0] = -axial
    flexural = _beam_element_stiffness(element.modulus * element.inertia, length)
    bending_dofs = (1, 2, 4, 5)
    for row, target_row in enumerate(bending_dofs):
        for column, target_column in enumerate(bending_dofs):
            local[target_row][target_column] = flexural[row][column]
    transform = [[0.0] * 6 for _ in range(6)]
    for base in (0, 3):
        transform[base][base:base + 3] = [cosine, sine, -element.offset]
        transform[base + 1][base:base + 3] = [-sine, cosine, 0.0]
        transform[base + 2][base + 2] = 1.0
    global_matrix = multiply(transpose(transform), multiply(local, transform))
    dofs = tuple(3 * node + component for node in (element.start, element.end)
                 for component in range(3))
    return local, transform, global_matrix, dofs, length


def polynomial(values, station):
    return values[0] + station * (values[1] + station * values[2])


def fit_polynomial(first, middle, last):
    return (first, 4 * middle - 3 * first - last, 2 * (last + first - 2 * middle))


def distributed_from_function(model, element, density):
    """Density returns global Fx, Fy and couple about the centroid per meter."""
    length, cosine, sine = element_geometry(model, element)
    rows = []
    for station in (0.0, 0.5, 1.0):
        horizontal, vertical, couple = density(station)
        rows.append((cosine * horizontal + sine * vertical,
                     -sine * horizontal + cosine * vertical, couple))
    return ElementLoad(*(fit_polynomial(*values) for values in zip(*rows)))


def consistent_load(load, length):
    result = [0.0] * 6
    for point, weight in ((-sqrt(3 / 5), 5 / 9), (0.0, 8 / 9), (sqrt(3 / 5), 5 / 9)):
        station = (point + 1) / 2
        factor = weight * length / 2
        axial = polynomial(load.axial, station)
        transverse = polynomial(load.transverse, station)
        couple = polynomial(load.couple, station)
        shape = (1 - 3 * station**2 + 2 * station**3,
                 length * (station - 2 * station**2 + station**3),
                 3 * station**2 - 2 * station**3,
                 length * (-station**2 + station**3))
        slope = ((-6 * station + 6 * station**2) / length,
                 1 - 4 * station + 3 * station**2,
                 (6 * station - 6 * station**2) / length,
                 -2 * station + 3 * station**2)
        result[0] += factor * axial * (1 - station)
        result[3] += factor * axial * station
        for index, dof in enumerate((1, 2, 4, 5)):
            result[dof] += factor * (transverse * shape[index] + couple * slope[index])
    return result

