"""Constructive detailing for longitudinal bridge girders."""

from dataclasses import dataclass
from math import ceil
from typing import Protocol

from bridge_design.codes.mtc_2018 import mtc_tension_development_length_cm
from bridge_design.domain.interior_girder import (
    InteriorGirderAnalysisResult,
    InteriorGirderReinforcementDesign,
    LongitudinalBarPlacementOption,
    ShearStirrupOption,
    _concrete_shear_resistance_tn,
    _effective_shear_depth_cm,
    _maximum_shear_spacing_m,
    _minimum_flexural_area_cm2,
    _minimum_shear_reinforcement_cm2_m,
    _moment_at,
    _nominal_shear_upper_limit_tn,
    _required_shear_reinforcement_cm2_m,
    _sample_at,
    _round_spacing_down,
    t_beam_flexural_steel_area_cm2,
)
from bridge_design.domain.materials import MaterialProperties


class GirderGeometry(Protocol):
    """Protocol for the girder geometry fields used by detailing."""

    span_length_m: float
    web_width_m: float
    total_t_section_depth_m: float


@dataclass(frozen=True)
class GirderEnvelopeStation:
    """Factored envelope values and required steel at one station."""

    x_m: float
    mu_tn_m: float
    vu_tn: float
    flexural_area_cm2: float
    minimum_area_cm2: float
    required_area_cm2: float
    required_bar_count: int
    selected_bar_count: int
    status: str


@dataclass(frozen=True)
class LongitudinalBarCutDetail:
    """Constructive cut length for one longitudinal bar group."""

    group: str
    bar_label: str
    bar_count: int
    threshold_bar_count: int
    theoretical_start_m: float
    theoretical_end_m: float
    development_length_m: float
    detail_start_m: float
    detail_end_m: float
    bar_length_m: float
    physical_cut_count: int
    status: str


@dataclass(frozen=True)
class StirrupZoneDetail:
    """Constructive stirrup spacing zone."""

    bar_label: str
    legs: int
    start_m: float
    end_m: float
    spacing_m: float
    maximum_vu_tn: float
    required_av_cm2_m: float
    provided_av_cm2_m: float
    maximum_spacing_m: float
    phi_vn_tn: float
    status: str


@dataclass(frozen=True)
class GirderDetailingResult:
    """Longitudinal cuts and stirrup zones for one girder."""

    label: str
    span_length_m: float
    selected_main_bar: LongitudinalBarPlacementOption
    selected_stirrup: ShearStirrupOption
    continuous_bar_count: int
    development_length_m: float
    physical_cut_count: int
    envelope: tuple[GirderEnvelopeStation, ...]
    longitudinal_cuts: tuple[LongitudinalBarCutDetail, ...]
    stirrup_zones: tuple[StirrupZoneDetail, ...]


def detail_interior_girder(
    label: str,
    geometry: GirderGeometry,
    materials: MaterialProperties,
    analysis: InteriorGirderAnalysisResult,
    reinforcement: InteriorGirderReinforcementDesign,
    selected_main_bar: LongitudinalBarPlacementOption | None = None,
    selected_stirrup: ShearStirrupOption | None = None,
) -> GirderDetailingResult:
    """Return detailing for an interior girder using the selected reinforcement."""
    return _detail_girder(
        label=label,
        geometry=geometry,
        materials=materials,
        analysis=analysis,
        reinforcement=reinforcement,
        selected_main_bar=selected_main_bar,
        selected_stirrup=selected_stirrup,
        include_pedestrian_load=False,
    )


def detail_exterior_girder(
    label: str,
    geometry: GirderGeometry,
    materials: MaterialProperties,
    analysis,
    reinforcement: InteriorGirderReinforcementDesign,
    selected_main_bar: LongitudinalBarPlacementOption | None = None,
    selected_stirrup: ShearStirrupOption | None = None,
) -> GirderDetailingResult:
    """Return detailing for an exterior girder using the selected reinforcement."""
    return _detail_girder(
        label=label,
        geometry=geometry,
        materials=materials,
        analysis=analysis,
        reinforcement=reinforcement,
        selected_main_bar=selected_main_bar,
        selected_stirrup=selected_stirrup,
        include_pedestrian_load=True,
    )


