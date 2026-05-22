"""Mise en forme brochure uniquement : encadrés arrondis + couleurs ``ofb_charte``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors as rl_colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from bilans.common.ofb_charte import (
    COLOR_GREY,
    COLOR_PRIMARY,
    COLOR_TABLE_ALT_ROW,
    COLOR_TABLE_BORDER,
    COLOR_TABLE_HEADER_BG,
)

_MODELE_OFB_DIR = Path(__file__).resolve().parents[3] / "ref" / "programme" / "modele_ofb"
LOGO_OFB_SVG = _MODELE_OFB_DIR / "ofb.svg"
LOGO_RF_PNG = _MODELE_OFB_DIR / "republique_francaise_rvb.png"
_PAGE1_LOGO_RF_H = 8.5 * mm
_PAGE1_LOGO_OFB_H = 7.5 * mm
_PAGE1_LOGO_GAP = 3.0 * mm

RADIUS_STD_PT = 10.0
RADIUS_CALLOUT_TL_PT = 22.0
_PAD_STD_PT = 3.0 * mm
_TABLE_CELL_PAD_PT = 4.0

_CLR_PRIMARY = COLOR_TABLE_HEADER_BG
_CLR_BODY_BG = rl_colors.white
_CLR_SURFACE = COLOR_TABLE_ALT_ROW
_CLR_BORDER = COLOR_TABLE_BORDER
_CLR_GREY = rl_colors.HexColor(COLOR_GREY)
_CLR_WHITE = rl_colors.white


def encadre_inner_width(outer_w: float, *, pad_pt: float = _PAD_STD_PT) -> float:
    """Largeur utile à l'intérieur d'un encadré (padding + petite marge)."""
    return max(30.0, float(outer_w) - 2 * pad_pt - 2.0)


def _flowable_col_widths(flow: Flowable) -> list[float] | None:
    if isinstance(flow, Table):
        cw = getattr(flow, "_colWidths", None) or getattr(flow, "colWidths", None)
        if cw:
            return [float(x) for x in cw]
    return None


def brochure_table(
    data_rows,
    *,
    col_widths=None,
    col_aligns=None,
    header_font_size: float | None = None,
    split_by_row: bool = False,
    header_row: bool = True,
):
    """Tableau brochure : pas de grille ni zébrage (l'encadré arrondi porte la forme)."""
    from bilans.common.pdf_utils import ofb_table

    return ofb_table(
        data_rows,
        col_widths=col_widths,
        col_aligns=col_aligns,
        header_font_size=header_font_size,
        split_by_row=split_by_row,
        show_grid=False,
        zebra_rows=False,
        header_row=header_row,
    )


def apply_brochure_mpl_style() -> None:
    from bilans.common.rendus_graphiques import apply_mpl_style

    apply_mpl_style()


@dataclass(frozen=True)
class EncadreStyle:
    header_bg: rl_colors.Color
    body_bg: rl_colors.Color
    border: rl_colors.Color
    radius_pt: float = RADIUS_STD_PT
    callout_tl: bool = False


ENCADRE_SECTION = EncadreStyle(_CLR_PRIMARY, _CLR_BODY_BG, _CLR_BORDER)
ENCADRE_SURFACE = EncadreStyle(_CLR_PRIMARY, _CLR_SURFACE, _CLR_BORDER)
ENCADRE_CALLOUT = EncadreStyle(_CLR_PRIMARY, _CLR_SURFACE, _CLR_BORDER, callout_tl=True)


def _radii_tuple(style: EncadreStyle, *, header: bool = False) -> tuple[float, float, float, float]:
    r = style.radius_pt
    if style.callout_tl and not header:
        return (RADIUS_CALLOUT_TL_PT, r, r, r)
    return (r, r, r, r)


def _draw_round_rect(
    canv,
    x: float,
    y: float,
    w: float,
    h: float,
    radii: tuple[float, float, float, float],
    *,
    fill: rl_colors.Color | None = None,
    stroke: rl_colors.Color | None = None,
    stroke_w: float = 0.6,
) -> None:
    rtl, rtr, rbr, rbl = (min(r, w / 2, h / 2) for r in radii)
    path = canv.beginPath()
    path.moveTo(x + rtl, y)
    path.lineTo(x + w - rtr, y)
    if rtr:
        path.arcTo(x + w - 2 * rtr, y, x + w, y + 2 * rtr, startAng=270, extent=90)
    else:
        path.lineTo(x + w, y)
    path.lineTo(x + w, y + h - rbr)
    if rbr:
        path.arcTo(x + w - 2 * rbr, y + h - 2 * rbr, x + w, y + h, startAng=0, extent=90)
    else:
        path.lineTo(x + w, y + h)
    path.lineTo(x + rbl, y + h)
    if rbl:
        path.arcTo(x, y + h - 2 * rbl, x + 2 * rbl, y + h, startAng=90, extent=90)
    else:
        path.lineTo(x, y + h)
    path.lineTo(x, y + rtl)
    if rtl:
        path.arcTo(x, y, x + 2 * rtl, y + 2 * rtl, startAng=180, extent=90)
    else:
        path.lineTo(x, y)
    path.close()
    canv.saveState()
    if fill is not None:
        canv.setFillColor(fill)
    if stroke is not None:
        canv.setStrokeColor(stroke)
        canv.setLineWidth(stroke_w)
    canv.drawPath(path, fill=1 if fill else 0, stroke=1 if stroke else 0)
    canv.restoreState()


class BrochureEncadre(Flowable):
    """Bloc titre + contenu dans un encadré à coins arrondis."""

    def __init__(
        self,
        width: float,
        title: str | None,
        body: list,
        style: EncadreStyle,
        *,
        styles,
        pad_pt: float = _PAD_STD_PT,
        col_headers: list[str] | None = None,
        col_width_fracs: list[float] | None = None,
    ):
        super().__init__()
        self.box_width = float(width)
        self.title = str(title or "").strip() or None
        self.body = [b for b in body if b]
        self.style = style
        self.styles = styles
        self.pad = float(pad_pt)
        self.col_headers = [str(h).strip() for h in (col_headers or []) if str(h).strip()]
        self.col_width_fracs = list(col_width_fracs) if col_width_fracs else None
        self._hdr_h = 0.0
        self._body_h = 0.0
        self._header_table: Table | None = None
        self._wrapped: list[tuple[Flowable, float, float]] = []
        self.height = 0.0

    def _header_title_style(self) -> ParagraphStyle:
        return ParagraphStyle(
            "BrochureEncTitle",
            parent=self.styles["BodyText"],
            fontName=f"{self.styles['BodyText'].fontName}-Bold",
            fontSize=9.5,
            leading=11.5,
            textColor=_CLR_WHITE,
            alignment=TA_LEFT,
        )

    def _header_col_style(self) -> ParagraphStyle:
        base = self._header_title_style()
        return ParagraphStyle(
            "BrochureEncColHdr",
            parent=base.parent,
            fontName=base.fontName,
            fontSize=base.fontSize,
            leading=base.leading,
            textColor=base.textColor,
            alignment=TA_RIGHT,
        )

    def _resolve_col_widths(self, inner_w: float) -> list[float]:
        for item in self.body:
            cw = _flowable_col_widths(item)
            if cw:
                return cw
        fracs = self.col_width_fracs
        if not fracs:
            return [inner_w]
        total = sum(float(f) for f in fracs) or 1.0
        return [inner_w * float(f) / total for f in fracs]

    def _build_header_table(self, col_ws: list[float], availHeight: float) -> Table | None:
        if not self.title:
            return None
        title_ps = self._header_title_style()
        col_ps = self._header_col_style()
        cells: list = [Paragraph(f"<b>{self.title}</b>", title_ps)]
        for label in self.col_headers:
            cells.append(Paragraph(f"<b>{label}</b>", col_ps))
        while len(cells) < len(col_ws):
            cells.append("")
        cells = cells[: len(col_ws)]
        tbl = Table([cells], colWidths=col_ws)
        n_hdr = len(self.col_headers)
        last_col = len(col_ws) - 1
        first_num = len(col_ws) - n_hdr
        style_cmds = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), _TABLE_CELL_PAD_PT),
            ("RIGHTPADDING", (0, 0), (-1, -1), _TABLE_CELL_PAD_PT),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ]
        if n_hdr and first_num <= last_col:
            style_cmds.append(("ALIGN", (first_num, 0), (last_col, 0), "RIGHT"))
        tbl.setStyle(TableStyle(style_cmds))
        return tbl

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        w = min(self.box_width, availWidth)
        self.box_width = w
        inner_w = encadre_inner_width(w, pad_pt=self.pad)
        if self.title:
            if self.col_headers:
                col_ws = self._resolve_col_widths(inner_w)
                self._header_table = self._build_header_table(col_ws, availHeight)
                _, th = self._header_table.wrap(inner_w, availHeight)
            else:
                ps = self._header_title_style()
                para = Paragraph(f"<b>{self.title}</b>", ps)
                self._header_table = Table([[para]], colWidths=[inner_w])
                self._header_table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("LEFTPADDING", (0, 0), (-1, -1), _TABLE_CELL_PAD_PT),
                            ("RIGHTPADDING", (0, 0), (-1, -1), _TABLE_CELL_PAD_PT),
                            ("TOPPADDING", (0, 0), (-1, -1), 2),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ]
                    )
                )
                _, th = self._header_table.wrap(inner_w, availHeight)
            self._hdr_h = th + 10.0
        else:
            self._header_table = None
            self._hdr_h = 0.0
        self._wrapped = []
        body_h = 0.0
        for item in self.body:
            if not item:
                continue
            iw, ih = item.wrap(inner_w, availHeight)
            self._wrapped.append((item, iw, ih))
            body_h += ih
        if not self._wrapped:
            body_h = 2 * mm
        self._body_h = body_h + (2.0 if self._wrapped else 0.0)
        self.height = self._hdr_h + self._body_h + 2 * self.pad
        return (w, self.height)

    def draw(self) -> None:
        c = self.canv
        w, h = self.box_width, self.height
        radii_body = _radii_tuple(self.style, header=False)
        _draw_round_rect(
            c, 0, 0, w, h, radii_body, fill=self.style.body_bg, stroke=self.style.border, stroke_w=0.6
        )
        if self.title and self._header_table:
            hh = self._hdr_h
            radii_hdr = _radii_tuple(self.style, header=True)
            _draw_round_rect(c, 0, h - hh, w, hh, radii_hdr, fill=self.style.header_bg, stroke=None)
            if hh > radii_hdr[0]:
                c.saveState()
                c.setFillColor(self.style.header_bg)
                c.rect(0, h - hh, w, hh - radii_hdr[0], fill=1, stroke=0)
                c.restoreState()
            inner_w = encadre_inner_width(w, pad_pt=self.pad)
            _, th = self._header_table.wrap(inner_w, hh)
            self._header_table.drawOn(c, self.pad, h - hh + 5.0 + (hh - 10.0 - th) * 0.5)
        y = h - self._hdr_h - self.pad
        for flow, _fw, fh in self._wrapped:
            y -= fh
            flow.drawOn(c, self.pad, y)


