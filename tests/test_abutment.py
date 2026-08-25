import re

import pytest
from bridge_design.cli.abutment_input_prompts import _collect_materials, collect_abutment_key
from bridge_design.domain.abutment import (
    AbutmentGeometryInputs,
    AbutmentInputs,
    AbutmentKeyInputs,
    LoadComponent,
    AbutmentLoadInputs,
    AbutmentSoilInputs,
    DEFAULT_LOAD_FACTORS,
    equivalent_vehicular_surcharge_height_m,
    rankine_passive_coefficient,
    solve_abutment_design,
)


def test_default_abutment_loads_match_reference_workbook() -> None:
    result = solve_abutment_design()

    assert result.dc_self_weight_tn_m == pytest.approx(20.016, abs=1e-3)
    assert result.dc_self_x_m == pytest.approx(2.135806, abs=1e-6)
    assert result.ev_weight_tn_m == pytest.approx(30.057176, abs=1e-6)
    assert result.ev_x_m == pytest.approx(3.327421, abs=1e-6)
    assert result.pressures.ka == pytest.approx(1.0 / 3.0)
    assert result.pressures.k_ae == pytest.approx(0.456615, abs=1e-6)
    assert result.pressures.lsy_tn_m == pytest.approx(2.71425, abs=1e-6)
    assert result.pressures.lsx_tn_m == pytest.approx(2.695, abs=1e-6)
    assert result.pressures.eh_tn_m == pytest.approx(15.720833, abs=1e-6)
    assert result.pressures.eq_terr_tn_m == pytest.approx(5.814250, abs=1e-6)


def test_abutment_report_omits_formula_table_and_bar_note_column() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result

    report = format_abutment_design_result(solve_abutment_design())

    assert "2. FORMULAS DE AREAS Y BRAZOS DEL MODELO PDF" not in report
    assert "Area PDF" not in report
    assert "|         Nota        |" not in report
    assert "CUADRO DE DETALLE DE ACERO" in report


def test_abutment_report_enumerates_titles_and_subtitles() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result

    report = format_abutment_design_result(solve_abutment_design())

    assert "1. DISENO DE ESTRIBO TIPO CANTILEVER" in report
    assert "1.1. DATOS INGRESADOS Y CONSIDERADOS" in report
    assert "1.1.1. DATOS PRINCIPALES" in report
    assert "1.2. ESTRIBO CON PUENTE" in report
    assert "1.2.1.1. CARGAS DC" in report
    assert "1.5.1.2. CORTE DE ACERO PRINCIPAL DE PANTALLA" in report


def test_abutment_report_shows_operation_columns_for_pressures_and_stability() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result

    report = format_abutment_design_result(solve_abutment_design())

    assert "Operacion matematica" in report
    assert "0.5*0.3333" in report
    assert "sum(gamma_i*P_i vertical)" in report
    assert "Vu/(B-2e)" not in report


def test_abutment_report_develops_required_steel_origin() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result

    report = format_abutment_design_result(solve_abutment_design())

    assert "Mcr" in report
    assert "1.33Mu" in report
    assert "Momento minimo adoptado" in report
    assert "min(Mcr, 1.33Mu)" in report
    assert "As por capacidad minima" in report
    assert "Operacion As requerido" in report
    assert "max(As flexion, As temperatura, As capacidad minima)" in report
    assert "Control As requerido" in report


def test_abutment_report_separates_sliding_without_and_with_key() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result

    report = format_abutment_design_result(solve_abutment_design())

    assert "Deslizamiento sin diente" in report
    assert "Deslizamiento con diente" in report
    assert "27.754 >= 28.298" in report
    assert "29.718 >= 28.298" in report


def test_abutment_reinforcement_option_tables_group_stem_before_footing() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_reinforcement_option_tables

    report = format_abutment_reinforcement_option_tables(solve_abutment_design())
    titles = [
        re.sub(r"^\d+(?:\.\d+)*\.\s+", "", line.strip("| ")).strip()
        for line in report.splitlines()
        if "OPCIONES - " in line
    ]

    assert titles == [
        "OPCIONES - Pantalla",
        "OPCIONES - Pantalla - vertical exterior",
        "OPCIONES - Pantalla - horizontal relleno",
        "OPCIONES - Pantalla - horizontal exterior",
        "OPCIONES - Zapata - talon superior",
        "OPCIONES - Zapata - puntera inferior",
        "OPCIONES - Zapata - transversal superior",
        "OPCIONES - Zapata - transversal inferior",
        "OPCIONES - Diente de concreto",
    ]
    assert "1.1.1. OPCION DE CORTE DE ACERO PRINCIPAL DE PANTALLA" in report


