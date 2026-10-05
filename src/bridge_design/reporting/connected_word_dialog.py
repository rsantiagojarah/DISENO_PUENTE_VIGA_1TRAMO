"""Optional Word generation and native save destination after final steel selection."""

from datetime import datetime
from pathlib import Path

from bridge_design.reporting.connected_docx import write_connected_docx
from bridge_design.domain.connected_2_inputs import is_connected_2


def select_connected_docx_save_path(*, variant_2=False):
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
            parent=root, title="Guardar memoria de calculo de estribos conectados" + (" 2" if variant_2 else ""),
            defaultextension=".docx",
            initialfile=f"MEMORIA_CALCULO_ESTRIBOS_CONECTADOS_{'2_' if variant_2 else ''}{datetime.now():%Y%m%d_%H%M}.docx",
            filetypes=(("Documento de Word", "*.docx"),))
    finally:
        root.destroy()
    return Path(selected) if selected else None


def generate_connected_docx_with_dialog(result, charts):
    path = select_connected_docx_save_path(variant_2=True) if is_connected_2(result.inputs) else select_connected_docx_save_path()
    if path is None:
        print("Generacion de la memoria Word cancelada por el usuario.")
        return None
    generated = write_connected_docx(result, path, charts)
    print(f"Memoria Word de estribos conectados guardada en: {generated}")
    return generated