def _rasterize_logo(path: Path, height_pt: float, cache_dir: Path) -> Path | None:
    """PNG utilisable par ReportLab (rasterise le SVG OFB si besoin)."""
    if not path.exists():
        return None
    if path.suffix.lower() != ".svg":
        return path
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"brochure_{path.stem}_{int(height_pt)}.png"
    if out.exists():
        return out
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
    except ImportError:
        return None
    drawing = svg2rlg(str(path))
    if not drawing or drawing.height <= 0:
        return None
    scale = float(height_pt) / float(drawing.height)
    drawing.width = float(drawing.width) * scale
    drawing.height = float(height_pt)
    drawing.scale(scale, scale)
    renderPM.drawToFile(drawing, str(out), fmt="PNG", dpi=150)
    return out if out.exists() else None


def _logo_size_pt(path: Path, target_h: float) -> tuple[float, float]:
    with PILImage.open(path) as im:
        ratio = im.width / max(im.height, 1)
    h = float(target_h)
    return h * ratio, h


class BrochureBandeau(Flowable):
    """Bandeau bleu compact (texte seul)."""

    def __init__(
        self,
        width: float,
        flowables: list,
        *,
        pad_pt: float = 2.5 * mm,
    ):
        super().__init__()
        self.box_width = float(width)
        self.flowables = flowables
        self.pad = float(pad_pt)
        self._text_wrapped: list[tuple[Flowable, float, float]] = []
        self.height = 0.0

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        w = min(self.box_width, availWidth)
        self.box_width = w
        text_w = max(40.0, w - 2 * self.pad)
        self._text_wrapped = []
        text_h = 0.0
        for f in self.flowables:
            fw, fh = f.wrap(text_w, availHeight)
            self._text_wrapped.append((f, fw, fh))
            text_h += fh
        self.height = text_h + 2 * self.pad + 2.0
        return (w, self.height)

    def draw(self) -> None:
        c = self.canv
        w, h = self.box_width, self.height
        r = RADIUS_STD_PT + 1.5
        _draw_round_rect(c, 0, 0, w, h, (r, r, r, r), fill=_CLR_PRIMARY, stroke=None)
        y = h - self.pad
        for flow, _fw, fh in self._text_wrapped:
            y -= fh
            flow.drawOn(c, self.pad, y)


