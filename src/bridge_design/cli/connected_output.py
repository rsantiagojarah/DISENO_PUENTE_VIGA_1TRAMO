"""ASCII results for continuous abutments; all checks consume domain results."""

from bridge_design.cli.ascii_tables import boxed_table


def format_connected_result(result):
    data, mesh = result.inputs, result.mesh
    lines = ["ANALISIS Y DISENO DE ESTRIBOS CONECTADOS - FRAME 2D - FRANJA 1.00 m",
             f"Nodos: {len(mesh.frame.nodes)} | Elementos: {len(mesh.frame.elements)} | Casos: {len(result.results)}",
             f"Longitud total: {data.total_length_m:.3f} m | Separacion libre: {data.clear_span_m:.3f} m",
             f"Ux=0: nodo {mesh.reference_node}, x={data.reference_position_m:.3f} m; Uy sobre resorte; giro libre.",
             f"ks={data.soil.subgrade_tn_m3:.3f} Tn/m3 | mu={data.soil.friction_coefficient:.3f} | qadm={data.soil.allowable_tn_m2:.3f} Tn/m2",
             f"Offsets: {'SI' if data.section_offsets else 'NO'} | Contacto solo a compresion | Empuje siempre activo.",
             "N positivo = traccion. Armadura principal simetrica en ambas caras.",
             "La restriccion central es idealizada; el deslizamiento se verifica independientemente.",
             "Presiones geotecnicas locales de Winkler; limite LRFD estimado como phi*FS*qadm."]
    rows = []
    for index, check in enumerate(result.foundation_checks, 1):
        rows.append((f"C{index:03d}", f"{check.horizontal_reaction:.3f}", f"{check.maximum_pressure:.3f}",
                     f"{check.maximum_settlement_mm:.3f}", f"{check.contact_length:.3f}",
                     check.sliding_status, check.bearing_status))
    lines.extend(boxed_table(("Caso", "Rx Tn", "qmax Tn/m2", "Asent. mm", "Contacto m", "Desliz.", "Presion"), rows,
                             title="CONTACTO Y ESTABILIDAD GLOBAL", row_separators=False))
    lines.extend(boxed_table(("Region", "Barra", "s m", "As/cara cm2/m", "N-M", "Corte", "Fisura", "Estado"),
        ((steel.region, steel.bar_label, f"{steel.spacing_m:.3f}", f"{steel.area_per_face_cm2_m:.3f}",
          f"{steel.axial_moment_utilization:.3f}", f"{steel.shear_utilization:.3f}",
          f"{steel.crack_utilization:.3f}", steel.status) for steel in result.reinforcement),
        title="ARMADURA PRINCIPAL POR CARA - INDICES DEMANDA/CAPACIDAD", row_separators=False))
    lines.extend(boxed_table(("Region", "Transversal por cara", "Indice temp.", "Ld recto cm", "Ldh cm", "Anclaje"),
        ((steel.region, f"{steel.transverse_bar_label} @ {steel.transverse_spacing_m:.3f} m",
          f"{steel.transverse_utilization:.3f}", f"{steel.required_straight_anchor_cm:.1f}",
          f"{steel.required_hook_anchor_cm:.1f}", steel.anchor_status)
         for steel in result.reinforcement), title="TEMPERATURA Y DESARROLLO", row_separators=False))
    if result.mesh_comparison:
        comparison = result.mesh_comparison
        lines.extend(["VERIFICACION DE MALLA",
            f"Paso {comparison.coarse_step:g} -> {comparison.fine_step:g} m; cambios relativos:",
            f"M: {comparison.moment_change:.2%}; qmax: {comparison.pressure_change:.2%}; asentamiento: {comparison.settlement_change:.2%}"])
    lines.append("IDENTIFICACION DE COMBINACIONES")
    lines.extend(f"C{index:03d}: {case.name}" for index, case in enumerate(result.results, 1))
    if any(steel.anchor_status != "OK RECTO" for steel in result.reinforcement):
        lines.append("El detalle de anclaje requiere las longitudes utiles por region y comprobacion de acomodo de ganchos.")
    return "\n".join(lines)
