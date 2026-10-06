"""One cutoff table shared by console options, final results and Word."""

from bridge_design.cli.ascii_tables import key_value_box


def foundation_cut_rows(steel):
    cut = steel.foundation_reinforcement_cut
    rows = [("Disposicion", cut.arrangement), ("Estado", cut.status), ("Criterio", cut.reason)]
    if cut.requested_continuous_spacing_m is not None:
        family = f"{steel.bar_label} @ {cut.requested_continuous_spacing_m:.3f} m"
        rows.extend((("Familia continua solicitada", family), ("Familia adicional intercalada solicitada", family),
                     ("Total donde coinciden ambas familias", f"{steel.bar_label} @ {steel.spacing_m:.3f} m")))
    if cut.status != "APLICA":
        return tuple(rows)
    pattern = cut.pattern
    continuous = (f"{steel.bar_label} @ {pattern.equivalent_spacing_m:.3f} m" if pattern.cycle_bars == 2 else
                  f"{steel.bar_label}: {pattern.continuing_bars} de cada {pattern.cycle_bars}; hueco maximo {pattern.maximum_gap_m:.3f} m")
    rows.extend((
        ("Acero continuo en toda la zapata", continuous),
        ("Familia adicional localizada", f"{steel.bar_label} @ {steel.spacing_m*pattern.cycle_bars:.3f} m"),
        ("Acero elegido en zona reforzada", f"{steel.bar_label} @ {steel.spacing_m:.3f} m"),
        ("Patron de corte", f"Cortar 1 de cada {pattern.cycle_bars}; continuan {pattern.continuing_bars} de cada {pattern.cycle_bars}"),
        ("As continuo / As en zona reforzada", f"{pattern.remaining_area_cm2_m:.3f} / {steel.area_per_face_cm2_m:.3f} cm2/m"),
        ("Separacion maxima real tras el corte", f"{pattern.maximum_gap_m:.3f} m"),
        ("Cortes teoricos x izquierdo / derecho", f"{cut.theoretical_left_m:.3f} / {cut.theoretical_right_m:.3f} m"),
        ("Cortes definitivos x izquierdo / derecho", f"{cut.cutoff_left_m:.3f} / {cut.cutoff_right_m:.3f} m"),
        ("Distancia de cada cara interior al corte", f"{abs(cut.distance_from_inner_face_m):.3f} m " +
         ("hacia el centro" if cut.distance_from_inner_face_m >= 0 else "hacia el talon exterior")),
        ("ld del calculo existente", f"{cut.development_length_m:.3f} m"),
        ("Prolongacion minima max(d, 15db, L/20)", f"{cut.minimum_extension_m:.3f} m"),
        ("Prolongacion adoptada max(ld, minimo)", f"{cut.adopted_extension_m:.3f} m"),
    ))
    for index, (start, end) in enumerate(cut.additional_intervals_m, 1):
        rows.append((f"Refuerzo adicional {index}: tramo x / longitud horizontal",
                     f"[{start:.3f}, {end:.3f}] m / {end-start:.3f} m"))
    start, end = cut.continuous_interval_m
    rows.extend((
        ("Barras continuas: tramo x / longitud horizontal", f"[{start:.3f}, {end:.3f}] m / {end-start:.3f} m"),
        ("Indices remanentes flexion / corte / fisuracion", f"{cut.flexural_utilization:.3f} / {cut.shear_utilization:.3f} / {cut.crack_utilization:.3f}"),
        ("Indice de acero minimo remanente", f"{cut.minimum_utilization:.3f}"),
        ("Caso gobernante del tramo reducido", f"{cut.governing_case}; elemento {cut.governing_element}; s/L={cut.governing_station:.3f}"),
        ("Reduccion de acero longitudinal horizontal", f"{cut.saved_steel_fraction:.1%}"),
    ))
    for zone in cut.zones:
        label = f"{zone.name} [{zone.start_m:.3f}, {zone.end_m:.3f}] m"
        rows.extend(((label, f"{zone.reinforcement}; As={zone.area_cm2_m:.3f} cm2/m; {zone.status}"),
            ("Momento de servicio local / fs / limite", f"{zone.service_moment_tn_m_m:.3f} Tn.m/m / "
             f"{zone.service_stress_kg_cm2:.2f} / {zone.service_stress_limit_kg_cm2:.2f} kg/cm2"),
            ("Separacion real / limite por fisuracion", f"{zone.maximum_gap_m:.3f} / " +
             (f"{zone.crack_spacing_limit_m:.3f} m" if zone.service_stress_kg_cm2 > 0 else "no gobierna (sin traccion)")),
            ("Indices locales flexion / corte / fisuracion / minimo", f"{zone.flexural_utilization:.3f} / "
             f"{zone.shear_utilization:.3f} / {zone.crack_utilization:.3f} / {zone.minimum_utilization:.3f}"),
            ("Caso de servicio local", f"{zone.service_case}; x={zone.service_x_m:.3f} m")))
    return tuple(rows)


def format_foundation_cut(steel):
    cut = steel.foundation_reinforcement_cut
    if cut is None:
        return []
    lines = key_value_box("CORTES DE ACERO - " + steel.region, foundation_cut_rows(steel))
    if cut.status == "APLICA":
        lines.extend(("Coordenadas x desde el extremo izquierdo de la zapata. Propuesta simetrica para ambos lados.",
                      "Cada zona usa su envolvente local. Se incluyen conservadoramente los elementos completos junto al corte.", cut.notes))
    else:
        lines.append("Se conserva el acero elegido continuo; no se coloca un corte sin verificacion.")
    return lines


def write_foundation_cut(document, steel):
    from bridge_design.reporting.deck_docx import _body, _table
    cut = steel.foundation_reinforcement_cut
    if cut is None:
        return
    document.add_heading("Cortes del acero de zapata - " + steel.face.lower(), level=4)
    from bridge_design.reporting.connected_case_groups import case_label
    rows = tuple((label.replace(" solicitada", " adoptada"), case_label(value))
                 for label, value in foundation_cut_rows(steel))
    _table(document, ("Concepto", "Resultado"), rows, widths=(76, 84))
    if cut.status == "APLICA":
        _body(document, "Las coordenadas x se miden desde el extremo izquierdo de la zapata. " + case_label(cut.notes))
    else:
        _body(document, "Se conserva el acero elegido continuo.")
