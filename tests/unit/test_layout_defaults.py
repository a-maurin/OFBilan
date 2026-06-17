"""Tests chargement layout_defaults.yaml (sans PyQGIS)."""

from pathlib import Path

import pytest

from ofbilan.cartographie.config_cartes_model import ProfileConfig
from ofbilan.cartographie.layout_defaults import (
    LAYOUT_DEFAULTS_YAML,
    load_layout_defaults,
    parse_layout_defaults_dict,
    resolve_template_name,
    resolve_title_ids,
    _match_page_template,
)


@pytest.fixture
def root_config():
    return load_layout_defaults(LAYOUT_DEFAULTS_YAML)


def test_layout_defaults_yaml_exists():
    assert LAYOUT_DEFAULTS_YAML.is_file()


def test_load_global_template(root_config):
    assert root_config.enabled
    assert "global" in root_config.templates
    tpl = root_config.templates["global"]
    assert tpl.page.width_mm == 297.0
    assert tpl.page.height_mm == 210.0
    assert tpl.legend.single is True
    assert tpl.legend.hide_extra is True


def test_global_title_id_mapping(root_config):
    layout_name = "global"
    assert layout_name in root_config.layout_title_ids
    prof = ProfileConfig(
        id="agrainage",
        title="t",
        layout_name=layout_name,
        output_filename="x.png",
    )
    title_id, sub_id = resolve_title_ids(prof, root_config)
    assert title_id == "titre_principal"
    assert sub_id == "sous_titre"


def test_resolve_template_explicit_ref():
    cfg = parse_layout_defaults_dict({"enabled": True, "templates": {"a4_paysage": {}}})
    prof = ProfileConfig(
        id="chasse",
        title="t",
        layout_name="Bilan – Chasse – SD21",
        output_filename="x.png",
        layout_defaults_ref="a4_paysage",
    )
    assert resolve_template_name(prof, cfg) == "a4_paysage"


def test_match_page_template():
    assert _match_page_template(210, 210) == "carre_210"
    assert _match_page_template(297, 210) == "a4_paysage"
    assert _match_page_template(200, 200) is None


def test_parse_minimal_dict():
    cfg = parse_layout_defaults_dict(
        {
            "enabled": False,
            "templates": {
                "custom": {
                    "page": {"width_mm": 100, "height_mm": 100},
                    "legend": {"single": True, "x_mm": 80, "y_mm": 5, "width_mm": 20, "height_mm": 40},
                }
            },
        }
    )
    assert cfg.enabled is False
    assert cfg.templates["custom"].legend.height_mm == 40