def test_default_abutment_stability_matches_reference_workbook() -> None:
    result = solve_abutment_design()
    res_ia, res_ib, extreme = result.with_bridge
    service = result.service_with_bridge[0]

    assert res_ia.vu_tn_m == pytest.approx(60.041576, abs=1e-6)
    assert res_ia.hu_tn_m == pytest.approx(31.78, abs=1e-6)
    assert res_ia.overturning_moment_tn_m_m == pytest.approx(102.175792, abs=1e-6)
    assert res_ia.qmax_kg_cm2 == pytest.approx(4.197230, abs=1e-6)
    assert res_ia.qmin_kg_cm2 == pytest.approx(0.0, abs=1e-6)
    assert res_ia.qmin_linear_kg_cm2 == pytest.approx(-0.999691, abs=1e-6)
    assert res_ia.eccentricity_limit_m == pytest.approx(result.inputs.geometry.footing_width_m / 3.0)
    assert res_ia.contact_type == "Parcial triangular"
    assert res_ia.effective_width_m == pytest.approx(1.907340, abs=1e-6)
    assert res_ia.geotechnical_pressure_kg_cm2 == pytest.approx(3.147922, abs=1e-6)
    assert res_ia.bearing_status == "OK"
    assert res_ia.sliding_status == "OK"
    assert res_ib.vu_tn_m == pytest.approx(104.661626, abs=1e-6)
    assert res_ib.geotechnical_pressure_kg_cm2 == pytest.approx(3.358628, abs=1e-6)
    assert res_ib.bearing_status == "OK"
    assert extreme.hu_tn_m == pytest.approx(33.352170, abs=1e-6)
    assert service.name == "Servicio I"
    assert service.contact_type == "Completo"
    assert service.contact_length_ratio == pytest.approx(1.0)
    assert service.qmin_linear_kg_cm2 == pytest.approx(0.279078, abs=1e-6)
    assert service.bearing_status == "OK"


def test_abutment_stability_report_includes_qmin_and_central_third_limit() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result

    report = format_abutment_design_result(solve_abutment_design())

    assert "qmin" in report
    assert "Lc/B" in report
    assert "Parcial triangular" in report
    assert "CRITERIO GEOTECNICO Y ESTRUCTURAL DE ZAPATA" in report
    assert "Servicio I" in report
    assert "Meyerhof" in report


def test_strength_allows_partial_triangular_contact_toward_toe_and_heel() -> None:
    from bridge_design.domain.abutment import _contact_pressure_tn_m2_at_x, _stability_state

    geometry = AbutmentGeometryInputs(footing_width_m=4.70)
    inputs = AbutmentInputs(
        geometry=geometry,
        soil=AbutmentSoilInputs(allowable_bearing_kg_cm2=10.0),
        key=AbutmentKeyInputs(enabled=False),
    )
    factors = DEFAULT_LOAD_FACTORS[0]
    toe_state = _stability_state(inputs, factors, (LoadComponent("P", "DC", 100.0, 1.0),), (), None)
    heel_state = _stability_state(inputs, factors, (LoadComponent("P", "DC", 100.0, 3.7),), (), None)

    assert toe_state.contact_type == "Parcial triangular"
    assert toe_state.contact_length_ratio == pytest.approx(3.0 / 4.70)
    assert toe_state.bearing_status == "OK"
    assert _contact_pressure_tn_m2_at_x(geometry, toe_state, 0.0) == pytest.approx(60.0)
    assert _contact_pressure_tn_m2_at_x(geometry, toe_state, 4.70) == pytest.approx(0.0)
    assert heel_state.contact_type == "Parcial triangular"
    assert heel_state.contact_length_ratio == pytest.approx(3.0 / 4.70)
    assert heel_state.bearing_status == "OK"
    assert _contact_pressure_tn_m2_at_x(geometry, heel_state, 0.0) == pytest.approx(0.0)
    assert _contact_pressure_tn_m2_at_x(geometry, heel_state, 4.70) == pytest.approx(60.0)


def test_partial_contact_length_is_structural_diagnostic_not_bearing_failure() -> None:
    from bridge_design.domain.abutment import _stability_state

    inputs = AbutmentInputs(
        geometry=AbutmentGeometryInputs(footing_width_m=4.70),
        soil=AbutmentSoilInputs(allowable_bearing_kg_cm2=10.0),
        key=AbutmentKeyInputs(enabled=False),
    )
    state = _stability_state(inputs, DEFAULT_LOAD_FACTORS[0], (LoadComponent("P", "DC", 100.0, 0.50),), (), None)

    assert state.contact_type == "Parcial triangular"
    assert state.contact_length_ratio < state.minimum_contact_length_ratio
    assert state.geotechnical_pressure_kg_cm2 <= state.q_allow_kg_cm2
    assert state.bearing_status == "OK"


