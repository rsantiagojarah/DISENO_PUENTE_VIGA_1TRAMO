"""Domain API for reinforced concrete cantilever retaining walls."""

from collections.abc import Mapping

from bridge_design.domain.abutment import (
    AbutmentDesignResult,
    AbutmentGeometryInputs,
    AbutmentInputs,
    AbutmentLoadInputs,
    AbutmentMaterialInputs,
    AbutmentReinforcementInputs,
    AbutmentSoilInputs,
    pure_wall_geometry_inputs,
    pure_wall_inputs,
    pure_wall_load_inputs,
    solve_abutment_design,
)
from bridge_design.domain.rebar_catalog import ReinforcementSpacingOption

CantileverWallDesignResult = AbutmentDesignResult
CantileverWallGeometryInputs = AbutmentGeometryInputs
CantileverWallInputs = AbutmentInputs
CantileverWallLoadInputs = AbutmentLoadInputs
CantileverWallMaterialInputs = AbutmentMaterialInputs
CantileverWallReinforcementInputs = AbutmentReinforcementInputs
CantileverWallSoilInputs = AbutmentSoilInputs


def cantilever_wall_load_inputs() -> CantileverWallLoadInputs:
    """Return zero bridge actions for an independent cantilever wall."""
    return pure_wall_load_inputs()


def cantilever_wall_geometry_inputs(
    geometry: CantileverWallGeometryInputs | None = None,
) -> CantileverWallGeometryInputs:
    """Return PDF-style simple cantilever-wall geometry."""
    return pure_wall_geometry_inputs(geometry)


def cantilever_wall_inputs(
    inputs: CantileverWallInputs | None = None,
) -> CantileverWallInputs:
    """Return inputs normalized for an independent cantilever wall."""
    return pure_wall_inputs(inputs)


def solve_cantilever_wall_design(
    inputs: CantileverWallInputs | None = None,
    selected_reinforcement: Mapping[str, ReinforcementSpacingOption] | None = None,
) -> CantileverWallDesignResult:
    """Return wall checks using the shared cantilever retaining-structure engine."""
    return solve_abutment_design(
        cantilever_wall_inputs(inputs),
        selected_reinforcement=selected_reinforcement,
    )
