"""Transverse slab structural model and matrix analysis."""

from dataclasses import dataclass, field, replace
from typing import Iterable, Literal
from itertools import combinations
from bridge_design.domain.transverse_patterns import TRANSVERSE_WHEEL_CLEARANCE_M, wheel_patterns

from bridge_design.codes.mtc_2018 import (
    mtc_cast_in_place_slab_equivalent_strip_widths_m,
    mtc_dynamic_load_allowance_for_slab,
    mtc_multiple_presence_factor,
    mtc_design_lanes,
)
from bridge_design.domain.loads import LiveLoads, VehicleLoadModel
from bridge_design.domain.materials import MaterialProperties
from bridge_design.domain.sampling import interpolate_sorted_samples, envelope_sorted_samples
from bridge_design.validation.input_validators import require_non_negative, require_positive


NODE_TOLERANCE = 1e-8
TRANSVERSE_DESIGN_LANE_SPACING_M = 3.60


@dataclass(frozen=True)
class TransverseSlabGeometry:
    """Geometry for the 1 m longitudinal design strip."""

    girder_spacing_m: float
    overhang_m: float
    girder_count: int
    slab_thickness_m: float
    girder_total_height_m: float
    girder_width_m: float
    strip_length_m: float = 1.0
    _allow_nonunit_strip: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        require_positive(self.girder_spacing_m, "S")
        require_non_negative(self.overhang_m, "a")
        require_positive(self.slab_thickness_m, "espesor de losa")
        require_positive(self.girder_total_height_m, "altura total de viga")
        require_positive(self.girder_width_m, "ancho de viga")
        require_positive(self.strip_length_m, "ancho longitudinal de analisis")
        if not self._allow_nonunit_strip and abs(self.strip_length_m - 1.0) > 1e-9:
            raise ValueError(
                "La franja longitudinal del tablero debe ser unitaria: "
                "strip_length_m = 1.00 m."
            )
        if self.girder_count < 2:
            raise ValueError("El numero de vigas debe ser al menos 2.")

    @property
    def total_width_m(self) -> float:
        """Return total transverse deck width."""
        return 2.0 * self.overhang_m + (self.girder_count - 1) * self.girder_spacing_m

    @property
    def support_positions_m(self) -> tuple[float, ...]:
        """Return support positions from the left deck edge."""
        return tuple(
            self.overhang_m + index * self.girder_spacing_m
            for index in range(self.girder_count)
        )

    @property
    def slab_inertia_m4(self) -> float:
        """Return inertia of a 1 m wide rectangular slab strip."""
        return self.strip_length_m * self.slab_thickness_m**3.0 / 12.0


@dataclass(frozen=True)
class LoadSegment:
    """Uniform load segment in Tn/m."""

    start_m: float
    end_m: float
    q_tn_m: float
    label: str

    def __post_init__(self) -> None:
        require_non_negative(self.start_m, f"inicio {self.label}")
        require_positive(self.end_m, f"fin {self.label}")
        if self.end_m <= self.start_m:
            raise ValueError(f"El tramo de carga {self.label} debe tener longitud positiva.")
        require_positive(self.q_tn_m, f"q {self.label}")


@dataclass(frozen=True)
class PointLoad:
    """Concentrated downward load in Tn."""

    position_m: float
    p_tn: float
    label: str

    def __post_init__(self) -> None:
        require_non_negative(self.position_m, f"ubicacion {self.label}")
        require_positive(self.p_tn, f"P {self.label}")


@dataclass(frozen=True)
class TransverseLoadLayout:
    """User-defined load placement inputs."""

    asphalt_start_m: float
    asphalt_end_m: float
    sidewalk_width_m: float
    railing_left_m: float
    barrier_left_m: float
    barrier_width_m: float
    vehicle_move_start_m: float
    vehicle_move_end_m: float
    vehicle_step_m: float = 0.10

    def __post_init__(self) -> None:
        require_non_negative(self.asphalt_start_m, "inicio asfalto")
        require_positive(self.asphalt_end_m, "fin asfalto")
        if self.asphalt_end_m <= self.asphalt_start_m:
            raise ValueError("El tramo de asfalto debe tener longitud positiva.")
        require_positive(self.sidewalk_width_m, "ancho de vereda")
        require_non_negative(self.railing_left_m, "ubicacion baranda")
        require_non_negative(self.barrier_left_m, "ubicacion barrera")
        require_positive(self.barrier_width_m, "ancho de barrera")
        require_non_negative(self.vehicle_move_start_m, "inicio recorrido vehicular")
        require_positive(self.vehicle_move_end_m, "fin recorrido vehicular")
        if self.vehicle_move_end_m <= self.vehicle_move_start_m:
            raise ValueError("El recorrido vehicular debe tener longitud positiva.")
        require_positive(self.vehicle_step_m, "paso de movimiento")


