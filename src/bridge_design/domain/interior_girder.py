"""Interior longitudinal girder analysis and reinforcement design."""

from dataclasses import dataclass, replace
from functools import lru_cache
from math import ceil, floor
from typing import Iterable, Literal

from bridge_design.codes.mtc_2018 import (
    DEFAULT_CRACK_CONTROL_EXPOSURE_FACTOR,
    DEFAULT_FLEXURAL_RESISTANCE_FACTOR,
    DEFAULT_SERVICE_STRESS_LEVER_ARM_FACTOR,
    DEFAULT_SHRINKAGE_TEMPERATURE_RATIO,
    mtc_dynamic_load_allowance_for_slab,
    mtc_interior_concrete_t_girder_fatigue_live_load_moment_distribution_factor,
    mtc_interior_concrete_t_girder_fatigue_live_load_shear_distribution_factor,
    mtc_interior_concrete_t_girder_live_load_distribution_factor,
    mtc_interior_concrete_t_girder_live_load_shear_distribution_factor,
)
from bridge_design.domain.concrete_flexure import (
    CONCRETE_ULTIMATE_STRAIN,
    DEFAULT_STEEL_ELASTIC_MODULUS_KG_CM2,
    RectangularFlexuralResponse,
    mtc_beta1,
    mtc_flexural_resistance_factor,
)
from bridge_design.domain.crack_control import (
    CrackControlCheck,
    crack_control_compliance_statuses,
    maximum_crack_control_spacing_m,
)
from bridge_design.domain.load_combinations import LoadFactor
from bridge_design.domain.loads import LiveLoads, VehicleLoadModel
from bridge_design.domain.materials import MaterialProperties
from bridge_design.domain.rebar_catalog import (
    DEFAULT_MAX_SPACING_M,
    DEFAULT_MIN_SPACING_M,
    DEFAULT_SPACING_STEP_M,
    REINFORCING_BAR_CATALOG,
    ReinforcementCaseOptions,
    ReinforcementSpacingOption,
    SpacingGrid,
    generate_spacing_options,
    reinforcing_bar_by_label,
)
from bridge_design.domain.reinforcement import (
    mtc_cracking_moment_tn_m,
    mtc_minimum_flexural_moment_tn_m,
)
from bridge_design.domain.sampling import interpolate_sorted_samples
from bridge_design.units.converters import kg_cm2_to_ksi, ksi_to_kg_cm2, kip_to_tn
from bridge_design.validation.input_validators import require_non_negative, require_positive

NODE_TOLERANCE = 1e-8
MomentTarget = Literal["max", "min"]
FATIGUE_DYNAMIC_LOAD_ALLOWANCE = 0.15
FATIGUE_I_LOAD_FACTOR = 1.50
DEFAULT_SHEAR_RESISTANCE_FACTOR = 0.90
DEFAULT_SHEAR_BETA = 2.0
DEFAULT_SHEAR_THETA_DEGREES = 45.0
FATIGUE_LOAD_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.4.3.2.4 y 2.4.3.3: "
    "un camion de diseno con separacion trasera fija de 30 ft e IM=15%."
)
FATIGUE_REINFORCEMENT_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.7.1.1.3 (5.5.3 AASHTO): "
    "seccion fisurada y rango limite de fatiga para barras rectas."
)
SHEAR_DESIGN_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.9.1.5.6 (5.8 AASHTO): "
    "modelo seccional para corte en concreto armado no pretensado."
)


@dataclass(frozen=True)
class DiaphragmGeometry:
    """One diaphragm modeled as a concentrated DC load on the interior girder.

    ``height_m`` is the net concrete depth below the deck slab so the slab
    volume, already included in the distributed DC load, is not counted twice.
    """

    position_m: float
    thickness_m: float
    height_m: float
    tributary_width_m: float

    def __post_init__(self) -> None:
        require_non_negative(self.position_m, "ubicacion de diafragma")
        require_positive(self.thickness_m, "espesor longitudinal de diafragma")
        require_positive(self.height_m, "altura de diafragma bajo losa")
        require_positive(self.tributary_width_m, "ancho tributario de diafragma")


@dataclass(frozen=True)
class InteriorGirderGeometry:
    """Geometry for one interior T girder in the bridge longitudinal direction."""

    span_length_m: float
    girder_spacing_m: float
    slab_thickness_m: float
    girder_total_height_m: float
    web_width_m: float
    live_load_distribution_factor_g: float | None = None
    live_load_shear_distribution_factor_g: float | None = None
    girder_count: int = 4
    diaphragms: tuple[DiaphragmGeometry, ...] = ()
    moving_load_step_m: float = 0.10
    moment_sample_step_m: float = 0.10

    def __post_init__(self) -> None:
        require_positive(self.span_length_m, "luz del puente")
        require_positive(self.girder_spacing_m, "separacion entre vigas")
        require_positive(self.slab_thickness_m, "espesor de losa")
        require_positive(self.girder_total_height_m, "altura de viga")
        require_positive(self.web_width_m, "ancho de alma")
        if self.girder_count < 1:
            raise ValueError("El numero de vigas debe ser al menos 1.")
        if self.live_load_distribution_factor_g is None:
            object.__setattr__(
                self,
                "live_load_distribution_factor_g",
                mtc_interior_concrete_t_girder_live_load_distribution_factor(
                    span_length_m=self.span_length_m,
                    girder_spacing_m=self.girder_spacing_m,
                    slab_thickness_m=self.slab_thickness_m,
                    girder_total_height_m=self.girder_total_height_m,
                    web_width_m=self.web_width_m,
                    girder_count=self.girder_count,
                ),
            )
        if self.live_load_shear_distribution_factor_g is None:
            object.__setattr__(
                self,
                "live_load_shear_distribution_factor_g",
                mtc_interior_concrete_t_girder_live_load_shear_distribution_factor(
                    span_length_m=self.span_length_m,
                    girder_spacing_m=self.girder_spacing_m,
                    slab_thickness_m=self.slab_thickness_m,
                    girder_count=self.girder_count,
                ),
            )
        require_positive(self.live_load_distribution_factor_g, "g")
        require_positive(self.live_load_shear_distribution_factor_g, "g corte")
        require_positive(self.moving_load_step_m, "paso de carga movil")
        require_positive(self.moment_sample_step_m, "paso de muestreo de momento")
        for diaphragm in self.diaphragms:
            if diaphragm.position_m > self.span_length_m:
                raise ValueError("La ubicacion de diafragma debe estar dentro de la luz.")

    @property
    def tributary_width_m(self) -> float:
        """Return the tributary deck width of an interior girder."""
        return self.girder_spacing_m

    @property
    def total_t_section_depth_m(self) -> float:
        """Return slab plus girder depth for flexural T-section design."""
        return self.slab_thickness_m + self.girder_total_height_m


@dataclass(frozen=True)
class LongitudinalLoadCaseAnalysis:
    """Longitudinal girder load-case moment result."""

    name: str
    max_positive_moment_tn_m: float
    max_positive_position_m: float
    support_reactions_tn: tuple[tuple[str, float], ...]
    moment_samples_tn_m: tuple[tuple[float, float], ...]
    shear_samples_tn: tuple[tuple[float, float], ...] = ()
    max_shear_tn: float = 0.0
    max_shear_position_m: float = 0.0
    maximum_support_reactions_tn: tuple[tuple[str, float], ...] = ()
    critical_vehicle_position_m: float | None = None
    vehicle_configuration: str | None = None
    dynamic_load_allowance: float | None = None
    distribution_factor_g: float | None = None
    shear_distribution_factor_g: float | None = None
    unfactored_before_g_moment_tn_m: float | None = None
    min_moment_samples_tn_m: tuple[tuple[float, float], ...] | None = None
    max_shear_samples_tn: tuple[tuple[float, float], ...] | None = None
    min_shear_samples_tn: tuple[tuple[float, float], ...] | None = None


@dataclass(frozen=True)
class InteriorGirderAnalysisResult:
    """Grouped DC, DW and LL+IM analysis for an interior girder."""

    dc: LongitudinalLoadCaseAnalysis
    dw: LongitudinalLoadCaseAnalysis
    truck_ll_im: LongitudinalLoadCaseAnalysis
    tandem_ll_im: LongitudinalLoadCaseAnalysis
    ll_im_envelope: LongitudinalLoadCaseAnalysis
    fatigue_truck: LongitudinalLoadCaseAnalysis
    dynamic_load_allowance: float
    distribution_factor_g: float
    shear_distribution_factor_g: float


@dataclass(frozen=True)
class InteriorGirderCombinedMoment:
    """One factored moment row for the interior girder."""

    combination_name: str
    limit_state: str
    position_m: float
    dc_moment_tn_m: float
    dc_factor: float
    dw_moment_tn_m: float
    dw_factor: float
    ll_im_moment_tn_m: float
    ll_im_factor: float
    combined_moment_tn_m: float


@dataclass(frozen=True)
class InteriorGirderCombinedShear:
    """Factored shear at a critical longitudinal girder section."""

    combination_name: str
    limit_state: str
    position_m: float
    dc_shear_tn: float
    dc_factor: float
    dw_shear_tn: float
    dw_factor: float
    ll_im_shear_tn: float
    ll_im_factor: float
    combined_shear_tn: float


@dataclass(frozen=True)
class LongitudinalBarPlacementOption:
    """A practical bottom-bar placement option for main girder steel."""

    item: int
    bar_label: str
    bar_area_cm2: float
    bar_diameter_cm: float
    bar_count: int
    layers: int
    bars_per_layer: int
    required_area_cm2: float
    provided_area_cm2: float
    clear_spacing_cm: float
    is_compliant: bool
    is_recommended: bool = False
    is_custom: bool = False
    steel_centroid_from_tension_face_cm: float = 0.0
    effective_depth_cm: float = 0.0

    @property
    def excess_percent(self) -> float:
        """Return excess steel over required area."""
        if self.required_area_cm2 <= 0.0:
            return 0.0
        return (self.provided_area_cm2 / self.required_area_cm2 - 1.0) * 100.0


@dataclass(frozen=True)
class LongitudinalPlacementCaseOptions:
    """Placement options for one main reinforcement case."""

    label: str
    required_area_cm2: float
    options: tuple[LongitudinalBarPlacementOption, ...]

    @property
    def recommended(self) -> LongitudinalBarPlacementOption | None:
        """Return the recommended compliant option."""
        for option in self.options:
            if option.is_recommended:
                return option
        return None


@dataclass(frozen=True)
class InteriorGirderReinforcementParameters:
    """Detailing assumptions used for interior girder reinforcement.

    ``concrete_cover_cm`` is the clear distance from the tension face to the
    outside of the modeled main-bar layer.  The calculated steel centroid then
    adds half the bar diameter and the clear separation between layers.
    """

    concrete_cover_cm: float = 5.0
    main_bar_diameter_cm: float = 2.54
    flexural_resistance_factor: float = DEFAULT_FLEXURAL_RESISTANCE_FACTOR
    shrinkage_temperature_ratio: float = DEFAULT_SHRINKAGE_TEMPERATURE_RATIO
    minimum_clear_bar_spacing_cm: float = 4.0
    maximum_main_bar_layers: int = 4
    spacing_step_m: float = DEFAULT_SPACING_STEP_M
    minimum_spacing_m: float = DEFAULT_MIN_SPACING_M
    maximum_spacing_m: float = DEFAULT_MAX_SPACING_M
    maximum_skin_spacing_m: float = 0.30
    shear_resistance_factor: float = DEFAULT_SHEAR_RESISTANCE_FACTOR
    shear_beta: float = DEFAULT_SHEAR_BETA
    shear_theta_degrees: float = DEFAULT_SHEAR_THETA_DEGREES
    stirrup_legs: int = 2

    def __post_init__(self) -> None:
        require_non_negative(self.concrete_cover_cm, "recubrimiento")
        require_positive(self.main_bar_diameter_cm, "diametro de barra principal")
        require_positive(self.flexural_resistance_factor, "phi flexion")
        if self.flexural_resistance_factor > 1.0:
            raise ValueError("phi flexion no debe exceder 1.0.")
        require_positive(self.shrinkage_temperature_ratio, "rho temperatura")
        require_positive(self.minimum_clear_bar_spacing_cm, "separacion libre minima")
        require_positive(self.spacing_step_m, "paso de espaciamiento")
        require_positive(self.minimum_spacing_m, "espaciamiento minimo")
        require_positive(self.maximum_spacing_m, "espaciamiento maximo")
        require_positive(self.maximum_skin_spacing_m, "espaciamiento maximo Ask")
        require_positive(self.shear_resistance_factor, "phi corte")
        require_positive(self.shear_beta, "beta corte")
        require_positive(self.shear_theta_degrees, "theta corte")
        if self.shear_resistance_factor > 1.0:
            raise ValueError("phi corte no debe exceder 1.0.")
        if self.maximum_main_bar_layers < 1:
            raise ValueError("El numero maximo de capas debe ser al menos 1.")
        if self.stirrup_legs < 2:
            raise ValueError("Los estribos deben tener al menos dos ramas.")


