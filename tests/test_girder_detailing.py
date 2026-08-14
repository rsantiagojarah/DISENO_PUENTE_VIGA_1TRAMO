from bridge_design.cli.ascii_output import format_girder_detailing_result
from bridge_design.domain.exterior_girder import (
    ExteriorGirderGeometry,
    exterior_asphalt_tributary_width_m,
    design_exterior_girder_reinforcement,
    solve_exterior_girder_design,
)
from bridge_design.domain.girder_detailing import (
    detail_exterior_girder,
    detail_interior_girder,
)
from bridge_design.domain.interior_girder import (
    DiaphragmGeometry,
    InteriorGirderGeometry,
    design_interior_girder_reinforcement,
    solve_interior_girder_design,
)
from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel
from bridge_design.domain.materials import (
    ConcreteProperties,
    LinearWeightProperties,
    MaterialProperties,
    SteelProperties,
    SurfaceLayerProperties,
)


def _materials() -> MaterialProperties:
    return MaterialProperties(
        concrete=ConcreteProperties.from_inputs(
            specific_weight_tn_m3=2.4,
            compressive_strength_kg_cm2=280.0,
        ),
        steel=SteelProperties(),
        asphalt=SurfaceLayerProperties("asfalto", 2.2, 0.05),
        sidewalk=SurfaceLayerProperties("vereda", 2.4, 0.20),
        railing=LinearWeightProperties("baranda", 100.0),
        barrier=LinearWeightProperties("barrera", 500.0),
    )


def _live_loads() -> LiveLoads:
    return LiveLoads(
        pedestrian=PedestrianLoad.mtc_sidewalk_default(),
        vehicular=VehicleLoadModel.mtc_hl93_default(),
    )


def _interior_geometry() -> InteriorGirderGeometry:
    return InteriorGirderGeometry(
        span_length_m=15.0,
        girder_spacing_m=2.10,
        slab_thickness_m=0.20,
        girder_total_height_m=1.20,
        web_width_m=0.30,
        girder_count=4,
        diaphragms=(
            DiaphragmGeometry(3.75, 0.25, 1.10, 2.10),
            DiaphragmGeometry(7.50, 0.25, 1.10, 2.10),
            DiaphragmGeometry(11.25, 0.25, 1.10, 2.10),
        ),
        moving_load_step_m=0.50,
        moment_sample_step_m=0.50,
    )


def _exterior_geometry() -> ExteriorGirderGeometry:
    return ExteriorGirderGeometry(
        span_length_m=15.0,
        girder_spacing_m=2.10,
        deck_overhang_m=0.825,
        slab_thickness_m=0.20,
        girder_total_height_m=1.20,
        web_width_m=0.30,
        exterior_web_to_traffic_barrier_m=-0.25,
        sidewalk_width_m=0.825,
        asphalt_tributary_width_m=exterior_asphalt_tributary_width_m(
            deck_overhang_m=0.825,
            girder_spacing_m=2.10,
            asphalt_start_m=1.075,
            asphalt_end_m=6.875,
        ),
        girder_count=4,
        diaphragms=(
            DiaphragmGeometry(3.75, 0.25, 1.10, 1.875),
            DiaphragmGeometry(7.50, 0.25, 1.10, 1.875),
            DiaphragmGeometry(11.25, 0.25, 1.10, 1.875),
        ),
        moving_load_step_m=0.50,
        moment_sample_step_m=0.50,
    )


def _assert_longitudinal_cuts_follow_selected_layers(detail) -> None:
    selected = detail.selected_main_bar
    full_layer_count = selected.bars_per_layer
    partial_top_layer_count = selected.bar_count % selected.bars_per_layer or full_layer_count
    layer_counts = []
    remaining = selected.bar_count
    while remaining > 0:
        layer_count = min(selected.bars_per_layer, remaining)
        layer_counts.append(layer_count)
        remaining -= layer_count
    cumulative_layer_counts = {
        sum(layer_counts[: index + 1])
        for index in range(len(layer_counts))
    }
    cut_counts = [cut.bar_count for cut in detail.longitudinal_cuts]

    assert sum(cut_counts) == selected.bar_count
    assert detail.continuous_bar_count in cumulative_layer_counts
    assert all(count in {full_layer_count, partial_top_layer_count} for count in cut_counts)


