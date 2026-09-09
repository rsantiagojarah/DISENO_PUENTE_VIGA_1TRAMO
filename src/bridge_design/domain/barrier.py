"""Concrete traffic barrier yield-line and connection checks."""

from dataclasses import dataclass, field
from math import sqrt
from typing import Literal

from bridge_design.domain.concrete_flexure import (
    DEFAULT_STEEL_ELASTIC_MODULUS_KG_CM2,
    rectangular_flexural_response,
)
from bridge_design.domain.materials import MaterialProperties
from bridge_design.validation.input_validators import require_non_negative, require_positive


ImpactPattern = Literal["segment", "end"]


@dataclass(frozen=True)
class BarrierImpactLoad:
    """Extreme-event collision load used for concrete barrier design."""

    test_level: str = "TL-4"
    transverse_force_tn: float = 24.47
    distribution_length_m: float = 1.07
    pattern: ImpactPattern = "segment"

    def __post_init__(self) -> None:
        require_positive(self.transverse_force_tn, "Ft")
        require_positive(self.distribution_length_m, "Lt")
        if self.pattern not in ("segment", "end"):
            raise ValueError("El patron de impacto debe ser 'segment' o 'end'.")


@dataclass(frozen=True)
class BarrierGeometry:
    """Concrete barrier geometric properties for a 1 m longitudinal strip."""

    height_m: float = 0.85
    base_width_m: float = 0.375
    cross_section_area_m2: float = 0.202875
    available_development_length_cm: float = 17.5
    top_additional_moment_tn_m: float = 0.0

    def __post_init__(self) -> None:
        require_positive(self.height_m, "H barrera")
        require_positive(self.base_width_m, "ancho de base barrera")
        require_positive(self.cross_section_area_m2, "area de barrera")
        require_positive(self.available_development_length_cm, "longitud disponible de anclaje")
        require_non_negative(self.top_additional_moment_tn_m, "Mb")


@dataclass(frozen=True)
class BarrierMwSegment:
    """One horizontal yield-line segment used to calculate Mw."""

    label: str
    concrete_width_cm: float
    effective_depths_cm: tuple[float, ...]
    steel_area_cm2: float

    def __post_init__(self) -> None:
        require_positive(self.concrete_width_cm, f"b {self.label}")
        require_positive(self.steel_area_cm2, f"As {self.label}")
        if not self.effective_depths_cm:
            raise ValueError(f"{self.label} debe tener al menos un peralte efectivo.")
        for depth in self.effective_depths_cm:
            require_positive(depth, f"d {self.label}")

    @property
    def average_effective_depth_cm(self) -> float:
        """Return the average effective depth used by the worked barrier model."""
        return sum(self.effective_depths_cm) / len(self.effective_depths_cm)


@dataclass(frozen=True)
class BarrierMcSegment:
    """One vertical cantilever segment used to calculate Mc."""

    label: str
    height_m: float
    effective_depth_cm: float

    def __post_init__(self) -> None:
        require_positive(self.height_m, f"altura {self.label}")
        require_positive(self.effective_depth_cm, f"d {self.label}")


