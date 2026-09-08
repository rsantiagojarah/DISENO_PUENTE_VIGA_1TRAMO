import tomllib

import pytest

import bridge_design.cantilever_wall_main as wall_main
import bridge_design.main as bridge_main


def test_bridge_design_muro_dispatches_to_wall_command(monkeypatch) -> None:
    called = []

    def fake_wall_main() -> None:
        called.append(True)

    monkeypatch.setattr(wall_main, "main", fake_wall_main)

    bridge_main.main(["muro"])

    assert called == [True]


def test_wall_command_uses_pure_retaining_wall_defaults(monkeypatch) -> None:
    from bridge_design.domain.cantilever_wall import cantilever_wall_load_inputs

    captured = {}

    def fake_run_abutment_design(**kwargs) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(wall_main, "run_abutment_design", fake_run_abutment_design)

    wall_main.main()

    loads = captured["load_defaults"]
    assert loads == cantilever_wall_load_inputs()
    assert captured["element_label"] == "muro"
    assert captured["primary_stability_title"] == "MURO PURO"
    assert captured["include_bridge_inputs"] is False


def test_wall_reinforcement_selection_prompt_uses_wall_label(monkeypatch) -> None:
    from bridge_design.cli.abutment_input_prompts import collect_abutment_reinforcement_selection
    from bridge_design.domain.abutment import solve_abutment_design

    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    collect_abutment_reinforcement_selection(solve_abutment_design(), element_label="muro")

    assert "distribuciones de acero del muro" in prompts[0]


def test_wall_sliding_failure_adds_key_before_reinforcement(monkeypatch) -> None:
    from bridge_design.abutment_main import _consider_key_when_sliding_fails, _recommended_key_height_m
    from bridge_design.domain.abutment import (
        AbutmentGeometryInputs,
        AbutmentInputs,
        AbutmentKeyInputs,
        AbutmentLoadInputs,
        AbutmentMaterialInputs,
        AbutmentSoilInputs,
        solve_abutment_design,
    )

    inputs = AbutmentInputs(
        geometry=AbutmentGeometryInputs(
            retained_height_m=7.8,
            footing_width_m=6.2,
            footing_thickness_m=0.95,
            toe_length_m=2.55,
            lower_stem_thickness_m=0.95,
            upper_stem_thickness_m=0.4,
            backfill_step_width_m=0.0,
            front_soil_depth_m=0.95,
        ),
        materials=AbutmentMaterialInputs(
            concrete_strength_kg_cm2=280.0,
            soil_unit_weight_kg_m3=1600.0,
        ),
        loads=AbutmentLoadInputs(
            pdc_tn_m=0.0,
            pdw_tn_m=0.0,
            ppl_tn_m=0.0,
            pll_im_tn_m=0.0,
            braking_tn_m=0.0,
        ),
        soil=AbutmentSoilInputs(
            allowable_bearing_kg_cm2=2.0,
            friction_angle_deg=28.0,
            wall_soil_friction_deg=0.0,
            pga=0.48,
            fpga=1.08,
            vehicular_surcharge_height_m=0.0,
        ),
        key=AbutmentKeyInputs(enabled=False),
        is_pure_wall=True,
    )
    preliminary = solve_abutment_design(inputs)
    assert any(state.sliding_status == "NO" for state in preliminary.with_bridge)
    assert _recommended_key_height_m(inputs, preliminary) == pytest.approx(1.50)

    captured_key_defaults = {}
    monkeypatch.setattr(
        "bridge_design.abutment_main.collect_abutment_key",
        lambda **kwargs: captured_key_defaults.update(kwargs)
        or AbutmentKeyInputs(
            enabled=True,
            height_m=kwargs["default_height_m"],
            passive_soil_height_m=0.0,
        ),
    )

    updated_inputs, updated_result = _consider_key_when_sliding_fails(inputs, preliminary)

    assert captured_key_defaults["default_height_m"] == pytest.approx(1.50)
    assert captured_key_defaults["default_passive_soil_height_m"] == pytest.approx(0.95)
    assert updated_inputs.key.enabled is True
    assert updated_inputs.key.height_m == pytest.approx(1.50)
    assert updated_inputs.key.passive_soil_height_m == pytest.approx(0.0)
    assert updated_result.key_design is not None
    assert any(state.sliding_with_key_status == "OK" for state in updated_result.with_bridge)


