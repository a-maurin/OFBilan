"""
PDFReportBuilder : classe commune pour générer des rapports PDF OFB.

Factorisation du code de génération PDF dupliqué dans les scripts
analyse_global.py, analyse_agrainage.py et analyse_chasse.py.
"""
from __future__ import annotations

import tempfile
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image as RLImage,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)
from PIL import Image as PILImage

from scripts.common.ofb_charte import (
    COLOR_GREY,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    FONT_FAMILY,
    IMG_BACKGROUND,
    IMG_FOOTER_DECO,
    IMG_LOGO_BANNER,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    PAGE_H,
    PAGE_W,
    _get_styles,
)
from scripts.common.pdf_utils import key_figures_table, ofb_table, ofb_table_wide

# Largeur relative (sur la zone utile du PDF) pour les graphiques matplotlib
# des bilans thématiques — barres, courbes, etc.
THEMATIC_CHART_WIDTH_RATIO = 0.72
# Camemberts : plus compacts que les barres (équilibre visuel), calibrés pour A4 +
# export matplotlib un peu plus dense (dpi / polices dans chart_pie) afin de rester nets à l’écran.
THEMATIC_PIE_CHART_WIDTH_RATIO = 0.34


class PDFReportBuilder:
    """Builds an OFB-branded PDF report incrementally."""

    def __init__(
        self,
        pdf_path: Path,
        header_title: str,
        footer_line1: str = "Office français de la biodiversité – Direction régionale Bourgogne-Franche-Comté",
        footer_line2: str = "Service départemental de la Côte-d'Or – 57, rue de Mulhouse – 21000 Dijon – www.ofb.gouv.fr",
        title: str = "",
        author: str = "OFB",
    ):
        self.pdf_path = Path(pdf_path)
        self.pdf_path.parent.mkdir(parents=True, exist_ok=True)

        self.header_title = header_title
        self.footer_line1 = footer_line1
        self.footer_line2 = footer_line2

        self.styles = _get_styles()
        self.avail_w = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT

        self._tmp_dir = Path(tempfile.mkdtemp(prefix="bilan_pdf_"))

        content_frame = Frame(
            MARGIN_LEFT,
            MARGIN_BOTTOM,
            PAGE_W - MARGIN_LEFT - MARGIN_RIGHT,
            PAGE_H - MARGIN_TOP - MARGIN_BOTTOM,
            id="content",
        )
        title_frame = Frame(0, 0, PAGE_W, PAGE_H, id="title_full")

        self.doc = BaseDocTemplate(
            str(self.pdf_path),
            pagesize=A4,
            title=title or header_title,
            author=author,
            pageTemplates=[
                PageTemplate(
                    id="TitlePage",
                    frames=[title_frame],
                    onPage=self._title_page_bg,
                ),
                PageTemplate(
                    id="Normal",
                    frames=[content_frame],
                    onPage=self._header_footer,
                ),
            ],
        )

        self.story: list = []
        # Titre de section en attente : gardé avec le prochain bloc (tableau, chiffres clés…)
        # pour éviter un titre seul en bas de page et le tableau en haut de la suivante.
        self._pending_section: Optional[List] = None

    @property
    def tmp_dir(self) -> Path:
        return self._tmp_dir

    # ------------------------------------------------------------------
    # Page backgrounds
    # ------------------------------------------------------------------
    def _title_page_bg(self, canvas, doc):
        canvas.saveState()
        if IMG_BACKGROUND.exists():
            canvas.drawImage(
                str(IMG_BACKGROUND), 0, 0,
                width=PAGE_W, height=PAGE_H * 0.86,
                preserveAspectRatio=False, mask="auto",
            )
        if IMG_LOGO_BANNER.exists():
            canvas.drawImage(
                str(IMG_LOGO_BANNER), 0, PAGE_H * 0.86,
                width=PAGE_W, height=PAGE_H * 0.14,
                preserveAspectRatio=False, mask="auto",
            )
        canvas.restoreState()

    def _header_footer(self, canvas, doc):
        canvas.saveState()
        if IMG_FOOTER_DECO.exists():
            canvas.drawImage(
                str(IMG_FOOTER_DECO),
                PAGE_W - 60 * mm, 0,
                width=60 * mm, height=7 * mm,
                preserveAspectRatio=False, mask="auto",
            )
        canvas.setStrokeColor(rl_colors.HexColor(COLOR_PRIMARY))
        canvas.setLineWidth(2)
        y_header = PAGE_H - 16 * mm
        canvas.line(MARGIN_LEFT, y_header, PAGE_W - MARGIN_RIGHT, y_header)
        canvas.setFont(f"{FONT_FAMILY}-Bold", 8)
        canvas.setFillColor(rl_colors.HexColor(COLOR_PRIMARY))
        canvas.drawString(MARGIN_LEFT, y_header + 3, self.header_title)

        y_foot = 8 * mm
        canvas.setFont(f"{FONT_FAMILY}", 7)
        canvas.setFillColor(rl_colors.HexColor(COLOR_SECONDARY))
        canvas.drawString(MARGIN_LEFT, y_foot + 12, self.footer_line1)
        canvas.drawString(MARGIN_LEFT, y_foot + 3, self.footer_line2)
        canvas.drawRightString(PAGE_W - MARGIN_RIGHT, y_foot + 3, f"{doc.page}")
        canvas.restoreState()

    # ------------------------------------------------------------------
    # Title page
    # ------------------------------------------------------------------
    def add_title_page(
        self,
        title_lines: List[str],
        period_str: str,
        subtitle: str = "",
    ) -> None:
        """Add a title page (uses TitlePage template)."""
        s = self.styles
        self.story.append(Spacer(1, PAGE_H * 0.30))
        for line in title_lines:
            self.story.append(
                Paragraph(
                    f'<font color="{COLOR_PRIMARY}" size="28"><b>{line}</b></font>',
                    s["Title"],
                )
            )
        self.story.append(Spacer(1, 12))
        self.story.append(
            Paragraph(
                f'<font color="{COLOR_SECONDARY}" size="16">{period_str}</font>',
                s["Title"],
            )
        )
        if subtitle:
            self.story.append(Spacer(1, 8))
            self.story.append(
                Paragraph(
                    f'<font color="{COLOR_GREY}" size="12">{subtitle}</font>',
                    s["Title"],
                )
            )
        self.story.append(Spacer(1, PAGE_H * 0.15))
        self.story.append(
            Paragraph(
                f'<font color="white" size="8">{self.footer_line1}<br/>{self.footer_line2}</font>',
                s["BodySmall"],
            )
        )
        self.story.append(NextPageTemplate("Normal"))
        self.story.append(PageBreak())

    # ------------------------------------------------------------------
    # Table of contents
    # ------------------------------------------------------------------
    def add_toc(self, sections: List[Tuple[str, str]]) -> None:
        """Add a table of contents.  sections = [(anchor, title), ...]"""
        s = self.styles
        self.story.append(Paragraph("Sommaire", s["Title"]))
        self.story.append(Spacer(1, 6 * mm))
        for anchor, title in sections:
            self.story.append(
                Paragraph(f'<a href="#{anchor}" color="{COLOR_PRIMARY}">{title}</a>', s["TOCEntry"])
            )
        self.story.append(PageBreak())

    # ------------------------------------------------------------------
    # Section header
    # ------------------------------------------------------------------
    def add_section(
        self,
        anchor: str,
        title: str,
        level: int = 1,
        *,
        compact: bool = False,
    ) -> None:
        if self._pending_section is not None:
            self.story.extend(self._pending_section)
            self._pending_section = None
        heading = {1: "Heading1", 2: "Heading2", 3: "Heading3"}.get(level, "Heading1")
        anchor_para = Paragraph(f'<a name="{anchor}"/>', self.styles["BodyText"])
        heading_style = self.styles[heading]
        if compact:
            heading_style = ParagraphStyle(
                f"{heading}_compact",
                parent=heading_style,
                spaceBefore=max(0, heading_style.spaceBefore - 8 * mm),
            )
        title_para = Paragraph(title, heading_style)
        spacer = Spacer(1, 2 * mm)
        self._pending_section = [anchor_para, title_para, spacer]

    # ------------------------------------------------------------------
    # Key figures
    # ------------------------------------------------------------------
    def add_key_figures(self, figures: List[Tuple[str, str]]) -> None:
        """figures = [(value_str, label_str), ...]"""
        if not figures:
            return
        kf_table = key_figures_table(figures, self.styles)
        spacer = Spacer(1, 6 * mm)
        if self._pending_section is not None:
            self.story.append(KeepTogether(self._pending_section + [kf_table, spacer]))
            self._pending_section = None
        else:
            self.story.append(kf_table)
            self.story.append(spacer)

    def add_key_figures_and_table(
        self,
        figures: List[Tuple[str, str]],
        table_rows: list,
        caption: str = "",
        col_widths: Optional[list] = None,
        col_aligns: Optional[list] = None,
    ) -> None:
        """Bandeau de chiffres clés + tableau dans un même KeepTogether pour éviter un débordement."""
        if not figures:
            return
        kf_table = key_figures_table(figures, self.styles)
        spacer = Spacer(1, 6 * mm)
        block: List = [kf_table, spacer]
        if caption:
            block.append(Paragraph(caption, self.styles["TableCaption"]))
            block.append(Spacer(1, 2 * mm))
        tbl = ofb_table(table_rows, col_widths=col_widths, col_aligns=col_aligns)
        block.append(tbl)
        block.append(Spacer(1, 6 * mm))
        if self._pending_section is not None:
            self.story.append(KeepTogether(self._pending_section + block))
            self._pending_section = None
        else:
            for el in block:
                self.story.append(el)

    def add_key_figures_and_tables(
        self,
        figures: List[Tuple[str, str]],
        tables: List[dict],
        *,
        compact: bool = False,
    ) -> None:
        """Bandeau + plusieurs tableaux dans un même KeepTogether (même page).
        tables = [{"data_rows": ..., "caption": ..., "col_widths": ..., "col_aligns": ...}, ...]
        compact=True : espacements verticaux réduits (ex. section PEJ sur une page).
        """
        if not figures:
            return
        kf_table = key_figures_table(figures, self.styles)
        gap_kf = 3 * mm if compact else 6 * mm
        gap_cap = 1 * mm if compact else 2 * mm
        gap_after_tbl = 2 * mm if compact else 6 * mm
        block: List = [kf_table, Spacer(1, gap_kf)]
        n_tables = len(tables)
        for i, t in enumerate(tables):
            if t.get("caption"):
                block.append(Paragraph(t["caption"], self.styles["TableCaption"]))
                block.append(Spacer(1, gap_cap))
            col_w = t.get("col_widths")
            col_a = t.get("col_aligns")
            tbl = ofb_table(
                t["data_rows"],
                col_widths=col_w,
                col_aligns=col_a,
            )
            block.append(tbl)
            if i < n_tables - 1:
                block.append(Spacer(1, gap_after_tbl))
        if self._pending_section is not None:
            self.story.append(KeepTogether(self._pending_section + block))
            self._pending_section = None
        else:
            for el in block:
                self.story.append(el)

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------
    def add_table(
        self,
        data_rows: list,
        caption: str = "",
        col_widths: Optional[list] = None,
        col_aligns: Optional[list] = None,
        keep_together: bool = False,
        wide_headers: bool = False,
        *,
        header_font_size: float | None = None,
    ) -> None:
        block: List = []
        if caption:
            block.append(Paragraph(caption, self.styles["TableCaption"]))
            block.append(Spacer(1, 2 * mm))
        if wide_headers:
            tbl = ofb_table_wide(
                data_rows,
                col_widths=col_widths,
                col_aligns=col_aligns,
                avail_w=self.avail_w,
            )
        else:
            tbl = ofb_table(
                data_rows,
                col_widths=col_widths,
                col_aligns=col_aligns,
                header_font_size=header_font_size,
            )
        block.append(tbl)
        block.append(Spacer(1, 6 * mm))
        if keep_together:
            self.story.append(KeepTogether(block))
        elif self._pending_section is not None:
            self.story.append(KeepTogether(self._pending_section + block))
            self._pending_section = None
        else:
            for el in block:
                self.story.append(el)

    def add_table_and_image_keep_together(
        self,
        data_rows: list,
        *,
        table_caption: str = "",
        col_widths: Optional[list] = None,
        col_aligns: Optional[list] = None,
        image_path: Optional[Path] = None,
        image_width_ratio: float = THEMATIC_CHART_WIDTH_RATIO,
    ) -> None:
        """
        Titre de section éventuellement en attente + légende de tableau + tableau
        + graphique PNG dans un seul ``KeepTogether`` (ex. section VII PNF).
        """
        block: List = []
        if self._pending_section is not None:
            block.extend(self._pending_section)
            self._pending_section = None
        if table_caption:
            block.append(Paragraph(table_caption, self.styles["TableCaption"]))
            block.append(Spacer(1, 1 * mm))
        block.append(
            ofb_table(data_rows, col_widths=col_widths, col_aligns=col_aligns)
        )
        if image_path is not None and Path(image_path).exists():
            block.append(Spacer(1, 2 * mm))
            w = self.avail_w * image_width_ratio
            try:
                with PILImage.open(str(image_path)) as im:
                    width_px, height_px = im.size
                ratio = (height_px / float(width_px)) if width_px > 0 else 0.45
            except Exception:
                ratio = 0.45
            img = RLImage(str(image_path), width=w, height=w * ratio)
            img.hAlign = "CENTER"
            block.append(img)
        block.append(Spacer(1, 2 * mm))
        self.story.append(KeepTogether(block))

    # ------------------------------------------------------------------
    # Images / Charts
    # ------------------------------------------------------------------
    def add_image(
        self,
        path: Path,
        width_ratio: float = 0.75,
        caption: str = "",
    ) -> None:
        if not Path(path).exists():
            return
        # Largeur maximale disponible pour l'image
        w = self.avail_w * width_ratio

        # Respecter le ratio réel du PNG si possible, pour éviter les effets
        # de graphiques "écrasés" dans le PDF.
        try:
            with PILImage.open(str(path)) as im:
                width_px, height_px = im.size
            if width_px > 0:
                ratio = height_px / float(width_px)
            else:
                ratio = 0.65
        except Exception:
            ratio = 0.65

        img = RLImage(str(path), width=w, height=w * ratio)
        img.hAlign = "CENTER"
        block = [img]
        if caption:
            block.append(Spacer(1, 2 * mm))
            block.append(Paragraph(f"<i>{caption}</i>", self.styles["BodySmall"]))
        block.append(Spacer(1, 4 * mm))
        if self._pending_section is not None:
            self.story.append(KeepTogether(self._pending_section + block))
            self._pending_section = None
        else:
            for el in block:
                self.story.append(el)

    def add_map(self, path: Path, caption: str = "") -> None:
        """Add a map image (full width)."""
        self.add_image(path, width_ratio=1.0, caption=caption)

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------
    def add_paragraph(self, text: str, style: str = "BodyText") -> None:
        para = Paragraph(text, self.styles[style])
        spacer = Spacer(1, 3 * mm)
        if self._pending_section is not None:
            self.story.append(KeepTogether(self._pending_section + [para, spacer]))
            self._pending_section = None
        else:
            self.story.append(para)
            self.story.append(spacer)

    def add_spacer(self, height_mm: float = 6) -> None:
        self.story.append(Spacer(1, height_mm * mm))

    def add_page_break(self) -> None:
        if self._pending_section is not None:
            self.story.extend(self._pending_section)
            self._pending_section = None
        self.story.append(PageBreak())

    # ------------------------------------------------------------------
    # Methodology
    # ------------------------------------------------------------------
    def add_methodology(self, html_text: str) -> None:
        block = [
            Paragraph("Méthodologie", self.styles["Heading2"]),
            Spacer(1, 2 * mm),
            Paragraph(html_text, self.styles["BodyText"]),
            Spacer(1, 6 * mm),
        ]
        if self._pending_section is not None:
            self.story.append(KeepTogether(self._pending_section + block))
            self._pending_section = None
        else:
            for el in block:
                self.story.append(el)

    # ------------------------------------------------------------------
    # Glossary
    # ------------------------------------------------------------------
    def add_glossary(self, rows: List[List[str]]) -> None:
        """rows = [["Terme", "Définition"], ...]  (first row = header)"""
        if not rows:
            return
        block = [
            Paragraph("Glossaire", self.styles["Heading2"]),
            Spacer(1, 2 * mm),
            ofb_table(rows),
            Spacer(1, 6 * mm),
        ]
        if self._pending_section is not None:
            self.story.append(KeepTogether(self._pending_section + block))
            self._pending_section = None
        else:
            for el in block:
                self.story.append(el)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def build(self) -> Path:
        """Build the PDF and clean up the temp directory. Returns pdf_path."""
        if self._pending_section is not None:
            self.story.extend(self._pending_section)
            self._pending_section = None
        try:
            self.doc.build(self.story)
        finally:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
        return self.pdf_path