@dataclass(frozen=True)
class TransverseSlabDesignInputs:
    """Complete transverse slab design input group."""

    geometry: TransverseSlabGeometry
    load_layout: TransverseLoadLayout


@dataclass(frozen=True)
class LoadCaseAnalysis:
    """Solved load case result."""

    name: str
    max_positive_moment_tn_m: float
    max_positive_position_m: float
    max_negative_moment_tn_m: float
    max_negative_position_m: float
    support_reactions_tn: tuple[tuple[float, float], ...]
    critical_vehicle_position_m: float | None = None
    vehicle_configuration: str | None = None
    multiple_presence_factor: float | None = None
    equivalent_strip_width_positive_m: float | None = None
    equivalent_strip_width_negative_m: float | None = None
    moment_samples_tn_m: tuple[tuple[float, float], ...] = ()
    max_moment_envelope_tn_m: tuple[tuple[float, float], ...] | None = None
    min_moment_envelope_tn_m: tuple[tuple[float, float], ...] | None = None


@dataclass(frozen=True)
class TransverseSlabAnalysisResult:
    """Results for all requested transverse slab load cases."""

    dc: LoadCaseAnalysis
    dw: LoadCaseAnalysis
    pl: LoadCaseAnalysis
    ll_im_one_truck: LoadCaseAnalysis
    ll_im_two_trucks: LoadCaseAnalysis
    ll_im_envelope: LoadCaseAnalysis
    dynamic_load_allowance: float
    equivalent_strip_width_positive_m: float
    equivalent_strip_width_negative_m: float


@dataclass(frozen=True)
class TransverseLoadPlacementCase:
    """Unsolved load placement data for auditing transverse load locations."""

    name: str
    segments: tuple[LoadSegment, ...]
    point_loads: tuple[PointLoad, ...]


def kg_cm2_to_tn_m2(value: float) -> float:
    """Convert kgf/cm2 to Tn/m2."""
    return value * 10.0


def validate_layout_inside_geometry(
    geometry: TransverseSlabGeometry,
    layout: TransverseLoadLayout,
) -> None:
    """Validate that all load positions fit inside the deck width."""
    width = geometry.total_width_m
    for value, field_name in (
        (layout.asphalt_start_m, "inicio asfalto"),
        (layout.asphalt_end_m, "fin asfalto"),
        (layout.sidewalk_width_m, "ancho de vereda"),
        (layout.railing_left_m, "ubicacion baranda"),
        (layout.barrier_left_m, "ubicacion barrera"),
        (layout.barrier_left_m + layout.barrier_width_m, "cara interior de barrera"),
        (layout.vehicle_move_start_m, "inicio recorrido vehicular"),
        (layout.vehicle_move_end_m, "fin recorrido vehicular"),
    ):
        if value > width:
            raise ValueError(f"{field_name} debe estar dentro del tablero ({width:g} m).")
    if layout.sidewalk_width_m * 2.0 > width:
        raise ValueError("La suma de veredas izquierda y derecha excede el ancho del tablero.")