@dataclass(frozen=True)
class BarrierSectionModel:
    """Section subdivisions and reinforcement used by the yield-line model."""

    mw_segments: tuple[BarrierMwSegment, ...]
    mc_segments: tuple[BarrierMcSegment, ...]
    dowel_bar_area_cm2: float = 1.29
    dowel_bar_diameter_cm: float = 1.27
    dowel_spacing_m: float = 0.17
    shear_transfer_legs: int = 1

    def __post_init__(self) -> None:
        if not self.mw_segments:
            raise ValueError("Se requiere al menos un segmento para Mw.")
        if not self.mc_segments:
            raise ValueError("Se requiere al menos un segmento para Mc.")
        require_positive(self.dowel_bar_area_cm2, "area barra dowel")
        require_positive(self.dowel_bar_diameter_cm, "diametro barra dowel")
        require_positive(self.dowel_spacing_m, "separacion dowel")
        if self.shear_transfer_legs < 1:
            raise ValueError("El numero de patas que cruzan la interface debe ser al menos 1.")

    @classmethod
    def new_jersey_image_default(cls) -> "BarrierSectionModel":
        """Return the New Jersey barrier section shown in the project reference image."""
        cover_cm = 5.08  # 2 in.
        horizontal_bar_area_cm2 = 0.71  # 3/8 in.
        horizontal_bar_diameter_cm = 0.95
        dowel_diameter_cm = 1.27  # 1/2 in.
        z_mw_cm = cover_cm + dowel_diameter_cm + horizontal_bar_diameter_cm / 2.0
        z_mc_cm = cover_cm + dowel_diameter_cm / 2.0
        return cls(
            mw_segments=(
                BarrierMwSegment(
                    "A1",
                    concrete_width_cm=47.0,
                    effective_depths_cm=(7.50, 17.90 - z_mw_cm, 20.00 - z_mw_cm),
                    steel_area_cm2=2.5 * horizontal_bar_area_cm2,
                ),
                BarrierMwSegment(
                    "A2",
                    concrete_width_cm=25.0,
                    effective_depths_cm=(20.00 - z_mw_cm, 37.50 - z_mw_cm),
                    steel_area_cm2=1.0 * horizontal_bar_area_cm2,
                ),
                BarrierMwSegment(
                    "A3",
                    concrete_width_cm=13.0,
                    effective_depths_cm=(37.50 - z_mw_cm,),
                    steel_area_cm2=0.5 * horizontal_bar_area_cm2,
                ),
            ),
            mc_segments=(
                BarrierMcSegment("A1", height_m=0.47, effective_depth_cm=17.90 - z_mc_cm),
                BarrierMcSegment(
                    "A2",
                    height_m=0.25,
                    effective_depth_cm=(20.00 + 37.50) / 2.0 - z_mc_cm,
                ),
                BarrierMcSegment("A3", height_m=0.13, effective_depth_cm=37.50 - z_mc_cm),
            ),
            dowel_bar_area_cm2=1.29,
            dowel_bar_diameter_cm=dowel_diameter_cm,
            dowel_spacing_m=0.17,
            shear_transfer_legs=1,
        )

    @property
    def dowel_area_cm2_m(self) -> float:
        """Return provided dowel steel area crossing the interface in cm2/m."""
        return self.shear_transfer_legs * self.dowel_bar_area_cm2 / self.dowel_spacing_m


@dataclass(frozen=True)
class ShearFrictionParameters:
    """AASHTO/MTC shear-friction coefficients for a selected interface case."""

    cohesion_kg_cm2: float = 5.0
    friction_factor: float = 0.6
    concrete_limit_factor: float = 0.2
    absolute_limit_kg_cm2: float = 56.0

    def __post_init__(self) -> None:
        require_non_negative(self.cohesion_kg_cm2, "c")
        require_positive(self.friction_factor, "mu")
        require_positive(self.concrete_limit_factor, "K1")
        require_positive(self.absolute_limit_kg_cm2, "K2")


@dataclass(frozen=True)
class HookedBarDevelopmentFactors:
    """Modification factors for hooked-bar development length."""

    side_cover_factor: float = 0.8
    coating_factor: float = 1.0
    reinforcement_excess_factor: float | None = None
    concrete_density_factor: float = 1.0
    minimum_hook_extension_db: float = 16.0

    def __post_init__(self) -> None:
        require_positive(self.side_cover_factor, "lambda rc")
        require_positive(self.coating_factor, "lambda cw")
        if self.reinforcement_excess_factor is not None:
            require_positive(self.reinforcement_excess_factor, "lambda er")
        require_positive(self.concrete_density_factor, "lambda")
        require_positive(self.minimum_hook_extension_db, "extension gancho")


