"""Local checks for the continuous and additional footing reinforcement.

Section calculations are shared with the uniform design (MTC/AASHTO checks).
Whole elements bordering a cutoff are included conservatively on both sides.
"""

from dataclasses import dataclass

from bridge_design.domain.connected_section_checks import section_check
from bridge_design.domain.rebar_catalog import reinforcing_bar_by_label


@dataclass(frozen=True)
class FoundationZoneCheck:
    name: str
    start_m: float
    end_m: float
    reinforcement: str
    area_cm2_m: float
    maximum_gap_m: float
    flexural_utilization: float
    shear_utilization: float
    crack_utilization: float
    minimum_utilization: float
    service_moment_tn_m_m: float
    service_stress_kg_cm2: float
    service_stress_limit_kg_cm2: float
    crack_spacing_limit_m: float
    service_case: str
    service_x_m: float
    status: str


def foundation_zone_choice(continuous):
    """Two equal, interleaved families: continuous s, additional s, total s/2."""
    from bridge_design.domain.connected_reinforcement import ConnectedBarChoice, ConnectedSteelChoice
    # Number/range validation is shared with design_region.validate_choice.
    if isinstance(continuous.spacing_m, bool) or not isinstance(continuous.spacing_m, (int, float)):
        raise ValueError("La separacion del acero continuo debe ser numerica.")
    combined = ConnectedBarChoice(continuous.bar_label, continuous.spacing_m / 2, continuous.is_custom)
    return ConnectedSteelChoice(combined, combined, continuous)


def validate_foundation_zone_choice(data, region, selection, grid, cover, demands):
    from bridge_design.domain.connected_2_inputs import is_connected_2
    from bridge_design.domain.connected_reinforcement import validate_choice
    if not is_connected_2(data) or region not in (
        "Zapata combinada - longitudinal superior", "Zapata combinada - longitudinal inferior"
    ):
        raise ValueError("El armado por zonas solo corresponde a la zapata longitudinal del comando 2.")
    _, bar, spacing = validate_choice(selection.foundation_continuous, grid, cover, demands)
    total = reinforcing_bar_by_label(selection.principal.bar_label)
    if bar != total or abs(spacing - 2*selection.principal.spacing_m) > 1e-9:
        raise ValueError("Use dos familias iguales intercaladas: continuo s y adicional s, total s/2.")


def foundation_zone_checks(data, mesh, steel, demands, cut):
    """Report actual local moments/stresses, not the centre peak in every zone."""
    bar = reinforcing_bar_by_label(steel.bar_label)
    cover = data.left.reinforcement.footing_cover_cm
    left, right = cut.cutoff_left_m, cut.cutoff_right_m
    spans = (("Extremo izquierdo", cover/100, left), ("Centro", left, right),
             ("Extremo derecho", right, data.total_length_m-cover/100))
    zones = []
    for index, (name, start, end) in enumerate(spans):
        additional = (index == 1) == (steel.face == "Superior")
        spacing = steel.spacing_m if additional else cut.pattern.equivalent_spacing_m
        gap = steel.spacing_m if additional else cut.pattern.maximum_gap_m
        checks = []
        for demand in demands:
            element = mesh.frame.elements[demand.element]
            a, b = (mesh.frame.nodes[n].x for n in (element.start, element.end))
            if max(a, b) < start-1e-8 or min(a, b) > end+1e-8:
                continue
            values = section_check(demand, data.left, cover, bar, spacing)
            if values.get("service_tension", False):
                values["crack_ratio"] = max(values["crack_ratio"], gap/max(values["maximum_spacing"], 1e-12))
            checks.append((values, a+demand.station*(b-a)))
        ratios = [max(v[key] for v, _ in checks) for key in ("flexure_ratio", "shear_ratio", "crack_ratio")]
        service = [(v, x) for v, x in checks if "stress" in v]
        trace, x = max(service, key=lambda row: (row[0]["crack_ratio"], abs(row[0]["demand"]["moment"]))) if service else ({}, start)
        area = bar.area_cm2/spacing
        minimum = steel.temperature_cm2_m/area
        zones.append(FoundationZoneCheck(name, start, end,
            "Continuo + adicional" if additional else "Solo continuo", area, gap,
            *ratios, minimum, trace.get("demand", {}).get("moment", 0.0), trace.get("stress", 0.0),
            .6*data.left.materials.steel_yield_kg_cm2, trace.get("maximum_spacing", 0.0),
            trace.get("demand", {}).get("case", "Sin caso de servicio"), x,
            "OK" if max(*ratios, minimum) <= 1+1e-8 else "NO CUMPLE"))
    return tuple(zones)
