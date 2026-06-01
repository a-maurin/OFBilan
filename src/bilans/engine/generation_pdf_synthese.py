"""Rendu PDF du profil synthese_activite_PA_PJ."""

from __future__ import annotations

import textwrap
from html import escape
from pathlib import Path

import pandas as pd

from bilans.common.carte_helper import (
    expected_map_filenames,
    resolve_map_layout,
    resolve_profile_map_paths,
)
from bilans.common.dataframe_rollup import rollup_small_categories as _rollup_small_categories
from bilans.common.pdf_presentation_config import (
    apply_diffusion_pdf_suffix,
    build_title_lines_from_cfg,
    is_section_enabled,
    normalize_dept_typography,
    resolve_charte_config,
    resolve_pdf_presentation_config,
    resolve_title_page_config,
    should_show_placeholder,
)
from bilans.common.pdf_report_builder import PDFReportBuilder
from bilans.common.pdf_utils import truncate_text_to_width
from bilans.common.pdf_shared_sections import (
    add_standard_cover_and_toc,
    add_standard_notice_methodology,
    build_filtered_glossary_rows,
    build_sec6_methodology_context,
    build_sec6_methodology_html,
    load_glossary_config,
)
from bilans.common.pdf_table_sort import (
    pdf_metric_caption,
    sort_dataframe_desc as _sort_desc,
)
from bilans.common.percent_format import format_pct_int_from_rate, tab_counts_to_pct_strings
from bilans.common.chart_display_config import (
    clamp_uniform_pie_ratio,
    compute_pdf_ratios,
    load_chart_display_config,
    resolve_reference_pie_display,
)
from bilans.common.rendus_graphiques import apply_mpl_style, chart_bar_horizontal_stacked, chart_pie
from bilans.common.utilitaires_metier import (
    _load_csv_opt,
    format_type_usager_display,
    get_dept_name,
)

_KEY_FIGURES_GRAIN_NOTE = (
    "Les localisations comptent les points de contrôle, tandis que les effectifs "
    "d'usagers sont comptés par fiche de contrôle ; ils peuvent donc être "
    "inférieurs ou supérieurs."
)


def _truncate_with_dash(value: str, max_len: int) -> str:
    txt = str(value or "")
    if len(txt) <= max_len:
        return txt
    if max_len <= 1:
        return "-"
    return txt[: max_len - 1].rstrip() + "-"


def _nb_non_conformes_brut(tab_resultats: pd.DataFrame | None) -> int:
    if tab_resultats is None or tab_resultats.empty:
        return 0
    m = tab_resultats["resultat"].astype(str).str.strip()
    return int(tab_resultats.loc[m.isin(["Infraction", "Manquement"]), "nb"].sum())


def _build_rows_resultats_controles_pdf(tr: pd.DataFrame) -> list[list[str]]:
    tbl = [["Résultat", "Nombre de contrôles", "Taux"]]
    strip_res = tr["resultat"].astype(str).str.strip()
    top_mask = strip_res.isin(["Conforme", "Non-conforme", "En attente"])
    top_counts = tr.loc[top_mask, "nb"].astype(int).tolist()
    top_rates = tab_counts_to_pct_strings(top_counts) if top_counts else []
    j = 0
    nb_nc = int(tr.loc[strip_res.eq("Non-conforme"), "nb"].sum())
    for _, row in tr.iterrows():
        rlib = str(row["resultat"])
        rlib_display = rlib
        if rlib.strip() in ("Dont infraction", "Dont manquement"):
            rlib_display = f"&nbsp;&nbsp;&nbsp;{rlib.strip()}"
        nbv = int(row["nb"])
        if rlib.strip() in ("Dont infraction", "Dont manquement"):
            t = format_pct_int_from_rate((nbv / nb_nc) if nb_nc > 0 else None)
        elif rlib.strip() in ("Conforme", "Non-conforme", "En attente"):
            t = top_rates[j] if j < len(top_rates) else "n.d."
            j += 1
        else:
            t = "n.d."
        tbl.append([rlib_display, str(nbv), t])
    return tbl


def _pct_table_cell(n: int | float, denom: float) -> str:
    if denom is None or denom <= 0:
        return "n.d."
    return format_pct_int_from_rate(float(n) / float(denom))


