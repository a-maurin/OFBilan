"""
PDFReportBuilder : classe commune pour générer des rapports PDF OFB.

Factorisation du code de génération PDF dupliqué dans les scripts
analyse_global.py, analyse_agrainage.py et analyse_chasse.py.
"""
from __future__ import annotations

import tempfile
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any, List, Optional, Tuple

from reportlab.lib import colors as rl_colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
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
    Table,
)
from reportlab.platypus.tableofcontents import TableOfContents
from PIL import Image as PILImage

from bilans.common.ofb_charte import (
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
from bilans.common.pdf_presentation_config import resolve_tables_layout
from bilans.common.pdf_utils import key_figures_table, ofb_table, ofb_table_wide

# Largeur relative (sur la zone utile du PDF) pour les graphiques matplotlib
# des bilans thématiques — barres, courbes, etc.
THEMATIC_CHART_WIDTH_RATIO = 0.72
# Camemberts : plus compacts que les barres (équilibre visuel), calibrés pour A4 +
# export matplotlib un peu plus dense (dpi / polices dans chart_pie) afin de rester nets à l’écran.
THEMATIC_PIE_CHART_WIDTH_RATIO = 0.34

# Marge réservée au titre de section 5 + espacements dans un KeepTogether cartes.
_MAPS_SECTION_RESERVE_PT = 28 * mm
_MAPS_VERTICAL_GAP_PT = 2 * mm
_MAPS_HORIZONTAL_GAP_PT = 4 * mm


def compute_stacked_maps_width(
    avail_w: float,
    frame_height: float,
    aspect_ratios: list[float],
    *,
    width_fraction: float = 0.98,
    vertical_gap_pt: float = _MAPS_VERTICAL_GAP_PT,
    reserve_pt: float = _MAPS_SECTION_RESERVE_PT,
) -> float:
    """Largeur pour empiler des cartes sans dépasser la hauteur utile d'une page."""
    max_w = avail_w * width_fraction
    budget = frame_height - reserve_pt
    total_ratio = sum(max(0.0, r) for r in aspect_ratios)
    if budget <= 0 or total_ratio <= 0:
        return max_w
    gaps = vertical_gap_pt * max(0, len(aspect_ratios) - 1)
    w_fit = (budget - gaps) / total_ratio
    return min(max_w, w_fit)


def compute_side_by_side_maps_width(
    avail_w: float,
    frame_height: float,
    aspect_ratios: list[float],
    *,
    horizontal_gap_pt: float = _MAPS_HORIZONTAL_GAP_PT,
    reserve_pt: float = _MAPS_SECTION_RESERVE_PT,
) -> float:
    """Largeur d'une colonne pour deux cartes côte à côte sur une page."""
    col_w_max = (avail_w - horizontal_gap_pt) / 2.0
    budget = frame_height - reserve_pt
    if not aspect_ratios or budget <= 0:
        return col_w_max
    peak_ratio = max(max(0.0, r) for r in aspect_ratios)
    if peak_ratio <= 0:
        return col_w_max
    w_fit = budget / peak_ratio
    return min(col_w_max, w_fit)


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
        *,
        tables_layout: dict[str, Any] | None = None,
    ):
        self.pdf_path = Path(pdf_path)
        self.pdf_path.parent.mkdir(parents=True, exist_ok=True)

        self.header_title = header_title
        self.footer_line1 = footer_line1
        self.footer_line2 = footer_line2

        self.styles = _get_styles()
        # Compaction globale renforcée pour limiter les blancs inter-sections.
        self.styles["Heading1"] = ParagraphStyle(
            "OFBH1_compact",
            parent=self.styles["Heading1"],
            spaceBefore=max(0, self.styles["Heading1"].spaceBefore - 7 * mm),
            spaceAfter=max(0, self.styles["Heading1"].spaceAfter - 2 * mm),
        )
        self.styles["Heading2"] = ParagraphStyle(
            "OFBH2_compact",
            parent=self.styles["Heading2"],
            spaceBefore=max(0, self.styles["Heading2"].spaceBefore - 5 * mm),
            spaceAfter=max(0, self.styles["Heading2"].spaceAfter - 2 * mm),
        )
        self.styles["Heading3"] = ParagraphStyle(
            "OFBH3_compact",
            parent=self.styles["Heading3"],
            spaceBefore=max(0, self.styles["Heading3"].spaceBefore - 4 * mm),
            spaceAfter=max(0, self.styles["Heading3"].spaceAfter - 2 * mm),
        )
        self.avail_w = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT
        self.avail_h = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM
        self._tables_layout = deepcopy(
            tables_layout if tables_layout is not None else resolve_tables_layout({})
        )

        self._tmp_dir = Path(tempfile.mkdtemp(prefix="bilan_pdf_"))

        content_frame = Frame(
            MARGIN_LEFT,
            MARGIN_BOTTOM,
            PAGE_W - MARGIN_LEFT - MARGIN_RIGHT,
            PAGE_H - MARGIN_TOP - MARGIN_BOTTOM,
            id="content",
        )
        title_frame = Frame(0, 0, PAGE_W, PAGE_H, id="title_full")

        class _OFBBaseDocTemplate(BaseDocTemplate):
            def afterFlowable(doc_self, flowable):
                if hasattr(flowable, "_bookmarkName"):
                    doc_self.canv.bookmarkPage(flowable._bookmarkName)
                if hasattr(flowable, "_toc_title") and hasattr(flowable, "_toc_level"):
                    doc_self.notify(
                        "TOCEntry",
                        (
                            int(flowable._toc_level),
                            str(flowable._toc_title),
                            doc_self.page,
                            getattr(flowable, "_bookmarkName", None),
                        ),
                    )

        self.doc = _OFBBaseDocTemplate(
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
        self._toc_allowed_anchors: set[str] = set()

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
        header_lines = [ln.strip() for ln in str(self.header_title).splitlines() if ln.strip()]
        if not header_lines:
            header_lines = [""]
        font_size = 7 if len(header_lines) > 1 else 8
        canvas.setFont(f"{FONT_FAMILY}-Bold", font_size)
        canvas.setFillColor(rl_colors.HexColor(COLOR_PRIMARY))
        if len(header_lines) == 1:
            canvas.drawString(MARGIN_LEFT, y_header + 3, header_lines[0])
        else:
            base_y = y_header + 14
            step = 5
            for idx, line in enumerate(header_lines[:3]):
                canvas.drawString(MARGIN_LEFT, base_y - idx * step, line)

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
        title_page_config: dict | None = None,
    ) -> None:
        """Add a title page (uses TitlePage template)."""
        s = self.styles
        cfg = title_page_config or {}

        alignment_raw = str(cfg.get("alignment", "center")).strip().lower()
        alignment = TA_CENTER
        if alignment_raw == "right":
            alignment = TA_RIGHT
        elif alignment_raw == "left":
            alignment = TA_LEFT

        main_font_size = int(cfg.get("main_title_font_size", 28))
        secondary_font_size = int(cfg.get("profile_department_font_size", 28))
        meta_font_size = int(cfg.get("meta_font_size", 16))
        paragraph_space_after = float(cfg.get("paragraph_space_after", 0))
        top_spacer_ratio = float(cfg.get("top_spacer_ratio", 0.30))
        meta_block_space_before = float(cfg.get("meta_block_space_before", 12))
        meta_block_space_between = float(cfg.get("meta_block_space_between", 8))
        right_indent_mm = float(cfg.get("right_indent_mm", 0))

        title_main_style = ParagraphStyle(
            "TitlePageMain",
            parent=s["Title"],
            alignment=alignment,
            spaceAfter=paragraph_space_after,
            rightIndent=right_indent_mm * mm,
        )
        title_secondary_style = ParagraphStyle(
            "TitlePageSecondary",
            parent=s["Title"],
            alignment=alignment,
            spaceAfter=paragraph_space_after,
            rightIndent=right_indent_mm * mm,
        )
        meta_style = ParagraphStyle(
            "TitlePageMeta",
            parent=s["Title"],
            alignment=alignment,
            rightIndent=right_indent_mm * mm,
        )

        self.story.append(Spacer(1, PAGE_H * max(0.0, top_spacer_ratio)))
        paragraphs: list[list[str]] = []
        current_lines: list[str] = []
        for raw_line in title_lines:
            txt = str(raw_line or "").strip()
            if not txt:
                if current_lines:
                    paragraphs.append(current_lines)
                    current_lines = []
                continue
            current_lines.append(txt)
        if current_lines:
            paragraphs.append(current_lines)

        for p_idx, lines in enumerate(paragraphs):
            is_main = p_idx == 0
            size = main_font_size if is_main else secondary_font_size
            style = title_main_style if is_main else title_secondary_style
            weight_open = "<b>" if is_main else ""
            weight_close = "</b>" if is_main else ""
            txt = "<br/>".join(lines)
            self.story.append(
                Paragraph(
                    f'<font color="{COLOR_PRIMARY}" size="{size}">{weight_open}{txt}{weight_close}</font>',
                    style,
                )
            )
        self.story.append(Spacer(1, meta_block_space_before))
        self.story.append(
            Paragraph(
                f'<font color="{COLOR_SECONDARY}" size="{meta_font_size}">{period_str}</font>',
                meta_style,
            )
        )
        if subtitle:
            self.story.append(Spacer(1, meta_block_space_between))
            self.story.append(
                Paragraph(
                    f'<font color="{COLOR_SECONDARY}" size="{meta_font_size}">{subtitle}</font>',
                    meta_style,
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
        """Add a table of contents with page numbers."""
        s = self.styles
        self._toc_allowed_anchors = {a for a, _ in sections}
        self.story.append(Paragraph("Sommaire", s["Title"]))
        self.story.append(Spacer(1, 3 * mm))
        # dotsMinLevel=0 : pointillés aussi pour les entrées de niveau principal (1., 2., …).
        toc = TableOfContents(dotsMinLevel=0)
        toc.levelStyles = [
            ParagraphStyle(
                "TOCLevel0",
                parent=s["TOCEntry"],
                fontSize=12,
                leading=16,
                leftIndent=5 * mm,
                firstLineIndent=0,
            ),
            ParagraphStyle(
                "TOCLevel1",
                parent=s["TOCEntry"],
                fontSize=11,
                leading=14,
                leftIndent=12 * mm,
                firstLineIndent=0,
            ),
            ParagraphStyle(
                "TOCLevel2",
                parent=s["TOCEntry"],
                fontSize=10,
                leading=13,
                leftIndent=18 * mm,
                firstLineIndent=0,
            ),
        ]
        self.story.append(toc)
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
        toc_level: int | None = None,
        start_on_new_page: bool = False,
    ) -> None:
        if self._pending_section is not None:
            self.story.extend(self._pending_section)
            self._pending_section = None
        if start_on_new_page and self.story:
            self.story.append(PageBreak())
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
        if anchor in self._toc_allowed_anchors:
            title_para._bookmarkName = anchor
            title_para._toc_title = title
            title_para._toc_level = max((toc_level if toc_level is not None else level - 1), 0)
        spacer = Spacer(1, 0.5 * mm)
        self._pending_section = [anchor_para, title_para, spacer]

    def add_keep_together_block(self, flowables: List) -> None:
        """
        Enchaîne le titre de section en attente (s'il y en a un) avec des flowables
        dans un seul ``KeepTogether`` (ex. section 2.4 : tableau + graphiques sur une page).
        """
        merged: List = []
        if self._pending_section is not None:
            merged.extend(self._pending_section)
            self._pending_section = None
        merged.extend(flowables)
        self.story.append(KeepTogether(merged))

    def add_heading_chart_table_keep_together(
        self,
        *,
        heading_text: str,
        heading_style: str,
        chart_path: Path,
        chart_width_ratio: float,
        table_rows: list,
        table_caption: str = "",
        col_widths: Optional[list] = None,
        col_aligns: Optional[list] = None,
        header_font_size: float | None = None,
        trailing_spacer_mm: float = 4.0,
    ) -> None:
        """
        Sous-titre + graphique + tableau dans un seul ``KeepTogether`` pour éviter qu'un
        saut de page n'isole le titre du contenu (cas fréquent en fin de page).
        """
        block: List = []
        if self._pending_section is not None:
            block.extend(self._pending_section)
            self._pending_section = None
        style_key = heading_style if heading_style in self.styles else "Heading2"
        block.append(Paragraph(heading_text, self.styles[style_key]))
        block.append(Spacer(1, 2 * mm))
        w = self.avail_w * float(chart_width_ratio)
        if Path(chart_path).exists():
            try:
                with PILImage.open(str(chart_path)) as im:
                    width_px, height_px = im.size
                ratio = height_px / float(width_px) if width_px > 0 else 0.65
            except Exception:
                ratio = 0.65
            img = RLImage(str(chart_path), width=w, height=w * ratio)
            img.hAlign = "CENTER"
            block.append(img)
            block.append(Spacer(1, 2 * mm))
        if table_caption:
            block.append(Paragraph(table_caption, self.styles["TableCaption"]))
            block.append(Spacer(1, 1 * mm))
        split_by_row = bool(self._tables_layout.get("split_by_row"))
        block.append(
            ofb_table(
                table_rows,
                col_widths=col_widths,
                col_aligns=col_aligns,
                header_font_size=header_font_size,
                split_by_row=split_by_row,
            )
        )
        block.append(Spacer(1, float(trailing_spacer_mm) * mm))
        self.story.append(KeepTogether(block))

    # ------------------------------------------------------------------
    # Key figures
    # ------------------------------------------------------------------
    def add_key_figures(self, figures: List[Tuple[str, str]], *, spacer_after_mm: float = 4.0) -> None:
        """figures = [(value_str, label_str), ...]"""
        if not figures:
            return
        kf_table = key_figures_table(figures, self.styles)
        spacer = Spacer(1, float(spacer_after_mm) * mm)
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
        spacer = Spacer(1, 4 * mm)
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
        gap_kf = 2 * mm if compact else 4 * mm
        gap_cap = 1 * mm if compact else 2 * mm
        gap_after_tbl = 2 * mm if compact else 4 * mm
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
        keep_together: bool = True,
        wide_headers: bool = False,
        *,
        header_font_size: float | None = None,
        spacer_after_mm: float = 4.0,
    ) -> None:
        block: List = []
        if caption:
            block.append(Paragraph(caption, self.styles["TableCaption"]))
            block.append(Spacer(1, 1 * mm))
        split_by_row = bool(self._tables_layout.get("split_by_row"))
        try:
            max_rows_keep = int(self._tables_layout.get("max_rows_keep_together", 8))
        except (TypeError, ValueError):
            max_rows_keep = 8
        try:
            max_cell_chars = int(self._tables_layout.get("max_cell_chars_before_split", 100))
        except (TypeError, ValueError):
            max_cell_chars = 100
        n_rows = len(data_rows) if data_rows else 0
        long_cell = False
        if n_rows > 1 and max_cell_chars > 0:
            for row in data_rows[1:]:
                for cell in row:
                    if isinstance(cell, str) and len(cell.strip()) > max_cell_chars:
                        long_cell = True
                        break
                if long_cell:
                    break
        if n_rows > max_rows_keep or long_cell:
            split_by_row = True
            keep_together = False
        vh = self._tables_layout.get("vertical_header")
        pad_x = 0.0
        if isinstance(vh, dict):
            try:
                pad_x = float(vh.get("pad_x_pt", 0.0))
            except (TypeError, ValueError):
                pad_x = 0.0
        if wide_headers:
            tbl = ofb_table_wide(
                data_rows,
                col_widths=col_widths,
                col_aligns=col_aligns,
                avail_w=self.avail_w,
                split_by_row=split_by_row,
                vertical_header_pad_x_pt=pad_x,
            )
        else:
            tbl = ofb_table(
                data_rows,
                col_widths=col_widths,
                col_aligns=col_aligns,
                header_font_size=header_font_size,
                split_by_row=split_by_row,
            )
        block.append(tbl)
        block.append(Spacer(1, float(spacer_after_mm) * mm))
        if keep_together:
            if self._pending_section is not None:
                self.story.append(KeepTogether(self._pending_section + block))
                self._pending_section = None
            else:
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
        split_by_row = bool(self._tables_layout.get("split_by_row"))
        block.append(
            ofb_table(
                data_rows,
                col_widths=col_widths,
                col_aligns=col_aligns,
                split_by_row=split_by_row,
            )
        )
        if image_path is not None and Path(image_path).exists():
            block.append(Spacer(1, 1 * mm))
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
        block.append(Spacer(1, 1 * mm))
        self.story.append(KeepTogether(block))

    # ------------------------------------------------------------------
    # Images / Charts
    # ------------------------------------------------------------------
    def add_image(
        self,
        path: Path,
        width_ratio: float = 0.75,
        caption: str = "",
        *,
        spacer_after_mm: float = 2.0,
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
        block.append(Spacer(1, float(spacer_after_mm) * mm))
        if self._pending_section is not None:
            self.story.append(KeepTogether(self._pending_section + block))
            self._pending_section = None
        else:
            for el in block:
                self.story.append(el)

    def add_map(self, path: Path, caption: str = "") -> None:
        """Add a map image (full width)."""
        self.add_image(path, width_ratio=1.0, caption=caption)

    def _image_aspect_ratio(self, path: Path) -> float:
        try:
            with PILImage.open(str(path)) as im:
                width_px, height_px = im.size
            if width_px > 0:
                return height_px / float(width_px)
        except Exception:
            pass
        return 0.65

    def _scaled_image_flowable(self, path: Path, target_width: float) -> RLImage:
        ratio = self._image_aspect_ratio(path)
        img = RLImage(str(path), width=target_width, height=target_width * ratio)
        img.hAlign = "CENTER"
        return img

    def add_maps(
        self,
        paths: list[Path],
        *,
        layout: str = "vertical",
        captions: list[str] | None = None,
    ) -> None:
        """Ajoute une ou deux cartes sur la page courante (côte à côte ou empilées)."""
        existing = [Path(p) for p in paths if p and Path(p).exists()]
        if not existing:
            return
        if len(existing) == 1:
            cap = (captions or [""])[0] if captions else ""
            self.add_map(existing[0], caption=cap)
            return

        layout_norm = str(layout).strip().lower()
        vertical = layout_norm in ("vertical", "verticale", "empilees", "stacked")
        pair = existing[:2]
        caps = captions or ["", ""]
        block: list = []

        if vertical:
            ratios = [self._image_aspect_ratio(path) for path in pair]
            map_w = compute_stacked_maps_width(self.avail_w, self.avail_h, ratios)
            for i, path in enumerate(pair):
                block.append(self._scaled_image_flowable(path, map_w))
                cap = caps[i] if i < len(caps) else ""
                if cap:
                    block.append(Spacer(1, 1 * mm))
                    block.append(Paragraph(f"<i>{cap}</i>", self.styles["BodySmall"]))
                if i < len(pair) - 1:
                    block.append(Spacer(1, 2 * mm))
        else:
            gap = _MAPS_HORIZONTAL_GAP_PT
            ratios = [self._image_aspect_ratio(path) for path in pair]
            col_w = compute_side_by_side_maps_width(self.avail_w, self.avail_h, ratios)
            cells = [self._scaled_image_flowable(path, col_w) for path in pair]
            table = Table([cells], colWidths=[col_w, col_w])
            table.hAlign = "CENTER"
            block.append(table)
            row_caps = [caps[i] if i < len(caps) and caps[i] else "" for i in range(2)]
            if any(row_caps):
                cap_cells = []
                for cap in row_caps:
                    cap_cells.append(
                        Paragraph(f"<i>{cap}</i>", self.styles["BodySmall"]) if cap else ""
                    )
                block.append(Spacer(1, 1 * mm))
                cap_table = Table([cap_cells], colWidths=[col_w, col_w])
                cap_table.hAlign = "CENTER"
                block.append(cap_table)

        block.append(Spacer(1, 3 * mm))
        if self._pending_section is not None:
            self.story.append(KeepTogether(self._pending_section + block))
            self._pending_section = None
        else:
            for el in block:
                self.story.append(el)

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------
    def add_paragraph(self, text: str, style: str = "BodyText") -> None:
        para = Paragraph(text, self.styles[style])
        spacer = Spacer(1, 2 * mm)
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
            Spacer(1, 4 * mm),
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
    def add_glossary(
        self,
        rows: List[List[str]],
        *,
        col_widths: Optional[list] = None,
        col_aligns: Optional[list] = None,
    ) -> None:
        """rows = [["Terme", "Définition"], ...]  (first row = header)"""
        if not rows:
            return
        tbl = ofb_table(rows, col_widths=col_widths, col_aligns=col_aligns)
        block = [
            Paragraph("Glossaire", self.styles["Heading2"]),
            Spacer(1, 2 * mm),
            tbl,
            Spacer(1, 4 * mm),
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
            self.doc.multiBuild(self.story)
        finally:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
        return self.pdf_path
