"""Rendu PDF brochure (2 pages A4 paysage).

Couleurs : charte OFB standard (``ofb_charte``).
Formes : encadrés arrondis via ``brochure_charte`` (module brochure uniquement).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage, Paragraph, Spacer, Table, TableStyle

from ofbilan.common.carte_helper import resolve_profile_map_paths
from ofbilan.common.ofb_charte import COLOR_PRIMARY
from ofbilan.common.pdf_presentation_config import (
    apply_diffusion_pdf_suffix,
    normalize_dept_typography,
    resolve_pdf_presentation_config,
)
from ofbilan.common.pdf_report_builder import PDFReportBuilder
from ofbilan.common.pdf_utils import truncate_text_to_width
from ofbilan.common.pdf_table_sort import pdf_metric_caption, sort_dataframe_desc as _sort_desc
from ofbilan.common.percent_format import format_pct_int_from_rate, tab_counts_to_pct_strings
from ofbilan.common.rendus_graphiques import (
    chart_bar_horizontal_stacked,
    chart_pie_legend_right,
)
from ofbilan.engine.brochure_charte import (
    BrochureBandeau,
    LOGO_OFB_INTRANET_BLANC,
    _BANDEAU_LOGO_H,
    _PAD_STD_PT,
    apply_brochure_mpl_style,
    brochure_table,
    brochure_totaux_band,
    col_widths_from_fracs,
    encadre_inner_width,
    encadre_section,
    kpi_encadre,
)
from ofbilan.common.bilan_config import BilanConfig, resolve_perimetre_kwargs
from ofbilan.engine.generation_pdf_synthese import (
    PROFILE_ID,
    _ROOT,
    _build_synthese_key_figure_rows,
    _display_type_usager,
    _KEY_FIGURES_GRAIN_NOTE,
    _load_csv_opt,
    _nb_non_conformes_brut,
    _pie_data_controles_par_type_usager,
    _rollup_small_categories,
)

_BROCHURE_MAX_THEMES = 5
_BROCHURE_MAX_PROC_THEMES = 7
_BROCHURE_MAX_PVE_NATINF = 9
_PAGE2_ENCADRE_OVERHEAD_MM = 14.0
_PAGE2_TABLE_ROW_MM = 5.4
_PAGE2_TABLE_FOOTER_MM = 10.0
_PAGE2_TOP_ROW_MAX_RATIO = 0.44
_PAGE2_BOTTOM_ROW_CAP = 7
_BROCHURE_MAX_USAGER_TYPES = 5
_BROCHURE_USAGER_MIN_SHARE = 0.02
_BROCHURE_MAX_RESULT_USAGER_TYPES = 7
_BROCHURE_RESULT_USAGER_MIN_SHARE = 0.01

BROCHURE_PAGE_SIZE = landscape(A4)
_GRID_GAP_MM = 10.0
_PAGE1_LOWER_GAP_MM = 6.0
_BROCHURE_SECTION_GAP_MM = 2.8
_PAGE1_KPI_HERO_RATIO = 0.36
_PAGE1_KPI_HERO_RATIO_WITH_MAPS = 0.28
_PAGE1_LOWER_SYNTH_RATIO = 0.32
_PAGE1_MAP_ENCADRE_OVERHEAD_MM = 13.0
_PAGE2_CHART_HERO_RATIO = 0.48
_PAGE2_LOWER_LEFT_RATIO = 0.40
_PAGE2_PROC_WIDTH_RATIO = 0.25
_PAGE2_TOP_PIE_RATIO = 0.50
_PAGE2_PIE_LEGEND_FONTSIZE = 10.0
_PAGE2_METHODO_MM = 9.0
_COL_LEFT_RATIO = 0.58


def _truncate_theme(label: str, max_len: int = 34) -> str:
    txt = str(label or "").strip()
    if len(txt) <= max_len:
        return txt
    return txt[: max_len - 1].rstrip() + "…"


def _rollup_usager_types(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty or "nb_total" not in df.columns:
        return df
    work = df.copy()
    work["nb_total"] = work["nb_total"].astype(float)
    total = float(work["nb_total"].sum())
    if total <= 0:
        return work
    rows: list[dict] = []
    autres_ctrl = 0.0
    autres_pej = 0.0
    for _, row in work.iterrows():
        share = float(row["nb_total"]) / total
        if share >= _BROCHURE_USAGER_MIN_SHARE and len(rows) < _BROCHURE_MAX_USAGER_TYPES - 1:
            rows.append(row.to_dict())
        else:
            autres_ctrl += float(row.get("nb_effectifs", row.get("nb_total", 0)) or 0)
            autres_pej += float(row.get("nb_pej_hors_controle", 0) or 0)
    if autres_ctrl + autres_pej > 0 or len(rows) >= _BROCHURE_MAX_USAGER_TYPES:
        rows.append(
            {
                "type_usager": "Autres",
                "nb_effectifs": int(autres_ctrl),
                "nb_pej_hors_controle": int(autres_pej),
                "nb_total": int(autres_ctrl + autres_pej),
            }
        )
    return pd.DataFrame(rows)


def _rollup_resultats_usager(
    df: pd.DataFrame | None,
    *,
    min_share: float = _BROCHURE_USAGER_MIN_SHARE,
    max_types: int = _BROCHURE_MAX_USAGER_TYPES,
) -> pd.DataFrame | None:
    if df is None or df.empty:
        return df
    work = df.copy()
    for col in ("Conforme", "Infraction", "Manquement", "Autre_resultat", "Total"):
        if col in work.columns:
            work[col] = work[col].astype(int)
    total_all = float(work["Total"].sum()) if "Total" in work.columns else 0.0
    if total_all <= 0:
        return work.head(max_types)
    kept: list[pd.Series] = []
    autres: dict[str, int] = {
        "Conforme": 0,
        "Infraction": 0,
        "Manquement": 0,
        "Autre_resultat": 0,
        "Total": 0,
    }
    for _, row in work.iterrows():
        t = int(row.get("Total", 0) or 0)
        if t / total_all >= min_share and len(kept) < max_types - 1:
            kept.append(row)
        else:
            for k in autres:
                if k in row.index:
                    autres[k] += int(row.get(k, 0) or 0)
    if autres["Total"] > 0:
        kept.append(pd.Series({**{"type_usager": "Autres"}, **autres}))
    return pd.DataFrame(kept)


def _flatten_key_figures(figure_rows: list[list[tuple[str, str]]]) -> list[tuple[str, str]]:
    flat: list[tuple[str, str]] = []
    for row in figure_rows:
        flat.extend(row)
    return flat


_BROCHURE_THEME_COL_FRACS = [0.64, 0.12, 0.24]
_BROCHURE_RESULT_COL_FRACS = [0.60, 0.12, 0.28]
_BROCHURE_PROC_COL_FRACS = [0.58, 0.21, 0.21]
_BROCHURE_PVE_NATINF_COL_FRACS = [0.76, 0.24]


def _build_rows_resultats_brochure(tr: pd.DataFrame | None) -> list[list[str]]:
    if tr is None or tr.empty:
        return [["—", "0", "n.d."]]
    strip_res = tr["resultat"].astype(str).str.strip()
    labels = ("Conforme", "Non-conforme", "En attente")
    counts: list[int] = []
    rows_out: list[list[str]] = []
    for label in labels:
        sub = tr.loc[strip_res == label]
        if sub.empty:
            continue
        counts.append(int(sub.iloc[0]["nb"]))
        rows_out.append([label, str(int(sub.iloc[0]["nb"])), ""])
    if counts:
        rates = tab_counts_to_pct_strings(counts)
        for i, row in enumerate(rows_out):
            if i < len(rates):
                row[2] = rates[i]
    return rows_out or [["—", "0", "n.d."]]


def _grid_columns(builder: PDFReportBuilder, left_ratio: float = _COL_LEFT_RATIO) -> tuple[float, float, float]:
    """Largeurs gauche | intercolonne | droite = zone utile (alignement strict)."""
    gap = _GRID_GAP_MM * mm
    inner = builder.avail_w - gap
    left_w = inner * left_ratio
    right_w = inner - left_w
    return left_w, gap, right_w


def _page1_lower_columns(builder: PDFReportBuilder) -> tuple[float, float, float]:
    """Colonnes bande basse page 1 : synthèse + carte ; bord droit carte = bord droit chiffres clés."""
    avail = builder.avail_w
    gap = _PAGE1_LOWER_GAP_MM * mm
    inner = avail - gap
    synth_w = inner * _PAGE1_LOWER_SYNTH_RATIO
    map_w = inner - synth_w
    widths = col_widths_from_fracs(avail, [synth_w, gap, map_w])
    return widths[0], widths[1], widths[2]


def _page2_lower_columns(
    builder: PDFReportBuilder, left_ratio: float = _PAGE2_LOWER_LEFT_RATIO
) -> tuple[float, float, float]:
    """Colonnes bas de page 2 ; bord droit procédures = bord droit graphique usagers."""
    avail = builder.avail_w
    gap = _PAGE1_LOWER_GAP_MM * mm
    inner = avail - gap
    left_w = inner * left_ratio
    right_w = inner - left_w
    widths = col_widths_from_fracs(avail, [left_w, gap, right_w])
    return widths[0], widths[1], widths[2]


def _content_height_mm(builder: PDFReportBuilder) -> float:
    return builder.avail_h / mm


def _layout_page1_heights(
    builder: PDFReportBuilder, *, has_maps: bool
) -> tuple[float, float]:
    """Hauteurs mm : bande KPI héros, bande basse (tableaux + carte)."""
    fixed_mm = 14.0 + 2 * _BROCHURE_SECTION_GAP_MM
    content_mm = max(80.0, _content_height_mm(builder) - fixed_mm)
    kpi_ratio = _PAGE1_KPI_HERO_RATIO_WITH_MAPS if has_maps else _PAGE1_KPI_HERO_RATIO
    kpi_mm = content_mm * kpi_ratio
    return kpi_mm, content_mm - kpi_mm


def _page1_map_image_height_mm(builder: PDFReportBuilder, kpi_mm: float) -> float:
    """Hauteur cible (mm) des images carto pour remplir le bas de page 1."""
    content_mm = _content_height_mm(builder)
    top_mm = 14.0 + kpi_mm + 2 * _BROCHURE_SECTION_GAP_MM + _PAGE1_MAP_ENCADRE_OVERHEAD_MM
    return max(48.0, content_mm - top_mm)


def _layout_page2_usager_chart_mm(builder: PDFReportBuilder, n_rows: int) -> float:
    """Hauteur encadré graphique usagers : plafond page + cible selon le nombre de lignes."""
    fixed_mm = 8.0 + 2 * _BROCHURE_SECTION_GAP_MM + 7.0
    content_mm = max(80.0, _content_height_mm(builder) - fixed_mm)
    n = max(1, int(n_rows))
    encadre_hdr_mm = 11.0
    row_mm = 6.0
    legend_mm = 13.0
    target_mm = encadre_hdr_mm + 8.0 + n * row_mm + legend_mm
    cap_mm = content_mm * _PAGE2_CHART_HERO_RATIO
    return max(30.0, min(cap_mm, target_mm, content_mm - 28.0))


def _layout_page2_heights(
    builder: PDFReportBuilder, n_usager_rows: int, *, with_pve_band: bool
) -> tuple[float, float]:
    """Répartit toute la hauteur utile : bande haute (graphiques) + bande basse (tableaux)."""
    del with_pve_band
    fixed_mm = 8.0 + 3 * _BROCHURE_SECTION_GAP_MM + _PAGE2_METHODO_MM
    content_mm = max(80.0, _content_height_mm(builder) - fixed_mm)
    chart_mm = _layout_page2_usager_chart_mm(builder, n_usager_rows) + 6.0
    top_mm = min(content_mm * _PAGE2_TOP_ROW_MAX_RATIO, chart_mm)
    top_mm = max(34.0, top_mm)
    bottom_mm = max(40.0, content_mm - top_mm - _BROCHURE_SECTION_GAP_MM)
    return top_mm, bottom_mm


def _page2_table_row_cap(height_mm: float, *, with_footer: bool) -> int:
    footer_mm = _PAGE2_TABLE_FOOTER_MM if with_footer else 0.0
    usable = height_mm - _PAGE2_ENCADRE_OVERHEAD_MM - footer_mm
    est = max(3, int(usable / _PAGE2_TABLE_ROW_MM))
    return min(_PAGE2_BOTTOM_ROW_CAP, est)


def _page2_chart_figsize_in(
    inner_w_pt: float, inner_h_pt: float, *, legend_right: bool
) -> tuple[float, float]:
    w_in = max(3.8, float(inner_w_pt) / 72.0 * 0.99)
    h_in = max(2.4, float(inner_h_pt) / 72.0 * (0.90 if legend_right else 0.82))
    return w_in, h_in


def _page2_top_columns(builder: PDFReportBuilder) -> tuple[float, float, float]:
    """Moitié gauche : pression d'activité ; moitié droite : résultats par type d'usager."""
    avail = builder.avail_w
    gap = _PAGE1_LOWER_GAP_MM * mm
    inner = avail - gap
    pie_w = inner * _PAGE2_TOP_PIE_RATIO
    result_w = inner - pie_w
    widths = col_widths_from_fracs(avail, [pie_w, gap, result_w])
    return widths[0], widths[1], widths[2]


def _page2_proc_column_width(builder: PDFReportBuilder) -> float:
    """Largeur du bloc procédures (moitié de l'ancienne colonne 40 %)."""
    avail = builder.avail_w
    gap = _PAGE1_LOWER_GAP_MM * mm
    inner = avail - gap
    return inner * _PAGE2_PROC_WIDTH_RATIO


def _page2_bottom_proc_pve_columns(builder: PDFReportBuilder) -> tuple[float, float, float]:
    """Procédures (largeur fixe) + PVe (reste de la page, libellés NATINF plus longs)."""
    avail = builder.avail_w
    gap = _PAGE1_LOWER_GAP_MM * mm
    proc_w = _page2_proc_column_width(builder)
    pve_w = avail - gap - proc_w
    widths = col_widths_from_fracs(avail, [proc_w, gap, pve_w])
    return widths[0], widths[1], widths[2]


def _brochure_usager_figure_scale(n_rows: int) -> float:
    n = max(1, int(n_rows))
    return min(0.52, max(0.32, 0.30 + 0.028 * n))


def _format_pve_natinf_label(row: pd.Series) -> str:
    libelle = row.get("libelle_natinf") or row.get("LIBELLE_NATINF") or ""
    code = str(row.get("numero_natinf") or row.get("natinf") or "").strip()
    if libelle:
        return f"{code} – {libelle}" if code else str(libelle)
    return code or "—"


def _build_pve_natinf_table_brochure(
    pve_natinf: pd.DataFrame | None, inner_w: float, *, max_rows: int
) -> Table:
    col_widths = col_widths_from_fracs(inner_w, _BROCHURE_PVE_NATINF_COL_FRACS)
    label_w = col_widths[0]
    cap = max(1, min(int(max_rows), _BROCHURE_MAX_PVE_NATINF))
    rows: list[list[str]] = []
    if pve_natinf is not None and not pve_natinf.empty:
        for _, row in pve_natinf.head(cap).iterrows():
            rows.append(
                [
                    truncate_text_to_width(_format_pve_natinf_label(row), label_w),
                    str(int(row["nb"])),
                ]
            )
    else:
        rows.append(["—", "0"])
    return brochure_table(
        rows,
        col_widths=col_widths,
        col_aligns=["LEFT", "RIGHT"],
        split_by_row=False,
        header_row=False,
    )


def _build_procedures_table_brochure(
    proc_theme: pd.DataFrame | None, inner_w: float, *, max_rows: int
) -> Table:
    """PEJ et PA par thème OSCEAN (les PVe sont dans un bloc dédié, cf. § 4 du rapport détaillé)."""
    cap = max(1, min(int(max_rows), _BROCHURE_MAX_PROC_THEMES))
    rows: list[list[str]] = []
    if proc_theme is not None and not proc_theme.empty:
        for _, row in proc_theme.head(cap).iterrows():
            rows.append(
                [
                    _truncate_theme(row["theme"], 32),
                    str(int(row.get("nb_pej", 0))),
                    str(int(row.get("nb_pa", 0))),
                ]
            )
    else:
        rows.append(["—", "0", "0"])
    return brochure_table(
        rows,
        col_widths=col_widths_from_fracs(inner_w, _BROCHURE_PROC_COL_FRACS),
        col_aligns=["LEFT", "RIGHT", "RIGHT"],
        split_by_row=False,
        header_row=False,
    )


def _build_themes_table_brochure(
    labels: list[str],
    values: list[int],
    inner_w: float,
    *,
    total_value: int,
) -> Table:
    rows: list[list[str]] = []
    for lb, v, pct in zip(labels, values, _theme_pct_strings_brochure(values, total_value=total_value)):
        rows.append([_truncate_theme(lb, 30), str(int(v)), pct])
    return brochure_table(
        rows,
        col_widths=col_widths_from_fracs(inner_w, _BROCHURE_THEME_COL_FRACS),
        col_aligns=["LEFT", "RIGHT", "RIGHT"],
        split_by_row=False,
        header_row=False,
    )


def _theme_pct_strings_brochure(values: list[int], *, total_value: int) -> list[str]:
    return [
        format_pct_int_from_rate((int(value) / int(total_value)) if total_value > 0 else None)
        for value in values
    ]


def _append_dual_panels(
    builder: PDFReportBuilder,
    *,
    left_panel,
    right_panel,
    left_ratio: float = _COL_LEFT_RATIO,
) -> None:
    left_w, gap_w, right_w = _grid_columns(builder, left_ratio)
    row = Table([[left_panel, "", right_panel]], colWidths=[left_w, gap_w, right_w])
    row.hAlign = "LEFT"
    row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    builder.story.append(row)


def _append_page2_lower_band(
    builder: PDFReportBuilder,
    *,
    left_panel,
    right_panel,
    left_ratio: float = _PAGE2_LOWER_LEFT_RATIO,
) -> None:
    """Bande basse page 2 alignée sur la largeur utile (comme le bloc usagers)."""
    left_w, gap_w, right_w = _page2_lower_columns(builder, left_ratio)
    left_panel.hAlign = "LEFT"
    right_panel.hAlign = "LEFT"
    row = Table([[left_panel, "", right_panel]], colWidths=[left_w, gap_w, right_w])
    row.hAlign = "LEFT"
    row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    builder.story.append(row)


def _append_page2_row(
    builder: PDFReportBuilder,
    panels: list,
    col_widths: list[float],
) -> None:
    cells = []
    for i, panel in enumerate(panels):
        if i > 0:
            cells.append("")
        panel.hAlign = "LEFT"
        cells.append(panel)
    row = Table([cells], colWidths=col_widths)
    row.hAlign = "LEFT"
    row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    builder.story.append(row)


def _append_spacer(builder: PDFReportBuilder, mm_h: float = 1.5) -> None:
    builder.story.append(Spacer(1, mm_h * mm))


def _append_bandeau(builder: PDFReportBuilder, dept: str, period: str) -> None:
    """Bandeau bleu OFB à coins arrondis."""
    title_style = ParagraphStyle(
        "BrochureBandeauTitle",
        parent=builder.styles["BodyText"],
        fontName=f"{builder.styles['BodyText'].fontName}-Bold",
        fontSize=13,
        leading=16,
        textColor=rl_colors.white,
    )
    bandeau = BrochureBandeau(
        builder.avail_w,
        [
            Paragraph(
                f"<b>Synthèse PA/PJ</b> — {dept} — <font color='#C5D9ED'>{period}</font>",
                title_style,
            ),
        ],
        pad_pt=2.5 * mm,
        logo_path=LOGO_OFB_INTRANET_BLANC,
        logo_height_pt=_BANDEAU_LOGO_H,
    )
    builder.story.append(bandeau)


def _append_kpi_strip(
    builder: PDFReportBuilder,
    figures: list[tuple[str, str]],
    *,
    hero: bool = False,
) -> None:
    kpi = kpi_encadre(builder.avail_w, figures, builder.styles, hero=hero)
    kpi.hAlign = "LEFT"
    builder.story.append(kpi)


def _image_fit(
    builder: PDFReportBuilder,
    path: Path,
    *,
    max_width: float,
    max_height: float,
    scale_to_fill: bool = False,
    prioritize_width: bool = False,
) -> RLImage | str:
    if not path.exists():
        return ""
    ratio = builder._image_aspect_ratio(path)
    if ratio <= 0:
        ratio = 1.0
    w = max_width
    h = w * ratio
    if h > max_height:
        h = max_height
        w = h / ratio
    elif scale_to_fill and h < max_height * 0.92:
        h_target = max_height
        w_fill = h_target / ratio
        if w_fill <= max_width:
            w, h = w_fill, h_target
        else:
            w = max_width
            h = w * ratio
    elif prioritize_width and w < max_width * 0.97:
        w = max_width
        h = w * ratio
        if h > max_height:
            h = max_height
            w = h / ratio
    img = RLImage(str(path), width=w, height=h)
    img.hAlign = "LEFT"
    return img


def _build_maps_body(
    builder: PDFReportBuilder,
    paths: list[Path],
    *,
    inner_w: float,
    max_height_mm: float,
) -> list:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return []
    max_h = max_height_mm * mm
    gap = _PAGE1_LOWER_GAP_MM * mm
    if len(existing) == 1:
        img = _image_fit(
            builder,
            existing[0],
            max_width=inner_w,
            max_height=max_h,
            scale_to_fill=True,
        )
        return [img] if img else []
    col_w = (inner_w - gap) / 2.0
    imgs = [
        _image_fit(
            builder,
            p,
            max_width=col_w,
            max_height=max_h,
            scale_to_fill=True,
        )
        for p in existing[:2]
    ]
    maps_tbl = Table([imgs], colWidths=[col_w, col_w])
    maps_tbl.hAlign = "LEFT"
    maps_tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return [maps_tbl]


def _append_page1_lower_band(
    builder: PDFReportBuilder,
    *,
    left_panel,
    right_panel,
    maps_paths: list[Path],
    lower_mm: float,
    map_height_mm: float,
    has_maps: bool,
) -> None:
    """Bande basse page 1 : synthèse (gauche) + cartographie secondaire (droite)."""
    if has_maps:
        left_w, gap_w, right_w = _page1_lower_columns(builder)
        map_h_mm = max(map_height_mm, lower_mm * 0.88)
        maps_body = _build_maps_body(
            builder,
            maps_paths,
            inner_w=encadre_inner_width(right_w, pad_pt=_PAD_STD_PT),
            max_height_mm=map_h_mm,
        )
        if maps_body:
            map_panel = encadre_section(
                right_w,
                "Cartographie de l'activité",
                maps_body,
                builder.styles,
                variant="default",
            )
            map_panel.hAlign = "LEFT"
            left_stack = Table([[left_panel], [right_panel]], colWidths=[left_w])
            left_stack.hAlign = "LEFT"
            left_stack.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (0, 0), 2 * mm),
                    ]
                )
            )
            row = Table([[left_stack, "", map_panel]], colWidths=[left_w, gap_w, right_w])
            row.hAlign = "LEFT"
            row.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            builder.story.append(row)
            return
    for panel in (left_panel, right_panel):
        panel.hAlign = "LEFT"
    _append_dual_panels(builder, left_panel=left_panel, right_panel=right_panel)


