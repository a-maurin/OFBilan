"""Tri décroissant des tableaux PDF (parties 2 et 3)."""

from __future__ import annotations

import pandas as pd

from core.common.pdf_table_sort import (
    PDF_LABEL_PEJ,
    pdf_column_label,
    prepare_pdf_results_sec23_sorting,
    resultat_controle_label_for_pdf,
    sort_dataframe_desc,
    sort_dataframe_desc_by_sum,
    sort_detail_dataframe_by_date_desc,
    sort_tab_resultats_controles_for_pdf,
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


def test_pdf_column_label_coeur_hors_coeur_is_zone() -> None:
    assert pdf_column_label("coeur_hors_coeur") == "Zone"


    assert pdf_column_label("nb_pej") == PDF_LABEL_PEJ
    assert pdf_column_label("nb_pa") == "PA"
    assert "Pj" not in pdf_column_label("nb_pej")


def test_pdf_metric_caption_suffixes() -> None:
    from core.common.pdf_table_sort import pdf_metric_caption

    assert "localisation" in pdf_metric_caption("Résultats des contrôles", "ctrl").lower()
    assert "procédure" in pdf_metric_caption("Synthèse par domaine", "proc").lower()
    assert pdf_metric_caption("PEJ par thème", "proc") == "PEJ par thème"
    assert "effectif" in pdf_metric_caption("Répartition par type", "effectifs").lower()
    assert pdf_metric_caption("Effectifs par type", "effectifs") == "Effectifs par type"


def test_sort_tab_resultats_controles_for_pdf_fixed_order() -> None:
    df = pd.DataFrame(
        {
            "resultat": [
                "En attente",
                "    Dont manquement",
                "Conforme",
                "    Dont infraction",
                "Non-conforme",
            ],
            "nb": [1, 0, 75, 36, 36],
        }
    )
    out = sort_tab_resultats_controles_for_pdf(df)
    assert [str(x).strip() for x in out["resultat"]] == [
        "Conforme",
        "Non-conforme",
        "Dont manquement",
        "Dont infraction",
        "En attente",
    ]


def test_resultat_controle_label_for_pdf_indents_dont_rows() -> None:
    assert resultat_controle_label_for_pdf("    Dont infraction").startswith("&nbsp;")
    assert "Dont infraction" in resultat_controle_label_for_pdf("    Dont infraction")


def test_prepare_pdf_results_sec23_sorting() -> None:
    results = {
        "pej_par_theme": pd.DataFrame({"theme": ["a", "b"], "nb_pej": [2, 9]}),
        "zone_pve": pd.DataFrame({"zone": ["PNF", "TUB"], "nb": [4, 12]}),
    }
    prepare_pdf_results_sec23_sorting(results)
    assert results["pej_par_theme"]["theme"].tolist() == ["b", "a"]
    assert results["zone_pve"]["zone"].tolist() == ["TUB", "PNF"]
