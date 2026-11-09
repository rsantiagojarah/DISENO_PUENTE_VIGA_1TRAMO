"""Shared skew trace for interior and exterior monolithic T girders."""

from bridge_design.codes.skew import concrete_t_girder_skew_shear_correction


def girder_skew_correction(geometry):
    return concrete_t_girder_skew_shear_correction(
        geometry.skew_angle_deg, geometry.span_length_m, geometry.girder_spacing_m,
        geometry.slab_thickness_m, geometry.girder_total_height_m,
        geometry.web_width_m, geometry.girder_count,
    )
