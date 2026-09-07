"""Cantilever abutment design workflow by 1 m longitudinal strip."""

from dataclasses import dataclass, replace
from math import atan, cos, radians, sin, sqrt, tan
from collections.abc import Mapping

from bridge_design.codes.mtc_2018 import (
    ABUTMENT_TEMPERATURE_REINFORCEMENT_REFERENCE,
    TEMPERATURE_STEEL_MAX_CM2_M,
    TEMPERATURE_STEEL_MIN_CM2_M,
    THICK_MEMBER_SPACING_MAX_M,
    THICK_MEMBER_SPACING_THRESHOLD_CM,
    mtc_tension_development_length_cm,
)
from bridge_design.domain.crack_control import maximum_crack_control_spacing_m
from bridge_design.domain.rebar_catalog import (
    ReinforcementCaseOptions,
    ReinforcementSpacingOption,
    REINFORCING_BAR_CATALOG,
    SpacingGrid,
    generate_spacing_options,
)
from bridge_design.validation.input_validators import (
    require_non_negative,
    require_positive,
    require_range,
)

ABUTMENT_STABILITY_REFERENCE = (
    "Manual de Puentes MTC 2018 / AASHTO LRFD: empujes de suelo, "
    "sobrecarga viva equivalente, combinaciones LRFD y verificaciones de "
    "volteo, deslizamiento y presion de contacto."
)
ABUTMENT_KEY_REFERENCE = (
    "AASHTO LRFD 3.11.5.4 y 10.6.3.4: resistencia pasiva reducida del diente "
    "como aporte contra deslizamiento cuando puede movilizarse."
)
STEEL_ELASTIC_MODULUS_KG_CM2 = 2_000_000.0
DEFAULT_MAX_AGGREGATE_SIZE_IN = 0.75
SIMPLIFIED_SHEAR_BETA = 2.0
CM_PER_IN = 2.54
REF_SHEAR_BETA = (
    "Manual de Puentes MTC 2018 Arts. 2.9.1.5.6.3.3, 2.9.1.5.6.3.4.1 y 2.9.1.5.6.3.4.2; "
    "AASHTO LRFD 5.7.3.3 y 5.7.3.4."
)


@dataclass(frozen=True)
class AbutmentMaterialInputs:
    """Material properties for the abutment design."""

    concrete_strength_kg_cm2: float = 210.0
    steel_yield_kg_cm2: float = 4200.0
    concrete_unit_weight_kg_m3: float = 2400.0
    soil_unit_weight_kg_m3: float = 1925.0

    def __post_init__(self) -> None:
        require_positive(self.concrete_strength_kg_cm2, "f'c")
        require_positive(self.steel_yield_kg_cm2, "fy")
        require_positive(self.concrete_unit_weight_kg_m3, "peso concreto")
        require_positive(self.soil_unit_weight_kg_m3, "peso suelo")


@dataclass(frozen=True)
class AbutmentGeometryInputs:
    """Geometric inputs in meters for a cantilever abutment."""

    retained_height_m: float = 7.0
    bridge_length_m: float = 20.0
    seat_block_height_m: float = 1.50
    seat_wall_width_m: float = 0.25
    bearing_seat_length_m: float = 0.70
    backwall_drop_m: float = 0.40
    backwall_taper_height_m: float = 0.60
    backfill_step_width_m: float = 0.35
    top_step_thickness_m: float = 0.30
    small_batter_width_m: float = 0.30
    upper_stem_thickness_m: float = 0.30
    lower_stem_thickness_m: float = 0.90
    footing_width_m: float = 4.70
    footing_thickness_m: float = 1.10
    toe_length_m: float = 1.10
    front_soil_depth_m: float = 1.50
    bridge_seat_to_bearing_height_m: float = 1.80
    strip_width_m: float = 1.0

    def __post_init__(self) -> None:
        non_negative_fields = {
            "seat_block_height_m",
            "seat_wall_width_m",
            "bearing_seat_length_m",
            "backwall_drop_m",
            "backwall_taper_height_m",
            "backfill_step_width_m",
            "top_step_thickness_m",
            "small_batter_width_m",
            "front_soil_depth_m",
            "bridge_seat_to_bearing_height_m",
        }
        for field_name, value in self.__dict__.items():
            if field_name in non_negative_fields:
                require_non_negative(value, field_name)
                continue
            require_positive(value, field_name)
        if self.footing_width_m <= self.toe_length_m + self.lower_stem_thickness_m:
            raise ValueError("B debe ser mayor que puntera + espesor inferior del muro.")
        if self.retained_height_m <= self.footing_thickness_m:
            raise ValueError("La altura retenida debe ser mayor que el espesor de zapata.")
        if self.upper_stem_thickness_m > self.lower_stem_thickness_m:
            raise ValueError("El espesor superior de pantalla no debe ser mayor que el inferior.")
        if self.backfill_step_width_m > self.heel_length_m:
            raise ValueError("t2 no debe ser mayor que la longitud del talon.")
        if self.seat_block_height_m + self.backwall_drop_m + self.backwall_taper_height_m > self.stem_height_above_footing_m:
            raise ValueError(
                "altura cajuela + altura bloque cajuela + altura transicion no debe exceder "
                "la altura de pantalla sobre zapata."
            )

    @property
    def stem_height_above_footing_m(self) -> float:
        return self.retained_height_m - self.footing_thickness_m

    @property
    def heel_length_m(self) -> float:
        return self.footing_width_m - self.toe_length_m - self.lower_stem_thickness_m

    @property
    def load_x_m(self) -> float:
        return (
            self.lower_stem_thickness_m
            + self.toe_length_m
            - self.upper_stem_thickness_m
            - self.small_batter_width_m
        )

    @property
    def superstructure_load_x_m(self) -> float:
        return self.load_x_m + self.bearing_seat_length_m / 2.0

    @property
    def backwall_height_m(self) -> float:
        return self.retained_height_m - self.seat_block_height_m / 2.0


@dataclass(frozen=True)
class AbutmentLoadInputs:
    """Loads transmitted to one meter of abutment length."""

    pdc_tn_m: float = 12.0
    pdw_tn_m: float = 1.80
    ppl_tn_m: float = 0.0
    pll_im_tn_m: float = 9.494
    braking_tn_m: float = 1.99

    def __post_init__(self) -> None:
        require_non_negative(self.pdc_tn_m, "PDC")
        require_non_negative(self.pdw_tn_m, "PDW")
        require_non_negative(self.ppl_tn_m, "PPL")
        require_non_negative(self.pll_im_tn_m, "PLL+IM")
        require_non_negative(self.braking_tn_m, "BR")


def _validate_coulomb_angles(
    friction_angle_deg: float,
    wall_soil_friction_deg: float,
    backfill_slope_deg: float,
    wall_backface_angle_deg: float,
) -> None:
    if friction_angle_deg >= 90.0:
        raise ValueError("El angulo de friccion debe ser menor que 90 grados.")
    if wall_soil_friction_deg > friction_angle_deg:
        raise ValueError("delta muro-suelo no debe ser mayor que el angulo de friccion.")
    if backfill_slope_deg >= friction_angle_deg:
        raise ValueError("beta pendiente del relleno debe ser menor que el angulo de friccion.")
    if wall_backface_angle_deg <= wall_soil_friction_deg:
        raise ValueError(
            "theta cara posterior se mide desde la horizontal; para cara vertical use 90 grados "
            "y debe ser mayor que delta muro-suelo."
        )
    if wall_backface_angle_deg + backfill_slope_deg >= 180.0:
        raise ValueError("theta + beta debe ser menor que 180 grados para Coulomb.")


@dataclass(frozen=True)
class AbutmentSoilInputs:
    """Soil and seismic inputs."""

    allowable_bearing_kg_cm2: float = 2.67
    friction_angle_deg: float = 30.0
    wall_soil_friction_deg: float = 0.0
    backfill_slope_deg: float = 0.0
    wall_backface_angle_deg: float = 90.0
    bearing_capacity_factor_fs: float = 3.0
    pga: float = 0.30
    fpga: float = 1.20
    vehicular_surcharge_height_m: float | None = None
    pedestrian_surcharge_tn_m2: float = 0.0

    def __post_init__(self) -> None:
        require_positive(self.allowable_bearing_kg_cm2, "qadm")
        require_positive(self.friction_angle_deg, "angulo de friccion")
        require_non_negative(self.wall_soil_friction_deg, "delta")
        require_non_negative(self.backfill_slope_deg, "beta")
        require_positive(self.wall_backface_angle_deg, "theta")
        require_non_negative(self.bearing_capacity_factor_fs, "FS")
        require_non_negative(self.pga, "PGA")
        require_positive(self.fpga, "Fpga")
        if self.vehicular_surcharge_height_m is not None:
            require_non_negative(self.vehicular_surcharge_height_m, "h' sobrecarga vehicular")
        require_non_negative(self.pedestrian_surcharge_tn_m2, "sobrecarga peatonal")
        _validate_coulomb_angles(
            self.friction_angle_deg,
            self.wall_soil_friction_deg,
            self.backfill_slope_deg,
            self.wall_backface_angle_deg,
        )


@dataclass(frozen=True)
class AbutmentKeyInputs:
    """Concrete shear key geometry and passive resistance inputs."""

    enabled: bool = True
    height_m: float = 0.40
    width_m: float = 0.40
    passive_soil_height_m: float = 0.0
    consider_upper_front_passive: bool = False
    passive_coefficient_prime: float | None = None
    passive_resistance_factor: float = 0.50

    def __post_init__(self) -> None:
        if not self.enabled:
            return
        require_positive(self.height_m, "altura de diente")
        require_positive(self.width_m, "ancho de diente")
        require_non_negative(self.passive_soil_height_m, "altura de relleno pasivo")
        if self.passive_coefficient_prime is not None:
            require_positive(self.passive_coefficient_prime, "k'p")
        require_positive(self.passive_resistance_factor, "phi ep")


@dataclass(frozen=True)
class AbutmentReinforcementInputs:
    """Detailing assumptions for structural checks."""

    flexural_phi: float = 0.90
    shear_phi: float = 0.90
    stem_design_phi_for_as: float = 1.00
    footing_design_phi_for_as: float = 0.90
    stem_cover_cm: float = 5.0
    footing_cover_cm: float = 7.5
    stem_main_bar_diameter_cm: float = 1.905
    footing_main_bar_diameter_cm: float = 1.905
    toe_main_bar_diameter_cm: float = 1.27
    stem_main_bar_label: str = '3/4"'
    heel_main_bar_label: str = '3/4"'
    toe_main_bar_label: str = '1/2"'
    key_main_bar_label: str = '1/2"'
    spacing_step_m: float = 0.025
    minimum_spacing_m: float = 0.10
    maximum_spacing_m: float = 0.30
    toe_moment_capacity_multiplier: float = 1.33
    minimum_flexural_capacity_multiplier: float = 1.33
    development_location_factor: float = 1.0
    development_coating_factor: float = 1.0
    development_lightweight_factor: float = 1.0
    development_confinement_factor: float = 1.0


GAMMA_EQ_DEFAULT = 0.50


@dataclass(frozen=True)
class AbutmentInputs:
    """Complete abutment input set."""

    materials: AbutmentMaterialInputs = AbutmentMaterialInputs()
    geometry: AbutmentGeometryInputs = AbutmentGeometryInputs()
    loads: AbutmentLoadInputs = AbutmentLoadInputs()
    soil: AbutmentSoilInputs = AbutmentSoilInputs()
    key: AbutmentKeyInputs = AbutmentKeyInputs()
    reinforcement: AbutmentReinforcementInputs = AbutmentReinforcementInputs()
    is_pure_wall: bool = False
    gamma_eq: float = GAMMA_EQ_DEFAULT

    def __post_init__(self) -> None:
        require_range(self.gamma_eq, "gamma_EQ", 0.0, 1.0)


@dataclass(frozen=True)
class LoadComponent:
    """Load component with resultant and lever arm."""

    name: str
    load_type: str
    value_tn_m: float
    arm_m: float
    vertical_arm_m: float = 0.0

    @property
    def moment_tn_m_m(self) -> float:
        return self.value_tn_m * self.arm_m


@dataclass(frozen=True)
class SoilPressureResult:
    """Lateral earth pressure data."""

    ka: float
    k_ae: float
    seismic_angle_deg: float
    live_surcharge_height_m: float
    lsy_tn_m: float
    lsx_tn_m: float
    eh_tn_m: float
    pae_tn_m: float
    eq_terr_tn_m: float
    pir_tn_m: float
    half_pir_tn_m: float
    peq_tn_m: float
    pedestrian_lsy_tn_m: float
    pedestrian_lsx_tn_m: float


@dataclass(frozen=True)
class ComponentGroup:
    """Grouped unfactored components."""

    vertical_with_bridge: tuple[LoadComponent, ...]
    horizontal_with_bridge: tuple[LoadComponent, ...]
    vertical_without_bridge: tuple[LoadComponent, ...]
    horizontal_without_bridge: tuple[LoadComponent, ...]
    # MTC 2.8.1.1.14.1 combo B: max(0.5·PAE, EH) + PIR (full).
    horizontal_with_bridge_seismic_b: tuple[LoadComponent, ...]
    horizontal_without_bridge_seismic_b: tuple[LoadComponent, ...]


SEISMIC_PAPIR_COMBO_A = "PAE+0.5PIR"
SEISMIC_PAPIR_COMBO_B = "max(0.5PAE,EH)+PIR"
REF_SEISMIC_PAPIR = (
    "Manual de Puentes MTC 2018, Art. 2.8.1.1.14.1: como PAE y PIR no alcanzan "
    "necesariamente sus máximos simultáneamente, se revisan PAE+0.5·PIR y "
    "max(0.5·PAE, EH)+PIR, adoptando la combinación más desfavorable."
)


@dataclass(frozen=True)
class LoadFactors:
    """LRFD load factors used in the workbook."""

    name: str
    dc: float
    dw: float
    ev: float
    ll: float
    ls_vertical: float
    ls_horizontal: float
    eh: float
    eq: float
    br: float
    limit_state: str


@dataclass(frozen=True)
class StabilityStateResult:
    """Stability checks for one limit state."""

    name: str
    vu_tn_m: float
    stabilizing_moment_tn_m_m: float
    hu_tn_m: float
    overturning_moment_tn_m_m: float
    resultant_x_m: float
    eccentricity_m: float
    eccentricity_limit_m: float
    overturning_status: str
    friction_resistance_tn_m: float
    sliding_status: str
    qmax_kg_cm2: float
    qmin_kg_cm2: float
    qmin_linear_kg_cm2: float
    effective_width_m: float
    geotechnical_pressure_kg_cm2: float
    q_allow_kg_cm2: float
    contact_type: str
    contact_length_m: float
    contact_length_ratio: float
    minimum_contact_length_ratio: float
    bearing_status: str
    key_resistance_tn_m: float | None = None
    sliding_with_key_status: str | None = None
    seismic_papir_combination: str | None = None


@dataclass(frozen=True)
class FootingWidthRecommendation:
    """Recommended footing width when overturning or Meyerhof pressure fails."""

    current_width_m: float
    recommended_width_m: float
    increment_step_m: float
    search_max_width_m: float
    controlling_case: str
    current_min_qmin_kg_cm2: float
    current_geotechnical_pressure_kg_cm2: float
    recommended_min_qmin_kg_cm2: float
    recommended_max_qmax_kg_cm2: float
    recommended_max_geotechnical_pressure_kg_cm2: float
    all_bearing_ok_at_recommended_width: bool
    all_overturning_ok_at_recommended_width: bool

    @property
    def found_compliant_width(self) -> bool:
        return self.all_bearing_ok_at_recommended_width and self.all_overturning_ok_at_recommended_width


@dataclass(frozen=True)
class PassiveKeyResult:
    """Passive resistance from shear key."""

    passive_coefficient_prime: float
    kp: float
    top_pressure_tn_m2: float
    bottom_pressure_tn_m2: float
    upper_front_passive_resistance_tn_m: float
    factored_upper_front_passive_tn_m: float
    passive_resistance_tn_m: float
    total_passive_resistance_tn_m: float
    factored_passive_tn_m: float


