"""Reinforcement design for transverse concrete bridge slabs."""

from dataclasses import dataclass

from bridge_design.codes.mtc_2018 import (
    DEFAULT_FLEXURAL_RESISTANCE_FACTOR,
    DEFAULT_SHRINKAGE_TEMPERATURE_RATIO,
    DISTRIBUTION_REINFORCEMENT_REFERENCE,
    FLEXURAL_STRENGTH_REFERENCE,
    TEMPERATURE_REINFORCEMENT_REFERENCE,
    mtc_distribution_reinforcement_percent_for_transverse_primary,
)
from bridge_design.domain.load_combinations import (
    CombinedMomentResult,
    combine_transverse_slab_moments,
)
from bridge_design.domain.concrete_flexure import (
    DEFAULT_STEEL_ELASTIC_MODULUS_KG_CM2,
    required_rectangular_steel_area_cm2,
)
from bridge_design.domain.materials import MaterialProperties
from bridge_design.domain.rebar_catalog import (
    DEFAULT_MAX_SPACING_M,
    DEFAULT_MIN_SPACING_M,
    DEFAULT_SPACING_STEP_M,
    ReinforcementCaseOptions,
    SpacingGrid,
    generate_spacing_options,
)
from bridge_design.domain.transverse_slab import (
    TransverseSlabAnalysisResult,
    TransverseSlabGeometry,
)
from bridge_design.validation.input_validators import require_non_negative, require_positive


def mtc_cracking_moment_tn_m(
    section_modulus_cm3: float,
    concrete_strength_kg_cm2: float,
    variability_factor: float = 1.60 * 0.67,
) -> float:
    """Return Mcr for a nonprestressed normal-weight concrete section.

    This is the nonprestressed, monolithic form of MTC 2.9.1.4.4.2:
    ``Mcr = gamma1*gamma3*fr*S``, with ``fr = 2.01*sqrt(fc')`` in
    kgf/cm2. The default is ASTM A615 Grade 60: ``gamma1=1.60`` and
    ``gamma3=0.67``.
    """
    require_positive(section_modulus_cm3, "modulo resistente")
    require_positive(concrete_strength_kg_cm2, "f'c")
    require_positive(variability_factor, "factor de fisuracion")
    return variability_factor * 2.01 * concrete_strength_kg_cm2**0.5 * section_modulus_cm3 / 100000.0


def mtc_minimum_flexural_moment_tn_m(
    design_moment_tn_m: float,
    cracking_moment_tn_m: float,
    multiplier: float = 1.33,
) -> float:
    """Return the MTC minimum-strength target ``max(Mu, min(1.33Mu, Mcr))``."""
    require_non_negative(design_moment_tn_m, "Mu")
    require_non_negative(cracking_moment_tn_m, "Mcr")
    require_positive(multiplier, "factor 1.33Mu")
    return max(design_moment_tn_m, min(multiplier * design_moment_tn_m, cracking_moment_tn_m))

@dataclass(frozen=True)
class SlabReinforcementParameters:
    """Detailing assumptions used by the slab reinforcement design.

    The cover is measured to the outside of the single modeled main-bar layer;
    the adopted bar diameter is included in the centroid used for ``d``.
    """

    concrete_cover_cm: float = 5.0
    main_bar_diameter_cm: float = 1.59
    flexural_resistance_factor: float = DEFAULT_FLEXURAL_RESISTANCE_FACTOR
    shrinkage_temperature_ratio: float = DEFAULT_SHRINKAGE_TEMPERATURE_RATIO
    spacing_step_m: float = DEFAULT_SPACING_STEP_M
    minimum_spacing_m: float = DEFAULT_MIN_SPACING_M
    maximum_spacing_m: float = DEFAULT_MAX_SPACING_M

    def __post_init__(self) -> None:
        require_non_negative(self.concrete_cover_cm, "recubrimiento")
        require_positive(self.main_bar_diameter_cm, "diametro de barra principal")
        require_positive(self.flexural_resistance_factor, "phi flexion")
        if self.flexural_resistance_factor > 1.0:
            raise ValueError("phi flexion no debe exceder 1.0.")
        require_positive(self.shrinkage_temperature_ratio, "rho temperatura")
        require_positive(self.spacing_step_m, "paso de espaciamiento")
        require_positive(self.minimum_spacing_m, "espaciamiento minimo")
        require_positive(self.maximum_spacing_m, "espaciamiento maximo")
        if self.maximum_spacing_m < self.minimum_spacing_m:
            raise ValueError("El espaciamiento maximo debe ser mayor o igual al minimo.")


@dataclass(frozen=True)
class FlexuralSteelDesign:
    """Positive or negative flexural reinforcement result."""

    label: str
    direction: str
    controlling_combination_name: str
    position_m: float
    design_moment_tn_m: float
    effective_depth_cm: float
    strength_area_cm2_m: float
    minimum_area_cm2_m: float
    required_area_cm2_m: float
    spacing_options: ReinforcementCaseOptions | None = None
    cracking_moment_tn_m: float = 0.0
    minimum_capacity_moment_tn_m: float = 0.0
    capacity_minimum_area_cm2_m: float = 0.0
    reference: str = FLEXURAL_STRENGTH_REFERENCE


