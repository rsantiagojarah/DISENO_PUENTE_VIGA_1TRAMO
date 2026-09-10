"""Terminal prompts for project input data."""

from dataclasses import replace

from bridge_design.domain.barrier import (
    BarrierDesignInputs,
    BarrierGeometry,
    BarrierImpactLoad,
    BarrierSectionModel,
)
from bridge_design.domain.diaphragm import (
    DiaphragmBeamGeometry,
    diaphragm_geometry_from_transverse,
)
from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel
from bridge_design.domain.exterior_girder import (
    ExteriorGirderGeometry,
    exterior_asphalt_tributary_width_m,
)
from bridge_design.domain.interior_girder import (
    DiaphragmGeometry,
    InteriorGirderGeometry,
)
from bridge_design.domain.materials import (
    ConcreteProperties,
    LinearWeightProperties,
    MaterialProperties,
    SteelProperties,
    SurfaceLayerProperties,
)
from bridge_design.domain.project_inputs import ProjectInputs
from bridge_design.domain.transverse_slab import (
    TransverseLoadLayout,
    TransverseSlabDesignInputs,
    TransverseSlabGeometry,
    format_transverse_scheme,
    validate_layout_inside_geometry,
)


def prompt_float(label: str, unit: str, default: float | None = None) -> float:
    """Prompt a positive numeric value from terminal."""
    suffix = f" [{default:g}]" if default is not None else ""
    while True:
        raw_value = input(f"{label} ({unit}){suffix}: ").strip()
        if not raw_value and default is not None:
            return default
        try:
            value = float(raw_value)
        except ValueError:
            print("Ingrese un numero valido.")
            continue
        if value <= 0:
            print("El valor debe ser mayor que cero.")
            continue
        return value


def prompt_non_negative_float(label: str, unit: str, default: float | None = None) -> float:
    """Prompt a numeric value greater than or equal to zero from terminal."""
    suffix = f" [{default:g}]" if default is not None else ""
    while True:
        raw_value = input(f"{label} ({unit}){suffix}: ").strip()
        if not raw_value and default is not None:
            return default
        try:
            value = float(raw_value)
        except ValueError:
            print("Ingrese un numero valido.")
            continue
        if value < 0:
            print("El valor no debe ser negativo.")
            continue
        return value


def prompt_int(label: str, default: int | None = None, minimum: int = 1) -> int:
    """Prompt an integer value from terminal."""
    suffix = f" [{default:d}]" if default is not None else ""
    while True:
        raw_value = input(f"{label}{suffix}: ").strip()
        if not raw_value and default is not None:
            return default
        try:
            value = int(raw_value)
        except ValueError:
            print("Ingrese un numero entero valido.")
            continue
        if value < minimum:
            print(f"El valor debe ser al menos {minimum}.")
            continue
        return value


def prompt_interval(
    label: str,
    width_m: float,
    default_start: float,
    default_end: float,
) -> tuple[float, float]:
    """Prompt a left-to-right interval inside the deck."""
    while True:
        start = prompt_non_negative_float(f"{label} - punto inicial desde la izquierda", "m", default_start)
        end = prompt_float(f"{label} - punto final desde la izquierda", "m", default_end)
        if start >= end:
            print("El punto final debe ser mayor que el punto inicial.")
            continue
        if end > width_m:
            print(f"El punto final debe estar dentro del tablero ({width_m:.3f} m).")
            continue
        return start, end


def collect_transverse_geometry() -> TransverseSlabGeometry:
    """Collect transverse slab geometry and print the structural scheme."""
    print("=" * 60)
    print("MODELO TRANSVERSAL DE LOSA ENTRE VIGAS")
    print("=" * 60)

    geometry = TransverseSlabGeometry(
        girder_spacing_m=prompt_float("S - Separacion entre vigas", "m", 2.10),
        overhang_m=prompt_non_negative_float("a - Volado de losa", "m", 0.825),
        girder_count=prompt_int("Numero de vigas/apoyos articulados", 4, minimum=2),
        slab_thickness_m=prompt_float("Espesor de losa", "m", 0.20),
        girder_total_height_m=prompt_float("Altura total de la viga", "m", 1.20),
        girder_width_m=prompt_float("Ancho de cada viga", "m", 0.30),
    )
    print()
    print(format_transverse_scheme(geometry))
    return geometry


