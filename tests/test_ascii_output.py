import pytest

from bridge_design.cli.ascii_output import (
    _format_main_placement_table,
    _format_shear_option_table,
    _format_spacing_case_table,
    format_abutment_reaction_summary,
    format_exterior_girder_analysis_result,
    format_interior_girder_analysis_result,
    format_transverse_load_location_schemes,
)
from bridge_design.cli.abutment_ascii_output import _format_spacing_option_table
from bridge_design.domain.barrier import BarrierDesignInputs
from bridge_design.domain.diaphragm import diaphragm_geometry_from_transverse
from bridge_design.domain.exterior_girder import (
    ExteriorGirderGeometry,
    exterior_asphalt_tributary_width_m,
    solve_exterior_girder_design,
)
from bridge_design.domain.interior_girder import (
    DiaphragmGeometry,
    InteriorGirderGeometry,
    LongitudinalBarPlacementOption,
    LongitudinalPlacementCaseOptions,
    ShearStirrupOption,
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
from bridge_design.domain.project_inputs import ProjectInputs
from bridge_design.domain.rebar_catalog import (
    ReinforcementCaseOptions,
    ReinforcementSpacingOption,
    ReinforcingBar,
)
from bridge_design.domain.transverse_slab import (
    TransverseLoadLayout,
    TransverseSlabDesignInputs,
    TransverseSlabGeometry,
)


def _project_inputs() -> ProjectInputs:
    geometry = TransverseSlabGeometry(
        girder_spacing_m=2.10,
        overhang_m=0.825,
        girder_count=4,
        slab_thickness_m=0.20,
        girder_total_height_m=1.20,
        girder_width_m=0.30,
    )
    layout = TransverseLoadLayout(
        asphalt_start_m=1.075,
        asphalt_end_m=6.875,
        sidewalk_width_m=0.825,
        railing_left_m=0.13,
        barrier_left_m=0.825,
        barrier_width_m=0.25,
        vehicle_move_start_m=1.075,
        vehicle_move_end_m=6.875,
        vehicle_step_m=0.10,
    )
    materials = MaterialProperties(
        concrete=ConcreteProperties.from_inputs(2.4, 280.0),
        steel=SteelProperties(),
        asphalt=SurfaceLayerProperties("asfalto", 2.2, 0.05),
        sidewalk=SurfaceLayerProperties("vereda", 2.4, 0.20),
        railing=LinearWeightProperties("baranda", 100.0),
        barrier=LinearWeightProperties("barrera", 500.0),
    )
    live_loads = LiveLoads(
        pedestrian=PedestrianLoad.mtc_sidewalk_default(),
        vehicular=VehicleLoadModel.mtc_hl93_default(),
    )
    diaphragms = (
        DiaphragmGeometry(3.75, 0.25, 1.10, 2.10),
        DiaphragmGeometry(7.50, 0.25, 1.10, 2.10),
        DiaphragmGeometry(11.25, 0.25, 1.10, 2.10),
    )
    interior = InteriorGirderGeometry(
        span_length_m=15.0,
        girder_spacing_m=geometry.girder_spacing_m,
        slab_thickness_m=geometry.slab_thickness_m,
        girder_total_height_m=geometry.girder_total_height_m,
        web_width_m=geometry.girder_width_m,
        girder_count=geometry.girder_count,
        diaphragms=diaphragms,
    )
    exterior = ExteriorGirderGeometry(
        span_length_m=15.0,
        girder_spacing_m=geometry.girder_spacing_m,
        deck_overhang_m=geometry.overhang_m,
        slab_thickness_m=geometry.slab_thickness_m,
        girder_total_height_m=geometry.girder_total_height_m,
        web_width_m=geometry.girder_width_m,
        exterior_web_to_traffic_barrier_m=-0.25,
        sidewalk_width_m=layout.sidewalk_width_m,
        asphalt_tributary_width_m=exterior_asphalt_tributary_width_m(
            deck_overhang_m=geometry.overhang_m,
            girder_spacing_m=geometry.girder_spacing_m,
            asphalt_start_m=layout.asphalt_start_m,
            asphalt_end_m=layout.asphalt_end_m,
        ),
        girder_count=geometry.girder_count,
        diaphragms=diaphragms,
        live_load_distribution_factor_g=0.536,
        live_load_shear_distribution_factor_g=0.536,
    )
    return ProjectInputs(
        materials=materials,
        live_loads=live_loads,
        barrier=BarrierDesignInputs(),
        transverse_slab=TransverseSlabDesignInputs(geometry, layout),
        interior_girder=interior,
        exterior_girder=exterior,
        diaphragm=diaphragm_geometry_from_transverse(
            geometry,
            thickness_m=0.25,
            height_m=1.10,
            load_tributary_length_m=0.25,
        ),
    )


def test_girder_reports_develop_total_and_effective_depths() -> None:
    project_inputs = _project_inputs()
    interior = solve_interior_girder_design(
        geometry=project_inputs.interior_girder,
        materials=project_inputs.materials,
        live_loads=project_inputs.live_loads,
    )
    exterior = solve_exterior_girder_design(
        geometry=project_inputs.exterior_girder,
        materials=project_inputs.materials,
        live_loads=project_inputs.live_loads,
    )

    interior_output = format_interior_girder_analysis_result(interior, project_inputs)
    exterior_output = format_exterior_girder_analysis_result(exterior, project_inputs)

    assert "Peralte resistente de la viga interior:" in interior_output
    assert "Peralte resistente de la viga exterior:" in exterior_output
    assert "h = 1.200 + 0.200 = 1.400 m" in interior_output
    assert "h = 1.200 + 0.200 = 1.400 m" in exterior_output
    assert "d inicial = 140.00 - 5.00 - 2.540/2 = 133.73 cm" in interior_output
    assert "d inicial = 140.00 - 5.00 - 2.540/2 = 133.73 cm" in exterior_output


def test_steel_spacing_tables_only_show_compliant_options() -> None:
    options = ReinforcementCaseOptions(
        label="Acero de prueba",
        required_area_cm2_m=5.0,
        options=(
            ReinforcementSpacingOption(101, ReinforcingBar("A", 1.0, 1.0), 0.075, 5.0, 10.0, True),
            ReinforcementSpacingOption(102, ReinforcingBar("B", 1.0, 1.0), 0.125, 5.0, 8.0, True),
            ReinforcementSpacingOption(103, ReinforcingBar("C", 1.0, 1.0), 0.15, 5.0, 4.0, False),
        ),
    )

    slab_table = "\n".join(_format_spacing_case_table(options))
    abutment_table = "\n".join(_format_spacing_option_table(options))

    for table in (slab_table, abutment_table):
        assert "101" in table
        assert "102" in table
        assert "103" not in table


def test_main_steel_table_only_shows_compliant_options() -> None:
    def option(item: int, spacing_cm: float, compliant: bool) -> LongitudinalBarPlacementOption:
        return LongitudinalBarPlacementOption(
            item=item,
            bar_label='1"',
            bar_area_cm2=5.0,
            bar_diameter_cm=2.54,
            bar_count=4,
            layers=1,
            bars_per_layer=4,
            required_area_cm2=15.0,
            provided_area_cm2=20.0,
            clear_spacing_cm=spacing_cm,
            is_compliant=compliant,
        )

    table = "\n".join(
        _format_main_placement_table(
            LongitudinalPlacementCaseOptions(
                "Acero principal",
                15.0,
                (option(201, 5.0, True), option(202, 10.01, True), option(203, 12.0, False)),
            )
        )
    )

    assert "201" in table
    assert "202" in table
    assert "203" not in table


def test_stirrup_table_only_shows_compliant_options() -> None:
    def option(item: int, spacing_m: float, compliant: bool) -> ShearStirrupOption:
        return ShearStirrupOption(
            item=item,
            bar_label='3/8"',
            bar_area_cm2=0.71,
            legs=2,
            spacing_m=spacing_m,
            required_av_cm2_m=5.0,
            provided_av_cm2_m=6.0,
            phi_vn_tn=20.0,
            is_compliant=compliant,
        )

    table = "\n".join(
        _format_shear_option_table(
            (option(301, 0.075, True), option(302, 0.125, True), option(303, 0.15, False))
        )
    )

    assert "301" in table
    assert "302" in table
    assert "303" not in table


def test_transverse_report_shows_all_admissible_lane_counts():
    from dataclasses import replace
    project = _project_inputs()
    geometry = replace(project.transverse_slab.geometry, girder_spacing_m=2.7, girder_count=5)
    layout = replace(project.transverse_slab.load_layout, vehicle_move_start_m=0.825,
                     vehicle_move_end_m=11.625)
    project = replace(project, transverse_slab=TransverseSlabDesignInputs(geometry, layout))
    output = format_transverse_load_location_schemes(project)
    assert "LL+IM - 3 carril(es) movil(es)" in output
    assert "LL+IM - 4 carril(es) movil(es)" not in output
    assert "W5 en x3 min" in output
    assert "Posiciones xi independientes" in output
    assert "separacion entre carriles=" not in output


def test_six_metre_roadway_report_uses_metric_dimensions():
    from dataclasses import replace
    project = _project_inputs()
    layout = replace(project.transverse_slab.load_layout, vehicle_move_start_m=0.975,
                     vehicle_move_end_m=6.975)
    project = replace(project, transverse_slab=replace(project.transverse_slab, load_layout=layout))
    output = format_transverse_load_location_schemes(project)
    assert "calzada de 6.00 m admite 2 carriles de 3.00 m" in output
    assert "LL+IM - 2 carril(es) movil(es)" in output
    assert "franja cargada=3.000 m" in output
    assert "separacion transversal de ruedas=1.800 m" in output
    assert "No aplicable" not in output
    assert "requiere definir" not in output


def test_incompatible_lane_geometry_stops_before_calculations(monkeypatch, capsys):
    from dataclasses import replace
    from bridge_design.main import run_bridge_design
    project = _project_inputs()
    layout = replace(project.transverse_slab.load_layout, vehicle_move_start_m=0.975,
                     vehicle_move_end_m=6.975)
    project = replace(project, transverse_slab=replace(project.transverse_slab, load_layout=layout))
    project = replace(project, live_loads=replace(project.live_loads,
                      vehicular=replace(project.live_loads.vehicular, lane_load_width_m=3.048)))
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("No debe solicitar armadura"))
    run_bridge_design(project)
    output = capsys.readouterr().out
    assert "CALCULO NO INICIADO" in output
    assert "convencion dimensional" in output
    assert "DISENO DE LOSA" not in output


