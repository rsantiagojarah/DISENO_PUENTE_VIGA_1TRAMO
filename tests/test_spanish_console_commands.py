import tomllib

import bridge_design.main as bridge_main


def test_bridge_design_tablero_dispatches_to_full_bridge_design(monkeypatch) -> None:
    called = []

    def fake_bridge_design() -> None:
        called.append(True)

    monkeypatch.setattr(bridge_main, "run_bridge_design", fake_bridge_design)

    bridge_main.main(["tablero"])

    assert called == [True]


def test_pyproject_exposes_simple_spanish_console_commands() -> None:
    with open("pyproject.toml", "rb") as file:
        pyproject = tomllib.load(file)

    scripts = pyproject["project"]["scripts"]
    assert scripts["diseno-tablero"] == "bridge_design.main:main"
    assert scripts["diseno-estribos"] == "bridge_design.abutment_main:main"
    assert scripts["diseno-apoyos"] == "bridge_design.cli.bearing_cli:main"
    assert scripts["diseno-apoyos-neopreno"] == "bridge_design.cli.simple_neoprene_cli:main"
    assert scripts["diseno-muros"] == "bridge_design.cantilever_wall_main:main"
