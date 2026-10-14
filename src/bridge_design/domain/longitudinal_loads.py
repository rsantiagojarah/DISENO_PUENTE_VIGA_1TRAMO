"""Physical girder load cases and equilibrium totals, without design envelopes."""
from dataclasses import replace

from bridge_design.domain.girder_tributaries import girder_load_groups
from bridge_design.domain.interior_girder import _solve_static_longitudinal_case
from bridge_design.domain import interior_girder, exterior_girder


def girder_reaction_cases(project, interior_result, exterior_result):
    """Return one analysis per equal-load group and its actual multiplicity.

    Moving-load factors remain those of its structural type. Static cases are
    assembled using each physical group's widths, never a design envelope.
    """
    groups = girder_load_groups(project)
    for group in groups:
        row = group[0]
        ext = row.exterior
        source = exterior_result if ext else interior_result
        primary_index = project.exterior_girder_index if ext else project.interior_girder_index
        if row.index == primary_index:
            analysis = source
        else:
            assigned = replace(project, **{'exterior_girder_index' if ext else 'interior_girder_index': row.index})
            geometry = assigned.exterior_girder if ext else assigned.interior_girder
            module = exterior_girder if ext else interior_girder
            m = project.materials
            dc = _solve_static_longitudinal_case(geometry, source.dc.name,
                module._dc_uniform_loads_tn_m(geometry, m), module._dc_point_loads_tn(geometry, m))
            dw = _solve_static_longitudinal_case(geometry, source.dw.name,
                (m.asphalt.specific_weight_tn_m3*m.asphalt.thickness_m*row.asphalt_m,), ())
            pl = _solve_static_longitudinal_case(geometry, 'PL - vereda tributaria',
                (project.live_loads.pedestrian.load_tn_m2*row.sidewalk_m,), ()) if ext or row.sidewalk_m else None
            analysis = replace(source, dc=dc, dw=dw, pl=pl)
        if project.transverse_slab.load_layout.pipe is not None:
            # Signed physical load for equilibrium, distinct from the conservative design case.
            m = project.materials
            geometry = project.exterior_girder if ext else project.interior_girder
            dw = _solve_static_longitudinal_case(geometry, 'DW - asfalto y tuberia, caso fisico',
                (m.asphalt.specific_weight_tn_m3*m.asphalt.thickness_m*row.asphalt_m
                 + project.girder_pipe_loads[row.index],), ())
            analysis = replace(analysis, dw=dw)
        label = 'Exterior' if ext else 'Interior'
        if sum(g[0].exterior == ext for g in groups) > 1:
            label += ' ' + ', '.join(r.label for r in group)
        yield label, len(group), analysis


def global_permanent_reactions(project, interior_result, exterior_result):
    totals = {key: [0.0, 0.0] for key in ('DC', 'DW', 'PL')}
    for _label, count, result in girder_reaction_cases(project, interior_result, exterior_result):
        for key in totals:
            case = getattr(result, key.lower(), None)
            if case is not None:
                for side, (_, value) in enumerate(case.support_reactions_tn):
                    totals[key][side] += count * value
    return {key: tuple(values) for key, values in totals.items()}
