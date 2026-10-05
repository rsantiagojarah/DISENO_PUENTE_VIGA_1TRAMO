"""Symmetric top-centre / bottom-end cutoff proposals for the combined footing.

Use selected bars and every FRAME case/station. Whole-element envelopes make
the search conservative without assuming monotonic moment or equal side loads.
Checks, minimum steel and development come from the existing design modules.
"""

from dataclasses import dataclass, replace
from math import ceil, floor

from bridge_design.codes.mtc_detailing import minimum_flexural_cutoff_extension_cm
from bridge_design.domain.connected_section_checks import section_check
from bridge_design.domain.rebar_catalog import reinforcing_bar_by_label
from bridge_design.domain.reinforcement_cut_patterns import BarCutPattern, partial_cut_patterns
from bridge_design.domain.connected_foundation_zones import FoundationZoneCheck, foundation_zone_checks

REFERENCE = "MTC 2018 Art. 2.6.5.6.1.2.1 / AASHTO LRFD 5.11.1.2.1."


@dataclass(frozen=True)
class FoundationReinforcementCut:
    status: str
    reason: str
    arrangement: str
    total_length_m: float
    inner_face_left_m: float
    inner_face_right_m: float
    pattern: BarCutPattern | None = None
    theoretical_left_m: float | None = None
    theoretical_right_m: float | None = None
    cutoff_left_m: float | None = None
    cutoff_right_m: float | None = None
    distance_from_inner_face_m: float | None = None
    development_length_m: float | None = None
    minimum_extension_m: float | None = None
    adopted_extension_m: float | None = None
    additional_intervals_m: tuple[tuple[float, float], ...] = ()
    continuous_interval_m: tuple[float, float] = ()
    saved_steel_fraction: float = 0.0
    flexural_utilization: float | None = None
    shear_utilization: float | None = None
    crack_utilization: float | None = None
    minimum_utilization: float | None = None
    governing_case: str = ""
    governing_element: int | None = None
    governing_station: float | None = None
    notes: str = ""
    requested_continuous_spacing_m: float | None = None
    zones: tuple[FoundationZoneCheck, ...] = ()


def _ratios(values, pattern):
    # section_check computes stresses/capacities with the actual remaining area.
    # Its uniform equivalent spacing cannot stand in for the real maximum gap.
    crack = values["crack_ratio"]
    if values.get("service_tension", False):
        crack = max(crack, pattern.maximum_gap_m / max(values["maximum_spacing"], 1e-12))
    return values["flexure_ratio"], values["shear_ratio"], crack


def _checked_records(data, mesh, demands, bar, pattern):
    cover = data.left.reinforcement.footing_cover_cm
    records = []
    for demand in demands:
        element = mesh.frame.elements[demand.element]
        a, b = (mesh.frame.nodes[n].x for n in (element.start, element.end))
        values = section_check(demand, data.left, cover, bar, pattern.equivalent_spacing_m)
        records.append((min(a, b), max(a, b), demand, _ratios(values, pattern)))
    return records


