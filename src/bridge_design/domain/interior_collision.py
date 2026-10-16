"""Interior barrier transfer through a continuous, unit-width deck strip.

This is an explicitly declared elastic strip model, not the A13.4 overhang
30-degree/0.40 approximation. Vertical reactions are deliverables for the
girder model, not an automatic verification of bearings or diaphragms.
"""

from dataclasses import dataclass, replace
from itertools import product
from math import isfinite

from bridge_design.codes.mtc_2018 import mtc_tension_development_length_cm
from bridge_design.domain.rebar_catalog import ReinforcementSpacingOption
from bridge_design.domain.reinforcement import flexural_steel_area_cm2
from bridge_design.domain.transverse_slab import (
    PointMoment, PointLoad, solve_load_case, transverse_load_placement_cases,
    _bending_moment_at,
)
from bridge_design.units.converters import kip_to_tn
from bridge_design.validation.input_validators import require_positive


REFERENCE = (
    "MTC 2018: 2.4.3.5.1.2 (remite a AASHTO Seccion 13), "
    "Tabla 2.4.3.6.3-1 (Fv, Lv), 2.4.5.3 (combinaciones). "
    "Modelo adoptado: franja elastica continua, apoyos verticales en ejes de vigas; "
    "sin reduccion longitudinal por dispersion. No es la formula de voladizo A13.4."
    " N y As(M)+N/(phi fy): FHWA PSC Design Step 4.10, "
    "https://www.fhwa.dot.gov/bridge/lrfd/pscus04.cfm ."
)


@dataclass(frozen=True)
class InteriorCollisionCase:
    name: str
    position_m: float
    applied_moment_tn_m_m: float
    applied_vertical_tn_m: float
    axial_tension_tn_m: float
    reactions_tn_m: tuple[tuple[float, float], ...]
    vertical_equilibrium_error_tn_m: float
    moment_equilibrium_error_tn_m_m: float


@dataclass(frozen=True)
class InteriorCollisionFace:
    face: str
    case_name: str
    position_m: float
    moment_tn_m_m: float
    tension_tn_m: float
    dc_factor: float
    dw_factor: float
    option: ReinforcementSpacingOption | None
    development_length_m: float
    development_available_m: float
    status: str
    reason: str = ""

    @property
    def steel_status(self) -> str:
        if self.option is None:
            return "PENDIENTE"
        return "OK" if self.option.is_compliant else "NO CUMPLE"

    @property
    def development_status(self) -> str:
        if self.option is None:
            return "PENDIENTE"
        return "OK" if self.development_available_m + 1e-9 >= self.development_length_m else "NO CUMPLE"


@dataclass(frozen=True)
class InteriorCollisionConnectionCheck:
    """One capacity check for the barrier-to-deck connection."""

    control: str
    demand: float
    capacity: float
    unit: str
    status: str


