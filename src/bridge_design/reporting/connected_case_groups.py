"""Human combination names and compatible envelope families for reporting."""

from dataclasses import dataclass


def case_label(name):
    return name.removeprefix("Par simultaneo ingresado / ")


@dataclass(frozen=True)
class CombinationGroup:
    name: str
    cases: tuple[str, ...]
    limit_state: str


def combination_groups(result):
    groups = {}
    for row in result.results:
        prefix, label = row.name.rsplit(" / ", 1)
        family = next((name for name in ("Resistencia Ia", "Resistencia Ib", "Servicio I", "Evento Extremo I")
                       if label == name or label.startswith(name + " ")), label)
        key = (prefix, family)
        groups.setdefault(key, []).append(row)
    return tuple(CombinationGroup(case_label(prefix + " / " + family),
                                  tuple(row.name for row in rows), rows[0].limit_state)
                 for (prefix, family), rows in groups.items())


def foundation_combination_groups(result):
    """Four soil envelopes, including all simultaneous pairs and deck conditions."""
    families = ("Resistencia Ia", "Resistencia Ib", "Servicio I", "Evento Extremo I")
    grouped = {family: [] for family in families}
    for row in result.results:
        label = row.name.rsplit(" / ", 1)[-1]
        family = next((name for name in families if label == name or label.startswith(name + " ")), None)
        if family is None:
            raise ValueError(f"Familia de combinación no reconocida: {row.name}")
        grouped[family].append(row)
    return tuple(CombinationGroup(family, tuple(row.name for row in rows), rows[0].limit_state)
                 for family, rows in grouped.items() if rows)
