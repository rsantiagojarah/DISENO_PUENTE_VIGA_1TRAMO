"""Contrastes con páginas 224-239 del PDF aportado y límites del nuevo flujo."""
from dataclasses import replace
import pytest
from bridge_design.cli.bearing_a_yaml import bearing_a_from_yaml, bearing_a_template, bearing_a_reference_example
from bridge_design.domain.bearing_method_a import design_bearing_a
from bridge_design.domain.elastomeric_bearing import TemperatureRange
from bridge_design.domain.serquen_bearings import CURVES, KSI_TO_KGF_CM2, catalog_rows, serquen_compression_curve


@pytest.mark.parametrize("hardness", [50,60])
def test_graph_domain_units_and_monotonicity(hardness):
    c = serquen_compression_curve(hardness)
    assert c.kind == "referencia"
    assert sorted({p[0] for p in c.points}) == [3,4,5,6,9,12]
    for shape,rows in CURVES[hardness].items():
        vals=[c.lookup(shape,stress*KSI_TO_KGF_CM2)[0] for stress,eps in rows]
        assert vals == sorted(vals)
        assert vals[0] == 0
    with pytest.raises(ValueError,match="fuera de la tabla"):
        c.lookup(12.1,30)
    with pytest.raises(ValueError,match="fuera de la tabla"):
        c.lookup(2.9,30)
    with pytest.raises(ValueError,match="excede"):
        c.lookup(3,1.0*KSI_TO_KGF_CM2)


def test_digitization_matches_independent_book_example_with_reading_tolerance():
    i = bearing_a_from_yaml(bearing_a_reference_example())
    r = design_bearing_a(replace(i,compression_curve=None,neoprene_only=True))
    # p.238: lecturas independientes de la digitalización p.231.
    for key,expected in {"EPS_ID":.036,"EPS_IT":.0445,"EPS_ED":.029,"EPS_ET":.035}.items():
        assert r.value(key) == pytest.approx(expected,abs=.0015)
    assert r.value("DEF_T") == pytest.approx(.323,abs=.01)
    assert r.value("JOINT") == pytest.approx(.153,abs=.01)
    assert r.status == "REFERENCIAL"
    assert "p. 231" in r.inputs.compression_curve.source
    assert r.step("STRAIN_CHECK").status == "REFERENCIAL"


def small_catalog_inputs(mode):
    i = bearing_a_from_yaml(bearing_a_template())
    return replace(i,neoprene_only=True,
        actions=replace(i.actions,dc_tn=10,dw_tn=1,ll_tn=2),
        movements=replace(i.movements,span_length_m=15,shrinkage_cm=.1,temperature=TemperatureRange(30,20,25)),
        geometry=replace(i.geometry,width_cm=20,length_cm=15,selection_mode=mode,
            interior_cm=None,exterior_cm=None,interior_layers=None,steel_cm=None,catalog_rotation_rad=.001))


@pytest.mark.parametrize("mode,capacity,area,rotation",[("semirecubierto",257,300,17),("recubierto",298,266,19.6)])
def test_catalog_selection_matches_printed_row_and_preserves_orientation(mode,capacity,area,rotation):
    r=design_bearing_a(small_catalog_inputs(mode))
    assert r.value("AREA") == area
    assert r.value("HEIGHT") == 2
    assert r.adopted.interior_layers == 1  # n=2 en el catálogo cuenta zunchos.
    assert r.step("CAT_LOAD").limit == capacity
    assert r.step("CAT_ROTATION").limit == rotation
    assert r.value("CAT_LOAD") == pytest.approx(13*9.80665)
    assert r.step("CAT_MOVE").limit == 11.2
    assert r.status == "REFERENCIAL"
    assert "certificado" in r.step("CAT_LOAD").legend


def test_catalog_preserves_height_and_checks_rotation_failure():
    i=small_catalog_inputs("semirecubierto")
    with pytest.raises(ValueError,match="No existe una fila"):
        design_bearing_a(replace(i,geometry=replace(i.geometry,total_height_cm=2.1)))
    with pytest.raises(ValueError,match="No existe una fila"):
        design_bearing_a(replace(i,geometry=replace(i.geometry,catalog_rotation_rad=1)))
    missing=design_bearing_a(replace(i,geometry=replace(i.geometry,catalog_rotation_rad=None)))
    assert missing.step("CAT_ROTATION").status == "PENDIENTE"