@dataclass(frozen=True)
class TemperatureSteelDesign:
    """Shrinkage and temperature reinforcement result."""

    ratio: float
    gross_area_cm2_m: float
    required_area_cm2_m: float
    spacing_options: ReinforcementCaseOptions | None = None
    reference: str = TEMPERATURE_REINFORCEMENT_REFERENCE


@dataclass(frozen=True)
class DistributionSteelDesign:
    """Longitudinal distribution reinforcement result."""

    effective_span_m: float
    percent_of_positive_steel: float
    positive_main_area_cm2_m: float
    required_area_cm2_m: float
    spacing_options: ReinforcementCaseOptions | None = None
    reference: str = DISTRIBUTION_REINFORCEMENT_REFERENCE


@dataclass(frozen=True)
class TransverseSlabReinforcementDesign:
    """Grouped reinforcement design requested for the transverse slab."""

    negative: FlexuralSteelDesign
    positive: FlexuralSteelDesign
    temperature: TemperatureSteelDesign
    distribution: DistributionSteelDesign
    parameters: SlabReinforcementParameters


def design_transverse_slab_reinforcement(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    analysis: TransverseSlabAnalysisResult,
    parameters: SlabReinforcementParameters | None = None,
) -> TransverseSlabReinforcementDesign:
    """Return negative, positive, temperature and distribution steel for the slab."""
    params = parameters or SlabReinforcementParameters()
    effective_depth_cm = _effective_depth_cm(geometry, params)
    strip_width_cm = geometry.strip_length_m * 100.0
    slab_height_cm = geometry.slab_thickness_m * 100.0
    minimum_area = _minimum_temperature_area_cm2_m(
        strip_width_cm=strip_width_cm,
        slab_height_cm=slab_height_cm,
        strip_length_m=geometry.strip_length_m,
        ratio=params.shrinkage_temperature_ratio,
    )
    spacing_grid = _spacing_grid(params)
    strength_rows = tuple(
        row
        for row in combine_transverse_slab_moments(analysis)
        if row.limit_state == "Resistencia"
    )

    positive = _design_flexural_steel(
        label="Acero positivo",
        direction="M+",
        row=max(
            (row for row in strength_rows if row.direction == "M+"),
            key=lambda item: item.combined_moment_tn_m,
        ),
        strip_width_cm=strip_width_cm,
        strip_length_m=geometry.strip_length_m,
        effective_depth_cm=effective_depth_cm,
        minimum_area_cm2_m=minimum_area,
        materials=materials,
        phi=params.flexural_resistance_factor,
        params=params,
    )
    negative = _design_flexural_steel(
        label="Acero negativo",
        direction="M-",
        row=min(
            (row for row in strength_rows if row.direction == "M-"),
            key=lambda item: item.combined_moment_tn_m,
        ),
        strip_width_cm=strip_width_cm,
        strip_length_m=geometry.strip_length_m,
        effective_depth_cm=effective_depth_cm,
        minimum_area_cm2_m=minimum_area,
        materials=materials,
        phi=params.flexural_resistance_factor,
        params=params,
    )
    temperature = TemperatureSteelDesign(
        ratio=params.shrinkage_temperature_ratio,
        gross_area_cm2_m=strip_width_cm * slab_height_cm / geometry.strip_length_m,
        required_area_cm2_m=minimum_area,
        spacing_options=generate_spacing_options(
            "Acero temperatura",
            minimum_area,
            spacing_grid,
        ),
    )
    distribution = _design_distribution_steel(geometry, positive, spacing_grid)
    return TransverseSlabReinforcementDesign(
        negative=negative,
        positive=positive,
        temperature=temperature,
        distribution=distribution,
        parameters=params,
    )


def flexural_steel_area_cm2(
    design_moment_tn_m: float,
    strip_width_cm: float,
    effective_depth_cm: float,
    concrete_strength_kg_cm2: float,
    steel_yield_kg_cm2: float,
    phi: float = DEFAULT_FLEXURAL_RESISTANCE_FACTOR,
    steel_elastic_modulus_kg_cm2: float = DEFAULT_STEEL_ELASTIC_MODULUS_KG_CM2,
    extreme_tension_depth_cm: float | None = None,
) -> float:
    """Return strain-compatible singly reinforced rectangular steel area.

    Units:
        design_moment_tn_m: factored moment in Tn*m.
        strip_width_cm, effective_depth_cm: section dimensions in cm.
        concrete_strength_kg_cm2, steel_yield_kg_cm2: material strengths.
        return: As in cm2 for the analyzed strip width.

    Reference:
        Manual de Puentes MTC 2018, Seccion 2.9.4.2 (5.7.3 AASHTO):
        MTC 2.7.1.1.4.2a and 2.7.2.4.2.1:
        equilibrium, strain compatibility and strain-dependent phi.
    """
    return required_rectangular_steel_area_cm2(
        design_moment_tn_m=design_moment_tn_m,
        concrete_width_cm=strip_width_cm,
        effective_depth_cm=effective_depth_cm,
        concrete_strength_kg_cm2=concrete_strength_kg_cm2,
        steel_yield_kg_cm2=steel_yield_kg_cm2,
        phi_limit=phi,
        steel_elastic_modulus_kg_cm2=steel_elastic_modulus_kg_cm2,
        extreme_tension_depth_cm=extreme_tension_depth_cm,
    )


