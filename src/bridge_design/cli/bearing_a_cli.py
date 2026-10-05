"""Ingreso manual/YAML y exportación auditable para diseno-apoyos-A."""

from __future__ import annotations

from dataclasses import replace
import argparse
import json
from math import isfinite
from pathlib import Path
import sys

from bridge_design.cli.bearing_a_output import format_bearing_a
from bridge_design.cli.bearing_a_yaml import bearing_a_from_yaml, bearing_a_template
from bridge_design.cli.input_prompts import prompt_float, prompt_non_negative_float
from bridge_design.cli.yaml_io import load_yaml_file, save_yaml_file, select_yaml_open_path, select_yaml_save_path
from bridge_design.domain.bearing_method_a import BearingAInputs, BearingAResult, CompressionCurve, design_bearing_a


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
    print("Alcance: solo apoyo de neopreno para concreto armado construido en sitio; sin postensado, pedestal ni conexiones externas.")
    print("Fuerzas: Tn (toneladas-fuerza); longitudes: cm y m; esfuerzos: kgf/cm2.")
    data["proyecto"] = input("Nombre del proyecto [Diseño de apoyo]: ").strip() or "Diseño de apoyo"
    data["identificador"] = input("Identificador del apoyo [A1]: ").strip() or "A1"
    a = data["acciones"]
    print("Valores predeterminados: reacciones del apoyo de viga exterior.")
    for k,label,default in (("dc_tn","DC estructural",27.470),("dw_tn","DW rodadura",0.169),("pl_tn","PL peatonal",4.669)):
        a[k] = prompt_non_negative_float(label,"Tn",default)
    print("LL e IM predeterminados: separación aproximada de 21.871 Tn suponiendo 33% de impacto sobre todo el total; solo válida sin carga de carril incluida.")
    for k,label,default in (("ll_sin_im_tn","LL vehicular sin impacto",16.444),("im_tn","IM incremento dinámico",5.427)):
        while True:
            value = prompt_non_negative_float(label,"Tn",default)
            if isfinite(value):
                a[k] = value
                break
            print("Ingrese una carga finita.")
    print(f"LL+IM = {a['ll_sin_im_tn'] + a['im_tn']:.6g} Tn.")
    a["reaccion_minima_tn"] = _optional_number("Reacción mínima concomitante para fricción (Tn); sin dato se usa DC")
    a["fuente"] = input("Procedencia de reacciones [Ingreso manual]: ").strip() or "Ingreso manual del usuario"
    if a["ll_sin_im_tn"] == 16.444 and a["im_tn"] == 5.427:
        a["fuente"] += "; LL/IM aproximados de 21.871 Tn con hipótesis de 33% sobre vehículo sin carril; composición por confirmar"
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
    print("La retracción debe provenir del cálculo de tu tablero; no se adopta el valor del ejemplo de Serquén.")
    while True:
        shrinkage = _optional_number("Acortamiento por retracción calculado (cm), obligatorio")
        if shrinkage is not None and isfinite(shrinkage) and shrinkage >= 0:
            m["retraccion_cm"] = shrinkage
            break
        print("Ingrese un valor finito no negativo de retracción.")
    m["postensado_cm"] = 0.0
    for k,label in (("otros_cm","Otros acortamientos permanentes"),):
        m[k] = prompt_non_negative_float(label,"cm",m[k])
    m["gamma_tu"] = prompt_float("Factor de movimientos gamma_TU","-",1.2)
    mat = data["materiales"]
    shore = _optional_number("Shore A 50/60; Enter=60",integer=True)
    mat["shore_a"] = 60 if shore is None else shore
    mat["fy_zuncho_kg_cm2"] = prompt_float("Fy de los zunchos","kgf/cm2",2530)
    g = data["geometria"]
    g["ancho_cm"] = prompt_float("Ancho transversal W","cm",45)
    g["largo_cm"] = _optional_number("Largo longitudinal propuesto L (cm); Enter=buscar")
    g["altura_total_cm"] = _optional_number("Altura TOTAL propuesta H (cm), incluye caucho y acero; Enter=buscar")
    while True:
        mode = input("Selección medida/usuales/semirecubierto/recubierto [medida]: ").strip().lower() or "medida"
        if mode in {"medida", "usuales", "semirecubierto", "recubierto"}:
            g["seleccion"] = mode
            break
        print("Ingrese medida, usuales, semirecubierto o recubierto.")
    if mode in {"semirecubierto", "recubierto"}:
        g["rotacion_catalogo_rad"] = _optional_number("Rotación de servicio del apoyo (rad); necesaria para comprobar catálogo")
    manual_layers = mode in {"medida", "usuales"} and (g["altura_total_cm"] is None or _yes("Definir también espesores y número de capas manualmente",False))
    for k,label,integer in (("capa_interior_cm","Espesor de UNA capa interior hri (cm)",False),("capa_exterior_cm","Espesor de UNA capa exterior hre (cm)",False),("numero_capas_interiores","Número de capas interiores",True),("zuncho_cm","Espesor de UN zuncho hs (cm)",False)):
        g[k] = _optional_number(label,integer=integer) if manual_layers else None
    g["casi_cuadrado"] = _yes("Clasificar como casi cuadrado (límite conservador 16)",False)
    g["rotacion_principal_eje_transversal"] = _yes("Rotación principal alrededor del eje transversal")
    data["conexiones"]["mu"] = prompt_non_negative_float("Coeficiente de fricción elastómero/superficie limpia","-",.2)
    curve_path = input("Curvas: Enter=gráficas Serquén automáticas; E=estimación elástica; G=lecturas propias; o ruta YAML: ").strip()
    if curve_path.lower() == "e":
        data["compresion"]["metodo"] = "elastico"
        return replace(bearing_a_from_yaml(data), neoprene_only=True)
    if curve_path.lower() == "g":
        inputs = replace(bearing_a_from_yaml(data), neoprene_only=True, compression_method="elastico")
        preliminary = design_bearing_a(inputs)
        points = {}
        area = preliminary.value("AREA")
        permanent = (inputs.actions.dc_tn + inputs.actions.dw_tn)*1000/area
        total = (preliminary.value("P") - inputs.actions.im_tn)*1000/area
        print("Ingrese deformaciones de la gráfica de la dureza elegida, en porcentaje (4.45 significa 4.45%).")
        for layer, shape in (("interior",preliminary.value("SI")),("exterior",preliminary.value("SE"))):
            points[(shape,0.0)] = 0.0
            for load, stress in (("permanente",permanent),("total sin IM",total)):
                if (shape,stress) in points:
                    continue
                while True:
                    raw = input(f"Deformación {layer}, {load}, S={shape:.8g}, sigma={stress:.8g} kgf/cm2 (%): ").strip()
                    try:
                        eps = float(raw)/100
                    except ValueError:
                        continue
                    if isfinite(eps) and 0 <= eps <= 1:
                        points[(shape,stress)] = eps
                        break
                    print("Ingrese un porcentaje finito entre 0 y 100.")
        curve = CompressionCurve("Lecturas gráficas ingresadas por el usuario para la geometría adoptada",
            inputs.hardness, tuple((shape,stress,eps) for (shape,stress),eps in sorted(points.items())), "referencia")
        return replace(inputs, geometry=preliminary.adopted, compression_curve=curve)
    if curve_path:
        data["compresion"] = load_yaml_file(Path(curve_path))["compresion"]
    return replace(bearing_a_from_yaml(data), neoprene_only=True)



