"""Recalculate design checks for the reinforcement actually adopted.

Selections are never silently replaced.  These functions update demands and
compliance on copies, so an inadequate selection remains visible as a failure.
"""

from dataclasses import replace

from bridge_design.domain.concrete_flexure import rectangular_flexural_response
from bridge_design.domain.interior_girder import (
    _minimum_flexural_area_cm2, _skin_reinforcement_requirements,
    t_beam_flexural_response, t_beam_flexural_steel_area_cm2,
)
from bridge_design.domain.rebar_catalog import SpacingGrid, generate_spacing_options
from bridge_design.domain.reinforcement import flexural_steel_area_cm2
from bridge_design.validation.input_validators import require_positive


def flexural_design_for_option(design, option, concrete, steel):
    """Return flexural demands at the selected depth, without changing loads.

    Strip designs retain the diameter and strip width associated with their
    stored depth, making this operation idempotent.  Unsupported legacy design
    types are left alone rather than guessing their cover or axial demands.
    """
    if option is None:
        return design
    if hasattr(design, "load_cases") and hasattr(design, "axial_area_cm2_m"):
        from bridge_design.domain._cantilever_slab_calculations import cantilever_flexural_for_bar
        return cantilever_flexural_for_bar(design, option.bar, concrete, steel)
    strip = hasattr(design, "bar_diameter_cm")
    if strip:
        depth = design.effective_depth_cm + (design.bar_diameter_cm - option.bar.diameter_cm) / 2
        width = 100 * design.strip_length_m
    elif hasattr(option, "effective_depth_cm"):
        depth = option.effective_depth_cm
        width = getattr(design, "section_width_cm", getattr(design, "web_width_cm", 0))
    else:
        return design
    require_positive(depth, "peralte efectivo del armado adoptado")
    target = max(design.design_moment_tn_m, design.minimum_capacity_moment_tn_m)
    phi = design.flexural_resistance_factor
    args = dict(
        design_moment_tn_m=target, effective_depth_cm=depth,
        concrete_strength_kg_cm2=concrete.compressive_strength_kg_cm2,
        steel_yield_kg_cm2=steel.yield_strength_kg_cm2, phi=phi,
        steel_elastic_modulus_kg_cm2=steel.elastic_modulus_kg_cm2,
    )
    updates = dict(effective_depth_cm=depth)
    if hasattr(design, "flange_width_cm"):
        strength, block = t_beam_flexural_steel_area_cm2(
            **args, flange_width_cm=design.flange_width_cm,
            flange_thickness_cm=design.flange_thickness_cm, web_width_cm=width,
        )
        updates["neutral_axis_block_depth_cm"] = block
    else:
        strength = flexural_steel_area_cm2(**args, strip_width_cm=width)
    if strip:
        strength /= design.strip_length_m
        updates.update(
            bar_diameter_cm=option.bar.diameter_cm,
            strength_area_cm2_m=strength, capacity_minimum_area_cm2_m=strength,
            required_area_cm2_m=max(strength, design.minimum_area_cm2_m),
        )
    else:
        minimum = _minimum_flexural_area_cm2(
            concrete.compressive_strength_kg_cm2, steel.yield_strength_kg_cm2, width, depth,
        )
        updates.update(strength_area_cm2=strength, minimum_area_cm2=minimum,
                       required_area_cm2=max(strength, minimum))
    return replace(design, **updates)


def flexural_capacity(design, area, concrete, steel):
    """Design moment capacity, in Tn.m (per metre for strip reinforcement)."""
    # Retain the overhang's existing As(M) + As(N) model: reserve As(N) first.
    area -= getattr(design, "axial_area_cm2_m", 0.0)
    if area <= 0.0:
        return 0.0
    args = dict(steel_area_cm2=area, effective_depth_cm=design.effective_depth_cm,
        concrete_strength_kg_cm2=concrete.compressive_strength_kg_cm2,
        steel_yield_kg_cm2=steel.yield_strength_kg_cm2,
        steel_elastic_modulus_kg_cm2=steel.elastic_modulus_kg_cm2)
    if hasattr(design, "flange_width_cm"):
        response = t_beam_flexural_response(**args, flange_width_cm=design.flange_width_cm,
            flange_thickness_cm=design.flange_thickness_cm, web_width_cm=design.web_width_cm)
    else:
        response = rectangular_flexural_response(**args,
            concrete_width_cm=getattr(design, "section_width_cm", 100.0))
    return min(design.flexural_resistance_factor, response.resistance_factor) * response.nominal_moment_tn_m