@dataclass(frozen=True)
class BarrierDesignInputs:
    """Complete concrete barrier design input group."""

    geometry: BarrierGeometry = field(default_factory=BarrierGeometry)
    section_model: BarrierSectionModel = field(
        default_factory=BarrierSectionModel.new_jersey_image_default
    )
    impact_load: BarrierImpactLoad = field(default_factory=BarrierImpactLoad)
    shear_friction: ShearFrictionParameters = field(default_factory=ShearFrictionParameters)
    development_factors: HookedBarDevelopmentFactors = field(
        default_factory=HookedBarDevelopmentFactors
    )

    def __post_init__(self) -> None:
        # Only the documented New Jersey profile has section geometry.
        g = self.geometry
        if any(abs(value - target) > 1e-9 for value, target in (
            (g.height_m, 0.85), (g.base_width_m, 0.375),
            (g.cross_section_area_m2, 0.202875),
        )):
            raise ValueError(
                "Geometría fuera de alcance; el perfil New Jersey implementado mide "
                "H=0.85 m, base=0.375 m y A=0.202875 m2."
            )
        reference = BarrierSectionModel.new_jersey_image_default()
        if self.section_model.dowel_bar_diameter_cm != reference.dowel_bar_diameter_cm:
            raise ValueError(
                "Cambiar el diámetro requiere reconstruir los peraltes de los segmentos."
            )
        if (tuple((s.concrete_width_cm, s.effective_depths_cm) for s in self.section_model.mw_segments)
                != tuple((s.concrete_width_cm, s.effective_depths_cm) for s in reference.mw_segments)
                or self.section_model.mc_segments != reference.mc_segments):
            raise ValueError(
                "Los segmentos resistentes deben corresponder al perfil geométrico implementado."
            )


@dataclass(frozen=True)
class BarrierFlexuralComponent:
    """Nominal flexural resistance of one section component."""

    label: str
    steel_area_cm2: float
    concrete_width_cm: float
    effective_depth_cm: float
    compression_block_depth_cm: float
    nominal_moment_tn_m: float


@dataclass(frozen=True)
class BarrierFlexuralResistance:
    """Grouped Mw and Mc flexural resistances."""

    mw_tn_m: float
    mc_tn_m: float
    mw_components: tuple[BarrierFlexuralComponent, ...]
    mc_components: tuple[BarrierFlexuralComponent, ...]


@dataclass(frozen=True)
class YieldLineResult:
    """Critical yield-line length and transverse nominal resistance."""

    critical_length_m: float
    nominal_transverse_resistance_tn: float
    demand_transverse_force_tn: float
    impact_pattern: ImpactPattern

    @property
    def resistance_status(self) -> str:
        """Return OK when Rw resists Ft."""
        return "OK" if self.nominal_transverse_resistance_tn + 1e-9 >= self.demand_transverse_force_tn else "NO CUMPLE"


@dataclass(frozen=True)
class ShearTransferCheck:
    """Shear-friction transfer check between barrier and deck."""

    acting_shear_tn_m: float
    contact_area_cm2_m: float
    provided_avf_cm2_m: float
    permanent_compression_kg_m: float
    nominal_shear_raw_tn_m: float
    nominal_shear_limit_tn_m: float
    nominal_shear_tn_m: float

    @property
    def status(self) -> str:
        """Return OK when nominal interface shear resistance exceeds demand."""
        return "OK" if self.nominal_shear_tn_m + 1e-9 >= self.acting_shear_tn_m else "NO CUMPLE"


@dataclass(frozen=True)
class DowelCheck:
    """Minimum dowel reinforcement check for the interface."""

    required_avf_cm2_m: float
    provided_avf_cm2_m: float

    @property
    def status(self) -> str:
        """Return OK when provided dowel area exceeds the minimum."""
        return "OK" if self.provided_avf_cm2_m + 1e-9 >= self.required_avf_cm2_m else "NO CUMPLE"


@dataclass(frozen=True)
class DevelopmentLengthCheck:
    """Hooked dowel development length check."""

    basic_lhb_cm: float
    excess_reinforcement_factor: float
    modified_ldh_cm: float
    minimum_ldh_cm: float
    required_ldh_cm: float
    available_length_cm: float
    hook_extension_cm: float

    @property
    def status(self) -> str:
        """Return OK when available straight development length is sufficient."""
        return "OK" if self.available_length_cm + 1e-9 >= self.required_ldh_cm else "NO CUMPLE"


