"""Bearing pressure from each solved structural case; limit by combination."""
from dataclasses import dataclass
from math import inf
from bridge_design.reporting.connected_case_groups import case_label, foundation_combination_groups
from bridge_design.reporting.connected_contact_envelope import contact_envelope
from bridge_design.reporting.connected_report_details import calculation
from bridge_design.reporting.deck_docx import _body, _table, _picture

@dataclass(frozen=True)
class BearingResult:
    width: float
    eccentricity: float
    effective_width: float
    pressure: float
    utilization: float
    status: str

def meyerhof_result(width, normal, resultant_x, pressure_limit):
    """Legacy auxiliary, never used as report demand."""
    eccentricity = width/2-resultant_x
    effective = width-2*abs(eccentricity)
    pressure = normal/effective if effective > 1e-9 and normal > 0 else inf
    utilization = pressure/pressure_limit
    return BearingResult(width, eccentricity, effective, pressure, utilization,
                         "CUMPLE" if utilization <= 1+1e-8 else "NO CUMPLE")

def spring_pressure_result(model, response):
    pressures = [r/s.tributary_area for s,r in zip(model.springs,response.spring_reactions)]
    index = max(range(len(pressures)), key=pressures.__getitem__)
    return index, pressures[index]

def write_case_bearing(document, result, response, check):
    data, model = result.inputs, result.mesh.frame
    index, maximum_pressure = spring_pressure_result(model, response)
    spring = model.springs[index]
    complies = maximum_pressure/check.pressure_limit <= 1+1e-8
    _body(document, "Presión máxima obtenida del análisis estructural de este caso, con su propio conjunto de resortes en contacto.")
    _table(document, ("Resultado del análisis", "Valor"), (
        ("q máximo", f"{maximum_pressure:.5f} tn/m² ({maximum_pressure/10:.5f} kgf/cm²)"),
        ("Nudo de presión máxima", str(spring.node)),
        ("Posición x del nudo", f"{model.nodes[spring.node].x:.5f} m"),
        ("Reacción del resorte R", f"{response.spring_reactions[index]:.5f} tn"),
        ("Área tributaria A", f"{spring.tributary_area:.6f} m²"),
        ("Contacto equivalente", f"{check.contact_length:.5f} m"),
        ("Asentamiento máximo", f"{check.maximum_settlement_mm:.5f} mm"),
        ("Levantamiento máximo", f"{check.maximum_uplift_mm:.5f} mm"),
    ), widths=(70, 90), font_size=10)
    phi = 1.0 if check.limit_state == "service" else (.8 if check.limit_state == "extreme" else .55)
    calculation(document, "Capacidad portante y presión límite factorizada",
                "q_lim = q_adm" if check.limit_state == "service" else "q_lim = phi_b*FS*q_adm",
                "q_lim: presión límite tn/m²; q_adm: presión admisible de servicio tn/m²; FS: factor nominal ingresado; phi_b: 0.55 en resistencia y 0.80 en evento extremo.",
                (f"q_lim=q_adm={check.pressure_limit:.5f} tn/m² (Servicio I)." if check.limit_state == "service" else
                 f"q_lim={phi:.2f}*{data.soil.nominal_bearing_fs:.3f}*{data.soil.allowable_tn_m2:.5f}={check.pressure_limit:.5f} tn/m²."),
                f"q_max del análisis={maximum_pressure:.5f} {'≤' if complies else '>'} q_lim={check.pressure_limit:.5f} tn/m²: {'CUMPLE' if complies else 'NO CUMPLE'}.",
                "La capacidad nominal se estima con FS·qadm. La demanda procede del análisis con resortes. Asentamientos sin verificación de un límite admisible.",
                "Manual de Puentes MTC 2018 criterios de capacidad portante del estado límite.")

def write_group_bearing(document, result, charts):
    checks = {check.case: check for check in result.foundation_checks}
    for index, group in enumerate(foundation_combination_groups(result),1):
        document.add_heading(f"7.{index}. {group.name}", level=2)
        _body(document, "Casos incluidos: " + "; ".join(case_label(c) for c in group.cases) + ".")
        _picture(document, charts[f"contacto_envolvente_{index}"],
                 f"Envolventes de presiones y asentamientos del suelo de {group.name}")
        points = contact_envelope(result, group)
        critical = max(points, key=lambda p:p['q_max'])
        check = checks[critical['q_case']]
        if any(abs(checks[name].pressure_limit-check.pressure_limit) > 1e-8 for name in group.cases):
            raise ValueError(f"{group.name}: los casos deben compartir q límite")
        maximum = critical['q_max']
        complies = maximum/check.pressure_limit <= 1+1e-8
        _body(document, f"q máximo de la envolvente={maximum:.3f} tn/m² "
              f"({maximum/10:.3f} kgf/cm²); nudo {critical['node']}; x={critical['x']:.3f} m. "
              f"Gobierna {case_label(critical['q_case'])}.")
        _body(document, f"Asentamiento máximo={max(p['s_max'] for p in points):.3f} mm; "
              f"levantamiento máximo={max(0,-min(p['s_min'] for p in points)):.3f} mm. "
              "Presiones y asentamientos proceden de las soluciones estructurales de la familia.")
        phi = 1.0 if group.limit_state == 'service' else (.8 if group.limit_state == 'extreme' else .55)
        soil = result.inputs.soil
        calculation(document, "Capacidad portante y presión límite factorizada",
                    "q_lim = q_adm" if group.limit_state == 'service' else "q_lim = phi_b*FS*q_adm",
                    "q_lim: presión límite tn/m²; q_adm: presión admisible de servicio tn/m²; "
                    "FS: factor nominal ingresado; phi_b: factor de resistencia de la familia.",
                    f"q_lim=q_adm={check.pressure_limit:.3f} tn/m²." if group.limit_state == 'service' else
                    f"q_lim={phi:.2f}*{soil.nominal_bearing_fs:.3f}*{soil.allowable_tn_m2:.3f}={check.pressure_limit:.3f} tn/m².",
                    f"q máximo de la envolvente={maximum:.3f} {'≤' if complies else '>'} "
                    f"q_lim={check.pressure_limit:.3f} tn/m²: {'CUMPLE' if complies else 'NO CUMPLE'}.",
                    "Se verifica la presión máxima de todos los casos "
                    "incluidos en la envolvente. Asentamientos sin límite admisible ingresado.",
                    "Manual de Puentes MTC 2018, Art. 2.8.1.1.12.2.")