def _detail_girder(
    label: str,
    geometry: GirderGeometry,
    materials: MaterialProperties,
    analysis,
    reinforcement: InteriorGirderReinforcementDesign,
    selected_main_bar: LongitudinalBarPlacementOption | None,
    selected_stirrup: ShearStirrupOption | None,
    include_pedestrian_load: bool,
) -> GirderDetailingResult:
    main_bar = selected_main_bar or _default_main_bar(reinforcement)
    stirrup = selected_stirrup or _default_stirrup(geometry, materials, analysis, reinforcement, include_pedestrian_load)
    envelope = _girder_envelope(
        geometry=geometry,
        materials=materials,
        analysis=analysis,
        reinforcement=reinforcement,
        main_bar=main_bar,
        include_pedestrian_load=include_pedestrian_load,
    )
    continuous_count = _continuous_bar_count(envelope, main_bar)
    development_length_m = _development_length_m(
        bar=main_bar,
        materials=materials,
    )
    cuts = _longitudinal_cut_details(
        label=label,
        span_length_m=geometry.span_length_m,
        envelope=envelope,
        main_bar=main_bar,
        continuous_count=continuous_count,
        development_length_m=development_length_m,
    )
    zones = _stirrup_zone_details(
        geometry=geometry,
        materials=materials,
        analysis=analysis,
        reinforcement=reinforcement,
        stirrup=stirrup,
        include_pedestrian_load=include_pedestrian_load,
    )
    physical_cut_count = sum(cut.physical_cut_count for cut in cuts)
    return GirderDetailingResult(
        label=label,
        span_length_m=geometry.span_length_m,
        selected_main_bar=main_bar,
        selected_stirrup=stirrup,
        continuous_bar_count=continuous_count,
        development_length_m=development_length_m,
        physical_cut_count=physical_cut_count,
        envelope=envelope,
        longitudinal_cuts=cuts,
        stirrup_zones=zones,
    )


def _girder_envelope(
    geometry: GirderGeometry,
    materials: MaterialProperties,
    analysis,
    reinforcement: InteriorGirderReinforcementDesign,
    main_bar: LongitudinalBarPlacementOption,
    include_pedestrian_load: bool,
) -> tuple[GirderEnvelopeStation, ...]:
    stations = []
    minimum_area = _minimum_flexural_area_cm2(
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        web_width_cm=reinforcement.main.web_width_cm,
        effective_depth_cm=reinforcement.main.effective_depth_cm,
    )
    for x_m in _analysis_positions(analysis):
        dc_m = _moment_at(analysis.dc.moment_samples_tn_m, x_m)
        dw_m = _moment_at(analysis.dw.moment_samples_tn_m, x_m)
        ll_m = _moment_at(analysis.ll_im_envelope.moment_samples_tn_m, x_m)
        dc_v = abs(_sample_at(analysis.dc.shear_samples_tn, x_m))
        dw_v = abs(_sample_at(analysis.dw.shear_samples_tn, x_m))
        ll_v = abs(_sample_at(analysis.ll_im_envelope.shear_samples_tn, x_m))
        pl_m = _moment_at(analysis.pl.moment_samples_tn_m, x_m) if include_pedestrian_load else 0.0
        pl_v = abs(_sample_at(analysis.pl.shear_samples_tn, x_m)) if include_pedestrian_load else 0.0
        mu = max(1.25 * dc_m + 1.50 * dw_m + 1.75 * pl_m + 1.75 * ll_m, 0.0)
        vu = 1.25 * dc_v + 1.50 * dw_v + 1.75 * pl_v + 1.75 * ll_v
        flexural_area, _ = t_beam_flexural_steel_area_cm2(
            design_moment_tn_m=mu,
            flange_width_cm=reinforcement.main.flange_width_cm,
            flange_thickness_cm=reinforcement.main.flange_thickness_cm,
            web_width_cm=reinforcement.main.web_width_cm,
            effective_depth_cm=reinforcement.main.effective_depth_cm,
            concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
            steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
            phi=reinforcement.parameters.flexural_resistance_factor,
            steel_elastic_modulus_kg_cm2=materials.steel.elastic_modulus_kg_cm2,
        )
        required_area = max(flexural_area, minimum_area)
        required_count = ceil(required_area / main_bar.bar_area_cm2)
        stations.append(
            GirderEnvelopeStation(
                x_m=x_m,
                mu_tn_m=mu,
                vu_tn=vu,
                flexural_area_cm2=flexural_area,
                minimum_area_cm2=minimum_area,
                required_area_cm2=required_area,
                required_bar_count=required_count,
                selected_bar_count=main_bar.bar_count,
                status="OK" if required_count <= main_bar.bar_count else "NO CUMPLE",
            )
        )
    return tuple(stations)