@dataclass(frozen=True)
class InteriorCollisionDesign:
    cases: tuple[InteriorCollisionCase, ...]
    faces: tuple[InteriorCollisionFace, ...]
    horizontal_force_tn: float
    transfer_length_m: float
    interface_moment_tn_m_m: float
    shear_demand_tn_m: float
    shear_capacity_tn_m: float
    shear_beta: float
    shear_status: str
    connection_checks: tuple[InteriorCollisionConnectionCheck, ...]
    connection_status: str
    status: str
    notes: tuple[str, ...]

    def report_lines(self) -> tuple[str, ...]:
        lines = [
            "TRANSFERENCIA DE COLISION A LOSA INTERIOR",
            REFERENCE,
            f"Ft=max(Ft de ensayo,Rw)={self.horizontal_force_tn:.3f} Tn; "
            f"L={self.transfer_length_m:.3f} m; "
            f"M interfaz={self.interface_moment_tn_m_m:.3f} Tn*m/m.",
        ]
        for case in self.cases:
            lines.append(
                f"{case.name}: x={case.position_m:.3f} m; "
                f"M aplicado={case.applied_moment_tn_m_m:.3f} Tn*m/m; "
                f"Fv={case.applied_vertical_tn_m:.3f} Tn/m; "
                f"N={case.axial_tension_tn_m:.3f} Tn/m."
            )
            lines.append("Reacciones verticales de colision por viga (Tn/m; + hacia arriba): " +
                         "; ".join(f"V{i+1}={r:.3f}" for i, (_, r) in enumerate(case.reactions_tn_m)))
            lines.append(f"Residuos equilibrio: fuerzas={case.vertical_equilibrium_error_tn_m:.2e} Tn/m; "
                         f"momentos={case.moment_equilibrium_error_tn_m_m:.2e} Tn*m/m.")
        for face in self.faces:
            lines.append(f"Acero transversal {face.face}: {face.case_name}; x={face.position_m:.3f} m; "
                         f"M={face.moment_tn_m_m:.3f} Tn*m/m, N={face.tension_tn_m:.3f} Tn/m; "
                         f"factores DC/DW={face.dc_factor:.2f}/{face.dw_factor:.2f}.")
            if face.option:
                o = face.option
                lines.append(f"{o.bar.label} cada {o.spacing_m:.3f} m; "
                             f"As req={o.required_area_cm2_m:.3f}, As prov={o.provided_area_cm2_m:.3f} cm2/m; "
                             f"area: {face.steel_status}; ld={face.development_length_m:.3f} m, "
                             f"disponible={face.development_available_m:.3f} m; anclaje: {face.development_status}; "
                             f"resultado: {face.status}.")
            else:
                lines.append("PENDIENTE: falta seleccionar el acero principal de la losa para esta cara.")
            if face.reason:
                lines.append(face.reason)
        if self.shear_status == "PENDIENTE":
            lines.append(f"Corte: Vu={self.shear_demand_tn_m:.3f} Tn/m; PENDIENTE: "
                         "seleccionar el acero de losa de ambas caras para calcular la resistencia.")
        else:
            lines.append(f"Corte: Vu={self.shear_demand_tn_m:.3f}, phi Vc={self.shear_capacity_tn_m:.3f} Tn/m; "
                         f"beta={self.shear_beta:.3f}: {self.shear_status}.")
        lines.append(f"Conexion barrera-losa: {self.connection_status}. Resultado local: {self.status}.")
        return tuple(lines) + self.notes


def _shear_at(x, segments, points, reactions):
    return (sum(r for s, r in reactions if s <= x)
            - sum(p.p_tn for p in points if p.position_m <= x)
            - sum(s.q_tn_m * max(0.0, min(x, s.end_m) - s.start_m) for s in segments))


