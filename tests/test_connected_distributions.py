from dataclasses import replace
from math import sqrt

import pytest

from bridge_design.domain.abutment import _stem_temperature_result, _footing_temperature_result, _shear_beta_detail
from bridge_design.domain.connected_design import solve_connected_abutments
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil
from bridge_design.domain.connected_options import apply_connected_selections
from bridge_design.domain.connected_reinforcement import ConnectedBarChoice, ConnectedSteelChoice
from bridge_design.domain.connected_distributions import reinforcement_demands
from bridge_design.reporting.connected_audit import build_connected_audit


@pytest.fixture(scope="module")
def analysis():
    return solve_connected_abutments(ConnectedInputs(FoundationSoil(3000,0,26.7),
                                    mesh_size_m=1, include_without_bridge=False))


def test_requested_distributions_and_individual_temperature_criteria(analysis):
    assert len(analysis.reinforcement) == 16
    for prefix in ("Pantalla", "Parapeto"):
        assert {s.region for s in analysis.reinforcement if s.base_region == prefix} == {
            f"{prefix} - {direction} {face}" for direction in ("vertical","horizontal")
            for face in ("relleno","exterior")}
    assert {s.region for s in analysis.reinforcement if s.base_region == "Losa central"} == {
        f"Losa central - {direction} {face}" for direction in ("longitudinal", "transversal")
        for face in ("superior", "inferior")}
    for steel in analysis.reinforcement:
        side = analysis.inputs.left if "izquierda" in steel.region else analysis.inputs.right
        if steel.region.startswith("Pantalla"):
            assert steel.temperature_cm2_m == _stem_temperature_result(side).required_as_cm2_m
        elif steel.region.startswith("Zapata"):
            assert steel.temperature_cm2_m == _footing_temperature_result(side).required_as_cm2_m
        if steel.role == "temperature":
            assert steel.required_as_cm2_m == steel.temperature_cm2_m
            assert steel.flexural_utilization == steel.shear_utilization == steel.crack_utilization == 0


def test_legacy_toe_factor_does_not_amplify_distributed_design_demands(analysis):
    left = replace(analysis.inputs.left, reinforcement=replace(
        analysis.inputs.left.reinforcement, toe_moment_capacity_multiplier=1.33))
    data = replace(analysis.inputs, left=left, right=left)
    original = reinforcement_demands(analysis.inputs, analysis.mesh, analysis.results)
    actual = reinforcement_demands(data, analysis.mesh, analysis.results)
    assert actual == original
    assert all(d.capacity_multiplier == 1 for d in actual['Zapata - puntera inferior'])


def test_one_face_selection_does_not_change_other_faces_or_frame(analysis):
    label = "Losa central - longitudinal superior"
    choice = ConnectedBarChoice('3/4"', .15, is_custom=True)
    chosen = apply_connected_selections(analysis, {label: ConnectedSteelChoice(choice,choice)})
    assert chosen.results is analysis.results and chosen.foundation_checks is analysis.foundation_checks
    original = {s.region: s for s in analysis.reinforcement}
    for steel in chosen.reinforcement:
        if steel.region != label:
            assert steel == original[steel.region]
        else:
            assert steel.area_per_face_cm2_m == pytest.approx(2.84/.15)
            assert steel.flexural_utilization != original[label].flexural_utilization
    audit = build_connected_audit(chosen)
    assert audit["steel"][label]["service"]["area"] == pytest.approx(2.84/.15)


def test_signs_do_not_mix_opposite_faces_and_shear_matches_individual(analysis):
    demands = reinforcement_demands(analysis.inputs, analysis.mesh, analysis.results)
    common = demands["Pantalla - vertical relleno"]
    left = [d for d in common if analysis.mesh.frame.elements[d.element].region.endswith("izquierda")]
    right = [d for d in common if analysis.mesh.frame.elements[d.element].region.endswith("derecha")]
    assert left and right
    assert all(d.moment <= 0 for d in left)
    assert all(d.moment >= 0 for d in right)
    assert all(d.moment <= 0 for d in demands["Losa central - longitudinal superior"])
    assert all(d.moment >= 0 for d in demands["Losa central - longitudinal inferior"])
    audit = build_connected_audit(analysis)
    for steel in analysis.reinforcement:
        if steel.role == "primary" and steel.region.startswith(("Zapata", "Losa")):
            row = audit["steel"][steel.region]["shear"]
            assert row["shear_method"] == "general"
            detail = _shear_beta_detail(abs(row["demand"]["moment"]), abs(row["demand"]["shear"]),
                row["area"], row["effective"], row["demand"]["depth_cm"], "general", inputs=analysis.inputs.left, axial_tn_m=row["demand"]["axial"])
            assert row["beta"] == pytest.approx(detail["beta"])
            assert row["shear_capacity"] == pytest.approx(.9*.265*detail["beta"]*sqrt(210)*100*row["shear_depth"]/1000)
        if steel.part:
            side = analysis.inputs.left if "izquierda" in steel.region else analysis.inputs.right
            cantilever = side.geometry.heel_length_m if steel.part == "talon" else side.geometry.toe_length_m
            length = side.geometry.footing_width_m-cantilever
            assert steel.available_anchor_cm == pytest.approx(100*length-side.reinforcement.footing_cover_cm)


