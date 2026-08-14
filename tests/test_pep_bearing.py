"""Tests for plain elastomeric pad (PEP) Method A design."""

from bridge_design.cli.pep_bearing_output import format_pep_bearing_result
from bridge_design.cli.pep_yaml_inputs import pep_inputs_from_yaml, pep_yaml_template
from bridge_design.domain.pep_bearing import (
    SIGMA_S_MAX_PEP_KG_CM2,
    PepAnchorGroup,
    PepBearingInputs,
    PepConcreteSupport,
    PepExternalPlate,
    PepGeometry,
    PepServiceDemands,
    PepTemperature,
    design_pep_bearing,
    pep_grade,
)
from bridge_design.domain.pep_demands import (
    build_demands_from_reactions,
    elastomeric_restraint_moment,
    select_governing_demands,
)
from bridge_design.domain.pep_steel_components import (
    ComponentDemands,
    auto_design_anchors,
    auto_design_plate,
    default_bolt_layout,
)
from bridge_design.domain.pep_strain_curves import compressive_strain_from_curve
from bridge_design.units.converters import ksi_to_kg_cm2


def _demands(**overrides) -> PepServiceDemands:
    data = dict(
        combination_id="SERVICIO_I",
        load_case_id="DC+DW+LL",
        position_id="POS_1",
        bearing_id="APOYO_1",
        r_dc_tn=40.0,
        r_dw_tn=4.0,
        r_ll_tn=20.0,
        h_long_tn=5.0,
        h_trans_tn=3.0,
        h_eq_long_tn=8.0,
        h_eq_trans_tn=10.0,
        delta_s_cm=1.5,
        span_length_m=25.0,
        temperature=PepTemperature.mtc_default("costa", 20.0),
        theta_dc_rad=0.002,
        theta_ll_rad=0.003,
    )
    data.update(overrides)
    return PepServiceDemands(**data)


def _movable(**overrides) -> PepBearingInputs:
    data = dict(
        tipo_apoyo="MOVIL_PEP_CORTE",
        geometry=PepGeometry(50.0, 50.0, 3.5),
        demands=_demands(),
        hardness=60,
        epsilon_source="curva_aashto",
        upper_plate=PepExternalPlate(70.0, 70.0, 2.5),
        lower_plate=PepExternalPlate(70.0, 70.0, 2.5),
        anchors=PepAnchorGroup(4, 2.2, 4220.0, 6330.0, 30.0),
        concrete_support=PepConcreteSupport(210.0),
        mode="VERIFICAR",
        design_plates_auto=False,
        design_anchors_auto=False,
    )
    data.update(overrides)
    return PepBearingInputs(**data)


def _fixed(**overrides) -> PepBearingInputs:
    return _movable(
        tipo_apoyo="FIJO",
        fixed_restraint_load_path="RESTRICCION_EXTERNA",
        **overrides,
    )


def test_ksi_conversion_0_80():
    assert abs(SIGMA_S_MAX_PEP_KG_CM2 - ksi_to_kg_cm2(0.80)) < 1e-9


def test_area_and_shape_factor():
    g = PepGeometry(30.0, 40.0, 4.0)
    assert g.area_cm2 == 1200.0
    assert abs(g.shape_factor - 2.142857) < 1e-4


def test_g_by_hardness_60():
    grade = pep_grade(60)
    assert abs(grade.g_min_kg_cm2 - 9.14) < 1e-6
    assert abs(grade.creep_ratio - 0.35) < 1e-9


def test_strain_curve_aashto():
    look = compressive_strain_from_curve(60, 6.0, 51.85)
    assert 0.02 < look.epsilon < 0.08
    assert "C14.7.6.3.3-1" in look.source


def test_movable_compression_uses_1_0_gs_not_1_25():
    result = design_pep_bearing(_movable())
    assert result.sigma_adm_kg_cm2 <= result.sigma_gs_kg_cm2 + 1e-9
    assert result.sigma_adm_kg_cm2 <= SIGMA_S_MAX_PEP_KG_CM2 + 1e-9
    assert all("1.25" not in c.formula for c in result.checks)


def test_movable_shear_h_ge_2_delta():
    ok = design_pep_bearing(_movable(geometry=PepGeometry(50.0, 50.0, 3.5), demands=_demands(delta_s_cm=1.5)))
    shear = next(c for c in ok.checks if c.name.startswith("Cortante h"))
    assert shear.status == "OK"
    fail = design_pep_bearing(_movable(geometry=PepGeometry(50.0, 50.0, 2.0), demands=_demands(delta_s_cm=1.5)))
    shear_fail = next(c for c in fail.checks if c.name.startswith("Cortante h"))
    assert shear_fail.status == "NO"


def test_stability_limits():
    fail = design_pep_bearing(_movable(geometry=PepGeometry(30.0, 40.0, 12.0), demands=_demands(delta_s_cm=0.5)))
    assert any(c.name.startswith("Estabilidad") and c.status == "NO" for c in fail.checks)


