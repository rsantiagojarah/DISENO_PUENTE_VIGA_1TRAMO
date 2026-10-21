"""Regresión del caso aprobado y del ingreso manual real del comando."""
from pathlib import Path
from zipfile import ZipFile
import json

from docx import Document
from lxml import etree
import pytest
import yaml

from bridge_design.cli.bearing_a_cli import main
from bridge_design.cli.bearing_a_pair_yaml import bearing_pair_from_yaml
from bridge_design.domain.bearing_a_pair import design_bearing_pair
from bridge_design.domain.bearing_method_a import BearingAActions
from bridge_design.reporting.bearing_a_pair_docx import generate_bearing_pair_docx

EXAMPLE = Path(__file__).resolve().parents[1]/'ejemplo_apoyos_A_V3_400x400x75.yaml'
NS = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}


def inputs():
    return yaml.safe_load(EXAMPLE.read_text(encoding='utf-8'))


def document_text(path):
    with ZipFile(path) as z:
        root = etree.fromstring(z.read('word/document.xml'))
    return ' '.join(root.xpath('//w:t/text()|//m:t/text()',namespaces=NS)),root


def check_v3(pair):
    assert pair.status == 'REFERENCIAL'
    for r in (pair.mobile,pair.fixed):
        assert r.adopted.steel_cm == .4
        assert r.adopted.interior_cm == 2
        assert r.adopted.exterior_cm == 1.15
        assert r.adopted.interior_layers == 2
        assert r.adopted.hole_diameter_cm == 2.54
        assert r.value('P') == pytest.approx(58.810)
        assert r.value('AREA') == pytest.approx(1594.932925209025)
        assert r.value('HS_HOLES')*10 == pytest.approx(3.3902829685)
        assert r.value('SIGMA') == pytest.approx(36.8730239814)
        assert r.value('EPS_IT') == pytest.approx(.0329112428718)
        assert r.value('JOINT') == pytest.approx(.12015808455)
        assert not any(s.status in ('NO CUMPLE','PENDIENTE') for s in r.checks)
    assert pair.mobile.value('DELTA') == pytest.approx(.85104)
    assert pair.mobile.value('HU') == pytest.approx(3.02926430736)
    assert pair.mobile.value('FRICTION') == pytest.approx(4.6222)
    assert pair.fixed.value('DELTA') == 0


def test_approved_case_and_native_report_have_actual_values_and_style(tmp_path):
    pair = design_bearing_pair(bearing_pair_from_yaml(inputs()))
    check_v3(pair)
    out = generate_bearing_pair_docx(pair,tmp_path/'subcarpeta/memoria.docx')
    text,root = document_text(out)
    for value in ('0.7092','0.85104','8.5104','3.0293','3.3903','374.6','65.5','REFERENCIAL'):
        assert value in text
    assert '42.4208' in text
    assert '1.2204' not in text and '12.204' not in text
    math = [''.join(e.xpath('.//m:t/text()',namespaces=NS)) for e in root.xpath('//m:oMath',namespaces=NS)]
    assert any('(23 − 7)' in e for e in math)
    assert any('(23 − 23)' in e for e in math)
    assert root.xpath('//m:f',namespaces=NS) and root.xpath('//m:sSub',namespaces=NS)
    assert all(s.title in text or s.id in ('CREEP','JOINT','STABILITY_L','STABILITY_W') for s in pair.mobile.checks)
    template = Path(__file__).resolve().parents[1]/'src/bridge_design/reporting/templates/bearing_a_pair.docx'
    with ZipFile(template) as a, ZipFile(out) as b:
        for part in ('word/styles.xml','word/numbering.xml','word/theme/theme1.xml','word/header1.xml','word/footer1.xml'):
            assert a.read(part) == b.read(part)
    section = Document(out).sections[0]
    assert section.page_width.mm == pytest.approx(210,abs=.02)
    assert section.left_margin.mm == pytest.approx(25.4,abs=.01)


