"""Develop governing checks in the calculation format of the reference Word."""

from collections import defaultdict
import re
from bridge_design.domain.connected_2_inputs import is_connected_2

from bridge_design.reporting.connected_docx_layout import SECTIONS
from bridge_design.reporting.connected_design_calculations import write_checks, write_temperature
from bridge_design.reporting.connected_case_groups import case_label
from bridge_design.reporting.deck_docx import _body, _table


def distribution_groups(reinforcement):
    grouped = defaultdict(list)
    for steel in reinforcement:
        grouped[steel.base_region or steel.region].append(steel)
    return grouped


def governing_source(row):
    d = row['demand']
    return (f"{row['region']}; {case_label(d['case'])}; elemento {d['element']}; "
            f"s/L={d['station']:.3f}; x={row['x']:.3f}, z={row['y']:.3f} m; "
            f"h={d['depth_cm']:.2f} cm; M={d['moment']:.3f} tn·m/m; "
            f"V={d['shear']:.3f} tn/m; cara {row['face']}.").replace('-0.000', '0.000')


def write_governing_checks(document, steel, trace):
    write_checks(document, steel, trace, governing_source)


def anchor_geometry_description(note):
    """Format only display values; retain the complete geometric audit separately."""
    precision = 2 if note.startswith('Criterio del modulo') else 3
    note = case_label(note)
    note = note.replace('; no se acredita doblado.', '.')
    note = note.replace(' Los cortes y empalmes requieren comprobar sus extremos particulares.', '')
    note = note.replace('Criterio del modulo', 'Detalle de anclaje')
    return re.sub(r'(?<![\w.])([+-]?\d+\.\d{4,})(?![\w.])',
                  lambda match: f'{float(match.group()):.{precision}f}', note)


