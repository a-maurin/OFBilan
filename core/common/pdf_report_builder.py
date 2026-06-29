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
    TableStyle,
    CondPageBreak,
)
from reportlab.platypus.tableofcontents import TableOfContents
from PIL import Image as PILImage

from ofbilan.common.ofb_charte import (
    COLOR_CALLOUT_BG,
    COLOR_NOTICE_BG,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    FONT_FAMILY,
    IMG_BANNER,
    IMG_FILIGRANE,
    IMG_FILIGRANE_ALT,
    IMG_TITLE_DECO,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    PAGE_H,
    PAGE_W,
    SPACING_L,
    SPACING_M,
    SPACING_S,
    SPACING_XXS,
    _get_styles,
    charte_asset_path,
    header_layout_metrics,
)
from ofbilan.common.pdf_presentation_config import (
    resolve_charte_config,
    resolve_internal_diffusion_notice_config,
    resolve_tables_layout,
    should_show_internal_diffusion_title_notice,
)
from ofbilan.common.pdf_utils import key_figures_table, key_figures_table_rows, ofb_table, ofb_table_wide

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
# Carte seule : fraction < 1 pour éviter une coupe visuelle au bord droit (arrondis / centrage).
_MAP_PAGE_WIDTH_FRACTION = 0.90
# Retrait supplémentaire sur la largeur du bitmap dans la cellule (pt) — marge mécanique RL.
_MAP_DRAW_INSET_PT = 4.0


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
        footer_line1: str | None = None,
        footer_line2: str = "Service départemental de la Côte-d'Or – 57, rue de Mulhouse – 21000 Dijon – www.ofb.gouv.fr",
        title: str = "",
        author: str = "OFB",
        *,
        tables_layout: dict[str, Any] | None = None,
        charte_config: dict[str, Any] | None = None,
        diffusion: str = "interne",
        title_page_config: dict[str, Any] | None = None,
        content_only: bool = False,
        pagesize: tuple[float, float] | None = None,
        margin_bottom: float | None = None,
    ):
        self.pdf_path = Path(pdf_path)
        self.pdf_path.parent.mkdir(parents=True, exist_ok=True)
        self._pagesize = pagesize if pagesize is not None else A4
        self._page_w, self._page_h = self._pagesize

        self.header_title = header_title
        self.footer_line1 = footer_line1 or "Office français de la biodiversité"
        self.footer_line2 = footer_line2

        self._charte = deepcopy(
            charte_config if charte_config is not None else resolve_charte_config({})
        )
        typography_cfg = self._charte.get("typography", {})
        self.styles = _get_styles(typography_config=typography_cfg)
        # Titres : espace minimal en tête de bloc (le cadre démarre déjà sous l'en-tête page).
        self.styles["Heading1"] = ParagraphStyle(
            "OFBH1_compact",
            parent=self.styles["Heading1"],
            spaceBefore=0,
            spaceAfter=1 * mm,
        )
        self.styles["Heading2"] = ParagraphStyle(
            "OFBH2_compact",
            parent=self.styles["Heading2"],
            spaceBefore=0,
            spaceAfter=1 * mm,
        )
        self.styles["Heading3"] = ParagraphStyle(
            "OFBH3_compact",
            parent=self.styles["Heading3"],
            spaceBefore=0,
            spaceAfter=1 * mm,
        )

        header_lines = [
            ln.strip() for ln in str(header_title).splitlines() if ln.strip()
        ]
        n_header_lines = len(header_lines) or 1
        rule_from_top, margin_top = header_layout_metrics(n_header_lines)
        self._header_rule_y = self._page_h - rule_from_top
        self._margin_top = margin_top

        self._margin_bottom = float(margin_bottom) if margin_bottom is not None else MARGIN_BOTTOM
        self.avail_w = self._page_w - MARGIN_LEFT - MARGIN_RIGHT
        self.avail_h = self._page_h - margin_top - self._margin_bottom
        self._tables_layout = deepcopy(
            tables_layout if tables_layout is not None else resolve_tables_layout({})
        )
        self._diffusion = str(diffusion or "interne").strip().lower()
        self._internal_diffusion_notice = resolve_internal_diffusion_notice_config(
            title_page_config
        )

        self._tmp_dir = Path(tempfile.mkdtemp(prefix="bilan_pdf_"))

        content_frame = Frame(
            MARGIN_LEFT,
            self._margin_bottom,
            self._page_w - MARGIN_LEFT - MARGIN_RIGHT,
            self._page_h - margin_top - self._margin_bottom,
            id="content",
        )
        title_frame = Frame(0, 0, self._page_w, self._page_h, id="title_full")

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

        normal_template = PageTemplate(
            id="Normal",
            frames=[content_frame],
            onPage=self._header_footer,
        )
        if content_only:
            page_templates = [normal_template]
        else:
            page_templates = [
                PageTemplate(
                    id="TitlePage",
                    frames=[title_frame],
                    onPage=self._title_page_bg,
                ),
                normal_template,
            ]
        self.doc = _OFBBaseDocTemplate(
            str(self.pdf_path),
            pagesize=self._pagesize,
            title=title or header_title,
            author=author,
            pageTemplates=page_templates,
        )

        self.story: list = []
        # Titre de section en attente : gardé avec le prochain bloc (tableau, chiffres clés…)
        # pour éviter un titre seul en bas de page et le tableau en haut de la suivante.
        self._pending_section: Optional[List] = None
        self._toc_allowed_anchors: set[str] = set()
        self._figure_counter: int = 0

    @property
    def tmp_dir(self) -> Path:
        return self._tmp_dir

    def begin_content_pages(self) -> None:
        """Contenu sur le gabarit Normal, sans page de garde ni sommaire."""
        self.story.append(NextPageTemplate("Normal"))

    # ------------------------------------------------------------------
    # Page backgrounds
    # ------------------------------------------------------------------
    def _title_page_banner_height_pt(self) -> float:
        title_cfg = self._charte.get("title_page", {}) if isinstance(self._charte, dict) else {}
        try:
            return float(title_cfg.get("banner_height_mm", 42.0)) * mm
        except (TypeError, ValueError):
            return 42.0 * mm

    def _draw_internal_diffusion_notice_on_title_page(self, canvas) -> None:
        """Bandeau discret sous le bandeau Marianne (diffusion interne uniquement)."""
        if not should_show_internal_diffusion_title_notice(self._diffusion):
            return
        cfg = self._internal_diffusion_notice
        text = str(cfg.get("text", "")).strip()
        if not text:
            return
        font_name = f"{FONT_FAMILY}-Bold"
        try:
            font_size = float(cfg.get("font_size", 8))
        except (TypeError, ValueError):
            font_size = 8.0
        try:
            pad_x = float(cfg.get("pad_x_mm", 4)) * mm
            pad_y = float(cfg.get("pad_y_mm", 2)) * mm
            gap_below_banner = float(cfg.get("gap_below_logo_banner_mm", 10)) * mm
        except (TypeError, ValueError):
            pad_x, pad_y, gap_below_banner = 4 * mm, 2 * mm, 10 * mm
        banner_h = self._title_page_banner_height_pt()
        box_top = self._page_h - banner_h - gap_below_banner
        canvas.saveState()
        canvas.setFont(font_name, font_size)
        text_w = canvas.stringWidth(text, font_name, font_size)
        box_w = text_w + 2 * pad_x
        box_h = font_size + 2 * pad_y
        box_x = (self._page_w - box_w) * 0.5
        box_bottom = box_top - box_h
        canvas.setFillColor(rl_colors.HexColor(COLOR_NOTICE_BG))
        canvas.setStrokeColor(rl_colors.HexColor(COLOR_PRIMARY))
        canvas.setLineWidth(0.6)
        canvas.rect(box_x, box_bottom, box_w, box_h, fill=1, stroke=1)
        canvas.setFillColor(rl_colors.HexColor(COLOR_PRIMARY))
        canvas.drawCentredString(self._page_w * 0.5, box_bottom + pad_y, text)
        canvas.restoreState()

    def _title_page_bg(self, canvas, doc):
        title_cfg = self._charte.get("title_page", {}) if isinstance(self._charte, dict) else {}
        assets = self._charte.get("assets", {}) if isinstance(self._charte, dict) else {}
        try:
            deco_ratio = float(title_cfg.get("deco_height_ratio", 0.50))
        except (TypeError, ValueError):
            deco_ratio = 0.50
        deco_ratio = max(0.0, min(1.0, deco_ratio))
        banner_h = self._title_page_banner_height_pt()

        deco_path = charte_asset_path(
            assets,
            "title_page_deco",
            "image6.jpeg",
            fallback=IMG_TITLE_DECO,
        )
        banner_path = charte_asset_path(
            assets,
            "banner",
            "image5.jpg",
            fallback=IMG_BANNER,
        )

        canvas.saveState()
        if deco_path.exists() and deco_ratio > 0:
            deco_h = self._page_h * deco_ratio
            canvas.drawImage(
                str(deco_path),
                0,
                0,
                width=self._page_w,
                height=deco_h,
                preserveAspectRatio=False,
                mask="auto",
            )
        if banner_path.exists() and banner_h > 0:
            canvas.drawImage(
                str(banner_path),
                0,
                self._page_h - banner_h,
                width=self._page_w,
                height=banner_h,
                preserveAspectRatio=False,
                mask="auto",
            )
        canvas.restoreState()
        self._draw_internal_diffusion_notice_on_title_page(canvas)

    def _content_page_cfg(self) -> dict[str, Any]:
        cfg = self._charte.get("content_page", {}) if isinstance(self._charte, dict) else {}
        return cfg if isinstance(cfg, dict) else {}

    def _charte_assets_cfg(self) -> dict[str, Any]:
        assets = self._charte.get("assets", {}) if isinstance(self._charte, dict) else {}
        return assets if isinstance(assets, dict) else {}

    def _footer_text_zone_top_pt(self) -> float:
        """Sommet réservé au texte footer_line1/2 (coordonnées inchangées)."""
        y_foot = 8 * mm
        return y_foot + 12 + 7

    def _filigrane_image_size_pt(self, path: Path) -> tuple[float, float]:
        """Retourne (largeur, hauteur) en pt pour le filigrane bas-droite."""
        cfg = self._content_page_cfg()
        align = str(cfg.get("filigrane_align", "bottom_right")).strip().lower()
        ratio_raw = cfg.get("filigrane_height_ratio")
        height_pt: float | None = None
        if ratio_raw is not None:
            try:
                ratio = max(0.0, min(1.0, float(ratio_raw)))
                if ratio > 0:
                    height_pt = self._page_h * ratio
            except (TypeError, ValueError):
                height_pt = None
        if height_pt is None:
            mm_raw = cfg.get("watermark_height_mm")
            try:
                height_pt = float(mm_raw) * mm if mm_raw is not None else self._page_h * 0.50
            except (TypeError, ValueError):
                height_pt = self._page_h * 0.50
        if height_pt <= 0:
            return 0.0, 0.0

        aspect = 2480 / 1440
        try:
            with PILImage.open(path) as im:
                if im.height > 0:
                    aspect = im.width / im.height
        except OSError:
            pass

        width_pt = height_pt * aspect
        if align in {"bottom_right", "bottom-right", "bottomright"} and width_pt > self._page_w:
            width_pt = self._page_w
            height_pt = width_pt / aspect
        return width_pt, height_pt

    def _draw_content_page_watermark(self, canvas) -> None:
        """Filigrane unique bas-droite (image3), sans doublon footer_deco."""
        cfg = self._content_page_cfg()
        if not cfg.get("watermark_enabled", True):
            return
        path = charte_asset_path(
            self._charte_assets_cfg(),
            "watermark",
            "image3.jpeg",
            fallback=IMG_FILIGRANE,
        )
        if not path.exists():
            return

        width_pt, height_pt = self._filigrane_image_size_pt(path)
        if width_pt <= 0 or height_pt <= 0:
            return

        align = str(cfg.get("filigrane_align", "bottom_right")).strip().lower()
        if align in {"bottom_right", "bottom-right", "bottomright"}:
            x = self._page_w - width_pt
            y = 0.0
        else:
            x = 0.0
            y = 0.0

        canvas.drawImage(
            str(path),
            x,
            y,
            width=width_pt,
            height=height_pt,
            preserveAspectRatio=False,
            mask="auto",
        )

    def _draw_content_page_footer_deco(self, canvas) -> None:
        cfg = self._content_page_cfg()
        if not cfg.get("footer_deco_enabled", True):
            return
        try:
            deco_w = float(cfg.get("footer_deco_width_mm", 96.7)) * mm
            deco_h = float(cfg.get("footer_deco_height_mm", 104.5)) * mm
            margin_left = float(cfg.get("footer_deco_margin_left_mm", 0.0)) * mm
            margin_above_text = float(cfg.get("footer_deco_margin_bottom_mm", 18.0)) * mm
        except (TypeError, ValueError):
            deco_w, deco_h = 96.7 * mm, 104.5 * mm
            margin_left, margin_above_text = 0.0, 18.0 * mm
        if deco_w <= 0 or deco_h <= 0:
            return
        path = charte_asset_path(
            self._charte_assets_cfg(),
            "footer_deco",
            "image4.jpeg",
            fallback=IMG_FILIGRANE_ALT,
        )
        if not path.exists():
            return
        deco_bottom = self._footer_text_zone_top_pt() + margin_above_text
        canvas.drawImage(
            str(path),
            margin_left,
            deco_bottom,
            width=deco_w,
            height=deco_h,
            preserveAspectRatio=False,
            mask="auto",
        )

    def _header_footer(self, canvas, doc):
        canvas.saveState()
        self._draw_content_page_watermark(canvas)
        self._draw_content_page_footer_deco(canvas)
        canvas.setStrokeColor(rl_colors.HexColor(COLOR_PRIMARY))
        canvas.setLineWidth(2)
        y_rule = getattr(self, "_header_rule_y", self._page_h - 12 * mm)
        canvas.line(MARGIN_LEFT, y_rule, self._page_w - MARGIN_RIGHT, y_rule)
        header_lines = [ln.strip() for ln in str(self.header_title).splitlines() if ln.strip()]
        if not header_lines:
            header_lines = [""]
        font_size = 7 if len(header_lines) > 1 else 8
        line_step = 3.2 * mm
        canvas.setFont(f"{FONT_FAMILY}-Bold", font_size)
        canvas.setFillColor(rl_colors.HexColor(COLOR_PRIMARY))
        y_text = y_rule + 1.5 * mm
        for line in header_lines[:3]:
            canvas.drawString(MARGIN_LEFT, y_text, line)
            y_text += line_step

        y_foot = 8 * mm
        canvas.setFont(f"{FONT_FAMILY}", 7)
        canvas.setFillColor(rl_colors.HexColor(COLOR_SECONDARY))
        canvas.drawString(MARGIN_LEFT, y_foot + 12, self.footer_line1)
        canvas.drawString(MARGIN_LEFT, y_foot + 3, self.footer_line2)
        canvas.drawRightString(self._page_w - MARGIN_RIGHT, y_foot + 3, f"{doc.page}")
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
            fontName=FONT_FAMILY,
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

        self.story.append(Spacer(1, self._page_h * max(0.0, top_spacer_ratio)))
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
        self.story.append(Spacer(1, self._page_h * 0.15))
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
        self.story.append(Spacer(1, 1 * mm))
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
        append_to_pending: bool = False,
    ) -> None:
        if self._pending_section is not None and not append_to_pending:
            for item in self._pending_section:
                if hasattr(item, "keepWithNext"):
                    item.keepWithNext = 1
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
                spaceBefore=0,
                spaceAfter=0,
            )
        title_para = Paragraph(title, heading_style)
        if anchor in self._toc_allowed_anchors:
            title_para._bookmarkName = anchor
            title_para._toc_title = title
            title_para._toc_level = max((toc_level if toc_level is not None else level - 1), 0)
        section_flowables = [anchor_para, title_para]
        if append_to_pending and self._pending_section is not None:
            self._pending_section.extend(section_flowables)
        else:
            self._pending_section = section_flowables

    def add_keep_together_block(self, flowables: List) -> None:
        """
        Enchaîne le titre de section en attente (s'il y en a un) avec des flowables
        dans un seul ``KeepTogether`` (ex. section 2.4 : tableau + graphiques sur une page).
        """
        self._append_with_pending(flowables, keep_together=True)

    def _should_keep_block_together(self, flowables: List) -> bool:
        """Heuristique anti-pages vides: éviter KeepTogether sur blocs lourds.

        Refuse le KeepTogether lorsque la hauteur estimée du bloc dépasse 40 %
        de la zone utile (avail_h), pour éviter qu'un bloc trop grand ne soit
        poussé entièrement sur la page suivante en laissant la précédente vide.
        """
        if not flowables:
            return False
        table_count = sum(1 for f in flowables if isinstance(f, Table))
        image_count = sum(1 for f in flowables if isinstance(f, RLImage))
        # Jamais KeepTogether sur un bloc avec beaucoup d'images ou de tableaux
        if image_count > 2:
            return False
        if table_count > 1:
            return False
        # Estimation rapide de la hauteur du bloc
        estimated_h = self._estimate_block_height(flowables)
        max_keep_h = self.avail_h * 0.40
        if estimated_h > max_keep_h:
            return False
        return True

    def _estimate_block_height(self, flowables: List) -> float:
        """Estimation rapide de la hauteur d'un bloc de flowables (en points)."""
        total = 0.0
        for f in flowables:
            if isinstance(f, Spacer):
                total += f.height if hasattr(f, 'height') else getattr(f, '_height', 2 * mm)
            elif isinstance(f, RLImage):
                total += getattr(f, 'drawHeight', 0) or getattr(f, '_height', 150)
            elif isinstance(f, Table):
                # Wrap pour obtenir la taille réelle
                try:
                    w_h = f.wrap(self.avail_w, self.avail_h)
                    total += w_h[1]
                except Exception:
                    total += 80  # fallback
            elif isinstance(f, Paragraph):
                try:
                    w_h = f.wrap(self.avail_w, self.avail_h)
                    total += w_h[1]
                except Exception:
                    total += 18  # fallback ~1 ligne
            elif isinstance(f, KeepTogether):
                # Recurse into nested KeepTogether
                inner = getattr(f, '_content', []) or getattr(f, '_flowables', [])
                if inner:
                    total += self._estimate_block_height(list(inner))
                else:
                    total += 100  # fallback
            else:
                total += 20  # fallback pour flowable inconnu
        return total

    @staticmethod
    def _block_has_local_heading_with_chart(block: List) -> bool:
        """Bloc titre local + graphique (KeepTogether image) : pas de fusion monolithique."""
        if not block or not isinstance(block[0], Paragraph):
            return False
        return any(isinstance(f, KeepTogether) for f in block)

    def _append_with_pending(self, block: List, *, keep_together: bool) -> None:
        """Ajoute un bloc en gérant le titre pending avec KeepTogether optionnel."""
        has_pending = self._pending_section is not None
        pending: List = list(self._pending_section or [])
        if has_pending:
            self._pending_section = None
            
        merged: List = pending + block
        if not merged:
            return
            
        if (
            keep_together
            and self._should_keep_block_together(merged)
            and not self._block_has_local_heading_with_chart(block)
        ):
            self.story.append(KeepTogether(merged))
            return

        # Règle stricte: un titre (section/sous-section ou titre local de bloc)
        # reste lié au premier contenu afférent, même en pagination souple.
        #
        # Stratégie à deux niveaux :
        #  1. Tenter un KeepTogether sur le sous-bloc minimal (pending + titre local
        #     + premier contenu réel, typiquement titre+caption+table sans image) —
        #     ce sous-bloc est souvent suffisamment petit pour tenir dans un KeepTogether,
        #     même quand le bloc complet (avec image) le dépasse.
        #  2. Si même ce sous-bloc est trop grand, revenir à keepWithNext sur les
        #     paragraphes du préfixe (dernier recours, moins fiable mais sans page vide).
        attach_count = self._leading_title_chunk_len(block)
        if not keep_together:
            # Si on ne veut pas keep_together (ex: tableau long), on ne met pas le contenu réel dans le préfixe
            attach_count = 0
            while attach_count < len(block) and isinstance(block[attach_count], (Paragraph, Spacer)):
                attach_count += 1
                
        prefix = pending + block[:attach_count]

        # On vérifie si le préfixe contient du vrai contenu (pas juste Titre + Spacer)
        has_real_content = any(not isinstance(item, (Paragraph, Spacer)) for item in prefix)

        if keep_together and prefix and has_real_content and self._should_keep_block_together(prefix):
            # Le sous-bloc titre+table tient dans un KeepTogether → cohérence garantie
            self.story.append(KeepTogether(prefix))
        else:
            # Dernier recours (ou keep_together=False, ou préfixe vide de vrai contenu) :
            # CondPageBreak(150) pour garantir le collage titre/contenu sans déclencher
            # le bug de saut de page de ReportLab sur les grands tableaux.
            self.story.append(CondPageBreak(150))
            for item in prefix:
                if hasattr(item, 'keepWithNext'):
                    item.keepWithNext = 0
            self.story.extend(prefix)

        self.story.extend(block[attach_count:])

    def _leading_title_chunk_len(self, block: List) -> int:
        """
        Taille minimale d'un préfixe à garder ensemble:
        - titre local (Paragraph) + spacers immédiats + premier contenu réel TEXT/TABLE,
        - mais JAMAIS au-delà d'une image (RLImage) ou KeepTogether (qui contient typiquement
          une image + légende) : ces blocs lourds ne sont pas inclus dans le préfixe du titre
          afin d'éviter de gonfler le sous-bloc et de provoquer des sauts de page.
        - sinon au moins le premier élément.
        """
        # Types considérés comme "lourds" — ne pas les inclure dans le préfixe du titre
        _HEAVY_TYPES = (RLImage, KeepTogether)

        if not block:
            return 0
        if not isinstance(block[0], Paragraph):
            # Le premier élément est déjà lourd ou non-Paragraph → ne lier que l'ancre (pending)
            return 0 if isinstance(block[0], _HEAVY_TYPES) else 1
        idx = 1
        while idx < len(block) and isinstance(block[idx], Spacer):
            idx += 1
        # Vérifier que le premier "contenu réel" n'est pas une image/KeepTogether lourd
        if idx < len(block):
            if isinstance(block[idx], _HEAVY_TYPES):
                # Ne pas inclure l'image dans le préfixe — s'arrêter avant
                return idx  # titre + spacers, sans le premier contenu lourd
            return idx + 1  # titre + spacers + premier contenu texte/tableau
        return 1

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
        if str(heading_text or "").strip():
            style_key = heading_style if heading_style in self.styles else "Heading2"
            block.append(Paragraph(heading_text, self.styles[style_key]))
            block.append(Spacer(1, SPACING_S))
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
            self._figure_counter += 1
            fig_paragraph = Paragraph(f"Figure {self._figure_counter}", self.styles.get("FigureCaption", self.styles["BodySmall"]))
            block.append(KeepTogether([img, fig_paragraph]))
            block.append(Spacer(1, SPACING_S))
        if table_caption:
            block.append(Paragraph(table_caption, self.styles["TableCaption"]))
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
        self._append_with_pending(
            block,
            keep_together=not split_by_row,
        )

    # ------------------------------------------------------------------
    # Key figures
    # ------------------------------------------------------------------
    def extend_pending(self, flowables: List) -> None:
        """Étend le bloc titre en attente ; sinon ajoute au story (comportement dégradé)."""
        if not flowables:
            return
        if self._pending_section is not None:
            self._pending_section.extend(flowables)
        else:
            self.story.extend(flowables)

    def add_key_figures(
        self,
        figures: List[Tuple[str, str]],
        *,
        spacer_after_mm: float = 2.0,
        density: str = "auto",
        merge_with_next: bool = False,
    ) -> None:
        """figures = [(value_str, label_str), ...]"""
        if not figures:
            return
        kf_table = key_figures_table(
            figures, self.styles, density=density, table_width=self.avail_w
        )
        spacer = Spacer(1, float(spacer_after_mm) * mm)
        if self._pending_section is not None:
            if merge_with_next:
                self._pending_section.extend([kf_table, spacer])
            else:
                self.story.append(KeepTogether(self._pending_section + [kf_table, spacer]))
                self._pending_section = None
        else:
            self.story.append(kf_table)
            self.story.append(spacer)

    def add_key_figures_rows(
        self,
        figure_rows: List[List[Tuple[str, str]]],
        *,
        spacer_after_mm: float = 2.0,
    ) -> None:
        """Chiffres clés sur plusieurs lignes ; s'ajoute au titre de section en attente si présent."""
        if not figure_rows:
            return
        kf_table = key_figures_table_rows(figure_rows, self.styles, table_width=self.avail_w)
        spacer = Spacer(1, float(spacer_after_mm) * mm)
        if self._pending_section is not None:
            self._pending_section.extend([kf_table, spacer])
        else:
            self.story.append(kf_table)
            self.story.append(spacer)

    def append_pending_paragraph(self, text: str, style: str = "BodyText") -> None:
        """Paragraphe ajouté au bloc en attente (sans flush immédiat)."""
        para = Paragraph(text, self.styles[style])
        spacer = Spacer(1, SPACING_XXS)
        if self._pending_section is not None:
            self._pending_section.extend([para, spacer])
        else:
            self._pending_section = [para, spacer]

    def _build_callout_box_block(
        self,
        text: str,
        *,
        title: str = "",
        style: str = "BodyText",
        spacer_after_mm: float = 2.0,
    ) -> List:
        callout_text = str(text or "").strip()
        if not callout_text:
            return []

        title_text = str(title or "").strip()
        title_html = ""
        if title_text:
            title_html = f'<font color="{COLOR_PRIMARY}"><b>{title_text}</b></font><br/>'

        callout_style = ParagraphStyle(
            "OFBCalloutBody",
            parent=self.styles[style],
            spaceBefore=0,
            spaceAfter=0,
        )
        callout_para = Paragraph(f"{title_html}{callout_text}", callout_style)
        callout_table = Table([[callout_para]], colWidths=[self.avail_w])
        callout_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), rl_colors.HexColor(COLOR_CALLOUT_BG)),
                    ("BOX", (0, 0), (-1, -1), 0.8, rl_colors.HexColor(COLOR_PRIMARY)),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        return [callout_table, Spacer(1, float(spacer_after_mm) * mm)]

    def add_callout_box(
        self,
        text: str,
        *,
        title: str = "",
        style: str = "BodyText",
        spacer_after_mm: float = 2.0,
    ) -> None:
        block = self._build_callout_box_block(
            text,
            title=title,
            style=style,
            spacer_after_mm=spacer_after_mm,
        )
        if not block:
            return
        self._append_with_pending(
            block,
            keep_together=self._should_keep_block_together(block),
        )

    def append_pending_callout_box(
        self,
        text: str,
        *,
        title: str = "",
        style: str = "BodyText",
        spacer_after_mm: float = 2.0,
    ) -> None:
        block = self._build_callout_box_block(
            text,
            title=title,
            style=style,
            spacer_after_mm=spacer_after_mm,
        )
        if not block:
            return
        if self._pending_section is not None:
            self._pending_section.extend(block)
        else:
            self.story.extend(block)

    def append_pending_image(
        self,
        path: Path,
        width_ratio: float = 0.55,
        *,
        spacer_after_mm: float = 1.0,
    ) -> None:
        """Image ajoutée au bloc en attente (sans flush immédiat)."""
        if not Path(path).exists():
            return
        w = self.avail_w * width_ratio
        try:
            with PILImage.open(str(path)) as im:
                width_px, height_px = im.size
            ratio = height_px / float(width_px) if width_px > 0 else 0.65
        except Exception:
            ratio = 0.65
        img = RLImage(str(path), width=w, height=w * ratio)
        img.hAlign = "CENTER"
        
        self._figure_counter += 1
        fig_text = f"Figure {self._figure_counter}"
        fig_paragraph = Paragraph(fig_text, self.styles.get("FigureCaption", self.styles["BodySmall"]))
        
        block = [
            KeepTogether([img, fig_paragraph]),
            Spacer(1, float(spacer_after_mm) * mm)
        ]
        if self._pending_section is not None:
            self._pending_section.extend(block)
        else:
            for el in block:
                self.story.append(el)

    def append_pending_table(
        self,
        data_rows: list,
        caption: str = "",
        *,
        col_widths: Optional[list] = None,
        col_aligns: Optional[list] = None,
        spacer_after_mm: float = 1.5,
    ) -> None:
        """Tableau ajouté au bloc en attente (sans flush immédiat)."""
        block: List = []
        if caption:
            block.append(Paragraph(caption, self.styles["TableCaption"]))
        block.append(
            ofb_table(
                data_rows,
                col_widths=col_widths,
                col_aligns=col_aligns,
                split_by_row=True,
            )
        )
        block.append(Spacer(1, float(spacer_after_mm) * mm))
        if self._pending_section is not None:
            self._pending_section.extend(block)
        else:
            for el in block:
                self.story.append(el)

    def add_key_figures_and_table(
        self,
        figures: List[Tuple[str, str]],
        table_rows: list,
        caption: str = "",
        col_widths: Optional[list] = None,
        col_aligns: Optional[list] = None,
        *,
        merge_with_next: bool = False,
    ) -> None:
        """Bandeau de chiffres clés + tableau dans un même KeepTogether pour éviter un débordement."""
        block: List = []
        if figures:
            kf_table = key_figures_table(figures, self.styles)
            spacer = Spacer(1, SPACING_M)
            block.extend([kf_table, spacer])
        if caption:
            block.append(Paragraph(caption, self.styles["TableCaption"]))
        tbl = ofb_table(table_rows, col_widths=col_widths, col_aligns=col_aligns)
        block.append(tbl)
        block.append(Spacer(1, SPACING_L))
        if merge_with_next:
            if self._pending_section is not None:
                self._pending_section.extend(block)
            else:
                self._pending_section = block
        else:
            self._append_with_pending(block, keep_together=True)

    def _build_key_figures_and_tables_block(
        self,
        figures: List[Tuple[str, str]],
        tables: List[dict],
        *,
        compact: bool = False,
    ) -> List:
        """Bandeau + tableaux (flowables) sans toucher au story ni au pending."""
        block: List = []
        if figures:
            kf_table = key_figures_table(figures, self.styles)
            gap_kf = 2 * mm if compact else 4 * mm
            block.extend([kf_table, Spacer(1, gap_kf)])
        gap_cap = 1 * mm if compact else 2 * mm
        gap_after_tbl = 2 * mm if compact else 4 * mm
        n_tables = len(tables)
        for i, t in enumerate(tables):
            if t.get("caption"):
                block.append(Paragraph(t["caption"], self.styles["TableCaption"]))
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
        return block

    def add_key_figures_and_tables(
        self,
        figures: List[Tuple[str, str]],
        tables: List[dict],
        *,
        compact: bool = False,
        merge_with_next: bool = False,
    ) -> None:
        """Bandeau + plusieurs tableaux dans un même KeepTogether (même page).
        tables = [{"data_rows": ..., "caption": ..., "col_widths": ..., "col_aligns": ...}, ...]
        compact=True : espacements verticaux réduits (ex. section PEJ sur une page).
        merge_with_next=True : garde le titre + bandeau + tableaux dans ``_pending_section``
        jusqu'au prochain ``add_table`` (ex. détail PA / PEJ).
        """
        block = self._build_key_figures_and_tables_block(figures, tables, compact=compact)
        if not block:
            return
        if merge_with_next:
            if self._pending_section is not None:
                self._pending_section.extend(block)
            else:
                self._pending_section = block
        else:
            self._append_with_pending(block, keep_together=True)

    def add_key_figures_section_keep_together(
        self,
        figures: List[Tuple[str, str]],
        *,
        intro_table: dict | None = None,
        table_specs: list[dict] | None = None,
        zone_table: dict | None = None,
        compact: bool = True,
    ) -> None:
        """
        Bandeau de chiffres clés + tableaux (ex. 3.1 PVe).

        Titres de section + bandeau (+ intro éventuelle) dans un ``KeepTogether`` ;
        chaque tableau avec légende dans son propre ``KeepTogether`` (légende + début
        du tableau sur la même page, coupure inter-lignes si le tableau est long).
        """
        if not figures and not intro_table and not table_specs and not zone_table:
            return
        gap_kf = 2 * mm if compact else 4 * mm
        gap_cap_mm = 1.0 if compact else 2.0
        gap_after_tbl_mm = 2.0 if compact else 4.0

        header: List = []
        if self._pending_section is not None:
            header.extend(self._pending_section)
            self._pending_section = None
            
        if figures:
            header.extend([key_figures_table(figures, self.styles), Spacer(1, gap_kf)])

        if intro_table and intro_table.get("data_rows"):
            intro_rows = intro_table["data_rows"]
            intro_caption = intro_table.get("caption") or ""
            if intro_caption:
                header.append(Paragraph(intro_caption, self.styles["TableCaption"]))
            header.append(
                ofb_table(
                    intro_rows,
                    col_widths=intro_table.get("col_widths"),
                    col_aligns=intro_table.get("col_aligns"),
                    split_by_row=self._table_uses_split_by_row(intro_rows),
                )
            )
            header.append(Spacer(1, gap_after_tbl_mm * mm))

        if header:
            self.story.append(KeepTogether(header))

        specs = [s for s in (table_specs or []) if s.get("data_rows")]
        for i, spec in enumerate(specs):
            gap_after = gap_after_tbl_mm if (i < len(specs) - 1 or zone_table) else gap_after_tbl_mm
            self._append_captioned_table_keep_together(
                spec["data_rows"],
                caption=spec.get("caption") or "",
                col_widths=spec.get("col_widths"),
                col_aligns=spec.get("col_aligns"),
                gap_cap_mm=gap_cap_mm,
                gap_after_mm=gap_after,
            )

        if zone_table and zone_table.get("data_rows"):
            self._append_captioned_table_keep_together(
                zone_table["data_rows"],
                caption=zone_table.get("caption") or "",
                col_widths=zone_table.get("col_widths"),
                col_aligns=zone_table.get("col_aligns"),
                gap_cap_mm=gap_cap_mm,
                gap_after_mm=gap_after_tbl_mm,
            )

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------
    def _table_uses_split_by_row(self, data_rows: list) -> bool:
        if bool(self._tables_layout.get("split_by_row")):
            return True
        n_rows = len(data_rows) if data_rows else 0
        # Seuil minimal robuste : même si la config n'indique pas de split,
        # certains tableaux (ex. NATINF détaillés) plantent si un tableau de
        # ~13 lignes ne peut pas se scinder entre deux pages.
        if n_rows > 12:
            return True
        try:
            max_rows_keep = int(self._tables_layout.get("max_rows_keep_together", 8))
        except (TypeError, ValueError):
            max_rows_keep = 8
        if n_rows > max_rows_keep:
            return True
        try:
            max_cell_chars = int(self._tables_layout.get("max_cell_chars_before_split", 100))
        except (TypeError, ValueError):
            max_cell_chars = 100
        if n_rows > 1 and max_cell_chars > 0:
            for row in data_rows[1:]:
                for cell in row:
                    if isinstance(cell, str) and len(cell.strip()) > max_cell_chars:
                        return True
        return False

    def _append_captioned_table_keep_together(
        self,
        data_rows: list,
        *,
        caption: str = "",
        col_widths: Optional[list] = None,
        col_aligns: Optional[list] = None,
        header_font_size: float | None = None,
        gap_cap_mm: float = 1.0,
        gap_after_mm: float = 2.0,
    ) -> None:
        """Légende + tableau : même page au début ; tableau long coupé entre les lignes."""
        if not data_rows:
            return
        split_by_row = self._table_uses_split_by_row(data_rows)
        block: List = []
        if caption:
            block.append(Paragraph(caption, self.styles["TableCaption"]))
        block.append(
            ofb_table(
                data_rows,
                col_widths=col_widths,
                col_aligns=col_aligns,
                header_font_size=header_font_size,
                split_by_row=split_by_row,
            )
        )
        block.append(Spacer(1, float(gap_after_mm) * mm))
        # Si le tableau doit être coupé entre les lignes, ne pas l'enfermer dans KeepTogether
        # (sinon LayoutError si le tableau dépasse la hauteur utile d'une page).
        if split_by_row:
            for el in block:
                self.story.append(el)
        else:
            self.story.append(KeepTogether(block))
    def add_table(
        self,
        data_rows: list,
        caption: str = "",
        col_widths: Optional[list] = None,
        col_aligns: Optional[list] = None,
        keep_together: bool = True,
        wide_headers: bool = False,
        wide_header_layout: str | None = None,
        *,
        header_font_size: float | None = None,
        wide_header_font_size: float | None = None,
        wide_header_max_lines: int | None = None,
        spacer_after_mm: float = 4.0,
        max_rows_keep_together: int | None = None,
        max_cell_chars_before_split: int | None = None,
        keep_caption_with_table: bool = True,
    ) -> None:
        block: List = []
        if caption:
            block.append(Paragraph(caption, self.styles["TableCaption"]))
        split_by_row = bool(self._tables_layout.get("split_by_row"))
        if max_rows_keep_together is not None:
            max_rows_keep = int(max_rows_keep_together)
        else:
            try:
                max_rows_keep = int(self._tables_layout.get("max_rows_keep_together", 8))
            except (TypeError, ValueError):
                max_rows_keep = 8
        if max_cell_chars_before_split is not None:
            max_cell_chars = int(max_cell_chars_before_split)
        else:
            try:
                max_cell_chars = int(self._tables_layout.get("max_cell_chars_before_split", 100))
            except (TypeError, ValueError):
                max_cell_chars = 100
        n_rows = len(data_rows) if data_rows else 0
        long_cell = False
        if n_rows > 1 and max_cell_chars > 0:
            for row in data_rows[1:]:
                for cell in row:
                    text_len = 0
                    if isinstance(cell, str):
                        text_len = len(cell.strip())
                    elif isinstance(cell, Paragraph):
                        if hasattr(cell, "getPlainText"):
                            text_len = len(cell.getPlainText().strip())
                        else:
                            text_len = len(getattr(cell, "text", ""))
                    if text_len > max_cell_chars:
                        long_cell = True
                        break
                if long_cell:
                    break
        if n_rows > max_rows_keep or long_cell:
            split_by_row = True
        vh = self._tables_layout.get("vertical_header")
        pad_x = 0.0
        vh_max_lines = 6
        vh_font_size = 7.0
        vh_row_pad = 8.0
        if isinstance(vh, dict):
            try:
                pad_x = float(vh.get("pad_x_pt", 0.0))
            except (TypeError, ValueError):
                pad_x = 0.0
            try:
                vh_max_lines = int(vh.get("max_lines", 6))
            except (TypeError, ValueError):
                vh_max_lines = 6
            try:
                vh_font_size = float(vh.get("font_size", 7.0))
            except (TypeError, ValueError):
                vh_font_size = 7.0
            try:
                vh_row_pad = float(vh.get("row_padding_pt", 8.0))
            except (TypeError, ValueError):
                vh_row_pad = 8.0
        wh_layout = str(wide_header_layout or "vertical").strip().lower()
        wh_font = vh_font_size
        if wide_header_font_size is not None:
            try:
                wh_font = float(wide_header_font_size)
            except (TypeError, ValueError):
                pass
        wh_max_lines = vh_max_lines
        if wide_header_max_lines is not None:
            try:
                wh_max_lines = int(wide_header_max_lines)
            except (TypeError, ValueError):
                pass
        if wide_headers:
            tbl = ofb_table_wide(
                data_rows,
                col_widths=col_widths,
                col_aligns=col_aligns,
                avail_w=self.avail_w,
                split_by_row=split_by_row,
                vertical_header_pad_x_pt=pad_x,
                vertical_header_max_lines=wh_max_lines,
                vertical_header_font_size=wh_font,
                vertical_header_row_padding_pt=vh_row_pad,
                header_layout=wh_layout,
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
        use_keep = (bool(caption) and keep_caption_with_table) or keep_together
        if split_by_row:
            use_keep = False
            
        if self._pending_section is not None:
            self._append_with_pending(block, keep_together=use_keep)
        elif use_keep and self._should_keep_block_together(block):
            self.story.append(KeepTogether(block))
        else:
            if caption and keep_caption_with_table and len(block) > 0:
                self.story.append(CondPageBreak(150))
            for el in block:
                if hasattr(el, 'keepWithNext'):
                    el.keepWithNext = 0
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
        if table_caption:
            block.append(Paragraph(table_caption, self.styles["TableCaption"]))
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
            block.append(Spacer(1, SPACING_XXS))
            w = self.avail_w * image_width_ratio
            try:
                with PILImage.open(str(image_path)) as im:
                    width_px, height_px = im.size
                ratio = (height_px / float(width_px)) if width_px > 0 else 0.45
            except Exception:
                ratio = 0.45
            img = RLImage(str(image_path), width=w, height=w * ratio)
            img.hAlign = "CENTER"
            self._figure_counter += 1
            fig_paragraph = Paragraph(f"Figure {self._figure_counter}", self.styles.get("FigureCaption", self.styles["BodySmall"]))
            block.append(KeepTogether([img, fig_paragraph]))
        block.append(Spacer(1, 1 * mm))
        keep_block = not split_by_row
        self._append_with_pending(block, keep_together=keep_block)

    def add_tables_keep_together(
        self,
        table_specs: list[dict],
        *,
        gap_between_mm: float = 2.0,
        trailing_spacer_mm: float = 2.0,
    ) -> None:
        """
        Enchaîne plusieurs tableaux (légendes incluses) dans un seul ``KeepTogether``
        pour éviter un saut de page entre eux (ex. détail PVe + analyse NATINF en 3.1).
        """
        if not table_specs:
            return
        block: List = []
        split_by_row = bool(self._tables_layout.get("split_by_row"))
        rendered = 0
        for spec in table_specs:
            rows = spec.get("data_rows") or []
            if not rows:
                continue
            if rendered:
                block.append(Spacer(1, float(gap_between_mm) * mm))
            caption = spec.get("caption") or ""
            if caption:
                block.append(Paragraph(caption, self.styles["TableCaption"]))
                block.append(Spacer(1, 1 * mm))
            block.append(
                ofb_table(
                    rows,
                    col_widths=spec.get("col_widths"),
                    col_aligns=spec.get("col_aligns"),
                    header_font_size=spec.get("header_font_size"),
                    split_by_row=split_by_row,
                )
            )
            rendered += 1
        if not rendered:
            return
        block.append(Spacer(1, float(trailing_spacer_mm) * mm))
        self._append_with_pending(
            block,
            keep_together=self._should_keep_block_together(block),
        )

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
        
        self._figure_counter += 1
        fig_text = f"Figure {self._figure_counter}"
        if caption:
            fig_text += f" : {caption}"
            
        fig_paragraph = Paragraph(fig_text, self.styles.get("FigureCaption", self.styles["BodySmall"]))
        block = [KeepTogether([img, fig_paragraph])]
        block.append(Spacer(1, float(spacer_after_mm) * mm))
        self._append_with_pending(
            block,
            keep_together=False,
        )

    def _map_image_holder_table(self, path: Path, map_cell_w: float) -> Table:
        """Table 1×1 largeur fixe : centre l'image et évite un débordement perçu au bord du cadre."""
        draw_w = max(1.0, float(map_cell_w) - _MAP_DRAW_INSET_PT)
        img = self._scaled_image_flowable(Path(path), draw_w)
        holder = Table([[img]], colWidths=[map_cell_w])
        holder.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        holder.hAlign = "CENTER"
        return holder

    def _map_display_width(self, path: Path) -> float:
        """Largeur pour une carte seule tenant dans la hauteur utile (réserve titre / légende)."""
        ratio = self._image_aspect_ratio(path)
        return compute_stacked_maps_width(
            self.avail_w, self.avail_h, [ratio], width_fraction=_MAP_PAGE_WIDTH_FRACTION
        )

    def add_map(self, path: Path, caption: str = "") -> None:
        """Ajoute une carte dimensionnée pour occuper au mieux la zone utile de la page."""
        if not Path(path).exists():
            return
        map_cell_w = self._map_display_width(path)
        block: List = [self._map_image_holder_table(Path(path), map_cell_w)]
        if caption:
            block.append(Spacer(1, 2 * mm))
            block.append(Paragraph(f"<i>{caption}</i>", self.styles["BodySmall"]))
        block.append(Spacer(1, SPACING_S))
        if self._pending_section is not None:
            self.story.append(KeepTogether(self._pending_section + block))
            self._pending_section = None
        else:
            for el in block:
                self.story.append(el)

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
        """
        Ajoute toutes les cartes PNG en les superposant par lot de 2 maximum par page.
        """
        existing = [Path(p) for p in paths if p and Path(p).exists()]
        if not existing:
            return
            
        caps = list(captions) if captions else []
        
        # --- Calcul de la largeur globale pour toutes les cartes ---
        # On calcule map_cell_w en se basant sur le premier lot pour que toutes les cartes 
        # (même celles sur les pages suivantes) aient exactement la même taille.
        eff_avail_h_global = self.avail_h
        if self._pending_section is not None:
            pending_h = self._estimate_block_height(self._pending_section)
            eff_avail_h_global = max(eff_avail_h_global * 0.3, eff_avail_h_global - pending_h - 20)

        first_chunk_ratios = [self._image_aspect_ratio(p) for p in existing[:2]]
        global_map_cell_w = compute_stacked_maps_width(
            self.avail_w, eff_avail_h_global, first_chunk_ratios, width_fraction=_MAP_PAGE_WIDTH_FRACTION
        )
        
        # Parcourir les cartes par lots de 2 maximum
        for chunk_idx in range(0, len(existing), 2):
            if chunk_idx > 0:
                self.add_page_break()
                
            chunk_paths = existing[chunk_idx:chunk_idx+2]
            chunk_caps = caps[chunk_idx:chunk_idx+2]
            
            map_cell_w = global_map_cell_w

            block: List = []
            for i, path in enumerate(chunk_paths):
                holder = self._map_image_holder_table(path, map_cell_w)
                block.append(holder)
                cap = chunk_caps[i] if i < len(chunk_caps) else ""
                if cap:
                    block.append(Spacer(1, 2 * mm))
                    block.append(Paragraph(f"<i>{cap}</i>", self.styles["BodySmall"]))
                if i < len(chunk_paths) - 1:
                    block.append(Spacer(1, SPACING_M))
                    
            block.append(Spacer(1, SPACING_S))
            
            if chunk_idx == 0 and self._pending_section is not None:
                self.story.append(KeepTogether(self._pending_section + block))
                self._pending_section = None
            else:
                self.story.append(KeepTogether(block))

    # ------------------------------------------------------------------
    # Text
    # ------------------------------------------------------------------
    def add_paragraph(self, text: str, style: str = "BodyText") -> None:
        para = Paragraph(text, self.styles[style])
        spacer = Spacer(1, SPACING_XXS)
        if self._pending_section is not None:
            for item in self._pending_section:
                if hasattr(item, "keepWithNext"):
                    item.keepWithNext = 1
            para.keepWithNext = 1
            spacer.keepWithNext = 1
            self.story.extend(self._pending_section)
            self.story.extend([para, spacer])
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
            Spacer(1, SPACING_S),
            Paragraph(html_text, self.styles["BodyText"]),
            Spacer(1, SPACING_M),
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
            Spacer(1, SPACING_S),
            tbl,
            Spacer(1, SPACING_M),
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
            
        # Debug story flowables
        try:
            debug_path = r"C:\Users\aguirre.maurin\.gemini\antigravity\brain\3fa1562d-d681-494a-bf8c-f533542965b2\scratch\story_flowables.txt"
            with open(debug_path, "w", encoding="utf-8") as f:
                for idx, flowable in enumerate(self.story):
                    f.write(f"{idx}: {type(flowable).__name__}\n")
                    if hasattr(flowable, "_content"):
                        f.write(f"  Nested: {[type(x).__name__ for x in flowable._content]}\n")
                    # If it has text or other info
                    if hasattr(flowable, "text"):
                        f.write(f"  Text: {flowable.text[:100]}\n")
                    # If it's a KeepTogether or has Paragraphs inside
                    if type(flowable).__name__ == "KeepTogether":
                        for sub in getattr(flowable, "_content", []):
                            if hasattr(sub, "text"):
                                f.write(f"    SubText: {sub.text[:100]}\n")
        except Exception as e:
            pass
            
        try:
            self.doc.multiBuild(self.story)
        finally:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
        return self.pdf_path
