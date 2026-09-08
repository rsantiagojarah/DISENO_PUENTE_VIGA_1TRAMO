"""Apoyos de neopreno simple con detalles constructivos especificos.

Incluye:
- apoyo fijo con barras pasantes/interiores tipo pasador;
- apoyo movil con planchas externas superior/inferior.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt
from typing import Literal

from bridge_design.domain.elastomeric_bearing import (
    ALPHA_CONCRETE_PER_C,
    GAMMA_TU_DEFAULT,
    MU_FRICTION_DEFAULT,
    ElastomerGrade,
    TemperatureRange,
)
from bridge_design.domain.pep_strain_curves import compressive_strain_from_curve
from bridge_design.units.converters import ksi_to_kg_cm2
from bridge_design.validation.input_validators import require_non_negative, require_positive

# AASHTO 14.7.6.3.2 para neopreno simple sin zunchos (0.80 ksi, no 1.25 ksi).
SIGMA_S_MAX_PEP_KG_CM2 = ksi_to_kg_cm2(0.80)

SimpleSupportType = Literal["FIJO_BARRAS", "MOVIL_PLACAS"]

A36_FY_KG_CM2 = 2530.0
A36_FU_KG_CM2 = 4080.0
PIN_A108_FY_KG_CM2 = 2500.0
PIN_PHI_FLEXURE = 1.0
PIN_PHI_SHEAR = 1.0
BRAKING_FACTOR_STRENGTH_I = 1.75


@dataclass(frozen=True)
class SimpleNeopreneGeometry:
    length_cm: float
    width_cm: float
    thickness_cm: float

    def __post_init__(self) -> None:
        require_positive(self.length_cm, "L neopreno")
        require_positive(self.width_cm, "W neopreno")
        require_positive(self.thickness_cm, "h neopreno")

    @property
    def gross_area_cm2(self) -> float:
        return self.length_cm * self.width_cm

    @property
    def gross_shape_factor(self) -> float:
        return self.gross_area_cm2 / (
            2.0 * self.thickness_cm * (self.length_cm + self.width_cm)
        )


@dataclass(frozen=True)
class SimpleSupportDemands:
    r_dc_tn: float
    r_dw_tn: float
    r_pl_tn: float
    r_ll_im_tn: float
    h_long_tn: float = 0.0  # BR nominal por apoyo; se factoriza en Resistencia I.
    pga: float = 0.0
    fpga: float = 1.0
    span_length_m: float = 15.0
    temperature: TemperatureRange | None = None
    gamma_tu: float = GAMMA_TU_DEFAULT
    alpha_per_c: float = ALPHA_CONCRETE_PER_C

    def __post_init__(self) -> None:
        require_positive(self.r_dc_tn, "R_DC")
        require_non_negative(self.r_dw_tn, "R_DW")
        require_non_negative(self.r_pl_tn, "R_PL")
        require_non_negative(self.r_ll_im_tn, "R_LL+IM")
        require_non_negative(self.h_long_tn, "BR nominal por apoyo")
        require_non_negative(self.pga, "PGA")
        require_positive(self.fpga, "Fpga")
        require_positive(self.span_length_m, "luz")
        require_positive(self.gamma_tu, "gamma_TU")

    @property
    def r_service_tn(self) -> float:
        return self.r_dc_tn + self.r_dw_tn + self.r_pl_tn + self.r_ll_im_tn

    @property
    def r_strength_tn(self) -> float:
        """MTC 2.4.5.3.1-1, Resistencia I; inputs remain service actions."""
        return 1.25 * self.r_dc_tn + 1.50 * self.r_dw_tn + 1.75 * (self.r_pl_tn + self.r_ll_im_tn)

    @property
    def r_permanent_tn(self) -> float:
        return self.r_dc_tn + self.r_dw_tn

    @property
    def as_coeff(self) -> float:
        return self.pga * self.fpga

    @property
    def h_eq_long_tn(self) -> float:
        return self.as_coeff * self.r_permanent_tn

    @property
    def h_br_strength_tn(self) -> float:
        return BRAKING_FACTOR_STRENGTH_I * self.h_long_tn

    def thermal_delta_cm(self) -> float:
        temp = self.temperature or TemperatureRange.mtc_default("costa")
        return (
            self.gamma_tu
            * self.alpha_per_c
            * self.span_length_m
            * 100.0
            * temp.envelope_delta_t_c
        )


@dataclass(frozen=True)
class FixedBarGroup:
    n_bars: int = 4
    diameter_cm: float = 2.54
    spacing_long_cm: float = 20.0
    spacing_trans_cm: float = 15.0
    fy_kg_cm2: float = PIN_A108_FY_KG_CM2
    moment_arm_cm: float = 5.0

    def __post_init__(self) -> None:
        if self.n_bars not in (4, 6, 8):
            raise ValueError("FIJO_BARRAS implementa grillas rectangulares de 4, 6 u 8 pasadores.")
        require_positive(self.diameter_cm, "diametro pasador")
        require_positive(self.spacing_long_cm, "separacion longitudinal pasadores")
        require_positive(self.spacing_trans_cm, "separacion transversal pasadores")
        require_positive(self.fy_kg_cm2, "fy pasadores")
        require_positive(self.moment_arm_cm, "brazo de momento del pasador")

    @property
    def area_one_cm2(self) -> float:
        return pi * self.diameter_cm**2 / 4.0

    @property
    def hole_area_total_cm2(self) -> float:
        return self.n_bars * self.area_one_cm2


@dataclass(frozen=True)
class ExternalSteelPlatePair:
    thickness_cm: float = 2.54
    fy_kg_cm2: float = A36_FY_KG_CM2
    fu_kg_cm2: float = A36_FU_KG_CM2

    def __post_init__(self) -> None:
        require_positive(self.thickness_cm, "espesor plancha")
        require_positive(self.fy_kg_cm2, "Fy plancha")
        require_positive(self.fu_kg_cm2, "Fu plancha")


@dataclass(frozen=True)
class SimpleSupportInputs:
    support_type: SimpleSupportType
    geometry: SimpleNeopreneGeometry
    demands: SimpleSupportDemands
    hardness: int = 60
    fixed_bars: FixedBarGroup | None = None
    plates: ExternalSteelPlatePair | None = None
    fc_kg_cm2: float = 210.0
    friction_coefficient: float = MU_FRICTION_DEFAULT

    def __post_init__(self) -> None:
        if self.support_type == "FIJO_BARRAS" and self.fixed_bars is None:
            raise ValueError("FIJO_BARRAS requiere datos de barras.")
        if self.support_type == "MOVIL_PLACAS" and self.plates is None:
            raise ValueError("MOVIL_PLACAS requiere datos de planchas.")
        if self.hardness not in (50, 60, 70):
            raise ValueError("Dureza Shore A debe ser 50, 60 o 70.")
        require_positive(self.fc_kg_cm2, "f'c")
        require_positive(self.friction_coefficient, "mu")


@dataclass(frozen=True)
class SupportCheck:
    name: str
    formula: str
    substitution: str
    demand: float
    limit: float
    unit: str
    status: str
    notes: str = ""

    @property
    def ratio(self) -> float | None:
        if abs(self.limit) <= 1e-12:
            return None
        return self.demand / self.limit

    @property
    def ok(self) -> bool:
        return self.status in {"OK", "N.A."}


@dataclass(frozen=True)
class SimpleSupportResult:
    inputs: SimpleSupportInputs
    g_min_kg_cm2: float
    g_max_kg_cm2: float
    g_capacity_reason: str
    g_force_reason: str
    gross_area_cm2: float
    removed_area_cm2: float
    free_area_cm2: float
    effective_area_cm2: float
    shape_factor: float
    sigma_service_kg_cm2: float
    sigma_gs_kg_cm2: float
    sigma_adm_kg_cm2: float
    epsilon_total: float
    delta_compression_cm: float
    delta_thermal_cm: float
    h_pad_tn: float
    friction_capacity_tn: float
    h_design_tn: float
    h_design_case: str
    checks: tuple[SupportCheck, ...]

    @property
    def overall_ok(self) -> bool:
        return all(check.ok for check in self.checks)


def design_simple_neoprene_support(inputs: SimpleSupportInputs) -> SimpleSupportResult:
    geom = inputs.geometry
    demands = inputs.demands
    grade = ElastomerGrade.from_hardness(inputs.hardness)
    delta_thermal = demands.thermal_delta_cm()
    checks: list[SupportCheck] = []

    if inputs.support_type == "FIJO_BARRAS":
        assert inputs.fixed_bars is not None
        removed_area = inputs.fixed_bars.hole_area_total_cm2
        effective_area = geom.gross_area_cm2 - removed_area
        free_area = (
            2.0 * geom.thickness_cm * (geom.length_cm + geom.width_cm)
            + inputs.fixed_bars.n_bars * pi * inputs.fixed_bars.diameter_cm * geom.thickness_cm
        )
        shape_factor = effective_area / free_area
    else:
        removed_area = 0.0
        effective_area = geom.gross_area_cm2
        free_area = 2.0 * geom.thickness_cm * (geom.length_cm + geom.width_cm)
        shape_factor = geom.gross_shape_factor

    sigma = demands.r_service_tn * 1000.0 / effective_area
    sigma_gs = grade.g_min_kg_cm2 * shape_factor
    sigma_adm = min(sigma_gs, SIGMA_S_MAX_PEP_KG_CM2)
    eps_lookup = compressive_strain_from_curve(inputs.hardness, shape_factor, sigma)
    delta_comp = eps_lookup.epsilon * geom.thickness_cm
    h_pad = grade.g_max_kg_cm2 * geom.gross_area_cm2 * delta_thermal / geom.thickness_cm / 1000.0
    friction = inputs.friction_coefficient * demands.r_dc_tn
    h_design = max(demands.h_br_strength_tn, demands.h_eq_long_tn)
    h_design_case = (
        "Resistencia I - frenado"
        if demands.h_br_strength_tn >= demands.h_eq_long_tn
        else "Evento Extremo I - sismo"
    )

    checks.extend(
        [
            _check(
                "Compresion neopreno",
                "sigma = R/A_eff <= min(G*S,0.80ksi)",
                f"{demands.r_service_tn*1000:.0f}/{effective_area:.1f}={sigma:.2f}; adm={sigma_adm:.2f}",
                sigma,
                sigma_adm,
                "kg/cm2",
            ),
            _check(
                "Deflexion por compresion",
                "delta = eps*h <= 0.09h",
                f"{eps_lookup.epsilon:.5f}*{geom.thickness_cm:.2f} <= 0.09*{geom.thickness_cm:.2f}",
                delta_comp,
                0.09 * geom.thickness_cm,
                "cm",
                notes=eps_lookup.source + (" [extrapolado]" if eps_lookup.extrapolated else ""),
            ),
            _check(
                "Estabilidad h <= L/3",
                "h <= L/3",
                f"{geom.thickness_cm:.2f} <= {geom.length_cm:.2f}/3",
                geom.thickness_cm,
                geom.length_cm / 3.0,
                "cm",
            ),
            _check(
                "Estabilidad h <= W/3",
                "h <= W/3",
                f"{geom.thickness_cm:.2f} <= {geom.width_cm:.2f}/3",
                geom.thickness_cm,
                geom.width_cm / 3.0,
                "cm",
            ),
            _check(
                "Aplastamiento concreto bajo apoyo",
                "R <= phi*0.85*f'c*A_eff",
                f"Resistencia I: {demands.r_strength_tn*1000:.0f} <= 0.70*0.85*{inputs.fc_kg_cm2:.0f}*{effective_area:.1f}",
                demands.r_strength_tn * 1000.0,
                0.70 * 0.85 * inputs.fc_kg_cm2 * effective_area,
                "kg",
            ),
        ]
    )

    if inputs.support_type == "FIJO_BARRAS":
        checks.extend(_fixed_bar_checks(inputs, effective_area, h_design))
    else:
        checks.extend(_movable_plate_checks(inputs, delta_thermal, h_pad, friction))

    return SimpleSupportResult(
        inputs=inputs,
        g_min_kg_cm2=grade.g_min_kg_cm2,
        g_max_kg_cm2=grade.g_max_kg_cm2,
        g_capacity_reason="Gmin: usado para capacidad de compresion G*S",
        g_force_reason="Gmax: usado para fuerza horizontal H=G*A*Delta/h",
        gross_area_cm2=geom.gross_area_cm2,
        removed_area_cm2=removed_area,
        free_area_cm2=free_area,
        effective_area_cm2=effective_area,
        shape_factor=shape_factor,
        sigma_service_kg_cm2=sigma,
        sigma_gs_kg_cm2=sigma_gs,
        sigma_adm_kg_cm2=sigma_adm,
        epsilon_total=eps_lookup.epsilon,
        delta_compression_cm=delta_comp,
        delta_thermal_cm=delta_thermal,
        h_pad_tn=h_pad,
        friction_capacity_tn=friction,
        h_design_tn=h_design,
        h_design_case=h_design_case,
        checks=tuple(checks),
    )


def _fixed_bar_checks(
    inputs: SimpleSupportInputs,
    effective_area: float,
    h_design: float,
) -> list[SupportCheck]:
    geom = inputs.geometry
    bars = inputs.fixed_bars
    assert bars is not None
    checks: list[SupportCheck] = []
    edge_long = geom.length_cm / 2.0 - bars.spacing_long_cm / 2.0 - bars.diameter_cm / 2.0
    edge_trans = geom.width_cm / 2.0 - bars.spacing_trans_cm / 2.0 - bars.diameter_cm / 2.0
    edge_min = min(edge_long, edge_trans)
    sep_min = min(bars.spacing_long_cm, bars.spacing_trans_cm)
    v_pin = h_design / bars.n_bars
    m_pin_kg_cm = v_pin * 1000.0 * bars.moment_arm_cm
    flexure_term = (
        6.0 * m_pin_kg_cm
        / (PIN_PHI_FLEXURE * bars.diameter_cm**3 * bars.fy_kg_cm2)
    )
    shear_term = (
        2.2 * v_pin * 1000.0
        / (PIN_PHI_SHEAR * bars.diameter_cm**2 * bars.fy_kg_cm2)
    ) ** 2
    pin_interaction = flexure_term + shear_term
    hole_ratio = bars.hole_area_total_cm2 / geom.gross_area_cm2
    checks.extend(
        [
            _check(
                "Relacion de perforaciones",
                "A_huecos/A_bruta <= 0.05",
                f"{bars.hole_area_total_cm2:.2f}/{geom.gross_area_cm2:.2f}={hole_ratio:.4f}",
                hole_ratio,
                0.05,
                "-",
                notes="Limite constructivo interno para no debilitar excesivamente la plancha de neopreno.",
            ),
            _check(
                "Area neta con perforaciones",
                "A_eff = L*W - n*pi*d^2/4 > 0",
                f"{geom.gross_area_cm2:.1f}-{bars.hole_area_total_cm2:.1f}={effective_area:.1f}",
                0.0,
                effective_area,
                "cm2",
                less_equal=False,
            ),
            _check(
                "Borde de pasadores dentro del neopreno",
                "e >= 2d",
                f"e_min={edge_min:.2f}; 2d={2*bars.diameter_cm:.2f}",
                2.0 * bars.diameter_cm,
                edge_min,
                "cm",
                less_equal=True,
            ),
            _check(
                "Separacion de pasadores",
                "s >= 3d",
                f"s_min={sep_min:.2f}; 3d={3*bars.diameter_cm:.2f}",
                3.0 * bars.diameter_cm,
                sep_min,
                "cm",
                less_equal=True,
            ),
            _check(
                "Interaccion pasador corte-flexion",
                "6Mu/(phi_f*D^3*Fy)+[2.2Vu/(phi_v*D^2*Fy)]^2 <= 0.95",
                f"Vu={h_design:.3f}/{bars.n_bars}={v_pin:.3f} Tn; "
                f"Mu={v_pin*1000:.1f}*{bars.moment_arm_cm:.2f}={m_pin_kg_cm:.1f}; "
                f"I={flexure_term:.3f}+{shear_term:.3f}={pin_interaction:.3f}",
                pin_interaction,
                0.95,
                "-",
                notes=(
                    "AASHTO LRFD 6.13.1: Vu y Mu en la misma seccion critica. "
                    "phi_f=phi_v=1.00 configurados para el caso actual."
                ),
            ),
        ]
    )
    return checks


def _movable_plate_checks(
    inputs: SimpleSupportInputs,
    delta_thermal: float,
    h_pad: float,
    friction: float,
) -> list[SupportCheck]:
    geom = inputs.geometry
    demands = inputs.demands
    plates = inputs.plates
    assert plates is not None
    plate_area = geom.gross_area_cm2
    sigma_plate = demands.r_strength_tn * 1000.0 / plate_area
    return [
        _check(
            "Cortante por movimiento termico",
            "h >= 2*Delta_s",
            f"{geom.thickness_cm:.2f} >= 2*{delta_thermal:.3f}",
            2.0 * delta_thermal,
            geom.thickness_cm,
            "cm",
        ),
        _check(
            "Deformacion angular del neopreno",
            "gamma = Delta_s/h <= 0.50",
            f"{delta_thermal:.3f}/{geom.thickness_cm:.2f}={delta_thermal/geom.thickness_cm:.3f}",
            delta_thermal / geom.thickness_cm,
            0.50,
            "-",
        ),
        _check(
            "Fuerza H_pad movil",
            "H = Gmax*A*Delta/h",
            f"H_pad={h_pad:.3f}",
            h_pad,
            h_pad,
            "Tn",
        ),
        _check(
            "Friccion disponible",
            "H_pad <= mu*R_DC",
            f"{h_pad:.3f} <= {friction:.3f}",
            h_pad,
            friction,
            "Tn",
            notes=(
                "H_pad queda cubierta por friccion mu*R_DC."
                if h_pad <= friction + 1e-9
                else (
                    "H_pad supera la friccion. MOVIL_PLACAS no disena guia/anclaje; "
                    "la verificacion falla hasta existir un mecanismo de transferencia."
                )
            ),
        ),
        _check(
            "Espesor planchas superior/inferior",
            "t >= 1 pulg",
            f"{plates.thickness_cm:.2f} >= 2.54",
            2.54,
            plates.thickness_cm,
            "cm",
            less_equal=True,
        ),
        _check(
            "Compresion en planchas A36",
            "R/A <= 0.95Fy",
            f"Resistencia I: {demands.r_strength_tn*1000:.0f}/{plate_area:.1f}={sigma_plate:.2f}",
            sigma_plate,
            0.95 * plates.fy_kg_cm2,
            "kg/cm2",
        ),
    ]


def _check(
    name: str,
    formula: str,
    substitution: str,
    demand: float,
    limit: float,
    unit: str,
    *,
    less_equal: bool = True,
    notes: str = "",
) -> SupportCheck:
    ok = demand <= limit + 1e-9 if less_equal else demand < limit - 1e-9
    return SupportCheck(
        name=name,
        formula=formula,
        substitution=substitution,
        demand=demand,
        limit=limit,
        unit=unit,
        status="OK" if ok else "NO",
        notes=notes,
    )


def climate_temperature(zone: str, t_install_c: float) -> TemperatureRange:
    return TemperatureRange.mtc_default(zone.lower(), t_install_c)  # type: ignore[arg-type]