@dataclass(frozen=True)
class StructuralDesignCase:
    """Flexure and shear summary for one concrete member."""

    name: str
    controlling_moment_tn_m_m: float
    effective_depth_cm: float
    strength_as_cm2_m: float
    cracking_moment_tn_m_m: float
    multiplier_minimum_moment_tn_m_m: float
    minimum_capacity_moment_tn_m_m: float
    capacity_minimum_as_cm2_m: float
    minimum_as_cm2_m: float
    required_as_cm2_m: float
    spacing_options: ReinforcementCaseOptions
    selected_bar_label: str
    selected_spacing_m: float
    provided_as_cm2_m: float
    moment_resistance_tn_m_m: float
    moment_status: str
    temperature_as_cm2_m: float
    shear_demand_tn_m: float
    shear_resistance_tn_m: float
    shear_status: str
    shear_effective_depth_cm: float = 0.0
    shear_beta: float = 0.0
    shear_longitudinal_strain: float = 0.0
    shear_crack_spacing_in: float = 0.0
    shear_effective_crack_spacing_in: float = 0.0
    shear_beta_method: str = ""
    shear_controlling_moment_tn_m_m: float = 0.0
    is_custom_selection: bool = False
    notes: str = ""
    strength_limit_mu_tn_m_m: float = 0.0
    extreme_limit_mu_tn_m_m: float = 0.0
    strength_limit_as_cm2_m: float = 0.0
    extreme_limit_as_cm2_m: float = 0.0
    strength_moment_resistance_tn_m_m: float = 0.0
    extreme_moment_resistance_tn_m_m: float = 0.0
    strength_moment_status: str = ""
    extreme_moment_status: str = ""


@dataclass(frozen=True)
class AbutmentTemperatureSteelResult:
    """Temperature and shrinkage steel for one abutment member zone."""

    b_cm: float
    h_cm: float
    raw_as_cm2_m: float
    required_as_cm2_m: float
    maximum_spacing_m: float
    reference: str = ABUTMENT_TEMPERATURE_REINFORCEMENT_REFERENCE


@dataclass(frozen=True)
class AbutmentSecondaryReinforcementCase:
    """Minimum distribution reinforcement not controlled by primary flexure."""

    name: str
    element: str
    face: str
    direction: str
    required_as_cm2_m: float
    spacing_options: ReinforcementCaseOptions
    selected_bar_label: str
    selected_spacing_m: float
    provided_as_cm2_m: float
    status: str
    temperature_required_as_cm2_m: float = 0.0
    primary_steel_as_cm2_m: float = 0.0
    temperature_b_cm: float = 0.0
    temperature_h_cm: float = 0.0
    raw_temperature_as_cm2_m: float = 0.0
    maximum_spacing_m: float = THICK_MEMBER_SPACING_MAX_M
    spacing_status: str = "OK"
    is_custom_selection: bool = False
    reference: str = ABUTMENT_TEMPERATURE_REINFORCEMENT_REFERENCE
    notes: str = ""


@dataclass(frozen=True)
class AbutmentCrackCheck:
    """Crack control review for one abutment reinforcement case."""

    element: str
    service_moment_tn_m_m: float
    steel_stress_kg_cm2: float
    steel_stress_used_kg_cm2: float
    beta_s: float
    dc_cm: float
    provided_spacing_m: float
    maximum_spacing_m: float
    status: str


@dataclass(frozen=True)
class AbutmentDevelopmentCheck:
    """Tension development and anchorage review for one bar family."""

    element: str
    bar_label: str
    required_ld_cm: float
    basic_ld_cm: float
    required_hooked_ld_cm: float
    hook_extension_cm: float
    available_length_cm: float
    excess_reinforcement_factor: float
    anchorage_type: str
    status: str


@dataclass(frozen=True)
class AbutmentStemReinforcementCut:
    """Single cutoff recommendation for the main stem reinforcement."""

    lower_bar_label: str
    lower_spacing_m: float
    lower_provided_as_cm2_m: float
    upper_bar_label: str
    upper_spacing_m: float
    upper_provided_as_cm2_m: float
    continuous_every_n_bars: int
    minimum_as_cm2_m: float
    theoretical_cut_height_m: float
    constructive_cut_height_m: float
    development_extension_m: float
    lower_cut_bar_length_m: float
    continuous_bar_length_m: float
    controlling_moment_at_cut_tn_m_m: float
    required_as_at_cut_cm2_m: float
    moment_resistance_at_cut_tn_m_m: float
    required_moment_at_cut_tn_m_m: float
    effective_depth_at_cut_cm: float
    thickness_at_cut_cm: float
    strength_as_at_cut_cm2_m: float
    minimum_as_at_cut_cm2_m: float
    upper_spacing_limit_m: float
    status: str
    notes: str = ""


@dataclass(frozen=True)
class AbutmentBarDetail:
    """Bar schedule row for the abutment sketch."""

    mark: str
    element: str
    face: str
    bar_label: str
    spacing_m: float
    length_m: float
    anchorage_m: float
    note: str


@dataclass(frozen=True)
class AbutmentDesignResult:
    """Complete abutment design result."""

    inputs: AbutmentInputs
    dc_self_weight_tn_m: float
    dc_self_x_m: float
    dc_self_y_m: float
    ev_weight_tn_m: float
    ev_x_m: float
    ev_y_m: float
    concrete_components: tuple[LoadComponent, ...]
    soil_components: tuple[LoadComponent, ...]
    pressures: SoilPressureResult
    components: ComponentGroup
    load_factors: tuple[LoadFactors, ...]
    with_bridge: tuple[StabilityStateResult, ...]
    without_bridge: tuple[StabilityStateResult, ...]
    service_with_bridge: tuple[StabilityStateResult, ...]
    service_without_bridge: tuple[StabilityStateResult, ...]
    extreme_seismic_with_bridge: tuple[StabilityStateResult, StabilityStateResult]
    extreme_seismic_without_bridge: tuple[StabilityStateResult, StabilityStateResult]
    footing_width_recommendation: FootingWidthRecommendation | None
    key: PassiveKeyResult | None
    stem_design: StructuralDesignCase
    stem_reinforcement_cut: AbutmentStemReinforcementCut | None
    heel_design: StructuralDesignCase
    toe_design: StructuralDesignCase
    key_design: StructuralDesignCase | None
    secondary_reinforcement: tuple[AbutmentSecondaryReinforcementCase, ...]
    crack_checks: tuple[AbutmentCrackCheck, ...]
    development_checks: tuple[AbutmentDevelopmentCheck, ...]
    bar_details: tuple[AbutmentBarDetail, ...]
    reference: str = ABUTMENT_STABILITY_REFERENCE


def abutment_load_factors(gamma_eq: float = GAMMA_EQ_DEFAULT) -> tuple[LoadFactors, ...]:
    """Return LRFD factors; Evento Extremo I uses γEQ on live, surcharge and braking."""
    require_range(gamma_eq, "gamma_EQ", 0.0, 1.0)
    return (
        LoadFactors("Resistencia Ia", 0.90, 0.65, 1.00, 0.00, 0.00, 1.75, 1.50, 0.00, 1.75, "strength"),
        LoadFactors("Resistencia Ib", 1.25, 1.50, 1.35, 1.75, 1.75, 1.75, 1.50, 0.00, 1.75, "strength"),
        LoadFactors("Evento Extremo I", 1.00, 1.00, 1.00, gamma_eq, gamma_eq, gamma_eq, 1.00, 1.00, gamma_eq, "extreme"),
        LoadFactors("Servicio I", 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 0.00, 1.00, "service"),
    )


DEFAULT_LOAD_FACTORS: tuple[LoadFactors, ...] = abutment_load_factors()


def eccentricity_limit_m(footing_width_m: float, factors: LoadFactors) -> float:
    """Resultant kern limit: service B/6, strength B/3, seismic MTC 2.8.1.1.14.1."""
    b = footing_width_m
    if factors.limit_state == "service":
        return b / 6.0
    if factors.limit_state == "extreme":
        return b * (1.0 / 6.0 + factors.ll * (0.40 - 1.0 / 6.0))
    return b / 3.0


def _minimum_contact_ratio_for_limit(e_limit: float, footing_width_m: float) -> float:
    """Contact ratio implied by a triangular pressure at the kern limit (report only)."""
    b = footing_width_m
    if b <= 1e-12:
        return 0.0
    if e_limit <= b / 6.0 + 1e-12:
        return 1.0
    return max(3.0 * (0.50 - e_limit / b), 0.0)


def pure_wall_load_inputs() -> AbutmentLoadInputs:
    """Return zero bridge actions for an independent cantilever wall."""
    return AbutmentLoadInputs(
        pdc_tn_m=0.0,
        pdw_tn_m=0.0,
        ppl_tn_m=0.0,
        pll_im_tn_m=0.0,
        braking_tn_m=0.0,
    )


def pure_wall_geometry_inputs(geometry: AbutmentGeometryInputs | None = None) -> AbutmentGeometryInputs:
    """Return a simple cantilever-wall geometry with bridge details removed."""
    base = geometry or AbutmentGeometryInputs()
    return replace(
        base,
        bridge_length_m=base.bridge_length_m,
        seat_block_height_m=0.0,
        seat_wall_width_m=0.0,
        bearing_seat_length_m=0.0,
        backwall_drop_m=0.0,
        backwall_taper_height_m=0.0,
        backfill_step_width_m=0.0,
        top_step_thickness_m=0.0,
        small_batter_width_m=0.0,
        bridge_seat_to_bearing_height_m=0.0,
    )


def pure_wall_inputs(inputs: AbutmentInputs | None = None) -> AbutmentInputs:
    """Return inputs normalized for the PDF-style simple cantilever wall."""
    data = inputs or AbutmentInputs(is_pure_wall=True)
    return replace(
        data,
        geometry=pure_wall_geometry_inputs(data.geometry),
        loads=pure_wall_load_inputs(),
        is_pure_wall=True,
    )


def solve_abutment_design(
    inputs: AbutmentInputs | None = None,
    selected_reinforcement: Mapping[str, ReinforcementSpacingOption] | None = None,
) -> AbutmentDesignResult:
    """Return all abutment checks for the given input set."""
    data = inputs or AbutmentInputs()
    if data.is_pure_wall:
        data = pure_wall_inputs(data)
    selected = selected_reinforcement or {}
    dc_components = _concrete_components(data)
    ev_components = _soil_components(data)
    dc_weight, dc_x, dc_y = _resultant(dc_components)
    ev_weight, ev_x, ev_y = _resultant(ev_components)
    pressures = _soil_pressures(data, dc_weight, ev_weight, dc_y, ev_y)
    components = _load_components(data, dc_weight, dc_x, dc_y, ev_weight, ev_x, ev_y, pressures)
    key = _passive_key(data) if data.key.enabled else None
    load_factors = abutment_load_factors(data.gamma_eq)
    strength_factors = load_factors[:2]
    extreme_factors = load_factors[2]

    def _strength_states(
        vertical: tuple[LoadComponent, ...],
        horizontal: tuple[LoadComponent, ...],
    ) -> tuple[StabilityStateResult, ...]:
        return tuple(
            _stability_state(data, factors, vertical, horizontal, key)
            for factors in strength_factors
        )

    extreme_without = _extreme_seismic_pair(
        data,
        extreme_factors,
        components.vertical_without_bridge,
        components.horizontal_without_bridge,
        components.horizontal_without_bridge_seismic_b,
        key,
    )
    without_bridge = _strength_states(
        components.vertical_without_bridge,
        components.horizontal_without_bridge,
    ) + (
        replace(_governing_seismic_state(*extreme_without), name="Evento Extremo I"),
    )
    if data.is_pure_wall:
        with_bridge = without_bridge
        extreme_with = extreme_without
    else:
        extreme_with = _extreme_seismic_pair(
            data,
            extreme_factors,
            components.vertical_with_bridge,
            components.horizontal_with_bridge,
            components.horizontal_with_bridge_seismic_b,
            key,
        )
        with_bridge = _strength_states(
            components.vertical_with_bridge,
            components.horizontal_with_bridge,
        ) + (
            replace(_governing_seismic_state(*extreme_with), name="Evento Extremo I"),
        )
    service_without_bridge = (
        _stability_state(
            data,
            load_factors[3],
            components.vertical_without_bridge,
            components.horizontal_without_bridge,
            key,
        ),
    )
    service_with_bridge = service_without_bridge if data.is_pure_wall else (
        _stability_state(
            data,
            load_factors[3],
            components.vertical_with_bridge,
            components.horizontal_with_bridge,
            key,
        ),
    )
    stem_design, heel_design, toe_design = _structural_design(data, pressures, with_bridge, selected)
    key_design = _key_structural_design(data, key, selected)
    structural_cases = (
        (stem_design, heel_design, toe_design, key_design)
        if key_design is not None
        else (stem_design, heel_design, toe_design)
    )
    crack_checks = _crack_checks(data, pressures, service_with_bridge[0], structural_cases)
    development_checks = _development_checks(data, structural_cases)
    secondary_reinforcement = _secondary_reinforcement(data, selected)
    stem_reinforcement_cut = _stem_reinforcement_cut(data, pressures, stem_design, development_checks)
    bar_details = _bar_details(data, structural_cases, development_checks, secondary_reinforcement)
    return AbutmentDesignResult(
        inputs=data,
        dc_self_weight_tn_m=dc_weight,
        dc_self_x_m=dc_x,
        dc_self_y_m=dc_y,
        ev_weight_tn_m=ev_weight,
        ev_x_m=ev_x,
        ev_y_m=ev_y,
        concrete_components=dc_components,
        soil_components=ev_components,
        pressures=pressures,
        components=components,
        load_factors=load_factors,
        with_bridge=with_bridge,
        without_bridge=without_bridge,
        service_with_bridge=service_with_bridge,
        service_without_bridge=service_without_bridge,
        extreme_seismic_with_bridge=extreme_with,
        extreme_seismic_without_bridge=extreme_without,
        footing_width_recommendation=_footing_width_recommendation(
            data,
            with_bridge,
            without_bridge,
            service_with_bridge,
            service_without_bridge,
        ),
        key=key,
        stem_design=stem_design,
        stem_reinforcement_cut=stem_reinforcement_cut,
        heel_design=heel_design,
        toe_design=toe_design,
        key_design=key_design,
        secondary_reinforcement=secondary_reinforcement,
        crack_checks=crack_checks,
        development_checks=development_checks,
        bar_details=bar_details,
    )


def _footing_width_recommendation(
    inputs: AbutmentInputs,
    with_bridge: tuple[StabilityStateResult, ...],
    without_bridge: tuple[StabilityStateResult, ...],
    service_with_bridge: tuple[StabilityStateResult, ...],
    service_without_bridge: tuple[StabilityStateResult, ...],
) -> FootingWidthRecommendation | None:
    current_states = _bearing_recommendation_states(
        inputs,
        with_bridge,
        without_bridge,
        service_with_bridge,
        service_without_bridge,
    )
    failing_states = tuple(
        (label, state) for label, state in current_states if _footing_width_state_fails(state)
    )
    if not failing_states:
        return None
    controlling_label, controlling_state = _footing_width_controlling_state(failing_states)

    step_m = 0.05
    current_width = inputs.geometry.footing_width_m
    max_width = max(current_width + 20.0, current_width * 4.0)
    candidate_width = current_width
    recommended_states = current_states

    while candidate_width < max_width:
        candidate_width = round(candidate_width + step_m, 10)
        candidate_inputs = replace(
            inputs,
            geometry=replace(inputs.geometry, footing_width_m=candidate_width),
        )
        recommended_states = _stability_states_for_width_recommendation(candidate_inputs)
        if all(not _footing_width_state_fails(state) for _, state in recommended_states):
            break
    else:
        recommended_states = current_states
        candidate_width = current_width

    return _footing_width_recommendation_result(
        current_width_m=current_width,
        recommended_width_m=candidate_width,
        increment_step_m=step_m,
        search_max_width_m=max_width,
        controlling_case=controlling_label,
        controlling_state=controlling_state,
        recommended_states=recommended_states,
    )


