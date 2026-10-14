"""Conservative geometric partition of deck surface loads among actual girders."""
from dataclasses import dataclass
from math import isclose


@dataclass(frozen=True)
class GirderTributary:
    index: int  # zero-based from the left edge
    start_m: float
    end_m: float
    sidewalk_m: float
    asphalt_m: float
    exterior: bool

    @property
    def label(self):
        return f"V{self.index + 1}"


def overlap(start, end, load_start, load_end):
    return max(0.0, min(end, load_end) - max(start, load_start))


def girder_tributaries(geometry, layout):
    """Assign every surface interval exactly once, including asymmetric paving."""
    axes = geometry.support_positions_m
    width = geometry.total_width_m
    boundaries = (0.0, *((a + b) / 2 for a, b in zip(axes, axes[1:])), width)
    sidewalks = layout.sidewalk_intervals(width)
    rows = []
    for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
        sidewalk = sum(overlap(start, end, a, b) for a, b in sidewalks)
        asphalt = overlap(start, end, layout.asphalt_start_m, layout.asphalt_end_m)
        # Preserve full-width inputs exactly; avoid artificial groups from roundoff.
        full_width = geometry.overhang_m + geometry.girder_spacing_m / 2 if index in (0, len(axes)-1) else geometry.girder_spacing_m
        if isclose(asphalt, full_width, abs_tol=1e-10, rel_tol=0):
            asphalt = full_width
        if isclose(sidewalk, layout.sidewalk_width_m, abs_tol=1e-10, rel_tol=0):
            sidewalk = layout.sidewalk_width_m
        rows.append(GirderTributary(index, start, end, sidewalk, asphalt, index in (0, len(axes)-1)))
    for actual, expected in ((sum(r.sidewalk_m for r in rows), 2*layout.sidewalk_width_m),
                             (sum(r.asphalt_m for r in rows), layout.asphalt_end_m-layout.asphalt_start_m)):
        if not isclose(actual, expected, abs_tol=1e-9, rel_tol=1e-10):
            raise ValueError("El reparto tributario no conserva las cargas del tablero.")
    return tuple(rows)


def girder_load_groups(project):
    """Group only girders with equal load widths and the same structural type."""
    groups = []
    for row in project.girder_tributaries:
        for group in groups:
            first = group[0]
            if (row.exterior == first.exterior and
                    isclose(row.sidewalk_m, first.sidewalk_m, abs_tol=1e-10, rel_tol=0) and
                    isclose(row.asphalt_m, first.asphalt_m, abs_tol=1e-10, rel_tol=0)):
                group.append(row)
                break
        else:
            groups.append([row])
    return tuple(tuple(group) for group in groups)