def test_wall_geometry_prompt_omits_bridge_fields(monkeypatch) -> None:
    from bridge_design.cli.abutment_input_prompts import _collect_geometry

    answers = iter([""] * 7)
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)

    geometry = _collect_geometry(include_bridge_inputs=False)

    prompt_text = "\n".join(prompts)
    assert "Altura total del muro desde fondo de zapata" in prompt_text
    assert "H activo - altura de relleno posterior" not in prompt_text
    assert "L - Luz del puente tributaria" not in prompt_text
    assert "t2 - Retiro superior del relleno" not in prompt_text
    assert "N - Longitud de cajuela/apoyo" not in prompt_text
    assert "bpar - Espesor parapeto posterior" not in prompt_text
    assert "Altura bloque/cajuela superior" not in prompt_text
    assert "h frontal - altura de suelo frontal desde fondo de zapata" in prompt_text
    assert geometry.backfill_step_width_m == 0.0
    assert geometry.seat_block_height_m == 0.0
    assert geometry.seat_wall_width_m == 0.0
    assert geometry.bearing_seat_length_m == 0.0
    assert geometry.backwall_drop_m == 0.0
    assert geometry.backwall_taper_height_m == 0.0
    assert geometry.small_batter_width_m == 0.0
    assert geometry.bridge_seat_to_bearing_height_m == 0.0
    assert geometry.front_soil_depth_m == geometry.footing_thickness_m


