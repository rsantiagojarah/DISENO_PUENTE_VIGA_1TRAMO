"""Optional pipe load: independent equilibrium, symmetry and workflow regressions."""
from dataclasses import replace
from pathlib import Path

import pytest

from bridge_design.cli.yaml_inputs import project_inputs_from_yaml, project_yaml_template
from bridge_design.cli.yaml_io import load_yaml_file
from bridge_design.domain.pipe_load import PipeLoad, pipe_girder_loads, pipe_points, mirrored_layout
from bridge_design.domain import transverse_slab as ts, interior_girder as ig, exterior_girder as eg
from bridge_design.domain.girder_tributaries import girder_load_groups
from bridge_design.domain.longitudinal_loads import global_permanent_reactions, girder_reaction_cases


def raw_project():
    return load_yaml_file(Path(__file__).parent / 'fixtures/soldeoro_20261005.yaml')


def project(q=180, x=.46):
    raw = raw_project()
    raw['tuberia'] = dict(incluir=True, peso_lineal_kg_m=q, x_desde_borde_izquierdo_m=x)
    return project_inputs_from_yaml(raw)


@pytest.fixture(scope='module')
def loaded():
    return project()


@pytest.fixture(scope='module')
def analyses(loaded):
    return (ig.solve_interior_girder_design(loaded.interior_girder, loaded.materials, loaded.live_loads),
            eg.solve_exterior_girder_design(loaded.exterior_girder, loaded.materials, loaded.live_loads))


def test_missing_disabled_and_zero_are_identical_inputs():
    old = project_inputs_from_yaml(raw_project())
    disabled = raw_project()
    disabled['tuberia'] = dict(incluir=False, peso_lineal_kg_m=180, x_desde_borde_izquierdo_m=.46)
    assert project_inputs_from_yaml(disabled) == old == project(0)
    assert project_yaml_template()['tuberia']['incluir'] is False
    assert len(girder_load_groups(old)) == 2


@pytest.mark.parametrize('q,x', [(-1,.46),(float('nan'),.46),(float('inf'),.46),
                                (180,-1),(180,float('nan')),(180,float('inf')),(180,12.25)])
def test_invalid_loads_rejected(q, x):
    with pytest.raises(ValueError):
        project(q,x)


@pytest.mark.parametrize('key', ['peso_lineal_kg_m','x_desde_borde_izquierdo_m'])
def test_active_requires_explicit_numeric_data(key):
    raw = raw_project()
    raw['tuberia'] = dict(incluir=True,peso_lineal_kg_m=180,x_desde_borde_izquierdo_m=.46)
    raw['tuberia'].pop(key)
    with pytest.raises(ValueError, match=key):
        project_inputs_from_yaml(raw)
    raw['tuberia'][key] = True
    with pytest.raises(ValueError, match=key):
        project_inputs_from_yaml(raw)


@pytest.mark.parametrize('x', [0,.46,1,2.2,6.12,11.78,12.24])
def test_pipe_reactions_conserve_force_moment_and_mirror(x):
    p = project(x=x)
    g = p.transverse_slab.geometry
    loads = p.girder_pipe_loads
    assert sum(loads) == pytest.approx(.18, abs=1e-10)
    assert sum(s*r for s,r in zip(g.support_positions_m,loads)) == pytest.approx(.18*x, abs=1e-10)
    assert project(x=g.total_width_m-x).girder_pipe_loads == pytest.approx(tuple(reversed(loads)), abs=1e-10)
    if x == 1:
        assert loads == pytest.approx((.18,0,0,0,0), abs=1e-10)


@pytest.mark.parametrize('key', ['peso_lineal_kg_m','x_desde_borde_izquierdo_m'])
@pytest.mark.parametrize('value', [None,'',[],{}])
def test_malformed_yaml_values_report_validation_error(key,value):
    raw=raw_project()
    raw['tuberia']=dict(incluir=True,peso_lineal_kg_m=180,x_desde_borde_izquierdo_m=.46)
    raw['tuberia'][key]=value
    with pytest.raises(ValueError,match='Datos de tuberia no validos'):
        project_inputs_from_yaml(raw)


