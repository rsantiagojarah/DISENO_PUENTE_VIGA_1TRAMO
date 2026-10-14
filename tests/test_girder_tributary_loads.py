"""Conservation, real load combinations and replay of the published bridge."""
from dataclasses import replace
from pathlib import Path

import pytest

from bridge_design.cli.yaml_inputs import project_inputs_from_yaml, project_yaml_template
from bridge_design.cli.yaml_io import load_yaml_file
from bridge_design.domain.girder_tributaries import girder_load_groups
from bridge_design.domain.interior_girder import solve_interior_girder_design, combine_interior_girder_moments, combine_interior_girder_shears
from bridge_design.domain.exterior_girder import solve_exterior_girder_design
from bridge_design.domain.longitudinal_loads import global_permanent_reactions, girder_reaction_cases
from bridge_design.validation.input_validators import require_positive, require_non_negative, require_range


def soldeoro():
    return project_inputs_from_yaml(load_yaml_file(Path(__file__).parent / 'fixtures/soldeoro_20261005.yaml'))


@pytest.fixture(scope='module')
def wide_project():
    raw = load_yaml_file(Path(__file__).parent / 'fixtures/soldeoro_20261005.yaml')
    raw['ubicacion_cargas_modelo_transversal'].update(
        ancho_vereda_cada_lado_m=3., ubicacion_barrera_izquierda_m=3.1,
        asfalto_inicio_m=3.475, asfalto_fin_m=8.765,
        recorrido_vehicular_inicio_m=3.475, recorrido_vehicular_fin_m=8.765)
    return project_inputs_from_yaml(raw)


@pytest.fixture(scope='module')
def wide_results(wide_project):
    p = wide_project
    return (solve_interior_girder_design(p.interior_girder, p.materials, p.live_loads),
            solve_exterior_girder_design(p.exterior_girder, p.materials, p.live_loads))


def test_wide_sidewalk_is_partitioned_into_real_girder_groups(wide_project):
    rows = wide_project.girder_tributaries
    assert [r.sidewalk_m for r in rows] == pytest.approx([2.18, .82, 0., .82, 2.18])
    assert [r.asphalt_m for r in rows] == pytest.approx([0., 1.365, 2.56, 1.365, 0.])
    assert [[r.index for r in g] for g in girder_load_groups(wide_project)] == [[0, 4], [1, 3], [2]]
    assert sum(r.sidewalk_m for r in rows) == pytest.approx(6.)
    assert sum(r.asphalt_m for r in rows) == pytest.approx(5.29)


def test_pedestrians_enter_interior_combinations_service_and_shear(wide_project, wide_results):
    p, analysis = wide_project, wide_results[0]
    qpl = .82 * p.live_loads.pedestrian.load_tn_m2
    assert sum(v for _, v in analysis.pl.support_reactions_tn) == pytest.approx(qpl * 15)
    without = replace(analysis, pl=None)
    actual = combine_interior_girder_moments(analysis)
    original = combine_interior_girder_moments(without)
    for row, old, factor in zip(actual, original, (1.75, 1., .8)):
        assert row.pl_factor == factor
        # At a common station the increment must equal the physical PL effect.
        x = row.position_m
        assert row.pl_moment_tn_m == pytest.approx(qpl*x*(15-x)/2)
        assert row.combined_moment_tn_m >= old.combined_moment_tn_m
        assert row.combined_moment_tn_m == pytest.approx(row.dc_factor*row.dc_moment_tn_m + row.dw_factor*row.dw_moment_tn_m + factor*row.pl_moment_tn_m + row.ll_im_factor*row.ll_im_moment_tn_m)
    for row in combine_interior_girder_shears(p.interior_girder, analysis):
        assert row.pl_shear_tn > 0
        assert row.combined_shear_tn == pytest.approx(1.25*row.dc_shear_tn+1.5*row.dw_shear_tn+1.75*row.pl_shear_tn+1.75*row.ll_im_shear_tn)


def test_global_reactions_conserve_loads_not_representative_girder_times_count(wide_project, wide_results):
    p = wide_project
    totals = global_permanent_reactions(p, *wide_results)
    assert sum(totals['PL']) == pytest.approx(6*p.live_loads.pedestrian.load_tn_m2*15)
    assert sum(totals['DW']) == pytest.approx(5.29*.11*15)
    uniform_dc = .48*12.24 + 5*2.4*.5*.9 + 6*.36 + 2*(.3+.4869)
    assert sum(totals['DC']) == pytest.approx(uniform_dc*15+2.4*.35*.7*12.24)
    assert len(tuple(girder_reaction_cases(p, *wide_results))) == 3


