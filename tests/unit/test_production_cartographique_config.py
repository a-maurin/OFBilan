"""Config cartographie : departement_code et get_effective_config."""
from __future__ import annotations

from dataclasses import dataclass, field

from ofbilan.cartographie.config_cartes_model import GlobalConfig, PerimetreConfig


def test_global_config_default_departement_code() -> None:
    cfg = GlobalConfig()
    assert cfg.departement_code == "21"


def test_resolve_departement_code_from_attribute() -> None:
    from ofbilan.cartographie.production_cartographique import _resolve_departement_code

    cfg = GlobalConfig(departement_code="89")
    assert _resolve_departement_code(cfg) == "89"


def test_resolve_departement_code_from_perimetre() -> None:
    from ofbilan.cartographie.production_cartographique import _resolve_departement_code

    @dataclass
    class _Cfg:
        perimetre: PerimetreConfig = field(default_factory=lambda: PerimetreConfig(code="89"))

    assert _resolve_departement_code(_Cfg()) == "89"


def test_get_effective_config_with_yaml_profiles() -> None:
    from ofbilan.cartographie.production_cartographique import get_effective_config

    cfg = get_effective_config()
    assert hasattr(cfg, "departement_code")
    assert str(cfg.departement_code).strip() == "21"
    assert cfg.profiles


def test_config_dept_override() -> None:
    from ofbilan.cartographie.production_cartographique import _ConfigExportOverride

    base = GlobalConfig(departement_code="21")
    wrapped = _ConfigExportOverride(base, "89")
    assert wrapped.departement_code == "89"
    assert wrapped.project_qgis_path == base.project_qgis_path


def test_depart_attr_condition_int_compat() -> None:
    from ofbilan.cartographie.production_cartographique import _depart_attr_condition

    assert _depart_attr_condition("num_depart", "89") == '"num_depart" IN (\'89\', 89)'
    assert _depart_attr_condition("num_depart", "2A") == '"num_depart" = \'2A\''


def test_resolve_map_title_custom_title_main() -> None:
    from ofbilan.cartographie.production_cartographique import resolve_map_title
    from ofbilan.cartographie.config_cartes_model import ProfileConfig

    prof = ProfileConfig(
        id="demo",
        title="Bilan demo — Côte-d'Or",
        layout_name="mock",
        output_filename="mock.png",
        title_main="Contrôles — résultats — Côte-d'Or",
        date_deb="2025-01-01",
        date_fin="2025-12-31"
    )
    # Le title_main personnalisé ne doit pas être tronqué par le split
    res = resolve_map_title(prof, "21")
    assert "Contrôles — résultats — Côte-d'Or" in res


