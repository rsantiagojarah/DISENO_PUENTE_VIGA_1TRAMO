"""Develop adopted-steel checks as formula, definitions, substitution and conclusion."""

from dataclasses import replace
from math import prod

from bridge_design.domain.abutment import DEFAULT_MAX_AGGREGATE_SIZE_IN, STEEL_ELASTIC_MODULUS_KG_CM2
from bridge_design.domain.concrete_flexure import mtc_beta1
from bridge_design.reporting.connected_report_details import mathematical_symbols
from bridge_design.reporting.connected_steel_trace import moment_demand_expression, steel_steps, status
from bridge_design.reporting.deck_docx import _body, _calc
from bridge_design.units.converters import kg_cm2_to_ksi


def write_block(document, step):
    start = len(document.paragraphs)
    _calc(document, *(mathematical_symbols(value) for value in (
        step.title, step.formula, step.legend, step.substitution,
        step.result, step.comment)), step.reference)
    # A long numerical development may continue across pages. Keep its title
    # and introductory prompts with their first line, without chaining all equations.
    for paragraph in document.paragraphs[start:]:
        if paragraph.style.name == 'Equation':
            paragraph.paragraph_format.keep_with_next = False


def developed_steps(steel, trace):
    """Use the actual audited results, with numerical operations shown explicitly."""
    f, v, service = (trace[key] for key in ('flexure', 'shear', 'service'))
    h, r, db, d = f['demand']['depth_cm'], f['cover'], f['diameter'], f['effective']
    fc, fy, area = trace['concrete'], trace['yield_strength'], f['area']
    response = f['response']
    c, a = response['neutral_axis_depth_cm'], response['compression_block_depth_cm']
    strain, stress = response['extreme_tensile_strain'], response['steel_stress_kg_cm2']
    mu = abs(f['demand']['moment'])
    substituted_demand = moment_demand_expression(f, f'{mu:.3f}', f'{f["cracking"]:.3f}')
    replacements = {
        'Peralte y acero de la seccion gobernante de flexion': dict(
            legend='h: espesor de la sección en cm; r: recubrimiento en cm; db: diámetro de barra en cm; '
                   'd: peralte efectivo en cm; Ab: área de una barra en cm²; s: separación en m; '
                   'As: área colocada por metro en cm²/m.',
            substitution=f'd = {h:.2f} - {r:.2f} - ({db:.2f}/2) = {d:.2f} cm\n'
                         f'As = {trace["bar_area"]:.3f}/{steel.spacing_m:.3f} = {area:.3f} cm²/m',
            result=f'd={d:.2f} cm; As proporcionado={area:.3f} cm²/m, con {steel.bar_label} cada {steel.spacing_m:.3f} m.'),
        'Momento minimo y demanda de capacidad': dict(
            formula='Mcr = 1.072*2.01*sqrt(fc)*b*h^2/(6*100000); '
                    f'Md = {moment_demand_expression(f)}; '
                    'As_req = max(As_flex, As_min, AsT)',
            legend='fc: resistencia del concreto en kgf/cm²; b: ancho de franja de 100 cm; '
                   'h: espesor en cm; Mu: momento último en tn·m/m; Mcr: momento de fisuración en tn·m/m; '
                   'As_flex: acero requerido por flexión; As_min: acero requerido por capacidad mínima; '
                   'AsT: mínimo por temperatura, todos en cm²/m.',
            substitution=f'Mcr = 1.072*2.01*sqrt({fc:.2f})*100*{h:.2f}^2/(6*100000) = {f["cracking"]:.3f} tn·m/m\n'
                         f'Md = {substituted_demand} = {f["required_moment"]:.3f} tn·m/m\n'
                         f'As_req = max({steel.flexural_as_cm2_m:.3f}, {steel.capacity_minimum_as_cm2_m:.3f}, '
                         f'{steel.temperature_cm2_m:.3f}) = {steel.required_as_cm2_m:.3f} cm²/m',
            result=f'Md={f["required_moment"]:.3f} tn·m/m. As requerido flexión y mínimos={steel.required_as_cm2_m:.3f} cm²/m.',
            comment='As_flex y As_min se obtienen invirtiendo el equilibrio y la compatibilidad de la sección rectangular '
                    'del bloque siguiente. Sus valores son los máximos de todas las secciones de la distribución; '
                    'pueden proceder de casos distintos.'),
        'Resistencia a flexion del acero elegido': dict(
            formula='a = beta1*c; eps_t = 0.003*(d-c)/c; fs = min(fy, Es*eps_t); '
                    '0.85*fc*b*a = As*fs; Mr = phi*As*fs*(d-a/2)/100000; eta_M = Md/Mr',
            legend='beta1: factor del bloque rectangular; c: profundidad del eje neutro en cm; '
                   'a: profundidad del bloque de compresión en cm; d: peralte efectivo en cm; '
                   'eps_t: deformación del acero en tracción; Es: módulo del acero de 2000000 kgf/cm²; '
                   'fc: resistencia del concreto en kgf/cm²; fy: fluencia del acero en kgf/cm²; '
                   'b: ancho de 100 cm; As: acero colocado en cm²/m; fs: tensión del acero en kgf/cm²; '
                   'phi: menor entre el límite del caso y el factor por deformación; '
                   'Mr: resistencia de diseño en tn·m/m; eta_M: índice de flexión, admisible hasta 1.',
            substitution=f'0.85*{fc:.2f}*100*({mtc_beta1(fc):.2f}*c) = {area:.3f}*min({fy:.2f}, 2000000*0.003*({d:.2f}-c)/c)\n'
                         f'c = {c:.2f} cm\n'
                         f'a = {mtc_beta1(fc):.2f}*{c:.2f} = {a:.2f} cm\n'
                         f'eps_t = 0.003*({d:.2f}-{c:.2f})/{c:.2f} = {strain:.6f}\n'
                         f'fs = min({fy:.2f}, 2000000*{strain:.6f}) = {stress:.2f} kgf/cm²\n'
                         f'phi = {f["phi"]:.2f}\n'
                         f'Mr = {f["phi"]:.2f}*{area:.3f}*{stress:.2f}*({d:.2f}-{a:.2f}/2)/100000 = {f["capacity"]:.3f} tn·m/m\n'
                         f'eta_M = {f["required_moment"]:.3f}/{f["capacity"]:.3f} = {f["flexure_ratio"]:.3f}',
            result=f'Md/Mr={f["flexure_ratio"]:.3f}: {status(f["flexure_ratio"])}.',
            comment='El eje neutro se obtiene resolviendo equilibrio y compatibilidad; '
                    'las operaciones conservan precisión completa y solo se redondea su presentación.'),
    }
    vh, vd, dv = v['demand']['depth_cm'], v['effective'], v['shear_depth']
    vm, vu = abs(v['demand']['moment']), abs(v['demand']['shear'])
    common_shear = (f'd = {vd:.2f} cm\n'
                    f'h = {vh:.2f} cm\n'
                    f'dv = max(0.9*{vd:.2f}, 0.72*{vh:.2f}) = {dv:.2f} cm\n')
    general = (f'Mv = max({vm:.3f}, {vu:.3f}*{dv:.2f}/100) = {v["shear_moment_used"]:.3f} tn·m/m\n'
               f'eps_s = max(0,1000*({v["shear_moment_used"]:.3f}/({dv:.2f}/100)+{vu:.3f}+0.5*{v["demand"]["axial"]:.3f})/(2000000*{v["area"]:.3f})) = {v["shear_strain"]:.6f}\n'
               f'sx = {dv:.2f}/2.54 = {v["spacing_x_in"]:.3f} in\n'
               f'sxe = min(80, max(12, {v["spacing_x_in"]:.3f}*1.38/(0.75+0.63))) = {v["spacing_xe_in"]:.3f} in\n'
               f'beta = 4.8*51/((1+750*{v["shear_strain"]:.6f})*(39+{v["spacing_xe_in"]:.3f})) = {v["beta"]:.3f}\n')
    resistance = (f'Vr = {trace["shear_phi"]:.2f}*0.265*{v["beta"]:.3f}*sqrt({fc:.2f})*100*{dv:.2f}/1000 = {v["shear_capacity"]:.3f} tn/m\n'
                  f'eta_V = {vu:.3f}/{v["shear_capacity"]:.3f} = {v["shear_ratio"]:.3f}')
    for title in ('Cortante y procedimiento general beta', 'Cortante y procedimiento simplificado'):
        simplified = title.endswith('simplificado')
        replacements[title] = dict(
            formula=('dv = max(0.9*d,0.72*h); beta = 2; '
                     'Vr = phi_v*0.265*beta*sqrt(fc)*100*dv/1000; eta_V = abs(V)/Vr' if simplified else
                     'dv = max(0.9*d,0.72*h); Mv = max(abs(M),abs(V)*dv/100); '
                     'eps_s = max(0,1000*(Mv/(dv/100)+abs(V)+0.5*N)/(Es*As)); '
                     'sx = dv/2.54; sxe = min(80,max(12,sx*1.38/(0.75+0.63))); '
                     'beta = 4.8*51/((1+750*eps_s)*(39+sxe)); '
                     'Vr = phi_v*0.265*beta*sqrt(fc)*100*dv/1000; eta_V = abs(V)/Vr'),
            legend=('d: peralte efectivo en cm; h: espesor en cm; dv: peralte efectivo de cortante en cm; '
                    'V: cortante simultáneo en tn/m; beta: factor de resistencia igual a 2; '
                    'phi_v: factor de resistencia al cortante; fc: resistencia del concreto en kgf/cm²; '
                    'Vr: resistencia al cortante en tn/m; eta_V: índice de cortante, admisible hasta 1.' if simplified else
                   'd: peralte efectivo en cm; h: espesor en cm; dv: peralte efectivo de cortante en cm; '
                   'M: momento simultáneo en tn·m/m; V: cortante simultáneo en tn/m; '
                   'Mv: momento utilizado para el cortante en tn·m/m; As: acero colocado en cm²/m; '
                   'Es: módulo del acero de 2000000 kgf/cm²; eps_s: deformación longitudinal; '
                   'sx y sxe: parámetros de espaciamiento en pulgadas; beta: factor de resistencia del concreto; '
                   'phi_v: factor de resistencia al cortante; fc: resistencia del concreto en kgf/cm²; '
                   'Vr: resistencia al cortante en tn/m; eta_V: índice de cortante, admisible hasta 1.'),
            substitution=common_shear + ('beta = 2.00\n' if simplified else general) + resistance,
            result=f'|Vu|/Vr={v["shear_ratio"]:.3f}: {status(v["shear_ratio"])}.',
            comment='El cortante usa su propia sección gobernante y el momento simultáneo de esa sección.')
    aggregate = DEFAULT_MAX_AGGREGATE_SIZE_IN
    modulus = STEEL_ELASTIC_MODULUS_KG_CM2
    comparison = '≤' if v['shear_ratio'] <= 1+1e-8 else '>'
    replacements['Cortante y procedimiento general beta'] = dict(
        title='Verificación de cortante',
        formula='Mu,usado = max(abs(Mu), abs(Vu)·dv/100); '
                'εs = max(0,1000·(Mu,usado/(dv/100)+abs(Vu)+0.5·Nu)/(Es·As,prov)); '
                'dv = max(0.9·d,0.72·h); sx = dv/2.54; '
                'sxe = min(80,max(12,sx·1.38/(ag+0.63))); '
                'β = (4.8/(1+750·εs))·(51/(39+sxe)); '
                "Vr = φv·0.265·β·√(f'c)·b·dv/1000",
        legend='Procedimiento general para secciones sin armadura de cortante; '
               'Nu: axial tn/m, positivo en tracción; Mu y Vu: esfuerzos simultáneos de la sección gobernante, en tn·m/m y tn/m; '
               'Mu,usado: momento empleado para calcular la deformación longitudinal; '
               'As,prov: acero principal colocado en cm²/m; εs: deformación longitudinal media; '
               'd y h: peralte efectivo y espesor total en cm; dv: peralte efectivo de cortante en cm; '
               'sx y sxe: espaciamiento de fisuras y valor efectivo en pulgadas; '
               f'ag: tamaño máximo del agregado adoptado de {aggregate:.2f} in (¾"); '
               f'Es: módulo del acero de {modulus:,.0f} kgf/cm²; b: ancho de franja de 100 cm; '
               "φv: factor de resistencia al cortante; f'c: resistencia del concreto en kgf/cm²",
        substitution=common_shear.replace('*', '·')+
            f'Mu = {vm:.3f} tn·m/m\n'
            f'Vu = {vu:.3f} tn/m\n'
            f'As,prov = {v["area"]:.3f} cm²/m\n'
            f'Mu,usado = max({vm:.3f}, {vu:.3f}·{dv/100:.3f}) = {v["shear_moment_used"]:.3f} tn·m/m\n'
            f'εs = max(0,1000·({v["shear_moment_used"]:.3f}/{dv/100:.3f}+{vu:.3f}+0.5·{v["demand"]["axial"]:.3f})/({modulus:.0f}·{v["area"]:.3f})) = {v["shear_strain"]:.6f}\n'
            f'sx = {v["spacing_x_in"]:.3f} in\n'
            f'ag = {aggregate:.2f} in\n'
            f'sxe = min(80,max(12,{v["spacing_x_in"]:.3f}·1.38/({aggregate:.2f}+0.63))) = {v["spacing_xe_in"]:.3f} in\n'
            f'β = (4.8/(1+750·{v["shear_strain"]:.6f}))·(51/(39+{v["spacing_xe_in"]:.3f})) = {v["beta"]:.6f}\n'
            f'Vr = {trace["shear_phi"]:.3f}·0.265·{v["beta"]:.6f}·√({fc:.1f})·100·{dv:.2f}/1000 = {v["shear_capacity"]:.3f} tn/m',
        result=f'Vu = {vu:.3f} tn/m {comparison} Vr = {v["shear_capacity"]:.3f} tn/m: '
               f'{status(v["shear_ratio"])}. Índice de cortante = {v["shear_ratio"]:.3f}.',
        comment='β se calcula con el acero principal adoptado (As,prov), porque la deformación longitudinal '
                'depende del refuerzo suministrado. Se utilizan N, M y V simultáneos '
                'de la sección gobernante de cortante.')
    if service is not None and service.get('service_tension', True):
        sd, sh, dc = service['effective'], service['demand']['depth_cm'], service['axis']
        sa, ms = service['area'], abs(service['demand']['moment'])
        replacements['Fisuracion y tension del acero en servicio'] = dict(
            formula='dc = r+db/2; d = h-dc; fs = abs(Ms)*100000/(As*0.90*d); fs_lim = 0.60*fy; '
                    'fs_usado = min(fs,fs_lim); beta_s = 1+dc/(0.7*(h-dc)); '
                    'smax = max(0,(123000/(beta_s*fs_usado*0.0980665)-20*dc)/1000); '
                    'eta_s = max(fs/fs_lim,s/smax)',
            legend='Ms: momento de Servicio I en tn·m/m; r: recubrimiento en cm; db: diámetro de barra en cm; '
                   'h: espesor en cm; dc: distancia del eje de barra a la cara en cm; d: peralte efectivo en cm; '
                   'As: acero elegido en cm²/m; fy: fluencia en kgf/cm²; fs: tensión del acero en kgf/cm²; '
                   'fs_lim: límite de tensión en kgf/cm²; fs_usado: tensión usada en la ecuación de separación; '
                   'beta_s: factor geométrico; s y smax: separaciones en m; '
                   'eta_s: mayor índice entre tensión y separación, admisible hasta 1.',
            substitution=f'dc = {service["cover"]:.2f}+{service["diameter"]:.2f}/2 = {dc:.2f} cm\n'
                         f'd = {sh:.2f}-{dc:.2f} = {sd:.2f} cm\n'
                         f'fs = {ms:.3f}*100000/({sa:.3f}*0.90*{sd:.2f}) = {service["stress"]:.2f} kgf/cm²\n'
                         f'fs_lim = 0.60*{fy:.2f} = {service["stress_limit"]:.2f} kgf/cm²\n'
                         f'fs_usado = min({service["stress"]:.2f},{service["stress_limit"]:.2f}) = {service["stress_used"]:.2f} kgf/cm²\n'
                         f'beta_s = 1+{dc:.2f}/(0.7*({sh:.2f}-{dc:.2f})) = {service["beta_service"]:.3f}\n'
                         f'smax = max(0,(123000/({service["beta_service"]:.3f}*{service["stress_used"]:.2f}*0.0980665)-20*{dc:.2f})/1000) = {service["maximum_spacing"]:.3f} m\n'
                         f'eta_s = max({service["stress"]:.2f}/{service["stress_limit"]:.2f},'
                         f'{steel.spacing_m:.3f}/{service["maximum_spacing"]:.3f}) = {service["crack_ratio"]:.3f}',
            result=f'Índice de servicio={service["crack_ratio"]:.3f}: {status(service["crack_ratio"])}.',
            comment='Se comprueba tanto la tensión calculada como la separación adoptada; '
                    'El índice de servicio combina fs/fs_lim y s/smax.')
    elif service is not None:
        replacements['Fisuracion sin traccion de servicio'] = dict(
            substitution=f'Ms = {service["demand"]["moment"]:.3f} tn·m/m\nfs = 0.00 kgf/cm²',
            result='No hay tracción por flexión de Servicio I: la separación por fisuración no gobierna.')
    db_in, fc_ksi, fy_ksi = db/2.54, kg_cm2_to_ksi(fc), kg_cm2_to_ksi(fy)
    factors = '*'.join(f'{factor:.2f}' for factor in trace['anchor_factors'])
    replacements['Desarrollo recto y gancho'] = dict(
        formula='db_in = db/2.54; fc_ksi = fc/70.306958; fy_ksi = fy/70.306958; '
                'ldb = 2.54*2.4*db_in*fy_ksi/sqrt(fc_ksi); '
                'ld = max(ldb*F,30.48); ldh = max(0.076*db*fy/sqrt(fc)*0.80,8*db,15.24); L_gancho = 16*db',
        legend='db: diámetro en cm; db_in: diámetro en pulgadas; fc y fy: resistencias en kgf/cm²; '
               'fc_ksi y fy_ksi: resistencias convertidas a ksi; ldb: longitud básica en cm; '
               'F: producto de factores de ubicación, revestimiento, concreto ligero y confinamiento; '
               'ld: longitud recta requerida en cm; ldh: longitud de desarrollo del gancho en cm; '
               'L_gancho: extensión recta del gancho en cm; L_disp: longitud recta disponible en cm.',
        substitution=f'db_in = {db:.2f}/2.54 = {db_in:.3f} in\n'
                     f'fc_ksi = {fc:.2f}/70.306958 = {fc_ksi:.3f} ksi\n'
                     f'fy_ksi = {fy:.2f}/70.306958 = {fy_ksi:.3f} ksi\n'
                     f'ldb = 2.54*2.4*{db_in:.3f}*{fy_ksi:.3f}/sqrt({fc_ksi:.3f}) = {trace["basic_anchor_cm"]:.2f} cm\n'
                     f'F = {factors} = {prod(trace["anchor_factors"]):.2f}\n'
                     f'ld = max({trace["basic_anchor_cm"]:.2f}*{prod(trace["anchor_factors"]):.2f},30.48) = {steel.required_straight_anchor_cm:.2f} cm\n'
                     f'ldh = max(0.076*{db:.2f}*{fy:.2f}/sqrt({fc:.2f})*0.80,8*{db:.2f},15.24) = {steel.required_hook_anchor_cm:.2f} cm\n'
                     f'L_gancho = 16*{db:.2f} = {steel.hook_extension_cm:.2f} cm',
        result=(f'ld recto={steel.required_straight_anchor_cm:.2f} cm; '
                f'ld gancho={steel.required_hook_anchor_cm:.2f} cm; L_disp={steel.available_anchor_cm:.2f} cm: '
                f'{steel.anchor_status}.'
                if steel.available_anchor_cm is not None else f'ld recto={steel.required_straight_anchor_cm:.2f} cm; ld gancho={steel.required_hook_anchor_cm:.2f} cm.'),
        comment='Se calculan las longitudes de desarrollo recto y con gancho.')
    for step in steel_steps(steel, trace):
        yield replace(step, **replacements.get(step.title, {}))


