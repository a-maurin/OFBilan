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

from pathlib import Path

import pytest


def test_load_profile_config_reads_config_profiles_dir(tmp_path: Path) -> None:
    import core.engine.orchestrateur_profils as engine

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
    import core.engine.orchestrateur_profils as engine

    called: dict[str, object] = {}

    def _fake_run_global_profile_via_yaml(
        profile: dict, date_deb: str, date_fin: str, echelle: str, code: str, options: dict
    ) -> int:
        called["args"] = (
            profile.get("id"),
            date_deb,
            date_fin,
            echelle,
            code,
            options.get("chart_preset"),
        )
        return 0

    monkeypatch.setattr(engine, "_run_global_profile_via_yaml", _fake_run_global_profile_via_yaml)
    ret = engine.run_engine(
        "global", "2025-01-01", "2025-12-31", "departement", "21", options={"chart_preset": "compact"}
    )
    assert ret == 0
    assert called.get("args") == ("global", "2025-01-01", "2025-12-31", "departement", "21", "compact")


def test_load_profile_config_does_not_fallback_to_ref(tmp_path: Path) -> None:
    import core.engine.orchestrateur_profils as engine

    legacy_dir = tmp_path / "ref" / "profils_bilan"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "legacy_only.yaml").write_text("id: legacy_only\nlabel: Legacy\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        engine.load_profile_config(tmp_path, "legacy_only")


def test_run_profiles_batch_combine_uses_data_out_dir(tmp_path: Path, monkeypatch) -> None:
    import core.common.carte_helper as carte_helper
    import core.engine.execution_lots_profils as runner

    calls: list[str] = []

    def _fake_run_profile(
        profil_id: str, date_deb: str, date_fin: str, echelle: str, code: str, options: dict | None = None
    ) -> int:
        calls.append(profil_id)
        out_dir = tmp_path / "data" / "out" / f"bilan_{profil_id}_{code}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{profil_id}.pdf").write_text("pdf", encoding="utf-8")
        return 0

    monkeypatch.setattr(runner, "run_profile", _fake_run_profile)
    monkeypatch.setattr(carte_helper, "ensure_maps_for_profiles", lambda *a, **k: None)
    monkeypatch.setattr(
        "core.engine.execution_lots_profils.get_out_dir", lambda subdir: tmp_path / "data" / "out" / subdir
    )
    revealed: list[object] = []
    monkeypatch.setattr(
        "core.engine.execution_lots_profils.reveal_path_in_file_manager",
        lambda p: revealed.append(p),
    )

    ret = runner.run_profiles_batch(
        profils=["chasse", "agrainage"],
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        echelle="departement",
        code="21",
        combine=True,
        cli_options={},
    )

    out_dir = tmp_path / "data" / "out" / "bilan_combine_chasse_agrainage"
    assert ret == 0
    assert calls == ["chasse", "agrainage"]
    assert out_dir.exists()
    assert (out_dir / "README.txt").exists()
    assert len(revealed) == 1
    assert revealed[0] == (tmp_path / "data" / "out" / "bilan_agrainage_21" / "agrainage.pdf").resolve()


def test_run_profiles_batch_sequential_reveals_last_output(tmp_path: Path, monkeypatch) -> None:
    import core.common.carte_helper as carte_helper
    import core.engine.execution_lots_profils as runner

    def _fake_run_profile(
        profil_id: str, date_deb: str, date_fin: str, echelle: str, code: str, options: dict | None = None
    ) -> int:
        out_dir = tmp_path / "data" / "out" / f"bilan_{profil_id}_{code}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{profil_id}.pdf").write_text("pdf", encoding="utf-8")
        return 0

    monkeypatch.setattr(runner, "run_profile", _fake_run_profile)
    monkeypatch.setattr(carte_helper, "ensure_maps_for_profiles", lambda *a, **k: None)
    monkeypatch.setattr(
        "core.engine.execution_lots_profils.get_out_dir", lambda subdir: tmp_path / "data" / "out" / subdir
    )
    revealed: list[object] = []
    monkeypatch.setattr(
        "core.engine.execution_lots_profils.reveal_path_in_file_manager",
        lambda p: revealed.append(p),
    )

    ret = runner.run_profiles_batch(
        profils=["chasse", "agrainage"],
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        echelle="departement",
        code="21",
        combine=False,
        cli_options={},
    )

    assert ret == 0
    assert revealed == [(tmp_path / "data" / "out" / "bilan_agrainage_21" / "agrainage.pdf").resolve()]


def test_run_profiles_batch_rejects_global_mixed_with_other_profile() -> None:
    import core.engine.execution_lots_profils as eng

    ret = eng.run_profiles_batch(
        profils=["global", "chasse"],
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        echelle="departement",
        code="21",
        combine=False,
        cli_options={},
    )
    assert ret == 1


def test_run_profiles_batch_opens_all_generated_pdfs_for_last_profile(
    tmp_path: Path, monkeypatch
) -> None:
    import core.common.carte_helper as carte_helper
    import core.engine.execution_lots_profils as runner

    def _fake_run_profile(
        profil_id: str, date_deb: str, date_fin: str, echelle: str, code: str, options: dict | None = None
    ) -> int:
        out_dir = tmp_path / "data" / "out" / f"bilan_{profil_id}_{code}"
        out_dir.mkdir(parents=True, exist_ok=True)
        if profil_id == "synthese_activite_PA_PJ":
            (out_dir / "synthese_detail.pdf").write_text("pdf", encoding="utf-8")
            (out_dir / "synthese_brochure.pdf").write_text("pdf", encoding="utf-8")
        return 0

    monkeypatch.setattr(runner, "run_profile", _fake_run_profile)
    monkeypatch.setattr(carte_helper, "ensure_maps_for_profiles", lambda *a, **k: None)
    monkeypatch.setattr(
        "core.engine.execution_lots_profils.get_out_dir", lambda subdir: tmp_path / "data" / "out" / subdir
    )
    revealed: list[Path] = []
    monkeypatch.setattr(
        "core.engine.execution_lots_profils.reveal_path_in_file_manager",
        lambda p: revealed.append(Path(p)),
    )

    ret = runner.run_profiles_batch(
        profils=["synthese_activite_PA_PJ"],
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        echelle="departement",
        code="21",
        combine=False,
        cli_options={},
    )

    assert ret == 0
    assert revealed == [
        (tmp_path / "data" / "out" / "bilan_synthese_activite_PA_PJ_21" / "synthese_brochure.pdf").resolve(),
        (tmp_path / "data" / "out" / "bilan_synthese_activite_PA_PJ_21" / "synthese_detail.pdf").resolve(),
    ]


def test_load_profile_config_normalizes_sources(tmp_path: Path) -> None:
    from core.engine.orchestration.loader import load_profile_config

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
    (profils_dir / "test_sources.yaml").write_text(
        "id: test_sources\nlabel: Test\nfilter:\n  type: custom\n",
        encoding="utf-8",
    )
    cfg = load_profile_config(tmp_path, "test_sources")
    assert "sources" in cfg
    assert cfg["sources"]["point_ctrl"] is True
    assert cfg["sources"]["pej"] is True
    assert cfg["sources"]["pa"] is True
    assert cfg["sources"]["pve"] is True


def test_tub_profile_has_sources() -> None:
    from core.chemins_projet import PROJECT_ROOT
    from core.engine.orchestration.loader import load_profile_config

    cfg = load_profile_config(PROJECT_ROOT, "tub")
    assert "sources" in cfg
    assert isinstance(cfg["sources"], dict)
    assert cfg["sources"]["point_ctrl"] is True
    assert cfg["sources"]["pej"] is True

