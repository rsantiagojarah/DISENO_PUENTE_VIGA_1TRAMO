"""Regresión contra APOYOS.pdf y límites de verificación del nuevo comando."""

from dataclasses import replace
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from bridge_design.cli.bearing_a_yaml import bearing_a_from_yaml, bearing_a_reference_example, bearing_a_template
from bridge_design.domain.bearing_method_a import BearingAActions, BearingAGeometry, CompressionCurve, design_bearing_a


def example_inputs():
    return bearing_a_from_yaml(bearing_a_reference_example())


def test_pdf_problem_4_1_independent_expected_results():
    r = design_bearing_a(example_inputs())
    # Fuente: pp. impresas 234-239. Se conservan cifras sin redondeo intermedio.
    assert r.value("P") == 92
    assert r.value("AREA") == 1350
    assert r.value("AREA_REQ") == pytest.approx(1046.64,abs=.01)
    assert r.value("SIGMA") == pytest.approx(68.148148148)
    assert r.value("DELTA") == pytest.approx(3.6408)
    assert r.value("SHEAR") == pytest.approx(7.2816)
    assert r.value("SI") == 6
    assert r.value("SE") == 11.25
    assert r.value("NEFF") == 5
    assert r.step("SCOPE").value == 7.2
    assert r.step("SCOPE").limit == 20
    assert r.value("HRT") == 7.6
    assert r.value("HS_SERVICE") == pytest.approx(.121212121212)
    assert r.value("HS_FATIGUE") == pytest.approx(.028979780017)
    assert r.value("HEIGHT") == 8.6
    assert r.value("EPS_IT") == pytest.approx(.0445)
    assert r.value("DEF_T") == pytest.approx(.323)
    assert r.value("DEF_D") == pytest.approx(.2624)
    assert r.value("DEF_LL") == pytest.approx(.0606)
    assert r.value("CREEP") == pytest.approx(.09184)
    assert r.value("JOINT") == pytest.approx(.15244)
    assert r.value("HU") == pytest.approx(9.092898)
    assert r.value("FRICTION") == 13
    assert r.status == "REFERENCIAL"
    assert not r.overall_ok


def test_small_adopted_plan_and_invalid_layers_remain_visible():
    i = example_inputs()
    g = replace(i.geometry,length_cm=5,exterior_cm=2,interior_layers=1,steel_cm=.1)
    r = design_bearing_a(replace(i,geometry=g))
    assert r.adopted == g
    assert r.status == "NO CONFORME"
    for id in ("AREA_REQ","SIGMA","EXTERIOR","HS_MIN","SHEAR"):
        assert r.step(id).status == "NO CUMPLE"


def test_missing_curves_and_seismic_resistance_cannot_pass():
    r = design_bearing_a(bearing_a_from_yaml(bearing_a_template()))
    assert r.status == "PENDIENTE"
    assert r.step("STRAIN_CHECK").status == "PENDIENTE"
    assert r.step("CONNECTION_T").status == "PENDIENTE"
    assert r.value("EQ_T") == 14.0
    assert r.value("CONNECTION_T") == 14.0  # no crédito de fricción ni H térmica


def test_documented_product_data_and_full_connection_capacity_can_pass():
    i = example_inputs()
    curve = replace(i.compression_curve,kind="fabricante",source="Certificado de ensayo PRUEBA: datos artificiales de la prueba unitaria")
    c = replace(i.connections,as_site=.2,restrained_transverse=True,resistance_transverse_tn=15,resistance_source="Memoria de conexión PRUEBA, capacidad de diseño 15 Tn")
    r = design_bearing_a(replace(i,compression_curve=curve,connections=c))
    assert r.overall_ok
    assert r.status == "CONFORME"
    assert r.step("CONNECTION_T").ratio == pytest.approx(14/15)
    r = design_bearing_a(replace(i,compression_curve=curve,connections=replace(c,resistance_transverse_tn=13)))
    assert r.status == "NO CONFORME"


def test_multispan_requires_analysis_and_resistance_is_not_inferred():
    i = example_inputs()
    c = replace(i.connections,single_span=False,as_site=.3,restrained_transverse=True)
    r = design_bearing_a(replace(i,connections=c))
    assert r.step("EQ_T").value is None
    assert r.step("EQ_T").status == "PENDIENTE"
    c = replace(c,eq_transverse_tn=40,resistance_transverse_tn=45,resistance_source="PRUEBA")
    r = design_bearing_a(replace(i,connections=c))
    assert r.value("CONNECTION_T") == 40
    assert r.step("CONNECTION_T").status == "CUMPLE"
    assert r.step("EQ_T").formula == "F_EQ = F_EQ_analisis"
    assert r.step("EQ_T").substitution == "F_EQ = 40 Tn"


def test_compression_bilinear_interpolation_and_no_extrapolation():
    curve = CompressionCurve("PRUEBA",60,((3,0,0),(3,50,.1),(6,0,0),(6,50,.05)))
    epsilon, trace = curve.lookup(4.5,25)
    assert epsilon == pytest.approx(.0375)
    assert "t_S=0.5" in trace
    for s,stress in ((2,25),(7,25),(4,51)):
        with pytest.raises(ValueError,match="extrapola"):
            curve.lookup(s,stress)


