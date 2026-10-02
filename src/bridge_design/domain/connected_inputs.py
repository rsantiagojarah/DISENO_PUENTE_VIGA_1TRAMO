"""Editable two-abutment inputs, retaining the existing seat geometry and materials."""

from dataclasses import asdict, dataclass, field
from math import isfinite

from bridge_design.domain.abutment import AbutmentInputs, AbutmentKeyInputs, AbutmentLoadInputs, AbutmentMaterialInputs
from bridge_design.domain.connected_defaults import (
    REFERENCE_CLEAR_SPAN_M, REFERENCE_SLAB_THICKNESS_M, REFERENCE_TRANSITION_M,
    connected_geometry_defaults, connected_load_defaults,
)


def default_connected_side():
    return AbutmentInputs(geometry=connected_geometry_defaults(), loads=connected_load_defaults(),
                          key=AbutmentKeyInputs(enabled=False))


def positive(value, label, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{label} debe ser numerico y finito.")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{label} debe ser {'no negativo' if allow_zero else 'positivo'}.")


@dataclass(frozen=True)
class FoundationSoil:
    subgrade_tn_m3: float
    friction_coefficient: float
    allowable_tn_m2: float
    nominal_bearing_fs: float = 3.0
    sliding_phi: float = 0.80
    extreme_sliding_phi: float = 1.0

    def __post_init__(self):
        for name, value in self.__dict__.items():
            positive(value, name, allow_zero=name == "friction_coefficient")
        for value in (self.sliding_phi, self.extreme_sliding_phi):
            if value > 1:
                raise ValueError("Los factores de resistencia no deben superar 1.")
        if self.nominal_bearing_fs < 1:
            raise ValueError("FS para capacidad nominal debe ser >= 1.")


@dataclass(frozen=True)
class PairedBridgeCase:
    name: str
    left: AbutmentLoadInputs
    right: AbutmentLoadInputs
    left_surcharge: float = 1.0
    right_surcharge: float = 1.0
    bridge_present: bool = True

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("Cada par simultaneo de cargas necesita un nombre.")
        positive(self.left_surcharge, "Sobrecarga izquierda", True)
        positive(self.right_surcharge, "Sobrecarga derecha", True)
        if not self.bridge_present and any(value != 0 for loads in (self.left, self.right)
                                           for value in loads.__dict__.values()):
            raise ValueError("Un caso sin tablero debe tener sus cargas de tablero en cero.")


