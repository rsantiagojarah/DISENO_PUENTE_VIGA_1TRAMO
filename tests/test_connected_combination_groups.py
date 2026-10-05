from dataclasses import replace
from types import SimpleNamespace
import pytest

from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil
from bridge_design.domain.connected_design import analyze_connected_abutments
from bridge_design.reporting.connected_case_groups import combination_groups, case_label
from bridge_design.reporting.connected_frame_charts import frame_envelope
from bridge_design.reporting.connected_bearing_report import meyerhof_result


@pytest.fixture(scope='module')
def grouped_result():
    return analyze_connected_abutments(ConnectedInputs(FoundationSoil(3000,.5,26.7),mesh_size_m=1))


def test_groups_partition_every_case_and_preserve_without_bridge(grouped_result):
    groups=combination_groups(grouped_result)
    assert [g.name for g in groups]==['Resistencia Ia','Resistencia Ib','Servicio I','Evento Extremo I',
                                   'Sin tablero / Resistencia Ia','Sin tablero / Resistencia Ib',
                                   'Sin tablero / Servicio I','Sin tablero / Evento Extremo I']
    assert [len(g.cases) for g in groups]==[2,2,2,4,1,1,1,4]
    assert sorted(n for g in groups for n in g.cases)==sorted(r.name for r in grouped_result.results)
    assert {case_label(n) for n in groups[3].cases}=={
        'Evento Extremo I A EQ-1','Evento Extremo I B EQ-1',
        'Evento Extremo I A EQ+1','Evento Extremo I B EQ+1'}


def test_service_envelope_includes_service_and_excludes_other_families(grouped_result):
    group=combination_groups(grouped_result)[2]
    inflated=replace(grouped_result,results=tuple(
        replace(r,end_forces=tuple(tuple(1e9 for x in f) for f in r.end_forces))
        if r.name not in group.cases else r for r in grouped_result.results))
    assert frame_envelope(grouped_result,'moment',group.cases)==frame_envelope(inflated,'moment',group.cases)
    for points in frame_envelope(grouped_result,'moment',group.cases):
        for p in points:
            assert p.minimum_case in {case_label(n) for n in group.cases}
            assert p.maximum_case in {case_label(n) for n in group.cases}


def test_different_simultaneous_pairs_are_not_merged():
    r=SimpleNamespace(results=[SimpleNamespace(name=f'{pair} / Resistencia Ia BR{sign}',limit_state='strength')
                              for pair in ('Camión posición 1','Camión posición 2') for sign in ('-1','+1')])
    assert len(combination_groups(r))==2


def test_meyerhof_effective_area_and_loss_of_equilibrium():
    r=meyerhof_result(18,180,8,15)
    assert r.effective_width==16
    assert r.pressure==pytest.approx(11.25)
    assert r.utilization==pytest.approx(.75)
    assert r.status=='CUMPLE'
    assert meyerhof_result(18,180,0,15).status=='NO CUMPLE'
    assert meyerhof_result(18,180,8,10).status=='NO CUMPLE'
