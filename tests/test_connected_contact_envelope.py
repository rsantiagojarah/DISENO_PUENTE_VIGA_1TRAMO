from types import SimpleNamespace as S
from bridge_design.reporting.connected_case_groups import foundation_combination_groups
from bridge_design.reporting.connected_contact_envelope import contact_envelope


def test_four_families_cover_with_and_without_deck_cases():
    rows = [S(name=f"{prefix} / {family} {suffix}", limit_state=state)
            for prefix in ("Par simultaneo ingresado", "Sin tablero")
            for family, state in (("Resistencia Ia", "strength"), ("Resistencia Ib", "strength"),
                                  ("Servicio I", "service"), ("Evento Extremo I", "extreme"))
            for suffix in ("BR-1", "BR+1")]
    groups = foundation_combination_groups(S(results=rows))
    assert len(groups) == 4
    assert [g.name for g in groups] == ["Resistencia Ia", "Resistencia Ib", "Servicio I", "Evento Extremo I"]
    assert all(len(g.cases) == 4 for g in groups)
    assert {name for group in groups for name in group.cases} == {row.name for row in rows}


def test_envelope_is_pointwise_and_preserves_signed_settlement_and_source():
    rows = [S(name='a', spring_reactions=[20, 8], displacements=[0, -.002, 0, 0, .001, 0]),
            S(name='b', spring_reactions=[0, 10], displacements=[0, .003, 0, 0, -.004, 0]),
            S(name='excluded', spring_reactions=[1000, 1000], displacements=[0]*6)]
    model = S(nodes=[S(x=0), S(x=1)], springs=[S(node=0, tributary_area=2), S(node=1, tributary_area=.5)])
    points = contact_envelope(S(results=rows, mesh=S(frame=model)), S(cases=('a', 'b')))
    assert [(p['q_min'],p['q_max'],p['q_case']) for p in points] == [(0,10,'a'), (16,20,'b')]
    assert [(p['s_min'],p['s_max']) for p in points] == [(-3,2), (-1,4)]
