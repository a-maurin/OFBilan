import pandas as pd

from ofbilan.common.dataframe_rollup import rollup_small_categories


def test_rollup_small_categories_groups_small_rows() -> None:
    df = pd.DataFrame(
        [
            {"theme": "Milieux aquatiques", "nb": 500, "taux": 0.595},
            {"theme": "Chasse", "nb": 250, "taux": 0.298},
            {"theme": "Déchets", "nb": 70, "taux": 0.083},
            {"theme": "Bruit", "nb": 6, "taux": 0.007},
            {"theme": "Publicité", "nb": 5, "taux": 0.006},
        ]
    )

    out = rollup_small_categories(
        df,
        label_col="theme",
        other_label="Autres thèmes de contrôle",
        value_col="nb",
        min_pct=0.01,
        sum_cols=["nb", "taux"],
    )

    assert out is not None
    assert out["theme"].tolist() == [
        "Milieux aquatiques",
        "Chasse",
        "Déchets",
        "Autres thèmes de contrôle",
    ]
    assert int(out.iloc[-1]["nb"]) == 11
    assert round(float(out.iloc[-1]["taux"]), 3) == 0.013


def test_rollup_small_categories_keeps_last_other_row_when_capped() -> None:
    df = pd.DataFrame(
        [
            {"theme": "A", "nb": 40, "taux": 0.40},
            {"theme": "B", "nb": 30, "taux": 0.30},
            {"theme": "C", "nb": 20, "taux": 0.20},
            {"theme": "D", "nb": 6, "taux": 0.06},
            {"theme": "E", "nb": 4, "taux": 0.04},
        ]
    )

    out = rollup_small_categories(
        df,
        label_col="theme",
        other_label="Autres thèmes de contrôle",
        value_col="nb",
        min_pct=0.01,
        sum_cols=["nb", "taux"],
        max_rows=4,
    )

    assert out is not None
    assert out["theme"].tolist() == ["A", "B", "C", "Autres thèmes de contrôle"]
    assert int(out.iloc[-1]["nb"]) == 10
    assert round(float(out.iloc[-1]["taux"]), 2) == 0.10