def test_service_bearing_uses_meyerhof_even_when_structural_qmin_is_negative() -> None:
    from bridge_design.domain.abutment import _stability_state

    inputs = AbutmentInputs(
        geometry=AbutmentGeometryInputs(footing_width_m=4.70),
        soil=AbutmentSoilInputs(allowable_bearing_kg_cm2=10.0),
        key=AbutmentKeyInputs(enabled=False),
    )
    state = _stability_state(inputs, DEFAULT_LOAD_FACTORS[3], (LoadComponent("P", "DC", 100.0, 1.0),), (), None)

    assert state.name == "Servicio I"
    assert state.minimum_contact_length_ratio == pytest.approx(1.0)
    assert state.qmin_linear_kg_cm2 < 0.0
    assert state.geotechnical_pressure_kg_cm2 <= state.q_allow_kg_cm2
    assert state.bearing_status == "OK"


def test_bearing_fails_when_qmax_exceeds_factored_capacity_even_with_full_contact() -> None:
    from bridge_design.domain.abutment import _stability_state

    inputs = AbutmentInputs(
        geometry=AbutmentGeometryInputs(footing_width_m=4.70),
        soil=AbutmentSoilInputs(allowable_bearing_kg_cm2=0.10),
        key=AbutmentKeyInputs(enabled=False),
    )
    state = _stability_state(inputs, DEFAULT_LOAD_FACTORS[0], (LoadComponent("P", "DC", 100.0, 2.35),), (), None)

    assert state.contact_type == "Completo"
    assert state.contact_length_ratio == pytest.approx(1.0)
    assert state.geotechnical_pressure_kg_cm2 > state.q_allow_kg_cm2
    assert state.bearing_status == "NO"


def test_abutment_recommends_footing_width_when_meyerhof_pressure_fails() -> None:
    result = solve_abutment_design(
        AbutmentInputs(
            soil=AbutmentSoilInputs(allowable_bearing_kg_cm2=2.0),
            key=AbutmentKeyInputs(enabled=False),
        )
    )

    recommendation = result.footing_width_recommendation

    assert recommendation is not None
    assert recommendation.current_width_m == pytest.approx(4.70)
    assert recommendation.recommended_width_m == pytest.approx(5.70)
    assert recommendation.controlling_case == "CON PUENTE - Servicio I"
    assert recommendation.current_geotechnical_pressure_kg_cm2 > 2.0
    assert recommendation.recommended_max_geotechnical_pressure_kg_cm2 <= 3.30
    assert recommendation.all_bearing_ok_at_recommended_width is True
    assert recommendation.all_overturning_ok_at_recommended_width is True
    assert recommendation.found_compliant_width is True


def test_abutment_report_includes_footing_width_recommendation() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result

    report = format_abutment_design_result(
        solve_abutment_design(
            AbutmentInputs(
                soil=AbutmentSoilInputs(allowable_bearing_kg_cm2=2.0),
                key=AbutmentKeyInputs(enabled=False),
            )
        )
    )

    assert "RECOMENDACION DE ANCHO DE ZAPATA" in report
    assert "Ancho recomendado B" in report
    assert "5.700 m" in report


def test_abutment_adopts_recommended_footing_width_before_reinforcement(monkeypatch) -> None:
    from bridge_design.abutment_main import _consider_footing_width_when_contact_fails

    inputs = AbutmentInputs(
        soil=AbutmentSoilInputs(allowable_bearing_kg_cm2=2.0),
        key=AbutmentKeyInputs(enabled=False),
    )
    preliminary = solve_abutment_design(inputs)
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    updated_inputs, updated_result = _consider_footing_width_when_contact_fails(inputs, preliminary)

    assert updated_inputs.geometry.footing_width_m == pytest.approx(5.70)
    assert updated_result.footing_width_recommendation is None
    assert any("Adoptar B recomendado = 5.70 m" in prompt for prompt in prompts)


def _abutment_inputs_overturning_controls_footing_width() -> AbutmentInputs:
    return AbutmentInputs(
        geometry=AbutmentGeometryInputs(footing_width_m=4.00, backfill_step_width_m=0.0),
        soil=AbutmentSoilInputs(allowable_bearing_kg_cm2=10.0),
        key=AbutmentKeyInputs(enabled=False),
    )


