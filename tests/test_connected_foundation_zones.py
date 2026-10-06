"""The centre service peak must not disqualify valid continuous steel near walls."""

import csv
import json
from dataclasses import replace

import pytest

from bridge_design.cli.connected_2_yaml import connected_2_inputs_from_yaml, connected_2_yaml_template
from bridge_design.cli.connected_selection import collect_connected_selection
from bridge_design.domain.connected_design import solve_connected_abutments
from bridge_design.domain.connected_foundation_zones import foundation_zone_choice
from bridge_design.domain.connected_options import (
    apply_connected_selections, check_region_choice, choice_from_steel, connected_reinforcement_options,
)
from bridge_design.domain.connected_reinforcement import ConnectedBarChoice, ConnectedSteelChoice
from bridge_design.reporting.connected_cut_report import foundation_cut_rows
from bridge_design.reporting.connected_export import export_connected_results

TOP = "Zapata combinada - longitudinal superior"
BOTTOM = "Zapata combinada - longitudinal inferior"


@pytest.fixture(scope="module")
def analysis():
    raw = connected_2_yaml_template(example=True)
    raw["estribo"]["geometria"]["altura_parapeto_m"] = 1.22
    raw["estribo"]["materiales"].update(fc_concreto_kg_cm2=280, peso_unitario_relleno_tn_m3=2.038)
    raw["estribo"]["suelo_sismo"].update(angulo_friccion_relleno_grados=36.12, pga=.5, fpga=1)
    raw["suelo_cimentacion"].update(modulo_balasto_vertical_tn_m3=620, qadm_tn_m2=13.5)
    raw["cimentacion"]["cantidad_nudos_cimentacion"] = 82
    return solve_connected_abutments(connected_2_inputs_from_yaml(raw))


@pytest.fixture(scope="module")
def zonal(analysis):
    choice = foundation_zone_choice(ConnectedBarChoice('1"', .20, True))
    return apply_connected_selections(analysis, {TOP: choice, BOTTOM: choice})


def test_local_continuous_steel_passes_despite_failing_at_centre(analysis, zonal):
    value = ConnectedBarChoice('1"', .20)
    uniform = check_region_choice(analysis, TOP, ConnectedSteelChoice(value, value))
    assert uniform.crack_utilization == pytest.approx(3008.7687565/2520)
    top = next(s for s in zonal.reinforcement if s.region == TOP)
    cut = top.foundation_reinforcement_cut
    assert cut.status == "APLICA" and top.status == "OK"
    assert top.spacing_m == .1 and cut.pattern.equivalent_spacing_m == .2
    assert cut.pattern.cycle_bars == 2  # Explicit base cannot silently become a denser pattern.
    left, centre, right = cut.zones
    assert [z.reinforcement for z in cut.zones] == ["Solo continuo", "Continuo + adicional", "Solo continuo"]
    assert [z.area_cm2_m for z in cut.zones] == [25, 50, 25]
    assert all(z.status == "OK" and z.crack_utilization <= 1 for z in cut.zones)
    assert centre.service_moment_tn_m_m == pytest.approx(-95.608892584)
    assert abs(left.service_moment_tn_m_m) < abs(centre.service_moment_tn_m_m)
    assert abs(right.service_moment_tn_m_m) < abs(centre.service_moment_tn_m_m)
    assert cut.cutoff_left_m < cut.theoretical_left_m
    assert zonal.results is analysis.results  # No load/FRAME changes.


def test_bottom_additional_steel_at_both_ends(zonal):
    steel = next(s for s in zonal.reinforcement if s.region == BOTTOM)
    cut = steel.foundation_reinforcement_cut
    assert cut.status == "APLICA"
    assert [z.area_cm2_m for z in cut.zones] == [50, 25, 50]
    assert len(cut.additional_intervals_m) == 2
    assert all(z.status == "OK" for z in cut.zones)


def test_user_model_stem_continues_one_in_two(zonal):
    stem = next(s for s in zonal.reinforcement if s.region == "Pantalla - vertical relleno")
    cut = stem.stem_reinforcement_cut
    assert cut.status == "OK"
    assert cut.lower_bar_label == cut.upper_bar_label == '1"'
    assert cut.lower_spacing_m == .1 and cut.upper_spacing_m == .2
    assert cut.continuous_every_n_bars == 2
    assert cut.constructive_cut_height_m == pytest.approx(
        cut.theoretical_cut_height_m + stem.required_straight_anchor_cm / 100)
    assert cut.constructive_cut_height_m < 6.896  # Earlier proposal retaining only one in three.