def collect_material_properties() -> MaterialProperties:
    """Collect material properties from terminal."""
    print("=" * 60)
    print("INGRESO DE PROPIEDADES DE MATERIALES")
    print("=" * 60)

    concrete = ConcreteProperties.from_inputs(
        specific_weight_tn_m3=prompt_float("Pec - Peso especifico del concreto", "Tn/m3", 2.4),
        compressive_strength_kg_cm2=prompt_float("f'c - Resistencia a compresion", "kg/cm2", 280.0),
    )

    steel = SteelProperties(
        yield_strength_kg_cm2=4200.0,
        elastic_modulus_kg_cm2=2000000.0,
        specification="ASTM A615 Grado 60",
    )
    print("Especificacion del acero de refuerzo [ASTM A615 Grado 60]: ASTM A615 Grado 60")
    print("fy - Esfuerzo de fluencia del acero (kg/cm2) [4200]: 4200")
    print("Es - Modulo de elasticidad del acero (kg/cm2) [2000000]: 2000000")

    asphalt = SurfaceLayerProperties(
        name="asfalto",
        specific_weight_tn_m3=prompt_float("Pea - Peso especifico del asfalto", "Tn/m3", 2.2),
        thickness_m=prompt_float("Espesor del asfalto", "m", 0.05),
    )
    sidewalk = SurfaceLayerProperties(
        name="vereda",
        specific_weight_tn_m3=prompt_float("Pev - Peso especifico de la vereda", "Tn/m3", 2.4),
        thickness_m=prompt_float("Espesor de la vereda", "m", 0.20),
    )
    railing = LinearWeightProperties(
        name="baranda",
        weight_kg_m=prompt_float("Peso lineal de la baranda", "kg/m", 100.0),
    )
    barrier = LinearWeightProperties(
        name="barrera",
        weight_kg_m=prompt_float("Peso lineal de la barrera", "kg/m", 500.0),
    )

    return MaterialProperties(
        concrete=concrete,
        steel=steel,
        asphalt=asphalt,
        sidewalk=sidewalk,
        railing=railing,
        barrier=barrier,
    )


def collect_live_loads() -> LiveLoads:
    """Collect live loads from terminal."""
    print()
    print("=" * 60)
    print("INGRESO DE CARGAS VIVAS")
    print("=" * 60)

    default_pl = PedestrianLoad.mtc_sidewalk_default().load_tn_m2
    pedestrian = PedestrianLoad(
        load_tn_m2=prompt_float("PL - Carga peatonal sobre veredas", "Tn/m2", default_pl),
    )
    vehicular = VehicleLoadModel.mtc_hl93_default()
    print("Carga vehicular: HL-93 por defecto segun Manual de Puentes MTC 2018.")

    return LiveLoads(pedestrian=pedestrian, vehicular=vehicular)


