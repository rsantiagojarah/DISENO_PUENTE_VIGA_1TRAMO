"""MTC 2018 strain-compatible reinforced-concrete flexure helpers."""

from dataclasses import dataclass

from bridge_design.validation.input_validators import (
    require_non_negative,
    require_positive,
)


CONCRETE_ULTIMATE_STRAIN = 0.003
COMPRESSION_CONTROLLED_TENSILE_STRAIN = 0.002
TENSION_CONTROLLED_TENSILE_STRAIN = 0.005
DEFAULT_STEEL_ELASTIC_MODULUS_KG_CM2 = 2_000_000.0


@dataclass(frozen=True)
class RectangularFlexuralResponse:
    """Strain-compatible response of a singly reinforced rectangular section."""

    neutral_axis_depth_cm: float
    compression_block_depth_cm: float
    steel_strain: float
    steel_stress_kg_cm2: float
    extreme_tensile_strain: float
    resistance_factor: float
    nominal_moment_tn_m: float


def mtc_beta1(concrete_strength_kg_cm2: float) -> float:
    """Return the MTC/AASHTO rectangular-block beta1 factor."""
    require_positive(concrete_strength_kg_cm2, "f'c")
    reduction = 0.05 * max(concrete_strength_kg_cm2 - 280.0, 0.0) / 70.0
    return max(0.85 - reduction, 0.65)


def mtc_flexural_resistance_factor(extreme_tensile_strain: float) -> float:
    """Return phi for nonprestressed reinforcement from MTC 2.7.1.1.4.2a."""
    require_non_negative(extreme_tensile_strain, "epsilon_t")
    if extreme_tensile_strain <= COMPRESSION_CONTROLLED_TENSILE_STRAIN:
        return 0.75
    if extreme_tensile_strain >= TENSION_CONTROLLED_TENSILE_STRAIN:
        return 0.90
    return 0.75 + 0.15 * (
        extreme_tensile_strain - COMPRESSION_CONTROLLED_TENSILE_STRAIN
    ) / (
        TENSION_CONTROLLED_TENSILE_STRAIN
        - COMPRESSION_CONTROLLED_TENSILE_STRAIN
    )


def rectangular_flexural_response(
    steel_area_cm2: float,
    concrete_width_cm: float,
    effective_depth_cm: float,
    concrete_strength_kg_cm2: float,
    steel_yield_kg_cm2: float,
    steel_elastic_modulus_kg_cm2: float = DEFAULT_STEEL_ELASTIC_MODULUS_KG_CM2,
    extreme_tension_depth_cm: float | None = None,
) -> RectangularFlexuralResponse:
    """Return equilibrium, compatibility and nominal resistance for provided As."""
    require_positive(steel_area_cm2, "As")
    require_positive(concrete_width_cm, "b")
    require_positive(effective_depth_cm, "ds")
    require_positive(concrete_strength_kg_cm2, "f'c")
    require_positive(steel_yield_kg_cm2, "fy")
    require_positive(steel_elastic_modulus_kg_cm2, "Es")
    tension_depth = (
        effective_depth_cm
        if extreme_tension_depth_cm is None
        else extreme_tension_depth_cm
    )
    require_positive(tension_depth, "dt")
    if tension_depth < effective_depth_cm:
        raise ValueError("dt no debe ser menor que ds.")

    beta1 = mtc_beta1(concrete_strength_kg_cm2)

    def equilibrium(c_cm: float) -> float:
        a_cm = beta1 * c_cm
        compression = 0.85 * concrete_strength_kg_cm2 * concrete_width_cm * a_cm
        steel_strain = CONCRETE_ULTIMATE_STRAIN * (
            effective_depth_cm - c_cm
        ) / c_cm
        steel_stress = min(
            steel_yield_kg_cm2,
            max(steel_elastic_modulus_kg_cm2 * steel_strain, 0.0),
        )
        return compression - steel_area_cm2 * steel_stress

    lower = effective_depth_cm * 1.0e-12
    upper = effective_depth_cm * (1.0 - 1.0e-12)
    for _ in range(100):
        mid = (lower + upper) / 2.0
        if equilibrium(mid) < 0.0:
            lower = mid
        else:
            upper = mid
    c_cm = (lower + upper) / 2.0
    a_cm = beta1 * c_cm
    steel_strain = CONCRETE_ULTIMATE_STRAIN * (
        effective_depth_cm - c_cm
    ) / c_cm
    steel_stress = min(
        steel_yield_kg_cm2,
        steel_elastic_modulus_kg_cm2 * steel_strain,
    )
    extreme_strain = CONCRETE_ULTIMATE_STRAIN * (
        tension_depth - c_cm
    ) / c_cm
    extreme_strain = max(extreme_strain, 0.0)
    compression = 0.85 * concrete_strength_kg_cm2 * concrete_width_cm * a_cm
    nominal_moment = (
        compression * (effective_depth_cm - a_cm / 2.0) / 100000.0
    )
    return RectangularFlexuralResponse(
        neutral_axis_depth_cm=c_cm,
        compression_block_depth_cm=a_cm,
        steel_strain=steel_strain,
        steel_stress_kg_cm2=steel_stress,
        extreme_tensile_strain=extreme_strain,
        resistance_factor=mtc_flexural_resistance_factor(extreme_strain),
        nominal_moment_tn_m=nominal_moment,
    )


