"""Collision, shear and crack checks for deck overhang cantilever design."""

from bridge_design.domain.barrier import BarrierDesignResult
from bridge_design.domain.cantilever_slab import (
    CantileverBarrierCollisionDesign,
    CantileverCombinedMoment,
    CantileverCrackControlDesign,
    CantileverFlexuralSteelDesign,
    CantileverLoadEffect,
    CantileverShearDesign,
    CantileverSlabParameters,
    LoadGroup,
)
from bridge_design.domain.crack_control import (
    crack_control_compliance_statuses,
    maximum_crack_control_spacing_m,
)
from bridge_design.domain.materials import MaterialProperties
from bridge_design.domain.rebar_catalog import ReinforcementSpacingOption
from bridge_design.domain.transverse_slab import TransverseSlabGeometry
from bridge_design.units.converters import kg_cm2_to_ksi, kip_to_tn
from bridge_design.validation.input_validators import require_positive

COLLISION_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.4.3.2.3.4 y 2.4.3.5.1.2 "
    "(3.6.1.3.4 y 3.6.5.2 AASHTO): las cargas horizontales por colision "
    "contra barreras se consideran en el voladizo."
)
SHEAR_DESIGN_REFERENCE = (
    "Manual de Puentes MTC 2018, Art. 2.9.1.5.6 (5.8 AASHTO): "
    "modelo seccional para corte en concreto armado no pretensado."
)


def design_barrier_collision(
    barrier: BarrierDesignResult,
    combinations: tuple[CantileverCombinedMoment, ...],
) -> CantileverBarrierCollisionDesign:
    """Return overhang root moment caused by barrier collision."""
    height = _barrier_height_from_demand(barrier)
    transfer_length = barrier.yield_line.critical_length_m + 2.0 * height
    require_positive(transfer_length, "longitud de transferencia de colision")
    shear = barrier.yield_line.demand_transverse_force_tn / transfer_length
    collision_moment = shear * height
    permanent = abs(_strength_i_permanent_moment(combinations))
    return CantileverBarrierCollisionDesign(
        transverse_force_tn=barrier.yield_line.demand_transverse_force_tn,
        barrier_height_m=height,
        transfer_length_m=transfer_length,
        interface_shear_tn_m=shear,
        collision_moment_tn_m=collision_moment,
        permanent_moment_tn_m=permanent,
        design_moment_tn_m=permanent + collision_moment,
        reference=COLLISION_REFERENCE,
    )


def design_shear(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    params: CantileverSlabParameters,
    effects: tuple[CantileverLoadEffect, ...],
) -> CantileverShearDesign:
    """Return vertical one-way shear check at the overhang root."""
    dc = _group_load(effects, "DC")
    dw = _group_load(effects, "DW")
    pl = _group_load(effects, "PL")
    ll_im = _group_load(effects, "LL_IM")
    vu = 1.25 * dc + 1.50 * dw + 1.75 * pl + 1.75 * ll_im
    effective_depth = _effective_depth_cm(geometry, params)
    effective_shear_depth = _effective_shear_depth_cm(geometry, effective_depth)
    vc = _concrete_shear_resistance_tn(
        concrete_strength_kg_cm2=materials.concrete.compressive_strength_kg_cm2,
        width_cm=geometry.strip_length_m * 100.0,
        effective_shear_depth_cm=effective_shear_depth,
        beta=params.shear_beta,
    )
    phi_vc = params.shear_resistance_factor * vc
    return CantileverShearDesign(
        dc_shear_tn=dc,
        dc_factor=1.25,
        dw_shear_tn=dw,
        dw_factor=1.50,
        pl_shear_tn=pl,
        pl_factor=1.75,
        ll_im_shear_tn=ll_im,
        ll_im_factor=1.75,
        combined_shear_tn=vu,
        effective_shear_depth_cm=effective_shear_depth,
        phi=params.shear_resistance_factor,
        beta=params.shear_beta,
        vc_tn=vc,
        phi_vc_tn=phi_vc,
        status="CUMPLE" if phi_vc + 1e-9 >= vu else "NO CUMPLE",
        reference=SHEAR_DESIGN_REFERENCE,
    )


