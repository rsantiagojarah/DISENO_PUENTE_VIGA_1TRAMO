"""Exterior longitudinal girder analysis and strength design."""

from dataclasses import dataclass, replace
from functools import lru_cache

from bridge_design.codes.mtc_2018 import (
    DEFAULT_FLEXURAL_RESISTANCE_FACTOR,
    DEFAULT_SHRINKAGE_TEMPERATURE_RATIO,
    mtc_dynamic_load_allowance_for_slab,
    mtc_exterior_concrete_t_girder_fatigue_live_load_moment_distribution_factor,
    mtc_exterior_concrete_t_girder_fatigue_live_load_shear_distribution_factor,
    mtc_exterior_concrete_t_girder_live_load_moment_distribution_factor,
    mtc_exterior_concrete_t_girder_live_load_shear_distribution_factor,
)
from bridge_design.domain.interior_girder import (
    DEFAULT_CRACK_CONTROL_EXPOSURE_FACTOR,
    DEFAULT_SHEAR_BETA,
    DEFAULT_SHEAR_RESISTANCE_FACTOR,
    DEFAULT_SHEAR_THETA_DEGREES,
    DiaphragmGeometry,
    FATIGUE_I_LOAD_FACTOR,
    InteriorGirderCombinedShear,
    InteriorGirderCrackControlReview,
    InteriorGirderFatigueReview,
    InteriorGirderReinforcementDesign,
    InteriorGirderReinforcementParameters,
    InteriorGirderShearDesign,
    InteriorGirderStressVerification,
    LongitudinalBarPlacementOption,
    LongitudinalLoadCaseAnalysis,
    MainGirderSteelDesign,
    ShearStirrupOption,
    SkinLongitudinalSteelDesign,
    WebTemperatureSteelDesign,
    _combine_live_load_cases,
    _combined_positions,
    _concrete_top_stress_kg_cm2,
    _concrete_shear_resistance_tn,
    _effective_depth_cm_for_girder,
    _effective_shear_depth_cm,
    _gross_t_section_properties,
    _generate_shear_stirrup_options,
    _minimum_flexural_area_cm2,
    _minimum_shear_reinforcement_cm2_m,
    _moment_at,
    _maximum_shear_spacing_m,
    _nominal_shear_upper_limit_tn,
    _required_shear_reinforcement_cm2_m,
    _sample_at,
    _recommended_main_option,
    _solve_moving_vehicle_case,
    _solve_static_longitudinal_case,
    _spacing_grid,
    _service_steel_stress_kg_cm2,
    _skin_reinforcement_requirements,
    _steel_depth_cm,
    _steel_stress_from_moment_kg_cm2,
    _truck_spacing_sets,
    cracked_section_properties,
    fatigue_reinforcing_bar_stress_range_limit_kg_cm2,
    generate_main_bar_placement_options,
    t_beam_flexural_steel_area_cm2,
)
from bridge_design.domain.crack_control import (
    CrackControlCheck,
    crack_control_compliance_statuses,
    maximum_crack_control_spacing_m,
)
from bridge_design.domain.load_combinations import LoadFactor
from bridge_design.domain.loads import LiveLoads, VehicleLoadModel
from bridge_design.domain.materials import MaterialProperties
from bridge_design.domain.rebar_catalog import SpacingGrid, generate_spacing_options
from bridge_design.domain.reinforcement import (
    mtc_cracking_moment_tn_m,
    mtc_minimum_flexural_moment_tn_m,
)
from bridge_design.validation.input_validators import require_non_negative, require_positive