def _footing_width_recommendation_result(
    *,
    current_width_m: float,
    recommended_width_m: float,
    increment_step_m: float,
    search_max_width_m: float,
    controlling_case: str,
    controlling_state: StabilityStateResult,
    recommended_states: tuple[tuple[str, StabilityStateResult], ...],
) -> FootingWidthRecommendation:
    return FootingWidthRecommendation(
        current_width_m=current_width_m,
        recommended_width_m=recommended_width_m,
        increment_step_m=increment_step_m,
        search_max_width_m=search_max_width_m,
        controlling_case=controlling_case,
        current_min_qmin_kg_cm2=controlling_state.qmin_linear_kg_cm2,
        current_geotechnical_pressure_kg_cm2=controlling_state.geotechnical_pressure_kg_cm2,
        recommended_min_qmin_kg_cm2=min(state.qmin_kg_cm2 for _, state in recommended_states),
        recommended_max_qmax_kg_cm2=max(state.qmax_kg_cm2 for _, state in recommended_states),
        recommended_max_geotechnical_pressure_kg_cm2=max(
            state.geotechnical_pressure_kg_cm2 for _, state in recommended_states
        ),
        all_bearing_ok_at_recommended_width=all(
            state.bearing_status == "OK" for _, state in recommended_states
        ),
        all_overturning_ok_at_recommended_width=all(
            state.overturning_status == "OK" for _, state in recommended_states
        ),
    )


def _footing_width_state_fails(state: StabilityStateResult) -> bool:
    return state.bearing_status != "OK" or state.overturning_status != "OK"


def _footing_width_controlling_state(
    failing_states: tuple[tuple[str, StabilityStateResult], ...],
) -> tuple[str, StabilityStateResult]:
    bearing_failing = tuple(item for item in failing_states if item[1].bearing_status != "OK")
    if bearing_failing:
        return max(
            bearing_failing,
            key=lambda item: item[1].geotechnical_pressure_kg_cm2 / item[1].q_allow_kg_cm2,
        )
    return max(
        failing_states,
        key=lambda item: (
            abs(item[1].eccentricity_m) / item[1].eccentricity_limit_m
            if item[1].eccentricity_limit_m > 0.0
            else float("inf")
        ),
    )


def _bearing_recommendation_states(
    inputs: AbutmentInputs,
    with_bridge: tuple[StabilityStateResult, ...],
    without_bridge: tuple[StabilityStateResult, ...],
    service_with_bridge: tuple[StabilityStateResult, ...],
    service_without_bridge: tuple[StabilityStateResult, ...],
) -> tuple[tuple[str, StabilityStateResult], ...]:
    if inputs.is_pure_wall:
        return (
            *((f"MURO PURO - {state.name}", state) for state in with_bridge),
            *((f"MURO PURO - {state.name}", state) for state in service_with_bridge),
        )
    return (
        *((f"CON PUENTE - {state.name}", state) for state in with_bridge),
        *((f"SIN PUENTE - {state.name}", state) for state in without_bridge),
        *((f"CON PUENTE - {state.name}", state) for state in service_with_bridge),
        *((f"SIN PUENTE - {state.name}", state) for state in service_without_bridge),
    )


def _stability_states_for_width_recommendation(
    inputs: AbutmentInputs,
) -> tuple[tuple[str, StabilityStateResult], ...]:
    dc_components = _concrete_components(inputs)
    ev_components = _soil_components(inputs)
    dc_weight, dc_x, dc_y = _resultant(dc_components)
    ev_weight, ev_x, ev_y = _resultant(ev_components)
    pressures = _soil_pressures(inputs, dc_weight, ev_weight, dc_y, ev_y)
    components = _load_components(inputs, dc_weight, dc_x, dc_y, ev_weight, ev_x, ev_y, pressures)
    key = _passive_key(inputs) if inputs.key.enabled else None
    load_factors = abutment_load_factors(inputs.gamma_eq)
    strength_factors = load_factors[:2]
    extreme_factors = load_factors[2]
    without_strength = tuple(
        _stability_state(
            inputs,
            factors,
            components.vertical_without_bridge,
            components.horizontal_without_bridge,
            key,
        )
        for factors in strength_factors
    )
    extreme_without = _extreme_seismic_pair(
        inputs,
        extreme_factors,
        components.vertical_without_bridge,
        components.horizontal_without_bridge,
        components.horizontal_without_bridge_seismic_b,
        key,
    )
    without_bridge = without_strength + (
        replace(_governing_seismic_state(*extreme_without), name="Evento Extremo I"),
    )
    service_without_bridge = (
        _stability_state(
            inputs,
            load_factors[3],
            components.vertical_without_bridge,
            components.horizontal_without_bridge,
            key,
        ),
    )
    if inputs.is_pure_wall:
        return (
            *((f"MURO PURO - {state.name}", state) for state in without_bridge),
            *((f"MURO PURO - {state.name}", state) for state in service_without_bridge),
        )
    with_strength = tuple(
        _stability_state(
            inputs,
            factors,
            components.vertical_with_bridge,
            components.horizontal_with_bridge,
            key,
        )
        for factors in strength_factors
    )
    extreme_with = _extreme_seismic_pair(
        inputs,
        extreme_factors,
        components.vertical_with_bridge,
        components.horizontal_with_bridge,
        components.horizontal_with_bridge_seismic_b,
        key,
    )
    with_bridge = with_strength + (
        replace(_governing_seismic_state(*extreme_with), name="Evento Extremo I"),
    )
    service_with_bridge = (
        _stability_state(
            inputs,
            load_factors[3],
            components.vertical_with_bridge,
            components.horizontal_with_bridge,
            key,
        ),
    )
    return (
        *((f"CON PUENTE - {state.name}", state) for state in with_bridge),
        *((f"SIN PUENTE - {state.name}", state) for state in without_bridge),
        *((f"CON PUENTE - {state.name}", state) for state in service_with_bridge),
        *((f"SIN PUENTE - {state.name}", state) for state in service_without_bridge),
    )


def equivalent_vehicular_surcharge_height_m(retained_height_m: float) -> float:
    """Return default equivalent soil height for vehicular live load surcharge."""
    require_positive(retained_height_m, "H")
    table = ((1.50, 1.20), (3.00, 0.90), (6.00, 0.60), (9.00, 0.60))
    if retained_height_m <= table[0][0]:
        return table[0][1]
    for (h0, v0), (h1, v1) in zip(table, table[1:]):
        if retained_height_m <= h1:
            ratio = (retained_height_m - h0) / (h1 - h0)
            return v0 + ratio * (v1 - v0)
    return table[-1][1]


def coulomb_active_coefficient(
    friction_angle_deg: float,
    wall_soil_friction_deg: float,
    backfill_slope_deg: float,
    wall_backface_angle_deg: float,
) -> float:
    """Return Coulomb active earth pressure coefficient."""
    _validate_coulomb_angles(
        friction_angle_deg,
        wall_soil_friction_deg,
        backfill_slope_deg,
        wall_backface_angle_deg,
    )
    phi = radians(friction_angle_deg)
    delta = radians(wall_soil_friction_deg)
    beta = radians(backfill_slope_deg)
    theta = radians(wall_backface_angle_deg)
    root_term = sqrt(
        sin(phi + delta)
        * sin(phi - beta)
        / (sin(theta - delta) * sin(theta + beta))
    )
    denominator = (
        (1.0 + root_term) ** 2.0
        * sin(theta) ** 2.0
        * sin(theta - delta)
    )
    return sin(theta + phi) ** 2.0 / denominator


def rankine_passive_coefficient(friction_angle_deg: float) -> float:
    """Return Rankine passive earth pressure coefficient."""
    require_positive(friction_angle_deg, "angulo de friccion")
    if friction_angle_deg >= 90.0:
        raise ValueError("El angulo de friccion debe ser menor que 90 grados.")
    return tan(radians(45.0 + friction_angle_deg / 2.0)) ** 2.0


def mononobe_okabe_active_coefficient(inputs: AbutmentInputs) -> tuple[float, float]:
    """Return seismic active coefficient and seismic angle in degrees."""
    soil = inputs.soil
    as_coeff = soil.fpga * soil.pga
    kh = 0.5 * as_coeff
    kv = 0.0
    seismic_angle = atan(kh / (1.0 - kv))
    phi = radians(soil.friction_angle_deg)
    delta = radians(soil.wall_soil_friction_deg)
    beta = radians(soil.backfill_slope_deg)
    theta = radians(0.0)
    numerator = cos(phi - seismic_angle - theta) ** 2.0
    denominator = (
        cos(seismic_angle)
        * cos(theta) ** 2.0
        * cos(delta + theta + seismic_angle)
        * (
            1.0
            + sqrt(
                sin(phi + delta)
                * sin(phi - seismic_angle - beta)
                / (
                    cos(delta + theta + seismic_angle)
                    * cos(beta - theta)
                )
            )
        )
        ** 2.0
    )
    return numerator / denominator, seismic_angle * 180.0 / 3.141592653589793


def _concrete_components(inputs: AbutmentInputs) -> tuple[LoadComponent, ...]:
    g = inputs.geometry
    gamma = inputs.materials.concrete_unit_weight_kg_m3 / 1000.0
    e71 = g.stem_height_above_footing_m
    if inputs.is_pure_wall:
        rows = (
            (
                "Pantalla rectangular",
                g.upper_stem_thickness_m * e71,
                g.toe_length_m + g.lower_stem_thickness_m - g.upper_stem_thickness_m / 2.0,
                g.footing_thickness_m + e71 / 2.0,
            ),
            (
                "Ensanche de pantalla",
                (g.lower_stem_thickness_m - g.upper_stem_thickness_m) * e71 / 2.0,
                g.toe_length_m + (g.lower_stem_thickness_m - g.upper_stem_thickness_m) / 3.0,
                g.footing_thickness_m + e71 / 3.0,
            ),
            ("Zapata - puntera", g.toe_length_m * g.footing_thickness_m, g.toe_length_m / 2.0, g.footing_thickness_m / 2.0),
            (
                "Zapata - bajo pantalla",
                g.lower_stem_thickness_m * g.footing_thickness_m,
                g.toe_length_m + g.lower_stem_thickness_m / 2.0,
                g.footing_thickness_m / 2.0,
            ),
            (
                "Zapata - talon",
                g.heel_length_m * g.footing_thickness_m,
                g.toe_length_m + g.lower_stem_thickness_m + g.heel_length_m / 2.0,
                g.footing_thickness_m / 2.0,
            ),
        )
        return tuple(
            LoadComponent(name, "DC", area * gamma * g.strip_width_m, x, y)
            for name, area, x, y in rows
        )
    m67 = g.load_x_m
    puntera = g.toe_length_m
    e_inferior = g.lower_stem_thickness_m
    e_superior = g.upper_stem_thickness_m
    t1 = g.small_batter_width_m
    t2 = g.backfill_step_width_m
    cajuela = g.bearing_seat_length_m
    e_parapeto = g.seat_wall_width_m
    altura_cajuela = g.seat_block_height_m
    altura_bloque_cajuela = g.backwall_drop_m
    altura_transicion = g.backwall_taper_height_m
    altura_pantalla = e71 - altura_cajuela - altura_bloque_cajuela
    altura_ensanche_inferior = altura_pantalla - altura_transicion
    x_bloque_izq = puntera + e_inferior - e_superior - t1
    x_pantalla_superior_izq = puntera + e_inferior - e_superior
    x_pantalla_superior_der = puntera + e_inferior
    x_bloque_der = x_pantalla_superior_der + t2
    rows = (
        (
            "1 Parapeto",
            e_parapeto * altura_cajuela,
            x_bloque_der - e_parapeto / 2.0,
            g.retained_height_m - altura_cajuela / 2.0,
        ),
        (
            "2 Cajuela",
            altura_bloque_cajuela * (cajuela + e_parapeto),
            x_bloque_izq + (cajuela + e_parapeto) / 2.0,
            g.retained_height_m - altura_cajuela - altura_bloque_cajuela / 2.0,
        ),
        (
            "3 Transicion t1",
            t1 * altura_transicion / 2.0,
            x_bloque_izq + 2.0 * t1 / 3.0,
            g.footing_thickness_m + altura_pantalla - altura_transicion / 3.0,
        ),
        (
            "4 Pantalla e superior",
            e_superior * altura_pantalla,
            x_pantalla_superior_izq + e_superior / 2.0,
            g.footing_thickness_m + altura_pantalla / 2.0,
        ),
        (
            "5 Transicion t2",
            t2 * altura_transicion / 2.0,
            x_pantalla_superior_der + t2 / 3.0,
            g.footing_thickness_m + altura_pantalla - altura_transicion / 3.0,
        ),
        (
            "6 Ensanche inferior",
            (e_inferior - e_superior) * altura_ensanche_inferior / 2.0,
            puntera + 2.0 * (e_inferior - e_superior) / 3.0,
            g.footing_thickness_m + altura_ensanche_inferior / 3.0,
        ),
        (
            "7 Zapata",
            g.footing_width_m * g.footing_thickness_m,
            g.footing_width_m / 2.0,
            g.footing_thickness_m / 2.0,
        ),
    )
    return tuple(
        LoadComponent(name, "DC", area * gamma * g.strip_width_m, x, y)
        for name, area, x, _y in rows
        for y in (_y,)
    )


def _soil_components(inputs: AbutmentInputs) -> tuple[LoadComponent, ...]:
    g = inputs.geometry
    gamma = inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    e71 = g.stem_height_above_footing_m
    if inputs.is_pure_wall:
        effective_heel_m = g.heel_length_m - g.backfill_step_width_m
        rows = (
            (
                "Relleno talon",
                effective_heel_m * e71,
                g.toe_length_m + g.lower_stem_thickness_m + g.backfill_step_width_m + effective_heel_m / 2.0,
                g.footing_thickness_m + e71 / 2.0,
            ),
            (
                "Relleno junto a pantalla",
                g.backfill_step_width_m * e71,
                g.toe_length_m + g.lower_stem_thickness_m + g.backfill_step_width_m / 2.0,
                g.footing_thickness_m + e71 / 2.0,
            ),
            (
                "Relleno sobre puntera",
                g.toe_length_m * max(g.front_soil_depth_m - g.footing_thickness_m, 0.0),
                g.toe_length_m / 2.0,
                g.footing_thickness_m + max(g.front_soil_depth_m - g.footing_thickness_m, 0.0) / 2.0,
            ),
        )
        return tuple(
            LoadComponent(name, "EV", area * gamma * g.strip_width_m, x, y)
            for name, area, x, y in rows
            if area > 0.0
        )
    front_depth = g.front_soil_depth_m
    puntera = g.toe_length_m
    e_inferior = g.lower_stem_thickness_m
    e_superior = g.upper_stem_thickness_m
    t2 = g.backfill_step_width_m
    altura_transicion = g.backwall_taper_height_m
    altura_pantalla = e71 - g.seat_block_height_m - g.backwall_drop_m
    altura_ensanche_inferior = altura_pantalla - altura_transicion
    altura_relleno_frontal = max(front_depth - g.footing_thickness_m, 0.0)
    batter_width = (
        altura_relleno_frontal * (e_inferior - e_superior) / altura_ensanche_inferior
        if altura_relleno_frontal > 0.0 and e_inferior > e_superior and altura_ensanche_inferior > 0.0
        else 0.0
    )
    ancho_relleno_posterior = g.footing_width_m - puntera - e_inferior - t2
    x_pantalla_inferior_der = puntera + e_inferior
    x_relleno_posterior_izq = x_pantalla_inferior_der + t2
    rows = (
        (
            "8 Relleno posterior",
            ancho_relleno_posterior * e71,
            x_relleno_posterior_izq + ancho_relleno_posterior / 2.0,
            g.footing_thickness_m + e71 / 2.0,
        ),
        (
            "9 Relleno triangular t2",
            t2 * altura_transicion / 2.0,
            x_pantalla_inferior_der + 2.0 * t2 / 3.0,
            g.footing_thickness_m + altura_pantalla - 2.0 * altura_transicion / 3.0,
        ),
        (
            "10 Relleno junto pantalla",
            t2 * altura_ensanche_inferior,
            x_pantalla_inferior_der + t2 / 2.0,
            g.footing_thickness_m + altura_ensanche_inferior / 2.0,
        ),
        (
            "11 Relleno triangular frontal",
            batter_width * altura_relleno_frontal / 2.0,
            puntera + batter_width / 3.0,
            g.footing_thickness_m + 2.0 * altura_relleno_frontal / 3.0,
        ),
        (
            "12 Relleno frontal",
            puntera * altura_relleno_frontal,
            puntera / 2.0,
            g.footing_thickness_m + altura_relleno_frontal / 2.0,
        ),
    )
    return tuple(
        LoadComponent(name, "EV", area * gamma * g.strip_width_m, x, y)
        for name, area, x, y in rows
        if area > 0.0
    )


def _resultant(components: tuple[LoadComponent, ...]) -> tuple[float, float, float]:
    total = sum(component.value_tn_m for component in components)
    x_moment = sum(component.moment_tn_m_m for component in components)
    y_moment = sum(component.value_tn_m * component.vertical_arm_m for component in components)
    return total, x_moment / total, y_moment / total