def test_outside_curve_coverage_is_pending_not_silently_extrapolated():
    i = example_inputs()
    r = design_bearing_a(replace(i,geometry=replace(i.geometry,width_cm=46)))
    assert r.step("EPS_ET").value is None
    assert r.step("JOINT").status == "PENDIENTE"
    assert not r.overall_ok
    json.dumps(r.to_dict(),allow_nan=False)


@pytest.mark.parametrize("bad",[0,-1,float("nan"),float("inf")])
def test_invalid_geometry_rejected(bad):
    with pytest.raises(ValueError):
        BearingAGeometry(width_cm=bad)


def test_invalid_shore_fractional_layers_and_unknown_yaml_rejected():
    for key,value in (("shore_a",70),("shore_a",60.5)):
        data = bearing_a_template()
        data["materiales"][key] = value
        with pytest.raises(ValueError):
            bearing_a_from_yaml(data)
    data = bearing_a_template()
    data["geometria"]["numero_capas_interiores"] = 4.5
    with pytest.raises(ValueError):
        bearing_a_from_yaml(data)
    data = bearing_a_template()
    data["acciones"]["dc_t"] = 20
    with pytest.raises(ValueError,match="desconocidos"):
        bearing_a_from_yaml(data)
    with pytest.raises(ValueError,match="obligatorios"):
        bearing_a_from_yaml({})


def test_curve_invalid_percent_and_non_monotonic_data_are_rejected():
    for points in (((6,0,0),(6,50,4.45)),((6,0,0),(6,50,.05),(6,60,.04)),((6,20,.02),(6,50,.05))):
        with pytest.raises(ValueError):
            CompressionCurve("PRUEBA",60,points)


def test_strain_failure_is_not_overridden_by_reference_status():
    i = example_inputs()
    points = tuple((s,stress,eps*3) for s,stress,eps in i.compression_curve.points)
    r = design_bearing_a(replace(i,compression_curve=replace(i.compression_curve,points=points)))
    assert r.step("STRAIN_CHECK").status == "NO CUMPLE"
    assert r.status == "NO CONFORME"


def test_strict_method_a_boundary_and_square_limit():
    i = example_inputs()
    # S=6, n_eff=2 => 18. Para cuadrado se requiere <16, para rectangular <22.
    r = design_bearing_a(replace(i,geometry=replace(i.geometry,interior_layers=1)))
    assert r.step("SCOPE").status == "CUMPLE"
    r = design_bearing_a(replace(i,geometry=replace(i.geometry,interior_layers=1,nearly_square=True)))
    assert r.step("SCOPE").status == "NO CUMPLE"
    # Planta 36 x 36, hri=1.5 => S=6; exterior <hri/2; n=2: S²/n=18.
    r = design_bearing_a(replace(i,geometry=replace(i.geometry,width_cm=36,length_cm=36,interior_layers=2,exterior_cm=.5)))
    assert r.step("SCOPE").limit == 16
    # S=sqrt(22), n_eff=1: frontera estricta, 22 no permitido.
    h = 9/(22**.5)  # LW/[2(L+W)] = 9 en planta 30x45
    r = design_bearing_a(replace(i,geometry=replace(i.geometry,interior_cm=h,exterior_cm=.1,interior_layers=1)))
    assert r.step("SCOPE").value == pytest.approx(22)
    assert r.step("SCOPE").status == "NO CUMPLE"


def test_automatic_selection_respects_locked_values_and_bounded_failure():
    i = bearing_a_from_yaml(bearing_a_template())
    auto = replace(i.geometry,length_cm=None,interior_cm=None,exterior_cm=None,interior_layers=None,steel_cm=None)
    r = design_bearing_a(replace(i,geometry=auto))
    assert r.candidates > 1
    assert r.value("AREA") >= r.value("AREA_REQ")
    assert r.value("HEIGHT") <= min(r.adopted.length_cm,r.adopted.width_cm)/3
    assert r.step("SCOPE").status == "CUMPLE"
    assert r.status == "PENDIENTE"
    locked = replace(auto,length_cm=5,max_layers=2)
    with pytest.raises(ValueError,match="No existe candidato"):
        design_bearing_a(replace(i,geometry=locked))


def test_expansion_temperature_controls_envelope_not_only_contraction():
    from bridge_design.domain.elastomeric_bearing import TemperatureRange
    i = example_inputs()
    m = replace(i.movements,temperature=TemperatureRange(50,10,11),shrinkage_cm=0,prestress_shortening_cm=0)
    r = design_bearing_a(replace(i,movements=m))
    assert r.value("DELTA") == pytest.approx(1.2*10.8e-6*3000*39)