def write_checks(document, steel, trace, source, *, service=False):
    if not service:
        _body(document, 'Secciones gobernantes independientes de flexión, cortante y servicio, considerando ambos estribos.')
        _body(document, 'Sección gobernante de flexión: ' + source(trace['flexure']))
        _body(document, f'N={steel.governing_axial:.3f} tn, incluido en beta de cortante.')
    for step in developed_steps(steel, trace):
        is_service = step.title.startswith(('Fisuracion', 'Desarrollo'))
        if service != is_service or step.title.startswith('Temperatura'):
            continue
        if step.title.startswith(('Cortante', 'Verificación de cortante')):
            _body(document, 'Sección gobernante de cortante: ' + source(trace['shear']))
        elif step.title.startswith('Fisuracion'):
            _body(document, 'Sección gobernante de servicio: ' + source(trace['service']))
        write_block(document, step)
    if not service:
        _body(document, f'Estado del acero elegido: {steel.status}. Índices: flexión {steel.flexural_utilization:.3f}; '
              f'cortante {steel.shear_utilization:.3f}; servicio {steel.crack_utilization:.3f}; mínimo {steel.minimum_utilization:.3f}.')


def write_temperature(document, records, audit):
    steel = records[0]
    trace = audit['steel'][steel.region]
    t, fy = trace['temperature'], trace['yield_strength']
    step = next(step for step in steel_steps(steel, trace) if step.title.startswith('Temperatura'))
    substitutions = [
        f'As0 = 7.65*{t["b_cm"]:.2f}*{t["h_cm"]:.2f}*100/(2*({t["b_cm"]:.2f}+{t["h_cm"]:.2f})*{fy:.2f}) = {t["raw_as_cm2_m"]:.3f} cm²/m',
        f'AsT = max(2.33,min(12.70,{t["raw_as_cm2_m"]:.3f})) = {steel.temperature_cm2_m:.3f} cm²/m',
    ]
    conclusions = []
    for chosen in records:
        item = audit['steel'][chosen.region]
        substitutions.append(f'As ({chosen.region.split(" - ",1)[-1]}) = {item["bar_area"]:.3f}/{chosen.spacing_m:.3f} = {chosen.area_per_face_cm2_m:.3f} cm²/m')
        okay = chosen.area_per_face_cm2_m >= chosen.temperature_cm2_m-1e-8 and chosen.spacing_m <= item['temperature']['maximum_spacing_m']+1e-8
        conclusions.append(f'{chosen.region.split(" - ",1)[-1]}: {"CUMPLE" if okay else "NO CUMPLE"}')
    write_block(document, replace(step, title='Temperatura y distribución por cara y dirección',
        legend='b y h: dimensiones del panel en cm; fy: fluencia del acero en kgf/cm²; '
               'As0: acero calculado por temperatura en cm²/m; AsT: mínimo acotado en cm²/m por cara y dirección; '
               'Ab: área de una barra en cm²; s: separación elegida en m; As_prov: acero colocado en cm²/m.',
        substitution='\n'.join(substitutions), result='; '.join(conclusions)+'.',
        comment=f'Separación máxima por temperatura={t["maximum_spacing_m"]:.3f} m. '
                'El acero transversal se dimensiona por temperatura y distribución.'))