def _soil_pressures(
    inputs: AbutmentInputs,
    dc_weight_tn_m: float,
    ev_weight_tn_m: float,
    dc_y_m: float,
    ev_y_m: float,
) -> SoilPressureResult:
    g = inputs.geometry
    soil = inputs.soil
    gamma_soil = inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    ka = coulomb_active_coefficient(
        soil.friction_angle_deg,
        soil.wall_soil_friction_deg,
        soil.backfill_slope_deg,
        soil.wall_backface_angle_deg,
    )
    h_eq = soil.vehicular_surcharge_height_m
    if h_eq is None:
        h_eq = equivalent_vehicular_surcharge_height_m(g.retained_height_m)
    effective_heel_m = g.heel_length_m - g.backfill_step_width_m
    lsy = effective_heel_m * h_eq * gamma_soil
    lsx = ka * h_eq * gamma_soil * g.retained_height_m
    pedestrian_lsy = soil.pedestrian_surcharge_tn_m2 * effective_heel_m
    pedestrian_lsx = ka * soil.pedestrian_surcharge_tn_m2 * g.retained_height_m
    eh = 0.5 * ka * gamma_soil * g.retained_height_m**2.0
    k_ae, seismic_angle = mononobe_okabe_active_coefficient(inputs)
    pae = 0.5 * k_ae * gamma_soil * g.retained_height_m**2.0
    eq_terr = pae - eh
    as_coeff = soil.fpga * soil.pga
    kh = 0.5 * as_coeff
    pir = kh * (dc_weight_tn_m + ev_weight_tn_m)
    peq = (inputs.loads.pdc_tn_m + inputs.loads.pdw_tn_m) * as_coeff
    return SoilPressureResult(
        ka=ka,
        k_ae=k_ae,
        seismic_angle_deg=seismic_angle,
        live_surcharge_height_m=h_eq,
        lsy_tn_m=lsy,
        lsx_tn_m=lsx + pedestrian_lsx,
        eh_tn_m=eh,
        pae_tn_m=pae,
        eq_terr_tn_m=eq_terr,
        pir_tn_m=pir,
        half_pir_tn_m=0.5 * pir,
        peq_tn_m=peq,
        pedestrian_lsy_tn_m=pedestrian_lsy,
        pedestrian_lsx_tn_m=pedestrian_lsx,
    )


def _load_components(
    inputs: AbutmentInputs,
    dc_weight_tn_m: float,
    dc_x_m: float,
    dc_y_m: float,
    ev_weight_tn_m: float,
    ev_x_m: float,
    ev_y_m: float,
    pressures: SoilPressureResult,
) -> ComponentGroup:
    g = inputs.geometry
    loads = inputs.loads
    lsy_total = pressures.lsy_tn_m + pressures.pedestrian_lsy_tn_m
    pir_arm = (dc_weight_tn_m * dc_y_m + ev_weight_tn_m * ev_y_m) / (dc_weight_tn_m + ev_weight_tn_m)
    if inputs.is_pure_wall:
        lsy_x = g.toe_length_m + g.lower_stem_thickness_m + g.backfill_step_width_m + (
            g.heel_length_m - g.backfill_step_width_m
        ) / 2.0
        vertical_without_bridge = (
            LoadComponent("DC muro", "DC", dc_weight_tn_m, dc_x_m),
            LoadComponent("EV relleno", "EV", ev_weight_tn_m, ev_x_m),
            LoadComponent("LSy sobrecarga relleno", "LS", lsy_total, lsy_x),
        )
        horizontal_a = _horizontal_seismic_combo_a(
            pressures,
            pir_arm,
            g.retained_height_m,
            include_superstructure=False,
            braking_tn_m=0.0,
            peq_arm_m=0.0,
            br_arm_m=0.0,
        )
        horizontal_b = _horizontal_seismic_combo_b(
            pressures,
            pir_arm,
            g.retained_height_m,
            include_superstructure=False,
            braking_tn_m=0.0,
            peq_arm_m=0.0,
            br_arm_m=0.0,
        )
        return ComponentGroup(
            vertical_with_bridge=vertical_without_bridge,
            horizontal_with_bridge=horizontal_a,
            vertical_without_bridge=vertical_without_bridge,
            horizontal_without_bridge=horizontal_a,
            horizontal_with_bridge_seismic_b=horizontal_b,
            horizontal_without_bridge_seismic_b=horizontal_b,
        )
    lsy_x = g.load_x_m + g.bearing_seat_length_m + g.seat_wall_width_m + (g.heel_length_m - g.backfill_step_width_m) / 2.0
    vertical_with_bridge = (
        LoadComponent("DC estribo", "DC", dc_weight_tn_m, dc_x_m),
        LoadComponent("PDC tablero", "DC", loads.pdc_tn_m, g.superstructure_load_x_m),
        LoadComponent("PDW asfalto", "DW", loads.pdw_tn_m, g.superstructure_load_x_m),
        LoadComponent("EV relleno", "EV", ev_weight_tn_m, ev_x_m),
        LoadComponent("PPL peatonal", "LL", loads.ppl_tn_m, g.superstructure_load_x_m),
        LoadComponent("PLL+IM vehicular", "LL", loads.pll_im_tn_m, g.superstructure_load_x_m),
        LoadComponent("LSy sobrecarga relleno", "LS", lsy_total, lsy_x),
    )
    vertical_without_bridge = (
        LoadComponent("DC estribo", "DC", dc_weight_tn_m, dc_x_m),
        LoadComponent("EV relleno", "EV", ev_weight_tn_m, ev_x_m),
        LoadComponent("LSy sobrecarga relleno", "LS", lsy_total, lsy_x),
    )
    peq_arm = g.retained_height_m - g.seat_block_height_m / 2.0
    br_arm = g.retained_height_m + g.bridge_seat_to_bearing_height_m
    horizontal_with_a = _horizontal_seismic_combo_a(
        pressures,
        pir_arm,
        g.retained_height_m,
        include_superstructure=True,
        braking_tn_m=loads.braking_tn_m,
        peq_arm_m=peq_arm,
        br_arm_m=br_arm,
    )
    horizontal_with_b = _horizontal_seismic_combo_b(
        pressures,
        pir_arm,
        g.retained_height_m,
        include_superstructure=True,
        braking_tn_m=loads.braking_tn_m,
        peq_arm_m=peq_arm,
        br_arm_m=br_arm,
    )
    horizontal_without_a = horizontal_with_a[:4]
    horizontal_without_b = horizontal_with_b[:3]  # LSx + max(0.5PAE,EH) + PIR
    return ComponentGroup(
        vertical_with_bridge=vertical_with_bridge,
        horizontal_with_bridge=horizontal_with_a,
        vertical_without_bridge=vertical_without_bridge,
        horizontal_without_bridge=horizontal_without_a,
        horizontal_with_bridge_seismic_b=horizontal_with_b,
        horizontal_without_bridge_seismic_b=horizontal_without_b,
    )


def _horizontal_seismic_combo_a(
    pressures: SoilPressureResult,
    pir_arm_m: float,
    retained_height_m: float,
    *,
    include_superstructure: bool,
    braking_tn_m: float,
    peq_arm_m: float,
    br_arm_m: float,
) -> tuple[LoadComponent, ...]:
    """MTC combo A: PAE (= EH + EQterr) + 0.5·PIR."""
    rows: list[LoadComponent] = [
        LoadComponent("LSx sobrecarga", "LS", pressures.lsx_tn_m, retained_height_m / 2.0),
        LoadComponent("EH terreno", "EH", pressures.eh_tn_m, retained_height_m / 3.0),
        LoadComponent("EQterr", "EQ", pressures.eq_terr_tn_m, retained_height_m / 2.0),
        LoadComponent("0.5PIR", "EQ", pressures.half_pir_tn_m, pir_arm_m),
    ]
    if include_superstructure:
        rows.append(LoadComponent("PEQ superestructura", "EQ", pressures.peq_tn_m, peq_arm_m))
        rows.append(LoadComponent("BR frenado", "BR", braking_tn_m, br_arm_m))
    return tuple(rows)


def _horizontal_seismic_combo_b(
    pressures: SoilPressureResult,
    pir_arm_m: float,
    retained_height_m: float,
    *,
    include_superstructure: bool,
    braking_tn_m: float,
    peq_arm_m: float,
    br_arm_m: float,
) -> tuple[LoadComponent, ...]:
    """MTC combo B: max(0.5·PAE, EH) + PIR completo."""
    earth_b = max(0.5 * pressures.pae_tn_m, pressures.eh_tn_m)
    # Si gobierna EH, brazo H/3; si gobierna 0.5·PAE, brazo H/2 (resultante sísmica).
    earth_arm = retained_height_m / 3.0 if earth_b <= pressures.eh_tn_m + 1e-12 else retained_height_m / 2.0
    earth_type = "EH" if earth_b <= pressures.eh_tn_m + 1e-12 else "EQ"
    rows: list[LoadComponent] = [
        LoadComponent("LSx sobrecarga", "LS", pressures.lsx_tn_m, retained_height_m / 2.0),
        LoadComponent("max(0.5PAE,EH)", earth_type, earth_b, earth_arm),
        LoadComponent("PIR", "EQ", pressures.pir_tn_m, pir_arm_m),
    ]
    if include_superstructure:
        rows.append(LoadComponent("PEQ superestructura", "EQ", pressures.peq_tn_m, peq_arm_m))
        rows.append(LoadComponent("BR frenado", "BR", braking_tn_m, br_arm_m))
    return tuple(rows)


def _stability_severity(state: StabilityStateResult) -> float:
    """Return a utilization index to pick the more unfavorable seismic combination."""
    e_limit = max(state.eccentricity_limit_m, 1e-9)
    e_ratio = abs(state.eccentricity_m) / e_limit
    resistance = (
        state.key_resistance_tn_m
        if state.key_resistance_tn_m is not None
        else state.friction_resistance_tn_m
    )
    slide_ratio = state.hu_tn_m / max(resistance, 1e-9)
    bearing_ratio = state.geotechnical_pressure_kg_cm2 / max(state.q_allow_kg_cm2, 1e-9)
    return max(e_ratio, slide_ratio, bearing_ratio)


def _governing_seismic_state(
    combo_a: StabilityStateResult,
    combo_b: StabilityStateResult,
) -> StabilityStateResult:
    """Return the more unfavorable of the two MTC PAE/PIR combinations."""
    if _stability_severity(combo_b) > _stability_severity(combo_a) + 1e-12:
        return combo_b
    return combo_a


def _extreme_seismic_pair(
    inputs: AbutmentInputs,
    factors: LoadFactors,
    vertical: tuple[LoadComponent, ...],
    horizontal_a: tuple[LoadComponent, ...],
    horizontal_b: tuple[LoadComponent, ...],
    key: PassiveKeyResult | None,
) -> tuple[StabilityStateResult, StabilityStateResult]:
    state_a = _stability_state(
        inputs,
        factors,
        vertical,
        horizontal_a,
        key,
        seismic_papir_combination=SEISMIC_PAPIR_COMBO_A,
        state_name="Evento Extremo I (PAE+0.5PIR)",
    )
    state_b = _stability_state(
        inputs,
        factors,
        vertical,
        horizontal_b,
        key,
        seismic_papir_combination=SEISMIC_PAPIR_COMBO_B,
        state_name="Evento Extremo I (max(0.5PAE,EH)+PIR)",
    )
    return state_a, state_b


def _stability_state(
    inputs: AbutmentInputs,
    factors: LoadFactors,
    vertical: tuple[LoadComponent, ...],
    horizontal: tuple[LoadComponent, ...],
    key: PassiveKeyResult | None,
    *,
    seismic_papir_combination: str | None = None,
    state_name: str | None = None,
) -> StabilityStateResult:
    factor_map = {
        "DC": factors.dc,
        "DW": factors.dw,
        "EV": factors.ev,
        "LL": factors.ll,
        "LS": factors.ls_vertical,
        "EH": factors.eh,
        "EQ": factors.eq,
        "BR": factors.br,
    }
    vu = sum(component.value_tn_m * factor_map[component.load_type] for component in vertical)
    mvu = sum(component.moment_tn_m_m * factor_map[component.load_type] for component in vertical)
    horizontal_factor_map = dict(factor_map)
    horizontal_factor_map["LS"] = factors.ls_horizontal
    hu = sum(component.value_tn_m * horizontal_factor_map[component.load_type] for component in horizontal)
    mhu = sum(component.moment_tn_m_m * horizontal_factor_map[component.load_type] for component in horizontal)
    x_resultant = (mvu - mhu) / vu
    eccentricity = inputs.geometry.footing_width_m / 2.0 - x_resultant
    abs_eccentricity = abs(eccentricity)
    friction = tan(radians(inputs.soil.friction_angle_deg)) * vu
    key_resistance = friction + (key.factored_passive_tn_m if key is not None else 0.0)
    q_allow = _allowable_factored_bearing(inputs, factors)
    b = inputs.geometry.footing_width_m
    qmax_linear = vu / b * (1.0 + 6.0 * abs_eccentricity / b) / 10.0
    qmin_linear = vu / b * (1.0 - 6.0 * abs_eccentricity / b) / 10.0
    e_limit = eccentricity_limit_m(b, factors)
    minimum_contact_ratio = _minimum_contact_ratio_for_limit(e_limit, b)
    effective_width = b - 2.0 * abs_eccentricity
    geotechnical_pressure = vu / effective_width / 10.0 if effective_width > 0.0 else float("inf")
    if qmin_linear >= -1e-9:
        contact_type = "Completo"
        contact_length = b
        contact_ratio = 1.0
        qmax = qmax_linear
        qmin = max(qmin_linear, 0.0)
    else:
        compression_distance = b / 2.0 - abs_eccentricity
        contact_length = max(3.0 * compression_distance, 0.0)
        contact_ratio = contact_length / b if b > 0.0 else 0.0
        contact_type = "Parcial triangular"
        qmax = 2.0 * vu / contact_length / 10.0 if contact_length > 0.0 else float("inf")
        qmin = 0.0
    bearing_ok = geotechnical_pressure <= q_allow
    return StabilityStateResult(
        name=state_name or factors.name,
        vu_tn_m=vu,
        stabilizing_moment_tn_m_m=mvu,
        hu_tn_m=hu,
        overturning_moment_tn_m_m=mhu,
        resultant_x_m=x_resultant,
        eccentricity_m=eccentricity,
        eccentricity_limit_m=e_limit,
        overturning_status="OK" if abs_eccentricity <= e_limit else "NO",
        friction_resistance_tn_m=friction,
        sliding_status="OK" if friction >= hu else "NO",
        qmax_kg_cm2=qmax,
        qmin_kg_cm2=qmin,
        qmin_linear_kg_cm2=qmin_linear,
        effective_width_m=effective_width,
        geotechnical_pressure_kg_cm2=geotechnical_pressure,
        q_allow_kg_cm2=q_allow,
        contact_type=contact_type,
        contact_length_m=contact_length,
        contact_length_ratio=contact_ratio,
        minimum_contact_length_ratio=minimum_contact_ratio,
        bearing_status="OK" if bearing_ok else "NO",
        key_resistance_tn_m=key_resistance if key is not None else None,
        sliding_with_key_status=("OK" if key_resistance >= hu else "NO") if key is not None else None,
        seismic_papir_combination=seismic_papir_combination,
    )


def _allowable_factored_bearing(inputs: AbutmentInputs, factors: LoadFactors) -> float:
    if factors.limit_state == "service":
        return inputs.soil.allowable_bearing_kg_cm2
    phi_b = 0.80 if factors.limit_state == "extreme" else 0.55
    return phi_b * inputs.soil.bearing_capacity_factor_fs * inputs.soil.allowable_bearing_kg_cm2


