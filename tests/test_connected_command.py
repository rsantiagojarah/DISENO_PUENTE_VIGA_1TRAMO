from copy import deepcopy
import json
from pathlib import Path
import tomllib

import pytest

from bridge_design.cli.connected_yaml import connected_inputs_from_yaml, connected_yaml_template
from bridge_design.cli.yaml_io import load_yaml_file
from bridge_design.connected_main import main


def test_template_requires_subgrade_and_interface_friction():
    data = connected_yaml_template()
    with pytest.raises(ValueError, match="balasto"):
        connected_inputs_from_yaml(data)
    data["suelo_cimentacion"]["modulo_balasto_vertical_tn_m3"] = 3000
    with pytest.raises(ValueError, match="friccion_interfaz"):
        connected_inputs_from_yaml(data)


def test_independent_editable_geometry_and_load_pairs():
    data = connected_yaml_template(example=True)
    data["estribo_derecho"]["geometria"]["altura_relleno_activo_m"] = 8.0
    left_loads = deepcopy(data["estribo_izquierdo"]["cargas_tablero"])
    right_loads = deepcopy(left_loads)
    right_loads["pll_im_vehicular_tn_m"] = 2.5
    data["casos_simultaneos"] = [{"nombre": "Vehiculo cerca de izquierda",
                                 "cargas_izquierda": left_loads, "cargas_derecha": right_loads,
                                 "factor_sobrecarga_derecha": 0.0}]
    result = connected_inputs_from_yaml(data)
    assert result.right.geometry.retained_height_m == 8
    assert result.cases[0].right.pll_im_tn_m == 2.5
    assert result.cases[0].right_surcharge == 0


def test_console_commands_registered_and_dispatched(monkeypatch):
    import bridge_design.main as bridge_main
    import bridge_design.connected_main as connected_main
    calls = []
    monkeypatch.setattr(connected_main, "main", lambda args: calls.append(args))
    bridge_main.main(["estribos-conectados", "--help"])
    assert calls == [["--help"]]
    with Path("pyproject.toml").open("rb") as stream:
        assert tomllib.load(stream)["project"]["scripts"]["diseno-estribos-conectados"] == "bridge_design.connected_main:main"


def test_output_generates_template_and_cli_runs_complete_example(tmp_path, capsys):
    template = tmp_path / "modelo.yaml"
    main(["output", str(template), "--ejemplo"])
    assert load_yaml_file(template)["suelo_cimentacion"]["modulo_balasto_vertical_tn_m3"] == 3000
    destination = tmp_path / "resultados"
    main(["input", str(template), "--resultados", str(destination), "--automatico", "--sin-word", "--verificar-malla"])
    document = json.loads((destination / "resultados.json").read_text(encoding="utf-8"))
    assert len(document["results"]) == 17
    assert all("Mixta" not in case["name"] for case in document["results"])
    assert document["reinforcement"]
    assert document["mesh_comparison"]["fine_step"] == 0.25
    assert (destination / "nodos.csv").exists()
    assert (destination / "esfuerzos.csv").exists()
    assert (destination / "geometria.png").exists()
    assert "ANALISIS Y DISENO" in capsys.readouterr().out


def test_cli_invalid_input_exits_nonzero_without_reports(tmp_path):
    template = tmp_path / "obligatorio.yaml"
    main(["output", str(template)])
    destination = tmp_path / "sin_resultados"
    with pytest.raises(SystemExit) as error:
        main(["input", str(template), "--resultados", str(destination)])
    assert error.value.code == 2
    assert not destination.exists()


def test_nonfinite_data_are_rejected():
    data = connected_yaml_template(example=True)
    data["estribo_izquierdo"]["cargas_tablero"]["pdc_carga_muerta_tablero_tn_m"] = float("nan")
    with pytest.raises(ValueError, match="finito"):
        connected_inputs_from_yaml(data)
