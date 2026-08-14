"""Reusable ASCII boxes for auditable terminal reports."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
import os
import sys
import textwrap

Alignment = str

_RESET = "\033[0m"
_BOLD = "\033[1m"
_ACCENT_COLOR = "\033[34m"


def audit_block_title(code: str, title: str, width: int = 104) -> list[str]:
    """Return a boxed title with a stable audit code."""
    text = f"{code}. {title}" if code else title
    lines = [
        "+" + "=" * (width - 2) + "+",
        "|" + text[: width - 4].center(width - 2) + "|",
        "+" + "=" * (width - 2) + "+",
    ]
    return _paint_lines(lines, bold=True)


def audit_subtitle(code: str, title: str, width: int = 104) -> list[str]:
    """Return a boxed subsection label."""
    text = f"{code}. {title}" if code else title
    lines = [
        "+" + "-" * (width - 2) + "+",
        "|" + text[: width - 4].ljust(width - 2) + "|",
        "+" + "-" * (width - 2) + "+",
    ]
    return _paint_lines(lines, bold=False)


def boxed_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[object]],
    aligns: Sequence[Alignment] | None = None,
    title: str | None = None,
    max_width: int = 112,
    row_separators: bool = True,
) -> list[str]:
    """Return a full-cell ASCII table using +---+ borders."""
    row_values = [[_cell(value) for value in row] for row in rows]
    header_values = [_cell(value) for value in headers]
    column_count = len(header_values)
    if any(len(row) != column_count for row in row_values):
        raise ValueError("Todas las filas deben tener la misma cantidad de columnas.")
    normalized_aligns = list(aligns or ["left"] * column_count)
    if len(normalized_aligns) != column_count:
        raise ValueError("La cantidad de alineamientos debe coincidir con las columnas.")

    widths = _fit_widths(
        [
            max(len(header_values[index]), *(len(row[index]) for row in row_values), 1)
            for index in range(column_count)
        ],
        max_width,
    )
    wrapped_headers = [_wrap_cell(value, width) for value, width in zip(header_values, widths)]
    wrapped_rows = [
        [_wrap_cell(value, width) for value, width in zip(row, widths)]
        for row in row_values
    ]
    border = _border(widths)
    lines = []
    if title:
        table_width = len(border)
        lines.extend(audit_subtitle("", title, table_width))
    lines.append(border)
    lines.extend(_format_wrapped_row(wrapped_headers, widths, ["center"] * column_count))
    lines.append(border)
    for row in wrapped_rows:
        lines.extend(_format_wrapped_row(row, widths, normalized_aligns))
        if row_separators:
            lines.append(border)
    if not row_separators or not wrapped_rows:
        lines.append(border)
    return lines


def _fit_widths(widths: list[int], max_width: int) -> list[int]:
    if not widths:
        return widths
    target_content_width = max_width - 3 * len(widths) - 1
    minimum_widths = [4] * len(widths)
    if target_content_width < sum(minimum_widths):
        return widths

    fitted = widths[:]
    while sum(fitted) > target_content_width:
        reducible = [
            (width, index)
            for index, width in enumerate(fitted)
            if width > minimum_widths[index]
        ]
        if not reducible:
            break
        _, index = max(reducible)
        fitted[index] -= 1
    return fitted


def _wrap_cell(value: str, width: int) -> list[str]:
    if value == "":
        return [""]
    return textwrap.wrap(
        value,
        width=width,
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]


def _format_wrapped_row(
    cells: Sequence[list[str]],
    widths: Sequence[int],
    aligns: Sequence[Alignment],
) -> list[str]:
    row_height = max(len(cell) for cell in cells)
    lines = []
    for line_index in range(row_height):
        line_cells = [
            cell[line_index] if line_index < len(cell) else ""
            for cell in cells
        ]
        lines.append(_format_row(line_cells, widths, aligns))
    return lines


def key_value_box(title: str, rows: Iterable[tuple[str, object]], width: int = 104) -> list[str]:
    """Return a two-column audit box for calculated values."""
    return boxed_table(
        ("Concepto", "Valor"),
        rows,
        aligns=("left", "right"),
        title=title,
        max_width=width,
    )


def _cell(value: object) -> str:
    return "" if value is None else str(value)


def _paint_lines(lines: list[str], bold: bool) -> list[str]:
    if not _colors_enabled():
        return lines
    prefix = _ACCENT_COLOR + (_BOLD if bold else "")
    return [f"{prefix}{line}{_RESET}" for line in lines]


def _colors_enabled() -> bool:
    if os.environ.get("NO_COLOR") or os.environ.get("BRIDGE_DESIGN_NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR") or os.environ.get("BRIDGE_DESIGN_FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


def _border(widths: Sequence[int]) -> str:
    return "+" + "+".join("-" * (width + 2) for width in widths) + "+"


def _format_row(
    cells: Sequence[str],
    widths: Sequence[int],
    aligns: Sequence[Alignment],
) -> str:
    formatted = []
    for cell, width, align in zip(cells, widths, aligns):
        if align == "right":
            value = cell.rjust(width)
        elif align == "center":
            value = cell.center(width)
        else:
            value = cell.ljust(width)
        formatted.append(f" {value} ")
    return "|" + "|".join(formatted) + "|"
