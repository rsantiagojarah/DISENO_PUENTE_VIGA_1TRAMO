from dataclasses import replace
from types import SimpleNamespace

import pytest

from bridge_design.cli.connected_2_yaml import connected_2_inputs_from_yaml, connected_2_yaml_template
from bridge_design.codes.mtc_detailing import minimum_flexural_cutoff_extension_cm
from bridge_design.domain.connected_foundation_cut import connected_foundation_reinforcement_cut
from bridge_design.domain.connected_reinforcement import SectionDemand
from bridge_design.domain.connected_section_checks import section_check
from bridge_design.domain.rebar_catalog import reinforcing_bar_by_label
from bridge_design.domain.reinforcement_cut_patterns import partial_cut_patterns


@pytest.fixture
def model():
    raw = connected_2_yaml_template(example=True)
    raw["estribo"]["geometria"]["luz_libre_superior_m"] = 16.6
    data = connected_2_inputs_from_yaml(raw)
    nodes = tuple(SimpleNamespace(x=float(x), y=0.0) for x in range(21))
    elements = tuple(SimpleNamespace(start=i, end=i+1, region="Zapata combinada") for i in range(20))
    mesh = SimpleNamespace(frame=SimpleNamespace(nodes=nodes, elements=elements))
    steel = SimpleNamespace(face="Superior", status="OK", bar_label='1"', spacing_m=.1,
        area_per_face_cm2_m=50, temperature_cm2_m=12.57, required_straight_anchor_cm=50,
        flexural_utilization=.8, shear_utilization=0, crack_utilization=0, minimum_utilization=.3)
    demands = tuple(SectionDemand("Resistencia Ia", "strength", 150, 0, 0, 0, i, .5,
                                flexural_phi_limit=.9) for i in range(20))
    return data, mesh, steel, demands


def high_moment(data, steel, demand):
    """Near capacity with the full grid, but above all reduced candidate grids."""
    low, high = 0, 1000
    for _ in range(40):
        middle = (low+high)/2
        check = section_check(replace(demand, moment=middle), data.left, 7.5,
                              reinforcing_bar_by_label(steel.bar_label), steel.spacing_m)
        if check["flexure_ratio"] < .99:
            low = middle
        else:
            high = middle
    return low


def shaped(model, face, indices):
    data, mesh, steel, demands = model
    steel.face = face
    peak = high_moment(data, steel, demands[0])
    sign = -1 if face == "Superior" else 1
    demands = tuple(replace(d, moment=sign*peak) if d.element in indices else d for d in demands)
    return data, mesh, steel, demands


def test_norm_extension_and_nonadjacent_partial_pattern():
    assert minimum_flexural_cutoff_extension_cm(140, 2.54, 1290) == 140
    assert minimum_flexural_cutoff_extension_cm(20, 2.54, 200) == pytest.approx(38.1)
    assert minimum_flexural_cutoff_extension_cm(20, 1.27, 1000) == 50
    patterns = partial_cut_patterns(reinforcing_bar_by_label('3/4"'), .125, 12.577, .30)
    assert patterns[0].cycle_bars == 3  # Half steel = 11.36, below minimum.
    assert patterns[0].remaining_area_cm2_m == pytest.approx(22.72*2/3)
    assert all(p.maximum_gap_m == .25 and p.continuing_bars/p.cycle_bars >= .5 for p in patterns)
    assert not partial_cut_patterns(reinforcing_bar_by_label('1"'), .2, 12.57, .30)


def test_upper_central_extra_and_existing_ld(model):
    data, mesh, steel, demands = shaped(model, "Superior", range(7, 13))
    steel.required_straight_anchor_cm = 200
    cut = connected_foundation_reinforcement_cut(data, mesh, steel, demands)
    assert cut.status == "APLICA"
    assert cut.pattern.cycle_bars == 2
    assert cut.theoretical_left_m == 7 and cut.theoretical_right_m == 13
    assert cut.cutoff_left_m == 5 and cut.cutoff_right_m == 15
    assert cut.additional_intervals_m == ((5, 15),)
    assert cut.distance_from_inner_face_m == 2.75
    assert cut.development_length_m == cut.adopted_extension_m == 2
    assert cut.continuous_interval_m == pytest.approx((.075, 19.925))
    assert cut.saved_steel_fraction > 0