def test_wall_geometry_prompt_accepts_zero_toe(monkeypatch) -> None:
    from bridge_design.cli.abutment_input_prompts import _collect_geometry

    answers = iter(["", "2.00", "0.50", "0", "0.30", "0.30", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    geometry = _collect_geometry(include_bridge_inputs=False)

    assert geometry.toe_length_m == 0.0
    assert geometry.heel_length_m == pytest.approx(1.70)


def test_pure_wall_without_toe_omits_nonexistent_structural_case() -> None:
    from bridge_design.cli.abutment_ascii_output import (
        format_abutment_design_result,
        format_abutment_reinforcement_option_tables,
    )
    from bridge_design.domain.abutment import (
        AbutmentGeometryInputs,
        AbutmentInputs,
        solve_abutment_design,
    )

    result = solve_abutment_design(
        AbutmentInputs(
            geometry=AbutmentGeometryInputs(
                retained_height_m=2.45,
                footing_width_m=2.00,
                footing_thickness_m=0.50,
                toe_length_m=0.0,
                lower_stem_thickness_m=0.30,
                upper_stem_thickness_m=0.30,
                front_soil_depth_m=0.50,
                seat_block_height_m=0.0,
                backwall_drop_m=0.0,
                backwall_taper_height_m=0.0,
            ),
            is_pure_wall=True,
        )
    )
    report = format_abutment_design_result(
        result,
        title="DISENO DE MURO DE CONCRETO ARMADO EN CANTILEVER",
        primary_stability_title="MURO PURO",
    )
    option_tables = format_abutment_reinforcement_option_tables(result)

    assert result.inputs.geometry.heel_length_m == pytest.approx(1.70)
    assert result.toe_design is None
    assert "Zapata - puntera" not in {
        component.name for component in result.concrete_components
    }
    assert all(check.element != "Zapata - puntera inferior" for check in result.crack_checks)
    assert all(check.element != "Zapata - puntera inferior" for check in result.development_checks)
    assert all(detail.element != "Zapata - puntera inferior" for detail in result.bar_details)
    assert "Solo talon" in report
    assert "DISENO ESTRUCTURAL - Zapata - puntera inferior" not in report
    assert "OPCIONES - Zapata - puntera inferior" not in option_tables


def test_wall_geometry_rejects_negative_toe() -> None:
    from bridge_design.domain.abutment import AbutmentGeometryInputs

    with pytest.raises(ValueError, match="toe_length_m"):
        AbutmentGeometryInputs(toe_length_m=-0.01)


def test_pure_wall_solver_sanitizes_bridge_geometry_and_loads() -> None:
    from bridge_design.domain.abutment import (
        AbutmentGeometryInputs,
        AbutmentInputs,
        AbutmentLoadInputs,
    )
    from bridge_design.domain.cantilever_wall import solve_cantilever_wall_design

    result = solve_cantilever_wall_design(
        AbutmentInputs(
            geometry=AbutmentGeometryInputs(
                seat_block_height_m=1.5,
                seat_wall_width_m=0.25,
                bearing_seat_length_m=0.7,
                backwall_drop_m=0.4,
                backwall_taper_height_m=0.6,
                backfill_step_width_m=0.35,
                small_batter_width_m=0.30,
            ),
            loads=AbutmentLoadInputs(
                pdc_tn_m=12.0,
                pdw_tn_m=1.8,
                ppl_tn_m=2.0,
                pll_im_tn_m=9.5,
                braking_tn_m=2.0,
            ),
            is_pure_wall=True,
        )
    )

    geometry = result.inputs.geometry
    assert result.inputs.loads == AbutmentLoadInputs(
        pdc_tn_m=0.0,
        pdw_tn_m=0.0,
        ppl_tn_m=0.0,
        pll_im_tn_m=0.0,
        braking_tn_m=0.0,
    )
    assert geometry.seat_block_height_m == 0.0
    assert geometry.seat_wall_width_m == 0.0
    assert geometry.bearing_seat_length_m == 0.0
    assert geometry.backwall_drop_m == 0.0
    assert geometry.backwall_taper_height_m == 0.0
    assert geometry.backfill_step_width_m == 0.0
    assert geometry.small_batter_width_m == 0.0
    assert result.pressures.peq_tn_m == 0.0
    assert [component.name for component in result.components.horizontal_with_bridge] == [
        "LSx sobrecarga",
        "EH terreno",
        "EQterr",
        "0.5PIR",
    ]


def test_pure_wall_stem_secondary_minimum_uses_average_stem_thickness() -> None:
    from bridge_design.domain.abutment import AbutmentGeometryInputs, AbutmentInputs
    from bridge_design.domain.cantilever_wall import solve_cantilever_wall_design

    result = solve_cantilever_wall_design(
        AbutmentInputs(
            geometry=AbutmentGeometryInputs(
                retained_height_m=7.8,
                footing_width_m=6.0,
                footing_thickness_m=0.95,
                toe_length_m=2.55,
                lower_stem_thickness_m=0.95,
                upper_stem_thickness_m=0.40,
                front_soil_depth_m=2.50,
            ),
            is_pure_wall=True,
        )
    )

    secondary_by_name = {case.name: case for case in result.secondary_reinforcement}
    for name in (
        "Pantalla - vertical exterior",
        "Pantalla - horizontal relleno",
        "Pantalla - horizontal exterior",
    ):
        assert secondary_by_name[name].temperature_required_as_cm2_m == pytest.approx(5.595901, abs=1e-6)
        assert secondary_by_name[name].required_as_cm2_m == pytest.approx(5.595901, abs=1e-6)
    for name in (
        "Zapata - transversal superior",
        "Zapata - transversal inferior",
    ):
        assert secondary_by_name[name].primary_steel_as_cm2_m == pytest.approx(0.0, abs=1e-9)
        assert secondary_by_name[name].required_as_cm2_m == pytest.approx(
            secondary_by_name[name].temperature_required_as_cm2_m
        )
    for case in secondary_by_name.values():
        assert case.provided_as_cm2_m >= case.required_as_cm2_m


def test_pure_wall_stem_cut_uses_continuous_bars_from_lower_grid() -> None:
    from bridge_design.domain.abutment import AbutmentGeometryInputs, AbutmentInputs
    from bridge_design.domain.cantilever_wall import solve_cantilever_wall_design

    result = solve_cantilever_wall_design(
        AbutmentInputs(
            geometry=AbutmentGeometryInputs(
                retained_height_m=7.8,
                footing_width_m=6.0,
                footing_thickness_m=0.95,
                toe_length_m=2.55,
                lower_stem_thickness_m=0.95,
                upper_stem_thickness_m=0.40,
                front_soil_depth_m=2.50,
            ),
            is_pure_wall=True,
        )
    )

    cut = result.stem_reinforcement_cut
    assert cut is not None
    assert cut.continuous_every_n_bars == 2
    assert cut.lower_spacing_m == pytest.approx(0.125)
    assert cut.upper_spacing_m == pytest.approx(0.250)
    assert cut.upper_spacing_m == pytest.approx(
        cut.continuous_every_n_bars * cut.lower_spacing_m
    )


def test_pure_wall_omits_cut_when_no_continuous_subset_is_possible() -> None:
    from bridge_design.domain.cantilever_wall import solve_cantilever_wall_design

    result = solve_cantilever_wall_design()

    assert result.stem_design.selected_spacing_m == pytest.approx(0.175)
    assert result.stem_reinforcement_cut is None


def test_pure_wall_main_stem_reinforcement_is_not_less_than_exterior_vertical_minimum() -> None:
    from bridge_design.domain.abutment import AbutmentGeometryInputs, AbutmentInputs
    from bridge_design.domain.cantilever_wall import solve_cantilever_wall_design

    result = solve_cantilever_wall_design(
        AbutmentInputs(
            geometry=AbutmentGeometryInputs(
                retained_height_m=2.45,
                footing_width_m=2.00,
                footing_thickness_m=0.50,
                toe_length_m=0.0001,
                lower_stem_thickness_m=0.30,
                upper_stem_thickness_m=0.30,
                front_soil_depth_m=1.00,
                seat_block_height_m=0.0,
                seat_wall_width_m=0.0,
                bearing_seat_length_m=0.0,
                backwall_drop_m=0.0,
                backwall_taper_height_m=0.0,
                backfill_step_width_m=0.0,
                small_batter_width_m=0.0,
            ),
            is_pure_wall=True,
        )
    )

    secondary_by_name = {case.name: case for case in result.secondary_reinforcement}
    exterior_vertical = secondary_by_name["Pantalla - vertical exterior"]

    assert result.stem_design.required_as_cm2_m == pytest.approx(5.018585, abs=1e-6)
    assert result.stem_design.required_as_cm2_m >= exterior_vertical.required_as_cm2_m


def test_pure_wall_footing_primary_reinforcement_uses_temperature_minimum() -> None:
    from bridge_design.domain.abutment import AbutmentGeometryInputs, AbutmentInputs
    from bridge_design.domain.cantilever_wall import solve_cantilever_wall_design

    result = solve_cantilever_wall_design(
        AbutmentInputs(
            geometry=AbutmentGeometryInputs(
                retained_height_m=2.45,
                footing_width_m=2.00,
                footing_thickness_m=0.50,
                toe_length_m=0.0001,
                lower_stem_thickness_m=0.30,
                upper_stem_thickness_m=0.30,
                front_soil_depth_m=1.00,
                seat_block_height_m=0.0,
                seat_wall_width_m=0.0,
                bearing_seat_length_m=0.0,
                backwall_drop_m=0.0,
                backwall_taper_height_m=0.0,
                backfill_step_width_m=0.0,
                small_batter_width_m=0.0,
            ),
            is_pure_wall=True,
        )
    )

    assert result.heel_design.required_as_cm2_m >= result.heel_design.temperature_as_cm2_m
    assert result.toe_design.required_as_cm2_m == pytest.approx(
        result.toe_design.temperature_as_cm2_m
    )
    assert result.toe_design.required_as_cm2_m == pytest.approx(3.642857, abs=1e-5)


def test_cantilever_wall_domain_api_uses_wall_names() -> None:
    from bridge_design.domain.cantilever_wall import (
        CantileverWallInputs,
        cantilever_wall_geometry_inputs,
        cantilever_wall_inputs,
        cantilever_wall_load_inputs,
        solve_cantilever_wall_design,
    )

    geometry = cantilever_wall_geometry_inputs()
    inputs = cantilever_wall_inputs(CantileverWallInputs())
    result = solve_cantilever_wall_design(inputs)

    assert geometry.seat_block_height_m == 0.0
    assert inputs.is_pure_wall is True
    assert inputs.loads == cantilever_wall_load_inputs()
    assert result.inputs.is_pure_wall is True


def test_abutment_geometry_prompt_includes_pdf_model_dimensions(monkeypatch) -> None:
    from bridge_design.cli.abutment_input_prompts import _collect_geometry

    answers = iter([""] * 15)
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)

    geometry = _collect_geometry(include_bridge_inputs=True)

    prompt_text = "\n".join(prompts)
    assert "t1 - Transicion frontal superior" in prompt_text
    assert "t2 - Retiro superior del relleno" in prompt_text
    assert "cajuela - Longitud horizontal de apoyo" in prompt_text
    assert "e parapeto - Espesor parapeto posterior" in prompt_text
    assert "altura cajuela - Altura del parapeto superior" in prompt_text
    assert "altura bloque cajuela" in prompt_text
    assert "altura transicion" in prompt_text
    assert geometry.small_batter_width_m > 0.0
    assert geometry.backwall_drop_m > 0.0
    assert geometry.backwall_taper_height_m > 0.0


def test_abutment_geometry_prompt_accepts_zero_optional_pdf_dimensions(monkeypatch) -> None:
    from bridge_design.cli.abutment_input_prompts import _collect_geometry

    answers = iter(
        [
            "7.8",
            "15",
            "6",
            "0.95",
            "2.1",
            "0.95",
            "0.95",
            "2.5",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
            "0",
        ]
    )

    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    geometry = _collect_geometry(include_bridge_inputs=True)

    assert geometry.small_batter_width_m == 0.0
    assert geometry.backfill_step_width_m == 0.0
    assert geometry.bearing_seat_length_m == 0.0
    assert geometry.seat_wall_width_m == 0.0
    assert geometry.seat_block_height_m == 0.0
    assert geometry.backwall_drop_m == 0.0
    assert geometry.backwall_taper_height_m == 0.0


def test_pure_wall_input_flow_omits_bridge_loads_and_key(monkeypatch) -> None:
    from bridge_design.cli.abutment_input_prompts import collect_abutment_inputs
    from bridge_design.domain.abutment import AbutmentLoadInputs

    answers = iter([""] * 30)
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)

    inputs = collect_abutment_inputs(
        element_label="muro",
        load_defaults=AbutmentLoadInputs(
            pdc_tn_m=0.0,
            pdw_tn_m=0.0,
            ppl_tn_m=0.0,
            pll_im_tn_m=0.0,
            braking_tn_m=0.0,
        ),
        include_bridge_inputs=False,
    )

    prompt_text = "\n".join(prompts)
    assert "PDC - carga muerta tablero" not in prompt_text
    assert "PLL+IM - carga viva vehicular" not in prompt_text
    assert "Considerar diente" not in prompt_text
    assert inputs.key.enabled is False
    assert inputs.is_pure_wall is True
    assert inputs.gamma_eq == pytest.approx(0.50)
    assert "gamma_EQ" in prompt_text


