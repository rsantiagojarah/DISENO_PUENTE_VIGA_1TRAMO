"""ASCII output helpers for terminal summaries."""

from bridge_design.cli.ascii_tables import audit_block_title, audit_subtitle, boxed_table
from bridge_design.domain.barrier import (
    BarrierDesignResult,
    BarrierFlexuralComponent,
)
from bridge_design.domain.cantilever_slab import (
    CantileverCombinedMoment,
    CantileverLoadEffect,
    CantileverSlabDesignResult,
)
from bridge_design.domain.load_combinations import (
    CombinedMomentResult,
    combine_transverse_slab_moments,
)
from bridge_design.domain.crack_control import (
    CrackControlCheck,
    SlabCrackControlReview,
)
from bridge_design.domain.diaphragm import (
    DiaphragmAnalysisResult,
    DiaphragmCombinedMoment,
    DiaphragmFlexuralSteelDesign,
    combine_diaphragm_moments,
    design_diaphragm_reinforcement,
)
from bridge_design.domain.girder_detailing import GirderDetailingResult
from bridge_design.domain.exterior_girder import (
    ExteriorGirderAnalysisResult,
    ExteriorGirderCombinedMoment,
    ExteriorGirderCombinedShear,
    combine_exterior_girder_moments,
    combine_exterior_girder_shears,
    design_exterior_girder_reinforcement,
    design_exterior_girder_shear,
)
from bridge_design.domain.interior_girder import (
    InteriorGirderFatigueReview,
    InteriorGirderAnalysisResult,
    InteriorGirderCombinedMoment,
    InteriorGirderCrackControlReview,
    InteriorGirderReinforcementDesign,
    InteriorGirderShearDesign,
    InteriorGirderStressVerification,
    LongitudinalBarPlacementOption,
    MainGirderSteelDesign,
    combine_interior_girder_moments,
    design_interior_girder_reinforcement,
    design_interior_girder_shear,
)
from bridge_design.domain.project_inputs import ProjectInputs
from bridge_design.domain.transverse_patterns import TransverseLaneGeometryError, validate_lane_geometry
from bridge_design.domain.rebar_catalog import (
    ReinforcementCaseOptions,
    ReinforcementSpacingOption,
)
from bridge_design.domain.reinforcement import (
    FlexuralSteelDesign,
    TransverseSlabReinforcementDesign,
    design_transverse_slab_reinforcement,
)
from bridge_design.domain.transverse_slab import (
    LoadCaseAnalysis,
    TRANSVERSE_WHEEL_CLEARANCE_M,
    TransverseLoadPlacementCase,
    TransverseSlabAnalysisResult,
    transverse_load_placement_cases,
)
from bridge_design.codes.mtc_2018 import (
    mtc_design_lanes,
    mtc_cast_in_place_slab_equivalent_strip_widths_m,
    mtc_dynamic_load_allowance_for_slab,
    mtc_multiple_presence_factor,
)

_LOAD_SCHEME_WIDTH = 62
_LOAD_SCHEME_LABEL_WIDTH = 31
_LONGITUDINAL_SCHEME_WIDTH = 72
_LONGITUDINAL_SCHEME_LABEL_WIDTH = 35


def format_input_summary(project_inputs: ProjectInputs) -> str:
    """Return an ASCII summary of collected inputs."""
    materials = project_inputs.materials
    loads = project_inputs.live_loads
    vehicle = loads.vehicular
    rear_spacing = vehicle.design_truck_spacings_m[1]
    layout = project_inputs.transverse_slab.load_layout
    barrier = project_inputs.barrier

    lines = [
        "=" * 60,
        "RESUMEN DE DATOS INGRESADOS",
        "=" * 60,
        "PROPIEDADES DE MATERIALES",
        "-" * 60,
        f"Pec concreto                         : {materials.concrete.specific_weight_tn_m3:10.3f} Tn/m3",
        f"f'c concreto                         : {materials.concrete.compressive_strength_kg_cm2:10.2f} kg/cm2",
        f"Ec concreto calculado                : {materials.concrete.elastic_modulus_kg_cm2:10.2f} kg/cm2",
        f"fy acero                             : {materials.steel.yield_strength_kg_cm2:10.2f} kg/cm2",
        f"Es acero                             : {materials.steel.elastic_modulus_kg_cm2:10.2f} kg/cm2",
        f"Pea asfalto                          : {materials.asphalt.specific_weight_tn_m3:10.3f} Tn/m3",
        f"Espesor asfalto                      : {materials.asphalt.thickness_m:10.3f} m",
        f"Pev vereda                           : {materials.sidewalk.specific_weight_tn_m3:10.3f} Tn/m3",
        f"Espesor vereda                       : {materials.sidewalk.thickness_m:10.3f} m",
        f"Peso lineal baranda                  : {materials.railing.weight_kg_m:10.2f} kg/m",
        f"Peso lineal barrera                  : {materials.barrier.weight_kg_m:10.2f} kg/m",
        f"H barrera diseno                     : {barrier.geometry.height_m:10.3f} m",
        f"Base barrera-losa                    : {barrier.geometry.base_width_m:10.3f} m",
        f"Ft barrera {barrier.impact_load.test_level:<6s}                  : {barrier.impact_load.transverse_force_tn:10.3f} Tn",
        f"Lt barrera                           : {barrier.impact_load.distribution_length_m:10.3f} m",
        f"Dowel barrera                        : 1/2 in @ {barrier.section_model.dowel_spacing_m:5.3f} m",
        f"Ancho barrera                        : {layout.barrier_width_m:10.3f} m",
        f"Cara exterior barrera izq.           : {layout.barrier_left_m:10.3f} m",
        f"Cara interior trafico barrera izq.   : {layout.barrier_left_m + layout.barrier_width_m:10.3f} m",
        f"Centroide carga barrera izq.         : {layout.barrier_left_m + layout.barrier_width_m / 2.0:10.3f} m",
        "-" * 60,
        "CARGAS VIVAS",
        "-" * 60,
        f"PL carga peatonal                    : {loads.pedestrian.load_tn_m2:10.3f} Tn/m2",
        f"Carga vehicular                      : {vehicle.name}",
        f"Camion ejes                          : {vehicle.design_truck_axles_tn[0]:.3f}, "
        f"{vehicle.design_truck_axles_tn[1]:.3f}, {vehicle.design_truck_axles_tn[2]:.3f} Tn",
        f"Camion espaciamientos                : {vehicle.design_truck_spacings_m[0]:.3f} m, "
        f"{rear_spacing[0]:.3f} a {rear_spacing[1]:.3f} m",
        f"Tandem ejes                          : {vehicle.design_tandem_axles_tn[0]:.3f}, "
        f"{vehicle.design_tandem_axles_tn[1]:.3f} Tn",
        f"Tandem espaciamiento                 : {vehicle.design_tandem_spacing_m:10.3f} m",
        f"Carga de carril                      : {vehicle.lane_load_tn_m:10.3f} Tn/m",
        "-" * 60,
        "VIGA PRINCIPAL INTERIOR",
        "-" * 60,
        f"Luz del puente                       : {project_inputs.interior_girder.span_length_m:10.3f} m",
        f"Ancho tributario interior            : {project_inputs.interior_girder.tributary_width_m:10.3f} m",
        f"g carga viva                         : {project_inputs.interior_girder.live_load_distribution_factor_g:10.3f}",
        f"Diafragmas interiores                : {len(project_inputs.interior_girder.diaphragms):10d}",
        f"Diafragma b x h                      : {project_inputs.diaphragm.thickness_m:5.3f} x "
        f"{project_inputs.diaphragm.height_m:5.3f} m",
        f"Diafragma long. tributaria cargas    : {project_inputs.diaphragm.load_tributary_length_m:10.3f} m",
        "-" * 60,
        "VIGA PRINCIPAL EXTERIOR",
        "-" * 60,
        f"Ancho tributario exterior            : {project_inputs.exterior_girder.tributary_width_m:10.3f} m",
        f"de exterior                          : {project_inputs.exterior_girder.exterior_web_to_traffic_barrier_m:10.3f} m",
        f"g momento exterior                   : {project_inputs.exterior_girder.live_load_distribution_factor_g:10.3f}",
        f"g corte exterior                     : {project_inputs.exterior_girder.live_load_shear_distribution_factor_g:10.3f}",
        "=" * 60,
    ]
    return "\n".join(lines)


def format_transverse_load_location_schemes(project_inputs: ProjectInputs) -> str:
    """Return ASCII schemes for DC, DW, PL and mobile LL+IM load placement."""
    geometry = project_inputs.transverse_slab.geometry
    layout = project_inputs.transverse_slab.load_layout
    cases = transverse_load_placement_cases(
        geometry=geometry,
        materials=project_inputs.materials,
        live_loads=project_inputs.live_loads,
        layout=layout,
    )
    lines = [
        "",
        "=" * 104,
        "ESQUEMAS DE UBICACION DE CARGAS TRANSVERSALES - DC / DW / PL / LL+IM",
        "=" * 104,
        (
            f"Eje x desde borde izquierdo del tablero. Ancho total={geometry.total_width_m:.3f} m | "
            f"S={geometry.girder_spacing_m:.3f} m | a={geometry.overhang_m:.3f} m | "
            f"franja longitudinal={geometry.strip_length_m:.3f} m."
        ),
        (
            "Apoyos: "
            + ", ".join(
                f"{chr(ord('A') + index)}={position:.3f} m"
                for index, position in enumerate(geometry.support_positions_m)
            )
        ),
        (
            f"Veredas: 0.000 a {layout.sidewalk_width_m:.3f} m y "
            f"{geometry.total_width_m - layout.sidewalk_width_m:.3f} a {geometry.total_width_m:.3f} m | "
            f"Calzada/asfalto DW: {layout.asphalt_start_m:.3f} a {layout.asphalt_end_m:.3f} m."
        ),
    ]
    for case in cases:
        lines.extend(_format_transverse_load_location_case(case, geometry))
    lines.extend(_format_mobile_load_location_schemes(project_inputs))
    lines.extend(_format_longitudinal_mobile_load_schemes(project_inputs))
    lines.append("=" * 104)
    return "\n".join(lines)


def _format_longitudinal_mobile_load_schemes(project_inputs: ProjectInputs) -> list[str]:
    geometry = project_inputs.interior_girder
    vehicle = project_inputs.live_loads.vehicular
    truck_rear_min, truck_rear_max = vehicle.design_truck_spacings_m[1]
    lines = [
        "",
        *audit_subtitle("", "LL+IM - esquema movil longitudinal en la luz del puente", 96),
        (
            f"Eje longitudinal X desde apoyo fijo hasta apoyo movil. Luz L={geometry.span_length_m:.3f} m | "
            f"paso de movimiento={geometry.moving_load_step_m:.3f} m | "
            f"carga de carril={vehicle.lane_load_tn_m:.3f} Tn/m."
        ),
        (
            f"Camion HL-93: ejes={vehicle.design_truck_axles_tn[0]:.3f}, "
            f"{vehicle.design_truck_axles_tn[1]:.3f}, {vehicle.design_truck_axles_tn[2]:.3f} Tn | "
            f"separaciones={vehicle.design_truck_spacings_m[0]:.3f} m y "
            f"{truck_rear_min:.3f} a {truck_rear_max:.3f} m | IM={mtc_dynamic_load_allowance_for_slab():.2f}. "
            "xb es la posicion del eje delantero E1; el barrido permite entrada y salida parcial."
        ),
    ]
    lines.extend(
        _format_longitudinal_vehicle_case(
            title="LL+IM - camion de diseno longitudinal",
            span_length_m=geometry.span_length_m,
            lane_load_tn_m=vehicle.lane_load_tn_m,
            axle_loads_tn=vehicle.design_truck_axles_tn,
            spacing_sets_m=(
                (
                    vehicle.design_truck_spacings_m[0],
                    truck_rear_min,
                ),
                (
                    vehicle.design_truck_spacings_m[0],
                    truck_rear_max,
                ),
            ),
            impact_factor=mtc_dynamic_load_allowance_for_slab(),
        )
    )
    lines.extend(
        _format_longitudinal_vehicle_case(
            title="LL+IM - tandem de diseno longitudinal",
            span_length_m=geometry.span_length_m,
            lane_load_tn_m=vehicle.lane_load_tn_m,
            axle_loads_tn=vehicle.design_tandem_axles_tn,
            spacing_sets_m=((vehicle.design_tandem_spacing_m,),),
            impact_factor=mtc_dynamic_load_allowance_for_slab(),
        )
    )
    return lines


def _format_longitudinal_vehicle_case(
    title: str,
    span_length_m: float,
    lane_load_tn_m: float,
    axle_loads_tn: tuple[float, ...],
    spacing_sets_m: tuple[tuple[float, ...], ...],
    impact_factor: float,
) -> list[str]:
    rows = []
    lines = ["", *audit_subtitle("", title, 96)]
    lines.extend(_format_longitudinal_lane_load_scheme(span_length_m, lane_load_tn_m))
    for config_index, spacing_set in enumerate(spacing_sets_m, start=1):
        offsets = _longitudinal_axle_offsets(spacing_set)
        vehicle_length = offsets[-1]
        config_label = f"Config {config_index}"
        lines.extend(
            _format_longitudinal_vehicle_positions(
                span_length_m=span_length_m,
                offsets=offsets,
                spacings=spacing_set,
                config_label=config_label,
            )
        )
        for axle_index, (offset, load) in enumerate(zip(offsets, axle_loads_tn), start=1):
            rows.append(
                (
                    f"C{config_index}-E{axle_index}",
                    f"eje {axle_index}",
                    f"xb + {offset:.3f} m",
                    f"{load:.3f} Tn",
                    f"{load * (1.0 + impact_factor):.3f} Tn",
                )
            )
    lines.extend(
        boxed_table(
            ("Cod.", "Eje", "Posicion movil", "P sin IM", "P con IM"),
            rows,
            aligns=("center", "left", "right", "right", "right"),
            title=f"DATOS - {title}",
        )
    )
    return lines


