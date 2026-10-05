from types import SimpleNamespace
from bridge_design.reporting.connected_bearing_report import spring_pressure_result


def test_pressure_uses_each_solved_case_and_tributary_area_not_largest_reaction():
    model = SimpleNamespace(springs=[SimpleNamespace(tributary_area=2),
                                    SimpleNamespace(tributary_area=.5)])
    assert spring_pressure_result(model, SimpleNamespace(spring_reactions=[20, 8])) == (1, 16)
    assert spring_pressure_result(model, SimpleNamespace(spring_reactions=[30, 0])) == (0, 15)
