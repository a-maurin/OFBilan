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

from core.common.ofb_charte import (
    COLOR_GREY,
    COLOR_PRIMARY,
    COLOR_TABLE_ALT_ROW,
    COLOR_TABLE_BORDER,
    COLOR_TABLE_HEADER_BG,
)

_MODELE_OFB_DIR = Path(__file__).resolve().parents[2] / "ref" / "programme" / "modele_ofb"
LOGO_OFB_INTRANET_BLANC = _MODELE_OFB_DIR / "logo-ofb-intranet_blanc.png"
_BANDEAU_LOGO_H = 9.0 * mm
_BANDEAU_LOGO_GAP = 2.5 * mm

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
    """Largeur utile à l'intérieur d'un encadré (alignée sur le padding du cadre)."""
    return max(30.0, float(outer_w) - 2 * float(pad_pt))


def col_widths_from_fracs(inner_w: float, fracs: list[float]) -> list[float]:
    """Répartit ``inner_w`` selon ``fracs`` (somme exacte pour alignement colonnes)."""
    total = sum(float(f) for f in fracs) or 1.0
    widths = [inner_w * float(f) / total for f in fracs]
    drift = inner_w - sum(widths)
    if widths:
        widths[-1] += drift
    return widths


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
    from core.common.pdf_utils import ofb_table

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
    from core.common.rendus_graphiques import apply_mpl_style

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
        self.hAlign = "LEFT"

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
        self._body_h = body_h + (1.0 if self._wrapped else 0.0)
        self.height = self._hdr_h + self._body_h + 2 * self.pad + 0.5
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


def _logo_size_pt(path: Path, target_h: float) -> tuple[float, float]:
    with PILImage.open(path) as im:
        ratio = im.width / max(im.height, 1)
    h = float(target_h)
    return h * ratio, h


class BrochureBandeau(Flowable):
    """Bandeau bleu compact : texte à gauche, logo OFB optionnel à droite."""

    def __init__(
        self,
        width: float,
        flowables: list,
        *,
        pad_pt: float = _PAD_STD_PT,
        logo_path: Path | None = None,
        logo_height_pt: float = _BANDEAU_LOGO_H,
    ):
        super().__init__()
        self.box_width = float(width)
        self.flowables = flowables
        self.pad = float(pad_pt)
        self.logo_path = Path(logo_path) if logo_path else None
        self.logo_height_pt = float(logo_height_pt)
        self._logo_size: tuple[float, float] = (0.0, 0.0)
        self.hAlign = "LEFT"
        self._text_wrapped: list[tuple[Flowable, float, float]] = []
        self.height = 0.0

    def _reserve_logo(self) -> float:
        if self.logo_path and self.logo_path.exists():
            self._logo_size = _logo_size_pt(self.logo_path, self.logo_height_pt)
            return self._logo_size[0] + _BANDEAU_LOGO_GAP
        self._logo_size = (0.0, 0.0)
        return 0.0

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        w = min(self.box_width, availWidth)
        self.box_width = w
        logo_reserve = self._reserve_logo()
        text_w = max(40.0, w - 2 * self.pad - logo_reserve)
        self._text_wrapped = []
        text_h = 0.0
        for f in self.flowables:
            fw, fh = f.wrap(text_w, availHeight)
            self._text_wrapped.append((f, fw, fh))
            text_h += fh
        self.height = max(text_h + 2 * self.pad + 2.0, self._logo_size[1] + 2 * self.pad + 2.0)
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
        if self._logo_size[0] > 0 and self.logo_path:
            lw, lh = self._logo_size
            lx = w - self.pad - lw
            ly = (h - lh) / 2.0
            c.drawImage(
                str(self.logo_path),
                lx,
                ly,
                width=lw,
                height=lh,
                preserveAspectRatio=True,
                mask="auto",
            )


_CLR_TOTALS_BG = rl_colors.HexColor("#E8EEF4")


def brochure_totaux_band(text_html: str, width: float, styles) -> Table:
    """Bandeau de synthèse pour totaux (fond léger, bordure, texte en gras)."""
    ps = ParagraphStyle(
        "BrochureTotauxBand",
        parent=styles["BodyText"],
        fontName=f"{styles['BodyText'].fontName}-Bold",
        fontSize=9,
        leading=11,
        textColor=_CLR_PRIMARY,
        alignment=TA_RIGHT,
    )
    tbl = Table([[Paragraph(text_html, ps)]], colWidths=[float(width)])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _CLR_TOTALS_BG),
                ("BOX", (0, 0), (-1, -1), 0.6, _CLR_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return tbl


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
    *,
    hero: bool = False,
) -> Flowable:
    if not figures:
        return Spacer(1, 0)
    n = len(figures)
    inner_w = encadre_inner_width(width, pad_pt=_PAD_STD_PT)
    if hero:
        val_style = ParagraphStyle(
            "BrochureKpiHeroVal",
            parent=styles["KeyFigure"],
            fontSize=22,
            leading=26,
            textColor=rl_colors.HexColor(COLOR_PRIMARY),
            alignment=TA_CENTER,
        )
        lbl_style = ParagraphStyle(
            "BrochureKpiHeroLbl",
            parent=styles["KeyFigureLabel"],
            fontSize=8,
            leading=10,
            textColor=_CLR_GREY,
            alignment=TA_CENTER,
        )
        pad_pt = 4.0 * mm
        title = "Chiffres clés"
    else:
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
        pad_pt = _PAD_STD_PT
        title = None
    vals = [Paragraph(f"<b>{v}</b>", val_style) for v, _ in figures]
    lbls = [Paragraph(lbl, lbl_style) for _, lbl in figures]
    col_ws = col_widths_from_fracs(inner_w, [1.0 / n] * n)
    inner = Table([vals, lbls], colWidths=col_ws)
    inner.hAlign = "LEFT"
    inner.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 8 if hero else 4),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8 if hero else 4),
                ("LINEAFTER", (0, 0), (-2, -1), 0.4, _CLR_BORDER),
            ]
        )
    )
    style = ENCADRE_SECTION if hero else ENCADRE_SURFACE
    return BrochureEncadre(width, title, [inner], style, styles=styles, pad_pt=pad_pt)


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
        pad_pt=_PAD_STD_PT,
    )