@dataclass(frozen=True)
class BarrierDesignResult:
    """Complete concrete barrier design result."""

    flexure: BarrierFlexuralResistance
    yield_line: YieldLineResult
    shear_transfer: ShearTransferCheck
    dowel: DowelCheck
    development: DevelopmentLengthCheck
    geometry: BarrierGeometry = field(default_factory=BarrierGeometry)
    line_weight_kg_m: float = 0.0
    impact_load: BarrierImpactLoad = field(default_factory=BarrierImpactLoad)


def design_concrete_barrier(
    inputs: BarrierDesignInputs,
    materials: MaterialProperties,
) -> BarrierDesignResult:
    """Return Mw, Mc, Lc, Rw, shear transfer, dowel and anchorage checks."""
    flexure = _barrier_flexural_resistance(inputs, materials)
    yield_line = _yield_line_result(inputs, flexure)
    shear_transfer = _shear_transfer_check(inputs, materials, yield_line)
    dowel = _dowel_check(inputs, materials, shear_transfer.contact_area_cm2_m)
    development = _development_length_check(inputs, materials, yield_line)
    return BarrierDesignResult(
        impact_load=inputs.impact_load,
        flexure=flexure,
        yield_line=yield_line,
        shear_transfer=shear_transfer,
        dowel=dowel,
        development=development,
        geometry=inputs.geometry,
        line_weight_kg_m=inputs.geometry.cross_section_area_m2 * materials.concrete.specific_weight_tn_m3 * 1000.0,
    )


def rectangular_nominal_moment_tn_m(
    steel_area_cm2: float,
    effective_depth_cm: float,
    concrete_width_cm: float,
    concrete_strength_kg_cm2: float,
    steel_yield_kg_cm2: float,
    phi: float = 1.0,
    steel_elastic_modulus_kg_cm2: float = DEFAULT_STEEL_ELASTIC_MODULUS_KG_CM2,
    extreme_tension_depth_cm: float | None = None,
) -> tuple[float, float]:
    """Return compatible (phi*Mn, a) for a singly reinforced section."""
    require_positive(steel_area_cm2, "As")
    require_positive(effective_depth_cm, "d")
    require_positive(concrete_width_cm, "b")
    require_positive(concrete_strength_kg_cm2, "f'c")
    require_positive(steel_yield_kg_cm2, "fy")
    require_positive(phi, "phi")
    require_positive(steel_elastic_modulus_kg_cm2, "Es")
    if phi > 1.0:
        raise ValueError("phi no debe exceder 1.0.")
    response = rectangular_flexural_response(
        steel_area_cm2=steel_area_cm2,
        concrete_width_cm=concrete_width_cm,
        effective_depth_cm=effective_depth_cm,
        concrete_strength_kg_cm2=concrete_strength_kg_cm2,
        steel_yield_kg_cm2=steel_yield_kg_cm2,
        steel_elastic_modulus_kg_cm2=steel_elastic_modulus_kg_cm2,
        extreme_tension_depth_cm=extreme_tension_depth_cm,
    )
    return (
        phi * response.nominal_moment_tn_m,
        response.compression_block_depth_cm,
    )


def critical_yield_line_length_m(
    height_m: float,
    distribution_length_m: float,
    mb_tn_m: float,
    mw_tn_m: float,
    mc_tn_m: float,
    pattern: ImpactPattern = "segment",
) -> float:
    """Return Lc for interior-segment or end/joint impact patterns."""
    require_positive(height_m, "H")
    require_positive(distribution_length_m, "Lt")
    require_non_negative(mb_tn_m, "Mb")
    require_positive(mw_tn_m, "Mw")
    require_positive(mc_tn_m, "Mc")
    multiplier = 8.0 if pattern == "segment" else 1.0
    if pattern not in ("segment", "end"):
        raise ValueError("El patron de impacto debe ser 'segment' o 'end'.")
    half_lt = distribution_length_m / 2.0
    return half_lt + sqrt(half_lt**2.0 + multiplier * height_m * (mb_tn_m + mw_tn_m) / mc_tn_m)


