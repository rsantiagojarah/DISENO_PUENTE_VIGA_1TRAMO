"""Entradas independientes del sistema fijo móvil de un tramo."""
from dataclasses import replace

from bridge_design.cli.bearing_a_yaml import bearing_a_from_yaml, bearing_a_template
from bridge_design.domain.bearing_a_pair import BearingPairInputs, pair_from_single

def bearing_pair_template():
    supports = {}
    for role in ('movil','fijo'):
        data = bearing_a_template()
        data.update(alcance='neopreno',identificador='A1 '+('Móvil' if role == 'movil' else 'Fijo'))
        data.pop('concreto')
        data['conexiones'] = {'mu':.2}
        supports[role] = data
    return {'esquema':'fijo_movil_un_tramo','reacciones_verticales_iguales':False,
            'desplazamiento_fijo_cm':0.,**supports}


def bearing_pair_from_yaml(data):
    if not isinstance(data,dict):
        raise ValueError('La raíz del YAML debe ser un mapa.')
    if 'esquema' not in data:
        return pair_from_single(bearing_a_from_yaml(data))
    defaults = bearing_pair_template()
    if data.keys()-defaults.keys() or data.get('esquema') != defaults['esquema']:
        raise ValueError('Esquema o campos del sistema fijo móvil inválidos.')
    mobile,fixed = (bearing_a_from_yaml(data[role]) for role in ('movil','fijo'))
    equal = data.get('reacciones_verticales_iguales',False)
    if type(equal) is not bool:
        raise ValueError('reacciones_verticales_iguales requiere true o false.')
    if equal:
        fixed = replace(fixed,actions=mobile.actions)
    displacement = data.get('desplazamiento_fijo_cm',0.)
    if isinstance(displacement,bool) or not isinstance(displacement,(int,float)):
        raise ValueError('desplazamiento_fijo_cm requiere un número no negativo.')
    return BearingPairInputs(mobile,fixed,equal,displacement)
