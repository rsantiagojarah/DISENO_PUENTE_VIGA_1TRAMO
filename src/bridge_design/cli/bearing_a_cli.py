"""Ingreso manual/YAML y exportación auditable para diseno-apoyos-A."""

from __future__ import annotations

import argparse
import json
from math import isfinite
from pathlib import Path
import sys

from bridge_design.cli.bearing_a_yaml import bearing_a_from_yaml, bearing_a_reference_example, bearing_a_template
from bridge_design.cli.input_prompts import prompt_float, prompt_non_negative_float
from bridge_design.cli.yaml_io import load_yaml_file, save_yaml_file, select_yaml_open_path, select_yaml_save_path
from bridge_design.domain.bearing_method_a import BearingAInputs, BearingAResult, design_bearing_a


def format_bearing_a(result: BearingAResult) -> str:
    g = result.adopted
    lines = [
        "=== DISENO DE APOYOS - METODO A MTC 2018 ===",
        f"Proyecto: {result.inputs.project} | Apoyo: {result.inputs.bearing_id}",
        f"Estado global: {result.status}",
        f"L x W x H = {g.length_cm*10:g} x {g.width_cm*10:g} x {result.value('HEIGHT')*10:g} mm",
        f"Capas: {g.interior_layers} interiores de {g.interior_cm*10:g} mm + 2 exteriores de {g.exterior_cm*10:g} mm",
        f"Zunchos: {g.interior_layers+1} de {g.steel_cm*10:g} mm | Shore A {result.inputs.hardness}",
        f"Version: {result.version} | SHA256 entradas: {result.input_sha256}",
        result.selection_note,
    ]
    section = None
    for s in result.steps:
        if s.section != section:
            section = s.section
            lines.extend(("",section.upper()))
        lines.extend((f"[{s.id}] {s.title}",f"  Formula: {s.formula}",f"  Donde: {s.legend}",f"  Sustitucion: {s.substitution}",
                      f"  Resultado: {'sin datos' if s.value is None else format(s.value,'.8g')} {s.unit} | {s.status}",
                      f"  Referencia: {s.reference}"))
        if s.limit is not None:
            lines.append(f"  Limite: {'<' if s.strict else '<='} {s.limit:.8g} {s.unit}; ratio: {s.ratio if s.ratio is not None else 'no definido'}")
        if s.note:
            lines.append("  Nota: "+s.note)
    return "\n".join(lines)


def _optional_number(label: str, *, integer: bool = False):
    while True:
        raw = input(label + " [Enter = automatico/sin dato]: ").strip()
        if not raw:
            return None
        try:
            return int(raw) if integer else float(raw)
        except ValueError:
            print("Ingrese un número válido.")


