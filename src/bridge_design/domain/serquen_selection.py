"""Selección discreta de las tablas carreteras 4.1 de Serquén.

La capacidad tabulada no sustituye al Método A: se comprueban ambos.
Las dimensiones propuestas son exteriores; recubierto reserva 5 mm laterales
según p.224. n de catálogo cuenta zunchos, no capas interiores.
"""
from dataclasses import asdict, replace
from hashlib import sha256
import json
from bridge_design.domain.serquen_bearings import catalog_rows


def select_catalog_bearing(inputs):
    from bridge_design.domain.bearing_method_a import BearingAResult, CalculationStep, _evaluate
    g = inputs.geometry
    candidates = []
    evaluated = 0
    for row in catalog_rows():
        if row.family != g.selection_mode:
            continue
        # L paralelo al movimiento / perpendicular al eje de giro: lado corto.
        # No se intercambian ejes: las rotaciones de catálogo no son simétricas.
        l, w = row.short_mm/10, row.long_mm/10
        if abs(w-g.width_cm)>1e-8 or (g.length_cm is not None and abs(l-g.length_cm)>1e-8) or l>g.max_length_cm:
            continue
        for plates, rotation_mrad in row.rotations:
            n = plates-1
            if n < 1 or n > g.max_layers:
                continue
            hi, hs = row.rubber_mm/10, row.steel_mm/10
            he = hi/2
            height = plates*(hi+hs)
            if g.total_height_cm is not None and abs(height-g.total_height_cm)>1e-6:
                continue
            constraints = ((g.interior_cm,hi),(g.exterior_cm,he),(g.steel_cm,hs),(g.interior_layers,n))
            if any(v is not None and abs(v-expected)>1e-8 for v,expected in constraints):
                continue
            adopted = replace(g,length_cm=l,interior_cm=hi,exterior_cm=he,steel_cm=hs,
                interior_layers=n,cover_cm=.5 if row.family=="recubierto" else 0)
            steps = list(_evaluate(inputs,adopted))
            evaluated += 1
            get = lambda key: next(s.value for s in steps if s.id==key)
            source = f"Serquén Tabla 4.1, p.{row.page}; {row.identifier}; n={plates} zunchos; catálogo histórico, disponibilidad por confirmar"
            def check(key,title,value,limit,unit,formula,note=""):
                status = "PENDIENTE" if value is None else "REFERENCIAL" if value<=limit+1e-9 else "NO CUMPLE"
                steps.append(CalculationStep(key,"Catálogo Serquén",title,formula,
                    "Valores de catálogo para puentes carreteros; no es certificado de producto",
                    f"{value} <= {limit:g}",value,unit,source,limit,status,note))
            check("CAT_LOAD","Carga vertical de catálogo",get("P")*9.80665,row.road_capacity_kn,"kN","9.80665 P <= N_catalogo")
            # Método A usa un límite más estricto: hrt >= 2 Delta, ya comprobado.
            # Se transcriben las excepciones impresas, sin corregir sus erratas.
            movement_mm = .7*plates*row.rubber_mm
            if row.family=="semirecubierto" and row.rubber_mm==8 and plates==5:
                movement_mm=26.0
            if row.family=="semirecubierto" and row.rubber_mm==12 and plates==3:
                movement_mm=31.6
            if row.family=="semirecubierto" and row.rubber_mm==10 and plates==7:
                movement_mm=49.9
            if row.family=="recubierto" and row.rubber_mm==12 and plates==11:
                movement_mm=94.4
            check("CAT_MOVE","Desplazamiento tabulado",get("DELTA")*10,movement_mm,"mm","10 Delta <= u_catalogo",
                "Se exige también corte del Método A; no se sustituye por el límite de catálogo.")
            check("CAT_ROTATION","Rotación tabulada",None if g.catalog_rotation_rad is None else g.catalog_rotation_rad*1000,
                rotation_mrad,"mrad","1000 theta <= alpha_catalogo",
                "Rotación de servicio del análisis en el eje transversal. Falta el dato." if g.catalog_rotation_rad is None else "Eje transversal; L corresponde al lado corto de la tabla.")
            # Las comprobaciones externas no intervienen en la selección del núcleo.
            core = [s for s in steps if not s.id.startswith(("CONNECTION_","EQ_")) and s.id not in {"CONCRETE","A2"}]
            if any(s.status=="NO CUMPLE" for s in core):
                continue
            pending = sum(s.status=="PENDIENTE" for s in core)
            candidates.append((pending,l,height,n,adopted,tuple(steps),source))
    if not candidates:
        raise ValueError("No existe una fila de catálogo compatible con W, L, H y las capas propuestas que pase las verificaciones calculables. El catálogo no permite alturas arbitrarias. Use medida/usuales o cambie dimensiones; no se modifican silenciosamente.")
    best = min(candidates,key=lambda r:r[:4])
    payload=json.dumps(asdict(inputs),sort_keys=True,ensure_ascii=False,allow_nan=False)
    note=best[6]+". Selección: menor número de verificaciones pendientes, luego menor L, H y capas. Recubrimiento lateral en recubiertos: 5 mm; confirmar detalle del fabricante."
    return BearingAResult(inputs,best[4],best[5],evaluated,note,sha256(payload.encode("utf-8")).hexdigest())