@dataclass(frozen=True)
class MainGirderSteelDesign:
    """Main longitudinal flexural steel for the interior girder."""

    controlling_combination_name: str
    position_m: float
    design_moment_tn_m: float
    effective_depth_cm: float
    flange_width_cm: float
    flange_thickness_cm: float
    web_width_cm: float
    strength_area_cm2: float
    minimum_area_cm2: float
    required_area_cm2: float
    neutral_axis_block_depth_cm: float
    placement_options: LongitudinalPlacementCaseOptions
    cracking_moment_tn_m: float = 0.0
    minimum_capacity_moment_tn_m: float = 0.0


@dataclass(frozen=True)
class WebTemperatureSteelDesign:
    """Shrinkage and temperature steel on each lateral web face."""

    ratio: float
    web_width_cm: float
    required_area_cm2_m_per_face: float
    spacing_options: ReinforcementCaseOptions


@dataclass(frozen=True)
class SkinLongitudinalSteelDesign:
    """Longitudinal skin reinforcement Ask on each side face."""

    effective_depth_cm: float
    distribution_height_m: float
    uncapped_required_area_cm2_m_per_face: float
    maximum_total_area_cm2_per_face: float
    required_total_area_cm2_per_face: float
    required_area_cm2_m_per_face: float
    maximum_spacing_m: float
    spacing_options: ReinforcementCaseOptions


@dataclass(frozen=True)
class InteriorGirderReinforcementDesign:
    """Grouped reinforcement design for the interior girder."""

    main: MainGirderSteelDesign
    temperature: WebTemperatureSteelDesign
    skin: SkinLongitudinalSteelDesign
    parameters: InteriorGirderReinforcementParameters


@dataclass(frozen=True)
class InteriorGirderCrackControlReview:
    """Crack control checks for selected interior girder reinforcement."""

    main: CrackControlCheck


@dataclass(frozen=True)
class CrackedSectionProperties:
    """Elastic transformed cracked-section properties for positive flexure."""

    modular_ratio: int
    neutral_axis_depth_cm: float
    inertia_cm4: float
    is_cracked: bool
    bottom_tension_kg_cm2: float
    cracking_threshold_kg_cm2: float


@dataclass(frozen=True)
class InteriorGirderFatigueReview:
    """Fatigue check for selected longitudinal flexural reinforcement."""

    fatigue_moment_tn_m: float
    fatigue_position_m: float
    permanent_moment_tn_m: float
    section: CrackedSectionProperties
    minimum_stress_kg_cm2: float
    stress_range_kg_cm2: float
    factored_stress_range_kg_cm2: float
    allowable_stress_range_kg_cm2: float
    status: str
    reference: str = FATIGUE_REINFORCEMENT_REFERENCE


@dataclass(frozen=True)
class InteriorGirderStressVerification:
    """Service stress verification for concrete and steel."""

    service_moment_tn_m: float
    position_m: float
    section: CrackedSectionProperties
    concrete_compression_kg_cm2: float
    concrete_compression_limit_kg_cm2: float
    steel_tension_kg_cm2: float
    steel_tension_limit_kg_cm2: float
    concrete_status: str
    steel_status: str


@dataclass(frozen=True)
class ShearStirrupOption:
    """Two-leg stirrup spacing option for shear design."""

    item: int
    bar_label: str
    bar_area_cm2: float
    legs: int
    spacing_m: float
    required_av_cm2_m: float
    provided_av_cm2_m: float
    phi_vn_tn: float
    is_compliant: bool
    is_recommended: bool = False
    is_custom: bool = False

    @property
    def excess_percent(self) -> float:
        """Return excess provided transverse steel."""
        if self.required_av_cm2_m <= 0.0:
            return 0.0
        return (self.provided_av_cm2_m / self.required_av_cm2_m - 1.0) * 100.0


@dataclass(frozen=True)
class InteriorGirderShearDesign:
    """Shear design result for the interior girder."""

    controlling_shear: InteriorGirderCombinedShear
    effective_shear_depth_cm: float
    web_width_cm: float
    steel_yield_kg_cm2: float
    phi: float
    beta: float
    theta_degrees: float
    vc_tn: float
    required_vs_tn: float
    nominal_shear_limit_tn: float
    required_av_cm2_m: float
    minimum_av_cm2_m: float
    maximum_spacing_m: float
    transverse_required: bool
    options: tuple[ShearStirrupOption, ...]
    reference: str = SHEAR_DESIGN_REFERENCE

    @property
    def recommended(self) -> ShearStirrupOption | None:
        """Return recommended stirrup option."""
        for option in self.options:
            if option.is_recommended:
                return option
        return None


def solve_interior_girder_design(
    geometry: InteriorGirderGeometry,
    materials: MaterialProperties,
    live_loads: LiveLoads,
) -> InteriorGirderAnalysisResult:
    """Solve longitudinal DC, DW and moving HL-93 live-load envelopes."""
    dc = _solve_static_longitudinal_case(
        geometry=geometry,
        name="DC - losa, viga y diafragmas",
        uniform_loads_tn_m=_dc_uniform_loads_tn_m(geometry, materials),
        point_loads_tn=_dc_point_loads_tn(geometry, materials),
    )
    dw = _solve_static_longitudinal_case(
        geometry=geometry,
        name="DW - superficie de rodadura",
        uniform_loads_tn_m=(materials.asphalt.specific_weight_tn_m3 * materials.asphalt.thickness_m * geometry.tributary_width_m,),
        point_loads_tn=(),
    )
    truck = _solve_moving_vehicle_case(
        geometry=geometry,
        vehicle=live_loads.vehicular,
        axles_tn=live_loads.vehicular.design_truck_axles_tn,
        spacing_sets_m=_truck_spacing_sets(live_loads.vehicular),
        name="LL+IM - camion de diseno",
        lane_load_tn_m=live_loads.vehicular.lane_load_tn_m,
        impact_factor=mtc_dynamic_load_allowance_for_slab(),
    )
    tandem = _solve_moving_vehicle_case(
        geometry=geometry,
        vehicle=live_loads.vehicular,
        axles_tn=live_loads.vehicular.design_tandem_axles_tn,
        spacing_sets_m=((live_loads.vehicular.design_tandem_spacing_m,),),
        name="LL+IM - tandem de diseno",
        lane_load_tn_m=live_loads.vehicular.lane_load_tn_m,
        impact_factor=mtc_dynamic_load_allowance_for_slab(),
    )
    fatigue = _solve_moving_vehicle_case(
        geometry=geometry,
        vehicle=live_loads.vehicular,
        axles_tn=live_loads.vehicular.design_truck_axles_tn,
        spacing_sets_m=(
            (
                live_loads.vehicular.design_truck_spacings_m[0],
                live_loads.vehicular.design_truck_spacings_m[1][1],
            ),
        ),
        name="FATIGA I - camion de fatiga",
        lane_load_tn_m=0.0,
        impact_factor=FATIGUE_DYNAMIC_LOAD_ALLOWANCE,
        moment_distribution_factor_g=mtc_interior_concrete_t_girder_fatigue_live_load_moment_distribution_factor(
            span_length_m=geometry.span_length_m,
            girder_spacing_m=geometry.girder_spacing_m,
            slab_thickness_m=geometry.slab_thickness_m,
            girder_total_height_m=geometry.girder_total_height_m,
            web_width_m=geometry.web_width_m,
            girder_count=geometry.girder_count,
        ),
        shear_distribution_factor_g=mtc_interior_concrete_t_girder_fatigue_live_load_shear_distribution_factor(
            span_length_m=geometry.span_length_m,
            girder_spacing_m=geometry.girder_spacing_m,
            slab_thickness_m=geometry.slab_thickness_m,
            girder_count=geometry.girder_count,
        ),
    )
    envelope = _combine_live_load_cases(geometry, truck, tandem)
    return InteriorGirderAnalysisResult(
        dc=dc,
        dw=dw,
        truck_ll_im=truck,
        tandem_ll_im=tandem,
        ll_im_envelope=envelope,
        fatigue_truck=fatigue,
        dynamic_load_allowance=mtc_dynamic_load_allowance_for_slab(),
        distribution_factor_g=geometry.live_load_distribution_factor_g,
        shear_distribution_factor_g=geometry.live_load_shear_distribution_factor_g,
    )


@lru_cache(maxsize=8)
def combine_interior_girder_moments(
    result: InteriorGirderAnalysisResult,
) -> tuple[InteriorGirderCombinedMoment, ...]:
    """Return interior girder factored moment rows for standard combinations."""
    combinations = (
        ("RESISTENCIA I", "Resistencia", LoadFactor(1.25, 0.90), LoadFactor(1.50, 0.65), LoadFactor(1.75, omit_when_favorable=True)),
        ("SERVICIO I", "Servicio", LoadFactor(1.00), LoadFactor(1.00), LoadFactor(1.00, omit_when_favorable=True)),
        ("SERVICIO III", "Servicio", LoadFactor(1.00), LoadFactor(1.00), LoadFactor(0.80, omit_when_favorable=True)),
    )
    positions = _combined_positions(result.dc, result.dw, result.ll_im_envelope)
    rows: list[InteriorGirderCombinedMoment] = []
    for name, limit_state, dc_factor, dw_factor, ll_factor in combinations:
        candidates = []
        for position in positions:
            dc = _moment_at(result.dc.moment_samples_tn_m, position)
            dw = _moment_at(result.dw.moment_samples_tn_m, position)
            ll = _moment_at(result.ll_im_envelope.moment_samples_tn_m, position)
            g_dc = dc_factor.for_effect(dc, "max")
            g_dw = dw_factor.for_effect(dw, "max")
            g_ll = ll_factor.for_effect(ll, "max")
            combined = g_dc * dc + g_dw * dw + g_ll * ll
            candidates.append(
                InteriorGirderCombinedMoment(
                    combination_name=name,
                    limit_state=limit_state,
                    position_m=position,
                    dc_moment_tn_m=dc,
                    dc_factor=g_dc,
                    dw_moment_tn_m=dw,
                    dw_factor=g_dw,
                    ll_im_moment_tn_m=ll,
                    ll_im_factor=g_ll,
                    combined_moment_tn_m=combined,
                )
            )
        rows.append(max(candidates, key=lambda item: item.combined_moment_tn_m))
    return tuple(rows)