@dataclass(frozen=True)
class ConnectedInputs:
    soil: FoundationSoil
    left: AbutmentInputs = field(default_factory=default_connected_side)
    right: AbutmentInputs = field(default_factory=default_connected_side)
    clear_span_m: float = REFERENCE_CLEAR_SPAN_M
    slab_thickness_m: float = REFERENCE_SLAB_THICKNESS_M
    left_transition_m: float = REFERENCE_TRANSITION_M
    right_transition_m: float = REFERENCE_TRANSITION_M
    mesh_size_m: float = 0.50
    section_offsets: bool = False
    reference_x_m: float | None = None
    slab_materials: AbutmentMaterialInputs = field(default_factory=AbutmentMaterialInputs)
    slab_cover_cm: float = 7.5
    cases: tuple[PairedBridgeCase, ...] = ()
    include_without_bridge: bool = True
    anchor_lengths_m: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        def finite_values(value, label):
            if isinstance(value, dict):
                for key, item in value.items():
                    finite_values(item, f"{label}.{key}")
            elif isinstance(value, (list, tuple)):
                for item in value:
                    finite_values(item, label)
            elif isinstance(value, float) and not isfinite(value):
                raise ValueError(f"{label} debe ser finito.")

        finite_values(asdict(self), "Entradas")
        for name in ("clear_span_m", "slab_thickness_m", "mesh_size_m", "slab_cover_cm"):
            positive(getattr(self, name), name)
        positive(self.left_transition_m, "Transicion izquierda", True)
        positive(self.right_transition_m, "Transicion derecha", True)
        if not isinstance(self.section_offsets, bool) or not isinstance(self.include_without_bridge, bool):
            raise ValueError("Offsets y casos sin tablero deben ser booleanos.")
        if self.connector_length_m <= self.left_transition_m + self.right_transition_m + 1e-6:
            raise ValueError("La separacion libre debe superar punteras y transiciones; falta losa central.")
        if self.reference_x_m is not None:
            positive(self.reference_x_m, "x del nodo Ux=0", True)
            if self.reference_x_m > self.total_length_m:
                raise ValueError("El nodo de referencia debe estar dentro de la cimentacion.")
        if self.mesh_size_m < 0.05:
            raise ValueError("El paso de malla debe ser >= 0.05 m.")
        if 2 * self.slab_cover_cm >= 100 * self.slab_thickness_m:
            raise ValueError("Recubrimiento incompatible con el espesor de losa.")
        if self.left.gamma_eq != self.right.gamma_eq:
            raise ValueError("gamma_EQ debe ser comun al sistema.")
        if self.left.soil.pga != self.right.soil.pga or self.left.soil.fpga != self.right.soil.fpga:
            raise ValueError("PGA y Fpga deben corresponder a un mismo evento sismico en ambos lados.")
        for side in (self.left, self.right):
            if side.is_pure_wall or side.key.enabled:
                raise ValueError("Esta modalidad usa estribos con cajuela, sin dentellon.")
            geometry = side.geometry
            seating = geometry.bearing_seat_length_m + geometry.seat_wall_width_m
            shoulders = geometry.upper_stem_thickness_m + geometry.small_batter_width_m + geometry.backfill_step_width_m
            if abs(seating - shoulders) > 1e-6:
                raise ValueError("Geometria de cajuela: longitud apoyo + parapeto debe igualar es + t1 + t2.")
            if geometry.seat_wall_width_m <= 0 or geometry.seat_block_height_m <= 0:
                raise ValueError("La cajuela requiere parapeto de espesor y altura positivos.")
            if geometry.stem_height_above_footing_m <= (
                geometry.seat_block_height_m + geometry.backwall_drop_m + geometry.backwall_taper_height_m
            ):
                raise ValueError("Debe existir pantalla bajo la transicion de cajuela.")
            if geometry.front_soil_depth_m > geometry.retained_height_m:
                raise ValueError("El relleno frontal no puede superar la altura del estribo.")
            straight_height = geometry.stem_height_above_footing_m - geometry.seat_block_height_m - geometry.backwall_drop_m - geometry.backwall_taper_height_m
            if geometry.front_soil_depth_m - geometry.footing_thickness_m > straight_height:
                raise ValueError("El relleno frontal debe quedar por debajo de la transicion de cajuela.")
            for value in (side.reinforcement.stem_cover_cm, side.reinforcement.footing_cover_cm,
                          side.reinforcement.spacing_step_m, side.reinforcement.minimum_spacing_m,
                          side.reinforcement.maximum_spacing_m):
                positive(value, "Recubrimientos y separaciones")
            if 2 * side.reinforcement.stem_cover_cm >= 100 * geometry.seat_wall_width_m:
                raise ValueError("El parapeto no admite los recubrimientos ingresados.")
            if 2 * side.reinforcement.footing_cover_cm >= 100 * geometry.footing_thickness_m:
                raise ValueError("La zapata no admite los recubrimientos ingresados.")
            if side.reinforcement.minimum_spacing_m > min(0.30, side.reinforcement.maximum_spacing_m):
                raise ValueError("Separaciones incompatibles: minimo > maximo permitido.")
            if self.slab_thickness_m > geometry.footing_thickness_m:
                raise ValueError("La losa central no debe ser mas gruesa que las zapatas.")
        names = [case.name for case in self.cases]
        if len(names) != len(set(names)):
            raise ValueError("Los nombres de casos simultaneos deben ser unicos.")
        for region, length in self.anchor_lengths_m.items():
            positive(length, f"Longitud de anclaje {region}", True)

    @property
    def connector_length_m(self):
        return self.clear_span_m - self.left.geometry.toe_length_m - self.right.geometry.toe_length_m

    @property
    def total_length_m(self):
        return self.left.geometry.footing_width_m + self.connector_length_m + self.right.geometry.footing_width_m

    @property
    def reference_position_m(self):
        return self.total_length_m / 2 if self.reference_x_m is None else self.reference_x_m
