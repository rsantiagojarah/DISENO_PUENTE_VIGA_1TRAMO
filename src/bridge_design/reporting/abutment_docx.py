"""Detailed A4 Word calculation report for ``diseno-estribos`` and ``diseno-muros``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from bridge_design.domain.abutment import (
    ABUTMENT_KEY_REFERENCE,
    AbutmentDesignResult,
    StabilityStateResult,
    StructuralDesignCase,
)
from bridge_design.domain.rebar_catalog import REINFORCING_BAR_CATALOG
from bridge_design.reporting.abutment_docx_charts import (
    save_abutment_geometry,
    save_contact_pressure_diagrams,
)
from bridge_design.reporting.abutment_docx_detail import (
    allowable_bearing_trace,
    component_factor_rows,
    concrete_geometry_rows,
    coulomb_ka_trace,
    crack_control_trace,
    cracking_and_temperature_trace,
    development_trace,
    eccentricity_limit_trace,
    effective_depth_trace,
    factors_for_state,
    heel_toe_demand_trace,
    horizontal_components_for_state,
    mononobe_okabe_trace,
    mtc_seismic_envelope_trace,
    passive_key_height_trace,
    peq_trace,
    pir_trace,
    pressure_arms_trace,
    seismic_angle_trace,
    secondary_temperature_trace,
    stem_cut_constructive_length_trace,
    stem_cut_continuous_pattern_trace,
    stem_cut_theoretical_height_trace,
    shear_beta_trace,
    stem_demand_trace,
    surcharge_height_trace,
)
from bridge_design.reporting.deck_docx import (
    GRAY,
    RULE,
    TEAL,
    _body,
    _bottom_border,
    _calc,
    _comment,
    _configure_document,
    _enforce_uniform_typography,
    _field,
    _format_run,
    _picture,
    _table,
)

REF_COMBINATIONS = "Manual de Puentes MTC 2018, Art. 2.4.5.3.1 y Tabla 2.4.5.3.1-1."
REF_EARTH = "Manual de Puentes MTC 2018, criterios de empuje de suelo de la Sección 2.11; AASHTO LRFD 3.11."
REF_STABILITY = "Manual de Puentes MTC 2018, criterios de estribos y cimentaciones; AASHTO LRFD 10.6.3.1 y 11.6.3."
REF_FLEXURE = "Manual de Puentes MTC 2018, Sección 2.9.4.2; AASHTO LRFD 5.7.3."
REF_SHEAR = (
    "Manual de Puentes MTC 2018 Arts. 2.9.1.5.6.3.3, 2.9.1.5.6.3.4.1 y 2.9.1.5.6.3.4.2; "
    "AASHTO LRFD 5.7.3.3 y 5.7.3.4."
)
REF_CRACK = "Manual de Puentes MTC 2018, Sección 2.9.4.4; AASHTO LRFD 5.7.3.4."
REF_DEVELOPMENT = "Manual de Puentes MTC 2018, Art. 2.6.5.6.2.1; AASHTO LRFD 5.11.2.1."
REF_TEMPERATURE = (
    "Manual de Puentes MTC 2018, Art. 2.9.1.4.5.8; AASHTO LRFD 5.10.8."
)


@dataclass(frozen=True)
class _ReportLabels:
    header: str
    cover_title: str
    cover_subtitle: str
    system: str
    analysis_intro: str
    structure: str
    geometry_caption: str
    filename_prefix: str
    save_title: str
    cancel_msg: str
    saved_msg: str
    stability_intro: str
    weight_owner: str
    pressure_chart_caption: str


def _labels(*, is_pure_wall: bool) -> _ReportLabels:
    if is_pure_wall:
        return _ReportLabels(
            header="MEMORIA DE CÁLCULO · MURO EN CANTILEVER",
            cover_title="Memoria de cálculo\ndel muro en cantilever",
            cover_subtitle="Geometría · empujes · estabilidad · dentellón · diseño estructural · detalle",
            system="Muro de contención de concreto armado en cantilever, franja de 1.00 m",
            analysis_intro=(
                "El muro se analiza por una franja longitudinal de 1.00 m sin acciones del tablero. "
                "Las acciones se conservan por naturaleza de carga y se combinan mediante factores LRFD. "
                "La estabilidad se verifica con la resultante en la base, la resistencia al deslizamiento "
                "y la presión de contacto; el diseño estructural emplea las presiones lineales adoptadas "
                "para la zapata."
            ),
            structure="muro",
            geometry_caption="Figura 1.1. Sección transversal y dimensiones principales del muro adoptado.",
            filename_prefix="MEMORIA_CALCULO_MURO",
            save_title="Guardar memoria de cálculo detallada del muro",
            cancel_msg="Generación de la memoria Word del muro cancelada por el usuario.",
            saved_msg="Memoria Word del muro guardada en:",
            stability_intro=(
                "Las verificaciones se desarrollan para el muro independiente. "
                "Se mantienen separados Servicio I, Resistencia I y Evento Extremo I."
            ),
            weight_owner="muro",
            pressure_chart_caption=(
                "Figura 4.1. Diagramas lineales de presión estructural bajo la zapata "
                "para la condición del muro."
            ),
        )
    return _ReportLabels(
        header="MEMORIA DE CÁLCULO · ESTRIBO DE PUENTE",
        cover_title="Memoria de cálculo\ndel estribo de puente",
        cover_subtitle="Geometría · empujes · estabilidad · dentellón · diseño estructural · detalle",
        system="Estribo de concreto armado tipo cantilever, franja de 1.00 m",
        analysis_intro=(
            "El estribo se analiza por una franja longitudinal de 1.00 m. Las acciones se conservan "
            "por naturaleza de carga y se combinan mediante factores LRFD. La estabilidad se verifica "
            "con la resultante en la base, la resistencia al deslizamiento y la presión de contacto; "
            "el diseño estructural emplea las presiones lineales adoptadas para la zapata."
        ),
        structure="estribo",
        geometry_caption="Figura 1.1. Sección transversal y dimensiones principales del estribo adoptado.",
        filename_prefix="MEMORIA_CALCULO_ESTRIBO",
        save_title="Guardar memoria de cálculo detallada del estribo",
        cancel_msg="Generación de la memoria Word del estribo cancelada por el usuario.",
        saved_msg="Memoria Word del estribo guardada en:",
        stability_intro=(
            "Las verificaciones se desarrollan con puente y sin puente. "
            "Se mantienen separados Servicio I, Resistencia I y Evento Extremo I."
        ),
        weight_owner="estribo",
        pressure_chart_caption=(
            "Figura 4.1. Diagramas lineales de presión estructural bajo la zapata "
            "para la condición con puente."
        ),
    )


def generate_abutment_docx(result: AbutmentDesignResult, output_path: str | Path) -> Path:
    """Create the detailed abutment Word memory and return its absolute path."""
    path = Path(output_path).expanduser().resolve()
    if path.suffix.lower() != ".docx":
        path = path.with_suffix(".docx")
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    labels = _labels(is_pure_wall=result.inputs.is_pure_wall)
    _configure_document(document)
    _configure_abutment_header_footer(document, labels)
    with TemporaryDirectory(prefix="abutment_report_") as chart_dir:
        chart_path = Path(chart_dir)
        _cover(document, result, labels)
        _contents(document)
        _design_basis(document, result, chart_path, labels)
        _weights(document, result, labels)
        _earth_pressures(document, result)
        _stability(document, result, chart_path, labels)
        _key_design(document, result)
        _structural_design(document, result)
        _service_and_detailing(document, result)
        _summary(document, result)
        _references(document)
        _enforce_uniform_typography(document)
        document.save(path)
    return path


def select_abutment_docx_save_path(result: AbutmentDesignResult | None = None) -> Path | None:
    """Open a native save dialog for the abutment or wall Word memory."""
    is_pure_wall = result.inputs.is_pure_wall if result is not None else False
    labels = _labels(is_pure_wall=is_pure_wall)
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise RuntimeError("Tkinter no está disponible para elegir el destino Word.") from exc
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    default_name = f"{labels.filename_prefix}_{datetime.now():%Y%m%d_%H%M}.docx"
    try:
        selected = filedialog.asksaveasfilename(
            parent=root,
            title=labels.save_title,
            defaultextension=".docx",
            initialfile=default_name,
            filetypes=(("Documento de Word", "*.docx"),),
        )
    finally:
        root.destroy()
    return Path(selected) if selected else None


def generate_abutment_docx_with_dialog(result: AbutmentDesignResult) -> Path | None:
    """Ask for a destination and create the Word memory when accepted."""
    labels = _labels(is_pure_wall=result.inputs.is_pure_wall)
    path = select_abutment_docx_save_path(result)
    if path is None:
        print(labels.cancel_msg)
        return None
    generated = generate_abutment_docx(result, path)
    print(f"{labels.saved_msg} {generated}")
    return generated


def _configure_abutment_header_footer(document: Document, labels: _ReportLabels) -> None:
    section = document.sections[0]
    header = section.header.paragraphs[0]
    header.clear()
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = header.add_run(labels.header)
    _format_run(run, 11, bold=True, color=TEAL)
    _bottom_border(header, RULE, 5)
    footer = section.footer.paragraphs[0]
    footer.clear()
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = footer.add_run("DISEÑO ESTRUCTURAL  ·  ")
    _format_run(run, 11, color=GRAY)
    _field(footer, "PAGE")


def _cover(document: Document, result: AbutmentDesignResult, labels: _ReportLabels) -> None:
    data = result.inputs
    g = data.geometry
    p = document.add_paragraph()
    p.paragraph_format.space_after = Pt(34)
    run = p.add_run("INGENIERÍA ESTRUCTURAL")
    _format_run(run, 11, bold=True, color=TEAL)
    _bottom_border(p, TEAL, 16)
    p = document.add_paragraph(style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.space_before = Pt(42)
    p.add_run(labels.cover_title)
    p = document.add_paragraph(style="Subtitle")
    p.add_run(labels.cover_subtitle)
    p = document.add_paragraph()
    p.paragraph_format.space_before = Pt(32)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("DOCUMENTO TÉCNICO DE DISEÑO")
    _format_run(run, 11, bold=True, color=TEAL)
    _table(
        document,
        ("Dato", "Descripción"),
        (
            ("Sistema", labels.system),
            ("Altura retenida", f"{g.retained_height_m:.2f} m"),
            ("Ancho de zapata", f"{g.footing_width_m:.2f} m"),
            ("Ángulo de fricción", f"{data.soil.friction_angle_deg:.1f}°"),
            ("Presión admisible", f"{data.soil.allowable_bearing_kg_cm2:.2f} kg/cm²"),
            ("Norma principal", "Manual de Puentes MTC 2018"),
            ("Fecha de emisión", datetime.now().strftime("%d/%m/%Y")),
        ),
        widths=(42, 125),
        accent=True,
    )
    p = document.add_paragraph()
    p.paragraph_format.space_before = Pt(30)
    run = p.add_run(
        "La presente memoria desarrolla las expresiones, leyendas, sustituciones numéricas, "
        "resultados y criterios técnicos correspondientes a la geometría y al refuerzo adoptados."
    )
    _format_run(run, 11, italic=True, color=GRAY)
    document.add_page_break()


def _contents(document: Document) -> None:
    document.add_heading("Contenido", level=1)
    _body(document, "La memoria se organiza siguiendo la secuencia del modelo de cálculo y conserva estilos jerárquicos de Word.")
    _table(
        document,
        ("Sección", "Contenido desarrollado"),
        (
            ("1", "Bases de diseño, materiales, geometría y acciones"),
            ("2", "Pesos propios, relleno y resultantes verticales"),
            ("3", "Empujes de suelo, sobrecargas y acción sísmica"),
            ("4", "Combinaciones LRFD y verificaciones de estabilidad"),
            ("5", "Resistencia pasiva y diseño del dentellón"),
            ("6", "Diseño estructural de pantalla, zapata y dentellón"),
            ("7", "Fisuración, desarrollo, corte de barras y acero secundario"),
            ("8", "Cuadro de detalle y resumen del diseño adoptado"),
            ("9", "Referencias normativas"),
        ),
        widths=(25, 142),
        accent=True,
    )
    document.add_page_break()


def _design_basis(
    document: Document,
    result: AbutmentDesignResult,
    chart_dir: Path,
    labels: _ReportLabels,
) -> None:
    data = result.inputs
    g = data.geometry
    m = data.materials
    document.add_heading("1. Bases de diseño", level=1)
    _body(document, labels.analysis_intro)
    document.add_heading("1.1 Materiales y parámetros geotécnicos", level=2)
    _table(
        document,
        ("Parámetro", "Símbolo", "Valor adoptado"),
        (
            ("Resistencia del concreto", "f'c", f"{m.concrete_strength_kg_cm2:.1f} kg/cm²"),
            ("Fluencia del acero", "fy", f"{m.steel_yield_kg_cm2:.1f} kg/cm²"),
            ("Peso específico del concreto", "γc", f"{m.concrete_unit_weight_kg_m3 / 1000:.3f} Tn/m³"),
            ("Peso específico del suelo", "γs", f"{m.soil_unit_weight_kg_m3 / 1000:.3f} Tn/m³"),
            ("Ángulo de fricción", "φ", f"{data.soil.friction_angle_deg:.2f}°"),
            ("Fricción muro-suelo", "δ", f"{data.soil.wall_soil_friction_deg:.2f}°"),
            ("Pendiente del relleno", "β", f"{data.soil.backfill_slope_deg:.2f}°"),
            ("Ángulo de la cara posterior", "θ", f"{data.soil.wall_backface_angle_deg:.2f}°"),
            ("Presión admisible", "qadm", f"{data.soil.allowable_bearing_kg_cm2:.3f} kg/cm²"),
            ("PGA y factor Fpga", "PGA; Fpga", f"{data.soil.pga:.3f}; {data.soil.fpga:.3f}"),
        ),
        widths=(78, 30, 59),
    )
    document.add_heading("1.2 Geometría adoptada", level=2)
    geometry_rows = [
        ("Altura retenida", "H", f"{g.retained_height_m:.3f} m"),
        ("Espesor de zapata", "D", f"{g.footing_thickness_m:.3f} m"),
        ("Ancho de zapata", "B", f"{g.footing_width_m:.3f} m"),
        ("Longitud de puntera", "Lp", f"{g.toe_length_m:.3f} m"),
        ("Espesor inferior de pantalla", "ei", f"{g.lower_stem_thickness_m:.3f} m"),
        ("Espesor superior de pantalla", "es", f"{g.upper_stem_thickness_m:.3f} m"),
        ("Longitud de talón", "Lt", f"{g.heel_length_m:.3f} m"),
        ("Suelo frontal", "hf", f"{g.front_soil_depth_m:.3f} m"),
    ]
    if not data.is_pure_wall:
        geometry_rows.extend(
            (
                ("Longitud de cajuela", "Lc", f"{g.bearing_seat_length_m:.3f} m"),
                ("Espesor parapeto posterior", "ep", f"{g.seat_wall_width_m:.3f} m"),
                ("Altura de cajuela", "hc", f"{g.seat_block_height_m:.3f} m"),
                ("Altura bloque cajuela", "hb", f"{g.backwall_drop_m:.3f} m"),
                ("Altura transición", "ht", f"{g.backwall_taper_height_m:.3f} m"),
                ("Retiro/transición t1", "t1", f"{g.small_batter_width_m:.3f} m"),
                ("Retiro superior t2", "t2", f"{g.backfill_step_width_m:.3f} m"),
            )
        )
    _table(
        document,
        ("Parámetro", "Símbolo", "Valor"),
        tuple(geometry_rows),
        widths=(78, 30, 59),
    )
    hp_label = "Hp" if data.is_pure_wall else "Hp'"
    hp_comment = (
        "La altura se utiliza para obtener los empujes y sus brazos respecto de la cara superior de la zapata."
        if data.is_pure_wall
        else "La altura libre de pantalla Hp' excluye la cajuela y el bloque de asiento del tablero."
    )
    _calc(
        document,
        "Altura libre de pantalla",
        f"{hp_label} = H − D",
        f"{hp_label}: altura de pantalla sobre la zapata; H: altura retenida desde el fondo; D: espesor de zapata.",
        f"{hp_label} = {g.retained_height_m:.3f} − {g.footing_thickness_m:.3f} = {g.stem_height_above_footing_m:.3f} m",
        f"La altura libre de pantalla es {hp_label} = {g.stem_height_above_footing_m:.3f} m.",
        hp_comment,
        REF_EARTH,
    )
    _calc(
        document,
        "Longitud del talón",
        "Lt = B − Lp − ei",
        "Lt: longitud del talón; B: ancho total; Lp: puntera; ei: espesor inferior de pantalla.",
        f"Lt = {g.footing_width_m:.3f} − {g.toe_length_m:.3f} − {g.lower_stem_thickness_m:.3f} = {g.heel_length_m:.3f} m",
        f"La longitud geométrica del talón es Lt = {g.heel_length_m:.3f} m.",
        "La suma de puntera, pantalla y talón reproduce exactamente el ancho adoptado de la zapata.",
        REF_STABILITY,
    )
    geometry = save_abutment_geometry(result, chart_dir / "geometria_estribo.png")
    _picture(document, geometry, labels.geometry_caption)
    if not data.is_pure_wall:
        document.add_heading("1.3 Acciones transferidas por el tablero", level=2)
        loads = data.loads
        _table(
            document,
            ("Acción", "Símbolo", "Valor por metro de estribo"),
            (
                ("Carga permanente estructural", "PDC", f"{loads.pdc_tn_m:.3f} Tn/m"),
                ("Superficie de rodadura", "PDW", f"{loads.pdw_tn_m:.3f} Tn/m"),
                ("Carga peatonal vertical", "PPL", f"{loads.ppl_tn_m:.3f} Tn/m"),
                ("Carga vehicular con impacto", "PLL+IM", f"{loads.pll_im_tn_m:.3f} Tn/m"),
                ("Frenado longitudinal", "BR", f"{loads.braking_tn_m:.3f} Tn/m"),
            ),
            widths=(83, 29, 55),
        )
        _comment(document, "Las reacciones del tablero se introducen sin factor y por metro lineal; los factores se aplican posteriormente dentro de cada estado límite.")
    else:
        _comment(
            document,
            "El muro se modela sin transferencia de acciones del tablero; las combinaciones LRFD "
            "consideran únicamente pesos propios, relleno, empujes y sismo.",
        )


def _weights(document: Document, result: AbutmentDesignResult, labels: _ReportLabels) -> None:
    data = result.inputs
    gamma_c = data.materials.concrete_unit_weight_kg_m3 / 1000.0
    gamma_s = data.materials.soil_unit_weight_kg_m3 / 1000.0
    document.add_heading("2. Pesos y resultantes verticales", level=1)
    _body(document, "Cada componente se conserva con su área, peso, brazo respecto de la puntera y momento estabilizante.")
    document.add_heading("2.1 Componentes de concreto", level=2)
    concrete_rows = tuple(
        (
            component.name,
            f"{component.value_tn_m / gamma_c:.3f}",
            f"{gamma_c:.3f}",
            f"{component.value_tn_m:.3f}",
            f"{component.arm_m:.3f}",
            f"{component.moment_tn_m_m:.3f}",
        )
        for component in result.concrete_components
    )
    _table(document, ("Componente", "A (m²)", "γc", "W (Tn/m)", "x (m)", "W·x"), concrete_rows, widths=(58, 21, 20, 27, 19, 22))
    _table(
        document,
        ("Componente", "Expresión Ai", "Ai (m²)", "xi (m)"),
        concrete_geometry_rows(result),
        widths=(52, 55, 30, 30),
    )
    _calc(
        document,
        "Peso y momento de cada componente",
        "Wi = Ai·γc·b ; Mi = Wi·xi ; xDC = ΣMi/ΣWi",
        "Wi: peso lineal; Ai: área de la sección; γc: peso específico; b: franja unitaria; xi: brazo desde la puntera; Mi: momento estabilizante.",
        f"γc = {gamma_c:.3f} Tn/m³; b = {data.geometry.strip_width_m:.2f} m\n"
        f"ΣWi = {result.dc_self_weight_tn_m:.3f} Tn/m; ΣMi = {result.dc_self_weight_tn_m * result.dc_self_x_m:.3f} Tn·m/m\n"
        f"xDC = {result.dc_self_weight_tn_m * result.dc_self_x_m:.3f}/{result.dc_self_weight_tn_m:.3f} = {result.dc_self_x_m:.3f} m",
        f"El peso propio del {labels.weight_owner} es {result.dc_self_weight_tn_m:.3f} Tn/m y su brazo resultante es {result.dc_self_x_m:.3f} m.",
        f"La descomposición mantiene cada volumen (pantalla, zapata y componentes asociados) en su posición física.",
        REF_STABILITY,
    )
    document.add_heading("2.2 Peso del relleno sobre el talón", level=2)
    soil_rows = tuple(
        (
            component.name,
            f"{component.value_tn_m / gamma_s:.3f}",
            f"{gamma_s:.3f}",
            f"{component.value_tn_m:.3f}",
            f"{component.arm_m:.3f}",
            f"{component.moment_tn_m_m:.3f}",
        )
        for component in result.soil_components
    )
    _table(document, ("Componente", "A (m²)", "γs", "W (Tn/m)", "x (m)", "W·x"), soil_rows, widths=(58, 21, 20, 27, 19, 22))
    _calc(
        document,
        "Resultante del relleno",
        "WEV = ΣWi ; xEV = Σ(Wi·xi)/ΣWi",
        "WEV: peso del relleno; Wi: peso de cada bloque; xi: brazo; xEV: posición de la resultante.",
        f"WEV = {result.ev_weight_tn_m:.3f} Tn/m; xEV = {result.ev_weight_tn_m * result.ev_x_m:.3f}/{result.ev_weight_tn_m:.3f} = {result.ev_x_m:.3f} m",
        f"La resultante EV es {result.ev_weight_tn_m:.3f} Tn/m, ubicada a {result.ev_x_m:.3f} m de la puntera.",
        "El peso del relleno se considera favorable para vuelco y fricción, con el factor que corresponde en cada combinación.",
        REF_STABILITY,
    )


def _earth_pressures(document: Document, result: AbutmentDesignResult) -> None:
    data = result.inputs
    g = data.geometry
    p = result.pressures
    gamma = data.materials.soil_unit_weight_kg_m3 / 1000.0
    effective_heel = g.heel_length_m - g.backfill_step_width_m
    document.add_heading("3. Empujes de suelo, sobrecargas y sismo", level=1)
    _calc(document, "Coeficiente activo de Coulomb", *coulomb_ka_trace(result), REF_EARTH)
    _calc(document, "Altura equivalente de sobrecarga vehicular", *surcharge_height_trace(result), REF_EARTH)
    _calc(
        document,
        "Sobrecarga vehicular equivalente",
        "LSy = Lt,ef·h'·γs ; LSx = Ka·h'·γs·H",
        "LSy: componente vertical; LSx: empuje horizontal uniforme; Lt,ef: talón efectivo; h': altura equivalente; γs: peso específico; H: altura retenida.",
        f"Lt,ef = {effective_heel:.3f} m; h' = {p.live_surcharge_height_m:.3f} m\n"
        f"LSy = {effective_heel:.3f}·{p.live_surcharge_height_m:.3f}·{gamma:.3f} = {p.lsy_tn_m:.3f} Tn/m\n"
        f"LSx = {p.ka:.5f}·{p.live_surcharge_height_m:.3f}·{gamma:.3f}·{g.retained_height_m:.3f} = {p.lsx_tn_m - p.pedestrian_lsx_tn_m:.3f} Tn/m",
        f"La sobrecarga vehicular produce LSy = {p.lsy_tn_m:.3f} Tn/m y LSx = {p.lsx_tn_m - p.pedestrian_lsx_tn_m:.3f} Tn/m.",
        "La altura equivalente se aplica como presión uniforme sobre toda la altura activa.",
        REF_EARTH,
    )
    _calc(
        document,
        "Empuje estático del relleno",
        "EH = 0.5·Ka·γs·H²",
        "EH: empuje activo resultante; Ka: coeficiente activo; γs: peso específico del suelo; H: altura retenida.",
        f"EH = 0.5·{p.ka:.5f}·{gamma:.3f}·{g.retained_height_m:.3f}² = {p.eh_tn_m:.3f} Tn/m",
        f"El empuje estático resultante es EH = {p.eh_tn_m:.3f} Tn/m.",
        "La distribución es triangular y su resultante actúa a H/3 desde la base del diagrama.",
        REF_EARTH,
    )
    _calc(document, "Brazos de las acciones horizontales", *pressure_arms_trace(result), REF_EARTH)
    _calc(document, "Parámetros sísmicos y ángulo ψ", *seismic_angle_trace(result), REF_EARTH)
    _calc(document, "Coeficiente sísmico Mononobe-Okabe kAE", *mononobe_okabe_trace(result), REF_EARTH)
    _calc(
        document,
        "Incremento sísmico de empuje",
        "PAE = 0.5·kAE·γs·H² ; EQterr = PAE − EH",
        "PAE: empuje activo sísmico total; kAE: coeficiente Mononobe-Okabe; EQterr: incremento sísmico respecto del empuje estático.",
        f"PAE = 0.5·{p.k_ae:.5f}·{gamma:.3f}·{g.retained_height_m:.3f}² = {p.pae_tn_m:.3f} Tn/m\n"
        f"EQterr = {p.pae_tn_m:.3f} − {p.eh_tn_m:.3f} = {p.eq_terr_tn_m:.3f} Tn/m",
        f"Se obtiene PAE = {p.pae_tn_m:.3f} Tn/m y EQterr = {p.eq_terr_tn_m:.3f} Tn/m.",
        "El incremento EQ se combina únicamente en el estado de Evento Extremo I.",
        REF_EARTH,
    )
    _calc(document, "Fuerza inercial del muro y combinaciones MTC PAE/PIR", *pir_trace(result), REF_EARTH)
    _calc(document, "Envolvente sísmica Art. 2.8.1.1.14.1", *mtc_seismic_envelope_trace(result), REF_EARTH)
    if not result.inputs.is_pure_wall:
        _calc(document, "Fuerza inercial de la superestructura PEQ", *peq_trace(result), REF_EARTH)
    pressure_summary = [
        ("Ka", f"{p.ka:.5f}"),
        ("kAE", f"{p.k_ae:.5f}"),
        ("ψ", f"{p.seismic_angle_deg:.3f}°"),
        ("LS vertical vehicular", f"{p.lsy_tn_m:.3f} Tn/m"),
        ("LS horizontal total", f"{p.lsx_tn_m:.3f} Tn/m"),
        ("EH", f"{p.eh_tn_m:.3f} Tn/m"),
        ("PAE", f"{p.pae_tn_m:.3f} Tn/m"),
        ("EQ del terreno", f"{p.eq_terr_tn_m:.3f} Tn/m"),
        ("PIR", f"{p.pir_tn_m:.3f} Tn/m"),
        ("0.5PIR", f"{p.half_pir_tn_m:.3f} Tn/m"),
    ]
    if not result.inputs.is_pure_wall:
        pressure_summary.append(("PEQ superestructura", f"{p.peq_tn_m:.3f} Tn/m"))
    _table(
        document,
        ("Efecto", "Valor"),
        tuple(pressure_summary),
        widths=(100, 67),
    )


def _stability(
    document: Document,
    result: AbutmentDesignResult,
    chart_dir: Path,
    labels: _ReportLabels,
) -> None:
    document.add_heading("4. Combinaciones y estabilidad", level=1)
    _body(document, labels.stability_intro)
    document.add_heading("4.1 Factores LRFD", level=2)
    _table(
        document,
        ("Estado", "DC", "DW", "EV", "LL", "LSv", "LSh", "EH", "EQ", "BR"),
        tuple(
            (
                f.name,
                f"{f.dc:.2f}", f"{f.dw:.2f}", f"{f.ev:.2f}", f"{f.ll:.2f}",
                f"{f.ls_vertical:.2f}", f"{f.ls_horizontal:.2f}", f"{f.eh:.2f}",
                f"{f.eq:.2f}", f"{f.br:.2f}",
            )
            for f in result.load_factors
        ),
        widths=(44, 13.6, 13.6, 13.6, 13.6, 13.6, 13.6, 13.6, 13.6, 13.6),
    )
    _comment(document, "Los factores se aplican a cada componente antes de sumar fuerzas y momentos. No se combinan máximos provenientes de estados incompatibles.")
    if result.inputs.is_pure_wall:
        document.add_heading("4.2 Estabilidad del muro", level=2)
        for state in result.without_bridge + result.service_without_bridge:
            _stability_state_calculations(document, result, state, "muro puro")
        stability_groups = (("Muro puro", result.without_bridge + result.service_without_bridge),)
    else:
        document.add_heading("4.2 Condición con puente", level=2)
        for state in result.with_bridge + result.service_with_bridge:
            _stability_state_calculations(document, result, state, "con puente")
        document.add_heading("4.3 Condición sin puente", level=2)
        for state in result.without_bridge + result.service_without_bridge:
            _stability_state_calculations(document, result, state, "sin puente")
        stability_groups = (
            ("Con puente", result.with_bridge + result.service_with_bridge),
            ("Sin puente", result.without_bridge + result.service_without_bridge),
        )
    document.add_heading("4.4 Resumen de estabilidad", level=2)
    rows = []
    for condition, states in stability_groups:
        for state in states:
            rows.append(
                (
                    condition,
                    state.name,
                    f"{state.eccentricity_m:.3f}",
                    state.overturning_status,
                    state.sliding_with_key_status or state.sliding_status,
                    f"{state.geotechnical_pressure_kg_cm2:.3f}",
                    f"{state.q_allow_kg_cm2:.3f}",
                    state.bearing_status,
                )
            )
    _table(document, ("Condición", "Estado", "e (m)", "Vuelco", "Desliz.", "q", "qlím", "Estado q"), rows, widths=(25, 35, 17, 18, 19, 15, 15, 23))
    pressure_chart = save_contact_pressure_diagrams(result, chart_dir / "presiones_contacto.png")
    _picture(document, pressure_chart, labels.pressure_chart_caption)


def _stability_state_calculations(
    document: Document,
    result: AbutmentDesignResult,
    state: StabilityStateResult,
    condition: str,
) -> None:
    b = result.inputs.geometry.footing_width_m
    phi = result.inputs.soil.friction_angle_deg
    factors = factors_for_state(result, state)
    title = f"{state.name} - {condition}"
    document.add_heading(title, level=3)
    if result.inputs.is_pure_wall or condition != "con puente":
        vertical = result.components.vertical_without_bridge
        horizontal = horizontal_components_for_state(result, state, with_bridge=False)
    else:
        vertical = result.components.vertical_with_bridge
        horizontal = horizontal_components_for_state(result, state, with_bridge=True)
    if state.seismic_papir_combination:
        _comment(
            document,
            f"Combinación sísmica MTC Art. 2.8.1.1.14.1 adoptada en este estado: "
            f"{state.seismic_papir_combination}.",
        )
    _comment(document, "Inventario vertical factorizado (fuerzas estabilizantes):")
    _table(
        document,
        ("Componente", "Tipo", "P (Tn/m)", "x (m)", "γ", "γP", "γP·x"),
        component_factor_rows(vertical, factors, horizontal=False),
        widths=(46, 14, 22, 18, 14, 22, 31),
    )
    _comment(document, "Inventario horizontal factorizado (fuerzas volcadoras/deslizantes):")
    _table(
        document,
        ("Componente", "Tipo", "H (Tn/m)", "y (m)", "γ", "γH", "γH·y"),
        component_factor_rows(horizontal, factors, horizontal=True),
        widths=(46, 14, 22, 18, 14, 22, 31),
    )
    _calc(
        document,
        "Resultantes factorizadas",
        "Vu = Σ(γi·Pi) ; MVu = Σ(γi·Pi·xi) ; Hu = Σ(γi·Hi) ; MHu = Σ(γi·Hi·yi)",
        "Vu: resultante vertical; MVu: momento estabilizante; Hu: resultante horizontal; MHu: momento volcador; γi: factor LRFD; xi, yi: brazos.",
        f"Vu = {state.vu_tn_m:.3f} Tn/m; MVu = {state.stabilizing_moment_tn_m_m:.3f} Tn·m/m\n"
        f"Hu = {state.hu_tn_m:.3f} Tn/m; MHu = {state.overturning_moment_tn_m_m:.3f} Tn·m/m",
        f"Para {title} se obtienen las cuatro resultantes factorizadas indicadas.",
        "Las fuerzas y momentos proceden de una única combinación compatible del estado límite.",
        REF_COMBINATIONS,
    )
    _calc(
        document,
        "Posición de la resultante y excentricidad",
        "xR = (MVu − MHu)/Vu ; e = B/2 − xR",
        "xR: distancia de la resultante desde la puntera; e: excentricidad respecto del centro; B: ancho de zapata.",
        f"xR = ({state.stabilizing_moment_tn_m_m:.3f} − {state.overturning_moment_tn_m_m:.3f})/{state.vu_tn_m:.3f} = {state.resultant_x_m:.3f} m\n"
        f"e = {b:.3f}/2 − {state.resultant_x_m:.3f} = {state.eccentricity_m:.3f} m",
        f"|e| = {abs(state.eccentricity_m):.3f} m.",
        "La excentricidad se compara a continuación con el límite del estado límite.",
        REF_STABILITY,
    )
    _calc(document, "Límite de excentricidad y contacto", *eccentricity_limit_trace(result, state), REF_STABILITY)
    if state.key_resistance_tn_m is None:
        passive_contribution = 0.0
        total_resistance = state.friction_resistance_tn_m
    else:
        total_resistance = state.key_resistance_tn_m
        passive_contribution = max(total_resistance - state.friction_resistance_tn_m, 0.0)
    sliding_status = state.sliding_with_key_status or state.sliding_status
    _calc(
        document,
        "Verificación al deslizamiento",
        "Ff = Vu·tan(φ) ; Rdes = Ff + φep·Rep ≥ Hu",
        "Ff: resistencia por fricción; φ: fricción del suelo; φep·Rep: resistencia pasiva factorizada; Hu: demanda horizontal.",
        f"Ff = {state.vu_tn_m:.3f}·tan({phi:.3f}°) = {state.friction_resistance_tn_m:.3f} Tn/m\n"
        f"Rdes = {state.friction_resistance_tn_m:.3f} + {passive_contribution:.3f} = {total_resistance:.3f} Tn/m\n"
        f"{total_resistance:.3f} ≥ {state.hu_tn_m:.3f}",
        f"El estado de deslizamiento es {sliding_status}.",
        _status_comment(sliding_status, "La fricción y la resistencia pasiva movilizable cubren la demanda horizontal."),
        REF_STABILITY,
    )
    if state.contact_type == "Completo":
        structural_formula = "qmax,min = Vu/B·(1 ± 6|e|/B)"
        structural_sub = (
            f"qmax = {state.vu_tn_m:.3f}/{b:.3f}·(1 + 6·{abs(state.eccentricity_m):.3f}/{b:.3f})/10 = {state.qmax_kg_cm2:.3f} kg/cm²\n"
            f"qmin = {state.vu_tn_m:.3f}/{b:.3f}·(1 − 6·{abs(state.eccentricity_m):.3f}/{b:.3f})/10 = {state.qmin_kg_cm2:.3f} kg/cm²"
        )
    else:
        structural_formula = "Lc = 3·(B/2 − |e|) ; qmax = 2·Vu/Lc"
        structural_sub = (
            f"Lc = 3·({b:.3f}/2 − |{state.eccentricity_m:.3f}|) = {state.contact_length_m:.3f} m\n"
            f"qmax = 2·{state.vu_tn_m:.3f}/{state.contact_length_m:.3f}/10 = {state.qmax_kg_cm2:.3f} kg/cm²; "
            f"qmin = {state.qmin_kg_cm2:.3f} kg/cm²"
        )
    _calc(
        document,
        "Presión de contacto estructural y Meyerhof",
        "B' = B − 2|e| ; qM = Vu/B' ; " + structural_formula,
        "B': ancho efectivo Meyerhof; qM: presión geotécnica; Lc: longitud comprimida; qmax, qmin: presiones del diagrama estructural.",
        f"B' = {b:.3f} − 2·|{state.eccentricity_m:.3f}| = {state.effective_width_m:.3f} m\n"
        f"qM = {state.vu_tn_m:.3f}/{state.effective_width_m:.3f}/10 = {state.geotechnical_pressure_kg_cm2:.3f} kg/cm²\n"
        f"{structural_sub}",
        f"La presión Meyerhof es qM = {state.geotechnical_pressure_kg_cm2:.3f} kg/cm².",
        "A continuación se desarrolla la presión límite qlím del estado.",
        REF_STABILITY,
    )
    _calc(document, "Presión admisible factorizada qlím", *allowable_bearing_trace(result, state), REF_STABILITY)


def _key_design(document: Document, result: AbutmentDesignResult) -> None:
    document.add_heading("5. Dentellón y resistencia pasiva", level=1)
    if result.key is None:
        _body(document, "La solución adoptada no requiere dentellón; la fricción de base satisface el deslizamiento en todos los estados.")
        return
    data = result.inputs
    key = result.key
    gamma = data.materials.soil_unit_weight_kg_m3 / 1000.0
    h = data.geometry.front_soil_depth_m
    hk = data.key.height_m
    _calc(
        document,
        "Coeficiente pasivo",
        "Kp = tan²(45° + φ/2)",
        "Kp: coeficiente pasivo de Rankine; φ: ángulo de fricción interna del suelo.",
        f"Kp = tan²(45° + {data.soil.friction_angle_deg:.3f}°/2) = {key.kp:.5f}",
        f"Se adopta Kp = {key.kp:.5f}.",
        "El coeficiente se aplica únicamente al suelo frontal cuya movilización es compatible con el dentellón.",
        ABUTMENT_KEY_REFERENCE,
    )
    _calc(
        document,
        "Presiones pasivas sobre el dentellón",
        "pp,sup = Kp·γs·hf ; pp,inf = Kp·γs·(hf + hk)",
        "pp,sup, pp,inf: presiones pasivas; γs: peso específico; hf: suelo frontal; hk: altura del dentellón.",
        f"pp,sup = {key.kp:.5f}·{gamma:.3f}·{h:.3f} = {key.top_pressure_tn_m2:.3f} Tn/m²; pp,inf = {key.kp:.5f}·{gamma:.3f}·({h:.3f}+{hk:.3f}) = {key.bottom_pressure_tn_m2:.3f} Tn/m²",
        f"Las presiones extremas son {key.top_pressure_tn_m2:.3f} y {key.bottom_pressure_tn_m2:.3f} Tn/m².",
        "La variación lineal reproduce el incremento de confinamiento con la profundidad.",
        ABUTMENT_KEY_REFERENCE,
    )
    _calc(
        document,
        "Resistencia pasiva factorizada",
        "Rep = 0.5·(pp,sup + pp,inf)·hk ; Rk = φep·Rep,total",
        "Rep: resistencia del dentellón; Rep,total: incluye el suelo frontal superior cuando se autoriza; φep: factor de resistencia; Rk: aporte de diseño.",
        f"Rep = 0.5·({key.top_pressure_tn_m2:.3f}+{key.bottom_pressure_tn_m2:.3f})·{hk:.3f} = {key.passive_resistance_tn_m:.3f} Tn/m\n"
        f"φep = {data.key.passive_resistance_factor:.3f}\n"
        f"Rk = {data.key.passive_resistance_factor:.3f}·{key.total_passive_resistance_tn_m:.3f} = {key.factored_passive_tn_m:.3f} Tn/m",
        f"El aporte pasivo factorizado del dentellón es Rk = {key.factored_passive_tn_m:.3f} Tn/m.",
        "La resistencia pasiva se suma a la fricción únicamente en la comprobación de deslizamiento.",
        ABUTMENT_KEY_REFERENCE,
    )
    key_height = passive_key_height_trace(result)
    if key_height is not None:
        _calc(document, "Altura de suelo pasivo y factor φep", *key_height, ABUTMENT_KEY_REFERENCE)


def _structural_design(document: Document, result: AbutmentDesignResult) -> None:
    document.add_heading("6. Diseño estructural", level=1)
    _body(document, "Se desarrollan por separado la pantalla, el talón, la puntera y el dentellón. Para cada elemento se muestra la demanda gobernante, el acero requerido y el refuerzo adoptado.")
    for index, case in enumerate(_structural_cases(result), start=1):
        document.add_heading(f"6.{index} {case.name}", level=2)
        _structural_case(document, result, case)


def _structural_case(document: Document, result: AbutmentDesignResult, case: StructuralDesignCase) -> None:
    data = result.inputs
    gross_depth = _gross_depth_cm(result, case.name)
    phi = data.reinforcement.flexural_phi if case.name == "Pantalla" else data.reinforcement.footing_design_phi_for_as
    rho = case.strength_as_cm2_m / (100.0 * case.effective_depth_cm) if case.effective_depth_cm else 0.0
    omega = rho * data.materials.steel_yield_kg_cm2 / data.materials.concrete_strength_kg_cm2
    bar_area = _bar_area_cm2(case.selected_bar_label)
    if case.name == "Pantalla":
        _calc(document, "Origen de Mu y Vu de pantalla", *stem_demand_trace(result), REF_FLEXURE)
    else:
        demand = heel_toe_demand_trace(result, case)
        if demand is not None:
            _calc(document, f"Origen de Mu y Vu - {case.name}", *demand, REF_FLEXURE)
    _calc(document, "Peralte efectivo", *effective_depth_trace(result, case, gross_depth), REF_FLEXURE)
    if case.name == "Pantalla" and case.strength_limit_as_cm2_m:
        _calc(
            document,
            "Acero por resistencia a flexión",
            "As,R = As(Mu,R; φ=0.90) ; As,E = As(Mu,E; φ=1.00) ; As,flex = max(As,R, As,E)",
            "Mu,R: momento de Resistencia I; Mu,E: momento de Evento Extremo; φ: factor de resistencia del estado; As,flex: acero gobernante.",
            f"Mu,R = {case.strength_limit_mu_tn_m_m:.3f} Tn·m/m; φ,R = {data.reinforcement.flexural_phi:.2f}; As,R = {case.strength_limit_as_cm2_m:.3f} cm²/m\n"
            f"Mu,E = {case.extreme_limit_mu_tn_m_m:.3f} Tn·m/m; φ,E = {data.reinforcement.stem_design_phi_for_as:.2f}; As,E = {case.extreme_limit_as_cm2_m:.3f} cm²/m\n"
            f"As,flex = {case.strength_as_cm2_m:.3f} cm²/m",
            f"El acero por resistencia es As,flex = {case.strength_as_cm2_m:.3f} cm²/m, gobernado por el estado de mayor requerimiento.",
            "No se dimensiona por el máximo momento bruto con un único φ; cada estado límite usa su factor MTC 2.7.1.1.4.2a.",
            REF_FLEXURE,
        )
    else:
        _calc(
            document,
            "Acero por resistencia a flexión",
            "ω = [1 − √(1 − 4·0.59·Mu/(φ·f'c·b·d²))]/(2·0.59) ; ρ = ω·f'c/fy ; As = ρ·b·d",
            "ω: índice mecánico; Mu: momento último; φ: factor de resistencia; b: ancho unitario; d: peralte efectivo; ρ: cuantía; As: acero requerido.",
            f"Mu = {case.controlling_moment_tn_m_m:.3f} Tn·m/m; φ = {phi:.3f}; b = 100 cm; d = {case.effective_depth_cm:.2f} cm\n"
            f"ω = {omega:.6f}; ρ = {rho:.6f}; As = {case.strength_as_cm2_m:.3f} cm²/m",
            f"El acero por resistencia es As,flex = {case.strength_as_cm2_m:.3f} cm²/m.",
            "La expresión corresponde a una sección rectangular con bloque equivalente de compresión.",
            REF_FLEXURE,
        )
    _calc(
        document,
        "Capacidad mínima, temperatura y acero requerido",
        *cracking_and_temperature_trace(result, case, gross_depth),
        REF_FLEXURE,
    )
    a_cm = case.provided_as_cm2_m * data.materials.steel_yield_kg_cm2 / (0.85 * data.materials.concrete_strength_kg_cm2 * 100.0)
    _calc(
        document,
        "Refuerzo adoptado y momento resistente",
        "As,prov = Ab/s ; a = As,prov·fy/(0.85·f'c·b) ; Mr = φ·As,prov·fy·(d − a/2)",
        "Ab: área de una barra; s: espaciamiento; a: profundidad del bloque equivalente; Mr: momento resistente.",
        (
            f"As,prov = {bar_area:.3f}/{case.selected_spacing_m:.3f} = {case.provided_as_cm2_m:.3f} cm²/m\n"
            f"a = {a_cm:.3f} cm; Mr = {case.moment_resistance_tn_m_m:.3f} Tn·m/m"
            + (
                f"\nMr,R = {case.strength_moment_resistance_tn_m_m:.3f} Tn·m/m "
                f"({'OK' if case.strength_moment_status == 'OK' else 'NO'} frente a Mu,R = {case.strength_limit_mu_tn_m_m:.3f})\n"
                f"Mr,E = {case.extreme_moment_resistance_tn_m_m:.3f} Tn·m/m "
                f"({'OK' if case.extreme_moment_status == 'OK' else 'NO'} frente a Mu,E = {case.extreme_limit_mu_tn_m_m:.3f})"
                if case.name == "Pantalla" and case.strength_limit_mu_tn_m_m
                else ""
            )
        ),
        f"Se adopta {case.selected_bar_label} @ {case.selected_spacing_m:.3f} m"
        f"{' (selección personalizada del usuario)' if case.is_custom_selection else ''}, "
        f"con estado a flexión {case.moment_status}.",
        _status_comment(
            case.moment_status,
            "El momento resistente cubre la demanda de cada estado límite y la capacidad mínima aplicable.",
        ),
        REF_FLEXURE,
    )
    _calc(document, "Verificación de cortante", *shear_beta_trace(result, case), REF_SHEAR)
    if case.notes:
        _comment(document, case.notes)


def _service_and_detailing(document: Document, result: AbutmentDesignResult) -> None:
    document.add_heading("7. Servicio y detallado", level=1)
    document.add_heading("7.1 Control de fisuración", level=2)
    for check in result.crack_checks:
        _calc(
            document,
            f"Fisuración - {check.element}",
            *crack_control_trace(result, check),
            REF_CRACK,
        )
    document.add_heading("7.2 Desarrollo y anclaje", level=2)
    for check in result.development_checks:
        _calc(
            document,
            f"Desarrollo - {check.element}",
            *development_trace(result, check),
            REF_DEVELOPMENT,
        )
    document.add_heading("7.3 Corte del acero principal de pantalla", level=2)
    cut = result.stem_reinforcement_cut
    if cut is None:
        _body(document, "No se adopta corte del acero principal porque la reducción no resulta práctica con la selección final.")
    else:
        _calc(
            document,
            "Patrón de acero superior continuo",
            *stem_cut_continuous_pattern_trace(result, cut),
            REF_TEMPERATURE,
        )
        _calc(
            document,
            "Altura teórica de corte ht",
            *stem_cut_theoretical_height_trace(result, cut),
            REF_FLEXURE,
        )
        _calc(
            document,
            "Altura constructiva y longitudes de barras",
            *stem_cut_constructive_length_trace(result, cut),
            REF_DEVELOPMENT,
        )
        _body(
            document,
            f"Patrón constructivo adoptado: continúa 1 de cada {cut.continuous_every_n_bars} barras de la parrilla inferior; "
            "las barras restantes terminan en la altura constructiva de corte.",
        )
        _table(
            document,
            ("Zona", "Refuerzo", "As provisto", "Longitud"),
            (
                ("Inferior", f"{cut.lower_bar_label} @ {cut.lower_spacing_m:.3f} m", f"{cut.lower_provided_as_cm2_m:.3f} cm²/m", f"{cut.lower_cut_bar_length_m:.3f} m"),
                (f"Superior continuo (1 de cada {cut.continuous_every_n_bars})", f"{cut.upper_bar_label} @ {cut.upper_spacing_m:.3f} m", f"{cut.upper_provided_as_cm2_m:.3f} cm²/m", f"{cut.continuous_bar_length_m:.3f} m"),
            ),
            widths=(39, 55, 36, 37),
        )
        _comment(document, f"Estado del corte: {cut.status}. {cut.notes}")
    document.add_heading("7.4 Acero secundario y transversal", level=2)
    for case in result.secondary_reinforcement:
        _calc(
            document,
            case.name,
            *secondary_temperature_trace(case),
            REF_TEMPERATURE,
        )
        _comment(document, f"Ubicación: {case.face}; dirección: {case.direction}. {case.notes}")


def _summary(document: Document, result: AbutmentDesignResult) -> None:
    document.add_heading("8. Detalle y resumen adoptado", level=1)
    document.add_heading("8.1 Cuadro de barras", level=2)
    _table(
        document,
        ("Marca", "Elemento", "Cara/ubicación", "Barra", "s (m)", "L (m)", "Anclaje (m)"),
        tuple(
            (
                detail.mark,
                detail.element,
                detail.face,
                detail.bar_label,
                f"{detail.spacing_m:.3f}",
                f"{detail.length_m:.3f}",
                f"{detail.anchorage_m:.3f}",
            )
            for detail in result.bar_details
        ),
        widths=(17, 38, 41, 19, 17, 17, 20),
    )
    _comment(document, "Las longitudes corresponden a la franja de diseño y deben coordinarse con recubrimientos, empalmes, radios de doblado y planos de construcción.")
    document.add_heading("8.2 Resumen del diseño", level=2)
    rows = []
    for case in _structural_cases(result):
        rows.append((case.name, "Acero principal", f"{case.selected_bar_label} @ {case.selected_spacing_m:.3f} m", case.moment_status))
    for case in result.secondary_reinforcement:
        rows.append((case.element, case.face, f"{case.selected_bar_label} @ {case.selected_spacing_m:.3f} m", case.status))
    _table(document, ("Elemento", "Función/ubicación", "Refuerzo adoptado", "Estado"), rows, widths=(42, 52, 52, 21))
    all_statuses = [case.moment_status for case in _structural_cases(result)]
    all_statuses += [case.shear_status for case in _structural_cases(result)]
    all_statuses += [case.status for case in result.secondary_reinforcement]
    all_statuses += [check.status for check in result.crack_checks]
    all_statuses += [check.status for check in result.development_checks]
    overall = "CUMPLE" if all(_is_ok(value) for value in all_statuses) else "REVISAR"
    _comment(document, f"Estado global del diseño adoptado: {overall}. El reporte conserva exclusivamente las opciones de refuerzo seleccionadas en el flujo de diseño.")


def _references(document: Document) -> None:
    document.add_heading("9. Referencias normativas", level=1)
    for text in (
        "Ministerio de Transportes y Comunicaciones. Manual de Puentes, Lima, 2018. Archivo de consulta: docs/Manual de Puentes MTC 2018 (PGA).pdf.",
        "Rodríguez Serquén, Arturo. Puentes con AASHTO LRFD 2020, 9th Edition. Archivo de consulta en la carpeta docs del proyecto.",
        "AASHTO LRFD Bridge Design Specifications, criterios equivalentes incorporados mediante las referencias del Manual de Puentes MTC 2018.",
    ):
        document.add_paragraph(text, style="List Bullet")


def _structural_cases(result: AbutmentDesignResult) -> tuple[StructuralDesignCase, ...]:
    cases = [result.stem_design, result.heel_design, result.toe_design]
    if result.key_design is not None:
        cases.append(result.key_design)
    return tuple(cases)


def _gross_depth_cm(result: AbutmentDesignResult, element: str) -> float:
    g = result.inputs.geometry
    if element == "Pantalla":
        return g.lower_stem_thickness_m * 100.0
    if element == "Diente de concreto":
        return result.inputs.key.width_m * 100.0
    return g.footing_thickness_m * 100.0


def _bar_area_cm2(label: str) -> float:
    normalized = label.strip().replace("Ø", "").strip()
    for bar in REINFORCING_BAR_CATALOG:
        if bar.label == normalized:
            return bar.area_cm2
    raise ValueError(f"No existe la barra {label} en el catálogo.")


def _status_comment(status: str, ok_text: str) -> str:
    return ok_text if _is_ok(status) else "La verificación no cumple; debe modificarse la geometría o el refuerzo y repetirse el cálculo antes de emitir planos."


def _is_ok(status: str) -> bool:
    return str(status).strip().upper() in {"OK", "CUMPLE", "ADECUADO"}
