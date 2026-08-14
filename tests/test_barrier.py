import pytest

from bridge_design.domain.barrier import (
    BarrierDesignInputs,
    BarrierImpactLoad,
    critical_yield_line_length_m,
    design_concrete_barrier,
    nominal_transverse_resistance_tn,
    rectangular_nominal_moment_tn_m,
)
from bridge_design.domain.materials import (
    ConcreteProperties,
    LinearWeightProperties,
    MaterialProperties,
    SteelProperties,
    SurfaceLayerProperties,
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


def test_rectangular_nominal_moment_returns_barrier_component_strength() -> None:
    moment, compression_depth = rectangular_nominal_moment_tn_m(
        steel_area_cm2=1.775,
        effective_depth_cm=10.58,
        concrete_width_cm=47.0,
        concrete_strength_kg_cm2=280.0,
        steel_yield_kg_cm2=4200.0,
    )

    assert round(compression_depth, 3) == 0.666
    assert round(moment, 3) == 0.764


def test_yield_line_helpers_match_aashto_segment_pattern() -> None:
    lc = critical_yield_line_length_m(
        height_m=0.85,
        distribution_length_m=1.07,
        mb_tn_m=0.0,
        mw_tn_m=1.88,
        mc_tn_m=5.64,
        pattern="segment",
    )
    rw = nominal_transverse_resistance_tn(
        height_m=0.85,
        distribution_length_m=1.07,
        critical_length_m=lc,
        mb_tn_m=0.0,
        mw_tn_m=1.88,
        mc_tn_m=5.64,
        pattern="segment",
    )

    assert round(lc, 2) == 2.13
    assert round(rw, 1) == 28.3


def test_new_jersey_barrier_design_returns_requested_checks() -> None:
    result = design_concrete_barrier(
        inputs=BarrierDesignInputs(),
        materials=_materials(),
    )

    assert result.flexure.mw_tn_m == pytest.approx(1.86, abs=0.02)
    assert result.flexure.mc_tn_m == pytest.approx(5.64, abs=0.02)
    assert result.yield_line.critical_length_m == pytest.approx(2.13, abs=0.01)
    assert result.yield_line.nominal_transverse_resistance_tn == pytest.approx(28.3, abs=0.1)
    assert result.yield_line.resistance_status == "OK"
    assert result.shear_transfer.acting_shear_tn_m == pytest.approx(7.38, abs=0.02)
    assert result.shear_transfer.nominal_shear_tn_m == pytest.approx(38.2, abs=0.1)
    assert result.shear_transfer.status == "OK"
    assert result.dowel.required_avf_cm2_m == pytest.approx(3.14, abs=0.01)
    assert result.dowel.provided_avf_cm2_m == pytest.approx(7.59, abs=0.01)
    assert result.dowel.status == "OK"
    assert result.development.required_ldh_cm == pytest.approx(16.8, abs=0.2)
    assert result.development.status == "OK"


def test_barrier_design_flags_insufficient_transverse_resistance() -> None:
    result = design_concrete_barrier(
        inputs=BarrierDesignInputs(
            impact_load=BarrierImpactLoad(transverse_force_tn=35.0),
        ),
        materials=_materials(),
    )

    assert result.yield_line.resistance_status == "NO CUMPLE"