def test_asymmetric_short_paving_does_not_extend_to_tributary_end():
    raw = project_yaml_template()
    raw['ubicacion_cargas_modelo_transversal'].update(asfalto_inicio_m=1.2, asfalto_fin_m=1.5)
    p = project_inputs_from_yaml(raw)
    assert p.exterior_girder.asphalt_tributary_width_m == pytest.approx(.3)
    assert [r.asphalt_m for r in p.girder_tributaries] == pytest.approx([.3, 0, 0, 0])
    assert p.interior_girder.effective_asphalt_width_m == 0
    right = replace(p, exterior_girder_index=3)
    assert right.exterior_girder.asphalt_tributary_width_m == 0


def test_soldeoro_published_moments_and_reactions_remain_unchanged():
    p = soldeoro()
    interior = solve_interior_girder_design(p.interior_girder, p.materials, p.live_loads)
    exterior = solve_exterior_girder_design(p.exterior_girder, p.materials, p.live_loads)
    from bridge_design.domain.exterior_girder import combine_exterior_girder_moments
    assert combine_interior_girder_moments(interior)[0].combined_moment_tn_m == pytest.approx(281.9074741451854, abs=1e-9, rel=0)
    assert combine_exterior_girder_moments(exterior)[0].combined_moment_tn_m == pytest.approx(288.6730886878097, abs=1e-9, rel=0)
    totals = global_permanent_reactions(p, interior, exterior)
    for key, expected in [('DC', 109.146), ('DW', 6.674), ('PL', 9.338)]:
        assert totals[key] == pytest.approx((expected, expected), abs=.0005, rel=0)
    assert len(girder_load_groups(p)) == 2


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), True, '2', None])
@pytest.mark.parametrize('validator', [require_positive, require_non_negative, lambda x,n: require_range(x,n,0,1)])
def test_invalid_numeric_inputs_are_rejected(value, validator):
    with pytest.raises(ValueError, match='finito'):
        validator(value, 'dato')


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_yaml_nonfinite_asphalt_is_rejected_before_analysis(value):
    raw = project_yaml_template()
    raw['materiales']['asfalto']['espesor_m'] = value
    with pytest.raises(ValueError, match='finito'):
        project_inputs_from_yaml(raw)


def test_full_workflow_designs_each_distinct_group(wide_project, monkeypatch):
    from bridge_design.main import run_bridge_design

    captured = []
    monkeypatch.setattr('builtins.input', lambda prompt='': '')
    monkeypatch.setattr('bridge_design.reporting.generate_deck_docx_with_dialog', captured.append)
    run_bridge_design(wide_project)
    assert len(captured) == 1
    data = captured[0]
    groups = {group.indices: group for group in data.girder_groups}
    assert set(groups) == {(0, 4), (1, 3), (2,)}
    adjacent, center = groups[(1, 3)], groups[(2,)]
    assert adjacent.result.pl is not None
    assert center.result.pl is None
    assert adjacent.reinforcement.main.design_moment_tn_m != center.reinforcement.main.design_moment_tn_m
    assert adjacent.shear.controlling_shear.pl_shear_tn > 0
    assert center.shear.controlling_shear.pl_shear_tn == 0
    context = center.report_context(data)
    assert context.interior_result is center.result
    assert context.interior_selected is center.selected
    assert context.interior_detail is center.detail
    # Every group is fully detailed with PL included at the same stations.
    from bridge_design.domain.girder_detailing import detail_interior_girder
    from bridge_design.domain.interior_girder import _moment_at
    detail = detail_interior_girder('Interior con vereda', wide_project.interior_girder,
                                   wide_project.materials, adjacent.result, adjacent.reinforcement)
    for station in detail.envelope:
        x = station.x_m
        expected = sum(factor * _moment_at(case.moment_samples_tn_m, x) for case, factor in
                       ((adjacent.result.dc, 1.25), (adjacent.result.dw, 1.5),
                        (adjacent.result.pl, 1.75), (adjacent.result.ll_im_envelope, 1.75)))
        assert station.mu_tn_m == pytest.approx(expected)
