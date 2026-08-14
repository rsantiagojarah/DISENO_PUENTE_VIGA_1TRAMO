"""Diseño de placas, pernos, soldaduras y anclaje al concreto para PEP.

Referencias:
- AASHTO LRFD Sec. 6.13 (pernos/soldaduras), 6.12 (placas)
- AASHTO 14.8 / MTC anclaje de apoyos
- ACI 318 Cap. 17 / metodologia de anclaje referida por AASHTO para concreto
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt

from bridge_design.domain.pep_bearing import PepCheck, PepExternalPlate
from bridge_design.validation.input_validators import require_positive

PHI_BOLT = 0.80
PHI_WELD = 0.80
PHI_PLATE_YIELD = 0.95
PHI_PLATE_SHEAR = 1.00
PHI_CONC_STEEL = 0.75
PHI_CONC_BREAKOUT = 0.70
MIN_EDGE_DIAMETERS = 1.5
MIN_SPACING_DIAMETERS = 3.0
PLATE_THICKNESSES_CM = (1.0, 1.2, 1.6, 2.0, 2.5, 3.0, 3.5, 4.0)
BOLT_DIAMETERS_CM = (1.6, 1.9, 2.2, 2.5, 3.2)
BOLT_COUNTS = (4, 6, 8)


@dataclass(frozen=True)
class BoltCoordinate:
    x_cm: float
    y_cm: float


@dataclass(frozen=True)
class PepAnchorDetail:
    n_bolts: int
    diameter_cm: float
    fy_kg_cm2: float
    fu_kg_cm2: float
    embedment_cm: float
    coordinates: tuple[BoltCoordinate, ...]
    fexx_kg_cm2: float = 4920.0  # E70 ~ 70 ksi
    weld_size_cm: float = 0.6
    concrete_edge_cm: float = 15.0
    layout_note: str = "rectangular fuera del PEP"

    def __post_init__(self) -> None:
        if self.n_bolts < 1:
            raise ValueError("n_bolts >= 1")
        if len(self.coordinates) != self.n_bolts:
            raise ValueError("Debe haber una coordenada por perno.")
        require_positive(self.diameter_cm, "diametro")
        require_positive(self.embedment_cm, "hef")
        require_positive(self.weld_size_cm, "garganta soldadura")

    @property
    def area_one_cm2(self) -> float:
        return pi * (self.diameter_cm**2) / 4.0


@dataclass(frozen=True)
class ComponentDemands:
    r_vertical_tn: float
    h_long_tn: float
    h_trans_tn: float
    t_uplift_tn: float
    moment_long_tn_m: float
    combination_id: str


def default_bolt_layout(
    n_bolts: int,
    plate_l_cm: float,
    plate_w_cm: float,
    pep_l_cm: float,
    pep_w_cm: float,
    diameter_cm: float = 2.0,
) -> tuple[BoltCoordinate, ...]:
    """Layout rectangular fuera del PEP, respetando borde >= 1.5d."""
    min_edge = MIN_EDGE_DIAMETERS * diameter_cm
    clear = max(0.75 * diameter_cm, 1.5)
    x_out = pep_l_cm / 2.0 + clear
    y_out = pep_w_cm / 2.0 + clear
    x_max = plate_l_cm / 2.0 - min_edge
    y_max = plate_w_cm / 2.0 - min_edge
    if x_max + 1e-9 < pep_l_cm / 2.0 or y_max + 1e-9 < pep_w_cm / 2.0:
        # Placa insuficiente para colocar pernos fuera del PEP con borde.
        return ()
    x_out = min(x_out, x_max)
    y_out = min(y_out, y_max)
    if n_bolts == 4:
        pts = [(-x_out, -y_out), (x_out, -y_out), (x_out, y_out), (-x_out, y_out)]
    elif n_bolts == 6:
        pts = [
            (-x_out, -y_out),
            (0.0, -y_out),
            (x_out, -y_out),
            (-x_out, y_out),
            (0.0, y_out),
            (x_out, y_out),
        ]
    else:
        pts = [
            (-x_out, -y_out),
            (0.0, -y_out),
            (x_out, -y_out),
            (x_out, 0.0),
            (x_out, y_out),
            (0.0, y_out),
            (-x_out, y_out),
            (-x_out, 0.0),
        ]
    return tuple(BoltCoordinate(x, y) for x, y in pts[:n_bolts])


def verify_plate(
    plate: PepExternalPlate,
    pep_l_cm: float,
    pep_w_cm: float,
    demands: ComponentDemands,
    label: str,
) -> list[PepCheck]:
    """Verifica placa externa (fluencia, corte, flexion de voladizo, bearing)."""
    combo = demands.combination_id
    checks: list[PepCheck] = []
    cover_ok = plate.length_cm + 1e-9 >= pep_l_cm and plate.width_cm + 1e-9 >= pep_w_cm
    checks.append(
        PepCheck(
            name=f"{label}: contiene PEP",
            articulo_mtc="MTC 2.10 compatibilidad",
            articulo_aashto="Detalle constructivo",
            estado_limite="Geometria",
            combination_id=combo,
            formula="L_p>=L ; W_p>=W",
            substitution=f"{plate.length_cm:.1f}>={pep_l_cm:.1f}; {plate.width_cm:.1f}>={pep_w_cm:.1f}",
            demand=0.0 if cover_ok else 1.0,
            limit=0.0,
            unit="-",
            status="OK" if cover_ok else "NO",
        )
    )
    area = plate.length_cm * plate.width_cm
    sigma = demands.r_vertical_tn * 1000.0 / area
    phi_fy = PHI_PLATE_YIELD * plate.fy_kg_cm2
    checks.append(
        PepCheck(
            name=f"{label}: fluencia por compresion",
            articulo_mtc="MTC acero / apoyo",
            articulo_aashto="AASHTO 6.12.2.2 (fluencia)",
            estado_limite="Resistencia",
            combination_id=combo,
            formula="R/A <= phi Fy",
            substitution=f"{demands.r_vertical_tn*1000:.0f}/{area:.1f} <= {PHI_PLATE_YIELD:.2f}*{plate.fy_kg_cm2:.0f}",
            demand=sigma,
            limit=phi_fy,
            unit="kg/cm2",
            status="OK" if sigma <= phi_fy + 1e-9 else "NO",
        )
    )
    h_res = sqrt(demands.h_long_tn**2 + demands.h_trans_tn**2)
    # Corte en seccion transversal de placa
    av = plate.thickness_cm * min(plate.length_cm, plate.width_cm)
    vn = 0.58 * plate.fy_kg_cm2 * av / 1000.0  # Tn
    phi_vn = PHI_PLATE_SHEAR * vn
    checks.append(
        PepCheck(
            name=f"{label}: corte",
            articulo_mtc="MTC acero",
            articulo_aashto="AASHTO 6.12.1.2.3 (corte)",
            estado_limite="Resistencia / EE",
            combination_id=combo,
            formula="H <= phi*0.58*Fy*Av",
            substitution=f"{h_res:.3f} <= {PHI_PLATE_SHEAR:.2f}*0.58*{plate.fy_kg_cm2:.0f}*{av:.1f}/1000",
            demand=h_res,
            limit=phi_vn,
            unit="Tn",
            status="OK" if h_res <= phi_vn + 1e-9 else "NO",
        )
    )
    # Flexion por voladizo del ala fuera del PEP (AASHTO 6.12 elementos de placa)
    overhang = max(
        (plate.length_cm - pep_l_cm) / 2.0,
        (plate.width_cm - pep_w_cm) / 2.0,
        0.0,
    )
    q = demands.r_vertical_tn * 1000.0 / max(pep_l_cm * pep_w_cm, 1e-9)  # kg/cm2
    # Franja de 1 cm: M = q * a^2 / 2  (kg-cm/cm)
    m_strip = q * overhang**2 / 2.0
    s_strip = plate.thickness_cm**2 / 4.0  # modulo plastico aprox Z/2 for rectangle = t^2/4 per cm
    mn = plate.fy_kg_cm2 * s_strip
    phi_mn = PHI_PLATE_YIELD * mn
    checks.append(
        PepCheck(
            name=f"{label}: flexion voladizo",
            articulo_mtc="MTC acero",
            articulo_aashto="AASHTO 6.12 (placa en voladizo bajo presion)",
            estado_limite="Resistencia",
            combination_id=combo,
            formula="M=q a^2/2 <= phi Fy (t^2/4)",
            substitution=f"a={overhang:.2f}; q={q:.2f}; M={m_strip:.2f}; phiMn={phi_mn:.2f}",
            demand=m_strip,
            limit=phi_mn,
            unit="kg-cm/cm",
            status="OK" if m_strip <= phi_mn + 1e-9 else "NO",
        )
    )
    # Bearing del perno sobre placa se verifica en grupo de anclajes; aqui aplastamiento local bajo PEP
    bearing_limit = PHI_PLATE_YIELD * 1.8 * plate.fy_kg_cm2  # limite practico local
    checks.append(
        PepCheck(
            name=f"{label}: aplastamiento local bajo PEP",
            articulo_mtc="MTC acero",
            articulo_aashto="AASHTO 6.13.2.9 analogia bearing",
            estado_limite="Resistencia",
            combination_id=combo,
            formula="sigma_pep <= phi*1.8 Fy",
            substitution=f"{demands.r_vertical_tn*1000/(pep_l_cm*pep_w_cm):.2f} <= {bearing_limit:.1f}",
            demand=demands.r_vertical_tn * 1000.0 / max(pep_l_cm * pep_w_cm, 1e-9),
            limit=bearing_limit,
            unit="kg/cm2",
            status=(
                "OK"
                if demands.r_vertical_tn * 1000.0 / max(pep_l_cm * pep_w_cm, 1e-9)
                <= bearing_limit + 1e-9
                else "NO"
            ),
        )
    )
    if demands.t_uplift_tn > 0:
        # traccion uniforme por uplift sobre area de placa
        sigma_t = demands.t_uplift_tn * 1000.0 / area
        checks.append(
            PepCheck(
                name=f"{label}: traccion por uplift",
                articulo_mtc="MTC anclaje",
                articulo_aashto="AASHTO 6.12.2.2",
                estado_limite="Evento Extremo",
                combination_id=combo,
                formula="T/A <= phi Fy",
                substitution=f"{demands.t_uplift_tn*1000:.0f}/{area:.1f} <= {phi_fy:.1f}",
                demand=sigma_t,
                limit=phi_fy,
                unit="kg/cm2",
                status="OK" if sigma_t <= phi_fy + 1e-9 else "NO",
            )
        )
    return checks


def verify_bolts_and_welds(
    anchors: PepAnchorDetail,
    demands: ComponentDemands,
    pep_l_cm: float,
    pep_w_cm: float,
    plate: PepExternalPlate,
) -> list[PepCheck]:
    """Pernos (corte/traccion/interaccion/flexion EE) y soldadura."""
    combo = demands.combination_id
    checks: list[PepCheck] = []
    n = anchors.n_bolts
    ab = anchors.area_one_cm2
    # Geometria: pernos fuera del PEP
    inside = 0
    for c in anchors.coordinates:
        if abs(c.x_cm) <= pep_l_cm / 2.0 + 1e-9 and abs(c.y_cm) <= pep_w_cm / 2.0 + 1e-9:
            inside += 1
    checks.append(
        PepCheck(
            name="Pernos fuera del PEP",
            articulo_mtc="MTC 2.10",
            articulo_aashto="Detalle constructivo",
            estado_limite="Geometria",
            combination_id=combo,
            formula="coordenadas fuera de L/2 x W/2 del PEP",
            substitution=f"pernos_dentro={inside}",
            demand=float(inside),
            limit=0.0,
            unit="-",
            status="OK" if inside == 0 else "NO",
            notes="Salvo excepcion aprobada, no atraviesan el neopreno.",
        )
    )
    # Distancias a borde de placa
    d = anchors.diameter_cm
    edge_ok = True
    min_edge = MIN_EDGE_DIAMETERS * d
    for c in anchors.coordinates:
        ex = plate.length_cm / 2.0 - abs(c.x_cm)
        ey = plate.width_cm / 2.0 - abs(c.y_cm)
        if ex + 1e-9 < min_edge or ey + 1e-9 < min_edge:
            edge_ok = False
    checks.append(
        PepCheck(
            name="Distancia a borde placa",
            articulo_mtc="MTC acero",
            articulo_aashto="AASHTO 6.13.2.6.6",
            estado_limite="Geometria",
            combination_id=combo,
            formula="e >= 1.5 d",
            substitution=f"e_min_req={min_edge:.2f} cm",
            demand=0.0 if edge_ok else 1.0,
            limit=0.0,
            unit="-",
            status="OK" if edge_ok else "NO",
        )
    )
    # Separacion minima
    spacing_ok = True
    coords = anchors.coordinates
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            dist = sqrt((coords[i].x_cm - coords[j].x_cm) ** 2 + (coords[i].y_cm - coords[j].y_cm) ** 2)
            if dist + 1e-9 < MIN_SPACING_DIAMETERS * d:
                spacing_ok = False
    checks.append(
        PepCheck(
            name="Separacion entre pernos",
            articulo_mtc="MTC acero",
            articulo_aashto="AASHTO 6.13.2.6.1",
            estado_limite="Geometria",
            combination_id=combo,
            formula="s >= 3 d",
            substitution=f"s_min_req={MIN_SPACING_DIAMETERS*d:.2f} cm",
            demand=0.0 if spacing_ok else 1.0,
            limit=0.0,
            unit="-",
            status="OK" if spacing_ok else "NO",
        )
    )

    vx = demands.h_long_tn / n
    vy = demands.h_trans_tn / n
    v_bolt = sqrt(vx**2 + vy**2)
    # Momento de grupo: distribuye H*e y M como fuerzas adicionales
    # excentricidad vertical tipica: espesor placa + h/2 no incluido aqui; se usa momento dado
    ix = sum(c.x_cm**2 for c in coords)
    iy = sum(c.y_cm**2 for c in coords)
    polar = ix + iy
    m_kgcm = demands.moment_long_tn_m * 1e5  # Tn-m -> kg-cm
    # Fuerza adicional por momento alrededor de eje transversal (produce Nx ~ My*x/I)
    t_moment = 0.0
    if polar > 1e-9:
        t_moment = max(abs(m_kgcm * c.x_cm / polar) for c in coords) / 1000.0  # Tn
    t_uplift = demands.t_uplift_tn / n
    t_bolt = t_uplift + t_moment

    # Capacidad acero perno
    rn_shear = 0.48 * ab * anchors.fu_kg_cm2 / 1000.0  # Tn, hilos en plano de corte
    pn_ten = anchors.fu_kg_cm2 * ab / 1000.0
    phi_rn = PHI_BOLT * rn_shear
    phi_pn = PHI_BOLT * pn_ten
    checks.append(
        PepCheck(
            name="Perno: corte",
            articulo_mtc="MTC 2.10 EE flex+corte",
            articulo_aashto="AASHTO 6.13.2.7",
            estado_limite="Resistencia / EE",
            combination_id=combo,
            formula="V <= phi*0.48 Ab Fu",
            substitution=f"{v_bolt:.3f} <= {PHI_BOLT:.2f}*0.48*{ab:.3f}*{anchors.fu_kg_cm2:.0f}/1000",
            demand=v_bolt,
            limit=phi_rn,
            unit="Tn",
            status="OK" if v_bolt <= phi_rn + 1e-9 else "NO",
        )
    )
    checks.append(
        PepCheck(
            name="Perno: traccion",
            articulo_mtc="MTC anclaje",
            articulo_aashto="AASHTO 6.13.2.10",
            estado_limite="Resistencia / EE",
            combination_id=combo,
            formula="T <= phi Fu Ab",
            substitution=f"{t_bolt:.3f} <= {PHI_BOLT:.2f}*{anchors.fu_kg_cm2:.0f}*{ab:.3f}/1000",
            demand=t_bolt,
            limit=phi_pn,
            unit="Tn",
            status="OK" if t_bolt <= phi_pn + 1e-9 else "NO",
        )
    )
    inter = 0.0
    if phi_pn > 0 and phi_rn > 0:
        inter = (t_bolt / phi_pn) ** 2 + (v_bolt / phi_rn) ** 2
    checks.append(
        PepCheck(
            name="Perno: interaccion corte-traccion",
            articulo_mtc="MTC 2.10.3.3.8",
            articulo_aashto="AASHTO 6.13.2.11",
            estado_limite="Evento Extremo",
            combination_id=combo,
            formula="(T/phiPn)^2+(V/phiRn)^2 <= 1",
            substitution=f"({t_bolt:.3f}/{phi_pn:.3f})^2+({v_bolt:.3f}/{phi_rn:.3f})^2={inter:.3f}",
            demand=inter,
            limit=1.0,
            unit="-",
            status="OK" if inter <= 1.0 + 1e-9 else "NO",
        )
    )
    # Flexion del esparrago por fuerza horizontal con brazo = espesor placa (EE)
    m_bolt = v_bolt * plate.thickness_cm  # Tn-cm
    # Modulo elastico I/c = pi d^3 / 32
    s_bolt = pi * d**3 / 32.0
    fb = (m_bolt * 1000.0) / max(s_bolt, 1e-12)  # kg/cm2
    fb_all = PHI_BOLT * anchors.fy_kg_cm2
    checks.append(
        PepCheck(
            name="Perno: flexion por EE (brazo t_placa)",
            articulo_mtc="MTC 2.10.3.3.8 (flex+corte)",
            articulo_aashto="AASHTO 6.13 / analogia flexion perno",
            estado_limite="Evento Extremo",
            combination_id=combo,
            formula="fb = M c / I <= phi Fy",
            substitution=f"M={m_bolt:.3f} Tn-cm; fb={fb:.1f}; phiFy={fb_all:.1f}",
            demand=fb,
            limit=fb_all,
            unit="kg/cm2",
            status="OK" if fb <= fb_all + 1e-9 else "NO",
        )
    )
    # Bearing perno-placa
    rn_brg = 2.4 * d * plate.thickness_cm * plate.fu_kg_cm2 / 1000.0
    phi_brg = 0.80 * rn_brg
    checks.append(
        PepCheck(
            name="Bearing perno-placa",
            articulo_mtc="MTC acero",
            articulo_aashto="AASHTO 6.13.2.9",
            estado_limite="Resistencia",
            combination_id=combo,
            formula="V <= phi*2.4 d t Fu",
            substitution=f"{v_bolt:.3f} <= 0.80*2.4*{d:.2f}*{plate.thickness_cm:.2f}*{plate.fu_kg_cm2:.0f}/1000",
            demand=v_bolt,
            limit=phi_brg,
            unit="Tn",
            status="OK" if v_bolt <= phi_brg + 1e-9 else "NO",
        )
    )
    # Soldadura filete alrededor del perno (circunferencia * garganta)
    throat = 0.707 * anchors.weld_size_cm
    le = pi * d
    rn_weld = 0.60 * anchors.fexx_kg_cm2 * throat * le / 1000.0
    phi_weld = PHI_WELD * rn_weld
    r_weld_demand = sqrt(v_bolt**2 + t_bolt**2)
    checks.append(
        PepCheck(
            name="Soldadura perno-placa",
            articulo_mtc="MTC acero",
            articulo_aashto="AASHTO 6.13.3 / AWS D1.5",
            estado_limite="Resistencia / EE",
            combination_id=combo,
            formula="R <= phi*0.6 Fexx*0.707*s*Le",
            substitution=(
                f"{r_weld_demand:.3f} <= {PHI_WELD:.2f}*0.6*{anchors.fexx_kg_cm2:.0f}*"
                f"{throat:.3f}*{le:.2f}/1000"
            ),
            demand=r_weld_demand,
            limit=phi_weld,
            unit="Tn",
            status="OK" if r_weld_demand <= phi_weld + 1e-9 else "NO",
            notes=f"Fuerza por soldadura={r_weld_demand:.3f} Tn",
        )
    )
    return checks


def verify_concrete_anchorage(
    anchors: PepAnchorDetail,
    demands: ComponentDemands,
    fc_kg_cm2: float,
) -> list[PepCheck]:
    """Anclaje al concreto (acero, breakout, pryout, interaccion)."""
    combo = demands.combination_id
    n = anchors.n_bolts
    ab = anchors.area_one_cm2
    hef = anchors.embedment_cm
    # Demandas por ancla
    v_ua = sqrt(demands.h_long_tn**2 + demands.h_trans_tn**2) / n
    n_ua = max(demands.t_uplift_tn, 0.0) / n

    # Acero
    n_sa = n * ab * anchors.fu_kg_cm2 / 1000.0
    v_sa = n * 0.60 * ab * anchors.fu_kg_cm2 / 1000.0
    phi_nsa = PHI_CONC_STEEL * n_sa
    phi_vsa = PHI_CONC_STEEL * v_sa

    # Breakout traccion ACI/AASHTO: Nb = k_c * sqrt(fc') * hef^1.5
    # k_c = 10 (SI N, mm) -> convertir: usar forma en kg, cm
    # Nb(kg) ≈ 7.0 * sqrt(fc) * hef^1.5  (calibracion practica SI->kg/cm)
    nb_one = 7.0 * sqrt(fc_kg_cm2) * (hef**1.5)
    # Factor de borde simplificado
    ca1 = anchors.concrete_edge_cm
    psi_ed = min(0.7 + 0.3 * ca1 / (1.5 * hef), 1.0) if hef > 0 else 1.0
    n_cbg = n * nb_one * psi_ed / 1000.0  # Tn (grupo aprox. sin solapamiento ANc)
    phi_ncb = PHI_CONC_BREAKOUT * n_cbg

    # Pryout: Vcp = k_cp * Ncp, k_cp=2.0 para hef>=6.5cm tipico
    k_cp = 2.0 if hef >= 6.5 else 1.0
    v_cp = k_cp * n_cbg
    phi_vcp = PHI_CONC_BREAKOUT * v_cp

    checks = [
        PepCheck(
            name="Anclaje: resistencia acero a traccion",
            articulo_mtc="MTC anclaje apoyos",
            articulo_aashto="AASHTO/ACI 318 Cap.17 (Nsa)",
            estado_limite="Resistencia / EE",
            combination_id=combo,
            formula="Nua <= phi n Ase Futa",
            substitution=f"{demands.t_uplift_tn:.3f} <= {PHI_CONC_STEEL:.2f}*{n}*{ab:.3f}*{anchors.fu_kg_cm2:.0f}/1000",
            demand=demands.t_uplift_tn,
            limit=phi_nsa,
            unit="Tn",
            status="OK" if demands.t_uplift_tn <= phi_nsa + 1e-9 else "NO",
        ),
        PepCheck(
            name="Anclaje: breakout concreto traccion",
            articulo_mtc="MTC anclaje",
            articulo_aashto="AASHTO/ACI 318 Cap.17 (Ncb)",
            estado_limite="Resistencia / EE",
            combination_id=combo,
            formula="Nua <= phi * psi * n * 7*sqrt(fc)*hef^1.5",
            substitution=f"{demands.t_uplift_tn:.3f} <= {phi_ncb:.3f}; hef={hef:.1f}; psi={psi_ed:.2f}",
            demand=demands.t_uplift_tn,
            limit=phi_ncb,
            unit="Tn",
            status="OK" if demands.t_uplift_tn <= phi_ncb + 1e-9 else "NO",
        ),
        PepCheck(
            name="Anclaje: resistencia acero a corte",
            articulo_mtc="MTC anclaje",
            articulo_aashto="AASHTO/ACI 318 Cap.17 (Vsa)",
            estado_limite="Resistencia / EE",
            combination_id=combo,
            formula="Vua <= phi n 0.6 Ase Futa",
            substitution=f"{sqrt(demands.h_long_tn**2+demands.h_trans_tn**2):.3f} <= {phi_vsa:.3f}",
            demand=sqrt(demands.h_long_tn**2 + demands.h_trans_tn**2),
            limit=phi_vsa,
            unit="Tn",
            status=(
                "OK"
                if sqrt(demands.h_long_tn**2 + demands.h_trans_tn**2) <= phi_vsa + 1e-9
                else "NO"
            ),
        ),
        PepCheck(
            name="Anclaje: pryout concreto",
            articulo_mtc="MTC anclaje",
            articulo_aashto="AASHTO/ACI 318 Cap.17 (Vcp)",
            estado_limite="Resistencia / EE",
            combination_id=combo,
            formula="Vua <= phi kcp Ncp",
            substitution=f"V={sqrt(demands.h_long_tn**2+demands.h_trans_tn**2):.3f}; phiVcp={phi_vcp:.3f}",
            demand=sqrt(demands.h_long_tn**2 + demands.h_trans_tn**2),
            limit=phi_vcp,
            unit="Tn",
            status=(
                "OK"
                if sqrt(demands.h_long_tn**2 + demands.h_trans_tn**2) <= phi_vcp + 1e-9
                else "NO"
            ),
        ),
    ]
    # Interaccion por ancla
    nn = min(phi_nsa / n, phi_ncb / n) if n else 0.0
    vn = min(phi_vsa / n, phi_vcp / n) if n else 0.0
    inter = 0.0
    if nn > 0 and vn > 0:
        inter = (n_ua / nn) ** 1.5 + (v_ua / vn) ** 1.5
    elif vn > 0:
        inter = (v_ua / vn) ** 1.5
    checks.append(
        PepCheck(
            name="Anclaje: interaccion corte-traccion",
            articulo_mtc="MTC 2.10.3.3.8",
            articulo_aashto="AASHTO/ACI 318 Cap.17",
            estado_limite="Evento Extremo",
            combination_id=combo,
            formula="(Nua/phiNn)^1.5+(Vua/phiVn)^1.5 <= 1",
            substitution=f"Nua={n_ua:.3f}; Vua={v_ua:.3f}; inter={inter:.3f}",
            demand=inter,
            limit=1.0,
            unit="-",
            status="OK" if inter <= 1.0 + 1e-9 else "NO",
        )
    )
    # Pullout simplificado: Np = 8 Abrg fc' ; Abrg ~ 1.5d cabeza tipica
    abrg = 1.5 * d_area_head(anchors.diameter_cm)
    np_one = 8.0 * abrg * fc_kg_cm2 / 1000.0
    phi_np = PHI_CONC_BREAKOUT * n * np_one
    checks.append(
        PepCheck(
            name="Anclaje: pullout",
            articulo_mtc="MTC anclaje",
            articulo_aashto="AASHTO/ACI 318 Cap.17 (Np)",
            estado_limite="Resistencia / EE",
            combination_id=combo,
            formula="Nua <= phi n 8 Abrg fc",
            substitution=f"{demands.t_uplift_tn:.3f} <= {phi_np:.3f}",
            demand=demands.t_uplift_tn,
            limit=phi_np,
            unit="Tn",
            status="OK" if demands.t_uplift_tn <= phi_np + 1e-9 else "NO",
        )
    )
    return checks


def d_area_head(diameter_cm: float) -> float:
    """Area de cabeza aproximada para pullout (1.5 veces area del vastago)."""
    return 1.5 * pi * (diameter_cm**2) / 4.0


def auto_design_plate(
    pep_l_cm: float,
    pep_w_cm: float,
    demands: ComponentDemands,
    fy: float = 2530.0,
    fu: float = 4080.0,
    margin_cm: float = 10.0,
) -> PepExternalPlate | None:
    """Busca espesor minimo de placa que cumpla verificaciones."""
    plate_l = pep_l_cm + margin_cm
    plate_w = pep_w_cm + margin_cm
    for t in PLATE_THICKNESSES_CM:
        plate = PepExternalPlate(plate_l, plate_w, t, fy, fu)
        checks = verify_plate(plate, pep_l_cm, pep_w_cm, demands, "Placa")
        if all(c.ok for c in checks):
            return plate
    return None


def auto_design_anchors(
    plate: PepExternalPlate,
    pep_l_cm: float,
    pep_w_cm: float,
    demands: ComponentDemands,
    fc_kg_cm2: float,
) -> tuple[PepAnchorDetail, PepExternalPlate] | None:
    """Busca n, diametro y hef; puede agrandar la placa para el layout."""
    for enlarge in (0.0, 5.0, 10.0, 15.0, 20.0):
        work = PepExternalPlate(
            length_cm=plate.length_cm + enlarge,
            width_cm=plate.width_cm + enlarge,
            thickness_cm=max(plate.thickness_cm, 1.6),
            fy_kg_cm2=plate.fy_kg_cm2,
            fu_kg_cm2=plate.fu_kg_cm2,
        )
        for n in BOLT_COUNTS:
            for d in BOLT_DIAMETERS_CM:
                for hef in (20.0, 25.0, 30.0, 35.0, 40.0):
                    coords = default_bolt_layout(
                        n,
                        work.length_cm,
                        work.width_cm,
                        pep_l_cm,
                        pep_w_cm,
                        diameter_cm=d,
                    )
                    if not coords:
                        continue
                    detail = PepAnchorDetail(
                        n_bolts=n,
                        diameter_cm=d,
                        fy_kg_cm2=4220.0,
                        fu_kg_cm2=6330.0,
                        embedment_cm=hef,
                        coordinates=coords,
                    )
                    checks = []
                    checks.extend(
                        verify_bolts_and_welds(detail, demands, pep_l_cm, pep_w_cm, work)
                    )
                    checks.extend(verify_concrete_anchorage(detail, demands, fc_kg_cm2))
                    if all(c.ok for c in checks):
                        return detail, work
    return None
