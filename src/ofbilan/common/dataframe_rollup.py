"""Helpers pandas pour regrouper des petites categories dans les tableaux PDF."""

from __future__ import annotations

from typing import Iterable

import pandas as pd


def _aggregate_other_row(
    df: pd.DataFrame,
    *,
    label_col: str,
    other_label: str,
    value_col: str,
    sum_cols: Iterable[str] | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df

    numeric_sum_cols = list(sum_cols or [])
    if not numeric_sum_cols:
        numeric_sum_cols = [
            col
            for col in df.columns
            if col != label_col and pd.api.types.is_numeric_dtype(df[col])
        ]
    if value_col not in numeric_sum_cols:
        numeric_sum_cols.append(value_col)

    other_row: dict[str, object] = {label_col: other_label}
    for col in numeric_sum_cols:
        if col in df.columns:
            other_row[col] = df[col].sum()
    return pd.DataFrame([other_row])


def rollup_small_categories(
    df: pd.DataFrame | None,
    *,
    label_col: str,
    other_label: str,
    value_col: str,
    min_pct: float | None = 0.01,
    sum_cols: list[str] | None = None,
    max_rows: int | None = None,
) -> pd.DataFrame | None:
    """Regroupe les categories sous un seuil et, si besoin, les excedents de lignes."""
    if df is None or df.empty or value_col not in df.columns or label_col not in df.columns:
        return df

    ordered = df.sort_values(by=value_col, ascending=False, kind="stable").reset_index(drop=True)
    total = float(ordered[value_col].astype(float).sum())
    if total <= 0:
        return ordered

    if min_pct is None:
        kept = ordered.copy()
        hidden = ordered.iloc[0:0].copy()
    else:
        shares = ordered[value_col].astype(float) / total
        kept = ordered.loc[shares >= float(min_pct)].copy().reset_index(drop=True)
        hidden = ordered.loc[shares < float(min_pct)].copy().reset_index(drop=True)

    out = kept
    if not hidden.empty:
        out = pd.concat(
            [
                kept,
                _aggregate_other_row(
                    hidden,
                    label_col=label_col,
                    other_label=other_label,
                    value_col=value_col,
                    sum_cols=sum_cols,
                ),
            ],
            ignore_index=True,
        )

    if max_rows is not None and max_rows > 0 and len(out) > max_rows:
        keep_count = max_rows - 1 if max_rows > 1 else 0
        visible = out.head(keep_count).copy() if keep_count > 0 else out.iloc[0:0].copy()
        overflow = out.iloc[keep_count:].copy()
        out = pd.concat(
            [
                visible,
                _aggregate_other_row(
                    overflow,
                    label_col=label_col,
                    other_label=other_label,
                    value_col=value_col,
                    sum_cols=sum_cols,
                ),
            ],
            ignore_index=True,
        )

    return out.reset_index(drop=True)
