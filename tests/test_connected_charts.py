from dataclasses import replace

from PIL import Image
import pytest

from bridge_design.domain.connected_design import analyze_connected_abutments
from bridge_design.domain.connected_geometry import build_connected_mesh
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil
from bridge_design.domain.frame_types import ElementLoad
from bridge_design.reporting.connected_chart_geometry import structure_polygons
from bridge_design.reporting.connected_charts import save_connected_charts
from bridge_design.reporting.connected_case_groups import case_label, combination_groups
from bridge_design.reporting.connected_frame_charts import (
    diagram_position, fitted_coordinates, frame_envelope, frame_envelope_chart,
)


@pytest.fixture(scope="module")
def analysis():
    return analyze_connected_abutments(ConnectedInputs(FoundationSoil(3000, 0.50, 26.7),
                                      mesh_size_m=1.0, include_without_bridge=False))


@pytest.mark.parametrize("field", ("axial", "shear", "moment"))
def test_whole_frame_envelope_preserves_elements_extrema_and_cases(analysis, field):
    diagrams = frame_envelope(analysis, field)
    assert len(diagrams) == len(analysis.mesh.frame.elements)
    included = [(case_label(result.name), result) for result in analysis.results
                if result.limit_state != "service"]
    assert any(row.station not in (0, .25, .5, .75, 1) for _, case in included for row in case.sections)
    for element, points in enumerate(diagrams):
        assert all(row.element == element and row.minimum <= row.maximum for row in points)
        for label, case in included:
            for section in case.sections:
                if section.element != element:
                    continue
                row = next(row for row in points if row.station == section.station)
                assert row.minimum - 1e-8 <= getattr(section, field) <= row.maximum + 1e-8
                if row.minimum_case == label:
                    assert row.minimum == pytest.approx(getattr(section, field))
                if row.maximum_case == label:
                    assert row.maximum == pytest.approx(getattr(section, field))
    assert min(row.minimum for points in diagrams for row in points) == pytest.approx(
        min(getattr(row, field) for _, case in included for row in case.sections))
    assert max(row.maximum for points in diagrams for row in points) == pytest.approx(
        max(getattr(row, field) for _, case in included for row in case.sections))


def test_diagram_ordinates_reverse_each_local_normal_without_rotating_geometry(analysis):
    model = analysis.mesh.frame
    for element_index in (0, analysis.mesh.side_elements[0][0], analysis.mesh.side_elements[1][0]):
        axis = diagram_position(model, element_index, 0.5)
        positive = diagram_position(model, element_index, 0.5, 12, 0.1)
        negative = diagram_position(model, element_index, 0.5, -12, 0.1)
        if element_index == 0:
            assert positive == pytest.approx((axis[0], axis[1] - 1.2))
            assert negative == pytest.approx((axis[0], axis[1] + 1.2))
        else:
            assert positive == pytest.approx((axis[0] + 1.2, axis[1]))
            assert negative == pytest.approx((axis[0] - 1.2, axis[1]))
    point = fitted_coordinates([(0, -2), (18, 10)], (0, 0, 2000, 900))
    assert point(1, 0)[0] - point(0, 0)[0] == pytest.approx(point(0, 0)[1] - point(0, 1)[1])


def test_service_does_not_enter_strength_envelopes(analysis):
    inflated = tuple(replace(case, end_forces=tuple(tuple(1e9 for value in forces) for forces in case.end_forces))
                     if case.limit_state == "service" else case for case in analysis.results)
    assert frame_envelope(replace(analysis, results=inflated), "moment") == frame_envelope(analysis, "moment")


def test_general_envelope_includes_service_cases(analysis):
    inflated = tuple(replace(case, end_forces=tuple(tuple(1e9 for value in forces) for forces in case.end_forces))
                     if case.limit_state == "service" else case for case in analysis.results)
    names = tuple(case.name for case in analysis.results)
    general = frame_envelope(replace(analysis, results=inflated), "moment", names)
    assert general != frame_envelope(analysis, "moment", names)
    assert any("Servicio I" in row.minimum_case or "Servicio I" in row.maximum_case
               for points in general for row in points)


def test_export_replaces_split_figures_with_three_complete_model_views(analysis, tmp_path):
    paths = save_connected_charts(analysis, tmp_path)
    assert set(paths) == {"geometria", "contacto", "modelo_axial", "modelo_cortante", "modelo_momento",
                          "cargas", "cargas_pesos", "cargas_sobrecarga_1", "cargas_tablero_1",
                          "cargas_sismo_A_menos", "cargas_sismo_A_mas", "cargas_sismo_B_menos",
                          "cargas_sismo_B_mas", "cargas_inercia", "deformada", "armado"} | {
                              f"envolvente_{i}_{field}" for i in range(1,len(combination_groups(analysis))+1)
                              for field in ("axial","shear","moment")} | {
                                  f"contacto_envolvente_{i}" for i in range(1,5)}
    for name in ("modelo_axial", "modelo_cortante", "modelo_momento"):
        with Image.open(paths[name]) as picture:
            assert picture.size == (2000, 1450)
            assert len(picture.getcolors(picture.width * picture.height)) > 10
    assert not (tmp_path / "izquierda_nvm.png").exists()
    assert not (tmp_path / "cimentacion_nvm.png").exists()


