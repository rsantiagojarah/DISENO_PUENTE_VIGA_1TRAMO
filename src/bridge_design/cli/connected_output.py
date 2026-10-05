"""ASCII results for continuous abutments; all checks consume domain results."""

from types import SimpleNamespace
from bridge_design.domain.anchorage_status import anchorage_passes
from bridge_design.domain.connected_2_inputs import is_connected_2
from bridge_design.reporting.connected_2_geometry import connected_2_geometry_rows

from bridge_design.cli.abutment_ascii_output import _format_input_summary, _format_stem_reinforcement_cut_option
from bridge_design.cli.ascii_tables import audit_block_title, audit_subtitle, boxed_table, key_value_box
from bridge_design.domain.connected_reinforcement import DESIGN_SCOPE_NOTE
from bridge_design.domain.connected_distributions import reinforcement_demands
from bridge_design.domain.connected_steel_audit import region_audit
from bridge_design.reporting.connected_case_groups import case_label
from bridge_design.reporting.connected_cut_report import format_foundation_cut


def format_connected_result(result):
    data, mesh = result.inputs, result.mesh
    lines = [*audit_block_title("3", "ANALISIS Y DISENO DE ESTRIBOS CONECTADOS", 112),
             "FRAME 2D - FRANJA 1.00 m. N positivo = traccion. Armado comun para ambos estribos por cara y direccion.",
             DESIGN_SCOPE_NOTE]
    if is_connected_2(data):
        lines.append("ESTRIBOS CONECTADOS 2 - BASE UNIFORME - GEOMETRIA ver_2l.pdf EDITABLE")
    lines.extend(_input_summary(result))
    lines.extend(audit_subtitle("3.2", "CONTACTO Y CAPACIDAD PORTANTE", 112))
    lines.extend(("qmax del analisis con resortes: R / area tributaria.",
                  "Servicio: qlim=qadm. Resistencia: qlim=0.55*FS*qadm. Evento extremo: qlim=0.80*FS*qadm.",
                  "Asentamientos calculados; sin limite admisible ingresado, no se verifica su cumplimiento."))
    rows = []
    for check in result.foundation_checks:
        rows.append((case_label(check.case), f"{check.maximum_pressure:.3f}", f"{check.pressure_limit:.3f}",
                     f"{check.maximum_settlement_mm:.3f}", f"{check.contact_length:.3f}",
                     check.bearing_status))
    lines.extend(boxed_table(("Combinacion", "qmax Tn/m2", "qlim Tn/m2", "Asent. mm", "Contacto m", "Presion"), rows,
                             aligns=("left", "right", "right", "right", "right", "center")))
    force_rows = []
    for field, label, unit in (("axial", "N", "tn"), ("shear", "V", "tn"), ("moment", "M", "tn m")):
        records = [(getattr(section, field), case_label(case.name), section.element, section.station)
                   for case in result.results for section in case.sections]
        for name, record in (("Minimo", min(records)), ("Maximo", max(records))):
            value, case, element, station = record
            force_rows.append((label, name, f"{value:.4f} {unit}", case, element, f"{station:.3f}"))
    lines.extend(boxed_table(("Esfuerzo", "Extremo", "Valor", "Combinacion", "Elemento", "s/L"), force_rows,
                             title="3.3. ENVOLVENTE GENERAL DE TODAS LAS COMBINACIONES"))
    lines.extend(_steel_summary(result))
    if result.mesh_comparison:
        comparison = result.mesh_comparison
        lines.extend(["VERIFICACION DE MALLA",
            f"Resortes {comparison.coarse_nodes} -> {comparison.fine_nodes}; "
            f"paso de referencia {comparison.coarse_step:g} -> {comparison.fine_step:g} m; cambios relativos:",
            f"M: {comparison.moment_change:.2%}; qmax: {comparison.pressure_change:.2%}; asentamiento: {comparison.settlement_change:.2%}"])
    force_error = max(abs(value) for case in result.results for value in case.equilibrium_error[:2])
    moment_error = max(abs(case.equilibrium_error[2]) for case in result.results)
    lines.extend(("VERIFICACION DEL EQUILIBRIO NUMERICO",
                  f"Residuo maximo: fuerzas {force_error:.3e} tn; momentos {moment_error:.3e} tn m."))
    if any(not anchorage_passes(steel.anchor_status) for steel in result.reinforcement if steel.role == "primary"):
        lines.append("Las longitudes disponibles siguen el detalle continuo definido y sus recubrimientos. "
                     "NO CUMPLE indica que no alcanza ni ld recto ni ld gancho; falta de longitud indica PENDIENTE DETALLE.")
    lines.append("Los estados de anclaje comparan L disponible con ld recto y ld gancho por separado. "
                 "La alternativa con gancho requiere comprobar su acomodo y doblado en el detalle.")
    return "\n".join(lines)


