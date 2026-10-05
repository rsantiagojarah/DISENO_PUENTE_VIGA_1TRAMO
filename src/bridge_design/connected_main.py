"""New command for the analysis and design of abutments with continuous foundation."""

import argparse
from pathlib import Path

from bridge_design.cli.connected_output import format_connected_result
from bridge_design.cli.connected_prompts import collect_connected_inputs
from bridge_design.cli.connected_selection import collect_connected_selection, format_connected_options, format_connected_selection
from bridge_design.cli.connected_yaml import connected_inputs_from_yaml, connected_yaml_template
from bridge_design.cli.yaml_io import load_yaml_file, save_yaml_file, select_yaml_open_path, select_yaml_save_path
from bridge_design.domain.connected_design import solve_connected_abutments
from bridge_design.domain.connected_options import apply_connected_selections, connected_reinforcement_options
from bridge_design.reporting.connected_export import export_connected_results


def main(argv=None):
    parser = argparse.ArgumentParser(prog="diseno-estribos-conectados",
        description="Dos estribos con cajuela, cimentacion FRAME continua y Winkler solo a compresion.")
    parser.add_argument("modo", choices=("input", "output"), nargs="?", help="Leer YAML o crear plantilla editable")
    parser.add_argument("archivo", nargs="?", type=Path)
    parser.add_argument("--ejemplo", action="store_true", help="En output, incluir ks referencial para pruebas")
    parser.add_argument("--resultados", type=Path, default=Path("output/estribos_conectados"))
    parser.add_argument("--sin-word", action="store_true", help="Generar TXT, JSON, CSV y graficos sin memoria Word")
    parser.add_argument("--automatico", action="store_true", help="Con YAML: conservar acero propuesto y guardar Word sin dialogos")
    parser.add_argument("--verificar-malla", action="store_true", help="Comparar con el doble de intervalos entre resortes")
    args = parser.parse_args(argv)
    if args.ejemplo and args.modo != "output":
        parser.error("--ejemplo solo se usa con output; el analisis requiere el YAML o los datos interactivos.")
    if args.automatico and args.modo != "input":
        parser.error("--automatico requiere input y un archivo YAML.")
    if args.automatico and args.archivo is None:
        parser.error("--automatico requiere la ruta del archivo YAML.")
    try:
        if args.modo == "output":
            path = args.archivo or select_yaml_save_path("Guardar modelo de estribos conectados", "modelo_estribos_conectados.yaml")
            save_yaml_file(path, connected_yaml_template(example=args.ejemplo))
            print(f"Plantilla YAML guardada en: {path}")
            return
        if args.modo == "input":
            path = args.archivo or select_yaml_open_path("Abrir modelo de estribos conectados")
            inputs = connected_inputs_from_yaml(load_yaml_file(path))
        else:
            inputs = collect_connected_inputs()
        print("Resolviendo FRAME, contacto y diseno de ambas caras...")
        result = solve_connected_abutments(inputs, check_mesh=args.verificar_malla)
        if not args.automatico:
            print("\n2. RECOMENDACIONES Y SELECCION DE DISTRIBUCIONES DE ACERO")
            options = connected_reinforcement_options(result)
            print(format_connected_options(options))
            selected = collect_connected_selection(result, options)
            result = apply_connected_selections(result, selected)
        print(format_connected_selection(result))
        print("\n3. RESUMEN DE RESULTADOS Y VERIFICACIONES FINALES - ACEROS ADOPTADOS")
        print(format_connected_result(result))
        destination = export_connected_results(result, args.resultados)
        from bridge_design.reporting.connected_charts import save_connected_charts
        charts = save_connected_charts(result, destination)
        print(f"Resumen, auditoria, JSON, CSV y graficos guardados en: {destination.resolve()}")
        if not args.sin_word:
            print("\n4. GENERACION DE LA MEMORIA DE CALCULO")
            if args.automatico:
                from bridge_design.reporting.connected_docx import write_connected_docx
                path = write_connected_docx(result, destination / "memoria_estribos_conectados.docx", charts)
                print(f"Memoria Word guardada en: {path.resolve()}")
            else:
                from bridge_design.reporting.connected_word_dialog import generate_connected_docx_with_dialog
                generate_connected_docx_with_dialog(result, charts)
    except EOFError:
        parser.exit(2, "Entrada interactiva interrumpida. Para ejecucion sin preguntas use input ARCHIVO --automatico.\n")
    except (ValueError, OSError) as error:
        parser.exit(2, f"Error: {error}\n")


if __name__ == "__main__":
    main()
