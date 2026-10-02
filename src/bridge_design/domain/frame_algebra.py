"""Scaled band Cholesky with graph ordering; no optional numerical dependency."""

from collections import deque
from math import sqrt


def degree_order(model):
    neighbors = {index: set() for index in range(len(model.nodes))}
    for element in model.elements:
        neighbors[element.start].add(element.end)
        neighbors[element.end].add(element.start)
    unseen = set(neighbors)
    ordered = []
    while unseen:
        root = min(unseen, key=lambda node: (len(neighbors[node]), node))
        queue = deque([root])
        unseen.remove(root)
        while queue:
            current = queue.popleft()
            ordered.append(current)
            following = sorted(neighbors[current] & unseen,
                               key=lambda node: (len(neighbors[node]), node))
            unseen.difference_update(following)
            queue.extend(following)
    return [3 * node + component for node in reversed(ordered) for component in range(3)
            if 3 * node + component not in model.fixed_dofs]


class BandFactor:
    def __init__(self, matrix):
        self.size = len(matrix)
        self.scale = []
        for index in range(self.size):
            if matrix[index][index] <= 0:
                raise ValueError("FRAME inestable: rigidez nula; revise contacto y restricciones.")
            self.scale.append(sqrt(matrix[index][index]))
        self.band = max((row - column for row in range(self.size)
                         for column in range(row) if matrix[row][column] != 0), default=0)
        self.lower = [[0.0] * (self.band + 1) for _ in range(self.size)]
        for row in range(self.size):
            for column in range(max(0, row - self.band), row + 1):
                value = matrix[row][column] / (self.scale[row] * self.scale[column])
                value -= sum(self.lower[row][row - inner] * self.lower[column][column - inner]
                             for inner in range(max(0, row - self.band), column))
                if column == row:
                    if value <= 1e-13:
                        raise ValueError("FRAME inestable o mal condicionado; revise contacto y malla.")
                    self.lower[row][0] = sqrt(value)
                else:
                    self.lower[row][row - column] = value / self.lower[column][0]

    def solve(self, vector):
        answer = [value / scale for value, scale in zip(vector, self.scale)]
        for row in range(self.size):
            answer[row] = (answer[row] - sum(
                self.lower[row][row - column] * answer[column]
                for column in range(max(0, row - self.band), row))) / self.lower[row][0]
        for row in reversed(range(self.size)):
            answer[row] = (answer[row] - sum(
                self.lower[column][column - row] * answer[column]
                for column in range(row + 1, min(self.size, row + self.band + 1)))) / self.lower[row][0]
        return [value / scale for value, scale in zip(answer, self.scale)]

