import pytest

from bridge_design.codes.mtc_2018 import mtc_deck_overhang_knife_load_tn_m
from bridge_design.domain.barrier import BarrierDesignInputs, design_concrete_barrier
from bridge_design.domain.cantilever_slab import design_cantilever_slab
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

    controlling = result.controlling_strength
    assert controlling.combination_name == "RESISTENCIA I"
    assert controlling.combined_moment_tn_m < 0.0
    assert result.barrier_collision is not None
    assert result.barrier_collision.design_moment_tn_m > controlling.design_moment_tn_m
    assert result.flexural_steel.controlling_combination_name.startswith("EVENTO EXTREMO II")
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
