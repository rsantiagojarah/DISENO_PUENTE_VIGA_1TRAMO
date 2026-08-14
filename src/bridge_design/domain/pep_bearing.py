"""Diseno de apoyos elastomericos PEP (sin zunchos internos) - Metodo A.

APOYO FIJO y MOVIL_PEP_CORTE.
Placas superior/inferior son externas y NO forman parte de h.

Referencias:
- MTC 2018 2.10 / 2.10.4
- AASHTO LRFD 14.7.5, 14.7.6, 14.6.3.1, 14.8.3, 5.7.5
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import ceil, sqrt
from typing import Literal

from bridge_design.domain.elastomeric_bearing import ElastomerGrade, HardnessShoreA
from bridge_design.domain.pep_strain_curves import compressive_strain_from_curve
from bridge_design.units.converters import ksi_to_kg_cm2
from bridge_design.validation.input_validators import (
    require_non_negative,
    require_positive,
    require_range,
)

# AASHTO 14.7.6.3.2 limites para PEP (NO usar 1.25 GS / 1.25 ksi)
SIGMA_S_MAX_PEP_KSI = 0.80
SIGMA_S_MAX_PEP_KG_CM2 = ksi_to_kg_cm2(SIGMA_S_MAX_PEP_KSI)
MU_FRICTION_DEFAULT = 0.20
ALPHA_CONCRETE_PER_C = 10.8e-6
GAMMA_TU_DEFAULT = 1.2

PepBearingType = Literal["FIJO", "MOVIL_PEP_CORTE"]
FixedRestraintLoadPath = Literal["RESTRICCION_EXTERNA", "CORTE_EN_ELASTOMERO"]
EpsilonSource = Literal["manual", "curva_aashto", "estimacion_analitica"]
DesignMode = Literal["VERIFICAR", "DISENAR"]
ClimateZone = Literal["costa", "sierra", "selva"]

PEP_THICKNESSES_CM = (1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0)
PEP_PLAN_STEP_CM = 5.0
PLATE_MARGIN_CM = 15.0

PENDING = "PENDIENTE"
NA = "N.A."


@dataclass(frozen=True)
class PepCheck:
    name: str
    articulo_mtc: str
    articulo_aashto: str
    estado_limite: str
    combination_id: str
    formula: str
    substitution: str
    demand: float
    limit: float
    unit: str
    status: str
    notes: str = ""

    @property
    def ratio(self) -> float | None:
        if self.limit == 0:
            return None
        return self.demand / self.limit

    @property
    def ok(self) -> bool:
        return self.status in {"OK", NA}


@dataclass(frozen=True)
class PepGeometry:
    length_cm: float
    width_cm: float
    thickness_cm: float

    def __post_init__(self) -> None:
        require_positive(self.length_cm, "L")
        require_positive(self.width_cm, "W")
        require_positive(self.thickness_cm, "h")

    @property
    def area_cm2(self) -> float:
        return self.length_cm * self.width_cm

    @property
    def shape_factor(self) -> float:
        """S = LW / [2 h (L+W)] - AASHTO 14.7.5.1-1; una sola capa."""
        return self.area_cm2 / (
            2.0 * self.thickness_cm * (self.length_cm + self.width_cm)
        )


@dataclass(frozen=True)
class PepTemperature:
    t_sup_c: float
    t_inf_c: float
    t_install_c: float

    def __post_init__(self) -> None:
        if self.t_sup_c < self.t_inf_c:
            raise ValueError("t_sup debe ser >= t_inf.")

    @property
    def contraction_delta_t_c(self) -> float:
        return max(self.t_install_c - self.t_inf_c, 0.0)

    @classmethod
    def mtc_default(cls, zone: ClimateZone, t_install_c: float = 20.0) -> "PepTemperature":
        defaults = {"costa": (40.0, 0.0), "sierra": (35.0, -10.0), "selva": (50.0, 10.0)}
        t_sup, t_inf = defaults[zone]
        return cls(t_sup_c=t_sup, t_inf_c=t_inf, t_install_c=t_install_c)


@dataclass(frozen=True)
class PepServiceDemands:
    """Demandas por apoyo conservando identificadores de combinacion/caso."""

    combination_id: str
    load_case_id: str
    position_id: str
    bearing_id: str
    r_dc_tn: float
    r_dw_tn: float
    r_ll_tn: float
    r_im_tn: float = 0.0
    r_min_tn: float | None = None
    h_long_tn: float = 0.0
    h_trans_tn: float = 0.0
    h_eq_long_tn: float = 0.0
    h_eq_trans_tn: float = 0.0
    delta_plus_cm: float | None = None
    delta_minus_cm: float | None = None
    delta_s_cm: float | None = None
    theta_initial_rad: float = 0.0
    theta_dc_rad: float = 0.0
    theta_dw_rad: float = 0.0
    theta_ll_rad: float = 0.0
    theta_other_rad: float = 0.0
    span_length_m: float = 25.0
    shrinkage_cm: float = 0.0
    prestress_cm: float = 0.0
    creep_cm: float = 0.0
    settlement_cm: float = 0.0
    other_perm_cm: float = 0.0
    gamma_tu: float = GAMMA_TU_DEFAULT
    alpha_per_c: float = ALPHA_CONCRETE_PER_C
    temperature: PepTemperature | None = None

    def __post_init__(self) -> None:
        require_positive(self.r_dc_tn, "R_DC")
        require_non_negative(self.r_dw_tn, "R_DW")
        require_non_negative(self.r_ll_tn, "R_LL")
        require_non_negative(self.r_im_tn, "R_IM")
        require_non_negative(self.h_long_tn, "H_long")
        require_non_negative(self.h_trans_tn, "H_trans")
        require_non_negative(self.h_eq_long_tn, "H_EQ_long")
        require_non_negative(self.h_eq_trans_tn, "H_EQ_trans")
        require_positive(self.span_length_m, "luz")
        require_positive(self.gamma_tu, "gamma_TU")

    @property
    def r_service_tn(self) -> float:
        return self.r_dc_tn + self.r_dw_tn + self.r_ll_tn + self.r_im_tn

    @property
    def r_permanent_tn(self) -> float:
        return self.r_dc_tn + self.r_dw_tn

    @property
    def r_live_tn(self) -> float:
        return self.r_ll_tn + self.r_im_tn

    @property
    def r_uplift_tn(self) -> float:
        if self.r_min_tn is None:
            return 0.0
        return max(-self.r_min_tn, 0.0)

    @property
    def theta_total_rad(self) -> float:
        return (
            self.theta_initial_rad
            + self.theta_dc_rad
            + self.theta_dw_rad
            + self.theta_ll_rad
            + self.theta_other_rad
        )

    def resolved_delta_s_cm(self) -> float:
        if self.delta_s_cm is not None:
            return abs(self.delta_s_cm)
        if self.delta_plus_cm is not None or self.delta_minus_cm is not None:
            plus = abs(self.delta_plus_cm or 0.0)
            minus = abs(self.delta_minus_cm or 0.0)
            return max(plus, minus)
        temp = self.temperature or PepTemperature.mtc_default("costa")
        length_cm = self.span_length_m * 100.0
        d_temp = self.alpha_per_c * length_cm * temp.contraction_delta_t_c
        d_perm = (
            d_temp
            + self.shrinkage_cm
            + self.prestress_cm
            + self.creep_cm
            + self.settlement_cm
            + self.other_perm_cm
        )
        return self.gamma_tu * d_perm


@dataclass(frozen=True)
class PepExternalPlate:
    length_cm: float
    width_cm: float
    thickness_cm: float
    fy_kg_cm2: float = 2530.0
    fu_kg_cm2: float = 4080.0

    def __post_init__(self) -> None:
        require_positive(self.length_cm, "L placa")
        require_positive(self.width_cm, "W placa")
        require_positive(self.thickness_cm, "t placa")
        require_positive(self.fy_kg_cm2, "Fy placa")
        require_positive(self.fu_kg_cm2, "Fu placa")


@dataclass(frozen=True)
class PepAnchorGroup:
    n_bolts: int
    diameter_cm: float
    fy_kg_cm2: float
    fu_kg_cm2: float
    embedment_cm: float
    layout_note: str = "usuario"
    # Coordenadas opcionales (cm) respecto al centro del PEP/placa.
    # Si vacio, se genera layout rectangular fuera del PEP.
    coordinates_cm: tuple[tuple[float, float], ...] = ()

    def __post_init__(self) -> None:
        if self.n_bolts < 1:
            raise ValueError("n_bolts debe ser >= 1.")
        require_positive(self.diameter_cm, "diametro perno")
        require_positive(self.fy_kg_cm2, "Fy perno")
        require_positive(self.fu_kg_cm2, "Fu perno")
        require_positive(self.embedment_cm, "longitud anclaje")
        if self.coordinates_cm and len(self.coordinates_cm) != self.n_bolts:
            raise ValueError("coordinates_cm debe tener n_bolts pares (x,y).")


@dataclass(frozen=True)
class PepConcreteSupport:
    fc_kg_cm2: float
    support_area_cm2: float | None = None
    phi: float = 0.70

    def __post_init__(self) -> None:
        require_positive(self.fc_kg_cm2, "f'c")
        require_positive(self.phi, "phi")


@dataclass(frozen=True)
class PepBearingInputs:
    tipo_apoyo: PepBearingType
    geometry: PepGeometry
    demands: PepServiceDemands
    hardness: HardnessShoreA = 60
    g_specified_kg_cm2: float | None = None
    fixed_restraint_load_path: FixedRestraintLoadPath = "RESTRICCION_EXTERNA"
    epsilon_source: EpsilonSource = "estimacion_analitica"
    epsilon_permanent: float | None = None
    epsilon_total: float | None = None
    friction_coefficient: float = MU_FRICTION_DEFAULT
    site_acceleration_as: float = 0.20
    seismic_pga: float | None = None
    seismic_fpga: float | None = None
    seismic_zone: int = 1
    upper_plate: PepExternalPlate | None = None
    lower_plate: PepExternalPlate | None = None
    anchors: PepAnchorGroup | None = None
    concrete_support: PepConcreteSupport | None = None
    bolts_through_pep_exception: bool = False
    mode: DesignMode = "VERIFICAR"
    design_plates_auto: bool = False
    design_anchors_auto: bool = False
    demand_cases: tuple[PepServiceDemands, ...] = ()

    def __post_init__(self) -> None:
        if self.hardness not in (50, 60, 70):
            raise ValueError("Dureza Shore A debe ser 50, 60 o 70.")
        require_range(float(self.seismic_zone), "zona sismica", 1, 4)
        require_non_negative(self.site_acceleration_as, "As")
        if self.seismic_pga is not None:
            require_non_negative(self.seismic_pga, "PGA")
        if self.seismic_fpga is not None:
            require_positive(self.seismic_fpga, "Fpga")
        require_positive(self.friction_coefficient, "mu")
        if self.g_specified_kg_cm2 is not None:
            require_positive(self.g_specified_kg_cm2, "G especificado")
        if self.epsilon_source == "manual":
            if self.epsilon_permanent is None or self.epsilon_total is None:
                raise ValueError("Con epsilon_source=manual se requieren epsilon_permanent y epsilon_total.")


@dataclass(frozen=True)
class PepBearingDesignResult:
    inputs: PepBearingInputs
    grade: ElastomerGrade
    g_for_capacity_kg_cm2: float
    g_for_force_kg_cm2: float
    g_capacity_reason: str
    g_force_reason: str
    shape_factor: float
    area_cm2: float
    sigma_s_kg_cm2: float
    sigma_perm_kg_cm2: float
    sigma_live_kg_cm2: float
    sigma_gs_kg_cm2: float
    sigma_adm_kg_cm2: float
    delta_s_cm: float
    epsilon_permanent: float
    epsilon_total: float
    epsilon_note: str
    delta_dead_cm: float
    delta_live_cm: float
    delta_creep_cm: float
    delta_long_term_cm: float
    h_pad_service_tn: float
    friction_capacity_tn: float
    h_fixed_long_tn: float
    h_fixed_trans_tn: float
    h_eq_gov_tn: float
    h_anchor_report_tn: float
    theta_total_rad: float
    moment_tn_m: float
    moment_formula: str
    checks: tuple[PepCheck, ...]
    designation: str
    pending_components: tuple[str, ...]

    @property
    def pep_core_ok(self) -> bool:
        """Cumplimiento del pad elastomero (sin placas/pernos/soldaduras)."""
        return _pep_core_ok_from_checks(self.checks)

    @property
    def overall_ok(self) -> bool:
        return all(check.ok for check in self.checks) and not self.pending_components


def _pep_core_ok_from_checks(checks: tuple[PepCheck, ...] | list[PepCheck]) -> bool:
    core_names = {
        "Compresion sigma_s <= G*S",
        "Compresion sigma_s <= 0.80 ksi",
        "Limite gobernante de compresion",
        "Deflexion capa <= 0.09 h",
        "Cortante h >= 2 Delta_s",
        "Estabilidad h <= L/3",
        "Estabilidad h <= W/3",
    }
    for check in checks:
        if check.name in core_names and check.status not in {"OK", NA}:
            return False
    return True


def pep_grade(hardness: HardnessShoreA, g_specified: float | None = None) -> ElastomerGrade:
    grade = ElastomerGrade.from_hardness(hardness)
    if g_specified is None:
        return grade
    # Si se especifica G, se usa ese valor como diseno (min=max=G) y creep de la dureza.
    return ElastomerGrade(
        hardness=hardness,
        g_min_kg_cm2=g_specified,
        g_max_kg_cm2=g_specified,
        creep_ratio=grade.creep_ratio,
        shape_factor_k=grade.shape_factor_k,
    )


def compressive_strain_estimate(
    sigma_kg_cm2: float,
    g_kg_cm2: float,
    shape_factor: float,
    k: float,
) -> float:
    """Estimacion analitica eps = sigma / [3G(1+2kS^2)].

    No sustituye la Fig. C14.7.6.3.3-1; se reporta como estimacion.
    """
    modulus = 3.0 * g_kg_cm2 * (1.0 + 2.0 * k * shape_factor**2)
    return sigma_kg_cm2 / modulus


def _status_le(demand: float, limit: float) -> str:
    return "OK" if demand <= limit + 1e-9 else "NO"


def design_pep_bearing(inputs: PepBearingInputs) -> PepBearingDesignResult:
    """Verifica o disena un apoyo PEP fijo/movil por Metodo A."""
    if inputs.mode == "DISENAR":
        return _auto_design_pep(inputs)
    return _verify_pep(inputs)


def _verify_pep(inputs: PepBearingInputs) -> PepBearingDesignResult:
    geom = inputs.geometry
    dem = inputs.demands
    grade = pep_grade(inputs.hardness, inputs.g_specified_kg_cm2)
    g_cap = grade.g_min_kg_cm2
    g_force = grade.g_max_kg_cm2
    s = geom.shape_factor
    area = geom.area_cm2
    combo = dem.combination_id

    r_kg = dem.r_service_tn * 1000.0
    r_perm_kg = dem.r_permanent_tn * 1000.0
    r_live_kg = dem.r_live_tn * 1000.0
    sigma_s = r_kg / area
    sigma_perm = r_perm_kg / area
    sigma_ll = r_live_kg / area
    sigma_gs = g_cap * s
    sigma_adm = min(sigma_gs, SIGMA_S_MAX_PEP_KG_CM2)

    delta_s = dem.resolved_delta_s_cm()
    if inputs.tipo_apoyo == "FIJO" and inputs.fixed_restraint_load_path == "RESTRICCION_EXTERNA":
        # Traslacion libre impedida por restriccion externa; no dimensiona h=2Ds.
        delta_for_shear_check = 0.0
        shear_applicable = False
    else:
        delta_for_shear_check = delta_s
        shear_applicable = True

    if inputs.epsilon_source == "manual":
        eps_perm = float(inputs.epsilon_permanent)
        eps_tot = float(inputs.epsilon_total)
        eps_note = "DATO DE CURVA AASHTO / FABRICANTE (ingreso manual)"
    elif inputs.epsilon_source == "curva_aashto":
        look_p = compressive_strain_from_curve(inputs.hardness, s, sigma_perm)
        look_t = compressive_strain_from_curve(inputs.hardness, s, sigma_s)
        eps_perm = look_p.epsilon
        eps_tot = look_t.epsilon
        eps_note = look_t.source + (" [extrapolado]" if look_t.extrapolated else "")
    else:
        eps_perm = compressive_strain_estimate(sigma_perm, g_cap, s, grade.shape_factor_k)
        eps_tot = compressive_strain_estimate(sigma_s, g_cap, s, grade.shape_factor_k)
        eps_note = (
            "ESTIMACION ANALITICA eps=sigma/[3G(1+2kS^2)]; "
            "preferible fuente_epsilon=curva_aashto o manual"
        )

    from bridge_design.domain.pep_demands import elastomeric_restraint_moment

    moment = elastomeric_restraint_moment(
        geom, dem.theta_total_rad, g_cap, grade.shape_factor_k, s
    )

    delta_dead = eps_perm * geom.thickness_cm
    delta_total = eps_tot * geom.thickness_cm
    delta_live = max(delta_total - delta_dead, 0.0)
    delta_creep = grade.creep_ratio * delta_dead
    delta_lt = delta_dead + delta_creep

    h_pad = (g_force * area * delta_s / geom.thickness_cm) / 1000.0 if geom.thickness_cm else 0.0
    friction = inputs.friction_coefficient * dem.r_dc_tn
    h_fixed_long = dem.h_long_tn if inputs.tipo_apoyo == "FIJO" else 0.0
    h_fixed_trans = dem.h_trans_tn if inputs.tipo_apoyo == "FIJO" else 0.0
    h_eq = max(dem.h_eq_long_tn, dem.h_eq_trans_tn)
    if h_eq <= 0.0:
        h_eq = inputs.site_acceleration_as * dem.r_permanent_tn

    # Criterio reportado para anclaje de apoyo movil (interpretacion MTC 2.10.4.3.8 /
    # 2.10.3.3.7 + capacidad horizontal del pad/friccion). No reduce H del fijo.
    if inputs.tipo_apoyo == "MOVIL_PEP_CORTE":
        horiz_cap = max(h_pad, friction)
        h_anchor = max(h_eq - horiz_cap, 0.0)
    else:
        horiz_cap = 0.0
        h_anchor = max(h_eq, h_fixed_long, h_fixed_trans)

    checks: list[PepCheck] = []
    checks.append(
        PepCheck(
            name="Compresion sigma_s <= G*S",
            articulo_mtc="MTC 2.10.4.3.2",
            articulo_aashto="AASHTO 14.7.6.3.2 (PEP: 1.00GS)",
            estado_limite="Servicio",
            combination_id=combo,
            formula="sigma_s = R/A ; sigma_s <= Gmin*S",
            substitution=(
                f"{r_kg:.0f}/{area:.1f}={sigma_s:.2f} ; "
                f"{g_cap:.2f}*{s:.3f}={sigma_gs:.2f}"
            ),
            demand=sigma_s,
            limit=sigma_gs,
            unit="kg/cm2",
            status=_status_le(sigma_s, sigma_gs),
            notes="Gmin usado para capacidad (mas desfavorable). NO se usa 1.25GS.",
        )
    )
    checks.append(
        PepCheck(
            name="Compresion sigma_s <= 0.80 ksi",
            articulo_mtc="MTC 2.10.4.3.2",
            articulo_aashto="AASHTO 14.7.6.3.2 (PEP: 0.80 ksi)",
            estado_limite="Servicio",
            combination_id=combo,
            formula="sigma_s <= 0.80 ksi",
            substitution=f"{sigma_s:.2f} <= {SIGMA_S_MAX_PEP_KG_CM2:.2f} (=0.80 ksi)",
            demand=sigma_s,
            limit=SIGMA_S_MAX_PEP_KG_CM2,
            unit="kg/cm2",
            status=_status_le(sigma_s, SIGMA_S_MAX_PEP_KG_CM2),
            notes="NO se usa 1.25 ksi (eso es elastomero zunchado).",
        )
    )
    checks.append(
        PepCheck(
            name="Limite gobernante de compresion",
            articulo_mtc="MTC 2.10.4.3.2",
            articulo_aashto="AASHTO 14.7.6.3.2",
            estado_limite="Servicio",
            combination_id=combo,
            formula="sigma_adm = min(G*S, 0.80ksi)",
            substitution=f"min({sigma_gs:.2f}, {SIGMA_S_MAX_PEP_KG_CM2:.2f})={sigma_adm:.2f}",
            demand=sigma_s,
            limit=sigma_adm,
            unit="kg/cm2",
            status=_status_le(sigma_s, sigma_adm),
        )
    )
    checks.append(
        PepCheck(
            name="Deflexion capa <= 0.09 h",
            articulo_mtc="MTC 2.10.4.3.3",
            articulo_aashto="AASHTO 14.7.6.3.3",
            estado_limite="Servicio",
            combination_id=combo,
            formula="delta_total = eps_total*h <= 0.09*h",
            substitution=f"{eps_tot:.5f}*{geom.thickness_cm:.2f} <= 0.09*{geom.thickness_cm:.2f}",
            demand=delta_total,
            limit=0.09 * geom.thickness_cm,
            unit="cm",
            status=_status_le(delta_total, 0.09 * geom.thickness_cm),
            notes=eps_note,
        )
    )
    checks.append(
        PepCheck(
            name="Creep (informativo + LL+creep)",
            articulo_mtc="MTC 2.10.4.3.3",
            articulo_aashto="AASHTO 14.7.5.3.6-3 / Tabla 14.7.6.2-1",
            estado_limite="Servicio",
            combination_id=combo,
            formula="delta_creep = a_cr * delta_DC",
            substitution=f"{grade.creep_ratio:.2f}*{delta_dead:.4f}",
            demand=delta_creep,
            limit=delta_creep,
            unit="cm",
            status="OK",
            notes=f"delta_DC={delta_dead:.4f}; delta_lt={delta_lt:.4f}; delta_LL={delta_live:.4f}",
        )
    )

    if shear_applicable:
        checks.append(
            PepCheck(
                name="Cortante h >= 2 Delta_s",
                articulo_mtc="MTC 2.10.4.3.4",
                articulo_aashto="AASHTO 14.7.6.3.4-1",
                estado_limite="Servicio",
                combination_id=combo,
                formula="h >= 2*Delta_s ; gamma=Delta_s/h <= 0.50",
                substitution=(
                    f"{geom.thickness_cm:.3f} >= 2*{delta_for_shear_check:.3f} ; "
                    f"gamma={delta_for_shear_check / geom.thickness_cm:.3f}"
                ),
                demand=2.0 * delta_for_shear_check,
                limit=geom.thickness_cm,
                unit="cm",
                status=_status_le(2.0 * delta_for_shear_check, geom.thickness_cm),
            )
        )
    else:
        checks.append(
            PepCheck(
                name="Cortante por movimiento termico",
                articulo_mtc="MTC 2.10.4.3.4",
                articulo_aashto="AASHTO 14.7.6.3.4",
                estado_limite="Servicio",
                combination_id=combo,
                formula="N.A. (restriccion externa; Delta libre = 0)",
                substitution=f"fixed_restraint_load_path={inputs.fixed_restraint_load_path}",
                demand=0.0,
                limit=0.0,
                unit="-",
                status=NA,
                notes="El PEP fijo no se dimensiona por h>=2Ds si la restriccion toma toda H.",
            )
        )

    checks.append(
        PepCheck(
            name="Estabilidad h <= L/3",
            articulo_mtc="MTC 2.10.4.3.6",
            articulo_aashto="AASHTO 14.7.6.3.6",
            estado_limite="Servicio",
            combination_id=combo,
            formula="h <= L/3",
            substitution=f"{geom.thickness_cm:.3f} <= {geom.length_cm:.2f}/3",
            demand=geom.thickness_cm,
            limit=geom.length_cm / 3.0,
            unit="cm",
            status=_status_le(geom.thickness_cm, geom.length_cm / 3.0),
        )
    )
    checks.append(
        PepCheck(
            name="Estabilidad h <= W/3",
            articulo_mtc="MTC 2.10.4.3.6",
            articulo_aashto="AASHTO 14.7.6.3.6",
            estado_limite="Servicio",
            combination_id=combo,
            formula="h <= W/3",
            substitution=f"{geom.thickness_cm:.3f} <= {geom.width_cm:.2f}/3",
            demand=geom.thickness_cm,
            limit=geom.width_cm / 3.0,
            unit="cm",
            status=_status_le(geom.thickness_cm, geom.width_cm / 3.0),
        )
    )
    checks.append(
        PepCheck(
            name="Rotacion Metodo A (implicita)",
            articulo_mtc="MTC 2.10.4.3.5",
            articulo_aashto="AASHTO 14.7.6.3.5 / C14.7.6.1",
            estado_limite="Servicio",
            combination_id=combo,
            formula="theta_s registrada; capacidad implicita Metodo A",
            substitution=(
                f"theta={dem.theta_total_rad:.6f} rad "
                f"(ini={dem.theta_initial_rad:.6f}+DC={dem.theta_dc_rad:.6f}+"
                f"DW={dem.theta_dw_rad:.6f}+LL={dem.theta_ll_rad:.6f}+otros={dem.theta_other_rad:.6f})"
            ),
            demand=dem.theta_total_rad,
            limit=dem.theta_total_rad,
            unit="rad",
            status="OK",
            notes="No se usan ecuaciones de rotacion del Metodo B.",
        )
    )

    if dem.r_uplift_tn > 0.0:
        checks.append(
            PepCheck(
                name="Uplift / levantamiento",
                articulo_mtc="MTC 2.10 / anclaje",
                articulo_aashto="AASHTO 14.8",
                estado_limite="Resistencia / Evento Extremo",
                combination_id=combo,
                formula="si Rmin<0 => anclar T_uplift",
                substitution=f"Rmin={dem.r_min_tn}; T_uplift={dem.r_uplift_tn:.3f} Tn",
                demand=dem.r_uplift_tn,
                limit=dem.r_uplift_tn,
                unit="Tn",
                status="OK",
                notes="Demanda de uplift transferida al diseno de pernos/anclaje al concreto.",
            )
        )
    else:
        checks.append(
            PepCheck(
                name="Uplift / levantamiento",
                articulo_mtc="MTC 2.10 / anclaje",
                articulo_aashto="AASHTO 14.8",
                estado_limite="Resistencia / Evento Extremo",
                combination_id=combo,
                formula="Rmin >= 0 => sin uplift",
                substitution=f"Rmin={dem.r_min_tn if dem.r_min_tn is not None else 'no ingresado (se asume >=0)'}",
                demand=0.0,
                limit=0.0,
                unit="Tn",
                status="OK",
            )
        )

    if inputs.tipo_apoyo == "FIJO":
        checks.append(
            PepCheck(
                name="Restriccion fija longitudinal 100% H",
                articulo_mtc="MTC 2.10.4.3.8 / 2.10.3.3.7",
                articulo_aashto="AASHTO 14.8",
                estado_limite="Resistencia / Evento Extremo",
                combination_id=combo,
                formula="H_restriccion_long = H_long (+ EE)",
                substitution=f"H_long={h_fixed_long:.3f}; H_EQ_long={dem.h_eq_long_tn:.3f}",
                demand=max(h_fixed_long, dem.h_eq_long_tn),
                limit=max(h_fixed_long, dem.h_eq_long_tn),
                unit="Tn",
                status="OK",
                notes="Demanda 100% H transferida a placas/pernos/anclaje. NO se reduce por friccion.",
            )
        )
        checks.append(
            PepCheck(
                name="Restriccion fija transversal 100% H",
                articulo_mtc="MTC 2.10.4.3.8 / 2.10.3.3.7",
                articulo_aashto="AASHTO 14.8",
                estado_limite="Resistencia / Evento Extremo",
                combination_id=combo,
                formula="H_restriccion_trans = H_trans (+ EE)",
                substitution=f"H_trans={h_fixed_trans:.3f}; H_EQ_trans={dem.h_eq_trans_tn:.3f}",
                demand=max(h_fixed_trans, dem.h_eq_trans_tn),
                limit=max(h_fixed_trans, dem.h_eq_trans_tn),
                unit="Tn",
                status="OK",
                notes="Demanda 100% H transferida a placas/pernos/anclaje.",
            )
        )
    else:
        checks.append(
            PepCheck(
                name="Fuerza H_pad por corte del PEP",
                articulo_mtc="MTC 2.10.2.1.1",
                articulo_aashto="AASHTO 14.6.3.1",
                estado_limite="Servicio",
                combination_id=combo,
                formula="H = Gmax*A*Delta_s/h",
                substitution=f"{g_force:.2f}*{area:.1f}*{delta_s:.3f}/{geom.thickness_cm:.3f}/1000",
                demand=h_pad,
                limit=h_pad,
                unit="Tn",
                status="OK",
                notes="Gmax maximiza la fuerza horizontal transferida.",
            )
        )
        friction_ok = h_pad <= friction + 1e-9
        checks.append(
            PepCheck(
                name="Friccion vs Hu servicio",
                articulo_mtc="MTC anclaje apoyos",
                articulo_aashto="AASHTO 14.8.3 / C14.8.3.1",
                estado_limite="Servicio",
                combination_id=combo,
                formula="si Hu > mu*PDC => anclar",
                substitution=f"Hu={h_pad:.3f}; mu*PDC={friction:.3f}",
                demand=h_pad,
                limit=max(friction, h_pad),
                unit="Tn",
                status="OK",
                notes=(
                    "mu=0.20 tipico C14.8.3.1 cuando la superficie es limpia concreto/acero."
                    + (
                        " Hu <= friccion: sin anclaje por servicio."
                        if friction_ok
                        else " Hu excede friccion: demanda transferida a anclajes."
                    )
                ),
            )
        )

        # Criterio EE movil (MTC 2.10.4.3.8 / 14.8.3): anclar el exceso sobre
        # capacidad horizontal admitida (pad por corte o friccion, la mayor).
        ee_ok = h_eq <= horiz_cap + 1e-9
        checks.append(
            PepCheck(
                name="Evento extremo / anclaje movil",
                articulo_mtc="MTC 2.10.4.3.8 / 2.10.3.3.7",
                articulo_aashto="AASHTO 3.10.9 / 14.8.3",
                estado_limite="Evento Extremo",
                combination_id=combo,
                formula="H_anchor_req = max(H_EE - max(H_pad, Ff), 0)",
                substitution=(
                    f"H_EE={h_eq:.3f}; H_pad={h_pad:.3f}; Ff={friction:.3f}; "
                    f"H_anchor_req={h_anchor:.3f}"
                ),
                demand=h_eq,
                limit=horiz_cap if ee_ok else h_eq,
                unit="Tn",
                status="OK" if ee_ok else "OK",
                notes=(
                    "Si H_anchor_req>0, la demanda se transfiere al diseno de pernos/anclaje. "
                    f"H_anchor_req={h_anchor:.3f} Tn."
                ),
            )
        )

    checks.append(
        PepCheck(
            name="Momento transferido por rotacion",
            articulo_mtc="MTC 2.10.2.1.2",
            articulo_aashto="AASHTO 14.6.3.2",
            estado_limite="Servicio / Resistencia",
            combination_id=combo,
            formula=moment.formula,
            substitution=(
                f"Ec={moment.e_comp_kg_cm2:.1f}; I={moment.inertia_cm4:.1f}; "
                f"theta={moment.theta_rad:.6f}; h={geom.thickness_cm:.2f}"
            ),
            demand=moment.moment_tn_m,
            limit=moment.moment_tn_m,
            unit="Tn-m",
            status="OK",
            notes=moment.notes,
        )
    )

    # --- Aparato completo: placas / pernos / soldadura / anclaje ---
    from bridge_design.domain.pep_steel_components import (
        BoltCoordinate,
        ComponentDemands,
        PepAnchorDetail,
        auto_design_anchors,
        auto_design_plate,
        default_bolt_layout,
        verify_bolts_and_welds,
        verify_concrete_anchorage,
        verify_plate,
    )

    pending: list[str] = []
    upper = inputs.upper_plate
    lower = inputs.lower_plate
    anchors_in = inputs.anchors

    h_for_anchors = (
        max(h_fixed_long, h_fixed_trans, h_eq, h_anchor)
        if inputs.tipo_apoyo == "FIJO"
        else max(h_anchor, h_eq if h_eq > horiz_cap else 0.0, 0.0)
    )
    if inputs.tipo_apoyo == "MOVIL_PEP_CORTE":
        # Direccion gobernante del exceso de anclaje / Hu
        if dem.h_eq_trans_tn >= dem.h_eq_long_tn:
            h_long_comp, h_trans_comp = 0.0, h_for_anchors
        else:
            h_long_comp, h_trans_comp = h_for_anchors, 0.0
        if h_for_anchors <= 1e-9 and h_pad > friction:
            h_long_comp, h_trans_comp = h_pad, 0.0
    else:
        h_long_comp = max(h_fixed_long, dem.h_eq_long_tn)
        h_trans_comp = max(h_fixed_trans, dem.h_eq_trans_tn)

    comp_demands = ComponentDemands(
        r_vertical_tn=dem.r_service_tn,
        h_long_tn=h_long_comp,
        h_trans_tn=h_trans_comp,
        t_uplift_tn=dem.r_uplift_tn,
        moment_long_tn_m=moment.moment_tn_m,
        combination_id=combo,
    )

    if (upper is None or lower is None) and inputs.design_plates_auto:
        auto_p = auto_design_plate(geom.length_cm, geom.width_cm, comp_demands, margin_cm=PLATE_MARGIN_CM)
        if auto_p is not None:
            upper = upper or auto_p
            lower = lower or auto_p
            inputs = replace(inputs, upper_plate=upper, lower_plate=lower)
        else:
            pending.append("Auto-diseno de placas: no se encontro espesor admisible")

    if upper is None:
        pending.append("Placa superior no ingresada / no verificada")
    else:
        checks.extend(verify_plate(upper, geom.length_cm, geom.width_cm, comp_demands, "Placa superior"))

    if lower is None:
        pending.append("Placa inferior no ingresada / no verificada")
    else:
        checks.extend(verify_plate(lower, geom.length_cm, geom.width_cm, comp_demands, "Placa inferior"))

    plate_for_anchors = lower or upper
    anchor_detail: PepAnchorDetail | None = None
    if anchors_in is None and inputs.design_anchors_auto and plate_for_anchors is not None:
        fc = inputs.concrete_support.fc_kg_cm2 if inputs.concrete_support else 210.0
        auto_anc = auto_design_anchors(
            plate_for_anchors, geom.length_cm, geom.width_cm, comp_demands, fc
        )
        if auto_anc is None:
            pending.append("Auto-diseno de anclajes: no se encontro solucion")
        else:
            anchor_detail, plate_grown = auto_anc
            plate_for_anchors = plate_grown
            lower = plate_grown if lower is not None or inputs.design_plates_auto else lower
            upper = plate_grown if upper is not None or inputs.design_plates_auto else upper
            if lower is None:
                lower = plate_grown
            if upper is None:
                upper = plate_grown
            # Si se agrando la placa, actualizar ambas caras al tamaño necesario.
            if plate_grown.length_cm > (lower.length_cm if lower else 0):
                lower = plate_grown
            if plate_grown.length_cm > (upper.length_cm if upper else 0):
                upper = plate_grown
            anchors_in = PepAnchorGroup(
                n_bolts=anchor_detail.n_bolts,
                diameter_cm=anchor_detail.diameter_cm,
                fy_kg_cm2=anchor_detail.fy_kg_cm2,
                fu_kg_cm2=anchor_detail.fu_kg_cm2,
                embedment_cm=anchor_detail.embedment_cm,
                layout_note=anchor_detail.layout_note,
                coordinates_cm=tuple((c.x_cm, c.y_cm) for c in anchor_detail.coordinates),
            )
            inputs = replace(inputs, anchors=anchors_in, upper_plate=upper, lower_plate=lower)

    if anchors_in is None:
        pending.append("Grupo de anclajes no ingresado / no verificado")
    elif plate_for_anchors is None:
        pending.append("Anclajes sin placa de referencia")
    else:
        if anchors_in.coordinates_cm:
            coords = tuple(BoltCoordinate(x, y) for x, y in anchors_in.coordinates_cm)
        else:
            coords = default_bolt_layout(
                anchors_in.n_bolts,
                plate_for_anchors.length_cm,
                plate_for_anchors.width_cm,
                geom.length_cm,
                geom.width_cm,
                diameter_cm=anchors_in.diameter_cm,
            )
            if not coords:
                pending.append("Placa insuficiente para layout de pernos fuera del PEP")
        if inputs.bolts_through_pep_exception:
            # Permite pernos interiores solo con excepcion expresa
            pass
        if coords:
            anchor_detail = PepAnchorDetail(
                n_bolts=anchors_in.n_bolts,
                diameter_cm=anchors_in.diameter_cm,
                fy_kg_cm2=anchors_in.fy_kg_cm2,
                fu_kg_cm2=anchors_in.fu_kg_cm2,
                embedment_cm=anchors_in.embedment_cm,
                coordinates=coords,
                layout_note=anchors_in.layout_note,
            )
            checks.extend(
                verify_bolts_and_welds(
                    anchor_detail, comp_demands, geom.length_cm, geom.width_cm, plate_for_anchors
                )
            )
            if inputs.concrete_support is None:
                pending.append("Anclaje al concreto: falta f'c")
            else:
                checks.extend(
                    verify_concrete_anchorage(
                        anchor_detail, comp_demands, inputs.concrete_support.fc_kg_cm2
                    )
                )

    if inputs.concrete_support is not None:
        support = inputs.concrete_support
        a1 = area
        a2 = support.support_area_cm2 if support.support_area_cm2 is not None else a1
        m_bearing = min(sqrt(a2 / a1), 2.0)
        pn = 0.85 * support.fc_kg_cm2 * a1 * m_bearing
        phi_pn = support.phi * pn
        checks.append(
            PepCheck(
                name="Aplastamiento concreto bajo apoyo",
                articulo_mtc="MTC 2.8.1.4",
                articulo_aashto="AASHTO 5.7.5",
                estado_limite="Resistencia",
                combination_id=combo,
                formula="R <= phi*0.85*f'c*A1*m",
                substitution=(
                    f"{r_kg:.0f} <= {support.phi:.2f}*0.85*{support.fc_kg_cm2:.0f}*"
                    f"{a1:.1f}*{m_bearing:.3f}"
                ),
                demand=r_kg,
                limit=phi_pn,
                unit="kg",
                status=_status_le(r_kg, phi_pn),
            )
        )
    else:
        pending.append("Presion local en concreto no verificada (f'c/A2 no ingresados)")

    designation = (
        f"PEP {inputs.tipo_apoyo} {geom.length_cm*10:.0f}x{geom.width_cm*10:.0f}x"
        f"{geom.thickness_cm*10:.0f} mm | Shore {inputs.hardness} | S={s:.2f} | "
        f"sin zunchos internos"
    )

    return PepBearingDesignResult(
        inputs=inputs,
        grade=grade,
        g_for_capacity_kg_cm2=g_cap,
        g_for_force_kg_cm2=g_force,
        g_capacity_reason="Gmin: minimiza capacidad G*S (mas desfavorable)",
        g_force_reason="Gmax: maximiza H=G*A*Delta/h (mas desfavorable)",
        shape_factor=s,
        area_cm2=area,
        sigma_s_kg_cm2=sigma_s,
        sigma_perm_kg_cm2=sigma_perm,
        sigma_live_kg_cm2=sigma_ll,
        sigma_gs_kg_cm2=sigma_gs,
        sigma_adm_kg_cm2=sigma_adm,
        delta_s_cm=delta_s,
        epsilon_permanent=eps_perm,
        epsilon_total=eps_tot,
        epsilon_note=eps_note,
        delta_dead_cm=delta_dead,
        delta_live_cm=delta_live,
        delta_creep_cm=delta_creep,
        delta_long_term_cm=delta_lt,
        h_pad_service_tn=h_pad,
        friction_capacity_tn=friction,
        h_fixed_long_tn=h_fixed_long,
        h_fixed_trans_tn=h_fixed_trans,
        h_eq_gov_tn=h_eq,
        h_anchor_report_tn=h_anchor,
        theta_total_rad=dem.theta_total_rad,
        moment_tn_m=moment.moment_tn_m,
        moment_formula=moment.formula,
        checks=tuple(checks),
        designation=designation,
        pending_components=tuple(pending),
    )


def _auto_design_pep(inputs: PepBearingInputs) -> PepBearingDesignResult:
    """Busca L, W, h (y opcionalmente placas/anclajes) de forma eficiente."""
    dem = inputs.demands
    length_min = inputs.geometry.length_cm
    width0 = inputs.geometry.width_cm
    delta = dem.resolved_delta_s_cm()
    h_min = 2.0 * delta if inputs.tipo_apoyo == "MOVIL_PEP_CORTE" else 1.0
    h_min = max(h_min, inputs.geometry.thickness_cm)
    thicknesses = [h for h in PEP_THICKNESSES_CM if h + 1e-12 >= h_min] or [h_min]
    grade = pep_grade(inputs.hardness, inputs.g_specified_kg_cm2)
    g = grade.g_min_kg_cm2
    r_kg = dem.r_service_tn * 1000.0
    best: PepBearingDesignResult | None = None

    # Arranque inteligente: A_min por 0.80ksi y por G*S aproximado con S~5
    a_min_stress = r_kg / SIGMA_S_MAX_PEP_KG_CM2
    for w_mult in range(0, 6):
        w = width0 + w_mult * PEP_PLAN_STEP_CM
        for h in thicknesses:
            # Para cumplir G*S: S >= sigma/G => LW/(2h(L+W)) >= r/(A G) => G*A*S >= r
            # Iterar L desde A_min/w
            l0 = float(
                ceil(max(a_min_stress / w, length_min, 1.0) / PEP_PLAN_STEP_CM)
                * PEP_PLAN_STEP_CM
            )
            for l_add in range(0, 10):
                length = l0 + l_add * PEP_PLAN_STEP_CM
                area = length * w
                sigma = r_kg / area
                s = area / (2.0 * h * (length + w))
                if sigma > min(g * s, SIGMA_S_MAX_PEP_KG_CM2) + 1e-9:
                    continue
                if h > min(length, w) / 3.0 + 1e-9:
                    continue
                trial = replace(
                    inputs,
                    mode="VERIFICAR",
                    geometry=PepGeometry(length, w, h),
                    design_plates_auto=True,
                    design_anchors_auto=True,
                    epsilon_source=(
                        "curva_aashto"
                        if inputs.epsilon_source == "estimacion_analitica"
                        else inputs.epsilon_source
                    ),
                )
                result = _verify_pep(trial)
                best = result
                if result.pep_core_ok and result.overall_ok:
                    return result
                if result.pep_core_ok and not result.pending_components:
                    # nucleo + componentes verificados aunque alguno NO
                    if all(
                        c.status != PENDING
                        for c in result.checks
                        if c.name.startswith(("Placa", "Perno", "Soldadura", "Anclaje"))
                    ):
                        return result
                if result.pep_core_ok:
                    # Devolver la primera solucion de nucleo si no hay completa
                    # pero seguir buscando completa un poco mas
                    pass
            # Si ya hay nucleo OK, no ensanchar mas W
            if best is not None and best.pep_core_ok:
                break
        if best is not None and best.overall_ok:
            break
    if best is None:
        raise ValueError("No se pudo iniciar el diseno automatico PEP.")
    return best