def required_rectangular_steel_area_cm2(
    design_moment_tn_m: float,
    concrete_width_cm: float,
    effective_depth_cm: float,
    concrete_strength_kg_cm2: float,
    steel_yield_kg_cm2: float,
    phi_limit: float = 0.90,
    steel_elastic_modulus_kg_cm2: float = DEFAULT_STEEL_ELASTIC_MODULUS_KG_CM2,
    extreme_tension_depth_cm: float | None = None,
) -> float:
    """Return minimum As satisfying strain-compatible phi*Mn >= Mu."""
    require_non_negative(design_moment_tn_m, "Mu")
    require_positive(concrete_width_cm, "b")
    require_positive(effective_depth_cm, "ds")
    require_positive(concrete_strength_kg_cm2, "f'c")
    require_positive(steel_yield_kg_cm2, "fy")
    require_positive(phi_limit, "phi")
    require_positive(steel_elastic_modulus_kg_cm2, "Es")
    if phi_limit > 1.0:
        raise ValueError("phi no debe exceder 1.0.")
    if design_moment_tn_m == 0.0:
        return 0.0

    tension_depth = (
        effective_depth_cm
        if extreme_tension_depth_cm is None
        else extreme_tension_depth_cm
    )
    require_positive(tension_depth, "dt")
    if tension_depth < effective_depth_cm:
        raise ValueError("dt no debe ser menor que ds.")
    beta1 = mtc_beta1(concrete_strength_kg_cm2)

    def state_at_c(c_cm: float) -> tuple[float, float]:
        a_cm = beta1 * c_cm
        compression = 0.85 * concrete_strength_kg_cm2 * concrete_width_cm * a_cm
        steel_strain = CONCRETE_ULTIMATE_STRAIN * (
            effective_depth_cm - c_cm
        ) / c_cm
        steel_stress = min(
            steel_yield_kg_cm2,
            max(steel_elastic_modulus_kg_cm2 * steel_strain, 0.0),
        )
        if steel_stress <= 0.0:
            return float("inf"), 0.0
        steel_area = compression / steel_stress
        extreme_strain = max(
            CONCRETE_ULTIMATE_STRAIN * (tension_depth - c_cm) / c_cm,
            0.0,
        )
        phi = min(phi_limit, mtc_flexural_resistance_factor(extreme_strain))
        resistance = (
            phi
            * compression
            * (effective_depth_cm - a_cm / 2.0)
            / 100000.0
        )
        return steel_area, resistance

    previous_c = 0.0
    previous_resistance = 0.0
    bracket: tuple[float, float] | None = None
    maximum_resistance = previous_resistance
    for index in range(1, 2001):
        current_c = effective_depth_cm * index / 2001.0
        _current_area, current_resistance = state_at_c(current_c)
        maximum_resistance = max(maximum_resistance, current_resistance)
        if (
            previous_resistance < design_moment_tn_m
            <= current_resistance
        ):
            bracket = (previous_c, current_c)
            break
        previous_c = current_c
        previous_resistance = current_resistance
    if bracket is None:
        raise ValueError(
            "El momento ultimo excede la capacidad compatible de una seccion "
            "rectangular simplemente reforzada "
            f"(maximo aproximado {maximum_resistance:.3f} Tn.m)."
        )

    lower, upper = bracket
    for _ in range(100):
        mid = (lower + upper) / 2.0
        _area, resistance = state_at_c(mid)
        if resistance < design_moment_tn_m:
            lower = mid
        else:
            upper = mid
    steel_area, _resistance = state_at_c((lower + upper) / 2.0)
    return steel_area
