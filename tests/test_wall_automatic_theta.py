"""Automatic theta must follow the entered geometry and preserve explicit overrides."""
from dataclasses import replace

import pytest

from bridge_design.cli.abutment_input_prompts import _collect_soil
from bridge_design.cli.yaml_inputs import (
    abutment_inputs_from_yaml,
    abutment_yaml_template,
    cantilever_wall_inputs_from_yaml,
    cantilever_wall_yaml_template,
)
from bridge_design.domain.abutment import AbutmentGeometryInputs, pure_wall_geometry_inputs

KEY = "theta_cara_posterior_desde_horizontal_grados"


def geometry():
    return pure_wall_geometry_inputs(AbutmentGeometryInputs(
        retained_height_m=7.25, footing_thickness_m=1.0,
        lower_stem_thickness_m=1.0, upper_stem_thickness_m=0.5,
    ))


@pytest.mark.parametrize("answer", ["", "auto", " AUTO "])
def test_enter_or_auto_uses_full_precision_geometry(monkeypatch, capsys, answer):
    answers = iter(["", "", "", "", "", "", answer, "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    soil = _collect_soil(geometry(), element_label="muro")
    assert soil.wall_backface_angle_deg == pytest.approx(85.42607874009914, abs=1e-12)
    assert "theta adoptado = 85.42607874" in capsys.readouterr().out


@pytest.mark.parametrize("answer, expected", [("90", 90.0), ("88", 88.0)])
def test_console_preserves_manual_choice(monkeypatch, answer, expected):
    answers = iter(["", "", "", "", "", "", answer, "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert _collect_soil(geometry(), element_label="muro").wall_backface_angle_deg == expected


def test_equal_thickness_auto_is_vertical(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    g = replace(geometry(), upper_stem_thickness_m=1.0)
    assert _collect_soil(g, element_label="muro").wall_backface_angle_deg == 90.0


def test_invalid_automatic_slope_reprompts_without_silent_geometry_change(monkeypatch, capsys):
    answers = iter(["", "", "", "", "", "5", "", "90", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    soil = _collect_soil(geometry(), element_label="muro")
    assert soil.wall_backface_angle_deg == 90.0
    assert soil.backfill_slope_deg == 5.0
    assert "beta=0" in capsys.readouterr().out


@pytest.mark.parametrize("mode", ["auto", None, "omitted"])
def test_yaml_auto_recomputes_from_current_dimensions(mode):
    data = cantilever_wall_yaml_template()
    assert data["suelo_sismo"][KEY] == "auto"
    data["geometria"].update({
        "altura_relleno_activo_m": 7.25, "espesor_zapata_m": 1.0,
        "espesor_inferior_pantalla_m": 1.0, "espesor_superior_pantalla_m": 0.5,
    })
    if mode == "omitted":
        del data["suelo_sismo"][KEY]
    else:
        data["suelo_sismo"][KEY] = mode
    assert cantilever_wall_inputs_from_yaml(data).soil.wall_backface_angle_deg == pytest.approx(85.42607874009914)
    data["geometria"]["espesor_superior_pantalla_m"] = 1.0
    assert cantilever_wall_inputs_from_yaml(data).soil.wall_backface_angle_deg == 90.0


@pytest.mark.parametrize("theta", [90.0, 88.0])
def test_old_yaml_numeric_angles_are_not_overridden(theta):
    data = cantilever_wall_yaml_template()
    data["suelo_sismo"][KEY] = theta
    assert cantilever_wall_inputs_from_yaml(data).soil.wall_backface_angle_deg == theta


def test_yaml_auto_incompatible_slope_is_rejected():
    data = cantilever_wall_yaml_template()
    data["suelo_sismo"]["beta_pendiente_relleno_grados"] = 5.0
    with pytest.raises(ValueError, match="beta=0"):
        cantilever_wall_inputs_from_yaml(data)


def test_abutment_keeps_vertical_default_and_does_not_enable_auto(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert _collect_soil(AbutmentGeometryInputs()).wall_backface_angle_deg == 90.0
    data = abutment_yaml_template()
    assert data["suelo_sismo"][KEY] == 90.0
    assert abutment_inputs_from_yaml(data).soil.wall_backface_angle_deg == 90.0
    data["suelo_sismo"][KEY] = "auto"
    with pytest.raises(ValueError, match="solo en diseno-muros"):
        abutment_inputs_from_yaml(data)
