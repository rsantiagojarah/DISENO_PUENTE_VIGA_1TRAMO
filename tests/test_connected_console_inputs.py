from dataclasses import replace

import pytest

from bridge_design.domain.connected_inputs import default_connected_side
from bridge_design.cli import connected_prompts as prompts


def test_console_collects_common_materials_without_case_or_anchor_questions(monkeypatch):
    side = default_connected_side()
    side = replace(side, materials=replace(side.materials, concrete_strength_kg_cm2=280))
    monkeypatch.setattr(prompts, "collect_abutment_inputs", lambda **kwargs: side)
    values = {
        "Modulo de balasto vertical OBLIGATORIO": 3000,
        "Altura adicional del apoyo sobre la cajuela para el brazo de frenado": .35,
    }
    def numeric_prompt(label, unit, default=None):
        assert "discretizacion" not in label
        assert "recubrimiento" not in label.lower()
        assert "barras" not in label.lower()
        assert "Incremento" not in label
        return values.get(label, default)
    monkeypatch.setattr(prompts, "prompt_float", numeric_prompt)
    monkeypatch.setattr(prompts, "prompt_non_negative_float", lambda label, unit, default=None: values.get(label, default))
    monkeypatch.setattr(prompts, "prompt_int", lambda label, default, minimum=1: 41 if "resorte" in label else 1)
    def yes_no(label, default=True):
        assert "materiales" not in label.lower()
        assert "anclaje" not in label.lower()
        assert "pares" not in label.lower()
        return default
    monkeypatch.setattr(prompts, "yes_no", yes_no)
    def unexpected_input(label):
        pytest.fail(f"Unexpected console question: {label}")
    monkeypatch.setattr("builtins.input", unexpected_input)
    result = prompts.collect_connected_inputs()
    assert result.left.reinforcement.stem_cover_cm == 7.5
    assert result.right.reinforcement.stem_cover_cm == 7.5
    assert result.left.reinforcement.footing_cover_cm == 7.5
    assert result.right.reinforcement.footing_cover_cm == 7.5
    assert result.right.reinforcement.minimum_spacing_m == .10
    assert result.right.reinforcement.maximum_spacing_m == .30
    assert result.right.reinforcement.spacing_step_m == .025
    assert result.right.geometry.bridge_seat_to_bearing_height_m == .35
    assert result.slab_materials == result.left.materials == result.right.materials == side.materials
    assert result.slab_cover_cm == 7.5
    assert result.mesh_size_m == .5
    assert result.foundation_node_count == 41
    assert result.anchor_lengths_m == {}
    assert result.cases == ()
    assert result.left.loads == result.right.loads == side.loads
    assert result.soil.allowable_tn_m2 == pytest.approx(side.soil.allowable_bearing_kg_cm2*10)
    assert result.soil.friction_coefficient == 0.0


def test_console_retains_individual_abutment_internal_spacing_defaults(monkeypatch):
    from bridge_design.domain.abutment import AbutmentReinforcementInputs
    side = default_connected_side()
    def unexpected_prompt(*args):
        pytest.fail("Internal spacing parameters must not be requested")
    monkeypatch.setattr(prompts, "prompt_float", unexpected_prompt)
    monkeypatch.setattr(prompts, "prompt_non_negative_float", lambda label, unit, default=None: default)
    result = prompts._collect_connected_detailing(side, "izquierdo")
    defaults = AbutmentReinforcementInputs()
    assert result.reinforcement.minimum_spacing_m == defaults.minimum_spacing_m
    assert result.reinforcement.maximum_spacing_m == defaults.maximum_spacing_m
    assert result.reinforcement.spacing_step_m == defaults.spacing_step_m