def test_wall_soil_prompt_accepts_zero_vehicular_surcharge(monkeypatch) -> None:
    from bridge_design.cli.abutment_input_prompts import _collect_soil
    from bridge_design.domain.abutment import AbutmentGeometryInputs

    answers = iter(["0", "", "", "", "", "", "", "", "", ""])
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)

    soil = _collect_soil(AbutmentGeometryInputs(), element_label="muro")

    assert soil.vehicular_surcharge_height_m == 0.0
    assert soil.allowable_bearing_kg_cm2 > 0.0
    assert "h' sobrecarga vehicular equivalente (m) [0.6]: " in prompts
    assert "qadm capacidad portante admisible (kg/cm2) [2.67]: " in prompts
    assert "theta cara posterior desde horizontal; vertical=90 (grados) [90]: " in prompts


def test_wall_soil_prompt_rejects_theta_measured_from_vertical(monkeypatch, capsys) -> None:
    from bridge_design.cli.abutment_input_prompts import _collect_soil
    from bridge_design.domain.abutment import AbutmentGeometryInputs

    answers = iter(["0", "", "28", "0", "", "5", "90", "", "", "", ""])

    def fake_input(prompt: str) -> str:
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)

    soil = _collect_soil(AbutmentGeometryInputs(), element_label="muro")

    assert soil.wall_backface_angle_deg == 90.0
    assert "trasdos vertical" in capsys.readouterr().out