def test_transverse_load_location_schemes_include_dc_dw_pl_data() -> None:
    output = format_transverse_load_location_schemes(_project_inputs())

    assert "ESQUEMAS DE UBICACION DE CARGAS TRANSVERSALES - DC / DW / PL / LL+IM" in output
    assert "DC - cargas muertas" in output
    assert "DW - superficie de rodadura" in output
    assert "PL - carga peatonal" in output
    assert "peso propio losa" in output
    assert "0.000 a 7.950 m" in output
    assert "asfalto" in output
    assert "1.200 a 6.750 m" in output  # H19: asphalt starts at the actual barrier face.
    assert "peatonal derecha" in output
    assert "7.125 a 7.950 m" in output
    assert "barrera izquierda" in output
    assert "x=1.012 m" in output  # H19: width matches the resisting barrier profile.
    assert "LL+IM - cargas moviles vehiculares" in output
    assert "LL+IM - 1 carril(es) movil(es)" in output
    assert "x1: 1.675 a 4.475 m" in output
    assert "W1 en x1 min" in output
    assert "rueda derecha carril 1" in output
    assert "LL+IM - 2 carril(es) movil(es)" not in output
    assert "Posiciones xi independientes" in output
    assert "LL+IM - esquema movil longitudinal en la luz del puente" in output
    assert "Eje longitudinal X desde apoyo fijo hasta apoyo movil" in output
    assert "LL+IM - camion de diseno longitudinal" in output
    assert "Carril diseno" in output
    assert "Vehiculo al inicio" in output
    assert "Vehiculo al final" in output
    assert "separacion ejes: E1 - 4.267 m - E2" in output
    assert "LL+IM - tandem de diseno longitudinal" in output
    assert "P con IM" in output


def test_abutment_reaction_summary_reports_dead_asphalt_pedestrian_and_live() -> None:
    project_inputs = _project_inputs()
    interior = solve_interior_girder_design(
        geometry=project_inputs.interior_girder,
        materials=project_inputs.materials,
        live_loads=project_inputs.live_loads,
    )
    exterior = solve_exterior_girder_design(
        geometry=project_inputs.exterior_girder,
        materials=project_inputs.materials,
        live_loads=project_inputs.live_loads,
    )

    output = format_abutment_reaction_summary(interior, exterior, project_inputs)

    assert "REACCIONES PARA DISENO DE ESTRIBOS" in output
    assert "PDC" in output
    assert "PDW" in output
    assert "PPL" in output
    assert "PLL+IM" in output
    assert "P servicio" in output
    assert "La carga peatonal se reporta como PPL" in output