def solve_transverse_slab_design(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    live_loads: LiveLoads,
    layout: TransverseLoadLayout,
) -> TransverseSlabAnalysisResult:
    """Solve DC, DW, PL and moving LL+IM cases."""
    validate_layout_inside_geometry(geometry, layout)
    dc = solve_load_case(
        geometry,
        materials,
        "DC - cargas muertas",
        _dc_segments(geometry, materials, layout),
        _dc_points(geometry, materials, layout),
    )
    dw = solve_load_case(
        geometry,
        materials,
        "DW - superficie de rodadura",
        _dw_segments(materials, layout),
        (),
    )
    pl = solve_load_case(
        geometry,
        materials,
        "PL - carga peatonal",
        _pl_segments(live_loads, layout, geometry.total_width_m),
        (),
    )
    pedestrian_segments = _pl_segments(live_loads, layout, geometry.total_width_m)
    for count in range(len(pedestrian_segments)):
        for pattern in combinations(pedestrian_segments, count):
            pl = replace(_combine_vehicle_envelopes(pl, solve_load_case(
                geometry, materials, "PL - patron peatonal", pattern, ()
            )), name="PL - envolvente de zonas peatonales")
    ll_one = solve_moving_vehicle_envelope(
        geometry=geometry,
        materials=materials,
        vehicle=live_loads.vehicular,
        layout=layout,
        truck_count=1,
    )
    ll_two = solve_moving_vehicle_envelope(
        geometry=geometry,
        materials=materials,
        vehicle=live_loads.vehicular,
        layout=layout,
        truck_count=2,
    )
    ll_envelope = _combine_vehicle_envelopes(ll_one, ll_two)
    lane_count, _ = mtc_design_lanes(layout.vehicle_move_end_m - layout.vehicle_move_start_m)
    for count in range(3, lane_count + 1):
        ll_envelope = _combine_vehicle_envelopes(ll_envelope, solve_moving_vehicle_envelope(
            geometry, materials, live_loads.vehicular, layout, count
        ))
    strip_positive, strip_negative = mtc_cast_in_place_slab_equivalent_strip_widths_m(
        geometry.girder_spacing_m
    )
    return TransverseSlabAnalysisResult(
        dc=dc,
        dw=dw,
        pl=pl,
        ll_im_one_truck=ll_one,
        ll_im_two_trucks=ll_two,
        ll_im_envelope=ll_envelope,
        dynamic_load_allowance=mtc_dynamic_load_allowance_for_slab(),
        equivalent_strip_width_positive_m=strip_positive,
        equivalent_strip_width_negative_m=strip_negative,
    )


def transverse_load_placement_cases(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    live_loads: LiveLoads,
    layout: TransverseLoadLayout,
) -> tuple[TransverseLoadPlacementCase, ...]:
    """Return DC, DW and PL load placements before structural analysis."""
    validate_layout_inside_geometry(geometry, layout)
    return (
        TransverseLoadPlacementCase(
            "DC - cargas muertas",
            _dc_segments(geometry, materials, layout),
            _dc_points(geometry, materials, layout),
        ),
        TransverseLoadPlacementCase(
            "DW - superficie de rodadura",
            _dw_segments(materials, layout),
            (),
        ),
        TransverseLoadPlacementCase(
            "PL - carga peatonal",
            _pl_segments(live_loads, layout, geometry.total_width_m),
            (),
        ),
    )


def solve_load_case(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    name: str,
    segments: Iterable[LoadSegment],
    point_loads: Iterable[PointLoad],
    critical_vehicle_position_m: float | None = None,
    vehicle_configuration: str | None = None,
) -> LoadCaseAnalysis:
    """Solve one load case by Euler-Bernoulli beam stiffness matrices."""
    segments_tuple = tuple(segments)
    points_tuple = tuple(point_loads)
    nodes = _analysis_nodes(geometry, segments_tuple, points_tuple)
    dof_count = len(nodes) * 2
    stiffness = [[0.0 for _ in range(dof_count)] for _ in range(dof_count)]
    force = [0.0 for _ in range(dof_count)]
    elastic_modulus = kg_cm2_to_tn_m2(materials.concrete.elastic_modulus_kg_cm2)
    ei = elastic_modulus * geometry.slab_inertia_m4

    for left_index, right_index in zip(range(len(nodes) - 1), range(1, len(nodes))):
        left = nodes[left_index]
        right = nodes[right_index]
        length = right - left
        if length <= NODE_TOLERANCE:
            continue
        element_stiffness = _beam_element_stiffness(ei, length)
        element_dofs = [
            2 * left_index,
            2 * left_index + 1,
            2 * right_index,
            2 * right_index + 1,
        ]
        for row in range(4):
            global_row = element_dofs[row]
            for col in range(4):
                stiffness[global_row][element_dofs[col]] += element_stiffness[row][col]

        q_tn_m = _uniform_load_on_element(left, right, segments_tuple)
        if q_tn_m > 0.0:
            equivalent = _uniform_load_vector(q_tn_m, length)
            for row in range(4):
                force[element_dofs[row]] += equivalent[row]

    for point_load in points_tuple:
        node_index = _node_index(nodes, point_load.position_m)
        force[2 * node_index] -= point_load.p_tn

    constrained = {_node_index(nodes, support) * 2 for support in geometry.support_positions_m}
    free = [index for index in range(dof_count) if index not in constrained]
    reduced_stiffness = [[stiffness[row][col] for col in free] for row in free]
    reduced_force = [force[row] for row in free]
    reduced_displacements = _solve_linear_system(reduced_stiffness, reduced_force)
    displacements = [0.0 for _ in range(dof_count)]
    for index, dof in enumerate(free):
        displacements[dof] = reduced_displacements[index]

    residual = _mat_vec(stiffness, displacements)
    reactions_by_dof = [residual[index] - force[index] for index in range(dof_count)]
    support_reactions = tuple(
        (support, reactions_by_dof[2 * _node_index(nodes, support)])
        for support in geometry.support_positions_m
    )
    samples = _moment_samples(geometry, nodes, segments_tuple, points_tuple, support_reactions)
    max_positive = max(samples, key=lambda item: item[1])
    max_negative = min(samples, key=lambda item: item[1])

    return LoadCaseAnalysis(
        name=name,
        max_positive_moment_tn_m=max_positive[1],
        max_positive_position_m=max_positive[0],
        max_negative_moment_tn_m=max_negative[1],
        max_negative_position_m=max_negative[0],
        support_reactions_tn=support_reactions,
        critical_vehicle_position_m=critical_vehicle_position_m,
        vehicle_configuration=vehicle_configuration,
        moment_samples_tn_m=tuple(samples),
    )