def _design_flexural_steel(
    label: str,
    direction: str,
    row: CombinedMomentResult,
    strip_width_cm: float,
    strip_length_m: float,
    effective_depth_cm: float,
    minimum_area_cm2_m: float,
    materials: MaterialProperties,
    phi: float,
    params: SlabReinforcementParameters,
) -> FlexuralSteelDesign:
    gross_depth_cm = effective_depth_cm + params.concrete_cover_cm + params.main_bar_diameter_cm / 2.0
    cracking_moment = mtc_cracking_moment_tn_m(
        strip_width_cm * gross_depth_cm**2.0 / 6.0,
        materials.concrete.compressive_strength_kg_cm2,
        variability_factor=materials.steel.cracking_moment_factor,
    )
    minimum_moment = mtc_minimum_flexural_moment_tn_m(
        abs(row.combined_moment_tn_m), cracking_moment
    )
    strength_area = flexural_steel_area_cm2(
        design_moment_tn_m=minimum_moment,
        strip_width_cm=strip_width_cm,
        effective_depth_cm=effective_depth_cm,
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        phi=phi,
    ) / strip_length_m
    required_area = max(strength_area, minimum_area_cm2_m)
    spacing_options = generate_spacing_options(label, required_area, _spacing_grid(params))
    selected = spacing_options.recommended
    adopted_depth_cm = effective_depth_cm
    if selected is not None:
        adopted_depth_cm = effective_depth_cm + params.main_bar_diameter_cm / 2.0 - selected.bar.diameter_cm / 2.0
        require_positive(adopted_depth_cm, "peralte efectivo adoptado")
        strength_area = flexural_steel_area_cm2(
            design_moment_tn_m=minimum_moment,
            strip_width_cm=strip_width_cm,
            effective_depth_cm=adopted_depth_cm,
            concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
            steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
            phi=phi,
        ) / strip_length_m
        required_area = max(strength_area, minimum_area_cm2_m)
        if required_area > spacing_options.required_area_cm2_m + 1e-9:
            spacing_options = generate_spacing_options(label, required_area, _spacing_grid(params))
    return FlexuralSteelDesign(
        label=label,
        direction=direction,
        controlling_combination_name=row.combination_name,
        position_m=row.position_m,
        design_moment_tn_m=abs(row.combined_moment_tn_m),
        effective_depth_cm=adopted_depth_cm,
        strength_area_cm2_m=strength_area,
        minimum_area_cm2_m=minimum_area_cm2_m,
        required_area_cm2_m=required_area,
        spacing_options=spacing_options,
        cracking_moment_tn_m=cracking_moment,
        minimum_capacity_moment_tn_m=minimum_moment,
        capacity_minimum_area_cm2_m=strength_area,
    )


def _design_distribution_steel(
    geometry: TransverseSlabGeometry,
    positive: FlexuralSteelDesign,
    spacing_grid: SpacingGrid,
) -> DistributionSteelDesign:
    percent = mtc_distribution_reinforcement_percent_for_transverse_primary(
        geometry.girder_spacing_m
    )
    required_area = positive.required_area_cm2_m * percent / 100.0
    return DistributionSteelDesign(
        effective_span_m=geometry.girder_spacing_m,
        percent_of_positive_steel=percent,
        positive_main_area_cm2_m=positive.required_area_cm2_m,
        required_area_cm2_m=required_area,
        spacing_options=generate_spacing_options(
            "Acero distribucion",
            required_area,
            spacing_grid,
        ),
    )


def _spacing_grid(parameters: SlabReinforcementParameters) -> SpacingGrid:
    return SpacingGrid(
        step_m=parameters.spacing_step_m,
        minimum_m=parameters.minimum_spacing_m,
        maximum_m=parameters.maximum_spacing_m,
    )


def _effective_depth_cm(
    geometry: TransverseSlabGeometry,
    parameters: SlabReinforcementParameters,
) -> float:
    depth = (
        geometry.slab_thickness_m * 100.0
        - parameters.concrete_cover_cm
        - parameters.main_bar_diameter_cm / 2.0
    )
    require_positive(depth, "peralte efectivo")
    return depth


def _minimum_temperature_area_cm2_m(
    strip_width_cm: float,
    slab_height_cm: float,
    strip_length_m: float,
    ratio: float,
) -> float:
    require_positive(strip_width_cm, "b")
    require_positive(slab_height_cm, "h")
    require_positive(strip_length_m, "ancho longitudinal de analisis")
    require_positive(ratio, "rho temperatura")
    return ratio * strip_width_cm * slab_height_cm / strip_length_m