@dataclass(frozen=True)
class ExteriorGirderGeometry:
    """Geometry and tributary load widths for one exterior T girder."""

    span_length_m: float
    girder_spacing_m: float
    deck_overhang_m: float
    slab_thickness_m: float
    girder_total_height_m: float
    web_width_m: float
    exterior_web_to_traffic_barrier_m: float
    sidewalk_width_m: float
    asphalt_tributary_width_m: float
    girder_count: int = 4
    diaphragms: tuple[DiaphragmGeometry, ...] = ()
    moving_load_step_m: float = 0.10
    moment_sample_step_m: float = 0.10
    live_load_distribution_factor_g: float | None = None
    live_load_shear_distribution_factor_g: float | None = None

    def __post_init__(self) -> None:
        require_positive(self.span_length_m, "luz del puente")
        require_positive(self.girder_spacing_m, "separacion entre vigas")
        require_non_negative(self.deck_overhang_m, "volado de losa")
        require_positive(self.slab_thickness_m, "espesor de losa")
        require_positive(self.girder_total_height_m, "altura de viga")
        require_positive(self.web_width_m, "ancho de alma")
        require_non_negative(self.sidewalk_width_m, "ancho de vereda")
        require_non_negative(self.asphalt_tributary_width_m, "ancho tributario de asfalto")
        require_positive(self.moving_load_step_m, "paso de carga movil")
        require_positive(self.moment_sample_step_m, "paso de muestreo de momento")
        if self.girder_count < 1:
            raise ValueError("El numero de vigas debe ser al menos 1.")
        if self.live_load_distribution_factor_g is not None:
            require_positive(self.live_load_distribution_factor_g, "g momento exterior")
        if self.live_load_shear_distribution_factor_g is not None:
            require_positive(self.live_load_shear_distribution_factor_g, "g corte exterior")
        for diaphragm in self.diaphragms:
            if diaphragm.position_m > self.span_length_m:
                raise ValueError("La ubicacion de diafragma debe estar dentro de la luz.")

    @property
    def tributary_width_m(self) -> float:
        """Return slab tributary width of the exterior girder."""
        return self.deck_overhang_m + self.girder_spacing_m / 2.0

    @property
    def sidewalk_tributary_width_m(self) -> float:
        """Return sidewalk width assigned to the exterior girder."""
        return min(self.sidewalk_width_m, self.tributary_width_m)

    @property
    def total_t_section_depth_m(self) -> float:
        """Return slab plus girder depth for flexural T-section design."""
        return self.slab_thickness_m + self.girder_total_height_m

    def with_distribution_factors(
        self,
        vehicle: VehicleLoadModel,
    ) -> "ExteriorGirderGeometry":
        """Return a copy with MTC/AASHTO exterior live-load g factors."""
        return replace(
            self,
            live_load_distribution_factor_g=mtc_exterior_concrete_t_girder_live_load_moment_distribution_factor(
                span_length_m=self.span_length_m,
                girder_spacing_m=self.girder_spacing_m,
                slab_thickness_m=self.slab_thickness_m,
                girder_total_height_m=self.girder_total_height_m,
                web_width_m=self.web_width_m,
                girder_count=self.girder_count,
                exterior_web_to_traffic_barrier_m=self.exterior_web_to_traffic_barrier_m,
                wheel_transverse_spacing_m=vehicle.wheel_transverse_spacing_m,
                design_lane_width_m=vehicle.design_lane_width_m,
            ),
            live_load_shear_distribution_factor_g=mtc_exterior_concrete_t_girder_live_load_shear_distribution_factor(
                span_length_m=self.span_length_m,
                girder_spacing_m=self.girder_spacing_m,
                slab_thickness_m=self.slab_thickness_m,
                girder_count=self.girder_count,
                exterior_web_to_traffic_barrier_m=self.exterior_web_to_traffic_barrier_m,
                wheel_transverse_spacing_m=vehicle.wheel_transverse_spacing_m,
                design_lane_width_m=vehicle.design_lane_width_m,
            ),
        )


@dataclass(frozen=True)
class ExteriorGirderAnalysisResult:
    """Grouped DC, DW, PL and LL+IM analysis for an exterior girder."""

    dc: LongitudinalLoadCaseAnalysis
    dw: LongitudinalLoadCaseAnalysis
    pl: LongitudinalLoadCaseAnalysis
    truck_ll_im: LongitudinalLoadCaseAnalysis
    tandem_ll_im: LongitudinalLoadCaseAnalysis
    ll_im_envelope: LongitudinalLoadCaseAnalysis
    fatigue_truck: LongitudinalLoadCaseAnalysis
    dynamic_load_allowance: float
    distribution_factor_g: float
    shear_distribution_factor_g: float


@dataclass(frozen=True)
class ExteriorGirderCombinedMoment:
    """One factored moment row for the exterior girder."""

    combination_name: str
    limit_state: str
    position_m: float
    dc_moment_tn_m: float
    dc_factor: float
    dw_moment_tn_m: float
    dw_factor: float
    pl_moment_tn_m: float
    pl_factor: float
    ll_im_moment_tn_m: float
    ll_im_factor: float
    combined_moment_tn_m: float


@dataclass(frozen=True)
class ExteriorGirderCombinedShear:
    """Factored shear at a critical exterior girder section."""

    combination_name: str
    limit_state: str
    position_m: float
    dc_shear_tn: float
    dc_factor: float
    dw_shear_tn: float
    dw_factor: float
    pl_shear_tn: float
    pl_factor: float
    ll_im_shear_tn: float
    ll_im_factor: float
    combined_shear_tn: float


