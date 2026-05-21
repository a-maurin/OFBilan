"""Tests du PDF brochure synthese (2 pages)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "data" / "out" / "bilan_synthese_activite_PA_PJ"


def _pdf_page_count(path: Path) -> int:
    data = path.read_bytes()
    return len(re.findall(rb"/Type\s*/Page\b", data))


@pytest.mark.skipif(not OUT_DIR.is_dir(), reason="Données de sortie synthèse absentes")
def test_brochure_pdf_has_two_pages() -> None:
    from bilans.engine.generation_pdf_synthese_brochure import generate_synthese_brochure_pdf_report

    generate_synthese_brochure_pdf_report(
        OUT_DIR,
        date_deb="2025-01-01",
        date_fin="2026-02-05",
        dept_code="21",
        diffusion="externe",
        cartes=False,
    )
    pdf_path = OUT_DIR / "synthese_activite_PA_PJ_brochure_ext.pdf"
    assert pdf_path.is_file()
    assert _pdf_page_count(pdf_path) == 2