def _format_longitudinal_lane_load_scheme(
    span_length_m: float,
    lane_load_tn_m: float,
) -> list[str]:
    row = ["v" for _ in range(_LONGITUDINAL_SCHEME_WIDTH + 1)]
    row[0] = "|"
    row[-1] = "|"
    return [
        _longitudinal_scheme_line("Carril diseno", f"q={lane_load_tn_m:.3f} Tn/m, aplicado hacia abajo en toda la luz"),
        _longitudinal_scheme_line("q carril", "".join(row)),
        *_longitudinal_deck_lines(span_length_m),
    ]


def _format_longitudinal_vehicle_positions(
    span_length_m: float,
    offsets: tuple[float, ...],
    spacings: tuple[float, ...],
    config_label: str,
) -> list[str]:
    vehicle_length = offsets[-1]
    base_end = span_length_m - vehicle_length
    positions = (
        ("Vehiculo al inicio", 0.0),
        ("Vehiculo al final", base_end),
    )
    lines = [
        "",
        (
            f"{config_label}: longitud entre primer y ultimo eje={vehicle_length:.3f} m | "
            f"separacion ejes: {_format_spacing_chain(spacings)} | "
            f"barrido xb={-vehicle_length:.3f} a {span_length_m:.3f} m."
        ),
        (
            "En el dibujo se muestran dos posiciones completas dentro de la luz: "
            f"xb=0.000 m y xb={base_end:.3f} m."
        ),
    ]
    for label, base in positions:
        lines.append(_longitudinal_scheme_line(label, _longitudinal_vehicle_row(span_length_m, offsets, base)))
    lines.extend(_longitudinal_deck_lines(span_length_m))
    return lines


def _format_spacing_chain(spacings: tuple[float, ...]) -> str:
    parts = ["E1"]
    for index, spacing in enumerate(spacings, start=2):
        parts.append(f"{spacing:.3f} m")
        parts.append(f"E{index}")
    return " - ".join(parts)


def _longitudinal_vehicle_row(
    span_length_m: float,
    offsets: tuple[float, ...],
    base: float,
) -> str:
    row = [" " for _ in range(_LONGITUDINAL_SCHEME_WIDTH + 1)]
    visible_markers = []
    for axle_index, offset in enumerate(offsets, start=1):
        x_position = base + offset
        if 0.0 <= x_position <= span_length_m:
            visible_markers.append(
                (_longitudinal_scheme_index(x_position, span_length_m), f"E{axle_index}")
            )
    if len(visible_markers) >= 2:
        for (left, _), (right, _) in zip(visible_markers[:-1], visible_markers[1:]):
            for marker in range(left + 1, right):
                row[marker] = "-"
    for marker, label in visible_markers:
        _put_longitudinal_point_load_marker(row, marker, label)
    return "".join(row)


def _longitudinal_deck_lines(span_length_m: float) -> list[str]:
    deck = ["=" for _ in range(_LONGITUDINAL_SCHEME_WIDTH + 1)]
    deck[0] = "^"
    deck[-1] = "^"
    return [
        _longitudinal_scheme_line("VIGA/APOYOS", "".join(deck)),
        _longitudinal_scheme_line("Apoyos", "Fijo" + " " * max(_LONGITUDINAL_SCHEME_WIDTH - 8, 1) + "Movil"),
        _longitudinal_scheme_line("X (m)", f"0.000{' ' * max(_LONGITUDINAL_SCHEME_WIDTH - 10, 1)}{span_length_m:.3f}"),
    ]


def _longitudinal_axle_offsets(spacing_set: tuple[float, ...]) -> tuple[float, ...]:
    offsets = [0.0]
    for spacing in spacing_set:
        offsets.append(offsets[-1] + spacing)
    return tuple(offsets)


def _longitudinal_scheme_line(label: str, scheme: str) -> str:
    return f"{label:<{_LONGITUDINAL_SCHEME_LABEL_WIDTH}} {scheme}"


def _longitudinal_scheme_index(position: float, span_length_m: float) -> int:
    if span_length_m <= 0.0:
        return 0
    return max(
        0,
        min(
            _LONGITUDINAL_SCHEME_WIDTH,
            round(position / span_length_m * _LONGITUDINAL_SCHEME_WIDTH),
        ),
    )


def _put_longitudinal_point_load_marker(row: list[str], index: int, label: str) -> None:
    row[index] = "v"
    if index + len(label) + 1 < len(row):
        _put_scheme_text(row, index + 1, label)
    else:
        _put_scheme_text(row, max(0, index - len(label)), label)
        row[index] = "v"


def _format_mobile_load_location_schemes(project_inputs: ProjectInputs) -> list[str]:
    geometry = project_inputs.transverse_slab.geometry
    layout = project_inputs.transverse_slab.load_layout
    vehicle = project_inputs.live_loads.vehicular
    lane_count, lane_width = mtc_design_lanes(layout.vehicle_move_end_m - layout.vehicle_move_start_m)
    lines = [
        "",
        *audit_subtitle("", "LL+IM - cargas moviles vehiculares", 96),
        "Convencion metrica del proyecto: calzada de 6.00 m admite 2 carriles de 3.00 m.",
        (
            f"Recorrido vehicular ingresado: {layout.vehicle_move_start_m:.3f} a "
            f"{layout.vehicle_move_end_m:.3f} m | separacion minima rueda-barrera="
            f"{TRANSVERSE_WHEEL_CLEARANCE_M:.4f} m | paso={layout.vehicle_step_m:.3f} m."
        ),
        (
            f"Eje pesado HL-93={max(vehicle.design_truck_axles_tn):.3f} Tn | "
            f"separacion transversal de ruedas={vehicle.wheel_transverse_spacing_m:.3f} m | "
            f"ancho de carril de diseno={lane_width:.3f} m | "
            f"franja cargada={vehicle.lane_load_width_m:.3f} m | "
            f"IM={mtc_dynamic_load_allowance_for_slab():.2f}."
        ),
    ]
    for truck_count in range(1, lane_count + 1):
        lines.extend(_format_mobile_load_case(project_inputs, truck_count))
    return lines


def _format_mobile_load_case(
    project_inputs: ProjectInputs,
    truck_count: int,
) -> list[str]:
    geometry = project_inputs.transverse_slab.geometry
    layout = project_inputs.transverse_slab.load_layout
    vehicle = project_inputs.live_loads.vehicular
    width = geometry.total_width_m
    wheel_spacing = vehicle.wheel_transverse_spacing_m
    lane_count, lane_width = mtc_design_lanes(layout.vehicle_move_end_m - layout.vehicle_move_start_m)
    group_width = (truck_count - 1) * lane_width + wheel_spacing
    path_start = layout.vehicle_move_start_m + TRANSVERSE_WHEEL_CLEARANCE_M
    path_end = layout.vehicle_move_end_m - TRANSVERSE_WHEEL_CLEARANCE_M - group_width
    positive_strip, negative_strip = mtc_cast_in_place_slab_equivalent_strip_widths_m(
        geometry.girder_spacing_m
    )
    multiple_presence = mtc_multiple_presence_factor(truck_count)
    impact = mtc_dynamic_load_allowance_for_slab()
    heavy_axle = max(vehicle.design_truck_axles_tn)
    positive_wheel_load = heavy_axle / 2.0 * (1.0 + impact) * multiple_presence / positive_strip
    negative_wheel_load = heavy_axle / 2.0 * (1.0 + impact) * multiple_presence / negative_strip
    title = f"LL+IM - {truck_count} carril(es) movil(es)"
    try:
        validate_lane_geometry(layout.vehicle_move_end_m - layout.vehicle_move_start_m,
                               wheel_spacing, vehicle.lane_load_width_m)
    except TransverseLaneGeometryError as exc:
        return ["", *audit_subtitle("", title, 96), str(exc)]
    if truck_count > lane_count or lane_width < 2 * TRANSVERSE_WHEEL_CLEARANCE_M + wheel_spacing:
        return [
            "",
            *audit_subtitle("", title, 96),
            _format_mobile_reference_scheme(geometry, layout),
            (
                "No aplicable: el ancho libre no permite ubicar el eje pesado HL-93 con "
                f"{truck_count} carril(es), holguras y separaciones normativas. "
                f"Se requiere {group_width + 2.0 * TRANSVERSE_WHEEL_CLEARANCE_M:.3f} m y "
                f"el recorrido libre ingresado mide {layout.vehicle_move_end_m - layout.vehicle_move_start_m:.3f} m."
            ),
        ]

    rows = []
    scheme_lines = []
    for lane_index in range(truck_count):
        left_offset = lane_index * lane_width
        first = path_start + left_offset
        last = path_end + left_offset
        rows.append(
            (
                f"W{2 * lane_index + 1}",
                f"rueda izquierda carril {lane_index + 1}",
                f"x{lane_index + 1}: {first:.3f} a {last:.3f} m",
                f"{positive_wheel_load:.3f} / {negative_wheel_load:.3f} Tn",
            )
        )
        rows.append(
            (
                f"W{2 * lane_index + 2}",
                f"rueda derecha carril {lane_index + 1}",
                f"x{lane_index + 1} + {wheel_spacing:.3f} m",
                f"{positive_wheel_load:.3f} / {negative_wheel_load:.3f} Tn",
            )
        )
        for offset, label in ((0.0, f"W{2 * lane_index + 1}"),
                              (wheel_spacing, f"W{2 * lane_index + 2}")):
            for x, bound in ((first, "min"), (last, "max")):
                row = _blank_load_scheme_row()
                _put_point_load_marker(row, _load_scheme_index(x + offset, width), label)
                scheme_lines.append(_load_scheme_line(f"{label} en x{lane_index + 1} {bound}", "".join(row)))
    return [
        "",
        *audit_subtitle("", title, 96),
        (
            f"m={multiple_presence:.2f}; E(+M)={positive_strip:.3f} m; E(-M)={negative_strip:.3f} m; "
            "P rueda mostrado como +M / -M."
        ),
        "Posiciones xi independientes; carriles sin superposicion dentro de la calzada.",
        "Los extremos de cada rueda son limites individuales, no un grupo rigido simultaneo.",
        *scheme_lines,
        _format_mobile_reference_scheme(geometry, layout),
        *boxed_table(
            ("Cod.", "Rueda", "Posicion movil", "P rueda +M / -M"),
            rows,
            aligns=("center", "left", "right", "right"),
            title=f"DATOS APLICADOS - {title}",
        ),
    ]


def _format_mobile_reference_scheme(geometry, layout) -> str:
    width = geometry.total_width_m
    deck, supports, labels = _deck_support_rows(geometry)
    travel = _blank_load_scheme_row()
    start = _load_scheme_index(layout.vehicle_move_start_m, width)
    end = _load_scheme_index(layout.vehicle_move_end_m, width)
    for marker in range(start, end + 1):
        travel[marker] = "."
    travel[start] = "["
    travel[end] = "]"
    return "\n".join(
        (
            _load_scheme_line("Recorrido calzada", "".join(travel)),
            _load_scheme_line("TABLERO/APOYOS", "".join(deck)),
            _load_scheme_line("", "".join(supports)),
            _load_scheme_line("", "".join(labels)),
            _load_scheme_line("x (m)", f"0.000{' ' * max(_LOAD_SCHEME_WIDTH - 10, 1)}{width:.3f}"),
        )
    )


def _format_mobile_load_scheme(
    geometry,
    layout,
    path_start: float,
    path_end: float,
    wheel_markers: list[tuple[float, str]],
) -> list[str]:
    width = geometry.total_width_m
    deck, supports, labels = _deck_support_rows(geometry)
    travel = _blank_load_scheme_row()
    start = _load_scheme_index(layout.vehicle_move_start_m, width)
    end = _load_scheme_index(layout.vehicle_move_end_m, width)
    for marker in range(start, end + 1):
        travel[marker] = "."
    travel[start] = "["
    travel[end] = "]"
    base_range = _blank_load_scheme_row()
    base_start = _load_scheme_index(path_start, width)
    base_end = _load_scheme_index(path_end, width)
    for marker in range(base_start, base_end + 1):
        base_range[marker] = "-"
    base_range[base_start] = "["
    base_range[base_end] = "]"
    lines = [
        _load_scheme_line("Recorrido calzada", "".join(travel)),
        _load_scheme_line("Rango xb", "".join(base_range)),
    ]
    for offset, label in wheel_markers:
        start_row = _blank_load_scheme_row()
        end_row = _blank_load_scheme_row()
        _put_point_load_marker(start_row, _load_scheme_index(path_start + offset, width), label)
        _put_point_load_marker(end_row, _load_scheme_index(path_end + offset, width), label)
        lines.append(_load_scheme_line(f"{label} en xb inicial", "".join(start_row)))
        lines.append(_load_scheme_line(f"{label} en xb final", "".join(end_row)))
    lines.extend(
        [
            _load_scheme_line("TABLERO/APOYOS", "".join(deck)),
            _load_scheme_line("", "".join(supports)),
            _load_scheme_line("", "".join(labels)),
            _load_scheme_line("x (m)", f"0.000{' ' * max(_LOAD_SCHEME_WIDTH - 10, 1)}{width:.3f}"),
        ]
    )
    return lines