def test_catalog_scope_does_not_invent_points_outside_graph():
    i=small_catalog_inputs("semirecubierto")
    g=replace(i.geometry,width_cm=40,length_cm=30,interior_cm=1.2,exterior_cm=.6,steel_cm=.3,interior_layers=4)
    r=design_bearing_a(replace(i,geometry=g))
    assert r.value("SE") > 12
    assert r.step("EPS_ET").value is None
    assert r.step("JOINT").status == "PENDIENTE"
    assert "fuera" in r.step("EPS_ET").substitution


def test_usual_thickness_pairs_are_a_mode_not_mandatory_for_custom():
    i=small_catalog_inputs("medida")
    usual=design_bearing_a(replace(i,geometry=replace(i.geometry,selection_mode="usuales")))
    assert (usual.adopted.interior_cm,usual.adopted.steel_cm) in {(.8,.2),(1,.3),(1.2,.3),(1.5,.4)}
    explicit=replace(i.geometry,selection_mode="usuales",interior_cm=1.5,steel_cm=.2,exterior_cm=.8,interior_layers=4)
    with pytest.raises(ValueError,match="pareja caucho/zuncho"):
        design_bearing_a(replace(i,geometry=explicit))


def test_fixed_height_can_use_thicker_than_minimum_steel_without_changing_dimensions():
    i=bearing_a_from_yaml(bearing_a_template())
    i=replace(i,neoprene_only=True,
        actions=replace(i.actions,dc_tn=27.47,dw_tn=.169,ll_tn=16.444,pl_tn=4.669,im_tn=5.427),
        movements=replace(i.movements,span_length_m=15,shrinkage_cm=.45),
        geometry=replace(i.geometry,width_cm=40,length_cm=30,total_height_cm=7.5,interior_cm=None,
            exterior_cm=None,interior_layers=None,steel_cm=None))
    r=design_bearing_a(i)
    assert r.adopted.length_cm == 30 and r.adopted.width_cm == 40
    assert r.value("HEIGHT") == pytest.approx(7.5)
    assert r.adopted.steel_cm == .3
    assert r.status == "REFERENCIAL"
    assert not any(s.status in {"PENDIENTE","NO CUMPLE"} for s in r.steps)


def test_catalog_transcription_spot_checks_and_ambiguous_cell_excluded():
    rows=catalog_rows()
    assert len(rows)==119
    def get(page,a,b):
        return next(r for r in rows if r.page==page and r.short_mm==a and r.long_mm==b)
    assert get(225,150,150).road_capacity_kn==169
    assert get(226,150,150).road_capacity_kn==135
    assert get(227,150,200).road_capacity_kn==161
    assert get(228,600,700).road_capacity_kn==6107
    assert get(228,200,250).road_capacity_kn==483
    assert 3 not in dict(get(226,100,100).rotations)
    assert all(r.short_mm<=r.long_mm for r in rows)


def test_default_yaml_uses_graphs_and_can_explicitly_choose_elastic():
    data=bearing_a_template()
    assert design_bearing_a(bearing_a_from_yaml(data)).inputs.compression_curve is not None
    data["compresion"]["metodo"]="elastico"
    assert design_bearing_a(bearing_a_from_yaml(data)).inputs.compression_curve is None


def test_command_exports_resolved_graph_points_to_json_and_word(tmp_path,capsys):
    import json
    from zipfile import ZipFile
    from bridge_design.cli.bearing_a_cli import run_bearing_a
    i=small_catalog_inputs("medida")
    output=tmp_path/"resultado.json"
    word=tmp_path/"memoria.docx"
    r=run_bearing_a(i,word_path=word,json_path=output)
    payload=json.loads(output.read_text(encoding="utf-8"))
    assert payload["inputs"]["compression_curve"]["kind"]=="referencia"
    assert len(payload["inputs"]["compression_curve"]["points"])>40
    assert "p. 231" in payload["inputs"]["compression_curve"]["source"]
    assert payload["status"]=="REFERENCIAL"
    with ZipFile(word) as z:
        text=z.read("word/document.xml").decode("utf-8")
    assert "digitalización referencial" in text
    assert "t_S=" in text
    assert "CUMPLE según la fuente referencial" in capsys.readouterr().out


def test_curve_failure_does_not_become_a_referential_pass():
    i=small_catalog_inputs("medida")
    r=design_bearing_a(replace(i,joint_limit_cm=.00001,geometry=replace(i.geometry,
        interior_cm=.8,exterior_cm=.4,interior_layers=2,steel_cm=.2)))
    assert r.step("JOINT").status=="NO CUMPLE"
    assert r.status=="NO CONFORME"
