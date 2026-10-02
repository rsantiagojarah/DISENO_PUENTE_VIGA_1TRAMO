import json

import pytest

from bridge_design.cli.connected_selection import collect_connected_selection, format_connected_options
from bridge_design.domain.connected_design import solve_connected_abutments
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil
from bridge_design.domain.connected_options import (
    apply_connected_selections, check_region_choice, choice_from_steel, connected_reinforcement_options,
)
from bridge_design.domain.connected_reinforcement import ConnectedBarChoice, ConnectedSteelChoice
from bridge_design.reporting.connected_export import export_connected_results


@pytest.fixture(scope="module")
def analysis():
    return solve_connected_abutments(ConnectedInputs(FoundationSoil(3000, 0.50, 26.7),
                                      mesh_size_m=1.0, include_without_bridge=False))


@pytest.fixture(scope="module")
def groups(analysis):
    return connected_reinforcement_options(analysis)


def test_options_and_default_selection_preserve_checks(analysis, groups, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    selected = collect_connected_selection(analysis, groups)
    adopted = apply_connected_selections(analysis, selected)
    assert adopted.reinforcement == analysis.reinforcement
    assert adopted.results is analysis.results
    assert len(selected) == len(analysis.reinforcement)
    assert all(group.transverse.recommended for group in groups)
    output = format_connected_options(groups)
    assert "Item" in output and "PRINCIPAL" in output and "TRANSVERSAL" in output
    assert "NO CUMPLE" in output


def test_custom_console_selection_rechecks_and_exports_adopted_steel(analysis, groups, monkeypatch, tmp_path):
    group = next(group for group in groups if group.region == "Parapeto izquierda")
    answers = iter(("s", "p", '3/4"', "0,15", "4"))
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    selected = collect_connected_selection(analysis, (group,))
    adopted = apply_connected_selections(analysis, selected)
    steel = next(steel for steel in adopted.reinforcement if steel.region == group.region)
    assert steel.bar_label == '3/4"'
    assert steel.spacing_m == 0.15
    assert steel.area_per_face_cm2_m == pytest.approx(2.84 / 0.15)
    assert steel.required_straight_anchor_cm > group.adopted.required_straight_anchor_cm
    assert steel.axial_moment_utilization < group.adopted.axial_moment_utilization
    assert steel.status == "OK"
    export_connected_results(adopted, tmp_path)
    data = json.loads((tmp_path / "resultados.json").read_text(encoding="utf-8"))
    assert data["selected_reinforcement"][group.region]["principal"]["spacing_m"] == 0.15
    assert next(row for row in data["reinforcement"] if row["region"] == group.region)["bar_label"] == '3/4"'


@pytest.mark.parametrize("label,spacing", [('1/2"', float("nan")), ('1/2"', 0), ('1/2"', 0.50), ('9"', 0.15), ('3/8"', 0.15)])
def test_invalid_custom_reinforcement_is_rejected(analysis, label, spacing):
    choice = ConnectedSteelChoice(ConnectedBarChoice(label, spacing), ConnectedBarChoice('1/2"', 0.15))
    with pytest.raises(ValueError):
        check_region_choice(analysis, "Parapeto izquierda", choice)


def test_inadequate_selected_steel_stays_noncompliant(analysis):
    choice = ConnectedSteelChoice(ConnectedBarChoice('1/2"', 0.30), ConnectedBarChoice('1/2"', 0.30))
    steel = check_region_choice(analysis, "Zapata izquierda", choice)
    assert steel.status == "NO CUMPLE"
    assert steel.minimum_utilization > 1
    assert steel.transverse_utilization > 1


@pytest.mark.parametrize("answer,path,expected", [("n", "unused.docx", False), ("s", None, False), ("s", "chosen.docx", True)])
def test_word_is_optional_and_uses_selected_destination(monkeypatch, tmp_path, analysis, answer, path, expected):
    import bridge_design.reporting.connected_word_dialog as dialog
    destination = tmp_path / path if path else None
    written = []
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    monkeypatch.setattr(dialog, "select_connected_docx_save_path", lambda: destination)
    monkeypatch.setattr(dialog, "write_connected_docx", lambda result, output, charts: written.append(output) or output)
    result = dialog.generate_connected_docx_with_dialog(analysis, {})
    assert bool(written) == expected
    assert result == (destination if expected else None)


def test_command_selects_before_exports_and_then_offers_word(monkeypatch, tmp_path, analysis, groups, capsys):
    import bridge_design.connected_main as command
    import bridge_design.reporting.connected_word_dialog as dialog
    events = []
    choices = {group.region: choice_from_steel(group.adopted) for group in groups}
    monkeypatch.setattr(command, "collect_connected_inputs", lambda: analysis.inputs)
    monkeypatch.setattr(command, "solve_connected_abutments", lambda *args, **kwargs: analysis)
    monkeypatch.setattr(command, "connected_reinforcement_options", lambda result: groups)
    monkeypatch.setattr(command, "collect_connected_selection", lambda *args: events.append("steel") or choices)

    def offer_word(result, charts):
        assert result.selected_reinforcement == choices
        assert (tmp_path / "resultados.json").exists()
        assert charts["geometria"].exists()
        events.append("word")

    monkeypatch.setattr(dialog, "generate_connected_docx_with_dialog", offer_word)
    command.main(["--resultados", str(tmp_path)])
    assert events == ["steel", "word"]
    assert not (tmp_path / "memoria_estribos_conectados.docx").exists()
    output = capsys.readouterr().out
    assert output.index("SELECCION DE ACERO") < output.index("ACEROS ADOPTADOS")
