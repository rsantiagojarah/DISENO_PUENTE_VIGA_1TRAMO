"""Memoria conjunta con el estilo aprobado y el mismo registro que consola/JSON."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from docx.enum.text import WD_ALIGN_PARAGRAPH

from bridge_design.domain.bearing_method_a import FATIGUE_LIMIT, MTC_URL, perforated_properties
from bridge_design.domain.elastomeric_bearing import ElastomerGrade
from bridge_design.reporting.bearing_a_layout import BearingReportLayout
from bridge_design.reporting.bearing_a_labels import compression_basis, conclusion, title


def _n(value, digits=3, scale=1):
    return 'No determinada' if value is None else f'{value*scale:.{digits}f}'


def _state(result):
    return result.status + (' favorable para los controles incluidos' if result.status in ('CONFORME','REFERENCIAL','ESTIMADO') else '')


def _geometry(r):
    g = r.adopted
    return f'{g.length_cm*10:g} × {g.width_cm*10:g} × {r.value("HEIGHT")*10:g} mm'


def _composition(r):
    g = r.adopted
    return f'{g.interior_layers} interiores de {g.interior_cm*10:g} mm; 2 exteriores de {g.exterior_cm*10:g} mm; {g.interior_layers+1} zunchos de {g.steel_cm*10:g} mm'


def _holes(r):
    g = r.adopted
    return f'{g.hole_count} agujero(s) pasante(s) de Ø{g.hole_diameter_cm*10:g} mm' if g.hole_count else 'Sin perforaciones'


def _comparison(s, scale=1, digits=3):
    if s is None:
        return 'No aplica a la traslación adoptada'
    return f'{_n(s.value,digits,scale)} {"<" if s.strict else "≤"} {_n(s.limit,digits,scale)}'


def _mark(steps):
    states = {s.status for s in steps if s is not None}
    for state, label in [('NO CUMPLE','NO CUMPLE'),('PENDIENTE','PENDIENTE'),('CUMPLE (ESTIMADO)','E'),('REFERENCIAL','R')]:
        if state in states:
            return label
    return 'C'


def _configuration(w, r, label):
    g, i = r.adopted, r.inputs
    w.p(label,'bold')
    w.table(('Componente','Especificación'),[
        ('Planta y altura total',f'L = {g.length_cm*10:g} mm; W = {g.width_cm*10:g} mm; H = {r.value("HEIGHT")*10:g} mm'),
        ('Elastómero',f'Neopreno Shore A {i.hardness}'),
        ('Capas interiores',f'{g.interior_layers} capas de {g.interior_cm*10:g} mm'),
        ('Capas exteriores',f'2 capas de {g.exterior_cm*10:g} mm'),
        ('Refuerzo de acero',f'{g.interior_layers+1} zunchos de {g.steel_cm*10:g} mm; Fy = {i.fy_kg_cm2:g} kgf/cm²'),
        ('Perforación',_holes(r)),('Recubrimiento lateral descontado',f'{g.cover_cm:g} cm'),
    ],(58,100))
    w.p('','blank'); w.diagram(r)


def _actions(w, pair):
    same = pair.mobile.inputs.actions == pair.fixed.inputs.actions
    w.p('Las acciones son fuerzas por apoyo, expresadas en toneladas fuerza (Tn). '
        + ('Se adoptan las mismas reacciones en ambos extremos. ' if same else 'Las reacciones se definen por separado para cada extremo. ')
        + 'La concomitancia de los máximos por acción debe confirmarse con el modelo.')
    rows = []
    for attr,name,label in [('dc_tn','DC','Peso estructural'),('dw_tn','DW','Carga permanente adicional'),('pl_tn','PL','Carga peatonal'),('ll_tn','LL','Vehicular sin impacto'),('im_tn','IM','Incremento dinámico')]:
        vals = [_n(getattr(r.inputs.actions,attr))+' Tn' for r in (pair.fixed,pair.mobile)]
        rows.append((name,label,vals[0]) if same else (name,label,*vals))
    for name,label,vals in [('P','Total de servicio',[_n(r.value('P'))+' Tn' for r in (pair.fixed,pair.mobile)]),
                            ('Pmín','Mínimo adoptado para fricción',[_n(r.inputs.actions.min_vertical_tn if r.inputs.actions.min_vertical_tn is not None else r.inputs.actions.dc_tn)+' Tn' for r in (pair.fixed,pair.mobile)])]:
        rows.append((name,label,vals[0]) if same else (name,label,*vals))
    w.table(('Acción','Descripción','Reacción por apoyo') if same else ('Acción','Descripción','Fijo','Móvil'),rows,(20,86,52) if same else (17,63,39,39))
    w.p('','blank')
    for label,r in ([(None,pair.mobile)] if same else [('Móvil',pair.mobile),('Fijo',pair.fixed)]):
        a = r.inputs.actions
        if label:
            w.p(label,'bold')
        if a.ll_tn > 0:
            factor = a.im_tn/a.ll_tn
            w.equation(f'LL = ({a.ll_tn+a.im_tn:.6f})/({1+factor:.6f}) = {a.ll_tn:.6f} Tn')
            w.equation(f'IM = {factor:.6g}·LL = {a.im_tn:.6f} Tn')
            w.p('La separación mediante un único factor supone una reacción vehicular sin carga de carril incluida. Si contiene carril, deben utilizarse LL e IM separados del modelo.')
        w.p('Procedencia de reacciones: '+a.source)


def _movements(w, pair):
    r = pair.mobile
    m, g = r.inputs.movements, r.adopted
    t = m.temperature
    alpha = f'{m.alpha_per_c:.12f}'.rstrip('0').rstrip('.')
    shortening = m.shrinkage_cm+m.prestress_shortening_cm+m.other_permanent_cm
    w.p(f'Longitud efectiva desde el fijo: {m.span_length_m:g} m. Tmin = {t.t_inf_c:g} °C y Tmax = {t.t_sup_c:g} °C. Temperatura de instalación: {t.t_install_c:g} °C. '
        f'Se adopta α = {alpha} /°C, γTU = {m.gamma_tu:g} y retracción de {m.shrinkage_cm:g} cm. Otros acortamientos: {m.other_permanent_cm:g} cm; postensado: {m.prestress_shortening_cm:g} cm.')
    def temp(v):
        return f'({v:g})' if v < 0 else f'{v:g}'
    if m.use_install_to_min:
        coeff = 100*m.alpha_per_c*m.span_length_m
        dc = coeff*t.contraction_delta_t_c+shortening
        de = coeff*t.expansion_delta_t_c-shortening
        w.equation('d_c = 100·α·L·(T_i − T_min) + d_perm')
        w.equation(f'd_c = 100·{alpha}·{m.span_length_m:g}·({temp(t.t_install_c)} − {temp(t.t_inf_c)}) + {shortening:g} = {dc:.4f} cm')
        w.equation(f'd_e = 100·{alpha}·{m.span_length_m:g}·({temp(t.t_sup_c)} − {temp(t.t_install_c)}) − {shortening:g} = {de:.4f} cm')
        w.equation(f'Δ_s = γ_TU·max(|d_c|,|d_e|) = {m.gamma_tu:g}·{max(abs(dc),abs(de)):.4f} = {r.value("DELTA"):.5f} cm')
    else:
        w.equation(f'Δ_s = γ_TU·(100·α·L·(T_max − T_min) + d_perm) = {r.value("DELTA"):.5f} cm')
        w.p(r.step('DELTA').substitution)
    w.p(f'El móvil tiene Δs = {r.value("DELTA")*10:.4f} mm; el fijo tiene Δs = {pair.fixed.value("DELTA")*10:g} mm. '+r.step('DELTA').note)
    w.equation(f'h_rt = {g.interior_layers}·{g.interior_cm:.2f} + 2·{g.exterior_cm:.2f} = {r.value("HRT"):.2f} cm')
    w.equation(f'2·Δ_s = {r.value("SHEAR"):.5f} cm ≤ {r.step("SHEAR").limit:.2f} cm')
    w.p('Control de espesor por corte del móvil: '+r.step('SHEAR').status+'. La altura total incluye elastómero y acero.','bold')


def _compression(w, r):
    g = r.adopted
    _,perimeter,_,_,_ = perforated_properties(g,g.length_cm)
    w.p(f'Se considera {_holes(r).lower()}, con L = {g.length_cm:g} cm y W = {g.width_cm:g} cm. El recubrimiento lateral descontado es {g.cover_cm:g} cm. '
        'Se utilizan área neta y perímetro libre de las capas. Base geométrica: AASHTO C14.7.5.1-1 y definición MTC 2.10.3.1.')
    w.equation(f'A_n = (L − 2·c)·(W − 2·c) − (N·π·d^2)/4 = {r.value("AREA"):.3f} cm²')
    w.equation(f'p_libre = 2·(L + W − 4·c) + N·π·d = {perimeter:.3f} cm')
    w.equation(f'S_i = (A_n)/(h_ri·p_libre) = {r.value("SI"):.4f}')
    w.equation(f'S_e = (A_n)/(h_re·p_libre) = {r.value("SE"):.4f}')
    w.equation(f'σ_s = (1000·P)/(A_n) = {r.value("SIGMA"):.3f} kgf/cm²')
    grade = ElastomerGrade.from_hardness(r.inputs.hardness)
    w.p(f'Para Shore {r.inputs.hardness} se adopta Gmín = {grade.g_min_kg_cm2:g} kgf/cm² y Gmáx = {grade.g_max_kg_cm2:g} kgf/cm². Límites de compresión según MTC 2.10.4.3.2:')
    w.equation(f'σ_s = {r.value("SIGMA"):.3f} ≤ {r.step("SIGMA").limit:.3f} kgf/cm²')
    w.equation(f'σ_s = {r.value("GS"):.3f} ≤ 1.25·G_min·S_i = {r.step("GS").limit:.3f} kgf/cm²')


def _deflections(w, r):
    w.p(compression_basis(r))
    if r.inputs.compression_curve is not None:
        w.p('Fuente: '+r.inputs.compression_curve.source+'. Se interpola en esfuerzo y factor S, sin extrapolar.')
    w.table(('Capa','Factor S','Permanentes DC + DW','Total sin IM'),[
        ('Interior',_n(r.value('SI'),4),'ε = '+_n(r.step('EPS_ID').value,4,100)+' %','ε = '+_n(r.step('EPS_IT').value,4,100)+' %'),
        ('Exterior',_n(r.value('SE'),4),'ε = '+_n(r.step('EPS_ED').value,4,100)+' %','ε = '+_n(r.step('EPS_ET').value,4,100)+' %'),
    ],(28,25,52,53))
    w.p('','blank')
    s = r.step('STRAIN_CHECK')
    if s.value is not None:
        w.equation(f'ε_IT = {s.value*100:.4f} % ≤ {s.limit*100:.4f} %')
    else:
        w.p('Deformación interior: PENDIENTE. '+s.note)
    grade = ElastomerGrade.from_hardness(r.inputs.hardness)
    w.p(f'Las deflexiones son sumas por capas: δ = n hri εi + 2 hre εe. Para el efecto diferido se adopta Cd = {grade.creep_ratio:g} y δcreep = Cd δD. '
        'La carga viva se evalúa como diferencia entre estados total sin IM y permanente.')
    w.table(('Resultado','Valor'),[
        ('Deflexión inicial permanente δD',_n(r.step('DEF_D').value,5)+' cm'),
        ('Deflexión inicial total sin IM δT',_n(r.step('DEF_T').value,5)+' cm'),
        ('Incremento por carga viva δLL = δT − δD',_n(r.step('DEF_LL').value,5)+' cm'),
        ('Deflexión diferida δcreep',_n(r.step('CREEP').value,5)+' cm'),
        ('δLL + δcreep frente al límite de junta',_comparison(r.step('JOINT'),digits=5)+' cm'),
    ],(100,58))
    w.p('','blank')


def _steel(w, r):
    g = r.adopted
    w.p(f'El espesor requerido se obtiene de servicio, fatiga y mínimo constructivo. Se usa hmax = {max(g.interior_cm,g.exterior_cm):.2f} cm, '
        f'Fy = {r.inputs.fy_kg_cm2:g} kgf/cm² y ΔFTH = {FATIGUE_LIMIT:g} kgf/cm² para la categoría A adoptada.')
    w.equation(f'h_serv = (3·h_max·σ_s)/(Fy) = {r.value("HS_SERVICE")*10:.4f} mm')
    a = r.inputs.actions
    stress_live = (a.ll_tn+a.im_tn+a.pl_tn)*1000/r.value('AREA')
    w.equation(f'σ_LL = (1000·(LL + IM + PL))/(A_n) = {stress_live:.4f} kgf/cm²')
    w.equation(f'h_fat = (2·h_max·σ_LL)/(ΔF_TH) = {r.value("HS_FATIGUE")*10:.4f} mm')
    w.equation(f'h_min = (25.4)/16 = {r.value("HS_MIN")*10:.4f} mm')
    base = max(r.value('HS_SERVICE'),r.value('HS_FATIGUE'),r.value('HS_MIN'))
    if g.hole_count:
        _,_,gross,net,_ = perforated_properties(g,g.length_cm)
        w.p(f'Zuncho con perforaciones pasantes: bg = {gross*10:g} mm y bn = {gross*10:g} − {g.hole_count}·{g.hole_diameter_cm*10:g} = {net*10:g} mm. '
            'Se consideran conservadoramente todos los agujeros en una sección. El incremento se aplica al mayor de los tres espesores anteriores.')
        w.equation('h_req = ((2·b_g)/(b_n))·max(h_serv,h_fat,h_min)')
        w.equation(f'h_req = ((2·{gross*10:g})/({net*10:g}))·{base*10:.4f} = {r.value("HS_HOLES")*10:.4f} mm ≤ {g.steel_cm*10:.4f} mm')
        control = r.step('HS_HOLES')
    else:
        w.equation(f'h_req = max(h_serv,h_fat,h_min) = {base*10:.4f} mm')
        control = max((r.step(k) for k in ('HS_SERVICE','HS_FATIGUE','HS_MIN')),key=lambda s:s.value)
    w.p(f'Se adoptan {g.interior_layers+1} zunchos de {g.steel_cm*10:g} mm. Control del refuerzo: {control.status}. '
        'El artículo 2.10.4.3.7 del MTC remite a 2.10.3.3.5; este último incluye el incremento por perforaciones.')


def _stability(w, r):
    g = r.adopted
    w.equation(f'H = {g.interior_layers}·{g.interior_cm*10:g} + 2·{g.exterior_cm*10:g} + {g.interior_layers+1}·{g.steel_cm*10:g} = {r.value("HEIGHT")*10:g} mm')
    w.equation(f'h_re = {g.exterior_cm*10:g} mm ≤ 0.70·{g.interior_cm*10:g} = {r.step("EXTERIOR").limit*10:g} mm')
    w.equation(f'H = {r.value("HEIGHT"):.2f} cm ≤ min(L/3,W/3) = {min(r.step("STABILITY_L").limit,r.step("STABILITY_W").limit):.3f} cm')
    w.p(f'Número efectivo de capas neff = {r.value("NEFF"):g}; límite de aplicabilidad adoptado: {r.step("SCOPE").limit:g}. '
        'El límite 22 procede del MTC; 20 y 16 corresponden al comentario C14.7.6.1 aplicado por Serquén.')
    w.equation(f'(S_i^2)/(n_eff) = {r.value("SCOPE"):.4f} < {r.step("SCOPE").limit:g}')
    w.p('Rotación principal alrededor del eje transversal: '+('sí' if g.principal_rotation_transverse else 'no')+'. Control de alcance: '+r.step('ROTATION').status
        +'. Deben comprobarse las rotaciones del análisis y las tolerancias de montaje.')


def _horizontal(w, pair):
    for role,r in [('Móvil',pair.mobile),('Fijo',pair.fixed)]:
        if 'HU' not in {s.id for s in r.steps}:
            continue
        if role == 'Fijo':
            w.p('Fijo con desplazamiento relativo adoptado','bold')
        w.equation(f'H_serv = (G_max·A_n·Δ_s)/(1000·h_rt) = {r.value("HU"):.4f} Tn')
        pmin = r.inputs.actions.min_vertical_tn if r.inputs.actions.min_vertical_tn is not None else r.inputs.actions.dc_tn
        w.equation(f'F_f = μ·P_min = {r.inputs.connections.friction_mu:g}·{pmin:g} = {r.value("FRICTION"):.4f} Tn')
        w.equation(f'H_serv = {r.value("HU"):.4f} Tn ≤ F_f = {r.value("FRICTION"):.4f} Tn')
        if r.value('FRICTION') > 0:
            w.p(f'Utilización de la fricción disponible: {100*r.value("HU")/r.value("FRICTION"):.1f} %. Control en servicio: '+r.step('SLIP').status+'.')
        else:
            w.p('La fricción disponible es nula. Control en servicio: '+r.step('SLIP').status+'.')
    w.p(f'El fijo tiene un desplazamiento relativo adoptado de {pair.fixed.value("DELTA"):g} cm. Su restricción horizontal corresponde al dispositivo externo, cuya resistencia no se verifica en esta memoria.')


def _summary(w, pair):
    w.p('C identifica un control numérico favorable; R, un control dependiente de curvas referenciales; E, un resultado con modelo elástico estimado. '
        'Los incumplimientos y resultados pendientes se indican expresamente.')
    checks = [{s.id:s for s in r.checks} for r in (pair.fixed,pair.mobile)]
    rows = []
    for key in dict.fromkeys([*checks[1],*checks[0]]):
        steps = [c.get(key) for c in checks]
        s = next(s for s in steps if s is not None)
        scale = 10 if key.startswith('HS_') or key == 'EXTERIOR' else 100 if key == 'STRAIN_CHECK' else 1
        unit = 'mm' if scale == 10 else '%' if scale == 100 else s.unit
        digits = 6 if key == 'HEIGHT_TARGET' else 5 if key == 'SHEAR' else 4 if key in ('SCOPE','STRAIN_CHECK','JOINT') or key.startswith('HS_') else 3
        rows.append((title(s)+(f' ({unit})' if unit != '-' else ''),*(_comparison(step,scale,digits) for step in steps),_mark(steps)))
    w.table(('Verificación','Izquierdo fijo','Derecho móvil','Estado'),rows,(60,39,39,20))
    w.p('','blank')


def generate_bearing_pair_docx(pair, output_path):
    path = Path(output_path).expanduser().resolve().with_suffix('.docx')
    path.parent.mkdir(parents=True,exist_ok=True)
    w = BearingReportLayout()
    r, f = pair.mobile, pair.fixed
    common_geometry = (r.adopted == f.adopted and r.inputs.hardness == f.inputs.hardness and r.inputs.fy_kg_cm2 == f.inputs.fy_kg_cm2)
    common_vertical = common_geometry and r.inputs.actions == f.inputs.actions and r.inputs.compression_curve == f.inputs.compression_curve and r.inputs.joint_limit_cm == f.inputs.joint_limit_cm
    w.p('INGENIERÍA ESTRUCTURAL','cover_label'); w.p('Memoria de cálculo\ndel sistema de apoyos','title')
    w.p('Geometría · movimientos · compresión · zunchos · estabilidad · fricción','subtitle'); w.p('DOCUMENTO TÉCNICO DE DISEÑO','label')
    w.table(('Dato','Descripción'),[
        ('Proyecto',r.inputs.project),('Sistema',f'Un tramo de {r.inputs.movements.span_length_m:g} m; izquierdo fijo y derecho móvil'),
        ('Identificación',f'Fijo: {f.inputs.bearing_id}; móvil: {r.inputs.bearing_id}'),
        ('Dimensiones',_geometry(r) if common_geometry else f'Móvil: {_geometry(r)}; fijo: {_geometry(f)}'),
        ('Composición',_composition(r) if common_geometry else 'Se detalla por separado para cada apoyo'),
        ('Norma principal','Manual de Puentes MTC 2018; Método A'),('Estado del cálculo',_state(pair)),
        ('Fecha de emisión',datetime.now(timezone(timedelta(hours=-5))).strftime('%d/%m/%Y')),
    ],(40,118))
    w.p('La memoria presenta los datos adoptados, las expresiones principales, los resultados y las verificaciones de los cuerpos de neopreno y sus zunchos. '
        'Se conservan las hipótesis de cálculo y las observaciones constructivas.','cover_intro')
    w.page_break(); w.heading('Contenido')
    w.p('Se desarrolla el cálculo de los neoprenos, identificando las diferencias del apoyo fijo y del móvil, con fórmulas editables y un resumen conjunto de verificaciones.')
    w.table(('Sección','Contenido desarrollado'),[
        ('1 y 2','Configuración adoptada y alcance de la verificación'),('3 y 4','Reacciones, separación de impacto, temperatura y retracción'),
        ('5 y 6','Geometría perforada, compresión y deformaciones verticales'),('7 a 9','Zunchos, estabilidad y fricción'),
        ('10 a 12','Resumen de verificaciones, conclusión, detalle constructivo y referencias'),
    ],(30,128))
    w.p('','blank'); w.p('Estado del sistema: '+_state(pair)+'. '+compression_basis(r)); w.page_break()
    w.heading('1. Configuración adoptada')
    w.p('Se verifican los cuerpos de neopreno y sus zunchos para un apoyo izquierdo fijo y un apoyo derecho móvil. '+f'Estado del cálculo: {_state(pair)}.')
    if common_geometry:
        _configuration(w,r,'Composición común a ambos apoyos')
    else:
        _configuration(w,r,'Apoyo derecho móvil'); _configuration(w,f,'Apoyo izquierdo fijo')
    w.p('L es longitudinal y W transversal. Se utiliza el área neta de caucho y el perímetro libre de las capas. La ubicación de los agujeros y las tolerancias deben definirse en el detalle de fabricación.')
    w.heading('2. Alcance del resultado')
    w.p('El fijo se representa con el desplazamiento relativo longitudinal adoptado mediante una restricción externa. El móvil acomoda el movimiento por deformación del elastómero. '
        'El dimensionamiento del pasador, su anclaje, el pedestal y las holguras requieren verificaciones complementarias.')
    w.heading('3. Acciones y movimientos de servicio'); _actions(w,pair)
    w.heading('4. Temperatura y retracción'); _movements(w,pair)
    for label,fn in [('5. Geometría efectiva y compresión',_compression),('6. Deformaciones y deflexiones verticales',_deflections),
                     ('7. Diseño de los zunchos perforados',_steel),('8. Composición estabilidad y aplicabilidad',_stability)]:
        w.heading(label)
        if common_vertical:
            fn(w,r)
        else:
            w.p('Apoyo derecho móvil','bold'); fn(w,r); w.p('Apoyo izquierdo fijo','bold'); fn(w,f)
    w.heading('9. Fuerza horizontal y fricción'); _horizontal(w,pair)
    w.heading('10. Resumen de verificaciones'); _summary(w,pair)
    w.heading('11. Conclusión y detalle constructivo'); w.p('Estado del sistema: '+_state(pair)+'.','bold')
    for label,result in ([('Ambos neoprenos',r)] if common_geometry else [('Móvil',r),('Fijo',f)]):
        w.p(f'{label}: neopreno Shore {result.inputs.hardness} de {_geometry(result)}, {_composition(result)}. '+_holes(result)+'. '+conclusion(pair if common_geometry else result))
    if r.adopted.hole_count or f.adopted.hole_count:
        w.p('Las perforaciones son diámetros de cálculo. El diámetro del pasador, las tolerancias y la holgura de montaje deben definirse en el detalle constructivo; '
            'la igualdad nominal entre agujero y pasador no incorpora holgura. Una perforación de fabricación mayor exige actualizar la verificación del neopreno y del zuncho.')
    pin = pair.inputs.pin_diameter_cm
    if pin is not None:
        w.p(f'Diámetro nominal del pasador indicado: {pin*10:g} mm. No se dimensiona su resistencia en esta memoria.')
        if any(g.hole_count and pin > g.hole_diameter_cm for g in (r.adopted,f.adopted)):
            w.p('El pasador indicado supera el diámetro de al menos una perforación: el detalle de montaje es incompatible y debe corregirse.','bold')
        tube = (f'Con ese pasador centrado en un tubo circular, el diámetro interior geométrico sería al menos '
                f'{(pin+2*r.value("DELTA"))*10:.4f} mm, antes de tolerancias. ')
    else:
        tube = (f'Si se usa un tubo circular con pasador centrado, el diámetro interior debe cubrir el diámetro real '
                f'del pasador más {2*r.value("DELTA")*10:.4f} mm, antes de tolerancias. El diámetro del pasador no se deduce de la perforación. ')
    w.p(f'El dispositivo derecho debe permitir el recorrido longitudinal de {r.value("DELTA")*10:.4f} mm, considerando la posición de montaje y las tolerancias. '
        +tube+'También deben verificarse el anclaje del fijo y el pasador frente a sus acciones de diseño.')
    w.heading('12. Referencias y registro')
    p = w.p('Manual de Puentes MTC 2018, artículos 2.10.3.3.5 y 2.10.4.1 a 2.10.4.3.8. ','bullet')
    w.link(p,'Portal normativo del MTC',MTC_URL)
    w.p('Rodríguez Serquén, Puentes con AASHTO LRFD 2020, capítulo de apoyos, pp. 223 a 239. Compresión: p. 231, Fig. C14.7.6.3.3-1, '
        'cuando se seleccionan las curvas referenciales incorporadas al programa.','bullet')
    p = w.p(f'Motor: {r.version}.\nSHA256 móvil: {r.input_sha256}\nSHA256 fijo: {f.input_sha256}')
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    w.doc.core_properties.title = 'Memoria de cálculo del sistema de apoyos'
    w.doc.core_properties.subject = r.inputs.project
    w.doc.save(path)
    return path
