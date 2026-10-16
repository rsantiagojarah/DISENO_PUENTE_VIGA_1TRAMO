"""Common design families with independently traceable governing members."""

from dataclasses import dataclass, replace
from math import inf, isclose

from bridge_design.domain.common_reinforcement import common_girder_detail


def ratio(demand, capacity):
    return demand / capacity if capacity > 0 else (inf if demand > 0 else 0.0)


def crack_ratio(check):
    return max(ratio(check.provided_spacing_m, check.maximum_spacing_m),
               ratio(check.steel_stress_kg_cm2, check.steel_stress_limit_kg_cm2))


def girder_checks(member):
    """Each demand/limit pair remains from one physical member."""
    selected = dict((label[:2], option) for label, option in member.selected)
    main, stirrup = selected['A.'], selected['D.']
    from bridge_design.domain.adopted_reinforcement import refresh_stirrup_option, flexural_capacity
    capacity = refresh_stirrup_option(stirrup, member.shear).phi_vn_tn
    materials = member.project_inputs.materials
    main_capacity = flexural_capacity(member.reinforcement.main, main.provided_area_cm2,
                                     materials.concrete, materials.steel)
    c, s, f = member.crack.main, member.service, member.fatigue
    return (
        ('Flexion', member.reinforcement.main.required_area_cm2, main.provided_area_cm2, 'cm2'),
        ('Cortante', member.shear.controlling_shear.combined_shear_tn, capacity, 'Tn'),
        ('Fisuracion: separacion', c.provided_spacing_m, c.maximum_spacing_m, 'm'),
        ('Fisuracion: tension', c.steel_stress_kg_cm2, c.steel_stress_limit_kg_cm2, 'kg/cm2'),
        ('Servicio: concreto', s.concrete_compression_kg_cm2, s.concrete_compression_limit_kg_cm2, 'kg/cm2'),
        ('Servicio: acero', s.steel_tension_kg_cm2, s.steel_tension_limit_kg_cm2, 'kg/cm2'),
        ('Fatiga', f.factored_stress_range_kg_cm2, f.allowable_stress_range_kg_cm2, 'kg/cm2'),
        ('Temperatura', member.reinforcement.temperature.required_area_cm2_m_per_face,
         selected['B.'].provided_area_cm2_m, 'cm2/m'),
        ('Piel', member.reinforcement.skin.required_area_cm2_m_per_face,
         selected['C.'].provided_area_cm2_m, 'cm2/m'),
        ('Estribos: separacion', stirrup.spacing_m, member.shear.maximum_spacing_m, 'm'),
        ('Estribos: cuantia', member.shear.required_av_cm2_m, stirrup.provided_av_cm2_m, 'cm2/m'),
        ('Flexion: capacidad', max(member.reinforcement.main.design_moment_tn_m,
            member.reinforcement.main.minimum_capacity_moment_tn_m), main_capacity, 'Tn.m'),
        ('Piel: separacion', selected['C.'].spacing_m, member.reinforcement.skin.maximum_spacing_m, 'm'),
    )


def governing_rows(members, checks, label):
    rows = []
    for index in range(len(checks(members[0]))):
        governing = max(members, key=lambda m: ratio(*checks(m)[index][1:3]))
        name, demand, limit, unit = checks(governing)[index]
        maximum = ratio(demand, limit)
        ties = [m for m in members if isclose(ratio(*checks(m)[index][1:3]), maximum, rel_tol=1e-10, abs_tol=1e-12)]
        rows.append((name, '; '.join(label(m) for m in ties), f'{demand:.3f}', f'{limit:.3f}', unit,
                     'OK' if demand <= limit + 1e-9 else 'NO CUMPLE'))
    return tuple(rows)


@dataclass(frozen=True)
class GirderDesignFamily:
    members: tuple
    reinforcement: object
    selected: tuple
    detail: object

    @property
    def exterior(self):
        return self.members[0].exterior

    @property
    def indices(self):
        return tuple(sorted(i for m in self.members for i in m.indices))

    @property
    def label(self):
        return ', '.join(f'V{i+1}' for i in self.indices)

    @property
    def title(self):
        return ('Vigas exteriores' if self.exterior else 'Vigas interiores') + ' — ' + self.label

    @property
    def basis(self):
        return max(self.members, key=lambda m: (m.reinforcement.main.required_area_cm2,
                                               m.reinforcement.main.design_moment_tn_m))

    @property
    def shear_member(self):
        return max(self.members, key=lambda m: ratio(*girder_checks(m)[1][1:3]))

    @property
    def service_members(self):
        concrete = max(self.members, key=lambda m: ratio(*girder_checks(m)[4][1:3]))
        steel = max(self.members, key=lambda m: ratio(*girder_checks(m)[5][1:3]))
        return (concrete,) if concrete is steel else (concrete, steel)

    @property
    def status(self):
        ok = all(r[-1] == 'OK' for r in self.checks)
        ok = ok and all(option.is_compliant for m in self.members for _, option in m.selected)
        ok = ok and all(s.status == 'OK' for s in self.detail.envelope)
        ok = ok and all(z.status == 'OK' for z in self.detail.stirrup_zones)
        return 'OK' if ok else 'NO CUMPLE'

    @property
    def checks(self):
        return governing_rows(self.members, girder_checks, lambda m: m.label)

    @property
    def individual_rows(self):
        rows = []
        for m in self.members:
            status = 'OK' if (all(r[1] <= r[2]+1e-9 for r in girder_checks(m))
                and all(option.is_compliant for _, option in m.selected)) else 'NO CUMPLE'
            for index in m.indices:
                rows.append((f'V{index+1}', f'{m.reinforcement.main.design_moment_tn_m:.3f}',
                    f'{m.shear.controlling_shear.combined_shear_tn:.3f}',
                    f'{m.reinforcement.main.required_area_cm2:.3f}', status))
        return tuple(sorted(rows, key=lambda r: int(r[0][1:])))

    def report_context(self, data):
        context = self.basis.report_context(data)
        prefix = 'exterior' if self.exterior else 'interior'
        crack = max(self.members, key=lambda m: crack_ratio(m.crack.main))
        fatigue = max(self.members, key=lambda m: ratio(*girder_checks(m)[6][1:3]))
        return replace(context, active_girder_family=self, **{
            prefix+'_reinforcement': self.reinforcement, prefix+'_selected': self.selected,
            prefix+'_detail': self.detail, prefix+'_shear': self.shear_member.shear,
            prefix+'_crack': crack.crack, prefix+'_fatigue': fatigue.fatigue,
            prefix+'_service': self.service_members[0].service})


