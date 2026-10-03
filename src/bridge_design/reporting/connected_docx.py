"""A4 calculation memorandum for the connected abutment FRAME, using existing Word styles."""

from pathlib import Path
from dataclasses import astuple

from docx import Document
from bridge_design.domain.connected_reinforcement import DESIGN_SCOPE_NOTE
from bridge_design.reporting.connected_docx_layout import connected_front_matter, connected_summary_and_references
from bridge_design.reporting.deck_docx import _body, _calc, _enforce_uniform_typography, _picture, _table
from bridge_design.reporting.connected_audit import build_connected_audit
from bridge_design.reporting.connected_audit_docx import write_audit_table, write_steel_audit


def write_connected_docx(result, path, charts):
    document = Document()
    connected_front_matter(document, result)
    document.add_heading("1. Bases de diseño y datos de entrada", level=1)
    _body(document, DESIGN_SCOPE_NOTE)
    data, mesh = result.inputs, result.mesh
    audit = build_connected_audit(result)
    failures = sum(steel.status != "OK" for steel in result.reinforcement)
    failures += sum(check.sliding_status != "OK" or check.bearing_status != "OK" for check in result.foundation_checks)
    pending = sum(steel.anchor_status != "OK RECTO" for steel in result.reinforcement)
    _body(document, "Análisis estático y seudoestático de dos estribos con cajuela unidos mediante una cimentación "
          "continua zapata–losa–zapata. Se analiza una franja de 1,00 m mediante elementos FRAME elásticos de primer orden "
          "y resortes verticales Winkler de contacto unilateral. El tablero transmite cargas a los asientos.")
    _body(document, f"Se resolvieron {len(result.results)} combinaciones. Se registran {failures} verificaciones "
          f"estructurales o geotécnicas no conformes y {pending} regiones con anclaje pendiente o insuficiente. "
          "Los valores ingresados se reproducen para facilitar la revisión del modelo y sus hipótesis.")
    document.add_heading("1.1. Modelo y geometría", level=2)
    _picture(document, charts["geometria"], "Configuración, eje de referencia y restricción horizontal del conjunto")
    _table(document, ("Parámetro", "Valor"), (
        ("Separación libre entre caras interiores", f"{data.clear_span_m:.3f} m"),
        ("Longitud total de cimentación", f"{data.total_length_m:.3f} m"),
        ("Espesor de losa central", f"{data.slab_thickness_m:.3f} m"),
        ("Transiciones izquierda y derecha", f"{data.left_transition_m:.3f} / {data.right_transition_m:.3f} m"),
        ("Paso máximo de malla", f"{data.mesh_size_m:.3f} m"),
        ("Módulo de balasto vertical", f"{data.soil.subgrade_tn_m3:.3f} Tn/m³"),
        ("Fricción de interfaz suelo concreto", f"{data.soil.friction_coefficient:.3f}"),
        ("Presión admisible", f"{data.soil.allowable_tn_m2:.3f} Tn/m²"),
        ("Nodo Ux restringido", f"{mesh.reference_node}; x = {data.reference_position_m:.3f} m"),
        ("Offsets de sección", "Activados" if data.section_offsets else "Desactivados"),
        ("Discretización", f"{len(mesh.frame.nodes)} nodos; {len(mesh.frame.elements)} elementos"),
    ), widths=(94, 66), font_size=10)
    geometry_labels = (
        ("retained_height_m", "Altura de relleno desde fondo de zapata"),
        ("footing_width_m", "Ancho de zapata"), ("footing_thickness_m", "Espesor de zapata"),
        ("toe_length_m", "Puntera hacia el vano"), ("lower_stem_thickness_m", "Espesor inferior de pantalla"),
        ("upper_stem_thickness_m", "Espesor superior de pantalla"),
        ("bearing_seat_length_m", "Longitud horizontal de cajuela"),
        ("seat_wall_width_m", "Espesor del parapeto"), ("seat_block_height_m", "Altura del parapeto"),
        ("backwall_drop_m", "Altura del bloque de cajuela"), ("backwall_taper_height_m", "Altura de transición"),
        ("small_batter_width_m", "Transición frontal t1"), ("backfill_step_width_m", "Retiro posterior t2"),
        ("front_soil_depth_m", "Altura de suelo frontal desde fondo de zapata"),
        ("bridge_seat_to_bearing_height_m", "Brazo adicional para frenado"),
    )
    _table(document, ("Dimensión en metros", "Izquierda", "Derecha"),
           ((label, f"{getattr(data.left.geometry, name):.3f}", f"{getattr(data.right.geometry, name):.3f}")
            for name, label in geometry_labels), widths=(94, 33, 33), font_size=10)
    _table(document, ("Material", "Izquierda", "Losa", "Derecha"), (
        ("f'c kg/cm²", *[f"{material.concrete_strength_kg_cm2:.1f}" for material in (data.left.materials, data.slab_materials, data.right.materials)]),
        ("fy kg/cm²", *[f"{material.steel_yield_kg_cm2:.1f}" for material in (data.left.materials, data.slab_materials, data.right.materials)]),
        ("Peso concreto Tn/m³", *[f"{material.concrete_unit_weight_kg_m3 / 1000:.3f}" for material in (data.left.materials, data.slab_materials, data.right.materials)]),
    ), widths=(70, 30, 30, 30), font_size=10)
    for table in audit["inputs"]:
        if table.title != "Propiedades FRAME por elemento":
            write_audit_table(document, table)
    document.add_heading("2. Rigidez y contacto", level=1)
    slab_element = next(element for element in mesh.frame.elements if element.region == "Losa central")
    _calc(document, "Propiedades de sección", "A = b·t; I = b·t³/12; Kᵢ = kₛ·b·Lᵢ",
          "b: franja de 1 m; t: espesor; Lᵢ: longitud tributaria del resorte; kₛ: módulo de balasto.",
          f"Losa central: A = 1 × {data.slab_thickness_m:.3f}; I = 1 × {data.slab_thickness_m:.3f}³ / 12.",
          f"A = {slab_element.area:.6f} m²; I = {slab_element.inertia:.6f} m⁴.",
          "Cada elemento usa su espesor y módulo del concreto. Las transiciones se subdividen.",
          "Euler Bernoulli y trabajo virtual; Ec según MTC 2018 Art. 2.5.4.4.")
    _body(document, "Se impone únicamente Ux = 0 en el nodo de referencia. Su desplazamiento vertical participa "
          "del equilibrio con el resorte y su giro permanece libre. La reacción horizontal representa el desequilibrio "
          "global de cargas. Concentrar esa reacción en un nodo es una idealización que puede afectar los esfuerzos "
          "bajo acciones desequilibradas. No representa la distribución de fricción en la base.")
    _body(document, "Se resuelve cada combinación con su propio conjunto de resortes activos. Para Uy negativo, "
          "R = −K·Uy; al levantarse la base, R = 0. Se comprueban el equilibrio de fuerzas y momentos, las reacciones "
          "sin tracción y la convergencia del contacto. Las rigideces son brutas; no se incluyen segundo orden, "
          "plasticidad del concreto ni consolidación del terreno.")
    document.add_heading("3. Cargas de ambos estribos y combinaciones", level=1)
    pressures = result.earth_parameters
    _table(document, ("Parámetro del relleno", "Izquierda", "Derecha"), (
        ("Peso unitario Tn/m³", f"{data.left.materials.soil_unit_weight_kg_m3 / 1000:.3f}", f"{data.right.materials.soil_unit_weight_kg_m3 / 1000:.3f}"),
        ("Ángulo de fricción grados", f"{data.left.soil.friction_angle_deg:.2f}", f"{data.right.soil.friction_angle_deg:.2f}"),
        ("Fricción muro suelo grados", f"{data.left.soil.wall_soil_friction_deg:.2f}", f"{data.right.soil.wall_soil_friction_deg:.2f}"),
        ("Pendiente del relleno grados", f"{data.left.soil.backfill_slope_deg:.2f}", f"{data.right.soil.backfill_slope_deg:.2f}"),
        ("Ka cara real", f"{pressures[0].stem_ka:.5f}", f"{pressures[1].stem_ka:.5f}"),
        ("Ka plano virtual del talón", f"{pressures[0].ka:.5f}", f"{pressures[1].ka:.5f}"),
    ), widths=(94, 33, 33), font_size=10)
    _body(document, "Por decisión de modelación se utiliza siempre empuje activo de Coulomb. La cajuela, el parapeto, "
          "las transiciones y los rellenos conservan la geometría y los pesos del módulo existente. El cálculo separa "
          "las presiones en la cara real del muro y la resultante externa en el plano vertical del talón. La diferencia "
          "se transfiere a los nodos del talón conservando fuerza y momento; así la fricción muro suelo permanece "
          "interna al conjunto muro más relleno y no duplica cargas verticales.")
    _body(document, "Se revisan ambos sentidos globales de frenado y sismo. Mononobe Okabe usa el signo del coeficiente "
          "horizontal respecto de cada relleno. Se mantienen los patrones PAE + 0,5 PIR y max(0,5 PAE, EH) + PIR. "
          "El incremento sísmico positivo se distribuye uniformemente como en el módulo de estribos; una reducción "
          "se distribuye triangularmente para conservar presión no negativa. Las inercias de concreto, relleno y "
          "tablero siguen un mismo sentido global. Referencia: MTC 2018 Art. 2.8.1.1.14.1 y Apéndice A.11.3.1.")
    factors = result.combination_factors
    _table(document, ("Acción", *(row.name for row in factors)),
           ((label, *(f"{getattr(row, attribute):.2f}" for row in factors))
            for label, attribute in (("DC", "dc"), ("DW", "dw"), ("EV", "ev"), ("LL", "ll"),
                                     ("LS vertical", "ls_vertical"), ("LS horizontal", "ls_horizontal"),
                                     ("EH", "eh"), ("EQ", "eq"), ("BR", "br"))),
           widths=(32, *(128 / len(factors) for row in factors)), font_size=11)
    entered_pairs = [(case.name, case.left, case.right) for case in data.cases]
    if not entered_pairs:
        entered_pairs = [("Par simultáneo ingresado", data.left.loads, data.right.loads)]
    for label, left_loads, right_loads in entered_pairs:
        _body(document, f"Reacciones por metro de estribo del caso {label}.")
        _table(document, ("Lado", "DC", "DW", "PL", "LL+IM", "BR"),
               ((side_label, f"{loads.pdc_tn_m:.3f}", f"{loads.pdw_tn_m:.3f}", f"{loads.ppl_tn_m:.3f}",
                 f"{loads.pll_im_tn_m:.3f}", f"{loads.braking_tn_m:.3f}")
                for side_label, loads in (("Izquierda", left_loads), ("Derecha", right_loads))),
               widths=(35, 25, 25, 25, 25, 25), font_size=10)
    _body(document, "Cada variante Ia o Ib se aplica globalmente a ambos estribos, losa y transiciones, sin cruces "
          "entre regiones. Las cargas de cada caso representan un par simultáneo del tablero y de las sobrecargas "
          "de relleno. La envolvente cubre los casos ingresados; debe incluirse cada posicionamiento vehicular relevante.")
    for step in audit["earth"]:
        _calc(document, *astuple(step))
    for table in audit["loads"]:
        if table.headers[0] != "Accion / lado":
            write_audit_table(document, table)
    document.add_heading("4. Presiones y deslizamiento", level=1)
    _picture(document, charts["contacto"], "Presiones y asentamientos de servicio en la cimentación completa")
    _body(document, "La demanda global de deslizamiento es |Rx|. La resistencia adoptada es φ·μ·ΣRᵥ, utilizando "
          "solo contacto compresivo de la misma combinación y sin contribución pasiva. El coeficiente μ corresponde "
          "a la interfaz suelo concreto. La presión local es qᵢ = Rᵢ / área tributaria. Servicio se compara con qadm; "
          "la comparación LRFD conserva la aproximación heredada qn = FS·qadm, con φ = 0,55 en resistencia y "
          "0,80 en evento extremo. Esta comparación local de Winkler no reproduce una distribución rígida de Meyerhof.")
    _table(document, ("Caso", "Rx Tn", "qmax Tn/m²", "Contacto m", "Deslizamiento", "Presión"),
           ((f"C{index:03d}", f"{row.horizontal_reaction:.3f}", f"{row.maximum_pressure:.3f}",
             f"{row.contact_length:.3f}", row.sliding_status, row.bearing_status)
            for index, row in enumerate(result.foundation_checks, 1)), widths=(18, 25, 31, 27, 33, 26), font_size=9)
    _body(document, "Los asentamientos se presentan como resultados del modelo, sin verificación de un límite "
          "admisible. Un estado conforme de presión no implica conformidad de asentamientos.")
    document.add_heading("5. Solicitaciones del FRAME", level=1)
    for name, caption in (("modelo_axial", "Envolvente axial N sobre la estructura completa"),
                          ("modelo_cortante", "Envolvente de cortante V sobre la estructura completa"),
                          ("modelo_momento", "Envolvente de momento M sobre la estructura completa")):
        _picture(document, charts[name], caption)
    _body(document, "N es positivo a tracción. El momento positivo tracciona la cara local negativa de la normal "
          "del elemento. Los diagramas conservan signos; el diseño adopta armadura simétrica por ambas caras. "
          "Cada vista incluye ambos estribos, cajuelas y toda la cimentación con igual escala geométrica x/y. "
          "Las ordenadas se dibujan normales al eje, positivas hacia arriba en la cimentación y hacia la izquierda "
          "en ambas pantallas, con una escala de esfuerzos común a todos los elementos de cada figura. "
          "Se incluyen las estaciones de extremos internos y se conservan los saltos entre elementos. "
          "Las envolventes de resistencia y evento extremo no representan un único caso simultáneo. "
          "Los archivos CSV contienen los esfuerzos simultáneos por combinación y estación, incluyendo extremos internos.")
    document.add_heading("6. Diseño de armaduras y detalle", level=1)
    _body(document, "Se presentan las distribuciones adoptadas después de la selección en consola y la "
          "reevaluación de resistencia, servicio y desarrollo. En modo automático se conserva la propuesta inicial. "
          "Cambiar el acero no modifica la rigidez bruta del FRAME utilizada en este análisis.")
    _body(document, "Se diseña por flexión y cortante con las funciones compartidas del estribo individual. "
          "Para cada signo de momento se utiliza el acero de la cara traccionada, sin acreditar el acero de "
          "la cara comprimida. La resistencia a flexión emplea bloque rectangular y φ limitado por la deformación. "
          "Se conserva el mínimo de flexión. El corte usa el procedimiento general compartido, sin término axial. "
          "En servicio se estima fs = |Ms| / (As · 0,90d), como en estribos individuales, y se verifica fisuración. "
          "No se realiza verificación de flexocompresión ni flexotracción. La simplificación no demuestra "
          "que el efecto axial sea despreciable. Los momentos mantienen las transformaciones de offsets "
          "del análisis cuando se activan.")
    for index, steel in enumerate(result.reinforcement, 1):
        document.add_heading(f"6.{index}. {steel.region}", level=2)
        write_steel_audit(document, steel, audit["steel"][steel.region], steel.region in result.selected_reinforcement)
        _calc(document, "Armadura principal adoptada", "As = Ab / s",
              "As: área de acero por metro y por cara; Ab: área de una barra; s: separación de barras en metros.",
              f"Barra adoptada {steel.bar_label}; separación s = {steel.spacing_m:.3f} m.",
              f"As = {steel.area_per_face_cm2_m:.3f} cm²/m por cara.",
              f"Estado de las comprobaciones del armado adoptado: {steel.status}.",
              "Manual de Puentes MTC 2018, Sección 2.9; catálogo de barras del programa.")
        _body(document, f"Armadura principal por cara: {steel.bar_label} cada {steel.spacing_m:.3f} m; "
              f"As = {steel.area_per_face_cm2_m:.3f} cm²/m. Armadura transversal por cara: "
              f"{steel.transverse_bar_label} cada {steel.transverse_spacing_m:.3f} m. "
              f"Mínimo por temperatura y retracción: {steel.temperature_cm2_m:.3f} cm²/m, según MTC Art. 2.9.1.4.5.8.")
        _body(document, f"Sección gobernante de flexión: elemento {steel.governing_element}, estación relativa "
              f"{steel.governing_station:.3f}, espesor {steel.governing_depth_cm:.2f} cm. "
              f"N = {steel.governing_axial:.3f} Tn (informativo, no verificado), V = {steel.governing_shear:.3f} Tn y "
              f"M = {steel.governing_moment:.3f} Tn·m del caso {steel.governing_case}.")
        _table(document, ("Comprobación", "Máximo demanda capacidad", "Estado"),
               ((label, f"{value:.3f}", "CUMPLE" if value <= 1 + 1e-8 else "NO CUMPLE")
                for label, value in (("Flexión", steel.flexural_utilization),
                                     ("Corte de concreto", steel.shear_utilization),
                                     ("Fisuración y tensión de servicio", steel.crack_utilization),
                                     ("Mínimo principal por temperatura", steel.minimum_utilization),
                                     ("Acero transversal por temperatura", steel.transverse_utilization))), widths=(70, 55, 35), font_size=10)
        _body(document, f"Desarrollo recto requerido: {steel.required_straight_anchor_cm:.1f} cm. "
              f"Desarrollo con gancho: {steel.required_hook_anchor_cm:.1f} cm; extensión del gancho: "
              f"{steel.hook_extension_cm:.1f} cm. Estado de anclaje: {steel.anchor_status}. "
              "La longitud útil debe corresponder al detalle real; el desarrollo con gancho no certifica su acomodo.")
    document.add_heading("7. Verificación numérica y trazabilidad", level=1)
    maximum_force_error = max(max(abs(row.equilibrium_error[0]), abs(row.equilibrium_error[1])) for row in result.results)
    maximum_moment_error = max(abs(row.equilibrium_error[2]) for row in result.results)
    _body(document, f"Máximo residuo global de fuerzas: {maximum_force_error:.3e} Tn; de momentos: "
          f"{maximum_moment_error:.3e} Tn·m. El solucionador rechaza inestabilidad, pérdida de soporte y falta de convergencia.")
    if result.mesh_comparison:
        comparison = result.mesh_comparison
        _body(document, f"Refinamiento de {comparison.coarse_step:.3f} a {comparison.fine_step:.3f} m. "
              f"Cambios relativos: momento {comparison.moment_change:.2%}, presión {comparison.pressure_change:.2%}, "
              f"asentamiento {comparison.settlement_change:.2%}. Evaluar refinamiento adicional si las variaciones son relevantes.")
    else:
        _body(document, "No se solicitó comparación de malla en esta ejecución. Está disponible mediante --verificar-malla.")
    _body(document, "resultados.json conserva entradas, propiedades, vectores de carga, contacto y comprobaciones. "
          "Las tablas detalladas por elemento, acción de cada combinación y nodo de contacto se omiten en esta "
          "memoria y permanecen en las salidas de auditoría. elementos.csv, nodos.csv, esfuerzos.csv y "
          "cargas_combinadas.csv permiten revisar el cálculo y reconstruir los diagramas.")
    for index, case in enumerate(result.results, 1):
        _body(document, f"C{index:03d}: {case.name}")
    connected_summary_and_references(document, result)
    _enforce_uniform_typography(document)
    destination = Path(path).expanduser().resolve()
    if destination.suffix.lower() != ".docx":
        destination = destination.with_suffix(".docx")
    destination.parent.mkdir(parents=True, exist_ok=True)
    document.save(destination)
    return destination