def solve_moving_vehicle_envelope(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    vehicle: VehicleLoadModel,
    layout: TransverseLoadLayout,
    truck_count: int,
) -> LoadCaseAnalysis:
    """Move independently positioned HL-93 heavy axles within design lanes."""
    require_positive(truck_count, "numero de carriles")

    wheel_spacing = vehicle.wheel_transverse_spacing_m
    positive_strip_width, negative_strip_width = mtc_cast_in_place_slab_equivalent_strip_widths_m(
        geometry.girder_spacing_m
    )
    lane_count, _ = mtc_design_lanes(layout.vehicle_move_end_m - layout.vehicle_move_start_m)
    if truck_count > lane_count:
        return _empty_vehicle_case(
            truck_count=truck_count,
            multiple_presence=mtc_multiple_presence_factor(truck_count),
            positive_strip_width=positive_strip_width,
            negative_strip_width=negative_strip_width,
            reason=(
                "ancho libre insuficiente para ubicar el eje pesado HL-93 "
                "con separaciones transversales normativas"
            ),
        )

    positive_cases: list[LoadCaseAnalysis] = []
    negative_cases: list[LoadCaseAnalysis] = []
    multiple_presence = mtc_multiple_presence_factor(truck_count)
    impact_factor = mtc_dynamic_load_allowance_for_slab()
    for wheel_positions in wheel_patterns(
        layout.vehicle_move_start_m, layout.vehicle_move_end_m, truck_count,
        layout.vehicle_step_m, wheel_spacing,
    ):
        base_position = wheel_positions[0]
        positive_segments, positive_points = _vehicle_loads_at_position(
            vehicle=vehicle,
            truck_count=truck_count,
            base_position_m=base_position,
            impact_factor=impact_factor,
            multiple_presence_factor=multiple_presence,
            equivalent_strip_width_m=positive_strip_width,
            wheel_positions_m=wheel_positions,
        )
        negative_segments, negative_points = _vehicle_loads_at_position(
            vehicle=vehicle,
            truck_count=truck_count,
            base_position_m=base_position,
            impact_factor=impact_factor,
            multiple_presence_factor=multiple_presence,
            equivalent_strip_width_m=negative_strip_width,
            wheel_positions_m=wheel_positions,
        )
        positive_case = solve_load_case(
            geometry=geometry,
            materials=materials,
            name=f"LL+IM - {truck_count} carril(es)",
            segments=positive_segments,
            point_loads=positive_points,
            critical_vehicle_position_m=base_position,
            vehicle_configuration=f"{truck_count} carril(es), ruedas izquierdas {wheel_positions}",
        )
        negative_case = solve_load_case(
            geometry=geometry,
            materials=materials,
            name=f"LL+IM - {truck_count} carril(es)",
            segments=negative_segments,
            point_loads=negative_points,
            critical_vehicle_position_m=base_position,
            vehicle_configuration=f"{truck_count} carril(es), ruedas izquierdas {wheel_positions}",
        )
        positive_cases.append(positive_case)
        negative_cases.append(negative_case)

    max_positive = max(positive_cases, key=lambda item: item.max_positive_moment_tn_m)
    max_negative = min(negative_cases, key=lambda item: item.max_negative_moment_tn_m)
    max_envelope = _envelope_moment_samples(positive_cases, "max")
    min_envelope = _envelope_moment_samples(negative_cases, "min")
    return LoadCaseAnalysis(
        name=f"LL+IM - {truck_count} carril(es)",
        max_positive_moment_tn_m=max_positive.max_positive_moment_tn_m,
        max_positive_position_m=max_positive.max_positive_position_m,
        max_negative_moment_tn_m=max_negative.max_negative_moment_tn_m,
        max_negative_position_m=max_negative.max_negative_position_m,
        support_reactions_tn=max_positive.support_reactions_tn,
        critical_vehicle_position_m=max_positive.critical_vehicle_position_m,
        vehicle_configuration=(f"M+: {max_positive.vehicle_configuration}; M-: {max_negative.vehicle_configuration}"),
        multiple_presence_factor=multiple_presence,
        equivalent_strip_width_positive_m=positive_strip_width,
        equivalent_strip_width_negative_m=negative_strip_width,
        moment_samples_tn_m=max_envelope,
        max_moment_envelope_tn_m=max_envelope,
        min_moment_envelope_tn_m=min_envelope,
    )


