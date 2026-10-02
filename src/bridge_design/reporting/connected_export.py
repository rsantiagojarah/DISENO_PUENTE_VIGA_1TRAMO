"""Machine-readable, auditable input, mesh, loads, displacements and section results."""

import csv
import json
from dataclasses import asdict
from math import isfinite
from pathlib import Path

from bridge_design.cli.connected_output import format_connected_result


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
    (destination / "resumen.txt").write_text(format_connected_result(result), encoding="utf-8")
    (destination / "resultados.json").write_text(json.dumps(_json_value(asdict(result)), ensure_ascii=False,
                                                          indent=2, allow_nan=False), encoding="utf-8")
    model = result.mesh.frame
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
    return destination