def _filter_dataframe_min_pct(
    df: pd.DataFrame | None,
    *,
    value_col: str = "nb_total",
    min_pct: float = 0.01,
) -> pd.DataFrame | None:
    """Exclut les lignes dont la part est strictement inférieure à *min_pct* du total."""
    if df is None or df.empty or value_col not in df.columns:
        return df
    total = float(df[value_col].astype(float).sum())
    if total <= 0:
        return df
    out = df.loc[df[value_col].astype(float) / total >= min_pct].copy()
    return out.sort_values(by=value_col, ascending=False, kind="stable").reset_index(drop=True)


def _chart_pie_compact_legend_kw(
    n_categories: int,
    *,
    legend_fontsize: float = 9.0,
) -> dict[str, float | int]:
    ncol = min(n_categories, 2) if n_categories > 4 else min(n_categories, 3)
    return {"legend_fontsize": legend_fontsize, "legend_ncol": max(1, ncol)}


_SEC3_1_TABLE_NOTE = (
    "<i>Note : les effectifs sont dérivés des fiches de contrôle ; les PEJ suite contrôle, "
    "du type d'usager renseigné sur le dossier de saisine. En cas de divergence entre ces "
    "deux sources pour un même contrôle, une ligne peut afficher 0 effectif et une ou "
    "plusieurs PEJ.</i>"
)


def _build_usager_theme_table_rows(sub: pd.DataFrame) -> list[list[str]]:
    tbl = [
        [
            "Thème",
            "Effectifs",
            "PEJ suite contrôle",
            "Saisines PEJ hors contrôle",
            "Total",
        ]
    ]
    for _, row in sub.iterrows():
        theme_label = " ".join(str(row.get("theme", "")).split())
        tbl.append(
            [
                theme_label,
                str(int(row.get("nb_effectifs", 0))),
                str(int(row.get("nb_pej_suite_controle", 0))),
                str(int(row.get("nb_pej_hors_controle", 0))),
                str(int(row.get("nb_total", 0))),
            ]
        )
    return tbl


def _display_type_usager(label: str) -> str:
    return format_type_usager_display(str(label or ""))


def _wrap_table_label(value: str, width: int = 34) -> str:
    txt = " ".join(str(value or "").split())
    if not txt:
        return ""
    lines = textwrap.wrap(
        txt,
        width=max(int(width), 8),
        break_long_words=False,
        break_on_hyphens=False,
    )
    if not lines:
        return escape(txt)
    return "<br/>".join(escape(line) for line in lines)


def _format_pve_natinf_label(row: pd.Series) -> str:
    libelle = row.get("libelle_natinf") or row.get("LIBELLE_NATINF") or ""
    code = str(row.get("numero_natinf") or row.get("natinf") or "").strip()
    if libelle:
        return f"{code} – {libelle}" if code else str(libelle)
    return code or "-"


def _resultats_controles_pie_data(tab_resultats: pd.DataFrame | None) -> dict[str, int]:
    """Camembert des résultats de contrôle sur les 4 catégories métier."""
    if (
        tab_resultats is None
        or tab_resultats.empty
        or "resultat" not in tab_resultats.columns
        or "nb" not in tab_resultats.columns
    ):
        return {}

    labels = tab_resultats["resultat"].astype(str).str.strip()
    out: dict[str, int] = {}
    for label, accepted in (
        ("Conforme", ("Conforme",)),
        ("Infraction", ("Infraction", "Dont infraction")),
        ("Manquement", ("Manquement", "Dont manquement")),
        ("En attente", ("En attente",)),
    ):
        nb = int(tab_resultats.loc[labels.isin(accepted), "nb"].astype(int).sum())
        if nb > 0:
            out[label] = nb
    return out


def _build_pve_natinf_table_rows(
    pve_natinf: pd.DataFrame,
    *,
    head: int = 12,
    label_col_width_pt: float | None = None,
) -> list[list[str]]:
    tbl = [["Nature d'infraction (NATINF)", "Nombre de PVe"]]
    for _, row in pve_natinf.head(head).iterrows():
        nature = _format_pve_natinf_label(row)
        if label_col_width_pt is not None and label_col_width_pt > 0:
            nature = truncate_text_to_width(nature, label_col_width_pt)
        else:
            nature = _truncate_with_dash(str(nature), 52)
        tbl.append([nature, str(int(row["nb"]))])
    return tbl


