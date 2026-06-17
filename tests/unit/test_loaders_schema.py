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
    import ofbilan.common.chargeurs_donnees as loaders

    root = tmp_path
    sources_sig = root / "data" / "sources" / "sig"
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

    monkeypatch.setattr("ofbilan.common.chargeurs_donnees.gpd.read_file", fake_read_file)

    # Appel : on s'attend à une KeyError pour date_ctrl manquant.
    with pytest.raises(KeyError):
        loaders.load_point_ctrl(
            root, echelle="departement", code="21", date_deb="2025-01-01", date_fin="2025-12-31"
        )


def test_load_communes_centroides_missing_insee_column(monkeypatch, tmp_path: Path) -> None:
    """
    Vérifie que load_communes_centroides signale proprement l'absence de
    colonne de code INSEE dans le CSV.
    """
    import ofbilan.common.chargeurs_donnees as loaders

    root = tmp_path
    sig_dir = root / "ref" / "programme" / "sig"
    sig_dir.mkdir(parents=True)
    csv_path = sig_dir / "communes-france-2025.csv"
    # CSV volontairement sans colonne code_insee / CODE_INSEE / insee
    csv_path.write_text("foo,latitude_centre,longitude_centre\n1,47.0,5.0\n", encoding="utf-8")

    with pytest.raises(KeyError):
        loaders.load_communes_centroides(root)


def test_enrich_with_commune_from_geometry_adds_insee_and_name(monkeypatch, tmp_path: Path) -> None:
    """Vérifie la jointure spatiale commune -> INSEE + nom."""
    import ofbilan.common.chargeurs_donnees as loaders

    root = tmp_path
    shp_dir = root / "ref" / "programme" / "sig" / "communes_21"
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

    monkeypatch.setattr("ofbilan.common.chargeurs_donnees.gpd.read_file", fake_read_file)

    out = loaders.enrich_with_commune_from_geometry(point, root)

    assert "insee_comm" in out.columns
    assert "nom_commune" in out.columns
    assert str(out.loc[0, "insee_comm"]) == "21231"
    assert str(out.loc[0, "nom_commune"]) == "Dijon"


def test_enrich_with_commune_from_geometry_requires_geometry_column(tmp_path: Path) -> None:
    """Vérifie le message d'erreur explicite sans géométrie."""
    import ofbilan.common.chargeurs_donnees as loaders

    root = tmp_path
    df = pd.DataFrame({"id": [1]})
    with pytest.raises(KeyError):
        loaders.enrich_with_commune_from_geometry(df, root)


def test_ensure_insee_from_communes_shp_builds_from_xy(monkeypatch, tmp_path: Path) -> None:
    """Lot 2 : points de contrôle sans insee_comm mais avec x/y -> jointure communes.shp."""
    import ofbilan.common.chargeurs_donnees as loaders

    root = tmp_path
    shp_dir = root / "ref" / "programme" / "sig" / "communes_21"
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

    monkeypatch.setattr("ofbilan.common.chargeurs_donnees.gpd.read_file", fake_read_file)

    df = pd.DataFrame({"dc_id": ["a"], "x": [5.04], "y": [47.32]})
    out = loaders.ensure_insee_from_communes_shp(df, root, context="test")
    assert "geometry" not in out.columns
    assert str(out.loc[0, "insee_comm"]) == "21231"
    assert str(out.loc[0, "nom_commune"]) == "Dijon"


