"""Zones PNF cœur / hors-cœur depuis le shapefile 127 communes."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from bilans.common import chargeurs_donnees as loaders


def test_pnf_zone_from_coeur_oui_non() -> None:
    assert loaders._pnf_zone_from_coeur_value("oui") == "Coeur_PNF"
    assert loaders._pnf_zone_from_coeur_value("OUI") == "Coeur_PNF"
    assert loaders._pnf_zone_from_coeur_value("non") == "Aire_adhesion_PNF"
    assert loaders._pnf_zone_from_coeur_value("NON") == "Aire_adhesion_PNF"
    assert loaders._pnf_zone_from_coeur_value("") == "Aire_adhesion_PNF"
    assert loaders._pnf_zone_from_coeur_value(None) == "Aire_adhesion_PNF"


def test_load_pnf_commune_zone_maps_coeur_null_is_hors_coeur(tmp_path: Path) -> None:
    """Commune du périmètre 127 sans valeur coeur (null) → aire d'adhésion / hors-cœur."""
    shp_dir = tmp_path / "ref" / "programme" / "sig" / "PNF" / "127_communes"
    shp_dir.mkdir(parents=True)
    shp_path = shp_dir / "127_communes_AOA_et_statuts_adhesion.shp"
    gdf = gpd.GeoDataFrame(
        {
            "INSEE_COM": ["21424"],
            "NOM_COM": ["Prusly-sur-Ource"],
            "coeur": [None],
            "geometry": [Point(0, 0)],
        },
        crs="EPSG:4326",
    )
    gdf.to_file(shp_path)

    by_insee, by_nom = loaders.load_pnf_commune_zone_maps(tmp_path)
    assert by_insee["21424"] == "Aire_adhesion_PNF"
    assert by_nom["prusly-sur-ource"] == "Aire_adhesion_PNF"


def test_load_pnf_commune_zone_maps_from_127_shp(tmp_path: Path) -> None:
    shp_dir = (
        tmp_path
        / "ref"
        / "programme"
        / "sig"
        / "PNF"
        / "127_communes"
    )
    shp_dir.mkdir(parents=True)
    shp_path = shp_dir / "127_communes_AOA_et_statuts_adhesion.shp"
    gdf = gpd.GeoDataFrame(
        {
            "INSEE_COM": ["21001", "21002"],
            "NOM_COM": ["Dijon", "Beaune"],
            "coeur": ["oui", "non"],
            "geometry": [Point(0, 0), Point(1, 1)],
        },
        crs="EPSG:4326",
    )
    gdf.to_file(shp_path)

    by_insee, by_nom = loaders.load_pnf_commune_zone_maps(tmp_path)
    assert by_insee["21001"] == "Coeur_PNF"
    assert by_insee["21002"] == "Aire_adhesion_PNF"
    assert by_nom["dijon"] == "Coeur_PNF"
    assert by_nom["beaune"] == "Aire_adhesion_PNF"


def test_overlay_pnf_zone_from_127_shp(tmp_path: Path) -> None:
    shp_dir = (
        tmp_path
        / "ref"
        / "programme"
        / "sig"
        / "PNF"
        / "127_communes"
    )
    shp_dir.mkdir(parents=True)
    shp_path = shp_dir / "127_communes_AOA_et_statuts_adhesion.shp"
    gpd.GeoDataFrame(
        {
            "INSEE_COM": ["21001"],
            "NOM_COM": ["Dijon"],
            "coeur": ["oui"],
            "geometry": [Point(0, 0)],
        },
        crs="EPSG:4326",
    ).to_file(shp_path)

    df = pd.DataFrame({"insee_comm": ["21001"], "pnf_zone_sig": ["Aire_adhesion_PNF"]})
    out = loaders.overlay_pnf_zone_from_communes_pnf_csv(df, tmp_path)
    assert out.iloc[0]["pnf_zone_sig"] == "Coeur_PNF"
