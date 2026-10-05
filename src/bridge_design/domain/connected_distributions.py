"""Independent reinforcement distributions, retaining simultaneous FRAME demands."""

from dataclasses import dataclass, replace

from bridge_design.domain.connected_geometry import local_x


@dataclass(frozen=True)
class Distribution:
    label: str
    region: str
    face: str
    direction: str
    role: str
    demands: tuple
    part: str = ""


def base_region(label):
    return label.split(" - ", 1)[0]


def common_region(region):
    """Map mirrored physical members to their shared reinforcement design."""
    for suffix in (" izquierda", " derecha"):
        if region.endswith(suffix):
            return region[:-len(suffix)]
    return region


def distribution_demands(data, mesh, grouped):
    # The central slab reinforcement also covers its tapered transitions, using
    # each section's actual depth and the slab materials/cover.
    grouped = dict(grouped)
    transitions = tuple(d for region in ("Transicion izquierda", "Transicion derecha")
                        for d in grouped.get(region, ()))
    if "Losa central" in grouped or transitions:
        grouped["Losa central"] = tuple(grouped.get("Losa central", ())) + transitions
    distributions = []
    ordered = sorted(grouped, key=lambda r: ((0 if r.startswith("Pantalla") else
        1 if r.startswith("Zapata") else 2 if r.startswith("Losa") else 3),
        0 if r.endswith("izquierda") else 1, r))
    for region in ordered:
        if region.startswith(("Transicion", "Cajuela")):
            continue
        demands = tuple(grouped[region])
        side = data.left if region.endswith("izquierda") else data.right
        vertical = region.startswith(("Pantalla", "Parapeto"))
        if vertical:
            for face in ("Relleno", "Exterior"):
                # Positive local bending tensions the exterior on the left and
                # the backfill face on the right; do not pool opposite signs.
                positive = (face == "Exterior") == region.endswith("izquierda")
                chosen = tuple(replace(d, moment=d.moment if (d.moment >= 0) == positive else 0.0,
                    shear=d.shear if (d.moment >= 0) == positive else 0.0,
                    flexural_phi_limit=(side.reinforcement.stem_design_phi_for_as
                        if d.limit_state == "extreme" else side.reinforcement.flexural_phi)) for d in demands)
                distributions.append(Distribution(f"{region} - vertical {face.lower()}", region,
                    face, "Vertical", "primary", chosen))
            for face in ("Relleno", "Exterior"):
                distributions.append(Distribution(f"{region} - horizontal {face.lower()}", region,
                    face, "Horizontal", "temperature", _temperature_demands(demands)))
        elif region.startswith("Zapata") and region != "Zapata combinada":
            index = 0 if region.endswith("izquierda") else 1
            front = side.geometry.toe_length_m
            back = front + side.geometry.lower_stem_thickness_m
            for part, title in (("talon", "talon superior"), ("puntera", "puntera inferior")):
                if part == "puntera" and side.geometry.toe_length_m == 0:
                    continue
                chosen = []
                for demand in demands:
                    element = mesh.frame.elements[demand.element]
                    start, end = (mesh.frame.nodes[n] for n in (element.start, element.end))
                    x = start.x + demand.station*(end.x-start.x)
                    lx = local_x(data, index, x)
                    midpoint = local_x(data, index, (start.x + end.x) / 2)
                    # Keep the one-sided face value from the cantilever member;
                    # members beneath the wall belong to neither distribution.
                    if ((part == "talon" and lx >= back-1e-8 and midpoint > back-1e-8)
                            or (part == "puntera" and lx <= front+1e-8 and midpoint < front+1e-8)):
                        chosen.append(replace(demand, shear_method="general",
                            flexural_phi_limit=side.reinforcement.footing_design_phi_for_as))
                if chosen:
                    # Same individual-abutment criterion: one governing steel
                    # distribution per cantilever zone, continuous on both faces.
                    distributions.append(Distribution(f"{region} - {title}", region,
                        "Superior e inferior", "Longitudinal", "primary", tuple(chosen), part))
            for face in ("Superior", "Inferior"):
                distributions.append(Distribution(f"{region} - transversal {face.lower()}", region,
                    face, "Transversal", "temperature", _temperature_demands(demands)))
        elif region in ("Losa central", "Zapata combinada"):
            # A combined footing uses every foundation section, including those
            # beneath the walls, with one longitudinal distribution per face.
            for face in ("Superior", "Inferior"):
                positive = face == "Inferior"
                chosen = tuple(replace(d, moment=d.moment if (d.moment >= 0) == positive else 0.0,
                    shear=d.shear if (d.moment >= 0) == positive else 0.0,
                    shear_method="general",
                    flexural_phi_limit=data.left.reinforcement.footing_design_phi_for_as) for d in demands)
                distributions.append(Distribution(f"{region} - longitudinal {face.lower()}", region,
                    face, "Longitudinal", "primary", chosen))
            for face in ("Superior", "Inferior"):
                distributions.append(Distribution(f"{region} - transversal {face.lower()}", region,
                    face, "Transversal", "temperature", _temperature_demands(demands)))
    # Resolve the tension face on each physical side before pooling demands.
    # Keeping every case/section preserves the simultaneous M/V and lets each
    # verification identify its own governing abutment.
    unified = {}
    for item in distributions:
        region = common_region(item.region)
        label = region + item.label[len(item.region):]
        if label in unified:
            previous = unified[label]
            unified[label] = replace(previous, demands=previous.demands + item.demands)
        else:
            unified[label] = replace(item, label=label, region=region)
    return tuple(unified.values())


def _temperature_demands(demands):
    # FRAME supplies bending only in its plane. Orthogonal reinforcement is
    # minimum temperature/distribution steel, never fictitious transverse M/V.
    return tuple(replace(d, moment=0.0, shear=0.0, axial=0.0) for d in demands)


def reinforcement_demands(data, mesh, results):
    from bridge_design.domain.connected_reinforcement import section_demands
    grouped = section_demands(data, mesh, results)
    return {item.label: item.demands for item in distribution_demands(data, mesh, grouped)}
