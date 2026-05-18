"""Tri décroissant des tableaux PDF (parties 2 et 3)."""

from __future__ import annotations

import pandas as pd

from bilans.common.pdf_table_sort import (
    PDF_LABEL_PEJ,
    pdf_column_label,
    prepare_pdf_results_sec23_sorting,
    sort_dataframe_desc,
    sort_dataframe_desc_by_sum,
    sort_detail_dataframe_by_date_desc,
)


def test_sort_dataframe_desc_by_nb() -> None:
    df = pd.DataFrame({"theme": ["B", "A", "C"], "nb": [1, 5, 3]})
    out = sort_dataframe_desc(df, ["nb"])
    assert out is not None
    assert out["theme"].tolist() == ["A", "C", "B"]


def test_sort_detail_by_date_desc() -> None:
    df = pd.DataFrame(
        {
            "numero": ["1", "2", "3"],
            "date": ["2025-01-01", "2025-06-01", "2025-03-01"],
        }
    )
    out = sort_detail_dataframe_by_date_desc(df)
    assert out is not None
    assert out["numero"].tolist() == ["2", "3", "1"]


def test_sort_procedures_by_sum_nb_columns() -> None:
    df = pd.DataFrame(
        {
            "domaine": ["X", "Y", "Z"],
            "nb_pej": [1, 10, 5],
            "nb_pa": [0, 2, 8],
        }
    )
    out = sort_dataframe_desc_by_sum(df)
    assert out is not None
    assert out["domaine"].tolist() == ["Z", "Y", "X"]


def test_pdf_column_label_pej_not_pj() -> None:
    assert pdf_column_label("nb_pej") == PDF_LABEL_PEJ
    assert pdf_column_label("nb_pa") == "PA"
    assert "Pj" not in pdf_column_label("nb_pej")


def test_prepare_pdf_results_sec23_sorting() -> None:
    results = {
        "pej_par_theme": pd.DataFrame({"theme": ["a", "b"], "nb_pej": [2, 9]}),
        "zone_pve": pd.DataFrame({"zone": ["PNF", "TUB"], "nb": [4, 12]}),
    }
    prepare_pdf_results_sec23_sorting(results)
    assert results["pej_par_theme"]["theme"].tolist() == ["b", "a"]
    assert results["zone_pve"]["zone"].tolist() == ["TUB", "PNF"]