def test_abutment_recommends_footing_width_when_overturning_fails() -> None:
    result = solve_abutment_design(_abutment_inputs_overturning_controls_footing_width())
    recommendation = result.footing_width_recommendation

    assert all(state.bearing_status == "OK" for state in result.with_bridge)
    assert any(state.overturning_status == "NO" for state in result.with_bridge)
    assert recommendation is not None
    assert recommendation.current_width_m == pytest.approx(4.00)
    assert recommendation.recommended_width_m == pytest.approx(4.45)
    assert recommendation.controlling_case == "CON PUENTE - Resistencia Ia"
    assert recommendation.all_bearing_ok_at_recommended_width is True
    assert recommendation.all_overturning_ok_at_recommended_width is True
    assert recommendation.found_compliant_width is True

    adopted = solve_abutment_design(
        AbutmentInputs(
            geometry=AbutmentGeometryInputs(footing_width_m=4.45, backfill_step_width_m=0.0),
            soil=AbutmentSoilInputs(allowable_bearing_kg_cm2=10.0),
            key=AbutmentKeyInputs(enabled=False),
        )
    )
    assert adopted.footing_width_recommendation is None
    assert all(
        state.overturning_status == "OK" and state.bearing_status == "OK"
        for state in adopted.with_bridge
        + adopted.without_bridge
        + adopted.service_with_bridge
        + adopted.service_without_bridge
    )


def test_abutment_adopts_footing_width_when_overturning_fails(monkeypatch) -> None:
    from bridge_design.abutment_main import _consider_footing_width_when_contact_fails

    inputs = _abutment_inputs_overturning_controls_footing_width()
    preliminary = solve_abutment_design(inputs)
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    updated_inputs, updated_result = _consider_footing_width_when_contact_fails(inputs, preliminary)

    assert updated_inputs.geometry.footing_width_m == pytest.approx(4.45)
    assert updated_result.footing_width_recommendation is None
    assert all(
        state.overturning_status == "OK" and state.bearing_status == "OK"
        for state in updated_result.with_bridge + updated_result.service_with_bridge
    )
    assert any("Adoptar B recomendado = 4.45 m" in prompt for prompt in prompts)


def _abutment_inputs_service_pressure_cannot_be_fixed_by_width() -> AbutmentInputs:
    return AbutmentInputs(
        geometry=AbutmentGeometryInputs(
            retained_height_m=11.0,
            footing_width_m=10.45,
            footing_thickness_m=1.10,
            toe_length_m=2.20,
            lower_stem_thickness_m=1.00,
            upper_stem_thickness_m=0.40,
            front_soil_depth_m=1.50,
        ),
        soil=AbutmentSoilInputs(allowable_bearing_kg_cm2=2.0, friction_angle_deg=28.0),
        key=AbutmentKeyInputs(enabled=False),
    )


def test_abutment_reports_footing_search_when_service_pressure_cannot_be_fixed() -> None:
    result = solve_abutment_design(_abutment_inputs_service_pressure_cannot_be_fixed_by_width())
    recommendation = result.footing_width_recommendation
    service = result.service_with_bridge[0]

    assert service.bearing_status == "NO"
    assert recommendation is not None
    assert recommendation.found_compliant_width is False
    assert recommendation.recommended_width_m == pytest.approx(10.45)
    assert recommendation.controlling_case == "CON PUENTE - Servicio I"
    assert recommendation.search_max_width_m == pytest.approx(max(10.45 + 20.0, 10.45 * 4.0))


def test_abutment_cli_shows_footing_search_when_no_width_complies(monkeypatch, capsys) -> None:
    from bridge_design.abutment_main import _consider_footing_width_when_contact_fails

    inputs = _abutment_inputs_service_pressure_cannot_be_fixed_by_width()
    preliminary = solve_abutment_design(inputs)
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    updated_inputs, updated_result = _consider_footing_width_when_contact_fails(inputs, preliminary)
    captured = capsys.readouterr()

    assert updated_inputs.geometry.footing_width_m == pytest.approx(10.45)
    assert updated_result.footing_width_recommendation is not None
    assert updated_result.footing_width_recommendation.found_compliant_width is False
    assert prompts == []
    assert "ningun ancho cumple" in captured.out
    assert "qadm" in captured.out


def test_abutment_report_includes_unsuccessful_footing_width_search() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result

    report = format_abutment_design_result(
        solve_abutment_design(_abutment_inputs_service_pressure_cannot_be_fixed_by_width())
    )

    assert "RECOMENDACION DE ANCHO DE ZAPATA" in report
    assert "no se encontro B que cumpla" in report
    assert "CON PUENTE - Servicio I" in report


