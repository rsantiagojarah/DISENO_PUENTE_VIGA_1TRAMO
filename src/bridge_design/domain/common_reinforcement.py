"""Common reinforcement checked against every independently analysed member."""

from dataclasses import replace

from bridge_design.domain.interior_girder import (
    custom_main_bar_placement_option, custom_shear_stirrup_option,
)
from bridge_design.domain.rebar_catalog import (
    SpacingGrid, custom_spacing_option, _spacing_option_for_bar, _recommended_option,
)


def common_spacing(cases):
    cases = tuple(cases)
    if all(case == cases[0] for case in cases):
        return cases[0]
    grid = SpacingGrid(minimum_m=max(case.minimum_spacing_m for case in cases),
                       maximum_m=min(case.maximum_spacing_m for case in cases))
    # Keep diameter-specific demands when intersecting the two overhangs.
    options = tuple(_spacing_option_for_bar(
        original.item, original.bar,
        max(next(o.required_area_cm2_m for o in case.options if o.bar == original.bar)
            for case in cases), grid,
    ) for original in cases[0].options)
    options = tuple(replace(option, is_compliant=option.is_compliant and all(
        next(o.is_compliant for o in case.options if o.bar == option.bar) for case in cases
    )) for option in options)
    recommended = _recommended_option(options, grid)
    return replace(cases[0], required_area_cm2_m=max(case.required_area_cm2_m for case in cases),
        options=tuple(replace(o, is_recommended=recommended is not None and o.item == recommended.item)
                      for o in options), minimum_spacing_m=grid.minimum_m, maximum_spacing_m=grid.maximum_m)


def common_girder_reinforcement(designs):
    """Intersect admissible placements; retain actual governing design sections."""
    designs = tuple(designs)
    base = max(designs, key=lambda d: (d.main.required_area_cm2, d.main.design_moment_tn_m))
    catalogs = [{(o.bar_label, o.bar_count): o for o in d.main.placement_options.options}
                for d in designs]
    options = []
    for option in base.main.placement_options.options:
        matches = [catalog.get((option.bar_label, option.bar_count)) for catalog in catalogs]
        if any(o is None for o in matches):
            continue
        options.append(replace(option,
            required_area_cm2=max(o.required_area_cm2 for o in matches),
            is_compliant=all(o.is_compliant for o in matches), is_recommended=False))
    admissible = [o for o in options if o.is_compliant]
    preferred = base.main.placement_options.recommended
    recommended = next((o for o in admissible if preferred is not None and o.item == preferred.item), None)
    if recommended is None and admissible:
        recommended = min(admissible, key=lambda o: (o.provided_area_cm2, o.layers, o.bar_count))
    case = replace(base.main.placement_options,
        required_area_cm2=recommended.required_area_cm2 if recommended else base.main.placement_options.required_area_cm2,
        options=tuple(
            replace(o, is_recommended=recommended is not None and o.item == recommended.item) for o in options))
    temperature = max(designs, key=lambda d: d.temperature.required_area_cm2_m_per_face).temperature
    skin = max(designs, key=lambda d: d.skin.required_area_cm2_m_per_face).skin
    return replace(base, main=replace(base.main, placement_options=case),
        temperature=replace(temperature, spacing_options=common_spacing(d.temperature.spacing_options for d in designs)),
        skin=replace(skin, spacing_options=common_spacing(d.skin.spacing_options for d in designs)))


def common_girder_shear(designs):
    """Offer only stirrups that satisfy every member, including spacing limits."""
    designs = tuple(designs)
    base = max(designs, key=lambda d: d.required_av_cm2_m)
    if all(d == base for d in designs):
        return base
    options = []
    seen = set()
    for design in (base, *designs):
        for option in design.options:
            key = (option.bar_label, option.legs, option.spacing_m)
            if key in seen:
                continue
            seen.add(key)
            try:
                checks = [custom_shear_stirrup_option(d, *key) for d in designs]
            except ValueError:
                continue
            options.append(replace(option, item=len(options)+1, is_compliant=True,
                required_av_cm2_m=max(d.required_av_cm2_m for d in designs),
                phi_vn_tn=min(c.phi_vn_tn for c in checks), is_recommended=False))
    if not options:
        raise ValueError("No hay estribos comunes admisibles para todas las vigas de la familia.")
    preferred = base.recommended
    recommended = next((o for o in options if preferred is not None and
        (o.bar_label, o.legs, o.spacing_m) == (preferred.bar_label, preferred.legs, preferred.spacing_m)), None)
    if recommended is None:
        recommended = min(options, key=lambda o: (o.provided_av_cm2_m, o.bar_area_cm2))
    return replace(base, required_av_cm2_m=max(d.required_av_cm2_m for d in designs),
        maximum_spacing_m=min(d.maximum_spacing_m for d in designs),
        options=tuple(replace(o, is_recommended=o.item == recommended.item) for o in options))


