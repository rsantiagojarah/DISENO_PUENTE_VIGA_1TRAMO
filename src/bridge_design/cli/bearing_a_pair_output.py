"""Salida conjunta compacta para ambos extremos del tramo."""
from shutil import get_terminal_size
from bridge_design.cli.ascii_tables import audit_block_title, boxed_table
from bridge_design.reporting.bearing_a_labels import design_checks,number,status,result_status,title


def format_bearing_pair(pair, *, detailed=False,width=None):
    width = max(80,min(112,width or get_terminal_size((100,24)).columns))
    lines = audit_block_title('',f'SISTEMA DE APOYOS FIJO Y MÓVIL · {result_status(pair)}',width)
    def table(headers,rows):
        lines.extend(boxed_table(headers,rows,max_width=width,row_separators=False))
        lines.append('')
    supports = (pair.mobile,pair.fixed)
    table(('Dato','Móvil','Fijo'),[
        ('Identificación',*(r.inputs.bearing_id for r in supports)),
        ('Planta × altura (mm)',*(f'{r.adopted.length_cm*10:g} × {r.adopted.width_cm*10:g} × {r.value("HEIGHT")*10:g}' for r in supports)),
        ('Capas interiores',*(f'{r.adopted.interior_layers} de {r.adopted.interior_cm*10:g} mm' for r in supports)),
        ('Capas exteriores',*(f'2 de {r.adopted.exterior_cm*10:g} mm' for r in supports)),
        ('Zunchos',*(f'{r.adopted.interior_layers+1} de {r.adopted.steel_cm*10:g} mm' for r in supports)),
        ('Reacción de servicio',*(number(r.value('P'),'Tn') for r in supports)),
        ('Desplazamiento longitudinal',*(number(r.value('DELTA'),'cm') for r in supports)),
        ('Perforaciones pasantes',*(f'{r.adopted.hole_count} de Ø {r.adopted.hole_diameter_cm*10:g} mm' if r.adopted.hole_count else 'Sin perforaciones' for r in (pair.mobile,pair.fixed))),
        ('Estado del neopreno',*(result_status(r) for r in supports)),
    ])
    checks = [{s.id:s for s in design_checks(r)} for r in supports]
    rows = []
    def cell(s):
        if s is None:
            return 'No aplica a la traslación adoptada'
        return number(s.value,s.unit,percent=s.id=='STRAIN_CHECK')+(' < ' if s.strict else ' ≤ ')+number(s.limit,s.unit,percent=s.id=='STRAIN_CHECK')+'; '+status(s)
    for key in dict.fromkeys([*checks[0],*checks[1]]):
        s = checks[0].get(key) or checks[1][key]
        rows.append((title(s),*(cell(c.get(key)) for c in checks)))
    table(('Verificación','Móvil','Fijo'),rows)
    lines.append('Esquema de un tramo: móvil con traslación longitudinal; fijo con desplazamiento relativo adoptado.')
    lines.append('Reacciones verticales: '+('iguales por hipótesis explícita.' if pair.inputs.equal_vertical_actions else 'definidas por separado.'))
    lines.append('Alcance de los resultados: cuerpos de neopreno Método A.')
    if detailed:
        from bridge_design.cli.bearing_a_output import format_bearing_a
        for role,result in zip(('MÓVIL','FIJO'),supports):
            lines.extend(('',role,format_bearing_a(result,detailed=True,width=width)))
    return '\n'.join(lines)
