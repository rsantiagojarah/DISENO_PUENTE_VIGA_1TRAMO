"""Internal detailing calculations for concrete deck overhang design."""

from dataclasses import replace

from bridge_design.codes.mtc_2018 import (
    FLEXURAL_STRENGTH_REFERENCE,
    TEMPERATURE_REINFORCEMENT_REFERENCE,
    TENSION_DEVELOPMENT_REFERENCE,
    mtc_tension_development_length_cm,
)
from bridge_design.domain.cantilever_slab import (
    CantileverCombinedMoment,
    CantileverDevelopmentDesign,
    CantileverFlexuralSteelDesign,
    CantileverLoadEffect,
    CantileverSlabParameters,
    CantileverTemperatureSteelDesign,
    LoadGroup,
)
from bridge_design.domain.load_combinations import (
    LoadCombination,
    default_transverse_slab_combinations,
)
from bridge_design.domain.materials import MaterialProperties
from bridge_design.domain.rebar_catalog import (
    ReinforcementSpacingOption,
    SpacingGrid,
    generate_spacing_options,
)
from bridge_design.domain.reinforcement import (
    flexural_steel_area_cm2,
    mtc_cracking_moment_tn_m,
    mtc_minimum_flexural_moment_tn_m,
)
from bridge_design.domain.transverse_slab import TransverseSlabGeometry
from bridge_design.validation.input_validators import require_positive


def combine_cantilever_moments(
    effects: tuple[CantileverLoadEffect, ...],
    combinations: tuple[LoadCombination, ...] | None = None,
) -> tuple[CantileverCombinedMoment, ...]:
    """Return LRFD overhang root moments."""
    definitions = combinations or default_transverse_slab_combinations()
    by_group = {
        "DC": _group_moment(effects, "DC"),
        "DW": _group_moment(effects, "DW"),
        "PL": _group_moment(effects, "PL"),
        "LL_IM": _group_moment(effects, "LL_IM"),
    }
    rows: list[CantileverCombinedMoment] = []
    for combination in definitions:
        dc_factor = combination.dc.for_effect(by_group["DC"], "min")
        dw_factor = combination.dw.for_effect(by_group["DW"], "min")
        pl_factor = combination.pl.for_effect(by_group["PL"], "min")
        ll_factor = combination.ll_im.for_effect(by_group["LL_IM"], "min")
        combined = (
            dc_factor * by_group["DC"]
            + dw_factor * by_group["DW"]
            + pl_factor * by_group["PL"]
            + ll_factor * by_group["LL_IM"]
        )
        rows.append(
            CantileverCombinedMoment(
                combination_name=combination.name,
                limit_state=combination.limit_state,
                dc_moment_tn_m=by_group["DC"],
                dc_factor=dc_factor,
                dw_moment_tn_m=by_group["DW"],
                dw_factor=dw_factor,
                pl_moment_tn_m=by_group["PL"],
                pl_factor=pl_factor,
                ll_im_moment_tn_m=by_group["LL_IM"],
                ll_im_factor=ll_factor,
                combined_moment_tn_m=combined,
            )
        )
    return tuple(rows)


def design_flexural_steel(
    geometry, materials, params, controlling, collision=None,
):
    """Envelope steel demands without mixing moment and tension across cases."""
    candidates = [_design_flexural_case(geometry, materials, params, controlling)]
    if collision is not None:
        # B-B is the modeled root section; A-A belongs to the barrier interface.
        case = next(c for c in collision.cases if c.name == "Caso 1 - seccion B-B")
        compatible = replace(controlling,
            combination_name="EVENTO EXTREMO II - colision barrera B-B",
            combined_moment_tn_m=-case.moment_tn_m)
        demand = replace(collision, design_moment_tn_m=case.moment_tn_m,
                         axial_tension_tn_m=case.axial_tension_tn_m)
        candidates.append(_design_flexural_case(geometry, materials, params, compatible, demand))
    return max(candidates, key=lambda c: c.required_area_cm2_m)


def _design_flexural_case(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    params: CantileverSlabParameters,
    controlling: CantileverCombinedMoment,
    collision=None,
) -> CantileverFlexuralSteelDesign:
    """Return top flexural steel required at the overhang root."""
    effective_depth = _effective_depth_cm(geometry, params)
    strength_moment = controlling.design_moment_tn_m
    controlling_name = controlling.combination_name
    if collision is not None and collision.design_moment_tn_m > strength_moment:
        strength_moment = collision.design_moment_tn_m
        controlling_name = "EVENTO EXTREMO II - colision barrera"
    cracking_moment = mtc_cracking_moment_tn_m(
        geometry.strip_length_m * 100.0 * (geometry.slab_thickness_m * 100.0) ** 2.0 / 6.0,
        materials.concrete.compressive_strength_kg_cm2,
        variability_factor=materials.steel.cracking_moment_factor,
    )
    minimum_moment = mtc_minimum_flexural_moment_tn_m(strength_moment, cracking_moment)
    # FHWA PSC example 4.10: As(M) + N/fy is a conservative combined
    # flexure/tension design. Retain phi <= 0.90 for this envelope.
    axial_area = (collision.axial_tension_tn_m * 1000.0 /
                  (params.flexural_resistance_factor * materials.steel.yield_strength_kg_cm2)
                  if collision is not None else 0.0)
    strength_area = flexural_steel_area_cm2(
        design_moment_tn_m=minimum_moment,
        strip_width_cm=geometry.strip_length_m * 100.0,
        effective_depth_cm=effective_depth,
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        phi=params.flexural_resistance_factor,
    ) / geometry.strip_length_m + axial_area
    minimum_area = minimum_temperature_area_cm2_m(geometry, params)
    required = max(strength_area, minimum_area)
    spacing_options = generate_spacing_options(
        "Acero superior voladizo", required, _spacing_grid(params)
    )
    selected = spacing_options.recommended
    if selected is not None:
        effective_depth = geometry.slab_thickness_m * 100.0 - params.concrete_cover_cm - selected.bar.diameter_cm / 2.0
        require_positive(effective_depth, "peralte efectivo adoptado")
        strength_area = flexural_steel_area_cm2(
            design_moment_tn_m=minimum_moment,
            strip_width_cm=geometry.strip_length_m * 100.0,
            effective_depth_cm=effective_depth,
            concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
            steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
            phi=params.flexural_resistance_factor,
        ) / geometry.strip_length_m + axial_area
        required = max(strength_area, minimum_area)
        if required > spacing_options.required_area_cm2_m + 1e-9:
            spacing_options = generate_spacing_options(
                "Acero superior voladizo", required, _spacing_grid(params)
            )
            selected = spacing_options.recommended
            if selected is not None:
                effective_depth = geometry.slab_thickness_m * 100.0 - params.concrete_cover_cm - selected.bar.diameter_cm / 2.0
    return CantileverFlexuralSteelDesign(
        controlling_combination_name=controlling_name,
        design_moment_tn_m=strength_moment,
        effective_depth_cm=effective_depth,
        strength_area_cm2_m=strength_area,
        minimum_area_cm2_m=minimum_area,
        required_area_cm2_m=required,
        spacing_options=spacing_options,
        cracking_moment_tn_m=cracking_moment,
        minimum_capacity_moment_tn_m=minimum_moment,
        reference=FLEXURAL_STRENGTH_REFERENCE,
    )


