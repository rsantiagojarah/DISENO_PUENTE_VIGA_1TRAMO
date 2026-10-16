"""Independent checks of simultaneous backface and backfill inclinations."""

from dataclasses import replace
from io import BytesIO
from math import atan, cos, radians, sin, tan

import pytest
from docx import Document

from bridge_design.domain import abutment as a
from bridge_design.domain.inclined_wall import stem_actions, surcharge_geometry_factor
from bridge_design.cli import abutment_ascii_output as terminal
from bridge_design.reporting import abutment_docx as report
from bridge_design.reporting import abutment_docx_detail as trace


def wall(theta=None, beta=10., delta=10., pga=.3, heel=3.):
    base = a.pure_wall_inputs()
    g = replace(base.geometry, retained_height_m=8.3, footing_thickness_m=1.,
                footing_width_m=3.+heel, toe_length_m=2., lower_stem_thickness_m=1.,
                upper_stem_thickness_m=.5, front_soil_depth_m=1.)
    if theta is None:
        theta = a.wall_vertical_front_angle_deg(g)
    return replace(base, geometry=g, key=replace(base.key, enabled=False),
                   soil=replace(base.soil, wall_backface_angle_deg=theta, backfill_slope_deg=beta,
                                wall_soil_friction_deg=delta, pga=pga,
                                vehicular_surcharge_height_m=.6, pedestrian_surcharge_tn_m2=.25))


def polygon(points):
    pairs = list(zip(points, points[1:]+points[:1]))
    crosses = [x*v-u*y for (x,y),(u,v) in pairs]
    area = sum(crosses)/2
    cx = sum((p[0]+q[0])*c for (p,q),c in zip(pairs,crosses))/(6*area)
    cy = sum((p[1]+q[1])*c for (p,q),c in zip(pairs,crosses))/(6*area)
    return abs(area), cx, cy


def wedge_thrust(data, height, kh=0., surcharge=0.):
    """Maximise independent wedge force equilibrium, not the closed Ka equation."""
    phi = radians(data.soil.friction_angle_deg)
    beta = radians(data.soil.backfill_slope_deg)
    alpha = radians(90-data.soil.wall_backface_angle_deg)
    eps = alpha+radians(data.soil.wall_soil_friction_deg)
    s, m = tan(alpha), tan(beta)
    gamma = data.materials.soil_unit_weight_kg_m3/1000

    def thrust(rho):
        # Intersect slip line z=x*tan(rho) with surface z=h+(x+h*s)*m.
        x = height*(1+s*m)/(tan(rho)-m)
        area = x*height*(1+s*tan(rho))/2
        weight = gamma*area
        load = surcharge*(x+height*s)
        return (kh*weight+(weight+load)*tan(rho-phi))/(cos(eps)+sin(eps)*tan(rho-phi))

    lo, hi = max(phi-atan(kh), beta)+1e-8, radians(89.99999)
    for _ in range(110):
        l, r = lo+(hi-lo)/3, hi-(hi-lo)/3
        if thrust(l) < thrust(r):
            lo = l
        else:
            hi = r
    return thrust((lo+hi)/2)


@pytest.mark.parametrize('theta', [90., 88., None])
@pytest.mark.parametrize('beta', [0., 5., 15.])
@pytest.mark.parametrize('delta', [0., 10.])
@pytest.mark.parametrize('pga', [0., .3])
def test_both_coefficients_and_surcharge_against_independent_wedges(theta, beta, delta, pga):
    data = wall(theta, beta, delta, pga)
    p = a._soil_pressures(data, 0., 0., 0., 0.)
    h, gamma = 7.3, 1.925
    kh = .5*data.soil.fpga*pga
    assert .5*p.stem_k_ae*gamma*h*h == pytest.approx(wedge_thrust(data,h,kh), rel=1e-11)
    assert .5*p.stem_ka*gamma*h*h == pytest.approx(wedge_thrust(data,h), rel=1e-11)
    q = gamma*.6+.25
    actual = stem_actions(data,p)
    eps = radians(p.stem_force_angle_deg)
    total = (actual['eh_horizontal']+actual['ls_horizontal'])/cos(eps)
    assert total == pytest.approx(wedge_thrust(data,h,surcharge=q), rel=1e-11)


@pytest.mark.parametrize('theta', [88., None])
@pytest.mark.parametrize('beta', [5., 10., 19.])
@pytest.mark.parametrize('heel', [1., 3., 5.])
def test_combined_soil_polygon_and_heel_partition(theta, beta, heel):
    data = wall(theta,beta,heel=heel)
    b = 7.3*tan(radians(90-data.soil.wall_backface_angle_deg))
    m = tan(radians(beta))
    hv = 8.3+(heel+b)*m
    area,x,y = polygon([(3.,1.),(3.+heel,1.),(3.+heel,hv),(3.-b,8.3)])
    assert a._resultant(a._soil_components(data)) == pytest.approx((area*1.925,x,y), rel=1e-12)
    assert a.virtual_retained_height_m(data) == pytest.approx(hv)
    direct,dx,_ = polygon([(0.,0.),(heel,0.),(heel,hv-1.),(0.,7.3+b*m)])
    extra,ex,_ = polygon([(0.,0.),(0.,7.3+b*m),(-b,7.3)])
    weights = a._heel_weight_breakdown(data)
    assert weights.soil_weight_tn_m == pytest.approx(direct*1.925)
    assert weights.soil_arm_m == pytest.approx(dx)
    assert (direct+extra)*1.925 == pytest.approx(area*1.925)
    assert (direct*dx+extra*ex)*1.925 == pytest.approx(area*(x-3.)*1.925)