def _input_summary(result):
    """Shared abutment data, with each side's simultaneous bridge reactions."""
    data, mesh = result.inputs, result.mesh
    lines = audit_subtitle("3.1", "DATOS INGRESADOS Y CONSIDERADOS", 112)
    for label, side in (("COMUN - ARMADO PARA AMBOS LADOS", data.left),):
        lines.extend(audit_subtitle("", f"ESTRIBO {label}", 112))
        if is_connected_2(data):
            lines.extend(key_value_box("GEOMETRIA COMUN - DIMENSIONES EN m", connected_2_geometry_rows(data)))
        else:
            lines.extend(_format_input_summary(SimpleNamespace(inputs=side)))
        material, soil = side.materials, side.soil
        lines.extend(key_value_box("MATERIALES, RELLENO Y SISMO", (
            ("Resistencia del concreto f'c", f"{material.concrete_strength_kg_cm2:.3f} kgf/cm2"),
            ("Fluencia del acero fy", f"{material.steel_yield_kg_cm2:.3f} kgf/cm2"),
            ("Peso unitario del concreto", f"{material.concrete_unit_weight_kg_m3:.3f} kgf/m3"),
            ("Peso unitario del relleno", f"{material.soil_unit_weight_kg_m3:.3f} kgf/m3"),
            ("Angulo de friccion interna del relleno", f"{soil.friction_angle_deg:.3f} grados"),
            ("Angulo de friccion muro-relleno", f"{soil.wall_soil_friction_deg:.3f} grados"),
            ("Pendiente del relleno", f"{soil.backfill_slope_deg:.3f} grados"),
            ("Angulo del trasdos desde la horizontal", f"{soil.wall_backface_angle_deg:.3f} grados"),
            ("PGA / Fpga", f"{soil.pga:.3f} / {soil.fpga:.3f}"),
            ("Altura equivalente de sobrecarga vehicular", "Automatica" if soil.vehicular_surcharge_height_m is None
             else f"{soil.vehicular_surcharge_height_m:.3f} m"),
            ("Frenado BR", f"{side.loads.braking_tn_m:.3f} tn/m"),
            ("Altura adicional del apoyo para brazo de frenado", f"{side.geometry.bridge_seat_to_bearing_height_m:.3f} m"),
        )))
    lines.extend(boxed_table(("Reaccion tn/m", "Izquierdo", "Derecho"),
        ((label, f"{getattr(data.left.loads, field):.3f}", f"{getattr(data.right.loads, field):.3f}")
         for field, label in (("pdc_tn_m", "PDC"), ("pdw_tn_m", "PDW"), ("ppl_tn_m", "PPL"),
                             ("pll_im_tn_m", "PLL+IM"), ("braking_tn_m", "BR"))),
        title="REACCIONES SIMULTANEAS DEL TABLERO POR LADO"))
    uniform = is_connected_2(data)
    foundation_rows = (("Espesor uniforme de zapata combinada", f"{data.slab_thickness_m:.3f} m"),) if uniform else (
        ("Espesor losa central", f"{data.slab_thickness_m:.3f} m"),
        ("Longitud transicion izquierda / derecha", f"{data.left_transition_m:.3f} / {data.right_transition_m:.3f} m"),
    )
    cover_row = ("Recubrimientos pantalla / zapata combinada", f"{data.left.reinforcement.stem_cover_cm:g} / "
                 f"{data.left.reinforcement.footing_cover_cm:g} cm") if uniform else (
        "Recubrimientos pantalla / zapata / losa", f"{data.left.reinforcement.stem_cover_cm:g} / "
        f"{data.left.reinforcement.footing_cover_cm:g} / {data.slab_cover_cm:g} cm")
    lines.extend(key_value_box("CIMENTACION CONTINUA Y MODELO", (
        ("Separacion libre / longitud total", f"{data.clear_span_m:.3f} / {data.total_length_m:.3f} m"),
        *foundation_rows,
        ("Condicion sin tablero", "SI" if data.include_without_bridge else "NO"),
        ("Nudos con resorte en cimentacion", len(mesh.frame.springs)),
        ("Nudos FRAME / elementos / casos", f"{len(mesh.frame.nodes)} / {len(mesh.frame.elements)} / {len(result.results)}"),
        ("Modulo de balasto ks", f"{data.soil.subgrade_tn_m3:.3f} tn/m3"),
        ("Presion admisible qadm", f"{data.soil.allowable_tn_m2:.3f} tn/m2"),
        ("FS de capacidad nominal", f"{data.soil.nominal_bearing_fs:.3f}"),
        ("Referencia horizontal Ux=0", f"Nudo {mesh.reference_node}; x={data.reference_position_m:.3f} m"),
        ("Contacto", "Resortes solo a compresion; Uy sin restriccion fija; giro libre"),
        ("Offsets de seccion", "SI" if data.section_offsets else "NO"),
        cover_row,
    )))
    return lines


