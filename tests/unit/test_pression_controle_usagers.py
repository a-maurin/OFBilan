"""Agrégation pression de contrôle : une localisation = une catégorie dominante."""
from __future__ import annotations

import pandas as pd

from bilans.common.utilitaires_metier import agg_nb_controles_par_type_usager


def test_agg_nb_controles_une_ligne_une_categorie_dominante():
    df = pd.DataFrame(
        {
            "type_usager": [
                "Agriculteur 3, Particulier 1",
                "Particulier 2",
                "Particulier 1, Agriculteur 1",
            ],
        }
    )
    out = agg_nb_controles_par_type_usager(df)
    assert set(out["type_usager"]) <= {
        "Agriculteurs",
        "Particuliers",
        "Autre",
        "Collectivités",
        "Entreprises",
        "Associations",
    }
    assert int(out["nb"].sum()) == 3


def test_agg_nb_controles_vide():
    out = agg_nb_controles_par_type_usager(pd.DataFrame())
    assert list(out.columns) == ["type_usager", "nb"]
    assert out.empty
