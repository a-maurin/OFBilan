"""Tests d'intégration légers : ordre des titres PDF (TOC) — agrainage et thématiques."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from bilans.common.pdf_presentation_config import (
    normalize_section_id,
    resolve_pdf_presentation_config,
    resolve_sec2_render_order,
    resolve_sections_for_toc,
)
from bilans.common.pdf_toc_inspection import (
    assert_section_headings_order,
    extract_pdf_section_headings,
)
from tests.unit.pdf_toc_test_support import patch_thematique_pdf_charts

FIXTURES_AGRAINAGE = Path(__file__).resolve().parent.parent / "fixtures" / "pdf_toc_agrainage"
FIXTURES_CHASSE = Path(__file__).resolve().parent.parent / "fixtures" / "pdf_toc_chasse"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_fixture_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", encoding="utf-8")


def _load_agrainage_results() -> dict:
    zone_ctrl = _read_fixture_csv(FIXTURES_AGRAINAGE / "zone_ctrl.csv")
    tab_res = _read_fixture_csv(FIXTURES_AGRAINAGE / "tab_resultats_controles.csv")
    synth = _read_fixture_csv(FIXTURES_AGRAINAGE / "synthese_zone.csv")
    ctrl_ut = pd.DataFrame(
        {
            "type_usager": ["Agriculteur", "Agriculteur"],
            "theme": ["Thème A", "Thème B"],
            "nb_controles": [2, 1],
        }
    )
    res_usager = pd.DataFrame(
        {
            "type_usager": ["Agriculteur"],
            "Conforme": [2],
            "Infraction": [0],
            "Manquement": [1],
            "Autre_resultat": [0],
        }
    )
    return {
        "nb_ctrl": 5,
        "nb_pej": 0,
        "nb_pa": 0,
        "nb_pve": 0,
        "ventilation_temporelle_type": "mensuelle",
        "tab_resultats_controles": tab_res,
        "zone_ctrl": zone_ctrl,
        "synthese_zone": synth,
        "ctrl_par_usager_theme": ctrl_ut,
        "res_bilan_par_type_usager": res_usager,
        "_pdf_show_activite_usagers": True,
    }


def test_resolve_sec2_render_order_agrainage_follows_yaml() -> None:
    resolved = resolve_pdf_presentation_config(
        PROJECT_ROOT, scope="thematique", profile_id="agrainage", diffusion="interne"
    )
    section_defs = [
        ("sec21", "2.1. Indicateurs mensuels"),
        ("sec22", "2.2. Résultats des contrôles"),
        ("sec22theme", "2.3. Analyse par zone"),
        ("sec22res", "2.4. Synthèse croisée par zone"),
    ]
    toc = resolve_sections_for_toc(resolved["effective"], section_defs)
    order = resolve_sec2_render_order(toc, include_zone_subsections=True)
    assert order == ["sec21", "sec22", "sec22theme", "sec22res"]


def test_section_id_alias_maps_to_canonical() -> None:
    with pytest.warns(DeprecationWarning, match="sec_usagers"):
        assert normalize_section_id("sec_usagers", emit_alias_warning=True) == "sec4"
    assert normalize_section_id("sec_procedures", emit_alias_warning=False) == "sec3"


def test_agrainage_pdf_section_headings_order(tmp_path: Path, monkeypatch) -> None:
    from bilans.common.bilan_config import BilanConfig
    from bilans.engine import orchestrateur_profils as orch

    profile = {
        "id": "agrainage",
        "label": "Bilan agrainage",
        "filter": {"type": "agrainage"},
        "analyses": {"type_usager": False},
        "sources": {"point_ctrl": True, "pej": True, "pa": True, "pve": True},
        "_export_prefix": "agrainage_test",
    }
    options = {"tub": True, "pnf": False, "cartes": False, "diffusion": "interne"}

    patch_thematique_pdf_charts(monkeypatch, orch)

    out_dir = tmp_path / "out_agrainage"
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = BilanConfig.from_strings("2025-01-01", "2025-12-31", "21", out_dir=out_dir)

    orch._generate_pdf(
        _load_agrainage_results(),
        out_dir,
        profile,
        cfg,
        options,
    )

    pdfs = list(out_dir.glob("agrainage_test_*.pdf"))
    assert len(pdfs) == 1, f"PDF attendu unique, trouvé : {pdfs}"
    pdf_path = pdfs[0]

    headings = extract_pdf_section_headings(pdf_path)
    assert_section_headings_order(
        headings,
        [
            "2.2.",
            "2.3.",
            "2.4.",
            "3. Activité",
            "3.1.",
            "3.2.",
            "4. Procédures",
        ],
    )


def _load_chasse_results() -> dict:
    tab_res = _read_fixture_csv(FIXTURES_CHASSE / "tab_resultats_controles.csv")
    return {
        "nb_ctrl": 5,
        "nb_pej": 0,
        "nb_pa": 0,
        "nb_pve": 1,
        "ventilation_temporelle_type": "mensuelle",
        "tab_resultats_controles": tab_res,
        "_pdf_show_activite_usagers": False,
    }


def test_chasse_section_titles_from_yaml_scope() -> None:
    resolved = resolve_pdf_presentation_config(
        PROJECT_ROOT, scope="thematique", profile_id="chasse", diffusion="interne"
    )
    titles = resolved["effective"].get("sections", {}).get("titles", {})
    assert "3." in str(titles.get("sec4", ""))
    assert "4." in str(titles.get("sec3", ""))


def test_chasse_yaml_usagers_before_procedures() -> None:
    resolved = resolve_pdf_presentation_config(
        PROJECT_ROOT, scope="thematique", profile_id="chasse", diffusion="interne"
    )
    order = resolved["effective"]["sections"]["order"]
    assert order.index("sec4") < order.index("sec3")

    section_defs = [
        ("sec1", "1. Chiffres clés"),
        ("sec4", "3. Activité par type d'usager"),
        ("sec3", "4. Procédures (PEJ, PA, PVe)"),
    ]
    toc = resolve_sections_for_toc(resolved["effective"], section_defs)
    assert [sid for sid, _ in toc if sid in ("sec4", "sec3")] == ["sec4", "sec3"]


def test_chasse_pdf_section_headings_order(tmp_path: Path, monkeypatch) -> None:
    from bilans.common.bilan_config import BilanConfig
    from bilans.engine import orchestrateur_profils as orch

    profile = {
        "id": "chasse",
        "label": "Bilan chasse",
        "filter": {"type": "chasse"},
        "analyses": {"type_usager": False},
        "sources": {"point_ctrl": True, "pej": True, "pa": False, "pve": True},
        "_export_prefix": "chasse_test",
    }
    options = {"tub": False, "pnf": False, "cartes": False, "diffusion": "interne"}

    patch_thematique_pdf_charts(monkeypatch, orch)

    out_dir = tmp_path / "out_chasse"
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = BilanConfig.from_strings("2025-01-01", "2025-12-31", "21", out_dir=out_dir)

    orch._generate_pdf(
        _load_chasse_results(),
        out_dir,
        profile,
        cfg,
        options,
    )

    pdfs = list(out_dir.glob("chasse_test_*.pdf"))
    assert len(pdfs) == 1, f"PDF attendu unique, trouvé : {pdfs}"

    headings = extract_pdf_section_headings(pdfs[0])
    assert_section_headings_order(
        headings,
        [
            "2.2.",
            "3. Activité",
            "4. Procédures",
        ],
    )
