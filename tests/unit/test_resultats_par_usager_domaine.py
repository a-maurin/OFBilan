"""Résultats des contrôles par domaine : colonnes Conforme / Manquement / Infraction."""
from __future__ import annotations

import pandas as pd

from core.common.pdf_table_sort import build_resultats_par_usager_domaine_pdf_rows
from core.common.utilitaires_metier import agg_resultats_par_type_usager_domaine


def test_agg_resultats_domaine_conforme_infraction_manquement() -> None:
    df = pd.DataFrame(
        {
            "domaine": ["Eau", "Eau", "Faune"],
            "resultat": ["Conforme", "Infraction", "Manquement"],
            "type_usager": ["Agriculteur 1", "Agriculteur 1", "Agriculteur 1"],
        }
    )
    out = agg_resultats_par_type_usager_domaine(df)
    eau = out[out["domaine"] == "Eau"].iloc[0]
    assert int(eau["nb_conforme"]) == 1
    assert int(eau["nb_infraction"]) == 1
    assert int(eau["nb_manquement"]) == 0
    assert int(eau["nb_en_attente"]) == 0
    assert int(eau["nb_localisations"]) == 2
    faune = out[out["domaine"] == "Faune"].iloc[0]
    assert int(faune["nb_manquement"]) == 1
    assert int(faune["nb_localisations"]) == 1


def test_agg_resultats_domaine_en_attente() -> None:
    df = pd.DataFrame(
        {
            "domaine": ["Eau", "Eau"],
            "resultat": ["Conforme", ""],
            "type_usager": ["Agriculteur 1", "Agriculteur 1"],
        }
    )
    out = agg_resultats_par_type_usager_domaine(df)
    row = out.iloc[0]
    assert int(row["nb_conforme"]) == 1
    assert int(row["nb_en_attente"]) == 1
    assert int(row["nb_localisations"]) == 2


def test_agg_resultats_domaine_consolide_par_fc_id() -> None:
    df = pd.DataFrame(
        {
            "fc_id": ["FC-1", "FC-1"],
            "domaine": ["Eau", "Eau"],
            "resultat": ["Infraction", "Infraction"],
            "type_usager": ["Collectivité 1", "Collectivité 1"],
        }
    )

    out = agg_resultats_par_type_usager_domaine(df)
    row = out.iloc[0]

    assert int(row["nb_infraction"]) == 1
    assert int(row["nb_localisations"]) == 1


def test_pdf_rows_mono_usager_aligne_colonnes_avec_en_attente() -> None:
    """Régression : 5 colonnes (domaine + 4 métriques) ne doit pas ajouter type_usager."""
    df = pd.DataFrame(
        {
            "type_usager": ["Agriculteur"] * 2,
            "domaine": ["Eau", "Faune"],
            "nb_conforme": [172, 10],
            "nb_manquement": [10, 1],
            "nb_infraction": [3, 0],
            "nb_en_attente": [2, 0],
            "nb_localisations": [187, 11],
        }
    )
    hdr, body, with_type = build_resultats_par_usager_domaine_pdf_rows(
        df, is_single_usager=True
    )
    assert with_type is False
    assert hdr == ["Domaine", "Conforme", "Manquement", "Infraction", "En attente"]
    assert len(body[0]) == len(hdr)
    assert body[0][0] == "Eau"
    assert body[0][1:] == ["172", "10", "3", "2"]