def design_temperature_steel(
    geometry: TransverseSlabGeometry,
    params: CantileverSlabParameters,
) -> CantileverTemperatureSteelDesign:
    """Return shrinkage and temperature steel for the overhang."""
    required = minimum_temperature_area_cm2_m(geometry, params)
    gross = geometry.strip_length_m * 100.0 * geometry.slab_thickness_m * 100.0
    return CantileverTemperatureSteelDesign(
        ratio=params.shrinkage_temperature_ratio,
        gross_area_cm2_m=gross / geometry.strip_length_m,
        required_area_cm2_m=required,
        spacing_options=generate_spacing_options(
            "Acero temperatura voladizo",
            required,
            _spacing_grid(params),
        ),
        reference=TEMPERATURE_REINFORCEMENT_REFERENCE,
    )


def design_development(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    params: CantileverSlabParameters,
    flexural: CantileverFlexuralSteelDesign,
    selected_spacing: ReinforcementSpacingOption | None = None,
) -> CantileverDevelopmentDesign:
    """Return straight development and total additional bar length."""
    option = selected_spacing or flexural.spacing_options.recommended or flexural.spacing_options.options[-1]
    excess_factor = min(1.0, flexural.required_area_cm2_m / option.provided_area_cm2_m)
    excess_factor = max(0.4, excess_factor)
    required_ld, basic_ld = mtc_tension_development_length_cm(
        bar_diameter_cm=option.bar.diameter_cm,
        steel_yield_kg_cm2=materials.steel.yield_strength_kg_cm2,
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        location_factor=params.development_location_factor,
        coating_factor=params.development_coating_factor,
        lightweight_factor=params.development_lightweight_factor,
        confinement_factor=params.development_confinement_factor,
        excess_reinforcement_factor=excess_factor,
    )
    cutoff_extension = max(
        flexural.effective_depth_cm,
        15.0 * option.bar.diameter_cm,
        geometry.overhang_m * 100.0 / 20.0,
    )
    exterior_projection = max(geometry.overhang_m - params.concrete_cover_cm / 100.0, 0.0)
    interior_anchor = required_ld / 100.0
    return CantileverDevelopmentDesign(
        bar_label=option.bar.label,
        bar_diameter_cm=option.bar.diameter_cm,
        provided_area_cm2_m=option.provided_area_cm2_m,
        required_area_cm2_m=flexural.required_area_cm2_m,
        excess_reinforcement_factor=excess_factor,
        basic_development_length_cm=basic_ld,
        required_development_length_cm=required_ld,
        minimum_past_cutoff_extension_cm=cutoff_extension,
        exterior_projection_length_m=exterior_projection,
        interior_anchor_length_m=interior_anchor,
        total_additional_bar_length_m=exterior_projection + interior_anchor,
        status="OK" if option.is_compliant else "NO CUMPLE",
        reference=TENSION_DEVELOPMENT_REFERENCE,
    )


def minimum_temperature_area_cm2_m(
    geometry: TransverseSlabGeometry,
    parameters: CantileverSlabParameters,
) -> float:
    """Return minimum slab steel area by the adopted temperature ratio."""
    return (
        parameters.shrinkage_temperature_ratio
        * geometry.strip_length_m
        * 100.0
        * geometry.slab_thickness_m
        * 100.0
        / geometry.strip_length_m
    )


def _group_moment(effects: tuple[CantileverLoadEffect, ...], group: LoadGroup) -> float:
    return sum(effect.root_moment_tn_m for effect in effects if effect.group == group)


def _spacing_grid(parameters: CantileverSlabParameters) -> SpacingGrid:
    return SpacingGrid(
        step_m=parameters.spacing_step_m,
        minimum_m=parameters.minimum_spacing_m,
        maximum_m=parameters.maximum_spacing_m,
    )


def _effective_depth_cm(
    geometry: TransverseSlabGeometry,
    parameters: CantileverSlabParameters,
) -> float:
    depth = (
        geometry.slab_thickness_m * 100.0
        - parameters.concrete_cover_cm
        - parameters.main_bar_diameter_cm / 2.0
    )
    require_positive(depth, "peralte efectivo")
    return depth
