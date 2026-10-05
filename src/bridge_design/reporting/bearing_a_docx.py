"""Word Método A con el formato tipográfico de diseno-apoyos-neopreno.

Las expresiones y verificaciones provienen del mismo registro que consola y
JSON. La figura se dibuja con la composición realmente adoptada.
"""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.shared import Mm, Pt
from PIL import Image, ImageDraw, ImageFont

from bridge_design.domain.bearing_method_a import BearingAResult, MTC_URL
from bridge_design.reporting.deck_docx import (
    GRAY, TEAL, _add_native_equation, _append_math_expression, _body, _configure_document,
    _enforce_uniform_typography, _field, _format_run, _math_run, _split_top_level, _table,
)


def select_bearing_a_docx_path() -> Path | None:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost",True)
    try:
        path = filedialog.asksaveasfilename(
            parent=root,title="Guardar memoria de cálculo del apoyo Método A",
            defaultextension=".docx",initialfile="MEMORIA_CALCULO_APOYO_METODO_A.docx",
            filetypes=(("Documento de Word","*.docx"),),
        )
    finally:
        root.destroy()
    return Path(path) if path else None


def _diagram(result: BearingAResult) -> BytesIO:
    g = result.adopted
    canvas = Image.new("RGB",(1700,1000),"white")
    d = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf",30)
        small = ImageFont.truetype("arial.ttf",26)
    except OSError:
        font = ImageFont.load_default(size=30)
        small = ImageFont.load_default(size=26)
    d.text((70,30),"APOYO ELASTOMERICO REFORZADO CON ACERO",font=font,fill="black")
    d.text((100,100),"Planta",font=font,fill="black")
    scale = min(600/g.width_cm,520/g.length_cm)
    x,y = 100,165
    w,l = g.width_cm*scale,g.length_cm*scale
    d.rectangle((x,y,x+w,y+l),fill="#ededed",outline="black",width=4)
    d.text((x,y+l+20),f"W = {g.width_cm*10:g} mm (transversal)",font=small,fill="black")
    d.text((x,y+l+65),f"L = {g.length_cm*10:g} mm (longitudinal)",font=small,fill="black")
    d.line((x+w*.5,y+l*.8,x+w*.5,y+l*.2),fill="black",width=4)
    d.polygon(((x+w*.5,y+l*.12),(x+w*.5-13,y+l*.2),(x+w*.5+13,y+l*.2)),fill="black")
    d.text((x+25,y+40),"Direccion del trafico",font=small,fill="black")
    d.text((850,100),"Seccion y composicion",font=font,fill="black")
    scale_h = 480/result.value("HEIGHT")
    x,y = 850,165
    composition = [g.exterior_cm]
    for _ in range(g.interior_layers):
        composition.extend((g.steel_cm,g.interior_cm))
    composition.extend((g.steel_cm,g.exterior_cm))
    for index,h in enumerate(composition):
        steel = index%2==1
        end = y+h*scale_h
        d.rectangle((x,y,x+620,end),fill="#383838" if steel else "#e5e5e5",outline="black",width=2)
        y = end
    d.text((x,y+20),f"H = {result.value('HEIGHT')*10:g} mm",font=small,fill="black")
    d.text((850,730),f"{g.interior_layers} capas interiores de {g.interior_cm*10:g} mm",font=small,fill="black")
    d.text((850,775),f"2 capas exteriores de {g.exterior_cm*10:g} mm",font=small,fill="black")
    d.text((850,820),f"{g.interior_layers+1} zunchos de {g.steel_cm*10:g} mm",font=small,fill="black")
    d.text((100,920),"Esquema de capas; dimensiones y recubrimientos según la geometría adoptada.",font=small,fill="black")
    stream = BytesIO()
    canvas.save(stream,format="PNG")
    stream.seek(0)
    return stream


