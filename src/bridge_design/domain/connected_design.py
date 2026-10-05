"""Orchestrate connected abutment analysis, contact, geotechnics and RC design."""

from dataclasses import dataclass, field, replace

from bridge_design.domain.abutment import _soil_pressures, abutment_load_factors
from bridge_design.domain.connected_cases import connected_load_cases
from bridge_design.domain.connected_geometry import build_connected_mesh
from bridge_design.domain.connected_reinforcement import design_connected_reinforcement
from bridge_design.domain.frame_solver import FrameSolver


@dataclass(frozen=True)
class FoundationCheck:
    case: str
    limit_state: str
    horizontal_reaction: float
    normal_reaction: float
    sliding_resistance: float
    sliding_utilization: float
    maximum_pressure: float
    pressure_limit: float
    bearing_utilization: float
    contact_length: float
    maximum_settlement_mm: float
    maximum_uplift_mm: float
    reaction_x: float
    eccentricity: float
    sliding_status: str
    bearing_status: str


@dataclass(frozen=True)
class MeshComparison:
    coarse_step: float
    fine_step: float
    moment_change: float
    pressure_change: float
    settlement_change: float
    coarse_nodes: int | None = None
    fine_nodes: int | None = None


@dataclass(frozen=True)
class ConnectedDesign:
    inputs: object
    mesh: object
    cases: tuple
    results: tuple
    foundation_checks: tuple[FoundationCheck, ...]
    reinforcement: tuple
    earth_parameters: tuple = ()
    combination_factors: tuple = ()
    mesh_comparison: MeshComparison | None = None
    selected_reinforcement: dict = field(default_factory=dict)


def foundation_check(data, mesh, result):
    normal = sum(result.spring_reactions)
    horizontal = result.reactions[3 * mesh.reference_node]
    if result.limit_state == "service":
        phi = 1.0
        pressure_limit = data.soil.allowable_tn_m2
    elif result.limit_state == "extreme":
        phi = data.soil.extreme_sliding_phi
        pressure_limit = 0.80 * data.soil.nominal_bearing_fs * data.soil.allowable_tn_m2
    else:
        phi = data.soil.sliding_phi
        pressure_limit = 0.55 * data.soil.nominal_bearing_fs * data.soil.allowable_tn_m2
    resistance = phi * data.soil.friction_coefficient * normal
    sliding = abs(horizontal) / resistance if resistance > 1e-12 else (0.0 if abs(horizontal) < 1e-8 else float("inf"))
    maximum = max((reaction / spring.tributary_area for reaction, spring
                   in zip(result.spring_reactions, mesh.frame.springs)), default=0.0)
    contact = sum(spring.tributary_area for spring, reaction in zip(mesh.frame.springs, result.spring_reactions)
                  if reaction > 1e-9)
    reaction_x = sum(mesh.frame.nodes[spring.node].x * reaction
                     for spring, reaction in zip(mesh.frame.springs, result.spring_reactions)) / normal
    vertical = [result.displacements[3 * spring.node + 1] for spring in mesh.frame.springs]
    bearing = maximum / pressure_limit
    return FoundationCheck(result.name, result.limit_state, horizontal, normal, resistance, sliding,
                           maximum, pressure_limit, bearing, contact, -1000 * min(vertical),
                           1000 * max(0.0, max(vertical)), reaction_x, data.total_length_m / 2 - reaction_x,
                           "OK" if sliding <= 1 + 1e-8 else "NO", "OK" if bearing <= 1 + 1e-8 else "NO")


def analyze_connected_abutments(inputs):
    mesh = build_connected_mesh(inputs)
    solver = FrameSolver(mesh.frame)
    cases = tuple(connected_load_cases(inputs, mesh))
    results = tuple(solver.solve(case) for case in cases)
    checks = tuple(foundation_check(inputs, mesh, result) for result in results)
    return ConnectedDesign(inputs, mesh, cases, results, checks, (),
                           tuple(_soil_pressures(side, 0, 0, 0, 0) for side in (inputs.left, inputs.right)),
                           abutment_load_factors(inputs.left.gamma_eq))


def solve_connected_abutments(inputs, *, check_mesh=False):
    result = analyze_connected_abutments(inputs)
    steel = design_connected_reinforcement(inputs, result.mesh, result.results)
    comparison = None
    if check_mesh:
        refined = (replace(inputs, foundation_node_count=2 * inputs.foundation_node_count - 1)
                   if inputs.foundation_node_count is not None
                   else replace(inputs, mesh_size_m=inputs.mesh_size_m / 2))
        finer = analyze_connected_abutments(refined)

        def relative(original, refined):
            return abs(refined - original) / max(abs(refined), 1e-9)

        comparison = MeshComparison(inputs.effective_mesh_size_m, refined.effective_mesh_size_m,
            relative(max(abs(row.moment) for case in result.results for row in case.sections),
                     max(abs(row.moment) for case in finer.results for row in case.sections)),
            relative(max(row.maximum_pressure for row in result.foundation_checks),
                     max(row.maximum_pressure for row in finer.foundation_checks)),
            relative(max(row.maximum_settlement_mm for row in result.foundation_checks),
                     max(row.maximum_settlement_mm for row in finer.foundation_checks)),
            len(result.mesh.frame.springs), len(finer.mesh.frame.springs))
    return replace(result, reinforcement=steel, mesh_comparison=comparison)