def _yes(label: str, default: bool = True) -> bool:
    while True:
        raw = input(f"{label} (s/n) [{'s' if default else 'n'}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"s","si","n","no"}:
            return raw in {"s","si"}
        print("Ingrese s o n.")


def _temperature(label: str, default: float) -> float:
    while True:
        raw = input(f"{label} (C) [{default:g}]: ").strip()
        try:
            value = default if not raw else float(raw)
            if isfinite(value):
                return value
        except ValueError:
            pass
        print("Ingrese una temperatura finita, positiva, cero o negativa.")


def collect_bearing_a_inputs() -> BearingAInputs:
    data = bearing_a_template()
    print("=== APOYO RECTANGULAR ZUNCHADO SIN AGUJEROS NI PTFE - METODO A ===")
    print("Fuerzas: Tn (toneladas-fuerza); longitudes: cm y m; esfuerzos: kgf/cm2.")
    data["proyecto"] = input("Nombre del proyecto [Diseño de apoyo]: ").strip() or "Diseño de apoyo"
    data["identificador"] = input("Identificador del apoyo [A1]: ").strip() or "A1"
    a = data["acciones"]
    for k,label in (("dc_tn","DC estructural"),("dw_tn","DW rodadura"),("ll_sin_im_tn","LL vehicular sin impacto"),("pl_tn","PL peatonal"),("im_tn","IM incremento dinámico")):
        a[k] = prompt_non_negative_float(label,"Tn",a[k])
    a["reaccion_minima_tn"] = _optional_number("Reacción mínima concomitante para fricción (Tn); sin dato se usa DC")
    a["fuente"] = input("Procedencia de reacciones [Ingreso manual]: ").strip() or "Ingreso manual del usuario"
    m = data["movimientos"]
    m["longitud_expansion_m"] = prompt_float("Longitud efectiva de expansión desde punto fijo","m",30)
    while True:
        zone = input("Zona climática costa/sierra/selva [sierra]: ").strip().lower() or "sierra"
        if zone in {"costa","sierra","selva"}:
            m["zona_climatica"] = zone
            break
    m["temperatura_instalacion_c"] = _temperature("Temperatura de instalación",25)
    if _yes("Definir temperaturas extremas propias",False):
        m["temperatura_minima_c"] = _temperature("Temperatura mínima",-10)
        m["temperatura_maxima_c"] = _temperature("Temperatura máxima",35)
    for k,label in (("retraccion_cm","Acortamiento por retracción"),("postensado_cm","Acortamiento por postensado"),("otros_cm","Otros acortamientos permanentes")):
        m[k] = prompt_non_negative_float(label,"cm",m[k])
    m["gamma_tu"] = prompt_float("Factor de movimientos gamma_TU","-",1.2)
    mat = data["materiales"]
    shore = _optional_number("Shore A 50/60; Enter=60",integer=True)
    mat["shore_a"] = 60 if shore is None else shore
    mat["fy_zuncho_kg_cm2"] = prompt_float("Fy de los zunchos","kgf/cm2",2530)
    g = data["geometria"]
    g["ancho_cm"] = prompt_float("Ancho transversal W","cm",45)
    for k,label,integer in (("largo_cm","Largo longitudinal L (cm)",False),("capa_interior_cm","Espesor interior hri (cm)",False),("capa_exterior_cm","Espesor exterior hre (cm)",False),("numero_capas_interiores","Número de capas interiores",True),("zuncho_cm","Espesor de zuncho hs (cm)",False)):
        g[k] = _optional_number(label,integer=integer)
    g["casi_cuadrado"] = _yes("Clasificar como casi cuadrado (límite conservador 16)",False)
    g["rotacion_principal_eje_transversal"] = _yes("Rotación principal alrededor del eje transversal")
    con = data["concreto"]
    con["fc_kg_cm2"] = prompt_float("f'c pedestal/estribo","kgf/cm2",210)
    con["area_a2_cm2"] = _optional_number("A2 similar y concéntrica del pedestal (cm2); Enter=A1")
    c = data["conexiones"]
    c["as_sitio"] = prompt_non_negative_float("Coeficiente sísmico As = PGA*Fpga","-",.2)
    c["un_solo_tramo"] = _yes("Puente de un solo tramo")
    c["restriccion_longitudinal"] = _yes("Conexión restringida longitudinalmente",False)
    c["restriccion_transversal"] = _yes("Conexión restringida transversalmente")
    if c["restriccion_longitudinal"]:
        c["permanente_tributaria_longitudinal_tn"] = _optional_number("Carga permanente tributaria longitudinal (Tn)")
    if not c["un_solo_tramo"]:
        for k in ("eq_longitudinal_analisis_tn","eq_transversal_analisis_tn"):
            c[k] = _optional_number(k)
    for direction in ("longitudinal","transversal"):
        k = f"envolvente_resistencia_i_{direction}_tn"
        c[k] = prompt_non_negative_float(f"Envolvente horizontal Resistencia I {direction} (incluye frenado/temperatura)","Tn",0)
        c[f"resistencia_diseno_{direction}_tn"] = _optional_number(f"Resistencia de diseño externa {direction} (Tn)")
    if any(c[k] is not None for k in ("resistencia_diseno_longitudinal_tn","resistencia_diseno_transversal_tn")):
        c["fuente_resistencia"] = input("Memoria/certificado de la trayectoria resistente externa: ").strip()
    c["mu"] = prompt_non_negative_float("Coeficiente de fricción elastómero/superficie limpia","-",.2)
    curve_path = input("YAML con sección compresion de fabricante [Enter = estimación pendiente]: ").strip()
    if curve_path:
        data["compresion"] = load_yaml_file(Path(curve_path))["compresion"]
    return bearing_a_from_yaml(data)


def run_bearing_a(inputs: BearingAInputs, *, word_path: Path | None = None, json_path: Path | None = None, no_word: bool = False) -> BearingAResult:
    result = design_bearing_a(inputs)
    print(format_bearing_a(result))
    if not no_word or word_path is not None:
        from bridge_design.reporting.bearing_a_docx import generate_bearing_a_docx, select_bearing_a_docx_path
        destination = word_path or select_bearing_a_docx_path()
        if destination is not None:
            output = generate_bearing_a_docx(result,destination)
            print(f"Memoria Word guardada en: {output}")
        else:
            print("Generación Word cancelada por el usuario.")
    if json_path is not None:
        json_path = json_path.expanduser().resolve()
        json_path.parent.mkdir(parents=True,exist_ok=True)
        json_path.write_text(json.dumps(result.to_dict(),ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
        print(f"Registro JSON guardado en: {json_path}")
    return result


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout,"reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="diseno-apoyos-A",description="Apoyo rectangular zunchado Método A MTC 2018; memoria Word y registro JSON trazables.")
    parser.add_argument("modo",nargs="?",choices=("input","output","ejemplo"),help="Sin modo: ingreso manual. input: leer YAML; output: guardar plantilla; ejemplo: guardar el problema 4.1 del PDF.")
    parser.add_argument("archivo",nargs="?",type=Path,help="Ruta YAML; si se omite se abre un selector.")
    parser.add_argument("--word",type=Path,help="Guardar Word directamente, sin ventana.")
    parser.add_argument("--json",type=Path,help="Exportar entradas, geometría, cálculos, verificaciones y SHA256.")
    parser.add_argument("--sin-word",action="store_true",help="Solo consola; evita ventana Word.")
    args = parser.parse_args(argv)
    if args.word is not None and args.sin_word:
        parser.error("--word y --sin-word son excluyentes.")
    try:
        if args.modo in {"output","ejemplo"}:
            if args.word is not None or args.json is not None or args.sin_word:
                parser.error("Las opciones de reporte requieren cálculo input o manual.")
            path = args.archivo or select_yaml_save_path("Guardar YAML de apoyos Método A","modelo_apoyos_A.yaml")
            save_yaml_file(path,bearing_a_reference_example() if args.modo=="ejemplo" else bearing_a_template())
            print(f"YAML guardado en: {path}")
            return 0
        if args.modo == "input":
            path = args.archivo or select_yaml_open_path("Seleccionar YAML de apoyo Método A")
            inputs = bearing_a_from_yaml(load_yaml_file(path))
        else:
            inputs = collect_bearing_a_inputs()
        run_bearing_a(inputs,word_path=args.word,json_path=args.json,no_word=args.sin_word)
    except (ValueError,OSError,KeyError,RuntimeError) as exc:
        print(f"Error: {exc}",file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
