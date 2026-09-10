"""Interior barrier transfer through a continuous, unit-width deck strip.

This is an explicitly declared elastic strip model, not the A13.4 overhang
30-degree/0.40 approximation. Vertical reactions are deliverables for the
girder model, not an automatic verification of bearings or diaphragms.
"""

from dataclasses import dataclass
from itertools import product
from math import floor

from bridge_design.codes.mtc_2018 import mtc_tension_development_length_cm
from bridge_design.domain.rebar_catalog import (
    REINFORCING_BAR_CATALOG, ReinforcementSpacingOption,
)
from bridge_design.domain.reinforcement import flexural_steel_area_cm2
from bridge_design.domain.transverse_slab import (
    PointMoment, PointLoad, solve_load_case, transverse_load_placement_cases,
    _bending_moment_at,
)
from bridge_design.units.converters import kip_to_tn


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
                             f"ld={face.development_length_m:.3f} m, disponible={face.development_available_m:.3f} m: {face.status}.")
            else:
                lines.append("NO CUMPLE: sin alternativa del catalogo compatible con la demanda y el peralte.")
        lines.append(f"Corte: Vu={self.shear_demand_tn_m:.3f}, phi Vc={self.shear_capacity_tn_m:.3f} Tn/m; "
                     f"beta={self.shear_beta:.3f}: {self.shear_status}. "
                     f"Conexion barrera-losa: {self.connection_status}. Resultado local: {self.status}.")
        return tuple(lines) + self.notes


def _shear_at(x, segments, points, reactions):
    return (sum(r for s, r in reactions if s <= x)
            - sum(p.p_tn for p in points if p.position_m <= x)
            - sum(s.q_tn_m * max(0.0, min(x, s.end_m) - s.start_m) for s in segments))


def design_interior_collision(geometry, materials, live_loads, layout, barrier, params):
    """Design the continuous two-face reinforcement required for collision.

    The same reinforcement is specified across the interior deck; ordinary
    Strength/Service reinforcement remains mandatory. Each (M,N) pair is kept
    compatible. N is conservatively carried without reduction to the interior
    side; its horizontal support allocation needs a global in-plane model.
    """
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
    faces = tuple(_design_face(face, rows, geometry, materials, params) for face, rows in demands.items())
    from bridge_design.domain._cantilever_slab_checks import _concrete_shear_resistance_tn
    # General no-stirrup shear procedure; aggregate contribution conservatively set to zero.
    selected = [f.option for f in faces if f.option is not None]
    d = min((geometry.slab_thickness_m*100 - params.concrete_cover_cm - o.bar.diameter_cm/2 for o in selected), default=0)
    dv = max(.9*d, .72*geometry.slab_thickness_m*100)
    area = min((o.provided_area_cm2_m for o in selected), default=1e-9)
    epsilon = (max(maximum_moment*100000/dv, vu*1000) + vu*1000 + n*1000) / (2_000_000*area)
    sxe = min(80., max(12., (dv/2.54)*1.38/.63))
    beta = 4.8/(1+750*epsilon) * 51/(39+sxe)
    capacity = params.shear_resistance_factor * _concrete_shear_resistance_tn(
        materials.concrete.compressive_strength_kg_cm2, 100, dv, beta)
    shear_status = "OK" if selected and capacity >= vu else "NO CUMPLE"
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
    status = "OK" if connection_ok and shear_status == "OK" and all(f.status == "OK" for f in faces) else "NO CUMPLE"
    return InteriorCollisionDesign(tuple(cases), faces, force, length, moment, vu, capacity, beta,
        shear_status, connection_checks, connection, status, (
            "Casos horizontales y verticales independientes; gamma CT=1.0; DC=0.90/1.25, DW=0.65/1.50. "
            "La colision de barrera no se combina con LL/PL; el armado ordinario de Resistencia y Servicio se conserva.",
            "Armadura indicada: minimo TOTAL por colision en cada cara de la losa interior. Adoptar la MAYOR "
            "demanda entre este bloque y el diseno ordinario de la misma cara, no sumar areas. "
            "Disponer barras continuas con el anclaje indicado hacia ambos bordes; no agregar esta area al voladizo.",
            "Alcance: transferencia LOCAL barrera-losa y demandas verticales hacia vigas calculadas. "
            "La distribucion horizontal entre vigas, diafragmas y apoyos requiere el modelo global en planta; "
            "este resultado local no certifica ese sistema.",
        ))


def _design_face(face, rows, geometry, materials, params):
    fc, fy = materials.concrete.compressive_strength_kg_cm2, materials.steel.yield_strength_kg_cm2
    h = geometry.slab_thickness_m*100
    # For a fixed axial demand, steel increases monotonically with |M|.
    rows = [max((r for r in rows if r[1] == n), key=lambda r:r[0])
            for n in sorted({r[1] for r in rows})]
    candidates = []
    for i, bar in enumerate(REINFORCING_BAR_CATALOG):
        d = h - params.concrete_cover_cm - bar.diameter_cm/2
        if d <= h/2:
            continue
        requirements = []
        try:
            for m, n, name, x, gd, gw in rows:
                # FHWA 4.10: As(M)+N/fy, conservative for combined tension/flexure.
                area = flexural_steel_area_cm2(m, 100, d, fc, fy,
                                               phi=params.flexural_resistance_factor)
                area += n*1000/(min(params.flexural_resistance_factor, .75)*fy)
                requirements.append((max(area, params.shrinkage_temperature_ratio*100*h),
                                     m, n, name, x, gd, gw))
        except ValueError:
            continue
        controlling = max(requirements, key=lambda row: row[0])
        req = controlling[0]
        spacing = min(params.maximum_spacing_m, floor((bar.area_cm2/req+1e-12)/params.spacing_step_m)*params.spacing_step_m)
        if spacing < max(params.minimum_spacing_m, bar.diameter_cm/100 + .028575):
            continue
        option = ReinforcementSpacingOption(i+1, bar, spacing, req, bar.area_cm2/spacing, True, True)
        ld, _ = mtc_tension_development_length_cm(bar.diameter_cm, fy, fc,
            location_factor=params.development_location_factor,
            coating_factor=params.development_coating_factor,
            lightweight_factor=params.development_lightweight_factor,
            confinement_factor=params.development_confinement_factor,
            excess_reinforcement_factor=1.0)
        # Full-width bars developed outside the interior design region.
        available = geometry.overhang_m - params.concrete_cover_cm/100
        status = "OK" if available+1e-9 >= ld/100 else "NO CUMPLE"
        candidates.append((option, controlling, ld/100, available, status))
    if not candidates:
        row = max(rows, key=lambda r:r[0])
        return InteriorCollisionFace(face, row[2], row[3], row[0], row[1], row[4], row[5], None, 0, 0, "NO CUMPLE")
    option, row, ld, available, status = min(candidates, key=lambda c:(c[4] != "OK", c[0].provided_area_cm2_m))
    _, m, n, name, x, gd, gw = row
    return InteriorCollisionFace(face, name, x, m, n, gd, gw, option, ld, available, status)
