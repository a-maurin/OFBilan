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
