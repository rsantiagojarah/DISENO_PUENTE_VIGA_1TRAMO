"""MTC 2018 skew correction for monolithic concrete T-girder support shear."""

from dataclasses import dataclass
from math import radians, tan

from bridge_design.codes.mtc_2018 import _concrete_t_girder_longitudinal_stiffness_in4
from bridge_design.units.converters import m_to_ft, m_to_in
from bridge_design.validation.input_validators import require_positive, require_range

SKEW_SHEAR_REFERENCE = (
    "MTC 2018 Art. 2.6.4.2.2.3c y Tabla 2.6.4.2.2.3c-1 "
    "(AASHTO 4.6.2.2.3c)."
)


@dataclass(frozen=True)
class SkewShearCorrection:
    """Calculated trace; feet, inches and in4 as required by the MTC table."""

    angle_deg: float
    span_ft: float
    slab_thickness_in: float
    longitudinal_stiffness_in4: float
    factor: float


def concrete_t_girder_skew_shear_correction(
    angle_deg: float, span_length_m: float, girder_spacing_m: float,
    slab_thickness_m: float, girder_depth_m: float, web_width_m: float,
    girder_count: int,
) -> SkewShearCorrection:
    """Return Cv=1+0.20*(12*L*ts**3/Kg)**0.3*tan(angle).

    MTC 2018 Table 2.6.4.2.2.3c-1, concrete deck / concrete T girders.
    Inputs are metres and degrees. Kg=n*(I+A*eg**2), n=1 for the
    monolithic concrete sections supported here; girder_depth excludes slab.
    Cv is conservatively held constant for every girder and the full span.
    It multiplies vehicular shear g only, including fatigue; moments and
    non-vehicular actions retain their original factors. No moment reduction.
    Zero skew preserves the existing uncorrected analysis and its validation.
    """
    require_range(angle_deg, "Angulo de esviaje (grados)", 0.0, 60.0)
    for value, name in ((span_length_m, "L"), (girder_spacing_m, "S"),
                        (slab_thickness_m, "ts"), (girder_depth_m, "hbajo"),
                        (web_width_m, "bw")):
        require_positive(value, name)
    span_ft = m_to_ft(span_length_m)
    slab_in = m_to_in(slab_thickness_m)
    kg = _concrete_t_girder_longitudinal_stiffness_in4(
        m_to_in(web_width_m), m_to_in(girder_depth_m),
        m_to_in((girder_depth_m + slab_thickness_m) / 2.0),
    )
    if angle_deg == 0.0:
        factor = 1.0
    else:
        require_range(m_to_ft(girder_spacing_m), "S para esviaje (ft)", 3.5, 16.0)
        require_range(span_ft, "L para esviaje (ft)", 20.0, 240.0)
        if girder_count < 4:
            raise ValueError("La correccion de esviaje para vigas T requiere al menos 4 vigas.")
        factor = 1.0 + 0.20 * (12.0 * span_ft * slab_in**3 / kg)**0.3 * tan(radians(angle_deg))
    return SkewShearCorrection(angle_deg, span_ft, slab_in, kg, factor)
