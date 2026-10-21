"""Model B geometry from MODELO_B_ESTRIBO, in the solver's toe-to-heel axes.

The PDF is reflected for calculation: x=0 at the outer toe, x=B at the heel;
y=0 at the footing bottom. The report reflects it back to the PDF orientation.
All regions are disjoint and retain the PDF numbering. No design equations
are duplicated here.
"""

from dataclasses import dataclass, replace
from math import hypot
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bridge_design.domain.abutment import AbutmentGeometryInputs


@dataclass(frozen=True)
class GeometryRegion:
    name: str
    vertices: tuple[tuple[float, float], ...]
    area_expression: str

    @property
    def properties(self) -> tuple[float, float, float]:
        pairs = tuple(zip(self.vertices, self.vertices[1:] + self.vertices[:1]))
        crosses = tuple(x1*y2-x2*y1 for (x1, y1), (x2, y2) in pairs)
        twice_area = sum(crosses)
        if abs(twice_area) < 1e-14:
            return 0.0, 0.0, 0.0
        cx = sum((a[0]+b[0])*cross for (a, b), cross in zip(pairs, crosses)) / (3*twice_area)
        cy = sum((a[1]+b[1])*cross for (a, b), cross in zip(pairs, crosses)) / (3*twice_area)
        return abs(twice_area)/2, cx, cy

    @property
    def area_m2(self) -> float:
        return self.properties[0]

    @property
    def centroid_x_m(self) -> float:
        return self.properties[1]

    @property
    def centroid_y_m(self) -> float:
        return self.properties[2]


def model_b_geometry(base: "AbutmentGeometryInputs | None" = None) -> "AbutmentGeometryInputs":
    """Editable example defaults, not dimensions inferred from the PDF."""
    from bridge_design.domain.abutment import AbutmentGeometryInputs
    g = base or AbutmentGeometryInputs()
    return replace(g, abutment_type="B", small_batter_width_m=0.0, top_step_thickness_m=0.0,
                   bearing_seat_length_m=round(g.upper_stem_thickness_m + g.backfill_step_width_m - g.seat_wall_width_m, 12))


def _rectangle(name, left, bottom, right, top, expression):
    return GeometryRegion(name, ((left, bottom), (right, bottom), (right, top), (left, top)), expression)


def concrete_regions(g: "AbutmentGeometryInputs") -> tuple[GeometryRegion, ...]:
    back = g.toe_length_m + g.lower_stem_thickness_m
    shoulder = back - g.upper_stem_thickness_m
    rear = back + g.backfill_step_width_m
    bottom = g.footing_thickness_m
    seat = bottom + g.seat_body_height_m
    body = seat - g.backwall_drop_m
    start = body - g.backwall_taper_height_m
    return (
        _rectangle("1 Parapeto", rear-g.seat_wall_width_m, seat, rear, g.retained_height_m, "b_parap. * h_parap."),
        _rectangle("2 Cabezal", shoulder, body, rear, seat, "(t_sup + t2) * h_bloque"),
        GeometryRegion("3 Transicion posterior", ((back, start), (rear, body), (back, body)), "t2 * h_transicion / 2"),
        _rectangle("4 Pantalla rectangular", shoulder, bottom, back, body, "t_sup * (H-D-h_parap.-h_bloque)"),
        GeometryRegion("5 Ensanche exterior continuo", ((g.toe_length_m, bottom), (shoulder, bottom), (shoulder, seat)), "(t_inf-t_sup) * (H-D-h_parap.) / 2"),
        _rectangle("6 Zapata", 0.0, 0.0, g.footing_width_m, bottom, "B * D"),
    )


def soil_regions(g: "AbutmentGeometryInputs") -> tuple[GeometryRegion, ...]:
    back = g.toe_length_m + g.lower_stem_thickness_m
    rear = back + g.backfill_step_width_m
    bottom = g.footing_thickness_m
    body = bottom + g.seat_body_height_m - g.backwall_drop_m
    start = body - g.backwall_taper_height_m
    front_height = max(g.front_soil_depth_m - bottom, 0.0)
    batter = (g.lower_stem_thickness_m-g.upper_stem_thickness_m) * front_height/g.seat_body_height_m
    return (
        _rectangle("7 Relleno posterior", rear, bottom, g.footing_width_m, g.retained_height_m, "(L_talon-t2) * (H-D)"),
        GeometryRegion("8 Relleno triangular t2", ((back, start), (rear, start), (rear, body)), "t2 * h_transicion / 2"),
        _rectangle("9 Relleno junto pantalla", back, bottom, rear, start, "t2 * (H-D-h_parap.-h_bloque-h_transicion)"),
        GeometryRegion("10 Relleno triangular frontal", ((g.toe_length_m, bottom), (g.toe_length_m+batter, bottom+front_height), (g.toe_length_m, bottom+front_height)), "(t_inf-t_sup) * (h-D)^2 / [2*(H-D-h_parap.)]"),
        _rectangle("11 Relleno frontal", 0.0, bottom, g.toe_length_m, bottom+front_height, "L_punta * max(h-D,0)"),
    )


def stem_faces_at_height(g: "AbutmentGeometryInputs", height: float) -> tuple[float, float]:
    y = min(max(height, 0.0), g.stem_height_above_footing_m)
    back = g.toe_length_m + g.lower_stem_thickness_m
    if y >= g.seat_body_height_m:
        return back + g.backfill_step_width_m - g.seat_wall_width_m, back + g.backfill_step_width_m
    front = g.toe_length_m + (g.lower_stem_thickness_m-g.upper_stem_thickness_m)*y/g.seat_body_height_m
    body = g.seat_body_height_m - g.backwall_drop_m
    start = body - g.backwall_taper_height_m
    if y > start:
        ratio = min((y-start)/g.backwall_taper_height_m, 1.0) if g.backwall_taper_height_m > 0 else 1.0
        back += g.backfill_step_width_m*ratio
    return front, back


def back_face_length_m(g: "AbutmentGeometryInputs", height: float) -> float:
    """Bar path along the piecewise-linear soil face, from the footing top."""
    y = min(max(height, 0.0), g.stem_height_above_footing_m)
    transition = g.backwall_taper_height_m
    start = g.seat_body_height_m-g.backwall_drop_m-transition
    fraction = min(max((y-start)/transition, 0.0), 1.0) if transition > 0 else 0.0
    return y + fraction*(hypot(transition, g.backfill_step_width_m)-transition)


def back_face_height_m(g: "AbutmentGeometryInputs", length: float) -> float:
    height = g.stem_height_above_footing_m
    if length <= 0.0:
        return 0.0
    if length >= back_face_length_m(g, height):
        return height
    transition = g.backwall_taper_height_m
    start = g.seat_body_height_m-g.backwall_drop_m-transition
    diagonal = hypot(transition, g.backfill_step_width_m)
    if length <= start:
        return length
    if length < start+diagonal:
        return start+(length-start)*transition/diagonal
    return length-(diagonal-transition)
