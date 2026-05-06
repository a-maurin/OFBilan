from __future__ import annotations

import sys


def test_bilans_cli_list_themes(monkeypatch, capsys) -> None:
    import bilans.cli as cli

    monkeypatch.setattr(sys, "argv", ["bilans", "--list-themes"])
    monkeypatch.setattr(cli, "_list_themes", lambda: ["demo_a", "demo_b"])
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "1. demo_a" in out
    assert "2. demo_b" in out


def test_bilans_cli_interactive_profile_prompt(monkeypatch) -> None:
    import bilans.cli as cli

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
        dept_code: str,
        *,
        combine: bool = False,
        cli_options: dict | None = None,
    ) -> int:
        captured["args"] = (profils, date_deb, date_fin, dept_code, combine, cli_options)
        return 0

    monkeypatch.setattr("bilans.engine.profiles.resolve_profile_ids", _fake_resolve)
    monkeypatch.setattr("bilans.engine.unified_engine.run_profiles_batch", _fake_run_batch)
    assert cli.main() == 0
    assert captured["args"] == (["chasse"], "2025-01-01", "2025-12-31", "21", False, None)


def test_bilans_cli_rejects_global_with_other_profile(monkeypatch, capsys) -> None:
    import bilans.cli as cli

    monkeypatch.setattr(
        sys,
        "argv",
        ["bilans", "--profil", "global", "--profil", "chasse", "--date-deb", "2025-01-01", "--date-fin", "2025-12-31"],
    )
    monkeypatch.setattr(cli, "_check_deps", lambda: None)
    monkeypatch.setattr("bilans.engine.profiles.resolve_profile_ids", lambda ids: ids)

    assert cli.main() == 1
    err = capsys.readouterr().err
    assert "doit être exécuté seul" in err