def refresh_main_option(option, design, materials, parameters):
    capacity = flexural_capacity(design, option.provided_area_cm2, materials.concrete, materials.steel)
    compliant = (
        option.provided_area_cm2 + 1e-9 >= design.required_area_cm2
        and capacity + 1e-9 >= max(design.design_moment_tn_m, design.minimum_capacity_moment_tn_m)
        and option.layers <= parameters.maximum_main_bar_layers
        and option.clear_spacing_cm + 1e-9 >= parameters.minimum_clear_bar_spacing_cm
    )
    return replace(option, required_area_cm2=design.required_area_cm2, is_compliant=compliant)


def refresh_spacing_option(option, case):
    compliant = (
        option.provided_area_cm2_m + 1e-9 >= case.required_area_cm2_m
        and case.minimum_spacing_m - 1e-9 <= option.spacing_m <= case.maximum_spacing_m + 1e-9
    )
    return replace(option, required_area_cm2_m=case.required_area_cm2_m, is_compliant=compliant)


def refresh_stirrup_option(option, shear):
    """Recheck the same stirrup, including failures, without invoking a selector."""
    provided = option.legs * option.bar_area_cm2 / option.spacing_m
    vs = provided / 100 * shear.steel_yield_kg_cm2 / 1000 * shear.effective_shear_depth_cm
    capacity = shear.phi * min(shear.vc_tn + vs, shear.nominal_shear_limit_tn)
    compliant = (provided + 1e-9 >= shear.required_av_cm2_m
        and option.spacing_m <= shear.maximum_spacing_m + 1e-9
        and capacity + 1e-9 >= shear.controlling_shear.combined_shear_tn)
    return replace(option, required_av_cm2_m=shear.required_av_cm2_m,
        provided_av_cm2_m=provided, phi_vn_tn=capacity, is_compliant=compliant)


def _adopt_skin(skin, parameters, extreme_depth, required_area, *, maximum_spacing_m=None):
    required, uncapped, height, total, maximum, spacing = _skin_reinforcement_requirements(
        extreme_tension_depth_cm=extreme_depth, required_flexural_area_cm2=required_area,
        configured_maximum_spacing_m=(parameters.maximum_skin_spacing_m
            if maximum_spacing_m is None else maximum_spacing_m),
    )
    return replace(skin, effective_depth_cm=extreme_depth, distribution_height_m=height,
        uncapped_required_area_cm2_m_per_face=uncapped, maximum_total_area_cm2_per_face=maximum,
        required_total_area_cm2_per_face=total, required_area_cm2_m_per_face=required,
        maximum_spacing_m=spacing, spacing_options=generate_spacing_options(
            skin.spacing_options.label, required, SpacingGrid(step_m=parameters.spacing_step_m,
                minimum_m=parameters.minimum_spacing_m, maximum_m=spacing)))


def adopt_girder_reinforcement(geometry, materials, reinforcement, option):
    if option is None:
        return reinforcement
    main = flexural_design_for_option(reinforcement.main, option, materials.concrete, materials.steel)
    extreme = geometry.total_t_section_depth_m * 100 - reinforcement.parameters.concrete_cover_cm - option.bar_diameter_cm / 2
    skin = _adopt_skin(reinforcement.skin, reinforcement.parameters, extreme, main.required_area_cm2)
    return replace(reinforcement, main=main, skin=skin)


def refresh_girder_selection(selected, reinforcement, shear, materials):
    result = []
    for label, option in selected:
        if label.startswith("A."):
            option = refresh_main_option(option, reinforcement.main, materials, reinforcement.parameters)
        elif label.startswith("D."):
            option = refresh_stirrup_option(option, shear)
        else:
            case = reinforcement.temperature if label.startswith("B.") else reinforcement.skin
            option = refresh_spacing_option(option, case.spacing_options)
        result.append((label, option))
    return tuple(result)


