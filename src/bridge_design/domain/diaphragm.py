"""Transverse diaphragm beam analysis and reinforcement design."""

from dataclasses import dataclass

from bridge_design.codes.mtc_2018 import (
    DEFAULT_FLEXURAL_RESISTANCE_FACTOR,
    DEFAULT_SHRINKAGE_TEMPERATURE_RATIO,
    mtc_cast_in_place_slab_equivalent_strip_widths_m,
    mtc_dynamic_load_allowance_for_slab,
    mtc_multiple_presence_factor,
)
from bridge_design.domain.interior_girder import (
    DEFAULT_SHEAR_BETA,
    DEFAULT_SHEAR_RESISTANCE_FACTOR,
    DEFAULT_SHEAR_THETA_DEGREES,
    InteriorGirderCombinedShear,
    InteriorGirderReinforcementParameters,
    InteriorGirderShearDesign,
    LongitudinalPlacementCaseOptions,
    WebTemperatureSteelDesign,
    _concrete_shear_resistance_tn,
    _effective_shear_depth_cm,
    _generate_shear_stirrup_options,
    _maximum_shear_spacing_m,
    _minimum_flexural_area_cm2,
    _minimum_shear_reinforcement_cm2_m,
    _nominal_shear_upper_limit_tn,
    _required_shear_reinforcement_cm2_m,
    _sample_at,
    generate_main_bar_placement_options,
)
from bridge_design.domain.load_combinations import LoadFactor
from bridge_design.domain.loads import LiveLoads, VehicleLoadModel
from bridge_design.domain.materials import MaterialProperties
from bridge_design.domain.rebar_catalog import (
    SpacingGrid,
    generate_spacing_options,
)
from bridge_design.domain.reinforcement import flexural_steel_area_cm2
from bridge_design.domain.transverse_slab import (
    LoadSegment,
    PointLoad,
    TransverseLoadLayout,
    TransverseSlabGeometry,
    _moving_positions,
    _sampled_moment_at,
    solve_load_case,
)
from bridge_design.validation.input_validators import require_non_negative, require_positive

NODE_TOLERANCE = 1e-8
SHEAR_SAMPLE_STEP_M = 0.05


@dataclass(frozen=True)
class DiaphragmBeamGeometry:
    """Geometry and load-transfer assumptions for a transverse diaphragm beam."""

    girder_spacing_m: float
    girder_count: int
    deck_overhang_m: float
    thickness_m: float
    height_m: float
    slab_thickness_m: float
    load_tributary_length_m: float | None = None
    wheel_distribution_length_m: float | None = None
    vehicle_step_m: float = 0.10

    def __post_init__(self) -> None:
        require_positive(self.girder_spacing_m, "S diafragma")
        require_non_negative(self.deck_overhang_m, "volado de losa")
        require_positive(self.thickness_m, "espesor longitudinal de diafragma")
        require_positive(self.height_m, "altura de diafragma")
        require_positive(self.slab_thickness_m, "espesor de losa")
        require_positive(self.vehicle_step_m, "paso vehicular diafragma")
        if self.girder_count < 2:
            raise ValueError("El diafragma requiere al menos dos vigas principales.")
        if self.load_tributary_length_m is None:
            object.__setattr__(self, "load_tributary_length_m", self.thickness_m)
        if self.wheel_distribution_length_m is None:
            positive_strip, _ = mtc_cast_in_place_slab_equivalent_strip_widths_m(
                self.girder_spacing_m
            )
            object.__setattr__(self, "wheel_distribution_length_m", positive_strip)
        require_positive(float(self.load_tributary_length_m), "longitud tributaria de carga")
        require_positive(float(self.wheel_distribution_length_m), "longitud de distribucion de rueda")

    @property
    def total_width_m(self) -> float:
        """Return transverse diaphragm model width."""
        return 2.0 * self.deck_overhang_m + (self.girder_count - 1) * self.girder_spacing_m

    @property
    def support_positions_m(self) -> tuple[float, ...]:
        """Return girder centerline supports from the left deck edge."""
        return tuple(
            self.deck_overhang_m + index * self.girder_spacing_m
            for index in range(self.girder_count)
        )

    @property
    def web_width_m(self) -> float:
        """Return diaphragm web width for existing placement helpers."""
        return self.thickness_m

    @property
    def total_t_section_depth_m(self) -> float:
        """Return total diaphragm depth for existing shear helpers."""
        return self.height_m


