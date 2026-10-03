"""Planar Euler-Bernoulli frames. Units: Tn, m, radians; N is tension positive."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class FrameNode:
    x: float
    y: float


@dataclass(frozen=True)
class FrameElement:
    start: int
    end: int
    area: float
    inertia: float
    modulus: float
    region: str = "Frame"
    depth: float = 1.0
    offset: float = 0.0

    def __post_init__(self):
        for value in (self.area, self.inertia, self.modulus, self.depth):
            if not isfinite(value) or value <= 0:
                raise ValueError("A, I, E y espesor deben ser positivos y finitos.")
        if not isfinite(self.offset):
            raise ValueError("Offset no finito.")


@dataclass(frozen=True)
class VerticalSpring:
    node: int
    stiffness: float
    tributary_area: float
    allowable_pressure: float = 0.0


@dataclass(frozen=True)
class FrameModel:
    nodes: tuple[FrameNode, ...]
    elements: tuple[FrameElement, ...]
    springs: tuple[VerticalSpring, ...]
    fixed_dofs: tuple[int, ...]
    compression_only: bool = True


@dataclass(frozen=True)
class ElementLoad:
    """Local distributed force/couple polynomials in normalized station s=x/L."""

    axial: tuple[float, float, float] = (0.0, 0.0, 0.0)
    transverse: tuple[float, float, float] = (0.0, 0.0, 0.0)
    couple: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def scaled(self, factor):
        return ElementLoad(*(tuple(factor * value for value in values)
                             for values in (self.axial, self.transverse, self.couple)))

    def plus(self, other):
        return ElementLoad(*(tuple(left + right for left, right in zip(values, added))
                             for values, added in zip(
                                 (self.axial, self.transverse, self.couple),
                                 (other.axial, other.transverse, other.couple))))


@dataclass(frozen=True)
class FrameCase:
    name: str
    nodal: tuple[float, ...]
    distributed: tuple[ElementLoad, ...]
    limit_state: str = "service"
    load_trace: tuple = ()


@dataclass(frozen=True)
class SectionForce:
    element: int
    station: float
    axial: float
    shear: float
    moment: float


@dataclass(frozen=True)
class FrameResult:
    name: str
    limit_state: str
    displacements: tuple[float, ...]
    reactions: tuple[float, ...]
    spring_reactions: tuple[float, ...]
    contact: tuple[bool, ...]
    end_forces: tuple[tuple[float, ...], ...]
    sections: tuple[SectionForce, ...]
    applied_resultant: tuple[float, float, float]
    equilibrium_error: tuple[float, float, float]
    iterations: int
