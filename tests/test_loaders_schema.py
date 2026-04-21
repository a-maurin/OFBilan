from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

def test_load_point_ctrl_missing_required_columns(monkeypatch, tmp_path: Path) -> None:
    """
    Vérifie que load_point_ctrl lève une erreur explicite si une colonne
    obligatoire est absente du GPKG.
    """
    import scripts.common.loaders as loaders

    root = tmp_path
    sources_sig = root / "sources" / "sig"
    year_dir = sources_sig / "points_de_ctrl_OSCEAN_2025"
    year_dir.mkdir(parents=True)
    fake_file = year_dir / "point_ctrl_20250101.gpkg"
    fake_file.write_bytes(b"")  # le contenu est ignoré par le mock

    # Monkeypatch du répertoire sources/sig utilisé par load_point_ctrl
    def fake_sources_sig() -> Path:
        return sources_sig

    monkeypatch.setattr(loaders, "_GPKG_ENGINE", "pyogrio", raising=False)

    # Mock de geopandas.read_file pour renvoyer un DataFrame incomplet
    import geopandas as gpd

    def fake_read_file(*args: Any, **kwargs: Any) -> gpd.GeoDataFrame:
        df = pd.DataFrame(
            [
                {
                    # "date_ctrl" manquant volontairement
                    "dc_id": 1,
                    "num_depart": "21",
                }
            ]
        )
        return gpd.GeoDataFrame(df)

    monkeypatch.setattr("scripts.common.loaders.gpd.read_file", fake_read_file)

    # Appel : on s'attend à une KeyError pour date_ctrl manquant.
    with pytest.raises(KeyError):
        loaders.load_point_ctrl(root, dept_code="21", date_deb="2025-01-01", date_fin="2025-12-31")


def test_load_communes_centroides_missing_insee_column(monkeypatch, tmp_path: Path) -> None:
    """
    Vérifie que load_communes_centroides signale proprement l'absence de
    colonne de code INSEE dans le CSV.
    """
    import scripts.common.loaders as loaders

    root = tmp_path
    sig_dir = root / "ref" / "sig"
    sig_dir.mkdir(parents=True)
    csv_path = sig_dir / "communes-france-2025.csv"
    # CSV volontairement sans colonne code_insee / CODE_INSEE / insee
    csv_path.write_text("foo,latitude_centre,longitude_centre\n1,47.0,5.0\n", encoding="utf-8")

    with pytest.raises(KeyError):
        loaders.load_communes_centroides(root)


def test_enrich_with_commune_from_geometry_adds_insee_and_name(monkeypatch, tmp_path: Path) -> None:
    """Vérifie la jointure spatiale commune -> INSEE + nom."""
    import scripts.common.loaders as loaders

    root = tmp_path
    shp_dir = root / "ref" / "sig" / "communes_21"
    shp_dir.mkdir(parents=True)
    (shp_dir / "communes.shp").write_bytes(b"")  # présence du chemin uniquement

    communes = gpd.GeoDataFrame(
        {
            "INSEE_COM": ["21231"],
            "NOM_COM": ["Dijon"],
            "geometry": [Polygon([(4.9, 47.2), (5.3, 47.2), (5.3, 47.5), (4.9, 47.5)])],
        },
        crs="EPSG:4326",
    )

    point = gpd.GeoDataFrame(
        {"id": [1], "geometry": [Point(5.04, 47.32)]},
        crs="EPSG:4326",
    )

    def fake_read_file(*args: Any, **kwargs: Any) -> gpd.GeoDataFrame:
        return communes

    monkeypatch.setattr("scripts.common.loaders.gpd.read_file", fake_read_file)

    out = loaders.enrich_with_commune_from_geometry(point, root)

    assert "insee_comm" in out.columns
    assert "nom_commune" in out.columns
    assert str(out.loc[0, "insee_comm"]) == "21231"
    assert str(out.loc[0, "nom_commune"]) == "Dijon"


def test_enrich_with_commune_from_geometry_requires_geometry_column(tmp_path: Path) -> None:
    """Vérifie le message d'erreur explicite sans géométrie."""
    import scripts.common.loaders as loaders

    root = tmp_path
    df = pd.DataFrame({"id": [1]})
    with pytest.raises(KeyError):
        loaders.enrich_with_commune_from_geometry(df, root)


