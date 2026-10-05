"""Método A MTC 2018 para apoyos rectangulares zunchados sin agujeros ni PTFE.

Un único registro de cálculo alimenta consola, Word y JSON. Las dimensiones
adoptadas se verifican sin corregirlas. La selección automática es discreta y
acotada. Una estimación elástica de compresión nunca acredita conformidad.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import product
import json
from math import ceil, isfinite, sqrt
import re

from bridge_design.domain.elastomeric_bearing import (
    BearingMovements, ElastomerGrade, compressive_strain, shape_factor_rectangular,
)

CALCULATION_VERSION = "metodo-a-serquen-2.0"
MTC_URL = "https://portal.mtc.gob.pe/transportes/caminos/normas_carreteras/manuales.html"
SIGMA_LIMIT = 87.9  # kgf/cm², 1.25 ksi redondeado según APOYOS.pdf
HS_MIN = 2.54 / 16  # cm, conversión exacta de 1/16 pulg
FATIGUE_LIMIT = 1687.0  # kgf/cm², categoría A


def _number(value: float, name: str, *, positive: bool = False) -> None:
    if isinstance(value, bool) or not isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError(f"{name}: se requiere un número finito {'positivo' if positive else 'no negativo'}.")


@dataclass(frozen=True)
class BearingAActions:
    dc_tn: float = 65.0
    dw_tn: float = 5.0
    ll_tn: float = 22.0
    pl_tn: float = 0.0
    im_tn: float = 0.0
    min_vertical_tn: float | None = None
    source: str = "Reacciones por apoyo ingresadas por el usuario"

    def __post_init__(self) -> None:
        for key in ("dc_tn", "dw_tn", "ll_tn", "pl_tn", "im_tn"):
            _number(getattr(self, key), key)
        if self.dc_tn + self.dw_tn <= 0:
            raise ValueError("La reacción permanente debe ser positiva; levantamiento fuera del alcance.")
        if self.min_vertical_tn is not None:
            _number(self.min_vertical_tn, "reacción mínima")
            if self.min_vertical_tn > self.dc_tn + self.dw_tn:
                raise ValueError("La reacción mínima no debe superar DC+DW.")
        if not self.source.strip():
            raise ValueError("Indique la procedencia de las reacciones.")


@dataclass(frozen=True)
class BearingAGeometry:
    width_cm: float = 45.0
    length_cm: float | None = None
    interior_cm: float | None = None
    exterior_cm: float | None = None
    interior_layers: int | None = None
    steel_cm: float | None = None
    max_length_cm: float = 120.0
    max_layers: int = 20
    nearly_square: bool = False
    principal_rotation_transverse: bool = True
    total_height_cm: float | None = None
    selection_mode: str = "medida"
    cover_cm: float = 0.0
    catalog_rotation_rad: float | None = None

    def __post_init__(self) -> None:
        for key in ("width_cm", "length_cm", "interior_cm", "exterior_cm", "steel_cm", "max_length_cm", "total_height_cm"):
            v = getattr(self, key)
            if v is not None:
                _number(v, key, positive=True)
        for key in ("interior_layers", "max_layers"):
            v = getattr(self, key)
            if v is not None and (type(v) is not int or not 1 <= v <= 100):
                raise ValueError(f"{key}: entero de 1 a 100.")
        if self.max_length_cm > 500:
            raise ValueError("La búsqueda automática admite un largo máximo de 500 cm.")
        if self.selection_mode not in {"medida", "usuales", "semirecubierto", "recubierto"}:
            raise ValueError("Selección: medida, usuales, semirecubierto o recubierto.")
        _number(self.cover_cm, "recubrimiento lateral")
        if self.width_cm <= 2*self.cover_cm or (self.length_cm is not None and self.length_cm <= 2*self.cover_cm):
            raise ValueError("El recubrimiento debe dejar un núcleo positivo.")
        if self.catalog_rotation_rad is not None:
            _number(self.catalog_rotation_rad, "rotación de catálogo")
        for key in ("nearly_square", "principal_rotation_transverse"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key}: se requiere verdadero o falso.")


@dataclass(frozen=True)
class CompressionCurve:
    """Tabla de producto o referencia: (S, sigma kgf/cm², epsilon decimal).

    Interpolación lineal en esfuerzo y S, sin extrapolación. Para reproducir
    el origen cada columna debe contener el punto (sigma=0, epsilon=0).
    """

    source: str
    hardness: int
    points: tuple[tuple[float, float, float], ...]
    kind: str = "fabricante"

    def __post_init__(self) -> None:
        if not self.source.strip() or self.kind not in {"fabricante", "referencia"}:
            raise ValueError("Curva: indique fuente y tipo fabricante o referencia.")
        if self.hardness not in (50, 60):
            raise ValueError("Curva: dureza 50 o 60.")
        if not self.points:
            raise ValueError("Curva vacía.")
        for s, stress, strain in self.points:
            _number(s, "S curva", positive=True)
            _number(stress, "esfuerzo curva")
            _number(strain, "deformación curva")
            if strain > 1:
                raise ValueError("epsilon se ingresa como decimal, no porcentaje.")
        for s in {p[0] for p in self.points}:
            column = sorted((p[1], p[2]) for p in self.points if p[0] == s)
            if len(column) < 2 or column[0] != (0.0, 0.0):
                raise ValueError("Cada S necesita origen (0,0) y al menos otro punto.")
            if any(b[0] <= a[0] or b[1] < a[1] for a, b in zip(column, column[1:])):
                raise ValueError("Curva: esfuerzos únicos crecientes y deformación no decreciente.")

    def lookup(self, shape: float, stress: float) -> tuple[float, str]:
        shapes = sorted({p[0] for p in self.points})
        if shape < shapes[0] - 1e-9 or shape > shapes[-1] + 1e-9:
            raise ValueError(f"S={shape:.6g} fuera de la tabla; no se extrapola.")
        lo = max(s for s in shapes if s <= shape + 1e-9)
        hi = min(s for s in shapes if s >= shape - 1e-9)

        def interp(s: float) -> tuple[float, str]:
            col = sorted((p[1], p[2]) for p in self.points if p[0] == s)
            if stress > col[-1][0] + 1e-9:
                raise ValueError(f"sigma={stress:.6g} excede la curva S={s}; no se extrapola.")
            for (x0, y0), (x1, y1) in zip(col, col[1:]):
                if x0 - 1e-9 <= stress <= x1 + 1e-9:
                    t = max(0.0, min(1.0, (stress - x0) / (x1 - x0)))
                    return y0 + t * (y1 - y0), f"S={s:g}: ({x0:.6g},{y0:.6g}) a ({x1:.6g},{y1:.6g}); t={t:.6g}"
            raise ValueError("Esfuerzo fuera de la curva.")

        a, ta = interp(lo)
        b, tb = interp(hi)
        t = 0.0 if hi == lo else (shape - lo) / (hi - lo)
        return a + t * (b - a), f"{ta}; {tb}; t_S={t:.6g}"


@dataclass(frozen=True)
class BearingAConnections:
    as_site: float = 0.20
    single_span: bool = True
    restrained_longitudinal: bool = False
    restrained_transverse: bool = True
    permanent_longitudinal_tn: float | None = None
    eq_longitudinal_tn: float | None = None
    eq_transverse_tn: float | None = None
    strength_longitudinal_tn: float = 0.0
    strength_transverse_tn: float = 0.0
    resistance_longitudinal_tn: float | None = None
    resistance_transverse_tn: float | None = None
    resistance_source: str = ""
    friction_mu: float = 0.2

    def __post_init__(self) -> None:
        for key, v in asdict(self).items():
            if key not in {"single_span", "restrained_longitudinal", "restrained_transverse", "resistance_source"} and v is not None:
                _number(v, key)
        if self.friction_mu > 1:
            raise ValueError("mu debe estar entre 0 y 1.")
        for key in ("single_span", "restrained_longitudinal", "restrained_transverse"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key}: se requiere verdadero o falso.")
        if (self.resistance_longitudinal_tn is not None or self.resistance_transverse_tn is not None) and not self.resistance_source.strip():
            raise ValueError("Toda resistencia de conexión necesita referencia a su memoria o certificado.")


@dataclass(frozen=True)
class BearingAInputs:
    actions: BearingAActions
    movements: BearingMovements
    geometry: BearingAGeometry
    connections: BearingAConnections
    hardness: int = 60
    fy_kg_cm2: float = 2530.0
    fc_kg_cm2: float = 210.0
    concrete_a2_cm2: float | None = None
    concrete_phi: float = 0.70
    compression_curve: CompressionCurve | None = None
    joint_limit_cm: float = 0.3175
    project: str = "Diseño de apoyo elastomérico"
    bearing_id: str = "A1"
    neoprene_only: bool = False
    compression_method: str = "elastico"

    def __post_init__(self) -> None:
        if self.compression_method not in {"elastico", "serquen"}:
            raise ValueError("Método de compresión: elastico o serquen.")
        if self.hardness not in (50, 60):
            raise ValueError("Sin PTFE este módulo admite Shore A 50 o 60; 70 fuera del alcance.")
        for key in ("fy_kg_cm2", "fc_kg_cm2", "concrete_phi", "joint_limit_cm"):
            _number(getattr(self, key), key, positive=True)
        if self.concrete_phi > 1:
            raise ValueError("phi no debe exceder 1.")
        if self.concrete_a2_cm2 is not None:
            _number(self.concrete_a2_cm2, "A2", positive=True)
        if self.compression_curve is not None and self.compression_curve.hardness != self.hardness:
            raise ValueError("La dureza de la curva no coincide con la del apoyo.")
        # Los validadores heredados no rechazan NaN: validar también aquí.
        for key in ("span_length_m", "gamma_tu", "alpha_per_c"):
            _number(getattr(self.movements, key), key, positive=True)
        for key in ("shrinkage_cm", "prestress_shortening_cm", "other_permanent_cm"):
            _number(getattr(self.movements, key), key)


@dataclass(frozen=True)
class CalculationStep:
    id: str
    section: str
    title: str
    formula: str
    legend: str
    substitution: str
    value: float | None
    unit: str
    reference: str
    limit: float | None = None
    status: str = "CALCULADO"
    note: str = ""
    strict: bool = False

    @property
    def ratio(self) -> float | None:
        return self.value / self.limit if self.value is not None and self.limit is not None and self.limit > 0 else None


@dataclass(frozen=True)
class BearingAResult:
    inputs: BearingAInputs
    adopted: BearingAGeometry
    steps: tuple[CalculationStep, ...]
    candidates: int
    selection_note: str
    input_sha256: str
    version: str = CALCULATION_VERSION

    def step(self, id: str) -> CalculationStep:
        return next(s for s in self.steps if s.id == id)

    def value(self, id: str) -> float:
        v = self.step(id).value
        if v is None:
            raise ValueError(f"{id} no tiene resultado numérico.")
        return v

    @property
    def checks(self) -> tuple[CalculationStep, ...]:
        return tuple(s for s in self.steps if s.status != "CALCULADO")

    @property
    def status(self) -> str:
        if any(s.status == "NO CUMPLE" for s in self.checks):
            return "NO CONFORME"
        if any(s.status == "PENDIENTE" for s in self.checks):
            return "PENDIENTE"
        if any(s.status == "CUMPLE (ESTIMADO)" for s in self.checks):
            return "ESTIMADO"
        if any(s.status == "REFERENCIAL" for s in self.checks):
            return "REFERENCIAL"
        return "CONFORME"

    @property
    def overall_ok(self) -> bool:
        return self.status == "CONFORME"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status
        data["steps"] = [dict(asdict(s), ratio=s.ratio) for s in self.steps]
        return data


def _evaluate(i: BearingAInputs, g: BearingAGeometry) -> tuple[CalculationStep, ...]:
    """Evaluar dimensiones completas sin mutaciones ni redondeo intermedio."""
    a, m, c = i.actions, i.movements, i.connections
    l, w, hi, he, n, hs = g.length_cm, g.width_cm, g.interior_cm, g.exterior_cm, g.interior_layers, g.steel_cm
    assert l is not None and hi is not None and he is not None and n is not None and hs is not None
    grade = ElastomerGrade.from_hardness(i.hardness)
    steps: list[CalculationStep] = []

    def add(id, section, title, formula, legend, substitution, value, unit, ref, *, limit=None, pending=False, note="", strict=False, referential=False, estimated=False):
        status = "CALCULADO"
        if limit is not None:
            ok = value is not None and (value < limit if strict else value <= limit + 1e-10)
            status = "CUMPLE" if ok else "NO CUMPLE"
            if ok and estimated:
                status = "CUMPLE (ESTIMADO)"
            if ok and referential:
                status = "REFERENCIAL"
        if pending:
            status = "PENDIENTE"
        # Redondeo exclusivo de presentación; valores numéricos sin modificar.
        substitution = re.sub(r"(?<![\w.])-?\d+\.\d{9,}(?:[eE][+-]?\d+)?", lambda match: f"{float(match.group()):.8g}", substitution)
        substitution = substitution.replace("None", "sin dato")
        steps.append(CalculationStep(id, section, title, formula, legend, substitution, value, unit, ref, limit, status, note, strict))
        return value

    sec = "Acciones y geometría"
    permanent = a.dc_tn + a.dw_tn
    total = permanent + a.ll_tn + a.pl_tn + a.im_tn
    pu = 1.25*a.dc_tn + 1.50*a.dw_tn + 1.75*(a.ll_tn + a.pl_tn + a.im_tn)
    lc, wc = l-2*g.cover_cm, w-2*g.cover_cm
    area = lc*wc
    add("P", sec, "Reacción vertical de servicio", "P = DC + DW + LL + PL + IM", "DC y DW: cargas permanentes (Tn); LL y PL: cargas vivas (Tn); IM: incremento dinámico (Tn)", f"P = {a.dc_tn:g} + {a.dw_tn:g} + {a.ll_tn:g} + {a.pl_tn:g} + {a.im_tn:g}", total, "Tn", "MTC 2.4.5.3.1 Servicio I; " + a.source)
    add("PU", sec, "Reacción vertical en Resistencia I", "Pu = 1.25 DC + 1.50 DW + 1.75 (LL + PL + IM)", "Pu: reacción mayorada (Tn); acciones: reacciones por apoyo (Tn)", f"Pu = 1.25 ({a.dc_tn:g}) + 1.50 ({a.dw_tn:g}) + 1.75 ({a.ll_tn+a.pl_tn+a.im_tn:g})", pu, "Tn", "MTC Tabla 2.4.5.3.1-1; envolvente vertical máxima")
    add("AREA", sec, "Área adoptada", "A = (L - 2 c) (W - 2 c)", "L y W: planta exterior; c: recubrimiento lateral sin zuncho (cm); A: núcleo efectivo (cm²)", f"A = ({l:g} - 2 ({g.cover_cm:g})) ({w:g} - 2 ({g.cover_cm:g}))", area, "cm²", "MTC 2.10.3.1; AASHTO 14.7.5.1")
    add("AREA_REQ", sec, "Área requerida por esfuerzo máximo", "A_req = 1000 P / 87.9", "P: reacción de servicio (Tn); 1000: kgf/Tn; A_req: área (cm²)", f"A_req = 1000 ({total:g}) / 87.9", total*1000/SIGMA_LIMIT, "cm²", "MTC 2.10.4.3.2-8", limit=area)
    sigma = total*1000/area
    add("SIGMA", sec, "Compresión de servicio", "sigma_s = 1000 P / A", "sigma_s: compresión (kgf/cm²); P: servicio (Tn); A: área (cm²)", f"sigma_s = 1000 ({total:g}) / {area:g}", sigma, "kgf/cm²", "MTC 2.10.4.3.2-8; AASHTO 14.7.6.3.2-8", limit=SIGMA_LIMIT)
    si, se = shape_factor_rectangular(lc,wc,hi), shape_factor_rectangular(lc,wc,he)
    for id, label, h, s in (("SI","interior",hi,si),("SE","exterior",he,se)):
        add(id, sec, f"Factor de forma {label}", "S = Lc Wc / (2 h (Lc + Wc))", "S: factor de forma; h: espesor de capa; Lc y Wc: núcleo efectivo sin recubrimiento lateral (cm)", f"S = {lc:g} ({wc:g}) / (2 ({h:g}) ({lc+wc:g}))", s, "-", "MTC 2.10.3.1; AASHTO 14.7.5.1-1")
    add("GS", sec, "Compresión limitada por factor de forma", "sigma_s <= 1.25 G_min S_i", "G_min: módulo mínimo (kgf/cm²); S_i: factor interior; sigma_s: kgf/cm²", f"{sigma:.6g} <= 1.25 ({grade.g_min_kg_cm2:g}) ({si:.6g})", sigma, "kgf/cm²", "MTC 2.10.4.3.2-7; Tabla 2.10.3.3.6-1", limit=1.25*grade.g_min_kg_cm2*si)
    sec = "Movimiento y composición"
    t = m.temperature
    coeff = m.alpha_per_c*m.span_length_m*100
    shortening = m.shrinkage_cm+m.prestress_shortening_cm+m.other_permanent_cm
    dc, de = coeff*t.contraction_delta_t_c+shortening, coeff*t.expansion_delta_t_c-shortening
    ds = m.service_shear_displacement_cm
    if m.use_install_to_min:
        movement_formula = "Delta_s = gamma_TU max(abs(d_c), abs(d_e))"
        movement_legend = "d_c: contracción térmica más acortamientos (cm); d_e: expansión térmica menos acortamientos (cm); gamma_TU: factor de movimiento"
        movement_substitution = f"d_c = {coeff:.6g} ({t.contraction_delta_t_c:g}) + {shortening:g} = {dc:.6g}; d_e = {coeff:.6g} ({t.expansion_delta_t_c:g}) - {shortening:g} = {de:.6g}; Delta_s = {m.gamma_tu:g} ({ds/m.gamma_tu:.6g})"
    else:
        movement_formula = "Delta_s = gamma_TU (100 alpha L (T_max - T_min) + d_perm)"
        movement_legend = "alpha: coeficiente térmico (1/C); L: longitud efectiva (m); 100: cm/m; temperaturas: C; d_perm: acortamientos (cm)"
        movement_substitution = f"Delta_s = {m.gamma_tu:g} (100 ({m.alpha_per_c:g}) ({m.span_length_m:g}) ({t.t_sup_c:g} - ({t.t_inf_c:g})) + {shortening:g})"
    add("DELTA", sec, "Envolvente del desplazamiento horizontal", movement_formula, movement_legend, movement_substitution, ds, "cm", "MTC 2.4.3.9.2 y 2.10.4.3.4; APOYOS.pdf pp. 234-235", note=("Rango térmico completo más acortamientos, conservador." if not m.use_install_to_min else "Envolvente desde la temperatura de instalación; gamma_TU aplicado al conjunto de movimientos como en la referencia."))
    hrt = n*hi+2*he
    add("HRT", sec, "Espesor total de elastómero", "h_rt = n h_ri + 2 h_re", "n: capas interiores; h_ri y h_re: espesores (cm)", f"h_rt = {n} ({hi:g}) + 2 ({he:g})", hrt, "cm", "MTC 2.10.4.1")
    add("SHEAR", sec, "Espesor requerido por corte", "2 Delta_s <= h_rt", "Delta_s: desplazamiento (cm); h_rt: elastómero total (cm)", f"2 ({ds:.6g}) <= {hrt:g}", 2*ds, "cm", "MTC 2.10.4.3.4-1", limit=hrt)
    add("EXTERIOR", sec, "Espesor de las capas exteriores", "h_re <= 0.70 h_ri", "h_re: exterior (cm); h_ri: interior (cm)", f"{he:g} <= 0.70 ({hi:g})", he, "cm", "MTC 2.10.4.1", limit=.7*hi)
    neff = n + (1 if he >= .5*hi else 0)
    scope_limit = 16.0 if g.nearly_square or abs(l-w)<1e-9 else (20.0 if n >= 3 else 22.0)
    add("NEFF", sec, "Número efectivo de capas", "n_eff = n + 2 b", "b: 0.5 si h_re >= 0.5 h_ri, o 0; n: interiores", f"n_eff = {n} + {1 if he >= .5*hi else 0}", neff, "-", "MTC 2.10.4.1")
    add("SCOPE", sec, "Aplicabilidad del Método A", "S_i^2 / n_eff < C", "C: límite 22 normativo; 20 para n >= 3 o 16 para casi cuadrados según comentario de la referencia", f"{si:.6g}^2 / {neff:g} < {scope_limit:g}", si**2/neff, "-", "MTC 2.10.4.1; APOYOS.pdf p. 229 C14.7.6.1", limit=scope_limit, strict=True)
    add("ROTATION", sec, "Dirección de rotación principal", "1 - r <= 0", "r: 1 si la rotación principal es alrededor del eje transversal; 0 si no lo es", f"1 - {1 if g.principal_rotation_transverse else 0} <= 0", 0.0 if g.principal_rotation_transverse else 1.0, "-", "MTC 2.10.4.1; APOYOS.pdf pp. 229 y 239", limit=0.0, note="Rotación implícita solo dentro del alcance geométrico del Método A; documentar paralelismo y giro de la viga.")
    hs_ser = 3*max(hi,he)*sigma/i.fy_kg_cm2
    hs_fat = 2*max(hi,he)*(a.ll_tn+a.pl_tn+a.im_tn)*1000/area/FATIGUE_LIMIT
    for id, title, formula, val, sub in (
        ("HS_SERVICE","Zuncho por servicio","h_s,req = 3 h_max sigma_s / Fy",hs_ser,f"3 ({max(hi,he):g}) ({sigma:.6g}) / {i.fy_kg_cm2:g}"),
        ("HS_FATIGUE","Zuncho por fatiga categoría A","h_s,req = 2 h_max sigma_LL / Delta_F_TH",hs_fat,f"2 ({max(hi,he):g}) ({(a.ll_tn+a.pl_tn+a.im_tn)*1000/area:.6g}) / {FATIGUE_LIMIT:g}"),
        ("HS_MIN","Espesor mínimo de zuncho","h_s,min = 2.54 / 16",HS_MIN,"2.54 / 16"),
    ):
        legend = "h_s,min: espesor mínimo de refuerzo (cm); 2.54: cm por pulgada" if id == "HS_MIN" else "h_max: capa más gruesa (cm); Fy y sigma: kgf/cm²; Delta_F_TH: 1687 kgf/cm² categoría A"
        add(id,sec,title,formula,legend,sub,val,"cm","MTC 2.10.3.3.5 / 2.10.4.3.7; APOYOS.pdf pp. 232-233",limit=hs)
    height = hrt+(n+1)*hs
    add("HEIGHT",sec,"Altura total del apoyo","H = h_rt + (n + 1) h_s","H: altura (cm); h_s: zuncho (cm); n+1: número de zunchos",f"H = {hrt:g} + ({n}+1) ({hs:g})",height,"cm","MTC 2.10.4.3.6")
    if g.total_height_cm is not None:
        add("HEIGHT_TARGET",sec,"Altura total propuesta","abs(H - H_propuesta) <= 0.000001",
            "H incluye todas las capas de elastómero y los zunchos; alturas en cm",
            f"abs({height:.8g} - {g.total_height_cm:g})",abs(height-g.total_height_cm),"cm",
            "Restricción geométrica propuesta por el usuario",limit=1e-6)
    for id, dim in (("STABILITY_L",l),("STABILITY_W",w)):
        add(id,sec,"Estabilidad en "+("L" if id.endswith("L") else "W"),"H <= d / 3","d: dimensión de planta (cm); H: altura total (cm)",f"{height:.6g} <= {dim:g} / 3",height,"cm","MTC 2.10.4.3.6",limit=dim/3)
    sec = "Compresión y deflexiones"
    strains = {}
    source_valid = i.compression_curve is not None
    compression_note = ""
    for layer,s in (("I",si),("E",se)):
        for load,stress in (("D",permanent*1000/area),("T",(total-a.im_tn)*1000/area)):
            id = "EPS_"+layer+load
            if i.compression_curve is not None:
                try:
                    eps, sub = i.compression_curve.lookup(s,stress)
                    ref = i.compression_curve.source
                    formula = "epsilon = e_0 + t (e_1 - e_0)"
                except ValueError as exc:
                    source_valid = False
                    compression_note = str(exc)
                    eps,sub,ref,formula = None,str(exc),i.compression_curve.source,"epsilon = interpolacion(S, sigma)"
            else:
                eps = compressive_strain(stress,grade.g_min_kg_cm2,s,grade.shape_factor_k)
                sub = f"{stress:.6g} / (3 ({grade.g_min_kg_cm2:g}) (1 + 2 ({grade.shape_factor_k:g}) ({s:.6g})^2))"
                ref = "Estimación elástica de predimensionamiento; no sustituye curvas de producto ni Fig. C14.7.6.3.3-1"
                formula = "epsilon_est = sigma / (3 G_min (1 + 2 k S^2))"
            strains[id] = eps
            add(id,sec,"Deformación "+layer+" por "+load,formula,"I y E: capa interior y exterior; D y T: permanente y total sin IM; epsilon: decimal; t: fracción interpolada",sub,eps,"-",ref)
    estimated = i.neoprene_only and i.compression_curve is None
    pending = not source_valid and not estimated
    referential = source_valid and i.compression_curve.kind == "referencia"
    add("STRAIN_CHECK",sec,"Deformación de capa interior sin impacto","epsilon_IT <= 0.09","epsilon_IT: deformación interior por DC+DW+LL+PL sin IM",f"epsilon_IT = {strains['EPS_IT']}",strains["EPS_IT"],"-","MTC 2.10.4.3.3",limit=.09,pending=(strains["EPS_IT"] is None or (i.compression_curve is None and not estimated)),referential=(i.compression_curve is not None and i.compression_curve.kind == "referencia"),estimated=estimated,note=("Cálculo automático con modelo elástico aproximado; no acredita propiedades del producto." if estimated else compression_note) or ("Faltan curvas de compresión trazables del producto." if pending else "Fuente: "+i.compression_curve.source))
    delta_d = None if strains["EPS_ID"] is None or strains["EPS_ED"] is None else n*hi*strains["EPS_ID"]+2*he*strains["EPS_ED"]
    delta_t = None if strains["EPS_IT"] is None or strains["EPS_ET"] is None else n*hi*strains["EPS_IT"]+2*he*strains["EPS_ET"]
    delta_ll = None if delta_d is None or delta_t is None else delta_t-delta_d
    creep = None if delta_d is None else grade.creep_ratio*delta_d
    for id,title,formula,v,sub in (
        ("DEF_D","Deflexión inicial permanente","delta_D = n h_ri epsilon_ID + 2 h_re epsilon_ED",delta_d,f"{n} ({hi:g}) ({strains['EPS_ID']}) + 2 ({he:g}) ({strains['EPS_ED']})"),
        ("DEF_T","Deflexión inicial total sin impacto","delta_T = n h_ri epsilon_IT + 2 h_re epsilon_ET",delta_t,f"{n} ({hi:g}) ({strains['EPS_IT']}) + 2 ({he:g}) ({strains['EPS_ET']})"),
        ("DEF_LL","Deflexión incremental por carga viva","delta_LL = delta_T - delta_D",delta_ll,f"{delta_t} - {delta_d}"),
        ("CREEP","Deflexión diferida por creep","delta_creep = C_d delta_D",creep,f"{grade.creep_ratio:g} ({delta_d})"),
    ):
        add(id,sec,title,formula,"delta: cm; epsilon: deformación decimal; C_d: razón creep de tabla por dureza",sub,v,"cm","MTC 2.10.3.3.6; Tabla 2.10.3.3.6-1")
    add("JOINT",sec,"Deflexión relativa en junta","delta_LL + delta_creep <= delta_lim","delta_lim: límite adoptado para la junta (cm); incluye creep de forma conservadora",f"{delta_ll} + {creep} <= {i.joint_limit_cm:g}",None if delta_ll is None or creep is None else delta_ll+creep,"cm","C14.7.5.3.6; APOYOS.pdf p. 238; límite recomendado de junta",limit=i.joint_limit_cm,pending=pending,referential=referential,estimated=estimated,note="Cálculo automático estimado; verificar compatibilidad con la junta real." if estimated else "Estimación pendiente de curvas" if pending else "Recomendación de junta adoptada; exigir compatibilidad con la junta real.")
    sec = "Fuerzas horizontales y conexiones"
    hu = grade.g_max_kg_cm2*area*ds/hrt/1000
    pmin = a.min_vertical_tn if a.min_vertical_tn is not None else a.dc_tn
    friction = c.friction_mu*pmin
    add("HU",sec,"Reacción horizontal por deformación","H_serv = G_max A Delta_s / (1000 h_rt)","G_max: kgf/cm²; A: cm²; Delta_s y h_rt: cm; H_serv: Tn",f"{grade.g_max_kg_cm2:g} ({area:g}) ({ds:.6g}) / (1000 ({hrt:g}))",hu,"Tn","MTC 2.10.2.1.1; AASHTO 14.6.3.1-2",note="Es una reacción, no una capacidad sísmica.")
    add("FRICTION",sec,"Fricción disponible en servicio","F_f = mu P_min","mu: fricción; P_min: mínima reacción concomitante (Tn); sin dato se usa solo DC",f"{c.friction_mu:g} ({pmin:g})",friction,"Tn","AASHTO C14.8.3.1; APOYOS.pdf p. 239")
    needs_anchor = hu > friction+1e-10
    add("SLIP",sec,"Deslizamiento o retención en servicio","H_serv <= R_ret","R_ret: fricción o resistencia documentada de retención; se exige H completo si la fricción resulta insuficiente",f"{hu:.6g} <= {friction:.6g}" if not needs_anchor else f"Retención para H completo = {hu:.6g}; resistencia = {c.resistance_longitudinal_tn}",hu,"Tn","MTC 2.10.4.3.8; AASHTO 14.8.3",limit=friction if not needs_anchor else c.resistance_longitudinal_tn,pending=needs_anchor and c.resistance_longitudinal_tn is None,note="Retención requerida con libertad de movimiento; no bloquear la expansión con el anclaje.")
    if i.neoprene_only:
        steps.pop()
        add("SLIP",sec,"Fricción del apoyo en servicio","H_serv <= F_f",
            "H_serv: reacción por deformación; F_f: fricción disponible, ambas en Tn",
            f"{hu:.6g} <= {friction:.6g}",hu,"Tn","APOYOS.pdf p. 239; C14.8.3.1",
            limit=friction,note="Fricción insuficiente: requiere retención externa, fuera de este dimensionamiento." if needs_anchor else "Fricción suficiente para esta comprobación de servicio.")
        return tuple(s for s in steps if s.id != "PU")
    for direction, restrained, explicit, strength, capacity in (
        ("L",c.restrained_longitudinal,c.eq_longitudinal_tn,c.strength_longitudinal_tn,c.resistance_longitudinal_tn),
        ("T",c.restrained_transverse,c.eq_transverse_tn,c.strength_transverse_tn,c.resistance_transverse_tn),
    ):
        tributary = c.permanent_longitudinal_tn if direction == "L" and c.permanent_longitudinal_tn is not None else permanent
        seismic = explicit if explicit is not None else (c.as_site*tributary if c.single_span and restrained else (0.0 if not restrained else None))
        if explicit is not None or (not c.single_span and restrained):
            seismic_formula = "F_EQ = F_EQ_analisis"
            seismic_legend = "F_EQ_analisis: demanda de conexión del análisis sísmico en la dirección considerada (Tn)"
            seismic_substitution = f"F_EQ = {explicit:g} Tn" if explicit is not None else "F_EQ_analisis: sin dato"
        elif restrained:
            seismic_formula = "F_EQ = As P_perm"
            seismic_legend = "As: aceleración del sitio; P_perm: carga tributaria (Tn); L y T: longitudinal y transversal"
            seismic_substitution = f"F_EQ = {c.as_site:g} ({tributary:g})"
        else:
            seismic_formula = "F_EQ = 0"
            seismic_legend = "Dirección declarada libre; no se asigna demanda sísmica automática de conexión"
            seismic_substitution = "F_EQ = 0; restricción declarada: no"
        add("EQ_"+direction,sec,"Fuerza sísmica de conexión "+direction,seismic_formula,seismic_legend,seismic_substitution,seismic,"Tn","MTC 2.4.3.11.8; 2.10.4.3.8",pending=seismic is None,note="Para varios tramos ingresar fuerzas del análisis sísmico. El cálculo automático As·P se limita a un tramo.")
        demand = None if seismic is None else max(seismic,strength,hu if direction=="L" and needs_anchor else 0.0)
        add("CONNECTION_"+direction,sec,"Resistencia externa de conexión "+direction,"F_req = max(F_EQ, H_RI, H_ret)","H_RI: envolvente horizontal de Resistencia I del análisis, incluyendo frenado y temperatura; H_ret: retención sin crédito de fricción; R: resistencia de diseño externa (Tn)",f"F_EQ = {seismic}; H_RI = {strength:g}; H_ret = {hu if direction=='L' and needs_anchor else 0:g}; R = {capacity}",demand,"Tn","MTC 2.10.3.3.7 / 2.10.4.3.8; "+c.resistance_source,limit=capacity if demand != 0 else 0.0,pending=demand is None or (demand>0 and capacity is None),note="Sin deducción de GA·Delta/h ni fricción del sismo; la capacidad debe incluir toda la trayectoria de carga y sus combinaciones.")
    sec = "Aplastamiento del concreto"
    a2 = i.concrete_a2_cm2 if i.concrete_a2_cm2 is not None else area
    add("A2",sec,"Área de soporte del pedestal","A1 <= A2","A1: área cargada (cm²); A2: área similar y concéntrica contenida en el pedestal (cm²)",f"{area:g} <= {a2:g}",area,"cm²","MTC 2.8.1.4",limit=a2,note="El usuario debe verificar geométricamente similitud, concentricidad y bordes de A2; por defecto A2=A1.")
    factor = min(sqrt(a2/area),2)
    capacity = i.concrete_phi*.85*i.fc_kg_cm2*area*factor/1000
    add("CONCRETE",sec,"Resistencia de apoyo del concreto","Pu <= phi 0.85 fc A1 min(sqrt(A2/A1),2) / 1000","Pu: Resistencia I (Tn); fc: kgf/cm²; A1 y A2: cm²; phi: factor de resistencia",f"{pu:.6g} <= {i.concrete_phi:g} (0.85) ({i.fc_kg_cm2:g}) ({area:g}) ({factor:.6g}) / 1000",pu,"Tn","MTC 2.8.1.4; AASHTO 5.7.5",limit=capacity)
    return tuple(steps)


def design_bearing_a(inputs: BearingAInputs) -> BearingAResult:
    """Verificar lo adoptado o buscar un candidato sin modificar datos manuales."""
    if inputs.compression_curve is None and inputs.compression_method == "serquen":
        from bridge_design.domain.serquen_bearings import serquen_compression_curve
        inputs = replace(inputs, compression_curve=serquen_compression_curve(inputs.hardness))
    g = inputs.geometry
    if g.selection_mode in {"semirecubierto", "recubierto"}:
        from bridge_design.domain.serquen_selection import select_catalog_bearing
        return select_catalog_bearing(inputs)
    payload = json.dumps(asdict(inputs),sort_keys=True,ensure_ascii=False,allow_nan=False)
    digest = sha256(payload.encode("utf-8")).hexdigest()
    fully_manual = all(getattr(g,k) is not None for k in ("length_cm","interior_cm","exterior_cm","interior_layers","steel_cm"))
    if fully_manual and g.selection_mode == "usuales":
        from bridge_design.domain.serquen_bearings import USUAL_LAYERS
        if g.interior_cm not in USUAL_LAYERS or abs(g.steel_cm-USUAL_LAYERS[g.interior_cm])>1e-9:
            raise ValueError("La pareja caucho/zuncho no pertenece a los espesores usuales de Serquén p.224; use modo medida para verificarla.")
    if fully_manual:
        return BearingAResult(inputs,g,_evaluate(inputs,g),1,"Geometría manual conservada exactamente; se verifican todos los incumplimientos.",digest)
    total = sum((inputs.actions.dc_tn,inputs.actions.dw_tn,inputs.actions.ll_tn,inputs.actions.pl_tn,inputs.actions.im_tn))
    start = max(1,ceil(total*1000/SIGMA_LIMIT/(g.width_cm-2*g.cover_cm)+2*g.cover_cm))
    lengths = (g.length_cm,) if g.length_cm is not None else tuple(float(x) for x in range(start,int(g.max_length_cm)+1))
    from bridge_design.domain.serquen_bearings import USUAL_LAYERS
    layers = (g.interior_cm,) if g.interior_cm is not None else (tuple(USUAL_LAYERS) if g.selection_mode == "usuales" else (.5,.8,1.0,1.2,1.5,2.0))
    counts = (g.interior_layers,) if g.interior_layers is not None else range(1,g.max_layers+1)
    best = None
    evaluated = 0
    for l in lengths:
        at_length = []
        steel_options = (g.steel_cm,) if g.steel_cm is not None else ((.2,.3,.4,.5,.6,.8,1.0) if g.total_height_cm is not None and g.selection_mode == "medida" else (None,))
        for hi,n,trial_hs in product(layers,counts,steel_options):
            he = g.exterior_cm if g.exterior_cm is not None else max((x for x in (.25,.4,.5,.8,1.0,1.2) if x<=.7*hi),default=.5*hi)
            sigma = total*1000/((l-2*g.cover_cm)*(g.width_cm-2*g.cover_cm))
            hs_req = max(HS_MIN,3*max(hi,he)*sigma/inputs.fy_kg_cm2,2*max(hi,he)*(inputs.actions.ll_tn+inputs.actions.pl_tn+inputs.actions.im_tn)*1000/((l-2*g.cover_cm)*(g.width_cm-2*g.cover_cm))/FATIGUE_LIMIT)
            hs = trial_hs if trial_hs is not None else max(.2,ceil(hs_req*10-1e-12)/10)
            if g.selection_mode == "usuales":
                if hi not in USUAL_LAYERS or (g.steel_cm is not None and abs(g.steel_cm-USUAL_LAYERS[hi])>1e-9):
                    continue
                hs = USUAL_LAYERS[hi]
            if g.total_height_cm is not None and g.exterior_cm is None:
                he = (g.total_height_cm - n*hi - (n+1)*hs)/2
                if he <= 0 or he > .7*hi + 1e-9:
                    continue
            candidate = replace(g,length_cm=l,interior_cm=hi,exterior_cm=he,interior_layers=n,steel_cm=hs)
            steps = _evaluate(inputs,candidate)
            evaluated += 1
            core = [s for s in steps if s.section not in {"Fuerzas horizontales y conexiones","Aplastamiento del concreto"}]
            if not any(s.status=="NO CUMPLE" for s in core):
                # A supplied curve must cover the selected geometry and stress.
                if inputs.compression_curve is not None and any(s.status=="PENDIENTE" for s in core):
                    continue
                at_length.append((next(s.value for s in steps if s.id=="HEIGHT"),n,hi,candidate,steps))
        if at_length:
            best = min(at_length,key=lambda t:(round(t[0],9),t[3].steel_cm,t[1],t[2]) if g.total_height_cm is not None else t[:3])
            break  # mínimo largo, luego altura y cantidad de capas
    if best is None and g.total_height_cm is not None:
        raise ValueError(f"No se encontró composición compatible con H total={g.total_height_cm:g} cm y L={g.length_cm if g.length_cm is not None else 'automático'} cm dentro de la búsqueda. Revise la altura, planta o capas; no se modifica la altura propuesta. H incluye elastómero y zunchos.")
    if best is None:
        raise ValueError("No existe candidato dentro de los límites de búsqueda y cobertura de curvas (Serquén: S entre 3 y 12). Aumente planta/límites o revise movimiento, capas y cobertura de curvas; no se altera la geometría ingresada.")
    return BearingAResult(inputs,best[3],best[4],evaluated,"Selección discreta: menor largo y altura; con H fija se prioriza menor espesor de acero, luego capas. Alcance: solo apoyo de neopreno. Modo: "+g.selection_mode if inputs.neoprene_only else "Selección discreta: menor largo, luego menor altura y número de capas; capacidades externas se verifican aparte.",digest)
