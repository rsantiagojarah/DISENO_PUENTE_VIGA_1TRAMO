"""Shared audit tables consumed by terminal, Word and JSON exports."""

from dataclasses import asdict, dataclass
from types import SimpleNamespace

from bridge_design.domain.abutment import _concrete_components, _soil_components
from bridge_design.domain.connected_reinforcement import section_demands
from bridge_design.domain.connected_steel_audit import region_audit
from bridge_design.reporting.abutment_docx_detail import concrete_geometry_rows


@dataclass(frozen=True)
class AuditTable:
    title: str
    headers: tuple
    rows: tuple
    note: str = ""


@dataclass(frozen=True)
class AuditStep:
    title: str
    formula: str
    legend: str
    substitution: str
    result: str
    comment: str
    reference: str


def number(value):
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def input_tables(result):
    data = result.inputs
    tables = []
    for block in ("geometry", "materials", "soil", "loads", "reinforcement"):
        left, right = asdict(getattr(data.left, block)), asdict(getattr(data.right, block))
        title = {"geometry": "Geometria", "materials": "Materiales", "soil": "Suelo y sismo",
                 "loads": "Cargas del tablero", "reinforcement": "Parametros de armado"}[block]
        tables.append(AuditTable(f"Entradas efectivas / {title}", ("Dato (unidad en clave)", "Izquierda", "Derecha"),
            tuple((key, number(value), number(right[key])) for key, value in left.items()),
            "m: metros; cm: centimetros; kg_cm2: kgf/cm2; kg_m3: kgf/m3; tn_m: Tn/m; deg: grados."))
    tables.append(AuditTable("Cimentacion y suelo comun", ("Dato", "Valor"),
        tuple((key, number(value)) for key, value in asdict(data).items()
              if not isinstance(value, (dict, list, tuple))) +
        tuple((f"suelo.{key}", number(value)) for key, value in asdict(data.soil).items()) +
        tuple((f"material_losa.{key}", number(value)) for key, value in asdict(data.slab_materials).items()),
        "Recubrimientos internos en cm. Longitudes de anclaje disponibles por region se detallan con el acero."))
    tables.append(AuditTable("Propiedades FRAME por elemento", ("Elem./region", "Nodos", "A m2", "I m4", "E Tn/m2", "Offset m"),
        tuple((f"{index}: {element.region}", f"{element.start}-{element.end}", number(element.area),
               number(element.inertia), number(element.modulus), number(element.offset))
              for index, element in enumerate(result.mesh.frame.elements)),
        "A = b*t; I = b*t^3/12; b = 1 m. Referencia horizontal y=0. E y offsets son los utilizados por el solucionador."))
    return tuple(tables)