def test_console_cut_table_and_enter_retain_families(analysis, zonal, monkeypatch):
    from bridge_design.cli.connected_selection import format_connected_options
    group = next(g for g in connected_reinforcement_options(analysis) if g.region == TOP)
    chosen = next(c for c in group.cuts if c.bar_label == '1"' and abs(c.light_spacing_m - .2) < 1e-9)
    text = format_connected_options((group,))
    assert "CORTES - " + TOP in text and chosen.location_text in text
    assert "Cortes definitivos" not in text
    assert not any(c.bar_label == '3/4"' and abs(c.light_spacing_m - .2) < 1e-9 for c in group.cuts)
    stem = next(g for g in connected_reinforcement_options(analysis) if g.region == "Pantalla - vertical relleno")
    assert stem.offer_cuts and all("sobre la base" in c.location_text for c in stem.cuts)
    assert all(abs(c.light_spacing_m - 2 * c.heavy_spacing_m) < 1e-9 for c in (*group.cuts, *stem.cuts))
    answers = iter(('s', chosen.code.lower()))
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    choice = collect_connected_selection(analysis, (group,))[TOP]
    assert choice.foundation_continuous.spacing_m == .20 and choice.principal.spacing_m == .10
    group = next(g for g in connected_reinforcement_options(zonal) if g.region == TOP)
    answers = iter(('s', ''))
    assert collect_connected_selection(zonal, (group,))[TOP] == choice_from_steel(group.adopted)


@pytest.mark.parametrize("spacing", [.05, .4, float('nan'), float('inf')])
def test_invalid_spacing_rejected(analysis, spacing):
    with pytest.raises(ValueError):
        check_region_choice(analysis, TOP, foundation_zone_choice(ConnectedBarChoice('1"', spacing)))


def test_mismatched_families_and_other_regions_rejected(analysis):
    choice = foundation_zone_choice(ConnectedBarChoice('1"', .2))
    with pytest.raises(ValueError, match="dos familias"):
        check_region_choice(analysis, TOP, replace(choice, foundation_continuous=ConnectedBarChoice('3/4"', .2)))
    with pytest.raises(ValueError, match="solo corresponde"):
        check_region_choice(analysis, "Pantalla - vertical relleno", choice)


def test_failed_full_family_does_not_produce_zones_or_cut(analysis):
    steel = check_region_choice(analysis, TOP, foundation_zone_choice(ConnectedBarChoice('3/4"', .2)))
    assert steel.status == "NO CUMPLE"
    assert steel.foundation_reinforcement_cut.status == "NO APLICA"
    assert not steel.foundation_reinforcement_cut.zones
    assert steel.foundation_reinforcement_cut.cutoff_left_m is None


def test_reports_and_reselection_remove_old_zone_checks(zonal, tmp_path):
    export_connected_results(zonal, tmp_path)
    zones = list(csv.DictReader((tmp_path/'zonas_zapata.csv').open(encoding='utf-8-sig')))
    assert len(zones) == 6 and all(z['estado'] == 'OK' for z in zones)
    payload = json.loads((tmp_path/'resultados.json').read_text(encoding='utf-8'))
    assert payload['selected_reinforcement'][TOP]['foundation_continuous']['spacing_m'] == .2
    for steel in zonal.reinforcement:
        if steel.region in (TOP, BOTTOM):
            text = str(foundation_cut_rows(steel))
            assert 'Familia continua solicitada' in text and 'Momento de servicio local' in text
    value = ConnectedBarChoice('1"', .2)
    updated = apply_connected_selections(zonal, {TOP: ConnectedSteelChoice(value, value)})
    cut = next(s for s in updated.reinforcement if s.region == TOP).foundation_reinforcement_cut
    assert not cut.zones and cut.requested_continuous_spacing_m is None
    export_connected_results(updated, tmp_path)
    zones = list(csv.DictReader((tmp_path/'zonas_zapata.csv').open(encoding='utf-8-sig')))
    assert not any(z['distribucion'] == TOP for z in zones)