@dataclass(frozen=True)
class DiaphragmLoadCaseAnalysis:
    """Solved transverse diaphragm load case."""

    name: str
    max_positive_moment_tn_m: float
    max_positive_position_m: float
    max_negative_moment_tn_m: float
    max_negative_position_m: float
    max_abs_shear_tn: float
    max_abs_shear_position_m: float
    support_reactions_tn: tuple[tuple[float, float], ...]
    moment_samples_tn_m: tuple[tuple[float, float], ...]
    shear_samples_tn: tuple[tuple[float, float], ...]
    min_moment_samples_tn_m: tuple[tuple[float, float], ...] | None = None
    critical_vehicle_position_m: float | None = None
    vehicle_configuration: str | None = None
    multiple_presence_factor: float | None = None


@dataclass(frozen=True)
class DiaphragmAnalysisResult:
    """Grouped diaphragm DC, DW, PL and LL+IM load effects."""

    dc: DiaphragmLoadCaseAnalysis
    dw: DiaphragmLoadCaseAnalysis
    pl: DiaphragmLoadCaseAnalysis
    ll_im_one_truck: DiaphragmLoadCaseAnalysis
    ll_im_two_trucks: DiaphragmLoadCaseAnalysis
    ll_im_envelope: DiaphragmLoadCaseAnalysis
    dynamic_load_allowance: float


@dataclass(frozen=True)
class DiaphragmCombinedMoment:
    """Factored diaphragm moment row."""

    combination_name: str
    limit_state: str
    direction: str
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
class DiaphragmCombinedShear:
    """Factored diaphragm shear row."""

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


@dataclass(frozen=True)
class DiaphragmFlexuralSteelDesign:
    """Main diaphragm flexural reinforcement for one bending direction."""

    label: str
    direction: str
    controlling_combination_name: str
    position_m: float
    design_moment_tn_m: float
    effective_depth_cm: float
    section_width_cm: float
    strength_area_cm2: float
    minimum_area_cm2: float
    required_area_cm2: float
    placement_options: LongitudinalPlacementCaseOptions


@dataclass(frozen=True)
class DiaphragmReinforcementDesign:
    """Grouped diaphragm flexural, temperature and shear reinforcement."""

    negative: DiaphragmFlexuralSteelDesign
    positive: DiaphragmFlexuralSteelDesign
    temperature: WebTemperatureSteelDesign
    shear: InteriorGirderShearDesign
    parameters: InteriorGirderReinforcementParameters


def diaphragm_geometry_from_transverse(
    transverse: TransverseSlabGeometry,
    thickness_m: float = 0.25,
    height_m: float | None = None,
    load_tributary_length_m: float | None = None,
) -> DiaphragmBeamGeometry:
    """Create diaphragm geometry from the transverse bridge geometry."""
    return DiaphragmBeamGeometry(
        girder_spacing_m=transverse.girder_spacing_m,
        girder_count=transverse.girder_count,
        deck_overhang_m=transverse.overhang_m,
        thickness_m=thickness_m,
        height_m=height_m if height_m is not None else max(transverse.girder_total_height_m - 0.10, 0.10),
        slab_thickness_m=transverse.slab_thickness_m,
        load_tributary_length_m=load_tributary_length_m,
    )


def solve_diaphragm_design(
    geometry: DiaphragmBeamGeometry,
    materials: MaterialProperties,
    live_loads: LiveLoads,
    layout: TransverseLoadLayout,
) -> DiaphragmAnalysisResult:
    """Solve diaphragm load effects for permanent, pedestrian and vehicle loads."""
    dc = _solve_diaphragm_case(
        geometry=geometry,
        materials=materials,
        name="DC - diafragma, losa, veredas, baranda y barrera",
        segments=_dc_segments(geometry, materials, layout),
        point_loads=_dc_points(geometry, materials, layout),
    )
    dw = _solve_diaphragm_case(
        geometry=geometry,
        materials=materials,
        name="DW - superficie de rodadura sobre diafragma",
        segments=_dw_segments(geometry, materials, layout),
        point_loads=(),
    )
    pl = _solve_diaphragm_case(
        geometry=geometry,
        materials=materials,
        name="PL - carga peatonal sobre diafragma",
        segments=_pl_segments(geometry, live_loads, layout),
        point_loads=(),
    )
    ll_one = _solve_moving_vehicle_case(
        geometry=geometry,
        materials=materials,
        vehicle=live_loads.vehicular,
        layout=layout,
        truck_count=1,
    )
    ll_two = _solve_moving_vehicle_case(
        geometry=geometry,
        materials=materials,
        vehicle=live_loads.vehicular,
        layout=layout,
        truck_count=2,
    )
    return DiaphragmAnalysisResult(
        dc=dc,
        dw=dw,
        pl=pl,
        ll_im_one_truck=ll_one,
        ll_im_two_trucks=ll_two,
        ll_im_envelope=_combine_vehicle_cases(ll_one, ll_two),
        dynamic_load_allowance=mtc_dynamic_load_allowance_for_slab(),
    )