def test_shear_key_uses_front_soil_height_for_trapezoidal_passive_pressure() -> None:
    result = solve_abutment_design()
    res_ia, res_ib, extreme = result.without_bridge

    assert res_ia.sliding_status == "NO"
    assert result.key is not None
    assert result.key.passive_coefficient_prime == pytest.approx(3.0)
    assert result.key.top_pressure_tn_m2 == pytest.approx(8.6625, abs=1e-6)
    assert result.key.bottom_pressure_tn_m2 == pytest.approx(10.9725, abs=1e-6)
    assert result.key.upper_front_passive_resistance_tn_m == pytest.approx(0.0)
    assert result.key.total_passive_resistance_tn_m == pytest.approx(result.key.passive_resistance_tn_m)
    assert res_ia.key_resistance_tn_m == pytest.approx(29.717638, abs=1e-6)
    assert res_ia.sliding_with_key_status == "OK"
    assert res_ib.sliding_with_key_status == "OK"
    assert extreme.sliding_with_key_status == "OK"


def test_shear_key_ignores_legacy_passive_fill_and_uses_front_soil_height() -> None:
    result = solve_abutment_design(
        AbutmentInputs(
            geometry=AbutmentGeometryInputs(front_soil_depth_m=2.50),
            key=AbutmentKeyInputs(passive_soil_height_m=0.0),
        )
    )
    res_ia = result.without_bridge[0]

    assert result.key is not None
    assert result.key.top_pressure_tn_m2 == pytest.approx(14.4375, abs=1e-6)
    assert result.key.bottom_pressure_tn_m2 == pytest.approx(16.7475, abs=1e-6)
    assert res_ia.sliding_with_key_status == "OK"


def test_shear_key_is_triangular_when_front_soil_height_is_zero() -> None:
    result = solve_abutment_design(
        AbutmentInputs(
            geometry=AbutmentGeometryInputs(front_soil_depth_m=0.0),
        )
    )

    assert result.key is not None
    assert result.key.top_pressure_tn_m2 == pytest.approx(0.0)
    assert result.key.bottom_pressure_tn_m2 > 0.0


def test_upper_front_fill_passive_is_optional_and_adds_to_sliding_only() -> None:
    base_result = solve_abutment_design()
    upper_result = solve_abutment_design(
        AbutmentInputs(
            key=AbutmentKeyInputs(consider_upper_front_passive=True),
        )
    )
    base_state = base_result.without_bridge[0]
    upper_state = upper_result.without_bridge[0]

    assert upper_result.key is not None
    assert base_result.key is not None
    expected_upper_passive = 0.5 * 3.0 * 1.925 * 1.50**2.0
    assert upper_result.key.upper_front_passive_resistance_tn_m == pytest.approx(expected_upper_passive)
    assert upper_result.key.passive_resistance_tn_m == pytest.approx(base_result.key.passive_resistance_tn_m)
    assert upper_result.key.total_passive_resistance_tn_m == pytest.approx(
        base_result.key.passive_resistance_tn_m + expected_upper_passive
    )
    assert upper_state.key_resistance_tn_m == pytest.approx(
        base_state.key_resistance_tn_m + 0.50 * expected_upper_passive
    )
    assert upper_result.key_design is not None
    assert base_result.key_design is not None
    assert upper_result.key_design.controlling_moment_tn_m_m == pytest.approx(
        base_result.key_design.controlling_moment_tn_m_m
    )


def test_abutment_design_accepts_zero_optional_pdf_dimensions() -> None:
    result = solve_abutment_design(
        AbutmentInputs(
            geometry=AbutmentGeometryInputs(
                retained_height_m=7.8,
                bridge_length_m=15.0,
                footing_width_m=6.0,
                footing_thickness_m=0.95,
                toe_length_m=2.1,
                lower_stem_thickness_m=0.95,
                upper_stem_thickness_m=0.95,
                front_soil_depth_m=2.5,
                small_batter_width_m=0.0,
                backfill_step_width_m=0.0,
                bearing_seat_length_m=0.0,
                seat_wall_width_m=0.0,
                seat_block_height_m=0.0,
                backwall_drop_m=0.0,
                backwall_taper_height_m=0.0,
            )
        )
    )

    assert result.dc_self_weight_tn_m > 0.0
    assert result.ev_weight_tn_m > 0.0
    assert result.with_bridge[0].bearing_status in {"OK", "NO"}


