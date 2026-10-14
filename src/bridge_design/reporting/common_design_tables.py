"""Shared Word/PDF tables for common construction details and governing checks."""


def family_tables(family, *, cantilever=False):
    unit = ' / m' if cantilever else ''
    yield ('Resultados individuales con el armado comun',
           ('Elemento', 'Mu (Tn.m'+unit+')', 'Vu (Tn'+unit+')', 'As req (cm2'+unit+')', 'Verificaciones'),
           family.individual_rows, (35, 30, 30, 30, 33))
    yield ('Elemento gobernante en cada verificacion',
           ('Verificacion', 'Gobierna', 'Demanda', 'Limite', 'Unidad', 'Estado'),
           family.checks, (40, 29, 24, 24, 20, 21))
    if cantilever:
        development = family.development
        yield ('Longitudes comunes para ambos volados',
               ('Lado', 'ld requerido (m)', 'Anclaje comun (m)', 'Longitud comun (m)'),
               tuple(('Volado '+m.side, f'{m.development.required_development_length_cm/100:.3f}',
                      f'{development.interior_anchor_length_m:.3f}',
                      f'{development.total_additional_bar_length_m:.3f}') for m in family.members),
               (40, 38, 40, 40))
        rows = []
        for member in family.members:
            for name, collision in (('Conexion en volado', member.result.barrier_collision),
                                    ('Transferencia a losa interior', member.result.interior_collision)):
                if collision is not None:
                    rows.append(('Volado '+member.side, name, collision.status))
        if rows:
            yield ('Comprobaciones locales de colision por lado', ('Lado', 'Comprobacion', 'Estado'),
                   tuple(rows), (40, 85, 33))
    else:
        d = family.detail
        yield ('Detalle longitudinal comun: distancias desde el apoyo inicial',
               ('Barras', 'Diametro', 'Inicio (m)', 'Fin (m)', 'Longitud (m)', 'Estado'),
               tuple((str(c.bar_count), c.bar_label, f'{c.detail_start_m:.3f}', f'{c.detail_end_m:.3f}',
                      f'{c.bar_length_m:.3f}', c.status) for c in d.longitudinal_cuts),
               (19, 22, 25, 25, 27, 40))
        yield ('Zonas de estribos comunes para toda la familia',
               ('Desde / hasta (m)', 'Diametro / ramas', 's (m)', 'Vu (Tn)', 'phi Vn (Tn)', 'Estado'),
               tuple((f'{z.start_m:.3f} / {z.end_m:.3f}', f'{z.bar_label} / {z.legs}',
                      f'{z.spacing_m:.3f}', f'{z.maximum_vu_tn:.3f}', f'{z.phi_vn_tn:.3f}', z.status)
                     for z in d.stirrup_zones), (34, 30, 20, 25, 28, 21))


def family_description(family, *, cantilever=False):
    basis = 'Volado '+family.basis.side if cantilever else family.basis.label
    return ('Se conserva el analisis independiente de cada elemento. El armado se selecciona una sola vez '
            'y se verifica en todos los miembros de la familia. Cada comprobacion conserva su caso gobernante; '
            'los esfuerzos no se promedian. El desarrollo de cargas y flexion corresponde a '+basis+'. '
            'Las tablas identifican los casos que gobiernan las demas comprobaciones. '
            'Las longitudes y separaciones comunes cubren ambos lados.' if cantilever else
            'Se conserva el analisis independiente de cada viga. Se adopta un armado comun para '+family.label+
            '. Cada comprobacion conserva su caso gobernante; los esfuerzos no se promedian. '
            'El desarrollo de cargas y flexion corresponde a '+basis+'. '
            'Los diagramas, cortes de barras y zonas de estribos cubren toda la familia.')


def stirrup_zones_text(family):
    zones = family.detail.stirrup_zones
    selected = family.detail.selected_stirrup
    spacings = sorted({z.spacing_m for z in zones})
    return (f'estribo {selected.bar_label}, {selected.legs} ramas; s = '
            + ' / '.join(f'{spacing:.3f}' for spacing in spacings) + ' m, segun zonas del detalle comun')


def word_family_summary(document, family, table, *, cantilever=False):
    document.add_paragraph(family_description(family, cantilever=cantilever))
    for title, headers, rows, widths in family_tables(family, cantilever=cantilever):
        document.add_heading(title, level=2)
        table(document, headers, rows, widths=widths)
    if cantilever:
        for member in family.members:
            for note in member.result.applicability_notes:
                if 'tuberia' in note.lower():
                    document.add_paragraph('Volado '+member.side+': '+note)


def pdf_family_summary(family, styles, *, cantilever=False):
    from reportlab.lib.units import mm
    from bridge_design.reporting.pdf_style import p, data_table
    story = [p(family_description(family, cantilever=cantilever), styles['body'])]
    for title, headers, rows, widths in family_tables(family, cantilever=cantilever):
        story.extend((p(title, styles['h2']), data_table(headers, list(rows), [w*mm for w in widths], styles)))
    return story


def family_audit(family, *, cantilever=False):
    """Avoid appending superseded individual bar cuts to a common design."""
    from bridge_design.cli.ascii_tables import boxed_table
    lines = [family_description(family, cantilever=cantilever)]
    for title, headers, rows, _ in family_tables(family, cantilever=cantilever):
        lines.extend(boxed_table(headers, rows, title=title))
    return '\n'.join(lines)
