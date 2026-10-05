"""Cuadros de consola del apoyo; valores tomados del registro de cálculo."""
from __future__ import annotations

from collections import Counter
from shutil import get_terminal_size

from bridge_design.cli.ascii_tables import audit_block_title, boxed_table
from bridge_design.domain.bearing_method_a import BearingAResult


def _status(value: str) -> str:
    return {"REFERENCIAL": "CUMPLE (ref.)", "CUMPLE (ESTIMADO)": "CUMPLE (est.)"}.get(value,value)


def _number(value: float | None, unit: str = "", percent: bool = False) -> str:
    if value is None:
        return "Sin dato"
    if percent:
        return f"{100*value:.3f} %"
    return f"{value:.6g}" + (f" {unit}" if unit and unit != "-" else "")


def format_bearing_a(result: BearingAResult, *, detailed: bool = True, width: int | None = None) -> str:
    width = max(72,min(112,width or get_terminal_size((100,24)).columns))
    i,g = result.inputs,result.adopted
    lines = audit_block_title("", "APOYO DE NEOPRENO - METODO A", width)

    def table(title, headers, rows, aligns=None, *, separate=False):
        lines.append("")
        # El encabezado se imprime a ancho completo para no truncarlo si la tabla es corta.
        lines.extend(audit_block_title("",title,width))
        lines.extend(boxed_table(headers,rows,aligns=aligns,max_width=width,row_separators=separate))

    meanings = {
        "REFERENCIAL": "CUMPLE según la fuente referencial: verificaciones favorables con gráficas/tablas; no es certificación del producto.",
        "ESTIMADO": "Verificaciones favorables con aproximación elástica; confirmar propiedades del producto.",
        "PENDIENTE": "Faltan datos o cobertura de curvas en las verificaciones señaladas.",
        "NO CONFORME": "Una o más verificaciones NO CUMPLEN; revisar las filas indicadas.",
        "CONFORME": "Todas las verificaciones incluidas cumplen con las fuentes declaradas.",
    }
    table("1. RESUMEN",("Concepto","Resultado"),[
        ("Proyecto",i.project),("Apoyo",i.bearing_id),
        (f"Estado global: {result.status}",meanings[result.status]),
        ("Alcance","Solo neopreno; pedestal y conexiones externas excluidos." if i.neoprene_only else "Completo"),
        ("L x W x H",f"{g.length_cm*10:g} x {g.width_cm*10:g} x {result.value('HEIGHT')*10:g} mm"),
        ("Dureza",f"Shore A {i.hardness}"),
        ("Modo de selección",g.selection_mode),
    ])
    a=i.actions
    table("2. CARGAS POR APOYO",("Carga","Descripción","Tn"),[
        ("DC","Permanente estructural",f"{a.dc_tn:.3f}"),
        ("DW","Rodadura",f"{a.dw_tn:.3f}"),("PL","Peatonal",f"{a.pl_tn:.3f}"),
        ("LL","Vehicular sin impacto",f"{a.ll_tn:.3f}"),("IM","Incremento dinámico",f"{a.im_tn:.3f}"),
        ("LL+IM","Total vehicular",f"{a.ll_tn+a.im_tn:.3f}"),
        ("Servicio","DC + DW + PL + LL + IM",f"{result.value('P'):.3f}"),
    ],("left","left","right"))
    table("3. COMPOSICION ADOPTADA",("Elemento","Cantidad","Espesor unitario (mm)","Total (mm)"),[
        ("Caucho interior",g.interior_layers,f"{g.interior_cm*10:g}",f"{g.interior_layers*g.interior_cm*10:g}"),
        ("Caucho exterior",2,f"{g.exterior_cm*10:g}",f"{2*g.exterior_cm*10:g}"),
        ("Zunchos de acero",g.interior_layers+1,f"{g.steel_cm*10:g}",f"{(g.interior_layers+1)*g.steel_cm*10:g}"),
        ("Altura total H","-","-",f"{result.value('HEIGHT')*10:g}"),
    ],("left","right","right","right"))
    if g.cover_cm:
        table("RECUBRIMIENTO LATERAL",("Concepto","Valor"),[
            ("Recubrimiento sin zuncho",f"{g.cover_cm*10:g} mm por lado"),
            ("Núcleo efectivo",f"{(g.length_cm-2*g.cover_cm)*10:g} x {(g.width_cm-2*g.cover_cm)*10:g} mm"),
        ])
    labels = {"EPS_ID": "Deformación interior por carga permanente", "EPS_IT": "Deformación interior por carga total sin IM", "EPS_ED": "Deformación exterior por carga permanente", "EPS_ET": "Deformación exterior por carga total sin IM"}
    keys={"AREA","SI","SE","NEFF","DELTA","HRT","EPS_ID","EPS_IT","EPS_ED","EPS_ET","DEF_D","DEF_T","DEF_LL","CREEP","HU","FRICTION"}
    table("4. RESULTADOS PRINCIPALES",("ID","Resultado","Valor"),[
        (s.id,labels.get(s.id,s.title),_number(s.value,s.unit,s.id.startswith("EPS_"))) for s in result.steps if s.id in keys
    ],("left","left","right"))
    table("5. VERIFICACIONES",("ID / comprobación","Valor","Límite","Uso (*)","Estado"),[
        (s.id+" / "+s.title,
         _number(s.value,s.unit,s.id=="STRAIN_CHECK"),
         ("< " if s.strict else "<= ")+_number(s.limit,s.unit,s.id=="STRAIN_CHECK") if s.limit is not None else "Sin dato",
         f"{s.ratio*100:.1f}%" if s.ratio is not None else "-",_status(s.status)) for s in result.checks
    ],("left","right","right","right","left"))
    counts=Counter(s.status for s in result.checks)
    table("6. LECTURA DEL RESULTADO",("Concepto","Explicación"),[
        ("Cumplen",str(sum(counts[x] for x in ("CUMPLE","REFERENCIAL","CUMPLE (ESTIMADO)")))),
        ("No cumplen",str(counts["NO CUMPLE"])),("Pendientes",str(counts["PENDIENTE"])),
        ("(*) Uso del límite","Valor / límite x 100. No es la deformación del caucho. Para límites estrictos (<), la igualdad no cumple."),
        ("CUMPLE (ref.)","Cumplimiento numérico con fuente referencial; no certifica propiedades del producto."),
        ("CUMPLE (est.)","Cumplimiento con modelo elástico aproximado."),
    ])
    notes=[("Cargas",a.source),("Selección",result.selection_note),
        ("Compresión",i.compression_curve.source if i.compression_curve else "Modelo elástico aproximado"),
        ("Versión",result.version)]
    notes.extend((s.id,s.note or s.reference) for s in result.checks if s.status in {"NO CUMPLE","PENDIENTE"})
    table("7. FUENTES Y OBSERVACIONES",("Concepto","Descripción"),notes)
    if detailed:
        lines.append("")
        lines.extend(audit_block_title("", "8. DESARROLLO DE FORMULAS Y REEMPLAZOS", width))
        for s in result.steps:
            rows=[("Cálculo",s.title),("Fórmula",s.formula),("Variables y unidades",s.legend),
                ("Reemplazo numérico",s.substitution),("Resultado",_number(s.value,s.unit))]
            if s.limit is not None:
                rows.append(("Comprobación",_number(s.value,s.unit)+(" < " if s.strict else " <= ")+_number(s.limit,s.unit)))
            if s.ratio is not None:
                rows.append(("Uso del límite",f"({_number(s.value)} / {_number(s.limit)}) x 100 = {s.ratio*100:.2f} %"))
            rows.extend((("Estado",_status(s.status)),("Referencia",s.reference)))
            if s.note:
                rows.append(("Nota",s.note))
            table("DESARROLLO - "+s.id,("Paso","Desarrollo"),rows,separate=True)
        table("TRAZABILIDAD",("Concepto","Valor"),[("SHA256 entradas",result.input_sha256)])
    else:
        lines.extend(("","Para ver fórmulas, sustituciones y referencias por cálculo: diseno-apoyos-A --detalle"))
    return "\n".join(lines)