@lru_cache(maxsize=8)
def combine_interior_girder_shears(
    geometry: InteriorGirderGeometry,
    result: InteriorGirderAnalysisResult,
    parameters: InteriorGirderReinforcementParameters | None = None,
) -> tuple[InteriorGirderCombinedShear, ...]:
    """Return Strength I shears at critical sections near both supports."""
    params = parameters or InteriorGirderReinforcementParameters()
    effective_depth_cm = _effective_depth_cm_for_girder(geometry, params)
    dv_m = _effective_shear_depth_cm(geometry, effective_depth_cm) / 100.0
    positions = (
        min(max(dv_m, 0.0), geometry.span_length_m),
        min(max(geometry.span_length_m - dv_m, 0.0), geometry.span_length_m),
    )
    rows = []
    for position in positions:
        dc = abs(_sample_at(result.dc.shear_samples_tn, position))
        dw = abs(_sample_at(result.dw.shear_samples_tn, position))
        ll = abs(_sample_at(result.ll_im_envelope.shear_samples_tn, position))
        rows.append(
            InteriorGirderCombinedShear(
                combination_name="RESISTENCIA I",
                limit_state="Resistencia",
                position_m=position,
                dc_shear_tn=dc,
                dc_factor=1.25,
                dw_shear_tn=dw,
                dw_factor=1.50,
                ll_im_shear_tn=ll,
                ll_im_factor=1.75,
                combined_shear_tn=1.25 * dc + 1.50 * dw + 1.75 * ll,
            )
        )
    return tuple(rows)


def design_interior_girder_reinforcement(
    geometry: InteriorGirderGeometry,
    materials: MaterialProperties,
    analysis: InteriorGirderAnalysisResult,
    parameters: InteriorGirderReinforcementParameters | None = None,
) -> InteriorGirderReinforcementDesign:
    """Return main, web-temperature and skin reinforcement for the interior girder."""
    params = parameters or InteriorGirderReinforcementParameters()
    strength_row = max(
        (row for row in combine_interior_girder_moments(analysis) if row.limit_state == "Resistencia"),
        key=lambda item: item.combined_moment_tn_m,
    )
    total_depth_cm = geometry.total_t_section_depth_m * 100.0
    effective_depth_cm = total_depth_cm - params.concrete_cover_cm - params.main_bar_diameter_cm / 2.0
    require_positive(effective_depth_cm, "peralte efectivo de viga")
    flange_width_cm = geometry.tributary_width_m * 100.0
    flange_thickness_cm = geometry.slab_thickness_m * 100.0
    web_width_cm = geometry.web_width_m * 100.0
    gross_centroid_cm, gross_inertia_cm4 = _gross_t_section_properties(geometry)
    cracking_moment = mtc_cracking_moment_tn_m(
        gross_inertia_cm4 / max(total_depth_cm - gross_centroid_cm, 1e-9),
        materials.concrete.compressive_strength_kg_cm2,
        variability_factor=materials.steel.cracking_moment_factor,
    )
    minimum_moment = mtc_minimum_flexural_moment_tn_m(
        abs(strength_row.combined_moment_tn_m), cracking_moment
    )
    strength_area, neutral_axis = t_beam_flexural_steel_area_cm2(
        design_moment_tn_m=minimum_moment,
        flange_width_cm=flange_width_cm,
        flange_thickness_cm=flange_thickness_cm,
        web_width_cm=web_width_cm,
        effective_depth_cm=effective_depth_cm,
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        phi=params.flexural_resistance_factor,
        steel_elastic_modulus_kg_cm2=materials.steel.elastic_modulus_kg_cm2,
    )
    minimum_area = _minimum_flexural_area_cm2(
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        web_width_cm=web_width_cm,
        effective_depth_cm=effective_depth_cm,
    )
    required_area = max(strength_area, minimum_area)
    placement_options = _iterated_main_placement_options(
        "Acero principal longitudinal", required_area, geometry, params,
        minimum_moment, flange_width_cm, flange_thickness_cm,
        web_width_cm, materials,
    )
    selected = placement_options.recommended
    adopted_depth_cm = selected.effective_depth_cm if selected is not None else effective_depth_cm
    if selected is not None:
        strength_area, neutral_axis = t_beam_flexural_steel_area_cm2(
            design_moment_tn_m=minimum_moment,
            flange_width_cm=flange_width_cm, flange_thickness_cm=flange_thickness_cm,
            web_width_cm=web_width_cm, effective_depth_cm=adopted_depth_cm,
            concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
            steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
            phi=params.flexural_resistance_factor,
            steel_elastic_modulus_kg_cm2=materials.steel.elastic_modulus_kg_cm2,
        )
        minimum_area = _minimum_flexural_area_cm2(
            concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
            steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
            web_width_cm=web_width_cm, effective_depth_cm=adopted_depth_cm,
        )
        required_area = max(strength_area, minimum_area)
    spacing_grid = _spacing_grid(params)
    temperature_required = (
        params.shrinkage_temperature_ratio * 100.0 * web_width_cm / 2.0
    )
    extreme_tension_depth_cm = (
        total_depth_cm
        - params.concrete_cover_cm
        - (selected.bar_diameter_cm if selected is not None else params.main_bar_diameter_cm) / 2.0
    )
    (
        skin_required,
        skin_uncapped,
        skin_distribution_height,
        skin_required_total,
        skin_maximum_total,
        skin_maximum_spacing,
    ) = _skin_reinforcement_requirements(
        extreme_tension_depth_cm=extreme_tension_depth_cm,
        required_flexural_area_cm2=required_area,
        configured_maximum_spacing_m=params.maximum_skin_spacing_m,
    )
    return InteriorGirderReinforcementDesign(
        main=MainGirderSteelDesign(
            controlling_combination_name=strength_row.combination_name,
            position_m=strength_row.position_m,
            design_moment_tn_m=strength_row.combined_moment_tn_m,
            effective_depth_cm=adopted_depth_cm,
            flange_width_cm=flange_width_cm,
            flange_thickness_cm=flange_thickness_cm,
            web_width_cm=web_width_cm,
            strength_area_cm2=strength_area,
            minimum_area_cm2=minimum_area,
            required_area_cm2=required_area,
            neutral_axis_block_depth_cm=neutral_axis,
            placement_options=placement_options,
            cracking_moment_tn_m=cracking_moment,
            minimum_capacity_moment_tn_m=minimum_moment,
        ),
        temperature=WebTemperatureSteelDesign(
            ratio=params.shrinkage_temperature_ratio,
            web_width_cm=web_width_cm,
            required_area_cm2_m_per_face=temperature_required,
            spacing_options=generate_spacing_options(
                "Temperatura en cada cara lateral",
                temperature_required,
                spacing_grid,
            ),
        ),
        skin=SkinLongitudinalSteelDesign(
            effective_depth_cm=extreme_tension_depth_cm,
            distribution_height_m=skin_distribution_height,
            uncapped_required_area_cm2_m_per_face=skin_uncapped,
            maximum_total_area_cm2_per_face=skin_maximum_total,
            required_total_area_cm2_per_face=skin_required_total,
            required_area_cm2_m_per_face=skin_required,
            maximum_spacing_m=skin_maximum_spacing,
            spacing_options=generate_spacing_options(
                "Ask longitudinal por cara",
                skin_required,
                SpacingGrid(
                    step_m=params.spacing_step_m,
                    minimum_m=params.minimum_spacing_m,
                    maximum_m=skin_maximum_spacing,
                ),
            ),
        ),
        parameters=params,
    )


def review_interior_girder_crack_control(
    geometry: InteriorGirderGeometry,
    materials: MaterialProperties,
    analysis: InteriorGirderAnalysisResult,
    reinforcement: InteriorGirderReinforcementDesign,
    main_placement: LongitudinalBarPlacementOption | None = None,
) -> InteriorGirderCrackControlReview:
    """Return crack control review for selected main longitudinal bars."""
    selected = main_placement or _recommended_main_option(reinforcement.main)
    service_row = max(
        (row for row in combine_interior_girder_moments(analysis) if row.combination_name == "SERVICIO I"),
        key=lambda item: item.combined_moment_tn_m,
    )
    dc_cm = reinforcement.parameters.concrete_cover_cm + selected.bar_diameter_cm / 2.0
    effective_depth_cm = geometry.total_t_section_depth_m * 100.0 - dc_cm
    steel_stress = _service_steel_stress_kg_cm2(
        service_moment_tn_m=service_row.combined_moment_tn_m,
        provided_area_cm2=selected.provided_area_cm2,
        effective_depth_cm=effective_depth_cm,
    )
    stress_limit = 0.60 * materials.steel.yield_strength_kg_cm2
    stress_used = min(steel_stress, stress_limit)
    maximum_spacing, beta_s = maximum_crack_control_spacing_m(
        steel_stress_kg_cm2=stress_used,
        dc_cm=dc_cm,
        slab_thickness_cm=geometry.total_t_section_depth_m * 100.0,
        exposure_factor=DEFAULT_CRACK_CONTROL_EXPOSURE_FACTOR,
    )
    provided_spacing_m = max(selected.clear_spacing_cm + selected.bar_diameter_cm, 0.0) / 100.0
    stress_status, spacing_status, status = crack_control_compliance_statuses(
        steel_stress,
        stress_limit,
        provided_spacing_m,
        maximum_spacing,
    )
    return InteriorGirderCrackControlReview(
        main=CrackControlCheck(
            label="Fisuracion acero principal viga interior",
            direction="M+",
            service_combination_name=service_row.combination_name,
            service_moment_tn_m=service_row.combined_moment_tn_m,
            bar_label=selected.bar_label,
            bar_area_cm2=selected.bar_area_cm2,
            provided_spacing_m=provided_spacing_m,
            provided_area_cm2_m=selected.provided_area_cm2,
            steel_stress_kg_cm2=steel_stress,
            steel_stress_used_kg_cm2=stress_used,
            steel_stress_limit_kg_cm2=stress_limit,
            beta_s=beta_s,
            dc_cm=dc_cm,
            maximum_spacing_m=maximum_spacing,
            stress_status=stress_status,
            spacing_status=spacing_status,
            status=status,
        )
    )


def review_interior_girder_fatigue(
    geometry: InteriorGirderGeometry,
    materials: MaterialProperties,
    analysis: InteriorGirderAnalysisResult,
    reinforcement: InteriorGirderReinforcementDesign,
    main_placement: LongitudinalBarPlacementOption | None = None,
) -> InteriorGirderFatigueReview:
    """Return Fatigue I stress-range check for straight reinforcing bars."""
    selected = main_placement or _recommended_main_option(reinforcement.main)
    fatigue_case = analysis.fatigue_truck
    fatigue_moment = fatigue_case.max_positive_moment_tn_m
    position = fatigue_case.max_positive_position_m
    permanent_moment = (
        _moment_at(analysis.dc.moment_samples_tn_m, position)
        + _moment_at(analysis.dw.moment_samples_tn_m, position)
    )
    section = cracked_section_properties(
        geometry=geometry,
        materials=materials,
        steel_area_cm2=selected.provided_area_cm2,
        total_moment_tn_m=permanent_moment + FATIGUE_I_LOAD_FACTOR * fatigue_moment,
        parameters=reinforcement.parameters,
        steel_depth_cm=_steel_depth_cm(geometry, selected, reinforcement.parameters),
    )
    minimum_stress = _steel_stress_from_moment_kg_cm2(
        moment_tn_m=permanent_moment,
        section=section,
        steel_depth_cm=_steel_depth_cm(geometry, selected, reinforcement.parameters),
    )
    stress_range = _steel_stress_from_moment_kg_cm2(
        moment_tn_m=fatigue_moment,
        section=section,
        steel_depth_cm=_steel_depth_cm(geometry, selected, reinforcement.parameters),
    )
    factored_range = FATIGUE_I_LOAD_FACTOR * stress_range
    allowable = fatigue_reinforcing_bar_stress_range_limit_kg_cm2(
        minimum_stress_kg_cm2=minimum_stress,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
    )
    return InteriorGirderFatigueReview(
        fatigue_moment_tn_m=fatigue_moment,
        fatigue_position_m=position,
        permanent_moment_tn_m=permanent_moment,
        section=section,
        minimum_stress_kg_cm2=minimum_stress,
        stress_range_kg_cm2=stress_range,
        factored_stress_range_kg_cm2=factored_range,
        allowable_stress_range_kg_cm2=allowable,
        status="CUMPLE" if factored_range <= allowable + 1e-9 else "NO CUMPLE",
    )