def solve_exterior_girder_design(
    geometry: ExteriorGirderGeometry,
    materials: MaterialProperties,
    live_loads: LiveLoads,
) -> ExteriorGirderAnalysisResult:
    """Solve longitudinal DC, DW, PL and moving HL-93 load envelopes."""
    analysis_geometry = geometry.with_distribution_factors(live_loads.vehicular)
    dc = _solve_static_longitudinal_case(
        geometry=analysis_geometry,
        name="DC - losa, viga, vereda, baranda, barrera y diafragmas",
        uniform_loads_tn_m=_dc_uniform_loads_tn_m(analysis_geometry, materials),
        point_loads_tn=_dc_point_loads_tn(analysis_geometry, materials),
    )
    dw = _solve_static_longitudinal_case(
        geometry=analysis_geometry,
        name="DW - superficie de rodadura tributaria",
        uniform_loads_tn_m=(
            materials.asphalt.specific_weight_tn_m3
            * materials.asphalt.thickness_m
            * analysis_geometry.asphalt_tributary_width_m,
        ),
        point_loads_tn=(),
    )
    pl = _solve_static_longitudinal_case(
        geometry=analysis_geometry,
        name="PL - carga peatonal en vereda exterior",
        uniform_loads_tn_m=(
            live_loads.pedestrian.load_tn_m2
            * analysis_geometry.sidewalk_tributary_width_m,
        ),
        point_loads_tn=(),
    )
    truck = _solve_moving_vehicle_case(
        geometry=analysis_geometry,
        vehicle=live_loads.vehicular,
        axles_tn=live_loads.vehicular.design_truck_axles_tn,
        spacing_sets_m=_truck_spacing_sets(live_loads.vehicular),
        name="LL+IM - camion de diseno",
        lane_load_tn_m=live_loads.vehicular.lane_load_tn_m,
        impact_factor=mtc_dynamic_load_allowance_for_slab(),
    )
    tandem = _solve_moving_vehicle_case(
        geometry=analysis_geometry,
        vehicle=live_loads.vehicular,
        axles_tn=live_loads.vehicular.design_tandem_axles_tn,
        spacing_sets_m=((live_loads.vehicular.design_tandem_spacing_m,),),
        name="LL+IM - tandem de diseno",
        lane_load_tn_m=live_loads.vehicular.lane_load_tn_m,
        impact_factor=mtc_dynamic_load_allowance_for_slab(),
    )
    fatigue = _solve_moving_vehicle_case(
        geometry=analysis_geometry,
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
        impact_factor=0.15,
        moment_distribution_factor_g=mtc_exterior_concrete_t_girder_fatigue_live_load_moment_distribution_factor(
            girder_spacing_m=analysis_geometry.girder_spacing_m,
            girder_count=analysis_geometry.girder_count,
            exterior_web_to_traffic_barrier_m=analysis_geometry.exterior_web_to_traffic_barrier_m,
            wheel_transverse_spacing_m=live_loads.vehicular.wheel_transverse_spacing_m,
            design_lane_width_m=live_loads.vehicular.design_lane_width_m,
        ),
        shear_distribution_factor_g=mtc_exterior_concrete_t_girder_fatigue_live_load_shear_distribution_factor(
            girder_spacing_m=analysis_geometry.girder_spacing_m,
            girder_count=analysis_geometry.girder_count,
            exterior_web_to_traffic_barrier_m=analysis_geometry.exterior_web_to_traffic_barrier_m,
            wheel_transverse_spacing_m=live_loads.vehicular.wheel_transverse_spacing_m,
            design_lane_width_m=live_loads.vehicular.design_lane_width_m,
        ),
    )
    envelope = _combine_live_load_cases(analysis_geometry, truck, tandem)
    return ExteriorGirderAnalysisResult(
        dc=dc,
        dw=dw,
        pl=pl,
        truck_ll_im=truck,
        tandem_ll_im=tandem,
        ll_im_envelope=envelope,
        fatigue_truck=fatigue,
        dynamic_load_allowance=mtc_dynamic_load_allowance_for_slab(),
        distribution_factor_g=float(analysis_geometry.live_load_distribution_factor_g),
        shear_distribution_factor_g=float(analysis_geometry.live_load_shear_distribution_factor_g),
    )