def _passive_key(inputs: AbutmentInputs) -> PassiveKeyResult:
    key = inputs.key
    gamma_soil = inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    kp_prime = (
        key.passive_coefficient_prime
        if key.passive_coefficient_prime is not None
        else rankine_passive_coefficient(inputs.soil.friction_angle_deg)
    )
    kp = kp_prime
    passive_soil_height = _key_passive_soil_height_m(inputs)
    top_pressure = kp * gamma_soil * passive_soil_height
    bottom_pressure = kp * gamma_soil * (passive_soil_height + key.height_m)
    upper_front_passive = (
        0.5 * kp * gamma_soil * passive_soil_height**2.0
        if key.consider_upper_front_passive
        else 0.0
    )
    passive = 0.5 * (top_pressure + bottom_pressure) * key.height_m
    total_passive = upper_front_passive + passive
    return PassiveKeyResult(
        passive_coefficient_prime=kp_prime,
        kp=kp,
        top_pressure_tn_m2=top_pressure,
        bottom_pressure_tn_m2=bottom_pressure,
        upper_front_passive_resistance_tn_m=upper_front_passive,
        factored_upper_front_passive_tn_m=key.passive_resistance_factor * upper_front_passive,
        passive_resistance_tn_m=passive,
        total_passive_resistance_tn_m=total_passive,
        factored_passive_tn_m=key.passive_resistance_factor * total_passive,
    )


def _key_passive_soil_height_m(inputs: AbutmentInputs) -> float:
    return inputs.geometry.front_soil_depth_m


def _structural_design(
    inputs: AbutmentInputs,
    pressures: SoilPressureResult,
    with_bridge: tuple[StabilityStateResult, ...],
    selected_reinforcement: Mapping[str, ReinforcementSpacingOption],
) -> tuple[StructuralDesignCase, StructuralDesignCase, StructuralDesignCase]:
    g = inputs.geometry
    r = inputs.reinforcement
    grid = SpacingGrid(r.spacing_step_m, r.minimum_spacing_m, r.maximum_spacing_m)
    stem_depth_cm = g.lower_stem_thickness_m * 100.0 - r.stem_cover_cm - r.stem_main_bar_diameter_cm / 2.0
    footing_depth_cm = g.footing_thickness_m * 100.0 - r.footing_cover_cm - r.footing_main_bar_diameter_cm / 2.0
    toe_depth_cm = g.footing_thickness_m * 100.0 - r.footing_cover_cm - r.toe_main_bar_diameter_cm / 2.0
    stem_demands = _stem_design_demands(inputs, pressures)
    stem_mu = max(stem_demands["strength_mu"], stem_demands["extreme_mu"])
    stem_vu = max(stem_demands["strength_vu"], stem_demands["extreme_vu"])
    stem_temperature_as = _stem_temperature_as(inputs)
    stem_limit_states = (
        ("Resistencia I", stem_demands["strength_mu"], r.flexural_phi),
        ("Evento Extremo", stem_demands["extreme_mu"], r.stem_design_phi_for_as),
    )
    heel_demands = tuple(_heel_design_demands(inputs, state) for state in with_bridge)
    heel_mu = max(moment for moment, _ in heel_demands)
    heel_vu = max(shear for _, shear in heel_demands)
    toe_demands = tuple(_toe_design_demands(inputs, state, toe_depth_cm) for state in with_bridge)
    toe_mu = max(moment for moment, _ in toe_demands)
    toe_vu = max(shear for _, shear in toe_demands)
    footing_temperature_as = _footing_temperature_as(inputs)
    return (
        _reinforced_case(
            "Pantalla",
            stem_mu,
            stem_depth_cm,
            stem_temperature_as,
            stem_vu,
            inputs,
            grid,
            r.flexural_phi,
            r.stem_main_bar_label,
            stem_temperature_as,
            selected_reinforcement.get("Pantalla"),
            notes=(
                "As = max(As Resistencia I con φ=0.90, As Evento Extremo con φ=1.00); "
                "cada estado se verifica con su propio factor de resistencia."
            ),
            shear_method="general",
            limit_states=stem_limit_states,
        ),
        _reinforced_case(
            "Zapata - talon superior",
            heel_mu,
            footing_depth_cm,
            footing_temperature_as,
            heel_vu,
            inputs,
            grid,
            r.footing_design_phi_for_as,
            r.heel_main_bar_label,
            footing_temperature_as,
            selected_reinforcement.get("Zapata - talon superior"),
            notes=(
                "Envolvente Resistencia/Evento Extremo; Mu neto = |M descendente - M reaccion suelo| "
                "con presion triangular/trapezoidal adoptada."
            ),
            shear_method="simplified",
        ),
        _reinforced_case(
            "Zapata - puntera inferior",
            toe_mu,
            toe_depth_cm,
            footing_temperature_as,
            toe_vu,
            inputs,
            grid,
            r.footing_design_phi_for_as,
            r.toe_main_bar_label,
            footing_temperature_as,
            selected_reinforcement.get("Zapata - puntera inferior"),
            r.toe_moment_capacity_multiplier,
            "Envolvente Resistencia/Evento Extremo con presion triangular/trapezoidal adoptada.",
            shear_method="simplified",
        ),
    )


def _key_structural_design(
    inputs: AbutmentInputs,
    key: PassiveKeyResult | None,
    selected_reinforcement: Mapping[str, ReinforcementSpacingOption],
) -> StructuralDesignCase | None:
    if key is None:
        return None
    r = inputs.reinforcement
    grid = SpacingGrid(r.spacing_step_m, r.minimum_spacing_m, r.maximum_spacing_m)
    bar = _bar_by_label(r.key_main_bar_label)
    effective_depth_cm = inputs.key.width_m * 100.0 - r.footing_cover_cm - bar.diameter_cm / 2.0
    moment = _key_base_moment_tn_m(inputs, key)
    shear = key.passive_resistance_tn_m
    minimum_as = _key_temperature_as(inputs)
    return _reinforced_case(
        "Diente de concreto",
        moment,
        effective_depth_cm,
        minimum_as,
        shear,
        inputs,
        grid,
        r.footing_design_phi_for_as,
        r.key_main_bar_label,
        minimum_as,
        selected_reinforcement.get("Diente de concreto"),
        shear_method="simplified",
    )


def _reinforced_case(
    name: str,
    mu_tn_m: float,
    effective_depth_cm: float,
    minimum_as_cm2_m: float,
    shear_demand_tn_m: float,
    inputs: AbutmentInputs,
    grid: SpacingGrid,
    design_phi_for_as: float,
    selected_bar_label: str,
    temperature_as_cm2_m: float,
    selected_option: ReinforcementSpacingOption | None = None,
    moment_capacity_multiplier: float = 1.0,
    notes: str = "Mr >= max(Mu, min(Mcr, 1.33Mu))",
    shear_method: str = "general",
    limit_states: tuple[tuple[str, float, float], ...] | None = None,
) -> StructuralDesignCase:
    states = limit_states or (("Diseño", abs(mu_tn_m), design_phi_for_as),)
    flexural_as_by_state = tuple(
        (
            label,
            abs(state_mu),
            state_phi,
            _flexural_steel_area_workbook_cm2_m(
                mu_tn_m=abs(state_mu),
                width_cm=100.0,
                effective_depth_cm=effective_depth_cm,
                concrete_strength_kg_cm2=inputs.materials.concrete_strength_kg_cm2,
                steel_yield_kg_cm2=inputs.materials.steel_yield_kg_cm2,
                phi=state_phi,
            ),
        )
        for label, state_mu, state_phi in states
    )
    governing_flexure = max(flexural_as_by_state, key=lambda item: (item[3], item[1]))
    as_strength = governing_flexure[3]
    governing_mu = governing_flexure[1]
    governing_phi = governing_flexure[2]
    gross_depth_cm = _section_depth_cm(inputs, name)
    cracking_moment = _cracking_moment_tn_m(gross_depth_cm, inputs) if governing_mu > 0.0 else 0.0
    multiplier_minimum_moment = (
        inputs.reinforcement.minimum_flexural_capacity_multiplier * governing_mu
        if governing_mu > 0.0
        else 0.0
    )
    minimum_moment = min(cracking_moment, multiplier_minimum_moment)
    capacity_minimum_as = 0.0
    for _label, state_mu, state_phi, _as_state in flexural_as_by_state:
        state_minimum_moment = (
            min(
                cracking_moment,
                inputs.reinforcement.minimum_flexural_capacity_multiplier * state_mu,
            )
            if state_mu > 0.0
            else 0.0
        )
        capacity_minimum_as = max(
            capacity_minimum_as,
            _flexural_steel_area_workbook_cm2_m(
                mu_tn_m=state_minimum_moment,
                width_cm=100.0,
                effective_depth_cm=effective_depth_cm,
                concrete_strength_kg_cm2=inputs.materials.concrete_strength_kg_cm2,
                steel_yield_kg_cm2=inputs.materials.steel_yield_kg_cm2,
                phi=state_phi,
            ),
        )
    minimum_as = max(minimum_as_cm2_m, capacity_minimum_as)
    required = max(as_strength, minimum_as)
    spacing_options = generate_spacing_options(name, required, grid)
    if selected_option is None:
        selected_bar, selected_spacing, provided_as = _select_reinforcement_for_required_area(
            selected_bar_label,
            required,
            grid,
            spacing_options,
        )
    else:
        selected_bar = selected_option.bar
        selected_spacing = selected_option.spacing_m
        provided_as = selected_option.provided_area_cm2_m
    nominal_resistance = _moment_resistance_tn_m(
        provided_as,
        100.0,
        effective_depth_cm,
        inputs.materials.concrete_strength_kg_cm2,
        inputs.materials.steel_yield_kg_cm2,
        1.0,
    )
    moment_resistance = governing_phi * nominal_resistance
    required_moment = max(governing_mu, minimum_moment)
    if moment_capacity_multiplier > 1.0:
        required_moment = max(required_moment, moment_capacity_multiplier * abs(mu_tn_m))
        while (
            moment_resistance + 1e-9 < required_moment
            and selected_spacing - grid.step_m >= grid.minimum_m
        ):
            selected_spacing = round(selected_spacing - grid.step_m, 3)
            provided_as = selected_bar.area_cm2 / selected_spacing
            nominal_resistance = _moment_resistance_tn_m(
                provided_as,
                100.0,
                effective_depth_cm,
                inputs.materials.concrete_strength_kg_cm2,
                inputs.materials.steel_yield_kg_cm2,
                1.0,
            )
            moment_resistance = governing_phi * nominal_resistance
    state_status: dict[str, tuple[str, float, float]] = {}
    all_states_ok = True
    for label, state_mu, state_phi, _as_state in flexural_as_by_state:
        state_minimum_moment = (
            min(
                cracking_moment,
                inputs.reinforcement.minimum_flexural_capacity_multiplier * state_mu,
            )
            if state_mu > 0.0
            else 0.0
        )
        state_required = max(state_mu, state_minimum_moment)
        if moment_capacity_multiplier > 1.0 and abs(state_mu - abs(mu_tn_m)) <= 1e-12:
            state_required = max(state_required, moment_capacity_multiplier * abs(mu_tn_m))
        state_resistance = state_phi * nominal_resistance
        ok = state_resistance + 1e-9 >= state_required
        state_status[label] = ("OK" if ok else "NO", state_resistance, state_mu)
        all_states_ok = all_states_ok and ok
    shear_detail = _shear_beta_detail(
        mu_tn_m=abs(mu_tn_m),
        vu_tn_m=shear_demand_tn_m,
        provided_as_cm2_m=provided_as,
        effective_depth_cm=effective_depth_cm,
        gross_depth_cm=gross_depth_cm,
        method=shear_method,
        inputs=inputs,
    )
    shear_resistance_tn_m = _concrete_shear_resistance_tn(
        effective_depth_cm,
        inputs,
        inputs.reinforcement.shear_phi,
        shear_detail["beta"],
    )
    as_by_label = {label: as_state for label, _mu, _phi, as_state in flexural_as_by_state}
    strength_info = state_status.get("Resistencia I")
    extreme_info = state_status.get("Evento Extremo")
    return StructuralDesignCase(
        name=name,
        controlling_moment_tn_m_m=governing_mu,
        effective_depth_cm=effective_depth_cm,
        strength_as_cm2_m=as_strength,
        cracking_moment_tn_m_m=cracking_moment,
        multiplier_minimum_moment_tn_m_m=multiplier_minimum_moment,
        minimum_capacity_moment_tn_m_m=minimum_moment,
        capacity_minimum_as_cm2_m=capacity_minimum_as,
        minimum_as_cm2_m=minimum_as,
        required_as_cm2_m=required,
        spacing_options=spacing_options,
        selected_bar_label=selected_bar.label,
        selected_spacing_m=selected_spacing,
        provided_as_cm2_m=provided_as,
        moment_resistance_tn_m_m=moment_resistance,
        moment_status="OK" if all_states_ok else "NO",
        temperature_as_cm2_m=temperature_as_cm2_m,
        shear_demand_tn_m=shear_demand_tn_m,
        shear_resistance_tn_m=shear_resistance_tn_m,
        shear_status="OK" if shear_resistance_tn_m >= shear_demand_tn_m else "NO",
        shear_effective_depth_cm=shear_detail["dv_cm"],
        shear_beta=shear_detail["beta"],
        shear_longitudinal_strain=shear_detail["epsilon_s"],
        shear_crack_spacing_in=shear_detail["s_x_in"],
        shear_effective_crack_spacing_in=shear_detail["s_xe_in"],
        shear_beta_method=shear_detail["method"],
        shear_controlling_moment_tn_m_m=shear_detail["mu_used_tn_m_m"],
        is_custom_selection=bool(selected_option and selected_option.is_custom),
        notes=notes,
        strength_limit_mu_tn_m_m=strength_info[2] if strength_info else 0.0,
        extreme_limit_mu_tn_m_m=extreme_info[2] if extreme_info else 0.0,
        strength_limit_as_cm2_m=as_by_label.get("Resistencia I", 0.0),
        extreme_limit_as_cm2_m=as_by_label.get("Evento Extremo", 0.0),
        strength_moment_resistance_tn_m_m=strength_info[1] if strength_info else 0.0,
        extreme_moment_resistance_tn_m_m=extreme_info[1] if extreme_info else 0.0,
        strength_moment_status=strength_info[0] if strength_info else "",
        extreme_moment_status=extreme_info[0] if extreme_info else "",
    )


def _minimum_flexural_capacity_moment_tn_m(
    mu_tn_m: float,
    gross_depth_cm: float,
    inputs: AbutmentInputs,
) -> float:
    if mu_tn_m <= 0.0:
        return 0.0
    return min(
        _cracking_moment_tn_m(gross_depth_cm, inputs),
        inputs.reinforcement.minimum_flexural_capacity_multiplier * mu_tn_m,
    )


def _cracking_moment_tn_m(gross_depth_cm: float, inputs: AbutmentInputs) -> float:
    fr_kg_cm2 = 2.01 * sqrt(inputs.materials.concrete_strength_kg_cm2)
    section_modulus_cm3 = 100.0 * gross_depth_cm**2.0 / 6.0
    return 1.1 * fr_kg_cm2 * section_modulus_cm3 / 100000.0


def _select_reinforcement_for_required_area(
    selected_bar_label: str,
    required_as_cm2_m: float,
    grid: SpacingGrid,
    spacing_options: ReinforcementCaseOptions,
):
    selected_bar = _bar_by_label(selected_bar_label)
    selected_spacing = _spacing_for_bar(selected_bar.area_cm2, required_as_cm2_m, grid)
    provided_as = selected_bar.area_cm2 / selected_spacing
    if provided_as + 1e-9 >= required_as_cm2_m:
        return selected_bar, selected_spacing, provided_as
    recommended = spacing_options.recommended
    if recommended is None:
        recommended = max(spacing_options.options, key=lambda option: option.provided_area_cm2_m)
    return recommended.bar, recommended.spacing_m, recommended.provided_area_cm2_m


