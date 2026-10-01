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
from __future__ import annotations

import sys


def test_bilans_cli_list_themes(monkeypatch, capsys) -> None:
    import core.point_entree_cli as cli

    monkeypatch.setattr(sys, "argv", ["bilans", "--list-themes"])
    monkeypatch.setattr(cli, "_list_themes", lambda: ["demo_a", "demo_b"])
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "1. demo_a" in out
    assert "2. demo_b" in out


def test_bilans_cli_interactive_profile_prompt(monkeypatch) -> None:
    import core.point_entree_cli as cli

    captured: dict[str, object] = {}

    monkeypatch.setattr(sys, "argv", ["bilans", "--date-deb", "2025-01-01", "--date-fin", "2025-12-31"])
    monkeypatch.setattr(cli, "_check_deps", lambda: None)
    monkeypatch.setattr(cli, "_list_themes", lambda: ["global", "chasse"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": "2")

    def _fake_resolve(ids: list[str]) -> list[str]:
        return ["chasse"] if ids == ["2"] else ids

    def _fake_run_batch(
        profils: list[str],
        date_deb: str,
        date_fin: str,
        echelle: str,
        code: str,
        *,
        combine: bool = False,
        cli_options: dict | None = None,
    ) -> int:
        captured["args"] = (profils, date_deb, date_fin, echelle, code, combine, cli_options)
        return 0

    monkeypatch.setattr("core.engine.catalogue_profils.resolve_profile_ids", _fake_resolve)
    monkeypatch.setattr("core.engine.execution_lots_profils.run_profiles_batch", _fake_run_batch)
    assert cli.main() == 0
    assert captured["args"] == (
        ["chasse"],
        "2025-01-01",
        "2025-12-31 23:59:59",
        "departement",
        "21",
        False,
        {},
    )


def test_bilans_cli_delegates_profile_compatibility_to_engine(monkeypatch) -> None:
    import core.point_entree_cli as cli

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        sys,
        "argv",
        ["bilans", "--profil", "global", "--profil", "chasse", "--date-deb", "2025-01-01", "--date-fin", "2025-12-31"],
    )
    monkeypatch.setattr(cli, "_check_deps", lambda: None)
    monkeypatch.setattr("core.engine.catalogue_profils.resolve_profile_ids", lambda ids: ids)
    def _fake_run_batch(*args, **kwargs):
        captured["called"] = True
        return 1
    monkeypatch.setattr("core.engine.execution_lots_profils.run_profiles_batch", _fake_run_batch)

    assert cli.main() == 1
    assert captured.get("called") is True


def test_bilans_cli_type_usager_and_cartes_options(monkeypatch) -> None:
    import core.point_entree_cli as cli

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bilans",
            "--profil",
            "types_usager_cible",
            "--date-deb",
            "2025-01-01",
            "--date-fin",
            "2026-03-31",
            "--dept-code",
            "21",
            "--type-usager",
            "2",
            "--no-cartes",
            "--no-pnf",
        ],
    )
    monkeypatch.setattr(cli, "_check_deps", lambda: None)
    monkeypatch.setattr(
        cli,
        "_load_type_usager_labels",
        lambda: ["Particulier", "Agriculteur et autres acteurs agricoles"],
    )
    monkeypatch.setattr(
        "core.engine.catalogue_profils.resolve_profile_ids",
        lambda ids: ids,
    )

    def _fake_run_batch(
        profils: list[str],
        date_deb: str,
        date_fin: str,
        echelle: str,
        code: str,
        *,
        combine: bool = False,
        cli_options: dict | None = None,
    ) -> int:
        captured["cli_options"] = cli_options
        captured["echelle"] = echelle
        captured["code"] = code
        return 0

    monkeypatch.setattr(
        "core.engine.execution_lots_profils.run_profiles_batch",
        _fake_run_batch,
    )

    assert cli.main() == 0
    opts = captured["cli_options"]
    assert captured["echelle"] == "departement"
    assert captured["code"] == "21"
    assert opts["type_usager_target"] == ["Agriculteur et autres acteurs agricoles"]
    assert opts["cartes"] is False
    assert opts["pnf"] is False


def test_bilans_cli_brochure_option(monkeypatch) -> None:
    import core.point_entree_cli as cli

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bilans",
            "--profil",
            "synthese_activite_PA_PJ",
            "--date-deb",
            "2025-01-01",
            "--date-fin",
            "2025-12-31",
            "--brochure",
        ],
    )
    monkeypatch.setattr(cli, "_check_deps", lambda: None)
    monkeypatch.setattr(
        "core.engine.catalogue_profils.resolve_profile_ids",
        lambda ids: ids,
    )

    def _fake_run_batch(
        _profils: list[str],
        _date_deb: str,
        _date_fin: str,
        _echelle: str,
        _code: str,
        *,
        combine: bool = False,
        cli_options: dict | None = None,
    ) -> int:
        captured["cli_options"] = cli_options
        return 0

    monkeypatch.setattr(
        "core.engine.execution_lots_profils.run_profiles_batch",
        _fake_run_batch,
    )
    assert cli.main() == 0
    assert captured["cli_options"]["brochure"] is True


