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

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from core.engine.orchestrateur_profils import _run_engine_thematic_pipeline


@pytest.fixture
def mock_thematic_env(monkeypatch, tmp_path):
    monkeypatch.setattr("core.engine.orchestrateur_profils.load_profile_config", lambda root, pid: {
        "id": "chasse",
        "label": "Chasse",
        "sources": {"point_ctrl": True, "pej": False, "pa": False, "pve": False},
        "options": {"pnf": {"default": False}},
    })
    monkeypatch.setattr("core.engine.orchestrateur_profils.load_point_ctrl", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr("core.engine.orchestrateur_profils.load_pej", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr("core.engine.orchestrateur_profils.load_pa", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr("core.engine.orchestrateur_profils.load_pve", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr("core.engine.orchestrateur_profils._run_spatial_analyses", lambda *a, **k: ({}, pd.DataFrame()))
    monkeypatch.setattr("core.engine.orchestrateur_profils._run_aggregations", lambda *a, **k: {})
    monkeypatch.setattr("core.engine.orchestrateur_profils._export_csv", lambda *a, **k: None)
    monkeypatch.setattr("core.engine.orchestrateur_profils.ensure_maps_for_profiles", lambda *a, **k: None)
    monkeypatch.setattr("core.engine.orchestrateur_profils.prompt_cartography_integration", lambda *a, **k: None)


def test_thematic_pipeline_format_brochure(mock_thematic_env):
    with patch("core.engine.orchestrateur_profils._generate_pdf") as mock_gen_pdf, \
         patch("core.engine.generation_pdf_synthese_brochure.generate_synthese_brochure_pdf_report") as mock_gen_brochure:
        ret = _run_engine_thematic_pipeline("chasse", "2025-01-01", "2025-12-31", "departement", "21", options={"format_sortie": "brochure", "cartes": False})
        assert ret == 0
        mock_gen_brochure.assert_called_once()
        mock_gen_pdf.assert_not_called()


def test_thematic_pipeline_format_complet(mock_thematic_env):
    with patch("core.engine.orchestrateur_profils._generate_pdf") as mock_gen_pdf, \
         patch("core.engine.generation_pdf_synthese_brochure.generate_synthese_brochure_pdf_report") as mock_gen_brochure:
        ret = _run_engine_thematic_pipeline("chasse", "2025-01-01", "2025-12-31", "departement", "21", options={"format_sortie": "complet", "cartes": False})
        assert ret == 0
        mock_gen_pdf.assert_called_once()
        mock_gen_brochure.assert_not_called()


def test_thematic_pipeline_format_les_deux(mock_thematic_env):
    with patch("core.engine.orchestrateur_profils._generate_pdf") as mock_gen_pdf, \
         patch("core.engine.generation_pdf_synthese_brochure.generate_synthese_brochure_pdf_report") as mock_gen_brochure:
        ret = _run_engine_thematic_pipeline("chasse", "2025-01-01", "2025-12-31", "departement", "21", options={"format_sortie": "les_deux", "cartes": False})
        assert ret == 0
        mock_gen_pdf.assert_called_once()
        mock_gen_brochure.assert_called_once()
