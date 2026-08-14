"""Project input aggregate models."""

from dataclasses import dataclass

from bridge_design.domain.barrier import BarrierDesignInputs
from bridge_design.domain.diaphragm import DiaphragmBeamGeometry
from bridge_design.domain.loads import LiveLoads
from bridge_design.domain.materials import MaterialProperties
from bridge_design.domain.exterior_girder import ExteriorGirderGeometry
from bridge_design.domain.interior_girder import InteriorGirderGeometry
from bridge_design.domain.transverse_slab import TransverseSlabDesignInputs


@dataclass(frozen=True)
class ProjectInputs:
    """General project inputs collected from terminal."""

    materials: MaterialProperties
    live_loads: LiveLoads
    barrier: BarrierDesignInputs
    transverse_slab: TransverseSlabDesignInputs
    interior_girder: InteriorGirderGeometry
    exterior_girder: ExteriorGirderGeometry
    diaphragm: DiaphragmBeamGeometry
