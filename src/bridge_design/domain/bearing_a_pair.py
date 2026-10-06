"""Sistema de un tramo con un extremo fijo y otro móvil longitudinalmente.

El fijo ideal dispone de restricciones externas que transmiten las fuerzas
horizontales. No se acredita su resistencia mediante la fricción del neopreno.
Alcance: cuerpos de neopreno; las condiciones cinemáticas son datos del esquema.
"""
from dataclasses import dataclass, replace
from math import isfinite

from bridge_design.domain.bearing_method_a import BearingAInputs, BearingAResult, design_bearing_a


@dataclass(frozen=True)
class BearingPairInputs:
    mobile: BearingAInputs
    fixed: BearingAInputs
    equal_vertical_actions: bool = False
    fixed_displacement_cm: float = 0.0

    def __post_init__(self):
        if isinstance(self.fixed_displacement_cm,bool) or not isfinite(self.fixed_displacement_cm) or self.fixed_displacement_cm < 0:
            raise ValueError('Desplazamiento del fijo: magnitud finita no negativa.')
        if not self.mobile.connections.single_span or not self.fixed.connections.single_span:
            raise ValueError('El sistema fijo móvil implementado corresponde a un solo tramo.')
        if self.equal_vertical_actions and self.mobile.actions != self.fixed.actions:
            raise ValueError('La hipótesis de reacciones iguales no coincide con las acciones de ambos apoyos.')


@dataclass(frozen=True)
class BearingPairResult:
    inputs: BearingPairInputs
    mobile: BearingAResult
    fixed: BearingAResult

    @property
    def status(self):
        states = [self.mobile.status,self.fixed.status]
        for state in ('NO CONFORME','NO CUMPLE','PENDIENTE','ESTIMADO','REFERENCIAL'):
            if state in states:
                return 'NO CONFORME' if state == 'NO CUMPLE' else state
        return 'CONFORME'

    def to_dict(self):
        return {'esquema':'fijo_movil_un_tramo','status':self.status,
                'reacciones_verticales_iguales':self.inputs.equal_vertical_actions,
                'movil':self.mobile.to_dict(),'fijo':self.fixed.to_dict()}


def pair_from_single(inputs):
    """Compatibilidad explícita: mismo apoyo vertical en ambos extremos."""
    return BearingPairInputs(
        mobile=replace(inputs,bearing_id=inputs.bearing_id+' Móvil',neoprene_only=True,
                       connections=replace(inputs.connections,restrained_longitudinal=False)),
        fixed=replace(inputs,bearing_id=inputs.bearing_id+' Fijo',neoprene_only=True,
                      connections=replace(inputs.connections,restrained_longitudinal=True,restrained_transverse=True)),
        equal_vertical_actions=True)


def design_bearing_pair(inputs):
    for support in (inputs.mobile,inputs.fixed):
        if support.movements.prestress_shortening_cm != 0:
            raise ValueError('El sistema corresponde a concreto armado construido en sitio; postensado_cm debe ser cero.')
    if inputs.mobile.horizontal_displacement_cm is not None:
        raise ValueError('El desplazamiento del móvil se calcula desde la longitud efectiva hasta el punto fijo.')
    mobile = design_bearing_a(replace(inputs.mobile,neoprene_only=True,
        connections=replace(inputs.mobile.connections,restrained_longitudinal=False)))
    fixed = design_bearing_a(replace(inputs.fixed,neoprene_only=True,
        horizontal_displacement_cm=inputs.fixed_displacement_cm,
        connections=replace(inputs.fixed.connections,restrained_longitudinal=True,restrained_transverse=True)))
    # La restricción externa del fijo toma la fuerza horizontal completa.
    # La comparación por fricción del móvil no sustituye esta comprobación.
    if inputs.fixed_displacement_cm == 0:
        fixed = replace(fixed,steps=tuple(s for s in fixed.steps if s.id not in {'HU','FRICTION','SLIP'}))
    return BearingPairResult(inputs,mobile,fixed)