def test_lower_end_extras_and_conservative_rounding(model):
    data, mesh, steel, demands = shaped(model, "Inferior", (2, 3, 16, 17))
    cut = connected_foundation_reinforcement_cut(data, mesh, steel, demands)
    assert cut.status == "APLICA"
    assert cut.theoretical_left_m == 4 and cut.theoretical_right_m == 16
    assert cut.cutoff_left_m == pytest.approx(5.42)
    assert cut.cutoff_right_m == pytest.approx(14.58)
    assert cut.additional_intervals_m[0] == pytest.approx((.075, 5.42))
    assert cut.additional_intervals_m[1] == pytest.approx((14.58, 19.925))
    assert cut.adopted_extension_m == pytest.approx((150-7.5-2.54/2)/100)
    assert cut.cutoff_left_m-cut.theoretical_left_m >= cut.adopted_extension_m
    assert cut.minimum_utilization <= 1


def test_asymmetric_far_peak_makes_both_end_bars_longer(model):
    data, mesh, steel, demands = shaped(model, "Inferior", (2, 3, 14, 17))
    cut = connected_foundation_reinforcement_cut(data, mesh, steel, demands)
    assert cut.status == "APLICA"
    assert cut.theoretical_left_m == 6
    assert cut.cutoff_left_m == pytest.approx(7.42)
    assert cut.cutoff_left_m + cut.cutoff_right_m == 20


@pytest.mark.parametrize("face,indices", [("Superior", (0, 7, 12, 19)), ("Inferior", (2, 9, 10, 17))])
def test_no_cut_when_bad_peak_is_outside_pdf_arrangement(model, face, indices):
    data, mesh, steel, demands = shaped(model, face, indices)
    cut = connected_foundation_reinforcement_cut(data, mesh, steel, demands)
    assert cut.status == "NO APLICA"
    assert not cut.additional_intervals_m
    assert cut.cutoff_left_m is cut.cutoff_right_m is None


def test_long_development_closes_lower_gap(model):
    data, mesh, steel, demands = shaped(model, "Inferior", (2, 3, 16, 17))
    steel.required_straight_anchor_cm = 1000
    cut = connected_foundation_reinforcement_cut(data, mesh, steel, demands)
    assert cut.status == "NO APLICA"
    assert "encuentran" in cut.reason


def test_full_selected_failure_reports_why_and_does_not_cut(model):
    data, mesh, steel, demands = model
    steel.status, steel.shear_utilization = "NO CUMPLE", 1.1
    cut = connected_foundation_reinforcement_cut(data, mesh, steel, demands)
    assert cut.status == "NO APLICA" and "cortante" in cut.reason
    assert cut.cutoff_left_m is None


def test_no_localized_extra_if_reduced_steel_covers_whole_footing(model):
    cut = connected_foundation_reinforcement_cut(*model)
    assert cut.status == "NO APLICA"
    assert "no se requiere refuerzo localizado" in cut.reason


def test_maximum_actual_gap_governs_cracking_not_equivalent_spacing(model):
    from bridge_design.domain.connected_foundation_cut import _ratios
    p = partial_cut_patterns(reinforcing_bar_by_label('3/4"'), .125, 12.577, .30)[0]
    # 0.1875 m equivalent spacing passes, while the actual 0.25 m gap fails.
    values = dict(flexure_ratio=0, shear_ratio=0, crack_ratio=.9, service_tension=True, maximum_spacing=.2)
    assert _ratios(values, p)[2] == 1.25


@pytest.mark.parametrize("field,state,face,element", [("shear", "strength", "Inferior", 9),
                                                   ("moment", "service", "Superior", 0)])
def test_shear_and_service_peaks_block_otherwise_feasible_cuts(model, field, state, face, element):
    indices = (2, 3, 16, 17) if face == "Inferior" else tuple(range(7, 13))
    data, mesh, steel, demands = shaped(model, face, indices)
    assert connected_foundation_reinforcement_cut(data, mesh, steel, demands).status == "APLICA"
    base = replace(demands[element], limit_state=state, moment=0, shear=0)
    low, high = 0, 1000
    key = "shear_ratio" if field == "shear" else "crack_ratio"
    for _ in range(40):
        value = (low+high)/2
        check = section_check(replace(base, **{field: value}), data.left, 7.5,
                              reinforcing_bar_by_label(steel.bar_label), steel.spacing_m)
        if check[key] < .999:
            low = value
        else:
            high = value
    altered = (*demands, replace(base, **{field: low}, case="Pico adicional"))
    cut = connected_foundation_reinforcement_cut(data, mesh, steel, altered)
    assert cut.status == "NO APLICA"
    assert cut.cutoff_left_m is None