def test_zero_force_diagram_has_finite_scale(analysis, tmp_path):
    cases = tuple(replace(case, distributed=tuple(ElementLoad() for load in case.distributed)) for case in analysis.cases)
    results = tuple(replace(case, end_forces=tuple((0,) * 6 for forces in case.end_forces),
                            sections=tuple(replace(row, axial=0, shear=0, moment=0) for row in case.sections))
                    for case in analysis.results)
    zero = replace(analysis, cases=cases, results=results)
    assert all(row.minimum == row.maximum == 0 for points in frame_envelope(zero, "moment") for row in points)
    frame_envelope_chart(zero, "moment", tmp_path / "cero.png")
    assert (tmp_path / "cero.png").exists()


def test_full_geometry_preserves_mirrored_seats_and_abrupt_thickness_change(analysis, tmp_path):
    data = replace(analysis.inputs, left_transition_m=0, section_offsets=True)
    mesh = build_connected_mesh(data)
    polygons = structure_polygons(data, mesh)
    assert len(polygons) == 3
    assert max(height for position, height in polygons[1]) == pytest.approx(9.2)
    assert max(height for position, height in polygons[2]) == pytest.approx(9.2)
    edge = [(position, height) for position, height in polygons[0] if position == data.left.geometry.footing_width_m]
    assert {round(height, 4) for position, height in edge} == {-1.5, -0.75}
    asymmetric = analyze_connected_abutments(data)
    frame_envelope_chart(asymmetric, "moment", tmp_path / "asimetrico.png")
    assert (tmp_path / "asimetrico.png").exists()


@pytest.fixture(scope="module", params=[1, 2])
def offset_analysis(request):
    if request.param == 1:
        data = ConnectedInputs(FoundationSoil(3000, .50, 26.7), mesh_size_m=1.0,
                               include_without_bridge=False, section_offsets=True)
    else:
        from bridge_design.cli.connected_2_yaml import connected_2_inputs_from_yaml, connected_2_yaml_template
        data = connected_2_inputs_from_yaml(connected_2_yaml_template(example=True))
        data = replace(data, foundation_node_count=21, include_without_bridge=False, section_offsets=True)
    return analyze_connected_abutments(data)


def test_offset_diagrams_use_design_moments_and_simultaneous_axials(offset_analysis):
    from bridge_design.domain.connected_reinforcement import section_demands
    result = offset_analysis
    changed = False
    for case in result.results:
        demands = {(d.element, d.station): d for rows in
                   section_demands(result.inputs, result.mesh, (case,)).values() for d in rows}
        points = {(p.element, p.station): p for rows in frame_envelope(result, "moment", (case.name,)) for p in rows}
        for raw in case.sections:
            demand = demands[raw.element, raw.station]
            point = points[raw.element, raw.station]
            assert point.minimum == pytest.approx(demand.moment, abs=1e-9)
            assert point.maximum == pytest.approx(demand.moment, abs=1e-9)
            assert point.minimum_case == point.maximum_case == case_label(case.name)
            changed |= abs(raw.moment-demand.moment) > .1
    assert changed  # Covers variable-depth stems or foundation transitions, not only zero corrections.


@pytest.mark.parametrize("field", ["axial", "shear"])
def test_offset_diagrams_do_not_transform_n_or_v(offset_analysis, field):
    names = tuple(c.name for c in offset_analysis.results)
    diagrams = frame_envelope(offset_analysis, field, names)
    points = {(p.element, p.station): p for rows in diagrams for p in rows}
    for case in offset_analysis.results:
        for raw in case.sections:
            point = points[raw.element, raw.station]
            assert point.minimum-1e-8 <= getattr(raw, field) <= point.maximum+1e-8
    assert min(p.minimum for p in points.values()) == pytest.approx(
        min(getattr(raw, field) for case in offset_analysis.results for raw in case.sections))
    assert max(p.maximum for p in points.values()) == pytest.approx(
        max(getattr(raw, field) for case in offset_analysis.results for raw in case.sections))


def test_offset_transition_regression_matches_83471_design_moment(analysis):
    result = analyze_connected_abutments(replace(analysis.inputs, section_offsets=True))
    name = "Par simultaneo ingresado / Evento Extremo I A EQ-1"
    case = next(c for c in result.results if c.name == name)
    raw = next(s for s in case.sections if s.element == 17 and s.station == 1.0)
    assert raw.moment == pytest.approx(71.80128518375716)
    point = next(p for p in frame_envelope(result, "moment", (name,))[17] if p.station == 1.0)
    assert point.maximum == pytest.approx(83.47145421999423)
    all_names = tuple(c.name for c in result.results)
    general = next(p for p in frame_envelope(result, "moment", all_names)[17] if p.station == 1.0)
    assert general.maximum == pytest.approx(point.maximum)


@pytest.mark.parametrize("offsets", [False, True])
def test_word_describes_centroid_transfer_only_when_active(analysis, offsets):
    from docx import Document
    from bridge_design.reporting.connected_report_details import write_model_description
    from bridge_design.reporting.deck_docx import _configure_document
    data = replace(analysis.inputs, section_offsets=offsets)
    result = replace(analysis, inputs=data, mesh=build_connected_mesh(data))
    document = Document()
    _configure_document(document)
    write_model_description(document, result)
    text = " ".join(p.text for p in document.paragraphs)
    equations = "".join(document.element.xpath(".//m:t/text()")).replace(" ", "")
    assert ("momento trasladado al centroide local" in text) == offsets
    assert ("M_seccion=M_elemento+(e_seccion-e_elemento)*N" in equations) == offsets
