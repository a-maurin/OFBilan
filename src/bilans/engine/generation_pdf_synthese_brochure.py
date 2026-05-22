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

from bilans.common.carte_helper import resolve_profile_map_paths
from bilans.common.ofb_charte import COLOR_PRIMARY
from bilans.common.pdf_presentation_config import (
    apply_diffusion_pdf_suffix,
    normalize_dept_typography,
    resolve_pdf_presentation_config,
)
from bilans.common.pdf_report_builder import PDFReportBuilder, compute_side_by_side_maps_width
from bilans.common.pdf_table_sort import pdf_metric_caption, sort_dataframe_desc as _sort_desc
from bilans.common.percent_format import tab_counts_to_pct_strings
from bilans.common.rendus_graphiques import (
    chart_bar_horizontal_stacked,
    chart_pie_legend_right,
)
from bilans.engine.brochure_charte import (
    BrochureBandeau,
    apply_brochure_mpl_style,
    append_page1_logos_bas_droite,
    brochure_table,
    encadre_inner_width,
    encadre_section,
    kpi_encadre,
    note_encadre,
)
from bilans.common.utilitaires_metier import get_dept_name
from bilans.engine.generation_pdf_synthese import (
    PROFILE_ID,
    _ROOT,
    _build_synthese_key_figure_rows,
    _display_type_usager,
    _filter_dataframe_min_pct,
    _load_csv_opt,
    _nb_non_conformes_brut,
    _pie_data_controles_par_type_usager,
)

_BROCHURE_MAX_THEMES = 5
_BROCHURE_MAX_PROC_THEMES = 5
_BROCHURE_MAX_USAGER_TYPES = 5
_BROCHURE_USAGER_MIN_SHARE = 0.02

BROCHURE_PAGE_SIZE = landscape(A4)
_GRID_GAP_MM = 10.0
_BROCHURE_SECTION_GAP_MM = 3.2
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


def _rollup_resultats_usager(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty:
        return df
    work = df.copy()
    for col in ("Conforme", "Infraction", "Manquement", "Autre_resultat", "Total"):
        if col in work.columns:
            work[col] = work[col].astype(int)
    total_all = float(work["Total"].sum()) if "Total" in work.columns else 0.0
    if total_all <= 0:
        return work.head(_BROCHURE_MAX_USAGER_TYPES)
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
        if t / total_all >= _BROCHURE_USAGER_MIN_SHARE and len(kept) < _BROCHURE_MAX_USAGER_TYPES - 1:
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


_BROCHURE_THEME_COL_FRACS = [0.54, 0.18, 0.28]
_BROCHURE_RESULT_COL_FRACS = [0.48, 0.22, 0.30]
_BROCHURE_PROC_COL_FRACS = [0.46, 0.18, 0.18, 0.18]


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


def _page1_vertical_gaps_mm(*, has_maps: bool) -> float:
    """Espace blanc entre bandeau, KPI, tableaux, cartes et logos."""
    n = 3 + (1 if has_maps else 0) + 1
    return n * _BROCHURE_SECTION_GAP_MM


def _page2_vertical_gaps_mm() -> float:
    return 3 * _BROCHURE_SECTION_GAP_MM


def _layout_page1_maps_mm(builder: PDFReportBuilder, *, has_maps: bool) -> float:
    """Hauteur réservée aux cartes page 1 (compense les espacements inter-blocs)."""
    if not has_maps:
        return 0.0
    avail_mm = builder.avail_h / mm
    fixed_mm = (
        9.0
        + 15.0
        + _page1_vertical_gaps_mm(has_maps=has_maps)
        + 37.0
        + 9.0
    )
    return min(31.0, max(21.0, avail_mm - fixed_mm - 3.0))


def _layout_page2_charts_mm(builder: PDFReportBuilder) -> float:
    avail_mm = builder.avail_h / mm
    fixed_mm = 32.0 + _page2_vertical_gaps_mm() + 19.0 + 10.0
    return min(41.0, max(30.0, avail_mm - fixed_mm))


def _build_procedures_table_brochure(proc_theme: pd.DataFrame | None, inner_w: float) -> Table:
    rows: list[list[str]] = []
    if proc_theme is not None and not proc_theme.empty:
        for _, row in proc_theme.head(_BROCHURE_MAX_PROC_THEMES).iterrows():
            rows.append(
                [
                    _truncate_theme(row["theme"], 32),
                    str(int(row.get("nb_pej", 0))),
                    str(int(row.get("nb_pa", 0))),
                    str(int(row.get("nb_pve", 0))),
                ]
            )
    else:
        rows.append(["—", "0", "0", "0"])
    return brochure_table(
        rows,
        col_widths=[inner_w * f for f in _BROCHURE_PROC_COL_FRACS],
        col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"],
        split_by_row=False,
        header_row=False,
    )


def _build_themes_table_brochure(
    labels: list[str],
    values: list[int],
    inner_w: float,
) -> Table:
    rows: list[list[str]] = []
    pcts = tab_counts_to_pct_strings([int(v) for v in values])
    for lb, v, pct in zip(labels, values, pcts):
        rows.append([_truncate_theme(lb, 30), str(int(v)), pct])
    return brochure_table(
        rows,
        col_widths=[inner_w * f for f in _BROCHURE_THEME_COL_FRACS],
        col_aligns=["LEFT", "RIGHT", "RIGHT"],
        split_by_row=False,
        header_row=False,
    )


def _append_dual_panels(
    builder: PDFReportBuilder,
    *,
    left_panel,
    right_panel,
    left_ratio: float = _COL_LEFT_RATIO,
) -> None:
    left_w, gap_w, right_w = _grid_columns(builder, left_ratio)
    row = Table([[left_panel, "", right_panel]], colWidths=[left_w, gap_w, right_w], hAlign="LEFT")
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
        fontSize=10,
        leading=12,
        textColor=rl_colors.white,
    )
    builder.story.append(
        BrochureBandeau(
            builder.avail_w,
            [
                Paragraph(
                    f"<b>Synthèse PA/PJ</b> — {dept} — <font color='#C5D9ED'>{period}</font>",
                    title_style,
                ),
            ],
        )
    )


