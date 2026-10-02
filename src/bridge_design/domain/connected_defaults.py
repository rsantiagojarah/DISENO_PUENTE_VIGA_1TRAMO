"""Editable PDF geometry and user-supplied deck reactions for connected abutments."""

from bridge_design.domain.abutment import AbutmentGeometryInputs, AbutmentLoadInputs


REFERENCE_CLEAR_SPAN_M = 13.10
REFERENCE_SLAB_THICKNESS_M = 0.75
REFERENCE_TRANSITION_M = 1.00


def connected_load_defaults():
    return AbutmentLoadInputs(pdc_tn_m=8.959, pdw_tn_m=0.545, ppl_tn_m=0.762,
                              pll_im_tn_m=6.92, braking_tn_m=1.33)


def connected_geometry_defaults():
    return AbutmentGeometryInputs(
        retained_height_m=10.70,
        bridge_length_m=14.10,
        seat_block_height_m=1.15,
        seat_wall_width_m=0.35,
        bearing_seat_length_m=1.00,
        backwall_drop_m=0.50,
        backwall_taper_height_m=0.40,
        backfill_step_width_m=0.35,
        small_batter_width_m=0.00,
        upper_stem_thickness_m=1.00,
        lower_stem_thickness_m=1.00,
        footing_width_m=5.00,
        footing_thickness_m=1.50,
        toe_length_m=2.50,
        front_soil_depth_m=1.50,
    )