def _format_transverse_load_location_case(
    case: TransverseLoadPlacementCase,
    geometry,
) -> list[str]:
    rows = [
        (
            f"Q{index}",
            "Uniforme",
            segment.label,
            f"{segment.start_m:.3f} a {segment.end_m:.3f} m",
            f"{segment.q_tn_m:.3f} Tn/m",
        )
        for index, segment in enumerate(case.segments, start=1)
    ]
    rows.extend(
        (
            f"P{index}",
            "Puntual",
            point.label,
            f"x={point.position_m:.3f} m",
            f"{point.p_tn:.3f} Tn",
        )
        for index, point in enumerate(case.point_loads, start=1)
    )
    return [
        "",
        *audit_subtitle("", case.name, 96),
        *_format_transverse_load_scheme(case, geometry),
        *boxed_table(
            ("Cod.", "Tipo", "Carga", "Ubicacion", "Intensidad"),
            rows,
            aligns=("center", "left", "left", "right", "right"),
            title=f"DATOS APLICADOS - {case.name}",
        ),
    ]


def _format_transverse_load_scheme(
    case: TransverseLoadPlacementCase,
    geometry,
) -> list[str]:
    width = geometry.total_width_m
    deck, supports, labels = _deck_support_rows(geometry)

    lines = [
        _load_scheme_line("Cargas hacia abajo", "v = sentido de aplicacion sobre el tablero"),
    ]
    for index, segment in enumerate(case.segments, start=1):
        row = _blank_load_scheme_row()
        start = _load_scheme_index(segment.start_m, width)
        end = _load_scheme_index(segment.end_m, width)
        for marker in range(start, end + 1):
            row[marker] = "v"
        row[start] = "|"
        row[end] = "|"
        label = f"Q{index} {segment.label}"[:_LOAD_SCHEME_LABEL_WIDTH]
        lines.append(_load_scheme_line(label, "".join(row)))
    for index, point in enumerate(case.point_loads, start=1):
        row = _blank_load_scheme_row()
        marker = _load_scheme_index(point.position_m, width)
        _put_point_load_marker(row, marker, f"P{index}")
        label = f"P{index} {point.label}"[:_LOAD_SCHEME_LABEL_WIDTH]
        lines.append(_load_scheme_line(label, "".join(row)))
    lines.extend(
        [
            _load_scheme_line("TABLERO/APOYOS", "".join(deck)),
            _load_scheme_line("", "".join(supports)),
            _load_scheme_line("", "".join(labels)),
            _load_scheme_line(
                "x (m)",
                f"0.000{' ' * max(_LOAD_SCHEME_WIDTH - 10, 1)}{width:.3f}",
            ),
        ]
    )
    return lines


def _deck_support_rows(geometry) -> tuple[list[str], list[str], list[str]]:
    width = geometry.total_width_m
    deck = ["=" for _ in range(_LOAD_SCHEME_WIDTH + 1)]
    supports = [" " for _ in range(_LOAD_SCHEME_WIDTH + 1)]
    labels = [" " for _ in range(_LOAD_SCHEME_WIDTH + 1)]
    deck[0] = "|"
    deck[-1] = "|"
    for index, support in enumerate(geometry.support_positions_m):
        marker = _load_scheme_index(support, width)
        deck[marker] = "+"
        supports[marker] = "^"
        labels[marker] = chr(ord("A") + index)
    return deck, supports, labels


def _load_scheme_line(label: str, scheme: str) -> str:
    return f"{label:<{_LOAD_SCHEME_LABEL_WIDTH}} {scheme}"


def _blank_load_scheme_row() -> list[str]:
    return [" " for _ in range(_LOAD_SCHEME_WIDTH + 1)]


def _put_scheme_text(row: list[str], index: int, text: str) -> None:
    start = max(0, min(len(row) - len(text), index))
    for offset, character in enumerate(text):
        row[start + offset] = character


def _put_point_load_marker(row: list[str], index: int, label: str) -> None:
    row[index] = "v"
    if index + len(label) + 1 < len(row):
        _put_scheme_text(row, index + 1, label)
    else:
        _put_scheme_text(row, max(0, index - len(label)), label)
        row[index] = "v"


def _load_scheme_index(position: float, width: float) -> int:
    if width <= 0.0:
        return 0
    return max(0, min(_LOAD_SCHEME_WIDTH, round(position / width * _LOAD_SCHEME_WIDTH)))


def format_diaphragm_design_result(
    result: DiaphragmAnalysisResult,
    project_inputs: ProjectInputs,
) -> str:
    """Return an ASCII summary for transverse diaphragm beam design."""
    geometry = project_inputs.diaphragm
    reinforcement = design_diaphragm_reinforcement(
        geometry=geometry,
        materials=project_inputs.materials,
        analysis=result,
    )
    lines = [
        "",
        *audit_block_title("6", "DISENO DE VIGA DIAFRAGMA", 104),
        "Modelo: viga transversal continua apoyada en los ejes de vigas principales.",
        (
            f"Ancho total={geometry.total_width_m:.3f} m | S={geometry.girder_spacing_m:.3f} m | "
            f"vigas={geometry.girder_count} | b={geometry.thickness_m:.3f} m | h={geometry.height_m:.3f} m."
        ),
        (
            f"Longitud tributaria cargas={geometry.load_tributary_length_m:.3f} m | "
            f"distribucion longitudinal rueda={geometry.wheel_distribution_length_m:.3f} m | "
            f"IM={result.dynamic_load_allowance:.2f}."
        ),
        *audit_subtitle("6.A", "CALCULO DEL ACERO PRINCIPAL NEGATIVO", 104),
    ]
    lines.extend(_format_diaphragm_flexural_table((reinforcement.negative,)))
    lines.extend(_format_main_placement_table(reinforcement.negative.placement_options))
    lines.extend(
        [
            *audit_subtitle("6.B", "MOMENTOS DE FLEXION POSITIVO POR CARGAS", 104),
        ]
    )
    lines.extend(
        _format_diaphragm_case_table(
            (
                result.dc,
                result.dw,
                result.pl,
                result.ll_im_one_truck,
                result.ll_im_two_trucks,
                result.ll_im_envelope,
            )
        )
    )
    lines.extend(_format_diaphragm_flexural_table((reinforcement.positive,)))
    lines.extend(_format_main_placement_table(reinforcement.positive.placement_options))
    lines.extend(
        [
            *audit_subtitle("6.C", "COMBINACIONES DE MOMENTO - DIAFRAGMA", 104),
        ]
    )
    lines.extend(_format_diaphragm_combined_table(tuple(combine_diaphragm_moments(result))))
    lines.extend(
        [
            *audit_subtitle("6.D", "ARMADURA DE CONTRACCION Y TEMPERATURA EN CARAS LATERALES (ART. 5.10.8)", 104),
            (
                f"rho={reinforcement.temperature.ratio:.4f}; "
                f"b={reinforcement.temperature.web_width_cm:.2f} cm; "
                f"As req por cara={reinforcement.temperature.required_area_cm2_m_per_face:.3f} cm2/m."
            ),
        ]
    )
    lines.extend(_format_spacing_case_table(reinforcement.temperature.spacing_options))
    lines.extend(_format_diaphragm_shear_design_lines(reinforcement.shear))
    lines.extend(["=" * 104])
    return "\n".join(lines)


def _format_diaphragm_case_row(case) -> str:
    return " ".join(_format_diaphragm_case_cells(case))


def _format_diaphragm_case_cells(case) -> tuple[str, str, str, str, str, str]:
    return (
        case.name[:52],
        f"{case.max_positive_position_m:.3f}",
        f"{case.max_positive_moment_tn_m:.3f}",
        f"{case.max_negative_position_m:.3f}",
        f"{case.max_negative_moment_tn_m:.3f}",
        f"{case.max_abs_shear_tn:.3f}",
    )


def _format_diaphragm_case_table(cases) -> list[str]:
    return boxed_table(
        ("Caso", "x M+", "M+", "x M-", "M-", "Vmax"),
        (_format_diaphragm_case_cells(case) for case in cases),
        aligns=("left", "right", "right", "right", "right", "right"),
        title="Casos de carga sin factor",
    )


def _format_diaphragm_case_row_legacy(case) -> str:
    return (
        f"{case.name[:52]:52s} "
        f"{case.max_positive_position_m:8.3f} "
        f"{case.max_positive_moment_tn_m:10.3f} "
        f"{case.max_negative_position_m:8.3f} "
        f"{case.max_negative_moment_tn_m:10.3f} "
        f"{case.max_abs_shear_tn:10.3f}"
    )


def _format_diaphragm_flexural_row(row: DiaphragmFlexuralSteelDesign) -> str:
    return " ".join(_format_diaphragm_flexural_cells(row))


def _format_diaphragm_flexural_cells(row: DiaphragmFlexuralSteelDesign) -> tuple[str, str, str, str, str, str, str, str, str]:
    return (
        row.label[:36],
        row.controlling_combination_name[:15],
        f"{row.position_m:.3f}",
        f"{row.design_moment_tn_m:.3f}",
        f"{row.effective_depth_cm:.2f}",
        f"{row.section_width_cm:.2f}",
        f"{row.strength_area_cm2:.3f}",
        f"{row.minimum_area_cm2:.3f}",
        f"{row.required_area_cm2:.3f}",
    )


def _format_diaphragm_flexural_table(rows: tuple[DiaphragmFlexuralSteelDesign, ...]) -> list[str]:
    return boxed_table(
        ("Elemento", "Comb", "x", "Mu", "d", "b", "As flex", "As min", "As req"),
        (_format_diaphragm_flexural_cells(row) for row in rows),
        aligns=("left", "left", "right", "right", "right", "right", "right", "right", "right"),
        title="Acero principal requerido",
    )


def _format_diaphragm_flexural_row_legacy(row: DiaphragmFlexuralSteelDesign) -> str:
    return (
        f"{row.label[:36]:36s} "
        f"{row.controlling_combination_name[:15]:15s} "
        f"{row.position_m:7.3f} "
        f"{row.design_moment_tn_m:10.3f} "
        f"{row.effective_depth_cm:8.2f} "
        f"{row.section_width_cm:8.2f} "
        f"{row.strength_area_cm2:9.3f} "
        f"{row.minimum_area_cm2:9.3f} "
        f"{row.required_area_cm2:9.3f}"
    )


def _format_diaphragm_combined_row(row: DiaphragmCombinedMoment) -> str:
    return " ".join(_format_diaphragm_combined_cells(row))


def _format_diaphragm_combined_cells(row: DiaphragmCombinedMoment) -> tuple[str, str, str, str, str, str, str, str, str, str, str, str]:
    return (
        row.combination_name[:15],
        row.direction,
        f"{row.position_m:.3f}",
        f"{row.dc_moment_tn_m:.3f}",
        f"{row.dc_factor:.2f}",
        f"{row.dw_moment_tn_m:.3f}",
        f"{row.dw_factor:.2f}",
        f"{row.pl_moment_tn_m:.3f}",
        f"{row.pl_factor:.2f}",
        f"{row.ll_im_moment_tn_m:.3f}",
        f"{row.ll_im_factor:.2f}",
        f"{row.combined_moment_tn_m:.3f}",
    )


def _format_diaphragm_combined_table(rows: tuple[DiaphragmCombinedMoment, ...]) -> list[str]:
    return boxed_table(
        ("Combinacion", "Dir", "x", "DC", "gDC", "DW", "gDW", "PL", "gPL", "LL+IM", "gLL", "M comb"),
        (_format_diaphragm_combined_cells(row) for row in rows),
        aligns=("left", "center", "right", "right", "right", "right", "right", "right", "right", "right", "right", "right"),
        title="Momentos combinados LRFD",
    )


def _format_diaphragm_combined_row_legacy(row: DiaphragmCombinedMoment) -> str:
    return (
        f"{row.combination_name[:15]:15s} "
        f"{row.direction:>3s} "
        f"{row.position_m:7.3f} "
        f"{row.dc_moment_tn_m:9.3f} "
        f"{row.dc_factor:5.2f} "
        f"{row.dw_moment_tn_m:9.3f} "
        f"{row.dw_factor:5.2f} "
        f"{row.pl_moment_tn_m:9.3f} "
        f"{row.pl_factor:5.2f} "
        f"{row.ll_im_moment_tn_m:9.3f} "
        f"{row.ll_im_factor:5.2f} "
        f"{row.combined_moment_tn_m:10.3f}"
    )


def _format_diaphragm_shear_design_lines(shear: InteriorGirderShearDesign) -> list[str]:
    row = shear.controlling_shear
    lines = [
        *audit_subtitle("D", "DISENO POR CORTE - VIGA DIAFRAGMA", 104),
        "Modelo seccional MTC/AASHTO para seccion no pretensada: beta=2.0, theta=45 grados.",
    ]
    lines.extend(
        boxed_table(
            ("x", "Vu", "DC", "DW", "PL+LL", "dv", "Vc", "Vs req", "Av/s req", "s max"),
            (
                (
                    f"{row.position_m:.3f}",
                    f"{row.combined_shear_tn:.3f}",
                    f"{row.dc_shear_tn:.3f}",
                    f"{row.dw_shear_tn:.3f}",
                    f"{row.ll_im_shear_tn:.3f}",
                    f"{shear.effective_shear_depth_cm:.2f}",
                    f"{shear.vc_tn:.3f}",
                    f"{shear.required_vs_tn:.3f}",
                    f"{shear.required_av_cm2_m:.3f}",
                    f"{shear.maximum_spacing_m:.3f}",
                ),
            ),
            aligns=("right",) * 10,
            title="Demanda y resistencia por corte",
        )
    )
    lines.extend(
        [
        _format_shear_section_limit(shear),
        (
            f"Armadura transversal requerida: {'SI' if shear.transverse_required else 'NO'}. "
            f"Av/s minimo={shear.minimum_av_cm2_m:.3f} cm2/m; phi={shear.phi:.2f}."
        ),
        ]
    )
    lines.extend(_format_shear_option_table(shear.options))
    return lines


