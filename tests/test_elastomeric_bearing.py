"""Tests for Method A elastomeric bearing design."""

from bridge_design.domain.elastomeric_bearing import (
    BearingLoads,
    BearingMovements,
    ConcreteBearingSupport,
    ElastomericBearingInputs,
    SeismicBearingInputs,
    TemperatureRange,
    design_elastomeric_bearing_method_a,
    recommend_bearing_plan,
    shape_factor_rectangular,
)


def _base_inputs(**overrides) -> ElastomericBearingInputs:
    data = dict(
        loads=BearingLoads(
            dead_load_dc_tn=48.0,
            wearing_surface_dw_tn=4.0,
            live_load_ll_tn=28.0,
        ),
        movements=BearingMovements(
            span_length_m=25.0,
            temperature=TemperatureRange.mtc_default("costa", t_install_c=20.0),
            shrinkage_cm=0.8,
            prestress_shortening_cm=0.0,
            gamma_tu=1.2,
        ),
        seismic=SeismicBearingInputs(
            site_acceleration_as=0.20,
            seismic_zone=1,
            is_single_span=True,
            bearing_role="expansion",
            longitudinal_restrained=False,
            transverse_restrained=True,
        ),
        hardness=60,
        girder_width_cm=40.0,
        steel_fy_kg_cm2=2530.0,
        adopted_length_cm=30.0,
        adopted_width_cm=40.0,
        concrete_support=ConcreteBearingSupport(fc_kg_cm2=210.0),
    )
    data.update(overrides)
    return ElastomericBearingInputs(**data)


def test_shape_factor_rectangular():
    si = shape_factor_rectangular(30.0, 40.0, 1.0)
    assert abs(si - 8.5714) < 1e-3


def test_recommend_bearing_plan_rounds_length_up():
    plan = recommend_bearing_plan(BearingLoads(48.0, 4.0, 28.0), width_cm=40.0)
    # A_req = 80000/87.9 ≈ 910.13; L_teo ≈ 22.75 -> L_prop = 23 cm
    assert abs(plan.required_area_cm2 - 910.13) < 0.1
    assert abs(plan.theoretical_length_cm - 22.753) < 0.01
    assert plan.recommended_length_cm == 23.0
    assert plan.recommended_area_cm2 >= plan.required_area_cm2 - 1e-9


def test_confirm_plan_dimensions_accepts_proposed_length(monkeypatch):
    from bridge_design.cli import bearing_cli

    answers = iter(["40", ""])  # W=40, Enter acepta L propuesto

    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    width, length = bearing_cli._confirm_plan_dimensions(
        BearingLoads(48.0, 4.0, 28.0),
        girder_width_cm=40.0,
    )
    assert width == 40.0
    assert length == 23.0


def test_confirm_plan_dimensions_allows_user_override(monkeypatch):
    from bridge_design.cli import bearing_cli

    answers = iter(["40", "30"])  # W=40, usuario impone L=30

    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    width, length = bearing_cli._confirm_plan_dimensions(
        BearingLoads(48.0, 4.0, 28.0),
        girder_width_cm=40.0,
    )
    assert width == 40.0
    assert length == 30.0


def test_method_a_non_prestressed_example_passes():
    result = design_elastomeric_bearing_method_a(_base_inputs())
    assert result.area_cm2 >= result.required_area_cm2
    assert result.sigma_s_kg_cm2 <= 87.9 + 1e-6
    assert result.total_elastomer_cm + 1e-9 >= 2.0 * result.delta_s_cm
    assert result.interior_layers >= 3
    assert result.shape_factor_interior >= 5.0
    assert result.overall_ok
    assert "mm" in result.designation


def test_delta_s_includes_gamma_tu_and_no_prestress():
    result = design_elastomeric_bearing_method_a(_base_inputs())
    # Δtemp = 10.8e-6 * 2500 * 20 = 0.54; +0.8 retraccion; *1.2 = 1.608
    assert abs(result.delta_s_cm - 1.608) < 0.02


def test_prestress_increases_required_thickness():
    without = design_elastomeric_bearing_method_a(_base_inputs())
    with_pt = design_elastomeric_bearing_method_a(
        _base_inputs(
            movements=BearingMovements(
                span_length_m=25.0,
                temperature=TemperatureRange.mtc_default("costa", t_install_c=20.0),
                shrinkage_cm=0.8,
                prestress_shortening_cm=1.0,
                gamma_tu=1.2,
            )
        )
    )
    assert with_pt.required_hrt_cm > without.required_hrt_cm


def test_seismic_anchor_reported_when_demand_exceeds_capacity():
    result = design_elastomeric_bearing_method_a(
        _base_inputs(
            seismic=SeismicBearingInputs(
                site_acceleration_as=0.80,
                seismic_zone=4,
                is_single_span=True,
                bearing_role="expansion",
                longitudinal_restrained=False,
                transverse_restrained=True,
            )
        )
    )
    assert result.seismic_governing_tn > 0.0
    seismic_check = next(c for c in result.checks if c.name.startswith("Sismo"))
    assert seismic_check.status in {"OK", "ANCLAR"}
    if result.seismic_governing_tn > max(
        result.shear_force_service_tn, result.friction_capacity_tn
    ):
        assert result.anchor_force_required_tn > 0.0
        assert seismic_check.status == "ANCLAR"


def test_serquen_style_area_requirement():
    result = design_elastomeric_bearing_method_a(
        _base_inputs(
            loads=BearingLoads(65.0, 5.0, 22.0),
            adopted_length_cm=30.0,
            adopted_width_cm=45.0,
        )
    )
    assert abs(result.required_area_cm2 - 1046.64) < 1.0
    assert result.area_cm2 == 1350.0


def test_bearing_report_is_step_by_step_and_ascii():
    from bridge_design.cli.bearing_output import format_elastomeric_bearing_result

    report = format_elastomeric_bearing_result(design_elastomeric_bearing_method_a(_base_inputs()))
    assert all(ord(ch) < 128 for ch in report)
    for section in (
        "PROCEDIMIENTO PASO A PASO DEL CALCULO",
        "1. AREA EN PLANTA",
        "2. DESPLAZAMIENTO POR CORTE",
        "3. ESPESOR TOTAL DE ELASTOMERO",
        "4. FACTOR DE FORMA Y CAPAS",
        "5. ZUNCHOS DE ACERO",
        "6. ALTURA TOTAL Y ESTABILIDAD",
        "7. DEFLEXIONES POR COMPRESION",
        "8. FUERZA HORIZONTAL Y FRICCION",
        "9. SISMO Y FUERZA DE UNION",
        "10. APLASTAMIENTO DEL CONCRETO",
        "RESUMEN DE VERIFICACIONES NORMATIVAS",
        "DESIGNACION FINAL DEL APOYO",
        "Formula",
        "Sustitucion",
        "Resultado",
    ):
        assert section in report
