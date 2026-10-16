"""Select reinforcement once per construction family, then check every member."""

from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO

from bridge_design.domain.common_reinforcement import (
    common_cantilever_reinforcement, common_girder_reinforcement, common_girder_shear,
    validate_cantilever_selection, validate_girder_selection,
)
from bridge_design.domain.girder_tributaries import girder_load_groups
from bridge_design.domain.interior_girder import require_admissible_main_placement
from bridge_design.domain.pipe_load import mirrored_layout
from bridge_design.reporting.models import CantileverReportGroup, GirderReportGroup
from bridge_design.reporting.common_design import CantileverDesignFamily, make_girder_family


def prepare_girder(api, project, exterior):
    prefix = 'exterior' if exterior else 'interior'
    geometry = getattr(project, prefix+'_girder')
    analysis = getattr(api, 'solve_'+prefix+'_girder_design')(geometry, project.materials, project.live_loads)
    steel = getattr(api, 'design_'+prefix+'_girder_reinforcement')(geometry, project.materials, analysis)
    require_admissible_main_placement(steel.main.placement_options)
    shear = getattr(api, 'design_'+prefix+'_girder_shear')(geometry, project.materials, analysis, steel)
    return analysis, steel, shear


def refresh_girder_for_main(api, project, exterior, values, main):
    """Rebuild dependent options at the explicitly selected main-bar centroid."""
    from bridge_design.domain.adopted_reinforcement import adopt_girder_reinforcement
    prefix = 'exterior' if exterior else 'interior'
    analysis, steel, _shear = values
    geometry = getattr(project, prefix+'_girder')
    steel = adopt_girder_reinforcement(geometry, project.materials, steel, main)
    shear = getattr(api, 'design_'+prefix+'_girder_shear')(geometry, project.materials, analysis, steel)
    return analysis, steel, shear


def run_girder_families(api, project):
    groups, families, primary = [], [], {}
    load_groups = girder_load_groups(project)
    for exterior in (False, True):
        prefix = 'exterior' if exterior else 'interior'
        prepared = []
        for load_group in load_groups:
            if load_group[0].exterior != exterior:
                continue
            member_project = replace(project, **{prefix+'_girder_index': load_group[0].index})
            prepared.append((tuple(row.index for row in load_group), member_project,
                             prepare_girder(api, member_project, exterior)))
        steel = common_girder_reinforcement(p[2][1] for p in prepared)
        recommended_main = require_admissible_main_placement(steel.main.placement_options)

        def refresh_for_main(main):
            nonlocal prepared
            refreshed = [
                (indices, member_project, refresh_girder_for_main(
                    api, member_project, exterior, values, main))
                for indices, member_project, values in prepared
            ]
            common_steel = common_girder_reinforcement(p[2][1] for p in refreshed)
            common_shear = common_girder_shear(p[2][2] for p in refreshed)
            prepared = refreshed
            return common_steel, common_shear

        # The first table uses the common default, not each member's own REC.
        steel, shear = refresh_for_main(recommended_main)
        print('\nARMADO COMUN DE VIGAS '+('EXTERIORES' if exterior else 'INTERIORES'))
        member_designs = tuple(
            (', '.join(f'V{index + 1}' for index in indices), values[1], values[2])
            for indices, _member_project, values in prepared
        )
        print(api.format_common_girder_reinforcement_options(steel, shear, member_designs))
        selected = getattr(api, 'collect_'+prefix+'_girder_reinforcement_selection')(
            steel, shear, refresh_for_main=refresh_for_main)
        # Also validate externally supplied selections against the adopted depth.
        refresh_for_main(next(o for label, o in selected if label.startswith('A.')))
        members = []
        for indices, member_project, values in prepared:
            validate_girder_selection(selected, values[1], values[2])
            with redirect_stdout(StringIO()):
                computed = getattr(api, '_run_'+prefix+'_girder')(
                    member_project, prepared=values, selected=selected)
            members.append(GirderReportGroup(indices, exterior, member_project, *computed[:8]))
            if getattr(project, prefix+'_girder_index') in indices:
                primary[prefix] = computed
        family = make_girder_family(members, steel, selected)
        print(api.format_girder_detailing_result(family.detail, 'ARMADO COMUN'))
        for row in family.individual_rows:
            print(f'{row[0]}: Mu={row[1]} Tn.m; Vu={row[2]} Tn; As req={row[3]} cm2; {row[4]}')
        for row in family.checks:
            print(f'{row[0]}: gobierna {row[1]}; {row[2]} / {row[3]} {row[4]}; {row[5]}')
        groups.extend(members)
        families.append(family)
    return tuple(groups), tuple(families), primary['interior'], primary['exterior']


def run_cantilever_family(api, project, barrier):
    layout = project.transverse_slab.load_layout
    right = replace(project, transverse_slab=replace(project.transverse_slab,
        load_layout=mirrored_layout(layout, project.transverse_slab.geometry.total_width_m)))
    prepared = []
    from bridge_design.reporting.deck_report_notes import cantilever_notes_for_side
    for side, member_project in (('izquierdo', project), ('derecho', right)):
        result = api.design_cantilever_slab(member_project.transverse_slab.geometry,
            member_project.materials, member_project.live_loads,
            member_project.transverse_slab.load_layout, barrier_result=barrier)
        result = replace(result, applicability_notes=cantilever_notes_for_side(result,
            member_project.transverse_slab.geometry, member_project.transverse_slab.load_layout, side))
        prepared.append((side, member_project, result))
    reinforcement = common_cantilever_reinforcement(p[2] for p in prepared)
    print('\nARMADO COMUN PARA AMBOS VOLADOS')
    member_designs = tuple(
        ('Volado '+side, result) for side, _member_project, result in prepared
    )
    print(api.format_common_cantilever_reinforcement_options(reinforcement, member_designs))
    selected = api.collect_cantilever_reinforcement_selection(reinforcement)
    members, computed_values = [], []
    for side, member_project, result in prepared:
        validate_cantilever_selection(selected, result)
        with redirect_stdout(StringIO()):
            computed = api._run_cantilever(member_project, barrier, prepared=result, selected=selected)
        members.append(CantileverReportGroup(side, member_project, *computed[:4]))
        computed_values.append(computed)
    reinforcement = common_cantilever_reinforcement(m.result for m in members)
    selected = tuple((label, replace(option,
        required_area_cm2_m=max(m.selected[i][1].required_area_cm2_m for m in members),
        is_compliant=all(m.selected[i][1].is_compliant for m in members)))
        for i, (label, option) in enumerate(selected))
    family = CantileverDesignFamily(tuple(members), reinforcement, selected)
    for row in family.individual_rows:
        print(f'{row[0]}: Mu={row[1]} Tn.m/m; Vu={row[2]} Tn/m; As req={row[3]} cm2/m; {row[4]}')
    for row in family.checks:
        print(f'{row[0]}: gobierna {row[1]}; {row[2]} / {row[3]} {row[4]}; {row[5]}')
    print(f'Longitud comun de barra adicional: {family.development.total_additional_bar_length_m:.3f} m')
    return tuple(members), family, computed_values[0]
