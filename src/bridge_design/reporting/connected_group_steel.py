"""Check the adopted reinforcement against each combination family separately."""

from bridge_design.domain.connected_reinforcement import region_inputs
from bridge_design.domain.connected_distributions import reinforcement_demands
from bridge_design.domain.connected_section_checks import section_check
from bridge_design.domain.rebar_catalog import reinforcing_bar_by_label
from bridge_design.reporting.connected_case_groups import combination_groups, case_label
from bridge_design.reporting.deck_docx import _body, _add_native_equation


def grouped_steel_checks(result, names):
    demands = reinforcement_demands(result.inputs,result.mesh,[r for r in result.results if r.name in names])
    controls = []
    for steel in result.reinforcement:
        if steel.role != "primary":
            continue
        inputs, cover, _length = region_inputs(result.inputs,steel.region)
        rows = [section_check(d, inputs, cover, reinforcing_bar_by_label(steel.bar_label),steel.spacing_m)
                for d in demands[steel.region]]
        strength = [r for r in rows if r['demand']['limit_state'] != 'service']
        services = [r for r in rows if r['demand']['limit_state'] == 'service']
        controls.append((steel,
                         max(strength,key=lambda r:r['flexure_ratio']) if strength else None,
                         max(strength,key=lambda r:r['shear_ratio']) if strength else None,
                         max(services,key=lambda r:r['crack_ratio']) if services else None))
    return controls


def write_group_steel(document,result):
    groups = combination_groups(result)
    _body(document,"Se verifica la armadura adoptada frente a cada familia de combinación por separado. "
          "Los controles de flexión y cortante conservan cada uno su sección y sus esfuerzos simultáneos; "
          "Servicio I comprueba fisuración y tensión del acero. No se rediseña una armadura distinta para cada familia.")
    for index, group in enumerate(groups,1):
        document.add_heading(f"8.{index}. Verificación de la envolvente {group.name}",level=2)
        _body(document,"Casos incluidos: "+"; ".join(case_label(n) for n in group.cases)+".")
        _add_native_equation(document,"eta_s = max(fs/fs_lim, s/s_max)" if group.limit_state=='service' else
                             "eta_M = Md/Mr; eta_V = abs(V)/Vr")
        _body(document,"Los índices deben ser menores o iguales a 1. Las expresiones de resistencia, "
              "peralte y fisuración se desarrollan en el diseño final por región.")
        for steel, flexure, shear, service in grouped_steel_checks(result,group.cases):
            _body(document,f"{steel.region}: {steel.bar_label} @ {steel.spacing_m:.3f} m por cara; "
                  f"As={steel.area_per_face_cm2_m:.5f} cm²/m.")
            for label, row in (("Flexión",flexure),("Cortante",shear),("Servicio",service)):
                if row is None:
                    continue
                demand=row['demand']
                if label=='Flexión':
                    ratio=row['flexure_ratio']
                    text=f"Md/Mr={row['required_moment']:.5f}/{row['capacity']:.5f}={ratio:.5f}"
                elif label=='Cortante':
                    ratio=row['shear_ratio']
                    text=f"|V|/Vr={abs(demand['shear']):.5f}/{row['shear_capacity']:.5f}={ratio:.5f}"
                else:
                    ratio=row['crack_ratio']
                    text=(f"fs/fs_lim={row['stress']:.5f}/{row['stress_limit']:.5f}={row['stress_ratio']:.5f}; "
                          f"s/smax={steel.spacing_m:.5f}/{row['maximum_spacing']:.5f}={row['spacing_ratio']:.5f}; "
                          f"índice={ratio:.5f}")
                _body(document,f"{label}: {case_label(demand['case'])}; elemento {demand['element']}; "
                      f"s/L={demand['station']:.5f}; h={demand['depth_cm']:.3f} cm; "
                      f"M={demand['moment']:.5f} tn·m; V={demand['shear']:.5f} tn. "
                      f"{text}: {'CUMPLE' if ratio<=1+1e-8 else 'NO CUMPLE'}.")
    return len(groups)
