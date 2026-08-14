import pytest

from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel
from bridge_design.domain.materials import (
    ConcreteProperties,
    LinearWeightProperties,
    MaterialProperties,
    SteelProperties,
    SurfaceLayerProperties,
)
from bridge_design.domain.transverse_slab import (
    LoadSegment,
    TRANSVERSE_DESIGN_LANE_SPACING_M,
    TRANSVERSE_WHEEL_CLEARANCE_M,
    TransverseLoadLayout,
    TransverseSlabGeometry,
    _vehicle_loads_at_position,
    solve_load_case,
    solve_transverse_slab_design,
    solve_moving_vehicle_envelope,
)


def _materials() -> MaterialProperties:
    return MaterialProperties(
        concrete=ConcreteProperties.from_inputs(
            specific_weight_tn_m3=2.4,
            compressive_strength_kg_cm2=280.0,
        ),
        steel=SteelProperties(),
        asphalt=SurfaceLayerProperties("asfalto", 2.2, 0.05),
        sidewalk=SurfaceLayerProperties("vereda", 2.4, 0.20),
        railing=LinearWeightProperties("baranda", 100.0),
        barrier=LinearWeightProperties("barrera", 500.0),
    )


def test_transverse_geometry_supports_and_width() -> None:
    geometry = TransverseSlabGeometry(
        girder_spacing_m=2.10,
        overhang_m=0.825,
        girder_count=4,
        slab_thickness_m=0.20,
        girder_total_height_m=1.20,
        girder_width_m=0.30,
    )

    assert round(geometry.total_width_m, 3) == 7.950
    assert tuple(round(value, 3) for value in geometry.support_positions_m) == (
        0.825,
        2.925,
        5.025,
        7.125,
    )


def test_matrix_solver_matches_simple_span_uniform_load() -> None:
    geometry = TransverseSlabGeometry(
        girder_spacing_m=4.0,
        overhang_m=0.0,
        girder_count=2,
        slab_thickness_m=0.20,
        girder_total_height_m=1.00,
        girder_width_m=0.30,
    )

    result = solve_load_case(
        geometry=geometry,
        materials=_materials(),
        name="uniforme",
        segments=(LoadSegment(0.0, 4.0, 1.0, "q"),),
        point_loads=(),
    )

    assert round(result.max_positive_moment_tn_m, 3) == 2.000
    assert round(result.max_positive_position_m, 3) == 2.000
    assert round(result.support_reactions_tn[0][1], 3) == 2.000
    assert round(result.support_reactions_tn[1][1], 3) == 2.000


def test_transverse_design_solves_all_requested_cases() -> None:
    geometry = TransverseSlabGeometry(
        girder_spacing_m=2.10,
        overhang_m=0.825,
        girder_count=4,
        slab_thickness_m=0.20,
        girder_total_height_m=1.20,
        girder_width_m=0.30,
    )
    layout = TransverseLoadLayout(
        asphalt_start_m=1.075,
        asphalt_end_m=6.875,
        sidewalk_width_m=0.825,
        railing_left_m=0.13,
        barrier_left_m=0.825,
        barrier_width_m=0.25,
        vehicle_move_start_m=0.825,
        vehicle_move_end_m=7.125,
        vehicle_step_m=0.50,
    )
    live_loads = LiveLoads(
        pedestrian=PedestrianLoad.mtc_sidewalk_default(),
        vehicular=VehicleLoadModel.mtc_hl93_default(),
    )

    result = solve_transverse_slab_design(
        geometry=geometry,
        materials=_materials(),
        live_loads=live_loads,
        layout=layout,
    )

    assert result.dc.max_positive_moment_tn_m > 0
    assert result.dw.max_positive_moment_tn_m > 0
    assert result.pl.max_positive_moment_tn_m > 0
    assert result.ll_im_envelope.max_positive_moment_tn_m > 0


def test_transverse_slab_ll_im_uses_only_hl93_heavy_axle() -> None:
    vehicle = VehicleLoadModel.mtc_hl93_default()

    segments, points = _vehicle_loads_at_position(
        vehicle=vehicle,
        truck_count=2,
        base_position_m=2.465,
        impact_factor=0.33,
        multiple_presence_factor=1.00,
        equivalent_strip_width_m=2.0185,
    )

    expected_wheel_load = max(vehicle.design_truck_axles_tn) / 2.0 * 1.33 / 2.0185
    assert segments == ()
    assert len(points) == 4
    assert points[0].p_tn == pytest.approx(expected_wheel_load)
    assert points[1].position_m - points[0].position_m == pytest.approx(
        vehicle.wheel_transverse_spacing_m
    )
    assert points[2].position_m - points[0].position_m == pytest.approx(
        TRANSVERSE_DESIGN_LANE_SPACING_M
    )


def test_transverse_slab_vehicle_path_is_measured_from_inner_barrier_faces() -> None:
    geometry = TransverseSlabGeometry(
        girder_spacing_m=2.47,
        overhang_m=1.00,
        girder_count=5,
        slab_thickness_m=0.20,
        girder_total_height_m=1.10,
        girder_width_m=0.40,
    )
    layout = TransverseLoadLayout(
        asphalt_start_m=2.13,
        asphalt_end_m=9.73,
        sidewalk_width_m=1.50,
        railing_left_m=0.12,
        barrier_left_m=1.48,
        barrier_width_m=0.375,
        vehicle_move_start_m=1.855,
        vehicle_move_end_m=10.025,
        vehicle_step_m=0.10,
    )

    case = solve_moving_vehicle_envelope(
        geometry=geometry,
        materials=MaterialProperties(
            concrete=ConcreteProperties.from_inputs(
                specific_weight_tn_m3=2.4,
                compressive_strength_kg_cm2=280.0,
            ),
            steel=SteelProperties(),
            asphalt=SurfaceLayerProperties("asfalto", 2.2, 0.05),
            sidewalk=SurfaceLayerProperties("vereda", 2.4, 0.20),
            railing=LinearWeightProperties("baranda", 15.0),
            barrier=LinearWeightProperties("barrera", 390.0),
        ),
        vehicle=VehicleLoadModel.mtc_hl93_default(),
        layout=layout,
        truck_count=2,
    )

    path_start = layout.vehicle_move_start_m + TRANSVERSE_WHEEL_CLEARANCE_M
    path_end = (
        layout.vehicle_move_end_m
        - TRANSVERSE_WHEEL_CLEARANCE_M
        - TRANSVERSE_DESIGN_LANE_SPACING_M
        - VehicleLoadModel.mtc_hl93_default().wheel_transverse_spacing_m
    )
    assert case.critical_vehicle_position_m is not None
    assert path_start <= case.critical_vehicle_position_m <= path_end