def verify_interior_girder_service_stresses(
    geometry: InteriorGirderGeometry,
    materials: MaterialProperties,
    analysis: InteriorGirderAnalysisResult,
    reinforcement: InteriorGirderReinforcementDesign,
    main_placement: LongitudinalBarPlacementOption | None = None,
) -> InteriorGirderStressVerification:
    """Return Service I concrete and steel stress verification."""
    selected = main_placement or _recommended_main_option(reinforcement.main)
    service_row = max(
        (row for row in combine_interior_girder_moments(analysis) if row.combination_name == "SERVICIO I"),
        key=lambda item: item.combined_moment_tn_m,
    )
    section = cracked_section_properties(
        geometry=geometry,
        materials=materials,
        steel_area_cm2=selected.provided_area_cm2,
        total_moment_tn_m=service_row.combined_moment_tn_m,
        parameters=reinforcement.parameters,
        steel_depth_cm=_steel_depth_cm(geometry, selected, reinforcement.parameters),
    )
    concrete_compression = _concrete_top_stress_kg_cm2(service_row.combined_moment_tn_m, section)
    steel_tension = _steel_stress_from_moment_kg_cm2(
        moment_tn_m=service_row.combined_moment_tn_m,
        section=section,
        steel_depth_cm=_steel_depth_cm(geometry, selected, reinforcement.parameters),
    )
    concrete_limit = 0.45 * materials.concrete.compressive_strength_kg_cm2
    steel_limit = 0.60 * materials.steel.yield_strength_kg_cm2
    return InteriorGirderStressVerification(
        service_moment_tn_m=service_row.combined_moment_tn_m,
        position_m=service_row.position_m,
        section=section,
        concrete_compression_kg_cm2=concrete_compression,
        concrete_compression_limit_kg_cm2=concrete_limit,
        steel_tension_kg_cm2=steel_tension,
        steel_tension_limit_kg_cm2=steel_limit,
        concrete_status="CUMPLE" if concrete_compression <= concrete_limit + 1e-9 else "NO CUMPLE",
        steel_status="CUMPLE" if steel_tension <= steel_limit + 1e-9 else "NO CUMPLE",
    )


def design_interior_girder_shear(
    geometry: InteriorGirderGeometry,
    materials: MaterialProperties,
    analysis: InteriorGirderAnalysisResult,
    reinforcement: InteriorGirderReinforcementDesign,
) -> InteriorGirderShearDesign:
    """Return simplified sectional shear design for a nonprestressed interior girder."""
    params = reinforcement.parameters
    controlling = max(
        combine_interior_girder_shears(geometry, analysis, params),
        key=lambda item: item.combined_shear_tn,
    )
    effective_shear_depth_cm = _effective_shear_depth_cm(
        geometry,
        reinforcement.main.effective_depth_cm,
    )
    web_width_cm = geometry.web_width_m * 100.0
    vc = _concrete_shear_resistance_tn(
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        web_width_cm=web_width_cm,
        effective_shear_depth_cm=effective_shear_depth_cm,
        beta=params.shear_beta,
    )
    nominal_limit = _nominal_shear_upper_limit_tn(
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        web_width_cm=web_width_cm,
        effective_shear_depth_cm=effective_shear_depth_cm,
    )
    required_vs = max(controlling.combined_shear_tn / params.shear_resistance_factor - vc, 0.0)
    minimum_av = _minimum_shear_reinforcement_cm2_m(
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        web_width_cm=web_width_cm,
    )
    transverse_required = controlling.combined_shear_tn > 0.5 * params.shear_resistance_factor * vc
    required_av = _required_shear_reinforcement_cm2_m(
        required_vs_tn=required_vs,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        effective_shear_depth_cm=effective_shear_depth_cm,
    )
    if transverse_required:
        required_av = max(required_av, minimum_av)
    max_spacing = _maximum_shear_spacing_m(
        vu_tn=controlling.combined_shear_tn,
        phi=params.shear_resistance_factor,
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        web_width_cm=web_width_cm,
        effective_shear_depth_cm=effective_shear_depth_cm,
    )
    options = _generate_shear_stirrup_options(
        required_av_cm2_m=required_av,
        max_spacing_m=max_spacing,
        legs=params.stirrup_legs,
        vu_tn=controlling.combined_shear_tn,
        vc_tn=vc,
        nominal_limit_tn=nominal_limit,
        materials=materials,
        effective_shear_depth_cm=effective_shear_depth_cm,
        phi=params.shear_resistance_factor,
    )
    return InteriorGirderShearDesign(
        controlling_shear=controlling,
        effective_shear_depth_cm=effective_shear_depth_cm,
        web_width_cm=web_width_cm,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        phi=params.shear_resistance_factor,
        beta=params.shear_beta,
        theta_degrees=params.shear_theta_degrees,
        vc_tn=vc,
        required_vs_tn=required_vs,
        nominal_shear_limit_tn=nominal_limit,
        required_av_cm2_m=required_av,
        minimum_av_cm2_m=minimum_av,
        maximum_spacing_m=max_spacing,
        transverse_required=transverse_required,
        options=options,
    )


def cracked_section_properties(
    geometry: InteriorGirderGeometry,
    materials: MaterialProperties,
    steel_area_cm2: float,
    total_moment_tn_m: float,
    parameters: InteriorGirderReinforcementParameters,
    steel_depth_cm: float | None = None,
) -> CrackedSectionProperties:
    """Return transformed section properties, cracking state and cracking demand."""
    require_positive(steel_area_cm2, "As")
    modular_ratio = round(
        materials.steel.elastic_modulus_kg_cm2 / materials.concrete.elastic_modulus_kg_cm2
    )
    d_cm = steel_depth_cm or (
        geometry.total_t_section_depth_m * 100.0
        - parameters.concrete_cover_cm - parameters.main_bar_diameter_cm / 2.0
    )
    threshold = _fatigue_cracking_threshold_kg_cm2(materials.concrete.compressive_strength_kg_cm2)
    gross = _gross_t_section_properties(geometry)
    bottom_stress = total_moment_tn_m * 100000.0 * (geometry.total_t_section_depth_m * 100.0 - gross[0]) / gross[1]
    is_cracked = bottom_stress > threshold
    if not is_cracked:
        transformed = _uncracked_transformed_properties(geometry, modular_ratio, steel_area_cm2, d_cm)
        return CrackedSectionProperties(
            modular_ratio=modular_ratio,
            neutral_axis_depth_cm=transformed[0],
            inertia_cm4=transformed[1],
            is_cracked=False,
            bottom_tension_kg_cm2=bottom_stress,
            cracking_threshold_kg_cm2=threshold,
        )
    neutral_axis = _cracked_neutral_axis_cm(
        flange_width_cm=geometry.tributary_width_m * 100.0,
        flange_thickness_cm=geometry.slab_thickness_m * 100.0,
        web_width_cm=geometry.web_width_m * 100.0,
        steel_area_cm2=steel_area_cm2,
        modular_ratio=modular_ratio,
        steel_depth_cm=d_cm,
    )
    inertia = _cracked_inertia_cm4(
        flange_width_cm=geometry.tributary_width_m * 100.0,
        flange_thickness_cm=geometry.slab_thickness_m * 100.0,
        web_width_cm=geometry.web_width_m * 100.0,
        steel_area_cm2=steel_area_cm2,
        modular_ratio=modular_ratio,
        steel_depth_cm=d_cm,
        neutral_axis_cm=neutral_axis,
    )
    return CrackedSectionProperties(
        modular_ratio=modular_ratio,
        neutral_axis_depth_cm=neutral_axis,
        inertia_cm4=inertia,
        is_cracked=True,
        bottom_tension_kg_cm2=bottom_stress,
        cracking_threshold_kg_cm2=threshold,
    )


def fatigue_reinforcing_bar_stress_range_limit_kg_cm2(
    minimum_stress_kg_cm2: float,
    steel_yield_kg_cm2: float,
) -> float:
    """Return MTC/AASHTO fatigue stress-range limit for straight bars."""
    fy_ksi = max(60.0, min(100.0, kg_cm2_to_ksi(steel_yield_kg_cm2)))
    fmin_ksi = kg_cm2_to_ksi(minimum_stress_kg_cm2)
    return ksi_to_kg_cm2(max(24.0 - 20.0 * fmin_ksi / fy_ksi, 0.0))


def t_beam_flexural_response(
    steel_area_cm2: float,
    flange_width_cm: float,
    flange_thickness_cm: float,
    web_width_cm: float,
    effective_depth_cm: float,
    concrete_strength_kg_cm2: float,
    steel_yield_kg_cm2: float,
    steel_elastic_modulus_kg_cm2: float = DEFAULT_STEEL_ELASTIC_MODULUS_KG_CM2,
    extreme_tension_depth_cm: float | None = None,
) -> RectangularFlexuralResponse:
    """Return the strain-compatible response of a singly reinforced T section."""
    require_positive(steel_area_cm2, "As")
    require_positive(flange_width_cm, "bf")
    require_positive(flange_thickness_cm, "hf")
    require_positive(web_width_cm, "bw")
    require_positive(effective_depth_cm, "d")
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
        flange_depth = min(a_cm, flange_thickness_cm)
        flange_width_extra = max(flange_width_cm - web_width_cm, 0.0)
        compression = 0.85 * concrete_strength_kg_cm2 * (
            web_width_cm * a_cm + flange_width_extra * flange_depth
        )
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
    flange_depth = min(a_cm, flange_thickness_cm)
    flange_width_extra = max(flange_width_cm - web_width_cm, 0.0)
    c_web = 0.85 * concrete_strength_kg_cm2 * web_width_cm * a_cm
    c_flange = (
        0.85
        * concrete_strength_kg_cm2
        * flange_width_extra
        * flange_depth
    )
    steel_strain = CONCRETE_ULTIMATE_STRAIN * (
        effective_depth_cm - c_cm
    ) / c_cm
    steel_stress = min(
        steel_yield_kg_cm2,
        max(steel_elastic_modulus_kg_cm2 * steel_strain, 0.0),
    )
    extreme_strain = max(
        CONCRETE_ULTIMATE_STRAIN * (tension_depth - c_cm) / c_cm,
        0.0,
    )
    nominal_moment = (
        c_web * (effective_depth_cm - a_cm / 2.0)
        + c_flange * (effective_depth_cm - flange_depth / 2.0)
    ) / 100000.0
    return RectangularFlexuralResponse(
        neutral_axis_depth_cm=c_cm,
        compression_block_depth_cm=a_cm,
        steel_strain=steel_strain,
        steel_stress_kg_cm2=steel_stress,
        extreme_tensile_strain=extreme_strain,
        resistance_factor=mtc_flexural_resistance_factor(extreme_strain),
        nominal_moment_tn_m=nominal_moment,
    )


