from __future__ import annotations

import sys


def test_bilans_cli_list_themes(monkeypatch, capsys) -> None:
    import ofbilan.point_entree_cli as cli

    monkeypatch.setattr(sys, "argv", ["bilans", "--list-themes"])
    monkeypatch.setattr(cli, "_list_themes", lambda: ["demo_a", "demo_b"])
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "1. demo_a" in out
    assert "2. demo_b" in out


def test_bilans_cli_interactive_profile_prompt(monkeypatch) -> None:
    import ofbilan.point_entree_cli as cli

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

    monkeypatch.setattr("ofbilan.engine.catalogue_profils.resolve_profile_ids", _fake_resolve)
    monkeypatch.setattr("ofbilan.engine.execution_lots_profils.run_profiles_batch", _fake_run_batch)
    assert cli.main() == 0
    assert captured["args"] == (
        ["chasse"],
        "2025-01-01",
        "2025-12-31 23:59:59",
        "departement",
        "21",
        False,
        None,
    )


def test_bilans_cli_delegates_profile_compatibility_to_engine(monkeypatch) -> None:
    import ofbilan.point_entree_cli as cli

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        sys,
        "argv",
        ["bilans", "--profil", "global", "--profil", "chasse", "--date-deb", "2025-01-01", "--date-fin", "2025-12-31"],
    )
    monkeypatch.setattr(cli, "_check_deps", lambda: None)
    monkeypatch.setattr("ofbilan.engine.catalogue_profils.resolve_profile_ids", lambda ids: ids)
    def _fake_run_batch(*args, **kwargs):
        captured["called"] = True
        return 1
    monkeypatch.setattr("ofbilan.engine.execution_lots_profils.run_profiles_batch", _fake_run_batch)

    assert cli.main() == 1
    assert captured.get("called") is True


def test_bilans_cli_type_usager_and_cartes_options(monkeypatch) -> None:
    import ofbilan.point_entree_cli as cli

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
        "ofbilan.engine.catalogue_profils.resolve_profile_ids",
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
        "ofbilan.engine.execution_lots_profils.run_profiles_batch",
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
    import ofbilan.point_entree_cli as cli

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
        "ofbilan.engine.catalogue_profils.resolve_profile_ids",
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
        "ofbilan.engine.execution_lots_profils.run_profiles_batch",
        _fake_run_batch,
    )
    assert cli.main() == 0
    assert captured["cli_options"]["brochure"] is True


def test_list_type_usagers(monkeypatch, capsys) -> None:
    import ofbilan.point_entree_cli as cli

    monkeypatch.setattr(sys, "argv", ["bilans", "--list-type-usagers"])
    monkeypatch.setattr(
        cli,
        "_load_type_usager_labels",
        lambda: ["Agriculteur et autres acteurs agricoles"],
    )
    assert cli.main() == 0
    assert "1. Agriculteur" in capsys.readouterr().out