def test_h_pad_and_moment():
    result = design_pep_bearing(_movable())
    expected = (
        result.g_for_force_kg_cm2
        * result.area_cm2
        * result.delta_s_cm
        / result.inputs.geometry.thickness_cm
        / 1000.0
    )
    assert abs(result.h_pad_service_tn - expected) < 1e-6
    assert result.moment_tn_m > 0.0
    assert "Ec*I*theta/h" in result.moment_formula.replace(" ", "")


def test_fixed_does_not_size_by_thermal_shear_when_external_restraint():
    result = design_pep_bearing(
        _fixed(geometry=PepGeometry(50.0, 50.0, 2.0), demands=_demands(delta_s_cm=3.0))
    )
    shear = next(c for c in result.checks if "Cortante" in c.name)
    assert shear.status == "N.A."


def test_apparatus_checks_present_and_can_pass():
    result = design_pep_bearing(_movable())
    names = {c.name for c in result.checks}
    assert any(n.startswith("Placa superior") for n in names)
    assert any(n.startswith("Perno:") for n in names)
    assert any(n.startswith("Soldadura") for n in names)
    assert any(n.startswith("Anclaje:") for n in names)
    assert "VERIFICACION PENDIENTE - FUENTE NORMATIVA INSUFICIENTE" not in {
        c.formula for c in result.checks
    }


def test_auto_design_complete_apparatus():
    result = design_pep_bearing(
        _movable(
            mode="DISENAR",
            geometry=PepGeometry(40.0, 40.0, 1.0),
            upper_plate=None,
            lower_plate=None,
            anchors=None,
            design_plates_auto=True,
            design_anchors_auto=True,
            demands=_demands(delta_s_cm=1.2, h_eq_trans_tn=6.0, h_eq_long_tn=5.0),
        )
    )
    assert result.pep_core_ok
    assert result.inputs.upper_plate is not None
    assert result.inputs.anchors is not None


def test_auto_design_respects_user_minimum_pep_dimensions():
    result = design_pep_bearing(
        _fixed(
            mode="DISENAR",
            geometry=PepGeometry(40.0, 40.0, 5.0),
            demands=_demands(
                r_dc_tn=20.10,
                r_dw_tn=1.18,
                r_ll_tn=22.63,
                r_im_tn=6.79,
                h_long_tn=4.87,
                h_eq_long_tn=11.032,
                h_eq_trans_tn=0.0,
                delta_s_cm=None,
                span_length_m=15.0,
                temperature=PepTemperature.mtc_default("costa", 20.0),
            ),
            upper_plate=None,
            lower_plate=None,
            anchors=None,
            design_plates_auto=True,
            design_anchors_auto=True,
        )
    )

    assert result.inputs.geometry.length_cm >= 40.0
    assert result.inputs.geometry.width_cm >= 40.0
    assert result.inputs.geometry.thickness_cm >= 5.0


def test_plate_and_anchor_autodesign_helpers():
    dem = ComponentDemands(64.0, 8.0, 6.0, 0.0, 0.5, "SERVICIO_I")
    plate = auto_design_plate(50.0, 50.0, dem)
    assert plate is not None
    anchors = auto_design_anchors(plate, 50.0, 50.0, dem, 210.0)
    assert anchors is not None
    detail, grown = anchors
    assert len(detail.coordinates) == detail.n_bolts
    assert grown.length_cm >= plate.length_cm
    layout = default_bolt_layout(4, 70.0, 70.0, 50.0, 50.0, diameter_cm=2.2)
    assert layout
    assert all(abs(c.x_cm) > 25.0 and abs(c.y_cm) > 25.0 for c in layout)


def test_demands_factory_and_governor():
    a = build_demands_from_reactions(
        combination_id="S1",
        load_case_id="LL_A",
        position_id="P1",
        bearing_id="B1",
        r_dc_tn=30.0,
        r_dw_tn=3.0,
        r_ll_tn=15.0,
        h_long_tn=4.0,
    )
    b = build_demands_from_reactions(
        combination_id="S1",
        load_case_id="LL_B",
        position_id="P1",
        bearing_id="B1",
        r_dc_tn=30.0,
        r_dw_tn=3.0,
        r_ll_tn=22.0,
        h_long_tn=2.0,
    )
    gov = select_governing_demands((a, b), objective="max_vertical")
    assert gov.r_ll_tn == 22.0
    mom = elastomeric_restraint_moment(PepGeometry(50, 50, 3.5), 0.005, 9.14, 0.6, 3.57)
    assert mom.moment_tn_m > 0.0