def t_beam_flexural_steel_area_cm2(
    design_moment_tn_m: float,
    flange_width_cm: float,
    flange_thickness_cm: float,
    web_width_cm: float,
    effective_depth_cm: float,
    concrete_strength_kg_cm2: float,
    steel_yield_kg_cm2: float,
    phi: float = DEFAULT_FLEXURAL_RESISTANCE_FACTOR,
    steel_elastic_modulus_kg_cm2: float = DEFAULT_STEEL_ELASTIC_MODULUS_KG_CM2,
    extreme_tension_depth_cm: float | None = None,
) -> tuple[float, float]:
    """Return strain-compatible required As and block depth for a T beam."""
    require_non_negative(design_moment_tn_m, "Mu")
    require_positive(flange_width_cm, "bf")
    require_positive(flange_thickness_cm, "hf")
    require_positive(web_width_cm, "bw")
    require_positive(effective_depth_cm, "d")
    require_positive(concrete_strength_kg_cm2, "f'c")
    require_positive(steel_yield_kg_cm2, "fy")
    require_positive(phi, "phi")
    require_positive(steel_elastic_modulus_kg_cm2, "Es")
    if phi > 1.0:
        raise ValueError("phi no debe exceder 1.0.")
    if design_moment_tn_m == 0.0:
        return 0.0, 0.0
    tension_depth = (
        effective_depth_cm
        if extreme_tension_depth_cm is None
        else extreme_tension_depth_cm
    )
    require_positive(tension_depth, "dt")
    if tension_depth < effective_depth_cm:
        raise ValueError("dt no debe ser menor que ds.")
    beta1 = mtc_beta1(concrete_strength_kg_cm2)

    def state_at_c(c_cm: float) -> tuple[float, float, float]:
        a_cm = beta1 * c_cm
        flange_depth = min(a_cm, flange_thickness_cm)
        flange_width_extra = max(flange_width_cm - web_width_cm, 0.0)
        c_web = 0.85 * concrete_strength_kg_cm2 * web_width_cm * a_cm
        c_flange = 0.85 * concrete_strength_kg_cm2 * flange_width_extra * flange_depth
        compression = c_web + c_flange
        steel_strain = CONCRETE_ULTIMATE_STRAIN * (
            effective_depth_cm - c_cm
        ) / c_cm
        steel_stress = min(
            steel_yield_kg_cm2,
            max(steel_elastic_modulus_kg_cm2 * steel_strain, 0.0),
        )
        steel_area = compression / steel_stress if steel_stress > 0.0 else float("inf")
        nominal_moment_kg_cm = (
            c_web * (effective_depth_cm - a_cm / 2.0)
            + c_flange * (effective_depth_cm - flange_depth / 2.0)
        )
        extreme_strain = max(
            CONCRETE_ULTIMATE_STRAIN * (tension_depth - c_cm) / c_cm,
            0.0,
        )
        effective_phi = min(
            phi,
            mtc_flexural_resistance_factor(extreme_strain),
        )
        return steel_area, effective_phi * nominal_moment_kg_cm / 100000.0, a_cm

    previous_c = 0.0
    previous_resistance = 0.0
    bracket: tuple[float, float] | None = None
    maximum_resistance = previous_resistance
    for index in range(1, 2001):
        current_c = effective_depth_cm * index / 2001.0
        _area, current_resistance, _a = state_at_c(current_c)
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
            "El momento ultimo excede la capacidad compatible de la seccion T "
            f"simplemente reforzada (maximo aproximado {maximum_resistance:.3f} Tn.m)."
        )

    lower, upper = bracket
    for _ in range(80):
        mid = (lower + upper) / 2.0
        _area, resistance, _a = state_at_c(mid)
        if resistance < design_moment_tn_m:
            lower = mid
        else:
            upper = mid
    steel_area, _resistance, a_cm = state_at_c((lower + upper) / 2.0)
    return steel_area, a_cm


def generate_main_bar_placement_options(
    label: str,
    required_area_cm2: float,
    geometry: InteriorGirderGeometry,
    parameters: InteriorGirderReinforcementParameters,
    maximum_bar_count: int | None = None,
) -> LongitudinalPlacementCaseOptions:
    """Return practical longitudinal bar-count options for the main girder steel."""
    require_non_negative(required_area_cm2, f"As requerido {label}")
    options: list[LongitudinalBarPlacementOption] = []
    item = 1
    largest_bar_area = max(bar.area_cm2 for bar in REINFORCING_BAR_CATALOG if bar.diameter_cm >= 1.27)
    default_max_count = max(24, ceil(required_area_cm2 / largest_bar_area) + 6)
    max_count = maximum_bar_count or default_max_count
    for bar in REINFORCING_BAR_CATALOG:
        if bar.diameter_cm < 1.27:
            continue
        max_per_layer = _max_bars_per_layer(geometry, parameters, bar.diameter_cm)
        for count in range(2, max_count + 1):
            layers = ceil(count / max_per_layer)
            provided = count * bar.area_cm2
            clear_spacing = _clear_spacing_cm(geometry, parameters, bar.diameter_cm, min(count, max_per_layer))
            centroid_cm, effective_depth_cm = _placement_effective_depth_cm(
                geometry, parameters, bar.diameter_cm, count, max_per_layer, clear_spacing
            )
            options.append(
                LongitudinalBarPlacementOption(
                    item=item,
                    bar_label=bar.label,
                    bar_area_cm2=bar.area_cm2,
                    bar_diameter_cm=bar.diameter_cm,
                    bar_count=count,
                    layers=layers,
                    bars_per_layer=max_per_layer,
                    required_area_cm2=required_area_cm2,
                    provided_area_cm2=provided,
                    clear_spacing_cm=clear_spacing,
                    is_compliant=(
                        provided + 1e-9 >= required_area_cm2
                        and layers <= parameters.maximum_main_bar_layers
                        and clear_spacing + 1e-9 >= parameters.minimum_clear_bar_spacing_cm
                    ),
                    steel_centroid_from_tension_face_cm=centroid_cm,
                    effective_depth_cm=effective_depth_cm,
                )
            )
            item += 1
    recommended = _recommended_placement(options)
    if recommended is None:
        return LongitudinalPlacementCaseOptions(label, required_area_cm2, tuple(options))
    return LongitudinalPlacementCaseOptions(
        label=label,
        required_area_cm2=required_area_cm2,
        options=tuple(
            LongitudinalBarPlacementOption(
                item=option.item,
                bar_label=option.bar_label,
                bar_area_cm2=option.bar_area_cm2,
                bar_diameter_cm=option.bar_diameter_cm,
                bar_count=option.bar_count,
                layers=option.layers,
                bars_per_layer=option.bars_per_layer,
                required_area_cm2=option.required_area_cm2,
                provided_area_cm2=option.provided_area_cm2,
                clear_spacing_cm=option.clear_spacing_cm,
                is_compliant=option.is_compliant,
                is_recommended=option.item == recommended.item,
                steel_centroid_from_tension_face_cm=option.steel_centroid_from_tension_face_cm,
                effective_depth_cm=option.effective_depth_cm,
            )
            for option in options
        ),
    )


def _dc_uniform_loads_tn_m(
    geometry: InteriorGirderGeometry,
    materials: MaterialProperties,
) -> tuple[float, ...]:
    slab = materials.concrete.specific_weight_tn_m3 * geometry.slab_thickness_m * geometry.tributary_width_m
    web = materials.concrete.specific_weight_tn_m3 * geometry.web_width_m * geometry.girder_total_height_m
    return (slab, web)


def _dc_point_loads_tn(
    geometry: InteriorGirderGeometry,
    materials: MaterialProperties,
) -> tuple[tuple[float, float], ...]:
    return tuple(
        (
            diaphragm.position_m,
            materials.concrete.specific_weight_tn_m3
            * diaphragm.thickness_m
            * diaphragm.height_m
            * diaphragm.tributary_width_m,
        )
        for diaphragm in geometry.diaphragms
    )


def _solve_static_longitudinal_case(
    geometry: InteriorGirderGeometry,
    name: str,
    uniform_loads_tn_m: Iterable[float],
    point_loads_tn: Iterable[tuple[float, float]],
) -> LongitudinalLoadCaseAnalysis:
    q_total = sum(uniform_loads_tn_m)
    points = tuple(point_loads_tn)
    samples = tuple(
        (x, _simple_span_moment_at(geometry.span_length_m, x, q_total, points))
        for x in _sample_positions(geometry)
    )
    shear_samples = tuple(
        (x, _simple_span_shear_at(geometry.span_length_m, x, q_total, points))
        for x in _sample_positions(geometry)
    )
    maximum = max(samples, key=lambda item: item[1])
    maximum_shear = max(shear_samples, key=lambda item: abs(item[1]))
    reaction_left = q_total * geometry.span_length_m / 2.0 + sum(
        load * (geometry.span_length_m - position) / geometry.span_length_m
        for position, load in points
    )
    reaction_right = q_total * geometry.span_length_m + sum(load for _, load in points) - reaction_left
    return LongitudinalLoadCaseAnalysis(
        name=name,
        max_positive_moment_tn_m=maximum[1],
        max_positive_position_m=maximum[0],
        support_reactions_tn=(("Fijo", reaction_left), ("Movil", reaction_right)),
        moment_samples_tn_m=samples,
        shear_samples_tn=shear_samples,
        max_shear_tn=abs(maximum_shear[1]),
        max_shear_position_m=maximum_shear[0],
        maximum_support_reactions_tn=(("Fijo", reaction_left), ("Movil", reaction_right)),
        min_moment_samples_tn_m=samples,
        max_shear_samples_tn=shear_samples,
        min_shear_samples_tn=shear_samples,
    )


def custom_main_bar_placement_option(
    case_options: LongitudinalPlacementCaseOptions,
    bar_label: str,
    bar_count: int,
) -> LongitudinalBarPlacementOption:
    """Return a validated catalog placement chosen by diameter and bar count."""
    if bar_count < 2:
        raise ValueError("El acero principal debe tener al menos 2 barras.")
    bar = reinforcing_bar_by_label(bar_label)
    option = next(
        (
            candidate
            for candidate in case_options.options
            if candidate.bar_label == bar.label and candidate.bar_count == bar_count
        ),
        None,
    )
    if option is None:
        maximum = max(
            (
                candidate.bar_count
                for candidate in case_options.options
                if candidate.bar_label == bar.label
            ),
            default=0,
        )
        raise ValueError(
            f"La cantidad solicitada no esta dentro del rango detallado para {bar.label} "
            f"(2 a {maximum} barras)."
        )
    if not option.is_compliant:
        reasons = []
        if option.provided_area_cm2 + 1e-9 < option.required_area_cm2:
            reasons.append(
                f"As provisto {option.provided_area_cm2:.3f} < As requerido {option.required_area_cm2:.3f} cm2"
            )
        reasons.append(
            f"capas={option.layers}, separacion libre={option.clear_spacing_cm:.2f} cm"
        )
        raise ValueError("La configuracion no cumple: " + "; ".join(reasons) + ".")
    return replace(option, item=0, is_recommended=False, is_custom=True)


def custom_shear_stirrup_option(
    design: InteriorGirderShearDesign,
    bar_label: str,
    legs: int,
    spacing_m: float,
) -> ShearStirrupOption:
    """Build a validated stirrup selected outside the generated spacing table."""
    if legs < 2:
        raise ValueError("El estribo debe tener al menos 2 ramas.")
    require_positive(spacing_m, "separacion personalizada de estribos")
    if spacing_m < DEFAULT_SPACING_STEP_M - 1e-9:
        raise ValueError(
            f"La separacion no puede ser menor que {DEFAULT_SPACING_STEP_M:.3f} m."
        )
    if spacing_m > design.maximum_spacing_m + 1e-9:
        raise ValueError(
            f"La separacion no puede exceder {design.maximum_spacing_m:.3f} m."
        )
    bar = reinforcing_bar_by_label(bar_label)
    provided = legs * bar.area_cm2 / spacing_m
    if provided + 1e-9 < design.required_av_cm2_m:
        raise ValueError(
            f"Av provisto = {provided:.3f} cm2/m es menor que "
            f"Av requerido = {design.required_av_cm2_m:.3f} cm2/m."
        )
    vs = (
        provided
        / 100.0
        * (design.steel_yield_kg_cm2 / 1000.0)
        * design.effective_shear_depth_cm
    )
    phi_vn = design.phi * min(design.vc_tn + vs, design.nominal_shear_limit_tn)
    demand = design.controlling_shear.combined_shear_tn
    if phi_vn + 1e-9 < demand:
        raise ValueError(
            f"phiVn = {phi_vn:.3f} Tn es menor que Vu = {demand:.3f} Tn."
        )
    return ShearStirrupOption(
        item=0,
        bar_label=bar.label,
        bar_area_cm2=bar.area_cm2,
        legs=legs,
        spacing_m=spacing_m,
        required_av_cm2_m=design.required_av_cm2_m,
        provided_av_cm2_m=provided,
        phi_vn_tn=phi_vn,
        is_compliant=True,
        is_custom=True,
    )


