"""Tests du PDF brochure synthese (2 pages)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "data" / "out" / "bilan_synthese_activite_PA_PJ"


def _pdf_page_count(path: Path) -> int:
    data = path.read_bytes()
    return len(re.findall(rb"/Type\s*/Page\b", data))


def _pdf_media_box_pts(path: Path) -> tuple[float, float]:
    data = path.read_bytes()
    matches = re.findall(
        rb"/MediaBox\s*\[\s*0(?:\.0+)?\s+0(?:\.0+)?\s+([\d.]+)\s+([\d.]+)\s*\]",
        data,
    )
    assert matches, "MediaBox introuvable"
    w, h = (float(matches[-1][0]), float(matches[-1][1]))
    return w, h


def _pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


@pytest.mark.skipif(not OUT_DIR.is_dir(), reason="Données de sortie synthèse absentes")
@pytest.mark.parametrize("cartes", [False, True])
def test_brochure_pdf_has_two_pages(cartes: bool) -> None:
    from bilans.engine.generation_pdf_synthese_brochure import generate_synthese_brochure_pdf_report

    generate_synthese_brochure_pdf_report(
        OUT_DIR,
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        dept_code="21",
        diffusion="externe",
        cartes=cartes,
    )
    pdf_path = OUT_DIR / "synthese_activite_PA_PJ_brochure_ext.pdf"
    assert pdf_path.is_file()
    assert _pdf_page_count(pdf_path) == 2, f"attendu 2 pages (cartes={cartes})"
    page_w, page_h = _pdf_media_box_pts(pdf_path)
    assert page_w > page_h, "La brochure doit être en A4 paysage (largeur > hauteur)"


@pytest.mark.skipif(not OUT_DIR.is_dir(), reason="Données de sortie synthèse absentes")
def test_generate_synthese_profile_outputs_detailed_and_brochure_with_same_period() -> None:
    from bilans.engine.generation_pdf_synthese import generate_synthese_pdf_report

    generate_synthese_pdf_report(
        OUT_DIR,
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        dept_code="21",
        diffusion="externe",
        cartes=False,
    )

    detailed_pdf = OUT_DIR / "synthese_activite_PA_PJ_ext.pdf"
    brochure_pdf = OUT_DIR / "synthese_activite_PA_PJ_brochure_ext.pdf"

    assert detailed_pdf.is_file()
    assert brochure_pdf.is_file()

    expected_period = "du 01/01/2025 au 31/12/2025"
    unexpected_period = "du 01/01/2025 au 05/02/2026"

    detailed_text = _pdf_text(detailed_pdf)
    brochure_text = _pdf_text(brochure_pdf)

    assert expected_period in detailed_text
    assert expected_period in brochure_text
    assert unexpected_period not in brochure_text
