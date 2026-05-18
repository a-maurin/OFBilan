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
PDF_LABEL_CTRL_LOCATIONS = "Localisations de contrôle"
PDF_LABEL_CTRL_LOCATIONS_SHORT = "Loc. de contrôle"
PDF_LABEL_NON_CONFORME_LOCATIONS = "Loc. non-conformes"
PDF_LABEL_EFFECTIFS = "Effectifs"

_PDF_COLUMN_LABELS: dict[str, str] = {
    "domaine": "Domaine",
    "theme": "Thème",
    "type_usager": "Type d'usager",
    "nb_pej": PDF_LABEL_PEJ,
    "nb_pa": "PA",
    "nb_pve": "PVe",
    "nb_controles": PDF_LABEL_CTRL_LOCATIONS_SHORT,
    "resultat": "Résultat",
}

_METRIC_SUFFIX_CTRL = " (localisations de contrôle)"
_METRIC_SUFFIX_PROC = " (nombre de procédures)"
_METRIC_SUFFIX_EFFECTIFS = " (effectifs d'usagers)"


def pdf_metric_caption(title: str, metric: str) -> str:
    """
    Complète un titre de tableau ou graphique avec la métrique si elle n'y figure pas déjà.

    metric : ``ctrl`` | ``proc`` | ``effectifs``
    """
    t = str(title).strip()
    low = t.lower()
    if metric == "ctrl" and "localisation" not in low:
        return t + _METRIC_SUFFIX_CTRL
    if metric == "proc" and "procédure" not in low and "pej" not in low and "pve" not in low:
        return t + _METRIC_SUFFIX_PROC
    if metric == "effectifs" and "effectif" not in low:
        return t + _METRIC_SUFFIX_EFFECTIFS
    return t


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
        ("res_par_usager_domaine", ["nb_controles", "nb_conforme", "nb_manquement", "nb_infraction"]),
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


def build_resultats_par_usager_domaine_pdf_rows(
    df: pd.DataFrame,
    *,
    is_single_usager: bool,
    max_rows: int = 15,
) -> tuple[list[str], list[list[str]], bool]:
    """
    Construit l'en-tête et les lignes du tableau « résultats par domaine ».

    Returns:
        (header, body_rows, with_type_usager_column)
    """
    if df is None or df.empty:
        return [], [], False

    work = df.copy()
    for col in ("nb_conforme", "nb_manquement", "nb_infraction", "nb_en_attente"):
        if col not in work.columns:
            work[col] = 0
    work["_sort_res"] = work["nb_controles"].fillna(0).astype(int)
    work = work.sort_values("_sort_res", ascending=False, kind="stable").head(max_rows)

    res_field_cols: list[tuple[str, str]] = [
        ("Conforme", "nb_conforme"),
        ("Manquement", "nb_manquement"),
        ("Infraction", "nb_infraction"),
    ]
    if int(work["nb_en_attente"].fillna(0).sum()) > 0:
        res_field_cols.append(("En attente", "nb_en_attente"))
    res_cols = [label for label, _ in res_field_cols]

    with_type_col = not (
        is_single_usager
        and "type_usager" in work.columns
        and work["type_usager"].nunique() == 1
    )
    if with_type_col:
        header = ["Type d'usager", "Domaine", *res_cols]
    else:
        work = work.drop(columns=["type_usager"])
        header = ["Domaine", *res_cols]

    body: list[list[str]] = []
    for _, row in work.iterrows():
        base = [str(row.get("domaine", ""))] + [
            str(int(row.get(field, 0))) for _, field in res_field_cols
        ]
        if with_type_col:
            body.append([str(row.get("type_usager", "")), *base])
        else:
            body.append(base)

    return header, body, with_type_col
