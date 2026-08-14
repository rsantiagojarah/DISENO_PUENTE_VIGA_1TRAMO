from bridge_design.cli.ascii_output import (
    format_abutment_reaction_summary,
    format_transverse_load_location_schemes,
)
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


def test_transverse_load_location_schemes_include_dc_dw_pl_data() -> None:
    output = format_transverse_load_location_schemes(_project_inputs())

    assert "ESQUEMAS DE UBICACION DE CARGAS TRANSVERSALES - DC / DW / PL / LL+IM" in output
    assert "DC - cargas muertas" in output
    assert "DW - superficie de rodadura" in output
    assert "PL - carga peatonal" in output
    assert "peso propio losa" in output
    assert "0.000 a 7.950 m" in output
    assert "asfalto" in output
    assert "1.075 a 6.875 m" in output
    assert "peatonal derecha" in output
    assert "7.125 a 7.950 m" in output
    assert "barrera izquierda" in output
    assert "x=0.950 m" in output
    assert "LL+IM - cargas moviles vehiculares" in output
    assert "LL+IM - 1 carril(es) movil(es)" in output
    assert "xb se desplaza de 1.685 a 4.436 m" in output
    assert "W1 en xb inicial" in output
    assert "rueda derecha carril 1" in output
    assert "LL+IM - 2 carril(es) movil(es)" in output
    assert "No aplicable" in output
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