def _trace(document, step) -> None:
    """Mismo desarrollo con ecuación editable, leyenda y sustitución compacta."""
    first = len(document.paragraphs)
    document.add_heading(step.id+" "+step.title,level=3)
    expression = step.formula.replace("<=", "≤").replace(">=", "≥").replace(" - ", " − ")
    strict_split = _split_top_level(expression,("<",))
    if strict_split:
        # El autor OMML compartido no reconoce '<': separar antes de la fracción.
        left, operator, right = strict_split
        p = document.add_paragraph(style="Equation")
        math = OxmlElement("m:oMath")
        _append_math_expression(math,left)
        math.append(_math_run(" "+operator+" "))
        _append_math_expression(math,right)
        p._p.append(math)
    else:
        _add_native_equation(document,expression)
    _body(document,"Donde: "+step.legend+".")
    p = document.add_paragraph("Reemplazando los valores correspondientes:")
    p.paragraph_format.keep_with_next = True
    # Cada sustitución se conserva literalmente además de la ecuación nativa.
    p = document.add_paragraph(step.substitution)
    p.paragraph_format.left_indent = Mm(4)
    p.paragraph_format.keep_with_next = True
    value = "sin datos suficientes" if step.value is None else f"{step.value:.8g} {step.unit}"
    text = "Resultado: "+value
    if step.limit is not None:
        text += f"; límite {'<' if step.strict else '<='} {step.limit:.8g} {step.unit}"
    if step.status != "CALCULADO":
        text += "; "+step.status
    p = document.add_paragraph()
    _format_run(p.add_run(text),11,bold=True,color=TEAL)
    if step.note:
        _body(document,step.note)
    p = document.add_paragraph("Referencia: "+step.reference)
    p.paragraph_format.space_after = Pt(8)
    paragraphs = document.paragraphs[first:]
    for paragraph in paragraphs:
        paragraph.paragraph_format.keep_together = True
        paragraph.paragraph_format.keep_with_next = True
    paragraphs[-1].paragraph_format.keep_with_next = False