def make_girder_family(members, reinforcement, selected):
    members = tuple(members)
    from bridge_design.domain.common_reinforcement import common_girder_reinforcement
    reinforcement = common_girder_reinforcement(m.reinforcement for m in members)
    refreshed = []
    for label, option in selected:
        matches = [next(o for name, o in m.selected if name[:2] == label[:2]) for m in members]
        changes = dict(is_compliant=all(o.is_compliant for o in matches))
        if label.startswith('A.'):
            changes['required_area_cm2'] = max(o.required_area_cm2 for o in matches)
        elif label.startswith('D.'):
            changes.update(required_av_cm2_m=max(o.required_av_cm2_m for o in matches),
                           phi_vn_tn=min(o.phi_vn_tn for o in matches))
        else:
            changes['required_area_cm2_m'] = max(o.required_area_cm2_m for o in matches)
        refreshed.append((label, replace(option, **changes)))
    selected = tuple(refreshed)
    label = 'Armado comun de vigas ' + ('exteriores' if members[0].exterior else 'interiores')
    detail = common_girder_detail(members, label)
    choices = {name[:2]: option for name, option in selected}
    detail = replace(detail, selected_main_bar=choices['A.'], selected_stirrup=choices['D.'])
    return GirderDesignFamily(members, reinforcement, selected, detail)


def cantilever_checks(member):
    selected = dict((label[:2], option) for label, option in member.selected)
    r, c = member.result, member.crack
    from bridge_design.domain.adopted_reinforcement import flexural_capacity
    materials = member.project_inputs.materials
    capacity = flexural_capacity(r.flexural_steel, selected['A.'].provided_area_cm2_m,
                                materials.concrete, materials.steel)
    return (
        ('Flexion', r.flexural_steel.required_area_cm2_m, selected['A.'].provided_area_cm2_m, 'cm2/m'),
        ('Temperatura', r.temperature_steel.required_area_cm2_m, selected['B.'].provided_area_cm2_m, 'cm2/m'),
        ('Cortante', r.shear.combined_shear_tn, r.shear.phi_vc_tn, 'Tn/m'),
        ('Fisuracion: separacion', c.provided_spacing_m, c.maximum_spacing_m, 'm'),
        ('Fisuracion: tension', c.steel_stress_kg_cm2, c.steel_stress_limit_kg_cm2, 'kg/cm2'),
        ('Flexion: capacidad', r.flexural_steel.minimum_capacity_moment_tn_m / r.flexural_steel.strip_length_m,
         capacity, 'Tn.m/m'),
        ('Principal: separacion', selected['A.'].spacing_m, r.flexural_steel.spacing_options.maximum_spacing_m, 'm'),
        ('Temperatura: separacion', selected['B.'].spacing_m, r.temperature_steel.spacing_options.maximum_spacing_m, 'm'),
    )


@dataclass(frozen=True)
class CantileverDesignFamily:
    members: tuple
    reinforcement: object
    selected: tuple

    @property
    def basis(self):
        return max(self.members, key=lambda m: (m.result.flexural_steel.required_area_cm2_m,
                                               m.result.flexural_steel.design_moment_tn_m))

    @property
    def development(self):
        """Common projection and anchorage cover both independently checked sides."""
        base = max(self.members, key=lambda m: m.development.required_development_length_cm).development
        projection = max(m.development.exterior_projection_length_m for m in self.members)
        anchorage = max(m.development.interior_anchor_length_m for m in self.members)
        return replace(base, exterior_projection_length_m=projection, interior_anchor_length_m=anchorage,
                       total_additional_bar_length_m=projection+anchorage)

    @property
    def checks(self):
        return governing_rows(self.members, cantilever_checks, lambda m: 'Volado '+m.side)

    @property
    def status(self):
        return 'OK' if (all(r[-1] == 'OK' for r in self.checks)
                        and all(option.is_compliant for _, option in self.selected)) else 'NO CUMPLE'

    @property
    def individual_rows(self):
        return tuple(('Volado '+m.side, f'{m.result.controlling_strength.design_moment_tn_m:.3f}',
            f'{m.result.shear.combined_shear_tn:.3f}', f'{m.result.flexural_steel.required_area_cm2_m:.3f}',
            'OK' if (all(r[1] <= r[2]+1e-9 for r in cantilever_checks(m))
                     and all(option.is_compliant for _, option in m.selected)) else 'NO CUMPLE') for m in self.members)

    def report_context(self, data):
        context = self.basis.report_context(data)
        shear = max(self.members, key=lambda m: ratio(*cantilever_checks(m)[2][1:3]))
        crack = max(self.members, key=lambda m: crack_ratio(m.crack))
        return replace(context, active_cantilever_family=self, cantilever_result=replace(
            self.reinforcement, shear=shear.result.shear), cantilever_selected=self.selected,
            cantilever_crack=crack.crack, cantilever_development=self.development)