def review_crack_control(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    params: CantileverSlabParameters,
    combinations: tuple[CantileverCombinedMoment, ...],
    flexural: CantileverFlexuralSteelDesign,
    selected_spacing: ReinforcementSpacingOption | None = None,
) -> CantileverCrackControlDesign:
    """Return service crack-control check for top overhang steel."""
    service = next(row for row in combinations if row.combination_name == "SERVICIO I")
    option = selected_spacing or flexural.spacing_options.recommended or flexural.spacing_options.options[-1]
    dc_cm = params.concrete_cover_cm + option.bar.diameter_cm / 2.0
    effective_depth = geometry.slab_thickness_m * 100.0 - dc_cm
    require_positive(effective_depth, "peralte efectivo servicio")
    steel_stress = _service_steel_stress_kg_cm2(
        service_moment_tn_m=abs(service.combined_moment_tn_m),
        provided_area_cm2_m=option.provided_area_cm2_m,
        effective_depth_cm=effective_depth,
        lever_arm_factor=params.service_stress_lever_arm_factor,
    )
    stress_limit = 0.60 * materials.steel.yield_strength_kg_cm2
    steel_stress_used = min(steel_stress, stress_limit)
    maximum_spacing, beta_s = maximum_crack_control_spacing_m(
        steel_stress_used,
        dc_cm,
        geometry.slab_thickness_m * 100.0,
        params.crack_exposure_factor,
    )
    stress_status, spacing_status, status = crack_control_compliance_statuses(
        steel_stress,
        stress_limit,
        option.spacing_m,
        maximum_spacing,
    )
    return CantileverCrackControlDesign(
        service_combination_name=service.combination_name,
        service_moment_tn_m=abs(service.combined_moment_tn_m),
        bar_label=option.bar.label,
        provided_spacing_m=option.spacing_m,
        provided_area_cm2_m=option.provided_area_cm2_m,
        steel_stress_kg_cm2=steel_stress,
        steel_stress_used_kg_cm2=steel_stress_used,
        steel_stress_limit_kg_cm2=stress_limit,
        beta_s=beta_s,
        dc_cm=dc_cm,
        maximum_spacing_m=maximum_spacing,
        stress_status=stress_status,
        spacing_status=spacing_status,
        status=status,
    )


def _strength_i_permanent_moment(
    combinations: tuple[CantileverCombinedMoment, ...],
) -> float:
    row = next(item for item in combinations if item.combination_name == "RESISTENCIA I")
    return row.dc_factor * row.dc_moment_tn_m + row.dw_factor * row.dw_moment_tn_m


def _barrier_height_from_demand(barrier: BarrierDesignResult) -> float:
    transfer = barrier.yield_line.nominal_transverse_resistance_tn / (
        barrier.shear_transfer.acting_shear_tn_m
    )
    height = (transfer - barrier.yield_line.critical_length_m) / 2.0
    require_positive(height, "altura de barrera para colision")
    return height


def _group_load(effects: tuple[CantileverLoadEffect, ...], group: LoadGroup) -> float:
    return sum(effect.load_tn for effect in effects if effect.group == group)


def _concrete_shear_resistance_tn(
    concrete_strength_kg_cm2: float,
    width_cm: float,
    effective_shear_depth_cm: float,
    beta: float,
) -> float:
    fc_ksi = kg_cm2_to_ksi(concrete_strength_kg_cm2)
    bv_in = width_cm / 2.54
    dv_in = effective_shear_depth_cm / 2.54
    return kip_to_tn(0.0316 * beta * fc_ksi**0.5 * bv_in * dv_in)


def _service_steel_stress_kg_cm2(
    service_moment_tn_m: float,
    provided_area_cm2_m: float,
    effective_depth_cm: float,
    lever_arm_factor: float,
) -> float:
    require_positive(provided_area_cm2_m, "As provisto")
    require_positive(effective_depth_cm, "d")
    require_positive(lever_arm_factor, "factor brazo servicio")
    if service_moment_tn_m <= 0.0:
        return 1e-9
    moment_kg_cm = service_moment_tn_m * 100000.0
    lever_arm_cm = lever_arm_factor * effective_depth_cm
    return moment_kg_cm / (provided_area_cm2_m * lever_arm_cm)


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


def _effective_shear_depth_cm(
    geometry: TransverseSlabGeometry,
    effective_depth_cm: float,
) -> float:
    return max(0.9 * effective_depth_cm, 0.72 * geometry.slab_thickness_m * 100.0)