def _pie_data_controles_par_type_usager(df: pd.DataFrame | None) -> dict[str, int]:
    """Données camembert § 3 : effectifs d'usagers contrôlés + saisines PEJ hors contrôle."""
    if df is None or df.empty or "nb_total" not in df.columns:
        return {}
    out: dict[str, int] = {}
    for _, row in df.iterrows():
        total = int(row.get("nb_total", 0) or 0)
        if total > 0:
            out[_display_type_usager(row["type_usager"])] = total
    return out


def _build_synthese_key_figure_rows(
    *,
    nb_effectifs: int,
    nb_ctrl: int,
    nb_nc: int,
    nb_pej: int,
    nb_pa: int,
    nb_pve: int,
) -> list[list[tuple[str, str]]]:
    row1: list[tuple[str, str]] = []
    if nb_effectifs > 0:
        row1.append((str(nb_effectifs), "Effectifs d'usagers contrôlés"))
    if nb_ctrl > 0:
        row1.append((str(nb_ctrl), "Localisations des contrôles"))
        if nb_nc > 0:
            row1.append((str(nb_nc), "Contrôles non-conformes"))
            row1.append(
                (format_pct_int_from_rate(nb_nc / nb_ctrl), "Taux de non-conformités")
            )
    row2: list[tuple[str, str]] = []
    if nb_pej > 0:
        row2.append((str(nb_pej), "Procédures judiciaires"))
    row2.append((str(nb_pa), "Procédures administratives"))
    if nb_pve > 0:
        row2.append((str(nb_pve), "Procès-verbaux électroniques"))
    rows = [row1]
    if row2:
        rows.append(row2)
    return rows

_ROOT = Path(__file__).resolve().parents[3]
PROFILE_ID = "synthese_activite_PA_PJ"


def generate_synthese_pdf_report(
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
    brochure: bool = False,
) -> None:
    del chart_preset, brochure
    apply_mpl_style()
    profile = profile or {"id": PROFILE_ID}
    date_deb_ts = pd.to_datetime(date_deb) if date_deb is not None else pd.Timestamp("2025-01-01")
    date_fin_ts = pd.to_datetime(date_fin) if date_fin is not None else pd.Timestamp("2026-02-05")
    dept_code_str = str(dept_code) if dept_code is not None else "21"
    _generate_synthese_pdf(
        out_dir,
        profile=profile,
        date_deb=date_deb_ts,
        date_fin=date_fin_ts,
        dept_code=dept_code_str,
        output_filename=output_filename,
        diffusion=diffusion,
        cartes=cartes,
    )
    from bilans.engine.generation_pdf_synthese_brochure import (
        generate_synthese_brochure_pdf_report,
    )

    generate_synthese_brochure_pdf_report(
        out_dir,
        profile=profile,
        date_deb=date_deb_ts,
        date_fin=date_fin_ts,
        dept_code=dept_code_str,
        ventilation_mode=ventilation_mode,
        output_filename=output_filename,
        diffusion=diffusion,
        cartes=cartes,
    )