def combine_diaphragm_moments(
    result: DiaphragmAnalysisResult,
) -> tuple[DiaphragmCombinedMoment, ...]:
    """Return positive and negative diaphragm moment combinations."""
    combinations = (
        ("RESISTENCIA I", "Resistencia", LoadFactor(1.25, 0.90), LoadFactor(1.50, 0.65), LoadFactor(1.75, omit_when_favorable=True), LoadFactor(1.75, omit_when_favorable=True)),
        ("SERVICIO I", "Servicio", LoadFactor(1.00), LoadFactor(1.00), LoadFactor(1.00, omit_when_favorable=True), LoadFactor(1.00, omit_when_favorable=True)),
    )
    positions = _combined_positions(result.dc, result.dw, result.pl, result.ll_im_envelope)
    rows: list[DiaphragmCombinedMoment] = []
    for name, limit_state, dc_factor, dw_factor, pl_factor, ll_factor in combinations:
        for target in ("max", "min"):
            candidates = []
            for position in positions:
                dc = _sampled_moment_at(result.dc.moment_samples_tn_m, position)
                dw = _sampled_moment_at(result.dw.moment_samples_tn_m, position)
                pl = _sampled_moment_at(result.pl.moment_samples_tn_m, position)
                ll = _moment_at_case(result.ll_im_envelope, position, target)
                g_dc = dc_factor.for_effect(dc, target)
                g_dw = dw_factor.for_effect(dw, target)
                g_pl = pl_factor.for_effect(pl, target)
                g_ll = ll_factor.for_effect(ll, target)
                candidates.append(
                    DiaphragmCombinedMoment(
                        combination_name=name,
                        limit_state=limit_state,
                        direction="M+" if target == "max" else "M-",
                        position_m=position,
                        dc_moment_tn_m=dc,
                        dc_factor=g_dc,
                        dw_moment_tn_m=dw,
                        dw_factor=g_dw,
                        pl_moment_tn_m=pl,
                        pl_factor=g_pl,
                        ll_im_moment_tn_m=ll,
                        ll_im_factor=g_ll,
                        combined_moment_tn_m=g_dc * dc + g_dw * dw + g_pl * pl + g_ll * ll,
                    )
                )
            rows.append(
                max(candidates, key=lambda item: item.combined_moment_tn_m)
                if target == "max"
                else min(candidates, key=lambda item: item.combined_moment_tn_m)
            )
    return tuple(rows)


