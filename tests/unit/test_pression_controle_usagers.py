"""Section 4 pression de contrôle : effectifs multi-usagers par catégorie."""
from __future__ import annotations

import pandas as pd

from bilans.common.utilitaires_metier import (
    agg_controles_par_type_usager_domaine,
    agg_controles_par_type_usager_theme,
    agg_effectifs_usagers,
    agg_nb_controles_par_type_usager,
    count_multi_usager_controles,
)


def test_agg_effectifs_repartit_multi_usagers():
    df = pd.DataFrame(
        {
            "type_usager": [
                "Agriculteur 3, Particulier 1",
                "Particulier 2",
            ],
        }
    )
    out = agg_effectifs_usagers(df)
    assert int(out["nb"].sum()) == 6


def test_agg_effectifs_vide():
    out = agg_effectifs_usagers(pd.DataFrame())
    assert list(out.columns) == ["type_usager", "nb"]
    assert out.empty


def test_agg_effectifs_ne_compte_qu_une_fois_par_fc_id():
    df = pd.DataFrame(
        {
            "fc_id": ["FC-1", "FC-1"],
            "type_usager": ["Collectivité 12", "Collectivité 12"],
        }
    )

    out = agg_effectifs_usagers(df)

    assert int(out["nb"].sum()) == 12
    assert int(out.loc[out["type_usager"] == "Collectivité", "nb"].sum()) == 12


def test_agg_nb_controles_consolide_par_fc_id():
    df = pd.DataFrame(
        {
            "fc_id": ["FC-1", "FC-1"],
            "type_usager": ["Collectivité 12", "Collectivité 12"],
        }
    )

    out = agg_nb_controles_par_type_usager(df)

    assert int(out["nb"].sum()) == 1
    assert int(out.loc[out["type_usager"] == "Collectivité", "nb"].sum()) == 1


def test_agg_controles_par_type_usager_dimension_consolide_par_fc_id():
    df = pd.DataFrame(
        {
            "fc_id": ["FC-1", "FC-1"],
            "domaine": ["Eau", "Eau"],
            "theme": ["Thème A", "Thème A"],
            "type_usager": ["Collectivité 12", "Collectivité 12"],
        }
    )

    out_dom = agg_controles_par_type_usager_domaine(df)
    out_theme = agg_controles_par_type_usager_theme(df)

    assert int(out_dom["nb_controles"].sum()) == 1
    assert int(
        out_dom.loc[
            (out_dom["type_usager"] == "Collectivité") & (out_dom["domaine"] == "Eau"),
            "nb_controles",
        ].sum()
    ) == 1
    assert int(out_theme["nb_controles"].sum()) == 1
    assert int(
        out_theme.loc[
            (out_theme["type_usager"] == "Collectivité") & (out_theme["theme"] == "Thème A"),
            "nb_controles",
        ].sum()
    ) == 1


def test_count_multi_usager_controles_consolide_par_fc_id():
    df = pd.DataFrame(
        {
            "fc_id": ["FC-1", "FC-1", "FC-2"],
            "type_usager": [
                "Collectivité 1, Agriculteur 1",
                "Collectivité 1, Agriculteur 1",
                "Collectivité 1",
            ],
        }
    )

    assert count_multi_usager_controles(df) == 1