def test_default_structural_design_matches_reference_workbook() -> None:
    result = solve_abutment_design()

    assert result.stem_design.controlling_moment_tn_m_m == pytest.approx(72.436292, abs=1e-6)
    assert result.stem_design.strength_as_cm2_m == pytest.approx(21.148141, abs=1e-6)
    assert result.stem_design.selected_bar_label == '3/4"'
    assert result.stem_design.selected_spacing_m == pytest.approx(0.125)
    assert result.stem_design.shear_demand_tn_m == pytest.approx(24.209938, abs=1e-6)
    assert result.stem_design.shear_resistance_tn_m == pytest.approx(32.954965, abs=1e-6)

    assert result.heel_design.controlling_moment_tn_m_m == pytest.approx(73.350916, abs=1e-6)
    assert result.heel_design.strength_as_cm2_m == pytest.approx(19.553577, abs=1e-6)
    assert result.heel_design.minimum_as_cm2_m == pytest.approx(17.176207, abs=1e-6)
    assert result.heel_design.required_as_cm2_m == pytest.approx(19.553577, abs=1e-6)
    assert result.heel_design.selected_spacing_m == pytest.approx(0.125)
    assert result.heel_design.shear_demand_tn_m == pytest.approx(47.619108, abs=1e-6)
    assert "Envolvente Resistencia/Evento Extremo" in result.heel_design.notes
    assert "presion triangular/trapezoidal" in result.heel_design.notes

    assert result.toe_design.controlling_moment_tn_m_m == pytest.approx(26.422087, abs=1e-6)
    assert result.toe_design.strength_as_cm2_m == pytest.approx(6.917424, abs=1e-6)
    assert result.toe_design.minimum_as_cm2_m == pytest.approx(9.225033, abs=1e-6)
    assert result.toe_design.required_as_cm2_m == pytest.approx(9.225033, abs=1e-6)
    assert result.toe_design.selected_bar_label == '1/2"'
    assert result.toe_design.selected_spacing_m == pytest.approx(0.125)
    assert result.toe_design.shear_demand_tn_m == pytest.approx(4.032242, abs=1e-6)
    assert result.toe_design.moment_resistance_tn_m_m >= 1.33 * 26.422087 - 1e-6
    assert "Envolvente Resistencia/Evento Extremo" in result.toe_design.notes
    assert result.key_design is not None
    assert result.key_design.selected_bar_label == '1/2"'
    assert result.key_design.selected_spacing_m == pytest.approx(0.175)
    assert result.key_design.moment_status == "OK"
    assert result.key_design.shear_status == "OK"


def test_abutment_primary_reinforcement_never_ignores_temperature_minimum() -> None:
    result = solve_abutment_design()

    cases = (
        result.stem_design,
        result.heel_design,
        result.toe_design,
        result.key_design,
    )

    for case in cases:
        assert case is not None
        assert case.minimum_as_cm2_m >= case.temperature_as_cm2_m
        assert case.required_as_cm2_m >= case.temperature_as_cm2_m
        assert case.provided_as_cm2_m >= case.required_as_cm2_m


def test_abutment_generates_single_stem_reinforcement_cut() -> None:
    result = solve_abutment_design()
    cut = result.stem_reinforcement_cut

    assert cut is not None
    assert cut.lower_bar_label == result.stem_design.selected_bar_label
    assert cut.lower_spacing_m == pytest.approx(result.stem_design.selected_spacing_m)
    assert cut.upper_bar_label == result.stem_design.selected_bar_label
    assert cut.upper_spacing_m > cut.lower_spacing_m
    assert cut.continuous_every_n_bars >= 2
    assert cut.upper_spacing_m == pytest.approx(
        cut.continuous_every_n_bars * cut.lower_spacing_m
    )
    assert cut.continuous_every_n_bars == 2
    assert cut.upper_spacing_m == pytest.approx(0.250)
    assert cut.upper_provided_as_cm2_m >= cut.minimum_as_cm2_m
    assert cut.required_as_at_cut_cm2_m <= cut.upper_provided_as_cm2_m + 1e-6
    assert cut.constructive_cut_height_m > cut.theoretical_cut_height_m
    assert cut.lower_cut_bar_length_m == pytest.approx(
        cut.constructive_cut_height_m + cut.development_extension_m
    )
    assert cut.continuous_bar_length_m > cut.lower_cut_bar_length_m
    assert cut.status == "OK"


def test_abutment_report_includes_stem_reinforcement_cut() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result

    report = format_abutment_design_result(solve_abutment_design())

    assert "CORTE DE ACERO PRINCIPAL DE PANTALLA" in report
    assert "Altura teorica de corte" in report
    assert "Altura constructiva de corte" in report
    assert "Acero continuo superior" in report
    assert "Continua 1 de cada 2 barras inferiores" in report


def test_abutment_report_can_omit_stem_reinforcement_cut() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result

    report = format_abutment_design_result(
        solve_abutment_design(),
        include_stem_reinforcement_cut=False,
    )

    assert "CORTE DE ACERO PRINCIPAL DE PANTALLA" not in report