def collect_concrete_barrier_design_inputs() -> BarrierDesignInputs:
    """Collect concrete traffic barrier design inputs using the project NJ profile."""
    print()
    print("=" * 60)
    print("DISENO DE BARRERA DE CONCRETO TIPO NEW JERSEY")
    print("=" * 60)
    print("Modelo base: seccion de la imagen, 7 barras 3/8 in y dowel 1/2 in.")
    geometry = BarrierGeometry(
        height_m=prompt_float("H - Altura total de barrera", "m", 0.85),
        base_width_m=prompt_float("Ancho de base en contacto con losa", "m", 0.375),
        cross_section_area_m2=prompt_float("Area de seccion de barrera", "m2", 0.202875),
        available_development_length_cm=prompt_float(
            "Longitud disponible de anclaje recto en losa",
            "cm",
            17.5,
        ),
        top_additional_moment_tn_m=prompt_non_negative_float(
            "Mb - Momento adicional en la parte superior",
            "Tn*m",
            0.0,
        ),
    )
    impact = BarrierImpactLoad(
        test_level=input("Nivel de ensayo de barrera [TL-4]: ").strip() or "TL-4",
        transverse_force_tn=prompt_float("Ft - Fuerza transversal de impacto", "Tn", 24.47),
        distribution_length_m=prompt_float("Lt - Longitud de distribucion longitudinal", "m", 1.07),
        pattern=_prompt_barrier_impact_pattern(),
    )
    section_model = BarrierSectionModel.new_jersey_image_default()
    dowel_spacing = prompt_float("Separacion de dowel 1/2 in", "m", section_model.dowel_spacing_m)
    section_model = replace(section_model, dowel_spacing_m=dowel_spacing)
    return BarrierDesignInputs(
        geometry=geometry,
        section_model=section_model,
        impact_load=impact,
    )


def _prompt_barrier_impact_pattern():
    """Prompt yield-line impact pattern."""
    while True:
        raw_value = input("Patron de impacto: segmento interior o extremo/junta [segmento]: ").strip().lower()
        if not raw_value or raw_value in ("segmento", "interior", "segment", "s"):
            return "segment"
        if raw_value in ("extremo", "junta", "end", "e"):
            return "end"
        print("Ingrese 'segmento' o 'extremo'.")


def collect_transverse_load_layout(geometry: TransverseSlabGeometry) -> TransverseLoadLayout:
    """Collect load positions for the transverse slab model."""
    print()
    print("=" * 60)
    print("UBICACION DE CARGAS EN EL MODELO TRANSVERSAL")
    print("=" * 60)
    width = geometry.total_width_m
    print(f"Ancho total de tablero: {width:.3f} m")
    print("La carga de peso propio de losa se aplica automaticamente en todo el tablero.")

    sidewalk_width = prompt_float("Ancho de vereda en cada lado", "m", geometry.overhang_m)
    barrier_width = prompt_float("Ancho de barrera New Jersey", "m", 0.25)
    barrier_left = prompt_non_negative_float(
        "Ubicacion de cara cercana de barrera izquierda desde la izquierda",
        "m",
        sidewalk_width,
    )
    asphalt_start, asphalt_end = prompt_interval(
        "Asfalto DW",
        width,
        barrier_left + barrier_width,
        width - barrier_left - barrier_width,
    )
    railing_left = prompt_non_negative_float(
        "Ubicacion de baranda izquierda desde la izquierda (borde exterior de vereda)",
        "m",
        0.13,
    )
    layout = TransverseLoadLayout(
        asphalt_start_m=asphalt_start,
        asphalt_end_m=asphalt_end,
        sidewalk_width_m=sidewalk_width,
        railing_left_m=railing_left,
        barrier_left_m=barrier_left,
        barrier_width_m=barrier_width,
        vehicle_move_start_m=prompt_non_negative_float(
            "Cara interna izquierda para recorrido vehicular",
            "m",
            barrier_left + barrier_width,
        ),
        vehicle_move_end_m=prompt_float(
            "Cara interna derecha para recorrido vehicular",
            "m",
            width - barrier_left - barrier_width,
        ),
        vehicle_step_m=prompt_float("Paso de movimiento vehicular", "m", 0.10),
    )
    validate_layout_inside_geometry(geometry, layout)
    return layout


