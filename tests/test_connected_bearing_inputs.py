from copy import deepcopy

import pytest

from bridge_design.cli.abutment_input_prompts import collect_abutment_inputs
from bridge_design.cli.connected_prompts import collect_connected_inputs
from bridge_design.cli.connected_yaml import connected_inputs_from_yaml, connected_yaml_template


@pytest.mark.parametrize("same_right", (True, False))
def test_connected_bearing_entered_once_and_shared_with_foundation(monkeypatch, capsys, same_right):
    prompts = []

    def answer(prompt):
        prompts.append(prompt)
        if prompt.startswith("Usar las mismas reacciones"):
            return "s" if same_right else "n"
        if prompt.startswith("qadm capacidad"):
            return "1.35"
        if prompt.startswith("FS capacidad"):
            return "4"
        if prompt.startswith("Modulo de balasto"):
            return "620"
        if prompt.startswith("Coeficiente de friccion"):
            return "0"
        if prompt.startswith("H activo") and sum(item.startswith("H activo") for item in prompts) == 2:
            return "11.2"
        if prompt.startswith(("Presion admisible de cimentacion", "FS para estimar")):
            pytest.fail("La cimentacion no debe volver a solicitar qadm ni FS.")
        return ""

    monkeypatch.setattr("builtins.input", answer)
    data = collect_connected_inputs()
    assert sum(prompt.startswith("qadm capacidad") for prompt in prompts) == 1
    assert sum(prompt.startswith("FS capacidad") for prompt in prompts) == 1
    assert data.left.soil.allowable_bearing_kg_cm2 == data.right.soil.allowable_bearing_kg_cm2 == 1.35
    assert data.soil.allowable_tn_m2 == pytest.approx(13.5)
    assert data.left.soil.bearing_capacity_factor_fs == data.right.soil.bearing_capacity_factor_fs == 4
    assert data.soil.nominal_bearing_fs == 4
    assert data.soil.subgrade_tn_m3 == 620
    assert data.right.geometry == data.left.geometry
    assert data.right.geometry.retained_height_m == 10.7
    assert sum(prompt.startswith("H activo") for prompt in prompts) == 1
    assert "1.35 kg/cm2 = 13.5 Tn/m2" in capsys.readouterr().out


@pytest.mark.parametrize("legacy", (False, True))
def test_yaml_has_one_authoritative_bearing_input_and_loads_legacy_files(legacy):
    raw = connected_yaml_template(example=True)
    if legacy:
        common = raw.pop("estribo")
        raw["estribo_izquierdo"] = deepcopy(common)
        raw["estribo_derecho"] = deepcopy(common)
    raw["suelo_cimentacion"].update(qadm_tn_m2=13.5, fs_capacidad_nominal=4)
    for name in (("estribo_izquierdo", "estribo_derecho") if legacy else ("estribo",)):
        assert "qadm_capacidad_portante_kg_cm2" not in raw[name]["suelo_sismo"]
        assert "fs_capacidad_portante_nominal" not in raw[name]["suelo_sismo"]
        if legacy:
            raw[name]["suelo_sismo"].update(qadm_capacidad_portante_kg_cm2=2.67,
                                          fs_capacidad_portante_nominal=3)
    original = deepcopy(raw)
    data = connected_inputs_from_yaml(raw)
    assert raw == original
    assert data.soil.allowable_tn_m2 == 13.5
    assert data.soil.nominal_bearing_fs == 4
    for side in (data.left, data.right):
        assert side.soil.allowable_bearing_kg_cm2 == pytest.approx(1.35)
        assert side.soil.bearing_capacity_factor_fs == 4


def test_individual_abutment_keeps_bearing_questions(monkeypatch):
    prompts = []

    def answer(prompt):
        prompts.append(prompt)
        if prompt.startswith("qadm capacidad"):
            return "1.35"
        if prompt.startswith("FS capacidad"):
            return "4"
        return ""

    monkeypatch.setattr("builtins.input", answer)
    data = collect_abutment_inputs(collect_key=False)
    assert sum(prompt.startswith("qadm capacidad") for prompt in prompts) == 1
    assert sum(prompt.startswith("FS capacidad") for prompt in prompts) == 1
    assert data.soil.allowable_bearing_kg_cm2 == 1.35
    assert data.soil.bearing_capacity_factor_fs == 4