def test_bilans_cli_no_brochure_option(monkeypatch) -> None:
    import core.point_entree_cli as cli

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bilans",
            "--profil",
            "global",
            "--date-deb",
            "2025-01-01",
            "--date-fin",
            "2025-12-31",
            "--no-brochure",
        ],
    )
    monkeypatch.setattr(cli, "_check_deps", lambda: None)
    monkeypatch.setattr(
        "core.engine.catalogue_profils.resolve_profile_ids",
        lambda ids: ids,
    )

    def _fake_run_batch(
        _profils: list[str],
        _date_deb: str,
        _date_fin: str,
        _echelle: str,
        _code: str,
        *,
        combine: bool = False,
        cli_options: dict | None = None,
    ) -> int:
        captured["cli_options"] = cli_options
        return 0

    monkeypatch.setattr(
        "core.engine.execution_lots_profils.run_profiles_batch",
        _fake_run_batch,
    )
    assert cli.main() == 0
    assert captured["cli_options"]["brochure"] is False


def test_bilans_cli_default_brochure_option(monkeypatch) -> None:
    import core.point_entree_cli as cli

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bilans",
            "--profil",
            "global",
            "--date-deb",
            "2025-01-01",
            "--date-fin",
            "2025-12-31",
        ],
    )
    monkeypatch.setattr(cli, "_check_deps", lambda: None)
    monkeypatch.setattr("core.common.prompt_periode._is_interactive", lambda: False)
    monkeypatch.setattr(
        "core.engine.catalogue_profils.resolve_profile_ids",
        lambda ids: ids,
    )

    def _fake_run_batch(
        _profils: list[str],
        _date_deb: str,
        _date_fin: str,
        _echelle: str,
        _code: str,
        *,
        combine: bool = False,
        cli_options: dict | None = None,
    ) -> int:
        captured["cli_options"] = cli_options
        return 0

    monkeypatch.setattr(
        "core.engine.execution_lots_profils.run_profiles_batch",
        _fake_run_batch,
    )
    assert cli.main() == 0
    assert "brochure" not in (captured["cli_options"] or {})


def test_list_type_usagers(monkeypatch, capsys) -> None:
    import core.point_entree_cli as cli

    monkeypatch.setattr(sys, "argv", ["bilans", "--list-type-usagers"])
    monkeypatch.setattr(
        cli,
        "_load_type_usager_labels",
        lambda: ["Agriculteur et autres acteurs agricoles"],
    )
    assert cli.main() == 0
    assert "1. Agriculteur" in capsys.readouterr().out


def test_bilans_cli_multi_codes(monkeypatch) -> None:
    import core.point_entree_cli as cli

    captured_codes = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bilans",
            "--profil",
            "global",
            "--date-deb",
            "2025-01-01",
            "--date-fin",
            "2025-12-31",
            "--code",
            "21, 25",
        ],
    )
    monkeypatch.setattr(cli, "_check_deps", lambda: None)
    monkeypatch.setattr(
        "core.engine.catalogue_profils.resolve_profile_ids",
        lambda ids: ids,
    )

    def _fake_run_batch(
        profils: list[str],
        date_deb: str,
        date_fin: str,
        echelle: str,
        code: str,
        *,
        combine: bool = False,
        cli_options: dict | None = None,
    ) -> int:
        captured_codes.append(code)
        return 0

    monkeypatch.setattr(
        "core.engine.execution_lots_profils.run_profiles_batch",
        _fake_run_batch,
    )

    assert cli.main() == 0
    assert captured_codes == ["21", "25"]


def test_bilans_cli_multi_codes_shares_options(monkeypatch) -> None:
    import core.point_entree_cli as cli

    captured_opts_list = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bilans",
            "--profil",
            "global",
            "--date-deb",
            "2025-01-01",
            "--date-fin",
            "2025-12-31",
            "--code",
            "21, 25",
        ],
    )
    monkeypatch.setattr(cli, "_check_deps", lambda: None)
    monkeypatch.setattr(
        "core.engine.catalogue_profils.resolve_profile_ids",
        lambda ids: ids,
    )

    def _fake_run_batch(
        profils: list[str],
        date_deb: str,
        date_fin: str,
        echelle: str,
        code: str,
        *,
        combine: bool = False,
        cli_options: dict | None = None,
    ) -> int:
        captured_opts_list.append(cli_options)
        if cli_options is not None:
            cli_options["cartes_selection"] = ["carte_1"]
        return 0

    monkeypatch.setattr(
        "core.engine.execution_lots_profils.run_profiles_batch",
        _fake_run_batch,
    )

    assert cli.main() == 0
    assert len(captured_opts_list) == 2
    assert captured_opts_list[0]["cartes_selection"] == ["carte_1"]
    assert captured_opts_list[1]["cartes_selection"] == ["carte_1"]