def _append_kpi_strip(builder: PDFReportBuilder, figures: list[tuple[str, str]]) -> None:
    builder.story.append(kpi_encadre(builder.avail_w, figures, builder.styles))


def _image_fit(
    builder: PDFReportBuilder,
    path: Path,
    *,
    max_width: float,
    max_height: float,
) -> RLImage | str:
    if not path.exists():
        return ""
    ratio = builder._image_aspect_ratio(path)
    w = max_width
    h = w * ratio
    if h > max_height:
        h = max_height
        w = h / ratio if ratio > 0 else max_width
    img = RLImage(str(path), width=w, height=h)
    img.hAlign = "CENTER"
    return img


def _append_maps_row(
    builder: PDFReportBuilder,
    paths: list[Path],
    *,
    max_height_mm: float,
) -> None:
    w = builder.avail_w
    existing = [p for p in paths if p.exists()]
    if not existing:
        return
    max_h = max_height_mm * mm
    gap = _GRID_GAP_MM * mm
    if len(existing) == 1:
        img = _image_fit(builder, existing[0], max_width=w - 8 * mm, max_height=max_h)
        body = [img] if img else []
    else:
        ratios = [builder._image_aspect_ratio(p) for p in existing[:2]]
        col_w = compute_side_by_side_maps_width(
            w - 8 * mm, max_h, ratios, horizontal_gap_pt=gap, reserve_pt=0
        )
        col_w = min(col_w, (w - gap - 8 * mm) / 2.0)
        imgs = [
            _image_fit(builder, p, max_width=col_w, max_height=max_h) for p in existing[:2]
        ]
        maps_tbl = Table([imgs], colWidths=[col_w, col_w], hAlign="CENTER")
        maps_tbl.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        body = [maps_tbl]
    builder.story.append(
        encadre_section(builder.avail_w, "Cartographie de l'activité", body, builder.styles, variant="surface")
    )


def _append_footer_note(builder: PDFReportBuilder, html: str) -> None:
    builder.story.append(note_encadre(builder.avail_w, html, builder.styles))


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
        "PEJ = suite à contrôle et saisines hors fiche contrôle.</i>"
    )


