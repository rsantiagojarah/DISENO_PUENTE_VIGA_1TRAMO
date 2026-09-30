"""Independent geometry, Coulomb-wedge and free-body tests for inclined walls."""
from dataclasses import replace
from math import atan, cos, degrees, radians, sin, tan

import pytest

import bridge_design.domain.abutment as a
from bridge_design.domain.inclined_wall import stem_actions


def wall(theta=None, pga=0.3):
    geometry = a.pure_wall_geometry_inputs(a.AbutmentGeometryInputs(
        retained_height_m=7.25, footing_thickness_m=1.0, footing_width_m=5.0,
        toe_length_m=1.5, lower_stem_thickness_m=1.0, upper_stem_thickness_m=0.5,
        front_soil_depth_m=1.0,
    ))
    if theta is None:
        theta = 90.0 - degrees(atan(0.5 / 6.25))
    return a.AbutmentInputs(
        geometry=geometry, soil=a.AbutmentSoilInputs(wall_backface_angle_deg=theta, pga=pga),
        key=a.AbutmentKeyInputs(enabled=False), is_pure_wall=True,
    )


def polygon_centroid(points):
    crosses = [x*v-u*y for (x,y),(u,v) in zip(points, points[1:]+points[:1])]
    area = sum(crosses)/2
    x = sum((p[0]+q[0])*c for p,q,c in zip(points, points[1:]+points[:1], crosses))/(6*area)
    y = sum((p[1]+q[1])*c for p,q,c in zip(points, points[1:]+points[:1], crosses))/(6*area)
    return abs(area), x, y


@pytest.mark.parametrize("theta", [90.0, 88.0, None])
def test_actual_stem_and_soil_polygon_centroids(theta):
    data = wall(theta)
    g=data.geometry
    b=6.25*tan(radians(90-data.soil.wall_backface_angle_deg))
    area,x,y=polygon_centroid([(1.5,1),(2.5,1),(2.5-b,7.25),(2-b,7.25)])
    parts=tuple(c for c in a._concrete_components(data) if c.name in {"Pantalla rectangular", "Ensanche de pantalla"})
    w,cx,cy=a._resultant(parts)
    assert (w,cx,cy)==pytest.approx((area*2.4,x,y))
    area,x,y=polygon_centroid([(2.5,1),(5,1),(5,7.25),(2.5-b,7.25)])
    w,cx,cy=a._resultant(a._soil_components(data))
    assert (w,cx,cy)==pytest.approx((area*1.925,x,y))
    if theta is None:
        assert 2-b==pytest.approx(1.5)  # exposed face vertical


@pytest.mark.parametrize("theta", [90.0, 88.0, None])
@pytest.mark.parametrize("pga", [0.0, 0.3, 0.9])
def test_coefficients_against_independent_sliding_wedge(theta,pga):
    data=wall(theta,pga)
    phi=radians(data.soil.friction_angle_deg)
    alpha=radians(90-data.soil.wall_backface_angle_deg)
    kh=0.5*data.soil.fpga*pga
    # Equilibrium of triangular wedges. P balances weight, kh*W and the
    # frictional reaction on the failure plane. Maximise over slip angle rho.
    def coefficient(rho):
        return (1/tan(rho)+tan(alpha))*(kh+tan(rho-phi))/(cos(alpha)+sin(alpha)*tan(rho-phi))
    lo,hi=phi-atan(kh)+1e-8,radians(89.999)
    for _ in range(100):
        r1,r2=lo+(hi-lo)/3,hi-(hi-lo)/3
        if coefficient(r1)<coefficient(r2): lo=r1
        else: hi=r2
    independent=coefficient((lo+hi)/2)
    kae,_=a.mononobe_okabe_active_coefficient(data)
    assert kae==pytest.approx(independent,rel=1e-10)
    if pga==0:
        ka=a.coulomb_active_coefficient(30,0,0,data.soil.wall_backface_angle_deg)
        assert kae==pytest.approx(ka,rel=1e-12)


def test_global_virtual_plane_and_actual_stem_are_distinct():
    result=a.solve_abutment_design(wall())
    p=result.pressures
    assert p.ka==pytest.approx(1/3)
    assert p.stem_ka>p.ka
    assert p.stem_force_angle_deg==pytest.approx(degrees(atan(0.08)))
    # Surface load extends from the actual top of stem to the end of heel.
    assert p.lsy_tn_m==pytest.approx(3.0*0.6*1.925)
    assert not any("EH" in c.name for c in result.components.vertical_with_bridge)
    assert stem_actions(result.inputs,p)["eh_vertical"]>0