def format_barrier_design_result(result: BarrierDesignResult) -> str:
    """Return an ASCII summary for concrete barrier design."""
    flexure = result.flexure
    yield_line = result.yield_line
    shear = result.shear_transfer
    dowel = result.dowel
    development = result.development
    lines = [
        "",
        *audit_block_title("4", "DISENO DE BARRERA DE CONCRETO TIPO NEW JERSEY", 104),
        "Metodo: lineas de fluencia AASHTO/MTC para Evento Extremo II.",
        *audit_subtitle("4.A", "RESISTENCIA EN FLEXION ALREDEDOR DE EJE VERTICAL A LA BARRERA - Mw", 104),
    ]
    lines.extend(_format_barrier_component_table(flexure.mw_components, "Componentes Mw"))
    lines.extend(
        [
            f"Mw = {flexure.mw_tn_m:.3f} Tn*m/m",
            *audit_subtitle("4.B", "RESISTENCIA EN FLEXION PARALELA AL EJE LONGITUDINAL DEL PUENTE - Mc", 104),
        ]
    )
    lines.extend(_format_barrier_component_table(flexure.mc_components, "Componentes Mc"))
    lines.extend(
        [
            f"Mc promedio = {flexure.mc_tn_m:.3f} Tn*m/m",
            *audit_subtitle("4.C", "LONGITUD CRITICA DE LINEA DE ROTURA - Lc", 104),
            (
                f"Patron={yield_line.impact_pattern}; "
                f"Lc={yield_line.critical_length_m:.3f} m"
            ),
            *audit_subtitle("4.D", "RESISTENCIA NOMINAL A CARGA TRANSVERSAL - Rw", 104),
            (
                f"Rw={yield_line.nominal_transverse_resistance_tn:.3f} Tn; "
                f"Ft={yield_line.demand_transverse_force_tn:.3f} Tn; "
                f"Estado={yield_line.resistance_status}"
            ),
            *audit_subtitle("4.E", "TRANSFERENCIA DE CORTANTE ENTRE BARRERA Y LOSA", 104),
            (
                f"Vct={shear.acting_shear_tn_m:.3f} Tn/m; "
                f"Vn={shear.nominal_shear_tn_m:.3f} Tn/m; "
                f"Vn bruto={shear.nominal_shear_raw_tn_m:.3f} Tn/m; "
                f"limite={shear.nominal_shear_limit_tn_m:.3f} Tn/m; "
                f"Estado={shear.status}"
            ),
            (
                f"Acv={shear.contact_area_cm2_m:.1f} cm2/m; "
                f"Avf={shear.provided_avf_cm2_m:.3f} cm2/m; "
                f"Pc={shear.permanent_compression_kg_m:.1f} kg/m"
            ),
            *audit_subtitle("4.F", "CHEQUEO DEL DOWEL", 104),
            (
                f"Avf requerido={dowel.required_avf_cm2_m:.3f} cm2/m; "
                f"Avf provisto={dowel.provided_avf_cm2_m:.3f} cm2/m; "
                f"Estado={dowel.status}"
            ),
            *audit_subtitle("4.G", "LONGITUD DE ANCLAJE DEL DOWEL CON GANCHO", 104),
            (
                f"lhb={development.basic_lhb_cm:.2f} cm; "
                f"lambda_er={development.excess_reinforcement_factor:.3f}; "
                f"ldh mod={development.modified_ldh_cm:.2f} cm; "
                f"ldh req={development.required_ldh_cm:.2f} cm; "
                f"disp={development.available_length_cm:.2f} cm; "
                f"Estado={development.status}"
            ),
            f"Extension minima de gancho = {development.hook_extension_cm:.2f} cm.",
            "=" * 104,
        ]
    )
    return "\n".join(lines)


def _format_barrier_component_row(component: BarrierFlexuralComponent) -> str:
    return " ".join(_format_barrier_component_cells(component))


def _format_barrier_component_cells(component: BarrierFlexuralComponent) -> tuple[str, str, str, str, str, str]:
    return (
        component.label,
        f"{component.steel_area_cm2:.3f}",
        f"{component.concrete_width_cm:.2f}",
        f"{component.effective_depth_cm:.2f}",
        f"{component.compression_block_depth_cm:.3f}",
        f"{component.nominal_moment_tn_m:.3f}",
    )


def _format_barrier_component_table(
    components: tuple[BarrierFlexuralComponent, ...],
    title: str,
) -> list[str]:
    return boxed_table(
        ("Seccion", "As", "b", "d", "a", "Mn"),
        (_format_barrier_component_cells(component) for component in components),
        aligns=("left", "right", "right", "right", "right", "right"),
        title=title,
    )


def _format_barrier_component_row_legacy(component: BarrierFlexuralComponent) -> str:
    return (
        f"{component.label:>7s} "
        f"{component.steel_area_cm2:8.3f} "
        f"{component.concrete_width_cm:8.2f} "
        f"{component.effective_depth_cm:8.2f} "
        f"{component.compression_block_depth_cm:8.3f} "
        f"{component.nominal_moment_tn_m:10.3f}"
    )


def format_transverse_analysis_result(
    result: TransverseSlabAnalysisResult,
    project_inputs: ProjectInputs | None = None,
) -> str:
    """Return an ASCII summary of transverse slab analysis results."""
    lines = [
        "",
        *audit_block_title("1", "DISENO DE LOSA ENTRE VIGAS", 104),
        "Convencion: momento positivo = sagante; momento negativo = sobre apoyos/voladizos.",
        "LL+IM: eje pesado HL-93; se evaluan todos los numeros admisibles de carriles cargados.",
        "Carriles y ruedas con posiciones independientes; retiros desde el borde de cada carril.",
        (
            f"Factores MTC: IM={result.dynamic_load_allowance:.2f}; "
            f"E+={result.equivalent_strip_width_positive_m:.3f} m; "
            f"E-={result.equivalent_strip_width_negative_m:.3f} m."
        ),
        "IM se aplica a ruedas; para losa entre vigas no se aplica tandem ni carga de carril.",
    ]

    combined = combine_transverse_slab_moments(result)
    lines.extend(
        [
            *audit_subtitle("1.A", "COMBINACIONES DE CARGA - MOMENTOS COMBINADOS", 104),
            "DC, DW, PL y LL+IM son momentos sin factor en la posicion critica.",
            "g=0.00 indica carga variable favorable no incluida en la envolvente.",
        ]
    )
    lines.extend(_format_combined_moment_table(tuple(combined)))

    if project_inputs is not None:
        reinforcement = design_transverse_slab_reinforcement(
            geometry=project_inputs.transverse_slab.geometry,
            materials=project_inputs.materials,
            analysis=result,
        )
        lines.extend(
            [
                *audit_subtitle("1.B", "DISENO DE ACERO DE LOSA TRANSVERSAL", 104),
                (
                    "Supuestos: franja de 1.00 m; phi flexion="
                    f"{reinforcement.parameters.flexural_resistance_factor:.2f}; "
                    f"recubrimiento={reinforcement.parameters.concrete_cover_cm:.2f} cm; "
                    f"barra principal={reinforcement.parameters.main_bar_diameter_cm:.2f} cm."
                ),
            ]
        )
        lines.extend(_format_transverse_reinforcement_table(reinforcement))
        lines.append(
            "Areas en cm2/m. Mu en Tn*m. El acero de distribucion se calcula sobre As+ requerido."
        )
        lines.extend(_format_reinforcement_spacing_tables(reinforcement))

    lines.extend(
        [
            "-" * 88,
            "Posiciones criticas vehiculares:",
            _format_vehicle_control(result.ll_im_one_truck),
            _format_vehicle_control(result.ll_im_two_trucks),
            _format_vehicle_control(result.ll_im_envelope),
            "-" * 88,
            "Reacciones por apoyo para casos estaticos (Tn):",
            _format_reactions("DC", result.dc),
            _format_reactions("DW", result.dw),
            _format_reactions("PL", result.pl),
            "=" * 88,
        ]
    )
    return "\n".join(lines)


def format_cantilever_slab_design_result(
    result: CantileverSlabDesignResult,
) -> str:
    """Return an ASCII A-E summary for deck-overhang cantilever design."""
    flexural = result.flexural_steel
    temperature = result.temperature_steel
    development = result.development
    shear = result.shear
    crack = result.crack_control
    lines = [
        "",
        *audit_block_title("5", "DISENO DE LOSA EN VOLADIZO - FRANJA DE 1.0 m", 108),
        *audit_subtitle("5.A", "CRITERIOS LRFD APLICABLES - TABLA 3.4.1-1 AASHTO / MTC 2.4.5.3.1-1", 108),
        (
            f"Resistencia I: DC 1.25/0.90, DW 1.50/0.65, PL 1.75 y LL+IM 1.75; "
            f"Servicio I: 1.00; Servicio III: LL+IM y PL 0.80."
        ),
        (
            f"Voladizo vehicular: cara trafico x={result.traffic_face_from_edge_m:.3f} m; "
            f"linea vehicular x={result.vehicular_line_from_edge_m:.3f} m; "
            f"D cara-viga={result.traffic_face_to_exterior_girder_m:.3f} m; "
            f"IM={result.parameters.dynamic_load_allowance:.2f}."
        ),
        f"Tratamiento vehicular: {result.vehicular_load_method}.",
        *audit_subtitle("5.B", "MOMENTOS DE FLEXION POR CARGAS - RAIZ EN EJE DE VIGA EXTERIOR", 108),
    ]
    lines.extend(_format_cantilever_load_effect_table(result.load_effects))
    lines.extend(
        [
            "P eq en Tn para la franja longitudinal de 1.0 m. Momentos negativos son hogging en el apoyo.",
            *audit_subtitle("5.B.1", "COMBINACIONES LRFD EN LA RAIZ DEL VOLADIZO", 108),
        ]
    )
    lines.extend(_format_cantilever_combination_table(result.combinations))
    lines.extend(
        [
            *audit_subtitle("5.C", "CALCULO DEL ACERO", 108),
            (
                f"phi={result.parameters.flexural_resistance_factor:.2f}; "
                f"d={flexural.effective_depth_cm:.2f} cm; "
                f"Mu={flexural.design_moment_tn_m:.3f} Tn*m/m "
                f"({flexural.controlling_combination_name})."
            ),
            (
                f"As flex={flexural.strength_area_cm2_m:.3f} cm2/m; "
                f"As min={flexural.minimum_area_cm2_m:.3f} cm2/m; "
                f"As req={flexural.required_area_cm2_m:.3f} cm2/m."
            ),
            (
                f"Temperatura: rho={temperature.ratio:.4f}; "
                f"Ag={temperature.gross_area_cm2_m:.1f} cm2/m; "
                f"As temp={temperature.required_area_cm2_m:.3f} cm2/m."
            ),
        ]
    )
    lines.extend(_format_spacing_case_table(flexural.spacing_options))
    lines.extend(_format_spacing_case_table(temperature.spacing_options))
    lines.extend(
        [
            *audit_subtitle("5.D", "LONGITUD DE DESARROLLO", 108),
            (
                f"Barra adoptada={development.bar_label}; "
                f"As prov={development.provided_area_cm2_m:.3f} cm2/m; "
                f"lambda excedente={development.excess_reinforcement_factor:.3f}."
            ),
            (
                f"ldb={development.basic_development_length_cm:.2f} cm; "
                f"ld req={development.required_development_length_cm:.2f} cm; "
                f"extension minima posterior a corte={development.minimum_past_cutoff_extension_cm:.2f} cm."
            ),
            *audit_subtitle("5.E", "LONGITUD DE BARRAS ADICIONALES DEL VOLADO", 108),
            (
                f"Proyeccion exterior hasta recubrimiento={development.exterior_projection_length_m:.3f} m; "
                f"anclaje interior requerido={development.interior_anchor_length_m:.3f} m; "
                f"L barra adicional={development.total_additional_bar_length_m:.3f} m; "
                f"Estado={development.status}."
            ),
            *audit_subtitle("5.F", "CARGA HORIZONTAL DE COLISION DE BARRERA SOBRE EL VOLADIZO", 108),
        ]
    )
    if result.barrier_collision is None:
        lines.append("No se evaluo colision de barrera porque no se recibio resultado de diseno de barrera.")
    else:
        collision = result.barrier_collision
        lines.extend(
            [
                (
                    f"Ft={collision.transverse_force_tn:.3f} Tn; "
                    f"H={collision.barrier_height_m:.3f} m; "
                    f"L transferencia={collision.transfer_length_m:.3f} m; "
                    f"Vct={collision.interface_shear_tn_m:.3f} Tn/m."
                ),
                (
                    f"M colision={collision.collision_moment_tn_m:.3f} Tn*m/m; "
                    f"M permanente factorizado={collision.permanent_moment_tn_m:.3f} Tn*m/m; "
                    f"Mu EE-II={collision.design_moment_tn_m:.3f} Tn*m/m."
                ),
            ]
        )
    lines.extend(
        [
            *audit_subtitle("5.G", "CHEQUEO POR CORTANTE EN LA RAIZ DEL VOLADIZO", 108),
            (
                f"Vu={shear.combined_shear_tn:.3f} Tn/m; "
                f"dv={shear.effective_shear_depth_cm:.2f} cm; "
                f"Vc={shear.vc_tn:.3f} Tn/m; "
                f"phiVc={shear.phi_vc_tn:.3f} Tn/m; "
                f"Estado={shear.status}."
            ),
            (
                f"Componentes: DC={shear.dc_shear_tn:.3f}*{shear.dc_factor:.2f}; "
                f"DW={shear.dw_shear_tn:.3f}*{shear.dw_factor:.2f}; "
                f"PL={shear.pl_shear_tn:.3f}*{shear.pl_factor:.2f}; "
                f"LL+IM={shear.ll_im_shear_tn:.3f}*{shear.ll_im_factor:.2f}."
            ),
            *audit_subtitle("5.H", "CONTROL DE FISURACION DEL ACERO SUPERIOR DEL VOLADIZO", 108),
            (
                f"{crack.service_combination_name}: Ms={crack.service_moment_tn_m:.3f} Tn*m/m; "
                f"barra={crack.bar_label}; s prov={crack.provided_spacing_m:.3f} m; "
                f"s max={crack.maximum_spacing_m:.3f} m; E-s={crack.spacing_status}; "
                f"Estado={crack.status}."
            ),
            (
                f"fs={crack.steel_stress_kg_cm2:.0f} kg/cm2; "
                f"fs lim={crack.steel_stress_limit_kg_cm2:.0f} kg/cm2; "
                f"E-fs={crack.stress_status}; "
                f"fs usado={crack.steel_stress_used_kg_cm2:.0f} kg/cm2; "
                f"beta_s={crack.beta_s:.3f}; dc={crack.dc_cm:.2f} cm."
            ),
        ]
    )
    if result.applicability_notes:
        lines.extend(["-" * 108, "Notas de aplicabilidad:"])
        lines.extend(f"- {note}" for note in result.applicability_notes)
    lines.append("=" * 108)
    return "\n".join(lines)


