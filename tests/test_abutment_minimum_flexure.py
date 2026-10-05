"""Regression for the conditional minimum capacity in individual toe design."""

from dataclasses import replace

import pytest

from bridge_design.domain import abutment
from bridge_design.domain.rebar_catalog import custom_spacing_option


@pytest.mark.parametrize("moment,minimum", [(100, 64.6148752047468), (55, 64.6148752047468), (20, 26.6)])
def test_toe_keeps_conditional_minimum_with_legacy_inputs(monkeypatch, moment, minimum):
    monkeypatch.setattr(abutment, '_toe_design_demands', lambda *args: (moment, 1))
    neutral = abutment.AbutmentInputs()
    legacy = replace(neutral, reinforcement=replace(
        neutral.reinforcement, toe_moment_capacity_multiplier=1.33))
    original = abutment.solve_abutment_design(neutral)
    actual = abutment.solve_abutment_design(legacy)
    assert actual.toe_design == original.toe_design
    assert actual.toe_design.controlling_moment_tn_m_m == moment
    assert actual.toe_design.minimum_capacity_moment_tn_m_m == pytest.approx(minimum)
    assert actual.toe_design.multiplier_minimum_moment_tn_m_m == pytest.approx(1.33*moment)


def test_adopted_toe_steel_is_checked_without_extra_factor_or_spacing_changes(monkeypatch):
    monkeypatch.setattr(abutment, '_toe_design_demands', lambda *args: (100, 1))
    inputs = abutment.AbutmentInputs()
    inputs = replace(inputs, reinforcement=replace(
        inputs.reinforcement, toe_moment_capacity_multiplier=1.33))
    preliminary = abutment.solve_abutment_design(inputs)
    chosen = custom_spacing_option(preliminary.toe_design.spacing_options, '1"', .175)
    result = abutment.solve_abutment_design(
        inputs, selected_reinforcement={'Zapata - puntera inferior': chosen})
    toe = result.toe_design
    # The chosen resistance covers Mu=100, but does not cover 1.33Mu=133.
    assert 100 < toe.moment_resistance_tn_m_m < 133
    assert toe.moment_status == 'OK'
    assert toe.selected_spacing_m == .175
    assert toe.provided_as_cm2_m == pytest.approx(chosen.provided_area_cm2_m)
