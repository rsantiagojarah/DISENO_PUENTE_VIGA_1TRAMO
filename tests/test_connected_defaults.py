import pytest

from bridge_design.cli.connected_prompts import collect_connected_inputs
from bridge_design.cli.connected_yaml import connected_inputs_from_yaml, connected_yaml_template
from bridge_design.cli.yaml_inputs import abutment_inputs_from_yaml, abutment_yaml_template
from bridge_design.domain.abutment import AbutmentGeometryInputs, AbutmentLoadInputs
from bridge_design.domain.connected_defaults import connected_geometry_defaults, connected_load_defaults
from bridge_design.domain.connected_geometry import build_connected_mesh
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil


def test_pdf_geometry_default_matches_dimensions_and_reference_node():
    inputs = ConnectedInputs(FoundationSoil(3000, 0.50, 26.7))
    geometry = inputs.left.geometry
    assert inputs.left.geometry == inputs.right.geometry == connected_geometry_defaults()
    assert inputs.left.loads == inputs.right.loads == connected_load_defaults()
    assert geometry.retained_height_m == 10.70
    assert geometry.footing_width_m == 5.00
    assert geometry.footing_thickness_m == 1.50
    assert geometry.heel_length_m == pytest.approx(1.50)
    assert geometry.toe_length_m == 2.50
    assert geometry.lower_stem_thickness_m == geometry.upper_stem_thickness_m == 1.00
    assert geometry.seat_wall_width_m == geometry.backfill_step_width_m == 0.35
    assert geometry.stem_height_above_footing_m - geometry.seat_block_height_m == pytest.approx(8.05)
    assert (geometry.stem_height_above_footing_m - geometry.seat_block_height_m
            - geometry.backwall_drop_m - geometry.backwall_taper_height_m) == pytest.approx(7.15)
    assert inputs.clear_span_m == 13.10
    assert inputs.slab_thickness_m == 0.75
    assert inputs.left_transition_m == inputs.right_transition_m == 1.00
    assert inputs.total_length_m == pytest.approx(18.10)
    mesh = build_connected_mesh(inputs)
    assert mesh.frame.nodes[mesh.reference_node].x == pytest.approx(9.05)
    assert mesh.frame.fixed_dofs == (3 * mesh.reference_node,)


def test_yaml_geometry_uses_pdf_defaults_without_overriding_explicit_values():
    data = connected_yaml_template(example=True)
    default = connected_inputs_from_yaml(data)
    assert default.left.geometry == connected_geometry_defaults()
    data["estribo_izquierdo"]["geometria"] = {"altura_relleno_activo_m": 11.20}
    data["estribo_derecho"]["geometria"]["longitud_puntera_m"] = 2.25
    data["cimentacion"]["separacion_libre_entre_caras_interiores_m"] = 15.0
    data["cimentacion"]["transicion_izquierda_m"] = 0.0
    del data["cimentacion"]["transicion_derecha_m"]
    changed = connected_inputs_from_yaml(data)
    assert changed.left.geometry.retained_height_m == 11.20
    assert changed.left.geometry.footing_thickness_m == 1.50
    assert changed.right.geometry.toe_length_m == 2.25
    assert changed.clear_span_m == 15.0
    assert changed.left_transition_m == 0.0
    assert changed.right_transition_m == 1.0


@pytest.mark.parametrize("same_right", (True, False))
def test_interactive_enter_uses_pdf_dimensions_and_still_requires_soil(monkeypatch, same_right):
    prompts = []

    def answer(prompt):
        prompts.append(prompt)
        if prompt.startswith("Usar los mismos datos"):
            return "s" if same_right else "n"
        if prompt.startswith("Modulo de balasto"):
            assert "[" not in prompt
            return "3000"
        if prompt.startswith("Coeficiente de friccion interfaz"):
            return "0.50"
        if prompt.startswith("Presion admisible de cimentacion"):
            return "26.7"
        return ""

    monkeypatch.setattr("builtins.input", answer)
    inputs = collect_connected_inputs()
    assert inputs.left.geometry == inputs.right.geometry == connected_geometry_defaults()
    assert inputs.clear_span_m == 13.10
    assert inputs.left_transition_m == inputs.right_transition_m == 1.00
    assert inputs.soil.subgrade_tn_m3 == 3000
    assert inputs.left.loads == inputs.right.loads == connected_load_defaults()
    assert inputs.reference_position_m == pytest.approx(9.05)
    assert any("Separacion libre" in prompt and "[13.1]" in prompt for prompt in prompts)


def test_individual_abutment_defaults_remain_unchanged():
    geometry = AbutmentGeometryInputs()
    assert geometry.retained_height_m == 7.0
    assert geometry.footing_width_m == 4.70
    assert geometry.footing_thickness_m == 1.10
    assert abutment_inputs_from_yaml(abutment_yaml_template()).geometry == geometry
    assert abutment_inputs_from_yaml(abutment_yaml_template()).loads == AbutmentLoadInputs()


def test_connected_deck_reactions_default_and_yaml_overrides():
    expected = AbutmentLoadInputs(8.959, 0.545, 0.762, 6.92, 1.33)
    assert connected_load_defaults() == expected
    data = connected_yaml_template(example=True)
    loaded = connected_inputs_from_yaml(data)
    assert loaded.left.loads == loaded.right.loads == expected
    del data["estribo_izquierdo"]["cargas_tablero"]
    data["estribo_derecho"]["cargas_tablero"] = {"pll_im_vehicular_tn_m": 3.4, "br_frenado_tn_m": 0}
    changed = connected_inputs_from_yaml(data)
    assert changed.left.loads == expected
    assert changed.right.loads == AbutmentLoadInputs(8.959, 0.545, 0.762, 3.4, 0)


def test_repository_yaml_has_the_requested_reactions_on_both_sides():
    from bridge_design.cli.yaml_io import load_yaml_file
    from pathlib import Path

    data = load_yaml_file(Path("modelo_estribos_conectados.yaml"))
    for name in ("estribo_izquierdo", "estribo_derecho"):
        assert data[name]["cargas_tablero"] == connected_yaml_template()[name]["cargas_tablero"]