def _status(ratio):
    return "OK" if ratio <= 1+1e-8 else "NO CUMPLE"


def _number(row, key, unit=""):
    value = row.get(key)
    return "No disponible" if value is None else f"{value:.3f}{(' '+unit) if unit else ''}"


def _source(row):
    demand = row["demand"]
    return f"{row['region']}; {case_label(demand['case'])}; elemento {demand['element']}; s/L={demand['station']:.3f}; {row['face']}"


def _steel_summary(result):
    """Display actual demand/capacity values after selection, using the report audit."""
    grouped = reinforcement_demands(result.inputs, result.mesh, result.results)
    traces = {steel.region: region_audit(result, steel, grouped[steel.region]) for steel in result.reinforcement}
    lines = audit_subtitle("3.4", "ARMADURA PRINCIPAL POR CARA - FLEXION Y CORTANTE", 112)
    lines.append("Armado comun colocado en ambos estribos. Cada comprobacion conserva el lado, la seccion "
                 "y la combinacion gobernante de la envolvente general.")
    for steel in result.reinforcement:
        if steel.role != "primary":
            continue
        trace = traces[steel.region]
        flexure, shear = trace["flexure"], trace["shear"]
        service = trace["service"]
        lines.extend(key_value_box(f"DISENO ESTRUCTURAL - {steel.region}", (
            ("Acero principal elegido por cara", f"{steel.bar_label} @ {steel.spacing_m:.3f} m"),
            ("As requerido flexion / capacidad minima / temperatura", f"{steel.flexural_as_cm2_m:.3f} / "
             f"{steel.capacity_minimum_as_cm2_m:.3f} / {steel.temperature_cm2_m:.3f} cm2/m"),
            ("As requerido / As proporcionado por cara", f"{steel.required_as_cm2_m:.3f} / {steel.area_per_face_cm2_m:.3f} cm2/m"),
            ("Flexion - seccion gobernante", _source(flexure)),
            ("Mu de la seccion", _number(flexure['demand'], 'moment', 'tn m/m')),
            ("Peralte efectivo d en flexion", _number(flexure, 'effective', 'cm')),
            ("Md con capacidad minima / Mr resistente", f"{_number(flexure, 'required_moment')} / "
             f"{_number(flexure, 'capacity')} tn m/m"),
            ("Estado flexion (Md/Mr)", f"{steel.flexural_utilization:.3f} - {_status(steel.flexural_utilization)}"),
            ("Cortante - seccion gobernante", _source(shear)),
            ("Vu de la seccion", _number(shear['demand'], 'shear', 'tn/m')),
            ("Peralte efectivo dv en cortante", _number(shear, 'shear_depth', 'cm')),
            ("Coeficiente beta de cortante", _number(shear, 'beta')),
            ("Vr resistente", _number(shear, 'shear_capacity', 'tn/m')),
            ("Estado cortante (abs(Vu)/Vr)", f"{steel.shear_utilization:.3f} - {_status(steel.shear_utilization)}"),
            ("Servicio - seccion gobernante", _source(service) if service else "Sin casos de servicio"),
            ("Estado flexion, cortante, servicio y minimos", steel.status),
        )))
    for steel in result.reinforcement:
        lines.extend(format_foundation_cut(steel))
        if steel.region == "Pantalla - vertical relleno" and steel.role == "primary":
            lines.append(f"Propuesta de corte del acero elegido - {steel.region}")
            lines.extend(_format_stem_reinforcement_cut_option(steel))
            if steel.stem_reinforcement_cut:
                lines.append(steel.stem_reinforcement_cut.notes)
    lines.extend(boxed_table(("Region", "Acero por cara", "As req", "As prov", "Indice", "Estado"),
        ((s.region, f"{s.bar_label} @ {s.spacing_m:.3f} m", f"{s.temperature_cm2_m:.3f}",
          f"{traces[s.region]['transverse_area']:.3f}", f"{s.transverse_utilization:.3f}", _status(s.transverse_utilization))
         for s in result.reinforcement if s.role == "temperature"), title="3.5. ACERO TRANSVERSAL POR TEMPERATURA - As EN cm2/m"))
    lines.extend(audit_subtitle("3.6", "CONTROL DE FISURACION - ACERO ELEGIDO", 112))
    crack_rows = []
    for steel in result.reinforcement:
        if steel.role != "primary":
            continue
        service = traces[steel.region]["service"]
        if service is None:
            continue
        crack_rows.append((steel.region, _number(service['demand'], 'moment'), _number(service, 'stress'),
            _number(service, 'stress_limit'), _number(service, 'axis'), _number(service, 'beta_service'),
            f"{steel.spacing_m:.3f}", _number(service, 'maximum_spacing') if service.get('service_tension', True) else "No gobierna",
            "OK" if service.get('stress_ratio', float('inf')) <= 1+1e-8 else "NO",
            "OK" if service.get('spacing_ratio', float('inf')) <= 1+1e-8 else "NO",
            "OK" if steel.crack_utilization <= 1+1e-8 else "NO"))
    if crack_rows:
        lines.extend(boxed_table(("Elemento", "Ms tn m/m", "fs kgf/cm2", "fs lim", "dc cm", "beta_s",
                                  "s prov m", "s max m", "E-fs", "E-s", "Estado"), crack_rows,
                                  aligns=("left", "right", "right", "right", "right", "right",
                                          "right", "right", "center", "center", "center")))
    else:
        lines.append("Sin casos de servicio: fisuracion no verificada.")
    lines.extend(boxed_table(("Elemento", "Barra", "ldb cm", "ld recto cm", "ld gancho cm", "Ext. cm", "L disp cm", "Estado"),
        ((s.region, s.bar_label, f"{traces[s.region]['basic_anchor_cm']:.1f}", f"{s.required_straight_anchor_cm:.1f}",
          f"{s.required_hook_anchor_cm:.1f}", f"{s.hook_extension_cm:.1f}",
          "Pendiente" if s.available_anchor_cm is None else f"{s.available_anchor_cm:.1f}", s.anchor_status)
         for s in result.reinforcement if s.role == "primary"), title="3.7. DESARROLLO Y ANCLAJE DE BARRAS"))
    return lines