def _candidate(data, steel, base, pattern, records, extension, minimum_extension):
    length = data.total_length_m
    cover = data.left.reinforcement.footing_cover_cm / 100
    midpoint = length / 2
    upper = steel.face == "Superior"
    failed = [row for row in records if max(row[3]) > 1 + 1e-8]
    if not failed:
        return None, "El acero remanente ya cumple en toda la zapata; no se requiere refuerzo localizado."
    if upper:
        # Additional top bars surround all failing sections, mirrored about L/2.
        theoretical = min(min(row[0] for row in failed), length-max(row[1] for row in failed))
        cutoff = floor((theoretical-extension)*100 + 1e-8) / 100
        if cutoff <= cover + 1e-8:
            return None, "La prolongacion del refuerzo superior alcanza los extremos; conservar barras continuas."
        reduced = [r for r in records if r[0] < cutoff+1e-8 or r[1] > length-cutoff-1e-8]
        intervals = ((cutoff, length-cutoff),)
        removed_length = 2*(cutoff-cover)
        available_continuation = theoretical-cover
    else:
        # All low-capacity failures must be covered by either end reinforcement.
        if any(a < midpoint < b for a, b, _, _ in failed):
            return None, "El acero remanente no cumple en el centro; no existe un tramo central para reducirlo."
        theoretical = max([base.inner_face_left_m] +
            [b if (a+b)/2 <= midpoint else length-a for a, b, _, _ in failed])
        cutoff = ceil((theoretical+extension)*100 - 1e-8) / 100
        if cutoff >= midpoint-1e-8:
            return None, "Los refuerzos inferiores de ambos extremos se encuentran; conservar barras continuas."
        reduced = [r for r in records if r[1] > cutoff-1e-8 and r[0] < length-cutoff+1e-8]
        intervals = ((cover, cutoff), (length-cutoff, length-cover))
        removed_length = length-2*cutoff
        available_continuation = length-cover-theoretical
    if available_continuation + 1e-8 < steel.required_straight_anchor_cm/100:
        return None, "Las barras que continuan no disponen de ld mas alla del corte teorico."
    if not reduced or any(max(row[3]) > 1+1e-8 for row in reduced):
        return None, "La envolvente completa del tramo reducido no cumple con el acero remanente."
    critical = max(reduced, key=lambda row: max(row[3]))
    ratios = tuple(max(row[3][i] for row in reduced) for i in range(3))
    saved = (1-pattern.continuing_bars/pattern.cycle_bars)*removed_length/(length-2*cover)
    return replace(base, status="APLICA", reason="El acero remanente cumple en todos los tramos reducidos.",
        pattern=pattern, theoretical_left_m=theoretical, theoretical_right_m=length-theoretical,
        cutoff_left_m=cutoff, cutoff_right_m=length-cutoff,
        distance_from_inner_face_m=cutoff-base.inner_face_left_m,
        development_length_m=steel.required_straight_anchor_cm/100,
        minimum_extension_m=minimum_extension, adopted_extension_m=extension,
        additional_intervals_m=intervals, continuous_interval_m=(cover, length-cover),
        saved_steel_fraction=saved, flexural_utilization=ratios[0], shear_utilization=ratios[1],
        crack_utilization=ratios[2], minimum_utilization=steel.temperature_cm2_m/pattern.remaining_area_cm2_m,
        governing_case=critical[2].case, governing_element=critical[2].element,
        governing_station=critical[2].station,
        notes=("Se corta 1 de cada N barras; las restantes conservan su posicion. No terminan barras "
               "adyacentes ni mas del 50% en una seccion. Se verifican todos los casos, ambos lados y "
               "elementos completos junto a cada corte. Prolongacion conservadora=max(ld existente, d, 15db, L libre/20), "
               "redondeada hacia mayor longitud de barra al centimetro. Longitudes horizontales; los doblados "
               "y anclajes exteriores conservan su comprobacion independiente. " + REFERENCE)), ""


def connected_foundation_reinforcement_cut(data, mesh, steel, demands, *, continuous=None):
    """Return a feasible proposal, or an explicit reason with no cutoff lengths."""
    base = FoundationReinforcementCut("NO APLICA", "", "Superior central" if steel.face == "Superior" else "Inferior en extremos",
        data.total_length_m, data.left.geometry.footing_width_m,
        data.total_length_m-data.right.geometry.footing_width_m,
        requested_continuous_spacing_m=continuous.spacing_m if continuous else None)
    if steel.status != "OK":
        failures = [label for label, ratio in (("flexion", steel.flexural_utilization),
            ("cortante", steel.shear_utilization), ("fisuracion", steel.crack_utilization),
            ("minimos", steel.minimum_utilization)) if ratio > 1+1e-8]
        return replace(base, reason="El armado elegido sin cortes no cumple: " + ", ".join(failures) + ".")
    if not demands or not any(d.limit_state != "service" for d in demands):
        return replace(base, reason="No hay envolvente de resistencia para calcular los cortes.")
    bar = reinforcing_bar_by_label(steel.bar_label)
    maximum = min(.30, data.left.reinforcement.maximum_spacing_m)
    patterns = partial_cut_patterns(bar, steel.spacing_m, steel.temperature_cm2_m, maximum)
    if continuous is not None:
        patterns = tuple(p for p in patterns if p.cycle_bars == 2 and
                         abs(p.equivalent_spacing_m-continuous.spacing_m) <= 1e-9)
    if not patterns:
        return replace(base, reason=(f"La parrilla elegida no admite cortar barras manteniendo As minimo y "
            f"separacion maxima {maximum:.3f} m; al retirar una barra el hueco es {2*steel.spacing_m:.3f} m."))
    effective = max(d.depth_cm for d in demands)-data.left.reinforcement.footing_cover_cm-bar.diameter_cm/2
    minimum_extension = minimum_flexural_cutoff_extension_cm(effective, bar.diameter_cm, data.clear_span_m*100)/100
    extension = max(steel.required_straight_anchor_cm/100, minimum_extension)
    proposals, reasons = [], []
    for pattern in patterns:
        records = _checked_records(data, mesh, demands, bar, pattern)
        candidate, reason = _candidate(data, steel, base, pattern, records, extension, minimum_extension)
        if candidate:
            proposals.append(candidate)
        else:
            reasons.append(reason)
    if not proposals:
        return replace(base, reason=" ".join(dict.fromkeys(reasons)))
    proposal = max(proposals, key=lambda cut: (cut.saved_steel_fraction, -cut.pattern.cycle_bars))
    return replace(proposal, zones=foundation_zone_checks(data, mesh, steel, demands, proposal))