def nominal_transverse_resistance_tn(
    height_m: float,
    distribution_length_m: float,
    critical_length_m: float,
    mb_tn_m: float,
    mw_tn_m: float,
    mc_tn_m: float,
    pattern: ImpactPattern = "segment",
) -> float:
    """Return Rw from the AASHTO/MTC concrete barrier yield-line expression."""
    require_positive(height_m, "H")
    require_positive(distribution_length_m, "Lt")
    require_positive(critical_length_m, "Lc")
    require_non_negative(mb_tn_m, "Mb")
    require_positive(mw_tn_m, "Mw")
    require_positive(mc_tn_m, "Mc")
    denominator = 2.0 * critical_length_m - distribution_length_m
    require_positive(denominator, "2Lc-Lt")
    if pattern == "segment":
        flexural_term = 8.0 * mb_tn_m + 8.0 * mw_tn_m
    elif pattern == "end":
        flexural_term = mb_tn_m + mw_tn_m
    else:
        raise ValueError("El patron de impacto debe ser 'segment' o 'end'.")
    return 2.0 / denominator * (flexural_term + mc_tn_m * critical_length_m**2.0 / height_m)


def _barrier_flexural_resistance(
    inputs: BarrierDesignInputs,
    materials: MaterialProperties,
) -> BarrierFlexuralResistance:
    fc = materials.concrete.compressive_strength_kg_cm2
    fy = materials.steel.yield_strength_kg_cm2
    es = materials.steel.elastic_modulus_kg_cm2
    mw_components = tuple(
        _component_moment(
            segment.label,
            segment.steel_area_cm2,
            segment.concrete_width_cm,
            segment.average_effective_depth_cm,
            fc,
            fy,
            es,
        )
        for segment in inputs.section_model.mw_segments
    )
    mc_steel_area = inputs.section_model.dowel_area_cm2_m
    mc_components = tuple(
        _component_moment(
            segment.label,
            mc_steel_area,
            100.0,
            segment.effective_depth_cm,
            fc,
            fy,
            es,
        )
        for segment in inputs.section_model.mc_segments
    )
    mc_by_label = {component.label: component.nominal_moment_tn_m for component in mc_components}
    total_height = sum(segment.height_m for segment in inputs.section_model.mc_segments)
    mc = sum(
        segment.height_m * mc_by_label[segment.label]
        for segment in inputs.section_model.mc_segments
    ) / total_height
    return BarrierFlexuralResistance(
        mw_tn_m=sum(component.nominal_moment_tn_m for component in mw_components),
        mc_tn_m=mc,
        mw_components=mw_components,
        mc_components=mc_components,
    )


def _component_moment(
    label: str,
    steel_area_cm2: float,
    concrete_width_cm: float,
    effective_depth_cm: float,
    fc_kg_cm2: float,
    fy_kg_cm2: float,
    es_kg_cm2: float,
) -> BarrierFlexuralComponent:
    moment, compression_depth = rectangular_nominal_moment_tn_m(
        steel_area_cm2=steel_area_cm2,
        effective_depth_cm=effective_depth_cm,
        concrete_width_cm=concrete_width_cm,
        concrete_strength_kg_cm2=fc_kg_cm2,
        steel_yield_kg_cm2=fy_kg_cm2,
        phi=1.0,
        steel_elastic_modulus_kg_cm2=es_kg_cm2,
    )
    return BarrierFlexuralComponent(
        label=label,
        steel_area_cm2=steel_area_cm2,
        concrete_width_cm=concrete_width_cm,
        effective_depth_cm=effective_depth_cm,
        compression_block_depth_cm=compression_depth,
        nominal_moment_tn_m=moment,
    )


