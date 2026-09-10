from dataclasses import replace

import pytest

from bridge_design.codes.mtc_2018 import mtc_deck_overhang_knife_load_tn_m
from bridge_design.domain.barrier import BarrierDesignInputs, design_concrete_barrier
from bridge_design.domain.cantilever_slab import (
    CantileverSlabApplicabilityError,
    design_cantilever_slab,
)
from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel
from bridge_design.domain.materials import (
    ConcreteProperties,
    LinearWeightProperties,
    MaterialProperties,
    SteelProperties,
    SurfaceLayerProperties,
)
from bridge_design.domain.transverse_slab import (
    TransverseLoadLayout,
    TransverseSlabGeometry,
    solve_transverse_slab_design,
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


def _geometry() -> TransverseSlabGeometry:
    return TransverseSlabGeometry(
        girder_spacing_m=2.10,
        overhang_m=0.825,
        girder_count=4,
        slab_thickness_m=0.20,
        girder_total_height_m=1.20,
        girder_width_m=0.30,
    )


def _layout() -> TransverseLoadLayout:
    return TransverseLoadLayout(
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


def test_mtc_deck_overhang_knife_load_converts_one_kip_per_ft() -> None:
    assert mtc_deck_overhang_knife_load_tn_m() == pytest.approx(1.488, abs=0.001)


@pytest.mark.parametrize("start, classification, applied", [
    (0.1, "SOBRE VOLADIZO", True),
    (0.85, "SOBRE VIGA", False),
    (1.7, "SOBRE LOSA INTERIOR", False),
    (0.6, "BASE CRUZA ZONAS", False),
])
def test_collision_uses_complete_barrier_base(start, classification, applied):
    geometry = replace(_geometry(), overhang_m=1.0, girder_width_m=0.5)
    materials = _materials()
    layout = replace(_layout(), barrier_left_m=start, barrier_width_m=0.375)
    live = LiveLoads(PedestrianLoad.mtc_sidewalk_default(), VehicleLoadModel.mtc_hl93_default())
    barrier = design_concrete_barrier(BarrierDesignInputs(), materials)
    result = design_cantilever_slab(geometry, materials, live, layout, barrier)
    assert any(classification in note for note in result.applicability_notes)
    assert (result.barrier_collision is not None) == applied
    if not applied:
        baseline = design_cantilever_slab(geometry, materials, live, layout)
        assert result.flexural_steel == baseline.flexural_steel
        assert not result.overall_ok
        if classification == "SOBRE LOSA INTERIOR":
            assert result.interior_collision is not None
            assert not any("Ft=" in note for note in result.applicability_notes)
        else:
            assert any("Ft=" in note for note in result.applicability_notes)


def test_cantilever_slab_design_returns_loads_steel_and_development() -> None:
    materials = _materials()
    result = design_cantilever_slab(
        geometry=_geometry(),
        materials=materials,
        live_loads=LiveLoads(
            pedestrian=PedestrianLoad.mtc_sidewalk_default(),
            vehicular=VehicleLoadModel.mtc_hl93_default(),
        ),
        layout=_layout(),
        barrier_result=design_concrete_barrier(BarrierDesignInputs(), materials),
    )

    by_label = {effect.label: effect for effect in result.load_effects}
    assert by_label["DC - peso propio losa"].root_moment_tn_m == pytest.approx(-0.163, abs=0.001)
    assert by_label["DC - vereda sobre volado"].root_moment_tn_m == pytest.approx(-0.163, abs=0.001)
    assert by_label["DC - baranda"].root_moment_tn_m == pytest.approx(-0.070, abs=0.001)
    assert "LL+IM - cuchilla voladizo" not in by_label
    assert result.traffic_face_to_exterior_girder_m == pytest.approx(-0.25)
    assert result.vehicular_load_method == "Ruedas reales en el analisis transversal"

    controlling = result.controlling_strength
    assert controlling.combination_name == "RESISTENCIA I"
    assert controlling.combined_moment_tn_m < 0.0
    assert result.barrier_collision is None
    assert not result.overall_ok
    assert any("PENDIENTE" in note for note in result.applicability_notes)
    assert result.flexural_steel.controlling_combination_name == "RESISTENCIA I"
    assert result.flexural_steel.required_area_cm2_m > 0.0
    assert result.shear.combined_shear_tn > 0.0
    assert result.shear.phi_vc_tn > result.shear.combined_shear_tn
    assert result.shear.status == "CUMPLE"
    assert result.crack_control.maximum_spacing_m > 0.0
    assert result.crack_control.steel_stress_limit_kg_cm2 == pytest.approx(
        0.60 * _materials().steel.yield_strength_kg_cm2
    )
    assert result.crack_control.status == (
        "CUMPLE"
        if (
            result.crack_control.stress_status == "CUMPLE"
            and result.crack_control.spacing_status == "CUMPLE"
        )
        else "NO CUMPLE"
    )
    assert result.development.required_development_length_cm >= 30.48
    assert result.development.total_additional_bar_length_m > _geometry().overhang_m
    assert result.applicability_notes


def test_vehicle_inside_exterior_girder_is_kept_in_transverse_analysis() -> None:
    live_loads = LiveLoads(
        pedestrian=PedestrianLoad.mtc_sidewalk_default(),
        vehicular=VehicleLoadModel.mtc_hl93_default(),
    )
    cantilever = design_cantilever_slab(
        geometry=_geometry(),
        materials=_materials(),
        live_loads=live_loads,
        layout=_layout(),
    )
    transverse = solve_transverse_slab_design(
        geometry=_geometry(),
        materials=_materials(),
        live_loads=live_loads,
        layout=_layout(),
    )

    assert not any(effect.group == "LL_IM" for effect in cantilever.load_effects)
    assert transverse.ll_im_envelope.max_positive_moment_tn_m > 0.0
    assert transverse.ll_im_envelope.max_negative_moment_tn_m < 0.0


def test_knife_applicability_uses_traffic_face_to_girder_not_full_overhang() -> None:
    geometry = replace(_geometry(), overhang_m=2.0)
    layout = replace(_layout(), barrier_left_m=0.25, barrier_width_m=0.25)
    result = design_cantilever_slab(
        geometry=geometry,
        materials=_materials(),
        live_loads=LiveLoads(
            pedestrian=PedestrianLoad.mtc_sidewalk_default(),
            vehicular=VehicleLoadModel.mtc_hl93_default(),
        ),
        layout=layout,
    )

    assert result.traffic_face_to_exterior_girder_m == pytest.approx(1.50)
    assert any(effect.group == "LL_IM" for effect in result.load_effects)
    assert result.vehicular_load_method.startswith("Cuchilla equivalente")


def test_design_stops_when_traffic_face_to_girder_exceeds_knife_limit() -> None:
    geometry = replace(_geometry(), overhang_m=2.50)
    layout = replace(_layout(), barrier_left_m=0.25, barrier_width_m=0.25)

    with pytest.raises(CantileverSlabApplicabilityError, match="D=2.000 m"):
        design_cantilever_slab(
            geometry=geometry,
            materials=_materials(),
            live_loads=LiveLoads(
                pedestrian=PedestrianLoad.mtc_sidewalk_default(),
                vehicular=VehicleLoadModel.mtc_hl93_default(),
            ),
            layout=layout,
        )