def _append_methodology_footer(builder: PDFReportBuilder, html: str) -> None:
    ps = ParagraphStyle(
        "BrochureMethodoFooter",
        parent=builder.styles["BodySmall"],
        fontSize=7.5,
        leading=9.5,
        textColor=rl_colors.HexColor("#6B7280"),
    )
    para = Paragraph(html, ps)
    para.hAlign = "LEFT"
    builder.story.append(para)


def _brochure_methodology_html(
    *,
    date_deb: pd.Timestamp,
    date_fin: pd.Timestamp,
    ventilation_mode: str,
    diffusion: str,
) -> str:
    diff = "externe" if str(diffusion).strip().lower() in ("externe", "external", "ext") else "interne"
    return (
        "<i><b>Méthodologie.</b> Sources OSCEAN (points de contrôle, PEJ, PA) et PVe OFB — "
        f"période du {date_deb.date():%d/%m/%Y} au {date_fin.date():%d/%m/%Y} — "
        f"ventilation {ventilation_mode} — diffusion {diff} — "
        "effectifs d'usagers contrôlés (chaque usager sur une fiche) ; "
        "contrôles = localisations OSCEAN ; "
        "PEJ = suite à contrôle et saisines hors fiche contrôle. — "
        "<b>Réalisation :</b> service départemental de la Côte d'Or.</i>"
    )


