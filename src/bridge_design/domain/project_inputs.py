"""Project input aggregate models."""

from dataclasses import dataclass, replace

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

    def __post_init__(self) -> None:
        """Derive the barrier dead load from its resisting profile."""
        weight = self.barrier.geometry.cross_section_area_m2 * self.materials.concrete.specific_weight_tn_m3 * 1000.0
        object.__setattr__(self, "materials", replace(
            self.materials, barrier=replace(self.materials.barrier, weight_kg_m=weight)
        ))
        old_layout = self.transverse_slab.load_layout
        traffic_face = old_layout.barrier_left_m + self.barrier.geometry.base_width_m
        other_face = self.transverse_slab.geometry.total_width_m - traffic_face
        layout = replace(old_layout, barrier_width_m=self.barrier.geometry.base_width_m,
                         asphalt_start_m=max(old_layout.asphalt_start_m, traffic_face),
                         asphalt_end_m=min(old_layout.asphalt_end_m, other_face))
        object.__setattr__(self, "transverse_slab", replace(self.transverse_slab, load_layout=layout))
        object.__setattr__(self, "exterior_girder", replace(
            self.exterior_girder,
            exterior_web_to_traffic_barrier_m=self.transverse_slab.geometry.overhang_m - layout.barrier_left_m - layout.barrier_width_m,
            asphalt_tributary_width_m=max(0.0, self.exterior_girder.tributary_width_m - layout.asphalt_start_m),
        ))
