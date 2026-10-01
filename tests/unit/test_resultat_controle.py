# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
# sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
# Voir la Licence Publique Générale GNU pour plus de détails.
#
# CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
# Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
# intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
# clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
# doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
# de l'auteur original (Aguirre MAURIN).

#
"""Classification des résultats de contrôle (section 2.2)."""

from __future__ import annotations

import pandas as pd

from core.common.utilitaires_metier import (
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
    assert [str(x).strip() for x in tab["resultat"]] == [
        "Conforme",
        "Non-conforme",
        "Dont manquement",
        "Dont infraction",
        "En attente",
    ]
    assert int(tab.loc[tab["resultat"] == "Conforme", "nb"].sum()) == 1
    assert int(tab.loc[tab["resultat"] == "Non-conforme", "nb"].sum()) == 2
    assert int(tab.loc[tab["resultat"] == "En attente", "nb"].sum()) == 3


def test_build_tab_resultats_controles_composite() -> None:
    point = pd.DataFrame(
        {
            "resultat": [
                "Conforme",
                "Manquement et infraction",
            ],
        }
    )
    tab = build_tab_resultats_controles(point)
    assert int(tab.loc[tab["resultat"] == "Conforme", "nb"].sum()) == 1
    assert int(tab.loc[tab["resultat"] == "Non-conforme", "nb"].sum()) == 1
    assert int(tab.loc[tab["resultat"].str.strip() == "Dont manquement", "nb"].sum()) == 1
    assert int(tab.loc[tab["resultat"].str.strip() == "Dont infraction", "nb"].sum()) == 1