def _solve_moving_vehicle_case(
    geometry: InteriorGirderGeometry,
    vehicle: VehicleLoadModel,
    axles_tn: tuple[float, ...],
    spacing_sets_m: tuple[tuple[float, ...], ...],
    name: str,
    lane_load_tn_m: float,
    impact_factor: float,
    moment_distribution_factor_g: float | None = None,
    shear_distribution_factor_g: float | None = None,
) -> LongitudinalLoadCaseAnalysis:
    samples = [(x, 0.0) for x in _sample_positions(geometry)]
    min_samples = [(x, float("inf")) for x in _sample_positions(geometry)]
    max_shear_samples = [(x, float("-inf")) for x in _sample_positions(geometry)]
    min_shear_samples = [(x, float("inf")) for x in _sample_positions(geometry)]
    critical_position = 0.0
    critical_config = ""
    critical_before_g = 0.0
    critical_reactions = (0.0, 0.0)
    maximum_support_reactions = [0.0, 0.0]
    moment_g = (
        _live_load_moment_distribution_factor(geometry)
        if moment_distribution_factor_g is None
        else moment_distribution_factor_g
    )
    shear_g = (
        _live_load_shear_distribution_factor(geometry)
        if shear_distribution_factor_g is None
        else shear_distribution_factor_g
    )
    require_positive(moment_g, "g momento carga movil")
    require_positive(shear_g, "g corte carga movil")
    for spacing_set in spacing_sets_m:
        for direction, axle_offsets, axle_loads in _oriented_axle_layouts(
            spacing_set,
            axles_tn,
        ):
            vehicle_length = axle_offsets[-1]
            vehicle_bases = set(
                _moving_vehicle_bases(
                    span_m=geometry.span_length_m,
                    vehicle_length_m=vehicle_length,
                    step_m=geometry.moving_load_step_m,
                )
            )
            vehicle_bases.update(-offset for offset in axle_offsets)
            vehicle_bases.update(geometry.span_length_m - offset for offset in axle_offsets)
            for base in sorted(vehicle_bases):
                axles = tuple(
                    (base + offset, load * (1.0 + impact_factor))
                    for offset, load in zip(axle_offsets, axle_loads)
                    if -NODE_TOLERANCE <= base + offset <= geometry.span_length_m + NODE_TOLERANCE
                )
                reactions = _simple_span_reactions(
                    geometry.span_length_m,
                    lane_load_tn_m,
                    axles,
                )
                scaled_reactions = (
                    shear_g * reactions[0],
                    shear_g * reactions[1],
                )
                maximum_support_reactions[0] = max(
                    maximum_support_reactions[0],
                    scaled_reactions[0],
                )
                maximum_support_reactions[1] = max(
                    maximum_support_reactions[1],
                    scaled_reactions[1],
                )
                reaction_left = reactions[0]
                for index, (x, current) in enumerate(samples):
                    before_g = _simple_span_moment_with_reaction(
                        x,
                        lane_load_tn_m,
                        axles,
                        reaction_left,
                    )
                    moment = moment_g * before_g
                    if moment > current:
                        samples[index] = (x, moment)
                    if moment < min_samples[index][1]:
                        min_samples[index] = (x, moment)
                    shear = shear_g * _simple_span_shear_with_reaction(
                        x,
                        lane_load_tn_m,
                        axles,
                        reaction_left,
                    )
                    if shear > max_shear_samples[index][1]:
                        max_shear_samples[index] = (x, shear)
                    if shear < min_shear_samples[index][1]:
                        min_shear_samples[index] = (x, shear)
                    if moment > critical_before_g * moment_g:
                        critical_position = base
                        critical_config = _configuration_label(name, spacing_set, direction)
                        critical_before_g = before_g
                        critical_reactions = scaled_reactions
    moment_samples = _symmetrized_envelope_samples(tuple(samples), geometry.span_length_m)
    min_moment_samples = _symmetrized_envelope_samples(
        tuple(min_samples),
        geometry.span_length_m,
        target="min",
    )
    max_shear_samples_tuple, min_shear_samples_tuple = _symmetrized_signed_shear_envelopes(
        tuple(max_shear_samples),
        tuple(min_shear_samples),
        geometry.span_length_m,
    )
    shear_samples_tuple = tuple(
        (upper[0], max(abs(upper[1]), abs(lower[1])))
        for upper, lower in zip(max_shear_samples_tuple, min_shear_samples_tuple)
    )
    maximum = max(moment_samples, key=lambda item: item[1])
    maximum_shear = max(shear_samples_tuple, key=lambda item: item[1])
    return LongitudinalLoadCaseAnalysis(
        name=name,
        max_positive_moment_tn_m=maximum[1],
        max_positive_position_m=maximum[0],
        support_reactions_tn=(("Fijo", critical_reactions[0]), ("Movil", critical_reactions[1])),
        shear_samples_tn=shear_samples_tuple,
        max_shear_tn=maximum_shear[1],
        max_shear_position_m=maximum_shear[0],
        maximum_support_reactions_tn=(
            ("Fijo", maximum_support_reactions[0]),
            ("Movil", maximum_support_reactions[1]),
        ),
        critical_vehicle_position_m=critical_position,
        vehicle_configuration=critical_config,
        dynamic_load_allowance=impact_factor,
        distribution_factor_g=moment_g,
        shear_distribution_factor_g=shear_g,
        unfactored_before_g_moment_tn_m=critical_before_g,
        moment_samples_tn_m=moment_samples,
        min_moment_samples_tn_m=min_moment_samples,
        max_shear_samples_tn=max_shear_samples_tuple,
        min_shear_samples_tn=min_shear_samples_tuple,
    )


def _combine_live_load_cases(
    geometry: InteriorGirderGeometry,
    truck: LongitudinalLoadCaseAnalysis,
    tandem: LongitudinalLoadCaseAnalysis,
) -> LongitudinalLoadCaseAnalysis:
    samples = []
    min_samples = []
    shear_samples = []
    max_shear_samples = []
    min_shear_samples = []
    for position in _sample_positions(geometry):
        truck_moment = _moment_at(truck.moment_samples_tn_m, position)
        tandem_moment = _moment_at(tandem.moment_samples_tn_m, position)
        samples.append((position, max(truck_moment, tandem_moment)))
        truck_min_moment = _sample_at(
            truck.min_moment_samples_tn_m or truck.moment_samples_tn_m,
            position,
        )
        tandem_min_moment = _sample_at(
            tandem.min_moment_samples_tn_m or tandem.moment_samples_tn_m,
            position,
        )
        min_samples.append((position, min(truck_min_moment, tandem_min_moment)))
        truck_upper_shear = _sample_at(
            truck.max_shear_samples_tn or truck.shear_samples_tn,
            position,
        )
        tandem_upper_shear = _sample_at(
            tandem.max_shear_samples_tn or tandem.shear_samples_tn,
            position,
        )
        truck_lower_shear = _sample_at(
            truck.min_shear_samples_tn or truck.shear_samples_tn,
            position,
        )
        tandem_lower_shear = _sample_at(
            tandem.min_shear_samples_tn or tandem.shear_samples_tn,
            position,
        )
        upper_shear = max(truck_upper_shear, tandem_upper_shear)
        lower_shear = min(truck_lower_shear, tandem_lower_shear)
        max_shear_samples.append((position, upper_shear))
        min_shear_samples.append((position, lower_shear))
        shear_samples.append((position, max(abs(upper_shear), abs(lower_shear))))
    maximum = max(samples, key=lambda item: item[1])
    maximum_shear = max(shear_samples, key=lambda item: item[1])
    source = truck if truck.max_positive_moment_tn_m >= tandem.max_positive_moment_tn_m else tandem
    truck_support_maxima = dict(
        truck.maximum_support_reactions_tn or truck.support_reactions_tn
    )
    tandem_support_maxima = dict(
        tandem.maximum_support_reactions_tn or tandem.support_reactions_tn
    )
    maximum_support_reactions = tuple(
        (
            label,
            max(truck_support_maxima.get(label, 0.0), tandem_support_maxima.get(label, 0.0)),
        )
        for label in ("Fijo", "Movil")
    )
    return LongitudinalLoadCaseAnalysis(
        name="LL+IM - envolvente camion/tandem + carril",
        max_positive_moment_tn_m=maximum[1],
        max_positive_position_m=maximum[0],
        support_reactions_tn=source.support_reactions_tn,
        critical_vehicle_position_m=source.critical_vehicle_position_m,
        vehicle_configuration=source.vehicle_configuration,
        shear_samples_tn=tuple(shear_samples),
        max_shear_tn=maximum_shear[1],
        max_shear_position_m=maximum_shear[0],
        maximum_support_reactions_tn=maximum_support_reactions,
        dynamic_load_allowance=source.dynamic_load_allowance,
        distribution_factor_g=source.distribution_factor_g,
        shear_distribution_factor_g=source.shear_distribution_factor_g,
        unfactored_before_g_moment_tn_m=source.unfactored_before_g_moment_tn_m,
        moment_samples_tn_m=tuple(samples),
        min_moment_samples_tn_m=tuple(min_samples),
        max_shear_samples_tn=tuple(max_shear_samples),
        min_shear_samples_tn=tuple(min_shear_samples),
    )


def _live_load_moment_distribution_factor(geometry: InteriorGirderGeometry) -> float:
    return float(geometry.live_load_distribution_factor_g)


def _live_load_shear_distribution_factor(geometry: InteriorGirderGeometry) -> float:
    return float(
        getattr(
            geometry,
            "live_load_shear_distribution_factor_g",
            geometry.live_load_distribution_factor_g,
        )
    )


def _simple_span_moment_at(
    span_m: float,
    x_m: float,
    uniform_q_tn_m: float,
    point_loads_tn: tuple[tuple[float, float], ...],
) -> float:
    reaction_left = uniform_q_tn_m * span_m / 2.0 + sum(
        load * (span_m - position) / span_m
        for position, load in point_loads_tn
        if -NODE_TOLERANCE <= position <= span_m + NODE_TOLERANCE
    )
    return _simple_span_moment_with_reaction(
        x_m,
        uniform_q_tn_m,
        point_loads_tn,
        reaction_left,
    )


def _simple_span_moment_with_reaction(
    x_m: float,
    uniform_q_tn_m: float,
    point_loads_tn: tuple[tuple[float, float], ...],
    reaction_left_tn: float,
) -> float:
    """Return moment using the already computed left support reaction."""
    moment = reaction_left_tn * x_m - uniform_q_tn_m * x_m**2.0 / 2.0
    for position, load in point_loads_tn:
        if x_m > position:
            moment -= load * (x_m - position)
    return max(moment, 0.0)


def _simple_span_reactions(
    span_m: float,
    uniform_q_tn_m: float,
    point_loads_tn: tuple[tuple[float, float], ...],
) -> tuple[float, float]:
    reaction_left = uniform_q_tn_m * span_m / 2.0 + sum(
        load * (span_m - position) / span_m
        for position, load in point_loads_tn
        if -NODE_TOLERANCE <= position <= span_m + NODE_TOLERANCE
    )
    total_load = uniform_q_tn_m * span_m + sum(
        load
        for position, load in point_loads_tn
        if -NODE_TOLERANCE <= position <= span_m + NODE_TOLERANCE
    )
    return reaction_left, total_load - reaction_left


def _simple_span_shear_at(
    span_m: float,
    x_m: float,
    uniform_q_tn_m: float,
    point_loads_tn: tuple[tuple[float, float], ...],
) -> float:
    reaction_left = _simple_span_reactions(span_m, uniform_q_tn_m, point_loads_tn)[0]
    return _simple_span_shear_with_reaction(
        x_m,
        uniform_q_tn_m,
        point_loads_tn,
        reaction_left,
    )


def _simple_span_shear_with_reaction(
    x_m: float,
    uniform_q_tn_m: float,
    point_loads_tn: tuple[tuple[float, float], ...],
    reaction_left_tn: float,
) -> float:
    """Return shear using the already computed left support reaction."""
    shear = reaction_left_tn - uniform_q_tn_m * x_m
    for position, load in point_loads_tn:
        if x_m > position:
            shear -= load
    return shear


def _sample_positions(geometry: InteriorGirderGeometry) -> tuple[float, ...]:
    return tuple(_moving_positions(0.0, geometry.span_length_m, geometry.moment_sample_step_m))