def test_ensure_insee_from_communes_shp_builds_from_xy_faits(monkeypatch, tmp_path: Path) -> None:
    """PEJ : x_faits / y_faits sans insee_comm -> jointure communes.shp."""
    import ofbilan.common.chargeurs_donnees as loaders

    root = tmp_path
    shp_dir = root / "ref" / "programme" / "sig" / "communes_21"
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

    monkeypatch.setattr("ofbilan.common.chargeurs_donnees.gpd.read_file", fake_read_file)

    df = pd.DataFrame(
        {
            "DC_ID": ["OF001", "OF002"],
            "x_faits": [5.04, pd.NA],
            "y_faits": [47.32, pd.NA],
        }
    )
    out = loaders.ensure_insee_from_communes_shp(df, root, context="test PEJ faits")
    assert "geometry" not in out.columns
    assert str(out.loc[0, "insee_comm"]) == "21231"
    assert str(out.loc[0, "nom_commune"]) == "Dijon"
    assert pd.isna(out.loc[1, "insee_comm"]) or str(out.loc[1, "insee_comm"]).strip() in (
        "",
        "nan",
        "<NA>",
    )


def test_enrich_pej_commune_from_faits_coordinates_fills_nom_com(
    monkeypatch, tmp_path: Path
) -> None:
    """enrich_pej_commune_from_faits_coordinates propage nom_commune vers NOM_COM."""
    import ofbilan.common.chargeurs_donnees as loaders

    root = tmp_path
    shp_dir = root / "ref" / "programme" / "sig" / "communes_21"
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

    monkeypatch.setattr("ofbilan.common.chargeurs_donnees.gpd.read_file", fake_read_file)

    pej = pd.DataFrame({"DC_ID": ["OF001"], "NOM_COM": [""], "x_faits": [5.04], "y_faits": [47.32]})
    out = loaders.enrich_pej_commune_from_faits_coordinates(pej, root, log=None)
    assert str(out.loc[0, "NOM_COM"]).strip() == "Dijon"
    assert str(out.loc[0, "insee_comm"]) == "21231"


def test_enrich_pej_commune_from_faits_coordinates_noop_without_coords(tmp_path: Path) -> None:
    import ofbilan.common.chargeurs_donnees as loaders

    pej = pd.DataFrame({"DC_ID": ["OF001"], "NOM_COM": ["Beaune"]})
    out = loaders.enrich_pej_commune_from_faits_coordinates(pej, tmp_path, log=None)
    assert str(out.loc[0, "NOM_COM"]) == "Beaune"


def test_merge_pej_faits_locations_joins_dossier_to_dc_id(tmp_path: Path) -> None:
    """Jointure PEJ (ODS) ↔ FAITS : DC_ID = dossier, entité SD{dept}, x/y faits."""
    import ofbilan.common.chargeurs_donnees as loaders

    root = tmp_path
    pj = root / "data" / "sources" / "sig" / "points_infractions_pj"
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
    out = loaders.merge_pej_faits_locations(
        pej, root, "departement", "21", log=None
    )
    assert float(out.loc[0, "x_faits"]) == 5.0
    assert float(out.loc[0, "y_faits"]) == 47.0
    assert pd.isna(out.loc[1, "x_faits"])
    assert pd.isna(out.loc[1, "y_faits"])


def test_enrich_pve_positions_from_pnf_commune_centroids_joins_insee(
    monkeypatch, tmp_path: Path
) -> None:
    """PVe : INF-INSEE joint au shapefile centroïdes PNF → x/y WGS84."""
    import ofbilan.common.chargeurs_donnees as loaders

    root = tmp_path
    ref_dir = root / "ref" / "programme" / "sig" / "communes_pnf"
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

    monkeypatch.setattr("ofbilan.common.chargeurs_donnees.gpd.read_file", fake_read_file)

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


