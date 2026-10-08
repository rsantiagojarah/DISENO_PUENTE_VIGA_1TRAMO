"""Project input aggregate models."""

from dataclasses import dataclass, replace

from bridge_design.domain.barrier import BarrierDesignInputs
from bridge_design.domain.diaphragm import DiaphragmBeamGeometry
from bridge_design.domain.loads import LiveLoads
from bridge_design.domain.materials import MaterialProperties
from bridge_design.domain.exterior_girder import ExteriorGirderGeometry
from bridge_design.domain.interior_girder import DiaphragmGeometry, InteriorGirderGeometry
from bridge_design.domain.transverse_slab import TransverseSlabDesignInputs

_SUPPORT_DIAPHRAGM_TOLERANCE_M = 1e-3


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
    end_diaphragm: DiaphragmBeamGeometry | None = None

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
        exterior = replace(
            self.exterior_girder,
            exterior_web_to_traffic_barrier_m=self.transverse_slab.geometry.overhang_m - layout.barrier_left_m - layout.barrier_width_m,
            asphalt_tributary_width_m=max(0.0, self.exterior_girder.tributary_width_m - layout.asphalt_start_m),
        )
        interior = self.interior_girder
        if self.end_diaphragm is not None:
            interior = _girder_with_end_diaphragms(
                interior,
                self.end_diaphragm,
                interior.girder_spacing_m,
            )
            exterior = _girder_with_end_diaphragms(
                exterior,
                self.end_diaphragm,
                exterior.tributary_width_m,
            )
        object.__setattr__(self, "interior_girder", interior)
        object.__setattr__(self, "exterior_girder", exterior)


def _is_support_diaphragm(position_m: float, span_m: float) -> bool:
    return position_m <= _SUPPORT_DIAPHRAGM_TOLERANCE_M or abs(position_m - span_m) <= _SUPPORT_DIAPHRAGM_TOLERANCE_M


def _girder_with_end_diaphragms(girder, end_diaphragm: DiaphragmBeamGeometry, tributary_width_m: float):
    """Keep span diaphragms and place the end section at both supports."""
    kept = tuple(
        item for item in girder.diaphragms
        if not _is_support_diaphragm(item.position_m, girder.span_length_m)
    )
    ends = tuple(
        DiaphragmGeometry(
            position_m=position_m,
            thickness_m=end_diaphragm.thickness_m,
            height_m=end_diaphragm.height_m,
            tributary_width_m=tributary_width_m,
        )
        for position_m in (0.0, girder.span_length_m)
    )
    return replace(girder, diaphragms=tuple(sorted((*kept, *ends), key=lambda item: item.position_m)))
