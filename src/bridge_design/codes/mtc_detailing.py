"""Shared bar termination provisions, MTC 2018 Art. 2.6.5.6.1.2.1."""

from bridge_design.validation.input_validators import require_non_negative, require_positive


def minimum_flexural_cutoff_extension_cm(effective_depth_cm, bar_diameter_cm, clear_span_cm):
    """Extension beyond theoretical cutoff; AASHTO LRFD 5.11.1.2.1.

    Extracted from the existing cantilever slab detailing calculation. This
    geometric extension does not replace development of the continuing bars.
    """
    require_positive(effective_depth_cm, "Peralte efectivo para corte de barras")
    require_positive(bar_diameter_cm, "Diametro de barra")
    require_non_negative(clear_span_cm, "Luz para corte de barras")
    return max(effective_depth_cm, 15.0 * bar_diameter_cm, clear_span_cm / 20.0)