def write_distributed_design(document, result, reinforcement, audit, charts=None):
    grouped = distribution_groups(reinforcement)
    uniform = is_connected_2(result.inputs)
    document.add_heading('8. ' + SECTIONS[7], level=1)
    _body(document, 'Se define un único armado de estribo, que se coloca tanto en el izquierdo como en el derecho. '
          'Cada distribución se verifica con todas las secciones de ambos lados; flexión, cortante, '
          'servicio y anclaje conservan su propio origen gobernante. El diseño utiliza la envolvente general '
          'del punto 6 y los esfuerzos simultáneos de cada sección. Cada control gobernante del acero elegido '
          'se desarrolla con expresión, definición de símbolos, sustitución numérica y conclusión.')
    _body(document, ('La zapata combinada tiene un armado longitudinal superior y otro inferior, '
          'cada uno diseñado con la envolvente de toda su longitud, incluidos los tramos bajo las pantallas. '
          'El acero transversal se selecciona por cara. El punto 9 utiliza los casos de Servicio I.'
          if uniform else 'La cara exterior de pantallas y parapetos tiene el mínimo por temperatura; si el análisis '
          'produce momentos que la traccionan, se comprueba también esa demanda. Talón y puntera conservan '
          'una distribución longitudinal gobernante por zona, continua en las caras superior e inferior. '
          'Los transversales se eligen por separado. El punto 9 utiliza únicamente los casos de Servicio I.'))
    for i, (region, records) in enumerate(grouped.items(), 1):
        document.add_heading(f'8.{i}. {region}', level=2)
        if region == "Zapata combinada" and charts and "cortes_zapata" in charts:
            from bridge_design.reporting.deck_docx import _picture
            _picture(document, charts["cortes_zapata"], "Cortes calculados del refuerzo superior central e inferior de extremos")
        _table(document, ('Distribución', 'Cara', 'As req cm²/m', 'Barra @ s m', 'As prov cm²/m', 'Estado'),
               ((s.region.split(' - ', 1)[-1], s.face, f'{s.required_as_cm2_m:.3f}',
                 f'{s.bar_label} @ {s.spacing_m:.3f}', f'{s.area_per_face_cm2_m:.3f}', s.status)
                for s in records), widths=(34, 25, 24, 34, 24, 19))
        for steel in records:
            if steel.role != 'primary':
                continue
            document.add_heading(steel.region.split(' - ', 1)[-1].capitalize(), level=3)
            write_governing_checks(document, steel, audit['steel'][steel.region])
            from bridge_design.reporting.connected_cut_report import write_foundation_cut
            write_foundation_cut(document, steel)
            if steel.region == 'Pantalla - vertical relleno':
                document.add_heading('Opción de corte de acero principal de pantalla', level=4)
                cut = steel.stem_reinforcement_cut
                if cut is None:
                    _body(document, 'NO APLICA: la distribución elegida no admite una reducción '
                          'con un corte que cumpla los controles de la envolvente FRAME.')
                else:
                    _table(document, ('Concepto', 'Valor'), (
                        ('Acero inferior', f'{cut.lower_bar_label} @ {cut.lower_spacing_m:.3f} m'),
                        ('Acero continuo superior', f'{cut.upper_bar_label} @ {cut.upper_spacing_m:.3f} m'),
                        ('Patrón constructivo', f'Continúa 1 de cada {cut.continuous_every_n_bars} barras inferiores'),
                        ('Altura teórica sobre zapata', f'{cut.theoretical_cut_height_m:.3f} m'),
                        ('Altura constructiva sobre zapata', f'{cut.constructive_cut_height_m:.3f} m'),
                        ('Prolongación ld', f'{cut.development_extension_m:.3f} m'),
                        ('Longitud barras cortadas', f'{cut.lower_cut_bar_length_m:.3f} m'),
                        ('Longitud barras continuas', f'{cut.continuous_bar_length_m:.3f} m'),
                        ('Estado de la opción', cut.status),
                    ), widths=(80, 80))
                    note = case_label(cut.notes).replace(
                        'La opcion no sustituye el armado uniforme seleccionado ni el detalle de union con la cajuela.', '')
                    _body(document, note.strip())

        write_temperature(document, records, audit)

    document.add_heading('9. ' + SECTIONS[8], level=1)
    _body(document, ('La fisuración y el desarrollo utilizan la barra y separación elegidas. La zapata '
          'combinada utiliza barras continuas y comprueba el espacio recto disponible en las secciones '
          'gobernantes de resistencia. Pantallas y parapetos conservan el detalle de anclaje compartido. '
          'Los cortes calculados se desarrollan en el punto 8.'
          if uniform else 'La fisuración y el desarrollo utilizan la barra y separación elegidas. La longitud recta '
          'disponible sigue el detalle continuo definido: pantalla dentro del espesor de zapata, '
          'losa dentro del ancho de zapata y parapeto en toda la altura del estribo, menos recubrimiento. '
          'Las barras de talón y puntera cruzan la pantalla hasta el borde opuesto de zapata. '
          'El punto 8 presenta opciones de corte de pantalla.'))
    _body(document, 'Sin tracción por flexión en Servicio I, la ecuación de separación por fisuración no '
          'gobierna. Se conservan los límites de acero mínimo y separación por temperatura. '
          'El estado de anclaje compara por separado ld recto y ld gancho con la longitud disponible. '
          'RECTO Y CON GANCHO indica ambas alternativas; SOLO GANCHO indica que solo cumple con gancho; '
          'NO CUMPLE indica que ninguna longitud alcanza el desarrollo calculado.')
    for region, records in grouped.items():
        document.add_heading(region, level=2)
        primary = [s for s in records if s.role == 'primary']
        service_rows = []
        geometry_notes = set()
        for steel in primary:
            row = audit['steel'][steel.region]['service']
            if row is None:
                continue
            tension = row.get('service_tension', True)
            service_rows.append((steel.region.split(' - ', 1)[-1],
                f"{row['side']}: {case_label(row['demand']['case'])}" if tension else 'Sin tracción',
                f"{row['stress']:.2f}", f"{row['stress_limit']:.2f}",
                f"{row['maximum_spacing']:.3f}" if tension else '—',
                'CUMPLE' if tension and row['crack_ratio'] <= 1+1e-8 else 'NO CUMPLE' if tension else 'No gobierna'))
        _table(document, ('Distribución', 'Servicio gobernante', 'fs kgf/cm²', 'fs límite', 's máx m', 'Estado'),
               service_rows, widths=(31, 42, 24, 23, 19, 21))
        _table(document, ('Distribución', 'Barra', 'ld recto cm', 'L disp cm', 'ld gancho cm', 'Estado anclaje'),
               ((s.region.split(' - ', 1)[-1], s.bar_label, f'{s.required_straight_anchor_cm:.2f}',
                 f'{s.available_anchor_cm:.2f}' if s.available_anchor_cm is not None else '—',
                 f'{s.required_hook_anchor_cm:.2f}', s.anchor_status if s.available_anchor_cm is not None else '—')
                for s in primary), widths=(34, 20, 25, 25, 25, 31))
        for steel in primary:
            trace = audit['steel'][steel.region]
            document.add_heading(steel.region.split(' - ', 1)[-1].capitalize(), level=3)
            write_checks(document, steel, trace, governing_source, service=True)
            if steel.anchor_geometry_note and steel.anchor_geometry_note not in geometry_notes:
                geometry_notes.add(steel.anchor_geometry_note)
                _body(document, anchor_geometry_description(steel.anchor_geometry_note))
    _body(document, ('Se mantiene la continuidad del acero entre las pantallas y la zapata combinada. '
          if uniform else 'Se mantiene la continuidad del acero entre pantalla y zapata y entre zapatas, transiciones y losa. '))