def format_transverse_scheme(geometry: TransverseSlabGeometry) -> str:
    """Return an ASCII transverse section scheme."""
    width = geometry.total_width_m
    scale_width = 72
    axis = ["-" for _ in range(scale_width + 1)]
    supports = [" " for _ in range(scale_width + 1)]
    labels = [" " for _ in range(scale_width + 1)]
    for index, support in enumerate(geometry.support_positions_m):
        marker = _scaled_index(support, width, scale_width)
        axis[marker] = "+"
        supports[marker] = "^"
        labels[marker] = chr(ord("A") + index)

    lines = [
        "ESQUEMA DE SECCION TRANSVERSAL - LOSA ENTRE VIGAS",
        f"Ancho total = {width:.3f} m | franja longitudinal de analisis = {geometry.strip_length_m:.3f} m",
        f"S = {geometry.girder_spacing_m:.3f} m | a = {geometry.overhang_m:.3f} m | vigas = {geometry.girder_count}",
        f"t losa = {geometry.slab_thickness_m:.3f} m | h viga = {geometry.girder_total_height_m:.3f} m | b viga = {geometry.girder_width_m:.3f} m",
        "",
        "".join(axis),
        "".join(supports),
        "".join(labels),
        f"0.000 m{' ' * max(scale_width - 13, 1)}{width:.3f} m",
        "",
        "Apoyos articulados en vigas: "
        + ", ".join(
            f"{chr(ord('A') + index)}={position:.3f} m"
            for index, position in enumerate(geometry.support_positions_m)
        ),
    ]
    return "\n".join(lines)


def _dc_segments(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    layout: TransverseLoadLayout,
) -> tuple[LoadSegment, ...]:
    width = geometry.total_width_m
    slab_q = materials.concrete.specific_weight_tn_m3 * geometry.slab_thickness_m
    sidewalk_q = materials.sidewalk.specific_weight_tn_m3 * materials.sidewalk.thickness_m
    return (
        LoadSegment(0.0, width, slab_q, "peso propio losa"),
        *_sidewalk_segments(width, layout.sidewalk_width_m, sidewalk_q, "vereda"),
    )


def _dc_points(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    layout: TransverseLoadLayout,
) -> tuple[PointLoad, ...]:
    width = geometry.total_width_m
    railing_p = materials.railing.weight_kg_m / 1000.0
    barrier_p = materials.barrier.weight_kg_m / 1000.0
    railing_positions = _mirror_positions(layout.railing_left_m, width)
    barrier_positions = _mirror_positions(
        layout.barrier_left_m + layout.barrier_width_m / 2.0,
        width,
    )
    return (
        *(
            PointLoad(position, railing_p, label)
            for position, label in _label_mirrored_positions(railing_positions, "baranda")
        ),
        *(
            PointLoad(position, barrier_p, label)
            for position, label in _label_mirrored_positions(barrier_positions, "barrera")
        ),
    )


