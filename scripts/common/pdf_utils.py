"""Helpers reportlab : tableaux OFB, chiffres clés."""
import re

from reportlab.lib import colors as rl_colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from scripts.common.ofb_charte import (
    COLOR_PRIMARY,
    COLOR_TABLE_ALT_ROW,
    COLOR_TABLE_BORDER,
    COLOR_TABLE_HEADER_BG,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    PAGE_W,
    _CELL_HEADER,
    _CELL_HEADER_RIGHT,
    _CELL_NORMAL,
    _CELL_RIGHT,
)

# Largeur utile par défaut pour le calcul des colonnes des tableaux larges
_AVail_W = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT


class VerticalText(Flowable):
    """Texte affiché verticalement (-90°) pour en-têtes de colonnes étroites."""

    def __init__(self, text: str, style=None):
        super().__init__()
        self.text = str(text)
        self.style = style or _CELL_HEADER

    def wrap(self, availWidth: float, availHeight: float):
        try:
            font = pdfmetrics.getFont(self.style.fontName)
            text_width = font.stringWidth(self.text, self.style.fontSize)
        except Exception:
            text_width = len(self.text) * self.style.fontSize * 0.6
        # Après rotation -90°, la largeur du texte devient la hauteur nécessaire.
        self._height = min(availHeight, text_width + 8)
        return (availWidth, self._height)

    def draw(self):
        canv = self.canv
        try:
            font = pdfmetrics.getFont(self.style.fontName)
            text_width = font.stringWidth(self.text, self.style.fontSize)
        except Exception:
            text_width = len(self.text) * self.style.fontSize * 0.6
        canv.saveState()
        canv.setFont(self.style.fontName, self.style.fontSize)
        canv.setFillColor(self.style.textColor)
        # Rotation -90° : on part du bas de la cellule, on tourne, le texte monte.
        canv.translate(4, self._height - 4)
        canv.rotate(-90)
        canv.drawString(0, 0, self.text)
        canv.restoreState()


