from bridge_design.domain.diaphragm import (
    DiaphragmBeamGeometry,
    combine_diaphragm_moments,
    combine_diaphragm_shears,
    design_diaphragm_reinforcement,
    solve_diaphragm_design,
)
from bridge_design.domain.loads import LiveLoads, PedestrianLoad, VehicleLoadModel
from bridge_design.domain.materials import (
    ConcreteProperties,
    LinearWeightProperties,
    MaterialProperties,
    SteelProperties,
    SurfaceLayerProperties,
)
from bridge_design.domain.transverse_slab import TransverseLoadLayout
from bridge_design.main import (
    collect_diaphragm_reinforcement_selection,
    format_diaphragm_reinforcement_selection,
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


def _geometry() -> DiaphragmBeamGeometry:
    return DiaphragmBeamGeometry(
        girder_spacing_m=2.10,
        girder_count=4,
        deck_overhang_m=0.825,
        thickness_m=0.25,
        height_m=1.10,
        slab_thickness_m=0.20,
        load_tributary_length_m=0.25,
        vehicle_step_m=0.50,
    )


def _layout() -> TransverseLoadLayout:
    return TransverseLoadLayout(
        asphalt_start_m=1.075,
        asphalt_end_m=6.875,
        sidewalk_width_m=0.825,
        railing_left_m=0.13,
        barrier_left_m=0.825,
        barrier_width_m=0.25,
        vehicle_move_start_m=0.825,
        vehicle_move_end_m=7.125,
        vehicle_step_m=0.50,
    )


def test_diaphragm_solves_loads_combinations_flexure_temperature_and_shear() -> None:
    analysis = solve_diaphragm_design(
        geometry=_geometry(),
        materials=_materials(),
        live_loads=LiveLoads(
            pedestrian=PedestrianLoad.mtc_sidewalk_default(),
            vehicular=VehicleLoadModel.mtc_hl93_default(),
        ),
        layout=_layout(),
    )

    assert analysis.dc.max_positive_moment_tn_m > 0.0
    assert analysis.dc.max_negative_moment_tn_m < 0.0
    assert analysis.dw.max_positive_moment_tn_m > 0.0
    assert analysis.pl.max_positive_moment_tn_m >= 0.0
    assert analysis.ll_im_envelope.max_positive_moment_tn_m > 0.0
    assert analysis.ll_im_envelope.max_abs_shear_tn > 0.0

    combined = combine_diaphragm_moments(analysis)
    strength_negative = next(
        row
        for row in combined
        if row.combination_name == "RESISTENCIA I" and row.direction == "M-"
    )
    strength_positive = next(
        row
        for row in combined
        if row.combination_name == "RESISTENCIA I" and row.direction == "M+"
    )
    assert strength_negative.combined_moment_tn_m < 0.0
    assert strength_positive.combined_moment_tn_m > 0.0

    shear_rows = combine_diaphragm_shears(analysis)
    assert max(row.combined_shear_tn for row in shear_rows) > 0.0

    reinforcement = design_diaphragm_reinforcement(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
    )
    assert reinforcement.negative.required_area_cm2 > 0.0
    assert reinforcement.negative.placement_options.recommended is not None
    assert reinforcement.positive.required_area_cm2 > 0.0
    assert reinforcement.positive.placement_options.recommended is not None
    assert reinforcement.temperature.required_area_cm2_m_per_face > 0.0
    assert reinforcement.temperature.spacing_options.recommended is not None
    assert reinforcement.shear.controlling_shear.combined_shear_tn > 0.0
    assert reinforcement.shear.recommended is not None


def test_diaphragm_ignores_two_truck_case_when_vehicle_path_is_too_narrow() -> None:
    layout = TransverseLoadLayout(
        asphalt_start_m=1.075,
        asphalt_end_m=6.875,
        sidewalk_width_m=0.825,
        railing_left_m=0.13,
        barrier_left_m=0.825,
        barrier_width_m=0.25,
        vehicle_move_start_m=1.075,
        vehicle_move_end_m=6.875,
        vehicle_step_m=0.50,
    )

    analysis = solve_diaphragm_design(
        geometry=_geometry(),
        materials=_materials(),
        live_loads=LiveLoads(
            pedestrian=PedestrianLoad.mtc_sidewalk_default(),
            vehicular=VehicleLoadModel.mtc_hl93_default(),
        ),
        layout=layout,
    )

    assert analysis.ll_im_one_truck.max_positive_moment_tn_m > 0.0
    assert analysis.ll_im_two_trucks.max_positive_moment_tn_m == 0.0
    assert analysis.ll_im_two_trucks.critical_vehicle_position_m is None
    assert "no aplicable" in analysis.ll_im_two_trucks.vehicle_configuration
    assert analysis.ll_im_envelope.max_positive_moment_tn_m > 0.0


def test_diaphragm_reinforcement_selection_uses_recommended_defaults(monkeypatch) -> None:
    analysis = solve_diaphragm_design(
        geometry=_geometry(),
        materials=_materials(),
        live_loads=LiveLoads(
            pedestrian=PedestrianLoad.mtc_sidewalk_default(),
            vehicular=VehicleLoadModel.mtc_hl93_default(),
        ),
        layout=_layout(),
    )
    reinforcement = design_diaphragm_reinforcement(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
    )
    monkeypatch.setattr("builtins.input", lambda _: "")

    selected = collect_diaphragm_reinforcement_selection(reinforcement)

    assert len(selected) == 4
    assert selected[0][1] == reinforcement.negative.placement_options.recommended
    assert selected[1][1] == reinforcement.positive.placement_options.recommended
    assert selected[2][1] == reinforcement.temperature.spacing_options.recommended
    assert selected[3][1] == reinforcement.shear.recommended
    assert "VIGA DIAFRAGMA" in format_diaphragm_reinforcement_selection(selected)


def test_diaphragm_reinforcement_selection_accepts_user_items(monkeypatch) -> None:
    analysis = solve_diaphragm_design(
        geometry=_geometry(),
        materials=_materials(),
        live_loads=LiveLoads(
            pedestrian=PedestrianLoad.mtc_sidewalk_default(),
            vehicular=VehicleLoadModel.mtc_hl93_default(),
        ),
        layout=_layout(),
    )
    reinforcement = design_diaphragm_reinforcement(
        geometry=_geometry(),
        materials=_materials(),
        analysis=analysis,
    )
    answers = iter(("s", "1", "2", "3", "4"))
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    selected = collect_diaphragm_reinforcement_selection(reinforcement)

    assert selected[0][1].item == 1
    assert selected[1][1].item == 2
    assert selected[2][1].item == 3
    assert selected[3][1].item == 4
