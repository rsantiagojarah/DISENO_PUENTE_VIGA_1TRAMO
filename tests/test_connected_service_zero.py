from math import isfinite

import pytest

from bridge_design.domain.abutment import AbutmentInputs
from bridge_design.domain.connected_reinforcement import SectionDemand
from bridge_design.domain.connected_section_checks import section_check
from bridge_design.domain.rebar_catalog import reinforcing_bar_by_label


@pytest.mark.parametrize('moment', [0.0, 1e-12, -1e-12])
def test_zero_service_demand_has_no_artificial_crack_spacing(moment):
    demand = SectionDemand('Servicio I', 'service', 75, 0, 0, moment, 0, 0)
    row = section_check(demand, AbutmentInputs(), 7.5, reinforcing_bar_by_label('5/8"'), .25)
    assert row['service_tension'] is False
    assert row['stress'] == row['crack_ratio'] == 0
    assert isfinite(row['maximum_spacing']) and row['maximum_spacing'] <= .30


def test_service_tension_keeps_the_actual_crack_and_stress_checks():
    demand = SectionDemand('Servicio I', 'service', 75, 0, 0, 80, 0, 0)
    row = section_check(demand, AbutmentInputs(), 7.5, reinforcing_bar_by_label('5/8"'), .25)
    assert row['service_tension'] is True
    assert row['stress'] > row['stress_limit']
    assert row['crack_ratio'] > 1
