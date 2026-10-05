from dataclasses import replace

import pytest

from bridge_design.domain.anchorage_status import anchorage_status, anchorage_passes
from bridge_design.domain.abutment import (
    solve_abutment_design, _development_checks, _required_anchor_length_cm,
    _available_development_length_cm,
)
from bridge_design.reporting.abutment_docx import _is_ok


@pytest.mark.parametrize("available,straight,hooked,expected", [
    (100, 100, 20, "RECTO Y CON GANCHO"),
    (40, 100, 20, "SOLO GANCHO"),
    (20, 100, 20, "SOLO GANCHO"),
    (19, 100, 20, "NO CUMPLE"),
    (0, 100, 20, "NO CUMPLE"),
    (20, 20, 20, "RECTO Y CON GANCHO"),
    (None, 100, 20, "PENDIENTE DETALLE"),
])
def test_three_length_states(available, straight, hooked, expected):
    assert anchorage_status(available, straight, hooked) == expected
    assert anchorage_passes(expected) == (expected in ("RECTO Y CON GANCHO", "SOLO GANCHO"))
    assert _is_ok(expected) == anchorage_passes(expected)


def test_inverted_required_lengths_need_review():
    with pytest.raises(ValueError, match="ld con gancho supera ld recto"):
        anchorage_status(40, 20, 100)


@pytest.fixture(scope="module")
def individual():
    return solve_abutment_design()


@pytest.mark.parametrize("mode", ("both", "hook", "neither"))
def test_individual_uses_shared_states_and_matching_detail_length(individual, monkeypatch, mode):
    original = individual.development_checks[0]
    length = {"both": max(original.required_ld_cm, original.required_hooked_ld_cm)+1,
              "hook": original.required_hooked_ld_cm,
              "neither": min(original.required_ld_cm, original.required_hooked_ld_cm)-1}[mode]
    monkeypatch.setattr("bridge_design.domain.abutment._available_development_length_cm", lambda *args: length)
    check = _development_checks(individual.inputs, (individual.stem_design,))[0]
    expected = {"both": "RECTO Y CON GANCHO", "hook": "SOLO GANCHO", "neither": "NO CUMPLE"}[mode]
    assert check.status == check.anchorage_type == expected
    assert _required_anchor_length_cm(check) == (check.required_hooked_ld_cm if mode == "hook" else check.required_ld_cm)


def test_individual_footing_development_crosses_stem(individual):
    g = individual.inputs.geometry
    r = individual.inputs.reinforcement.footing_cover_cm
    assert _available_development_length_cm(individual.inputs, "Zapata - talon superior") == pytest.approx(
        (g.lower_stem_thickness_m+g.toe_length_m)*100-r)
    assert _available_development_length_cm(individual.inputs, "Zapata - puntera inferior") == pytest.approx(
        (g.lower_stem_thickness_m+g.heel_length_m)*100-r)
