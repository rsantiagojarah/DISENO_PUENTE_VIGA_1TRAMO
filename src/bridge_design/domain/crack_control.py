"""Crack control checks for slab flexural reinforcement."""

from dataclasses import dataclass

from bridge_design.codes.mtc_2018 import (
    CRACK_CONTROL_REINFORCEMENT_REFERENCE,
    DEFAULT_CRACK_CONTROL_EXPOSURE_FACTOR,
    DEFAULT_SERVICE_STRESS_LEVER_ARM_FACTOR,
)
from bridge_design.domain.load_combinations import (
    CombinedMomentResult,
    combine_transverse_slab_moments,
)
from bridge_design.domain.materials import MaterialProperties
from bridge_design.domain.rebar_catalog import ReinforcementSpacingOption
from bridge_design.domain.reinforcement import (
    FlexuralSteelDesign,
    TransverseSlabReinforcementDesign,
)
from bridge_design.domain.transverse_slab import (
    TransverseSlabAnalysisResult,
    TransverseSlabGeometry,
)
from bridge_design.validation.input_validators import require_positive


KG_CM2_TO_MPA = 0.0980665


@dataclass(frozen=True)
class CrackControlCheck:
    """Crack control result for one main reinforcement direction."""

    label: str
    direction: str
    service_combination_name: str
    service_moment_tn_m: float
    bar_label: str
    bar_area_cm2: float
    provided_spacing_m: float
    provided_area_cm2_m: float
    steel_stress_kg_cm2: float
    steel_stress_used_kg_cm2: float
    beta_s: float
    dc_cm: float
    maximum_spacing_m: float
    status: str
    reference: str = CRACK_CONTROL_REINFORCEMENT_REFERENCE

    @property
    def is_compliant(self) -> bool:
        """Return whether provided spacing satisfies crack control."""
        return self.status == "CUMPLE"


@dataclass(frozen=True)
class SlabCrackControlReview:
    """Crack control review for the requested main slab steels."""

    negative_main: CrackControlCheck
    positive_main: CrackControlCheck


def review_transverse_slab_crack_control(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    analysis: TransverseSlabAnalysisResult,
    reinforcement: TransverseSlabReinforcementDesign,
    negative_spacing: ReinforcementSpacingOption | None = None,
    positive_spacing: ReinforcementSpacingOption | None = None,
) -> SlabCrackControlReview:
    """Return crack control review for negative and positive main steel."""
    service_rows = tuple(
        row
        for row in combine_transverse_slab_moments(analysis)
        if row.combination_name == "SERVICIO I"
    )
    negative_row = min(
        (row for row in service_rows if row.direction == "M-"),
        key=lambda item: item.combined_moment_tn_m,
    )
    positive_row = max(
        (row for row in service_rows if row.direction == "M+"),
        key=lambda item: item.combined_moment_tn_m,
    )
    return SlabCrackControlReview(
        negative_main=_review_flexural_steel(
            "E.1 Acero principal negativo",
            reinforcement.negative,
            negative_row,
            geometry,
            materials,
            reinforcement,
            negative_spacing,
        ),
        positive_main=_review_flexural_steel(
            "E.2 Acero principal positivo",
            reinforcement.positive,
            positive_row,
            geometry,
            materials,
            reinforcement,
            positive_spacing,
        ),
    )


def maximum_crack_control_spacing_m(
    steel_stress_kg_cm2: float,
    dc_cm: float,
    slab_thickness_cm: float,
    exposure_factor: float = DEFAULT_CRACK_CONTROL_EXPOSURE_FACTOR,
) -> tuple[float, float]:
    """Return maximum crack-control spacing and beta_s.

    Units:
        steel_stress_kg_cm2: service steel stress used in the check.
        dc_cm: distance from tension face to closest bar center.
        slab_thickness_cm: total slab thickness.
        return: (maximum spacing in m, beta_s).

    Reference:
        AASHTO LRFD 5.7.3.4/MTC 2.9.4.4:
        s <= 123000*gamma_e/(beta_s*f_ss) - 2*d_c, with MPa and mm.
    """
    require_positive(steel_stress_kg_cm2, "fss")
    require_positive(dc_cm, "dc")
    require_positive(slab_thickness_cm, "h")
    if slab_thickness_cm <= dc_cm:
        raise ValueError("h debe ser mayor que dc para calcular beta_s.")
    require_positive(exposure_factor, "gamma_e")

    beta_s = 1.0 + dc_cm / (0.7 * (slab_thickness_cm - dc_cm))
    steel_stress_mpa = steel_stress_kg_cm2 * KG_CM2_TO_MPA
    maximum_spacing_mm = 123000.0 * exposure_factor / (beta_s * steel_stress_mpa)
    maximum_spacing_mm -= 2.0 * dc_cm * 10.0
    return max(maximum_spacing_mm / 1000.0, 0.0), beta_s


def _review_flexural_steel(
    label: str,
    steel: FlexuralSteelDesign,
    service_row: CombinedMomentResult,
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    reinforcement: TransverseSlabReinforcementDesign,
    selected_spacing: ReinforcementSpacingOption | None,
) -> CrackControlCheck:
    selected = selected_spacing or _recommended_option(steel)
    dc_cm = (
        reinforcement.parameters.concrete_cover_cm
        + selected.bar.diameter_cm / 2.0
    )
    slab_thickness_cm = geometry.slab_thickness_m * 100.0
    effective_depth_cm = slab_thickness_cm - dc_cm
    steel_stress = _service_steel_stress_kg_cm2(
        service_moment_tn_m=abs(service_row.combined_moment_tn_m),
        provided_area_cm2_m=selected.provided_area_cm2_m,
        effective_depth_cm=effective_depth_cm,
    )
    stress_limit = 0.60 * materials.steel.yield_strength_kg_cm2
    steel_stress_used = min(steel_stress, stress_limit)
    maximum_spacing, beta_s = maximum_crack_control_spacing_m(
        steel_stress_used,
        dc_cm,
        slab_thickness_cm,
    )
    return CrackControlCheck(
        label=label,
        direction=steel.direction,
        service_combination_name=service_row.combination_name,
        service_moment_tn_m=abs(service_row.combined_moment_tn_m),
        bar_label=selected.bar.label,
        bar_area_cm2=selected.bar.area_cm2,
        provided_spacing_m=selected.spacing_m,
        provided_area_cm2_m=selected.provided_area_cm2_m,
        steel_stress_kg_cm2=steel_stress,
        steel_stress_used_kg_cm2=steel_stress_used,
        beta_s=beta_s,
        dc_cm=dc_cm,
        maximum_spacing_m=maximum_spacing,
        status="CUMPLE" if selected.spacing_m <= maximum_spacing + 1e-9 else "NO CUMPLE",
    )


def _recommended_option(steel: FlexuralSteelDesign) -> ReinforcementSpacingOption:
    if steel.spacing_options is None or steel.spacing_options.recommended is None:
        raise ValueError(f"No hay distribucion recomendada para {steel.label}.")
    return steel.spacing_options.recommended


def _service_steel_stress_kg_cm2(
    service_moment_tn_m: float,
    provided_area_cm2_m: float,
    effective_depth_cm: float,
) -> float:
    require_positive(provided_area_cm2_m, "As provisto")
    require_positive(effective_depth_cm, "d")
    if service_moment_tn_m <= 0.0:
        return 1e-9
    moment_kg_cm = service_moment_tn_m * 100000.0
    lever_arm_cm = DEFAULT_SERVICE_STRESS_LEVER_ARM_FACTOR * effective_depth_cm
    return moment_kg_cm / (provided_area_cm2_m * lever_arm_cm)
