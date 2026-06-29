"""Affichage des pourcentages en entiers (PDF, tableaux, légendes de graphiques)."""
from __future__ import annotations

from typing import Sequence

import pandas as pd


def format_pct_int_from_rate(rate: float | None, *, na: str = "n.d.") -> str:
    """Formate un taux dans [0, 1] (ou proche) en pourcentage entier, ex. ``42 %``."""
    if rate is None or pd.isna(rate):
        return na
    try:
        r = float(rate)
    except (TypeError, ValueError):
        return na
    p = int(round(r * 100.0))
    p = max(0, min(100, p))
    return f"{p} %"


def int_percents_largest_remainder(counts: Sequence[int]) -> list[int]:
    """
    Répartit 100 points de pourcentage sur des effectifs entiers (méthode des plus grands restes).

    La somme des pourcentages retournés vaut exactement 100 dès que ``sum(counts) > 0``.
    """
    counts = [int(max(0, c)) for c in counts]
    total = sum(counts)
    n = len(counts)
    if n == 0:
        return []
    if total <= 0:
        return [0] * n
    longs = [100 * c for c in counts]
    floors = [ln // total for ln in longs]
    rem = [ln % total for ln in longs]
    deficit = 100 - sum(floors)
    order = sorted(range(n), key=lambda i: (rem[i], counts[i], i), reverse=True)
    for k in range(deficit):
        floors[order[k]] += 1
    return floors


def format_partition_pct_strings(counts: Sequence[int]) -> list[str]:
    """Même logique que ``int_percents_largest_remainder``, avec suffixe ``%``."""
    return [f"{p} %" for p in int_percents_largest_remainder(counts)]


def tab_counts_to_pct_strings(nbs: Sequence[int]) -> list[str]:
    """Tableau « Nombre / Taux » : taux entiers dont la somme vaut 100 % des lignes."""
    counts = [int(max(0, x)) for x in nbs]
    if not counts or sum(counts) <= 0:
        return ["n.d."] * len(counts)
    return format_partition_pct_strings(counts)
