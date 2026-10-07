"""Independent wedge, pressure integration and free-body checks for delta > 0."""
from dataclasses import replace
from math import atan, cos, radians, sin, tan

import pytest

import bridge_design.domain.abutment as a
from bridge_design.domain.inclined_wall import stem_actions
from bridge_design.domain.wall_friction import abutment_actions, earth_actions
from test_inclined_wall import wall


@pytest.mark.parametrize("theta", [90.0, 88.0])
@pytest.mark.parametrize("delta", [0.0, 10.0, 20.0, 30.0])
@pytest.mark.parametrize("pga", [0.0, 0.3, 0.9])
def test_mtc_coefficients_against_independent_wedge(theta, delta, pga):
    data = wall(theta,pga)
    data = replace(data,soil=replace(data.soil,wall_soil_friction_deg=delta))
    phi, alpha = radians(30), radians(90-theta)
    direction = alpha+radians(delta)
    kh = 0.5*data.soil.fpga*pga
    # Unit-height triangular wedge: W=(cot(rho)+tan(alpha))/2.
    # Resolve the reaction inclined phi from the slip-plane normal and the
    # wall reaction inclined alpha+delta. Optimize the independent equilibrium.
    def coefficient(rho):
        return (1/tan(rho)+tan(alpha))*(kh+tan(rho-phi))/(cos(direction)+sin(direction)*tan(rho-phi))
    lo,hi=phi-atan(kh)+1e-8,radians(89.999)
    for _ in range(100):
        r1,r2=lo+(hi-lo)/3,hi-(hi-lo)/3
        if coefficient(r1)<coefficient(r2): lo=r1
        else: hi=r2
    kae,_=a.mononobe_okabe_active_coefficient(data)
    assert kae == pytest.approx(coefficient((lo+hi)/2),rel=1e-10)
    if pga==0:
        assert kae == pytest.approx(a.coulomb_active_coefficient(30,delta,0,theta),rel=1e-12)


@pytest.mark.parametrize("theta",[90,88])
@pytest.mark.parametrize("delta",[10,20])
@pytest.mark.parametrize("cut",[0,2,5])
def test_rough_wall_pressure_moments_by_numerical_integration(theta,delta,cut):
    data=wall(theta)
    data=replace(data,soil=replace(data.soil,wall_soil_friction_deg=delta))
    p=a._soil_pressures(data,1,1,1,1)
    h=data.geometry.stem_height_above_footing_m-cut
    thickness=a._stem_thickness_at_height_m(data,cut)
    alpha=radians(90-theta)
    direction=alpha+radians(delta)
    n=4000
    horizontal=vertical=moment=0
    for i in range(n):
        y=(i+0.5)*h/n
        force=p.stem_ka*1.925*(h-y)*h/n
        horizontal+=force*cos(direction)
        vertical+=force*sin(direction)
        moment+=force*(cos(direction)*y-sin(direction)*(thickness/2-tan(alpha)*y))
    result=stem_actions(data,p,cut)
    assert result["eh_horizontal"]==pytest.approx(horizontal)
    assert result["eh_vertical"]==pytest.approx(vertical)
    assert result["eh_moment"]==pytest.approx(moment,rel=2e-6)


@pytest.mark.parametrize("pure",[True,False])
@pytest.mark.parametrize("delta",[10,20])
def test_global_equilibrium_and_heel_reaction(pure,delta):
    data=wall(90) if pure else a.AbutmentInputs()
    rough=replace(data,soil=replace(data.soil,wall_soil_friction_deg=delta))
    smooth_result=a.solve_abutment_design(data)
    result=a.solve_abutment_design(rough)
    p=result.pressures
    # Static AND seismic virtual-plane coefficients must stay delta=0.
    assert (p.ka,p.k_ae)==pytest.approx((smooth_result.pressures.ka,smooth_result.pressures.k_ae))
    actions=stem_actions(rough,p) if pure else abutment_actions(rough,p)
    rows=None if pure else earth_actions(rough,p)
    for previous,state in zip(smooth_result.with_bridge,result.with_bridge):
        assert (state.vu_tn_m,state.hu_tn_m)==pytest.approx((previous.vu_tn_m,previous.hu_tn_m))
        f=state.load_factors
        if state.seismic_papir_combination==a.SEISMIC_PAPIR_COMBO_B:
            if pure:
                h=rough.geometry.stem_height_above_footing_m
                eb=max(0.5*p.stem_k_ae,p.stem_ka)*0.5*1.925*h*h
                earth_vertical=eb*sin(radians(delta))
            else:
                earth_vertical=rows["b"]["vertical"]
        else:
            earth_vertical=f.eh*actions["eh_vertical"]+f.eq*actions["eq_vertical"]
        face_vertical=earth_vertical+f.ls_horizontal*actions["ls_vertical"]
        heel=a._heel_state_demand(rough,state)
        smooth_heel=a._heel_state_demand(data,previous)
        assert heel.downward_shear_tn_m-smooth_heel.downward_shear_tn_m==pytest.approx(-face_vertical,abs=1e-9)


