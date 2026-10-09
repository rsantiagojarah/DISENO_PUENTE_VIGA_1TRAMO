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
            sidewalk_start_m=layout.sidewalk_start_m,
            sidewalk_width_m=layout.sidewalk_width_m,
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


def _occupies_end_diaphragm(position_m: float, span_m: float, thickness_m: float) -> bool:
    """Return whether a load lies inside the end diaphragm measured from either edge."""
    return (
        position_m <= thickness_m + _SUPPORT_DIAPHRAGM_TOLERANCE_M
        or position_m >= span_m - thickness_m - _SUPPORT_DIAPHRAGM_TOLERANCE_M
    )


def _girder_with_end_diaphragms(girder, end_diaphragm: DiaphragmBeamGeometry, tributary_width_m: float):
    """Keep span diaphragms and place each end diaphragm on its own centerline.

    The diaphragm face is flush with the girder end, so its axis is half its
    thickness in from that edge.
    """
    thickness_m = end_diaphragm.thickness_m
    if thickness_m >= girder.span_length_m:
        raise ValueError("El espesor del diafragma de extremo debe ser menor que la luz.")
    kept = tuple(
        item for item in girder.diaphragms
        if not _occupies_end_diaphragm(item.position_m, girder.span_length_m, thickness_m)
    )
    axis_m = thickness_m / 2.0
    ends = tuple(
        DiaphragmGeometry(
            position_m=position_m,
            thickness_m=thickness_m,
            height_m=end_diaphragm.height_m,
            tributary_width_m=tributary_width_m,
        )
        for position_m in (axis_m, girder.span_length_m - axis_m)
    )
    return replace(girder, diaphragms=tuple(sorted((*kept, *ends), key=lambda item: item.position_m)))
