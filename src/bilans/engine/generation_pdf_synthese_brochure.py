"""Rendu PDF brochure (2 pages A4 portrait) du profil synthese_activite_PA_PJ."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage, Paragraph, Spacer, Table

from bilans.common.carte_helper import resolve_map_layout, resolve_profile_map_paths
from bilans.common.pdf_presentation_config import (
    apply_diffusion_pdf_suffix,
    build_title_lines_from_cfg,
    normalize_dept_typography,
    resolve_pdf_presentation_config,
)
from bilans.common.pdf_report_builder import (
    PDFReportBuilder,
    compute_side_by_side_maps_width,
    compute_stacked_maps_width,
)
from bilans.common.pdf_table_sort import pdf_metric_caption, sort_dataframe_desc as _sort_desc
from bilans.common.pdf_utils import ofb_table
from bilans.common.rendus_graphiques import apply_mpl_style, chart_bar_horizontal_stacked, chart_pie
from bilans.common.utilitaires_metier import get_dept_name
from bilans.engine.generation_pdf_synthese import (
    PROFILE_ID,
    _ROOT,
    _build_rows_resultats_controles_pdf,
    _build_synthese_key_figure_rows,
    _chart_pie_compact_legend_kw,
    _display_type_usager,
    _filter_dataframe_min_pct,
    _load_csv_opt,
    _nb_non_conformes_brut,
    _pie_data_controles_par_type_usager,
)

_BROCHURE_MAX_THEMES = 7
_BROCHURE_MAX_PROC_THEMES = 5
_BROCHURE_MAX_USAGER_TYPES = 5
_BROCHURE_USAGER_MIN_SHARE = 0.02


def _truncate_theme(label: str, max_len: int = 32) -> str:
    txt = str(label or "").strip()
    if len(txt) <= max_len:
        return txt
    return txt[: max_len - 1].rstrip() + "…"


def _rollup_usager_types(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Regroupe les types d'usagers peu représentés sous « Autres »."""
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


def _brochure_methodology_line(
    *,
    date_deb: pd.Timestamp,
    date_fin: pd.Timestamp,
    ventilation_mode: str,
    diffusion: str,
) -> str:
    diff = "externe" if str(diffusion).strip().lower() in ("externe", "external", "ext") else "interne"
    return (
        "<i>Méthodologie : sources OSCEAN (points de contrôle, PEJ, PA) et PVe OFB — "
        f"période du {date_deb.date():%d/%m/%Y} au {date_fin.date():%d/%m/%Y} — "
        f"ventilation {ventilation_mode} — diffusion {diff} — "
        "effectifs d'usagers contrôlés (chaque usager renseigné sur une fiche) ; "
        "contrôles = localisations OSCEAN ; PEJ = suite contrôle et saisines hors fiche contrôle.</i>"
    )