@pytest.mark.parametrize("cut",[0,1,3])
def test_abutment_straight_backface_force_and_eccentric_moment(cut):
    data=a.AbutmentInputs(
        geometry=replace(a.AbutmentGeometryInputs(),backfill_step_width_m=0),
        soil=a.AbutmentSoilInputs(wall_soil_friction_deg=20,pga=0),
    )
    p=a._soil_pressures(data,1,1,1,1)
    h=data.geometry.stem_height_above_footing_m-cut
    force=0.5*p.stem_ka*1.925*h*h
    eccentricity=a._stem_thickness_at_height_m(data,cut)/2
    rows=earth_actions(data,p,cut)
    assert rows["eh"]["horizontal"]==pytest.approx(force*cos(radians(20)))
    assert rows["eh"]["vertical"]==pytest.approx(force*sin(radians(20)))
    assert rows["eh"]["moment"]==pytest.approx(force*(cos(radians(20))*h/3-sin(radians(20))*eccentricity))
    expected=abutment_actions(data,p,cut)
    assert a._stem_design_limit_moments_at_height(data,p,cut)==pytest.approx((expected["strength_mu"],expected["extreme_mu"]))
    if cut==0:
        assert a._stem_service_moment(data,p)==pytest.approx(expected["service_mu"])


def test_smooth_abutment_limit_and_bridge_loads_preserved():
    data=a.AbutmentInputs()
    p=a._soil_pressures(data,1,1,1,1)
    actual=abutment_actions(data,p)
    reference=a._stem_design_demands(data,p)
    for key in reference:
        assert actual[key]==pytest.approx(reference[key])
    assert actual["service_mu"]==pytest.approx(a._stem_service_moment(data,p))
    for cut in (0,1,3):
        row=abutment_actions(data,p,cut)
        assert (row["strength_mu"],row["extreme_mu"])==pytest.approx(a._stem_design_limit_moments_at_height(data,p,cut))


@pytest.mark.parametrize("delta",[-1,31,float("nan"),float("inf")])
def test_invalid_friction_rejected(delta):
    with pytest.raises(ValueError):
        a.AbutmentSoilInputs(wall_soil_friction_deg=delta)


def test_mononobe_denominator_domain():
    with pytest.raises(ValueError,match="delta mas el angulo sismico"):
        a.AbutmentSoilInputs(friction_angle_deg=80,wall_soil_friction_deg=80)


@pytest.mark.parametrize("pure",[False,True])
def test_yaml_and_reports_carry_actual_and_virtual_delta(pure):
    from bridge_design.cli.yaml_inputs import (
        abutment_yaml_template,abutment_inputs_from_yaml,
        cantilever_wall_yaml_template,cantilever_wall_inputs_from_yaml,
    )
    from bridge_design.cli.abutment_ascii_output import format_abutment_design_result
    from bridge_design.reporting.abutment_docx_detail import coulomb_ka_trace,mononobe_okabe_trace,stem_demand_trace
    template=cantilever_wall_yaml_template() if pure else abutment_yaml_template()
    template["suelo_sismo"]["delta_muro_suelo_grados"]=15
    reader=cantilever_wall_inputs_from_yaml if pure else abutment_inputs_from_yaml
    result=a.solve_abutment_design(reader(template))
    assert result.inputs.soil.wall_soil_friction_deg==15
    for trace in (coulomb_ka_trace,mononobe_okabe_trace):
        assert "δ = 0.000" in trace(result)[2]
        assert "δ = 15.000" in trace(result,stem_face=True)[2]
    report=format_abutment_design_result(result)
    assert "vertical descendente" in report
    assert "15.000000 grados" in report
    assert "α=90°-θ+δ" in stem_demand_trace(result)[0]


def test_console_accepts_nonzero_delta(monkeypatch):
    from bridge_design.cli.abutment_input_prompts import _collect_soil
    answers=iter(["0","","30","","15","0","88","","0","",""])
    monkeypatch.setattr("builtins.input",lambda _:next(answers))
    assert _collect_soil(wall().geometry,element_label="muro").wall_soil_friction_deg==15


