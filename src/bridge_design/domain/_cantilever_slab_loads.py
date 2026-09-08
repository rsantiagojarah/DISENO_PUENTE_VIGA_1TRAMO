"""Load effects for concrete deck overhang cantilever design."""

from bridge_design.codes.mtc_2018 import (
    DECK_OVERHANG_LIVE_LOAD_REFERENCE,
    MAX_DECK_OVERHANG_KNIFE_LOAD_APPLICABILITY_M,
    mtc_deck_overhang_knife_load_tn_m,
)
from bridge_design.domain.cantilever_slab import (
    CantileverLoadEffect,
    CantileverSlabApplicabilityError,
    CantileverSlabParameters,
    LoadGroup,
)
from bridge_design.domain.loads import LiveLoads
from bridge_design.domain.materials import MaterialProperties
from bridge_design.domain.transverse_slab import (
    TransverseLoadLayout,
    TransverseSlabGeometry,
)
from bridge_design.validation.input_validators import require_non_negative, require_positive


def cantilever_load_effects(
    geometry: TransverseSlabGeometry,
    materials: MaterialProperties,
    live_loads: LiveLoads,
    layout: TransverseLoadLayout,
    params: CantileverSlabParameters,
) -> tuple[
    tuple[CantileverLoadEffect, ...],
    float,
    float,
    float,
    str,
    tuple[str, ...],
]:
    """Return unfactored load effects at the exterior-girder overhang root."""
    root = geometry.overhang_m
    effects: list[CantileverLoadEffect] = []
    notes: list[str] = []

    effects.append(
        _uniform_effect(
            "DC - peso propio losa",
            "DC",
            materials.concrete.specific_weight_tn_m3 * geometry.slab_thickness_m,
            0.0,
            root,
            root,
            "Peso propio = gamma concreto * t * 1.0 m.",
        )
    )
    _append_uniform_intersection(
        effects,
        "DC - vereda sobre volado",
        "DC",
        materials.sidewalk.specific_weight_tn_m3 * materials.sidewalk.thickness_m,
        0.0,
        layout.sidewalk_width_m,
        root,
        "Carga muerta de vereda en la franja de 1.0 m.",
    )
    _append_uniform_intersection(
        effects,
        "DW - superficie de rodadura sobre volado",
        "DW",
        materials.asphalt.specific_weight_tn_m3 * materials.asphalt.thickness_m,
        layout.asphalt_start_m,
        layout.asphalt_end_m,
        root,
        "DW = superficie de rodadura dentro del volado.",
    )
    _append_uniform_intersection(
        effects,
        "PL - peatones sobre vereda",
        "PL",
        live_loads.pedestrian.load_tn_m2,
        0.0,
        layout.sidewalk_width_m,
        root,
        live_loads.pedestrian.reference,
    )
    _append_point_if_inside(
        effects,
        "DC - baranda",
        "DC",
        materials.railing.weight_kg_m / 1000.0,
        layout.railing_left_m,
        root,
        "Peso lineal de baranda en franja de 1.0 m.",
        notes,
    )
    barrier_centroid = layout.barrier_left_m + layout.barrier_width_m / 2.0
    _append_point_if_inside(
        effects,
        "DC - barrera",
        "DC",
        materials.barrier.weight_kg_m / 1000.0,
        barrier_centroid,
        root,
        "Peso lineal de barrera en franja de 1.0 m.",
        notes,
    )

    traffic_face = layout.barrier_left_m + layout.barrier_width_m
    vehicular_line = traffic_face + params.wheel_clearance_to_traffic_face_m
    traffic_face_to_girder = root - traffic_face
    if vehicular_line > root:
        vehicular_load_method = "Ruedas reales en el analisis transversal"
        notes.append(
            "La linea vehicular queda hacia el interior del eje de la viga exterior "
            f"(D={traffic_face_to_girder:.3f} m; x rueda={vehicular_line:.3f} m > "
            f"x viga={root:.3f} m): no carga directamente el voladizo y su efecto "
            "se evalua como ruedas reales en el analisis transversal de la losa."
        )
    elif traffic_face_to_girder <= MAX_DECK_OVERHANG_KNIFE_LOAD_APPLICABILITY_M:
        vehicular_load_method = "Cuchilla equivalente MTC 2.4.3.2.3.4"
        _append_point_if_inside(
            effects,
            "LL+IM - cuchilla voladizo",
            "LL_IM",
            mtc_deck_overhang_knife_load_tn_m()
            * geometry.strip_length_m
            * (1.0 + params.dynamic_load_allowance),
            vehicular_line,
            root,
            DECK_OVERHANG_LIVE_LOAD_REFERENCE,
            notes,
        )
    else:
        raise CantileverSlabApplicabilityError(
            "No puede completarse el diseno del voladizo: la distancia desde la cara "
            "de trafico hasta el eje de la viga exterior "
            f"(D={traffic_face_to_girder:.3f} m) excede el limite de aplicacion de "
            "la cuchilla equivalente "
            f"({MAX_DECK_OVERHANG_KNIFE_LOAD_APPLICABILITY_M:.3f} m). "
            "Se requiere un calculo alternativo de ruedas y distribucion."
        )
    return (
        tuple(effects),
        traffic_face,
        vehicular_line,
        traffic_face_to_girder,
        vehicular_load_method,
        tuple(notes),
    )


def _append_uniform_intersection(
    effects: list[CantileverLoadEffect],
    label: str,
    group: LoadGroup,
    q_tn_m: float,
    start_m: float,
    end_m: float,
    root_m: float,
    reference: str,
) -> None:
    start = max(start_m, 0.0)
    end = min(end_m, root_m)
    if end > start:
        effects.append(_uniform_effect(label, group, q_tn_m, start, end, root_m, reference))


def _append_point_if_inside(
    effects: list[CantileverLoadEffect],
    label: str,
    group: LoadGroup,
    load_tn: float,
    position_m: float,
    root_m: float,
    reference: str,
    notes: list[str],
) -> None:
    if position_m <= root_m:
        effects.append(_point_effect(label, group, load_tn, position_m, root_m, reference))
        return
    notes.append(
        f"{label} no genera momento de voladizo: x={position_m:.3f} m "
        f"queda hacia el interior del eje exterior x={root_m:.3f} m."
    )


def _uniform_effect(
    label: str,
    group: LoadGroup,
    q_tn_m: float,
    start_m: float,
    end_m: float,
    root_m: float,
    reference: str,
) -> CantileverLoadEffect:
    require_positive(q_tn_m, f"q {label}")
    require_non_negative(start_m, f"inicio {label}")
    require_positive(end_m, f"fin {label}")
    if end_m <= start_m:
        raise ValueError(f"El tramo {label} debe tener longitud positiva.")
    length = end_m - start_m
    centroid = start_m + length / 2.0
    return _point_effect(label, group, q_tn_m * length, centroid, root_m, reference)


def _point_effect(
    label: str,
    group: LoadGroup,
    load_tn: float,
    position_m: float,
    root_m: float,
    reference: str,
) -> CantileverLoadEffect:
    require_positive(load_tn, f"P {label}")
    require_non_negative(position_m, f"x {label}")
    arm = max(root_m - position_m, 0.0)
    return CantileverLoadEffect(
        label=label,
        group=group,
        load_tn=load_tn,
        centroid_from_edge_m=position_m,
        arm_to_root_m=arm,
        root_moment_tn_m=-load_tn * arm,
        reference=reference,
    )
