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
"""Config cartographie : departement_code et get_effective_config."""
from __future__ import annotations

from dataclasses import dataclass, field

from core.cartographie.config_cartes_model import GlobalConfig, PerimetreConfig


def test_global_config_default_departement_code() -> None:
    cfg = GlobalConfig()
    assert cfg.departement_code == "21"


def test_resolve_departement_code_from_attribute() -> None:
    from core.cartographie.production_cartographique import _resolve_departement_code

    cfg = GlobalConfig(departement_code="89")
    assert _resolve_departement_code(cfg) == "89"


def test_resolve_departement_code_from_perimetre() -> None:
    from core.cartographie.production_cartographique import _resolve_departement_code

    @dataclass
    class _Cfg:
        perimetre: PerimetreConfig = field(default_factory=lambda: PerimetreConfig(code="89"))

    assert _resolve_departement_code(_Cfg()) == "89"


def test_get_effective_config_with_yaml_profiles() -> None:
    from core.cartographie.production_cartographique import get_effective_config

    cfg = get_effective_config()
    assert hasattr(cfg, "departement_code")
    assert str(cfg.departement_code).strip() == "21"
    assert cfg.profiles


def test_config_dept_override() -> None:
    from core.cartographie.production_cartographique import _ConfigExportOverride

    base = GlobalConfig(departement_code="21")
    wrapped = _ConfigExportOverride(base, "89")
    assert wrapped.departement_code == "89"
    assert wrapped.project_qgis_path == base.project_qgis_path


def test_depart_attr_condition_int_compat() -> None:
    from core.cartographie.production_cartographique import _depart_attr_condition

    assert _depart_attr_condition("num_depart", "89") == '"num_depart" IN (\'89\', \'89\' || \'.0\', 89)'
    assert _depart_attr_condition("num_depart", "2A") == '"num_depart" IN (\'2A\', \'2A\' || \'.0\')'


def test_resolve_map_title_custom_title_main() -> None:
    from core.cartographie.production_cartographique import resolve_map_title
    from core.cartographie.config_cartes_model import ProfileConfig

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


def test_deduplicate_legend_data() -> None:
    from core.cartographie.production_cartographique import _deduplicate_legend_data

    raw = [
        {
            "title": "Contrôles (localisations)",
            "items": [
                {"label": "Conforme", "color": "#2ECC71", "shape": "square"},
                {"label": "Infraction", "color": "#E74C3C", "shape": "square"},
            ],
        },
        {
            "title": "Contrôles (localisations)",
            "items": [
                {"label": "Conforme", "color": "#2ECC71", "shape": "square"},
                {"label": "Infraction", "color": "#E74C3C", "shape": "square"},
            ],
        },
    ]

    dedup_std = _deduplicate_legend_data(raw, is_brochure=False)
    assert len(dedup_std) == 1
    assert len(dedup_std[0]["items"]) == 2

    dedup_brochure = _deduplicate_legend_data(raw, is_brochure=True)
    assert len(dedup_brochure) == 1
    assert len(dedup_brochure[0]["items"]) == 2