def _secondary_reinforcement(
    inputs: AbutmentInputs,
    selected_reinforcement: Mapping[str, ReinforcementSpacingOption],
) -> tuple[AbutmentSecondaryReinforcementCase, ...]:
    r = inputs.reinforcement
    grid = SpacingGrid(r.spacing_step_m, r.minimum_spacing_m, r.maximum_spacing_m)
    stem_temperature = _stem_temperature_result(inputs)
    footing_temperature = _footing_temperature_result(inputs)
    vertical_stem_note = (
        "Acero vertical adicional en cara exterior; la cara de relleno queda cubierta "
        "por el acero principal vertical."
        if not inputs.is_pure_wall
        else "Acero vertical adicional en cara exterior; la cara opuesta queda cubierta "
        "por el acero principal vertical."
    )
    horizontal_stem_note = (
        "Acero horizontal de distribucion en ambas caras; el acero principal es vertical."
    )
    return (
        _secondary_reinforcement_case(
            "Pantalla - vertical exterior",
            "Pantalla",
            "Cara exterior al relleno",
            "Vertical",
            stem_temperature,
            0.0,
            grid,
            vertical_stem_note,
            selected_reinforcement.get("Pantalla - vertical exterior"),
        ),
        _secondary_reinforcement_case(
            "Pantalla - horizontal relleno",
            "Pantalla",
            "Cara interior / relleno",
            "Horizontal transversal",
            stem_temperature,
            0.0,
            grid,
            f"{horizontal_stem_note} Cara de relleno.",
            selected_reinforcement.get("Pantalla - horizontal relleno"),
        ),
        _secondary_reinforcement_case(
            "Pantalla - horizontal exterior",
            "Pantalla",
            "Cara exterior al relleno",
            "Horizontal transversal",
            stem_temperature,
            0.0,
            grid,
            f"{horizontal_stem_note} Cara exterior.",
            selected_reinforcement.get("Pantalla - horizontal exterior"),
        ),
        _secondary_reinforcement_case(
            "Zapata - transversal superior",
            "Zapata",
            "Superior",
            "Horizontal transversal a talon/puntera",
            footing_temperature,
            0.0,
            grid,
            "Acero transversal superior; el acero principal del talon es longitudinal "
            "y no cubre el minimo por temperatura en esta direccion.",
            selected_reinforcement.get("Zapata - transversal superior"),
        ),
        _secondary_reinforcement_case(
            "Zapata - transversal inferior",
            "Zapata",
            "Inferior",
            "Horizontal transversal a talon/puntera",
            footing_temperature,
            0.0,
            grid,
            "Acero transversal inferior; el acero principal de la puntera es longitudinal "
            "y no cubre el minimo por temperatura en esta direccion.",
            selected_reinforcement.get("Zapata - transversal inferior"),
        ),
    )


def _secondary_reinforcement_case(
    name: str,
    element: str,
    face: str,
    direction: str,
    temperature: AbutmentTemperatureSteelResult,
    primary_steel_as_cm2_m: float,
    grid: SpacingGrid,
    notes: str,
    selected_option: ReinforcementSpacingOption | None = None,
) -> AbutmentSecondaryReinforcementCase:
    additional_required = max(0.0, temperature.required_as_cm2_m - primary_steel_as_cm2_m)
    spacing_options = generate_spacing_options(name, additional_required, grid)
    selected = selected_option or spacing_options.recommended or spacing_options.options[-1]
    area_status = "OK" if selected.provided_area_cm2_m + 1e-9 >= additional_required else "NO"
    spacing_status = "OK" if selected.spacing_m <= temperature.maximum_spacing_m + 1e-9 else "NO"
    status = "OK" if area_status == "OK" and spacing_status == "OK" else "NO"
    return AbutmentSecondaryReinforcementCase(
        name=name,
        element=element,
        face=face,
        direction=direction,
        required_as_cm2_m=additional_required,
        spacing_options=spacing_options,
        selected_bar_label=selected.bar.label,
        selected_spacing_m=selected.spacing_m,
        provided_as_cm2_m=selected.provided_area_cm2_m,
        status=status,
        temperature_required_as_cm2_m=temperature.required_as_cm2_m,
        primary_steel_as_cm2_m=primary_steel_as_cm2_m,
        temperature_b_cm=temperature.b_cm,
        temperature_h_cm=temperature.h_cm,
        raw_temperature_as_cm2_m=temperature.raw_as_cm2_m,
        maximum_spacing_m=temperature.maximum_spacing_m,
        spacing_status=spacing_status,
        is_custom_selection=selected.is_custom,
        notes=notes,
    )


def _crack_checks(
    inputs: AbutmentInputs,
    pressures: SoilPressureResult,
    service_state: StabilityStateResult,
    cases: tuple[StructuralDesignCase | None, ...],
) -> tuple[AbutmentCrackCheck, ...]:
    service_moments = _service_moments(inputs, pressures, service_state)
    checks: list[AbutmentCrackCheck] = []
    for case in cases:
        if case is None:
            continue
        section_depth_cm = _section_depth_cm(inputs, case.name)
        cover_cm = _cover_for_case(inputs, case.name)
        bar = _bar_by_label(case.selected_bar_label)
        dc_cm = cover_cm + bar.diameter_cm / 2.0
        service_moment = service_moments.get(case.name, case.controlling_moment_tn_m_m / 1.75)
        stress = _service_steel_stress_kg_cm2(
            service_moment,
            case.provided_as_cm2_m,
            case.effective_depth_cm,
        )
        stress_used = min(stress, 0.60 * inputs.materials.steel_yield_kg_cm2)
        maximum_spacing, beta_s = maximum_crack_control_spacing_m(
            max(stress_used, 1e-9),
            dc_cm,
            section_depth_cm,
        )
        checks.append(
            AbutmentCrackCheck(
                element=case.name,
                service_moment_tn_m_m=service_moment,
                steel_stress_kg_cm2=stress,
                steel_stress_used_kg_cm2=stress_used,
                beta_s=beta_s,
                dc_cm=dc_cm,
                provided_spacing_m=case.selected_spacing_m,
                maximum_spacing_m=maximum_spacing,
                status="CUMPLE" if case.selected_spacing_m <= maximum_spacing + 1e-9 else "NO CUMPLE",
            )
        )
    return tuple(checks)


def _development_checks(
    inputs: AbutmentInputs,
    cases: tuple[StructuralDesignCase | None, ...],
) -> tuple[AbutmentDevelopmentCheck, ...]:
    checks: list[AbutmentDevelopmentCheck] = []
    r = inputs.reinforcement
    for case in cases:
        if case is None:
            continue
        bar = _bar_by_label(case.selected_bar_label)
        excess_factor = min(1.0, case.required_as_cm2_m / case.provided_as_cm2_m)
        excess_factor = max(0.4, excess_factor)
        required_ld, basic_ld = mtc_tension_development_length_cm(
            bar_diameter_cm=bar.diameter_cm,
            steel_yield_kg_cm2=inputs.materials.steel_yield_kg_cm2,
            concrete_strength_kg_cm2=inputs.materials.concrete_strength_kg_cm2,
            location_factor=r.development_location_factor,
            coating_factor=r.development_coating_factor,
            lightweight_factor=r.development_lightweight_factor,
            confinement_factor=r.development_confinement_factor,
            excess_reinforcement_factor=excess_factor,
        )
        hooked_ld, hook_extension = _hooked_development_length_cm(
            bar.diameter_cm,
            inputs.materials.concrete_strength_kg_cm2,
            inputs.materials.steel_yield_kg_cm2,
            excess_factor,
        )
        available = _available_development_length_cm(inputs, case.name)
        if available + 1e-9 >= required_ld:
            anchorage_type = "RECTO"
            status = "OK"
        elif available + 1e-9 >= hooked_ld:
            anchorage_type = "GANCHO"
            status = "OK"
        else:
            anchorage_type = "INSUF."
            status = "NO CUMPLE"
        checks.append(
            AbutmentDevelopmentCheck(
                element=case.name,
                bar_label=bar.label,
                required_ld_cm=required_ld,
                basic_ld_cm=basic_ld,
                required_hooked_ld_cm=hooked_ld,
                hook_extension_cm=hook_extension,
                available_length_cm=available,
                excess_reinforcement_factor=excess_factor,
                anchorage_type=anchorage_type,
                status=status,
            )
        )
    return tuple(checks)


def _bar_details(
    inputs: AbutmentInputs,
    cases: tuple[StructuralDesignCase | None, ...],
    development_checks: tuple[AbutmentDevelopmentCheck, ...],
    secondary_cases: tuple[AbutmentSecondaryReinforcementCase, ...],
) -> tuple[AbutmentBarDetail, ...]:
    development_by_element = {check.element: check for check in development_checks}
    details: list[AbutmentBarDetail] = []
    for index, case in enumerate((case for case in cases if case is not None), start=1):
        check = development_by_element[case.name]
        details.append(
            AbutmentBarDetail(
                mark=f"E{index}",
                element=case.name,
                face=_detail_face(case.name),
                bar_label=case.selected_bar_label,
                spacing_m=case.selected_spacing_m,
                length_m=_bar_detail_length_m(inputs, case.name, _required_anchor_length_cm(check)),
                anchorage_m=_required_anchor_length_cm(check) / 100.0,
                note=f"{_detail_note(case.name)}; {check.anchorage_type}",
            )
        )
    first_secondary_mark = len(details) + 1
    for index, case in enumerate(secondary_cases, start=first_secondary_mark):
        details.append(
            AbutmentBarDetail(
                mark=f"E{index}",
                element=case.element,
                face=case.face,
                bar_label=case.selected_bar_label,
                spacing_m=case.selected_spacing_m,
                length_m=_secondary_bar_detail_length_m(inputs, case),
                anchorage_m=0.0,
                note=f"{case.direction}; {case.notes}",
            )
        )
    ordered_details = sorted(details, key=lambda detail: _bar_detail_group_rank(detail.element))
    return tuple(
        replace(detail, mark=f"E{index}")
        for index, detail in enumerate(ordered_details, start=1)
    )


def _bar_detail_group_rank(element: str) -> int:
    if element.startswith("Pantalla"):
        return 0
    if element.startswith("Zapata"):
        return 1
    return 2


def _stem_reinforcement_cut(
    inputs: AbutmentInputs,
    pressures: SoilPressureResult,
    stem_design: StructuralDesignCase,
    development_checks: tuple[AbutmentDevelopmentCheck, ...],
) -> AbutmentStemReinforcementCut | None:
    g = inputs.geometry
    r = inputs.reinforcement
    height = g.stem_height_above_footing_m
    if height <= 0.0:
        return None

    lower_bar = _bar_by_label(stem_design.selected_bar_label)
    grid = SpacingGrid(r.spacing_step_m, r.minimum_spacing_m, r.maximum_spacing_m)
    upper_spacing_limit = _spacing_for_bar(
        lower_bar.area_cm2,
        stem_design.temperature_as_cm2_m,
        grid,
    )
    continuous_every_n_bars = int(
        (upper_spacing_limit + 1e-9) / stem_design.selected_spacing_m
    )
    if continuous_every_n_bars < 2:
        return None

    # Las barras continuas deben ocupar posiciones de la parrilla inferior.
    # Por ello la separacion superior solo puede ser un multiplo entero de la
    # separacion inferior (una de cada n barras), nunca una grilla independiente.
    upper_spacing = round(
        continuous_every_n_bars * stem_design.selected_spacing_m,
        3,
    )

    upper_as = lower_bar.area_cm2 / upper_spacing
    development = next(
        (check for check in development_checks if check.element == "Pantalla"),
        None,
    )
    development_extension_m = (
        _required_anchor_length_cm(development) / 100.0
        if development is not None
        else 0.0
    )

    if _stem_cut_upper_steel_satisfies(inputs, pressures, 0.0, upper_as, lower_bar.diameter_cm):
        theoretical_cut = 0.0
    elif not _stem_cut_upper_steel_satisfies(inputs, pressures, height, upper_as, lower_bar.diameter_cm):
        return None
    else:
        low = 0.0
        high = height
        for _ in range(60):
            mid = (low + high) / 2.0
            if _stem_cut_upper_steel_satisfies(inputs, pressures, mid, upper_as, lower_bar.diameter_cm):
                high = mid
            else:
                low = mid
        theoretical_cut = high

    constructive_cut = min(height, theoretical_cut + development_extension_m)
    (
        moment_at_cut,
        effective_depth_cm,
        strength_as_at_cut,
        minimum_as_at_cut,
        required_as,
        required_moment_at_cut,
    ) = _stem_cut_design_at_height(
        inputs,
        pressures,
        theoretical_cut,
        lower_bar.diameter_cm,
    )
    moment_resistance_at_cut = _moment_resistance_tn_m(
        upper_as,
        100.0,
        effective_depth_cm,
        inputs.materials.concrete_strength_kg_cm2,
        inputs.materials.steel_yield_kg_cm2,
        inputs.reinforcement.flexural_phi,
    )
    thickness_at_cut_cm = _stem_thickness_at_height_m(inputs, theoretical_cut) * 100.0
    status = "OK"
    notes = (
        "Acero superior continuo: "
        f"1 de cada {continuous_every_n_bars} barras inferiores; "
        "las barras cortadas se prolongan ld sobre el corte teorico."
    )
    if constructive_cut >= height - r.spacing_step_m:
        status = "NO CONVIENE"
        notes = "La longitud de desarrollo lleva el corte cerca de la coronacion; ahorro constructivo limitado."
    if effective_depth_cm <= 0.0:
        return None

    return AbutmentStemReinforcementCut(
        lower_bar_label=lower_bar.label,
        lower_spacing_m=stem_design.selected_spacing_m,
        lower_provided_as_cm2_m=stem_design.provided_as_cm2_m,
        upper_bar_label=lower_bar.label,
        upper_spacing_m=upper_spacing,
        upper_provided_as_cm2_m=upper_as,
        continuous_every_n_bars=continuous_every_n_bars,
        minimum_as_cm2_m=stem_design.temperature_as_cm2_m,
        theoretical_cut_height_m=theoretical_cut,
        constructive_cut_height_m=constructive_cut,
        development_extension_m=development_extension_m,
        lower_cut_bar_length_m=constructive_cut + development_extension_m,
        continuous_bar_length_m=height + development_extension_m,
        controlling_moment_at_cut_tn_m_m=moment_at_cut,
        required_as_at_cut_cm2_m=required_as,
        moment_resistance_at_cut_tn_m_m=moment_resistance_at_cut,
        required_moment_at_cut_tn_m_m=required_moment_at_cut,
        effective_depth_at_cut_cm=effective_depth_cm,
        thickness_at_cut_cm=thickness_at_cut_cm,
        strength_as_at_cut_cm2_m=strength_as_at_cut,
        minimum_as_at_cut_cm2_m=minimum_as_at_cut,
        upper_spacing_limit_m=upper_spacing_limit,
        status=status,
        notes=notes,
    )


def _stem_cut_upper_steel_satisfies(
    inputs: AbutmentInputs,
    pressures: SoilPressureResult,
    height_above_footing_m: float,
    provided_as_cm2_m: float,
    bar_diameter_cm: float,
) -> bool:
    _moment, effective_depth_cm, _, _, required_as, _required_moment = _stem_cut_design_at_height(
        inputs,
        pressures,
        height_above_footing_m,
        bar_diameter_cm,
    )
    if provided_as_cm2_m + 1e-9 < required_as:
        return False
    return _stem_provided_steel_satisfies_limit_states(
        inputs,
        provided_as_cm2_m,
        effective_depth_cm,
        _stem_design_moments_at_height(inputs, pressures, height_above_footing_m),
    )


def _stem_cut_design_at_height(
    inputs: AbutmentInputs,
    pressures: SoilPressureResult,
    height_above_footing_m: float,
    bar_diameter_cm: float,
) -> tuple[float, float, float, float, float, float]:
    thickness_m = _stem_thickness_at_height_m(inputs, height_above_footing_m)
    effective_depth_cm = thickness_m * 100.0 - inputs.reinforcement.stem_cover_cm - bar_diameter_cm / 2.0
    moments = _stem_design_moments_at_height(inputs, pressures, height_above_footing_m)
    strength_mu = moments["strength_mu"]
    extreme_mu = moments["extreme_mu"]
    as_strength_i = _flexural_steel_area_workbook_cm2_m(
        mu_tn_m=strength_mu,
        width_cm=100.0,
        effective_depth_cm=effective_depth_cm,
        concrete_strength_kg_cm2=inputs.materials.concrete_strength_kg_cm2,
        steel_yield_kg_cm2=inputs.materials.steel_yield_kg_cm2,
        phi=inputs.reinforcement.flexural_phi,
    )
    as_extreme = _flexural_steel_area_workbook_cm2_m(
        mu_tn_m=extreme_mu,
        width_cm=100.0,
        effective_depth_cm=effective_depth_cm,
        concrete_strength_kg_cm2=inputs.materials.concrete_strength_kg_cm2,
        steel_yield_kg_cm2=inputs.materials.steel_yield_kg_cm2,
        phi=inputs.reinforcement.stem_design_phi_for_as,
    )
    as_strength = max(as_strength_i, as_extreme)
    governing_mu = strength_mu if as_strength_i >= as_extreme else extreme_mu
    minimum_moment = _minimum_flexural_capacity_moment_tn_m(
        governing_mu,
        thickness_m * 100.0,
        inputs,
    )
    capacity_minimum_as = max(
        _flexural_steel_area_workbook_cm2_m(
            mu_tn_m=_minimum_flexural_capacity_moment_tn_m(
                strength_mu,
                thickness_m * 100.0,
                inputs,
            ),
            width_cm=100.0,
            effective_depth_cm=effective_depth_cm,
            concrete_strength_kg_cm2=inputs.materials.concrete_strength_kg_cm2,
            steel_yield_kg_cm2=inputs.materials.steel_yield_kg_cm2,
            phi=inputs.reinforcement.flexural_phi,
        ),
        _flexural_steel_area_workbook_cm2_m(
            mu_tn_m=_minimum_flexural_capacity_moment_tn_m(
                extreme_mu,
                thickness_m * 100.0,
                inputs,
            ),
            width_cm=100.0,
            effective_depth_cm=effective_depth_cm,
            concrete_strength_kg_cm2=inputs.materials.concrete_strength_kg_cm2,
            steel_yield_kg_cm2=inputs.materials.steel_yield_kg_cm2,
            phi=inputs.reinforcement.stem_design_phi_for_as,
        ),
    )
    minimum_as = max(_stem_temperature_as(inputs), capacity_minimum_as)
    required_as = max(as_strength, minimum_as)
    required_moment = max(governing_mu, minimum_moment)
    return governing_mu, effective_depth_cm, as_strength, minimum_as, required_as, required_moment


