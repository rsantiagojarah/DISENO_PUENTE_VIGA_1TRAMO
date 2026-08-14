from bridge_design.codes.mtc_2018 import (
    calculate_concrete_elastic_modulus_kg_cm2,
    default_sidewalk_pedestrian_load_tn_m2,
    mtc_cast_in_place_slab_equivalent_strip_widths_m,
    mtc_distribution_reinforcement_percent_for_transverse_primary,
    mtc_dynamic_load_allowance_for_slab,
    mtc_exterior_concrete_t_girder_live_load_moment_distribution_factor,
    mtc_exterior_concrete_t_girder_live_load_shear_distribution_factor,
    mtc_exterior_rigid_cross_section_distribution_factor,
    mtc_interior_concrete_t_girder_live_load_shear_distribution_factor,
    mtc_multiple_presence_factor,
)
from bridge_design.domain.loads import VehicleLoadModel
from bridge_design.domain.materials import ConcreteProperties


def test_concrete_elastic_modulus_uses_mtc_units() -> None:
    ec = calculate_concrete_elastic_modulus_kg_cm2(
        specific_weight_tn_m3=2.4,
        compressive_strength_kg_cm2=280.0,
    )

    assert round(ec, 0) == 298822


def test_concrete_properties_calculates_ec_automatically() -> None:
    concrete = ConcreteProperties.from_inputs(
        specific_weight_tn_m3=2.4,
        compressive_strength_kg_cm2=280.0,
    )

    assert concrete.elastic_modulus_kg_cm2 > 0


def test_default_sidewalk_pedestrian_load_conversion() -> None:
    assert round(default_sidewalk_pedestrian_load_tn_m2(), 3) == 0.366


def test_hl93_vehicle_default_values() -> None:
    vehicle = VehicleLoadModel.mtc_hl93_default()

    assert vehicle.name == "HL-93"
    assert round(vehicle.design_truck_axles_tn[0], 3) == 3.629
    assert round(vehicle.design_truck_axles_tn[1], 3) == 14.515
    assert round(vehicle.lane_load_tn_m, 3) == 0.954


def test_mtc_live_load_factors_for_transverse_slab() -> None:
    assert mtc_dynamic_load_allowance_for_slab() == 0.33
    assert mtc_multiple_presence_factor(1) == 1.20
    assert mtc_multiple_presence_factor(2) == 1.00
    assert mtc_multiple_presence_factor(3) == 0.85
    assert mtc_multiple_presence_factor(4) == 0.65


def test_mtc_equivalent_strip_widths_for_cast_in_place_slab() -> None:
    positive, negative = mtc_cast_in_place_slab_equivalent_strip_widths_m(2.10)

    assert round(positive, 3) == 1.815
    assert round(negative, 3) == 1.745


def test_mtc_distribution_reinforcement_percent_for_transverse_primary() -> None:
    assert round(mtc_distribution_reinforcement_percent_for_transverse_primary(2.10), 1) == 67.0
    assert round(mtc_distribution_reinforcement_percent_for_transverse_primary(4.00), 1) == 60.7


def test_mtc_girder_shear_and_exterior_distribution_factors() -> None:
    vehicle = VehicleLoadModel.mtc_hl93_default()

    interior_shear = mtc_interior_concrete_t_girder_live_load_shear_distribution_factor(
        span_length_m=15.0,
        girder_spacing_m=2.10,
        slab_thickness_m=0.20,
        girder_count=4,
    )
    exterior_moment = mtc_exterior_concrete_t_girder_live_load_moment_distribution_factor(
        span_length_m=15.0,
        girder_spacing_m=2.10,
        slab_thickness_m=0.20,
        girder_total_height_m=1.20,
        web_width_m=0.30,
        girder_count=4,
        exterior_web_to_traffic_barrier_m=0.0,
        wheel_transverse_spacing_m=vehicle.wheel_transverse_spacing_m,
        design_lane_width_m=vehicle.design_lane_width_m,
    )
    exterior_shear = mtc_exterior_concrete_t_girder_live_load_shear_distribution_factor(
        span_length_m=15.0,
        girder_spacing_m=2.10,
        slab_thickness_m=0.20,
        girder_count=4,
        exterior_web_to_traffic_barrier_m=0.0,
        wheel_transverse_spacing_m=vehicle.wheel_transverse_spacing_m,
        design_lane_width_m=vehicle.design_lane_width_m,
    )
    rigid = mtc_exterior_rigid_cross_section_distribution_factor(
        girder_spacing_m=2.10,
        girder_count=4,
        exterior_web_to_traffic_barrier_m=0.0,
        wheel_transverse_spacing_m=vehicle.wheel_transverse_spacing_m,
        design_lane_width_m=vehicle.design_lane_width_m,
    )

    assert round(interior_shear, 3) == 0.735
    assert rigid > 0.0
    assert round(exterior_moment, 3) == round(max(0.32914285714285707, rigid), 3)
    assert round(exterior_shear, 3) == round(max(0.32914285714285707, rigid), 3)
