"""Continuous connected-bar anchorage and straight-path geometry utilities."""

from bridge_design.domain.connected_geometry import foundation_section
from bridge_design.domain.wall_friction import _back_x
from bridge_design.domain.abutment import _stem_thickness_at_height_m


def _clip_segment(start, end, first, last):
    """Clip a linear interval by nonnegative geometric clearance constraints."""
    lower, upper = 0.0, 1.0
    for a, b in zip(first, last):
        if a < -1e-9 and b < -1e-9:
            return None
        if abs(b-a) < 1e-12:
            continue
        crossing = -a/(b-a)
        if a < -1e-9:
            lower = max(lower, crossing)
        elif b < -1e-9:
            upper = min(upper, crossing)
    return (start+(end-start)*lower, start+(end-start)*upper) if lower <= upper else None


def _space_at(origin, intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]+1e-7:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    for start, end in merged:
        if start-1e-7 <= origin <= end+1e-7:
            return max(0.0, min(origin-start, end-origin)), start, end
    return 0.0, origin, origin


def straight_space(data, mesh, region, demand, cover_cm, diameter_cm):
    """Limit straight continuation on both sides; never credit a bend or hook."""
    element = mesh.frame.elements[demand.element]
    first, last = mesh.frame.nodes[element.start], mesh.frame.nodes[element.end]
    x = first.x+demand.station*(last.x-first.x)
    y = first.y+demand.station*(last.y-first.y)
    clearance = (cover_cm+diameter_cm/2)/100
    intervals = []
    if first.y == last.y:
        # The continuous top bar can cross the floor. A deep bottom bar stops
        # at the taper if maintaining a straight line would violate cover.
        bar_y = -demand.depth_cm/100+clearance if demand.moment >= 0 else -clearance
        left = data.left.geometry.footing_width_m
        right = data.total_length_m-data.right.geometry.footing_width_m
        levels = sorted({0.0, left, left+data.left_transition_m,
                         right-data.right_transition_m, right, data.total_length_m})
        def gaps(position):
            depth = foundation_section(data, position)[0]
            return (bar_y+depth-clearance, -clearance-bar_y,
                    position-data.left.reinforcement.footing_cover_cm/100,
                    data.total_length_m-data.right.reinforcement.footing_cover_cm/100-position)
        for a, b in zip(levels, levels[1:]):
            clipped = _clip_segment(a, b, gaps(a+1e-8), gaps(b-1e-8))
            if clipped:
                intervals.append(clipped)
        available, start, end = _space_at(x, intervals)
        axis = "x"
        origin = x
    else:
        physical_region = element.region
        side = data.left if physical_region.endswith("izquierda") else data.right
        g = side.geometry
        height = g.stem_height_above_footing_m
        body = height-g.seat_block_height_m-g.backwall_drop_m
        # Evaluate the concrete on the governing element's side of a step.
        sample = first.y+min(max(demand.station, 1e-8), 1-1e-8)*(last.y-first.y)
        back = _back_x(g, sample)
        front = back-_stem_thickness_at_height_m(side, sample)
        rear_face = demand.moment < 0 if physical_region.endswith("izquierda") else demand.moment > 0
        bar_x = back-clearance if rear_face else front+clearance
        foot_cover = side.reinforcement.footing_cover_cm/100
        levels = sorted({-g.footing_thickness_m, 0.0, body-g.backwall_taper_height_m,
                         body, height-g.seat_block_height_m, height})
        def gaps(level):
            if level < 0:
                return (bar_x-foot_cover-diameter_cm/200,
                        g.footing_width_m-foot_cover-diameter_cm/200-bar_x,
                        level+g.footing_thickness_m-foot_cover)
            back = _back_x(g, level)
            front = back-_stem_thickness_at_height_m(side, level)
            return (bar_x-front-clearance, back-clearance-bar_x, height-cover_cm/100-level)
        for a, b in zip(levels, levels[1:]):
            clipped = _clip_segment(a, b, gaps(a+1e-8), gaps(b-1e-8))
            if clipped:
                intervals.append(clipped)
        available, start, end = _space_at(y, intervals)
        axis = "y"
        origin = y
    return available*100, (
        f"{element.region}; {demand.case}; elemento {demand.element}; s/L={demand.station:.4f}; "
        f"{axis} critica={origin:.4f} m; tramo recto compatible [{start:.4f}, {end:.4f}] m; "
        f"L disponible=min({origin-start:.4f}, {end-origin:.4f})={available:.4f} m. "
        "Se conserva la continuidad recta dentro del concreto y su recubrimiento; no se acredita doblado.")


def geometric_anchorage(data, mesh, region, demands, inputs, cover, bar, spacing, *, part=""):
    """Available straight lengths for the user's continuous connected detail.

    Footing bars cross the stem and develop toward the opposite footing edge.
    Slab bars continue into the footing; parapet bars continue down the abutment.
    These are detailing assumptions, not inferred shortest paths at FRAME stations.
    """
    geometry = inputs.geometry
    footing_cover = inputs.reinforcement.footing_cover_cm
    if region.startswith("Pantalla"):
        available = max(0.0, geometry.footing_thickness_m*100-footing_cover)
        return available, ("Detalle continuo definido: pantalla anclada en la zapata; "
                           f"L disponible=D-r={geometry.footing_thickness_m*100:.4f}"
                           f"-{footing_cover:.4f}={available:.4f} cm.")
    if region.startswith("Zapata"):
        heel = max(0.0, (geometry.footing_width_m-geometry.heel_length_m)*100-footing_cover)
        toe = max(0.0, (geometry.footing_width_m-geometry.toe_length_m)*100-footing_cover)
        if part == "talon" or "talon" in region:
            return heel, ("Detalle continuo definido: barra de talon cruza la pantalla hasta el borde de puntera; "
                          f"L disponible=(B-talon)-r=({geometry.footing_width_m:.4f}"
                          f"-{geometry.heel_length_m:.4f})*100-{footing_cover:.4f}={heel:.4f} cm.")
        if part == "puntera" or "puntera" in region:
            return toe, ("Detalle continuo definido: barra de puntera cruza la pantalla hasta el borde de talon; "
                         f"L disponible=(B-puntera)-r=({geometry.footing_width_m:.4f}"
                         f"-{geometry.toe_length_m:.4f})*100-{footing_cover:.4f}={toe:.4f} cm.")
        return min(heel, toe), ("Detalle continuo definido: barras de zapata cruzan la pantalla; "
                               f"L talon hacia puntera={heel:.4f} cm; "
                               f"L puntera hacia talon={toe:.4f} cm; "
                               f"L disponible=min({heel:.4f}, {toe:.4f})={min(heel,toe):.4f} cm.")
    if region.startswith("Losa central"):
        lengths = [(side.geometry.footing_width_m*100-side.reinforcement.footing_cover_cm)
                   for side in (data.left, data.right)]
        available = max(0.0, min(lengths))
        return available, ("Detalle continuo definido: losa superior e inferior prolongadas dentro de las zapatas; "
                           f"L disponible=min(B izquierda-r, B derecha-r)="
                           f"min({lengths[0]:.4f}, {lengths[1]:.4f})={available:.4f} cm.")
    if region.startswith("Parapeto"):
        available = max(0.0, geometry.retained_height_m*100-footing_cover)
        return available, ("Detalle continuo definido: barras de parapeto relleno y exterior continuas "
                           "en toda la altura del estribo, desde fondo de zapata; "
                           f"L disponible=H-r={geometry.retained_height_m*100:.4f}"
                           f"-{footing_cover:.4f}={available:.4f} cm.")
    return None, "Sin detalle de anclaje definido para esta region."