class BrochureLogosMarque(Flowable):
    """Bloc RF + OFB (Marianne / Office français de la biodiversité)."""

    def __init__(self, cache_dir: Path):
        super().__init__()
        self.cache_dir = Path(cache_dir)
        self._logos: list[tuple[Path, float, float]] = []
        self.width = 0.0
        self.height = 0.0

    def _prepare(self) -> None:
        self._logos = []
        rf_path = _rasterize_logo(LOGO_RF_PNG, _PAGE1_LOGO_RF_H, self.cache_dir)
        if rf_path:
            self._logos.append((rf_path, *_logo_size_pt(rf_path, _PAGE1_LOGO_RF_H)))
        ofb_src = _rasterize_logo(LOGO_OFB_SVG, _PAGE1_LOGO_OFB_H, self.cache_dir)
        if ofb_src:
            self._logos.append((ofb_src, *_logo_size_pt(ofb_src, _PAGE1_LOGO_OFB_H)))
        self.width = sum(w for _p, w, _h in self._logos)
        if len(self._logos) > 1:
            self.width += _PAGE1_LOGO_GAP * (len(self._logos) - 1)
        self.height = max((h for _p, _w, h in self._logos), default=0.0) + 1.0

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        self._prepare()
        return (min(self.width, availWidth), self.height)

    def draw(self) -> None:
        if not self._logos:
            return
        c = self.canv
        x = 0.0
        y = (self.height - max(h for _p, _w, h in self._logos)) / 2.0
        for path, lw, lh in self._logos:
            c.drawImage(
                str(path),
                x,
                y,
                width=lw,
                height=lh,
                preserveAspectRatio=True,
                mask="auto",
            )
            x += lw + _PAGE1_LOGO_GAP


