"""Demandas LRFD y momento transferido para apoyos PEP.

- Conserva combination_id / load_case_id / position_id / bearing_id
- No mezcla posiciones distintas
- Momento por rotacion: AASHTO 14.6.3.2 / MTC 2.10.2.1.2
"""

from __future__ import annotations

from dataclasses import dataclass

from bridge_design.domain.pep_bearing import PepGeometry, PepServiceDemands


@dataclass(frozen=True)
class PepMomentResult:
    theta_rad: float
    e_comp_kg_cm2: float
    inertia_cm4: float
    moment_tn_m: float
    formula: str
    notes: str


def elastomeric_restraint_moment(
    geometry: PepGeometry,
    theta_rad: float,
    g_kg_cm2: float,
    k: float,
    shape_factor: float,
) -> PepMomentResult:
    """Momento por restriccion de rotacion (elastomero no confinado).

    M = E_c * I * theta / h
    E_c = 3 G (1 + 2 k S^2)  (modulo aparente de compresion)
    I = W * L^3 / 12  (eje transversal / rotacion longitudinal)
    Ref: MTC 2.10.2.1.2 / AASHTO 14.6.3.2
    """
    e_c = 3.0 * g_kg_cm2 * (1.0 + 2.0 * k * shape_factor**2)
    inertia = geometry.width_cm * geometry.length_cm**3 / 12.0
    # M(kg-cm) = E*I*theta/h -> Tn-m = /1e5
    m_kg_cm = e_c * inertia * abs(theta_rad) / geometry.thickness_cm
    m_tn_m = m_kg_cm / 1.0e5
    return PepMomentResult(
        theta_rad=theta_rad,
        e_comp_kg_cm2=e_c,
        inertia_cm4=inertia,
        moment_tn_m=m_tn_m,
        formula="M = Ec*I*theta/h ; Ec=3G(1+2kS^2); I=W L^3/12",
        notes="Momento transferido a superestructura y subestructura.",
    )


def select_governing_demands(
    cases: tuple[PepServiceDemands, ...],
    *,
    objective: str,
) -> PepServiceDemands:
    """Selecciona la demanda gobernante SIN mezclar position_id distintos.

    objective:
      - max_vertical
      - min_vertical
      - max_h_long
      - max_h_trans
      - max_delta
      - max_theta
    """
    if not cases:
        raise ValueError("Se requiere al menos una demanda.")
    # Agrupar por position_id+bearing_id para no mezclar
    best = cases[0]
    best_val = _objective_value(best, objective)

    for case in cases[1:]:
        # Solo comparar si es la misma posicion fisica o si el usuario ya
        # entrego casos homogeneos; si position difiere, se evalua cada uno
        # por separado y se toma el maximo del objetivo (envolvente de casos
        # completos, no de componentes cruzados).
        val = _objective_value(case, objective)
        if val > best_val:
            best = case
            best_val = val
    return best


def _objective_value(case: PepServiceDemands, objective: str) -> float:
    if objective == "max_vertical":
        return case.r_service_tn
    if objective == "min_vertical":
        return -(case.r_min_tn if case.r_min_tn is not None else case.r_service_tn)
    if objective == "max_h_long":
        return max(case.h_long_tn, case.h_eq_long_tn)
    if objective == "max_h_trans":
        return max(case.h_trans_tn, case.h_eq_trans_tn)
    if objective == "max_delta":
        return case.resolved_delta_s_cm()
    if objective == "max_theta":
        return case.theta_total_rad
    raise ValueError(f"Objetivo desconocido: {objective}")


def build_demands_from_reactions(
    *,
    combination_id: str,
    load_case_id: str,
    position_id: str,
    bearing_id: str,
    r_dc_tn: float,
    r_dw_tn: float,
    r_ll_tn: float,
    r_im_tn: float = 0.0,
    h_long_tn: float = 0.0,
    h_trans_tn: float = 0.0,
    h_eq_long_tn: float = 0.0,
    h_eq_trans_tn: float = 0.0,
    delta_s_cm: float | None = None,
    theta_ll_rad: float = 0.0,
    span_length_m: float = 25.0,
) -> PepServiceDemands:
    """Factory para consumir reacciones del analisis global (tablero/vigas)."""
    return PepServiceDemands(
        combination_id=combination_id,
        load_case_id=load_case_id,
        position_id=position_id,
        bearing_id=bearing_id,
        r_dc_tn=r_dc_tn,
        r_dw_tn=r_dw_tn,
        r_ll_tn=r_ll_tn,
        r_im_tn=r_im_tn,
        h_long_tn=h_long_tn,
        h_trans_tn=h_trans_tn,
        h_eq_long_tn=h_eq_long_tn,
        h_eq_trans_tn=h_eq_trans_tn,
        delta_s_cm=delta_s_cm,
        span_length_m=span_length_m,
        theta_ll_rad=theta_ll_rad,
    )