@lru_cache(maxsize=8)
def combine_exterior_girder_moments(
    result: ExteriorGirderAnalysisResult,
) -> tuple[ExteriorGirderCombinedMoment, ...]:
    """Return exterior girder factored moment rows for standard combinations."""
    combinations = (
        ("RESISTENCIA I", "Resistencia", LoadFactor(1.25, 0.90), LoadFactor(1.50, 0.65), LoadFactor(1.75, omit_when_favorable=True), LoadFactor(1.75, omit_when_favorable=True)),
        ("SERVICIO I", "Servicio", LoadFactor(1.00), LoadFactor(1.00), LoadFactor(1.00, omit_when_favorable=True), LoadFactor(1.00, omit_when_favorable=True)),
        ("SERVICIO III", "Servicio", LoadFactor(1.00), LoadFactor(1.00), LoadFactor(0.80, omit_when_favorable=True), LoadFactor(0.80, omit_when_favorable=True)),
    )
    positions = _combined_positions(result.dc, result.dw, result.pl, result.ll_im_envelope)
    rows: list[ExteriorGirderCombinedMoment] = []
    for name, limit_state, dc_factor, dw_factor, pl_factor, ll_factor in combinations:
        candidates = []
        for position in positions:
            dc = _moment_at(result.dc.moment_samples_tn_m, position)
            dw = _moment_at(result.dw.moment_samples_tn_m, position)
            pl = _moment_at(result.pl.moment_samples_tn_m, position)
            ll = _moment_at(result.ll_im_envelope.moment_samples_tn_m, position)
            g_dc = dc_factor.for_effect(dc, "max")
            g_dw = dw_factor.for_effect(dw, "max")
            g_pl = pl_factor.for_effect(pl, "max")
            g_ll = ll_factor.for_effect(ll, "max")
            combined = g_dc * dc + g_dw * dw + g_pl * pl + g_ll * ll
            candidates.append(
                ExteriorGirderCombinedMoment(
                    combination_name=name,
                    limit_state=limit_state,
                    position_m=position,
                    dc_moment_tn_m=dc,
                    dc_factor=g_dc,
                    dw_moment_tn_m=dw,
                    dw_factor=g_dw,
                    pl_moment_tn_m=pl,
                    pl_factor=g_pl,
                    ll_im_moment_tn_m=ll,
                    ll_im_factor=g_ll,
                    combined_moment_tn_m=combined,
                )
            )
        rows.append(max(candidates, key=lambda item: item.combined_moment_tn_m))
    return tuple(rows)


@lru_cache(maxsize=8)
def combine_exterior_girder_shears(
    geometry: ExteriorGirderGeometry,
    result: ExteriorGirderAnalysisResult,
    parameters: InteriorGirderReinforcementParameters | None = None,
) -> tuple[ExteriorGirderCombinedShear, ...]:
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
        pl = abs(_sample_at(result.pl.shear_samples_tn, position))
        ll = abs(_sample_at(result.ll_im_envelope.shear_samples_tn, position))
        rows.append(
            ExteriorGirderCombinedShear(
                combination_name="RESISTENCIA I",
                limit_state="Resistencia",
                position_m=position,
                dc_shear_tn=dc,
                dc_factor=1.25,
                dw_shear_tn=dw,
                dw_factor=1.50,
                pl_shear_tn=pl,
                pl_factor=1.75,
                ll_im_shear_tn=ll,
                ll_im_factor=1.75,
                combined_shear_tn=1.25 * dc + 1.50 * dw + 1.75 * pl + 1.75 * ll,
            )
        )
    return tuple(rows)