def _format_combined_moment_row(row: CombinedMomentResult) -> str:
    return " ".join(_format_combined_moment_cells(row))


def _format_combined_moment_cells(row: CombinedMomentResult) -> tuple[str, str, str, str, str, str, str, str, str, str, str, str]:
    return (
        row.combination_name[:15],
        row.direction,
        f"{row.position_m:.3f}",
        f"{row.dc_moment_tn_m:.3f}",
        f"{row.dc_factor:.2f}",
        f"{row.dw_moment_tn_m:.3f}",
        f"{row.dw_factor:.2f}",
        f"{row.pl_moment_tn_m:.3f}",
        f"{row.pl_factor:.2f}",
        f"{row.ll_im_moment_tn_m:.3f}",
        f"{row.ll_im_factor:.2f}",
        f"{row.combined_moment_tn_m:.3f}",
    )


def _format_combined_moment_table(rows: tuple[CombinedMomentResult, ...]) -> list[str]:
    return boxed_table(
        ("Combinacion", "Dir", "x (m)", "DC", "gDC", "DW", "gDW", "PL", "gPL", "LL+IM", "gLL", "M comb"),
        (_format_combined_moment_cells(row) for row in rows),
        aligns=("left", "center", "right", "right", "right", "right", "right", "right", "right", "right", "right", "right"),
        title="Momentos combinados LRFD",
    )


def _format_combined_moment_row_legacy(row: CombinedMomentResult) -> str:
    return (
        f"{row.combination_name[:15]:15s} "
        f"{row.direction:>3s} "
        f"{row.position_m:7.3f} "
        f"{row.dc_moment_tn_m:8.3f} "
        f"{row.dc_factor:5.2f} "
        f"{row.dw_moment_tn_m:8.3f} "
        f"{row.dw_factor:5.2f} "
        f"{row.pl_moment_tn_m:8.3f} "
        f"{row.pl_factor:5.2f} "
        f"{row.ll_im_moment_tn_m:8.3f} "
        f"{row.ll_im_factor:5.2f} "
        f"{row.combined_moment_tn_m:9.3f}"
    )


def _format_cantilever_load_effect(effect: CantileverLoadEffect) -> str:
    return " ".join(_format_cantilever_load_effect_cells(effect))


def _format_cantilever_load_effect_cells(effect: CantileverLoadEffect) -> tuple[str, str, str, str, str, str]:
    return (
        effect.label[:38],
        effect.group,
        f"{effect.load_tn:.3f}",
        f"{effect.centroid_from_edge_m:.3f}",
        f"{effect.arm_to_root_m:.3f}",
        f"{effect.root_moment_tn_m:.3f}",
    )


def _format_cantilever_load_effect_table(effects: tuple[CantileverLoadEffect, ...]) -> list[str]:
    return boxed_table(
        ("Carga", "Tipo", "P eq", "x", "brazo", "M"),
        (_format_cantilever_load_effect_cells(effect) for effect in effects),
        aligns=("left", "center", "right", "right", "right", "right"),
        title="Efectos de carga por franja de 1.0 m",
    )


def _format_cantilever_load_effect_legacy(effect: CantileverLoadEffect) -> str:
    return (
        f"{effect.label[:38]:38s} "
        f"{effect.group:>6s} "
        f"{effect.load_tn:9.3f} "
        f"{effect.centroid_from_edge_m:8.3f} "
        f"{effect.arm_to_root_m:8.3f} "
        f"{effect.root_moment_tn_m:10.3f}"
    )


def _format_cantilever_combination_row(row: CantileverCombinedMoment) -> str:
    return " ".join(_format_cantilever_combination_cells(row))


def _format_cantilever_combination_cells(row: CantileverCombinedMoment) -> tuple[str, str, str, str, str, str, str, str, str, str]:
    return (
        row.combination_name[:15],
        f"{row.dc_moment_tn_m:.3f}",
        f"{row.dc_factor:.2f}",
        f"{row.dw_moment_tn_m:.3f}",
        f"{row.dw_factor:.2f}",
        f"{row.pl_moment_tn_m:.3f}",
        f"{row.pl_factor:.2f}",
        f"{row.ll_im_moment_tn_m:.3f}",
        f"{row.ll_im_factor:.2f}",
        f"{row.combined_moment_tn_m:.3f}",
    )


def _format_cantilever_combination_table(rows: tuple[CantileverCombinedMoment, ...]) -> list[str]:
    return boxed_table(
        ("Combinacion", "DC", "gDC", "DW", "gDW", "PL", "gPL", "LL+IM", "gLL", "Mu"),
        (_format_cantilever_combination_cells(row) for row in rows),
        aligns=("left", "right", "right", "right", "right", "right", "right", "right", "right", "right"),
        title="Momentos combinados LRFD",
    )


def _format_cantilever_combination_row_legacy(row: CantileverCombinedMoment) -> str:
    return (
        f"{row.combination_name[:15]:15s} "
        f"{row.dc_moment_tn_m:9.3f} "
        f"{row.dc_factor:5.2f} "
        f"{row.dw_moment_tn_m:9.3f} "
        f"{row.dw_factor:5.2f} "
        f"{row.pl_moment_tn_m:9.3f} "
        f"{row.pl_factor:5.2f} "
        f"{row.ll_im_moment_tn_m:9.3f} "
        f"{row.ll_im_factor:5.2f} "
        f"{row.combined_moment_tn_m:10.3f}"
    )


def _format_flexural_steel_row(row: FlexuralSteelDesign) -> str:
    return " ".join(_format_flexural_steel_cells(row))


def _format_flexural_steel_cells(row: FlexuralSteelDesign) -> tuple[str, str, str, str, str, str, str, str]:
    return (
        row.label,
        row.controlling_combination_name[:15],
        f"{row.position_m:.3f}",
        f"{row.design_moment_tn_m:.3f}",
        f"{row.effective_depth_cm:.2f}",
        f"{row.strength_area_cm2_m:.3f}",
        f"{row.minimum_area_cm2_m:.3f}",
        f"{row.required_area_cm2_m:.3f}",
    )


def _format_transverse_reinforcement_table(
    reinforcement: TransverseSlabReinforcementDesign,
) -> list[str]:
    rows = [
        _format_flexural_steel_cells(reinforcement.negative),
        _format_flexural_steel_cells(reinforcement.positive),
        (
            "Acero temperatura",
            "rho",
            "-",
            "-",
            "-",
            "-",
            f"{reinforcement.temperature.ratio:.4f}",
            f"{reinforcement.temperature.required_area_cm2_m:.3f}",
        ),
        (
            "Acero distribucion",
            "% As+",
            "-",
            "-",
            "-",
            f"{reinforcement.distribution.percent_of_positive_steel:.2f}%",
            f"{reinforcement.distribution.positive_main_area_cm2_m:.3f}",
            f"{reinforcement.distribution.required_area_cm2_m:.3f}",
        ),
    ]
    return boxed_table(
        ("Elemento", "Comb", "x (m)", "Mu", "d", "As flex", "As min/base", "As req"),
        rows,
        aligns=("left", "left", "right", "right", "right", "right", "right", "right"),
        title="Acero requerido por franja de 1.0 m",
    )


def _format_flexural_steel_row_legacy(row: FlexuralSteelDesign) -> str:
    return (
        f"{row.label:22s} "
        f"{row.controlling_combination_name[:15]:15s} "
        f"{row.position_m:7.3f} "
        f"{row.design_moment_tn_m:9.3f} "
        f"{row.effective_depth_cm:7.2f} "
        f"{row.strength_area_cm2_m:9.3f} "
        f"{row.minimum_area_cm2_m:9.3f} "
        f"{row.required_area_cm2_m:9.3f}"
    )


def _format_reinforcement_spacing_tables(
    reinforcement: TransverseSlabReinforcementDesign,
) -> list[str]:
    lines = [
        "-" * 88,
        "TABLAS DE DIAMETRO Y DISTRIBUCION DE ACERO",
        (
            "Item: opcion elegible. REC: recomendada por menor exceso de As entre "
            "opciones que cumplen y quedan en rango constructivo de referencia."
        ),
        (
            "Separacion calculada con s=Abarra/As req y redondeada hacia abajo "
            f"cada {reinforcement.parameters.spacing_step_m:.3f} m."
        ),
    ]
    for case_options in _reinforcement_case_options(reinforcement):
        lines.extend(_format_spacing_case_table(case_options))
    return lines


def _reinforcement_case_options(
    reinforcement: TransverseSlabReinforcementDesign,
) -> tuple[ReinforcementCaseOptions, ...]:
    return tuple(
        case
        for case in (
            reinforcement.negative.spacing_options,
            reinforcement.positive.spacing_options,
            reinforcement.temperature.spacing_options,
            reinforcement.distribution.spacing_options,
        )
        if case is not None
    )


def _format_spacing_case_table(case_options: ReinforcementCaseOptions) -> list[str]:
    rows = (
        (
            option.item,
            option.bar.label,
            f"{option.bar.area_cm2:.2f}",
            f"{option.spacing_m:.3f}",
            f"{option.provided_area_cm2_m:.3f}",
            f"{option.excess_percent:.1f}%",
            "OK" if option.is_compliant else "NO",
            "REC" if option.is_recommended else "",
        )
        for option in case_options.options
        if option.is_compliant
    )
    return boxed_table(
        ("Item", "Diam", "Abar", "s (m)", "As prov", "Exceso", "Estado", "Uso"),
        rows,
        aligns=("right", "right", "right", "right", "right", "right", "center", "center"),
        title=f"{case_options.label} | As req = {case_options.required_area_cm2_m:.3f} cm2/m",
    )


def _format_spacing_option_row(option: ReinforcementSpacingOption) -> str:
    state = "OK" if option.is_compliant else "NO"
    use = "REC" if option.is_recommended else ""
    return (
        f"{option.item:4d} "
        f"{option.bar.label:>7s} "
        f"{option.bar.area_cm2:8.2f} "
        f"{option.spacing_m:8.3f} "
        f"{option.provided_area_cm2_m:9.3f} "
        f"{option.excess_percent:8.1f}% "
        f"{state:>7s} "
        f"{use:>5s}"
    )


def format_crack_control_review(crack_review: SlabCrackControlReview) -> str:
    """Return an ASCII crack-control review table."""
    return "\n".join(_format_crack_control_review_lines(crack_review))