def test_actual_pipe_position_and_no_automatic_mirror(loaded):
    p = loaded
    layout = p.transverse_slab.load_layout
    points = pipe_points(layout)
    assert len(points) == 1
    assert points[0].position_m == .46
    assert points[0].p_tn == .18
    assert len(girder_load_groups(p)) == 5
    assert p.exterior_girder.pipe_load_tn_m == pytest.approx(.228138950892857)
    assert p.interior_girder.pipe_load_tn_m < 0
    case = ts.transverse_load_placement_cases(p.transverse_slab.geometry,p.materials,p.live_loads,layout)[1]
    assert case.point_loads == points


def test_viga_and_global_reactions_distinguish_design_from_physical(loaded, analyses):
    p = loaded
    interior, exterior = analyses
    # Analytical uniform-load bending diagram q*x*(L-x)/2, with no live-load distribution factor.
    q = .11*p.exterior_girder.asphalt_tributary_width_m + p.girder_pipe_loads[0]
    for x,m in exterior.dw.moment_samples_tn_m:
        assert m == pytest.approx(q*x*(15-x)/2)
    assert eg.combine_exterior_girder_moments(exterior)[0].combined_moment_tn_m == pytest.approx(298.2908565100753)
    assert ig.combine_interior_girder_moments(interior)[0].combined_moment_tn_m == pytest.approx(281.9074741451854)
    totals = global_permanent_reactions(p,*analyses)
    expected = (.11*(10.165-2.075)+.18)*15/2
    assert totals['DW'] == pytest.approx((expected,expected))
    physical = list(girder_reaction_cases(p,*analyses))
    assert len(physical) == 5
    assert sum(count*sum(a.dw.support_reactions_tn[i][1] for i in (0,1)) for _,count,a in physical) == pytest.approx(2*expected)


def test_transverse_and_diaphragm_weight_not_duplicated(loaded):
    from bridge_design.domain.diaphragm import solve_diaphragm_design
    p=loaded
    g=p.transverse_slab.geometry
    slab=ts.solve_transverse_slab_design(g,p.materials,p.live_loads,p.transverse_slab.load_layout)
    q=.11*(10.165-2.075)+.18
    assert sum(v for _,v in slab.dw.support_reactions_tn) == pytest.approx(q)
    diaphragm=solve_diaphragm_design(p.diaphragm,p.materials,p.live_loads,p.transverse_slab.load_layout)
    assert sum(v for _,v in diaphragm.dw.support_reactions_tn) == pytest.approx(q*.35)


def test_overhang_root_and_right_hand_coordinates(loaded):
    from bridge_design.domain._cantilever_slab_loads import cantilever_load_effects
    from bridge_design.domain._cantilever_slab_calculations import combine_cantilever_moments
    from bridge_design.domain.cantilever_slab import CantileverSlabParameters
    p=loaded
    g=p.transverse_slab.geometry
    layout=p.transverse_slab.load_layout
    def strength(l):
        effects=cantilever_load_effects(g,p.materials,p.live_loads,l,CantileverSlabParameters())[0]
        return next(r for r in combine_cantilever_moments(effects) if r.limit_state=='Resistencia').design_moment_tn_m
    assert strength(layout)-strength(replace(layout,pipe=None)) == pytest.approx(1.5*.18*.54)
    assert strength(mirrored_layout(layout,g.total_width_m)) == pytest.approx(strength(replace(layout,pipe=None)))
    right=replace(layout,pipe=PipeLoad(180,g.total_width_m-.46))
    assert strength(mirrored_layout(right,g.total_width_m)) == pytest.approx(strength(layout))


@pytest.mark.parametrize('weight', [0, 180])
def test_slab_chart_matches_design_at_every_station_with_and_without_pipe(weight):
    from bridge_design.reporting.deck_charts import strength_diagram_envelopes
    from bridge_design.domain.load_combinations import _combined_moment_at, default_transverse_slab_combinations
    p = project(q=weight, x=.40)
    g = p.transverse_slab.geometry
    result = ts.solve_transverse_slab_design(g, p.materials, p.live_loads, p.transverse_slab.load_layout)
    diagrams = strength_diagram_envelopes(result, include_pl=True, transverse=True)
    combination = default_transverse_slab_combinations()[0]
    for target, samples in (('max', diagrams.moment_upper), ('min', diagrams.moment_lower)):
        for x, value in samples:
            assert value == pytest.approx(_combined_moment_at(result, combination, x, target).combined_moment_tn_m)
    lower = dict(diagrams.moment_lower)
    assert lower[1.0] == pytest.approx(-1.1829093136125 - 1.5 * weight / 1000 * .60)
    assert lower[11.24] == pytest.approx(-1.1829093136125)


