"""First-order elastic frames on unilateral Winkler springs by active contact sets."""

from math import isfinite

from bridge_design.domain.frame_algebra import BandFactor, degree_order
from bridge_design.domain.frame_elements import consistent_load, element_matrices, matvec, transpose
from bridge_design.domain.frame_sections import member_sections
from bridge_design.domain.frame_types import FrameResult


def global_resultant(model, vector):
    return (sum(vector[0::3]), sum(vector[1::3]),
            sum(node.x * vector[3 * index + 1] - node.y * vector[3 * index]
                + vector[3 * index + 2] for index, node in enumerate(model.nodes)))


class FrameSolver:
    def __init__(self, model):
        self.model = model
        self.size = 3 * len(model.nodes)
        if not model.nodes or not model.elements:
            raise ValueError("El FRAME requiere nodos y elementos.")
        if any(not isfinite(value) for node in model.nodes for value in (node.x, node.y)):
            raise ValueError("Coordenada no finita.")
        if any(dof < 0 or dof >= self.size for dof in model.fixed_dofs):
            raise ValueError("Restriccion fuera del modelo.")
        if any(node < 0 or node >= len(model.nodes) for element in model.elements
               for node in (element.start, element.end)):
            raise ValueError("Conectividad fuera del modelo.")
        self.matrices = [element_matrices(model, element) for element in model.elements]
        self.stiffness = [[0.0] * self.size for _ in range(self.size)]
        for _local, _transform, matrix, dofs, _length in self.matrices:
            for row, global_row in enumerate(dofs):
                for column, global_column in enumerate(dofs):
                    self.stiffness[global_row][global_column] += matrix[row][column]
        for spring in model.springs:
            if not (0 <= spring.node < len(model.nodes)) or any(
                not isfinite(value) or value <= 0 for value in (spring.stiffness, spring.tributary_area)
            ):
                raise ValueError("Resorte invalido: nodo, rigidez o area tributaria.")
        self.free = degree_order(model)
        self.cache = {}

    def _factor(self, active):
        key = tuple(active)
        if key not in self.cache:
            matrix = [[self.stiffness[row][column] for column in self.free] for row in self.free]
            positions = {dof: index for index, dof in enumerate(self.free)}
            for enabled, spring in zip(active, self.model.springs):
                position = positions.get(3 * spring.node + 1)
                if enabled and position is not None:
                    matrix[position][position] += spring.stiffness
            if len(self.cache) > 64:
                self.cache.clear()
            self.cache[key] = BandFactor(matrix)
        return self.cache[key]

    def solve(self, case, max_iterations=100):
        if len(case.nodal) != self.size or len(case.distributed) != len(self.matrices):
            raise ValueError("Dimensiones de cargas incompatibles con el FRAME.")
        force = list(case.nodal)
        equivalent = []
        for load, (_local, transform, _matrix, dofs, length) in zip(case.distributed, self.matrices):
            local_force = consistent_load(load, length)
            equivalent.append(local_force)
            for dof, value in zip(dofs, matvec(transpose(transform), local_force)):
                force[dof] += value
        if any(not isfinite(value) for value in force):
            raise ValueError("Las cargas deben ser finitas.")
        active = [True] * len(self.model.springs)
        visited = set()
        force_scale = max(1.0, sum(abs(value) for value in force))
        tolerance = 1e-10 * force_scale
        for iteration in range(1, max_iterations + 1):
            if tuple(active) in visited:
                raise ValueError(f"El contacto no converge en {case.name}; revise cargas y malla.")
            visited.add(tuple(active))
            try:
                solution = self._factor(active).solve([force[dof] for dof in self.free])
            except ValueError as error:
                raise ValueError(f"{case.name}: {error}") from error
            displacements = [0.0] * self.size
            for dof, value in zip(self.free, solution):
                displacements[dof] = value
            updated = list(active)
            if self.model.compression_only:
                for index, spring in enumerate(self.model.springs):
                    reaction = -spring.stiffness * displacements[3 * spring.node + 1]
                    if reaction < -tolerance:
                        updated[index] = False
                    elif reaction > tolerance:
                        updated[index] = True
            if updated == active:
                break
            active = updated
        else:
            raise ValueError(f"Contacto sin convergencia tras {max_iterations} iteraciones: {case.name}.")
        spring_reactions = tuple(-spring.stiffness * displacements[3 * spring.node + 1] if enabled else 0.0
                                 for enabled, spring in zip(active, self.model.springs))
        residual = [value - load for value, load in zip(matvec(self.stiffness, displacements), force)]
        for spring, reaction in zip(self.model.springs, spring_reactions):
            residual[3 * spring.node + 1] -= reaction
        free_error = max((abs(residual[dof]) for dof in self.free), default=0.0)
        if free_error > 1e-6 * force_scale:
            raise ValueError(f"Equilibrio nodal insuficiente en {case.name}: {free_error:g} Tn.")
        reactions = tuple(value if dof in self.model.fixed_dofs else 0.0 for dof, value in enumerate(residual))
        total = [load + reaction for load, reaction in zip(force, reactions)]
        for spring, reaction in zip(self.model.springs, spring_reactions):
            total[3 * spring.node + 1] += reaction
        errors = global_resultant(self.model, total)
        dimension = max(1.0, *(abs(node.x) + abs(node.y) for node in self.model.nodes))
        if max(abs(errors[0]), abs(errors[1]), abs(errors[2]) / dimension) > 1e-6 * force_scale:
            raise ValueError(f"Equilibrio global insuficiente en {case.name}.")
        end_forces, sections = [], []
        for index, (load, data, fixed_end) in enumerate(zip(case.distributed, self.matrices, equivalent)):
            local, transform, _matrix, dofs, length = data
            local_displacements = matvec(transform, [displacements[dof] for dof in dofs])
            ends = tuple(value - applied for value, applied in zip(matvec(local, local_displacements), fixed_end))
            end_forces.append(ends)
            sections.extend(member_sections(index, ends, load, length))
        return FrameResult(case.name, case.limit_state, tuple(displacements), reactions,
                           spring_reactions, tuple(active), tuple(end_forces), tuple(sections),
                           global_resultant(self.model, force), errors, iteration)
