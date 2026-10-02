"""Optional Word generation and native save destination after final steel selection."""

from datetime import datetime
from pathlib import Path

from bridge_design.cli.connected_prompts import yes_no
from bridge_design.reporting.connected_docx import write_connected_docx


def select_connected_docx_save_path():
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as error:
        raise RuntimeError("Tkinter no esta disponible para elegir el destino Word.") from error
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.asksaveasfilename(
            parent=root, title="Guardar memoria de calculo de estribos conectados",
            defaultextension=".docx",
            initialfile=f"MEMORIA_CALCULO_ESTRIBOS_CONECTADOS_{datetime.now():%Y%m%d_%H%M}.docx",
            filetypes=(("Documento de Word", "*.docx"),))
    finally:
        root.destroy()
    return Path(selected) if selected else None


def generate_connected_docx_with_dialog(result, charts):
    if not yes_no("Desea generar la memoria de calculo en Word", True):
        print("Generacion de la memoria Word omitida por el usuario.")
        return None
    path = select_connected_docx_save_path()
    if path is None:
        print("Generacion de la memoria Word cancelada por el usuario.")
        return None
    generated = write_connected_docx(result, path, charts)
    print(f"Memoria Word de estribos conectados guardada en: {generated}")
    return generated
