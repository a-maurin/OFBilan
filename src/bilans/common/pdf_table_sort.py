"""Tri décroissant des jeux de données affichés dans les tableaux PDF (parties 2 et 3)."""

from __future__ import annotations

import pandas as pd

_COUNT_COLUMNS_PRIORITY = (
    "nb_controles",
    "nb_total",
    "nb",
    "nb_pej",
    "nb_pa",
    "nb_pve",
    "Total",
)

# Libellés d'en-têtes de tableaux PDF (ne pas dériver « nb_pej » → « Nb Pej »).
PDF_LABEL_PEJ = "PEJ"
PDF_LABEL_PEJ_COUNT = "Nombre de PEJ"

_PDF_COLUMN_LABELS: dict[str, str] = {
    "domaine": "Domaine",
    "theme": "Thème",
    "type_usager": "Type d'usager",
    "nb_pej": PDF_LABEL_PEJ,
    "nb_pa": "PA",
    "nb_pve": "PVe",
    "nb_controles": "Nombre de contrôles",
    "resultat": "Résultat",
}


def pdf_column_label(col: str) -> str:
    """Libellé affiché pour une colonne de tableau PDF."""
    key = str(col).strip()
    if key in _PDF_COLUMN_LABELS:
        return _PDF_COLUMN_LABELS[key]
    return key.replace("_", " ").title()


def sort_dataframe_desc(df: pd.DataFrame | None, columns: list[str]) -> pd.DataFrame | None:
    """Trie un DataFrame par la première colonne numérique disponible (ordre décroissant)."""
    if df is None or df.empty:
        return df
    for col in columns:
        if col in df.columns:
            return df.sort_values(by=col, ascending=False, kind="stable").reset_index(drop=True)
    return df


def sort_dataframe_desc_auto(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Tri décroissant selon une colonne de dénombrement connue."""
    return sort_dataframe_desc(df, list(_COUNT_COLUMNS_PRIORITY))


def sort_dataframe_desc_by_sum(
    df: pd.DataFrame | None,
    sum_columns: list[str] | None = None,
) -> pd.DataFrame | None:
    """Tri décroissant selon la somme de colonnes numériques ``nb_*``."""
    if df is None or df.empty:
        return df
    cols = sum_columns or [c for c in df.columns if str(c).startswith("nb_")]
    if not cols:
        return sort_dataframe_desc_auto(df)
    tmp = df.copy()
    tmp["_pdf_sort"] = tmp[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
    return sort_dataframe_desc(tmp, ["_pdf_sort"]).drop(columns=["_pdf_sort"])


def sort_detail_dataframe_by_date_desc(
    df: pd.DataFrame | None,
    date_col: str = "date",
) -> pd.DataFrame | None:
    """Tableaux de détail : tri décroissant par date (plus récent en premier)."""
    if df is None or df.empty or date_col not in df.columns:
        return df
    tmp = df.copy()
    tmp["_pdf_date"] = pd.to_datetime(tmp[date_col], errors="coerce")
    return (
        tmp.sort_values("_pdf_date", ascending=False, kind="stable")
        .drop(columns=["_pdf_date"])
        .reset_index(drop=True)
    )


def prepare_pdf_results_sec23_sorting(results: dict) -> None:
    """Applique le tri décroissant aux données des tableaux des parties 2 et 3 (in-place)."""
    column_sorts: list[tuple[str, list[str]]] = [
        ("usager_effectifs", ["nb"]),
        ("tab_resultats", ["nb"]),
        ("tab_resultats_controles", ["nb"]),
        ("pve_top_infractions", ["nb"]),
        ("pve_natinf_analysis", ["nb"]),
        ("zone_pve", ["nb"]),
        ("pej_top_infractions", ["nb"]),
        ("pej_par_theme", ["nb_pej", "nb"]),
        ("pej_natinf_analysis", ["nb"]),
        ("zone_pej", ["nb"]),
        ("pej_clotur", ["nb"]),
        ("pej_suite", ["nb"]),
        ("res_par_usager_domaine", ["nb_controles"]),
        ("zone_ctrl", ["nb_total"]),
        ("agg_theme", ["nb"]),
        ("agg_commune", ["nb_controles", "nb"]),
        ("pa_par_theme", ["nb_pa", "nb"]),
    ]
    for key, cols in column_sorts:
        value = results.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            results[key] = sort_dataframe_desc(value, cols)

    for key in ("proc_par_usager_domaine", "proc_par_usager_theme"):
        value = results.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            results[key] = sort_dataframe_desc_by_sum(value)

    for key in ("pve_detail", "pej_detail", "pa_detail"):
        value = results.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            results[key] = sort_detail_dataframe_by_date_desc(value)