def generate_synthese_brochure_pdf_report(
    out_dir: Path,
    *,
    profile: dict | None = None,
    date_deb: str | pd.Timestamp | None = None,
    date_fin: str | pd.Timestamp | None = None,
    echelle: str | None = None,
    code: str | None = None,
    dept_code: str | None = None,
    ventilation_mode: str = "globale",
    chart_preset: str | None = None,
    output_filename: str | None = None,
    diffusion: str = "externe",
    cartes: bool = True,
    brochure: bool = True,
) -> None:
    del chart_preset, brochure
    apply_brochure_mpl_style()
    profile = profile or {"id": PROFILE_ID}
    date_deb_ts = pd.to_datetime(date_deb) if date_deb is not None else pd.Timestamp("2025-01-01")
    date_fin_ts = pd.to_datetime(date_fin) if date_fin is not None else pd.Timestamp("2026-02-05")
    echelle_res, code_res = resolve_perimetre_kwargs(
        echelle=echelle, code=code, dept_code=dept_code
    )
    _generate_synthese_brochure_pdf(
        out_dir,
        profile=profile,
        date_deb=date_deb_ts,
        date_fin=date_fin_ts,
        echelle=echelle_res,
        code=code_res,
        ventilation_mode=str(ventilation_mode or "globale"),
        output_filename=output_filename,
        diffusion=diffusion,
        cartes=cartes,
    )


