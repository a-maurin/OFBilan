"""Section 4 pression de contrôle : effectifs multi-usagers par catégorie."""
from __future__ import annotations

import pandas as pd

from bilans.common.utilitaires_metier import agg_effectifs_usagers


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
