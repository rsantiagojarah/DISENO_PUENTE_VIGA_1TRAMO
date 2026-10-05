import json
from dataclasses import replace

import pytest
from bridge_design.domain.anchorage_status import anchorage_status

from bridge_design.cli.connected_selection import collect_connected_selection, format_connected_options, format_connected_selection
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
    assert all(group.transverse is None for group in groups)
    assert all(s.available_anchor_cm is not None for s in adopted.reinforcement if s.role == "primary")
    assert all(s.anchor_source == "Detalle continuo definido para estribos conectados"
               for s in adopted.reinforcement if s.role == "primary")
    assert all(s.anchor_status == anchorage_status(s.available_anchor_cm,
                   s.required_straight_anchor_cm, s.required_hook_anchor_cm)
               for s in adopted.reinforcement if s.role == "primary")
    output = format_connected_options(groups)
    assert "Item" in output and "vertical relleno" in output and "transversal" in output
    assert "NO CUMPLE" not in output
    assert "TRANSICION" not in output
    assert "Cajuela" not in output
    assert not any(s.region.startswith(("Transicion", "Cajuela")) for s in analysis.reinforcement)
    assert any(e.region.startswith("Transicion") for e in analysis.mesh.frame.elements)
    assert any(e.region.startswith("Cajuela") for e in analysis.mesh.frame.elements)
    assert "Fisura" not in output and "Flexion" not in output and "Corte" not in output
    assert "As req" in output and "As prov" in output and "Exceso" in output and "RECOM." in output


@pytest.mark.parametrize("region", ["Cajuela izquierda", "Cajuela derecha", "Transicion izquierda"])
def test_excluded_regions_cannot_be_selected_for_design(analysis, region):
    choice = ConnectedSteelChoice(ConnectedBarChoice('3/4"', .15), ConnectedBarChoice('3/4"', .15))
    with pytest.raises(ValueError, match="Region no reconocida"):
        check_region_choice(analysis, region, choice)
    with pytest.raises(ValueError, match="Regiones de acero no reconocidas"):
        apply_connected_selections(analysis, {region: choice})


def test_recommendations_only_check_area_before_user_selection(analysis, monkeypatch):
    import bridge_design.domain.connected_options as options
    def premature_design(*args, **kwargs):
        pytest.fail("Final service and strength verification must not run for recommendation rows")
    monkeypatch.setattr(options, "design_region", premature_design)
    groups = options.connected_reinforcement_options(analysis)
    assert groups
    assert all(option.is_compliant == (option.area_per_face_cm2_m+1e-8 >= option.required_as_cm2_m)
               for group in groups for option in group.principal)


def test_custom_console_selection_rechecks_and_exports_adopted_steel(analysis, groups, monkeypatch, tmp_path):
    group = next(group for group in groups if group.region == "Parapeto - vertical relleno")
    answers = iter(("s", "p", '3/4"', "0,15", "4"))
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    selected = collect_connected_selection(analysis, (group,))
    adopted = apply_connected_selections(analysis, selected)
    steel = next(steel for steel in adopted.reinforcement if steel.region == group.region)
    assert steel.bar_label == '3/4"'
    assert steel.spacing_m == 0.15
    assert steel.area_per_face_cm2_m == pytest.approx(2.84 / 0.15)
    assert steel.required_straight_anchor_cm > group.adopted.required_straight_anchor_cm
    assert steel.flexural_utilization < group.adopted.flexural_utilization
    assert steel.status == "OK"
    assert selected[group.region].principal.is_custom
    output = format_connected_selection(adopted)
    assert "USUARIO" in output and "TABLA" in output
    assert "Flexion" not in output and "Fisura" not in output
    export_connected_results(adopted, tmp_path)
    data = json.loads((tmp_path / "resultados.json").read_text(encoding="utf-8"))
    assert "sin verificacion de interaccion axial-momento" in data["design_scope"]
    assert all("flexural_utilization" in row and "axial_moment_utilization" not in row
               for row in data["reinforcement"])
    trace = data["calculation_audit"]["steel"][group.region]
    assert trace["flexure"]["area"] == pytest.approx(steel.area_per_face_cm2_m)
    assert trace["flexure"]["diameter"] == pytest.approx(1.91)
    assert (tmp_path / "cargas_combinadas.csv").exists()
    assert (tmp_path / "auditoria.txt").exists()
    assert "Propiedades FRAME por elemento" in (tmp_path / "auditoria.txt").read_text(encoding="utf-8")
    assert "Propiedades FRAME por elemento" not in (tmp_path / "resumen.txt").read_text(encoding="utf-8")
    assert data["selected_reinforcement"][group.region]["principal"]["spacing_m"] == 0.15
    assert next(row for row in data["reinforcement"] if row["region"] == group.region)["bar_label"] == '3/4"'


