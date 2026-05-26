import pandas as pd

from bilans.engine.generation_pdf_synthese import _rollup_small_categories
from bilans.engine.generation_pdf_synthese_brochure import _theme_pct_strings_brochure


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
