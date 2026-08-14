import yaml


def test_abutment_yaml_output_and_input_direct(tmp_path, monkeypatch) -> None:
    from bridge_design import abutment_main
    from bridge_design.domain.abutment import AbutmentInputs

    path = tmp_path / "modelo_estribo.yaml"
    abutment_main.main(["output", str(path)])

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["comando"] == "diseno-estribos"
    assert "geometria" in data
    assert "ancho_zapata_m" in data["geometria"]
    assert list(data["geometria"])[:8] == [
        "altura_relleno_activo_m",
        "luz_puente_m",
        "ancho_zapata_m",
        "espesor_zapata_m",
        "longitud_puntera_m",
        "espesor_inferior_pantalla_m",
        "espesor_superior_pantalla_m",
        "altura_suelo_frontal_m",
    ]
    assert "diente" not in data

    captured = []

    def fake_run_abutment_design(**kwargs) -> None:
        captured.append(kwargs["inputs"])

    monkeypatch.setattr(abutment_main, "run_abutment_design", fake_run_abutment_design)
    abutment_main.main(["input", str(path)])

    assert isinstance(captured[0], AbutmentInputs)
    assert captured[0].is_pure_wall is False


def test_abutment_yaml_file_runs_full_contact_recommendation_case(tmp_path) -> None:
    from bridge_design.cli.yaml_inputs import abutment_inputs_from_yaml
    from bridge_design.domain.abutment import solve_abutment_design

    path = tmp_path / "estribo_7_8m.yaml"
    data = {
        "version_esquema": 1,
        "comando": "diseno-estribos",
        "geometria": {
            "altura_relleno_activo_m": 7.8,
            "luz_puente_m": 15.0,
            "ancho_zapata_m": 6.2,
            "espesor_zapata_m": 0.95,
            "longitud_puntera_m": 2.10,
            "espesor_inferior_pantalla_m": 0.95,
            "espesor_superior_pantalla_m": 0.95,
            "altura_suelo_frontal_m": 2.5,
            "transicion_frontal_superior_t1_m": 0.0,
            "retiro_superior_relleno_t2_m": 0.2,
            "longitud_cajuela_m": 0.8,
            "espesor_parapeto_posterior_m": 0.35,
            "altura_cajuela_m": 1.15,
            "altura_bloque_cajuela_m": 0.4,
            "altura_transicion_m": 0.95,
            "altura_apoyo_a_cajuela_m": 1.8,
            "franja_analisis_m": 1.0,
        },
        "materiales": {
            "fc_concreto_kg_cm2": 210.0,
            "fy_acero_kg_cm2": 4200.0,
            "peso_unitario_concreto_tn_m3": 2.4,
            "peso_unitario_relleno_tn_m3": 1.925,
        },
        "cargas_tablero": {
            "pdc_carga_muerta_tablero_tn_m": 12.0,
            "pdw_superficie_tn_m": 1.8,
            "ppl_peatonal_tablero_tn_m": 0.0,
            "pll_im_vehicular_tn_m": 9.494,
            "br_frenado_tn_m": 1.99,
        },
        "suelo_sismo": {
            "h_sobrecarga_vehicular_equivalente_m": 0.6,
            "qadm_capacidad_portante_kg_cm2": 2.67,
            "angulo_friccion_relleno_grados": 30.0,
            "delta_muro_suelo_grados": 0.0,
            "beta_pendiente_relleno_grados": 0.0,
            "theta_cara_posterior_desde_horizontal_grados": 90.0,
            "fs_capacidad_portante_nominal": 3.0,
            "pga": 0.3,
            "fpga": 1.2,
            "sobrecarga_peatonal_relleno_tn_m2": 0.0,
        },
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    inputs = abutment_inputs_from_yaml(yaml.safe_load(path.read_text(encoding="utf-8")))
    result = solve_abutment_design(inputs)

    assert result.footing_width_recommendation is None
    assert result.with_bridge[0].contact_type == "Parcial triangular"
    assert result.with_bridge[0].bearing_status == "OK"
    assert result.with_bridge[2].contact_type == "Parcial triangular"
    assert result.service_with_bridge[0].contact_type == "Completo"
    assert result.service_with_bridge[0].bearing_status == "OK"


def test_wall_yaml_output_and_input_direct(tmp_path, monkeypatch) -> None:
    from bridge_design import cantilever_wall_main
    from bridge_design.domain.abutment import AbutmentInputs

    path = tmp_path / "modelo_muro.yaml"
    cantilever_wall_main.main(["output", str(path)])

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["comando"] == "diseno-muros"
    assert list(data["geometria"]) == [
        "altura_relleno_activo_m",
        "ancho_zapata_m",
        "espesor_zapata_m",
        "longitud_puntera_m",
        "espesor_inferior_pantalla_m",
        "espesor_superior_pantalla_m",
        "altura_suelo_frontal_m",
    ]
    assert "cargas_tablero" not in data
    assert "diente" not in data
    data["cargas_tablero"] = {
        "pdc_carga_muerta_tablero_tn_m": 99.0,
        "pdw_superficie_tn_m": 99.0,
        "ppl_peatonal_tablero_tn_m": 99.0,
        "pll_im_vehicular_tn_m": 99.0,
        "br_frenado_tn_m": 99.0,
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    captured = []

    def fake_run_wall_design(inputs=None) -> None:
        captured.append(inputs)

    monkeypatch.setattr(cantilever_wall_main, "_run_wall_design", fake_run_wall_design)
    cantilever_wall_main.main(["input", str(path)])

    assert isinstance(captured[0], AbutmentInputs)
    assert captured[0].is_pure_wall is True
    assert captured[0].loads.pdc_tn_m == 0.0
    assert captured[0].loads.pdw_tn_m == 0.0
    assert captured[0].loads.ppl_tn_m == 0.0
    assert captured[0].loads.pll_im_tn_m == 0.0
    assert captured[0].loads.braking_tn_m == 0.0
    assert captured[0].geometry.seat_block_height_m == 0.0
    assert captured[0].geometry.bearing_seat_length_m == 0.0


def test_wall_yaml_helpers_expose_wall_named_api() -> None:
    from bridge_design.cli.yaml_inputs import cantilever_wall_inputs_from_yaml, cantilever_wall_yaml_template

    data = cantilever_wall_yaml_template()
    data["cargas_tablero"] = {
        "pdc_carga_muerta_tablero_tn_m": 10.0,
        "br_frenado_tn_m": 5.0,
    }

    inputs = cantilever_wall_inputs_from_yaml(data)

    assert data["comando"] == "diseno-muros"
    assert inputs.is_pure_wall is True
    assert inputs.loads.pdc_tn_m == 0.0
    assert inputs.loads.braking_tn_m == 0.0


def test_bearing_yaml_output_and_input_direct(tmp_path, monkeypatch) -> None:
    from bridge_design.cli import bearing_cli
    from bridge_design.domain.elastomeric_bearing import ElastomericBearingInputs

    path = tmp_path / "modelo_apoyos.yaml"
    bearing_cli.main(["output", str(path)])

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["comando"] == "diseno-apoyos"
    assert "cargas_servicio_por_apoyo" in data
    assert "temperatura_superior_c" not in data["movimientos"]
    assert "adoptar_dimensiones_planta_manualmente" in data["material_geometria"]

    captured = []

    def fake_run_bearing_design(inputs=None) -> None:
        captured.append(inputs)

    monkeypatch.setattr(bearing_cli, "run_bearing_design", fake_run_bearing_design)
    bearing_cli.main(["input", str(path)])

    assert isinstance(captured[0], ElastomericBearingInputs)


def test_deck_yaml_output_and_input_direct(tmp_path, monkeypatch) -> None:
    import bridge_design.main as bridge_main
    from bridge_design.domain.project_inputs import ProjectInputs

    path = tmp_path / "modelo_tablero.yaml"
    bridge_main.main(["output", str(path)])

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["comando"] == "diseno-tablero"
    assert list(data)[3:8] == [
        "modelo_transversal_losa",
        "materiales",
        "barrera_concreto",
        "cargas_vivas",
        "ubicacion_cargas_modelo_transversal",
    ]

    captured = []

    def fake_run_bridge_design(project_inputs=None) -> None:
        captured.append(project_inputs)

    monkeypatch.setattr(bridge_main, "run_bridge_design", fake_run_bridge_design)
    bridge_main.main(["input", str(path)])

    assert isinstance(captured[0], ProjectInputs)