def test_custom_transverse_origin_survives_matching_the_default(analysis, groups, monkeypatch):
    group = next(group for group in groups if group.region == "Parapeto - horizontal relleno")
    answers = iter(("s", "p", group.adopted.bar_label, str(group.adopted.spacing_m)))
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    selected = collect_connected_selection(analysis, (group,))
    assert selected[group.region].principal.is_custom
    final = apply_connected_selections(analysis, selected)
    assert final.reinforcement == analysis.reinforcement
    assert "USUARIO" in format_connected_selection(final)


@pytest.mark.parametrize("label,spacing", [('1/2"', float("nan")), ('1/2"', 0), ('1/2"', 0.50), ('9"', 0.15)])
def test_invalid_custom_reinforcement_is_rejected(analysis, label, spacing):
    choice = ConnectedSteelChoice(ConnectedBarChoice(label, spacing), ConnectedBarChoice('1/2"', 0.15))
    with pytest.raises(ValueError):
        check_region_choice(analysis, "Parapeto - vertical relleno", choice)


def test_inadequate_selected_steel_stays_noncompliant(analysis):
    choice = ConnectedSteelChoice(ConnectedBarChoice('1/2"', 0.30), ConnectedBarChoice('1/2"', 0.30))
    steel = check_region_choice(analysis, "Zapata - talon superior", choice)
    assert steel.status == "NO CUMPLE"
    assert steel.minimum_utilization > 1
    assert steel.transverse_utilization > 1


def test_explicit_verified_anchor_length_overrides_geometric_estimate(analysis):
    steel = next(s for s in analysis.reinforcement if s.region == "Pantalla - vertical relleno")
    inputs = replace(analysis.inputs, anchor_lengths_m={steel.region: .025})
    selected = check_region_choice(replace(analysis, inputs=inputs), steel.region, choice_from_steel(steel))
    assert selected.available_anchor_cm == 2.5
    assert selected.anchor_source == "Longitud ingresada"
    assert selected.anchor_status == "NO CUMPLE"


def test_legacy_anchor_override_still_checks_the_other_abutment(analysis):
    steel = next(s for s in analysis.reinforcement if s.region == "Pantalla - vertical relleno")
    inputs = replace(analysis.inputs, anchor_lengths_m={"Pantalla izquierda": 5.0})
    selected = check_region_choice(replace(analysis, inputs=inputs), steel.region, choice_from_steel(steel))
    assert selected.available_anchor_cm == steel.available_anchor_cm
    assert selected.anchor_source == "Longitudes por lado y geometria"
    inputs = replace(analysis.inputs, anchor_lengths_m={"Pantalla izquierda": .025})
    selected = check_region_choice(replace(analysis, inputs=inputs), steel.region, choice_from_steel(steel))
    assert selected.available_anchor_cm == 2.5
    assert selected.anchor_status == "NO CUMPLE"