def combine_diaphragm_shears(
    result: DiaphragmAnalysisResult,
) -> tuple[DiaphragmCombinedShear, ...]:
    """Return Strength I diaphragm shear envelope."""
    positions = _combined_shear_positions(result.dc, result.dw, result.pl, result.ll_im_envelope)
    rows = []
    for position in positions:
        dc = abs(_sample_at(result.dc.shear_samples_tn, position))
        dw = abs(_sample_at(result.dw.shear_samples_tn, position))
        pl = abs(_sample_at(result.pl.shear_samples_tn, position))
        ll = abs(_sample_at(result.ll_im_envelope.shear_samples_tn, position))
        rows.append(
            DiaphragmCombinedShear(
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


def design_diaphragm_reinforcement(
    geometry: DiaphragmBeamGeometry,
    materials: MaterialProperties,
    analysis: DiaphragmAnalysisResult,
    parameters: InteriorGirderReinforcementParameters | None = None,
) -> DiaphragmReinforcementDesign:
    """Return diaphragm negative, positive, side-face temperature and shear design."""
    params = parameters or InteriorGirderReinforcementParameters(
        main_bar_diameter_cm=1.59,
        flexural_resistance_factor=DEFAULT_FLEXURAL_RESISTANCE_FACTOR,
        shrinkage_temperature_ratio=DEFAULT_SHRINKAGE_TEMPERATURE_RATIO,
        shear_resistance_factor=DEFAULT_SHEAR_RESISTANCE_FACTOR,
        shear_beta=DEFAULT_SHEAR_BETA,
        shear_theta_degrees=DEFAULT_SHEAR_THETA_DEGREES,
    )
    strength_rows = tuple(
        row for row in combine_diaphragm_moments(analysis) if row.limit_state == "Resistencia"
    )
    negative = _design_flexural_steel(
        label="Acero principal negativo diafragma",
        direction="M-",
        row=min(
            (row for row in strength_rows if row.direction == "M-"),
            key=lambda item: item.combined_moment_tn_m,
        ),
        geometry=geometry,
        materials=materials,
        params=params,
    )
    positive = _design_flexural_steel(
        label="Acero principal positivo diafragma",
        direction="M+",
        row=max(
            (row for row in strength_rows if row.direction == "M+"),
            key=lambda item: item.combined_moment_tn_m,
        ),
        geometry=geometry,
        materials=materials,
        params=params,
    )
    temperature_required = (
        params.shrinkage_temperature_ratio * 100.0 * geometry.thickness_m * 100.0 / 2.0
    )
    temperature = WebTemperatureSteelDesign(
        ratio=params.shrinkage_temperature_ratio,
        web_width_cm=geometry.thickness_m * 100.0,
        required_area_cm2_m_per_face=temperature_required,
        spacing_options=generate_spacing_options(
            "Temperatura diafragma en cada cara lateral",
            temperature_required,
            SpacingGrid(
                step_m=params.spacing_step_m,
                minimum_m=params.minimum_spacing_m,
                maximum_m=params.maximum_spacing_m,
            ),
        ),
    )
    return DiaphragmReinforcementDesign(
        negative=negative,
        positive=positive,
        temperature=temperature,
        shear=_design_diaphragm_shear(geometry, materials, analysis, params, positive),
        parameters=params,
    )


def _solve_diaphragm_case(
    geometry: DiaphragmBeamGeometry,
    materials: MaterialProperties,
    name: str,
    segments: tuple[LoadSegment, ...],
    point_loads: tuple[PointLoad, ...],
    critical_vehicle_position_m: float | None = None,
    vehicle_configuration: str | None = None,
    multiple_presence_factor: float | None = None,
) -> DiaphragmLoadCaseAnalysis:
    transverse_geometry = _as_transverse_geometry(geometry)
    solved = solve_load_case(
        geometry=transverse_geometry,
        materials=materials,
        name=name,
        segments=segments,
        point_loads=point_loads,
        critical_vehicle_position_m=critical_vehicle_position_m,
        vehicle_configuration=vehicle_configuration,
    )
    shear_samples = _shear_samples(geometry, segments, point_loads, solved.support_reactions_tn)
    max_shear = max(shear_samples, key=lambda item: abs(item[1]))
    return DiaphragmLoadCaseAnalysis(
        name=name,
        max_positive_moment_tn_m=solved.max_positive_moment_tn_m,
        max_positive_position_m=solved.max_positive_position_m,
        max_negative_moment_tn_m=solved.max_negative_moment_tn_m,
        max_negative_position_m=solved.max_negative_position_m,
        max_abs_shear_tn=abs(max_shear[1]),
        max_abs_shear_position_m=max_shear[0],
        support_reactions_tn=solved.support_reactions_tn,
        moment_samples_tn_m=solved.moment_samples_tn_m,
        shear_samples_tn=shear_samples,
        min_moment_samples_tn_m=solved.moment_samples_tn_m,
        critical_vehicle_position_m=critical_vehicle_position_m,
        vehicle_configuration=vehicle_configuration,
        multiple_presence_factor=multiple_presence_factor,
    )


def _solve_moving_vehicle_case(
    geometry: DiaphragmBeamGeometry,
    materials: MaterialProperties,
    vehicle: VehicleLoadModel,
    layout: TransverseLoadLayout,
    truck_count: int,
) -> DiaphragmLoadCaseAnalysis:
    if truck_count not in (1, 2):
        raise ValueError("Solo se permite analizar 1 o 2 camiones.")
    lane_width = vehicle.design_lane_width_m
    group_width = lane_width * truck_count
    travel_length = layout.vehicle_move_end_m - layout.vehicle_move_start_m
    if travel_length + NODE_TOLERANCE < group_width:
        return _empty_vehicle_case(
            name=f"LL+IM - {truck_count} camion(es) sobre diafragma",
            truck_count=truck_count,
            multiple_presence_factor=mtc_multiple_presence_factor(truck_count),
            reason=(
                "recorrido vehicular insuficiente para ubicar el grupo de camiones "
                "HL-93 con ancho de carril de diseno"
            ),
        )

    cases: list[DiaphragmLoadCaseAnalysis] = []
    multiple_presence = mtc_multiple_presence_factor(truck_count)
    impact = mtc_dynamic_load_allowance_for_slab()
    for base_position in _moving_positions(
        layout.vehicle_move_start_m,
        layout.vehicle_move_end_m - group_width,
        geometry.vehicle_step_m,
    ):
        segments, points = _vehicle_loads_at_position(
            geometry=geometry,
            vehicle=vehicle,
            truck_count=truck_count,
            base_position_m=base_position,
            impact_factor=impact,
            multiple_presence_factor=multiple_presence,
        )
        cases.append(
            _solve_diaphragm_case(
                geometry=geometry,
                materials=materials,
                name=f"LL+IM - {truck_count} camion(es) sobre diafragma",
                segments=segments,
                point_loads=points,
                critical_vehicle_position_m=base_position,
                vehicle_configuration=f"{truck_count} camion(es) HL-93",
                multiple_presence_factor=multiple_presence,
            )
        )
    return _envelope_vehicle_cases(
        name=f"LL+IM - {truck_count} camion(es) sobre diafragma",
        cases=cases,
        multiple_presence_factor=multiple_presence,
    )


def _empty_vehicle_case(
    name: str,
    truck_count: int,
    multiple_presence_factor: float,
    reason: str,
) -> DiaphragmLoadCaseAnalysis:
    return DiaphragmLoadCaseAnalysis(
        name=name,
        max_positive_moment_tn_m=0.0,
        max_positive_position_m=0.0,
        max_negative_moment_tn_m=0.0,
        max_negative_position_m=0.0,
        max_abs_shear_tn=0.0,
        max_abs_shear_position_m=0.0,
        support_reactions_tn=(),
        moment_samples_tn_m=((0.0, 0.0),),
        shear_samples_tn=((0.0, 0.0),),
        min_moment_samples_tn_m=((0.0, 0.0),),
        critical_vehicle_position_m=None,
        vehicle_configuration=f"{truck_count} camion(es) no aplicable: {reason}",
        multiple_presence_factor=multiple_presence_factor,
    )


def _combine_vehicle_cases(
    one_truck: DiaphragmLoadCaseAnalysis,
    two_trucks: DiaphragmLoadCaseAnalysis,
) -> DiaphragmLoadCaseAnalysis:
    positions = _combined_positions(one_truck, two_trucks)
    shear_positions = _combined_shear_positions(one_truck, two_trucks)
    moment_samples = tuple(
        (
            position,
            max(
                _sampled_moment_at(one_truck.moment_samples_tn_m, position),
                _sampled_moment_at(two_trucks.moment_samples_tn_m, position),
            ),
        )
        for position in positions
    )
    min_samples = tuple(
        (
            position,
            min(
                _moment_at_case(one_truck, position, "min"),
                _moment_at_case(two_trucks, position, "min"),
            ),
        )
        for position in positions
    )
    min_source = min(min_samples, key=lambda item: item[1])
    positive = max(moment_samples, key=lambda item: item[1])
    shear_samples = tuple(
        (
            position,
            max(
                abs(_sample_at(one_truck.shear_samples_tn, position)),
                abs(_sample_at(two_trucks.shear_samples_tn, position)),
            ),
        )
        for position in shear_positions
    )
    max_shear = max(shear_samples, key=lambda item: abs(item[1]))
    source = max((one_truck, two_trucks), key=lambda item: item.max_positive_moment_tn_m)
    return DiaphragmLoadCaseAnalysis(
        name="LL+IM - envolvente vehicular diafragma",
        max_positive_moment_tn_m=positive[1],
        max_positive_position_m=positive[0],
        max_negative_moment_tn_m=min_source[1],
        max_negative_position_m=min_source[0],
        max_abs_shear_tn=abs(max_shear[1]),
        max_abs_shear_position_m=max_shear[0],
        support_reactions_tn=source.support_reactions_tn,
        moment_samples_tn_m=moment_samples,
        shear_samples_tn=shear_samples,
        min_moment_samples_tn_m=min_samples,
        critical_vehicle_position_m=source.critical_vehicle_position_m,
        vehicle_configuration=source.vehicle_configuration,
        multiple_presence_factor=source.multiple_presence_factor,
    )


def _envelope_vehicle_cases(
    name: str,
    cases: list[DiaphragmLoadCaseAnalysis],
    multiple_presence_factor: float,
) -> DiaphragmLoadCaseAnalysis:
    positions = _combined_positions(*cases)
    shear_positions = _combined_shear_positions(*cases)
    moment_samples = tuple(
        (
            position,
            max(_sampled_moment_at(case.moment_samples_tn_m, position) for case in cases),
        )
        for position in positions
    )
    min_samples = tuple(
        (
            position,
            min(_moment_at_case(case, position, "min") for case in cases),
        )
        for position in positions
    )
    positive_source = max(cases, key=lambda item: item.max_positive_moment_tn_m)
    negative = min(min_samples, key=lambda item: item[1])
    shear_samples = tuple(
        (
            position,
            max(abs(_sample_at(case.shear_samples_tn, position)) for case in cases),
        )
        for position in shear_positions
    )
    max_shear = max(shear_samples, key=lambda item: abs(item[1]))
    positive = max(moment_samples, key=lambda item: item[1])
    return DiaphragmLoadCaseAnalysis(
        name=name,
        max_positive_moment_tn_m=positive[1],
        max_positive_position_m=positive[0],
        max_negative_moment_tn_m=negative[1],
        max_negative_position_m=negative[0],
        max_abs_shear_tn=abs(max_shear[1]),
        max_abs_shear_position_m=max_shear[0],
        support_reactions_tn=positive_source.support_reactions_tn,
        moment_samples_tn_m=moment_samples,
        shear_samples_tn=shear_samples,
        min_moment_samples_tn_m=min_samples,
        critical_vehicle_position_m=positive_source.critical_vehicle_position_m,
        vehicle_configuration=positive_source.vehicle_configuration,
        multiple_presence_factor=multiple_presence_factor,
    )


def _design_flexural_steel(
    label: str,
    direction: str,
    row: DiaphragmCombinedMoment,
    geometry: DiaphragmBeamGeometry,
    materials: MaterialProperties,
    params: InteriorGirderReinforcementParameters,
) -> DiaphragmFlexuralSteelDesign:
    section_width_cm = geometry.thickness_m * 100.0
    effective_depth_cm = geometry.height_m * 100.0 - params.concrete_cover_cm - params.main_bar_diameter_cm / 2.0
    require_positive(effective_depth_cm, f"d {label}")
    strength_area = flexural_steel_area_cm2(
        design_moment_tn_m=abs(row.combined_moment_tn_m),
        strip_width_cm=section_width_cm,
        effective_depth_cm=effective_depth_cm,
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        phi=params.flexural_resistance_factor,
    )
    minimum_area = _minimum_flexural_area_cm2(
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        web_width_cm=section_width_cm,
        effective_depth_cm=effective_depth_cm,
    )
    required_area = max(strength_area, minimum_area)
    return DiaphragmFlexuralSteelDesign(
        label=label,
        direction=direction,
        controlling_combination_name=row.combination_name,
        position_m=row.position_m,
        design_moment_tn_m=abs(row.combined_moment_tn_m),
        effective_depth_cm=effective_depth_cm,
        section_width_cm=section_width_cm,
        strength_area_cm2=strength_area,
        minimum_area_cm2=minimum_area,
        required_area_cm2=required_area,
        placement_options=generate_main_bar_placement_options(
            label,
            required_area,
            geometry,
            params,
            maximum_bar_count=16,
        ),
    )


def _design_diaphragm_shear(
    geometry: DiaphragmBeamGeometry,
    materials: MaterialProperties,
    analysis: DiaphragmAnalysisResult,
    params: InteriorGirderReinforcementParameters,
    positive: DiaphragmFlexuralSteelDesign,
) -> InteriorGirderShearDesign:
    controlling = max(
        combine_diaphragm_shears(analysis),
        key=lambda item: item.combined_shear_tn,
    )
    effective_shear_depth_cm = _effective_shear_depth_cm(geometry, positive.effective_depth_cm)
    web_width_cm = geometry.thickness_m * 100.0
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
    required_av = _required_shear_reinforcement_cm2_m(
        required_vs_tn=required_vs,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        effective_shear_depth_cm=effective_shear_depth_cm,
    )
    transverse_required = controlling.combined_shear_tn > 0.5 * params.shear_resistance_factor * vc
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


def _as_transverse_geometry(geometry: DiaphragmBeamGeometry) -> TransverseSlabGeometry:
    return TransverseSlabGeometry(
        girder_spacing_m=geometry.girder_spacing_m,
        overhang_m=geometry.deck_overhang_m,
        girder_count=geometry.girder_count,
        slab_thickness_m=geometry.height_m,
        girder_total_height_m=geometry.height_m,
        girder_width_m=geometry.thickness_m,
        strip_length_m=geometry.thickness_m,
    )


def _dc_segments(
    geometry: DiaphragmBeamGeometry,
    materials: MaterialProperties,
    layout: TransverseLoadLayout,
) -> tuple[LoadSegment, ...]:
    q_self = materials.concrete.specific_weight_tn_m3 * geometry.thickness_m * geometry.height_m
    q_slab = (
        materials.concrete.specific_weight_tn_m3
        * geometry.slab_thickness_m
        * float(geometry.load_tributary_length_m)
    )
    sidewalk_q = (
        materials.sidewalk.specific_weight_tn_m3
        * materials.sidewalk.thickness_m
        * float(geometry.load_tributary_length_m)
    )
    width = geometry.total_width_m
    return (
        LoadSegment(0.0, width, q_self + q_slab, "peso propio diafragma y losa"),
        *_sidewalk_segments(width, layout.sidewalk_width_m, sidewalk_q, "vereda"),
    )


def _dc_points(
    geometry: DiaphragmBeamGeometry,
    materials: MaterialProperties,
    layout: TransverseLoadLayout,
) -> tuple[PointLoad, ...]:
    width = geometry.total_width_m
    tributary = float(geometry.load_tributary_length_m)
    railing_p = materials.railing.weight_kg_m / 1000.0 * tributary
    barrier_p = materials.barrier.weight_kg_m / 1000.0 * tributary
    return (
        *(
            PointLoad(position, railing_p, "baranda")
            for position in _mirror_positions(layout.railing_left_m, width)
        ),
        *(
            PointLoad(position, barrier_p, "barrera")
            for position in _mirror_positions(
                layout.barrier_left_m + layout.barrier_width_m / 2.0,
                width,
            )
        ),
    )


def _dw_segments(
    geometry: DiaphragmBeamGeometry,
    materials: MaterialProperties,
    layout: TransverseLoadLayout,
) -> tuple[LoadSegment, ...]:
    asphalt_q = (
        materials.asphalt.specific_weight_tn_m3
        * materials.asphalt.thickness_m
        * float(geometry.load_tributary_length_m)
    )
    return (LoadSegment(layout.asphalt_start_m, layout.asphalt_end_m, asphalt_q, "asfalto"),)


def _pl_segments(
    geometry: DiaphragmBeamGeometry,
    live_loads: LiveLoads,
    layout: TransverseLoadLayout,
) -> tuple[LoadSegment, ...]:
    return _sidewalk_segments(
        geometry.total_width_m,
        layout.sidewalk_width_m,
        live_loads.pedestrian.load_tn_m2 * float(geometry.load_tributary_length_m),
        "peatonal",
    )


def _vehicle_loads_at_position(
    geometry: DiaphragmBeamGeometry,
    vehicle: VehicleLoadModel,
    truck_count: int,
    base_position_m: float,
    impact_factor: float,
    multiple_presence_factor: float,
) -> tuple[tuple[LoadSegment, ...], tuple[PointLoad, ...]]:
    lane_width = vehicle.design_lane_width_m
    wheel_spacing = vehicle.wheel_transverse_spacing_m
    tributary_factor = float(geometry.load_tributary_length_m) / float(geometry.wheel_distribution_length_m)
    wheel_line_load = (
        sum(vehicle.design_truck_axles_tn)
        / 2.0
        * (1.0 + impact_factor)
        * multiple_presence_factor
        * tributary_factor
    )
    lane_q = (
        vehicle.lane_load_tn_m
        * multiple_presence_factor
        * float(geometry.load_tributary_length_m)
        / lane_width
    )
    points: list[PointLoad] = []
    segments: list[LoadSegment] = []
    for truck_index in range(truck_count):
        lane_start = base_position_m + truck_index * lane_width
        points.append(PointLoad(lane_start, wheel_line_load, "rueda HL-93 izquierda"))
        points.append(PointLoad(lane_start + wheel_spacing, wheel_line_load, "rueda HL-93 derecha"))
        segments.append(LoadSegment(lane_start, lane_start + lane_width, lane_q, "carga de carril HL-93"))
    return tuple(segments), tuple(points)


def _shear_samples(
    geometry: DiaphragmBeamGeometry,
    segments: tuple[LoadSegment, ...],
    point_loads: tuple[PointLoad, ...],
    support_reactions: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...]:
    positions = set(_moving_positions(0.0, geometry.total_width_m, SHEAR_SAMPLE_STEP_M))
    positions.update(geometry.support_positions_m)
    positions.update(position for position, _ in support_reactions)
    positions.update(point.position_m for point in point_loads)
    for segment in segments:
        positions.update((segment.start_m, segment.end_m))
    offset = 1e-6
    expanded = set()
    for position in positions:
        expanded.add(position)
        if position - offset >= 0.0:
            expanded.add(position - offset)
        if position + offset <= geometry.total_width_m:
            expanded.add(position + offset)
    return tuple(
        (position, _shear_at(position, segments, point_loads, support_reactions))
        for position in sorted(expanded)
    )


def _shear_at(
    x_position: float,
    segments: tuple[LoadSegment, ...],
    point_loads: tuple[PointLoad, ...],
    support_reactions: tuple[tuple[float, float], ...],
) -> float:
    shear = 0.0
    for support_position, reaction in support_reactions:
        if x_position > support_position:
            shear += reaction
    for point_load in point_loads:
        if x_position > point_load.position_m:
            shear -= point_load.p_tn
    for segment in segments:
        if x_position <= segment.start_m:
            continue
        loaded_end = min(x_position, segment.end_m)
        shear -= segment.q_tn_m * (loaded_end - segment.start_m)
    return shear


def _combined_positions(*cases: DiaphragmLoadCaseAnalysis) -> tuple[float, ...]:
    values = set()
    for case in cases:
        values.update(position for position, _ in case.moment_samples_tn_m)
        if case.min_moment_samples_tn_m is not None:
            values.update(position for position, _ in case.min_moment_samples_tn_m)
    return tuple(sorted(values))


def _moment_at_case(
    case: DiaphragmLoadCaseAnalysis,
    position: float,
    target: str,
) -> float:
    if target == "min" and case.min_moment_samples_tn_m is not None:
        return _sampled_moment_at(case.min_moment_samples_tn_m, position)
    return _sampled_moment_at(case.moment_samples_tn_m, position)


def _combined_shear_positions(*cases: DiaphragmLoadCaseAnalysis) -> tuple[float, ...]:
    return tuple(sorted({position for case in cases for position, _ in case.shear_samples_tn}))


def _sidewalk_segments(
    width: float,
    sidewalk_width: float,
    q_tn_m: float,
    label: str,
) -> tuple[LoadSegment, ...]:
    return (
        LoadSegment(0.0, sidewalk_width, q_tn_m, f"{label} izquierda"),
        LoadSegment(width - sidewalk_width, width, q_tn_m, f"{label} derecha"),
    )


def _mirror_positions(left_position: float, width: float) -> tuple[float, ...]:
    right_position = width - left_position
    if abs(left_position - right_position) <= NODE_TOLERANCE:
        return (left_position,)
    return (left_position, right_position)