def test_pure_wall_report_includes_shear_beta_trace() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result
    from bridge_design.domain.abutment import AbutmentInputs, solve_abutment_design

    result = solve_abutment_design(AbutmentInputs(is_pure_wall=True))
    report = format_abutment_design_result(
        result,
        title="DISENO DE MURO DE CONCRETO ARMADO EN CANTILEVER",
        primary_stability_title="MURO PURO",
    )

    assert result.stem_design.shear_beta_method == "general"
    assert "Beta de corte" in report
    assert "Metodo beta" in report
    assert "Profundidad efectiva cortante dv" in report


def test_pure_wall_report_omits_bridge_load_terms() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result
    from bridge_design.domain.abutment import (
        AbutmentGeometryInputs,
        AbutmentInputs,
        AbutmentLoadInputs,
        solve_abutment_design,
    )

    result = solve_abutment_design(
        AbutmentInputs(
            geometry=AbutmentGeometryInputs(backfill_step_width_m=0.0),
            loads=AbutmentLoadInputs(
                pdc_tn_m=0.0,
                pdw_tn_m=0.0,
                ppl_tn_m=0.0,
                pll_im_tn_m=0.0,
                braking_tn_m=0.0,
            ),
            is_pure_wall=True,
        )
    )
    report = format_abutment_design_result(
        result,
        title="DISENO DE MURO DE CONCRETO ARMADO EN CANTILEVER",
        primary_stability_title="MURO PURO",
    )

    assert "PDC tablero" not in report
    assert "PDW asfalto" not in report
    assert "PPL peatonal tablero" not in report
    assert "PLL+IM vehicular" not in report
    assert "PEQ superestructura" not in report
    assert "ESTRIBO CON PUENTE" not in report
    assert "DC estribo" not in report
    assert "con/sin puente" not in report.lower()
    assert "con puente" not in report.lower()
    assert "sin puente" not in report.lower()
    assert "cajuela" not in report.lower()
    assert "transicion" not in report.lower()
    assert "ESTABILIDAD SIN PUENTE" not in report
    assert "Altura total desde fondo de zapata" in report
    assert "e inferior pantalla" in report
    assert "e superior pantalla" in report
    assert "Mcr" in report
    assert "1.33Mu" in report
    assert "As por capacidad minima" in report
    assert "Operacion As requerido" in report
    assert "Control As requerido" in report