def _stem_thickness_at_height_m(inputs: AbutmentInputs, height_above_footing_m: float) -> float:
    g = inputs.geometry
    height = g.stem_height_above_footing_m
    if height <= 0.0:
        return g.lower_stem_thickness_m
    ratio = min(max(height_above_footing_m / height, 0.0), 1.0)
    return g.lower_stem_thickness_m - (g.lower_stem_thickness_m - g.upper_stem_thickness_m) * ratio


def _stem_provided_steel_satisfies_limit_states(
    inputs: AbutmentInputs,
    provided_as_cm2_m: float,
    effective_depth_cm: float,
    moments: dict[str, float] | float,
) -> bool:
    if isinstance(moments, dict):
        strength_mu = moments["strength_mu"]
        extreme_mu = moments["extreme_mu"]
    else:
        # Compatibilidad: un solo momento se verifica con ambos φ.
        strength_mu = abs(moments)
        extreme_mu = abs(moments)
    nominal = _moment_resistance_tn_m(
        provided_as_cm2_m,
        100.0,
        effective_depth_cm,
        inputs.materials.concrete_strength_kg_cm2,
        inputs.materials.steel_yield_kg_cm2,
        1.0,
    )
    thickness_cm = (
        effective_depth_cm
        + inputs.reinforcement.stem_cover_cm
        + inputs.reinforcement.stem_main_bar_diameter_cm / 2.0
    )
    strength_required = max(
        strength_mu,
        _minimum_flexural_capacity_moment_tn_m(strength_mu, thickness_cm, inputs),
    )
    extreme_required = max(
        extreme_mu,
        _minimum_flexural_capacity_moment_tn_m(extreme_mu, thickness_cm, inputs),
    )
    return (
        inputs.reinforcement.flexural_phi * nominal + 1e-9 >= strength_required
        and inputs.reinforcement.stem_design_phi_for_as * nominal + 1e-9 >= extreme_required
    )


def _stem_design_moments_at_height(
    inputs: AbutmentInputs,
    pressures: SoilPressureResult,
    height_above_footing_m: float,
) -> dict[str, float]:
    strength_mu, extreme_mu = _stem_design_limit_moments_at_height(
        inputs,
        pressures,
        height_above_footing_m,
    )
    return {
        "strength_mu": strength_mu,
        "extreme_mu": extreme_mu,
    }


def _stem_design_moment_at_height(
    inputs: AbutmentInputs,
    pressures: SoilPressureResult,
    height_above_footing_m: float,
) -> float:
    strength_mu, extreme_mu = _stem_design_limit_moments_at_height(
        inputs,
        pressures,
        height_above_footing_m,
    )
    return max(strength_mu, extreme_mu)


def _stem_design_limit_moments_at_height(
    inputs: AbutmentInputs,
    pressures: SoilPressureResult,
    height_above_footing_m: float,
) -> tuple[float, float]:
    g = inputs.geometry
    gamma_soil = inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    height = g.stem_height_above_footing_m
    remaining_height = max(height - height_above_footing_m, 0.0)
    if remaining_height <= 0.0:
        return 0.0, 0.0

    ka = pressures.ka
    k_ae = pressures.k_ae
    kh = 0.5 * inputs.soil.fpga * inputs.soil.pga
    vehicular_surcharge_force = ka * pressures.live_surcharge_height_m * gamma_soil * remaining_height
    pedestrian_force = pressures.pedestrian_lsx_tn_m * remaining_height / g.retained_height_m
    ls_moment = (vehicular_surcharge_force + pedestrian_force) * remaining_height / 2.0
    eh_force = 0.5 * ka * gamma_soil * remaining_height**2.0
    eh_moment = eh_force * remaining_height / 3.0
    eq_pressure = 0.5 * (k_ae - ka) * remaining_height * gamma_soil
    eq_force = eq_pressure * remaining_height
    eq_moment = eq_force * remaining_height / 2.0

    upper_concrete = _upper_concrete_weight_and_arm(inputs)
    pir = kh * upper_concrete[0]
    pir_base_moment = 0.5 * pir * upper_concrete[1]
    pir_moment = pir_base_moment * (remaining_height / height)

    peq_arm = max(remaining_height - g.seat_block_height_m / 2.0, 0.0)
    peq_moment = pressures.peq_tn_m * peq_arm
    br_moment = inputs.loads.braking_tn_m * max(
        remaining_height + g.bridge_seat_to_bearing_height_m,
        0.0,
    )
    strength_mu = 1.75 * ls_moment + 1.50 * eh_moment + 1.75 * br_moment
    pae_force = eh_force + eq_force
    gamma_eq = inputs.gamma_eq
    # MTC 2.8.1.1.14.1 — envolvente de las dos combinaciones PAE/PIR
    extreme_mu_a = gamma_eq * ls_moment + eh_moment + eq_moment + pir_moment + peq_moment + gamma_eq * br_moment
    earth_b = max(0.5 * pae_force, eh_force)
    earth_moment_b = eh_moment if earth_b <= eh_force + 1e-12 else earth_b * remaining_height / 2.0
    pir_moment_full = (pir * upper_concrete[1]) * (remaining_height / height)
    extreme_mu_b = gamma_eq * ls_moment + earth_moment_b + pir_moment_full + peq_moment + gamma_eq * br_moment
    extreme_mu = max(extreme_mu_a, extreme_mu_b)
    return strength_mu, extreme_mu


def _secondary_bar_detail_length_m(
    inputs: AbutmentInputs,
    case: AbutmentSecondaryReinforcementCase,
) -> float:
    if case.element == "Pantalla" and case.direction == "Vertical":
        return inputs.geometry.stem_height_above_footing_m
    return inputs.geometry.strip_width_m


def _stem_design_demands(
    inputs: AbutmentInputs,
    pressures: SoilPressureResult,
) -> dict[str, float]:
    g = inputs.geometry
    gamma_soil = inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    height = g.stem_height_above_footing_m
    h_ls = pressures.live_surcharge_height_m
    ka = pressures.ka
    k_ae = pressures.k_ae
    kh = 0.5 * inputs.soil.fpga * inputs.soil.pga
    upper_concrete = _upper_concrete_weight_and_arm(inputs)
    pir = kh * upper_concrete[0]
    pir_arm = upper_concrete[1]
    ls_force = ka * h_ls * gamma_soil * height + pressures.pedestrian_lsx_tn_m * height / g.retained_height_m
    eh_pressure_base = ka * height * gamma_soil
    eh_force = 0.5 * height * eh_pressure_base
    eq_pressure_base = 0.5 * (k_ae - ka) * height * gamma_soil
    eq_force = eq_pressure_base * height
    pae_force = eh_force + eq_force
    peq_force = pressures.peq_tn_m
    br_force = inputs.loads.braking_tn_m
    ls_moment = ls_force * height / 2.0
    eh_moment = eh_force * height / 3.0
    eq_moment = eq_force * height / 2.0
    pir_moment_half = 0.5 * pir * pir_arm
    pir_moment_full = pir * pir_arm
    peq_moment = peq_force * (height - g.seat_block_height_m / 2.0)
    br_moment = br_force * (height + g.bridge_seat_to_bearing_height_m)
    gamma_eq = inputs.gamma_eq
    # MTC 2.8.1.1.14.1 — combo A: PAE + 0.5·PIR
    extreme_mu_a = gamma_eq * ls_moment + eh_moment + eq_moment + pir_moment_half + peq_moment + gamma_eq * br_moment
    extreme_vu_a = gamma_eq * ls_force + eh_force + eq_force + 0.50 * pir + peq_force + gamma_eq * br_force
    # MTC combo B: max(0.5·PAE, EH) + PIR
    earth_b = max(0.5 * pae_force, eh_force)
    earth_moment_b = eh_moment if earth_b <= eh_force + 1e-12 else earth_b * height / 2.0
    extreme_mu_b = gamma_eq * ls_moment + earth_moment_b + pir_moment_full + peq_moment + gamma_eq * br_moment
    extreme_vu_b = gamma_eq * ls_force + earth_b + pir + peq_force + gamma_eq * br_force
    return {
        "strength_mu": 1.75 * ls_moment + 1.50 * eh_moment + 1.75 * br_moment,
        "extreme_mu": max(extreme_mu_a, extreme_mu_b),
        "extreme_mu_a": extreme_mu_a,
        "extreme_mu_b": extreme_mu_b,
        "strength_vu": 1.75 * ls_force + 1.50 * eh_force + 1.75 * br_force,
        "extreme_vu": max(extreme_vu_a, extreme_vu_b),
        "extreme_vu_a": extreme_vu_a,
        "extreme_vu_b": extreme_vu_b,
    }


def _upper_concrete_weight_and_arm(inputs: AbutmentInputs) -> tuple[float, float]:
    upper_names = {
        "1 Parapeto",
        "2 Cajuela",
        "3 Transicion t1",
        "4 Pantalla e superior",
        "5 Transicion t2",
        "6 Ensanche inferior",
        "Murete superior",
        "Cajuela",
        "Transicion posterior",
        "Pantalla rectangular",
        "Transicion frontal",
        "Ensanche de pantalla",
    }
    upper = tuple(
        component
        for component in _concrete_components(inputs)
        if component.name in upper_names
    )
    weight = sum(component.value_tn_m for component in upper)
    arm = sum(
        component.value_tn_m
        * (component.vertical_arm_m - inputs.geometry.footing_thickness_m)
        for component in upper
    ) / weight
    return weight, arm


def _heel_design_demands(inputs: AbutmentInputs, state: StabilityStateResult) -> tuple[float, float]:
    g = inputs.geometry
    gamma_concrete = inputs.materials.concrete_unit_weight_kg_m3 / 1000.0
    gamma_soil = inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    h = g.stem_height_above_footing_m
    h_heel = g.heel_length_m - g.backfill_step_width_m
    b_step = g.backfill_step_width_m
    footing_weight = g.heel_length_m * g.footing_thickness_m * gamma_concrete
    soil_rect = h_heel * h * gamma_soil
    soil_triangle = b_step * g.backwall_taper_height_m / 2.0 * gamma_soil
    soil_step = b_step * (h - g.seat_block_height_m - g.backwall_drop_m - g.backwall_taper_height_m) * gamma_soil
    soil_weight = soil_rect + soil_triangle + soil_step
    soil_arm = (
        soil_rect * (b_step + h_heel / 2.0)
        + soil_triangle * (b_step / 3.0)
        + soil_step * (b_step / 2.0)
    ) / soil_weight
    h_eq = inputs.soil.vehicular_surcharge_height_m
    if h_eq is None:
        h_eq = equivalent_vehicular_surcharge_height_m(g.retained_height_m)
    lsy = h_heel * h_eq * gamma_soil
    lsy += inputs.soil.pedestrian_surcharge_tn_m2 * h_heel
    lsy_arm = h_heel / 2.0 + b_step
    moment = (
        1.25 * footing_weight * (h_heel + b_step) / 2.0
        + 1.35 * soil_weight * soil_arm
        + 1.75 * lsy * lsy_arm
    )
    shear = 1.25 * footing_weight + 1.35 * soil_weight + 1.75 * lsy
    heel_start = g.toe_length_m + g.lower_stem_thickness_m
    soil_reaction, soil_reaction_moment = _contact_pressure_resultant_over_interval(
        g,
        state,
        heel_start,
        g.footing_width_m,
        heel_start,
    )
    return abs(moment - soil_reaction_moment), abs(shear - soil_reaction)


def _toe_design_demands(
    inputs: AbutmentInputs,
    state: StabilityStateResult,
    effective_depth_cm: float,
) -> tuple[float, float]:
    g = inputs.geometry
    toe = g.toe_length_m
    qmax = _contact_pressure_tn_m2_at_x(g, state, 0.0)
    q_at_stem = _contact_pressure_tn_m2_at_x(g, state, toe)
    moment = toe**2.0 / 6.0 * (q_at_stem + 2.0 * qmax)
    # Iterative capacity refinements can reduce the critical shear section; use
    # d initially, matching the workbook order within a small tolerance.
    critical_distance_m = min(effective_depth_cm / 100.0, toe)
    q_at_critical = _contact_pressure_tn_m2_at_x(g, state, toe - critical_distance_m)
    shear = 0.5 * (q_at_critical + qmax) * max(toe - critical_distance_m, 0.0)
    return moment, shear


def _service_moments(
    inputs: AbutmentInputs,
    pressures: SoilPressureResult,
    service_state: StabilityStateResult,
) -> dict[str, float]:
    return {
        "Pantalla": _stem_service_moment(inputs, pressures),
        "Zapata - talon superior": _heel_service_moment(inputs, service_state),
        "Zapata - puntera inferior": _toe_service_moment(inputs, service_state),
        "Diente de concreto": _key_base_moment_tn_m(inputs, _passive_key(inputs)),
    }


def _stem_service_moment(inputs: AbutmentInputs, pressures: SoilPressureResult) -> float:
    g = inputs.geometry
    height = g.stem_height_above_footing_m
    gamma_soil = inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    ka = pressures.ka
    ls_force = (
        ka * pressures.live_surcharge_height_m * gamma_soil * height
        + pressures.pedestrian_lsx_tn_m * height / g.retained_height_m
    )
    eh_force = 0.5 * ka * gamma_soil * height**2.0
    br_force = inputs.loads.braking_tn_m
    return (
        ls_force * height / 2.0
        + eh_force * height / 3.0
        + br_force * (height + g.bridge_seat_to_bearing_height_m)
    )


def _heel_service_moment(inputs: AbutmentInputs, state: StabilityStateResult) -> float:
    g = inputs.geometry
    gamma_concrete = inputs.materials.concrete_unit_weight_kg_m3 / 1000.0
    gamma_soil = inputs.materials.soil_unit_weight_kg_m3 / 1000.0
    h = g.stem_height_above_footing_m
    h_heel = g.heel_length_m - g.backfill_step_width_m
    b_step = g.backfill_step_width_m
    footing_weight = g.heel_length_m * g.footing_thickness_m * gamma_concrete
    soil_rect = h_heel * h * gamma_soil
    soil_triangle = b_step * g.backwall_taper_height_m / 2.0 * gamma_soil
    soil_step = b_step * (h - g.seat_block_height_m - g.backwall_drop_m - g.backwall_taper_height_m) * gamma_soil
    soil_weight = soil_rect + soil_triangle + soil_step
    soil_arm = (
        soil_rect * (b_step + h_heel / 2.0)
        + soil_triangle * (b_step / 3.0)
        + soil_step * (b_step / 2.0)
    ) / soil_weight
    h_eq = inputs.soil.vehicular_surcharge_height_m
    if h_eq is None:
        h_eq = equivalent_vehicular_surcharge_height_m(g.retained_height_m)
    lsy = h_heel * h_eq * gamma_soil
    lsy += inputs.soil.pedestrian_surcharge_tn_m2 * h_heel
    lsy_arm = h_heel / 2.0 + b_step
    moment = footing_weight * (h_heel + b_step) / 2.0 + soil_weight * soil_arm + lsy * lsy_arm
    heel_start = g.toe_length_m + g.lower_stem_thickness_m
    _, soil_reaction_moment = _contact_pressure_resultant_over_interval(
        g,
        state,
        heel_start,
        g.footing_width_m,
        heel_start,
    )
    return abs(moment - soil_reaction_moment)