def _moving_positions(start: float, end: float, step: float) -> list[float]:
    positions: list[float] = []
    current = start
    while current <= end + NODE_TOLERANCE:
        positions.append(round(current, 10))
        current += step
    if not positions or abs(positions[-1] - end) > NODE_TOLERANCE:
        positions.append(end)
    return positions


def _moving_vehicle_bases(
    span_m: float,
    vehicle_length_m: float,
    step_m: float,
) -> tuple[float, ...]:
    positions = _moving_positions(-vehicle_length_m, span_m, step_m)
    mirrored = [round(span_m - base - vehicle_length_m, 10) for base in positions]
    return tuple(sorted(set(positions + mirrored)))


def _symmetrized_envelope_samples(
    samples: tuple[tuple[float, float], ...],
    span_m: float,
    target: str = "max",
) -> tuple[tuple[float, float], ...]:
    by_position = {round(position, 10): value for position, value in samples}
    result = []
    for position, value in samples:
        mirrored_position = round(span_m - position, 10)
        mirrored_value = by_position.get(mirrored_position)
        if mirrored_value is None:
            selected = value
        elif target == "max":
            selected = max(value, mirrored_value)
        else:
            selected = min(value, mirrored_value)
        result.append((position, 0.0 if abs(selected) <= NODE_TOLERANCE else selected))
    return tuple(result)


def _symmetrized_signed_shear_envelopes(
    upper_samples: tuple[tuple[float, float], ...],
    lower_samples: tuple[tuple[float, float], ...],
    span_m: float,
) -> tuple[tuple[tuple[float, float], ...], tuple[tuple[float, float], ...]]:
    """Enforce Vmax(x)=-Vmin(L-x) for the symmetric simple span."""
    upper_by_position = {round(position, 10): value for position, value in upper_samples}
    lower_by_position = {round(position, 10): value for position, value in lower_samples}
    upper_result = []
    lower_result = []
    for position, upper in upper_samples:
        mirror = round(span_m - position, 10)
        mirrored_lower = lower_by_position.get(mirror)
        selected = max(upper, -mirrored_lower) if mirrored_lower is not None else upper
        upper_result.append((position, 0.0 if abs(selected) <= NODE_TOLERANCE else selected))
    for position, lower in lower_samples:
        mirror = round(span_m - position, 10)
        mirrored_upper = upper_by_position.get(mirror)
        selected = min(lower, -mirrored_upper) if mirrored_upper is not None else lower
        lower_result.append((position, 0.0 if abs(selected) <= NODE_TOLERANCE else selected))
    return tuple(upper_result), tuple(lower_result)


def _truck_spacing_sets(vehicle: VehicleLoadModel) -> tuple[tuple[float, ...], ...]:
    first_spacing = vehicle.design_truck_spacings_m[0]
    rear_min, rear_max = vehicle.design_truck_spacings_m[1]
    if abs(rear_max - rear_min) <= NODE_TOLERANCE:
        return ((first_spacing, rear_min),)
    return tuple((first_spacing, rear_spacing) for rear_spacing in _moving_positions(rear_min, rear_max, 0.50))


def _axle_offsets(spacings_m: tuple[float, ...]) -> tuple[float, ...]:
    offsets = [0.0]
    current = 0.0
    for spacing in spacings_m:
        current += spacing
        offsets.append(current)
    return tuple(offsets)


def _oriented_axle_layouts(
    spacing_set: tuple[float, ...],
    axles_tn: tuple[float, ...],
) -> tuple[tuple[str, tuple[float, ...], tuple[float, ...]], ...]:
    axle_offsets = _axle_offsets(spacing_set)
    vehicle_length = axle_offsets[-1]
    direct = ("sentido directo", axle_offsets, axles_tn)
    reversed_pairs = tuple(
        sorted(
            (
                (round(vehicle_length - offset, 10), load)
                for offset, load in zip(axle_offsets, axles_tn)
            ),
            key=lambda item: item[0],
        )
    )
    reversed_offsets = tuple(offset for offset, _ in reversed_pairs)
    reversed_loads = tuple(load for _, load in reversed_pairs)
    if reversed_offsets == axle_offsets and reversed_loads == axles_tn:
        return (direct,)
    return (
        direct,
        ("sentido inverso", reversed_offsets, reversed_loads),
    )


def _configuration_label(name: str, spacing_set: tuple[float, ...], direction: str) -> str:
    if len(spacing_set) == 2:
        return (
            f"{name}; {direction}; separacion ejes = "
            f"{spacing_set[0]:.3f} m y {spacing_set[1]:.3f} m"
        )
    spacings = ", ".join(f"{value:.3f} m" for value in spacing_set)
    return f"{name}; {direction}; separacion ejes = {spacings}"


def _combined_positions(*cases: LongitudinalLoadCaseAnalysis) -> tuple[float, ...]:
    values: set[float] = set()
    for case in cases:
        values.update(position for position, _ in case.moment_samples_tn_m)
    return tuple(sorted(values))


def _moment_at(samples: tuple[tuple[float, float], ...], position: float) -> float:
    return _sample_at(samples, position)


def _sample_at(samples: tuple[tuple[float, float], ...], position: float) -> float:
    return interpolate_sorted_samples(samples, position, tolerance=NODE_TOLERANCE)


def _effective_depth_cm_for_girder(
    geometry: InteriorGirderGeometry,
    parameters: InteriorGirderReinforcementParameters,
) -> float:
    depth = (
        geometry.total_t_section_depth_m * 100.0
        - parameters.concrete_cover_cm
        - parameters.main_bar_diameter_cm / 2.0
    )
    require_positive(depth, "peralte efectivo de viga")
    return depth


def _effective_shear_depth_cm(
    geometry: InteriorGirderGeometry,
    effective_depth_cm: float,
) -> float:
    return max(0.9 * effective_depth_cm, 0.72 * geometry.total_t_section_depth_m * 100.0)


def _steel_depth_cm(
    geometry: InteriorGirderGeometry,
    selected: LongitudinalBarPlacementOption,
    parameters: InteriorGirderReinforcementParameters,
) -> float:
    return selected.effective_depth_cm or (
        geometry.total_t_section_depth_m * 100.0
        - parameters.concrete_cover_cm - selected.bar_diameter_cm / 2.0
    )