def _longitudinal_cut_details(
    label: str,
    span_length_m: float,
    envelope: tuple[GirderEnvelopeStation, ...],
    main_bar: LongitudinalBarPlacementOption,
    continuous_count: int,
    development_length_m: float,
) -> tuple[LongitudinalBarCutDetail, ...]:
    details = [
        LongitudinalBarCutDetail(
            group="Barras continuas",
            bar_label=main_bar.bar_label,
            bar_count=continuous_count,
            threshold_bar_count=continuous_count,
            theoretical_start_m=0.0,
            theoretical_end_m=span_length_m,
            development_length_m=0.0,
            detail_start_m=0.0,
            detail_end_m=span_length_m,
            bar_length_m=span_length_m,
            physical_cut_count=0,
            status="OK",
        )
    ]
    provided_count = continuous_count
    group_index = 1
    critical_positions = _critical_flexural_positions(envelope, span_length_m)
    for group_count in _additional_bar_groups(main_bar, continuous_count):
        threshold = provided_count + 1
        active = [station.x_m for station in envelope if station.required_bar_count >= threshold]
        status_for_inactive_group = "OK"
        if not active:
            active = critical_positions
            status_for_inactive_group = "ADOPTADA EN ZONA CRITICA"
        theoretical_start = min(active)
        theoretical_end = max(active)
        detail_start = max(0.0, theoretical_start - development_length_m)
        detail_end = min(span_length_m, theoretical_end + development_length_m)
        if detail_end - detail_start >= 0.90 * span_length_m:
            detail_start = 0.0
            detail_end = span_length_m
        physical_cuts = int(detail_start > 1e-9) + int(detail_end < span_length_m - 1e-9)
        status = (
            "CONTINUA POR LD"
            if physical_cuts == 0
            else status_for_inactive_group
        )
        details.append(
            LongitudinalBarCutDetail(
                group=f"Adicional {group_index}",
                bar_label=main_bar.bar_label,
                bar_count=group_count,
                threshold_bar_count=threshold,
                theoretical_start_m=round(theoretical_start, 3),
                theoretical_end_m=round(theoretical_end, 3),
                development_length_m=round(development_length_m, 3),
                detail_start_m=round(detail_start, 3),
                detail_end_m=round(detail_end, 3),
                bar_length_m=round(detail_end - detail_start, 3),
                physical_cut_count=physical_cuts,
                status=status,
            )
        )
        provided_count += group_count
        group_index += 1
    return tuple(details)


def _critical_flexural_positions(
    envelope: tuple[GirderEnvelopeStation, ...],
    span_length_m: float,
) -> tuple[float, ...]:
    """Return the station(s) where the flexural steel demand is highest."""
    if not envelope:
        return (span_length_m / 2.0,)
    maximum_required_area = max(station.required_area_cm2 for station in envelope)
    positions = tuple(
        station.x_m
        for station in envelope
        if abs(station.required_area_cm2 - maximum_required_area) <= 1e-9
    )
    return positions or (span_length_m / 2.0,)


def _stirrup_zone_details(
    geometry: GirderGeometry,
    materials: MaterialProperties,
    analysis,
    reinforcement: InteriorGirderReinforcementDesign,
    stirrup: ShearStirrupOption,
    include_pedestrian_load: bool,
) -> tuple[StirrupZoneDetail, ...]:
    station_details = tuple(
        _stirrup_station_detail(
            geometry=geometry,
            materials=materials,
            analysis=analysis,
            reinforcement=reinforcement,
            stirrup=stirrup,
            x_m=x_m,
            include_pedestrian_load=include_pedestrian_load,
        )
        for x_m in _analysis_positions(analysis)
    )
    if not station_details:
        return ()
    span = geometry.span_length_m
    boundaries = tuple(round(span * index / 6.0, 3) for index in range(7))
    zones = []
    for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
        if index == len(boundaries) - 2:
            zone = [station for station in station_details if start <= station.start_m <= end]
        else:
            zone = [station for station in station_details if start <= station.start_m < end]
        if not zone:
            zone = [min(station_details, key=lambda station: abs(station.start_m - (start + end) / 2.0))]
        zones.append(_collapse_stirrup_zone(zone, start, end))
    return tuple(zones)