def format_interior_girder_analysis_result(
    result: InteriorGirderAnalysisResult,
    project_inputs: ProjectInputs,
) -> str:
    """Return an ASCII summary of interior girder analysis and design."""
    geometry = project_inputs.interior_girder
    reinforcement = design_interior_girder_reinforcement(
        geometry=geometry,
        materials=project_inputs.materials,
        analysis=result,
    )
    lines = [
        "",
        *audit_block_title("2", "DISENO DE VIGAS INTERIORES", 104),
        "Modelo: viga simplemente apoyada; apoyo izquierdo fijo y apoyo derecho movil.",
        (
            f"L={geometry.span_length_m:.3f} m | ancho tributario={geometry.tributary_width_m:.3f} m | "
            f"g={geometry.live_load_distribution_factor_g:.3f} | IM={result.dynamic_load_allowance:.2f}"
        ),
        (
            f"Seccion T: bf={geometry.tributary_width_m:.3f} m, hf={geometry.slab_thickness_m:.3f} m, "
            f"bw={geometry.web_width_m:.3f} m, h alma={geometry.girder_total_height_m:.3f} m."
        ),
        *audit_subtitle("2.A", "DIAFRAGMAS MODELADOS COMO CARGAS DC CONCENTRADAS", 104),
    ]
    if geometry.diaphragms:
        lines.extend(
            boxed_table(
                ("Item", "x (m)", "t long", "h", "b trib"),
                (
                    (
                        index,
                        f"{diaphragm.position_m:.3f}",
                        f"{diaphragm.thickness_m:.3f}",
                        f"{diaphragm.height_m:.3f}",
                        f"{diaphragm.tributary_width_m:.3f}",
                    )
                    for index, diaphragm in enumerate(geometry.diaphragms, start=1)
                ),
                aligns=("right", "right", "right", "right", "right"),
                title="Diafragmas ingresados",
            )
        )
    else:
        lines.append("No se ingresaron diafragmas interiores.")
    lines.extend(
        [
            *audit_subtitle("2.B", "CASOS DE CARGA SIN FACTOR", 104),
        ]
    )
    lines.extend(
        _format_longitudinal_case_table(
            (
                result.dc,
                result.dw,
                result.truck_ll_im,
                result.tandem_ll_im,
                result.ll_im_envelope,
            )
        )
    )
    lines.extend(
        [
            "LL+IM ya incluye IM en ejes, carga de carril concurrente y factor g.",
            *audit_subtitle("2.C", "COMBINACIONES DE CARGA - MOMENTOS EN LA MISMA ESTACION", 104),
        ]
    )
    lines.extend(_format_interior_combined_table(tuple(combine_interior_girder_moments(result))))
    lines.extend(_format_interior_reinforcement_lines(reinforcement))
    lines.extend(_format_interior_reinforcement_option_tables(reinforcement))
    shear = design_interior_girder_shear(
        geometry=geometry,
        materials=project_inputs.materials,
        analysis=result,
        reinforcement=reinforcement,
    )
    lines.extend(_format_shear_design_lines(shear))
    lines.extend(
        [
            "-" * 96,
            "Posiciones criticas de carga movil:",
            _format_interior_vehicle_control(result.truck_ll_im),
            _format_interior_vehicle_control(result.tandem_ll_im),
            _format_interior_vehicle_control(result.ll_im_envelope),
            "=" * 96,
        ]
    )
    return "\n".join(lines)


def format_interior_girder_crack_control_review(
    crack_review: InteriorGirderCrackControlReview,
) -> str:
    """Return an ASCII crack-control table for the interior girder."""
    row = crack_review.main
    lines = [
        *audit_subtitle("2.E", "REVISION DE FISURACION POR DISTRIBUCION DE ARMADURA - VIGA INTERIOR", 104),
        "Criterio: s prov <= s max, evaluado con Servicio I y acero principal seleccionado.",
    ]
    lines.extend(_format_crack_control_table((row,)))
    return "\n".join(lines)


def format_girder_detailing_result(
    result: GirderDetailingResult,
    code: str,
) -> str:
    """Return longitudinal bar-cut and stirrup-zone detailing tables."""
    detailed_bar_count = sum(cut.bar_count for cut in result.longitudinal_cuts)
    lines = [
        *audit_subtitle(code, f"DETALLE CONSTRUCTIVO - {result.label.upper()}", 104),
        "Criterio: envolvente Mu(x)/Vu(x) y As requerido por estacion.",
        "Grupos de barras adicionales extendidos con ld; estribos zonificados por Vu(x).",
        (
            f"Acero longitudinal adoptado: {result.selected_main_bar.bar_count} barras "
            f"{result.selected_main_bar.bar_label}; base continua={result.continuous_bar_count}; "
            f"barras detalladas={detailed_bar_count}; ld={result.development_length_m:.3f} m."
        ),
        (
            f"Detalle por capas: {result.selected_main_bar.layers} capas; "
            f"hasta {result.selected_main_bar.bars_per_layer} barras/capa; cortes agrupados por capa."
        ),
        f"Cortes fisicos adoptados: {result.physical_cut_count}.",
    ]
    lines.extend(_format_longitudinal_cut_detail_table(result))
    lines.extend(
        [
            (
                f"Estribo adoptado: {result.selected_stirrup.legs} ramas "
                f"{result.selected_stirrup.bar_label}. La separacion se redondea hacia abajo "
                "a la grilla del proyecto."
            )
        ]
    )
    lines.extend(
        boxed_table(
            (
                "Zona",
                "x ini",
                "x fin",
                "Estribo",
                "s",
                "Vu max",
                "Av/s req",
                "Av/s prov",
                "s max",
                "phiVn",
                "Estado",
            ),
            (
                (
                    index,
                    f"{zone.start_m:.3f}",
                    f"{zone.end_m:.3f}",
                    f"{zone.legs}r {zone.bar_label}",
                    f"{zone.spacing_m:.3f}",
                    f"{zone.maximum_vu_tn:.3f}",
                    f"{zone.required_av_cm2_m:.3f}",
                    f"{zone.provided_av_cm2_m:.3f}",
                    f"{zone.maximum_spacing_m:.3f}",
                    f"{zone.phi_vn_tn:.3f}",
                    zone.status,
                )
                for index, zone in enumerate(result.stirrup_zones, start=1)
            ),
            aligns=(
                "right",
                "right",
                "right",
                "right",
                "right",
                "right",
                "right",
                "right",
                "right",
                "right",
                "center",
            ),
            title="Distribucion de estribos por zonas",
        )
    )
    return "\n".join(lines)


def _format_longitudinal_cut_detail_table(result: GirderDetailingResult) -> list[str]:
    status_notes = {
        "OK": "OK",
        "CONTINUA POR LD": "LD",
        "ADOPTADA EN ZONA CRITICA": "ZC",
    }
    rows = []
    for cut in result.longitudinal_cuts:
        note_code = status_notes.get(cut.status, cut.status)
        rows.append(
            (
                _compact_cut_group(cut.group),
                cut.bar_label,
                cut.bar_count,
                cut.threshold_bar_count,
                _format_m_range(cut.theoretical_start_m, cut.theoretical_end_m),
                f"{cut.development_length_m:.3f}",
                _format_m_range(cut.detail_start_m, cut.detail_end_m),
                f"{cut.bar_length_m:.3f}",
                cut.physical_cut_count,
                note_code,
            )
        )

    lines = boxed_table(
        (
            "Grupo",
            "Barra",
            "Cant.",
            "Req.",
            "x teor. (m)",
            "ld (m)",
            "x det. (m)",
            "L (m)",
            "Cortes",
            "Estado",
        ),
        rows,
        aligns=(
            "left",
            "right",
            "right",
            "right",
            "right",
            "right",
            "right",
            "right",
            "right",
            "center",
        ),
        title="Cortes de acero longitudinal (rangos en m)",
        max_width=104,
    )
    lines.extend(
        [
            "Leyenda: Base=barras continuas; Adic.=barras adicionales; "
            "Req.=barras requeridas para activar el grupo.",
            "Estado: OK=corte adoptado; LD=continua por longitud de desarrollo; "
            "ZC=adoptada en zona critica.",
        ]
    )
    return lines


def _compact_cut_group(group: str) -> str:
    if group == "Barras continuas":
        return "Base"
    if group.startswith("Adicional "):
        return group.replace("Adicional ", "Adic. ", 1)
    return group


def _format_m_range(start_m: float, end_m: float) -> str:
    return f"{start_m:.3f}-{end_m:.3f}"


def format_exterior_girder_analysis_result(
    result: ExteriorGirderAnalysisResult,
    project_inputs: ProjectInputs,
) -> str:
    """Return an ASCII summary of exterior girder analysis and strength design."""
    geometry = project_inputs.exterior_girder.with_distribution_factors(
        project_inputs.live_loads.vehicular
    )
    reinforcement = design_exterior_girder_reinforcement(
        geometry=geometry,
        materials=project_inputs.materials,
        analysis=result,
    )
    shear = design_exterior_girder_shear(
        geometry=geometry,
        materials=project_inputs.materials,
        analysis=result,
        reinforcement=reinforcement,
    )
    exterior_shear = max(
        combine_exterior_girder_shears(geometry, result, reinforcement.parameters),
        key=lambda item: item.combined_shear_tn,
    )
    lines = [
        "",
        *audit_block_title("3", "DISENO DE VIGAS EXTERIORES", 104),
        "Modelo: viga simplemente apoyada; apoyo izquierdo fijo y apoyo derecho movil.",
        (
            f"L={geometry.span_length_m:.3f} m | ancho tributario={geometry.tributary_width_m:.3f} m | "
            f"de={geometry.exterior_web_to_traffic_barrier_m:.3f} m | "
            f"gM={result.distribution_factor_g:.3f} | gV={result.shear_distribution_factor_g:.3f} | "
            f"IM={result.dynamic_load_allowance:.2f}"
        ),
        (
            f"Cargas DC exteriores: losa tributaria, alma, vereda={geometry.sidewalk_tributary_width_m:.3f} m, "
            "baranda, barrera y diafragmas. DW usa solo el ancho tributario de asfalto."
        ),
        *audit_subtitle("3.A", "MOMENTOS DE FLEXION POR CARGAS SIN FACTOR", 104),
    ]
    lines.extend(
        _format_exterior_load_case_table(
            (
                result.dc,
                result.dw,
                result.pl,
                result.truck_ll_im,
                result.tandem_ll_im,
                result.ll_im_envelope,
            )
        )
    )
    lines.extend(
        [
        "LL+IM vehicular incluye IM, carga de carril concurrente, gM para momentos y gV para cortes.",
        *audit_subtitle("3.B", "MOMENTO DE DISENO - ESTADO LIMITE DE RESISTENCIA I", 104),
        "DC, DW, PL y LL+IM son efectos sin factor tomados en la misma estacion critica.",
        ]
    )
    lines.extend(_format_exterior_combined_table(tuple(combine_exterior_girder_moments(result))))
    lines.extend(
        [
            *audit_subtitle("3.C", "ACERO A FLEXION - VIGA EXTERIOR", 104),
            (
                f"phi flexion={reinforcement.parameters.flexural_resistance_factor:.2f}; "
                f"bf={reinforcement.main.flange_width_cm:.2f} cm; "
                f"hf={reinforcement.main.flange_thickness_cm:.2f} cm; "
                f"bw={reinforcement.main.web_width_cm:.2f} cm; "
                f"capas max detalle={reinforcement.parameters.maximum_main_bar_layers}."
            ),
        ]
    )
    lines.extend(_format_main_girder_steel_table((reinforcement.main,)))
    lines.extend(_format_main_placement_table(reinforcement.main.placement_options))
    lines.extend(
        [
            *audit_subtitle("3.D", "ACERO COMPLEMENTARIO - VIGA EXTERIOR", 104),
            "Acero de temperatura y Ask en cm2/m por cada cara lateral.",
        ]
    )
    lines.extend(_format_side_reinforcement_table(reinforcement))
    lines.extend(_format_spacing_case_table(reinforcement.temperature.spacing_options))
    lines.extend(_format_spacing_case_table(reinforcement.skin.spacing_options))
    lines.extend(_format_exterior_shear_design_lines(exterior_shear, shear))
    lines.extend(
        [
            "-" * 104,
            "Posiciones criticas de carga movil:",
            _format_interior_vehicle_control(result.truck_ll_im),
            _format_interior_vehicle_control(result.tandem_ll_im),
            _format_interior_vehicle_control(result.ll_im_envelope),
            "=" * 104,
        ]
    )
    return "\n".join(lines)


def format_abutment_reaction_summary(
    interior_result: InteriorGirderAnalysisResult,
    exterior_result: ExteriorGirderAnalysisResult,
    project_inputs: ProjectInputs,
) -> str:
    """Return unfactored bridge reactions converted to abutment line loads."""
    girder_count = project_inputs.interior_girder.girder_count
    exterior_count = 2
    interior_count = max(girder_count - exterior_count, 0)
    abutment_length_m = project_inputs.transverse_slab.geometry.total_width_m
    rows = (
        _abutment_reaction_row(
            "PDC",
            "Carga muerta DC",
            interior_result.dc,
            exterior_result.dc,
            interior_count,
            exterior_count,
            abutment_length_m,
        ),
        _abutment_reaction_row(
            "PDW",
            "Carga de asfalto DW",
            interior_result.dw,
            exterior_result.dw,
            interior_count,
            exterior_count,
            abutment_length_m,
        ),
        _abutment_reaction_row(
            "PPL",
            "Carga peatonal PL",
            None,
            exterior_result.pl,
            interior_count,
            exterior_count,
            abutment_length_m,
        ),
        _abutment_live_reaction_row(
            "PLL+IM",
            "Carga viva vehicular",
            interior_result.ll_im_envelope,
            exterior_result.ll_im_envelope,
            interior_count,
            exterior_count,
            abutment_length_m,
        ),
    )
    service_fixed_total = sum(float(row[2]) for row in rows)
    service_movable_total = sum(float(row[3]) for row in rows)
    service_fixed_line = sum(float(row[4]) for row in rows)
    service_movable_line = sum(float(row[5]) for row in rows)
    total_row = (
        "P servicio",
        "DC+DW+PL+LL+IM",
        f"{service_fixed_total:.3f}",
        f"{service_movable_total:.3f}",
        f"{service_fixed_line:.3f}",
        f"{service_movable_line:.3f}",
    )
    lines = [
        "",
        *audit_block_title("7", "REACCIONES PARA DISENO DE ESTRIBOS", 104),
        (
            "Valores sin factor. La columna q es la carga por metro lineal que usa el modelo de estribo "
            f"por franja de 1 m; L estribo={abutment_length_m:.3f} m."
        ),
        (
            f"Primero se suman {interior_count} viga(s) interior(es) y {exterior_count} viga(s) exterior(es); "
            "luego q = R total / L estribo."
        ),
    ]
    lines.extend(
        boxed_table(
            ("Simbolo", "Carga", "R fijo total", "R movil total", "q fijo", "q movil"),
            (*rows, total_row),
            aligns=("left", "left", "right", "right", "right", "right"),
            title="Reacciones verticales sin factor: total y carga lineal",
        )
    )
    lines.extend(
        [
            "Unidades: R en Tn; q en Ton/m.",
            "PDC incluye losa, vigas, veredas, barandas, barreras y diafragmas modelados como DC.",
            "PDW incluye solo la superficie de rodadura de asfalto tributaria.",
            "PLL+IM es la envolvente vehicular maxima de reaccion; incluye IM y carga de carril.",
            (
                "La carga peatonal se reporta como PPL: usarla aparte de PLL+IM, sin IM, "
                "y combinarla como carga viva peatonal cuando las veredas puedan estar cargadas."
            ),
            "=" * 104,
        ]
    )
    return "\n".join(lines)