def _placement_effective_depth_cm(
    geometry: InteriorGirderGeometry,
    parameters: InteriorGirderReinforcementParameters,
    diameter_cm: float,
    bar_count: int,
    bars_per_layer: int,
    clear_spacing_cm: float,
) -> tuple[float, float]:
    """Return the actual tension-steel centroid and d for a multilayer layout."""
    layers = ceil(bar_count / bars_per_layer)
    vertical_clear = max(parameters.minimum_clear_bar_spacing_cm, clear_spacing_cm)
    first = parameters.concrete_cover_cm + diameter_cm / 2.0
    last_layer = min(layers, 1 + (bar_count - 1) // bars_per_layer)
    centroid = first + (last_layer - 1) * (diameter_cm + vertical_clear) / 2.0
    depth = geometry.total_t_section_depth_m * 100.0 - centroid
    require_positive(depth, "peralte efectivo multicapa")
    return centroid, depth


def _iterated_main_placement_options(
    label: str,
    required_area_cm2: float,
    geometry: InteriorGirderGeometry,
    parameters: InteriorGirderReinforcementParameters,
    moment_tn_m: float,
    flange_width_cm: float,
    flange_thickness_cm: float,
    web_width_cm: float,
    materials: MaterialProperties,
) -> LongitudinalPlacementCaseOptions:
    """Select detail and repeat flexural demand with its actual centroid."""
    options = generate_main_bar_placement_options(label, required_area_cm2, geometry, parameters)
    for _ in range(3):
        selected = options.recommended
        if selected is None:
            break
        d = selected.effective_depth_cm
        strength, _ = t_beam_flexural_steel_area_cm2(
            moment_tn_m, flange_width_cm, flange_thickness_cm, web_width_cm, d,
            materials.concrete.compressive_strength_kg_cm2,
            materials.steel.yield_strength_kg_cm2, parameters.flexural_resistance_factor,
            materials.steel.elastic_modulus_kg_cm2,
        )
        minimum = _minimum_flexural_area_cm2(
            materials.concrete.compressive_strength_kg_cm2,
            materials.steel.yield_strength_kg_cm2, web_width_cm, d,
        )
        updated = max(strength, minimum)
        if updated <= required_area_cm2 + 1e-9:
            break
        required_area_cm2 = updated
        options = generate_main_bar_placement_options(label, required_area_cm2, geometry, parameters)
    return options


def _gross_t_section_properties(
    geometry: InteriorGirderGeometry,
) -> tuple[float, float]:
    flange_width = geometry.tributary_width_m * 100.0
    flange_thickness = geometry.slab_thickness_m * 100.0
    web_width = geometry.web_width_m * 100.0
    web_height = geometry.girder_total_height_m * 100.0
    flange_area = flange_width * flange_thickness
    web_area = web_width * web_height
    flange_centroid = flange_thickness / 2.0
    web_centroid = flange_thickness + web_height / 2.0
    centroid = (
        flange_area * flange_centroid + web_area * web_centroid
    ) / (flange_area + web_area)
    inertia = (
        flange_width * flange_thickness**3.0 / 12.0
        + flange_area * (centroid - flange_centroid) ** 2.0
        + web_width * web_height**3.0 / 12.0
        + web_area * (web_centroid - centroid) ** 2.0
    )
    return centroid, inertia


def _uncracked_transformed_properties(
    geometry: InteriorGirderGeometry,
    modular_ratio: int,
    steel_area_cm2: float,
    steel_depth_cm: float,
) -> tuple[float, float]:
    gross_centroid, _ = _gross_t_section_properties(geometry)
    flange_width = geometry.tributary_width_m * 100.0
    flange_thickness = geometry.slab_thickness_m * 100.0
    web_width = geometry.web_width_m * 100.0
    web_height = geometry.girder_total_height_m * 100.0
    flange_area = flange_width * flange_thickness
    web_area = web_width * web_height
    transformed_steel = (modular_ratio - 1.0) * steel_area_cm2
    centroid = (
        flange_area * (flange_thickness / 2.0)
        + web_area * (flange_thickness + web_height / 2.0)
        + transformed_steel * steel_depth_cm
    ) / (flange_area + web_area + transformed_steel)
    inertia = (
        flange_width * flange_thickness**3.0 / 12.0
        + flange_area * (centroid - flange_thickness / 2.0) ** 2.0
        + web_width * web_height**3.0 / 12.0
        + web_area * (flange_thickness + web_height / 2.0 - centroid) ** 2.0
        + transformed_steel * (steel_depth_cm - centroid) ** 2.0
    )
    if inertia <= 0.0:
        return gross_centroid, _gross_t_section_properties(geometry)[1]
    return centroid, inertia


def _cracked_neutral_axis_cm(
    flange_width_cm: float,
    flange_thickness_cm: float,
    web_width_cm: float,
    steel_area_cm2: float,
    modular_ratio: int,
    steel_depth_cm: float,
) -> float:
    lower = 1e-9
    upper = steel_depth_cm - 1e-9
    for _ in range(100):
        mid = (lower + upper) / 2.0
        concrete_area, concrete_centroid = _compression_concrete_area_centroid(
            mid,
            flange_width_cm,
            flange_thickness_cm,
            web_width_cm,
        )
        equilibrium = concrete_area * (mid - concrete_centroid) - modular_ratio * steel_area_cm2 * (steel_depth_cm - mid)
        if equilibrium < 0.0:
            lower = mid
        else:
            upper = mid
    return (lower + upper) / 2.0


def _cracked_inertia_cm4(
    flange_width_cm: float,
    flange_thickness_cm: float,
    web_width_cm: float,
    steel_area_cm2: float,
    modular_ratio: int,
    steel_depth_cm: float,
    neutral_axis_cm: float,
) -> float:
    inertia = 0.0
    if neutral_axis_cm <= flange_thickness_cm:
        inertia += flange_width_cm * neutral_axis_cm**3.0 / 3.0
    else:
        inertia += (
            flange_width_cm * flange_thickness_cm**3.0 / 12.0
            + flange_width_cm
            * flange_thickness_cm
            * (neutral_axis_cm - flange_thickness_cm / 2.0) ** 2.0
        )
        web_depth = neutral_axis_cm - flange_thickness_cm
        inertia += web_width_cm * web_depth**3.0 / 3.0
    inertia += modular_ratio * steel_area_cm2 * (steel_depth_cm - neutral_axis_cm) ** 2.0
    return inertia


def _compression_concrete_area_centroid(
    neutral_axis_cm: float,
    flange_width_cm: float,
    flange_thickness_cm: float,
    web_width_cm: float,
) -> tuple[float, float]:
    if neutral_axis_cm <= flange_thickness_cm:
        return flange_width_cm * neutral_axis_cm, neutral_axis_cm / 2.0
    flange_area = flange_width_cm * flange_thickness_cm
    web_depth = neutral_axis_cm - flange_thickness_cm
    web_area = web_width_cm * web_depth
    centroid = (
        flange_area * flange_thickness_cm / 2.0
        + web_area * (flange_thickness_cm + web_depth / 2.0)
    ) / (flange_area + web_area)
    return flange_area + web_area, centroid


def _fatigue_cracking_threshold_kg_cm2(concrete_strength_kg_cm2: float) -> float:
    return ksi_to_kg_cm2(0.095 * kg_cm2_to_ksi(concrete_strength_kg_cm2) ** 0.5)


def _steel_stress_from_moment_kg_cm2(
    moment_tn_m: float,
    section: CrackedSectionProperties,
    steel_depth_cm: float,
) -> float:
    if moment_tn_m <= 0.0:
        return 1e-9
    return (
        section.modular_ratio
        * moment_tn_m
        * 100000.0
        * max(steel_depth_cm - section.neutral_axis_depth_cm, 0.0)
        / section.inertia_cm4
    )


def _concrete_top_stress_kg_cm2(
    moment_tn_m: float,
    section: CrackedSectionProperties,
) -> float:
    if moment_tn_m <= 0.0:
        return 0.0
    return moment_tn_m * 100000.0 * section.neutral_axis_depth_cm / section.inertia_cm4


def _concrete_shear_resistance_tn(
    concrete_strength_kg_cm2: float,
    web_width_cm: float,
    effective_shear_depth_cm: float,
    beta: float,
) -> float:
    fc_ksi = kg_cm2_to_ksi(concrete_strength_kg_cm2)
    bv_in = web_width_cm / 2.54
    dv_in = effective_shear_depth_cm / 2.54
    vc_kip = 0.0316 * beta * fc_ksi**0.5 * bv_in * dv_in
    return kip_to_tn(vc_kip)


def _nominal_shear_upper_limit_tn(
    concrete_strength_kg_cm2: float,
    web_width_cm: float,
    effective_shear_depth_cm: float,
) -> float:
    fc_ksi = kg_cm2_to_ksi(concrete_strength_kg_cm2)
    bv_in = web_width_cm / 2.54
    dv_in = effective_shear_depth_cm / 2.54
    return kip_to_tn(0.25 * fc_ksi * bv_in * dv_in)


def _minimum_shear_reinforcement_cm2_m(
    concrete_strength_kg_cm2: float,
    steel_yield_kg_cm2: float,
    web_width_cm: float,
) -> float:
    fc_ksi = kg_cm2_to_ksi(concrete_strength_kg_cm2)
    fy_ksi = min(100.0, kg_cm2_to_ksi(steel_yield_kg_cm2))
    bv_in = web_width_cm / 2.54
    av_over_s_in2_in = 0.0316 * fc_ksi**0.5 * bv_in / fy_ksi
    return av_over_s_in2_in * 254.0


def _required_shear_reinforcement_cm2_m(
    required_vs_tn: float,
    steel_yield_kg_cm2: float,
    effective_shear_depth_cm: float,
) -> float:
    if required_vs_tn <= 0.0:
        return 0.0
    fy_tn_cm2 = steel_yield_kg_cm2 / 1000.0
    av_over_s_cm2_cm = required_vs_tn / (fy_tn_cm2 * effective_shear_depth_cm)
    return av_over_s_cm2_cm * 100.0


def _maximum_shear_spacing_m(
    vu_tn: float,
    phi: float,
    concrete_strength_kg_cm2: float,
    web_width_cm: float,
    effective_shear_depth_cm: float,
) -> float:
    vu_kip = vu_tn / kip_to_tn(1.0)
    bv_in = web_width_cm / 2.54
    dv_in = effective_shear_depth_cm / 2.54
    vu_stress_ksi = vu_kip / (phi * bv_in * dv_in)
    fc_ksi = kg_cm2_to_ksi(concrete_strength_kg_cm2)
    if vu_stress_ksi < 0.125 * fc_ksi:
        return min(0.8 * effective_shear_depth_cm / 100.0, 0.60)
    return min(0.4 * effective_shear_depth_cm / 100.0, 0.30)


def _generate_shear_stirrup_options(
    required_av_cm2_m: float,
    max_spacing_m: float,
    legs: int,
    vu_tn: float,
    vc_tn: float,
    nominal_limit_tn: float,
    materials: MaterialProperties,
    effective_shear_depth_cm: float,
    phi: float,
) -> tuple[ShearStirrupOption, ...]:
    options = []
    for item, bar in enumerate(REINFORCING_BAR_CATALOG, start=1):
        if required_av_cm2_m <= 0.0:
            spacing = max_spacing_m
        else:
            spacing = _round_spacing_down(
                min(legs * bar.area_cm2 / required_av_cm2_m, max_spacing_m),
                DEFAULT_SPACING_STEP_M,
            )
        spacing = max(spacing, DEFAULT_SPACING_STEP_M)
        provided = legs * bar.area_cm2 / spacing
        vs = (
            provided
            / 100.0
            * (materials.steel.yield_strength_kg_cm2 / 1000.0)
            * effective_shear_depth_cm
        )
        phi_vn = phi * min(vc_tn + vs, nominal_limit_tn)
        options.append(
            ShearStirrupOption(
                item=item,
                bar_label=bar.label,
                bar_area_cm2=bar.area_cm2,
                legs=legs,
                spacing_m=spacing,
                required_av_cm2_m=required_av_cm2_m,
                provided_av_cm2_m=provided,
                phi_vn_tn=phi_vn,
                is_compliant=(
                    provided + 1e-9 >= required_av_cm2_m
                    and spacing <= max_spacing_m + 1e-9
                    and phi_vn + 1e-9 >= vu_tn
                ),
            )
        )
    recommended = _recommended_shear_option(options)
    if recommended is None:
        return tuple(options)
    return tuple(
        ShearStirrupOption(
            item=option.item,
            bar_label=option.bar_label,
            bar_area_cm2=option.bar_area_cm2,
            legs=option.legs,
            spacing_m=option.spacing_m,
            required_av_cm2_m=option.required_av_cm2_m,
            provided_av_cm2_m=option.provided_av_cm2_m,
            phi_vn_tn=option.phi_vn_tn,
            is_compliant=option.is_compliant,
            is_recommended=option.item == recommended.item,
        )
        for option in options
    )


def _recommended_shear_option(
    options: list[ShearStirrupOption],
) -> ShearStirrupOption | None:
    compliant = [option for option in options if option.is_compliant]
    if not compliant:
        return None
    return min(
        compliant,
        key=lambda option: (
            option.provided_av_cm2_m - option.required_av_cm2_m,
            -option.spacing_m,
        ),
    )


def _round_spacing_down(value_m: float, step_m: float) -> float:
    return round(floor(value_m / step_m + 1e-9) * step_m, 3)


def _minimum_flexural_area_cm2(
    concrete_strength_kg_cm2: float,
    steel_yield_kg_cm2: float,
    web_width_cm: float,
    effective_depth_cm: float,
) -> float:
    ratio = max(
        0.8 * concrete_strength_kg_cm2**0.5 / steel_yield_kg_cm2,
        14.0 / steel_yield_kg_cm2,
    )
    return ratio * web_width_cm * effective_depth_cm


def _spacing_grid(parameters: InteriorGirderReinforcementParameters) -> SpacingGrid:
    return SpacingGrid(
        step_m=parameters.spacing_step_m,
        minimum_m=parameters.minimum_spacing_m,
        maximum_m=parameters.maximum_spacing_m,
    )


def _skin_reinforcement_requirements(
    extreme_tension_depth_cm: float,
    required_flexural_area_cm2: float,
    configured_maximum_spacing_m: float = 0.30,
) -> tuple[float, float, float, float, float, float]:
    """Return MTC 2.9.1.4.4.3 skin steel and spacing requirements per face."""
    require_positive(extreme_tension_depth_cm, "dl")
    require_non_negative(required_flexural_area_cm2, "As flexion requerido")
    require_positive(configured_maximum_spacing_m, "espaciamiento maximo Ask")
    maximum_total = required_flexural_area_cm2 / 4.0
    if extreme_tension_depth_cm <= 90.0:
        return (
            0.0,
            0.0,
            0.0,
            0.0,
            maximum_total,
            min(configured_maximum_spacing_m, 0.30),
        )

    distribution_height_m = extreme_tension_depth_cm / 200.0
    uncapped_rate = 0.1 * (extreme_tension_depth_cm - 76.2)
    uncapped_total = uncapped_rate * distribution_height_m
    required_total = min(uncapped_total, maximum_total)
    required_rate = required_total / distribution_height_m
    maximum_spacing = min(
        configured_maximum_spacing_m,
        0.30,
        extreme_tension_depth_cm / 600.0,
    )
    return (
        required_rate,
        uncapped_rate,
        distribution_height_m,
        required_total,
        maximum_total,
        maximum_spacing,
    )


def _max_bars_per_layer(
    geometry: InteriorGirderGeometry,
    parameters: InteriorGirderReinforcementParameters,
    diameter_cm: float,
) -> int:
    available_width_cm = geometry.web_width_m * 100.0 - 2.0 * parameters.concrete_cover_cm
    pitch_cm = diameter_cm + parameters.minimum_clear_bar_spacing_cm
    return max(2, floor((available_width_cm + parameters.minimum_clear_bar_spacing_cm) / pitch_cm))


def _clear_spacing_cm(
    geometry: InteriorGirderGeometry,
    parameters: InteriorGirderReinforcementParameters,
    diameter_cm: float,
    bars_in_layer: int,
) -> float:
    if bars_in_layer <= 1:
        return geometry.web_width_m * 100.0 - 2.0 * parameters.concrete_cover_cm - diameter_cm
    available_width_cm = geometry.web_width_m * 100.0 - 2.0 * parameters.concrete_cover_cm
    return (available_width_cm - bars_in_layer * diameter_cm) / (bars_in_layer - 1)


def _recommended_placement(
    options: list[LongitudinalBarPlacementOption],
) -> LongitudinalBarPlacementOption | None:
    compliant = [option for option in options if option.is_compliant]
    if not compliant:
        return None
    return min(
        compliant,
        key=lambda option: (
            option.layers,
            option.provided_area_cm2 - option.required_area_cm2,
            option.bar_diameter_cm,
        ),
    )


def _recommended_main_option(
    steel: MainGirderSteelDesign,
) -> LongitudinalBarPlacementOption:
    recommended = steel.placement_options.recommended
    if recommended is None:
        raise ValueError("No hay opcion recomendada para el acero principal de viga.")
    return recommended


def _service_steel_stress_kg_cm2(
    service_moment_tn_m: float,
    provided_area_cm2: float,
    effective_depth_cm: float,
) -> float:
    require_positive(provided_area_cm2, "As provisto")
    require_positive(effective_depth_cm, "d")
    if service_moment_tn_m <= 0.0:
        return 1e-9
    moment_kg_cm = service_moment_tn_m * 100000.0
    lever_arm_cm = DEFAULT_SERVICE_STRESS_LEVER_ARM_FACTOR * effective_depth_cm
    return moment_kg_cm / (provided_area_cm2 * lever_arm_cm)
