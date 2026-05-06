from __future__ import annotations

from pathlib import Path

import pytest


def test_load_profile_config_reads_config_profiles_dir(tmp_path: Path) -> None:
    import bilans.engine.orchestrateur_profils as engine

    profils_dir = tmp_path / "config" / "profils_bilan"
    profils_dir.mkdir(parents=True, exist_ok=True)
    (profils_dir / "_defaults.yaml").write_text(
        "\n".join(
            [
                "pipeline: thematic",
                "presentation_scope: thematique",
                "aggregation:",
                "  adapter: run_profile_aggregations",
                "pdf:",
                "  adapter: generate_profile_pdf_report",
            ]
        ),
        encoding="utf-8",
    )
    (profils_dir / "demo.yaml").write_text(
        "\n".join(
            [
                "id: demo",
                "label: Demo Profil",
                "filter:",
                "  type: keywords",
                "  keywords: [chasse, agrainage]",
            ]
        ),
        encoding="utf-8",
    )

    cfg = engine.load_profile_config(tmp_path, "demo")
    assert cfg["id"] == "demo"
    assert cfg["label"] == "Demo Profil"
    assert cfg["filter"]["keywords"] == ["chasse", "agrainage"]


def test_run_engine_accepts_global_profile_via_yaml(monkeypatch) -> None:
    import bilans.engine.orchestrateur_profils as engine

    called: dict[str, object] = {}

    def _fake_run_global_profile_via_yaml(
        profile: dict, date_deb: str, date_fin: str, dept_code: str, options: dict
    ) -> int:
        called["args"] = (
            profile.get("id"),
            date_deb,
            date_fin,
            dept_code,
            options.get("chart_preset"),
        )
        return 0

    monkeypatch.setattr(engine, "_run_global_profile_via_yaml", _fake_run_global_profile_via_yaml)
    ret = engine.run_engine("global", "2025-01-01", "2025-12-31", "21", options={"chart_preset": "compact"})
    assert ret == 0
    assert called.get("args") == ("global", "2025-01-01", "2025-12-31", "21", "compact")


def test_load_profile_config_does_not_fallback_to_ref(tmp_path: Path) -> None:
    import bilans.engine.orchestrateur_profils as engine

    legacy_dir = tmp_path / "ref" / "profils_bilan"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "legacy_only.yaml").write_text("id: legacy_only\nlabel: Legacy\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        engine.load_profile_config(tmp_path, "legacy_only")


def test_run_profiles_batch_combine_uses_data_out_dir(tmp_path: Path, monkeypatch) -> None:
    import bilans.engine.orchestrateur_profils as engine
    import bilans.common.carte_helper as carte_helper
    import bilans.engine.execution_lots_profils as runner

    calls: list[str] = []

    def _fake_run_engine(
        profil_id: str, date_deb: str, date_fin: str, dept_code: str, options: dict | None = None
    ) -> int:
        calls.append(profil_id)
        return 0

    monkeypatch.setattr(engine, "run_engine", _fake_run_engine)
    monkeypatch.setattr(carte_helper, "ensure_maps", lambda *a, **k: None)
    monkeypatch.setattr(carte_helper, "ensure_maps_for_profiles", lambda *a, **k: None)
    monkeypatch.setattr(
        "bilans.engine.execution_lots_profils.get_out_dir", lambda subdir: tmp_path / "data" / "out" / subdir
    )

    ret = runner.run_profiles_batch(
        profils=["chasse", "agrainage"],
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        dept_code="21",
        combine=True,
        cli_options={},
    )

    out_dir = tmp_path / "data" / "out" / "bilan_combine_chasse_agrainage"
    assert ret == 0
    assert calls == ["chasse", "agrainage"]
    assert out_dir.exists()
    assert (out_dir / "README.txt").exists()


def test_run_profiles_batch_rejects_global_mixed_with_other_profile() -> None:
    import bilans.engine.execution_lots_profils as eng

    ret = eng.run_profiles_batch(
        profils=["global", "chasse"],
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        dept_code="21",
        combine=False,
        cli_options={},
    )
    assert ret == 1