def collect_interior_girder_geometry(
    transverse_geometry: TransverseSlabGeometry,
) -> InteriorGirderGeometry:
    """Collect interior girder longitudinal geometry and diaphragm data."""
    print()
    print("=" * 60)
    print("VIGA PRINCIPAL INTERIOR - MODELO LONGITUDINAL")
    print("=" * 60)
    print("Apoyo izquierdo: fijo. Apoyo derecho: movil. Ambos son apoyos simples verticales.")
    span_length = prompt_float("Luz del puente", "m", 15.0)
    diaphragm_count = prompt_int("Numero de diafragmas interiores", 3, minimum=0)
    diaphragms: list[DiaphragmGeometry] = []
    default_positions = _default_diaphragm_positions(span_length, diaphragm_count)
    for index in range(diaphragm_count):
        print(f"Diafragma {index + 1}")
        diaphragms.append(
            DiaphragmGeometry(
                position_m=prompt_non_negative_float(
                    "  Ubicacion desde apoyo fijo",
                    "m",
                    default_positions[index],
                ),
                thickness_m=prompt_float("  Espesor longitudinal", "m", 0.25),
                height_m=prompt_float(
                    "  Altura de concreto bajo la losa",
                    "m",
                    max(transverse_geometry.girder_total_height_m - 0.10, 0.10),
                ),
                tributary_width_m=prompt_float(
                    "  Ancho tributario transversal",
                    "m",
                    transverse_geometry.girder_spacing_m,
                ),
            )
        )
    geometry = InteriorGirderGeometry(
        span_length_m=span_length,
        girder_spacing_m=transverse_geometry.girder_spacing_m,
        slab_thickness_m=transverse_geometry.slab_thickness_m,
        girder_total_height_m=transverse_geometry.girder_total_height_m,
        web_width_m=transverse_geometry.girder_width_m,
        girder_count=transverse_geometry.girder_count,
        diaphragms=tuple(diaphragms),
        moving_load_step_m=prompt_float("Paso de movimiento longitudinal de carga viva", "m", 0.10),
        moment_sample_step_m=prompt_float("Paso de muestreo de momentos longitudinales", "m", 0.10),
    )
    print(
        "g - Factor de distribucion de carga viva calculado "
        f"(MTC 2018 2.6.4.2.2.2b): {geometry.live_load_distribution_factor_g:.3f}"
    )
    return geometry


def collect_exterior_girder_geometry(
    transverse_geometry: TransverseSlabGeometry,
    layout: TransverseLoadLayout,
    live_loads: LiveLoads,
    interior_girder: InteriorGirderGeometry,
) -> ExteriorGirderGeometry:
    """Create exterior girder geometry from transverse data and exterior de."""
    print()
    print("=" * 60)
    print("VIGA PRINCIPAL EXTERIOR - MODELO LONGITUDINAL")
    print("=" * 60)
    default_de = _default_exterior_de_m(transverse_geometry, layout)
    de = _prompt_signed_float(
        "de - distancia del eje/alma exterior a la cara interior de barrera de trafico",
        "m",
        default_de,
    )
    exterior_tributary_width = transverse_geometry.overhang_m + transverse_geometry.girder_spacing_m / 2.0
    diaphragms = tuple(
        DiaphragmGeometry(
            position_m=diaphragm.position_m,
            thickness_m=diaphragm.thickness_m,
            height_m=diaphragm.height_m,
            tributary_width_m=exterior_tributary_width,
        )
        for diaphragm in interior_girder.diaphragms
    )
    geometry = ExteriorGirderGeometry(
        span_length_m=interior_girder.span_length_m,
        girder_spacing_m=transverse_geometry.girder_spacing_m,
        deck_overhang_m=transverse_geometry.overhang_m,
        slab_thickness_m=transverse_geometry.slab_thickness_m,
        girder_total_height_m=transverse_geometry.girder_total_height_m,
        web_width_m=transverse_geometry.girder_width_m,
        exterior_web_to_traffic_barrier_m=de,
        sidewalk_width_m=layout.sidewalk_width_m,
        asphalt_tributary_width_m=exterior_asphalt_tributary_width_m(
            deck_overhang_m=transverse_geometry.overhang_m,
            girder_spacing_m=transverse_geometry.girder_spacing_m,
            asphalt_start_m=layout.asphalt_start_m,
            asphalt_end_m=layout.asphalt_end_m,
        ),
        girder_count=transverse_geometry.girder_count,
        diaphragms=diaphragms,
        moving_load_step_m=interior_girder.moving_load_step_m,
        moment_sample_step_m=interior_girder.moment_sample_step_m,
    ).with_distribution_factors(live_loads.vehicular)
    print(
        "g exterior calculado (MTC 2018 2.6.4.2.2.2d/2.6.4.2.2.3b): "
        f"momento={geometry.live_load_distribution_factor_g:.3f}, "
        f"corte={geometry.live_load_shear_distribution_factor_g:.3f}"
    )
    return geometry