def adopt_slab_reinforcement(geometry, materials, reinforcement, selected):
    from bridge_design.domain.reinforcement import _design_distribution_steel, _spacing_grid
    choices = {label[:2]: option for label, option in selected}
    negative = flexural_design_for_option(reinforcement.negative, choices.get("A."), materials.concrete, materials.steel)
    positive = flexural_design_for_option(reinforcement.positive, choices.get("B."), materials.concrete, materials.steel)
    distribution = _design_distribution_steel(geometry, positive, _spacing_grid(reinforcement.parameters))
    reinforcement = replace(reinforcement, negative=negative, positive=positive, distribution=distribution)
    cases = {"A.": negative, "B.": positive, "C.": reinforcement.temperature, "D.": distribution}
    result = []
    for label, option in selected:
        design = cases[label[:2]]
        case = replace(design.spacing_options, required_area_cm2_m=design.required_area_cm2_m)
        option = refresh_spacing_option(option, case)
        if label[:2] in ("A.", "B."):
            capacity = flexural_capacity(design, option.provided_area_cm2_m, materials.concrete, materials.steel)
            target = max(design.design_moment_tn_m, design.minimum_capacity_moment_tn_m) / design.strip_length_m
            option = replace(option, is_compliant=option.is_compliant and capacity + 1e-9 >= target)
        result.append((label, option))
    return reinforcement, tuple(result)


def adopt_cantilever_reinforcement(geometry, materials, result, selected):
    """Refresh the overhang and all its reviews, preserving the chosen bars."""
    from bridge_design.domain._cantilever_slab_calculations import design_development
    from bridge_design.domain._cantilever_slab_checks import design_shear, review_crack_control

    choices = {label[:2]: option for label, option in selected}
    flexural = flexural_design_for_option(result.flexural_steel, choices["A."],
                                         materials.concrete, materials.steel)
    updated = []
    for label, option in selected:
        design = flexural if label.startswith("A.") else result.temperature_steel
        option = refresh_spacing_option(option, design.spacing_options)
        if label.startswith("A."):
            capacity = flexural_capacity(flexural, option.provided_area_cm2_m,
                                        materials.concrete, materials.steel)
            target = flexural.minimum_capacity_moment_tn_m / flexural.strip_length_m
            option = replace(option, is_compliant=option.is_compliant and capacity + 1e-9 >= target)
        updated.append((label, option))
    selected = tuple(updated)
    principal = next(option for label, option in selected if label.startswith("A."))
    shear = design_shear(geometry, materials,
        replace(result.parameters, main_bar_diameter_cm=principal.bar.diameter_cm), result.load_effects)
    crack = review_crack_control(geometry, materials, result.parameters, result.combinations, flexural, principal)
    development = design_development(geometry, materials, result.parameters, flexural, principal)
    return replace(result, flexural_steel=flexural, shear=shear,
                   crack_control=crack, development=development), selected


def adopt_diaphragm_reinforcement(geometry, materials, analysis, reinforcement, selected):
    from bridge_design.domain.diaphragm import _design_diaphragm_shear
    choices = {label[:2]: option for label, option in selected}
    negative = flexural_design_for_option(reinforcement.negative, choices.get("A."), materials.concrete, materials.steel)
    positive = flexural_design_for_option(reinforcement.positive, choices.get("B."), materials.concrete, materials.steel)
    # Both bending directions can govern; use the smaller adopted depth for shear.
    governing = min((negative, positive), key=lambda design: design.effective_depth_cm)
    shear = _design_diaphragm_shear(geometry, materials, analysis, reinforcement.parameters, governing)
    bars = [choices[key].bar_diameter_cm for key in ("A.", "B.") if key in choices]
    extreme = geometry.total_depth_m * 100 - reinforcement.parameters.concrete_cover_cm - min(bars or [reinforcement.parameters.main_bar_diameter_cm]) / 2
    skin = _adopt_skin(reinforcement.skin, reinforcement.parameters, extreme,
                      max(negative.required_area_cm2, positive.required_area_cm2),
                      maximum_spacing_m=reinforcement.parameters.maximum_spacing_m)
    reinforcement = replace(reinforcement, negative=negative, positive=positive, shear=shear, skin=skin)
    result = []
    for label, option in selected:
        if label[:2] in ("A.", "B."):
            option = refresh_main_option(option, negative if label.startswith("A.") else positive,
                                         materials, reinforcement.parameters)
        elif label.startswith("D."):
            option = refresh_stirrup_option(option, shear)
        else:
            case = reinforcement.temperature if label.startswith("C.") else skin
            option = refresh_spacing_option(option, case.spacing_options)
        result.append((label, option))
    return reinforcement, tuple(result)