def test_pure_wall_report_uses_reorganized_design_structure() -> None:
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result
    from bridge_design.domain.abutment import AbutmentInputs, solve_abutment_design

    report = format_abutment_design_result(
        solve_abutment_design(AbutmentInputs(is_pure_wall=True)),
        title="DISENO DE MURO DE CONCRETO ARMADO EN CANTILEVER",
        primary_stability_title="MURO PURO",
    )

    assert "DATOS INGRESADOS Y CONSIDERADOS" in report
    assert "MURO PURO" in report
    assert "CARGAS VERTICALES" in report
    assert "CARGAS DC" in report
    assert "CARGAS HORIZONTALES" in report
    assert "ESTADOS LIMITES APLICABLES Y COMBINACIONES DE CARGAS" in report
    assert "CHEQUEO DE ESTABILIDAD Y ESFUERZOS" in report
    assert "CALCULO DE ACERO" in report
    assert "DISENO DE PANTALLA" in report
    assert "DISENO DE CIMENTACION" in report


def test_pyproject_exposes_wall_console_commands() -> None:
    with open("pyproject.toml", "rb") as file:
        pyproject = tomllib.load(file)

    scripts = pyproject["project"]["scripts"]
    assert scripts["bridge-cantilever-wall-design"] == "bridge_design.cantilever_wall_main:main"
    assert scripts["bridge-muro-cantilever"] == "bridge_design.cantilever_wall_main:main"