def load_tables(result):
    tables = []
    for label, side in (("Izquierda", result.inputs.left), ("Derecha", result.inputs.right)):
        for kind, components in (("Concreto", _concrete_components(side)), ("Relleno", _soil_components(side))):
            gamma = (side.materials.concrete_unit_weight_kg_m3 if kind == "Concreto"
                     else side.materials.soil_unit_weight_kg_m3) / 1000
            # Fixed decimal places per numeric column make the comparison
            # readable. Keep full-precision domain values for every operation.
            rows = tuple((part.name, *(f"{value:.3f}" for value in (
                part.value_tn_m / gamma, gamma, part.value_tn_m, part.arm_m,
                part.value_tn_m * part.arm_m))) for part in components)
            tables.append(AuditTable(f"{label} / {kind}: descomposicion geometrica", ("Componente", "Area m2", "Gamma Tn/m3", "Peso Tn/m", "Brazo local m", "W*x Tn.m/m"),
                rows + (("SUMA", "-", "-", f"{sum(part.value_tn_m for part in components):.3f}", "-",
                         f"{sum(part.value_tn_m * part.arm_m for part in components):.3f}"),),
                "W = volumen de franja * peso unitario. Brazo local desde puntera, no coordenada global. "
                "Control geometrico del estribo individual; las acciones efectivamente ensambladas se muestran por combinacion."))
            if kind == "Concreto":
                tables.append(AuditTable(f"{label}: expresiones geometricas reutilizadas", ("Componente", "Area", "Area m2", "Brazo m"),
                    concrete_geometry_rows(SimpleNamespace(inputs=side, concrete_components=components)),
                    "ep=espesor parapeto; hc=altura parapeto; hb=altura bloque; Lc=longitud cajuela; "
                    "ht=altura transicion; es/ei=espesores pantalla; Hp'=altura rectangular; He=altura del ensanche; B,D=zapata."))
    parameters = result.earth_parameters
    tables.append(AuditTable("Coeficientes de empuje por lado", ("Parametro", "Izquierda", "Derecha"),
        tuple((key, number(getattr(parameters[0], key)), number(getattr(parameters[1], key)))
              for key in ("ka", "stem_ka", "k_ae", "stem_k_ae", "live_surcharge_height_m")),
        "Coulomb activo; ka: plano virtual; stem_ka: cara real. k_ae es referencia positiva; "
        "cada direccion sismica se ensambla separadamente en A/B. EH=Ka*gamma*H^2/2; "
        "LS=Ka*q*H. Los cuadros siguientes incluyen componentes verticales y transferencia al talon. "
        "Combinaciones globales: Ia o Ib se aplica a ambos estribos, losa y transiciones, sin cruces por region. "
        "Servicio I y Evento Extremo I tambien actuan simultaneamente sobre toda la estructura."))
    for index, (case, solved) in enumerate(zip(result.cases, result.results), 1):
        rows = tuple((name, number(factor), number(horizontal), number(vertical), number(moment))
                     for name, factor, horizontal, vertical, moment in case.load_trace)
        tables.append(AuditTable(f"C{index:03d}: {case.name}", ("Accion / lado", "Factor", "Fx base Tn", "Fy base Tn", "Mz base Tn.m"), rows,
            "DC: concreto; EV: relleno; BDC/DW/LL: tablero; BR: frenado; PIR: inercia; PEQ: sismo tablero. "
            "A=PAE+0.5PIR; B=max(0.5PAE,EH)+PIR (PIR en fila independiente). "
            "Factores incluyen sentido y escala de sobrecarga. Global +x derecha, +y arriba, +Mz antihorario. "
            "SUMA(factor*base): " + "; ".join(f"{name}={value:.6g}" for name, value in zip(
                ("Fx Tn", "Fy Tn", "Mz Tn.m"), solved.applied_resultant))))
    return tuple(tables)


def foundation_tables(result):
    tables = []
    springs = result.mesh.frame.springs
    for index, (case, check) in enumerate(zip(result.results, result.foundation_checks), 1):
        rows = []
        for spring, reaction in zip(springs, case.spring_reactions):
            vertical = case.displacements[3 * spring.node + 1]
            rows.append((str(spring.node), number(result.mesh.frame.nodes[spring.node].x),
                         number(spring.tributary_area), number(spring.stiffness), number(reaction),
                         number(reaction / spring.tributary_area), number(-1000 * vertical)))
        tables.append(AuditTable(f"C{index:03d}: contacto, presion y asentamiento", ("Nodo", "x m", "Area m2", "K Tn/m", "R Tn", "q Tn/m2", "s mm"),
            tuple(rows),
            f"K=ks*Area; R=max(0,-K*Uy); q=R/Area; s=-1000*Uy. qmax={check.maximum_pressure:.6g}; "
            f"limite={check.pressure_limit:.6g}; indice={check.bearing_utilization:.6g}; {check.bearing_status}. "
            "Servicio: limite=qadm; Resistencia/Extremo: limite=phi*FS*qadm (phi=0.55/0.80, aproximacion heredada). "
            f"Contacto={check.contact_length:.6g} m. Asentamientos sin limite admisible: NO VERIFICADOS. "
            f"Rx={check.horizontal_reaction:.6g} Tn; suma R={check.normal_reaction:.6g} Tn. "
            f"Residuos Fx,Fy,Mz={tuple(round(value, 9) for value in case.equilibrium_error)}; iteraciones={case.iterations}."))
    return tuple(tables)


def build_connected_audit(result):
    from bridge_design.reporting.connected_earth_trace import earth_steps
    from bridge_design.domain.connected_distributions import reinforcement_demands
    grouped = reinforcement_demands(result.inputs, result.mesh, result.results)
    return {"inputs": input_tables(result), "loads": load_tables(result),
            "earth": tuple(earth_steps(result)),
            "foundation": foundation_tables(result),
            "steel": {steel.region: region_audit(result, steel, grouped[steel.region]) for steel in result.reinforcement}}