def validate_girder_selection(selected, reinforcement, shear):
    """Reject a common selection unless it fits this member's own checks."""
    for label, option in selected:
        if label.startswith("A."):
            custom_main_bar_placement_option(reinforcement.main.placement_options, option.bar_label, option.bar_count)
        elif label.startswith("D."):
            custom_shear_stirrup_option(shear, option.bar_label, option.legs, option.spacing_m)
        else:
            case = reinforcement.temperature if label.startswith("B.") else reinforcement.skin
            custom_spacing_option(case.spacing_options, option.bar.label, option.spacing_m)


def common_cantilever_reinforcement(results):
    results = tuple(results)
    base = max(results, key=lambda r: (r.flexural_steel.required_area_cm2_m, r.flexural_steel.design_moment_tn_m))
    temperature = max(results, key=lambda r: r.temperature_steel.required_area_cm2_m).temperature_steel
    return replace(base,
        flexural_steel=replace(base.flexural_steel,
            spacing_options=common_spacing(r.flexural_steel.spacing_options for r in results)),
        temperature_steel=replace(temperature,
            spacing_options=common_spacing(r.temperature_steel.spacing_options for r in results)))


def validate_cantilever_selection(selected, result):
    for label, option in selected:
        case = result.flexural_steel if label.startswith("A.") else result.temperature_steel
        custom_spacing_option(case.spacing_options, option.bar.label, option.spacing_m)


def common_girder_detail(members, label):
    """Envelope required steel at every station, then derive shared bar cuts."""
    from bridge_design.domain.girder_detailing import (
        _continuous_bar_count, _longitudinal_cut_details, _girder_envelope,
    )
    details = [m.detail for m in members]
    base = details[0]
    def main_key(option):
        return (option.bar_label, option.bar_count, option.layers, option.bars_per_layer,
                option.effective_depth_cm, option.clear_spacing_cm)
    def stirrup_key(option):
        return option.bar_label, option.legs, option.spacing_m
    if any(d.span_length_m != base.span_length_m or
           main_key(d.selected_main_bar) != main_key(base.selected_main_bar) or
           stirrup_key(d.selected_stirrup) != stirrup_key(base.selected_stirrup) for d in details):
        raise ValueError("El detalle comun requiere igual luz y armado en toda la familia.")
    positions = sorted({s.x_m for d in details for s in d.envelope})
    envelopes = [_girder_envelope(
        m.project_inputs.exterior_girder if m.exterior else m.project_inputs.interior_girder,
        m.project_inputs.materials, m.result, m.reinforcement, base.selected_main_bar,
        getattr(m.result, "pl", None) is not None, positions=positions) for m in members]
    envelope = []
    for stations in zip(*envelopes):
        worst = max(stations, key=lambda s: s.required_area_cm2)
        envelope.append(replace(worst, mu_tn_m=max(s.mu_tn_m for s in stations),
                                vu_tn=max(s.vu_tn for s in stations)))
    envelope = tuple(envelope)
    continuous = _continuous_bar_count(envelope, base.selected_main_bar)
    development = max(d.development_length_m for d in details)
    cuts = _longitudinal_cut_details(label, base.span_length_m, envelope,
                                    base.selected_main_bar, continuous, development)
    zones = []
    for member_zones in zip(*(d.stirrup_zones for d in details)):
        if len({(z.start_m, z.end_m) for z in member_zones}) != 1:
            raise ValueError("Las zonas de estribos de la familia deben compartir limites.")
        governing = min(member_zones, key=lambda z: z.spacing_m)
        spacing = min(governing.spacing_m, base.selected_stirrup.spacing_m)
        provided = base.selected_stirrup.legs * base.selected_stirrup.bar_area_cm2 / spacing
        capacities = [m.shear.phi * min(m.shear.vc_tn + provided / 100 *
            m.shear.steel_yield_kg_cm2 / 1000 * m.shear.effective_shear_depth_cm,
            m.shear.nominal_shear_limit_tn) for m in members]
        demand = max(z.maximum_vu_tn for z in member_zones)
        required = max(z.required_av_cm2_m for z in member_zones)
        limit = min(z.maximum_spacing_m for z in member_zones)
        capacity = min(capacities)
        zones.append(replace(governing, spacing_m=spacing, maximum_vu_tn=demand,
            required_av_cm2_m=required, provided_av_cm2_m=provided, maximum_spacing_m=limit,
            phi_vn_tn=capacity, status="OK" if capacity+1e-9 >= demand and
            spacing <= limit+1e-9 and provided+1e-9 >= required else "NO CUMPLE"))
    return replace(base, label=label, continuous_bar_count=continuous,
        development_length_m=development, physical_cut_count=sum(c.physical_cut_count for c in cuts),
        envelope=envelope, longitudinal_cuts=cuts, stirrup_zones=tuple(zones))