def test_interior_girder_detailing_returns_bar_groups_and_stirrup_zones() -> None:
    geometry = _interior_geometry()
    analysis = solve_interior_girder_design(geometry, _materials(), _live_loads())
    reinforcement = design_interior_girder_reinforcement(geometry, _materials(), analysis)

    detail = detail_interior_girder(
        label="Viga interior",
        geometry=geometry,
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
    )

    assert detail.continuous_bar_count >= 2
    assert detail.development_length_m > 0.0
    assert detail.longitudinal_cuts[0].group == "Barras continuas"
    assert any(cut.group.startswith("Adicional") for cut in detail.longitudinal_cuts)
    assert all(zone.status == "OK" for zone in detail.stirrup_zones)
    assert detail.envelope[0].selected_bar_count == detail.selected_main_bar.bar_count


def test_interior_girder_detailing_keeps_all_user_selected_main_bars() -> None:
    geometry = _interior_geometry()
    analysis = solve_interior_girder_design(geometry, _materials(), _live_loads())
    reinforcement = design_interior_girder_reinforcement(geometry, _materials(), analysis)
    user_selected = next(
        option
        for option in reinforcement.main.placement_options.options
        if option.bar_label == '1"' and option.bar_count == 20
    )

    detail = detail_interior_girder(
        label="Viga interior",
        geometry=geometry,
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
        selected_main_bar=user_selected,
    )

    assert detail.selected_main_bar == user_selected
    _assert_longitudinal_cuts_follow_selected_layers(detail)
    excess_cuts = [
        cut
        for cut in detail.longitudinal_cuts
        if cut.status == "ADOPTADA EN ZONA CRITICA"
    ]
    assert excess_cuts
    assert all(cut.detail_start_m > 0.0 for cut in excess_cuts)
    assert all(cut.detail_end_m < geometry.span_length_m for cut in excess_cuts)


def test_exterior_girder_detailing_cuts_main_bars_by_constructive_layers() -> None:
    geometry = _exterior_geometry()
    analysis = solve_exterior_girder_design(geometry, _materials(), _live_loads())
    reinforcement = design_exterior_girder_reinforcement(geometry, _materials(), analysis)
    user_selected = next(
        option
        for option in reinforcement.main.placement_options.options
        if option.bar_label == '1"' and option.bar_count == 20
    )

    detail = detail_exterior_girder(
        label="Viga exterior",
        geometry=geometry,
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
        selected_main_bar=user_selected,
    )

    _assert_longitudinal_cuts_follow_selected_layers(detail)


def test_girder_detailing_ascii_cut_table_is_compact_and_readable() -> None:
    geometry = _interior_geometry()
    analysis = solve_interior_girder_design(geometry, _materials(), _live_loads())
    reinforcement = design_interior_girder_reinforcement(geometry, _materials(), analysis)
    user_selected = next(
        option
        for option in reinforcement.main.placement_options.options
        if option.bar_label == '1"' and option.bar_count == 20
    )
    detail = detail_interior_girder(
        label="Viga interior",
        geometry=geometry,
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
        selected_main_bar=user_selected,
    )

    output = format_girder_detailing_result(detail, "2.F")
    lines = output.splitlines()

    assert "Cortes de acero longitudinal (rangos en m)" in output
    assert "Detalle por capas:" in output
    assert "Base" in output
    assert "Adic. 1" in output
    assert "ADOPTADA EN ZONA CRITICA" not in output
    assert "ZC=adoptada en zona critica" in output
    assert max(len(line) for line in lines) <= 104


def test_exterior_girder_detailing_includes_pedestrian_load_in_envelope() -> None:
    geometry = _exterior_geometry()
    analysis = solve_exterior_girder_design(geometry, _materials(), _live_loads())
    reinforcement = design_exterior_girder_reinforcement(geometry, _materials(), analysis)

    detail = detail_exterior_girder(
        label="Viga exterior",
        geometry=geometry,
        materials=_materials(),
        analysis=analysis,
        reinforcement=reinforcement,
    )

    assert detail.envelope
    assert max(station.mu_tn_m for station in detail.envelope) > analysis.dc.max_positive_moment_tn_m
    assert detail.stirrup_zones[0].maximum_vu_tn > 0.0