def _generate_synthese_pdf(
    out_dir: Path,
    *,
    profile: dict,
    date_deb: pd.Timestamp,
    date_fin: pd.Timestamp,
    dept_code: str,
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
    behavior_cfg = resolved.get("behavior", {}) if isinstance(resolved, dict) else {}
    show_placeholder = should_show_placeholder(behavior_cfg if isinstance(behavior_cfg, dict) else None)

    chart_ratios = compute_pdf_ratios(load_chart_display_config(_ROOT))
    pie_ratio_uniform = clamp_uniform_pie_ratio(
        chart_ratios,
        uniform_key="global_uniform_pie",
        min_key="global_uniform_pie_min_ratio",
        max_key="global_uniform_pie_max_ratio",
    )
    ref_pie = resolve_reference_pie_display(chart_ratios, pie_ratio_uniform)
    ref_pie_w = ref_pie["width_ratio"]
    ref_pie_fs = ref_pie["figure_scale"]
    ref_pie_legend_fs = ref_pie["legend_fontsize"]

    dept_name = get_dept_name(dept_code)
    dept_name_typo = normalize_dept_typography(dept_name)
    profile_label = str(profile.get("label", profil_id))

    act_theme = _sort_desc(_load_csv_opt(out_dir, "synthese_activite_par_theme.csv"), ["nb_total"])
    proc_theme = _sort_desc(_load_csv_opt(out_dir, "synthese_procedures_par_theme.csv"), ["nb_pej"])
    act_ut = _sort_desc(_load_csv_opt(out_dir, "synthese_activite_usager_theme.csv"), ["nb_total"])
    act_par_type = _sort_desc(
        _load_csv_opt(out_dir, "synthese_activite_par_type_usager.csv"), ["nb_total"]
    )
    proc_ut = _load_csv_opt(out_dir, "synthese_procedures_usager_theme.csv")
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
    nb_effectifs = (
        int(res_usager["Total"].sum())
        if res_usager is not None and not res_usager.empty and "Total" in res_usager.columns
        else 0
    )

    section_defs = [
        ("sec1", "1. Chiffres clés"),
        ("sec2", "2. Activité de police administrative et judiciaire"),
        ("sec2_1", "2.1. Activité de police par thème du plan de contrôle"),
        ("sec2_2", "2.2. Résultat des contrôles au titre de la police administrative"),
        ("sec2_3", "2.3. Activité procédurale"),
        ("sec3", "3. Activité de police par type d'usager"),
        ("sec3_1", "3.1. Thème de contrôle par type d'usager"),
        ("sec3_2", "3.2. Résultat des contrôles par type d'usager"),
        ("sec3_3", "3.3. Activité procédurale par type d'usager"),
        ("sec4", "4. Procès-verbaux électroniques (PVe)"),
        ("sec5", "5. Cartographie"),
        ("sec6", "6. Annexes"),
    ]
    sections_toc = section_defs

    cover_title_lines, header_title_lines = build_title_lines_from_cfg(
        presentation_cfg, profile_label="", dept_name_typo=dept_name_typo
    )
    report_header = " — ".join(line.strip() for line in header_title_lines if line.strip())

    safe_name = dept_name.replace(" ", "_").replace("'", "")
    pdf_name = output_filename or f"{profil_id}_{safe_name}.pdf"
    pdf_path = apply_diffusion_pdf_suffix(out_dir / pdf_name, diffusion)
    charte_cfg = resolve_charte_config(presentation_cfg)
    title_page_cfg = resolve_title_page_config(_ROOT, scope=scope, profile_id=profil_id)
    builder = PDFReportBuilder(
        pdf_path=pdf_path,
        header_title=report_header,
        title=report_header,
        author="Office français de la biodiversité",
        charte_config=charte_cfg,
        diffusion=diffusion,
        title_page_config=title_page_cfg,
    )
    avail_w = builder.avail_w
    tmp_dir = builder.tmp_dir

    add_standard_cover_and_toc(
        builder,
        project_root=_ROOT,
        scope=scope,
        cover_title_lines=cover_title_lines,
        period_str=f"Période : du {date_deb.date():%d/%m/%Y} au {date_fin.date():%d/%m/%Y}",
        sections_toc=sections_toc,
        nb_pve=nb_pve,
    )
    add_standard_notice_methodology(
        builder,
        period_sentence=(
            f"Pour ce bilan, les extractions portent sur la période du {date_deb.date():%d/%m/%Y} "
            f"au {date_fin.date():%d/%m/%Y}."
        ),
        effective_cfg=presentation_cfg,
        diffusion=diffusion,
    )

    # ── 1. Chiffres clés + § 2 + § 2.1 (même page) ──
    builder.add_section("sec1", "1. Chiffres clés")
    nb_nc = _nb_non_conformes_brut(tab_resultats) if nb_ctrl > 0 else 0
    kf_rows = _build_synthese_key_figure_rows(
        nb_effectifs=nb_effectifs,
        nb_ctrl=nb_ctrl,
        nb_nc=nb_nc,
        nb_pej=nb_pej,
        nb_pa=nb_pa,
        nb_pve=nb_pve,
    )
    builder.add_key_figures_rows(kf_rows)

    builder.add_section(
        "sec2",
        "2. Activité de police administrative et judiciaire",
        append_to_pending=True,
    )
    builder.append_pending_paragraph(_KEY_FIGURES_GRAIN_NOTE)
    builder.append_pending_callout_box(
        "Comme indiqué dans la notice méthodologique, le terme contrôle désigne ici "
        "exclusivement une mesure de police administrative.",
        title="Rappel",
        spacer_after_mm=1.5,
    )
    builder.append_pending_paragraph(
        "Sauf mention contraire, les tableaux de cette partie cumulent les localisations de "
        "contrôle (points de contrôle OSCEAN) et les procédures d'enquêtes judiciaires (PEJ) "
        "non rattachées à une fiche contrôle (i.e. saisines judiciaires hors opérations de "
        "contrôle)."
    )

    builder.add_section(
        "sec2_1",
        "2.1. Activité de police par thème du plan de contrôle",
        level=2,
        toc_level=1,
        append_to_pending=True,
    )
    act_theme_display = _rollup_small_categories(
        act_theme,
        label_col="theme",
        other_label="Autres thèmes de contrôle",
        value_col="nb_total",
        min_pct=0.01,
        sum_cols=["nb_ctrl", "nb_pej_hors_controle", "nb_total"],
    )
    act_theme_total = (
        int(act_theme["nb_total"].astype(float).sum())
        if act_theme is not None and not act_theme.empty
        else 0
    )
    if act_theme_display is not None and not act_theme_display.empty:
        tbl = [["Thème", "Contrôles PA", "PEJ hors contrôle PA", "Total"]]
        for _, row in act_theme_display.iterrows():
            nb_row = int(row["nb_total"])
            pct = format_pct_int_from_rate(nb_row / act_theme_total) if act_theme_total > 0 else "n.d."
            tbl.append(
                [
                    _wrap_table_label(row["theme"]),
                    str(int(row.get("nb_ctrl", 0))),
                    str(int(row.get("nb_pej_hors_controle", 0))),
                    f"{nb_row} ({pct})",
                ]
            )
        builder.add_table(
            tbl,
            caption="Activité de police par thème (contrôles + PEJ hors fiche contrôle)",
            col_widths=[avail_w * 0.44, avail_w * 0.18, avail_w * 0.18, avail_w * 0.20],
            col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"],
            keep_together=True,
        )
    elif show_placeholder:
        builder.append_pending_paragraph("Aucune donnée disponible pour l'activité par thème.")
        builder.add_keep_together_block([])

    builder.add_section(
        "sec2_2",
        "2.2. Résultat des contrôles au titre de la police administrative",
        level=2,
        toc_level=1,
    )
    if tab_res_ctrl is not None and not tab_res_ctrl.empty:
        tbl_pdf = _build_rows_resultats_controles_pdf(tab_res_ctrl)
        pie_data = _resultats_controles_pie_data(tab_resultats)
        pie_path = None
        if pie_data:
            pie_path = chart_pie(
                pie_data,
                "",
                tmp_dir,
                "pie_synthese_resultats_controles.png",
                figure_scale=ref_pie_fs,
                legend_fontsize=ref_pie_legend_fs,
            )
        builder.add_table_and_image_keep_together(
            tbl_pdf,
            table_caption="Résultats des contrôles",
            col_widths=[avail_w * 0.44, avail_w * 0.28, avail_w * 0.28],
            col_aligns=["LEFT", "RIGHT", "RIGHT"],
            image_path=Path(pie_path) if pie_path else None,
            image_width_ratio=ref_pie_w,
        )
    elif show_placeholder:
        builder.add_paragraph("Aucune donnée de résultat de contrôle sur la période.")

    builder.add_section("sec2_3", "2.3. Activité procédurale", level=2, toc_level=1)
    builder.append_pending_paragraph(
        "Les effectifs PEJ du tableau ci-dessous regroupent les saisines engagées à l’issue "
        "des contrôles réalisés sur la période et les saisines PEJ ouvertes hors activité de "
        "contrôle."
    )
    if proc_theme is not None and not proc_theme.empty:
        tbl = [["Thème", "PEJ", "PA"]]
        for _, row in proc_theme.head(25).iterrows():
            tbl.append(
                [
                    _wrap_table_label(row["theme"]),
                    str(int(row.get("nb_pej", 0))),
                    str(int(row.get("nb_pa", 0))),
                ]
            )
        builder.add_table(
            tbl,
            caption=pdf_metric_caption("Procédures par thème", "proc"),
            col_widths=[avail_w * 0.52, avail_w * 0.24, avail_w * 0.24],
            col_aligns=["LEFT", "RIGHT", "RIGHT"],
        )
    elif show_placeholder:
        builder.append_pending_paragraph("Aucune procédure sur la période.")
        builder.add_keep_together_block([])

    # ── 3. Activité par type d'usager ──
    builder.add_section("sec3", "3. Activité de police par type d'usager", start_on_new_page=True)
    builder.append_pending_paragraph(
        "Pour la partie contrôles : cumul des <b>effectifs</b> par type d'usager (chaque usager "
        "renseigné sur une fiche est compté avec son effectif ; ces effectifs sont calculés au "
        "niveau des fiches de contrôle et ne se confondent donc pas avec le nombre de "
        "localisations de contrôle), des PEJ ouvertes à l'issue d'un contrôle et des PEJ hors "
        "fiche contrôle, "
        "ventilés par thème du plan de contrôle (détail en § 3.1). "
        "Pour la partie procédurale (§ 3.3) : une procédure ne comporte qu'un seul type d'usager."
    )

    pie_data = _pie_data_controles_par_type_usager(act_par_type)
    if pie_data:
        pie_path = chart_pie(
            pie_data,
            "Répartition des effectifs contrôlés et saisines PEJ hors contrôle par type d'usager",
            tmp_dir,
            "pie_synthese_controles_par_type_usager.png",
            legend_percent_only=True,
            figure_scale=ref_pie_fs,
            **_chart_pie_compact_legend_kw(
                len(pie_data),
                legend_fontsize=ref_pie_legend_fs,
            ),
        )
        builder.append_pending_image(
            Path(pie_path),
            width_ratio=ref_pie_w,
            spacer_after_mm=0.4,
        )

    builder.add_section(
        "sec3_1",
        "3.1. Thème de contrôle par type d'usager",
        level=2,
        toc_level=1,
        start_on_new_page=True,
    )
    col_w_ut = [
        avail_w * 0.36,
        avail_w * 0.14,
        avail_w * 0.14,
        avail_w * 0.14,
        avail_w * 0.22,
    ]
    col_a_ut = ["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"]
    if act_ut is not None and not act_ut.empty:
        type_order = (
            act_ut.groupby("type_usager")["nb_total"]
            .sum()
            .sort_values(ascending=False)
            .index
        )

        def _subtable_for_type(tu) -> list[list[str]] | None:
            sub = act_ut[act_ut["type_usager"].astype(str) == str(tu)].copy()
            sub = sub.sort_values("nb_total", ascending=False, kind="stable")
            if sub.empty:
                return None
            return _build_usager_theme_table_rows(sub)

        for tu in type_order:
            tbl = _subtable_for_type(tu)
            if not tbl:
                continue
            builder.add_table(
                tbl,
                caption=pdf_metric_caption(
                    f"Thèmes de contrôle — {_display_type_usager(tu)}", "effectifs"
                ),
                col_widths=col_w_ut,
                col_aligns=col_a_ut,
                keep_together=False,
                keep_caption_with_table=True,
                spacer_after_mm=1.0,
            )
        builder.add_paragraph(_SEC3_1_TABLE_NOTE)
    elif show_placeholder:
        builder.append_pending_paragraph("Aucune donnée type d'usager disponible.")
        builder.add_keep_together_block([])

    builder.add_section(
        "sec3_2",
        "3.2. Résultat des contrôles par type d'usager",
        level=2,
        toc_level=1,
    )
    if res_usager is not None and not res_usager.empty:
        labels = [_display_type_usager(x) for x in res_usager["type_usager"].tolist()]
        series: dict[str, list[int]] = {
            "Conforme": [int(x) for x in res_usager["Conforme"].tolist()],
            "Infraction": [int(x) for x in res_usager["Infraction"].tolist()],
            "Manquement": [int(x) for x in res_usager["Manquement"].tolist()],
        }
        if "Autre_resultat" in res_usager.columns and int(res_usager["Autre_resultat"].sum()) > 0:
            series["En attente"] = [int(x) for x in res_usager["Autre_resultat"].tolist()]
        bar_path = chart_bar_horizontal_stacked(
            labels,
            series,
            pdf_metric_caption("Résultats des contrôles par type d'usager", "effectifs"),
            "Effectifs",
            tmp_dir,
            "bar_synthese_resultats_usager.png",
            figure_scale=0.88,
        )
        builder.add_image(Path(bar_path), width_ratio=0.88, spacer_after_mm=1.0)

        has_autre = "Autre_resultat" in res_usager.columns and int(res_usager["Autre_resultat"].sum()) > 0
        total_global = float(
            res_usager["Conforme"].sum()
            + res_usager["Infraction"].sum()
            + res_usager["Manquement"].sum()
            + (res_usager["Autre_resultat"].sum() if has_autre else 0)
        ) or 1.0
        tbl_res = [
            [
                "Type d'usager",
                "Conforme",
                "Infraction",
                "Manquement",
                *(["En attente"] if has_autre else []),
                "Total",
                "% du total",
            ]
        ]
        for _, row in res_usager.iterrows():
            c = int(row.get("Conforme", 0))
            i = int(row.get("Infraction", 0))
            m = int(row.get("Manquement", 0))
            a = int(row.get("Autre_resultat", 0)) if has_autre else 0
            t = c + i + m + a
            tbl_res.append(
                [
                    _truncate_with_dash(_display_type_usager(row.get("type_usager", "")), 34),
                    str(c),
                    str(i),
                    str(m),
                    *( [str(a)] if has_autre else [] ),
                    str(t),
                    _pct_table_cell(t, total_global),
                ]
            )
        builder.add_table(
            tbl_res,
            caption=pdf_metric_caption("Résultats des contrôles par type d'usager", "effectifs"),
            keep_together=True,
        )
    elif show_placeholder:
        builder.add_paragraph("Aucun résultat par type d'usager.")

    builder.add_section("sec3_3", "3.3. Activité procédurale par type d'usager", level=2, toc_level=1)
    if proc_ut is not None and not proc_ut.empty:
        types = proc_ut["type_usager"].dropna().astype(str).unique().tolist()
        first = True
        for tu in types:
            sub = proc_ut[proc_ut["type_usager"].astype(str) == tu].copy()
            sub = sub.sort_values(["nb_pej", "nb_pa"], ascending=False, kind="stable")
            if sub.empty:
                continue
            if not first:
                builder.add_spacer(1.5)
            first = False
            tbl = [["Thème", "PEJ", "PA"]]
            for _, row in sub.head(15).iterrows():
                tbl.append(
                    [
                        str(row["theme"])[:40],
                        str(int(row.get("nb_pej", 0))),
                        str(int(row.get("nb_pa", 0))),
                    ]
                )
            builder.add_table(
                tbl,
                caption=pdf_metric_caption(
                    f"Procédures par thème — {_display_type_usager(tu)}", "proc"
                ),
                col_widths=[avail_w * 0.52, avail_w * 0.24, avail_w * 0.24],
                col_aligns=["LEFT", "RIGHT", "RIGHT"],
                keep_together=True,
            )
    elif show_placeholder:
        builder.add_paragraph("Aucune procédure ventilée par type d'usager.")

    # ── 4. PVe (source OFB, hors périmètre type d'usager OSCEAN) ──
    builder.add_section("sec4", "4. Procès-verbaux électroniques (PVe)", start_on_new_page=True)
    builder.add_paragraph(
        "Les procès-verbaux électroniques (PVe) proviennent du fichier national OFB "
        "(<i>Stats_PVe_OFB</i>). Ils recensent des infractions constatées et intégrées sur la "
        f"période du {date_deb.date():%d/%m/%Y} au {date_fin.date():%d/%m/%Y} "
        "(date d'intégration <i>INF-DATE-INTG</i>). Ils ne sont pas rattachés aux fiches de "
        "contrôle OSCEAN ni ventilés par type d'usager : cette section les présente "
        "selon leur propre nomenclature (NATINF et classe d'infraction)."
    )
    pve_natinf = _sort_desc(_load_csv_opt(out_dir, "pve_global_par_natinf.csv"), ["nb"])
    pve_classe = _sort_desc(_load_csv_opt(out_dir, "synthese_pve_par_classe.csv"), ["nb"])

    if nb_pve > 0:
        if pve_natinf is not None and not pve_natinf.empty:
            natinf_label_w = avail_w * 0.72
            builder.add_table(
                _build_pve_natinf_table_rows(
                    pve_natinf,
                    label_col_width_pt=natinf_label_w,
                ),
                caption=pdf_metric_caption("Principales natures d'infraction (NATINF)", "proc"),
                col_widths=[natinf_label_w, avail_w * 0.28],
                col_aligns=["LEFT", "RIGHT"],
                keep_together=True,
            )
        if pve_classe is not None and not pve_classe.empty:
            tbl_cl = [["Classe d'infraction", "Nombre de PVe"]]
            total_cl = float(pve_classe["nb"].sum()) or 1.0
            for _, row in pve_classe.iterrows():
                lib = str(row.get("libelle_classe") or row.get("classe") or "-")
                nbv = int(row["nb"])
                tbl_cl.append([lib, f"{nbv} ({_pct_table_cell(nbv, total_cl)})"])
            builder.add_table(
                tbl_cl,
                caption=pdf_metric_caption("PVe par classe d'infraction", "proc"),
                col_widths=[avail_w * 0.60, avail_w * 0.40],
                col_aligns=["LEFT", "RIGHT"],
                keep_together=True,
            )
    elif show_placeholder:
        builder.add_paragraph("Aucun procès-verbal électronique sur la période.")

    # ── 5. Cartographie ──
    builder.add_section("sec5", "5. Cartographie", start_on_new_page=True)
    if cartes:
        map_id = str(profile.get("_map_id") or profil_id)
        map_paths = resolve_profile_map_paths(map_id, profile=profile, presentation_cfg=presentation_cfg)
        map_layout = resolve_map_layout(profile=profile, presentation_cfg=presentation_cfg)
        if map_paths:
            builder.add_maps(map_paths, layout=map_layout)
        elif show_placeholder:
            expected = expected_map_filenames(map_id, profile=profile, presentation_cfg=presentation_cfg)
            files_hint = ", ".join(f"<b>{n}</b>" for n in expected) or f"<b>carte_{map_id}.png</b>"
            builder.add_paragraph(
                f"<i>Carte(s) non disponible(s). Déposez {files_hint} dans le dossier des cartes.</i>"
            )
    elif show_placeholder:
        builder.add_paragraph("<i>Cartographie désactivée pour ce bilan.</i>")

    # ── 6. Annexes ──
    builder.add_section("sec6", "6. Annexes", start_on_new_page=True)
    methodo = build_sec6_methodology_html(
        effective_cfg=presentation_cfg,
        context=build_sec6_methodology_context(
            period_str=f"du {date_deb.date():%d/%m/%Y} au {date_fin.date():%d/%m/%Y}",
            dept_name=f"de la {dept_name_typo}",
            dept_code=str(dept_code),
            profile_label=profile_label or "Synthèse PA / PJ",
            profile_id=profil_id,
            diffusion=diffusion,
            nb_ctrl=nb_ctrl,
            nb_pej=nb_pej,
            nb_pa=nb_pa,
            nb_pve=nb_pve,
            ventilation_mode="globale",
            show_usagers=is_section_enabled(presentation_cfg, "sec3", True),
        ),
    )
    builder.add_methodology(methodo)
    gloss_cfg = load_glossary_config(_ROOT)
    glossaire_rows = build_filtered_glossary_rows(
        gloss_cfg=gloss_cfg,
        nb_ctrl=nb_ctrl,
        nb_pej=nb_pej,
        nb_pa=nb_pa,
        nb_pve=nb_pve,
    )
    if glossaire_rows:
        builder.add_glossary(
            glossaire_rows,
            col_widths=[avail_w * 0.25, avail_w * 0.75],
            col_aligns=["LEFT", "LEFT"],
        )

    builder.build()