def _toe_service_moment(inputs: AbutmentInputs, state: StabilityStateResult) -> float:
    g = inputs.geometry
    toe = g.toe_length_m
    qmax = _contact_pressure_tn_m2_at_x(g, state, 0.0)
    q_at_stem = _contact_pressure_tn_m2_at_x(g, state, toe)
    return toe**2.0 / 6.0 * (q_at_stem + 2.0 * qmax)


def _contact_pressure_resultant_over_interval(
    geometry: AbutmentGeometryInputs,
    state: StabilityStateResult,
    start_x_m: float,
    end_x_m: float,
    moment_origin_x_m: float,
) -> tuple[float, float]:
    """Return resultant and moment of the adopted contact pressure over an interval."""
    b = geometry.footing_width_m
    start = min(max(start_x_m, 0.0), b)
    end = min(max(end_x_m, 0.0), b)
    if end <= start:
        return 0.0, 0.0

    points = [start, end]
    if state.contact_type != "Completo":
        if state.resultant_x_m <= b / 2.0:
            points.append(state.contact_length_m)
        else:
            points.append(b - state.contact_length_m)
    points = sorted({round(point, 12) for point in points if start <= point <= end})

    force = 0.0
    moment = 0.0
    for x1, x2 in zip(points, points[1:]):
        length = x2 - x1
        if length <= 1e-12:
            continue
        q1 = _contact_pressure_tn_m2_at_x(geometry, state, x1)
        q2 = _contact_pressure_tn_m2_at_x(geometry, state, x2)
        segment_force = length * (q1 + q2) / 2.0
        if segment_force <= 1e-12:
            continue
        centroid_from_x1 = length * (q1 + 2.0 * q2) / (3.0 * (q1 + q2))
        force += segment_force
        moment += segment_force * (x1 + centroid_from_x1 - moment_origin_x_m)
    return force, moment


def _contact_pressure_tn_m2_at_x(
    geometry: AbutmentGeometryInputs,
    state: StabilityStateResult,
    x_m: float,
) -> float:
    """Return adopted upward soil reaction at position x from the toe."""
    b = geometry.footing_width_m
    x = min(max(x_m, 0.0), b)
    qmax = state.qmax_kg_cm2 * 10.0
    if state.contact_type == "Completo":
        q_toe = state.vu_tn_m / b * (1.0 + 6.0 * state.eccentricity_m / b)
        q_heel = state.vu_tn_m / b * (1.0 - 6.0 * state.eccentricity_m / b)
        return q_toe + (q_heel - q_toe) * x / b
    c = state.contact_length_m
    if c <= 0.0:
        return 0.0
    if state.resultant_x_m <= b / 2.0:
        if x > c:
            return 0.0
        return qmax * (1.0 - x / c)
    contact_start = b - c
    if x < contact_start:
        return 0.0
    return qmax * (x - contact_start) / c


def _key_base_moment_tn_m(inputs: AbutmentInputs, key: PassiveKeyResult) -> float:
    height = inputs.key.height_m
    return height**2.0 * (2.0 * key.top_pressure_tn_m2 + key.bottom_pressure_tn_m2) / 6.0


def _service_steel_stress_kg_cm2(
    service_moment_tn_m: float,
    provided_area_cm2_m: float,
    effective_depth_cm: float,
) -> float:
    require_positive(provided_area_cm2_m, "As provisto")
    require_positive(effective_depth_cm, "d")
    if service_moment_tn_m <= 0.0:
        return 1e-9
    return service_moment_tn_m * 100000.0 / (provided_area_cm2_m * 0.90 * effective_depth_cm)


def _hooked_development_length_cm(
    bar_diameter_cm: float,
    concrete_strength_kg_cm2: float,
    steel_yield_kg_cm2: float,
    excess_factor: float,
) -> tuple[float, float]:
    basic = 0.076 * bar_diameter_cm * steel_yield_kg_cm2 / sqrt(concrete_strength_kg_cm2)
    modified = basic * 0.80 * excess_factor
    required = max(modified, 8.0 * bar_diameter_cm, 15.24)
    return required, 16.0 * bar_diameter_cm


def _required_anchor_length_cm(check: AbutmentDevelopmentCheck) -> float:
    if check.anchorage_type == "GANCHO":
        return check.required_hooked_ld_cm
    return check.required_ld_cm


def _section_depth_cm(inputs: AbutmentInputs, element: str) -> float:
    if element == "Pantalla":
        return inputs.geometry.lower_stem_thickness_m * 100.0
    if element == "Diente de concreto":
        return inputs.key.width_m * 100.0
    return inputs.geometry.footing_thickness_m * 100.0


def _cover_for_case(inputs: AbutmentInputs, element: str) -> float:
    if element == "Pantalla":
        return inputs.reinforcement.stem_cover_cm
    return inputs.reinforcement.footing_cover_cm


def _available_development_length_cm(inputs: AbutmentInputs, element: str) -> float:
    g = inputs.geometry
    cover = inputs.reinforcement.footing_cover_cm
    if element == "Pantalla":
        return g.footing_thickness_m * 100.0 - cover
    if element == "Zapata - talon superior":
        return g.heel_length_m * 100.0 - cover
    if element == "Zapata - puntera inferior":
        return g.toe_length_m * 100.0 - cover
    if element == "Diente de concreto":
        return g.footing_thickness_m * 100.0 - cover
    return 0.0


def _bar_detail_length_m(inputs: AbutmentInputs, element: str, required_ld_cm: float) -> float:
    g = inputs.geometry
    ld_m = required_ld_cm / 100.0
    if element == "Pantalla":
        return g.stem_height_above_footing_m + ld_m
    if element == "Zapata - talon superior":
        return g.heel_length_m + ld_m
    if element == "Zapata - puntera inferior":
        return g.toe_length_m + ld_m
    if element == "Diente de concreto":
        return inputs.key.height_m + ld_m
    return ld_m


def _detail_face(element: str) -> str:
    if element == "Pantalla":
        return "Cara relleno"
    if element == "Zapata - talon superior":
        return "Superior talon"
    if element == "Zapata - puntera inferior":
        return "Inferior puntera"
    if element == "Diente de concreto":
        return "Cara pasiva"
    return "-"


def _detail_note(element: str) -> str:
    if element == "Pantalla":
        return "Anclar en zapata"
    if element == "Zapata - talon superior":
        return "Prolongar hacia pantalla"
    if element == "Zapata - puntera inferior":
        return "Anclar hacia pantalla"
    if element == "Diente de concreto":
        return "Anclar dentro de zapata"
    return ""


def _stem_temperature_as(inputs: AbutmentInputs) -> float:
    return _stem_temperature_result(inputs).required_as_cm2_m


def _stem_average_thickness_cm(inputs: AbutmentInputs) -> float:
    g = inputs.geometry
    return (g.lower_stem_thickness_m + g.upper_stem_thickness_m) * 50.0


def _stem_panel_height_cm(inputs: AbutmentInputs) -> float:
    g = inputs.geometry
    if inputs.is_pure_wall:
        return g.stem_height_above_footing_m * 100.0
    return (
        g.stem_height_above_footing_m
        - g.seat_block_height_m
        - g.backwall_drop_m
        - g.backwall_taper_height_m
    ) * 100.0


def _temperature_max_spacing_m(thickness_cm: float, grid: SpacingGrid) -> float:
    if thickness_cm > THICK_MEMBER_SPACING_THRESHOLD_CM:
        return min(grid.maximum_m, THICK_MEMBER_SPACING_MAX_M)
    return grid.maximum_m


def _temperature_mtc_bounded(
    b_cm: float,
    h_cm: float,
    steel_yield_kg_cm2: float,
    grid: SpacingGrid,
) -> AbutmentTemperatureSteelResult:
    raw = _temperature_mtc_aashto_cm2_m(b_cm, h_cm, steel_yield_kg_cm2)
    bounded = max(TEMPERATURE_STEEL_MIN_CM2_M, min(TEMPERATURE_STEEL_MAX_CM2_M, raw))
    return AbutmentTemperatureSteelResult(
        b_cm=b_cm,
        h_cm=h_cm,
        raw_as_cm2_m=raw,
        required_as_cm2_m=bounded,
        maximum_spacing_m=_temperature_max_spacing_m(max(b_cm, h_cm), grid),
    )


def _stem_temperature_result(inputs: AbutmentInputs) -> AbutmentTemperatureSteelResult:
    grid = SpacingGrid(
        inputs.reinforcement.spacing_step_m,
        inputs.reinforcement.minimum_spacing_m,
        inputs.reinforcement.maximum_spacing_m,
    )
    return _temperature_mtc_bounded(
        _stem_average_thickness_cm(inputs),
        _stem_panel_height_cm(inputs),
        inputs.materials.steel_yield_kg_cm2,
        grid,
    )


def _footing_temperature_as(inputs: AbutmentInputs) -> float:
    return _footing_temperature_result(inputs).required_as_cm2_m


def _footing_temperature_result(inputs: AbutmentInputs) -> AbutmentTemperatureSteelResult:
    grid = SpacingGrid(
        inputs.reinforcement.spacing_step_m,
        inputs.reinforcement.minimum_spacing_m,
        inputs.reinforcement.maximum_spacing_m,
    )
    g = inputs.geometry
    return _temperature_mtc_bounded(
        g.footing_width_m * 100.0,
        g.footing_thickness_m * 100.0,
        inputs.materials.steel_yield_kg_cm2,
        grid,
    )


def _key_temperature_as(inputs: AbutmentInputs) -> float:
    grid = SpacingGrid(
        inputs.reinforcement.spacing_step_m,
        inputs.reinforcement.minimum_spacing_m,
        inputs.reinforcement.maximum_spacing_m,
    )
    return _temperature_mtc_bounded(
        inputs.key.width_m * 100.0,
        inputs.key.height_m * 100.0,
        inputs.materials.steel_yield_kg_cm2,
        grid,
    ).required_as_cm2_m


def _temperature_mtc_aashto_cm2_m(
    b_cm: float,
    h_cm: float,
    steel_yield_kg_cm2: float,
) -> float:
    require_positive(b_cm, "b temperatura")
    require_positive(h_cm, "h temperatura")
    require_positive(steel_yield_kg_cm2, "fy temperatura")
    return 7.65 * b_cm * h_cm / (2.0 * (b_cm + h_cm) * steel_yield_kg_cm2) * 100.0


def _effective_shear_depth_cm(effective_depth_cm: float, gross_depth_cm: float) -> float:
    return max(0.9 * effective_depth_cm, 0.72 * gross_depth_cm)


def _footing_simplified_shear_eligible(
    inputs: AbutmentInputs,
    effective_shear_depth_cm: float,
) -> bool:
    """Simplified β=2 applies when the critical section is within 3·dv of the stem face."""
    stem_thickness_m = inputs.geometry.lower_stem_thickness_m
    return stem_thickness_m <= 0.0 or stem_thickness_m <= 3.0 * effective_shear_depth_cm / 100.0


def _general_shear_beta(
    mu_tn_m_m: float,
    vu_tn_m: float,
    provided_as_cm2_m: float,
    effective_shear_depth_cm: float,
    steel_modulus_kg_cm2: float = STEEL_ELASTIC_MODULUS_KG_CM2,
    max_aggregate_size_in: float = DEFAULT_MAX_AGGREGATE_SIZE_IN,
) -> tuple[float, float, float, float, float]:
    """Return beta, epsilon_s, s_x (in), s_xe (in) and Mu used for the general procedure."""
    dv_m = effective_shear_depth_cm / 100.0
    mu_used = max(mu_tn_m_m, abs(vu_tn_m) * dv_m)
    if provided_as_cm2_m <= 0.0 or steel_modulus_kg_cm2 <= 0.0:
        return SIMPLIFIED_SHEAR_BETA, 0.0, 0.0, 0.0, mu_used
    force_tn_per_m = mu_used / dv_m + abs(vu_tn_m)
    epsilon_s = 1000.0 * force_tn_per_m / (steel_modulus_kg_cm2 * provided_as_cm2_m)
    epsilon_s = max(epsilon_s, 0.0)
    s_x_in = effective_shear_depth_cm / CM_PER_IN
    s_xe_in = s_x_in * 1.38 / (max_aggregate_size_in + 0.63)
    beta = (4.8 / (1.0 + 750.0 * epsilon_s)) * (51.0 / (39.0 + s_xe_in))
    return beta, epsilon_s, s_x_in, s_xe_in, mu_used


def _shear_beta_detail(
    mu_tn_m: float,
    vu_tn_m: float,
    provided_as_cm2_m: float,
    effective_depth_cm: float,
    gross_depth_cm: float,
    method: str,
    inputs: AbutmentInputs | None = None,
) -> dict[str, float | str]:
    dv_cm = _effective_shear_depth_cm(effective_depth_cm, gross_depth_cm)
    use_simplified = method == "simplified"
    if use_simplified and inputs is not None:
        use_simplified = _footing_simplified_shear_eligible(inputs, dv_cm)
    if use_simplified:
        return {
            "method": "simplified",
            "dv_cm": dv_cm,
            "beta": SIMPLIFIED_SHEAR_BETA,
            "epsilon_s": 0.0,
            "s_x_in": dv_cm / CM_PER_IN,
            "s_xe_in": 0.0,
            "mu_used_tn_m_m": mu_tn_m,
        }
    beta, epsilon_s, s_x_in, s_xe_in, mu_used = _general_shear_beta(
        mu_tn_m_m=mu_tn_m,
        vu_tn_m=vu_tn_m,
        provided_as_cm2_m=provided_as_cm2_m,
        effective_shear_depth_cm=dv_cm,
    )
    return {
        "method": "general",
        "dv_cm": dv_cm,
        "beta": beta,
        "epsilon_s": epsilon_s,
        "s_x_in": s_x_in,
        "s_xe_in": s_xe_in,
        "mu_used_tn_m_m": mu_used,
    }


def _concrete_shear_resistance_tn(
    effective_depth_cm: float,
    inputs: AbutmentInputs,
    phi_v: float,
    beta: float,
) -> float:
    vc_kg = (
        0.265
        * beta
        * sqrt(inputs.materials.concrete_strength_kg_cm2)
        * 100.0
        * effective_depth_cm
    )
    return phi_v * vc_kg / 1000.0


def _flexural_steel_area_workbook_cm2_m(
    mu_tn_m: float,
    width_cm: float,
    effective_depth_cm: float,
    concrete_strength_kg_cm2: float,
    steel_yield_kg_cm2: float,
    phi: float,
) -> float:
    if mu_tn_m == 0.0:
        return 0.0
    term = 1.0 - 4.0 * 0.59 * mu_tn_m * 100000.0 / (
        phi * concrete_strength_kg_cm2 * width_cm * effective_depth_cm**2.0
    )
    if term < 0.0:
        raise ValueError("El momento excede la capacidad de la seccion con el peralte disponible.")
    omega = (1.0 - sqrt(term)) / (2.0 * 0.59)
    rho = omega * concrete_strength_kg_cm2 / steel_yield_kg_cm2
    return width_cm * effective_depth_cm * rho


def _moment_resistance_tn_m(
    provided_as_cm2_m: float,
    width_cm: float,
    effective_depth_cm: float,
    concrete_strength_kg_cm2: float,
    steel_yield_kg_cm2: float,
    phi: float,
) -> float:
    a_cm = provided_as_cm2_m * steel_yield_kg_cm2 / (0.85 * concrete_strength_kg_cm2 * width_cm)
    return phi * steel_yield_kg_cm2 * provided_as_cm2_m * (effective_depth_cm - a_cm / 2.0) / 100000.0


def _bar_by_label(label: str):
    normalized = label.strip().replace("Ø", "").strip()
    for bar in REINFORCING_BAR_CATALOG:
        if bar.label == normalized:
            return bar
    raise ValueError(f"No existe la barra {label} en el catalogo.")


def _spacing_for_bar(area_cm2: float, required_as_cm2_m: float, grid: SpacingGrid) -> float:
    if required_as_cm2_m <= 0.0:
        return grid.maximum_m
    raw_spacing = area_cm2 / required_as_cm2_m
    steps = int(raw_spacing / grid.step_m + 1e-9)
    spacing = round(steps * grid.step_m, 3)
    spacing = min(spacing, grid.maximum_m)
    if spacing < grid.minimum_m:
        spacing = grid.minimum_m
    return spacing