def append_page1_logos_bas_droite(builder, cache_dir: Path) -> None:
    """Logos RF + OFB alignés en bas à droite de la page 1."""
    logos = BrochureLogosMarque(cache_dir)
    w = builder.avail_w
    lw, lh = logos.wrap(w, builder.avail_h)
    gap_left = max(0.0, w - lw)
    row = Table([["", logos]], colWidths=[gap_left, lw])
    row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    builder.story.append(row)


def encadre_section(
    width: float,
    title: str,
    body: list,
    styles,
    *,
    variant: str = "default",
    col_headers: list[str] | None = None,
    col_width_fracs: list[float] | None = None,
) -> BrochureEncadre:
    style = ENCADRE_SURFACE if variant == "surface" else ENCADRE_SECTION
    return BrochureEncadre(
        width,
        title,
        body,
        style,
        styles=styles,
        col_headers=col_headers,
        col_width_fracs=col_width_fracs,
    )


def kpi_encadre(
    width: float,
    figures: list[tuple[str, str]],
    styles,
) -> Flowable:
    if not figures:
        return Spacer(1, 0)
    n = len(figures)
    inner_w = encadre_inner_width(width, pad_pt=2.5 * mm)
    val_style = ParagraphStyle(
        "BrochureKpiVal",
        parent=styles["KeyFigure"],
        fontSize=16,
        leading=19,
        textColor=rl_colors.HexColor(COLOR_PRIMARY),
        alignment=TA_CENTER,
    )
    lbl_style = ParagraphStyle(
        "BrochureKpiLbl",
        parent=styles["KeyFigureLabel"],
        fontSize=7,
        leading=8.5,
        textColor=_CLR_GREY,
        alignment=TA_CENTER,
    )
    vals = [Paragraph(f"<b>{v}</b>", val_style) for v, _ in figures]
    lbls = [Paragraph(lbl, lbl_style) for _, lbl in figures]
    col_w = inner_w / n
    inner = Table([vals, lbls], colWidths=[col_w] * n)
    inner.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 4),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 4),
                ("LINEAFTER", (0, 0), (-2, -1), 0.4, _CLR_BORDER),
            ]
        )
    )
    return BrochureEncadre(width, None, [inner], ENCADRE_SURFACE, styles=styles, pad_pt=2.5 * mm)


def note_encadre(width: float, html: str, styles) -> BrochureEncadre:
    ps = ParagraphStyle(
        "BrochureNote",
        parent=styles["BodySmall"],
        fontSize=8,
        leading=10.5,
        textColor=_CLR_GREY,
    )
    return BrochureEncadre(
        width,
        None,
        [Paragraph(html, ps)],
        ENCADRE_CALLOUT,
        styles=styles,
        pad_pt=3 * mm,
    )