def test_date_parsing_dayfirst_in_loaders(monkeypatch, tmp_path: Path) -> None:
    """Vérifie que les dates avec jour en premier (DD/MM/YYYY) et au format ISO (YYYY-MM-DD) sont correctement lues."""
    import ofbilan.common.chargeurs_donnees as loaders

    pej_dir = tmp_path / "data" / "sources"
    pej_dir.mkdir(parents=True)
    (pej_dir / "suivi_procedure_enq_judiciaire_20260423.ods").write_bytes(b"")
    (pej_dir / "suivi_procedure_administrative_20260206.ods").write_bytes(b"")
    (pej_dir / "Stats_PVe_OFB_20260602.ods").write_bytes(b"")

    df_pej_raw = pd.DataFrame([
        {
            "DC_ID": "OF001",
            "DATE_CONSTATATION": "13/05/2025",
            "DATE_OUVERTURE_PROCEDURE": "14/05/2025",
            "RECAP_DATE_INIT_PJ": "15/05/2025",
            "ENTITE_ORIGINE_PROCEDURE": "SD21"
        },
        {
            "DC_ID": "OF002",
            "DATE_CONSTATATION": "2025-05-13 00:00:00",
            "DATE_OUVERTURE_PROCEDURE": "2025-05-14",
            "RECAP_DATE_INIT_PJ": "2025-05-15",
            "ENTITE_ORIGINE_PROCEDURE": "SD21"
        }
    ])

    df_pa_raw = pd.DataFrame([
        {
            "DATE_CONTROLE": "13/05/2025",
            "DATE_DOSSIER": "14/05/2025"
        },
        {
            "DATE_CONTROLE": "2025-05-13",
            "DATE_DOSSIER": "2025-05-14"
        }
    ])

    df_pve_raw = pd.DataFrame([
        {
            "INF-ID": "1",
            "INF-DATE-MIF": "2024-05-15",
            "INF-DATE-INTG": "15/05/2025",
            "INF-DEPART": "21"
        },
        {
            "INF-ID": "2",
            "INF-DATE-MIF": "15/05/2025",
            "INF-DATE-INTG": "2024-05-15",
            "INF-DEPART": "21"
        }
    ])

    def fake_read_spreadsheet(path, **kwargs):
        name = Path(path).name
        if "enq_judiciaire" in name:
            return df_pej_raw
        elif "administrative" in name:
            return df_pa_raw
        elif "Stats_PVe_OFB" in name:
            return df_pve_raw
        return pd.DataFrame()

    monkeypatch.setattr(loaders, "_read_spreadsheet", fake_read_spreadsheet)

    pej_df = loaders.load_pej(tmp_path, echelle="departement", code="21", date_deb="2025-01-01", date_fin="2025-12-31")
    assert len(pej_df) == 2
    for i in (0, 1):
        assert pej_df.loc[i, "DATE_CONSTATATION"] == pd.Timestamp("2025-05-13")
        assert pej_df.loc[i, "DATE_OUVERTURE_PROCEDURE"] == pd.Timestamp("2025-05-14")
        assert pej_df.loc[i, "RECAP_DATE_INIT_PJ"] == pd.Timestamp("2025-05-15")

    pa_df = loaders.load_pa(tmp_path, echelle="departement", code="21", date_deb="2025-01-01", date_fin="2025-12-31")
    assert len(pa_df) == 2
    for i in (0, 1):
        assert pa_df.loc[i, "DATE_CONTROLE"] == pd.Timestamp("2025-05-13")
        assert pa_df.loc[i, "DATE_DOSSIER"] == pd.Timestamp("2025-05-14")

    pve_df = loaders.load_pve(tmp_path, echelle="departement", code="21", date_deb="2025-01-01", date_fin="2025-12-31")
    assert len(pve_df) == 1
    assert pve_df.iloc[0]["INF-ID"] == "1"


def test_safe_to_datetime_with_nan() -> None:
    """Vérifie que safe_to_datetime gère les valeurs non-string (float, None, NaN) et hors limites sans crash."""
    import ofbilan.common.chargeurs_donnees as loaders
    s = pd.Series(["2025-01-01", "0202-03-15", None, pd.NA, float("nan"), "15/05/0202", "15/05/2025"])
    res = loaders.safe_to_datetime(s)
    assert res.iloc[0] == pd.Timestamp("2025-01-01")
    assert pd.isna(res.iloc[1])
    assert pd.isna(res.iloc[2])
    assert pd.isna(res.iloc[3])
    assert pd.isna(res.iloc[4])
    assert pd.isna(res.iloc[5])
    assert res.iloc[6] == pd.Timestamp("2025-05-15")