def test_terminal_entry_and_retry(loaded,monkeypatch):
    from bridge_design.cli.input_prompts import collect_pipe_load
    inputs=iter(['si','nan','.46','180','99','180','.46'])
    monkeypatch.setattr('builtins.input',lambda prompt='':next(inputs))
    assert collect_pipe_load(loaded.transverse_slab.geometry) == PipeLoad(180,.46)
    monkeypatch.setattr('builtins.input',lambda prompt='':'')
    assert collect_pipe_load(loaded.transverse_slab.geometry) is None


def test_full_workflow_both_sides_and_report_comparison(loaded,monkeypatch,tmp_path):
    from bridge_design.main import run_bridge_design
    from bridge_design.reporting.pipe_load_report import pipe_comparison_rows,pipe_input_lines
    captured=[]
    monkeypatch.setattr('builtins.input',lambda prompt='':'')
    monkeypatch.setattr('bridge_design.reporting.generate_deck_docx_with_dialog',captured.append)
    run_bridge_design(loaded)
    assert len(captured)==1
    data=captured[0]
    assert len(data.girder_groups)==5
    assert [g.side for g in data.cantilever_groups]==['izquierdo','derecho']
    left,right=data.cantilever_groups
    assert left.result.flexural_steel.design_moment_tn_m==pytest.approx(1.3287093136125)
    assert right.result.flexural_steel.design_moment_tn_m==pytest.approx(1.1829093136125)
    right_notes = ' '.join(right.result.applicability_notes)
    assert 'La tuberia se ubica en el volado izquierdo, a 0.460 m del borde exterior izquierdo' in right_notes
    assert '11.780 m desde el borde exterior derecho' in right_notes
    assert 'no carga directamente el volado derecho' in right_notes
    assert 'DW - tuberia llena no genera momento de voladizo:' not in right_notes
    assert right.report_context(data).cantilever_result is right.result
    rows={r[0]:r for r in pipe_comparison_rows(data)}
    assert float(rows['Viga V1'][2])==pytest.approx(298.290857,abs=1e-6)
    assert float(rows['Volado derecho'][1])==float(rows['Volado derecho'][2])
    assert 'x=0.460' in ' '.join(pipe_input_lines(loaded))
    # Exercise actual exporters: tables, both overhangs, grouped girders and physical reactions.
    from bridge_design.reporting.deck_docx import generate_deck_docx
    from bridge_design.reporting.deck_pdf import generate_deck_pdf
    from zipfile import ZipFile
    word=generate_deck_docx(data,tmp_path/'con_tuberia.docx')
    with ZipFile(word) as archive:
        xml=archive.read('word/document.xml').decode('utf-8')
    for text in ('Carga adicional de tuberia','Mu sin tuberia','298.290857','Volado derecho','Volado izquierdo'):
        assert text in xml
    assert 'no carga directamente el volado derecho' in xml
    from docx import Document
    headings = [p.text for p in Document(word).paragraphs if p.style.name == 'Heading 1']
    assert sum(h.startswith('3. Viga principal interior') for h in headings) == 1
    assert sum(h.startswith('4. Viga principal exterior') for h in headings) == 1
    assert sum(h.startswith('6. Losa en voladizo') for h in headings) == 1
    assert 'V2, V3, V4' in xml and 'V1, V5' in xml
    assert 'Detalle longitudinal comun' in xml and 'Zonas de estribos comunes' in xml
    assert 'segun zonas del detalle comun' in xml
    pdf=generate_deck_pdf(data,tmp_path/'con_tuberia.pdf')
    assert pdf.read_bytes().startswith(b'%PDF')