@pytest.mark.parametrize("mode,expected", (("both", "RECTO Y CON GANCHO"), ("hook", "SOLO GANCHO")))
def test_connected_accepts_either_anchorage_alternative(analysis, mode, expected):
    steel = next(s for s in analysis.reinforcement if s.region == "Pantalla - vertical relleno")
    length = (max(steel.required_straight_anchor_cm, steel.required_hook_anchor_cm)+1
              if mode == "both" else steel.required_hook_anchor_cm)
    inputs = replace(analysis.inputs, anchor_lengths_m={steel.region: length/100})
    selected = check_region_choice(replace(analysis, inputs=inputs), steel.region, choice_from_steel(steel))
    assert selected.anchor_status == expected


@pytest.mark.parametrize("path,expected", [(None, False), ("chosen.docx", True)])
def test_word_is_optional_and_uses_selected_destination(monkeypatch, tmp_path, analysis, path, expected):
    import bridge_design.reporting.connected_word_dialog as dialog
    destination = tmp_path / path if path else None
    written = []
    monkeypatch.setattr("builtins.input", lambda prompt: pytest.fail("Word destination must use the native dialog"))
    monkeypatch.setattr(dialog, "select_connected_docx_save_path", lambda: destination)
    monkeypatch.setattr(dialog, "write_connected_docx", lambda result, output, charts: written.append(output) or output)
    result = dialog.generate_connected_docx_with_dialog(analysis, {})
    assert bool(written) == expected
    assert result == (destination if expected else None)


def test_command_selects_before_exports_and_generates_word_automatically(monkeypatch, tmp_path, analysis, groups, capsys):
    import bridge_design.connected_main as command
    import bridge_design.reporting.connected_docx as report
    import bridge_design.reporting.connected_word_dialog as dialog
    events = []
    choices = {group.region: choice_from_steel(group.adopted) for group in groups}
    choices["Parapeto - vertical relleno"] = ConnectedSteelChoice(ConnectedBarChoice('3/4"', .15),
                                                          choices["Parapeto - vertical relleno"].transverse)
    monkeypatch.setattr(command, "collect_connected_inputs", lambda: events.append("inputs") or analysis.inputs)
    monkeypatch.setattr(command, "solve_connected_abutments", lambda *args, **kwargs: analysis)
    monkeypatch.setattr(command, "connected_reinforcement_options", lambda result: events.append("options") or groups)
    monkeypatch.setattr(command, "collect_connected_selection", lambda *args: events.append("steel") or choices)
    original_summary = command.format_connected_result
    original_export = command.export_connected_results

    def summary(result):
        assert result.selected_reinforcement == choices
        assert next(s for s in result.reinforcement if s.region == "Parapeto - vertical relleno").spacing_m == .15
        events.append("summary")
        return original_summary(result)

    def export(result, path):
        events.append("export")
        return original_export(result, path)

    monkeypatch.setattr(command, "format_connected_result", summary)
    monkeypatch.setattr(command, "export_connected_results", export)

    def write_word(result, path, charts):
        assert result.selected_reinforcement == choices
        assert (tmp_path / "resultados.json").exists()
        assert charts["geometria"].exists()
        assert charts["modelo_momento"].exists()
        assert path == tmp_path / "seleccion_usuario.docx"
        path.write_bytes(b"report")
        events.append("word")
        return path

    monkeypatch.setattr(dialog, "select_connected_docx_save_path", lambda: events.append("destination") or tmp_path / "seleccion_usuario.docx")
    monkeypatch.setattr(dialog, "write_connected_docx", write_word)
    command.main(["--resultados", str(tmp_path)])
    assert events == ["inputs", "options", "steel", "summary", "export", "destination", "word"]
    assert (tmp_path / "seleccion_usuario.docx").exists()
    assert not (tmp_path / "memoria_estribos_conectados.docx").exists()
    output = capsys.readouterr().out
    assert output.index("SELECCION DE ACERO") < output.index("ACEROS ADOPTADOS")
    assert output.index("ACEROS SELECCIONADOS") < output.index("RESUMEN DE RESULTADOS")
    assert output.index("RESUMEN DE RESULTADOS") < output.index("GENERACION DE LA MEMORIA")
    assert "qlim Tn/m2" in output and "Minimo" in output
    assert "Desliz." not in output and "C001" not in output
