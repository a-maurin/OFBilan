"""Non-régression pagination: titre lié au début de contenu."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.platypus import KeepTogether

from bilans.common.pdf_report_builder import PDFReportBuilder


def _make_png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (120, 80), color=(230, 240, 250)).save(path)
    return path


def _has_image(flowables: list) -> bool:
    for f in flowables:
        if type(f).__name__ == "Image":
            return True
        if type(f).__name__ == "KeepTogether":
            if _has_image(getattr(f, "_content", [])):
                return True
    return False


def test_section_heading_stays_bound_to_first_content_item_for_image(tmp_path: Path) -> None:
    pdf_path = tmp_path / "out.pdf"
    img_path = _make_png(tmp_path / "img.png")
    builder = PDFReportBuilder(pdf_path=pdf_path, header_title="Test")

    builder.add_section("sec_test", "Section test")
    builder.add_image(img_path, width_ratio=0.4)

    assert builder.story, "Story vide inattendue."
    first = builder.story[0]
    assert isinstance(first, KeepTogether) or getattr(first, "keepWithNext", 0) == 1, (
        "Le titre doit être lié (KeepTogether ou keepWithNext=1)."
    )


def test_subsection_heading_stays_bound_when_table_and_image_can_split(tmp_path: Path) -> None:
    pdf_path = tmp_path / "out2.pdf"
    img_path = _make_png(tmp_path / "img2.png")
    builder = PDFReportBuilder(
        pdf_path=pdf_path,
        header_title="Test",
        tables_layout={"split_by_row": True},
    )

    builder.add_section("sec_sub", "Sous-section test", level=2)
    builder.add_table_and_image_keep_together(
        [["Col A", "Col B"], ["x", "1"], ["y", "2"]],
        table_caption="Table test",
        image_path=img_path,
        image_width_ratio=0.5,
    )

    assert builder.story, "Story vide inattendue."
    first = builder.story[0]
    assert isinstance(first, KeepTogether) or getattr(first, "keepWithNext", 0) == 1, (
        "Le titre doit être lié (KeepTogether ou keepWithNext=1)."
    )


def test_local_heading_chart_table_keeps_heading_with_first_content(tmp_path: Path) -> None:
    pdf_path = tmp_path / "out3.pdf"
    img_path = _make_png(tmp_path / "img3.png")
    builder = PDFReportBuilder(pdf_path=pdf_path, header_title="Test")
    builder.add_section("sec_usagers", "Section usagers")
    builder.add_heading_chart_table_keep_together(
        heading_text="Résultats des contrôles par type d'usager",
        heading_style="Heading2",
        chart_path=img_path,
        chart_width_ratio=0.5,
        table_rows=[["Type", "Nb"], ["A", "1"], ["B", "2"]],
        table_caption="Résultats des contrôles par type d'usager",
    )

    assert builder.story, "Story vide inattendue."
    first = builder.story[0]
    if isinstance(first, KeepTogether):
        content = getattr(first, "_content", [])
        assert not _has_image(content), "Le KeepTogether lié au titre ne doit plus inclure d'image lourde."
    else:
        assert getattr(first, "keepWithNext", 0) == 1, "Le titre local doit être lié par keepWithNext=1."


def test_local_heading_without_pending_still_keeps_first_content(tmp_path: Path) -> None:
    pdf_path = tmp_path / "out4.pdf"
    img_path = _make_png(tmp_path / "img4.png")
    builder = PDFReportBuilder(pdf_path=pdf_path, header_title="Test")

    builder.add_heading_chart_table_keep_together(
        heading_text="Résultats des contrôles par type d'usager",
        heading_style="Heading2",
        chart_path=img_path,
        chart_width_ratio=0.5,
        table_rows=[["Type", "Nb"], ["A", "1"]],
    )

    assert builder.story, "Story vide inattendue."
    first = builder.story[0]
    if isinstance(first, KeepTogether):
        content = getattr(first, "_content", [])
        assert not _has_image(content), "Le KeepTogether lié au titre ne doit plus inclure d'image lourde."
    else:
        assert getattr(first, "keepWithNext", 0) == 1, "Le titre local doit rester lié par keepWithNext=1."
