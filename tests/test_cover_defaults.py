from copy import deepcopy
from pathlib import Path

import pytest

from bridge_design.cli.connected_yaml import connected_inputs_from_yaml, connected_yaml_template
from bridge_design.cli.yaml_io import load_yaml_file
from bridge_design.domain.abutment import AbutmentInputs, solve_abutment_design
from bridge_design.domain.barrier import BarrierSectionModel
from bridge_design.domain.cantilever_slab import CantileverSlabParameters
from bridge_design.domain.cantilever_wall import cantilever_wall_inputs
from bridge_design.domain.connected_inputs import ConnectedInputs, FoundationSoil
from bridge_design.domain.connected_reinforcement import region_inputs
from bridge_design.domain.interior_girder import InteriorGirderReinforcementParameters
from bridge_design.domain.reinforcement import SlabReinforcementParameters


def test_superstructure_keeps_approved_internal_covers():
    assert SlabReinforcementParameters().concrete_cover_cm == 5.0
    assert CantileverSlabParameters().concrete_cover_cm == 5.0
    assert InteriorGirderReinforcementParameters().concrete_cover_cm == 5.0
    barrier = BarrierSectionModel.new_jersey_image_default()
    assert barrier.mc_segments[0].effective_depth_cm == pytest.approx(
        17.90 - 5.08 - barrier.dowel_bar_diameter_cm / 2)


@pytest.mark.parametrize("inputs", [AbutmentInputs(), cantilever_wall_inputs()])
def test_retaining_structures_use_internal_cover_in_effective_depth(inputs):
    from bridge_design.domain.rebar_catalog import reinforcing_bar_by_label

    assert inputs.reinforcement.stem_cover_cm == 7.5
    assert inputs.reinforcement.footing_cover_cm == 7.5
    result = solve_abutment_design(inputs)
    bar = reinforcing_bar_by_label(result.stem_design.selected_bar_label)
    assert result.stem_design.effective_depth_cm == pytest.approx(
        inputs.geometry.lower_stem_thickness_m * 100 - 7.5 - bar.diameter_cm / 2)


def test_all_connected_regions_use_internal_cover():
    inputs = ConnectedInputs(FoundationSoil(3000, 0.5, 26.7))
    regions = ["Losa central"]
    for side in ("izquierda", "derecha"):
        regions.extend(f"{name} {side}" for name in (
            "Zapata", "Transicion", "Pantalla", "Transicion cajuela", "Cajuela", "Parapeto"))
    for region in regions:
        assert region_inputs(inputs, region)[1] == 7.5


@pytest.mark.parametrize("raw", [connected_yaml_template(example=True),
                                  load_yaml_file(Path("modelo_estribos_conectados.yaml"))])
def test_templates_do_not_require_cover_inputs(raw):
    data = deepcopy(raw)
    assert "recubrimiento_losa_cm" not in data["cimentacion"]
    for side in ("estribo_izquierdo", "estribo_derecho"):
        assert not any("recubrimiento" in key for key in data[side]["armadura"])
    data["suelo_cimentacion"].update(modulo_balasto_vertical_tn_m3=3000,
                                    coeficiente_friccion_interfaz=0.5)
    inputs = connected_inputs_from_yaml(data)
    assert inputs.slab_cover_cm == 7.5
    assert inputs.left.reinforcement.stem_cover_cm == inputs.right.reinforcement.stem_cover_cm == 7.5


@pytest.mark.parametrize("block,key", [
    ("cimentacion", "recubrimiento_losa_cm"),
    ("estribo_izquierdo", "recubrimiento_pantalla_cm"),
    ("estribo_izquierdo", "recubrimiento_zapata_cm"),
    ("estribo_derecho", "recubrimiento_pantalla_cm"),
    ("estribo_derecho", "recubrimiento_zapata_cm"),
])
@pytest.mark.parametrize("value", [5.0, 10.0])
def test_yaml_cannot_override_internal_covers(block, key, value):
    raw = connected_yaml_template(example=True)
    target = raw[block] if block == "cimentacion" else raw[block]["armadura"]
    target[key] = value
    inputs = connected_inputs_from_yaml(raw)
    assert inputs.slab_cover_cm == 7.5
    for side in (inputs.left, inputs.right):
        assert side.reinforcement.stem_cover_cm == 7.5
        assert side.reinforcement.footing_cover_cm == 7.5
    assert target[key] == value