def design_exterior_girder_reinforcement(
    geometry: ExteriorGirderGeometry,
    materials: MaterialProperties,
    analysis: ExteriorGirderAnalysisResult,
    parameters: InteriorGirderReinforcementParameters | None = None,
) -> InteriorGirderReinforcementDesign:
    """Return main, web-temperature and skin reinforcement for the exterior girder."""
    params = parameters or InteriorGirderReinforcementParameters(
        flexural_resistance_factor=DEFAULT_FLEXURAL_RESISTANCE_FACTOR,
        shrinkage_temperature_ratio=DEFAULT_SHRINKAGE_TEMPERATURE_RATIO,
        shear_resistance_factor=DEFAULT_SHEAR_RESISTANCE_FACTOR,
        shear_beta=DEFAULT_SHEAR_BETA,
        shear_theta_degrees=DEFAULT_SHEAR_THETA_DEGREES,
    )
    strength_row = max(
        (row for row in combine_exterior_girder_moments(analysis) if row.limit_state == "Resistencia"),
        key=lambda item: item.combined_moment_tn_m,
    )
    effective_depth_cm = _effective_depth_cm_for_girder(geometry, params)
    flange_width_cm = geometry.tributary_width_m * 100.0
    flange_thickness_cm = geometry.slab_thickness_m * 100.0
    web_width_cm = geometry.web_width_m * 100.0
    gross_depth_cm = geometry.total_t_section_depth_m * 100.0
    gross_centroid_cm, gross_inertia_cm4 = _gross_t_section_properties(geometry)
    cracking_moment = mtc_cracking_moment_tn_m(
        gross_inertia_cm4 / max(gross_depth_cm - gross_centroid_cm, 1e-9),
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
    params, placement_options = _main_placement_options_with_required_layers(
        label="Acero principal longitudinal exterior",
        required_area_cm2=required_area,
        geometry=geometry,
        parameters=params,
    )
    selected = placement_options.recommended
    adopted_depth_cm = selected.effective_depth_cm if selected is not None else effective_depth_cm
    if selected is not None:
        strength_area, neutral_axis = t_beam_flexural_steel_area_cm2(
            design_moment_tn_m=minimum_moment,
            flange_width_cm=flange_width_cm,
            flange_thickness_cm=flange_thickness_cm,
            web_width_cm=web_width_cm,
            effective_depth_cm=adopted_depth_cm,
            concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
            steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
            phi=params.flexural_resistance_factor,
            steel_elastic_modulus_kg_cm2=materials.steel.elastic_modulus_kg_cm2,
        )
        minimum_area = _minimum_flexural_area_cm2(
            concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
            steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
            web_width_cm=web_width_cm,
            effective_depth_cm=adopted_depth_cm,
        )
        required_area = max(strength_area, minimum_area)
        if required_area > placement_options.required_area_cm2 + 1e-9:
            params, placement_options = _main_placement_options_with_required_layers(
                label="Acero principal longitudinal exterior",
                required_area_cm2=required_area,
                geometry=geometry,
                parameters=params,
            )
            selected = placement_options.recommended
            adopted_depth_cm = selected.effective_depth_cm if selected is not None else adopted_depth_cm
        if selected is not None:
            strength_area, neutral_axis = t_beam_flexural_steel_area_cm2(
                design_moment_tn_m=minimum_moment,
                flange_width_cm=flange_width_cm,
                flange_thickness_cm=flange_thickness_cm,
                web_width_cm=web_width_cm,
                effective_depth_cm=adopted_depth_cm,
                concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
                steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
                phi=params.flexural_resistance_factor,
                steel_elastic_modulus_kg_cm2=materials.steel.elastic_modulus_kg_cm2,
            )
            minimum_area = _minimum_flexural_area_cm2(
                concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
                steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
                web_width_cm=web_width_cm,
                effective_depth_cm=adopted_depth_cm,
            )
            required_area = max(strength_area, minimum_area)
    spacing_grid = _spacing_grid(params)
    temperature_required = params.shrinkage_temperature_ratio * 100.0 * web_width_cm / 2.0
    extreme_tension_depth_cm = (
        gross_depth_cm
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
                "Temperatura en cada cara lateral exterior",
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
                "Ask longitudinal exterior por cara",
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


def design_exterior_girder_shear(
    geometry: ExteriorGirderGeometry,
    materials: MaterialProperties,
    analysis: ExteriorGirderAnalysisResult,
    reinforcement: InteriorGirderReinforcementDesign,
) -> InteriorGirderShearDesign:
    """Return sectional shear design for a nonprestressed exterior girder."""
    params = reinforcement.parameters
    controlling = max(
        combine_exterior_girder_shears(geometry, analysis, params),
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
        controlling_shear=InteriorGirderCombinedShear(
            combination_name=controlling.combination_name,
            limit_state=controlling.limit_state,
            position_m=controlling.position_m,
            dc_shear_tn=controlling.dc_shear_tn,
            dc_factor=controlling.dc_factor,
            dw_shear_tn=controlling.dw_shear_tn,
            dw_factor=controlling.dw_factor,
            ll_im_shear_tn=controlling.pl_shear_tn + controlling.ll_im_shear_tn,
            ll_im_factor=controlling.ll_im_factor,
            combined_shear_tn=controlling.combined_shear_tn,
        ),
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


def review_exterior_girder_crack_control(
    geometry: ExteriorGirderGeometry,
    materials: MaterialProperties,
    analysis: ExteriorGirderAnalysisResult,
    reinforcement: InteriorGirderReinforcementDesign,
    main_placement: LongitudinalBarPlacementOption | None = None,
) -> InteriorGirderCrackControlReview:
    """Return crack control review for selected exterior main bars."""
    selected = main_placement or _recommended_main_option(reinforcement.main)
    service_row = max(
        (row for row in combine_exterior_girder_moments(analysis) if row.combination_name == "SERVICIO I"),
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
            label="Fisuracion acero principal viga exterior",
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


def review_exterior_girder_fatigue(
    geometry: ExteriorGirderGeometry,
    materials: MaterialProperties,
    analysis: ExteriorGirderAnalysisResult,
    reinforcement: InteriorGirderReinforcementDesign,
    main_placement: LongitudinalBarPlacementOption | None = None,
) -> InteriorGirderFatigueReview:
    """Return Fatigue I stress-range check for exterior straight bars."""
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


def verify_exterior_girder_service_stresses(
    geometry: ExteriorGirderGeometry,
    materials: MaterialProperties,
    analysis: ExteriorGirderAnalysisResult,
    reinforcement: InteriorGirderReinforcementDesign,
    main_placement: LongitudinalBarPlacementOption | None = None,
) -> InteriorGirderStressVerification:
    """Return exterior Service I concrete and steel stress verification."""
    selected = main_placement or _recommended_main_option(reinforcement.main)
    service_row = max(
        (row for row in combine_exterior_girder_moments(analysis) if row.combination_name == "SERVICIO I"),
        key=lambda item: item.combined_moment_tn_m,
    )
    section = cracked_section_properties(
        geometry=geometry,
        materials=materials,
        steel_area_cm2=selected.provided_area_cm2,
        total_moment_tn_m=service_row.combined_moment_tn_m,
        parameters=reinforcement.parameters,
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


def exterior_asphalt_tributary_width_m(
    deck_overhang_m: float,
    girder_spacing_m: float,
    asphalt_start_m: float,
    asphalt_end_m: float,
) -> float:
    """Return asphalt width overlapping the left exterior girder tributary strip."""
    require_non_negative(deck_overhang_m, "volado de losa")
    require_positive(girder_spacing_m, "S")
    require_non_negative(asphalt_start_m, "inicio asfalto")
    require_positive(asphalt_end_m, "fin asfalto")
    if asphalt_end_m <= asphalt_start_m:
        raise ValueError("El tramo de asfalto debe tener longitud positiva.")
    tributary_start = 0.0
    tributary_end = deck_overhang_m + girder_spacing_m / 2.0
    return max(min(tributary_end, asphalt_end_m) - max(tributary_start, asphalt_start_m), 0.0)


def _main_placement_options_with_required_layers(
    label: str,
    required_area_cm2: float,
    geometry: ExteriorGirderGeometry,
    parameters: InteriorGirderReinforcementParameters,
):
    placement_options = generate_main_bar_placement_options(
        label,
        required_area_cm2,
        geometry,
        parameters,
    )
    if placement_options.recommended is not None:
        return parameters, placement_options

    layer_candidates = [
        option.layers
        for option in placement_options.options
        if option.provided_area_cm2 + 1e-9 >= required_area_cm2
        and option.clear_spacing_cm + 1e-9 >= parameters.minimum_clear_bar_spacing_cm
    ]
    if not layer_candidates:
        return parameters, placement_options

    required_layers = min(layer_candidates)
    if required_layers <= parameters.maximum_main_bar_layers:
        return parameters, placement_options

    adjusted = replace(parameters, maximum_main_bar_layers=required_layers)
    return adjusted, generate_main_bar_placement_options(
        label,
        required_area_cm2,
        geometry,
        adjusted,
    )


def _dc_uniform_loads_tn_m(
    geometry: ExteriorGirderGeometry,
    materials: MaterialProperties,
) -> tuple[float, ...]:
    slab = materials.concrete.specific_weight_tn_m3 * geometry.slab_thickness_m * geometry.tributary_width_m
    web = materials.concrete.specific_weight_tn_m3 * geometry.web_width_m * geometry.girder_total_height_m
    sidewalk = (
        materials.sidewalk.specific_weight_tn_m3
        * materials.sidewalk.thickness_m
        * geometry.sidewalk_tributary_width_m
    )
    railing = materials.railing.weight_kg_m / 1000.0
    barrier = materials.barrier.weight_kg_m / 1000.0
    return (slab, web, sidewalk, railing, barrier)


def _dc_point_loads_tn(
    geometry: ExteriorGirderGeometry,
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
