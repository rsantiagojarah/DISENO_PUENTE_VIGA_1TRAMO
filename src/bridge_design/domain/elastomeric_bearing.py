"""Diseño de apoyos elastoméricos reforzados con acero - Método A.

Referencias:
- AASHTO LRFD Art. 14.7.6 (Método A), 14.7.5.3.5 (zunchos), 14.8.3 (anclaje),
  14.6.3.1 (fuerza por deformación), 3.10.9 / MTC 2.4.3.11.8 (sismo),
  5.7.5 / MTC 2.8.1.4 (aplastamiento del concreto).
- Manual de Puentes MTC 2018 Art. 2.10.4.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt
from typing import Literal

from bridge_design.validation.input_validators import (
    require_non_negative,
    require_positive,
    require_range,
)

# AASHTO 14.7.6.3.2-8: 1.25 ksi = 87.89 kg/cm2
SIGMA_S_MAX_KG_CM2 = 87.9
# Fatiga Categoría A, Tabla 6.6.1.2.3-1
DELTA_F_TH_CATEGORY_A_KG_CM2 = 1687.0
# 1/16 in = 1.5875 mm
HS_MIN_CM = 0.1588
MU_FRICTION_DEFAULT = 0.2
GAMMA_TU_DEFAULT = 1.2
ALPHA_CONCRETE_PER_C = 10.8e-6
JOINT_DEFLECTION_LIMIT_CM = 0.3175  # 1/8 in
METHOD_A_SI2_OVER_N_LIMIT = 22.0

ELASTOMER_LAYER_THICKNESSES_CM = (0.5, 0.8, 1.0, 1.2, 1.5, 2.0)
STEEL_PLATE_THICKNESSES_CM = (0.2, 0.3, 0.4)

HardnessShoreA = Literal[50, 60, 70]
ClimateZone = Literal["costa", "sierra", "selva"]
BearingRole = Literal["expansion", "fixed"]
SeismicZone = Literal[1, 2, 3, 4]


@dataclass(frozen=True)
class ElastomerGrade:
    """Propiedades de elastómero por dureza Shore A (Tabla 14.7.6.2-1)."""

    hardness: HardnessShoreA
    g_min_kg_cm2: float
    g_max_kg_cm2: float
    creep_ratio: float
    shape_factor_k: float

    @classmethod
    def from_hardness(cls, hardness: HardnessShoreA) -> "ElastomerGrade":
        table = {
            50: cls(50, 6.68, 9.14, 0.25, 0.75),
            60: cls(60, 9.14, 14.06, 0.35, 0.60),
            70: cls(70, 14.06, 21.09, 0.45, 0.55),
        }
        return table[hardness]


@dataclass(frozen=True)
class TemperatureRange:
    """Rango térmico de diseño (Manual MTC / AASHTO 3.12)."""

    t_sup_c: float
    t_inf_c: float
    t_install_c: float

    def __post_init__(self) -> None:
        from math import isfinite
        if not all(isfinite(v) for v in (self.t_sup_c, self.t_inf_c, self.t_install_c)):
            raise ValueError("Las temperaturas deben ser finitas.")
        if self.t_sup_c < self.t_inf_c:
            raise ValueError("t_sup debe ser mayor o igual que t_inf.")
        if not self.t_inf_c <= self.t_install_c <= self.t_sup_c:
            raise ValueError("La temperatura de instalacion debe estar dentro del rango de diseno.")

    @property
    def design_range_c(self) -> float:
        return self.t_sup_c - self.t_inf_c

    @property
    def contraction_delta_t_c(self) -> float:
        """ΔT desde instalación hacia el extremo inferior (contracción)."""
        return max(self.t_install_c - self.t_inf_c, 0.0)

    @property
    def expansion_delta_t_c(self) -> float:
        return self.t_sup_c - self.t_install_c

    @property
    def envelope_delta_t_c(self) -> float:
        return max(self.contraction_delta_t_c, self.expansion_delta_t_c)

    @classmethod
    def mtc_default(cls, zone: ClimateZone, t_install_c: float = 20.0) -> "TemperatureRange":
        defaults = {
            "costa": (40.0, 0.0),
            "sierra": (35.0, -10.0),
            "selva": (50.0, 10.0),
        }
        t_sup, t_inf = defaults[zone]
        return cls(t_sup_c=t_sup, t_inf_c=t_inf, t_install_c=t_install_c)


@dataclass(frozen=True)
class BearingLoads:
    """Cargas de servicio por apoyo (Tn)."""

    dead_load_dc_tn: float
    wearing_surface_dw_tn: float
    live_load_ll_tn: float

    def __post_init__(self) -> None:
        require_positive(self.dead_load_dc_tn, "PDC")
        require_non_negative(self.wearing_surface_dw_tn, "PDW")
        require_non_negative(self.live_load_ll_tn, "PLL")

    @property
    def permanent_tn(self) -> float:
        return self.dead_load_dc_tn + self.wearing_surface_dw_tn

    @property
    def total_service_tn(self) -> float:
        return self.permanent_tn + self.live_load_ll_tn

    @property
    def strength_i_tn(self) -> float:
        """MTC 2.4.5.3.1-1: maximum vertical Strength I reaction."""
        return 1.25 * self.dead_load_dc_tn + 1.50 * self.wearing_surface_dw_tn + 1.75 * self.live_load_ll_tn

    @property
    def total_service_kg(self) -> float:
        return self.total_service_tn * 1000.0

    @property
    def permanent_kg(self) -> float:
        return self.permanent_tn * 1000.0

    @property
    def live_load_kg(self) -> float:
        return self.live_load_ll_tn * 1000.0

    @property
    def dead_load_dc_kg(self) -> float:
        return self.dead_load_dc_tn * 1000.0


@dataclass(frozen=True)
class BearingMovements:
    """Movimientos horizontales de servicio (cm)."""

    span_length_m: float
    temperature: TemperatureRange
    shrinkage_cm: float = 0.0
    prestress_shortening_cm: float = 0.0
    other_permanent_cm: float = 0.0
    gamma_tu: float = GAMMA_TU_DEFAULT
    alpha_per_c: float = ALPHA_CONCRETE_PER_C
    use_install_to_min: bool = True

    def __post_init__(self) -> None:
        require_positive(self.span_length_m, "luz")
        require_non_negative(self.shrinkage_cm, "retraccion")
        require_non_negative(self.prestress_shortening_cm, "acortamiento por pretensado")
        require_non_negative(self.other_permanent_cm, "otros movimientos")
        require_positive(self.gamma_tu, "gamma_TU")
        require_positive(self.alpha_per_c, "coeficiente termico")

    @property
    def thermal_displacement_cm(self) -> float:
        length_cm = self.span_length_m * 100.0
        delta_t = (
            self.temperature.envelope_delta_t_c
            if self.use_install_to_min
            else self.temperature.design_range_c
        )
        return self.alpha_per_c * length_cm * delta_t

    @property
    def unfactored_permanent_displacement_cm(self) -> float:
        shortening = self.shrinkage_cm + self.prestress_shortening_cm + self.other_permanent_cm
        if not self.use_install_to_min:
            return self.thermal_displacement_cm + shortening
        coefficient = self.alpha_per_c * self.span_length_m * 100.0
        return max(coefficient * self.temperature.contraction_delta_t_c + shortening,
                   abs(coefficient * self.temperature.expansion_delta_t_c - shortening))

    @property
    def service_shear_displacement_cm(self) -> float:
        """Δs en estado límite de servicio (con γ_TU sobre movimientos permanentes)."""
        return self.gamma_tu * self.unfactored_permanent_displacement_cm


@dataclass(frozen=True)
class SeismicBearingInputs:
    """Datos para verificación sísmica del apoyo (MTC 2.4.3.11.8 / AASHTO 3.10.9)."""

    site_acceleration_as: float
    seismic_zone: SeismicZone
    is_single_span: bool = True
    bearing_role: BearingRole = "expansion"
    longitudinal_restrained: bool = False
    transverse_restrained: bool = True
    tributary_permanent_longitudinal_tn: float | None = None
    friction_coefficient: float = MU_FRICTION_DEFAULT

    def __post_init__(self) -> None:
        require_non_negative(self.site_acceleration_as, "As")
        require_range(float(self.seismic_zone), "zona sismica", 1, 4)
        require_positive(self.friction_coefficient, "mu friccion")
        if self.tributary_permanent_longitudinal_tn is not None:
            require_positive(
                self.tributary_permanent_longitudinal_tn,
                "carga permanente tributaria longitudinal",
            )


@dataclass(frozen=True)
class ConcreteBearingSupport:
    """Datos opcionales para aplastamiento del concreto bajo el apoyo."""

    fc_kg_cm2: float
    support_area_cm2: float | None = None
    phi: float = 0.70

    def __post_init__(self) -> None:
        require_positive(self.fc_kg_cm2, "f'c")
        require_positive(self.phi, "phi aplastamiento")
        if self.support_area_cm2 is not None:
            require_positive(self.support_area_cm2, "area de apoyo del concreto")


@dataclass(frozen=True)
class ElastomericBearingInputs:
    """Entrada completa para diseño Método A."""

    loads: BearingLoads
    movements: BearingMovements
    seismic: SeismicBearingInputs
    hardness: HardnessShoreA = 60
    girder_width_cm: float = 40.0
    steel_fy_kg_cm2: float = 2530.0
    adopted_length_cm: float | None = None
    adopted_width_cm: float | None = None
    adopted_interior_layer_cm: float | None = None
    adopted_exterior_layer_cm: float | None = None
    adopted_interior_layers: int | None = None
    adopted_steel_plate_cm: float | None = None
    concrete_support: ConcreteBearingSupport | None = None

    def __post_init__(self) -> None:
        require_positive(self.girder_width_cm, "ancho de viga")
        require_positive(self.steel_fy_kg_cm2, "Fy acero zuncho")
        if self.hardness not in (50, 60, 70):
            raise ValueError("La dureza debe ser 50, 60 o 70 Shore A.")
        if self.hardness == 70:
            # AASHTO 14.7.6.2: dureza 70 solo con PTFE/deslizador o PEP/FGP.
            pass


@dataclass(frozen=True)
class DesignCheck:
    """Resultado de una verificación normativa."""

    name: str
    demand: float
    limit: float
    unit: str
    status: str
    reference: str
    notes: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "OK"


@dataclass(frozen=True)
class ElastomericBearingDesignResult:
    """Resultado del diseño y verificaciones Método A + sismo."""

    inputs: ElastomericBearingInputs
    grade: ElastomerGrade
    length_cm: float
    width_cm: float
    area_cm2: float
    required_area_cm2: float
    sigma_s_kg_cm2: float
    sigma_permanent_kg_cm2: float
    sigma_live_kg_cm2: float
    delta_s_cm: float
    required_hrt_cm: float
    interior_layer_cm: float
    exterior_layer_cm: float
    interior_layers: int
    n_for_shape_limit: float
    shape_factor_interior: float
    shape_factor_exterior: float
    total_elastomer_cm: float
    steel_plate_cm: float
    steel_plates: int
    total_height_cm: float
    design_g_kg_cm2: float
    max_g_kg_cm2: float
    epsilon_permanent: float
    epsilon_total: float
    delta_dead_cm: float
    delta_live_cm: float
    delta_creep_cm: float
    shear_force_service_tn: float
    friction_capacity_tn: float
    seismic_force_transverse_tn: float
    seismic_force_longitudinal_tn: float
    seismic_governing_tn: float
    anchor_force_required_tn: float
    checks: tuple[DesignCheck, ...]
    designation: str

    @property
    def overall_ok(self) -> bool:
        return all(check.ok for check in self.checks)

    @property
    def elastomer_ok(self) -> bool:
        """Service checks of the pad, excluding unverified external restraints."""
        external = {"Friccion vs fuerza servicio", "Sismo: fuerza de union", "Aplastamiento concreto"}
        return all(check.ok for check in self.checks if check.name not in external)


def _status(demand: float, limit: float, *, lower_is_better: bool = True) -> str:
    if lower_is_better:
        return "OK" if demand <= limit + 1e-9 else "NO"
    return "OK" if demand + 1e-9 >= limit else "NO"


@dataclass(frozen=True)
class BearingPlanRecommendation:
    """Propuesta de planta a partir de A_req y el ancho W."""

    required_area_cm2: float
    width_cm: float
    theoretical_length_cm: float
    recommended_length_cm: float

    @property
    def recommended_area_cm2(self) -> float:
        return self.recommended_length_cm * self.width_cm


def recommend_bearing_plan(
    loads: BearingLoads,
    width_cm: float,
) -> BearingPlanRecommendation:
    """Calcula A_req, L teorico y L propuesto (redondeo al cm superior)."""
    require_positive(width_cm, "ancho del apoyo W")
    required_area = loads.total_service_kg / SIGMA_S_MAX_KG_CM2
    theoretical_length = required_area / width_cm
    recommended_length = float(max(ceil(theoretical_length - 1e-12), 1))
    if recommended_length * width_cm + 1e-9 < required_area:
        recommended_length = float(ceil(required_area / width_cm))
    return BearingPlanRecommendation(
        required_area_cm2=required_area,
        width_cm=width_cm,
        theoretical_length_cm=theoretical_length,
        recommended_length_cm=recommended_length,
    )


def shape_factor_rectangular(length_cm: float, width_cm: float, layer_cm: float) -> float:
    """Factor de forma Si = LW / [2 hri (L+W)] (AASHTO 14.7.5.1-1)."""
    require_positive(layer_cm, "espesor de capa")
    return (length_cm * width_cm) / (2.0 * layer_cm * (length_cm + width_cm))


def compressive_strain(sigma_kg_cm2: float, g_kg_cm2: float, shape_factor: float, k: float) -> float:
    """Deformación por compresión aproximada ε = σ / [3G(1+2kS²)]."""
    modulus = 3.0 * g_kg_cm2 * (1.0 + 2.0 * k * shape_factor**2)
    return sigma_kg_cm2 / modulus


def seismic_connection_force_factor(
    seismic: SeismicBearingInputs,
) -> float:
    """Factor mínimo sobre carga permanente para fuerza de unión."""
    if seismic.is_single_span:
        return max(seismic.site_acceleration_as, 0.0)
    if seismic.seismic_zone == 1:
        if seismic.site_acceleration_as < 0.05:
            return 0.15
        return 0.25
    # Zonas 2-4: mínimo práctico de conexión si no hay análisis multimodal.
    # Se usa As como piso; el usuario debe reemplazar con F_EQ del análisis.
    return max(seismic.site_acceleration_as, 0.25)


def design_elastomeric_bearing_method_a(
    inputs: ElastomericBearingInputs,
) -> ElastomericBearingDesignResult:
    """Diseña y verifica un apoyo elastomérico por Método A + sismo."""
    grade = ElastomerGrade.from_hardness(inputs.hardness)
    g_design = grade.g_min_kg_cm2
    g_max = grade.g_max_kg_cm2
    loads = inputs.loads
    movements = inputs.movements
    seismic = inputs.seismic

    p_total_kg = loads.total_service_kg
    required_area = p_total_kg / SIGMA_S_MAX_KG_CM2

    width_cm = inputs.adopted_width_cm or inputs.girder_width_cm
    if inputs.adopted_length_cm is not None:
        length_cm = inputs.adopted_length_cm
    else:
        length_cm = max(ceil(required_area / width_cm), 1.0)
        # redondeo práctico a 1 cm hacia arriba y mínimo razonable
        length_cm = float(ceil(length_cm))

    area = length_cm * width_cm
    if area + 1e-9 < required_area:
        length_cm = float(ceil(required_area / width_cm))
        area = length_cm * width_cm

    sigma_s = p_total_kg / area
    sigma_perm = loads.permanent_kg / area
    sigma_ll = loads.live_load_kg / area
    delta_s = movements.service_shear_displacement_cm
    required_hrt = 2.0 * delta_s

    si_min = sigma_s / (1.25 * g_design) if g_design > 0 else float("inf")

    if inputs.adopted_interior_layer_cm is not None:
        hri = inputs.adopted_interior_layer_cm
    else:
        hri_max = (length_cm * width_cm) / (2.0 * si_min * (length_cm + width_cm))
        hri_candidates = [
            t for t in ELASTOMER_LAYER_THICKNESSES_CM if t <= hri_max + 1e-9
        ]
        # Mayor espesor comercial admisible => Si mas cercano al minimo (eficiente).
        hri = hri_candidates[-1] if hri_candidates else max(min(hri_max, 1.5), 0.5)

    def _exterior_from_interior(interior_cm: float) -> float:
        if inputs.adopted_exterior_layer_cm is not None:
            return min(inputs.adopted_exterior_layer_cm, 0.7 * interior_cm)
        ext_candidates = [
            t for t in ELASTOMER_LAYER_THICKNESSES_CM if t <= 0.7 * interior_cm + 1e-9
        ]
        if ext_candidates:
            return ext_candidates[-1]
        return min(0.5 * interior_cm, 0.7 * interior_cm)

    hre = _exterior_from_interior(hri)

    if inputs.adopted_interior_layers is not None:
        n = max(int(inputs.adopted_interior_layers), 1)
    else:
        n_raw = (required_hrt - 2.0 * hre) / hri
        n = max(int(ceil(n_raw - 1e-12)), 3 if n_raw > 0 else 1)

    def _n_shape(n_layers: int, interior_cm: float, exterior_cm: float) -> float:
        value = float(n_layers)
        if exterior_cm + 1e-12 >= 0.5 * interior_cm:
            value += 1.0
        return value

    hrt = n * hri + 2.0 * hre
    while hrt + 1e-9 < required_hrt:
        n += 1
        hrt = n * hri + 2.0 * hre

    si = shape_factor_rectangular(length_cm, width_cm, hri)
    # Ajustar hri/n para cumplir Si^2/n < 22 del Metodo A.
    if inputs.adopted_interior_layer_cm is None and inputs.adopted_interior_layers is None:
        hri_max = (length_cm * width_cm) / (2.0 * si_min * (length_cm + width_cm))
        while (si**2) / _n_shape(n, hri, hre) > METHOD_A_SI2_OVER_N_LIMIT - 1e-9:
            thicker = [t for t in ELASTOMER_LAYER_THICKNESSES_CM if t > hri + 1e-12 and t <= hri_max + 1e-9]
            if thicker:
                hri = thicker[0]
                hre = _exterior_from_interior(hri)
                n_raw = (required_hrt - 2.0 * hre) / hri
                n = max(int(ceil(n_raw - 1e-12)), 3 if n_raw > 0 else 1)
                hrt = n * hri + 2.0 * hre
                while hrt + 1e-9 < required_hrt:
                    n += 1
                    hrt = n * hri + 2.0 * hre
                si = shape_factor_rectangular(length_cm, width_cm, hri)
                continue
            n += 1
            hrt = n * hri + 2.0 * hre
            if n > 20:
                break

    n_shape = _n_shape(n, hri, hre)
    si = shape_factor_rectangular(length_cm, width_cm, hri)
    se = shape_factor_rectangular(length_cm, width_cm, hre)
    hrt = n * hri + 2.0 * hre

    hs_service = 3.0 * hri * sigma_s / inputs.steel_fy_kg_cm2
    hs_fatigue = 2.0 * hri * sigma_ll / DELTA_F_TH_CATEGORY_A_KG_CM2
    hs_req = max(hs_service, hs_fatigue, HS_MIN_CM)
    if inputs.adopted_steel_plate_cm is not None:
        hs = inputs.adopted_steel_plate_cm
    else:
        hs = next(
            (t for t in STEEL_PLATE_THICKNESSES_CM if t >= hs_req - 1e-12),
            STEEL_PLATE_THICKNESSES_CM[-1],
        )

    steel_plates = n + 1
    total_height = hrt + steel_plates * hs

    eps_perm_i = compressive_strain(sigma_perm, g_design, si, grade.shape_factor_k)
    eps_total_i = compressive_strain(sigma_s, g_design, si, grade.shape_factor_k)
    eps_perm_e = compressive_strain(sigma_perm, g_design, se, grade.shape_factor_k)
    eps_total_e = compressive_strain(sigma_s, g_design, se, grade.shape_factor_k)

    delta_total = n * eps_total_i * hri + 2.0 * eps_total_e * hre
    delta_dead = n * eps_perm_i * hri + 2.0 * eps_perm_e * hre
    delta_live = max(delta_total - delta_dead, 0.0)
    delta_creep = grade.creep_ratio * delta_dead
    delta_ll_creep = delta_live + delta_creep

    shear_force_service_tn = (g_max * area * delta_s / hrt) / 1000.0
    friction_tn = seismic.friction_coefficient * loads.dead_load_dc_tn

    factor = seismic_connection_force_factor(seismic)
    f_eq_transverse = (
        factor * loads.permanent_tn if seismic.transverse_restrained else 0.0
    )
    p_long = (
        seismic.tributary_permanent_longitudinal_tn
        if seismic.tributary_permanent_longitudinal_tn is not None
        else loads.permanent_tn
    )
    f_eq_longitudinal = factor * p_long if seismic.longitudinal_restrained else 0.0
    f_eq_gov = max(f_eq_transverse, f_eq_longitudinal)

    # GA*Delta/h is a service reaction, never an ultimate resistance.
    # Without a verified seismic load path, size the external restraint for
    # the full connection force, with no thermal/friction deduction.
    horizontal_capacity = 0.0
    anchor_required = max(f_eq_gov, shear_force_service_tn if shear_force_service_tn > friction_tn else 0.0)

    checks: list[DesignCheck] = [
        DesignCheck(
            name="Area en planta",
            demand=required_area,
            limit=area,
            unit="cm2",
            status=_status(required_area, area, lower_is_better=True),
            reference="AASHTO 14.7.6.3.2-8",
            notes="A_req = PT / 87.9",
        ),
        DesignCheck(
            name="Esfuerzo compresion total",
            demand=sigma_s,
            limit=SIGMA_S_MAX_KG_CM2,
            unit="kg/cm2",
            status=_status(sigma_s, SIGMA_S_MAX_KG_CM2),
            reference="AASHTO 14.7.6.3.2-8",
        ),
        DesignCheck(
            name="Esfuerzo 1.25 G Si",
            demand=sigma_s,
            limit=1.25 * g_design * si,
            unit="kg/cm2",
            status=_status(sigma_s, 1.25 * g_design * si),
            reference="AASHTO 14.7.6.3.2-7",
        ),
        DesignCheck(
            name="Espesor elastomero por corte",
            demand=required_hrt,
            limit=hrt,
            unit="cm",
            status=_status(required_hrt, hrt),
            reference="AASHTO 14.7.6.3.4-1",
            notes="hrt >= 2 Ds",
        ),
        DesignCheck(
            name="Capa exterior <= 0.70 hri",
            demand=hre,
            limit=0.70 * hri,
            unit="cm",
            status=_status(hre, 0.70 * hri),
            reference="AASHTO 14.7.6.1",
        ),
        DesignCheck(
            name="Limite Si^2/n Metodo A",
            demand=(si**2) / n_shape,
            limit=METHOD_A_SI2_OVER_N_LIMIT,
            unit="-",
            status=_status((si**2) / n_shape, METHOD_A_SI2_OVER_N_LIMIT),
            reference="AASHTO/MTC 14.7.6.1",
        ),
        DesignCheck(
            name="Espesor zuncho acero",
            demand=hs_req,
            limit=hs,
            unit="cm",
            status=_status(hs_req, hs),
            reference="AASHTO 14.7.5.3.5",
        ),
        DesignCheck(
            name="Estabilidad H <= L/3",
            demand=total_height,
            limit=length_cm / 3.0,
            unit="cm",
            status=_status(total_height, length_cm / 3.0),
            reference="AASHTO 14.7.6.3.6",
        ),
        DesignCheck(
            name="Estabilidad H <= W/3",
            demand=total_height,
            limit=width_cm / 3.0,
            unit="cm",
            status=_status(total_height, width_cm / 3.0),
            reference="AASHTO 14.7.6.3.6",
        ),
        DesignCheck(
            name="Deformacion capa interior",
            demand=eps_total_i,
            limit=0.09,
            unit="-",
            status=_status(eps_total_i, 0.09),
            reference="AASHTO 14.7.6.3.3",
        ),
        DesignCheck(
            name="Deflexion LL+creep en junta",
            demand=delta_ll_creep,
            limit=JOINT_DEFLECTION_LIMIT_CM,
            unit="cm",
            status=_status(delta_ll_creep, JOINT_DEFLECTION_LIMIT_CM),
            reference="AASHTO C14.7.5.3.6",
        ),
        DesignCheck(
            name="Friccion vs fuerza servicio",
            demand=shear_force_service_tn,
            limit=friction_tn,
            unit="Tn",
            status=(
                "OK"
                if shear_force_service_tn <= friction_tn + 1e-9
                else "ANCLAR"
            ),
            reference="AASHTO 14.8.3 / C14.8.3.1",
            notes="ANCLAR si Hu servicio > mu*PDC",
        ),
        DesignCheck(
            name="Sismo: fuerza de union",
            demand=f_eq_gov,
            limit=horizontal_capacity,
            unit="Tn",
            status=(
                "OK"
                if f_eq_gov <= horizontal_capacity + 1e-9
                else "ANCLAR"
            ),
            reference="MTC 2.4.3.11.8 / 2.10.3.3.7",
            notes=(
                f"F_EQ={f_eq_gov:.3f} Tn; capacidad={horizontal_capacity:.3f} Tn; "
                f"anclaje req.={anchor_required:.3f} Tn"
            ),
        ),
    ]

    if inputs.concrete_support is not None:
        support = inputs.concrete_support
        a1 = area
        a2 = support.support_area_cm2 if support.support_area_cm2 is not None else a1
        m = min(sqrt(a2 / a1), 2.0)
        pn = 0.85 * support.fc_kg_cm2 * a1 * m
        phi_pn = support.phi * pn
        demand_kg = loads.strength_i_tn * 1000.0
        checks.append(
            DesignCheck(
                name="Aplastamiento concreto",
                demand=demand_kg,
                limit=phi_pn,
                unit="kg",
                status=_status(demand_kg, phi_pn),
                reference="AASHTO 5.7.5 / MTC 2.8.1.4",
                notes=f"Resistencia I: 1.25DC+1.50DW+1.75LL; m={m:.3f}; phiPn={phi_pn:.0f} kg",
            )
        )

    designation = (
        f"{length_cm * 10.0:.0f}x{width_cm * 10.0:.0f}x{total_height * 10.0:.0f} mm | "
        f"{n} int@{hri * 10.0:.0f}mm + 2 ext@{hre * 10.0:.0f}mm + "
        f"{steel_plates} zunchos@{hs * 10.0:.0f}mm | Shore {inputs.hardness}"
    )

    return ElastomericBearingDesignResult(
        inputs=inputs,
        grade=grade,
        length_cm=length_cm,
        width_cm=width_cm,
        area_cm2=area,
        required_area_cm2=required_area,
        sigma_s_kg_cm2=sigma_s,
        sigma_permanent_kg_cm2=sigma_perm,
        sigma_live_kg_cm2=sigma_ll,
        delta_s_cm=delta_s,
        required_hrt_cm=required_hrt,
        interior_layer_cm=hri,
        exterior_layer_cm=hre,
        interior_layers=n,
        n_for_shape_limit=n_shape,
        shape_factor_interior=si,
        shape_factor_exterior=se,
        total_elastomer_cm=hrt,
        steel_plate_cm=hs,
        steel_plates=steel_plates,
        total_height_cm=total_height,
        design_g_kg_cm2=g_design,
        max_g_kg_cm2=g_max,
        epsilon_permanent=eps_perm_i,
        epsilon_total=eps_total_i,
        delta_dead_cm=delta_dead,
        delta_live_cm=delta_live,
        delta_creep_cm=delta_creep,
        shear_force_service_tn=shear_force_service_tn,
        friction_capacity_tn=friction_tn,
        seismic_force_transverse_tn=f_eq_transverse,
        seismic_force_longitudinal_tn=f_eq_longitudinal,
        seismic_governing_tn=f_eq_gov,
        anchor_force_required_tn=anchor_required,
        checks=tuple(checks),
        designation=designation,
    )