def _generate_synthese_brochure_pdf(
    out_dir: Path,
    *,
    profile: dict,
    date_deb: pd.Timestamp,
    date_fin: pd.Timestamp,
    echelle: str,
    code: str,
    ventilation_mode: str,
    output_filename: str | None,
    diffusion: str,
    cartes: bool,
) -> None:
    profil_id = str(profile.get("id", PROFILE_ID))
    scope = str(profile.get("presentation_scope", "global")).strip() or "global"
    resolved = resolve_pdf_presentation_config(
        _ROOT, scope=scope, profile_id=profil_id, diffusion=diffusion
    )
    presentation_cfg = resolved.get("effective", {}) if isinstance(resolved, dict) else {}

    cfg = BilanConfig.from_strings(
        str(date_deb.date()),
        str(date_fin.date()),
        echelle=echelle,
        code=code,
        root=_ROOT,
    )
    dept_name_typo = (
        normalize_dept_typography(cfg.perimetre_name)
        if cfg.echelle == "departement"
        else cfg.perimetre_name
    )
    report_header = f"Synthèse PA/PJ — {dept_name_typo}"
    period_str = f"du {date_deb.date():%d/%m/%Y} au {date_fin.date():%d/%m/%Y}"

    act_theme = _sort_desc(_load_csv_opt(out_dir, "synthese_activite_par_theme.csv"), ["nb_total"])
    proc_theme = _sort_desc(_load_csv_opt(out_dir, "synthese_procedures_par_theme.csv"), ["nb_pej"])
    pve_natinf = _sort_desc(_load_csv_opt(out_dir, "pve_global_par_natinf.csv"), ["nb"])
    act_par_type = _sort_desc(
        _load_csv_opt(out_dir, "synthese_activite_par_type_usager.csv"), ["nb_total"]
    )
    tab_res_ctrl = _load_csv_opt(out_dir, "controles_global_resultats_controles.csv")
    tab_resultats = _load_csv_opt(out_dir, "controles_global_resultats.csv")
    res_usager = _sort_desc(
        _load_csv_opt(out_dir, "synthese_resultats_usager_effectifs.csv"),
        ["Total", "Conforme", "Infraction", "Manquement"],
    )
    resume = _load_csv_opt(out_dir, "synthese_resume.csv")
    pej_resume = _load_csv_opt(out_dir, "pej_global_resume.csv")
    pa_resume = _load_csv_opt(out_dir, "pa_global_resume.csv")
    pve_resume = _load_csv_opt(out_dir, "pve_global_resume.csv")

    nb_localisations = int(resume.iloc[0]["nb_localisations"]) if resume is not None and not resume.empty else 0
    nb_operations_controle = int(resume.iloc[0]["nb_operations_controle"]) if resume is not None and not resume.empty and "nb_operations_controle" in resume.columns else 0
    nb_pej = int(pej_resume.iloc[0]["nb_pej_global"]) if pej_resume is not None and not pej_resume.empty else 0
    nb_pa = int(pa_resume.iloc[0]["nb_pa_global"]) if pa_resume is not None and not pa_resume.empty else 0
    nb_pve = int(pve_resume.iloc[0]["nb_pve_global"]) if pve_resume is not None and not pve_resume.empty else 0
    res_usager_roll = _rollup_resultats_usager(res_usager)
    nb_effectifs = (
        int(res_usager_roll["Total"].sum())
        if res_usager_roll is not None and not res_usager_roll.empty and "Total" in res_usager_roll.columns
        else 0
    )
    nb_nc = _nb_non_conformes_brut(tab_resultats) if nb_localisations > 0 else 0

    map_paths: list[Path] = []
    if cartes:
        map_id = str(profile.get("_map_id") or profil_id)
        map_paths = [
            Path(p) for p in resolve_profile_map_paths(
                map_id, profile=profile, presentation_cfg=presentation_cfg
            )
            if p and Path(p).exists()
        ][:2]
    has_maps = bool(map_paths)

    base_name = output_filename or f"{profil_id}.pdf"
    stem = Path(base_name).stem
    if not stem.endswith("_brochure"):
        stem = f"{stem}_brochure"
    pdf_path = apply_diffusion_pdf_suffix(out_dir / f"{stem}.pdf", diffusion)

    builder = PDFReportBuilder(
        pdf_path=pdf_path,
        header_title=report_header,
        title=report_header,
        author="Office français de la biodiversité",
        diffusion=diffusion,
        content_only=True,
        pagesize=BROCHURE_PAGE_SIZE,
        margin_bottom=10 * mm,
    )
    kpi_mm, lower_mm = _layout_page1_heights(builder, has_maps=has_maps)
    map_height_mm = _page1_map_image_height_mm(builder, kpi_mm) if has_maps else 0.0
    tmp_dir = builder.tmp_dir

    # ── Page 1 : héros = chiffres clés ──
    _append_bandeau(builder, dept_name_typo, period_str)
    _append_spacer(builder, _BROCHURE_SECTION_GAP_MM)

    kf_rows = _build_synthese_key_figure_rows(
        nb_effectifs=nb_effectifs,
        nb_operations_controle=nb_operations_controle,
        nb_localisations=nb_localisations,
        nb_nc=nb_nc,
        nb_pej=nb_pej,
        nb_pa=nb_pa,
        nb_pve=nb_pve,
    )
    _append_kpi_strip(builder, _flatten_key_figures(kf_rows), hero=True)
    builder.add_paragraph(_KEY_FIGURES_GRAIN_NOTE)
    _append_spacer(builder, _BROCHURE_SECTION_GAP_MM)

    if has_maps:
        themes_w, _, _map_w = _page1_lower_columns(builder)
        results_w = themes_w
    else:
        themes_w, _, results_w = _grid_columns(builder, _COL_LEFT_RATIO)

    inner_themes = encadre_inner_width(themes_w, pad_pt=_PAD_STD_PT)
    inner_results = encadre_inner_width(results_w, pad_pt=_PAD_STD_PT)
    themes_body: list = []
    act_theme_display = _rollup_small_categories(
        act_theme,
        label_col="theme",
        other_label="Autres thèmes de contrôle",
        value_col="nb_total",
        min_pct=0.01,
        sum_cols=["nb_localisations", "nb_pej_hors_controle", "nb_total"],
    )
    act_theme_total = int(act_theme["nb_total"].sum()) if act_theme is not None and not act_theme.empty else 0
    if act_theme_display is not None and not act_theme_display.empty:
        sub = act_theme_display
        if len(sub) > _BROCHURE_MAX_THEMES:
            has_other_row = str(sub.iloc[-1].get("theme", "")).strip() == "Autres thèmes de contrôle"
            if has_other_row and _BROCHURE_MAX_THEMES > 1:
                sub = pd.concat(
                    [sub.head(_BROCHURE_MAX_THEMES - 1), sub.tail(1)],
                    ignore_index=True,
                )
            else:
                sub = sub.head(_BROCHURE_MAX_THEMES)
        labels = [_truncate_theme(r["theme"]) for _, r in sub.iterrows()]
        values = [int(r["nb_total"]) for _, r in sub.iterrows()]
        themes_body = [
            _build_themes_table_brochure(
                labels,
                values,
                inner_themes,
                total_value=act_theme_total,
            )
        ]

    res_tbl = _build_rows_resultats_brochure(tab_res_ctrl)
    res_table = brochure_table(
        res_tbl,
        col_widths=col_widths_from_fracs(inner_results, _BROCHURE_RESULT_COL_FRACS),
        col_aligns=["LEFT", "RIGHT", "RIGHT"],
        split_by_row=False,
        header_row=False,
    )
    themes_panel = encadre_section(
        themes_w,
        "Principaux thèmes d'activité",
        themes_body,
        builder.styles,
        col_headers=["Nb", "Taux"],
        col_width_fracs=_BROCHURE_THEME_COL_FRACS,
    )
    results_panel = encadre_section(
        results_w,
        "Résultats des contrôles",
        [res_table],
        builder.styles,
        variant="surface",
        col_headers=["Nb", "Taux"],
        col_width_fracs=_BROCHURE_RESULT_COL_FRACS,
    )
    themes_panel.hAlign = "LEFT"
    results_panel.hAlign = "LEFT"

    if has_maps:
        _append_page1_lower_band(
            builder,
            left_panel=themes_panel,
            right_panel=results_panel,
            maps_paths=map_paths,
            lower_mm=lower_mm,
            map_height_mm=map_height_mm,
            has_maps=True,
        )
    else:
        _append_page1_lower_band(
            builder,
            left_panel=themes_panel,
            right_panel=results_panel,
            maps_paths=[],
            lower_mm=lower_mm,
            map_height_mm=0.0,
            has_maps=False,
        )
        _append_spacer(builder, _BROCHURE_SECTION_GAP_MM)
        _append_methodology_footer(
            builder,
            "<i>Cartographie : cartes non disponibles "
            "(fichiers attendus dans data/out/generateur_de_cartes/).</i>",
        )

    builder.add_page_break()

    # ── Page 2 : bande haute (pression | résultats) + bande basse (proc | PVe) ──
    res_usager_plot = _rollup_resultats_usager(
        res_usager,
        min_share=_BROCHURE_RESULT_USAGER_MIN_SHARE,
        max_types=_BROCHURE_MAX_RESULT_USAGER_TYPES,
    )
    n_usager_rows = (
        len(res_usager_plot)
        if res_usager_plot is not None and not res_usager_plot.empty
        else 0
    )
    show_pve_band = nb_pve > 0 and pve_natinf is not None and not pve_natinf.empty
    top_p2_mm, bottom_p2_mm = _layout_page2_heights(
        builder,
        n_usager_rows,
        with_pve_band=show_pve_band,
    )
    pie_w, top_gap, result_w = _page2_top_columns(builder)
    proc_w = _page2_proc_column_width(builder)
    if show_pve_band:
        proc_w, bottom_gap, pve_w = _page2_bottom_proc_pve_columns(builder)
    else:
        bottom_gap = top_gap
        pve_w = 0.0

    top_body_mm = max(28.0, top_p2_mm - _PAGE2_ENCADRE_OVERHEAD_MM)
    top_img_h = top_body_mm * mm
    result_inner_w = encadre_inner_width(result_w, pad_pt=_PAD_STD_PT)
    result_fig_w_in, result_fig_h_in = _page2_chart_figsize_in(
        result_inner_w, top_img_h, legend_right=True
    )

    pie_body: list = []
    pie_data = _pie_data_controles_par_type_usager(_rollup_usager_types(act_par_type))
    if pie_data:
        chart_path = Path(
            chart_pie_legend_right(
                pie_data,
                "",
                tmp_dir,
                "brochure_pie_usagers.png",
                legend_percent_only=True,
                figure_scale=min(0.88, 0.58 + top_p2_mm * 0.004),
                legend_fontsize=_PAGE2_PIE_LEGEND_FONTSIZE,
            )
        )
        img = _image_fit(
            builder,
            chart_path,
            max_width=encadre_inner_width(pie_w, pad_pt=_PAD_STD_PT),
            max_height=top_img_h,
            scale_to_fill=True,
        )
        if img:
            pie_body = [img]

    result_chart_body: list = []
    if res_usager_plot is not None and not res_usager_plot.empty:
        labels = [_truncate_theme(_display_type_usager(x), 20) for x in res_usager_plot["type_usager"]]
        series: dict[str, list[int]] = {
            "Conforme": [int(x) for x in res_usager_plot["Conforme"].tolist()],
            "Infraction": [int(x) for x in res_usager_plot["Infraction"].tolist()],
            "Manquement": [int(x) for x in res_usager_plot["Manquement"].tolist()],
        }
        if "Autre_resultat" in res_usager_plot.columns and int(res_usager_plot["Autre_resultat"].sum()) > 0:
            series["En attente"] = [int(x) for x in res_usager_plot["Autre_resultat"].tolist()]
        chart_path = Path(
            chart_bar_horizontal_stacked(
                labels,
                series,
                "",
                "",
                tmp_dir,
                "brochure_resultats_usager.png",
                figure_scale=1.0,
                show_title=False,
                legend_below=False,
                legend_right=True,
                legend_fontsize=7.5,
                brochure_narrow=True,
                figure_width_in=result_fig_w_in,
                figure_height_in=result_fig_h_in,
                plot_area_scale=1.5,
                x_tick_fontsize=7.0,
                y_tick_fontsize=8.0,
                bar_value_fontsize=7.5,
            )
        )
        img = _image_fit(
            builder,
            chart_path,
            max_width=result_inner_w,
            max_height=top_img_h,
            prioritize_width=True,
        )
        if img:
            result_chart_body = [img]

    pie_panel = encadre_section(
        pie_w,
        "Activité par type d'usager",
        pie_body,
        builder.styles,
        variant="default",
    )
    result_panel = encadre_section(
        result_w,
        "Résultats par type d'usager",
        result_chart_body,
        builder.styles,
    )
    _append_page2_row(builder, [pie_panel, result_panel], [pie_w, top_gap, result_w])
    _append_spacer(builder, _BROCHURE_SECTION_GAP_MM)

    bottom_row_cap = _page2_table_row_cap(bottom_p2_mm, with_footer=True)
    proc_row_cap = bottom_row_cap
    if proc_theme is not None and not proc_theme.empty:
        proc_row_cap = min(bottom_row_cap, len(proc_theme))
    pve_row_cap = bottom_row_cap
    if show_pve_band and pve_natinf is not None and not pve_natinf.empty:
        n_pve_avail = len(pve_natinf)
        pve_row_cap = min(bottom_row_cap, n_pve_avail)
        pve_row_cap = max(pve_row_cap, min(proc_row_cap, n_pve_avail))

    inner_proc = encadre_inner_width(proc_w, pad_pt=_PAD_STD_PT)
    proc_body: list = [
        _build_procedures_table_brochure(proc_theme, inner_proc, max_rows=proc_row_cap)
    ]
    if nb_pej or nb_pa:
        parts = []
        if nb_pej:
            parts.append(f"<b>{nb_pej}</b> PEJ")
        parts.append(f"<b>{nb_pa}</b> PA")
        proc_body.append(
            brochure_totaux_band(
                f"<b>Totaux procéduraux</b> : {' · '.join(parts)}",
                inner_proc,
                builder.styles,
            )
        )

    proc_panel = encadre_section(
        proc_w,
        pdf_metric_caption("Procédures par thème (principaux postes)", "proc"),
        proc_body,
        builder.styles,
        variant="surface",
        col_headers=["PEJ", "PA"],
        col_width_fracs=_BROCHURE_PROC_COL_FRACS,
    )
    if show_pve_band:
        inner_pve = encadre_inner_width(pve_w, pad_pt=_PAD_STD_PT)
        pve_body: list = [
            _build_pve_natinf_table_brochure(pve_natinf, inner_pve, max_rows=pve_row_cap)
        ]
        if nb_pve:
            pve_body.append(
                brochure_totaux_band(
                    f"<b>Total PVe (source OFB)</b> : <b>{nb_pve}</b>",
                    inner_pve,
                    builder.styles,
                )
            )
        pve_panel = encadre_section(
            pve_w,
            "PVe — natures d'infraction",
            pve_body,
            builder.styles,
            variant="default",
            col_headers=["Nb"],
            col_width_fracs=_BROCHURE_PVE_NATINF_COL_FRACS,
        )
        _append_page2_row(builder, [proc_panel, pve_panel], [proc_w, bottom_gap, pve_w])
    else:
        _append_page2_row(builder, [proc_panel], [proc_w])
    _append_methodology_footer(
        builder,
        _brochure_methodology_html(
            date_deb=date_deb,
            date_fin=date_fin,
            ventilation_mode=ventilation_mode,
            diffusion=diffusion,
        ),
    )

    builder.build()