def test_abutment_crack_development_and_detailing_are_complete() -> None:
    result = solve_abutment_design()

    assert {check.element for check in result.crack_checks} == {
        "Pantalla",
        "Zapata - talon superior",
        "Zapata - puntera inferior",
        "Diente de concreto",
    }
    assert all(check.status == "CUMPLE" for check in result.crack_checks)
    assert all(check.status == "OK" for check in result.development_checks)
    assert result.development_checks[0].element == "Pantalla"
    assert result.development_checks[0].anchorage_type == "GANCHO"
    assert {detail.mark for detail in result.bar_details} == {
        "E1",
        "E2",
        "E3",
        "E4",
        "E5",
        "E6",
        "E7",
        "E8",
        "E9",
    }
    assert [detail.element for detail in result.bar_details] == [
        "Pantalla",
        "Pantalla",
        "Pantalla",
        "Pantalla",
        "Zapata - talon superior",
        "Zapata - puntera inferior",
        "Zapata",
        "Zapata",
        "Diente de concreto",
    ]
    assert [detail.mark for detail in result.bar_details] == [
        "E1",
        "E2",
        "E3",
        "E4",
        "E5",
        "E6",
        "E7",
        "E8",
        "E9",
    ]
    assert any(detail.element == "Diente de concreto" for detail in result.bar_details)


def test_abutment_selected_reinforcement_is_used_for_final_checks() -> None:
    preliminary = solve_abutment_design()
    selected_toe = next(
        option
        for option in preliminary.toe_design.spacing_options.options
        if option.bar.label == '5/8"'
    )

    result = solve_abutment_design(
        selected_reinforcement={"Zapata - puntera inferior": selected_toe}
    )

    assert result.toe_design.selected_bar_label == '5/8"'
    assert result.toe_design.selected_spacing_m == pytest.approx(selected_toe.spacing_m)
    assert result.toe_design.provided_as_cm2_m == pytest.approx(selected_toe.provided_area_cm2_m)
    toe_crack = next(check for check in result.crack_checks if check.element == "Zapata - puntera inferior")
    toe_development = next(
        check for check in result.development_checks if check.element == "Zapata - puntera inferior"
    )
    toe_detail = next(detail for detail in result.bar_details if detail.element == "Zapata - puntera inferior")
    assert toe_crack.provided_spacing_m == pytest.approx(selected_toe.spacing_m)
    assert toe_development.bar_label == '5/8"'
    assert toe_detail.bar_label == '5/8"'
    assert toe_detail.spacing_m == pytest.approx(selected_toe.spacing_m)


def test_abutment_custom_reinforcement_is_used_and_identified() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_reinforcement_selection
    from bridge_design.domain.rebar_catalog import custom_spacing_option

    preliminary = solve_abutment_design()
    selected_stem = custom_spacing_option(
        preliminary.stem_design.spacing_options,
        '1"',
        0.125,
    )
    selected = (("A. Pantalla", selected_stem),)

    result = solve_abutment_design(selected_reinforcement={"Pantalla": selected_stem})
    report = format_abutment_reinforcement_selection(selected)

    assert result.stem_design.selected_bar_label == '1"'
    assert result.stem_design.selected_spacing_m == pytest.approx(0.125)
    assert result.stem_design.is_custom_selection is True
    assert "USUARIO" in report


def test_abutment_reports_missing_secondary_reinforcement_families() -> None:
    result = solve_abutment_design()

    secondary_by_name = {case.name: case for case in result.secondary_reinforcement}
    assert set(secondary_by_name) == {
        "Pantalla - vertical exterior",
        "Pantalla - horizontal relleno",
        "Pantalla - horizontal exterior",
        "Zapata - transversal superior",
        "Zapata - transversal inferior",
    }
    assert secondary_by_name["Pantalla - vertical exterior"].face == "Cara exterior al relleno"
    assert secondary_by_name["Pantalla - horizontal relleno"].direction == "Horizontal transversal"
    assert secondary_by_name["Pantalla - horizontal exterior"].direction == "Horizontal transversal"
    assert secondary_by_name["Zapata - transversal superior"].direction == "Horizontal transversal a talon/puntera"
    assert secondary_by_name["Zapata - transversal inferior"].direction == "Horizontal transversal a talon/puntera"
    assert all(case.provided_as_cm2_m >= case.required_as_cm2_m for case in result.secondary_reinforcement)
    assert secondary_by_name["Pantalla - vertical exterior"].selected_bar_label == '1/2"'
    assert secondary_by_name["Pantalla - vertical exterior"].selected_spacing_m == pytest.approx(0.275)
    assert secondary_by_name["Zapata - transversal superior"].required_as_cm2_m == pytest.approx(8.022413793)
    assert secondary_by_name["Zapata - transversal superior"].selected_bar_label == '1/2"'
    assert secondary_by_name["Zapata - transversal superior"].selected_spacing_m == pytest.approx(0.150)