def _dw_segments(
    materials: MaterialProperties,
    layout: TransverseLoadLayout,
) -> tuple[LoadSegment, ...]:
    asphalt_q = materials.asphalt.specific_weight_tn_m3 * materials.asphalt.thickness_m
    return (LoadSegment(layout.asphalt_start_m, layout.asphalt_end_m, asphalt_q, "asfalto"),)


def _pl_segments(
    live_loads: LiveLoads,
    layout: TransverseLoadLayout,
    width: float,
) -> tuple[LoadSegment, ...]:
    return _sidewalk_segments(
        width,
        layout.sidewalk_width_m,
        live_loads.pedestrian.load_tn_m2,
        "peatonal",
    )


def _vehicle_loads_at_position(
    vehicle: VehicleLoadModel,
    truck_count: int,
    base_position_m: float,
    impact_factor: float,
    multiple_presence_factor: float,
    equivalent_strip_width_m: float,
    wheel_positions_m: tuple[float, ...] | None = None,
) -> tuple[tuple[LoadSegment, ...], tuple[PointLoad, ...]]:
    wheel_spacing = vehicle.wheel_transverse_spacing_m
    heavy_axle_load = max(vehicle.design_truck_axles_tn)
    wheel_line_load = (
        heavy_axle_load
        / 2.0
        * (1.0 + impact_factor)
        * multiple_presence_factor
        / equivalent_strip_width_m
    )
    points: list[PointLoad] = []
    for lane_start in (wheel_positions_m or tuple(
        base_position_m + index * TRANSVERSE_DESIGN_LANE_SPACING_M for index in range(truck_count)
    )):
        points.append(PointLoad(lane_start, wheel_line_load, "rueda eje pesado HL-93 izquierda"))
        points.append(
            PointLoad(
                lane_start + wheel_spacing,
                wheel_line_load,
                "rueda eje pesado HL-93 derecha",
            )
        )
    return (), tuple(points)


def _empty_vehicle_case(
    truck_count: int,
    multiple_presence: float,
    positive_strip_width: float | None,
    negative_strip_width: float | None,
    reason: str,
) -> LoadCaseAnalysis:
    return LoadCaseAnalysis(
        name=f"LL+IM - {truck_count} carril(es)",
        max_positive_moment_tn_m=0.0,
        max_positive_position_m=0.0,
        max_negative_moment_tn_m=0.0,
        max_negative_position_m=0.0,
        support_reactions_tn=(),
        critical_vehicle_position_m=None,
        vehicle_configuration=f"{truck_count} carril(es) no aplicable: {reason}",
        multiple_presence_factor=multiple_presence,
        equivalent_strip_width_positive_m=positive_strip_width,
        equivalent_strip_width_negative_m=negative_strip_width,
        moment_samples_tn_m=((0.0, 0.0),),
        max_moment_envelope_tn_m=((0.0, 0.0),),
        min_moment_envelope_tn_m=((0.0, 0.0),),
    )


def _combine_vehicle_envelopes(
    one_truck: LoadCaseAnalysis,
    two_trucks: LoadCaseAnalysis,
) -> LoadCaseAnalysis:
    positive_source = max(
        (one_truck, two_trucks),
        key=lambda item: item.max_positive_moment_tn_m,
    )
    negative_source = min(
        (one_truck, two_trucks),
        key=lambda item: item.max_negative_moment_tn_m,
    )
    max_envelope = _merge_moment_envelopes(one_truck, two_trucks, "max")
    min_envelope = _merge_moment_envelopes(one_truck, two_trucks, "min")
    return LoadCaseAnalysis(
        name="LL+IM - envolvente vehicular",
        max_positive_moment_tn_m=positive_source.max_positive_moment_tn_m,
        max_positive_position_m=positive_source.max_positive_position_m,
        max_negative_moment_tn_m=negative_source.max_negative_moment_tn_m,
        max_negative_position_m=negative_source.max_negative_position_m,
        support_reactions_tn=positive_source.support_reactions_tn,
        critical_vehicle_position_m=positive_source.critical_vehicle_position_m,
        vehicle_configuration=(
            f"M+ gobierna {positive_source.vehicle_configuration}; "
            f"M- gobierna {negative_source.vehicle_configuration}"
        ),
        equivalent_strip_width_positive_m=positive_source.equivalent_strip_width_positive_m,
        equivalent_strip_width_negative_m=negative_source.equivalent_strip_width_negative_m,
        moment_samples_tn_m=max_envelope,
        max_moment_envelope_tn_m=max_envelope,
        min_moment_envelope_tn_m=min_envelope,
    )