def _yield_line_result(
    inputs: BarrierDesignInputs,
    flexure: BarrierFlexuralResistance,
) -> YieldLineResult:
    geometry = inputs.geometry
    impact = inputs.impact_load
    lc = critical_yield_line_length_m(
        height_m=geometry.height_m,
        distribution_length_m=impact.distribution_length_m,
        mb_tn_m=geometry.top_additional_moment_tn_m,
        mw_tn_m=flexure.mw_tn_m,
        mc_tn_m=flexure.mc_tn_m,
        pattern=impact.pattern,
    )
    rw = nominal_transverse_resistance_tn(
        height_m=geometry.height_m,
        distribution_length_m=impact.distribution_length_m,
        critical_length_m=lc,
        mb_tn_m=geometry.top_additional_moment_tn_m,
        mw_tn_m=flexure.mw_tn_m,
        mc_tn_m=flexure.mc_tn_m,
        pattern=impact.pattern,
    )
    return YieldLineResult(
        critical_length_m=lc,
        nominal_transverse_resistance_tn=rw,
        demand_transverse_force_tn=impact.transverse_force_tn,
        impact_pattern=impact.pattern,
    )


def _shear_transfer_check(
    inputs: BarrierDesignInputs,
    materials: MaterialProperties,
    yield_line: YieldLineResult,
) -> ShearTransferCheck:
    geometry = inputs.geometry
    params = inputs.shear_friction
    acv = geometry.base_width_m * 100.0 * 100.0
    avf = inputs.section_model.dowel_area_cm2_m
    pc = geometry.cross_section_area_m2 * materials.concrete.specific_weight_tn_m3 * 1000.0
    raw_kg = params.cohesion_kg_cm2 * acv + params.friction_factor * (
        avf * materials.steel.yield_strength_kg_cm2 + pc
    )
    limit_kg = min(
        params.concrete_limit_factor * materials.concrete.compressive_strength_kg_cm2 * acv,
        params.absolute_limit_kg_cm2 * acv,
    )
    nominal_kg = min(raw_kg, limit_kg)
    acting = yield_line.nominal_transverse_resistance_tn / (
        yield_line.critical_length_m + 2.0 * geometry.height_m
    )
    return ShearTransferCheck(
        acting_shear_tn_m=acting,
        contact_area_cm2_m=acv,
        provided_avf_cm2_m=avf,
        permanent_compression_kg_m=pc,
        nominal_shear_raw_tn_m=raw_kg / 1000.0,
        nominal_shear_limit_tn_m=limit_kg / 1000.0,
        nominal_shear_tn_m=nominal_kg / 1000.0,
    )


def _dowel_check(
    inputs: BarrierDesignInputs,
    materials: MaterialProperties,
    contact_area_cm2_m: float,
) -> DowelCheck:
    required = 3.52 * contact_area_cm2_m / materials.steel.yield_strength_kg_cm2
    return DowelCheck(
        required_avf_cm2_m=required,
        provided_avf_cm2_m=inputs.section_model.dowel_area_cm2_m,
    )


def _development_length_check(
    inputs: BarrierDesignInputs,
    materials: MaterialProperties,
    yield_line: YieldLineResult,
) -> DevelopmentLengthCheck:
    factors = inputs.development_factors
    db = inputs.section_model.dowel_bar_diameter_cm
    fc = materials.concrete.compressive_strength_kg_cm2
    fy = materials.steel.yield_strength_kg_cm2
    basic = 0.076 * db * fy / sqrt(fc)
    excess_factor = factors.reinforcement_excess_factor
    if excess_factor is None:
        excess_factor = min(
            1.0,
            yield_line.demand_transverse_force_tn / yield_line.nominal_transverse_resistance_tn,
        )
    modified = basic * (
        factors.side_cover_factor * factors.coating_factor * excess_factor
        / factors.concrete_density_factor
    )
    minimum = max(8.0 * db, 15.24)
    required = max(modified, minimum)
    hook_extension = factors.minimum_hook_extension_db * db
    return DevelopmentLengthCheck(
        basic_lhb_cm=basic,
        excess_reinforcement_factor=excess_factor,
        modified_ldh_cm=modified,
        minimum_ldh_cm=minimum,
        required_ldh_cm=required,
        available_length_cm=inputs.geometry.available_development_length_cm,
        hook_extension_cm=hook_extension,
    )