def test_ensure_insee_from_communes_shp_builds_from_xy(monkeypatch, tmp_path: Path) -> None:
    """Lot 2 : points de contrôle sans insee_comm mais avec x/y -> jointure communes.shp."""
    import scripts.common.loaders as loaders

    root = tmp_path
    shp_dir = root / "ref" / "sig" / "communes_21"
    shp_dir.mkdir(parents=True)
    (shp_dir / "communes.shp").write_bytes(b"")

    communes = gpd.GeoDataFrame(
        {
            "INSEE_COM": ["21231"],
            "NOM_COM": ["Dijon"],
            "geometry": [Polygon([(4.9, 47.2), (5.3, 47.2), (5.3, 47.5), (4.9, 47.5)])],
        },
        crs="EPSG:4326",
    )

    def fake_read_file(*args: Any, **kwargs: Any) -> gpd.GeoDataFrame:
        return communes

    monkeypatch.setattr("scripts.common.loaders.gpd.read_file", fake_read_file)

    df = pd.DataFrame({"dc_id": ["a"], "x": [5.04], "y": [47.32]})
    out = loaders.ensure_insee_from_communes_shp(df, root, context="test")
    assert "geometry" not in out.columns
    assert str(out.loc[0, "insee_comm"]) == "21231"
    assert str(out.loc[0, "nom_commune"]) == "Dijon"


def test_merge_pej_faits_locations_joins_dossier_to_dc_id(tmp_path: Path) -> None:
    """Jointure PEJ (ODS) ↔ FAITS : DC_ID = dossier, entité SD{dept}, x/y faits."""
    import scripts.common.loaders as loaders

    root = tmp_path
    pj = root / "sources" / "sig" / "points_infractions_pj"
    pj.mkdir(parents=True)
    gdf = gpd.GeoDataFrame(
        {
            "entite": ["SD21", "SD21", "SD39"],
            "dossier": ["OF001", "OF002", "OF003"],
            "x_infrac": [5.0, 6.0, 7.0],
            "y_infrac": [47.0, 48.0, 49.0],
            "geometry": [Point(5, 47), Point(6, 48), Point(7, 49)],
        },
        crs="EPSG:4326",
    )
    out_path = pj / "localisation_infrac_FAITS_20260306.gpkg"
    gdf.to_file(out_path, driver="GPKG")

    pej = pd.DataFrame({"DC_ID": ["OF001", "OF999"], "foo": [1, 2]})
    out = loaders.merge_pej_faits_locations(pej, root, "21", log=None)
    assert float(out.loc[0, "x_faits"]) == 5.0
    assert float(out.loc[0, "y_faits"]) == 47.0
    assert pd.isna(out.loc[1, "x_faits"])
    assert pd.isna(out.loc[1, "y_faits"])


def test_enrich_pve_positions_from_pnf_commune_centroids_joins_insee(
    monkeypatch, tmp_path: Path
) -> None:
    """PVe : INF-INSEE joint au shapefile centroïdes PNF → x/y WGS84."""
    import scripts.common.loaders as loaders

    root = tmp_path
    ref_dir = root / "ref" / "sig" / "communes_pnf"
    ref_dir.mkdir(parents=True)
    (ref_dir / "communes_PNF_centroides.shp").write_bytes(b"")

    def fake_read_file(path: Any, *args: Any, **kwargs: Any) -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame(
            {
                "INSEE_COM": ["21231", "21000"],
                "long_centr": [5.04, 4.5],
                "lat_centro": [47.32, 47.0],
                "geometry": [Point(0, 0), Point(1, 1)],
            },
            crs="EPSG:4326",
        )

    monkeypatch.setattr("scripts.common.loaders.gpd.read_file", fake_read_file)

    # Colonnes GPS en chaînes (comme read_excel dtype=str) : doit accepter des floats centroïde.
    df = pd.DataFrame(
        {
            "INF-INSEE": ["21231", "99999"],
            "INF-NATINF": ["1", "2"],
            "inf_gps_long": pd.Series(["4.0", ""], dtype="string"),
            "inf_gps_lat": pd.Series(["47.0", ""], dtype="string"),
        }
    )
    out = loaders.enrich_pve_positions_from_pnf_commune_centroids(root, df, log=None)
    assert float(out.loc[0, "x"]) == 5.04
    assert float(out.loc[0, "y"]) == 47.32
    assert float(out.loc[0, "inf_gps_long"]) == 5.04
    assert float(out.loc[0, "inf_gps_lat"]) == 47.32
    assert pd.isna(out.loc[1, "x"])