def test_bilans_cli_debug_option(monkeypatch) -> None:
    import core.point_entree_cli as cli
    import logging

    captured_level = []
    
    # Mock configure_logging pour intercepter le niveau passé
    def _fake_configure_logging(level):
        captured_level.append(level)
        
    monkeypatch.setattr(cli, "configure_logging", _fake_configure_logging)
    monkeypatch.setattr(sys, "argv", ["bilans", "--list-themes", "--debug"])
    monkeypatch.setattr(cli, "_list_themes", lambda: ["demo_a"])
    
    assert cli.main() == 0
    assert captured_level == [logging.DEBUG]


def test_bilans_cli_pnf_v2_code_unification(monkeypatch) -> None:
    import core.point_entree_cli as cli
    from core.common.utilitaires_metier import resolve_code_subdir_suffix

    captured_runs = []

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bilans",
            "--profil",
            "pnf_v2",
            "--date-deb",
            "2025-01-01",
            "--date-fin",
            "2025-12-31",
            "--echelle",
            "departement",
            "--code",
            "21, 52",
        ],
    )
    monkeypatch.setattr(cli, "_check_deps", lambda: None)
    monkeypatch.setattr("core.engine.catalogue_profils.resolve_profile_ids", lambda ids: ids)

    def _fake_run_batch(profils, date_deb, date_fin, echelle, code, combine=False, cli_options=None):
        captured_runs.append(code)
        return 0

    monkeypatch.setattr("core.engine.execution_lots_profils.run_profiles_batch", _fake_run_batch)

    assert cli.main() == 0
    assert captured_runs == ["21_52"]

    profile = {"restrict_geo": "pnf", "departements": ["21", "52"]}
    assert resolve_code_subdir_suffix(profile, "21, 52") == "21_52"
    assert resolve_code_subdir_suffix(profile, "PNF") == "21_52"
    assert resolve_code_subdir_suffix(profile, "") == "21_52"
    assert resolve_code_subdir_suffix(profile, "21") == "21"


def test_bilans_cli_format_options(monkeypatch) -> None:
    import core.point_entree_cli as cli

    captured: dict[str, object] = {}

    def _fake_run_batch(profils, date_deb, date_fin, echelle, code, combine=False, cli_options=None):
        captured["cli_options"] = cli_options
        return 0

    monkeypatch.setattr(cli, "_check_deps", lambda: None)
    monkeypatch.setattr("core.engine.catalogue_profils.resolve_profile_ids", lambda ids: ids)
    monkeypatch.setattr("core.engine.execution_lots_profils.run_profiles_batch", _fake_run_batch)

    # 1. Test --format brochure
    monkeypatch.setattr(
        sys,
        "argv",
        ["bilans", "--profil", "chasse", "--date-deb", "2025-01-01", "--date-fin", "2025-12-31", "--format", "brochure"],
    )
    assert cli.main() == 0
    assert captured["cli_options"]["format_sortie"] == "brochure"
    assert captured["cli_options"]["brochure"] is True

    # 2. Test --format les_deux
    monkeypatch.setattr(
        sys,
        "argv",
        ["bilans", "--profil", "chasse", "--date-deb", "2025-01-01", "--date-fin", "2025-12-31", "--format", "les_deux"],
    )
    assert cli.main() == 0
    assert captured["cli_options"]["format_sortie"] == "les_deux"
    assert captured["cli_options"]["brochure"] is True

    # 3. Test --format complet
    monkeypatch.setattr(
        sys,
        "argv",
        ["bilans", "--profil", "chasse", "--date-deb", "2025-01-01", "--date-fin", "2025-12-31", "--format", "complet"],
    )
    assert cli.main() == 0
    assert captured["cli_options"]["format_sortie"] == "complet"
    assert captured["cli_options"]["brochure"] is False

    # 4. Test retrocompatibilite --brochure
    monkeypatch.setattr(
        sys,
        "argv",
        ["bilans", "--profil", "chasse", "--date-deb", "2025-01-01", "--date-fin", "2025-12-31", "--brochure"],
    )
    assert cli.main() == 0
    assert captured["cli_options"]["format_sortie"] == "brochure"
    assert captured["cli_options"]["brochure"] is True


