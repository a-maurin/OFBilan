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

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from core.common.chargeurs_donnees import merge_pej_faits_locations

def test_merge_pej_faits_locations_of_prefix_and_numproc(tmp_path):
    # Mock PEJ dataframe
    pej = pd.DataFrame([
        {
            "DC_ID": "OF20260707-101",
            "NUMERO_PROCEDURE": "SD21 2026 PJ 0054",
            "ENTITE_ORIGINE_PROCEDURE": "SD21",
            "DATE_REF": pd.Timestamp("2026-07-07"),
            "NOM_COM": np.nan,
        },
        {
            "DC_ID": "OF20260707-102",
            "NUMERO_PROCEDURE": "SD21 2026 PJ 0055",
            "ENTITE_ORIGINE_PROCEDURE": "SD21",
            "DATE_REF": pd.Timestamp("2026-07-07"),
            "NOM_COM": "Recey-sur-Ource",
        }
    ])

    # Mock FAITS layer dataframe
    gdf_faits = pd.DataFrame([
        # Match via cleaned ID (20260707-101) without OF prefix
        {
            "dossier": "20260707-101",
            "entite": "SD21 - Côte-d'Or",
            "x_infrac": 5.0,
            "y_infrac": 47.0,
            "commune_fait": "Recey-sur-Ource",
        }
    ])

    merged = merge_pej_faits_locations(pej, tmp_path, "dept", "21", gdf_faits=gdf_faits)
    
    assert len(merged) == 2
    row1 = merged[merged["DC_ID"] == "OF20260707-101"].iloc[0]
    assert row1["x_faits"] == 5.0
    assert row1["y_faits"] == 47.0
    assert row1["precision_loc"] == "GPS Fait (Exacte)"
    assert row1["NOM_COM"] == "Recey-sur-Ource"


def test_merge_pej_faits_locations_uses_gdf_oscean(tmp_path, monkeypatch):
    import core.common.chargeurs_donnees as cd

    called = False

    def mock_load_point_ctrl(*args, **kwargs):
        nonlocal called
        called = True
        return pd.DataFrame()

    monkeypatch.setattr(cd, "load_point_ctrl", mock_load_point_ctrl)

    pej = pd.DataFrame([
        {
            "DC_ID": "2026-DC-001",
            "NUMERO_PROCEDURE": "PROC-001",
            "NOM_COM": np.nan,
        }
    ])

    gdf_oscean = pd.DataFrame([
        {
            "dc_id": "2026-DC-001",
            "code_pej": "PROC-001",
            "nom_commun": "Dijon",
            "x": 5.04,
            "y": 47.32,
        }
    ])

    out = cd.merge_pej_faits_locations(pej, tmp_path, "departement", "21", gdf_oscean=gdf_oscean)
    assert not called
    assert out.iloc[0]["NOM_COM"] == "Dijon"
    assert out.iloc[0]["x_faits"] == 5.04
    assert out.iloc[0]["y_faits"] == 47.32
    assert out.iloc[0]["precision_loc"] == "Point de contrôle rattaché"