def design_interior_collision(geometry, materials, live_loads, layout, barrier, params, *,
                              slab_selected=(), slab_cover_cm=None):
    """Check the adopted transverse slab reinforcement under local collision.

    Negative (A.) and positive (B.) slab selections supply the upper and lower
    layers; never replace them with independently recommended bars. Ordinary
    Strength/Service reinforcement remains mandatory. Each (M,N) pair is kept
    compatible. N is conservatively carried without reduction to the interior
    side; its horizontal support allocation needs a global in-plane model.
    Local straight-bar anchorage is measured outward from the outer face of
    each barrier base to the bar end at the deck edge cover, for both layers.
    """
    if slab_cover_cm is not None:
        # The adopted interior slab may not share the overhang's cover.
        params = replace(params, concrete_cover_cm=slab_cover_cm)
    placements = transverse_load_placement_cases(geometry, materials, live_loads, layout)
    dead = placements[:2]
    dead_results = tuple(solve_load_case(geometry, materials, p.name, p.segments, p.point_loads) for p in dead)
    force = max(barrier.yield_line.demand_transverse_force_tn,
                barrier.yield_line.nominal_transverse_resistance_tn)
    # Interface tension per A13.4.2; preserve Mc without slab dispersion.
    length = barrier.yield_line.critical_length_m + 2*barrier.geometry.height_m
    n = force / length
    moment = barrier.flexure.mc_tn_m * max(
        1.0, barrier.yield_line.demand_transverse_force_tn / barrier.yield_line.nominal_transverse_resistance_tn)
    level = barrier.impact_load.test_level.upper().replace("-", "")
    vertical_table = {"TL1": (4.5, 18), "TL2": (4.5, 18), "TL3": (4.5, 18),
                      "TL4": (18, 18), "TL5": (80, 40), "TL6": (80, 40)}
    if level not in vertical_table:
        raise ValueError(f"Nivel de ensayo no reconocido para Fv/Lv: {level}")
    fv_kip, lv_ft = vertical_table[level]
    vertical = kip_to_tn(fv_kip) / (lv_ft * 0.3048)
    base = (layout.barrier_left_m, layout.barrier_left_m + barrier.geometry.base_width_m)
    if base[0] < geometry.overhang_m + geometry.girder_width_m / 2 or base[1] > geometry.support_positions_m[1] - geometry.girder_width_m / 2:
        raise ValueError("La transferencia interior requiere la base completa en el primer vano libre.")
    # Mirrored barriers have the same outer-face-to-near-edge distance.
    # This is the adopted LOCAL anchorage reference, not the girder axis,
    # barrier centre, or the section governing the reinforcement demand.
    edge_cover_m = params.concrete_cover_cm / 100
    development_available_m = max(0.0, base[0] - edge_cover_m)
    slab_choices = {label[:2]: option for label, option in slab_selected}
    adopted = {"superior": slab_choices.get("A."), "inferior": slab_choices.get("B.")}
    cases, demands = [], {"superior": [], "inferior": []}
    vu = 0.0
    maximum_moment = 0.0
    # Both base faces bound the unresolved distribution through its width.
    # Mirror impacts are independent; opposite barriers never collide together.
    for edge, sign in (("izquierda", 1), ("derecha", -1)):
        for base_x in base:
            x = base_x if sign == 1 else geometry.total_width_m - base_x
            for kind, cm, pv, tension in (("horizontal", sign * moment, 0.0, n),
                                          ("vertical", 0.0, vertical, 0.0)):
                name = f"EEII {kind}, barrera {edge}, x={x:.3f}"
                points = (PointLoad(x, pv, name),) if pv else ()
                moments = (PointMoment(x, cm, name),) if cm else ()
                solved = solve_load_case(geometry, materials, name, (), points, point_moments=moments)
                rf = sum(r for _, r in solved.support_reactions_tn) - pv
                rm = sum(s*r for s, r in solved.support_reactions_tn) - pv*x + cm
                if max(abs(rf), abs(rm)) > 1e-6:
                    raise ArithmeticError("No se cumple el equilibrio de transferencia de colision.")
                cases.append(InteriorCollisionCase(name, x, cm, pv, tension, solved.support_reactions_tn, rf, rm))
                # Retain one-sided couple values, plus all permanent-load nodes.
                samples = list(solved.moment_samples_tn_m)
                for load_result in dead_results:
                    for s, _ in load_result.moment_samples_tn_m:
                        if not any(abs(s-t) < 1e-9 for t, _ in samples):
                            m = _bending_moment_at(s, (), points, solved.support_reactions_tn) - (cm if s > x else 0)
                            samples.append((s, m))
                # Exact stationary points of every factored piecewise-quadratic
                # permanent + collision moment diagram, not just grid samples.
                boundaries = sorted({0., geometry.total_width_m, x, *geometry.support_positions_m,
                                     *(s for p in dead for seg in p.segments for s in (seg.start_m, seg.end_m)),
                                     *(p.position_m for load in dead for p in load.point_loads)})
                for a, b in zip(boundaries, boundaries[1:]):
                    mid = (a+b)/2
                    qs = [sum(seg.q_tn_m for seg in p.segments if seg.start_m <= mid <= seg.end_m) for p in dead]
                    vs = [_shear_at(a, p.segments, p.point_loads, r.support_reactions_tn) for p, r in zip(dead, dead_results)]
                    for gd, gw in product((.9, 1.25), (.65, 1.5)):
                        q = gd*qs[0] + gw*qs[1]
                        v = gd*vs[0] + gw*vs[1] + _shear_at(a, (), points, solved.support_reactions_tn)
                        if q > 0 and a < a+v/q < b:
                            s = a+v/q
                            samples.append((s, _bending_moment_at(s, (), points, solved.support_reactions_tn) - (cm if s > x else 0)))
                for s, collision_m in samples:
                    if not geometry.overhang_m <= s <= geometry.support_positions_m[-1]:
                        continue
                    dc, dw = (_bending_moment_at(s, p.segments, p.point_loads, r.support_reactions_tn)
                              for p, r in zip(dead, dead_results))
                    for gd, gw in product((0.9, 1.25), (0.65, 1.5)):
                        m = gd*dc + gw*dw + collision_m
                        maximum_moment = max(maximum_moment, abs(m))
                        face = "superior" if m < 0 else "inferior"
                        demands[face].append((abs(m), tension, name, s, gd, gw))
                        # Both sides of every reaction/load jump; no beneficial cancellation of signs.
                        for sx in (s-1e-7, s+1e-7):
                            vdc, vdw = (_shear_at(sx, p.segments, p.point_loads, r.support_reactions_tn)
                                        for p, r in zip(dead, dead_results))
                            vu = max(vu, abs(gd*vdc + gw*vdw + _shear_at(sx, (), points, solved.support_reactions_tn)))
    faces = tuple(
        _review_face(face, rows, geometry, materials, params, adopted[face],
                     development_available_m=development_available_m)
        for face, rows in demands.items()
    )
    from bridge_design.domain._cantilever_slab_checks import _concrete_shear_resistance_tn
    # General no-stirrup shear procedure; aggregate contribution conservatively set to zero.
    selected = [f.option for f in faces if f.option is not None]
    d = min((geometry.slab_thickness_m*100 - params.concrete_cover_cm - o.bar.diameter_cm/2 for o in selected), default=0)
    if len(selected) < 2:
        # Missing reinforcement is not a failed physical check or a substitute
        # catalogue choice. Keep the demands, but do not publish a fake capacity.
        beta = capacity = 0.0
        shear_status = "PENDIENTE"
    elif d <= 0:
        beta = capacity = 0.0
        shear_status = "NO CUMPLE"
    else:
        dv = max(.9*d, .72*geometry.slab_thickness_m*100)
        area = min(o.provided_area_cm2_m for o in selected)
        epsilon = (max(maximum_moment*100000/dv, vu*1000) + vu*1000 + n*1000) / (2_000_000*area)
        sxe = min(80., max(12., (dv/2.54)*1.38/.63))
        beta = 4.8/(1+750*epsilon) * 51/(39+sxe)
        capacity = params.shear_resistance_factor * _concrete_shear_resistance_tn(
            materials.concrete.compressive_strength_kg_cm2, 100, dv, beta)
        shear_status = "OK" if capacity >= vu else "NO CUMPLE"
    hook = barrier.development
    hook_capacity_ld = max(hook.minimum_ldh_cm, hook.modified_ldh_cm / hook.excess_reinforcement_factor)
    connection_ok = (barrier.yield_line.resistance_status == "OK"
                     and barrier.shear_transfer.nominal_shear_tn_m >= n
                     and barrier.dowel.status == "OK" and hook.available_length_cm >= hook_capacity_ld)
    connection_checks = (
        InteriorCollisionConnectionCheck(
            "Lineas de fluencia",
            barrier.yield_line.demand_transverse_force_tn,
            barrier.yield_line.nominal_transverse_resistance_tn,
            "Tn",
            barrier.yield_line.resistance_status,
        ),
        InteriorCollisionConnectionCheck(
            "Friccion barrera-losa",
            n,
            barrier.shear_transfer.nominal_shear_tn_m,
            "Tn/m",
            "OK" if barrier.shear_transfer.nominal_shear_tn_m + 1e-9 >= n else "NO CUMPLE",
        ),
        InteriorCollisionConnectionCheck(
            "Acero de dowels",
            barrier.dowel.required_avf_cm2_m,
            barrier.dowel.provided_avf_cm2_m,
            "cm2/m",
            barrier.dowel.status,
        ),
        InteriorCollisionConnectionCheck(
            "Desarrollo de dowel",
            hook_capacity_ld,
            hook.available_length_cm,
            "cm",
            "OK" if hook.available_length_cm + 1e-9 >= hook_capacity_ld else "NO CUMPLE",
        ),
    )
    connection = "OK" if connection_ok else "NO CUMPLE"
    states = (connection, shear_status, *(f.status for f in faces))
    status = "NO CUMPLE" if "NO CUMPLE" in states else ("PENDIENTE" if "PENDIENTE" in states else "OK")
    return InteriorCollisionDesign(tuple(cases), faces, force, length, moment, vu, capacity, beta,
        shear_status, connection_checks, connection, status, (
            "Casos horizontales y verticales independientes; gamma CT=1.0; DC=0.90/1.25, DW=0.65/1.50. "
            "La colision de barrera no se combina con LL/PL; el armado ordinario de Resistencia y Servicio se conserva.",
            "Armadura verificada: acero transversal de losa seleccionado para flexion negativa (cara superior) "
            "y positiva (cara inferior). As requerido se recalcula para colision con el diametro real de cada cara. "
            "No se seleccionan barras nuevas ni se suman las areas de los casos ordinario y de colision. "
            "El armado debe estar presente en la misma cara, direccion y zona de la demanda, y continuar hasta sus anclajes.",
            "Anclaje local adoptado para ambas caras de acero: desde la cara exterior de la base de cada barrera "
            "hacia el borde exterior cercano de la losa, con barras rectas continuas hasta el recubrimiento lateral. "
            f"Ldisp = max(0, ab - c) = max(0, {base[0]:.3f} - {edge_cover_m:.3f}) "
            f"= {development_available_m:.3f} m; "
            "ab: distancia cara exterior de barrera-borde de losa; c: recubrimiento lateral. "
            "La misma longitud se aplica a ambos lados por simetria. Se exige desarrollo completo, sin reduccion por exceso de acero.",
            "La coordenada x de las demandas se mide desde el borde izquierdo del tablero y no define el origen "
            "del anclaje local adoptado. Este control no sustituye las verificaciones de desarrollo en otras "
            "secciones, cortes o empalmes del armado; se mantienen los controles del diseno ordinario y del voladizo.",
            "Alcance: transferencia LOCAL barrera-losa y demandas verticales hacia vigas calculadas. "
            "La distribucion horizontal entre vigas, diafragmas y apoyos requiere el modelo global en planta; "
            "este resultado local no certifica ese sistema.",
        ))