def generate_synthese_brochure_pdf_report(
    out_dir: Path,
    *,
    profile: dict | None = None,
    date_deb: str | pd.Timestamp | None = None,
    date_fin: str | pd.Timestamp | None = None,
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
    dept_code_str = str(dept_code) if dept_code is not None else "21"
    _generate_synthese_brochure_pdf(
        out_dir,
        profile=profile,
        date_deb=date_deb_ts,
        date_fin=date_fin_ts,
        dept_code=dept_code_str,
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
    dept_code: str,
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

    dept_name_typo = normalize_dept_typography(get_dept_name(dept_code))
    report_header = f"Synthèse PA/PJ — {dept_name_typo}"
    period_str = f"du {date_deb.date():%d/%m/%Y} au {date_fin.date():%d/%m/%Y}"

    act_theme = _sort_desc(_load_csv_opt(out_dir, "synthese_activite_par_theme.csv"), ["nb_total"])
    proc_theme = _sort_desc(_load_csv_opt(out_dir, "synthese_procedures_par_theme.csv"), ["nb_pej"])
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

    nb_ctrl = int(resume.iloc[0]["nb_ctrl"]) if resume is not None and not resume.empty else 0
    nb_pej = int(pej_resume.iloc[0]["nb_pej_global"]) if pej_resume is not None and not pej_resume.empty else 0
    nb_pa = int(pa_resume.iloc[0]["nb_pa_global"]) if pa_resume is not None and not pa_resume.empty else 0
    nb_pve = int(pve_resume.iloc[0]["nb_pve_global"]) if pve_resume is not None and not pve_resume.empty else 0
    res_usager_roll = _rollup_resultats_usager(res_usager)
    nb_effectifs = (
        int(res_usager_roll["Total"].sum())
        if res_usager_roll is not None and not res_usager_roll.empty and "Total" in res_usager_roll.columns
        else 0
    )
    nb_nc = _nb_non_conformes_brut(tab_resultats) if nb_ctrl > 0 else 0

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
        margin_bottom=15 * mm,
    )
    left_w, _, right_w = _grid_columns(builder)
    maps_mm = _layout_page1_maps_mm(builder, has_maps=has_maps)
    charts_mm = _layout_page2_charts_mm(builder)
    tmp_dir = builder.tmp_dir

    # ── Page 1 ──
    _append_bandeau(builder, dept_name_typo, period_str)
    _append_spacer(builder, _BROCHURE_SECTION_GAP_MM)

    kf_rows = _build_synthese_key_figure_rows(
        nb_effectifs=nb_effectifs,
        nb_ctrl=nb_ctrl,
        nb_nc=nb_nc,
        nb_pej=nb_pej,
        nb_pa=nb_pa,
        nb_pve=nb_pve,
    )
    _append_kpi_strip(builder, _flatten_key_figures(kf_rows))
    _append_spacer(builder, _BROCHURE_SECTION_GAP_MM)

    inner_left = encadre_inner_width(left_w)
    inner_right = encadre_inner_width(right_w)
    left_body: list = []
    act_theme_display = _filter_dataframe_min_pct(act_theme, value_col="nb_total", min_pct=0.01)
    if act_theme_display is not None and not act_theme_display.empty:
        sub = act_theme_display.head(_BROCHURE_MAX_THEMES)
        labels = [_truncate_theme(r["theme"]) for _, r in sub.iterrows()]
        values = [int(r["nb_total"]) for _, r in sub.iterrows()]
        left_body = [_build_themes_table_brochure(labels, values, inner_left)]

    res_tbl = _build_rows_resultats_brochure(tab_res_ctrl)
    res_table = brochure_table(
        res_tbl,
        col_widths=[inner_right * f for f in _BROCHURE_RESULT_COL_FRACS],
        col_aligns=["LEFT", "RIGHT", "RIGHT"],
        split_by_row=False,
        header_row=False,
    )
    left_panel = encadre_section(
        left_w,
        "Principaux thèmes d'activité",
        left_body,
        builder.styles,
        col_headers=["Nb", "Taux"],
        col_width_fracs=_BROCHURE_THEME_COL_FRACS,
    )
    right_panel = encadre_section(
        right_w,
        "Résultats des contrôles",
        [res_table],
        builder.styles,
        variant="surface",
        col_headers=["Nb", "Taux"],
        col_width_fracs=_BROCHURE_RESULT_COL_FRACS,
    )
    _append_dual_panels(builder, left_panel=left_panel, right_panel=right_panel)
    _append_spacer(builder, _BROCHURE_SECTION_GAP_MM)

    if has_maps:
        _append_maps_row(builder, map_paths, max_height_mm=maps_mm)
    else:
        _append_footer_note(
            builder,
            "<i>Cartographie : cartes non disponibles "
            "(fichiers attendus dans data/out/generateur_de_cartes/).</i>",
        )
    _append_spacer(builder, _BROCHURE_SECTION_GAP_MM)
    append_page1_logos_bas_droite(builder, builder.tmp_dir)

    builder.add_page_break()

    # ── Page 2 ──
    chart_h2 = charts_mm * mm
    left_w2, _, right_w2 = _grid_columns(builder, 0.55)

    left_body2: list = []
    res_usager_plot = _rollup_resultats_usager(res_usager)
    if res_usager_plot is not None and not res_usager_plot.empty:
        labels = [_truncate_theme(_display_type_usager(x), 28) for x in res_usager_plot["type_usager"]]
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
                "Effectifs",
                tmp_dir,
                "brochure_resultats_usager.png",
                figure_scale=0.35,
                show_title=False,
                legend_below=True,
                legend_fontsize=7.0,
            )
        )
        img = _image_fit(
            builder,
            chart_path,
            max_width=encadre_inner_width(left_w2),
            max_height=chart_h2 * 0.92,
        )
        if img:
            left_body2 = [img]

    right_body2: list = []
    pie_data = _pie_data_controles_par_type_usager(_rollup_usager_types(act_par_type))
    if pie_data:
        chart_path = Path(
            chart_pie_legend_right(
                pie_data,
                "",
                tmp_dir,
                "brochure_pie_usagers.png",
                legend_percent_only=True,
                figure_scale=0.76,
                legend_fontsize=7.0,
            )
        )
        img = _image_fit(
            builder,
            chart_path,
            max_width=encadre_inner_width(right_w2),
            max_height=chart_h2 * 0.95,
        )
        if img:
            right_body2 = [img]

    _append_dual_panels(
        builder,
        left_panel=encadre_section(
            left_w2, "Résultats par type d'usager", left_body2, builder.styles
        ),
        right_panel=encadre_section(
            right_w2,
            "Répartition par type d'usager",
            right_body2,
            builder.styles,
            variant="surface",
        ),
        left_ratio=0.55,
    )
    _append_spacer(builder, _BROCHURE_SECTION_GAP_MM)

    inner_full = encadre_inner_width(builder.avail_w)
    proc_tbl = _build_procedures_table_brochure(proc_theme, inner_full)
    builder.story.append(
        encadre_section(
            builder.avail_w,
            pdf_metric_caption("Procédures par thème (principaux postes)", "proc"),
            [proc_tbl],
            builder.styles,
            variant="surface",
            col_headers=["PEJ", "PA", "PVe"],
            col_width_fracs=_BROCHURE_PROC_COL_FRACS,
        )
    )
    _append_spacer(builder, _BROCHURE_SECTION_GAP_MM)

    if nb_pej or nb_pa or nb_pve:
        parts = []
        if nb_pej:
            parts.append(f"<b>{nb_pej}</b> PEJ")
        parts.append(f"<b>{nb_pa}</b> PA")
        if nb_pve:
            parts.append(f"<b>{nb_pve}</b> PVe")
        totaux_style = ParagraphStyle(
            "BrochureTotaux",
            parent=builder.styles["BodyText"],
            fontSize=9.5,
            leading=12,
            textColor=rl_colors.HexColor(COLOR_PRIMARY),
        )
        builder.story.append(
            encadre_section(
                builder.avail_w,
                None,
                [Paragraph("Totaux procéduraux : " + " · ".join(parts), totaux_style)],
                builder.styles,
                variant="surface",
            )
        )
        _append_spacer(builder, _BROCHURE_SECTION_GAP_MM)

    _append_footer_note(
        builder,
        _brochure_methodology_html(
            date_deb=date_deb,
            date_fin=date_fin,
            ventilation_mode=ventilation_mode,
            diffusion=diffusion,
        ),
    )

    builder.build()