def _stirrup_station_detail(
    geometry: GirderGeometry,
    materials: MaterialProperties,
    analysis,
    reinforcement: InteriorGirderReinforcementDesign,
    stirrup: ShearStirrupOption,
    x_m: float,
    include_pedestrian_load: bool,
) -> StirrupZoneDetail:
    params = reinforcement.parameters
    effective_shear_depth_cm = _effective_shear_depth_cm(
        geometry,
        reinforcement.main.effective_depth_cm,
    )
    web_width_cm = geometry.web_width_m * 100.0
    vu = _factored_shear_at(analysis, x_m, include_pedestrian_load)
    vc = _concrete_shear_resistance_tn(
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        web_width_cm=web_width_cm,
        effective_shear_depth_cm=effective_shear_depth_cm,
        beta=params.shear_beta,
    )
    required_vs = max(vu / params.shear_resistance_factor - vc, 0.0)
    required_av = _required_shear_reinforcement_cm2_m(
        required_vs_tn=required_vs,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        effective_shear_depth_cm=effective_shear_depth_cm,
    )
    minimum_av = _minimum_shear_reinforcement_cm2_m(
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        web_width_cm=web_width_cm,
    )
    if vu > 0.5 * params.shear_resistance_factor * vc:
        required_av = max(required_av, minimum_av)
    max_spacing = _maximum_shear_spacing_m(
        vu_tn=vu,
        phi=params.shear_resistance_factor,
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        web_width_cm=web_width_cm,
        effective_shear_depth_cm=effective_shear_depth_cm,
    )
    spacing_limit = (
        max_spacing
        if required_av <= 0.0
        else min(max_spacing, stirrup.legs * stirrup.bar_area_cm2 / required_av)
    )
    spacing = max(
        _round_spacing_down(spacing_limit, reinforcement.parameters.spacing_step_m),
        reinforcement.parameters.spacing_step_m,
    )
    provided_av = stirrup.legs * stirrup.bar_area_cm2 / spacing
    nominal_limit = _nominal_shear_upper_limit_tn(
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        web_width_cm=web_width_cm,
        effective_shear_depth_cm=effective_shear_depth_cm,
    )
    vs = (
        provided_av
        / 100.0
        * (materials.steel.yield_strength_kg_cm2 / 1000.0)
        * effective_shear_depth_cm
    )
    phi_vn = params.shear_resistance_factor * min(vc + vs, nominal_limit)
    return StirrupZoneDetail(
        bar_label=stirrup.bar_label,
        legs=stirrup.legs,
        start_m=x_m,
        end_m=x_m,
        spacing_m=round(spacing, 3),
        maximum_vu_tn=vu,
        required_av_cm2_m=required_av,
        provided_av_cm2_m=provided_av,
        maximum_spacing_m=max_spacing,
        phi_vn_tn=phi_vn,
        status="OK" if phi_vn + 1e-9 >= vu and spacing <= max_spacing + 1e-9 else "NO CUMPLE",
    )


def _collapse_stirrup_zone(
    zone: list[StirrupZoneDetail],
    start_m: float,
    end_m: float,
) -> StirrupZoneDetail:
    governing = min(zone, key=lambda item: item.spacing_m)
    maximum_vu = max(item.maximum_vu_tn for item in zone)
    maximum_spacing = min(item.maximum_spacing_m for item in zone)
    return StirrupZoneDetail(
        bar_label=governing.bar_label,
        legs=governing.legs,
        start_m=round(start_m, 3),
        end_m=round(end_m, 3),
        spacing_m=governing.spacing_m,
        maximum_vu_tn=maximum_vu,
        required_av_cm2_m=max(item.required_av_cm2_m for item in zone),
        provided_av_cm2_m=governing.provided_av_cm2_m,
        maximum_spacing_m=maximum_spacing,
        phi_vn_tn=governing.phi_vn_tn,
        status=(
            "OK"
            if governing.phi_vn_tn + 1e-9 >= maximum_vu
            and governing.spacing_m <= maximum_spacing + 1e-9
            else "NO CUMPLE"
        ),
    )