def _envelope_moment_samples(
    cases: list[LoadCaseAnalysis],
    target: Literal["max", "min"],
) -> tuple[tuple[float, float], ...]:
    positions = sorted(
        {
            position
            for case in cases
            for position, _ in case.moment_samples_tn_m
        }
    )
    return envelope_sorted_samples(
        (case.moment_samples_tn_m for case in cases), positions, target,
        tolerance=NODE_TOLERANCE,
    )


def _merge_moment_envelopes(
    first: LoadCaseAnalysis,
    second: LoadCaseAnalysis,
    target: Literal["max", "min"],
) -> tuple[tuple[float, float], ...]:
    first_samples = (
        first.max_moment_envelope_tn_m
        if target == "max"
        else first.min_moment_envelope_tn_m
    ) or first.moment_samples_tn_m
    second_samples = (
        second.max_moment_envelope_tn_m
        if target == "max"
        else second.min_moment_envelope_tn_m
    ) or second.moment_samples_tn_m
    positions = sorted(
        {position for position, _ in first_samples}
        | {position for position, _ in second_samples}
    )
    envelope = []
    for position in positions:
        first_value = _sampled_moment_at(first_samples, position)
        second_value = _sampled_moment_at(second_samples, position)
        selected = (
            max(first_value, second_value)
            if target == "max"
            else min(first_value, second_value)
        )
        envelope.append((position, selected))
    return tuple(envelope)


def _sampled_moment_at(
    samples: tuple[tuple[float, float], ...],
    position: float,
) -> float:
    return interpolate_sorted_samples(
        samples,
        position,
        tolerance=NODE_TOLERANCE,
        empty_message="No hay muestras de momento.",
    )


def _sidewalk_segments(
    width: float,
    sidewalk_width: float,
    q_tn_m: float,
    label: str,
) -> tuple[LoadSegment, ...]:
    left = LoadSegment(0.0, sidewalk_width, q_tn_m, f"{label} izquierda")
    right = LoadSegment(width - sidewalk_width, width, q_tn_m, f"{label} derecha")
    return (left, right)


def _mirror_positions(left_position: float, width: float) -> tuple[float, ...]:
    right_position = width - left_position
    if abs(left_position - right_position) <= NODE_TOLERANCE:
        return (left_position,)
    return (left_position, right_position)


def _label_mirrored_positions(
    positions: tuple[float, ...],
    base_label: str,
) -> tuple[tuple[float, str], ...]:
    if len(positions) == 1:
        return ((positions[0], base_label),)
    return (
        (positions[0], f"{base_label} izquierda"),
        (positions[1], f"{base_label} derecha"),
    )


def _analysis_nodes(
    geometry: TransverseSlabGeometry,
    segments: tuple[LoadSegment, ...],
    point_loads: tuple[PointLoad, ...],
) -> list[float]:
    raw_nodes = [0.0, geometry.total_width_m]
    raw_nodes.extend(geometry.support_positions_m)
    for segment in segments:
        raw_nodes.extend((segment.start_m, segment.end_m))
    for point_load in point_loads:
        raw_nodes.append(point_load.position_m)
    return _unique_sorted(raw_nodes)


def _unique_sorted(values: Iterable[float]) -> list[float]:
    result: list[float] = []
    for value in sorted(values):
        if not result or abs(value - result[-1]) > NODE_TOLERANCE:
            result.append(value)
    return result


def _node_index(nodes: list[float], value: float) -> int:
    for index, node in enumerate(nodes):
        if abs(node - value) <= NODE_TOLERANCE:
            return index
    raise ValueError(f"No se encontro nodo en x={value:g} m.")


