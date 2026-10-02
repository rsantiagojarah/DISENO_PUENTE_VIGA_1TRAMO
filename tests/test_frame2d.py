import pytest

from bridge_design.domain.frame_solver import FrameSolver
from bridge_design.domain.frame_types import (
    ElementLoad, FrameCase, FrameElement, FrameModel, FrameNode, VerticalSpring,
)


def test_cantilever_matches_axial_and_bending_closed_forms():
    model = FrameModel((FrameNode(0, 0), FrameNode(4, 0)),
                       (FrameElement(0, 1, 2, 0.3, 10000),), (), (0, 1, 2))
    result = FrameSolver(model).solve(FrameCase("Punta", (0, 0, 0, 10, -8, 0), (ElementLoad(),)))
    assert result.displacements[3] == pytest.approx(10 * 4 / (10000 * 2))
    assert result.displacements[4] == pytest.approx(-8 * 4**3 / (3 * 10000 * 0.3))
    assert result.reactions[:3] == pytest.approx((-10, 8, 32))
    assert result.sections[0].axial == pytest.approx(10)
    assert result.sections[0].moment == pytest.approx(-32)
    assert result.equilibrium_error == pytest.approx((0, 0, 0), abs=1e-8)


def test_distributed_load_has_exact_midspan_extremum():
    model = FrameModel((FrameNode(0, 0), FrameNode(6, 0)),
                       (FrameElement(0, 1, 1, 0.1, 30000),), (), (0, 1, 4))
    result = FrameSolver(model).solve(FrameCase("Uniforme", (0,) * 6,
                                               (ElementLoad(transverse=(-2, 0, 0)),)))
    assert result.reactions[1] == pytest.approx(6)
    assert result.reactions[4] == pytest.approx(6)
    assert max(section.moment for section in result.sections) == pytest.approx(9)


def test_compression_contact_lifts_one_end_and_preserves_equilibrium():
    model = FrameModel(tuple(FrameNode(index, 0) for index in range(3)),
                       tuple(FrameElement(index, index + 1, 1, 0.2, 10000) for index in range(2)),
                       tuple(VerticalSpring(index, 1000, 1) for index in range(3)), (0,))
    result = FrameSolver(model).solve(FrameCase("Excentrica", (0, 0, 0, 0, -10, 0, 0, 0, 8),
                                               (ElementLoad(),) * 2))
    assert min(result.spring_reactions) >= -1e-8
    assert not all(result.contact)
    assert sum(result.spring_reactions) == pytest.approx(10)
    assert sum(index * reaction for index, reaction in enumerate(result.spring_reactions)) == pytest.approx(2)
    assert result.equilibrium_error == pytest.approx((0, 0, 0), abs=1e-7)


def test_uplift_without_any_compression_support_is_rejected():
    model = FrameModel((FrameNode(0, 0), FrameNode(2, 0)),
                       (FrameElement(0, 1, 1, 0.2, 10000),),
                       (VerticalSpring(0, 1000, 1), VerticalSpring(1, 1000, 1)), (0,))
    with pytest.raises(ValueError, match="inestable"):
        FrameSolver(model).solve(FrameCase("Levantamiento", (0, 10, 0, 0, 10, 0), (ElementLoad(),)))


def test_centroid_offset_couples_axial_force_and_reference_moment():
    model = FrameModel((FrameNode(0, 0), FrameNode(3, 0)),
                       (FrameElement(0, 1, 1, 0.2, 10000, offset=-0.5),), (), (0, 1, 2))
    result = FrameSolver(model).solve(FrameCase("Offset", (0, 0, 0, 10, 0, 0), (ElementLoad(),)))
    assert result.sections[0].axial == pytest.approx(10)
    assert abs(result.sections[0].moment) == pytest.approx(5)
    assert result.reactions[2] == pytest.approx(0, abs=1e-8)


def test_vertical_member_transform_and_compression_sign():
    model = FrameModel((FrameNode(0, 0), FrameNode(0, 3)),
                       (FrameElement(0, 1, 2, 0.3, 10000),), (), (0, 1, 2))
    result = FrameSolver(model).solve(FrameCase("Vertical", (0, 0, 0, 5, -12, 0), (ElementLoad(),)))
    assert result.displacements[3] == pytest.approx(5 * 3**3 / (3 * 10000 * 0.3))
    assert result.displacements[4] == pytest.approx(-12 * 3 / (10000 * 2))
    assert result.sections[0].axial == pytest.approx(-12)
    assert result.reactions[:3] == pytest.approx((-5, 12, 15))


def test_uniform_nodal_pressure_matches_winkler_settlement():
    model = FrameModel(tuple(FrameNode(index, 0) for index in range(4)),
                       tuple(FrameElement(index, index + 1, 1, 0.2, 10000) for index in range(3)),
                       tuple(VerticalSpring(index, 3000 * area, area)
                             for index, area in enumerate((0.5, 1, 1, 0.5))), (3,))
    force = tuple(value for spring in model.springs for value in (0, -12 * spring.tributary_area, 0))
    result = FrameSolver(model).solve(FrameCase("Uniforme nodal", force, (ElementLoad(),) * 3))
    assert result.displacements[1::3] == pytest.approx((-0.004,) * 4)
    assert all(abs(row.moment) < 1e-7 for row in result.sections)
