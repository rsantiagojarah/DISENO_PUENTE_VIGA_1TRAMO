"""Signed global envelope checks for the actual symmetric adopted reinforcement."""

from bridge_design.domain.connected_reinforcement import section_demands
from bridge_design.domain.connected_steel_audit import region_audit
from bridge_design.reporting.connected_case_groups import case_label
from bridge_design.reporting.deck_docx import _table, _body


def face_demands(region, demands):
    horizontal = region.startswith(("Zapata", "Losa", "Transicion"))
    faces = ("Inferior", "Superior") if horizontal else (
        ("Exterior", "Relleno") if region.endswith("izquierda") else ("Relleno", "Exterior"))
    return [(face, [d for d in demands if (d.moment >= 0 if index == 0 else d.moment < 0)])
            for index, face in enumerate(faces)]


def write_face_reinforcement(document, result, steel, demands):
    rows = []
    for face, selected in face_demands(steel.region, demands):
        strength = [d for d in selected if d.limit_state != "service"]
        if strength:
            trace = region_audit(result, steel, selected)
            required = max(steel.temperature_cm2_m,
                           *(max(r["flexural_area"], r["minimum_area"]) for r in trace["areas"]))
            critical = trace["flexure"]
            origin = case_label(critical["demand"]["case"])
            moment = critical["demand"]["moment"]
            ratio = critical["flexure_ratio"]
        else:
            required, moment, ratio, origin = steel.temperature_cm2_m, 0, 0, "Mínimo por temperatura"
        direction = "Longitudinal" if face in ("Superior", "Inferior") else "Vertical"
        rows.append((face, direction, f"{moment:.3f}", f"{required:.3f}",
                     f"{steel.bar_label} @ {steel.spacing_m:.3f}", f"{ratio:.3f}"))
        _body(document, f"{face}: gobierna {origin}; M={moment:.4f} tn·m/m; "
              f"As requerido={required:.4f} cm²/m; As colocado={steel.area_per_face_cm2_m:.4f} cm²/m.")
        rows.append((face, "Transversal", "—", f"{steel.temperature_cm2_m:.3f}",
                     f"{steel.transverse_bar_label} @ {steel.transverse_spacing_m:.3f}",
                     f"{steel.transverse_utilization:.3f}"))
    _table(document, ("Cara", "Dirección", "M tn·m/m", "As req cm²/m", "Barra @ s m", "Índice"),
           rows, widths=(24, 27, 23, 26, 42, 18), font_size=10)


def write_face_service(document, result, steel, demands):
    rows = []
    for face, selected in face_demands(steel.region, demands):
        service = [d for d in selected if d.limit_state == "service"]
        strength = [d for d in selected if d.limit_state != "service"]
        if not service:
            rows.append((face, "Sin tracción de servicio", "—", "—", "—", "—"))
            continue
        # region_audit requires a strength row; it cannot alter the service control.
        trace = region_audit(result, steel, selected if strength else service +
                             [next(d for d in demands if d.limit_state != "service")])
        row = trace["service"]
        rows.append((face, case_label(row["demand"]["case"]), f"{row['stress']:.2f}",
                     f"{row['stress_limit']:.2f}", f"{row['maximum_spacing']:.3f}",
                     "CUMPLE" if row["crack_ratio"] <= 1+1e-8 else "NO CUMPLE"))
    _table(document, ("Cara", "Servicio gobernante", "fs kgf/cm²", "fs límite", "s máx m", "Estado"),
           rows, widths=(23, 47, 24, 22, 20, 24), font_size=10)
