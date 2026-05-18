"""Classification des résultats de contrôle (section 2.2)."""

from __future__ import annotations

import pandas as pd

from bilans.common.utilitaires_metier import (
    build_tab_resultats_controles,
    classify_resultat_controle,
)


def test_classify_autres_libelles_en_attente() -> None:
    assert classify_resultat_controle("Conforme") == "Conforme"
    assert classify_resultat_controle("Infraction") == "Infraction"
    assert classify_resultat_controle("Manquement") == "Manquement"
    assert classify_resultat_controle("") == "En attente"
    assert classify_resultat_controle("Non-conforme") == "En attente"
    assert classify_resultat_controle("En cours") == "En attente"


def test_build_tab_resultats_controles_agrege_en_attente() -> None:
    point = pd.DataFrame(
        {
            "resultat": [
                "Conforme",
                "Infraction",
                "Manquement",
                "Non-conforme",
                "",
                "Autre",
            ],
        }
    )
    tab = build_tab_resultats_controles(point)
    assert int(tab.loc[tab["resultat"] == "Conforme", "nb"].sum()) == 1
    assert int(tab.loc[tab["resultat"] == "Non-conforme", "nb"].sum()) == 2
    assert int(tab.loc[tab["resultat"] == "En attente", "nb"].sum()) == 3