@pytest.mark.parametrize("cut", [0.0,2.0,6.0])
def test_stem_moments_against_numerical_pressure_integration(cut):
    result=a.solve_abutment_design(wall())
    data,p=result.inputs,result.pressures
    h=6.25-cut
    thickness=1-0.08*cut
    alpha=atan(0.08)
    n=4000
    dy=h/n
    horizontal=vertical=moment=0.0
    for i in range(n):
        y=(i+0.5)*dy
        force=p.stem_ka*1.925*(h-y)*dy
        horizontal+=force*cos(alpha)
        vertical+=force*sin(alpha)
        moment+=force*cos(alpha)*y-force*sin(alpha)*(thickness/2-0.08*y)
    actions=stem_actions(data,p,cut)
    assert actions["eh_horizontal"]==pytest.approx(horizontal)
    assert actions["eh_vertical"]==pytest.approx(vertical)
    assert actions["eh_moment"]==pytest.approx(moment,rel=2e-6)
    assert a._stem_design_limit_moments_at_height(data,p,cut)==pytest.approx((actions["strength_mu"],actions["extreme_mu"]))


def test_heel_and_stem_vertical_forces_close_global_equilibrium():
    result=a.solve_abutment_design(wall())
    inputs=result.inputs
    p=result.pressures
    actions=stem_actions(inputs,p)
    for state in result.with_bridge[:2]:
        f=state.load_factors
        heel=a._heel_state_demand(inputs,state)
        # Include all concrete except heel concrete, already in heel demand.
        other_concrete=result.dc_self_weight_tn_m-2.5*1.0*2.4
        stem_vertical=f.eh*actions["eh_vertical"]+f.ls_horizontal*actions["ls_vertical"]
        assembled=f.dc*other_concrete+heel.downward_shear_tn_m+stem_vertical
        assert assembled==pytest.approx(state.vu_tn_m,rel=1e-12)


def test_inclined_principal_bars_use_actual_length():
    data=wall()
    assert a._bar_detail_length_m(data,"Pantalla",50)==pytest.approx((6.25**2+0.5**2)**0.5+0.5)


@pytest.mark.parametrize("theta", [5,75,85.0])
def test_incompatible_angle_rejected(theta):
    with pytest.raises(ValueError,match="theta incompatible|angulo sismico"):
        wall(theta)


def test_sloping_fill_rejected_and_rough_interface_supported():
    with pytest.raises(ValueError,match="beta=0"):
        a.AbutmentSoilInputs(wall_backface_angle_deg=88,backfill_slope_deg=5)
    assert a.AbutmentSoilInputs(wall_backface_angle_deg=88,wall_soil_friction_deg=5).wall_soil_friction_deg == 5
    with pytest.raises(ValueError,match="diseno-muros"):
        replace(wall(),is_pure_wall=False)


def test_console_accepts_compatible_inclined_theta(monkeypatch):
    from bridge_design.cli.abutment_input_prompts import _collect_soil
    answers=iter(["0","","30","0","0","88","","0","",""])
    monkeypatch.setattr("builtins.input",lambda _:next(answers))
    assert _collect_soil(wall().geometry,element_label="muro").wall_backface_angle_deg==88


def test_yaml_and_report_distinguish_face_from_global_plane(tmp_path):
    from bridge_design.cli.yaml_inputs import cantilever_wall_yaml_template,cantilever_wall_inputs_from_yaml
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result
    from bridge_design.reporting.abutment_docx_detail import coulomb_ka_trace,mononobe_okabe_trace,stem_demand_trace
    from bridge_design.reporting.abutment_docx_charts import save_abutment_geometry
    data=cantilever_wall_yaml_template()
    data["suelo_sismo"]["theta_cara_posterior_desde_horizontal_grados"]=88
    result=a.solve_abutment_design(cantilever_wall_inputs_from_yaml(data))
    report=format_abutment_design_result(result)
    assert "theta del trasdos real" in report
    assert "plano virtual vertical" in report
    assert "vertical descendente" in report
    assert "88.000" in " ".join(coulomb_ka_trace(result,stem_face=True))
    assert "90.000" in " ".join(coulomb_ka_trace(result))
    assert "2.000" in " ".join(mononobe_okabe_trace(result,stem_face=True))
    assert "eh_vertical" in " ".join(stem_demand_trace(result))
    path=save_abutment_geometry(result,tmp_path/"inclined.png")
    assert path.stat().st_size>1000


def test_inclined_wall_word_report_uses_real_face_and_heel_transfer(tmp_path):
    from zipfile import ZipFile
    from xml.etree import ElementTree
    from bridge_design.reporting.abutment_docx import generate_abutment_docx

    result = a.solve_abutment_design(wall())
    path = generate_abutment_docx(result, tmp_path / "inclined-wall.docx")
    with ZipFile(path) as archive:
        # Calculation boxes contain nested tables and mathematical text nodes.
        text = " ".join(ElementTree.fromstring(archive.read("word/document.xml")).itertext())
    assert "Coulomb sobre trasdós real" in text
    assert "Mononobe-Okabe sobre trasdós real" in text
    assert "85.426" in text
    assert "eh_vertical" in text
    assert "Transferencia del relleno sobre trasdos" in text