def ofb_table_wide(
    data_rows: list,
    col_widths=None,
    col_aligns=None,
    avail_w: float = None,
):
    """Tableau OFB avec en-têtes de colonnes 1..n en texte vertical (lisibles quand beaucoup de colonnes).

    data_rows[0] = première ligne (en-têtes) : cellule 0 = Paragraph, cellules 1..n = VerticalText.
    Si col_widths est None, on calcule : première colonne ~28% de avail_w, reste réparti à égalité.
    """
    if not data_rows:
        return Table([], colWidths=[])

    avail_w = avail_w or _AVail_W
    n_cols = max(len(r) for r in data_rows)
    if n_cols == 0:
        return Table([], colWidths=[])

    def _looks_numeric(text: str) -> bool:
        txt = str(text).strip().replace("\u202f", "").replace(" ", "")
        if not txt:
            return False
        if txt.endswith("%"):
            txt = txt[:-1]
        return bool(re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", txt))

    if col_widths is None:
        first_w = avail_w * 0.28
        rest_w = (avail_w - first_w) / max(1, n_cols - 1)
        col_widths = [first_w] + [rest_w] * (n_cols - 1)
    if col_aligns is None:
        right_cols = set()
        for row in data_rows[1:]:
            for ci, cell in enumerate(row):
                if _looks_numeric(str(cell)):
                    right_cols.add(ci)
        col_aligns = [
            "RIGHT" if ci in right_cols else "LEFT"
            for ci in range(n_cols)
        ]

    wrapped = []
    for ri, row in enumerate(data_rows):
        new_row = []
        for ci, cell in enumerate(row):
            cell_str = str(cell) if cell is not None else ""
            if ri == 0:
                if ci == 0:
                    new_row.append(Paragraph(cell_str, _CELL_HEADER))
                else:
                    new_row.append(VerticalText(cell_str, _CELL_HEADER))
            else:
                is_right = col_aligns[ci] == "RIGHT" if ci < len(col_aligns) else False
                style = _CELL_RIGHT if is_right else _CELL_NORMAL
                new_row.append(Paragraph(cell_str, style))
        # Compléter la ligne si nécessaire
        while len(new_row) < n_cols:
            if ri == 0:
                new_row.append(VerticalText("", _CELL_HEADER))
            else:
                new_row.append(Paragraph("", _CELL_NORMAL))
        wrapped.append(new_row)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_TABLE_HEADER_BG),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("LEFTPADDING", (0, 0), (-1, 0), 6),
        ("RIGHTPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("TOPPADDING", (0, 1), (-1, -1), 3),
        ("LEFTPADDING", (0, 1), (-1, -1), 4),
        ("RIGHTPADDING", (0, 1), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_TABLE_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
    ]
    for i in range(1, len(wrapped)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), COLOR_TABLE_ALT_ROW))

    tbl = Table(wrapped, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    return tbl




def ofb_table(
    data_rows,
    col_widths=None,
    col_aligns=None,
    *,
    header_font_size: float | None = None,
):
    """Crée un Table reportlab stylisé charte OFB (en-tête bleu, lignes alternées).

    header_font_size : si renseigné, police des cellules d'en-tête (ligne 0) réduite
    pour limiter le retour à la ligne / la compression visuelle sur tableaux étroits.

    Règle d’alignement :
    - si col_aligns est fourni, il est utilisé tel quel ;
    - sinon, les colonnes dont le contenu est majoritairement numérique
      (nombres, pourcentages) sont automatiquement alignées à droite
      pour l’ensemble du tableau (en-tête compris).
    """

    def _looks_numeric(text: str) -> bool:
        """Heuristique simple pour détecter une valeur chiffrée ou un pourcentage."""
        txt = text.strip().replace("\u202f", "").replace(" ", "")
        if not txt:
            return False
        # Pourcentages du type '12.3%' ou '45 %'
        if txt.endswith("%"):
            txt_num = txt[:-1]
        else:
            txt_num = txt
        # Nombres entiers ou décimaux, éventuellement signés
        return bool(re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", txt_num))

    inferred_aligns = None
    if not col_aligns and data_rows:
        right_cols = set()
        # On analyse uniquement les lignes de données (hors en-tête)
        for row in data_rows[1:]:
            for ci, cell in enumerate(row):
                if isinstance(cell, str) and _looks_numeric(cell):
                    right_cols.add(ci)
        if right_cols:
            max_cols = max(len(r) for r in data_rows)
            inferred_aligns = [
                "RIGHT" if ci in right_cols else "LEFT" for ci in range(max_cols)
            ]

    hdr_left = _CELL_HEADER
    hdr_right = _CELL_HEADER_RIGHT
    if header_font_size is not None:
        fs = float(header_font_size)
        lead = max(fs + 2.0, fs * 1.25)
        hdr_left = ParagraphStyle(
            "CellHeaderCustom",
            parent=_CELL_HEADER,
            fontSize=fs,
            leading=lead,
        )
        hdr_right = ParagraphStyle(
            "CellHeaderRightCustom",
            parent=_CELL_HEADER_RIGHT,
            fontSize=fs,
            leading=lead,
        )

    wrapped = []
    for ri, row in enumerate(data_rows):
        new_row = []
        for ci, cell in enumerate(row):
            if isinstance(cell, str):
                is_right = False
                if col_aligns and ci < len(col_aligns):
                    is_right = col_aligns[ci] == "RIGHT"
                elif inferred_aligns and ci < len(inferred_aligns):
                    is_right = inferred_aligns[ci] == "RIGHT"

                if ri == 0:
                    style = hdr_right if is_right else hdr_left
                else:
                    style = _CELL_RIGHT if is_right else _CELL_NORMAL
                new_row.append(Paragraph(cell, style))
            else:
                new_row.append(cell)
        wrapped.append(new_row)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_TABLE_HEADER_BG),
        # Lignes d'en-tête : padding légèrement réduit pour éviter des hauteurs
        # excessives lorsque les libellés sont courts.
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        # Lignes de données : padding plus serré pour compacter les tableaux.
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("TOPPADDING", (0, 1), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_TABLE_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in range(1, len(wrapped)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), COLOR_TABLE_ALT_ROW))

    tbl = Table(wrapped, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def key_figures_table(figures: list[tuple[str, str]], styles):
    """Bloc de chiffres clés : liste de (valeur, libellé) affichés en ligne."""
    if not figures:
        return Spacer(1, 0)
    header = []
    labels = []
    for val, lbl in figures:
        header.append(Paragraph(f"<b>{val}</b>", styles["KeyFigure"]))
        labels.append(Paragraph(lbl, styles["KeyFigureLabel"]))
    col_w = (PAGE_W - MARGIN_LEFT - MARGIN_RIGHT) / len(figures)
    tbl = Table([header, labels], colWidths=[col_w] * len(figures))
    tbl.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 1, rl_colors.HexColor(COLOR_PRIMARY)),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, COLOR_TABLE_BORDER),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
            ]
        )
    )
    return tbl
