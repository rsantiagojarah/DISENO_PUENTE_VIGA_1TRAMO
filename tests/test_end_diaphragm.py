"""End diaphragms keep their own depth and girder weight."""

import pytest

from bridge_design.cli.yaml_inputs import project_inputs_from_yaml, project_yaml_template
from bridge_design.domain.interior_girder import _dc_point_loads_tn


def _ends(girder, thickness_m: float):
    axis_m = thickness_m / 2.0
    span = girder.span_length_m
    return tuple(
        item for item in girder.diaphragms
        if item.position_m in (axis_m, span - axis_m)
    )


def _interior(girder, thickness_m: float):
    ends = {item.position_m for item in _ends(girder, thickness_m)}
    return tuple(item for item in girder.diaphragms if item.position_m not in ends)


def test_missing_end_diaphragm_keeps_only_interior_loads() -> None:
    data = project_yaml_template()
    data.pop("diafragma_borde")
    project = project_inputs_from_yaml(data)

    assert project.end_diaphragm is None
    assert _ends(project.interior_girder, 0.30) == ()
    assert _ends(project.exterior_girder, 0.30) == ()
    assert len(project.interior_girder.diaphragms) == 3


def test_end_diaphragm_uses_its_own_depth_and_weight() -> None:
    data = project_yaml_template()
    data["diafragma_borde"] = {
        "espesor_longitudinal_m": 0.40,
        "altura_resistente_m": 1.20,
        "longitud_tributaria_cargas_m": 0.40,
    }
    data["viga_interior"]["diafragmas"].append(
        {
            "ubicacion_m": 0.0,
            "espesor_longitudinal_m": 0.20,
            "altura_m": 0.50,
            "ancho_tributario_transversal_m": 2.10,
        }
    )
    project = project_inputs_from_yaml(data)
    gamma = project.materials.concrete.specific_weight_tn_m3
    spacing = project.interior_girder.girder_spacing_m
    exterior_width = project.exterior_girder.tributary_width_m

    assert project.diaphragm.height_m == pytest.approx(1.10)
    assert project.end_diaphragm is not None
    assert project.end_diaphragm.height_m == pytest.approx(1.20)
    assert project.end_diaphragm.thickness_m == pytest.approx(0.40)
    assert len(_ends(project.interior_girder, 0.40)) == 2
    assert len(_ends(project.exterior_girder, 0.40)) == 2
    assert [item.position_m for item in _ends(project.interior_girder, 0.40)] == pytest.approx((0.20, 14.80))
    assert all(item.height_m == pytest.approx(1.10) and item.thickness_m == pytest.approx(0.25) for item in _interior(project.interior_girder, 0.40))
    assert all(
        item.height_m == pytest.approx(1.20)
        and item.thickness_m == pytest.approx(0.40)
        and item.tributary_width_m == pytest.approx(spacing)
        for item in _ends(project.interior_girder, 0.40)
    )
    assert all(
        item.height_m == pytest.approx(1.20)
        and item.tributary_width_m == pytest.approx(exterior_width)
        for item in _ends(project.exterior_girder, 0.40)
    )

    interior_loads = dict(_dc_point_loads_tn(project.interior_girder, project.materials))
    exterior_loads = dict(_dc_point_loads_tn(project.exterior_girder, project.materials))
    assert interior_loads[0.20] == pytest.approx(gamma * 0.40 * 1.20 * spacing)
    assert interior_loads[7.5] == pytest.approx(gamma * 0.25 * 1.10 * spacing)
    assert exterior_loads[0.20] == pytest.approx(gamma * 0.40 * 1.20 * exterior_width)
    assert 0.0 not in interior_loads
    assert interior_loads[0.20] != pytest.approx(interior_loads[7.5])
    assert exterior_loads[0.20] != pytest.approx(interior_loads[0.20])
