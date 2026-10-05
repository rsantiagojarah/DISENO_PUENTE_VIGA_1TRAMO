"""Editable ver_2l geometry adapted to the existing connected-abutment model.

No new analysis or concrete design equations: the same FRAME, loads and
MTC 2018 checks consume the derived AbutmentGeometryInputs/ConnectedInputs.
"""

from dataclasses import dataclass, field, fields
from math import isclose

from bridge_design.domain.abutment import AbutmentGeometryInputs
from bridge_design.domain.connected_inputs import ConnectedInputs, positive


@dataclass(frozen=True)
class Connected2Geometry:
    upper_clear_span_m: float = 14.00
    stem_body_height_m: float = 8.03
    parapet_height_m: float = 1.17
    parapet_thickness_m: float = 0.25
    seat_length_m: float = 0.55
    stem_base_thickness_m: float = 1.35
    outer_heel_m: float = 0.90
    foundation_thickness_m: float = 1.50
    bearing_extra_height_m: float = 1.80

    def __post_init__(self):
        for item in fields(self):
            positive(getattr(self, item.name), item.name,
                     allow_zero=item.name == "bearing_extra_height_m")
        if self.stem_base_thickness_m < self.upper_stem_thickness_m:
            raise ValueError("El espesor inferior de pantalla debe ser >= asiento + espesor del parapeto.")
        positive(self.lower_clear_span_m, "Separacion libre inferior calculada")

    @property
    def upper_stem_thickness_m(self):
        return self.seat_length_m + self.parapet_thickness_m

    @property
    def lower_clear_span_m(self):
        return self.upper_clear_span_m - 2 * (self.stem_base_thickness_m - self.upper_stem_thickness_m)

    def abutment_geometry(self):
        return AbutmentGeometryInputs(
            retained_height_m=self.foundation_thickness_m + self.stem_body_height_m + self.parapet_height_m,
            bridge_length_m=self.upper_clear_span_m + self.seat_length_m,
            seat_block_height_m=self.parapet_height_m,
            seat_wall_width_m=self.parapet_thickness_m,
            bearing_seat_length_m=self.seat_length_m,
            backwall_drop_m=0.0, backwall_taper_height_m=0.0,
            backfill_step_width_m=0.0, top_step_thickness_m=0.0, small_batter_width_m=0.0,
            upper_stem_thickness_m=self.upper_stem_thickness_m,
            lower_stem_thickness_m=self.stem_base_thickness_m,
            footing_width_m=self.stem_base_thickness_m + self.outer_heel_m,
            footing_thickness_m=self.foundation_thickness_m,
            toe_length_m=0.0,
            # Existing convention measures front soil from the footing bottom.
            # Setting it to D gives exactly zero soil above the foundation.
            front_soil_depth_m=self.foundation_thickness_m,
            bridge_seat_to_bearing_height_m=self.bearing_extra_height_m,
        )


@dataclass(frozen=True)
class Connected2Inputs(ConnectedInputs):
    geometry_model: str = field(default="ver_2l", init=False)

    def __post_init__(self):
        super().__post_init__()
        g = self.left.geometry
        if any(value != 0 for value in (
            self.left_transition_m, self.right_transition_m, g.toe_length_m,
            g.backwall_drop_m, g.backwall_taper_height_m, g.backfill_step_width_m,
            g.small_batter_width_m, g.top_step_thickness_m,
        )):
            raise ValueError("Estribos conectados 2 requiere base uniforme sin punteras ni transiciones.")
        if not (isclose(self.slab_thickness_m, g.footing_thickness_m)
                and isclose(g.front_soil_depth_m, g.footing_thickness_m)):
            raise ValueError("Estribos conectados 2 requiere espesor uniforme y ningun relleno interior.")
        if self.left.soil != self.right.soil:
            raise ValueError("Estribos conectados 2 requiere el mismo suelo en ambos lados.")

    @property
    def upper_clear_span_m(self):
        g = self.left.geometry
        return self.clear_span_m + 2 * (g.lower_stem_thickness_m - g.upper_stem_thickness_m)


def connected_2_inputs(data):
    """Keep all shared validation, materials, cases and reinforcement settings."""
    return Connected2Inputs(**{item.name: getattr(data, item.name) for item in fields(ConnectedInputs)})


def is_connected_2(data):
    return isinstance(data, Connected2Inputs)
