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

#
"""Tests unitaires — pochoir dynamique par département."""
from pathlib import Path

import pytest

from core.cartographie.layer_resolver import resolve_layer_name
from core.cartographie.pochoir_helper import (
    adapt_text_for_department,
    department_bounds,
    get_departements_admin_shp,
    is_map_valid_for_dept,
    load_department_gdf,
    pochoir_layer_name,
    read_map_dept_marker,
    warn_if_unknown_carto_dept,
    write_map_dept_marker,
)
from core.chemins_projet import PROJECT_ROOT

ADMIN_SHP = PROJECT_ROOT / "ref/programme/sig/limites_admin_dep/DEPARTEMENT_ADMIN_Express_200207.shp"


@pytest.fixture(scope="module")
def require_admin_shp():
    if not ADMIN_SHP.exists():
        pytest.skip("Shapefile DEPARTEMENT_ADMIN_Express_200207 absent")


def test_pochoir_layer_name():
    assert pochoir_layer_name("21") == "pochoir_sd21"
    assert pochoir_layer_name("25") == "pochoir_sd25"


def test_get_departements_admin_shp_path():
    assert get_departements_admin_shp().name == "DEPARTEMENT_ADMIN_Express_200207.shp"


def test_load_department_gdf_21(require_admin_shp):
    gdf = load_department_gdf("21", project_root=PROJECT_ROOT)
    assert len(gdf) == 1
    assert gdf.iloc[0]["insee_dep"] == "21"
    assert gdf.geometry.iloc[0] is not None


def test_load_department_gdf_25(require_admin_shp):
    gdf = load_department_gdf("25", project_root=PROJECT_ROOT)
    assert len(gdf) == 1
    assert gdf.iloc[0]["insee_dep"] == "25"


def test_department_bounds_margin(require_admin_shp):
    b21 = department_bounds("21", project_root=PROJECT_ROOT)
    b25 = department_bounds("25", project_root=PROJECT_ROOT)
    assert b21[0] < b21[2] and b21[1] < b21[3]
    assert b25[0] < b25[2] and b25[1] < b25[3]
    assert b21 != b25


def test_adapt_text_for_department():
    text = "Bilan agrainage — Côte-d'Or (SD21)"
    out = adapt_text_for_department(text, "25", "Doubs")
    assert "Doubs" in out
    assert "SD25" in out
    assert "Côte" not in out


def test_resolve_pochoir_prefers_dept_25():
    layers = [
        "emprise_dep",
        "pochoir_sd25",
        "point_ctrl_20260505_wgs84",
    ]
    name, source = resolve_layer_name(
        configured_name="emprise_dep",
        layer_role="pochoir",
        available_names=layers,
        dept_code="25",
    )
    assert name == "pochoir_sd25"
    assert source == "dept"


def test_resolve_pochoir_no_wrong_dept_fallback():
    layers = ["emprise_dep", "point_ctrl_20260505_wgs84"]
    name, source = resolve_layer_name(
        configured_name="emprise_dep",
        layer_role="pochoir",
        available_names=layers,
        dept_code="25",
    )
    assert name is None
    assert source == "missing"


def test_map_without_marker_invalid_for_all(tmp_path, monkeypatch):
    monkeypatch.setattr("core.chemins_projet.get_cartes_dir", lambda: tmp_path)
    png = tmp_path / "carte_global.png"
    png.write_bytes(b"x")
    assert not is_map_valid_for_dept(png, "21")
    assert not is_map_valid_for_dept(png, "25")


def test_map_dept_marker_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("core.chemins_projet.get_cartes_dir", lambda: tmp_path)
    png = tmp_path / "carte_agrainage.png"
    png.write_bytes(b"x")
    write_map_dept_marker(png, "25")
    assert read_map_dept_marker(png) == "25"
    assert is_map_valid_for_dept(png, "25")
    assert not is_map_valid_for_dept(png, "21")


def test_warn_if_unknown_carto_dept(require_admin_shp, caplog):
    import logging

    logging.getLogger("core").propagate = True
    with caplog.at_level(logging.WARNING, logger="core.cartographie.pochoir_helper"):
        assert warn_if_unknown_carto_dept("25", project_root=PROJECT_ROOT)
        assert not warn_if_unknown_carto_dept("999", project_root=PROJECT_ROOT)
    assert any("999" in r.getMessage() for r in caplog.records)


def test_load_department_gdf_region_dissolve_false(require_admin_shp):
    gdf = load_department_gdf("r27", project_root=PROJECT_ROOT, dissolve=False)
    assert len(gdf) > 1
    assert all(gdf["insee_reg"] == "27")


def test_write_pochoir_gpkg_strips_fid(tmp_path, monkeypatch):
    import geopandas as gpd
    from shapely.geometry import Polygon
    from core.cartographie.pochoir_helper import write_pochoir_gpkg

    # Mock load_pochoir_gdf to return a GeoDataFrame with 'fid' column
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    mock_gdf = gpd.GeoDataFrame(
        [{"fid": 123, "name": "test_zone", "geometry": poly}],
        crs="EPSG:2154",
    )
    monkeypatch.setattr(
        "core.cartographie.pochoir_helper.load_pochoir_gdf",
        lambda *args, **kwargs: mock_gdf.copy(),
    )

    out_gpkg = tmp_path / "pochoir_test.gpkg"
    write_pochoir_gpkg("21", out_gpkg, pochoir_id="zone_a_risque")
    assert out_gpkg.exists()

    loaded = gpd.read_file(out_gpkg)
    assert "name" in loaded.columns

