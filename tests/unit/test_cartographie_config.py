"""Résolution catalogue / sélection cartes (profil global)."""

from __future__ import annotations

from pathlib import Path

from bilans.common.cartographie_config import (
    collect_bilan_carto_override,
    default_cartes_selection,
    expected_map_filenames_for_selection,
    parse_cartography_catalog,
    resolve_cartes_selection,
    resolve_map_profiles_for_batch,
    resolve_qgis_profile_id,
    resolve_qgis_profile_ids,
    resolve_selected_map_paths,
)


def _global_profile() -> dict:
    return {
        "id": "global",
        "options": {
            "cartes": {"default": True},
            "cartes_selection": {
                "type": "multi_choice",
                "default": ["global", "global_usagers", "procedures_pve", "global_domaines"],
            },
        },
        "cartographie": {
            "catalog": [
                {"id": "global", "label": "Contrôles", "fichier": "carte_global.png"},
                {"id": "global_usagers", "label": "Types d'usagers", "fichier": "carte_global_usagers.png"},
                {"id": "procedures_pve", "label": "Procédures", "fichier": "carte_procedures_pve.png"},
                {"id": "global_domaines", "label": "Domaines", "fichier": "carte_global_domaines.png"},
            ],
        },
    }


def test_parse_catalog_global() -> None:
    catalog = parse_cartography_catalog(_global_profile())
    assert [e["id"] for e in catalog] == [
        "global",
        "global_usagers",
        "procedures_pve",
        "global_domaines",
    ]


def test_default_selection_all_four() -> None:
    assert default_cartes_selection(_global_profile()) == [
        "global",
        "global_usagers",
        "procedures_pve",
        "global_domaines",
    ]


def test_cli_carte_subset() -> None:
    profile = _global_profile()
    selected = resolve_cartes_selection(
        profile,
        {"cartes_profil": ["global", "procedures_pve"]},
    )
    assert selected == ["global", "procedures_pve"]


def test_cli_carte_all() -> None:
    profile = _global_profile()
    selected = resolve_cartes_selection(profile, {"cartes_profil": ["all"]})
    assert len(selected) == 4


def test_resolve_selected_map_paths_order(tmp_path: Path, monkeypatch) -> None:
    cartes = tmp_path / "cartes"
    cartes.mkdir()
    (cartes / "carte_global.png").write_bytes(b"a")
    (cartes / "carte_procedures_pve.png").write_bytes(b"b")
    monkeypatch.setattr("bilans.common.cartographie_config.get_cartes_dir", lambda: cartes)

    paths, captions = resolve_selected_map_paths(
        _global_profile(),
        ["procedures_pve", "global"],
    )
    assert [p.name for p in paths] == ["carte_global.png", "carte_procedures_pve.png"]
    assert captions == ["Contrôles", "Procédures"]


def test_resolve_selected_map_paths_rejects_wrong_dept(tmp_path: Path, monkeypatch, caplog) -> None:
    import logging

    from bilans.cartographie.pochoir_helper import write_map_dept_marker

    cartes = tmp_path / "cartes"
    cartes.mkdir()
    png = cartes / "carte_global.png"
    png.write_bytes(b"a")
    write_map_dept_marker(png, "21")
    monkeypatch.setattr("bilans.common.cartographie_config.get_cartes_dir", lambda: cartes)

    with caplog.at_level(logging.WARNING):
        paths, captions = resolve_selected_map_paths(
            _global_profile(),
            ["global"],
            carto_dept="89",
        )
    assert paths == []
    assert captions == []
    assert any("ignorée" in r.message and "89" in r.message for r in caplog.records)


def test_resolve_selected_map_paths_accepts_matching_dept(tmp_path: Path, monkeypatch) -> None:
    from bilans.cartographie.pochoir_helper import write_map_dept_marker

    cartes = tmp_path / "cartes"
    cartes.mkdir()
    png = cartes / "carte_global.png"
    png.write_bytes(b"a")
    write_map_dept_marker(png, "89")
    monkeypatch.setattr("bilans.common.cartographie_config.get_cartes_dir", lambda: cartes)

    paths, _ = resolve_selected_map_paths(
        _global_profile(),
        ["global"],
        carto_dept="89",
    )
    assert len(paths) == 1
    assert paths[0].name == "carte_global.png"


def test_expected_filenames_for_selection() -> None:
    names = expected_map_filenames_for_selection(
        _global_profile(),
        ["global_domaines", "global"],
    )
    assert names == ["carte_global.png", "carte_global_domaines.png"]


def test_map_profiles_for_batch_respects_cli() -> None:
    ids = resolve_map_profiles_for_batch(
        _global_profile(),
        "global",
        {"cartes": True, "cartes_profil": ["global_usagers"]},
    )
    assert ids == ["global_usagers"]


def test_thematique_ref_resolves_profil_id() -> None:
    profile = {
        "id": "faune_sauvage",
        "filter": {"type": "keywords", "keywords": ["faune sauvage"]},
        "options": {"cartes": {"default": True}},
    }
    ids = resolve_qgis_profile_ids(profile, "faune_sauvage", {"cartes": True})
    assert ids == ["faune_sauvage"]


def test_dedie_types_usager_alias() -> None:
    profile = {
        "id": "types_usager",
        "filter": {"type": "all"},
        "cartographie": {"mode": "dedie", "profil_qgis": "global_usagers"},
        "options": {"cartes": {"default": True}},
    }
    assert resolve_qgis_profile_id(profile, "types_usager") == "global_usagers"


def test_manuel_types_usager_cible_no_qgis() -> None:
    profile = {
        "id": "types_usager_cible",
        "cartographie": {"mode": "manuel"},
        "options": {"cartes": {"default": True}},
    }
    assert resolve_qgis_profile_ids(profile, "types_usager_cible", {"cartes": True}) == []


def test_synthese_two_map_profiles() -> None:
    profile = {
        "id": "synthese_activite_PA_PJ",
        "pipeline": "global",
        "filter": {"type": "all"},
        "cartographie": {
            "mode": "synthese",
            "map_profiles": ["synthese_activite_PA_PJ", "synthese_activite_PA_PJ_2"],
        },
        "options": {"cartes": {"default": True}},
    }
    ids = resolve_qgis_profile_ids(profile, "synthese_activite_PA_PJ", {"cartes": True})
    assert ids == ["synthese_activite_PA_PJ", "synthese_activite_PA_PJ_2"]


def test_collect_bilan_carto_override_keywords() -> None:
    profile = {
        "filter": {"keywords": ["pollution", "urbaine"], "columns": ["theme", "nom_dossie"]},
    }
    override = collect_bilan_carto_override(profile)
    assert override["keywords"] == ["pollution", "urbaine"]
    assert "theme" in override["keyword_columns"]
