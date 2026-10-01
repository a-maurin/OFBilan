# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.

import pandas as pd
import pytest
from shapely.geometry import Point
import geopandas as gpd

from core.engine.orchestrateur_profils import _sanitize_gdf_for_gpkg
from core.common.chargeurs_donnees import get_communes_centroids_dicts
from core.chemins_projet import PROJECT_ROOT


def test_sanitize_gdf_for_gpkg_removes_case_duplicate_columns():
    df = pd.DataFrame({
        "INF-ID": [1, 2],
        "UNITE_Libelle": ["Brigade A", "Brigade B"],
        "UNITE_libelle": ["Brigade A", "Brigade B"],
        "unite_libelle": ["Brigade A", "Brigade B"],
        "date_ctrl": pd.to_datetime(["2025-07-01", "2025-08-01"]),
    })
    gdf = gpd.GeoDataFrame(df, geometry=[Point(5.0, 47.0), Point(5.1, 47.1)], crs="EPSG:4326")
    
    cleaned = _sanitize_gdf_for_gpkg(gdf)
    
    cols = list(cleaned.columns)
    # Vérification : une seule colonne d'unité est conservée
    unite_cols = [c for c in cols if str(c).lower() == "unite_libelle"]
    assert len(unite_cols) == 1
    assert unite_cols[0] == "UNITE_Libelle"
    assert "geometry" in cols
    # Vérification : conversion datetime en chaîne
    assert cleaned["date_ctrl"].dtype == object


def test_communes_centroids_resolution_with_project_root():
    dict_x, dict_y = get_communes_centroids_dicts(PROJECT_ROOT)
    assert isinstance(dict_x, dict)
    assert isinstance(dict_y, dict)
    assert len(dict_x) > 0
    # Vérification d'une commune de Côte-d'Or (ex. Dijon 21231)
    if "21231" in dict_x:
        assert isinstance(dict_x["21231"], float)
        assert isinstance(dict_y["21231"], float)