@pytest.mark.parametrize('cut', [0., 2., 6.])
def test_combined_stem_cut_pressure_moments(cut):
    data = wall()
    p = a._soil_pressures(data,0.,0.,0.,0.)
    h, s = 7.3-cut, .5/7.3
    thickness = 1.-s*cut
    eps = radians(p.stem_force_angle_deg)
    # Obtain static resultants from wedge equilibrium, including surcharge.
    eh = wedge_thrust(data,h)
    ls = wedge_thrust(data,h,surcharge=1.925*.6+.25)-eh
    n = 4000
    dy = h/n
    eh_m = ls_m = 0.
    for i in range(n):
        y = (i+.5)*dy
        lever = cos(eps)*y-sin(eps)*(thickness/2-s*y)
        eh_m += 2*eh/h**2*(h-y)*dy*lever
        ls_m += ls/h*dy*lever
    actual = stem_actions(data,p,cut)
    assert actual['eh_moment'] == pytest.approx(eh_m,rel=2e-6)
    assert actual['ls_moment'] == pytest.approx(ls_m,rel=1e-10)
    assert a._stem_design_limit_moments_at_height(data,p,cut) == pytest.approx((actual['strength_mu'],actual['extreme_mu']))


@pytest.mark.parametrize('theta', [88., None])
@pytest.mark.parametrize('beta', [5., 15.])
@pytest.mark.parametrize('delta', [0., 10.])
def test_combined_global_pressures_surcharge_arms_and_inertia(theta, beta, delta):
    result = a.solve_abutment_design(wall(theta,beta,delta))
    p = result.pressures
    b = 7.3*tan(radians(90-result.inputs.soil.wall_backface_angle_deg))
    hv = 8.3+(3+b)*tan(radians(beta))
    assert p.eh_tn_m == pytest.approx(.5*p.ka*1.925*hv**2)
    assert p.pae_tn_m == pytest.approx(.5*p.k_ae*1.925*hv**2)
    assert p.lsx_tn_m == pytest.approx(p.ka*(1.925*.6+.25)*hv)
    assert p.lsy_tn_m+p.pedestrian_lsy_tn_m == pytest.approx((3+b)*(1.925*.6+.25))
    ls = next(c for c in result.components.vertical_without_bridge if c.load_type=='LS')
    assert ls.arm_m == pytest.approx(3+(3-b)/2)
    horizontal = result.components.horizontal_without_bridge
    assert [c.arm_m for c in horizontal[:3]] == pytest.approx([hv/2,hv/3,hv/2])
    soil_area,_,soil_y = polygon([(3.,1.),(6.,1.),(6.,hv),(3-b,8.3)])
    first_y = sum(c.value_tn_m*c.vertical_arm_m for c in result.concrete_components)+soil_area*1.925*soil_y
    assert horizontal[3].moment_tn_m_m == pytest.approx(.5*.18*first_y)
    assert result.components.horizontal_without_bridge_seismic_b[2].moment_tn_m_m == pytest.approx(.18*first_y)