def generate_bearing_a_docx(result: BearingAResult, output_path: str | Path) -> Path:
    path = Path(output_path).expanduser().resolve().with_suffix(".docx")
    path.parent.mkdir(parents=True,exist_ok=True)
    doc = Document()
    _configure_document(doc)
    # Word's built-in Title style may carry a blue rule from its template.
    for name in ("Title", "Subtitle"):
        ppr = doc.styles[name]._element.pPr
        if ppr is not None:
            for child in list(ppr):
                if child.tag.endswith("}pBdr"):
                    ppr.remove(child)
    section = doc.sections[0]
    header = section.header.paragraphs[0]
    header.clear()
    # Descartar el borde de la configuración compartida en este encabezado.
    ppr = header._p.get_or_add_pPr()
    for child in list(ppr):
        if child.tag.endswith("}pBdr"):
            ppr.remove(child)
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _format_run(header.add_run("MEMORIA DE CÁLCULO DEL APOYO MÉTODO A"),11,bold=True,color=TEAL)
    footer = section.footer.paragraphs[0]
    footer.clear()
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _format_run(footer.add_run("DISEÑO ESTRUCTURAL  "),11,color=GRAY)
    _field(footer,"PAGE")
    p = doc.add_paragraph(style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(60)
    p.add_run("Memoria de cálculo\ndel apoyo elastomérico Método A")
    doc.add_paragraph("Apoyo rectangular reforzado con zunchos de acero",style="Subtitle")
    g,i = result.adopted,result.inputs
    _table(doc,("Dato","Descripción"),(
        ("Proyecto",i.project),("Apoyo",i.bearing_id),("Estado global",result.status),
        ("Planta y altura",f"{g.length_cm*10:g} × {g.width_cm*10:g} × {result.value('HEIGHT')*10:g} mm"),
        ("Elastómero",f"Shore A {i.hardness}; {g.interior_layers} interiores de {g.interior_cm*10:g} mm y 2 exteriores de {g.exterior_cm*10:g} mm"),
        ("Zunchos",f"{g.interior_layers+1} de {g.steel_cm*10:g} mm"),
        ("Norma de cálculo","Manual de Puentes MTC 2018, Artículo 2.10.4"),
        ("Fecha de emisión",datetime.now(timezone(timedelta(hours=-5))).strftime("%d/%m/%Y")),
    ),widths=(42,117),accent=True)
    _body(doc,"Alcance: dimensionamiento del apoyo de neopreno, incluidas capas, zunchos, deformaciones, estabilidad y fricción. Pedestal y conexiones externas fuera de alcance. Estado: "+result.status if result.inputs.neoprene_only else "La memoria desarrolla la geometría, las acciones, el movimiento horizontal, la compresión, los zunchos, la estabilidad, las conexiones y el aplastamiento del concreto. Estado del cálculo: "+result.status+". Las verificaciones pendientes y referenciales se identifican expresamente en el resumen.")
    doc.add_page_break()
    doc.add_heading("Contenido",1)
    groups = tuple(dict.fromkeys(s.section for s in result.steps))
    contents = (("1","Bases de diseño y entradas"),) + tuple((str(j+2),name) for j,name in enumerate(groups)) + (("7","Resumen de verificaciones"),("8","Diseño adoptado y detalle de capas"),("9","Trazabilidad y referencias"))
    _table(doc,("Sección","Contenido"),contents,widths=(25,134),accent=True)
    doc.add_heading("1 Bases de diseño y entradas",1)
    if result.inputs.movements.prestress_shortening_cm == 0:
        _body(doc,"Alcance de diseno-apoyos-A: concreto armado construido en sitio, sin postensado. La retracción se ingresa desde el cálculo del tablero.")
    _body(doc,"Apoyo rectangular zunchado sin agujeros ni PTFE. L longitudinal y W transversal; rotación principal alrededor del eje transversal. Se requiere respaldo de las propiedades del elastómero." if result.inputs.neoprene_only else "Se considera un apoyo rectangular zunchado sin agujeros ni superficie deslizante PTFE, sometido a compresión. L es longitudinal y W transversal. El alcance requiere rotación principal alrededor del eje transversal. Los certificados del producto, la geometría del pedestal y las resistencias externas deben corresponder al apoyo identificado.")
    _body(doc,"Fuerzas en Tn; longitudes en cm; esfuerzos en kgf/cm². La deformación por compresión excluye IM. Las demandas y capacidades de conexiones externas no se evalúan." if result.inputs.neoprene_only else "Los esfuerzos se expresan en kgf/cm² y las fuerzas en toneladas-fuerza (Tn), con 1 Tn = 1000 kgf. No se aplica redondeo intermedio. La compresión para el límite de deformación excluye IM; los esfuerzos y el aplastamiento usan las acciones declaradas. La envolvente Resistencia I horizontal debe incluir las combinaciones de frenado y temperatura del modelo.")
    _table(doc,("Parámetro","Valor"),(
        ("Procedencia de cargas",i.actions.source),
        ("Acciones DC / DW / LL / PL / IM",f"{i.actions.dc_tn:g} / {i.actions.dw_tn:g} / {i.actions.ll_tn:g} / {i.actions.pl_tn:g} / {i.actions.im_tn:g} Tn"),
        ("Reacción mínima para fricción",f"{i.actions.min_vertical_tn:g} Tn" if i.actions.min_vertical_tn is not None else f"No declarada; se utiliza DC = {i.actions.dc_tn:g} Tn"),
        ("Longitud efectiva de expansión",f"{i.movements.span_length_m:g} m"),
        ("T mínima / instalación / máxima",f"{i.movements.temperature.t_inf_c:g} / {i.movements.temperature.t_install_c:g} / {i.movements.temperature.t_sup_c:g} °C"),
        ("Retracción / postensado / otros",f"{i.movements.shrinkage_cm:g} / {i.movements.prestress_shortening_cm:g} / {i.movements.other_permanent_cm:g} cm"),
        ("Movimiento térmico",("Rango completo" if not i.movements.use_install_to_min else "Desde instalación")+f"; gamma_TU={i.movements.gamma_tu:g}; alpha={i.movements.alpha_per_c:g}/°C"),
        ("G mínimo / máximo",f"{({50:(6.68,9.14),60:(9.14,14.06)}[i.hardness])[0]:g} / {({50:(6.68,9.14),60:(9.14,14.06)}[i.hardness])[1]:g} kgf/cm²"),
        *(((("Fy zunchos",f"{i.fy_kg_cm2:g} kgf/cm²"),)) if i.neoprene_only else (
        ("Fy zunchos / f'c concreto",f"{i.fy_kg_cm2:g} / {i.fc_kg_cm2:g} kgf/cm²; phi={i.concrete_phi:g}"),
        ("As / número de tramos",f"{i.connections.as_site:g} / "+("un tramo" if i.connections.single_span else "varios tramos")),
        ("Restricción longitudinal / transversal",("Sí" if i.connections.restrained_longitudinal else "No")+" / "+("Sí" if i.connections.restrained_transverse else "No")),
        )),
        ("Fricción",f"mu={i.connections.friction_mu:g}"),
        *(() if i.neoprene_only else (("Fuente de resistencia de conexiones",i.connections.resistance_source or "Sin memoria de resistencia externa"),)),
        ("Modelo de compresión",i.compression_curve.source if i.compression_curve else "Cálculo elástico automático estimado; sin curvas de producto" if i.neoprene_only else "Estimación elástica pendiente de curvas de producto"),
        ("Selección",result.selection_note+f" Candidatos evaluados: {result.candidates}."),
    ),widths=(65,94))
    if i.compression_curve:
        doc.add_heading("1 1 Tabla de compresión utilizada",2)
        _table(doc,("S","sigma kgf/cm²","epsilon decimal"),tuple((f"{s:.8g}",f"{stress:.8g}",f"{eps:.8g}") for s,stress,eps in i.compression_curve.points),widths=(40,59,60))
        _body(doc,"Interpolación lineal entre puntos de esfuerzo y entre factores S. Se prohíbe extrapolar. Los datos de tipo referencia producen estado REFERENCIAL y no acreditan propiedades de un producto fabricado.")
    for number,group in enumerate(groups,2):
        doc.add_heading(f"{number} {group}",1)
        for step in result.steps:
            if step.section == group:
                _trace(doc,step)
    doc.add_heading("7 Resumen de verificaciones",1)
    _table(doc,("ID y verificación","Demanda","Límite","Ratio","Estado"),tuple((
        s.id+" "+s.title,"Sin datos" if s.value is None else f"{s.value:.5g} {s.unit}",
        "Sin datos" if s.limit is None else ("< " if s.strict else "<= ")+f"{s.limit:.5g} {s.unit}",
        "-" if s.ratio is None else f"{s.ratio:.3f}",s.status,
    ) for s in result.checks),widths=(53,30,29,17,30))
    _body(doc,"Estado global: "+result.status+". NO CONFORME identifica incumplimientos; ESTIMADO identifica comprobaciones favorables calculadas mediante aproximación elástica, sin acreditar propiedades del producto; PENDIENTE identifica verificaciones sin datos suficientes; REFERENCIAL indica cumplimiento numérico con gráficas, tablas o lecturas académicas; no certifica el producto. CONFORME requiere que todas las comprobaciones cumplan con las fuentes de entrada declaradas.")
    doc.add_heading("8 Diseño adoptado y detalle de capas",1)
    doc.add_picture(_diagram(result),width=Mm(159))
    _body(doc,"Las capas interiores tienen igual espesor y dos caras adheridas; las exteriores tienen una cara adherida. Cada zuncho se adhiere al elastómero. Los planos de fabricación deben definir protección de cantos, recubrimiento lateral, tolerancias, paralelismo y la retención compatible con el movimiento. No se consideran agujeros ni diseño de PTFE en este módulo.")
    doc.add_heading("9 Trazabilidad y referencias",1)
    _body(doc,"Versión del algoritmo: "+result.version+". La consola, el Word y el JSON se generan desde el mismo registro numérico. El JSON conserva todas las entradas y la geometría seleccionada. El hash identifica las entradas normalizadas, no constituye una firma de certificación.")
    _body(doc,"SHA256 de las entradas normalizadas:")
    doc.add_paragraph(result.input_sha256[:32]+"\n"+result.input_sha256[32:])
    _table(doc,("Fuente","Aplicación"),(
        ("Manual de Puentes MTC 2018, 2.10.4","Método A, alcance, compresión, corte y estabilidad; 2.10.3.3.5 y 2.10.3.3.6: refuerzo y deflexión"),
        ("Manual de Puentes MTC 2018, 2.4.3.9.2, 2.4.3.11.8 y 2.4.5.3.1","Temperatura, conexiones sísmicas y combinaciones; 2.8.1.4: resistencia local del concreto"),
        ("AASHTO LRFD, artículos correlativos citados por MTC 2018","14.7.6 Método A; 14.7.5.1 factor S; 14.7.5.3.5 zunchos; 14.7.5.3.6 deflexión; 14.8.3 anclaje"),
        ("APOYOS.pdf, Arturo Rodríguez Serquén, pp. impresas 229 a 239","Procedimiento y ejemplo 4.1; límites conservadores del comentario, datos gráficos referenciales y comparación numérica"),
    ),widths=(73,86))
    _body(doc,"Acceso oficial al Manual de Puentes: "+MTC_URL)
    _enforce_uniform_typography(doc)
    doc.save(path)
    return path