def _add_chart_table_row(
    builder: PDFReportBuilder,
    *,
    chart_path: Path,
    table_rows: list[list[str]],
    col_widths: list[float],
    col_aligns: list[str],
    chart_width_ratio: float = 0.56,
    table_caption: str = "",
    header_font_size: float = 7.5,
) -> None:
    if not chart_path.exists() and not table_rows:
        return
    left_w = builder.avail_w * chart_width_ratio
    right_w = builder.avail_w - left_w - 3 * mm
    cells: list = []
    if chart_path.exists():
        ratio = builder._image_aspect_ratio(chart_path)
        max_h = builder.avail_h * 0.34
        img_w = left_w
        img_h = img_w * ratio
        if img_h > max_h:
            img_h = max_h
            img_w = img_h / ratio if ratio > 0 else left_w
        cells.append(RLImage(str(chart_path), width=img_w, height=img_h))
    else:
        cells.append("")
    tbl_block: list = []
    if table_caption:
        tbl_block.append(Paragraph(table_caption, builder.styles["TableCaption"]))
        tbl_block.append(Spacer(1, 0.5 * mm))
    if table_rows:
        tbl_block.append(
            ofb_table(
                table_rows,
                col_widths=col_widths,
                col_aligns=col_aligns,
                header_font_size=header_font_size,
                split_by_row=False,
            )
        )
    cells.append(tbl_block or "")
    row = Table([[cells[0], cells[1]]], colWidths=[left_w, right_w])
    row.hAlign = "LEFT"
    builder.story.append(row)
    builder.story.append(Spacer(1, 1.5 * mm))


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
    apply_mpl_style()
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

    dept_name = get_dept_name(dept_code)
    dept_name_typo = normalize_dept_typography(dept_name)
    cover_title_lines, header_title_lines = build_title_lines_from_cfg(
        presentation_cfg, profile_label="", dept_name_typo=dept_name_typo
    )
    report_header = " — ".join(line.strip() for line in header_title_lines if line.strip())
    period_str = f"Période : du {date_deb.date():%d/%m/%Y} au {date_fin.date():%d/%m/%Y}"

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

    base_name = output_filename or f"{profil_id}.pdf"
    stem = Path(base_name).stem
    if not stem.endswith("_brochure"):
        stem = f"{stem}_brochure"
    pdf_name = f"{stem}.pdf"
    pdf_path = apply_diffusion_pdf_suffix(out_dir / pdf_name, diffusion)

    builder = PDFReportBuilder(
        pdf_path=pdf_path,
        header_title=report_header,
        title=report_header,
        author="Office français de la biodiversité",
        diffusion=diffusion,
    )
    avail_w = builder.avail_w
    tmp_dir = builder.tmp_dir

    builder.begin_content_pages()
    title_line = " — ".join(ln.replace("\n", " ").strip() for ln in cover_title_lines if ln.strip())
    builder.add_paragraph(
        f"<b>{title_line}</b><br/>{dept_name_typo} — {period_str}",
        style="Heading1",
    )
    builder.add_spacer(1.0)

    kf_rows = _build_synthese_key_figure_rows(
        nb_effectifs=nb_effectifs,
        nb_ctrl=nb_ctrl,
        nb_nc=nb_nc,
        nb_pej=nb_pej,
        nb_pa=nb_pa,
        nb_pve=nb_pve,
    )
    builder.add_key_figures_rows(kf_rows, spacer_after_mm=1.0)

    act_theme_display = _filter_dataframe_min_pct(act_theme, value_col="nb_total", min_pct=0.01)
    theme_labels: list[str] = []
    theme_values: list[int] = []
    if act_theme_display is not None and not act_theme_display.empty:
        sub = act_theme_display.head(_BROCHURE_MAX_THEMES)
        theme_labels = [_truncate_theme(r["theme"]) for _, r in sub.iterrows()]
        theme_values = [int(r["nb_total"]) for _, r in sub.iterrows()]
    chart_theme_path = Path()
    if theme_labels and theme_values:
        chart_theme_path = Path(
            chart_bar_horizontal_stacked(
                theme_labels,
                {"Activité": theme_values},
                "Principaux thèmes d'activité (contrôles + PEJ hors fiche)",
                "Nombre",
                tmp_dir,
                "brochure_themes.png",
                figure_scale=0.40,
                legend_fontsize=7.0,
                legend_ncol_max=1,
            )
        )

    res_tbl = (
        _build_rows_resultats_controles_pdf(tab_res_ctrl)
        if tab_res_ctrl is not None and not tab_res_ctrl.empty
        else [["Résultat", "Nombre", "Taux"], ["—", "0", "n.d."]]
    )
    _add_chart_table_row(
        builder,
        chart_path=chart_theme_path,
        table_rows=res_tbl,
        col_widths=[avail_w * 0.40, avail_w * 0.30, avail_w * 0.30],
        col_aligns=["LEFT", "RIGHT", "RIGHT"],
        table_caption="Résultats des contrôles",
        chart_width_ratio=0.58,
    )

    if cartes:
        map_id = str(profile.get("_map_id") or profil_id)
        map_paths = resolve_profile_map_paths(
            map_id, profile=profile, presentation_cfg=presentation_cfg
        )
        map_layout = resolve_map_layout(profile=profile, presentation_cfg=presentation_cfg)
        existing = [Path(p) for p in map_paths if p and Path(p).exists()][:2]
        if existing:
            layout_norm = str(map_layout).strip().lower()
            vertical = layout_norm in ("vertical", "verticale", "empilees", "stacked")
            if len(existing) == 1:
                ratio = builder._image_aspect_ratio(existing[0])
                map_w = min(avail_w * 0.92, builder.avail_h * 0.30 / max(ratio, 0.2))
                builder.story.append(builder._scaled_image_flowable(existing[0], map_w))
            elif vertical:
                ratios = [builder._image_aspect_ratio(p) for p in existing]
                map_w = compute_stacked_maps_width(
                    avail_w, builder.avail_h * 0.32, ratios, width_fraction=0.95
                )
                for i, path in enumerate(existing):
                    builder.story.append(builder._scaled_image_flowable(path, map_w))
                    if i < len(existing) - 1:
                        builder.story.append(Spacer(1, 1 * mm))
            else:
                ratios = [builder._image_aspect_ratio(p) for p in existing]
                col_w = compute_side_by_side_maps_width(
                    avail_w, builder.avail_h * 0.32, ratios
                )
                cells = [builder._scaled_image_flowable(p, col_w) for p in existing]
                builder.story.append(Table([cells], colWidths=[col_w, col_w]))
            builder.story.append(Spacer(1, 1 * mm))

    builder.add_page_break()

    res_usager_plot = _rollup_resultats_usager(res_usager)
    chart_res_path = Path()
    if res_usager_plot is not None and not res_usager_plot.empty:
        labels = [_display_type_usager(x) for x in res_usager_plot["type_usager"].tolist()]
        series: dict[str, list[int]] = {
            "Conforme": [int(x) for x in res_usager_plot["Conforme"].tolist()],
            "Infraction": [int(x) for x in res_usager_plot["Infraction"].tolist()],
            "Manquement": [int(x) for x in res_usager_plot["Manquement"].tolist()],
        }
        if (
            "Autre_resultat" in res_usager_plot.columns
            and int(res_usager_plot["Autre_resultat"].sum()) > 0
        ):
            series["En attente"] = [int(x) for x in res_usager_plot["Autre_resultat"].tolist()]
        chart_res_path = Path(
            chart_bar_horizontal_stacked(
                labels,
                series,
                pdf_metric_caption("Résultats des contrôles par type d'usager", "effectifs"),
                "Effectifs",
                tmp_dir,
                "brochure_resultats_usager.png",
                figure_scale=0.42,
                legend_fontsize=7.0,
            )
        )

    act_type_roll = _rollup_usager_types(act_par_type)
    pie_data = _pie_data_controles_par_type_usager(act_type_roll)
    chart_pie_path = Path()
    if pie_data:
        chart_pie_path = Path(
            chart_pie(
                pie_data,
                "Effectifs contrôlés et PEJ hors contrôle par type d'usager",
                tmp_dir,
                "brochure_pie_usagers.png",
                legend_percent_only=True,
                figure_scale=0.72,
                **_chart_pie_compact_legend_kw(len(pie_data)),
            )
        )

    proc_rows = [["Thème", "PEJ", "PA", "PVe"]]
    if proc_theme is not None and not proc_theme.empty:
        for _, row in proc_theme.head(_BROCHURE_MAX_PROC_THEMES).iterrows():
            proc_rows.append(
                [
                    _truncate_theme(row["theme"], 28),
                    str(int(row.get("nb_pej", 0))),
                    str(int(row.get("nb_pa", 0))),
                    str(int(row.get("nb_pve", 0))),
                ]
            )
    else:
        proc_rows.append(["—", "0", "0", "0"])

    if chart_res_path.exists() or chart_pie_path.exists():
        left_w = avail_w * 0.52
        right_w = avail_w - left_w - 3 * mm
        left_cell: object = ""
        right_cell: object = ""
        if chart_res_path.exists():
            ratio = builder._image_aspect_ratio(chart_res_path)
            img_w = left_w
            img_h = min(img_w * ratio, builder.avail_h * 0.36)
            if img_h < img_w * ratio:
                img_w = img_h / ratio if ratio > 0 else img_w
            left_cell = RLImage(str(chart_res_path), width=img_w, height=img_h)
        if chart_pie_path.exists():
            ratio = builder._image_aspect_ratio(chart_pie_path)
            img_w = right_w
            img_h = min(img_w * ratio, builder.avail_h * 0.36)
            if img_h < img_w * ratio:
                img_w = img_h / ratio if ratio > 0 else img_w
            right_cell = RLImage(str(chart_pie_path), width=img_w, height=img_h)
        builder.story.append(Table([[left_cell, right_cell]], colWidths=[left_w, right_w]))
        builder.story.append(Spacer(1, 1.5 * mm))

    builder.add_table(
        proc_rows,
        caption=pdf_metric_caption("Procédures par thème (principaux postes)", "proc"),
        col_widths=[avail_w * 0.46, avail_w * 0.18, avail_w * 0.18, avail_w * 0.18],
        col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"],
        keep_together=True,
        spacer_after_mm=1.5,
        max_rows_keep_together=12,
    )

    if nb_pej or nb_pa or nb_pve:
        parts = []
        if nb_pej:
            parts.append(f"<b>{nb_pej}</b> PEJ")
        parts.append(f"<b>{nb_pa}</b> PA")
        if nb_pve:
            parts.append(f"<b>{nb_pve}</b> PVe")
        builder.add_paragraph(
            "Totaux procéduraux sur la période : " + " · ".join(parts) + ".",
            style="BodyText",
        )

    builder.add_paragraph(
        _brochure_methodology_line(
            date_deb=date_deb,
            date_fin=date_fin,
            ventilation_mode=ventilation_mode,
            diffusion=diffusion,
        ),
        style="BodySmall",
    )

    builder.build()
