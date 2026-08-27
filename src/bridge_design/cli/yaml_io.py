"""YAML file helpers for command line workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


YamlData = dict[str, Any]


class _LiteralSafeDumper(yaml.SafeDumper):
    """Safe YAML dumper that keeps multiline reference diagrams readable."""


def _represent_readable_string(
    dumper: _LiteralSafeDumper,
    value: str,
) -> yaml.nodes.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_LiteralSafeDumper.add_representer(str, _represent_readable_string)


class YamlModeError(ValueError):
    """Raised when the YAML command mode cannot be completed."""


def resolve_yaml_mode_path(args: list[str], *, mode: str) -> Path | None:
    """Return an optional direct path for `input` or `output` mode."""
    if not args or args[0] != mode:
        return None
    if len(args) == 1:
        return None
    if len(args) == 2:
        return Path(args[1])
    raise YamlModeError(f"Uso invalido: demasiados argumentos para '{mode}'.")


def is_yaml_mode(args: list[str]) -> bool:
    """Return True when args request YAML input/output mode."""
    return bool(args) and args[0] in {"input", "output"}


def select_yaml_open_path(title: str) -> Path:
    """Ask the user for a YAML file using a GUI file picker."""
    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    try:
        filename = filedialog.askopenfilename(
            title=title,
            filetypes=(("Archivos YAML", "*.yaml *.yml"), ("Todos los archivos", "*.*")),
        )
    finally:
        root.destroy()
    if not filename:
        raise YamlModeError("No se selecciono ningun archivo YAML.")
    return Path(filename)


def select_yaml_save_path(title: str, default_filename: str) -> Path:
    """Ask the user where to save a YAML template using a GUI file picker."""
    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    try:
        filename = filedialog.asksaveasfilename(
            title=title,
            defaultextension=".yaml",
            initialfile=default_filename,
            filetypes=(("Archivos YAML", "*.yaml"), ("Archivos YML", "*.yml"), ("Todos los archivos", "*.*")),
        )
    finally:
        root.destroy()
    if not filename:
        raise YamlModeError("No se selecciono ruta para guardar el YAML.")
    return Path(filename)


def load_yaml_file(path: Path) -> YamlData:
    """Load a YAML mapping from disk."""
    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except OSError as exc:
        raise YamlModeError(f"No se pudo leer el archivo YAML: {path}") from exc
    except yaml.YAMLError as exc:
        raise YamlModeError(f"El archivo YAML no tiene formato valido: {path}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise YamlModeError("El YAML debe contener un mapa principal de claves y valores.")
    return data


def save_yaml_file(path: Path, data: YamlData) -> None:
    """Save a YAML mapping to disk."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as file:
            yaml.dump(
                data,
                file,
                Dumper=_LiteralSafeDumper,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )
    except OSError as exc:
        raise YamlModeError(f"No se pudo guardar el archivo YAML: {path}") from exc


def print_yaml_mode_help(command: str) -> None:
    """Print a compact help block for YAML modes."""
    print(
        f"Uso:\n"
        f"  {command}                  ingreso manual normal\n"
        f"  {command} input            elegir YAML con ventana\n"
        f"  {command} input datos.yaml leer YAML directo\n"
        f"  {command} output           guardar plantilla YAML con ventana\n"
        f"  {command} output modelo.yaml guardar plantilla YAML directo"
    )
