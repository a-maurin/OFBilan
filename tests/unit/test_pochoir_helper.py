"""Tests unitaires — pochoir dynamique par département."""
from pathlib import Path

import pytest

from bilans.cartographie.layer_resolver import resolve_layer_name
from bilans.cartographie.pochoir_helper import (
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
from bilans.chemins_projet import PROJECT_ROOT

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
        "pochoir_sd21",
        "pochoir_sd25",
        "point_ctrl_20260505_wgs84",
    ]
    name, source = resolve_layer_name(
        configured_name="pochoir_sd21",
        layer_role="pochoir",
        available_names=layers,
        dept_code="25",
    )
    assert name == "pochoir_sd25"
    assert source == "dept"


def test_resolve_pochoir_no_wrong_dept_fallback():
    layers = ["pochoir_sd21", "point_ctrl_20260505_wgs84"]
    name, source = resolve_layer_name(
        configured_name="pochoir_sd21",
        layer_role="pochoir",
        available_names=layers,
        dept_code="25",
    )
    assert name is None
    assert source == "missing"


def test_legacy_map_without_marker_valid_for_dept_21_only(tmp_path):
    png = tmp_path / "carte_global.png"
    png.write_bytes(b"x")
    assert is_map_valid_for_dept(png, "21")
    assert not is_map_valid_for_dept(png, "25")


def test_map_dept_marker_roundtrip(tmp_path):
    png = tmp_path / "carte_agrainage.png"
    png.write_bytes(b"x")
    write_map_dept_marker(png, "25")
    assert read_map_dept_marker(png) == "25"
    assert is_map_valid_for_dept(png, "25")
    assert not is_map_valid_for_dept(png, "21")


def test_warn_if_unknown_carto_dept(require_admin_shp, caplog):
    import logging

    with caplog.at_level(logging.WARNING):
        assert warn_if_unknown_carto_dept("25")
        assert not warn_if_unknown_carto_dept("999")
    assert any("999" in r.message for r in caplog.records)
