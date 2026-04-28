from __future__ import annotations


def test_bilans_cli_delegates_to_run_bilan(monkeypatch) -> None:
    import bilans.cli as cli

    monkeypatch.setattr(cli, "_run_bilan_main", lambda: 7)
    assert cli.main() == 7