def test_complete_thermal_range_has_reproducible_formula_and_substitution():
    i = example_inputs()
    r = design_bearing_a(replace(i,movements=replace(i.movements,use_install_to_min=False)))
    # Rango 35 - (-10) = 45 C; retracción+postensado = 1.9 cm.
    assert r.value("DELTA") == pytest.approx(1.2*(10.8e-6*3000*45+1.9))
    assert r.step("DELTA").formula == "Delta_s = gamma_TU (100 alpha L (T_max - T_min) + d_perm)"
    assert "35 - (-10)" in r.step("DELTA").substitution
    assert "+ 1.9" in r.step("DELTA").substitution


def test_im_included_for_stress_and_concrete_but_excluded_from_strain():
    i = example_inputs()
    r = design_bearing_a(replace(i,actions=replace(i.actions,im_tn=2)))
    assert r.value("P") == 94
    assert r.value("PU") == 130.75
    assert r.value("EPS_IT") == pytest.approx(.0445)


def test_no_friction_credit_to_seismic_and_full_service_retention():
    i = example_inputs()
    c = replace(i.connections,friction_mu=.01,restrained_longitudinal=True,as_site=.2)
    r = design_bearing_a(replace(i,connections=c))
    assert r.step("SLIP").status == "PENDIENTE"
    assert r.value("CONNECTION_L") == 14
    c = replace(c,resistance_longitudinal_tn=10,resistance_source="PRUEBA")
    r = design_bearing_a(replace(i,connections=c))
    assert r.step("SLIP").status == "CUMPLE"
    assert r.step("CONNECTION_L").status == "NO CUMPLE"


def test_a2_smaller_than_loaded_area_and_phi_invalid():
    i = example_inputs()
    r = design_bearing_a(replace(i,concrete_a2_cm2=1000))
    assert r.step("A2").status == "NO CUMPLE"
    with pytest.raises(ValueError):
        replace(i,concrete_phi=1.1)


def test_hash_changes_and_json_keeps_all_source_and_results():
    i = example_inputs()
    r = design_bearing_a(i)
    assert r.input_sha256 == design_bearing_a(i).input_sha256
    assert r.input_sha256 != design_bearing_a(replace(i,actions=replace(i.actions,dc_tn=64))).input_sha256
    payload = json.loads(json.dumps(r.to_dict(),allow_nan=False))
    assert payload["adopted"]["steel_cm"] == .2
    assert payload["inputs"]["compression_curve"]["source"].startswith("APOYOS.pdf")
    assert payload["status"] == "REFERENCIAL"
    assert len(payload["steps"]) == len(r.steps)


def test_cli_template_calculation_and_report_exports(tmp_path,capsys):
    from bridge_design.cli.bearing_a_cli import main
    yaml = tmp_path/"modelo.yaml"
    assert main(["ejemplo",str(yaml)]) == 0
    audit = tmp_path/"calculo.json"
    word = tmp_path/"memoria.docx"
    assert main(["input",str(yaml),"--word",str(word),"--json",str(audit)]) == 0
    assert "Estado global: REFERENCIAL" in capsys.readouterr().out
    data = json.loads(audit.read_text(encoding="utf-8"))
    with ZipFile(word) as package:
        assert package.testzip() is None
        xml = package.read("word/document.xml").decode("utf-8")
        styles = package.read("word/styles.xml").decode("utf-8")
    assert data["input_sha256"][:32] in xml
    assert "m:oMath" in xml and "m:f" in xml
    assert "Arial Narrow" in styles
    assert 'w:top="1440"' in xml
    assert "REF" in xml and "PENDIENTE" in xml
    assert "Reemplazando los valores correspondientes" in xml
    assert "Tabla de compresión utilizada" in xml
    from lxml import etree
    namespaces = {"m":"http://schemas.openxmlformats.org/officeDocument/2006/math","w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    root = etree.fromstring(xml.encode("utf-8"))
    # La comparación estricta debe estar fuera del denominador de la fracción.
    strict = root.xpath("//m:oMath[m:r/m:t[contains(text(), '<')]]",namespaces=namespaces)
    assert strict
    assert all("<" not in "".join(node.itertext()) for math in strict for node in math.xpath(".//m:den",namespaces=namespaces))
    style_root = etree.fromstring(styles.encode("utf-8"))
    assert not style_root.xpath("//w:style[@w:styleId='Title']//w:pBdr",namespaces=namespaces)


def test_cli_error_exit_and_no_report_dialog(tmp_path,monkeypatch):
    from bridge_design.cli.bearing_a_cli import main
    from bridge_design.reporting import bearing_a_docx
    monkeypatch.setattr(bearing_a_docx,"select_bearing_a_docx_path",lambda:pytest.fail("No debe abrirse diálogo"))
    yaml = tmp_path/"modelo.yaml"
    assert main(["output",str(yaml)]) == 0
    assert main(["input",str(yaml),"--sin-word"]) == 0
    assert main(["input",str(tmp_path/"inexistente.yaml"),"--sin-word"]) == 2


def test_console_command_registered():
    import tomllib
    with open("pyproject.toml","rb") as stream:
        scripts = tomllib.load(stream)["project"]["scripts"]
    assert scripts["diseno-apoyos-A"] == "bridge_design.cli.bearing_a_cli:main"
