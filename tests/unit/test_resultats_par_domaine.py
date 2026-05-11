from __future__ import annotations

import pandas as pd

from bilans.engine.agregations_profil import _resultats_par_domaine_pour_pdf


def test_resultats_par_domaine_conforme_nc_attente() -> None:
    pt = pd.DataFrame(
        {
            "domaine": ["A", "A", "B", "B", "B", "C"],
            "resultat": [
                "Conforme",
                "Infraction",
                "Conforme",
                "Manquement",
                "Conforme",
                "Autre",
            ],
        }
    )
    out = _resultats_par_domaine_pour_pdf(pt)
    row_b = out.loc[out["domaine"] == "B"].iloc[0]
    assert int(row_b["Conforme"]) == 2
    assert int(row_b["Non-conforme"]) == 1
    assert int(row_b["En attente"]) == 0

    row_c = out.loc[out["domaine"] == "C"].iloc[0]
    assert int(row_c["Conforme"]) == 0
    assert int(row_c["Non-conforme"]) == 0
    assert int(row_c["En attente"]) == 1
