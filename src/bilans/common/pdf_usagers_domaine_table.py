"""Préparation du tableau PDF « Usagers × Domaine » (troncature pilotée YAML)."""

from __future__ import annotations

from typing import Any

import pandas as pd


def build_usagers_x_domaine_pdf_rows(
    cross_df: pd.DataFrame,
    *,
    tables_layout: dict[str, Any] | None,
) -> tuple[list[list[str]], str | None]:
    """
    Construit les lignes du tableau (en-tête + données) et un message HTML optionnel.

    - Colonnes domaines : tri décroissant sur la somme des contrôles par colonne,
      puis troncature selon ``max_domain_columns``.
    - Lignes : tri décroissant sur la somme des contrôles (toutes colonnes domaines),
      puis troncature selon ``max_usager_rows``.
    """
    cfg_root = tables_layout if isinstance(tables_layout, dict) else {}
    cfg = cfg_root.get("usagers_x_domaine")
    if not isinstance(cfg, dict):
        cfg = {}

    id_col = "type_usager"
    if id_col not in cross_df.columns or cross_df.empty:
        return [], None

    df = cross_df.copy()
    _skip_meta = {id_col, "total", "Total"}
    domain_cols_all = [c for c in df.columns if c not in _skip_meta]
    for c in domain_cols_all:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    if not domain_cols_all:
        header = [id_col]
        tbl: list[list[str]] = [header]
        for _, row in df.iterrows():
            tbl.append([str(row[id_col])])
        return tbl, None

    col_sums = {c: int(df[c].sum()) for c in domain_cols_all}
    ordered_domains = sorted(domain_cols_all, key=lambda c: col_sums[c], reverse=True)

    max_dom = cfg.get("max_domain_columns")
    if max_dom is None or (isinstance(max_dom, (int, float)) and int(max_dom) <= 0):
        max_dom_eff = len(ordered_domains)
    else:
        max_dom_eff = min(len(ordered_domains), int(max_dom))

    shown_domains = ordered_domains[:max_dom_eff]
    omitted_domains = ordered_domains[max_dom_eff:]

    max_rows = cfg.get("max_usager_rows")
    if max_rows is None or (isinstance(max_rows, (int, float)) and int(max_rows) <= 0):
        max_rows_eff = len(df)
    else:
        max_rows_eff = int(max_rows)

    n_rows_total = len(df)
    df["_row_sort"] = df[domain_cols_all].sum(axis=1)
    df = df.sort_values("_row_sort", ascending=False, kind="stable").drop(
        columns=["_row_sort"], errors="ignore"
    )
    df = df.head(max_rows_eff)
    n_rows_shown = len(df)

    header = [id_col] + [str(c) for c in shown_domains]
    tbl: list[list[str]] = [header]
    for _, row in df.iterrows():
        tbl.append([str(row[id_col])] + [str(int(row[c])) for c in shown_domains])

    parts: list[str] = []
    if len(shown_domains) < len(ordered_domains):
        col_tpl = str(
            cfg.get("overflow_note_column_part")
            or (
                "Domaines : {shown} colonnes affichées sur {total} "
                "(ordre décroissant du volume de contrôles par domaine)."
            )
        )
        parts.append(
            col_tpl.format(shown=len(shown_domains), total=len(ordered_domains))
        )
    if n_rows_shown < n_rows_total:
        row_tpl = str(
            cfg.get("overflow_note_row_part")
            or (
                "Types d’usagers : {rows_shown} lignes affichées sur {rows_total} "
                "(ordre décroissant du volume de contrôles sur les colonnes affichées)."
            )
        )
        parts.append(
            row_tpl.format(rows_shown=n_rows_shown, rows_total=n_rows_total)
        )

    if not parts:
        return tbl, None

    sep = str(cfg.get("overflow_note_separator") or " ")
    combined = sep.join(parts)
    wrap_tpl = cfg.get("overflow_note_wrap")
    if isinstance(wrap_tpl, str) and wrap_tpl.strip():
        note_html = wrap_tpl.format(note=combined)
    else:
        note_html = f"<i>{combined}</i>"
    return tbl, note_html
