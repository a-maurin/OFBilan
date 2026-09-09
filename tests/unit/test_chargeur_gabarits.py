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

from pathlib import Path
from core.common.chargeur_gabarits import (
    list_gabarits,
    load_gabarit,
    is_gabarit_compatible,
    resolve_gabarit_for_service,
    validate_gabarit_schema,
)


def test_list_gabarits_finds_srp_r27():
    gabarits = list_gabarits()
    ids = [g["gabarit_id"] for g in gabarits]
    assert "srp_r27" in ids

    srp = next(g for g in gabarits if g["gabarit_id"] == "srp_r27")
    assert "Service Régional Police" in srp["label"]
    assert srp["organisation"]["code_region"] == "r27"
    assert srp["organisation"]["service"] == "srp"


def test_load_gabarit_valid_and_missing():
    g_srp = load_gabarit("srp_r27")
    assert g_srp is not None
    assert g_srp["gabarit_id"] == "srp_r27"
    assert isinstance(g_srp["layout"], dict)
    assert g_srp["layout"].get("type") == "grid"

    # Inexistant -> None avec log warning gracieux
    g_unknown = load_gabarit("gabarit_inexistant_xyz")
    assert g_unknown is None


def test_is_gabarit_compatible():
    g = {
        "gabarit_id": "test_g",
        "cible": "bilan",
        "profils_compatibles": ["chasse", "global"],
    }
    assert is_gabarit_compatible(g, profile_id="chasse", cible="bilan") is True
    assert is_gabarit_compatible(g, profile_id="agrainage", cible="bilan") is False
    assert is_gabarit_compatible(g, profile_id="chasse", cible="brochure") is False


def test_resolve_gabarit_for_service():
    resolved = resolve_gabarit_for_service(code_region="r27", code_service="srp")
    assert resolved == "srp_r27"

    resolved_none = resolve_gabarit_for_service(code_region="r99", code_service="inconnu")
    assert resolved_none is None


def test_list_gabarits_finds_gabarit_defaut():
    gabarits = list_gabarits()
    ids = [g["gabarit_id"] for g in gabarits]
    assert "gabarit_defaut" in ids
    assert "brochure_defaut" not in ids

    alias_gabarits = list_gabarits(include_aliases=True)
    alias_ids = [g["gabarit_id"] for g in alias_gabarits]
    assert "brochure_defaut" in alias_ids

    g_defaut = load_gabarit("gabarit_defaut")
    assert g_defaut is not None
    assert g_defaut["gabarit_id"] == "gabarit_defaut"
    assert isinstance(g_defaut["layout"], dict)
    assert g_defaut["layout"].get("type") == "grid"

    # Vérification de l'alias de rétrocompatibilité
    g_alias = load_gabarit("brochure_defaut")
    assert g_alias is not None
    assert g_alias["gabarit_id"] == "gabarit_defaut"


def test_validate_gabarit_schema_valid_and_invalid():
    # Valide
    valid_data = {
        "gabarit_id": "test_g",
        "layout": {
            "type": "grid",
            "pages": [
                {
                    "page_number": 1,
                    "rows": [
                        {
                            "columns": [
                                {
                                    "width": "100%",
                                    "widget": {"type": "map"},
                                }
                            ]
                        }
                    ],
                }
            ],
        },
    }
    ok, errors = validate_gabarit_schema(valid_data)
    assert ok is True
    assert len(errors) == 0

    # Invalide : widget type inconnu
    invalid_data = {
        "gabarit_id": "test_bad",
        "layout": {
            "type": "grid",
            "pages": [
                {
                    "page_number": 1,
                    "rows": [
                        {
                            "columns": [
                                {
                                    "width": "100%",
                                    "widget": {"type": "type_widget_inconnu"},
                                }
                            ]
                        }
                    ],
                }
            ],
        },
    }
    ok_bad, errors_bad = validate_gabarit_schema(invalid_data)
    assert ok_bad is False
    assert len(errors_bad) > 0
    assert "non reconnu" in errors_bad[0]


