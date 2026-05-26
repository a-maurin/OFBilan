import pandas as pd

from bilans.engine.generation_pdf_synthese import (
    _KEY_FIGURES_GRAIN_NOTE,
    _build_usager_theme_table_rows,
    _resultats_controles_pie_data,
    _rollup_small_categories,
    _wrap_table_label,
)
from bilans.engine.generation_pdf_synthese_brochure import _theme_pct_strings_brochure


def test_key_figures_grain_note_explains_difference_briefly() -> None:
    note = _KEY_FIGURES_GRAIN_NOTE

    assert "points de contrôle" in note
    assert "fiche de contrôle" in note
    assert "peuvent donc être inférieurs ou supérieurs" in note


def test_wrap_table_label_inserts_line_breaks_without_truncating() -> None:
    wrapped = _wrap_table_label("Contrôles espaces protégés et protection des milieux")

    assert "<br/>" in wrapped
    assert "Contrôles espaces protégés" in wrapped
    assert "protection des milieux" in wrapped


def test_resultats_controles_pie_data_uses_four_expected_categories() -> None:
    df = pd.DataFrame(
        [
            {"resultat": "Conforme", "nb": 10},
            {"resultat": "Infraction", "nb": 3},
            {"resultat": "Manquement", "nb": 2},
            {"resultat": "En attente", "nb": 1},
            {"resultat": "Non-conforme", "nb": 5},
        ]
    )

    out = _resultats_controles_pie_data(df)

    assert out == {
        "Conforme": 10,
        "Infraction": 3,
        "Manquement": 2,
        "En attente": 1,
    }


def test_rollup_small_categories_adds_last_other_row() -> None:
    df = pd.DataFrame(
        [
            {"theme": "Milieux aquatiques", "nb_ctrl": 500, "nb_pej_hors_controle": 0, "nb_total": 500},
            {"theme": "Chasse", "nb_ctrl": 250, "nb_pej_hors_controle": 5, "nb_total": 255},
            {"theme": "Déchets", "nb_ctrl": 70, "nb_pej_hors_controle": 0, "nb_total": 70},
            {"theme": "Bruit", "nb_ctrl": 6, "nb_pej_hors_controle": 0, "nb_total": 6},
            {"theme": "Publicité", "nb_ctrl": 4, "nb_pej_hors_controle": 1, "nb_total": 5},
        ]
    )

    out = _rollup_small_categories(
        df,
        label_col="theme",
        other_label="Autres thèmes de contrôle",
        value_col="nb_total",
        min_pct=0.01,
        sum_cols=["nb_ctrl", "nb_pej_hors_controle", "nb_total"],
    )

    assert out is not None
    assert out["theme"].tolist() == [
        "Milieux aquatiques",
        "Chasse",
        "Déchets",
        "Autres thèmes de contrôle",
    ]
    assert int(out.iloc[-1]["nb_ctrl"]) == 10
    assert int(out.iloc[-1]["nb_pej_hors_controle"]) == 1
    assert int(out.iloc[-1]["nb_total"]) == 11


def test_theme_pct_strings_brochure_use_global_total() -> None:
    values = [326, 162, 107, 61, 36]

    out = _theme_pct_strings_brochure(values, total_value=980)

    assert out == ["33 %", "17 %", "11 %", "6 %", "4 %"]


def test_build_usager_theme_table_rows_keeps_full_theme_label() -> None:
    df = pd.DataFrame(
        [
            {
                "theme": "Protection des milieux naturels et de la biodiversite remarquable",
                "nb_effectifs": 3,
                "nb_pej_suite_controle": 1,
                "nb_pej_hors_controle": 2,
                "nb_total": 6,
            }
        ]
    )

    rows = _build_usager_theme_table_rows(df)

    assert rows[1][0] == "Protection des milieux naturels et de la biodiversite remarquable"
