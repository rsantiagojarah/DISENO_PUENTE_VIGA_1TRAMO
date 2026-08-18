"""Immutable report context assembled by the deck command."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DeckReportData:
    """All adopted inputs, analyses, selections and checks for one deck run."""

    project_inputs: Any
    transverse_result: Any
    slab_reinforcement: Any
    slab_selected: tuple[tuple[str, Any], ...]
    slab_crack: Any
    interior_result: Any
    interior_reinforcement: Any
    interior_shear: Any
    interior_selected: tuple[tuple[str, Any], ...]
    interior_detail: Any
    exterior_result: Any
    exterior_reinforcement: Any
    exterior_shear: Any
    exterior_selected: tuple[tuple[str, Any], ...]
    exterior_detail: Any
    barrier_result: Any
    cantilever_result: Any
    cantilever_selected: tuple[tuple[str, Any], ...]
    diaphragm_result: Any
    diaphragm_reinforcement: Any
    diaphragm_selected: tuple[tuple[str, Any], ...]
    audit_sections: tuple[tuple[str, str], ...] = ()


def selected_option(items: tuple[tuple[str, Any], ...], prefix: str) -> Any | None:
    """Return the adopted option whose display label begins with prefix."""
    for label, option in items:
        if label.startswith(prefix):
            return option
    return None
