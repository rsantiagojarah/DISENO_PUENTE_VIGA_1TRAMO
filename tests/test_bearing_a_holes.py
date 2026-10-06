from dataclasses import replace
from math import pi

import pytest

from bridge_design.cli.bearing_a_pair_yaml import bearing_pair_template, bearing_pair_from_yaml
from bridge_design.domain.bearing_a_pair import design_bearing_pair
from bridge_design.domain.bearing_method_a import BearingAGeometry


def perforated_pair():
    data = bearing_pair_template()
    data['movil']['geometria'].update(cantidad_agujeros=2, diametro_agujeros_cm=2)
    data['fijo']['geometria'].update(cantidad_agujeros=4, diametro_agujeros_cm=2)
    return design_bearing_pair(bearing_pair_from_yaml(data))


def test_holes_update_area_shape_horizontal_force_and_plate_requirement():
    plain = design_bearing_pair(bearing_pair_from_yaml(bearing_pair_template()))
    pair = perforated_pair()
    for r, original, count in ((pair.mobile, plain.mobile, 2), (pair.fixed, plain.fixed, 4)):
        g = r.adopted
        area = 30*45-count*pi
        assert r.value('AREA') == pytest.approx(area)
        assert r.value('SI') == pytest.approx(area/(1.5*(150+count*2*pi)))
        assert r.value('SIGMA') > original.value('SIGMA')
        base = max(r.value('HS_SERVICE'), r.value('HS_FATIGUE'), r.value('HS_MIN'))
        assert r.value('HS_HOLES') == pytest.approx(2*30/(30-count*2)*base)
        assert r.step('HS_HOLES').status == 'NO CUMPLE'
    assert pair.mobile.value('HU')/plain.mobile.value('HU') == pytest.approx(pair.mobile.value('AREA')/plain.mobile.value('AREA'))
    assert pair.status == 'NO CONFORME'


@pytest.mark.parametrize('count,diameter', [(True,2),(-1,2),(1,0),(0,2),(2,float('nan')),(20,2)])
def test_invalid_hole_geometry_is_rejected(count, diameter):
    with pytest.raises(ValueError):
        BearingAGeometry(width_cm=30,length_cm=45,hole_count=count,hole_diameter_cm=diameter)


def test_auto_selection_accounts_for_perforated_steel():
    data = bearing_pair_template()
    for role in ('movil','fijo'):
        data[role]['geometria'].update(cantidad_agujeros=2,diametro_agujeros_cm=2,zuncho_cm=None)
        data[role]['movimientos'].update(longitud_expansion_m=15,retraccion_cm=.45)
        data[role]['acciones'].update(dc_tn=35,ll_sin_im_tn=10)
    pair = design_bearing_pair(bearing_pair_from_yaml(data))
    for r in (pair.mobile,pair.fixed):
        assert r.adopted.steel_cm >= r.value('HS_HOLES')
        assert r.step('HS_HOLES').status == 'CUMPLE'


def test_hole_inputs_and_calculation_are_visible_in_report(tmp_path):
    from docx import Document
    from bridge_design.reporting.bearing_a_pair_docx import generate_bearing_pair_docx
    from bridge_design.cli.bearing_a_pair_output import format_bearing_pair
    pair = perforated_pair()
    text = format_bearing_pair(pair,width=112)
    assert 'Perforaciones pasantes' in text and 'NO CUMPLE' in text
    assert len(text.splitlines()) < 90
    doc = Document(generate_bearing_pair_docx(pair,tmp_path/'perforado.docx'))
    body = '\n'.join(p.text for p in doc.paragraphs)
    assert 'sin perforaciones ni superficie' not in body
    assert 'todos los agujeros' in body and 'Zuncho con perforaciones pasantes' in body
    assert 'AASHTO C14.7.5.1-1' in body
