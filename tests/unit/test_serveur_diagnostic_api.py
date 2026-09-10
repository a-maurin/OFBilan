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
Tests unitaires pour l'assemblage de l'archive de diagnostic et son point d'accès API (lot 2).
"""

import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from core.common.diagnostic_helper import generer_archive_diagnostic


def test_generer_archive_diagnostic_contenu(tmp_path: Path) -> None:
    mock_df = pd.DataFrame({"col1": [1, 2], "col2": ["val1", "val2"]})
    fake_log = tmp_path / "logs" / "serveur_web.log"
    fake_log.parent.mkdir(parents=True, exist_ok=True)
    fake_log.write_text("log serveur test", encoding="utf-8")

    with patch("core.common.diagnostic_helper.get_app_data_dir", return_value=tmp_path), \
         patch("core.common.chargeurs_donnees.load_point_ctrl", return_value=mock_df), \
         patch("core.common.chargeurs_donnees.load_pej", return_value=mock_df), \
         patch("core.common.chargeurs_donnees.load_pa", return_value=mock_df), \
         patch("core.common.chargeurs_donnees.load_pve", return_value=mock_df):

        zip_bytes = generer_archive_diagnostic(nb_lignes_echantillon=2)

        assert isinstance(zip_bytes, bytes)
        assert len(zip_bytes) > 0

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            noms = zf.namelist()
            if "erreur_diagnostic_systeme.txt" in noms:
                err = zf.read("erreur_diagnostic_systeme.txt").decode("utf-8")
                raise AssertionError(f"Erreur diagnostic détectée : {err}")
            assert "diagnostic_systeme.json" in noms
            assert "resume_diagnostic.txt" in noms
            assert "logs/serveur_web.log" in noms
            assert "echantillons/point_ctrl_echantillon.csv" in noms
            assert "echantillons/pej_echantillon.csv" in noms


def test_api_diagnostic_download_serveur() -> None:
    from core.web.serveur import Handler

    handler = Handler.__new__(Handler)
    handler.path = "/api/diagnostic/download"
    handler.rfile = io.BytesIO()
    handler.wfile = io.BytesIO()
    handler.headers = {}

    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    with patch("core.common.diagnostic_helper.generer_archive_diagnostic", return_value=b"FAKE_ZIP_DATA"):
        handler.do_GET()

        handler.send_response.assert_called_with(200)
        handler.send_header.assert_any_call("Content-Type", "application/zip")
        assert handler.wfile.getvalue() == b"FAKE_ZIP_DATA"
