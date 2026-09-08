"""Concrete deck overhang cantilever design."""

from dataclasses import dataclass

from bridge_design.codes.mtc_2018 import (
    CRACK_CONTROL_REINFORCEMENT_REFERENCE,
    DEFAULT_DECK_OVERHANG_WHEEL_CLEARANCE_TO_RAIL_M,
    DEFAULT_CRACK_CONTROL_EXPOSURE_FACTOR,
    DEFAULT_FLEXURAL_RESISTANCE_FACTOR,
    DEFAULT_SERVICE_STRESS_LEVER_ARM_FACTOR,
    DEFAULT_SHRINKAGE_TEMPERATURE_RATIO,
    FLEXURAL_STRENGTH_REFERENCE,
    LOAD_COMBINATION_REFERENCE,
    TEMPERATURE_REINFORCEMENT_REFERENCE,
    TENSION_DEVELOPMENT_REFERENCE,
    mtc_dynamic_load_allowance_for_slab,
)
from bridge_design.domain.barrier import BarrierDesignResult
from bridge_design.domain.loads import LiveLoads
from bridge_design.domain.materials import MaterialProperties
from bridge_design.domain.rebar_catalog import (
    DEFAULT_MAX_SPACING_M,
    DEFAULT_MIN_SPACING_M,
    DEFAULT_SPACING_STEP_M,
    ReinforcementCaseOptions,
)
from bridge_design.domain.transverse_slab import (
    TransverseLoadLayout,
    TransverseSlabGeometry,
)
from bridge_design.validation.input_validators import require_non_negative, require_positive


LoadGroup = str


class CantileverSlabApplicabilityError(ValueError):
    """Raised when the implemented overhang live-load method is not applicable."""


@dataclass(frozen=True)
class CantileverSlabParameters:
    """Design and detailing assumptions for the deck overhang."""

    concrete_cover_cm: float = 5.0
    main_bar_diameter_cm: float = 1.59
    flexural_resistance_factor: float = DEFAULT_FLEXURAL_RESISTANCE_FACTOR
    shrinkage_temperature_ratio: float = DEFAULT_SHRINKAGE_TEMPERATURE_RATIO
    wheel_clearance_to_traffic_face_m: float = (
        DEFAULT_DECK_OVERHANG_WHEEL_CLEARANCE_TO_RAIL_M
    )
    dynamic_load_allowance: float = mtc_dynamic_load_allowance_for_slab()
    spacing_step_m: float = DEFAULT_SPACING_STEP_M
    minimum_spacing_m: float = DEFAULT_MIN_SPACING_M
    maximum_spacing_m: float = DEFAULT_MAX_SPACING_M
    shear_resistance_factor: float = DEFAULT_FLEXURAL_RESISTANCE_FACTOR
    shear_beta: float = 2.0
    crack_exposure_factor: float = DEFAULT_CRACK_CONTROL_EXPOSURE_FACTOR
    service_stress_lever_arm_factor: float = DEFAULT_SERVICE_STRESS_LEVER_ARM_FACTOR
    development_location_factor: float = 1.0
    development_coating_factor: float = 1.0
    development_lightweight_factor: float = 1.0
    development_confinement_factor: float = 1.0

    def __post_init__(self) -> None:
        require_non_negative(self.concrete_cover_cm, "recubrimiento")
        require_positive(self.main_bar_diameter_cm, "diametro barra principal")
        require_positive(self.flexural_resistance_factor, "phi flexion")
        if self.flexural_resistance_factor > 1.0:
            raise ValueError("phi flexion no debe exceder 1.0.")
        require_positive(self.shrinkage_temperature_ratio, "rho temperatura")
        require_positive(self.wheel_clearance_to_traffic_face_m, "separacion rueda-barrera")
        require_non_negative(self.dynamic_load_allowance, "IM")
        require_positive(self.spacing_step_m, "paso de espaciamiento")
        require_positive(self.minimum_spacing_m, "espaciamiento minimo")
        require_positive(self.maximum_spacing_m, "espaciamiento maximo")
        if self.maximum_spacing_m < self.minimum_spacing_m:
            raise ValueError("El espaciamiento maximo debe ser mayor o igual al minimo.")
        require_positive(self.shear_resistance_factor, "phi corte")
        if self.shear_resistance_factor > 1.0:
            raise ValueError("phi corte no debe exceder 1.0.")
        require_positive(self.shear_beta, "beta corte")
        require_positive(self.crack_exposure_factor, "gamma fisuracion")
        require_positive(self.service_stress_lever_arm_factor, "factor brazo servicio")
        require_positive(self.development_location_factor, "lambda ubicacion")
        require_positive(self.development_coating_factor, "lambda recubrimiento")
        require_positive(self.development_lightweight_factor, "lambda concreto ligero")
        require_positive(self.development_confinement_factor, "lambda confinamiento")