@pytest.mark.parametrize("theta", [90,88])
def test_wall_heel_moment_closes_with_face_forces_for_all_states(theta):
    data=wall(theta)
    rough=replace(data,soil=replace(data.soil,wall_soil_friction_deg=20))
    smooth_result=a.solve_abutment_design(data)
    result=a.solve_abutment_design(rough)
    h=data.geometry.stem_height_above_footing_m
    slope=tan(radians(90-theta))
    def face_moments(p):
        angle=radians(p.stem_force_angle_deg)
        def moment(force,y):
            return force*(cos(angle)+sin(angle)*slope)*y
        eh=0.5*p.stem_ka*1.925*h*h
        pae=0.5*p.stem_k_ae*1.925*h*h
        ls=p.stem_ka*p.live_surcharge_height_m*1.925*h
        return dict(ls=moment(ls,h/2),eh=moment(eh,h/3),eq=moment(pae-eh,h/2),
                    b=moment(max(0.5*pae,eh),h/3 if 0.5*pae<=eh else h/2))
    act,ref=face_moments(result.pressures),face_moments(smooth_result.pressures)
    for previous,state in zip(smooth_result.with_bridge+smooth_result.service_with_bridge,
                              result.with_bridge+result.service_with_bridge):
        f=state.load_factors
        expected=f.ls_horizontal*(act["ls"]-ref["ls"])
        if state.seismic_papir_combination==a.SEISMIC_PAPIR_COMBO_B:
            expected+=act["b"]-ref["b"]
        else:
            expected+=f.eh*(act["eh"]-ref["eh"])+f.eq*(act["eq"]-ref["eq"])
        actual=(a._heel_state_demand(rough,state).downward_moment_tn_m_m
                -a._heel_state_demand(data,previous).downward_moment_tn_m_m)
        assert actual==pytest.approx(expected,abs=1e-9)


def test_stepped_abutment_eccentricity_by_independent_integration():
    data=a.AbutmentInputs(soil=a.AbutmentSoilInputs(wall_soil_friction_deg=20))
    p=a._soil_pressures(data,1,1,1,1)
    g=data.geometry
    h=g.stem_height_above_footing_m
    end=h-g.seat_block_height_m-g.backwall_drop_m
    start=end-g.backwall_taper_height_m
    direction=radians(20)
    moment=0
    n=20000
    for i in range(n):
        y=(i+0.5)*h/n
        offset=g.backfill_step_width_m*min(max((y-start)/g.backwall_taper_height_m,0),1)
        force=p.stem_ka*1.925*(h-y)*h/n
        moment+=force*(cos(direction)*y-sin(direction)*(offset+g.lower_stem_thickness_m/2))
    assert earth_actions(data,p)["eh"]["moment"]==pytest.approx(moment,rel=1e-7)


def test_abutment_heel_moment_balances_face_about_the_root():
    data=a.AbutmentInputs()
    rough=replace(data,soil=replace(data.soil,wall_soil_friction_deg=20))
    old,new=a.solve_abutment_design(data),a.solve_abutment_design(rough)
    h=data.geometry.stem_height_above_footing_m
    centre_to_root=data.geometry.lower_stem_thickness_m/2
    for prev,state in zip(old.with_bridge+old.service_with_bridge,new.with_bridge+new.service_with_bridge):
        f=state.load_factors
        act,ref=earth_actions(rough,new.pressures),earth_actions(data,old.pressures)
        factors=[("ls",f.ls_horizontal)]
        factors+=([("b",f.eq)] if state.seismic_papir_combination==a.SEISMIC_PAPIR_COMBO_B
                  else [("eh",f.eh),("eq",f.eq)])
        # Move each independently integrated stem moment to the heel root.
        dm=sum(factor*(act[k]["moment"]+act[k]["vertical"]*centre_to_root-ref[k]["moment"])
               for k,factor in factors)
        actual=a._heel_state_demand(rough,state).downward_moment_tn_m_m-a._heel_state_demand(data,prev).downward_moment_tn_m_m
        assert actual==pytest.approx(dm,abs=1e-9)


@pytest.mark.parametrize("pure",[False,True])
def test_word_report_with_friction_generates_and_traces_delta(pure,tmp_path):
    from zipfile import ZipFile
    from xml.etree import ElementTree
    from bridge_design.reporting.abutment_docx import generate_abutment_docx
    data=wall() if pure else a.AbutmentInputs()
    data=replace(data,soil=replace(data.soil,wall_soil_friction_deg=15))
    result=a.solve_abutment_design(data)
    path=generate_abutment_docx(result,tmp_path/"friction.docx")
    with ZipFile(path) as archive:
        text=" ".join(ElementTree.fromstring(archive.read("word/document.xml")).itertext())
    # OMML equations split tokens into runs and insert additional whitespace.
    text=" ".join(text.split())
    assert "δ = 15.000" in text
    assert "δ = 0.000" in text
    assert "eh_vertical" in text
    assert "2.4.4.1.5.3-1" in text
    if not pure:
        assert "cara vertical equivalente del estribo" in text
        assert "Transferencia por friccion del trasdos" in text
