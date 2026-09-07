"""Live load input models."""

from dataclasses import dataclass
from typing import Tuple

from bridge_design.codes.mtc_2018 import (
    DEFAULT_LANE_LOAD_WIDTH_M,
    PEDESTRIAN_SIDEWALK_REFERENCE,
    default_hl93_vehicle_load_data,
    default_sidewalk_pedestrian_load_tn_m2,
)
from bridge_design.validation.input_validators import require_positive


@dataclass(frozen=True)
class VehicleLoadModel:
    """Default vehicular live load model."""

    name: str
    design_truck_axles_tn: Tuple[float, float, float]
    design_truck_spacings_m: Tuple[float, Tuple[float, float]]
    design_tandem_axles_tn: Tuple[float, float]
    design_tandem_spacing_m: float
    lane_load_tn_m: float
    design_lane_width_m: float
    wheel_transverse_spacing_m: float
    tire_contact_width_m: float
    tire_contact_length_m: float
    reference: str

    lane_load_width_m: float = DEFAULT_LANE_LOAD_WIDTH_M

    @classmethod
    def mtc_hl93_default(cls) -> "VehicleLoadModel":
        """Create the default HL-93 vehicular live load from MTC 2018."""
        data = default_hl93_vehicle_load_data()
        return cls(
            name=str(data["name"]),
            design_truck_axles_tn=tuple(data["design_truck_axles_tn"]),
            design_truck_spacings_m=tuple(data["design_truck_spacings_m"]),
            design_tandem_axles_tn=tuple(data["design_tandem_axles_tn"]),
            design_tandem_spacing_m=float(data["design_tandem_spacing_m"]),
            lane_load_tn_m=float(data["lane_load_tn_m"]),
            design_lane_width_m=float(data["design_lane_width_m"]),
            lane_load_width_m=float(data["lane_load_width_m"]),
            wheel_transverse_spacing_m=float(data["wheel_transverse_spacing_m"]),
            tire_contact_width_m=float(data["tire_contact_width_m"]),
            tire_contact_length_m=float(data["tire_contact_length_m"]),
            reference=str(data["reference"]),
        )


@dataclass(frozen=True)
class PedestrianLoad:
    """Pedestrian live load PL."""

    load_tn_m2: float
    reference: str = PEDESTRIAN_SIDEWALK_REFERENCE

    def __post_init__(self) -> None:
        require_positive(self.load_tn_m2, "PL")

    @classmethod
    def mtc_sidewalk_default(cls) -> "PedestrianLoad":
        """Create the MTC sidewalk pedestrian load default."""
        return cls(load_tn_m2=default_sidewalk_pedestrian_load_tn_m2())


@dataclass(frozen=True)
class LiveLoads:
    """Complete live load input set."""

    pedestrian: PedestrianLoad
    vehicular: VehicleLoadModel