def test_user_gabarit_lifecycle(tmp_path, monkeypatch):
    from core.common.chargeur_gabarits import (
        is_system_gabarit,
        save_user_gabarit,
        delete_user_gabarit,
        import_gabarit_content,
        get_user_gabarits_dir,
    )

    # Mock user directory to temporary directory for isolated test
    monkeypatch.setattr("core.common.chargeur_gabarits.get_user_gabarits_dir", lambda: tmp_path)

    # 1. Vérifier qu'un gabarit système est reconnu en tant que tel et ne peut pas être supprimé
    assert is_system_gabarit("gabarit_defaut") is True
    ok_del_sys, msg_del_sys = delete_user_gabarit("gabarit_defaut")
    assert ok_del_sys is False
    assert "lecture seule" in msg_del_sys.lower() or "système" in msg_del_sys.lower()

    # 2. Sauvegarde d'un gabarit utilisateur
    sample_gabarit = {
        "gabarit_id": "mon_gabarit_test",
        "label": "Gabarit Test Unitaire",
        "description": "Gabarit temporaire de test",
        "cible": "brochure",
        "layout": {
            "type": "grid",
            "pages": [
                {
                    "page_number": 1,
                    "rows": [
                        {
                            "columns": [
                                {"width": "100%", "widget": {"type": "stat_kpi_grid"}}
                            ]
                        }
                    ]
                }
            ]
        }
    }

    ok_save, gid, errors_save = save_user_gabarit(sample_gabarit)
    assert ok_save is True
    assert gid == "mon_gabarit_test"
    assert (tmp_path / "mon_gabarit_test.yaml").exists()

    # 3. Importation via chaîne YAML
    yaml_str = """
gabarit_id: gabarit_importe
label: Gabarit Importé Test
cible: les_deux
layout:
  type: grid
  pages:
    - page_number: 1
      rows:
        - columns:
            - width: "100%"
              widget:
                type: map
"""
    ok_imp, imp_id, errors_imp = import_gabarit_content(yaml_str)
    assert ok_imp is True
    assert imp_id == "gabarit_importe"
    assert (tmp_path / "gabarit_importe.yaml").exists()

    # 4. Suppression du gabarit utilisateur créé
    ok_del, msg_del = delete_user_gabarit("mon_gabarit_test")
    assert ok_del is True
    assert not (tmp_path / "mon_gabarit_test.yaml").exists()

    # 5. Tentative de sauvegarde d'un gabarit système -> création automatique sous *_custom
    sys_edit_gabarit = dict(sample_gabarit)
    sys_edit_gabarit["gabarit_id"] = "gabarit_defaut"
    ok_sys_save, sys_gid, _ = save_user_gabarit(sys_edit_gabarit)
    assert ok_sys_save is True
    assert sys_gid == "gabarit_defaut_custom"
    assert (tmp_path / "gabarit_defaut_custom.yaml").exists()


def test_resolve_items_masques_carte_fusion():
    from core.common.chargeur_gabarits import resolve_items_masques_carte

    profil_data = {
        "cartographie": {
            "items_masques_defaut": ["masque_profil_1", "masque_commun"],
        }
    }
    gabarit_data = {
        "cartographie": {
            "items_masques": ["masque_gabarit_1", "masque_commun"],
        }
    }

    # Fusion additive sans doublons
    masques = resolve_items_masques_carte(profil_data=profil_data, gabarit_data=gabarit_data, is_brochure=False)
    assert masques == ["masque_profil_1", "masque_commun", "masque_gabarit_1"]


def test_pnf_v2_gabarit_compatibility():
    g_pnf = load_gabarit("pnf_v2")
    assert g_pnf is not None
    assert g_pnf["gabarit_id"] == "pnf_v2"
    assert is_gabarit_compatible(g_pnf, profile_id="pnf_v2", cible="bilan") is True
    assert is_gabarit_compatible(g_pnf, profile_id="pnf", cible="bilan") is True


def test_resolve_items_masques_carte_gabarit_brochure_key_non_brochure_mode():
    from core.common.chargeur_gabarits import resolve_items_masques_carte, load_gabarit

    g_srp = load_gabarit("srp_r27")
    masques = resolve_items_masques_carte(profil_data=None, gabarit_data=g_srp, is_brochure=False)
    assert masques == [
        "titre_principal",
        "sous_titre",
        "bandeau_titre",
        "bandeau_logos_ofb",
        "logo_ofb_bas_droite",
        "bandeau_source",
    ]