def _factored_shear_at(analysis, x_m: float, include_pedestrian_load: bool) -> float:
    dc = abs(_sample_at(analysis.dc.shear_samples_tn, x_m))
    dw = abs(_sample_at(analysis.dw.shear_samples_tn, x_m))
    ll = abs(_sample_at(analysis.ll_im_envelope.shear_samples_tn, x_m))
    pl = abs(_sample_at(analysis.pl.shear_samples_tn, x_m)) if include_pedestrian_load else 0.0
    return 1.25 * dc + 1.50 * dw + 1.75 * pl + 1.75 * ll


def _analysis_positions(analysis) -> tuple[float, ...]:
    positions = {
        x_m
        for case in (analysis.dc, analysis.dw, analysis.ll_im_envelope)
        for x_m, _ in case.moment_samples_tn_m
    }
    if hasattr(analysis, "pl"):
        positions.update(x_m for x_m, _ in analysis.pl.moment_samples_tn_m)
    return tuple(sorted(positions))


def _continuous_bar_count(
    envelope: tuple[GirderEnvelopeStation, ...],
    main_bar: LongitudinalBarPlacementOption,
) -> int:
    minimum_required = max((station.required_bar_count for station in envelope if station.minimum_area_cm2 >= station.required_area_cm2 - 1e-9), default=2)
    continuous = max(2, minimum_required)
    return _round_up_to_complete_layer(continuous, _bar_layer_counts(main_bar))


def _additional_bar_groups(
    main_bar: LongitudinalBarPlacementOption,
    continuous_count: int,
) -> tuple[int, ...]:
    layer_counts = _bar_layer_counts(main_bar)
    if continuous_count >= main_bar.bar_count:
        return ()
    groups = []
    accumulated = 0
    for layer_count in layer_counts:
        next_accumulated = accumulated + layer_count
        if next_accumulated > continuous_count:
            groups.append(next_accumulated - max(accumulated, continuous_count))
        accumulated = next_accumulated
    return tuple(group for group in groups if group > 0)


def _bar_layer_counts(main_bar: LongitudinalBarPlacementOption) -> tuple[int, ...]:
    bars_per_layer = max(main_bar.bars_per_layer, 1)
    counts = []
    remaining = main_bar.bar_count
    while remaining > 0:
        layer_count = min(bars_per_layer, remaining)
        counts.append(layer_count)
        remaining -= layer_count
    return tuple(counts)


def _round_up_to_complete_layer(value: int, layer_counts: tuple[int, ...]) -> int:
    accumulated = 0
    for layer_count in layer_counts:
        accumulated += layer_count
        if accumulated >= value:
            return accumulated
    return accumulated


def _development_length_m(
    bar: LongitudinalBarPlacementOption,
    materials: MaterialProperties,
) -> float:
    required_ld_cm, _ = mtc_tension_development_length_cm(
        bar_diameter_cm=bar.bar_diameter_cm,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
    )
    return round(required_ld_cm / 100.0, 3)


def _default_main_bar(
    reinforcement: InteriorGirderReinforcementDesign,
) -> LongitudinalBarPlacementOption:
    option = reinforcement.main.placement_options.recommended
    if option is not None:
        return option
    return reinforcement.main.placement_options.options[-1]


def _default_stirrup(
    geometry: GirderGeometry,
    materials: MaterialProperties,
    analysis,
    reinforcement: InteriorGirderReinforcementDesign,
    include_pedestrian_load: bool,
) -> ShearStirrupOption:
    # Import locally to keep this module independent from exterior_girder imports.
    if include_pedestrian_load:
        from bridge_design.domain.exterior_girder import design_exterior_girder_shear

        shear = design_exterior_girder_shear(geometry, materials, analysis, reinforcement)
    else:
        from bridge_design.domain.interior_girder import design_interior_girder_shear

        shear = design_interior_girder_shear(geometry, materials, analysis, reinforcement)
    option = shear.recommended
    if option is not None:
        return option
    return shear.options[-1]