@dataclass(frozen=True)
class CantileverLoadEffect:
    """One load contribution to the exterior-girder cantilever root moment."""

    label: str
    group: LoadGroup
    load_tn: float
    centroid_from_edge_m: float
    arm_to_root_m: float
    root_moment_tn_m: float
    reference: str


@dataclass(frozen=True)
class CantileverCombinedMoment:
    """LRFD combined cantilever root moment."""

    combination_name: str
    limit_state: str
    dc_moment_tn_m: float
    dc_factor: float
    dw_moment_tn_m: float
    dw_factor: float
    pl_moment_tn_m: float
    pl_factor: float
    ll_im_moment_tn_m: float
    ll_im_factor: float
    combined_moment_tn_m: float
    reference: str = LOAD_COMBINATION_REFERENCE

    @property
    def design_moment_tn_m(self) -> float:
        """Return absolute moment demand."""
        return abs(self.combined_moment_tn_m)


@dataclass(frozen=True)
class CantileverFlexuralSteelDesign:
    """Top transverse flexural steel for the deck overhang."""

    controlling_combination_name: str
    design_moment_tn_m: float
    effective_depth_cm: float
    strength_area_cm2_m: float
    minimum_area_cm2_m: float
    required_area_cm2_m: float
    spacing_options: ReinforcementCaseOptions
    reference: str = FLEXURAL_STRENGTH_REFERENCE


@dataclass(frozen=True)
class CantileverCollisionCase:
    """One MTC/AASHTO overhang collision design case."""

    name: str
    moment_tn_m: float
    axial_tension_tn_m: float
    vertical_force_tn_m: float
    status: str
    reference: str


@dataclass(frozen=True)
class CantileverBarrierCollisionDesign:
    """Extreme-event barrier collision demand transmitted to the deck overhang."""

    transverse_force_tn: float
    barrier_height_m: float
    transfer_length_m: float
    interface_shear_tn_m: float
    collision_moment_tn_m: float
    permanent_moment_tn_m: float
    design_moment_tn_m: float
    reference: str
    axial_tension_tn_m: float = 0.0
    status: str = "PENDIENTE"
    scope_note: str = ""
    cases: tuple[CantileverCollisionCase, ...] = ()
    connection_checks: tuple[str, ...] = ()


@dataclass(frozen=True)
class CantileverShearDesign:
    """Vertical one-way shear check at the overhang root."""

    dc_shear_tn: float
    dc_factor: float
    dw_shear_tn: float
    dw_factor: float
    pl_shear_tn: float
    pl_factor: float
    ll_im_shear_tn: float
    ll_im_factor: float
    combined_shear_tn: float
    effective_shear_depth_cm: float
    phi: float
    beta: float
    vc_tn: float
    phi_vc_tn: float
    status: str
    reference: str


@dataclass(frozen=True)
class CantileverCrackControlDesign:
    """Service crack-control check for the selected top overhang steel."""

    service_combination_name: str
    service_moment_tn_m: float
    bar_label: str
    provided_spacing_m: float
    provided_area_cm2_m: float
    steel_stress_kg_cm2: float
    steel_stress_used_kg_cm2: float
    steel_stress_limit_kg_cm2: float
    beta_s: float
    dc_cm: float
    maximum_spacing_m: float
    stress_status: str
    spacing_status: str
    status: str
    reference: str = CRACK_CONTROL_REINFORCEMENT_REFERENCE


@dataclass(frozen=True)
class CantileverTemperatureSteelDesign:
    """Shrinkage and temperature steel for the overhang strip."""

    ratio: float
    gross_area_cm2_m: float
    required_area_cm2_m: float
    spacing_options: ReinforcementCaseOptions
    reference: str = TEMPERATURE_REINFORCEMENT_REFERENCE


