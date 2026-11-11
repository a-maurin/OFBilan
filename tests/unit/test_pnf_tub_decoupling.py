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

"""Tests de découplage PNF / TUB et de résilience cartographique."""

from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest

from core.common.chargeurs_donnees import (
    load_pnf_codes,
    load_tub_codes,
    load_tub_pnf_codes,
)
from core.engine.filtres_profil import _run_spatial_analyses
from core.common.bilan_config import BilanConfig


def test_tub_codes_fail_soft_when_missing(tmp_path: Path) -> None:
    """En mode non-strict, l'absence de tub_communes.csv renvoie un ensemble vide sans lever d'erreur."""
    empty_root = tmp_path / "empty_proj"
    empty_root.mkdir()
    codes = load_tub_codes(empty_root, strict=False)
    assert codes == set()


def test_tub_codes_strict_raises_when_missing(tmp_path: Path) -> None:
    """En mode strict (ex. profil dédié TUB), l'absence de tub_communes.csv lève FileNotFoundError."""
    empty_root = tmp_path / "empty_proj"
    empty_root.mkdir()
    with pytest.raises(FileNotFoundError):
        load_tub_codes(empty_root, strict=True)


def test_pnf_codes_fail_soft_when_missing(tmp_path: Path) -> None:
    """En mode non-strict, l'absence de référentiel PNF renvoie un ensemble vide sans lever d'erreur."""
    empty_root = tmp_path / "empty_proj"
    empty_root.mkdir()
    codes = load_pnf_codes(empty_root, strict=False)
    assert codes == set()


def test_load_tub_pnf_codes_tolerant_to_missing_tub(tmp_path: Path) -> None:
    """load_tub_pnf_codes retourne les codes PNF même si tub_communes.csv est manquant."""
    fake_pnf = pd.DataFrame({"CODE_INSEE": ["21004", "21006"], "NOM": ["Aignay", "Aisey"]})
    with patch("core.common.chargeurs_donnees.load_tub", side_effect=FileNotFoundError("TUB manquant")), \
         patch("core.common.chargeurs_donnees.load_pnf", return_value=fake_pnf):
        tub_codes, pnf_codes = load_tub_pnf_codes(tmp_path, strict=False)
        assert tub_codes == set()
        assert pnf_codes == {"21004", "21006"}


def test_apply_spatial_breakdowns_pnf_only_does_not_call_tub(tmp_path: Path) -> None:
    """L'activation de l'option PNF seule ne tente pas de charger le fichier TUB manquant."""
    pt = pd.DataFrame({
        "dc_id": [1, 2],
        "insee_comm": ["21004", "99999"],
        "resultat": ["Conforme", "Non conforme"],
    })
    pej = pd.DataFrame()
    pve = pd.DataFrame()
    options = {"pnf": True, "tub": False}
    cfg = BilanConfig(
        date_deb=pd.to_datetime("2025-01-01"),
        date_fin=pd.to_datetime("2025-12-31"),
        echelle="departement",
        code="21",
        root=tmp_path,
    )

    fake_pnf = pd.DataFrame({"CODE_INSEE": ["21004"]})

    with patch("core.engine.filtres_profil.load_tub", side_effect=FileNotFoundError("TUB manquant")), \
         patch("core.engine.filtres_profil.load_pnf", return_value=fake_pnf), \
         patch("core.common.chargeurs_donnees.load_pnf", return_value=fake_pnf):
        results, pt_out = _run_spatial_analyses(pt, pej, pve, options, cfg)

        assert results.get("tub_codes") == set()
        assert results.get("pnf_codes") == {"21004"}
        assert "PNF" in pt_out.columns
        assert list(pt_out["PNF"]) == ["PNF", "Hors PNF"]


def test_thematic_pipeline_succeeds_even_if_cartography_crashes(monkeypatch, tmp_path: Path) -> None:
    """Si la cartographie QGIS échoue, l'export PDF se termine quand même avec succès."""
    from core.engine.orchestrateur_profils import _run_engine_thematic_pipeline

    monkeypatch.setattr("core.engine.orchestrateur_profils.load_profile_config", lambda root, pid: {
        "id": "chasse",
        "label": "Chasse",
        "sources": {"point_ctrl": True, "pej": False, "pa": False, "pve": False},
        "options": {"pnf": {"default": False}},
        "cartographie": {"mode": "catalog", "cartes_actives": ["resultats"]},
    })
    monkeypatch.setattr("core.engine.orchestrateur_profils.load_point_ctrl", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr("core.engine.orchestrateur_profils.load_pej", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr("core.engine.orchestrateur_profils.load_pa", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr("core.engine.orchestrateur_profils.load_pve", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr("core.engine.orchestrateur_profils._run_spatial_analyses", lambda *a, **k: ({}, pd.DataFrame()))
    monkeypatch.setattr("core.engine.orchestrateur_profils._run_aggregations", lambda *a, **k: {})
    monkeypatch.setattr("core.engine.orchestrateur_profils._export_csv", lambda *a, **k: None)
    monkeypatch.setattr("core.engine.orchestrateur_profils.prompt_cartography_integration", lambda *a, **k: None)
    
    # Simuler un crash sévère du sous-système cartographique QGIS
    def _exploding_ensure_maps(*args, **kwargs):
        raise RuntimeError("Erreur critique QGIS simulée : projet introuvable")

    monkeypatch.setattr("core.engine.orchestrateur_profils.ensure_maps_for_profiles", _exploding_ensure_maps)

    with patch("core.engine.orchestrateur_profils._generate_pdf") as mock_gen_pdf:
        ret = _run_engine_thematic_pipeline(
            "chasse",
            "2025-01-01",
            "2025-12-31",
            "departement",
            "21",
            options={"format_sortie": "complet", "cartes": True},
        )
        assert ret == 0
        mock_gen_pdf.assert_called_once()

