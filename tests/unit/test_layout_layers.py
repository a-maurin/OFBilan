"""Tests — mode layout-driven (découverte couches depuis layout / arborescence QGIS)."""
from pathlib import Path

import pytest

from ofbilan.cartographie.config_cartes_model import LayerSymbologyConfig, ProfileConfig
from ofbilan.cartographie.layout_layers import (
    build_layer_configs_from_names,
    discover_layers_from_qgs_file,
    filter_operational_layer_names,
    infer_filter_type_for_layer,
    is_basemap_layer,
    is_operational_layer,
    parse_qgs_layer_tree_group,
    parse_qgs_layout_layerset,
)

QGZ = Path("ref/programme/sig/bilans_carte.qgz")


@pytest.fixture(scope="module")
def qgs_text() -> str:
    if not QGZ.exists():
        pytest.skip("Projet export QGZ absent")
    import zipfile

    with zipfile.ZipFile(QGZ) as zf:
        return zf.read("bilans_carte.qgs").decode("utf-8", "replace")


def test_is_basemap():
    assert is_basemap_layer("ESRI Topo") is True
    assert is_operational_layer("point_ctrl_20260505_wgs84") is True
    assert is_operational_layer("ESRI Topo") is False
    assert is_operational_layer("point_ctrl_20260505_wgs84 copie") is False


def test_filter_operational_excludes_basemaps():
    names = ["ESRI Topo", "point_ctrl_20260505_wgs84", "pochoir_sd21"]
    assert filter_operational_layer_names(names) == ["point_ctrl_20260505_wgs84", "pochoir_sd21"]


def test_infer_filter_type_agrainage():
    assert infer_filter_type_for_layer("point_ctrl_20260505_wgs84", "agrainage") == "point_ctrl_agrainage"
    assert infer_filter_type_for_layer("point_ctrl_20260505_wgs84", "global") == "point_ctrl_global"
    assert infer_filter_type_for_layer("localisation_infrac_FAITS_20260505", "global") == "pj"


def test_parse_layer_tree_group_agrainage(qgs_text):
    layers = parse_qgs_layer_tree_group(qgs_text, "agrainage")
    assert any("point_ctrl" in n for n in layers)
    assert all(not is_basemap_layer(n) for n in layers)


def test_layout_layerset_empty_for_current_project(qgs_text):
    layers = parse_qgs_layout_layerset(
        qgs_text,
        "Bilan 2025 / 2026 - Agrainage illicite - Côte d'Or",
    )
    assert layers == []


def test_discover_from_qgs_with_group(qgs_text):
    layers = discover_layers_from_qgs_file(
        qgs_text,
        "Bilan – Chasse – SD21",
        layout_layer_group="Contrôles",
    )
    assert any("point_ctrl" in n for n in layers)


def test_build_layer_configs_from_discovered_names():
    prof = ProfileConfig(
        id="agrainage",
        title="test",
        layout_name="layout",
        output_filename="carte.png",
        layers={
            "point_controles": LayerSymbologyConfig(
                layer_name="point_ctrl_old",
                layer_role="point_controles",
                filter_type="point_ctrl_agrainage",
            ),
        },
    )
    configs = build_layer_configs_from_names(
        ["point_ctrl_20260505_wgs84", "pochoir_sd21", "ESRI Topo"],
        prof,
        prof.layers,
    )
    assert "point_ctrl_20260505_wgs84" in configs
    assert configs["point_ctrl_20260505_wgs84"].filter_type == "point_ctrl_agrainage"
    assert "ESRI Topo" not in configs


def test_profile_config_layers_from_layout_default():
    prof = ProfileConfig(
        id="x",
        title="t",
        layout_name="l",
        output_filename="c.png",
        layers_from_layout=True,
    )
    assert prof.layers_from_layout is True