def collect_diaphragm_beam_geometry(
    transverse_geometry: TransverseSlabGeometry,
    interior_girder: InteriorGirderGeometry,
) -> DiaphragmBeamGeometry:
    """Collect diaphragm transverse-beam design inputs."""
    print()
    print("=" * 60)
    print("VIGA DIAFRAGMA - MODELO TRANSVERSAL")
    print("=" * 60)
    reference = interior_girder.diaphragms[0] if interior_girder.diaphragms else None
    default_thickness = reference.thickness_m if reference is not None else 0.25
    default_height = (
        reference.height_m
        if reference is not None
        else max(transverse_geometry.girder_total_height_m - 0.10, 0.10)
    )
    thickness = prompt_float("Espesor longitudinal del diafragma", "m", default_thickness)
    height = prompt_float("Altura del diafragma bajo la losa", "m", default_height)
    tributary = prompt_float(
        "Longitud tributaria longitudinal para cargas sobre diafragma",
        "m",
        thickness,
    )
    geometry = diaphragm_geometry_from_transverse(
        transverse=transverse_geometry,
        thickness_m=thickness,
        height_m=height,
        load_tributary_length_m=tributary,
    )
    print(
        "Longitud de distribucion longitudinal de rueda adoptada: "
        f"{geometry.wheel_distribution_length_m:.3f} m."
    )
    return geometry


def _default_diaphragm_positions(span_length_m: float, count: int) -> tuple[float, ...]:
    if count <= 0:
        return ()
    return tuple(span_length_m * (index + 1) / (count + 1) for index in range(count))


def _prompt_signed_float(label: str, unit: str, default: float) -> float:
    suffix = f" [{default:g}]"
    while True:
        raw_value = input(f"{label} ({unit}){suffix}: ").strip()
        if not raw_value:
            return default
        try:
            return float(raw_value)
        except ValueError:
            print("Ingrese un numero valido.")


def _default_exterior_de_m(
    transverse_geometry: TransverseSlabGeometry,
    layout: TransverseLoadLayout,
) -> float:
    """Return MTC/AASHTO de using the traffic-side barrier face.

    For the left exterior girder, x grows from the exterior edge toward the
    bridge interior. Therefore de = x_web - x_traffic_face: positive when the
    exterior web is inboard of the traffic-side barrier face, negative when it
    is outboard.
    """
    exterior_web_x_m = transverse_geometry.overhang_m
    traffic_face_x_m = layout.barrier_left_m + layout.barrier_width_m
    return exterior_web_x_m - traffic_face_x_m


def collect_project_inputs() -> ProjectInputs:
    """Collect all project inputs from terminal."""
    geometry = collect_transverse_geometry()
    materials = collect_material_properties()
    barrier = collect_concrete_barrier_design_inputs()
    live_loads = collect_live_loads()
    load_layout = collect_transverse_load_layout(geometry)
    interior_girder = collect_interior_girder_geometry(geometry)
    exterior_girder = collect_exterior_girder_geometry(
        geometry,
        load_layout,
        live_loads,
        interior_girder,
    )
    diaphragm = collect_diaphragm_beam_geometry(geometry, interior_girder)
    transverse_slab = TransverseSlabDesignInputs(
        geometry=geometry,
        load_layout=load_layout,
    )
    return ProjectInputs(
        materials=materials,
        live_loads=live_loads,
        barrier=barrier,
        transverse_slab=transverse_slab,
        interior_girder=interior_girder,
        exterior_girder=exterior_girder,
        diaphragm=diaphragm,
    )
