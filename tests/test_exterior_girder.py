import pytest

from bridge_design.domain.exterior_girder import (
    ExteriorGirderGeometry,
    combine_exterior_girder_moments,
    design_exterior_girder_reinforcement,
    design_exterior_girder_shear,
    exterior_asphalt_tributary_width_m,
    review_exterior_girder_crack_control,
    review_exterior_girder_fatigue,
    solve_exterior_girder_design,
    verify_exterior_girder_service_stresses,
)
from bridge_design.domain.interior_girder import DiaphragmGeometry
from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel
from bridge_design.domain.materials import (
    ConcreteProperties,
    LinearWeightProperties,
    MaterialProperties,
    SteelProperties,
    SurfaceLayerProperties,
)
from bridge_design.domain.transverse_slab import TransverseLoadLayout, TransverseSlabGeometry
from bridge_design.cli.input_prompts import _default_exterior_de_m


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


def _geometry() -> ExteriorGirderGeometry:
    return ExteriorGirderGeometry(
        span_length_m=15.0,
        girder_spacing_m=2.10,
        deck_overhang_m=0.825,
        slab_thickness_m=0.20,
        girder_total_height_m=1.20,
        web_width_m=0.30,
        exterior_web_to_traffic_barrier_m=-0.25,
        sidewalk_width_m=0.825,
        asphalt_tributary_width_m=exterior_asphalt_tributary_width_m(
            deck_overhang_m=0.825,
            girder_spacing_m=2.10,
            asphalt_start_m=1.075,
            asphalt_end_m=6.875,
        ),
        girder_count=4,
        diaphragms=(
            DiaphragmGeometry(3.75, 0.25, 1.10, 1.875),
            DiaphragmGeometry(7.50, 0.25, 1.10, 1.875),
            DiaphragmGeometry(11.25, 0.25, 1.10, 1.875),
        ),
        moving_load_step_m=0.50,
        moment_sample_step_m=0.50,
    )


def test_exterior_asphalt_tributary_width_uses_overlap_with_tributary_strip() -> None:
    assert round(_geometry().asphalt_tributary_width_m, 3) == 0.800


def test_default_exterior_de_uses_traffic_side_barrier_face_with_mtc_sign() -> None:
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

    assert _default_exterior_de_m(geometry, layout) == -0.25


def test_exterior_girder_solves_loads_strength_flexure_and_shear() -> None:
    analysis = solve_exterior_girder_design(
        geometry=_geometry(),
        materials=_materials(),
        live_loads=LiveLoads(
            pedestrian=PedestrianLoad.mtc_sidewalk_default(),
            vehicular=VehicleLoadModel.mtc_hl93_default(),
        ),
    )

    assert analysis.dc.max_positive_moment_tn_m > 0.0
    assert analysis.dw.max_positive_moment_tn_m > 0.0
    assert analysis.pl.max_positive_moment_tn_m > 0.0
    assert analysis.ll_im_envelope.max_positive_moment_tn_m > 0.0
    assert analysis.distribution_factor_g > 0.0
    assert analysis.shear_distribution_factor_g > 0.0
    assert round(analysis.fatigue_truck.distribution_factor_g, 3) == 0.447
    assert analysis.fatigue_truck.distribution_factor_g < analysis.distribution_factor_g
    reactions = dict(analysis.truck_ll_im.support_reactions_tn)
    assert round(reactions["Fijo"], 3) == 14.403
    assert round(reactions["Movil"], 3) == 16.543

    combined = combine_exterior_girder_moments(analysis)
    strength = next(row for row in combined if row.combination_name == "RESISTENCIA I")
    assert strength.pl_moment_tn_m > 0.0
    assert strength.combined_moment_tn_m > analysis.dc.max_positive_moment_tn_m

    reinforcement = design_exterior_girder_reinforcement(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
    )
    assert reinforcement.main.required_area_cm2 > 0.0
    assert reinforcement.main.placement_options.recommended is not None
    assert reinforcement.skin.required_total_area_cm2_per_face <= (
        reinforcement.skin.maximum_total_area_cm2_per_face + 1e-9
    )
    assert reinforcement.skin.maximum_spacing_m == pytest.approx(
        min(reinforcement.skin.effective_depth_cm / 600.0, 0.30)
    )

    crack = review_exterior_girder_crack_control(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
    )
    assert crack.main.maximum_spacing_m > 0.0

    fatigue = review_exterior_girder_fatigue(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
    )
    assert fatigue.stress_range_kg_cm2 > 0.0

    stresses = verify_exterior_girder_service_stresses(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
    )
    assert stresses.concrete_compression_kg_cm2 > 0.0
    assert stresses.steel_tension_kg_cm2 > 0.0

    shear = design_exterior_girder_shear(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
    )
    assert shear.controlling_shear.combined_shear_tn > 0.0
    assert shear.required_av_cm2_m >= shear.minimum_av_cm2_m
    assert shear.recommended is not None


def test_exterior_girder_increases_main_bar_layers_when_required() -> None:
    demanding_geometry = ExteriorGirderGeometry(
        **{
            **_geometry().__dict__,
            "exterior_web_to_traffic_barrier_m": 0.695,
        }
    )
    analysis = solve_exterior_girder_design(
        geometry=demanding_geometry,
        materials=_materials(),
        live_loads=LiveLoads(
            pedestrian=PedestrianLoad.mtc_sidewalk_default(),
            vehicular=VehicleLoadModel.mtc_hl93_default(),
        ),
    )
    reinforcement = design_exterior_girder_reinforcement(
        geometry=demanding_geometry,
        materials=_materials(),
        analysis=analysis,
    )

    assert reinforcement.parameters.maximum_main_bar_layers > 4
    assert reinforcement.main.placement_options.recommended is not None