def test_yaml_roundtrip_and_report_ascii():
    data = pep_yaml_template()
    assert "combination_id" not in data["demandas"]
    assert "theta_dc_rad" not in data["demandas"]
    assert "h_trans_tn" not in data["demandas"]
    assert "h_eq_trans_tn" not in data["demandas"]
    assert data["demandas"]["h_eq_long_tn"] is None
    assert data["demandas"]["delta_s_cm"] is None
    assert data["demandas"]["theta_total_rad"] == 0.0
    assert "as_sitio" not in data["sismo"]
    assert data["sismo"]["pga"] == 0.20
    assert data["sismo"]["fpga"] == 1.00
    movable = design_pep_bearing(pep_inputs_from_yaml(data))
    assert movable.inputs.site_acceleration_as == 0.20
    assert movable.inputs.seismic_pga == 0.20
    assert movable.inputs.seismic_fpga == 1.00
    assert movable.inputs.demands.h_trans_tn == 0.0
    assert movable.inputs.demands.h_eq_long_tn == 0.20 * (
        movable.inputs.demands.r_dc_tn + movable.inputs.demands.r_dw_tn
    )
    assert movable.inputs.demands.h_eq_trans_tn == 0.0
    assert abs(movable.delta_s_cm - 0.648) < 1e-9
    report = format_pep_bearing_result(movable)
    assert all(ord(ch) < 128 for ch in report)
    assert "H_trans" not in report
    assert "H_EQ_trans" not in report
    assert "Calculado por temperatura" in report
    assert "gamma_TU*alpha*L*Delta_T" in report
    assert "PGA*Fpga*(R_DC+R_DW)" in report
    assert "Resumen constructivo final" in report
    assert "ASTM A36" in report
    assert "ASTM A325" in report
    assert "Pernos requeridos" in report
    assert "CONFORME" in report
    assert "Momento" in report or "momento" in report.lower() or "Momento rotacion" in report
    data["tipo_apoyo"] = "FIJO"
    fixed = design_pep_bearing(pep_inputs_from_yaml(data))
    assert fixed.inputs.tipo_apoyo == "FIJO"


def test_cli_yaml_modes(tmp_path, monkeypatch):
    from bridge_design.cli import pep_bearing_cli

    path = tmp_path / "modelo_apoyos_pep.yaml"
    pep_bearing_cli.main(["output", str(path)])
    captured = []

    def fake_run(inputs=None):
        captured.append(inputs)

    monkeypatch.setattr(pep_bearing_cli, "run_pep_bearing_design", fake_run)
    pep_bearing_cli.main(["input", str(path)])
    assert captured and captured[0].epsilon_source == "curva_aashto"


def test_pep_yaml_keeps_legacy_as_sitio_compatibility():
    data = pep_yaml_template()
    data["sismo"].pop("pga")
    data["sismo"].pop("fpga")
    data["sismo"]["as_sitio"] = 0.30

    inputs = pep_inputs_from_yaml(data)

    assert inputs.site_acceleration_as == 0.30
    assert inputs.seismic_pga is None
    assert inputs.seismic_fpga is None
    assert inputs.demands.h_eq_long_tn == 0.30 * (
        inputs.demands.r_dc_tn + inputs.demands.r_dw_tn
    )


def test_interactive_pep_prompts_minimal_inputs(monkeypatch):
    from bridge_design.cli import pep_bearing_cli

    prompts = []

    def fake_input(prompt):
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", fake_input)
    inputs = pep_bearing_cli.collect_pep_bearing_inputs()
    joined = "\n".join(prompts)

    assert "Mostrar matriz normativa implementada" not in joined
    assert "combination_id" not in joined
    assert "load_case_id" not in joined
    assert "position_id" not in joined
    assert "bearing_id" not in joined
    assert "theta DC" not in joined
    assert "Fuente de epsilon" not in joined
    assert "Auto-disenar placas" not in joined
    assert "H transversal" not in joined
    assert "H_EQ longitudinal" not in joined
    assert "H_EQ transversal" not in joined
    assert "As longitudinal" not in joined
    assert "PGA" in joined
    assert "Fpga" in joined
    assert "Delta_s de servicio" not in joined
    assert "Luz del tramo para movimiento termico" in joined
    assert "Zona climatica MTC" in joined
    assert "Temperatura de instalacion" in joined
    assert inputs.mode == "DISENAR"
    assert inputs.design_plates_auto
    assert inputs.design_anchors_auto
    assert inputs.demands.theta_total_rad == 0.0
    assert inputs.site_acceleration_as == 0.20
    assert inputs.seismic_pga == 0.20
    assert inputs.seismic_fpga == 1.00
    assert inputs.demands.h_trans_tn == 0.0
    assert inputs.demands.h_eq_long_tn == 0.20 * (
        inputs.demands.r_dc_tn + inputs.demands.r_dw_tn
    )
    assert inputs.demands.h_eq_trans_tn == 0.0
    assert inputs.demands.delta_s_cm is None
    assert abs(inputs.demands.resolved_delta_s_cm() - 0.648) < 1e-9
    assert inputs.upper_plate is None
    assert inputs.anchors is None


def test_compression_failure_case():
    result = design_pep_bearing(
        _movable(
            geometry=PepGeometry(20.0, 20.0, 3.0),
            demands=_demands(r_dc_tn=80.0, r_dw_tn=10.0, r_ll_tn=40.0, delta_s_cm=0.5),
            design_plates_auto=True,
            design_anchors_auto=True,
            upper_plate=None,
            lower_plate=None,
            anchors=None,
        )
    )
    assert any("Compresion" in c.name and c.status == "NO" for c in result.checks)