@pytest.mark.parametrize('delta', [0., 10.])
@pytest.mark.parametrize('pga', [0., .3, .9])
def test_incremental_heel_equilibrium_all_states(delta, pga):
    # beta=1 stays within the seismic domain even for PGA=.9, Fpga=1.2.
    result = a.solve_abutment_design(wall(beta=1.,delta=delta,pga=pga))
    data, p = result.inputs, result.pressures
    h,b,m = 7.3,.5,tan(radians(1.))
    h0 = h+b*m
    eps = radians(p.stem_force_angle_deg)
    gamma,q = 1.925,1.925*.6+.25
    extra,x,y = polygon([(0.,0.),(0.,h0),(-b,h)])
    wd,xd,_ = polygon([(0.,0.),(3.,0.),(3.,h0+3*m),(0.,h0)])
    real_ls = wedge_thrust(data,h,surcharge=q)-wedge_thrust(data,h)
    eh,pae = .5*p.stem_ka*gamma*h*h,.5*p.stem_k_ae*gamma*h*h
    eh0,pae0 = .5*p.ka*gamma*h0*h0,.5*p.k_ae*gamma*h0*h0
    states = result.without_bridge[:2]+result.extreme_seismic_without_bridge+result.service_without_bridge
    for state in states:
        f = state.load_factors
        is_b = state.seismic_papir_combination == a.SEISMIC_PAPIR_COMBO_B
        pairs = [(f.ls_horizontal,real_ls,h/2,p.ka*q*h0,h0/2)]
        if is_b:
            e,e0 = max(.5*pae,eh),max(.5*pae0,eh0)
            pairs.append((1.,e,h/3 if e<=eh+1e-12 else h/2,e0,h0/3 if e0<=eh0+1e-12 else h0/2))
        else:
            pairs += [(f.eh,eh,h/3,eh0,h0/3),(f.eq,pae-eh,h/2,pae0-eh0,h0/2)]
        face_v = sum(factor*force*sin(eps) for factor,force,_,_,_ in pairs)
        face_m = sum(factor*(force*(cos(eps)+sin(eps)*b/h)*z-ref*z0) for factor,force,z,ref,z0 in pairs)
        inertial_m = f.eq*(1. if is_b else .5)*(.5*data.soil.fpga*pga)*(extra*gamma)*y
        force = f.dc*7.2+f.ev*gamma*(wd+extra)+f.ls_vertical*q*(3+b)-face_v
        moment = f.dc*10.8+f.ev*gamma*(wd*xd+extra*x)+f.ls_vertical*q*(4.5-b*b/2)+face_m-inertial_m
        heel = a._heel_state_demand(data,state)
        assert heel.downward_shear_tn_m == pytest.approx(force,rel=1e-11)
        assert heel.downward_moment_tn_m_m == pytest.approx(moment,rel=1e-11)
        other_concrete = result.dc_self_weight_tn_m-7.2
        assert f.dc*other_concrete+heel.downward_shear_tn_m+face_v == pytest.approx(state.vu_tn_m,rel=1e-11)


@pytest.mark.parametrize('delta', [0., 10.])
@pytest.mark.parametrize('limit', ['theta', 'beta'])
def test_combined_model_has_continuous_vertical_and_horizontal_limits(delta, limit):
    data = wall(theta=90. if limit=='theta' else 88.,beta=10. if limit=='theta' else 0.,delta=delta)
    nearby = replace(data,soil=replace(data.soil,**({'wall_backface_angle_deg':90.-1e-7} if limit=='theta' else {'backfill_slope_deg':1e-7})))
    base = a.solve_abutment_design(data)
    near = a.solve_abutment_design(nearby)
    assert stem_actions(data,base.pressures) == pytest.approx(stem_actions(nearby,near.pressures),abs=1e-4)
    for left,right in zip(base.without_bridge[:2]+base.extreme_seismic_without_bridge,
                          near.without_bridge[:2]+near.extreme_seismic_without_bridge):
        l,r = a._heel_state_demand(data,left),a._heel_state_demand(nearby,right)
        assert l.downward_moment_tn_m_m == pytest.approx(r.downward_moment_tn_m_m,abs=1e-4)
        assert l.downward_shear_tn_m == pytest.approx(r.downward_shear_tn_m,abs=1e-4)
        assert l.moment_tn_m_m == pytest.approx(r.moment_tn_m_m,abs=1e-4)
        assert left.hu_tn_m == pytest.approx(right.hu_tn_m,abs=1e-4)
        assert left.vu_tn_m == pytest.approx(right.vu_tn_m,abs=1e-4)


def test_combined_word_and_terminal_reproduce_engine_geometry_loads_and_transfer():
    result = a.solve_abutment_design(wall())
    document = Document()
    report._configure_document(document)
    report._weights(document,result,report._labels(is_pure_wall=True))
    report._earth_pressures(document,result)
    report._structural_case(document,result,result.stem_design)
    report._structural_case(document,result,result.heel_design)
    stream = BytesIO()
    document.save(stream)
    stream.seek(0)
    text = ''.join(''.join(Document(stream).element.xpath('//*[local-name()="t"]/text()')).split())
    hv = 8.3+3.5*tan(radians(10.))
    assert f'{hv:.6f}' in text
    assert f'{1.925*3.5**2*tan(radians(10.))/2:.6f}' in text
    assert 'H0=Hp+b·tanβ' in text
    assert 'ΔM=Mpesos+Msobrecarga+Mcaras+Minercia' in text
    qfactor = surcharge_geometry_factor(result.inputs)
    assert f'Fq={qfactor:.8f}' in text
    pls = result.pressures.stem_ka*(1.925*.6+.25)*7.3*qfactor
    assert f'={pls:.6f}Tn/m' in text
    for formatter in (terminal._format_soil_pressure_procedure,terminal._format_pressures):
        output = '\n'.join(formatter(result))
        assert 'H + (Lt+b)*tan(beta)' in output
        assert f'{hv:.6f}' in output
    assert f'{qfactor:.8f}' in '\n'.join(terminal._format_wall_backface(result))
    htrace = trace.heel_toe_demand_trace(result,result.heel_design)[2]
    assert f'xβ,t = {a._heel_weight_breakdown(result.inputs).soil_slope_arm_m:.6f}' in htrace