@dataclass(frozen=True)
class CantileverDevelopmentDesign:
    """Straight development and added-bar length for overhang top bars."""

    bar_label: str
    bar_diameter_cm: float
    provided_area_cm2_m: float
    required_area_cm2_m: float
    excess_reinforcement_factor: float
    basic_development_length_cm: float
    required_development_length_cm: float
    minimum_past_cutoff_extension_cm: float
    exterior_projection_length_m: float
    interior_anchor_length_m: float
    total_additional_bar_length_m: float
    status: str
    reference: str = TENSION_DEVELOPMENT_REFERENCE


@dataclass(frozen=True)
class CantileverSlabDesignResult:
    """Complete deck-overhang design result."""

    load_effects: tuple[CantileverLoadEffect, ...]
    combinations: tuple[CantileverCombinedMoment, ...]
    controlling_strength: CantileverCombinedMoment
    barrier_collision: CantileverBarrierCollisionDesign | None
    flexural_steel: CantileverFlexuralSteelDesign
    temperature_steel: CantileverTemperatureSteelDesign
    shear: CantileverShearDesign
    crack_control: CantileverCrackControlDesign
    development: CantileverDevelopmentDesign
    parameters: CantileverSlabParameters
    traffic_face_from_edge_m: float
    vehicular_line_from_edge_m: float
    traffic_face_to_exterior_girder_m: float
    vehicular_load_method: str
    applicability_notes: tuple[str, ...]

    @property
    def overall_ok(self) -> bool:
        """A horizontal collision calculation alone cannot approve the connection."""
        return bool(
            self.barrier_collision is not None
            and self.barrier_collision.status == "OK"
            and all(case.status == "OK" for case in self.barrier_collision.cases)
            and all(check == "OK" for check in self.barrier_collision.connection_checks)
            and self.flexural_steel.spacing_options.recommended is not None
            and self.shear.status == "CUMPLE"
            and self.crack_control.status == "CUMPLE"
            and self.development.status == "OK"
        )


def design_cantilever_slab(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    live_loads: LiveLoads,
    layout: TransverseLoadLayout,
    barrier_result: BarrierDesignResult | None = None,
    parameters: CantileverSlabParameters | None = None,
) -> CantileverSlabDesignResult:
    """Return load effects, LRFD combinations, steel and bar lengths for the overhang."""
    require_positive(geometry.overhang_m, "volado de losa")
    from bridge_design.domain._cantilever_slab_calculations import (
        combine_cantilever_moments,
        design_development,
        design_flexural_steel,
        design_temperature_steel,
    )
    from bridge_design.domain._cantilever_slab_checks import (
        design_barrier_collision,
        design_shear,
        review_crack_control,
    )
    from bridge_design.domain._cantilever_slab_loads import cantilever_load_effects

    params = parameters or CantileverSlabParameters()
    (
        effects,
        traffic_face,
        vehicular_line,
        traffic_face_to_girder,
        vehicular_load_method,
        notes,
    ) = cantilever_load_effects(
        geometry,
        materials,
        live_loads,
        layout,
        params,
    )
    combinations = combine_cantilever_moments(effects)
    controlling = min(
        (row for row in combinations if row.limit_state == "Resistencia"),
        key=lambda row: row.combined_moment_tn_m,
    )
    collision = (
        design_barrier_collision(
            barrier_result,
            combinations,
            overhang_m=geometry.overhang_m,
            traffic_face_m=traffic_face,
            girder_spacing_m=geometry.girder_spacing_m,
        )
        if barrier_result
        else None
    )
    flexural = design_flexural_steel(geometry, materials, params, controlling, collision)
    temperature = design_temperature_steel(geometry, params)
    shear = design_shear(geometry, materials, params, effects)
    crack_control = review_crack_control(geometry, materials, params, combinations, flexural)
    development = design_development(geometry, materials, params, flexural)
    return CantileverSlabDesignResult(
        load_effects=effects,
        combinations=combinations,
        controlling_strength=controlling,
        barrier_collision=collision,
        flexural_steel=flexural,
        temperature_steel=temperature,
        shear=shear,
        crack_control=crack_control,
        development=development,
        parameters=params,
        traffic_face_from_edge_m=traffic_face,
        vehicular_line_from_edge_m=vehicular_line,
        traffic_face_to_exterior_girder_m=traffic_face_to_girder,
        vehicular_load_method=vehicular_load_method,
        applicability_notes=notes,
    )
