"""Material input models."""

from dataclasses import dataclass

from bridge_design.codes.mtc_2018 import (
    CONCRETE_EC_REFERENCE,
    STEEL_REFERENCE,
    calculate_concrete_elastic_modulus_kg_cm2,
)
from bridge_design.validation.input_validators import require_positive


@dataclass(frozen=True)
class ConcreteProperties:
    """Concrete material properties in project units."""

    specific_weight_tn_m3: float
    compressive_strength_kg_cm2: float
    elastic_modulus_kg_cm2: float
    aggregate_correction_factor: float = 1.0
    reference: str = CONCRETE_EC_REFERENCE

    @classmethod
    def from_inputs(
        cls,
        specific_weight_tn_m3: float,
        compressive_strength_kg_cm2: float,
        aggregate_correction_factor: float = 1.0,
    ) -> "ConcreteProperties":
        """Create concrete properties and calculate Ec automatically."""
        elastic_modulus = calculate_concrete_elastic_modulus_kg_cm2(
            specific_weight_tn_m3=specific_weight_tn_m3,
            compressive_strength_kg_cm2=compressive_strength_kg_cm2,
            aggregate_correction_factor=aggregate_correction_factor,
        )
        return cls(
            specific_weight_tn_m3=specific_weight_tn_m3,
            compressive_strength_kg_cm2=compressive_strength_kg_cm2,
            elastic_modulus_kg_cm2=elastic_modulus,
            aggregate_correction_factor=aggregate_correction_factor,
        )


@dataclass(frozen=True)
class SteelProperties:
    """Reinforcing steel properties in project units."""

    yield_strength_kg_cm2: float = 4200.0
    elastic_modulus_kg_cm2: float = 2000000.0
    reference: str = STEEL_REFERENCE

    def __post_init__(self) -> None:
        require_positive(self.yield_strength_kg_cm2, "fy")
        require_positive(self.elastic_modulus_kg_cm2, "Es")


@dataclass(frozen=True)
class SurfaceLayerProperties:
    """Surface layer properties used for dead load inputs."""

    name: str
    specific_weight_tn_m3: float
    thickness_m: float

    def __post_init__(self) -> None:
        require_positive(self.specific_weight_tn_m3, f"Pe {self.name}")
        require_positive(self.thickness_m, f"espesor de {self.name}")


@dataclass(frozen=True)
class LinearWeightProperties:
    """Linear weight input for longitudinal bridge accessories."""

    name: str
    weight_kg_m: float

    def __post_init__(self) -> None:
        require_positive(self.weight_kg_m, f"peso lineal de {self.name}")


@dataclass(frozen=True)
class MaterialProperties:
    """Complete material and permanent accessory input set."""

    concrete: ConcreteProperties
    steel: SteelProperties
    asphalt: SurfaceLayerProperties
    sidewalk: SurfaceLayerProperties
    railing: LinearWeightProperties
    barrier: LinearWeightProperties
