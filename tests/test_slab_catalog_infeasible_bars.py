"""An infeasible diameter must not abort the slab's remaining alternatives."""

from dataclasses import replace
from math import isinf
from types import SimpleNamespace

import pytest

from bridge_design import main
from bridge_design.cli.ascii_output import _format_spacing_case_table
from bridge_design.domain import reinforcement as r
from bridge_design.domain.crack_control import review_slab_spacing_crack_control
from bridge_design.domain.rebar_catalog import custom_spacing_option
from bridge_design.domain.transverse_slab import TransverseSlabGeometry
from test_reinforcement import _materials


@pytest.fixture
def thin_slab():
    # Deliberately thin boundary case, not a proposed bridge design.
    geometry = TransverseSlabGeometry(2.1, .825, 4, .08, 1.2, .3)
    materials = _materials()
    params = r.SlabReinforcementParameters()
    steel = r._design_flexural_steel(
        "Acero positivo", "M+",
        SimpleNamespace(combined_moment_tn_m=.23,
                        combination_name="RESISTENCIA I", position_m=1.),
        100., 1., 8. - params.concrete_cover_cm - params.main_bar_diameter_cm / 2.,
        1.44, materials, params.flexural_resistance_factor, params,
    )
    return geometry, materials, params, steel


@pytest.mark.parametrize("bad_first", [False, True])
def test_slab_keeps_feasible_bars_when_one_diameter_has_no_solution(thin_slab, bad_first):
    geometry, materials, params, steel = thin_slab
    if bad_first:
        steel = replace(steel, spacing_options=replace(
            steel.spacing_options, options=tuple(reversed(steel.spacing_options.options))))
    updated = r._with_service_spacing_options(steel, geometry, materials, params, .10)
    case = updated.spacing_options
    assert {o.item: o.bar for o in case.options} == {o.item: o.bar for o in steel.spacing_options.options}
    invalid = next(o for o in case.options if o.bar.label == '1"')
    assert isinf(invalid.required_area_cm2_m)
    assert not invalid.is_compliant and not invalid.is_recommended
    assert invalid.crack_control_status is None
    selected = case.recommended
    assert selected is not None and selected.is_compliant
    assert selected.bar != invalid.bar
    assert selected.crack_control_status == "CUMPLE"
    assert updated.effective_depth_cm == pytest.approx(8. - 5. - selected.bar.diameter_cm / 2.)
    assert updated.required_area_cm2_m == selected.required_area_cm2_m
    # A feasible custom alternative still passes at its own diameter/depth.
    alternative = custom_spacing_option(case, '3/8"', .15)
    assert alternative.required_area_cm2_m == pytest.approx(3.67760648165)
    assert review_slab_spacing_crack_control(geometry, materials, .10, 5., alternative).is_compliant
    with pytest.raises(ValueError, match="no tiene una solucion de flexion viable"):
        custom_spacing_option(case, '1"', .10)
    table = "\n".join(_format_spacing_case_table(case))
    assert '3/8"' in table and '1"' not in table


def test_slab_cannot_select_infeasible_item_by_number(thin_slab, monkeypatch, capsys):
    geometry, materials, params, steel = thin_slab
    updated = r._with_service_spacing_options(steel, geometry, materials, params, .10)
    case = updated.spacing_options
    invalid = next(o for o in case.options if o.bar.label == '1"')
    answers = iter((str(invalid.item), ""))
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert main._prompt_spacing_option(case) == case.recommended
    assert "El item no existe para este caso" in capsys.readouterr().out


@pytest.mark.parametrize("no_depth", [False, True])
def test_slab_does_not_recommend_an_infeasible_fallback(thin_slab, no_depth):
    geometry, materials, params, steel = thin_slab
    if no_depth:
        geometry = replace(geometry, slab_thickness_m=.06)
    else:
        steel = replace(steel, minimum_capacity_moment_tn_m=10.)
    updated = r._with_service_spacing_options(steel, geometry, materials, params, .10)
    assert updated.spacing_options.recommended is None
    assert len(updated.spacing_options.options) == len(steel.spacing_options.options)
    assert all(isinf(o.required_area_cm2_m) and not o.is_compliant and not o.is_recommended
               for o in updated.spacing_options.options)
    with pytest.raises(ValueError, match="Sin solucion"):
        main._prompt_spacing_option(updated.spacing_options)


def test_slab_design_completes_all_groups_despite_infeasible_diameter(thin_slab, monkeypatch):
    geometry, materials, params, _ = thin_slab
    rows = tuple(
        SimpleNamespace(combination_name=name, limit_state=state, direction=direction,
                        position_m=1., combined_moment_tn_m=sign * moment)
        for name, state, moment in (("RESISTENCIA I", "Resistencia", .23), ("SERVICIO I", "Servicio", .10))
        for direction, sign in (("M+", 1.), ("M-", -1.))
    )
    monkeypatch.setattr(r, "combine_transverse_slab_moments", lambda _: rows)
    result = r.design_transverse_slab_reinforcement(geometry, materials, None, params)
    for steel in (result.negative, result.positive):
        assert steel.spacing_options.recommended.is_compliant
        assert not next(o for o in steel.spacing_options.options if o.bar.label == '1"').is_compliant
    assert result.temperature.spacing_options.recommended is not None
    assert result.distribution.spacing_options.recommended is not None