def run_bearing_a(inputs: BearingAInputs, *, word_path: Path | None = None, json_path: Path | None = None, no_word: bool = False, detailed: bool = True) -> BearingAResult:
    if inputs.movements.prestress_shortening_cm != 0:
        raise ValueError("diseno-apoyos-A es solo para concreto armado construido en sitio: postensado_cm debe ser 0. Revise el YAML; no se descarta el acortamiento silenciosamente.")
    result = design_bearing_a(replace(inputs, neoprene_only=True))
    print(format_bearing_a(result,detailed=detailed))
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
    parser = argparse.ArgumentParser(prog="diseno-apoyos-A",description="Apoyos Método A para concreto armado construido en sitio, sin postensado.")
    parser.add_argument("modo",nargs="?",choices=("input","output","ejemplo"),help="Sin modo: ingreso manual. input: leer YAML; output: guardar plantilla; ejemplo: fuera de alcance (el problema original es postensado).")
    parser.add_argument("archivo",nargs="?",type=Path,help="Ruta YAML; si se omite se abre un selector.")
    parser.add_argument("--word",type=Path,help="Guardar Word directamente, sin ventana.")
    parser.add_argument("--json",type=Path,help="Exportar entradas, geometría, cálculos, verificaciones y SHA256.")
    parser.add_argument("--sin-word",action="store_true",help="Solo consola; evita ventana Word.")
    display = parser.add_mutually_exclusive_group()
    display.add_argument("--detalle",action="store_true",help="Mostrar fórmulas y reemplazos en cuadros (comportamiento predeterminado).")
    display.add_argument("--resumen",action="store_true",help="Mostrar solo los cuadros de resumen, sin desarrollo de fórmulas.")
    args = parser.parse_args(argv)
    if args.word is not None and args.sin_word:
        parser.error("--word y --sin-word son excluyentes.")
    try:
        if args.modo == "ejemplo":
            raise ValueError("El problema 4.1 de Serquén es postensado y queda fuera de este comando. Use output para generar la plantilla de concreto armado construido en sitio.")
        if args.modo == "output":
            if args.word is not None or args.json is not None or args.sin_word or args.detalle or args.resumen:
                parser.error("Las opciones de reporte requieren cálculo input o manual.")
            path = args.archivo or select_yaml_save_path("Guardar YAML de apoyos Método A","modelo_apoyos_A.yaml")
            template = bearing_a_template()
            template["alcance"] = "neopreno"
            template.pop("concreto")
            template["conexiones"] = {"mu": 0.2}
            save_yaml_file(path,template)
            print(f"YAML guardado en: {path}")
            return 0
        if args.modo == "input":
            path = args.archivo or select_yaml_open_path("Seleccionar YAML de apoyo Método A")
            inputs = bearing_a_from_yaml(load_yaml_file(path))
        else:
            inputs = collect_bearing_a_inputs()
        run_bearing_a(inputs,word_path=args.word,json_path=args.json,no_word=args.sin_word,detailed=not args.resumen)
    except (ValueError,OSError,KeyError,RuntimeError) as exc:
        print(f"Error: {exc}",file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