def _beam_element_stiffness(ei: float, length: float) -> list[list[float]]:
    factor = ei / length**3.0
    return [
        [12.0 * factor, 6.0 * length * factor, -12.0 * factor, 6.0 * length * factor],
        [
            6.0 * length * factor,
            4.0 * length**2.0 * factor,
            -6.0 * length * factor,
            2.0 * length**2.0 * factor,
        ],
        [-12.0 * factor, -6.0 * length * factor, 12.0 * factor, -6.0 * length * factor],
        [
            6.0 * length * factor,
            2.0 * length**2.0 * factor,
            -6.0 * length * factor,
            4.0 * length**2.0 * factor,
        ],
    ]


def _uniform_load_vector(q_tn_m: float, length: float) -> list[float]:
    return [
        -q_tn_m * length / 2.0,
        -q_tn_m * length**2.0 / 12.0,
        -q_tn_m * length / 2.0,
        q_tn_m * length**2.0 / 12.0,
    ]


def _uniform_load_on_element(
    left: float,
    right: float,
    segments: tuple[LoadSegment, ...],
) -> float:
    midpoint = (left + right) / 2.0
    q_total = 0.0
    for segment in segments:
        if segment.start_m - NODE_TOLERANCE <= midpoint <= segment.end_m + NODE_TOLERANCE:
            q_total += segment.q_tn_m
    return q_total


def _moment_samples(
    geometry: TransverseSlabGeometry,
    nodes: list[float],
    segments: tuple[LoadSegment, ...],
    point_loads: tuple[PointLoad, ...],
    support_reactions: tuple[tuple[float, float], ...],
) -> list[tuple[float, float]]:
    sample_positions = set(nodes)
    for left, right in zip(nodes[:-1], nodes[1:]):
        for index in range(1, 24):
            sample_positions.add(left + (right - left) * index / 24.0)
    sample_positions.update(geometry.support_positions_m)
    samples = []
    for position in sorted(sample_positions):
        samples.append(
            (
                position,
                _bending_moment_at(position, segments, point_loads, support_reactions),
            )
        )
    return samples


def _bending_moment_at(
    x_position: float,
    segments: tuple[LoadSegment, ...],
    point_loads: tuple[PointLoad, ...],
    support_reactions: tuple[tuple[float, float], ...],
) -> float:
    moment = 0.0
    for support_position, reaction in support_reactions:
        if x_position > support_position:
            moment += reaction * (x_position - support_position)
    for point_load in point_loads:
        if x_position > point_load.position_m:
            moment -= point_load.p_tn * (x_position - point_load.position_m)
    for segment in segments:
        if x_position <= segment.start_m:
            continue
        loaded_end = min(x_position, segment.end_m)
        loaded_length = loaded_end - segment.start_m
        centroid = segment.start_m + loaded_length / 2.0
        moment -= segment.q_tn_m * loaded_length * (x_position - centroid)
    return moment


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for pivot_index in range(size):
        pivot_row = max(
            range(pivot_index, size),
            key=lambda row_index: abs(augmented[row_index][pivot_index]),
        )
        if abs(augmented[pivot_row][pivot_index]) <= 1e-12:
            raise ValueError("La matriz de rigidez es singular; revise apoyos y geometria.")
        if pivot_row != pivot_index:
            augmented[pivot_index], augmented[pivot_row] = (
                augmented[pivot_row],
                augmented[pivot_index],
            )
        pivot = augmented[pivot_index][pivot_index]
        for col in range(pivot_index, size + 1):
            augmented[pivot_index][col] /= pivot
        for row in range(size):
            if row == pivot_index:
                continue
            factor = augmented[row][pivot_index]
            if abs(factor) <= 1e-18:
                continue
            for col in range(pivot_index, size + 1):
                augmented[row][col] -= factor * augmented[pivot_index][col]
    return [augmented[row][size] for row in range(size)]


def _mat_vec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(value * vector[col] for col, value in enumerate(row)) for row in matrix]


def _moving_positions(start: float, end: float, step: float) -> list[float]:
    if end < start:
        return [start]
    positions: list[float] = []
    current = start
    while current <= end + NODE_TOLERANCE:
        positions.append(round(current, 10))
        current += step
    if abs(positions[-1] - end) > NODE_TOLERANCE:
        positions.append(end)
    return positions


def _scaled_index(position: float, width: float, scale_width: int) -> int:
    if width <= NODE_TOLERANCE:
        return 0
    return max(0, min(scale_width, round(position / width * scale_width)))