def test_manual_command_reproduces_yaml_without_rounding_components(tmp_path,monkeypatch,capsys):
    answers = [
        ('Nombre del proyecto','Puente de 15 m V3'),('Identificador del apoyo','V3 derecho'),
        ('DC estructural','20.016'),('DW rodadura','3.095'),('PL peatonal','0'),
        ('LL+IM vehicular conjunta','35.699'),('Confirmar que LL+IM','s'),('Factor de impacto','0.33'),
        ('Reacción mínima concomitante','23.111'),('Procedencia de reacciones','Reacciones V3 sin carril'),
        ('Longitud efectiva','15'),('Zona climática','sierra'),('Temperatura de instalación','23'),
        ('Definir temperaturas extremas','s'),('Temperatura mínima','7'),('Temperatura máxima','23'),
        ('Acortamiento por retracción','0.45'),('Otros acortamientos','0'),('Factor de movimientos','1.2'),
        ('Shore A','60'),('Fy de los zunchos','2530'),('Ancho transversal','40'),('Largo longitudinal','40'),
        ('Altura TOTAL','7.5'),('Selección medida','medida'),('Definir también espesores','s'),
        ('Espesor de UNA capa interior','2'),('Espesor de UNA capa exterior','1.15'),('Número de capas interiores','2'),
        ('Espesor de UN zuncho','0.4'),('Móvil: cantidad','1'),('Móvil: diámetro','2.54'),
        ('Clasificar como casi cuadrado','s'),('Rotación principal','s'),('Coeficiente de fricción','0.2'),('Curvas:',''),
        ('Adoptar las mismas reacciones','s'),('Usar la misma geometría','s'),('Fijo: cantidad','1'),('Fijo: diámetro','2.54'),
        ('Desplazamiento relativo longitudinal del fijo','0'),
        ('Diámetro real del pasador común','2.54'),
    ]
    remaining = iter(answers)
    def answer(prompt):
        expected,value = next(remaining)
        assert expected in prompt
        return value
    monkeypatch.setattr('builtins.input',answer)
    word,audit = tmp_path/'manual.docx',tmp_path/'manual.json'
    assert main(['--word',str(word),'--json',str(audit)]) == 0
    assert list(remaining) == []
    capsys.readouterr()
    data = json.loads(audit.read_text(encoding='utf-8'))
    baseline = design_bearing_pair(bearing_pair_from_yaml(inputs())).to_dict()
    for role in ('movil','fijo'):
        assert data[role]['adopted'] == baseline[role]['adopted']
        assert {s['id']:(s['value'],s['limit'],s['status']) for s in data[role]['steps']} == {
            s['id']:(s['value'],s['limit'],s['status']) for s in baseline[role]['steps']}
    assert data['movil']['inputs']['actions']['ll_tn'] == pytest.approx(35.699/1.33)
    assert data['diametro_pasador_cm'] == 2.54
    text,_ = document_text(word)
    assert '0.85104' in text and '3.0293' in text


def test_manual_minimum_reaction_accepts_float_roundoff_but_not_larger_reaction():
    BearingAActions(dc_tn=20.016,dw_tn=3.095,min_vertical_tn=23.111)
    with pytest.raises(ValueError,match='DC\\+DW'):
        BearingAActions(dc_tn=20.016,dw_tn=3.095,min_vertical_tn=23.111001)


def test_modified_fixed_geometry_cannot_reuse_mobile_results_or_favorable_conclusion(tmp_path):
    data = inputs()
    data['fijo']['geometria'].update(zuncho_cm=.3,capa_exterior_cm=1.3)
    pair = design_bearing_pair(bearing_pair_from_yaml(data))
    assert pair.mobile.status == 'REFERENCIAL'
    assert pair.fixed.step('HS_HOLES').status == 'NO CUMPLE'
    text,_ = document_text(generate_bearing_pair_docx(pair,tmp_path/'fallo.docx'))
    assert 'Estado del sistema: NO CONFORME' in text
    assert '3 zunchos de 3 mm' in text and '3 zunchos de 4 mm' in text
    assert 'NO CUMPLE' in text and 'no satisface' in text


def test_pending_curve_and_full_temperature_range_remain_explicit(tmp_path):
    data = inputs()
    for role in ('movil','fijo'):
        data[role]['compresion'].update(fuente='Tabla de prueba incompleta',tipo='fabricante',puntos=[[4,0,0],[4,50,.01]])
        data[role]['movimientos']['usar_rango_completo'] = True
    pair = design_bearing_pair(bearing_pair_from_yaml(data))
    assert pair.status == 'PENDIENTE'
    text,_ = document_text(generate_bearing_pair_docx(pair,tmp_path/'pendiente.docx'))
    assert 'PENDIENTE' in text and 'No determinada' in text
    assert 'Tmax−Tmin' in text.replace(' ','')
    assert 'Estado del sistema: REFERENCIAL favorable' not in text


@pytest.mark.parametrize('pin',[0,-1,True,'25.4',float('nan'),float('inf')])
def test_invalid_pin_metadata_is_rejected(pin):
    data = inputs()
    data['diametro_pasador_cm'] = pin
    with pytest.raises(ValueError):
        bearing_pair_from_yaml(data)