def test_no_puntera_omits_that_design_without_losing_other_steel(analysis):
    left = replace(analysis.inputs.left, geometry=replace(analysis.inputs.left.geometry,toe_length_m=0))
    result = solve_connected_abutments(replace(analysis.inputs,left=left,right=left))
    assert len(result.reinforcement) == 15
    assert not any(s.region == "Zapata - puntera inferior" for s in result.reinforcement)
    assert any(s.region == "Zapata - transversal inferior" for s in result.reinforcement)


def test_shared_design_checks_both_sides_with_different_bridge_reactions(analysis):
    from bridge_design.domain.connected_distributions import distribution_demands
    from bridge_design.domain.connected_reinforcement import design_region, section_demands
    from bridge_design.domain.connected_options import choice_from_steel
    right = replace(analysis.inputs.right, loads=replace(analysis.inputs.right.loads, pll_im_tn_m=12.0))
    result = solve_connected_abutments(replace(analysis.inputs, right=right))
    definitions = {d.label: d for d in distribution_demands(result.inputs, result.mesh,
                    section_demands(result.inputs, result.mesh, result.results))}
    audit = build_connected_audit(result)
    for steel in result.reinforcement:
        if steel.base_region == "Losa central":
            continue
        definition = definitions[steel.region]
        sides = []
        for physical_side in ("izquierda", "derecha"):
            demands = tuple(d for d in definition.demands
                            if result.mesh.frame.elements[d.element].region.endswith(physical_side))
            assert demands
            one_side = replace(definition, demands=demands)
            sides.append(design_region(result.inputs, result.mesh, steel.region, demands,
                         choice_from_steel(steel), distribution=one_side))
        for field in ("flexural_utilization", "shear_utilization", "crack_utilization", "required_as_cm2_m"):
            assert getattr(steel, field) == pytest.approx(max(getattr(s, field) for s in sides))
        if steel.role == "primary":
            if all(s.available_anchor_cm is not None for s in sides):
                assert steel.available_anchor_cm == pytest.approx(min(s.available_anchor_cm for s in sides))
            for key, field in (("flexure", "flexural_utilization"), ("shear", "shear_utilization"),
                               ("service", "crack_utilization")):
                row = audit["steel"][steel.region][key]
                assert row["region"] in (steel.base_region+" izquierda", steel.base_region+" derecha")
                assert row["side"] in ("Izquierdo", "Derecho")
                assert row[{"flexure":"flexure_ratio","shear":"shear_ratio","service":"crack_ratio"}[key]] == pytest.approx(getattr(steel,field))


@pytest.mark.parametrize("field", ("geometry", "materials", "reinforcement"))
def test_common_design_rejects_incompatible_sides(analysis, field):
    values = {"geometry": {"retained_height_m": 11.2},
              "materials": {"concrete_strength_kg_cm2": 280},
              "reinforcement": {"footing_cover_cm": 8.0}}
    right = replace(analysis.inputs.right, **{field: replace(getattr(analysis.inputs.right, field), **values[field])})
    with pytest.raises(ValueError, match="diseno comun"):
        replace(analysis.inputs, right=right)


def test_footing_faces_exclude_wall_members_and_retain_face_sections(analysis):
    from bridge_design.domain.connected_geometry import local_x
    demands = reinforcement_demands(analysis.inputs, analysis.mesh, analysis.results)
    for part, label in (("puntera", "puntera inferior"), ("talon", "talon superior")):
        faces = set()
        for d in demands["Zapata - " + label]:
            e = analysis.mesh.frame.elements[d.element]
            a, b = (analysis.mesh.frame.nodes[n] for n in (e.start, e.end))
            index = 0 if e.region.endswith("izquierda") else 1
            g = (analysis.inputs.left, analysis.inputs.right)[index].geometry
            x = local_x(analysis.inputs, index, a.x+d.station*(b.x-a.x))
            mid = local_x(analysis.inputs, index, (a.x+b.x)/2)
            face = g.toe_length_m + (g.lower_stem_thickness_m if part == "talon" else 0)
            if part == "puntera":
                assert x <= face+1e-8 and mid < face
            else:
                assert x >= face-1e-8 and mid > face
            if abs(x-face) < 1e-8:
                faces.add(index)
        assert faces == {0, 1}


def test_slab_design_includes_both_thickness_transitions(analysis):
    demands = reinforcement_demands(analysis.inputs, analysis.mesh, analysis.results)
    regions = {analysis.mesh.frame.elements[d.element].region
               for d in demands["Losa central - longitudinal inferior"]}
    for side, length in (("izquierda", analysis.inputs.left_transition_m),
                         ("derecha", analysis.inputs.right_transition_m)):
        if length:
            assert "Transicion " + side in regions


def test_axial_force_changes_general_shear_beta_and_compression_is_bounded():
    arguments = (40, 25, 20, 80, 100, "general")
    zero = _shear_beta_detail(*arguments)
    tension = _shear_beta_detail(*arguments, axial_tn_m=30)
    compression = _shear_beta_detail(*arguments, axial_tn_m=-10000)
    expected = zero["epsilon_s"] + 1000*0.5*30/(2000000*20)
    assert tension["epsilon_s"] == pytest.approx(expected)
    assert tension["beta"] < zero["beta"]
    assert compression["epsilon_s"] == 0
