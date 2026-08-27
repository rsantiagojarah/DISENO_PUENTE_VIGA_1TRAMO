from bridge_design.cli.simple_neoprene_output import format_simple_neoprene_result
from bridge_design.domain.simple_neoprene_support import (
    ExternalSteelPlatePair,
    FixedBarGroup,
    SimpleNeopreneGeometry,
    SimpleSupportDemands,
    SimpleSupportInputs,
    climate_temperature,
    design_simple_neoprene_support,
)


def test_simple_neoprene_yaml_loader_rejects_unknown_support_type():
    import pytest

    from bridge_design.cli.simple_neoprene_yaml_inputs import (
        simple_neoprene_inputs_from_yaml,
        simple_neoprene_yaml_template,
    )

    data = simple_neoprene_yaml_template()
    data["tipo_apoyo"] = "DESCONOCIDO"

    with pytest.raises(ValueError, match="FIJO_BARRAS o MOVIL_PLACAS"):
        simple_neoprene_inputs_from_yaml(data)


def test_movable_plate_support_matches_steel_plate_detail():
    inputs = SimpleSupportInputs(
        support_type="MOVIL_PLACAS",
        geometry=SimpleNeopreneGeometry(60.0, 40.0, 5.0),
        demands=SimpleSupportDemands(
            r_dc_tn=20.0,
            r_dw_tn=1.18,
            r_pl_tn=0.0,
            r_ll_im_tn=29.42,
            pga=0.0,
            fpga=1.08,
            span_length_m=15.0,
            temperature=climate_temperature("costa", 20.0),
        ),
        plates=ExternalSteelPlatePair(thickness_cm=2.54),
        fc_kg_cm2=280.0,
    )

    result = design_simple_neoprene_support(inputs)
    report = format_simple_neoprene_result(result)

    assert result.overall_ok
    assert result.delta_thermal_cm > 0.0
    assert "MOVIL PLACAS" in report
    assert "Plancha superior" in report
    assert "ASTM A36" in report
    assert "Gmin" in report
    assert "Gmax" in report
    assert "9.14" in report
    assert "14.06" in report
    assert "PROCEDIMIENTO PASO A PASO" in report
    assert "H_pad movil" in report


def test_fixed_pin_support_uses_pin_interaction_only():
    inputs = SimpleSupportInputs(
        support_type="FIJO_BARRAS",
        geometry=SimpleNeopreneGeometry(60.0, 40.0, 5.0),
        demands=SimpleSupportDemands(
            r_dc_tn=20.0,
            r_dw_tn=1.18,
            r_pl_tn=0.0,
            r_ll_im_tn=29.42,
            h_long_tn=4.87,
            pga=0.48,
            fpga=1.08,
            span_length_m=15.0,
            temperature=climate_temperature("costa", 20.0),
        ),
        fixed_bars=FixedBarGroup(),
        fc_kg_cm2=280.0,
    )

    result = design_simple_neoprene_support(inputs)
    names = {check.name for check in result.checks}

    assert "Interaccion pasador corte-flexion" in names
    assert "Aplastamiento de camisa por pasador" not in names
    assert "Anclaje del pasador al pedestal" not in names
    assert result.inputs.demands.h_br_strength_tn == 1.75 * 4.87


def test_fixed_bar_support_can_pass_when_horizontal_demand_is_small():
    inputs = SimpleSupportInputs(
        support_type="FIJO_BARRAS",
        geometry=SimpleNeopreneGeometry(80.0, 50.0, 5.0),
        demands=SimpleSupportDemands(
            r_dc_tn=10.0,
            r_dw_tn=1.0,
            r_pl_tn=0.0,
            r_ll_im_tn=10.0,
            h_long_tn=0.0,
            pga=0.0,
            fpga=1.0,
            span_length_m=15.0,
            temperature=climate_temperature("costa", 20.0),
        ),
        fixed_bars=FixedBarGroup(),
        fc_kg_cm2=280.0,
    )

    result = design_simple_neoprene_support(inputs)

    assert result.overall_ok


def test_fixed_bar_support_accepts_six_bar_grid():
    inputs = SimpleSupportInputs(
        support_type="FIJO_BARRAS",
        geometry=SimpleNeopreneGeometry(65.0, 40.0, 5.0),
        demands=SimpleSupportDemands(
            r_dc_tn=20.0,
            r_dw_tn=1.2,
            r_pl_tn=1.81,
            r_ll_im_tn=29.4,
            h_long_tn=4.87,
            pga=0.48,
            fpga=1.08,
            span_length_m=15.0,
            temperature=climate_temperature("costa", 20.0),
        ),
        fixed_bars=FixedBarGroup(n_bars=6),
        fc_kg_cm2=280.0,
    )

    result = design_simple_neoprene_support(inputs)

    assert result.inputs.fixed_bars is not None
    assert result.inputs.fixed_bars.n_bars == 6
    assert any(check.name == "Interaccion pasador corte-flexion" for check in result.checks)


def test_fixed_pin_support_factors_nominal_braking_and_selects_governing_case():
    inputs = SimpleSupportInputs(
        support_type="FIJO_BARRAS",
        geometry=SimpleNeopreneGeometry(65.0, 40.0, 5.0),
        demands=SimpleSupportDemands(
            r_dc_tn=20.10,
            r_dw_tn=1.18,
            r_pl_tn=0.0,
            r_ll_im_tn=29.4,
            h_long_tn=1.96,
            pga=0.26,
            fpga=1.0,
            span_length_m=15.0,
            temperature=climate_temperature("costa", 20.0),
        ),
        fixed_bars=FixedBarGroup(n_bars=6, moment_arm_cm=5.0),
        fc_kg_cm2=280.0,
    )

    result = design_simple_neoprene_support(inputs)

    assert round(result.inputs.demands.h_br_strength_tn, 3) == 3.43
    assert round(result.inputs.demands.h_eq_long_tn, 3) == 5.533
    assert result.h_design_tn == result.inputs.demands.h_eq_long_tn
    assert result.h_design_case == "Evento Extremo I - sismo"
