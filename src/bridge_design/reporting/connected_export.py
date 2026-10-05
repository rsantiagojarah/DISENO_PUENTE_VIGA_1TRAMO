"""Machine-readable, auditable input, mesh, loads, displacements and section results."""

import csv
import json
from dataclasses import asdict
from math import isfinite
from pathlib import Path

from bridge_design.cli.connected_audit_output import format_connected_audit
from bridge_design.cli.connected_output import format_connected_result
from bridge_design.domain.connected_reinforcement import DESIGN_SCOPE_NOTE
from bridge_design.reporting.connected_audit import build_connected_audit


def _json_value(value):
    if isinstance(value, float) and not isfinite(value):
        return "INF" if value > 0 else "-INF"
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def write_csv(path, headers, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)


def export_connected_results(result, directory):
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    audit = build_connected_audit(result)
    (destination / "resumen.txt").write_text(format_connected_result(result), encoding="utf-8")
    (destination / "auditoria.txt").write_text(format_connected_audit(result, audit), encoding="utf-8")
    trace = {key: [asdict(table) for table in audit[key]] for key in ("inputs", "loads", "foundation")}
    trace["steel"] = audit["steel"]
    trace["earth"] = [asdict(step) for step in audit["earth"]]
    payload = {**asdict(result), "design_scope": DESIGN_SCOPE_NOTE, "calculation_audit": trace}
    (destination / "resultados.json").write_text(json.dumps(_json_value(payload), ensure_ascii=False,
                                                          indent=2, allow_nan=False), encoding="utf-8")
    model = result.mesh.frame
    write_csv(destination / "cargas_combinadas.csv", ("caso", "accion", "factor", "Fx_base_Tn", "Fy_base_Tn", "Mz_base_Tn_m",
              "Fx_ponderada_Tn", "Fy_ponderada_Tn", "Mz_ponderado_Tn_m"),
              ((case.name, name, factor, horizontal, vertical, moment, factor * horizontal, factor * vertical, factor * moment)
               for case in result.cases for name, factor, horizontal, vertical, moment in case.load_trace))
    write_csv(destination / "elementos.csv", ("elemento", "nodo_i", "nodo_j", "region", "A_m2", "I_m4", "E_Tn_m2", "espesor_m", "offset_m"),
              ((index, element.start, element.end, element.region, element.area, element.inertia, element.modulus,
                element.depth, element.offset) for index, element in enumerate(model.elements)))
    springs = {spring.node: (index, spring) for index, spring in enumerate(model.springs)}

    def node_rows():
        for case_index, case in enumerate(result.results, 1):
            for index, node in enumerate(model.nodes):
                spring_index, spring = springs.get(index, (None, None))
                reaction = case.spring_reactions[spring_index] if spring else 0.0
                yield (f"C{case_index:03d}", case.name, index, node.x, node.y,
                       *case.displacements[3 * index:3 * index + 3], case.reactions[3 * index],
                       reaction, reaction / spring.tributary_area if spring else "",
                       spring.stiffness if spring else "", spring.tributary_area if spring else "")

    write_csv(destination / "nodos.csv", ("caso", "nombre", "nodo", "x_m", "y_m", "Ux_m", "Uy_m", "giro_rad",
              "Rx_Tn", "reaccion_vertical_Tn", "q_Tn_m2", "K_Tn_m", "area_tributaria_m2"), node_rows())
    write_csv(destination / "esfuerzos.csv", ("caso", "elemento", "region", "s_relativa", "N_traccion_Tn", "V_Tn", "M_centroidal_elemento_Tn_m"),
              ((f"C{case_index:03d}", row.element, model.elements[row.element].region, row.station,
                row.axial, row.shear, row.moment) for case_index, case in enumerate(result.results, 1) for row in case.sections))
    cuts = [(s.region, s.foundation_reinforcement_cut) for s in result.reinforcement if s.foundation_reinforcement_cut is not None]
    if cuts:
        write_csv(destination / "cortes_zapata.csv", ("distribucion", "estado", "criterio", "x_teorico_izq_m", "x_teorico_der_m",
            "x_corte_izq_m", "x_corte_der_m", "distancia_cara_interior_m", "ld_m", "prolongacion_m", "continuas", "cada_n",
            "As_remanente_cm2_m", "separacion_maxima_real_m", "tramos_adicionales_x_m"),
            ((region, c.status, c.reason, c.theoretical_left_m, c.theoretical_right_m, c.cutoff_left_m, c.cutoff_right_m,
              c.distance_from_inner_face_m, c.development_length_m, c.adopted_extension_m,
              c.pattern.continuing_bars if c.pattern else None, c.pattern.cycle_bars if c.pattern else None,
              c.pattern.remaining_area_cm2_m if c.pattern else None, c.pattern.maximum_gap_m if c.pattern else None,
              c.additional_intervals_m) for region, c in cuts))
        write_csv(destination / "zonas_zapata.csv", ("distribucion", "zona", "x_inicio_m", "x_fin_m", "armado", "As_cm2_m",
            "separacion_real_m", "Ms_local_Tn_m_m", "fs_kg_cm2", "fs_limite_kg_cm2", "s_fisuracion_limite_m",
            "indice_flexion", "indice_corte", "indice_fisuracion", "indice_minimo", "caso_servicio", "x_servicio_m", "estado"),
            ((region, z.name, z.start_m, z.end_m, z.reinforcement, z.area_cm2_m, z.maximum_gap_m,
              z.service_moment_tn_m_m, z.service_stress_kg_cm2, z.service_stress_limit_kg_cm2, z.crack_spacing_limit_m,
              z.flexural_utilization, z.shear_utilization, z.crack_utilization, z.minimum_utilization,
              z.service_case, z.service_x_m, z.status) for region, c in cuts for z in c.zones))
    return destination