def _abutment_reaction_row(
    symbol: str,
    label: str,
    interior_case,
    exterior_case,
    interior_count: int,
    exterior_count: int,
    abutment_length_m: float,
) -> tuple[str, str, str, str, str, str]:
    interior_fixed, interior_movable = _support_reaction_pair(interior_case)
    exterior_fixed, exterior_movable = _support_reaction_pair(exterior_case)
    fixed_total = interior_count * interior_fixed + exterior_count * exterior_fixed
    movable_total = interior_count * interior_movable + exterior_count * exterior_movable
    return (
        symbol,
        label,
        f"{fixed_total:.3f}",
        f"{movable_total:.3f}",
        f"{fixed_total / abutment_length_m:.3f}",
        f"{movable_total / abutment_length_m:.3f}",
    )


def _abutment_live_reaction_row(
    symbol: str,
    label: str,
    interior_case,
    exterior_case,
    interior_count: int,
    exterior_count: int,
    abutment_length_m: float,
) -> tuple[str, str, str, str, str, str]:
    interior_reaction = interior_case.max_shear_tn
    exterior_reaction = exterior_case.max_shear_tn
    total = interior_count * interior_reaction + exterior_count * exterior_reaction
    return (
        symbol,
        label,
        f"{total:.3f}",
        f"{total:.3f}",
        f"{total / abutment_length_m:.3f}",
        f"{total / abutment_length_m:.3f}",
    )


def _support_reaction_pair(case) -> tuple[float, float]:
    if case is None:
        return (0.0, 0.0)
    reactions = dict(case.support_reactions_tn)
    return (reactions.get("Fijo", 0.0), reactions.get("Movil", 0.0))


def _format_longitudinal_case_row(case) -> str:
    return " ".join(_format_longitudinal_case_cells(case))


def _format_longitudinal_case_cells(case) -> tuple[str, str, str, str, str]:
    reactions = dict(case.support_reactions_tn)
    return (
        case.name[:42],
        f"{case.max_positive_position_m:.3f}",
        f"{case.max_positive_moment_tn_m:.3f}",
        f"{reactions.get('Fijo', 0.0):.3f}",
        f"{reactions.get('Movil', 0.0):.3f}",
    )


def _format_longitudinal_case_table(cases) -> list[str]:
    return boxed_table(
        ("Caso", "x Mmax", "Mmax", "R fijo", "R movil"),
        (_format_longitudinal_case_cells(case) for case in cases),
        aligns=("left", "right", "right", "right", "right"),
        title="Casos longitudinales sin factor",
    )


def _format_longitudinal_case_row_legacy(case) -> str:
    reactions = dict(case.support_reactions_tn)
    return (
        f"{case.name[:42]:42s} "
        f"{case.max_positive_position_m:8.3f} "
        f"{case.max_positive_moment_tn_m:10.3f} "
        f"{reactions.get('Fijo', 0.0):10.3f} "
        f"{reactions.get('Movil', 0.0):10.3f}"
    )


def _format_exterior_load_case_row(case) -> str:
    return " ".join(_format_exterior_load_case_cells(case))


def _format_exterior_load_case_cells(case) -> tuple[str, str, str, str, str, str]:
    reactions = dict(case.support_reactions_tn)
    return (
        case.name[:52],
        f"{case.max_positive_position_m:.3f}",
        f"{case.max_positive_moment_tn_m:.3f}",
        f"{case.max_shear_tn:.3f}",
        f"{reactions.get('Fijo', 0.0):.3f}",
        f"{reactions.get('Movil', 0.0):.3f}",
    )


def _format_exterior_load_case_table(cases) -> list[str]:
    return boxed_table(
        ("Caso", "x Mmax", "Mmax", "Vmax", "R fijo", "R movil"),
        (_format_exterior_load_case_cells(case) for case in cases),
        aligns=("left", "right", "right", "right", "right", "right"),
        title="Casos exteriores sin factor",
    )


def _format_exterior_load_case_row_legacy(case) -> str:
    reactions = dict(case.support_reactions_tn)
    return (
        f"{case.name[:52]:52s} "
        f"{case.max_positive_position_m:8.3f} "
        f"{case.max_positive_moment_tn_m:10.3f} "
        f"{case.max_shear_tn:10.3f} "
        f"{reactions.get('Fijo', 0.0):10.3f} "
        f"{reactions.get('Movil', 0.0):10.3f}"
    )


def _format_interior_combined_row(row: InteriorGirderCombinedMoment) -> str:
    return " ".join(_format_interior_combined_cells(row))


def _format_interior_combined_cells(row: InteriorGirderCombinedMoment) -> tuple[str, str, str, str, str, str, str, str, str]:
    return (
        row.combination_name[:15],
        f"{row.position_m:.3f}",
        f"{row.dc_moment_tn_m:.3f}",
        f"{row.dc_factor:.2f}",
        f"{row.dw_moment_tn_m:.3f}",
        f"{row.dw_factor:.2f}",
        f"{row.ll_im_moment_tn_m:.3f}",
        f"{row.ll_im_factor:.2f}",
        f"{row.combined_moment_tn_m:.3f}",
    )


def _format_interior_combined_table(rows: tuple[InteriorGirderCombinedMoment, ...]) -> list[str]:
    return boxed_table(
        ("Combinacion", "x (m)", "DC", "gDC", "DW", "gDW", "LL+IM", "gLL", "Mu/Ms"),
        (_format_interior_combined_cells(row) for row in rows),
        aligns=("left", "right", "right", "right", "right", "right", "right", "right", "right"),
        title="Momentos combinados LRFD",
    )


def _format_interior_combined_row_legacy(row: InteriorGirderCombinedMoment) -> str:
    return (
        f"{row.combination_name[:15]:15s} "
        f"{row.position_m:7.3f} "
        f"{row.dc_moment_tn_m:9.3f} "
        f"{row.dc_factor:5.2f} "
        f"{row.dw_moment_tn_m:9.3f} "
        f"{row.dw_factor:5.2f} "
        f"{row.ll_im_moment_tn_m:9.3f} "
        f"{row.ll_im_factor:5.2f} "
        f"{row.combined_moment_tn_m:10.3f}"
    )


def _format_exterior_combined_row(row: ExteriorGirderCombinedMoment) -> str:
    return " ".join(_format_exterior_combined_cells(row))


def _format_exterior_combined_cells(row: ExteriorGirderCombinedMoment) -> tuple[str, str, str, str, str, str, str, str, str, str, str]:
    return (
        row.combination_name[:15],
        f"{row.position_m:.3f}",
        f"{row.dc_moment_tn_m:.3f}",
        f"{row.dc_factor:.2f}",
        f"{row.dw_moment_tn_m:.3f}",
        f"{row.dw_factor:.2f}",
        f"{row.pl_moment_tn_m:.3f}",
        f"{row.pl_factor:.2f}",
        f"{row.ll_im_moment_tn_m:.3f}",
        f"{row.ll_im_factor:.2f}",
        f"{row.combined_moment_tn_m:.3f}",
    )


def _format_exterior_combined_table(rows: tuple[ExteriorGirderCombinedMoment, ...]) -> list[str]:
    return boxed_table(
        ("Combinacion", "x", "DC", "gDC", "DW", "gDW", "PL", "gPL", "LL+IM", "gLL", "Mu"),
        (_format_exterior_combined_cells(row) for row in rows),
        aligns=("left", "right", "right", "right", "right", "right", "right", "right", "right", "right", "right"),
        title="Momentos combinados LRFD",
    )


def _format_exterior_combined_row_legacy(row: ExteriorGirderCombinedMoment) -> str:
    return (
        f"{row.combination_name[:15]:15s} "
        f"{row.position_m:7.3f} "
        f"{row.dc_moment_tn_m:9.3f} "
        f"{row.dc_factor:5.2f} "
        f"{row.dw_moment_tn_m:9.3f} "
        f"{row.dw_factor:5.2f} "
        f"{row.pl_moment_tn_m:9.3f} "
        f"{row.pl_factor:5.2f} "
        f"{row.ll_im_moment_tn_m:9.3f} "
        f"{row.ll_im_factor:5.2f} "
        f"{row.combined_moment_tn_m:10.3f}"
    )


def _format_interior_reinforcement_lines(
    reinforcement: InteriorGirderReinforcementDesign,
) -> list[str]:
    main = reinforcement.main
    lines = [
        *audit_subtitle("2.D", "DISENO DE ACERO - VIGA PRINCIPAL INTERIOR", 104),
        (
            "Supuestos: seccion T simplemente reforzada; phi flexion="
            f"{reinforcement.parameters.flexural_resistance_factor:.2f}; "
            f"recubrimiento={reinforcement.parameters.concrete_cover_cm:.2f} cm."
        ),
    ]
    lines.extend(_format_main_girder_steel_table((main,)))
    lines.extend(_format_side_reinforcement_table(reinforcement))
    lines.append("Areas principales en cm2. Acero de temperatura y Ask en cm2/m por cada cara lateral.")
    return lines


def _format_main_girder_steel_row(row: MainGirderSteelDesign) -> str:
    return " ".join(_format_main_girder_steel_cells(row))


def _format_main_girder_steel_cells(row: MainGirderSteelDesign) -> tuple[str, str, str, str, str, str, str, str]:
    return (
        "Acero principal inferior",
        row.controlling_combination_name[:15],
        f"{row.position_m:.3f}",
        f"{row.design_moment_tn_m:.3f}",
        f"{row.effective_depth_cm:.2f}",
        f"{row.strength_area_cm2:.3f}",
        f"{row.minimum_area_cm2:.3f}",
        f"{row.required_area_cm2:.3f}",
    )


def _format_main_girder_steel_table(rows: tuple[MainGirderSteelDesign, ...]) -> list[str]:
    return boxed_table(
        ("Elemento", "Comb", "x (m)", "Mu", "d", "As flex", "As min", "As req"),
        (_format_main_girder_steel_cells(row) for row in rows),
        aligns=("left", "left", "right", "right", "right", "right", "right", "right"),
        title="Acero principal requerido",
    )


def _format_side_reinforcement_table(
    reinforcement: InteriorGirderReinforcementDesign,
) -> list[str]:
    return boxed_table(
        ("Elemento", "Criterio", "dl", "As base", "As req"),
        (
            (
                "Temp. caras laterales",
                f"rho={reinforcement.temperature.ratio:.4f}",
                "-",
                "-",
                f"{reinforcement.temperature.required_area_cm2_m_per_face:.3f}",
            ),
            (
                "Ask longitudinal por cara",
                "AASHTO/MTC",
                f"{reinforcement.skin.effective_depth_cm:.2f}",
                "-",
                f"{reinforcement.skin.required_area_cm2_m_per_face:.3f}",
            ),
        ),
        aligns=("left", "left", "right", "right", "right"),
        title="Acero complementario requerido por cara",
    )


def _format_main_girder_steel_row_legacy(row: MainGirderSteelDesign) -> str:
    return (
        f"{'Acero principal inferior':30s} "
        f"{row.controlling_combination_name[:15]:15s} "
        f"{row.position_m:7.3f} "
        f"{row.design_moment_tn_m:10.3f} "
        f"{row.effective_depth_cm:8.2f} "
        f"{row.strength_area_cm2:9.3f} "
        f"{row.minimum_area_cm2:9.3f} "
        f"{row.required_area_cm2:9.3f}"
    )


def _format_interior_reinforcement_option_tables(
    reinforcement: InteriorGirderReinforcementDesign,
) -> list[str]:
    lines = [
        "-" * 96,
        "TABLAS DE ACEROS REQUERIDOS Y OPCIONES DE COLOCACION - VIGA INTERIOR",
        "REC: opcion recomendada entre las que cumplen area, capas y separacion libre minima.",
    ]
    lines.extend(_format_main_placement_table(reinforcement.main.placement_options))
    lines.extend(_format_spacing_case_table(reinforcement.temperature.spacing_options))
    lines.extend(_format_spacing_case_table(reinforcement.skin.spacing_options))
    return lines


def _format_main_placement_table(case_options) -> list[str]:
    rows = []
    for option in case_options.options:
        if option.is_compliant or option.is_recommended or option.bar_count in (2, 4, 6, 8, 10, 12, 16, 20, 24):
            rows.append(
                (
                    option.item,
                    option.bar_label,
                    option.bar_count,
                    option.layers,
                    f"{option.provided_area_cm2:.3f}",
                    f"{option.excess_percent:.1f}%",
                    f"{option.clear_spacing_cm:.2f}",
                    "OK" if option.is_compliant else "NO",
                    "REC" if option.is_recommended else "",
                )
            )
    return boxed_table(
        ("Item", "Diam", "N", "Capas", "As prov", "Exceso", "s libre", "Estado", "Uso"),
        rows,
        aligns=("right", "right", "right", "right", "right", "right", "right", "center", "center"),
        title=f"{case_options.label} | As req = {case_options.required_area_cm2:.3f} cm2",
    )