def test_abutment_material_prompts_use_tn_m3_for_unit_weights(monkeypatch) -> None:
    answers = iter(("", "", "2.5", "1.8"))
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)

    materials = _collect_materials()

    assert "Peso unitario concreto (Tn/m3) [2.4]: " in prompts
    assert "Peso unitario relleno (Tn/m3) [1.925]: " in prompts
    assert materials.concrete_unit_weight_kg_m3 == pytest.approx(2500.0)
    assert materials.soil_unit_weight_kg_m3 == pytest.approx(1800.0)


def test_abutment_key_prompt_does_not_request_passive_coefficient(monkeypatch) -> None:
    answers = iter(["", "", ""])
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)

    key = collect_abutment_key()

    assert key.enabled is True
    assert key.passive_soil_height_m == pytest.approx(0.0)
    assert key.passive_coefficient_prime is None
    prompt_text = "\n".join(prompts)
    assert "h pasivo - altura garantizada de relleno" not in prompt_text
    assert "k'p pasivo" not in prompt_text
    assert "R reduccion pasiva" not in prompt_text
    assert "phi ep" not in prompt_text
    assert key.passive_resistance_factor == pytest.approx(0.50)


def test_abutment_key_prompt_uses_previously_entered_passive_height(monkeypatch) -> None:
    answers = iter(["", "", "", ""])
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)

    key = collect_abutment_key(default_passive_soil_height_m=0.95)

    assert key.passive_soil_height_m == pytest.approx(0.95)
    assert key.consider_upper_front_passive is False
    assert "h pasivo - altura garantizada de relleno" not in "\n".join(prompts)
    assert "Considerar empuje pasivo del relleno frontal superior" in "\n".join(prompts)


def test_abutment_key_prompt_can_consider_upper_front_passive(monkeypatch) -> None:
    answers = iter(["", "s", "", ""])

    def fake_input(prompt: str) -> str:
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)

    key = collect_abutment_key(default_passive_soil_height_m=0.95)

    assert key.consider_upper_front_passive is True


def test_abutment_key_prompt_uses_recommended_key_height(monkeypatch) -> None:
    answers = iter(["", "", ""])
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)

    key = collect_abutment_key(default_height_m=1.50)

    assert key.height_m == pytest.approx(1.50)
    assert "h die - altura de diente (m) [1.5]" in "\n".join(prompts)


def test_abutment_input_flow_can_defer_key_prompt_until_stability_check(monkeypatch) -> None:
    from bridge_design.cli.abutment_input_prompts import collect_abutment_inputs

    answers = iter([""] * 40)
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)

    inputs = collect_abutment_inputs(collect_key=False)

    assert inputs.key.enabled is False
    assert inputs.key.passive_soil_height_m == pytest.approx(inputs.geometry.front_soil_depth_m)
    assert "h pasivo - altura garantizada de relleno sobre fondo de zapata" not in "\n".join(prompts)
    assert "Considerar diente" not in "\n".join(prompts)
    assert "h die - altura de diente" not in "\n".join(prompts)


def test_pedestrian_loads_are_considered_separately_from_vehicle_impact() -> None:
    result = solve_abutment_design(
        AbutmentInputs(
            loads=AbutmentLoadInputs(ppl_tn_m=2.0),
            soil=AbutmentSoilInputs(pedestrian_surcharge_tn_m2=0.25),
        )
    )
    res_ib = result.with_bridge[1]

    assert result.pressures.pedestrian_lsy_tn_m > 0.0
    assert result.pressures.pedestrian_lsx_tn_m > 0.0
    assert res_ib.vu_tn_m > solve_abutment_design().with_bridge[1].vu_tn_m


def test_equivalent_vehicular_surcharge_height_is_not_fixed_at_sixty_cm() -> None:
    assert equivalent_vehicular_surcharge_height_m(7.0) == pytest.approx(0.60)
    assert equivalent_vehicular_surcharge_height_m(2.0) > 0.60


def test_rankine_passive_coefficient_is_computed_from_soil_friction_angle() -> None:
    assert rankine_passive_coefficient(30.0) == pytest.approx(3.0)


def test_coulomb_angle_validation_reports_invalid_backface_angle() -> None:
    with pytest.raises(ValueError, match="theta cara posterior se mide desde la horizontal"):
        AbutmentSoilInputs(
            friction_angle_deg=28.0,
            wall_soil_friction_deg=28.0,
            wall_backface_angle_deg=5.0,
        )
