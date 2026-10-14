"""Optional vertical pipe load, uniform along the entire bridge span."""
from dataclasses import dataclass

from bridge_design.validation.input_validators import require_non_negative


@dataclass(frozen=True)
class PipeLoad:
    """Operating mass per metre and load axis from the left outside deck edge."""

    weight_kg_m: float
    x_from_left_m: float

    def __post_init__(self):
        require_non_negative(self.weight_kg_m, "peso total de tuberia")
        require_non_negative(self.x_from_left_m, "ubicacion de tuberia desde borde izquierdo")

    @property
    def q_tn_m(self):
        return self.weight_kg_m / 1000.0

    def validate_width(self, width_m):
        if self.x_from_left_m > width_m:
            raise ValueError(f"La tuberia debe estar dentro del tablero: 0 <= x <= {width_m:g} m.")


def pipe_points(layout, longitudinal_length_m=1.0):
    """Convert the longitudinal line load to a force on a transverse strip."""
    from bridge_design.domain.transverse_slab import PointLoad
    pipe = layout.pipe
    if pipe is None or pipe.q_tn_m == 0:
        return ()
    return (PointLoad(pipe.x_from_left_m, pipe.q_tn_m * longitudinal_length_m, "DW - tuberia llena"),)


def pipe_girder_loads(geometry, materials, layout):
    """Signed girder reactions per longitudinal metre; preserve equilibrium."""
    from bridge_design.domain.transverse_slab import solve_load_case
    points = pipe_points(layout, geometry.strip_length_m)
    if not points:
        return (0.0,) * geometry.girder_count
    layout.pipe.validate_width(geometry.total_width_m)
    solved = solve_load_case(geometry, materials, "DW - tuberia", (), points)
    return tuple(r / geometry.strip_length_m for _, r in solved.support_reactions_tn)


def mirrored_layout(layout, width_m):
    """Express a right overhang in a local coordinate measured from its edge."""
    from dataclasses import replace
    pipe = layout.pipe
    return replace(layout, asphalt_start_m=width_m-layout.asphalt_end_m,
                   asphalt_end_m=width_m-layout.asphalt_start_m,
                   vehicle_move_start_m=width_m-layout.vehicle_move_end_m,
                   vehicle_move_end_m=width_m-layout.vehicle_move_start_m,
                   pipe=replace(pipe, x_from_left_m=width_m-pipe.x_from_left_m) if pipe else None)
