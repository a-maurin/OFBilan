# -*- coding: utf-8 -*-
# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
# sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
# Voir la Licence Publique Générale GNU pour plus de détails.

"""
Tests unitaires pour le module de diagnostic et de gestion des journaux (lot 1).
"""

import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import pandas as pd

from core.common.diagnostic_helper import (
    initialiser_journal_generation,
    obtenir_chemins_journaux_recents,
    enregistrer_derniers_parametres_run,
    lire_derniers_parametres_run,
    collecter_diagnostic_systeme,
    extraire_echantillons_donnees,
)


def test_rotation_journaux_generation(tmp_path: Path) -> None:
    with patch("core.common.diagnostic_helper.get_app_data_dir", return_value=tmp_path):
        f1 = initialiser_journal_generation(max_runs=3)
        time.sleep(0.01)
        f2 = initialiser_journal_generation(max_runs=3)
        time.sleep(0.01)
        f3 = initialiser_journal_generation(max_runs=3)
        time.sleep(0.01)
        f4 = initialiser_journal_generation(max_runs=3)

        recents = obtenir_chemins_journaux_recents(max_runs=3)
        assert len(recents) == 3
        # f1 doit avoir été supprimé par la rotation
        assert not f1.exists()
        assert f2.exists()
        assert f3.exists()
        assert f4.exists()
        assert recents[0] == f4


def test_enregistrer_et_lire_derniers_parametres(tmp_path: Path) -> None:
    with patch("core.common.diagnostic_helper.get_app_data_dir", return_value=tmp_path):
        params_in = {"profil": "chasse", "echelle": "departement", "code": "21"}
        enregistrer_derniers_parametres_run(params_in)
        params_out = lire_derniers_parametres_run()
        assert params_out == params_in


def test_collecter_diagnostic_systeme(tmp_path: Path) -> None:
    with patch("core.common.diagnostic_helper.get_app_data_dir", return_value=tmp_path):
        diag = collecter_diagnostic_systeme({"profil": "peche"})
        assert "environnement" in diag
        assert "ressources" in diag
        assert "chemins" in diag
        assert "sources_donnees" in diag
        assert diag["parametres_dernier_calcul"] == {"profil": "peche"}
        assert "python_version" in diag["environnement"]
        assert "systeme_exploitation" in diag["environnement"]


def test_extraire_echantillons_donnees(tmp_path: Path) -> None:
    mock_df = pd.DataFrame({"id": [1, 2, 3], "valeur": ["a", "b", "c"]})
    with patch("core.common.chargeurs_donnees.load_point_ctrl", return_value=mock_df), \
         patch("core.common.chargeurs_donnees.load_pej", return_value=mock_df), \
         patch("core.common.chargeurs_donnees.load_pa", return_value=None), \
         patch("core.common.chargeurs_donnees.load_pve", side_effect=RuntimeError("Erreur simulée")):

        echantillons = extraire_echantillons_donnees(params={"echelle": "national", "code": "FR"}, nb_lignes=2)

        assert "point_ctrl_echantillon.csv" in echantillons
        assert "1;a" in echantillons["point_ctrl_echantillon.csv"]
        assert "pej_echantillon.csv" in echantillons
        assert "pa_echantillon.csv" in echantillons
        assert "erreur_pve_echantillon.csv.txt" in echantillons