def _format_main_placement_row(option: LongitudinalBarPlacementOption) -> str:
    state = "OK" if option.is_compliant else "NO"
    use = "REC" if option.is_recommended else ""
    return (
        f"{option.item:4d} "
        f"{option.bar_label:>7s} "
        f"{option.bar_count:4d} "
        f"{option.layers:6d} "
        f"{option.provided_area_cm2:9.3f} "
        f"{option.excess_percent:8.1f}% "
        f"{option.clear_spacing_cm:8.2f} "
        f"{state:>7s} "
        f"{use:>5s}"
    )


def _format_interior_vehicle_control(case) -> str:
    if case.critical_vehicle_position_m is None:
        return f"{case.name}: no aplica."
    before_g = (
        f"; M antes de g={case.unfactored_before_g_moment_tn_m:.3f} Tn*m"
        if case.unfactored_before_g_moment_tn_m is not None
        else ""
    )
    return (
        f"{case.name}: primer eje en x={case.critical_vehicle_position_m:.3f} m; "
        f"{case.vehicle_configuration}; g={case.distribution_factor_g:.3f}{before_g}."
    )


def _format_fatigue_review_lines(review: InteriorGirderFatigueReview) -> list[str]:
    cracked = "SI" if review.section.is_cracked else "NO"
    lines = [
        *audit_subtitle("F", "FATIGA - VIGA PRINCIPAL INTERIOR", 104),
        "F.1 Carga de fatiga: camion de diseno, separacion trasera fija de 30 ft, IM=15%, sin carga de carril ni presencia multiple.",
        "F.2 Seccion fisurada: se usa si la traccion por cargas permanentes + Fatiga I excede 0.095 sqrt(f'c).",
    ]
    lines.extend(_format_fatigue_review_table(review, cracked))
    lines.append(
        "Esfuerzos en kg/cm2. M fat incluye gFat e IM=15%; Fatiga I aplica factor 1.50 al rango.",
    )
    return lines


def _format_stress_verification_lines(
    verification: InteriorGirderStressVerification,
) -> list[str]:
    lines = [*audit_subtitle("F.3 / D.3", "VERIFICACION DE ESFUERZOS - SERVICIO I", 104)]
    lines.extend(_format_stress_verification_table(verification))
    lines.append(f"Concreto: {verification.concrete_status}. Acero: {verification.steel_status}.")
    return lines


def _format_shear_design_lines(shear: InteriorGirderShearDesign) -> list[str]:
    row = shear.controlling_shear
    lines = [
        *audit_subtitle("G", "DISENO POR CORTE - VIGA PRINCIPAL INTERIOR", 104),
        "Modelo seccional MTC/AASHTO para seccion no pretensada: beta=2.0, theta=45 grados.",
    ]
    lines.extend(
        boxed_table(
            ("x", "Vu", "DC", "DW", "LL+IM", "dv", "Vc", "Vs req", "Av/s req", "s max"),
            (
                (
                    f"{row.position_m:.3f}",
                    f"{row.combined_shear_tn:.3f}",
                    f"{row.dc_shear_tn:.3f}",
                    f"{row.dw_shear_tn:.3f}",
                    f"{row.ll_im_shear_tn:.3f}",
                    f"{shear.effective_shear_depth_cm:.2f}",
                    f"{shear.vc_tn:.3f}",
                    f"{shear.required_vs_tn:.3f}",
                    f"{shear.required_av_cm2_m:.3f}",
                    f"{shear.maximum_spacing_m:.3f}",
                ),
            ),
            aligns=("right",) * 10,
            title="Demanda y resistencia por corte",
        )
    )
    lines.extend(
        [
        _format_shear_section_limit(shear),
        (
            f"Armadura transversal requerida: {'SI' if shear.transverse_required else 'NO'}. "
            f"Av/s minimo={shear.minimum_av_cm2_m:.3f} cm2/m; phi={shear.phi:.2f}."
        ),
        ]
    )
    lines.extend(_format_shear_option_table(shear.options))
    return lines


def _format_exterior_shear_design_lines(
    row: ExteriorGirderCombinedShear,
    shear: InteriorGirderShearDesign,
) -> list[str]:
    lines = [
        *audit_subtitle("C", "DISENO POR CORTE - VIGA PRINCIPAL EXTERIOR", 104),
        "Modelo seccional MTC/AASHTO para seccion no pretensada: beta=2.0, theta=45 grados.",
    ]
    lines.extend(
        boxed_table(
            ("x", "Vu", "DC", "DW", "PL", "LL+IM", "dv", "Vc", "Vs req", "Av/s req", "s max"),
            (
                (
                    f"{row.position_m:.3f}",
                    f"{row.combined_shear_tn:.3f}",
                    f"{row.dc_shear_tn:.3f}",
                    f"{row.dw_shear_tn:.3f}",
                    f"{row.pl_shear_tn:.3f}",
                    f"{row.ll_im_shear_tn:.3f}",
                    f"{shear.effective_shear_depth_cm:.2f}",
                    f"{shear.vc_tn:.3f}",
                    f"{shear.required_vs_tn:.3f}",
                    f"{shear.required_av_cm2_m:.3f}",
                    f"{shear.maximum_spacing_m:.3f}",
                ),
            ),
            aligns=("right",) * 11,
            title="Demanda y resistencia por corte",
        )
    )
    lines.extend(
        [
        _format_shear_section_limit(shear),
        (
            f"Factores Resistencia I: DC={row.dc_factor:.2f}, DW={row.dw_factor:.2f}, "
            f"PL={row.pl_factor:.2f}, LL+IM={row.ll_im_factor:.2f}. "
            f"Av/s minimo={shear.minimum_av_cm2_m:.3f} cm2/m; phi={shear.phi:.2f}."
        ),
        ]
    )
    lines.extend(_format_shear_option_table(shear.options))
    return lines


def _format_shear_section_limit(shear: InteriorGirderShearDesign) -> str:
    vu = shear.controlling_shear.combined_shear_tn
    nominal_limit = shear.nominal_shear_limit_tn
    factored_limit = shear.phi * nominal_limit
    status = "OK" if factored_limit + 1e-9 >= vu else "NO CUMPLE"
    return (
        f"Limite de la seccion: Vn,max={nominal_limit:.3f} Tn; "
        f"phiVn,max={factored_limit:.3f} Tn; Vu={vu:.3f} Tn; Estado={status}."
    )


def _format_shear_option_table(options) -> list[str]:
    rows = []
    for option in options:
        state = "OK" if option.is_compliant else "NO"
        use = "REC" if option.is_recommended else ""
        rows.append(
            (
                option.item,
                f"{option.legs}r {option.bar_label}",
                f"{option.spacing_m:.3f}",
                f"{option.provided_av_cm2_m:.3f}",
                f"{option.phi_vn_tn:.3f}",
                f"{option.excess_percent:.1f}%",
                state,
                use,
            )
        )
    return boxed_table(
        ("Item", "Estribo", "s (m)", "Av/s prov", "phiVn", "Exceso", "Estado", "Uso"),
        rows,
        aligns=("right", "right", "right", "right", "right", "right", "center", "center"),
        title="Opciones de estribos por corte",
    )


def _format_exterior_crack_control_review_lines(
    crack_review: InteriorGirderCrackControlReview,
) -> list[str]:
    lines = [
        *audit_subtitle("", "REVISION DE FISURACION - VIGA PRINCIPAL EXTERIOR", 104),
        "Criterio: s prov <= s max, evaluado con Servicio I y acero principal recomendado/seleccionado.",
    ]
    lines.extend(_format_crack_control_table((crack_review.main,)))
    return lines


def _format_exterior_fatigue_review_lines(
    review: InteriorGirderFatigueReview,
) -> list[str]:
    cracked = "SI" if review.section.is_cracked else "NO"
    lines = [
        *audit_subtitle("", "REVISION DE FATIGA - VIGA PRINCIPAL EXTERIOR", 104),
        "Carga de fatiga: camion de diseno, separacion trasera fija de 30 ft, IM=15%, sin carga de carril ni presencia multiple.",
    ]
    lines.extend(_format_fatigue_review_table(review, cracked))
    lines.append(
        "Esfuerzos en kg/cm2. M fat incluye gFat e IM=15%; Fatiga I aplica factor 1.50 al rango.",
    )
    return lines


def _format_exterior_stress_verification_lines(
    verification: InteriorGirderStressVerification,
) -> list[str]:
    lines = [*audit_subtitle("", "VERIFICACION DE ESFUERZOS - SERVICIO I - VIGA PRINCIPAL EXTERIOR", 104)]
    lines.extend(_format_stress_verification_table(verification))
    lines.append(f"Concreto: {verification.concrete_status}. Acero: {verification.steel_status}.")
    return lines


def _format_crack_control_review_lines(
    crack_review: SlabCrackControlReview,
) -> list[str]:
    lines = [
        *audit_subtitle("E", "REVISION DE FISURACION POR DISTRIBUCION DE ARMADURA", 104),
        "Criterios: fs real <= 0.60fy y s prov <= s max, ambos evaluados con Servicio I.",
    ]
    lines.extend(_format_crack_control_table((crack_review.negative_main, crack_review.positive_main)))
    return lines


def _format_crack_control_row(row: CrackControlCheck) -> str:
    return _format_crack_control_cells(row)


def _format_crack_control_cells(row: CrackControlCheck) -> tuple[str, ...]:
    return (
        row.label[:32],
        row.bar_label,
        f"{row.provided_spacing_m:.3f}",
        f"{row.maximum_spacing_m:.3f}",
        f"{row.service_moment_tn_m:.3f}",
        f"{row.steel_stress_kg_cm2:.0f}",
        f"{row.steel_stress_limit_kg_cm2:.0f}",
        f"{row.steel_stress_used_kg_cm2:.0f}",
        f"{row.beta_s:.3f}",
        f"{row.dc_cm:.2f}",
        row.stress_status,
        row.spacing_status,
        row.status,
    )


def _format_crack_control_table(rows: tuple[CrackControlCheck, ...]) -> list[str]:
    return boxed_table(
        (
            "Item", "Diam", "s prov", "s max", "Ms", "fs", "fs lim",
            "fs uso", "beta", "dc", "E-fs", "E-s", "Estado",
        ),
        (_format_crack_control_cells(row) for row in rows),
        aligns=(
            "left", "right", "right", "right", "right", "right", "right",
            "right", "right", "right", "center", "center", "center",
        ),
        title="Tabla de control de fisuracion",
    )


def _format_fatigue_review_table(
    review: InteriorGirderFatigueReview,
    cracked: str,
) -> list[str]:
    return boxed_table(
        ("x fat", "M fat", "M perm", "fis?", "f bot", "f lim", "fmin", "Df*1.5", "Df adm", "Estado"),
        (
            (
                f"{review.fatigue_position_m:.3f}",
                f"{review.fatigue_moment_tn_m:.3f}",
                f"{review.permanent_moment_tn_m:.3f}",
                cracked,
                f"{review.section.bottom_tension_kg_cm2:.1f}",
                f"{review.section.cracking_threshold_kg_cm2:.1f}",
                f"{review.minimum_stress_kg_cm2:.0f}",
                f"{review.factored_stress_range_kg_cm2:.0f}",
                f"{review.allowable_stress_range_kg_cm2:.0f}",
                review.status,
            ),
        ),
        aligns=("right", "right", "right", "center", "right", "right", "right", "right", "right", "center"),
        title="Tabla de fatiga",
    )


def _format_stress_verification_table(
    verification: InteriorGirderStressVerification,
) -> list[str]:
    return boxed_table(
        ("x", "Ms", "y NA", "Icr", "fc", "fc adm", "fs", "fs adm"),
        (
            (
                f"{verification.position_m:.3f}",
                f"{verification.service_moment_tn_m:.3f}",
                f"{verification.section.neutral_axis_depth_cm:.2f}",
                f"{verification.section.inertia_cm4:.0f}",
                f"{verification.concrete_compression_kg_cm2:.1f}",
                f"{verification.concrete_compression_limit_kg_cm2:.1f}",
                f"{verification.steel_tension_kg_cm2:.0f}",
                f"{verification.steel_tension_limit_kg_cm2:.0f}",
            ),
        ),
        aligns=("right",) * 8,
        title="Tabla de esfuerzos de servicio",
    )


def _format_vehicle_control(case: LoadCaseAnalysis) -> str:
    if case.critical_vehicle_position_m is None:
        return f"{case.name}: no aplica."
    multiple_presence = (
        f"; m={case.multiple_presence_factor:.2f}"
        if case.multiple_presence_factor is not None
        else ""
    )
    return (
        f"{case.name}: posicion izquierda critica = "
        f"{case.critical_vehicle_position_m:.3f} m; "
        f"{case.vehicle_configuration}{multiple_presence}."
    )


def _format_reactions(label: str, case: LoadCaseAnalysis) -> str:
    reactions = ", ".join(
        f"x={position:.3f}: {reaction:.3f}"
        for position, reaction in case.support_reactions_tn
    )
    return f"{label}: {reactions}"


from bridge_design.cli.bearing_output import format_elastomeric_bearing_result