def _review_face(face, rows, geometry, materials, params, selected, *, development_available_m):
    """Keep the physical slab bars and refresh only their collision checks."""
    fc, fy = materials.concrete.compressive_strength_kg_cm2, materials.steel.yield_strength_kg_cm2
    h = geometry.slab_thickness_m*100
    # For a fixed axial demand, steel increases monotonically with |M|.
    rows = [max((r for r in rows if r[1] == n), key=lambda r:r[0])
            for n in sorted({r[1] for r in rows})]
    if selected is None:
        row = max(rows, key=lambda r:r[0])
        return InteriorCollisionFace(face, row[2], row[3], row[0], row[1], row[4], row[5],
                                     None, 0, development_available_m, "PENDIENTE")
    bar = selected.bar
    require_positive(selected.spacing_m, "separacion del acero de losa adoptado")
    d = h - params.concrete_cover_cm - bar.diameter_cm/2
    requirements = []
    reason = ""
    for m, n, name, x, gd, gw in rows:
        try:
            if d <= h/2:
                raise ValueError("El peralte efectivo no permite la verificacion de la cara traccionada.")
            # Preserve the existing collision model at the ACTUAL diameter.
            area = flexural_steel_area_cm2(m, 100, d, fc, fy,
                                           phi=params.flexural_resistance_factor)
            area += n*1000/(min(params.flexural_resistance_factor, .75)*fy)
            area = max(area, params.shrinkage_temperature_ratio*100*h)
        except ValueError as exc:
            area = float("inf")
            reason = f"Se conserva el acero elegido, pero no hay solucion de flexion para esta cara: {exc}"
        requirements.append((area, m, n, name, x, gd, gw))
    row = max(requirements, key=lambda r:r[0])
    required = row[0]
    provided = bar.area_cm2 / selected.spacing_m
    option = replace(selected, required_area_cm2_m=required, provided_area_cm2_m=provided,
                     is_compliant=isfinite(required) and provided + 1e-9 >= required,
                     is_recommended=False, crack_control_status=None)
    ld, _ = mtc_tension_development_length_cm(bar.diameter_cm, fy, fc,
        location_factor=params.development_location_factor,
        coating_factor=params.development_coating_factor,
        lightweight_factor=params.development_lightweight_factor,
        confinement_factor=params.development_confinement_factor,
        excess_reinforcement_factor=1.0)
    status = "OK" if option.is_compliant and development_available_m + 1e-9 >= ld/100 else "NO CUMPLE"
    _, m, n, name, x, gd, gw = row
    return InteriorCollisionFace(face, name, x, m, n, gd, gw, option, ld/100,
                                 development_available_m, status, reason)
