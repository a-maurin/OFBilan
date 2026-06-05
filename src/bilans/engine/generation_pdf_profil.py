"""Rendu PDF du profil global (moteur unique)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image as PILImage

from bilans.common.chart_display_config import (
    clamp_uniform_pie_ratio,
    compute_pdf_ratios,
    load_chart_display_config,
    resolve_reference_pie_display,
)
from bilans.common.dataframe_rollup import rollup_small_categories
from bilans.common.rendus_graphiques import (
    chart_bar_horizontal_stacked,
    chart_bar_stacked,
    chart_line_evolution,
    chart_pie,
    chart_stackplot_resultats_domaine,
)
from bilans.common.pdf_presentation_config import (
    apply_diffusion_pdf_suffix,
    build_title_lines_from_cfg,
    get_block_int,
    is_block_enabled,
    is_section_enabled,
    normalize_dept_typography,
    resolve_charte_config,
    resolve_pdf_presentation_config,
    inject_sec4_subsections,
    resolve_section_titles,
    resolve_sec34_render_order,
    resolve_sections_for_toc,
    resolve_tables_layout,
    resolve_title_page_config,
    should_show_placeholder,
    format_proc_detail_caption,
    slice_proc_detail_for_pdf,
)
from bilans.common.pdf_report_builder import PDFReportBuilder
from bilans.common.pdf_utils import ofb_table, truncate_text_to_width, wrap_plain_text_for_pdf_paragraph
from bilans.common.pdf_table_sort import (
    PDF_LABEL_CTRL_LOCATIONS,
    PDF_LABEL_CTRL_LOCATIONS_SHORT,
    PDF_LABEL_NON_CONFORME_LOCATIONS,
    PDF_LABEL_PEJ_COUNT,
    pdf_metric_caption,
    resultat_controle_label_for_pdf,
    sort_dataframe_desc as _sort_desc,
    sort_tab_resultats_controles_for_pdf,
)
from bilans.common.pdf_usagers_domaine_table import (
    build_usagers_x_domaine_pdf_rows,
    resolve_usagers_x_domaine_header_layout,
    resolve_usagers_x_domaine_header_font_size,
    resolve_usagers_x_domaine_header_max_lines,
    usagers_x_domaine_col_widths,
)
from bilans.common.pdf_shared_sections import (
    add_procedures_par_type_usager_subsection,
    add_standard_cover_and_toc,
    add_standard_notice_methodology,
    build_filtered_glossary_rows,
    build_sec6_methodology_context,
    build_sec6_methodology_html,
    load_glossary_config,
    summarize_procedures_par_type_usager,
)
from bilans.common.percent_format import (
    format_pct_int_from_rate,
    int_percents_largest_remainder,
    tab_counts_to_pct_strings,
)
from bilans.common.utilitaires_metier import _load_csv_opt
from bilans.common.bilan_config import BilanConfig, resolve_perimetre_kwargs
from bilans.engine.registre_sections_pdf import SectionRegistry
from bilans.common.carte_helper import (
    expected_map_filenames,
    resolve_map_layout,
    resolve_profile_map_paths,
)
from bilans.common.cartographie_config import (
    expected_map_filenames_for_selection,
    has_cartography_catalog,
    resolve_selected_map_paths,
)
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage, Paragraph, Spacer

_ROOT = Path(__file__).resolve().parents[3]

VENTILATION_SEUIL_JOURS_GLOBAL = 366


def resolve_ventilation_mode_global(date_deb: pd.Timestamp, date_fin: pd.Timestamp) -> str:
    """Détermine le mode global de ventilation temporelle (aligné sur les profils thématiques)."""
    from bilans.engine.ventilation_temporelle import resolve_ventilation_auto

    duree_jours = int((date_fin - date_deb).days)
    return resolve_ventilation_auto(duree_jours, seuil_jours=int(VENTILATION_SEUIL_JOURS_GLOBAL))


def generate_profile_pdf_report(
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
    diffusion: str = "interne",
    cartes: bool = True,
) -> None:
    """Point d’entrée moteur unique pour générer le PDF d'un profil."""
    date_deb_ts = pd.to_datetime(date_deb) if date_deb is not None else pd.Timestamp("2025-01-01")
    date_fin_ts = pd.to_datetime(date_fin) if date_fin is not None else pd.Timestamp("2026-02-05")
    echelle_res, code_res = resolve_perimetre_kwargs(
        echelle=echelle, code=code, dept_code=dept_code
    )

    generate_pdf_report(
        out_dir,
        profile=profile or {},
        date_deb=date_deb_ts,
        date_fin=date_fin_ts,
        echelle=echelle_res,
        code=code_res,
        ventilation_mode=ventilation_mode,
        chart_preset=chart_preset,
        output_filename=output_filename,
        diffusion=diffusion,
        cartes=cartes,
    )


from bilans.engine.pdf_utils import (
    truncate_with_dash as _truncate_with_dash,
    nb_non_conformes_brut as _nb_non_conformes_brut,
    pct_table_cell as _pct_table_cell,
)


def _build_rows_resultats_controles_pdf(tr: pd.DataFrame) -> list[list[str]]:
    """Tableau PDF 3 colonnes (bilan global : sans colonne zones PNF)."""
    tbl = [["Résultat", "Nombre", "Taux"]]
    strip_res = tr["resultat"].astype(str).str.strip()
    top_mask = strip_res.isin(["Conforme", "Non-conforme", "En attente"])
    top_counts = tr.loc[top_mask, "nb"].astype(int).tolist()
    top_rates = tab_counts_to_pct_strings(top_counts) if top_counts else []
    j = 0
    nb_nc = int(tr.loc[strip_res.eq("Non-conforme"), "nb"].sum())
    for _, row in tr.iterrows():
        rlib = str(row["resultat"])
        nbv = int(row["nb"])
        if rlib.strip() in ("Dont infraction", "Dont manquement"):
            t = format_pct_int_from_rate((nbv / nb_nc) if nb_nc > 0 else None)
        elif rlib.strip() in ("Conforme", "Non-conforme", "En attente"):
            t = top_rates[j] if j < len(top_rates) else "n.d."
            j += 1
        else:
            t = "n.d."
        tbl.append([resultat_controle_label_for_pdf(rlib), str(nbv), t])
    return tbl





def _chart_pie_compact_legend_kw(
    n_categories: int,
    *,
    legend_fontsize: float,
    legend_ncol_max: int,
) -> dict[str, float | int]:
    # Colonnes fixes (pilotées par YAML) ; seules les lignes varient.
    ncol = min(n_categories, max(1, legend_ncol_max))
    return {
        "legend_fontsize": legend_fontsize,
        "legend_ncol": max(1, ncol),
    }


def generate_pdf_report(
    out_dir: Path,
    *,
    profile: dict,
    date_deb: pd.Timestamp,
    date_fin: pd.Timestamp,
    echelle: str,
    code: str,
    ventilation_mode: str = "globale",
    chart_preset: str | None = None,
    output_filename: str | None = None,
    diffusion: str = "interne",
    cartes: bool = True,
) -> None:
    from bilans.common.rendus_graphiques import apply_mpl_style

    apply_mpl_style()
    _generate_pdf_content(
        out_dir,
        profile=profile,
        date_deb=date_deb,
        date_fin=date_fin,
        echelle=echelle,
        code=code,
        ventilation_mode=ventilation_mode,
        chart_preset=chart_preset,
        output_filename=output_filename,
        diffusion=diffusion,
        cartes=cartes,
    )


def _generate_pdf_content(
    out_dir: Path,
    *,
    profile: dict,
    date_deb: pd.Timestamp,
    date_fin: pd.Timestamp,
    echelle: str,
    code: str,
    ventilation_mode: str = "globale",
    chart_preset: str | None = None,
    output_filename: str | None = None,
    diffusion: str = "interne",
    cartes: bool = True,
) -> None:
    chart_ratios = compute_pdf_ratios(load_chart_display_config(_ROOT, preset=chart_preset))
    scope = str((profile or {}).get("presentation_scope", "global")).strip() or "global"
    profile_id = str((profile or {}).get("id", "")).strip() or None
    resolved_presentation_cfg = resolve_pdf_presentation_config(
        _ROOT, scope=scope, profile_id=profile_id, diffusion=diffusion
    )
    presentation_cfg = (
        resolved_presentation_cfg.get("effective", {}) if isinstance(resolved_presentation_cfg, dict) else {}
    )
    behavior_cfg = (
        resolved_presentation_cfg.get("behavior", {}) if isinstance(resolved_presentation_cfg, dict) else {}
    )
    show_placeholder = should_show_placeholder(behavior_cfg if isinstance(behavior_cfg, dict) else None)

    tab_resultats = _load_csv_opt(out_dir, "controles_global_resultats.csv")
    tab_resultats_controles = _load_csv_opt(out_dir, "controles_global_resultats_controles.csv")
    agg_domaine = _load_csv_opt(out_dir, "controles_global_par_domaine.csv")
    agg_theme = _load_csv_opt(out_dir, "controles_global_par_theme.csv")
    agg_usager = _load_csv_opt(out_dir, "controles_global_par_usager.csv")
    res_usager = _load_csv_opt(out_dir, "controles_global_resultats_par_type_usager.csv")
    cross_usager_dom = _load_csv_opt(out_dir, "controles_global_usager_par_domaine.csv")
    usagers_resume = _load_csv_opt(out_dir, "controles_global_usagers_resume.csv")
    if ventilation_mode == "mensuelle":
        agg_periode = _load_csv_opt(out_dir, "indicateurs_global_par_mois.csv")
    elif ventilation_mode == "trimestrielle":
        agg_periode = _load_csv_opt(out_dir, "indicateurs_global_par_trimestre.csv")
    elif ventilation_mode == "hebdomadaire":
        agg_periode = _load_csv_opt(out_dir, "indicateurs_global_par_semaine.csv")
    else:
        agg_periode = _load_csv_opt(out_dir, "indicateurs_global_par_annee.csv")
    pej_resume = _load_csv_opt(out_dir, "pej_global_resume.csv")
    pa_resume = _load_csv_opt(out_dir, "pa_global_resume.csv")
    pve_resume = _load_csv_opt(out_dir, "pve_global_resume.csv")
    ops_resume = _load_csv_opt(out_dir, "controles_global_operations_resume.csv")

    nb_localisations = 0
    if agg_domaine is not None and not agg_domaine.empty:
        nb_localisations = int(agg_domaine["nb"].sum())
    nb_pej = int(pej_resume["nb_pej_global"].iloc[0]) if pej_resume is not None and not pej_resume.empty else 0
    nb_pa = int(pa_resume["nb_pa_global"].iloc[0]) if pa_resume is not None and not pa_resume.empty else 0
    nb_pve = int(pve_resume["nb_pve_global"].iloc[0]) if pve_resume is not None and not pve_resume.empty else 0
    nb_ops = int(ops_resume["nb_operations_controle"].iloc[0]) if ops_resume is not None and not ops_resume.empty and "nb_operations_controle" in ops_resume.columns else 0

    cfg = BilanConfig.from_strings(
        str(date_deb.date()),
        str(date_fin.date()),
        echelle=echelle,
        code=code,
        root=_ROOT,
    )
    perimetre_typo = (
        normalize_dept_typography(cfg.perimetre_name)
        if cfg.echelle == "departement"
        else cfg.perimetre_name
    )

    cover_title_lines, header_title_lines = build_title_lines_from_cfg(
        presentation_cfg,
        profile_label="",
        perimetre_name_typo=perimetre_typo,
        echelle=cfg.echelle,
    )
    report_header = " — ".join(line.strip() for line in header_title_lines if line.strip())
    map_captions: list[str] = []
    if cartes and has_cartography_catalog(profile):
        from bilans.common.utilitaires_metier import resolve_carto_dept_code

        selected = list(profile.get("_cartes_selection") or [])
        carto_dept = resolve_carto_dept_code(cfg.echelle, cfg.code)
        global_map_paths, map_captions = resolve_selected_map_paths(
            profile, selected, carto_dept=carto_dept, target_dir=out_dir
        )
        global_map_layout = resolve_map_layout(profile=profile, presentation_cfg=presentation_cfg)
        map_id = str(profile.get("id", "global")).strip() or "global"
    elif cartes:
        map_id = str(profile.get("_map_id") or "global").strip() or "global"
        global_map_paths = resolve_profile_map_paths(
            map_id, profile=profile, presentation_cfg=presentation_cfg, target_dir=out_dir
        )
        global_map_layout = resolve_map_layout(profile=profile, presentation_cfg=presentation_cfg)
    else:
        map_id = str(profile.get("_map_id") or "global").strip() or "global"
        global_map_paths = []
        global_map_layout = "vertical"

    resolved_output_name = str(output_filename or "").strip() or "bilan_global.pdf"
    pdf_path = apply_diffusion_pdf_suffix(out_dir / resolved_output_name, diffusion)
    chart_bar_w = chart_ratios["chart_base"]
    legend_fontsize = float(chart_ratios.get("legend_fontsize", 8.0))
    legend_ncol_max = int(chart_ratios.get("legend_ncol_max", 4.0))
    figure_scale = float(chart_ratios.get("figure_scale", 1.0))

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

    agg_domaine = _sort_desc(agg_domaine, ["nb"])
    agg_theme = _sort_desc(agg_theme, ["nb"])
    tab_resultats = _sort_desc(tab_resultats, ["nb"])
    if tab_resultats_controles is not None and not tab_resultats_controles.empty:
        tab_resultats_controles = sort_tab_resultats_controles_for_pdf(tab_resultats_controles)
    agg_usager = _sort_desc(agg_usager, ["nb"])
    res_usager = _sort_desc(res_usager, ["Total", "Conforme", "Infraction", "Manquement"])
    cross_usager_dom = _sort_desc(cross_usager_dom, ["total"])

    sec21_titre = (
        "2.1. Indicateurs hebdomadaires"
        if ventilation_mode == "hebdomadaire"
        else "2.1. Indicateurs de la période"
    )
    section_defs = [
        ("sec1", "1. Chiffres clés"),
        ("sec2_chap", "2. Contrôles et procédures"),
        ("sec21", sec21_titre),
        ("sec22", "2.2. Répartition de l'activité par domaines (contrôles + PEJ)"),
        ("sec22theme", "2.3. Nombre de contrôles par thèmes"),
        ("sec22res", "2.4. Résultats des contrôles"),
        ("sec4", "3. Activité par type d’usager"),
        ("sec3", "4. Procédures (PEJ, PA, PVe)"),
        ("sec31", "4.1 Procès-verbaux électroniques (PVe)"),
        ("sec32", "4.2 Procédures d’enquête judiciaire (PEJ)"),
        ("sec33", "4.3 Procédures administratives (PA)"),
        ("sec5map", "5. Localisation cartographique"),
        ("sec6", "6. Annexes"),
    ]
    section_defs = inject_sec4_subsections(section_defs)
    resolved_section_defs = resolve_section_titles(presentation_cfg, section_defs)
    sections = resolve_sections_for_toc(presentation_cfg, resolved_section_defs)
    section_title = {sid: title for sid, title in resolved_section_defs}

    tables_layout = resolve_tables_layout(presentation_cfg)
    charte_cfg = resolve_charte_config(presentation_cfg)
    title_page_cfg = resolve_title_page_config(_ROOT, scope=scope, profile_id=profile_id)
    
    from reportlab.lib.pagesizes import A4, landscape
    pagesize = landscape(A4) if echelle == "region" else A4
    
    builder = PDFReportBuilder(
        pdf_path=pdf_path,
        header_title=report_header,
        title=" — ".join(header_title_lines),
        author="Office français de la biodiversité",
        tables_layout=tables_layout,
        charte_config=charte_cfg,
        diffusion=diffusion,
        title_page_config=title_page_cfg,
        pagesize=pagesize,
    )
    avail_w = builder.avail_w
    tmp_dir = builder.tmp_dir

    add_standard_cover_and_toc(
        builder,
        project_root=_ROOT,
        scope=scope,
        cover_title_lines=cover_title_lines,
        period_str=f"Période : du {date_deb.date():%d/%m/%Y} au {date_fin.date():%d/%m/%Y}",
        sections_toc=sections,
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



    from bilans.engine.pdf_context import PdfContext
    from bilans.engine.sections_profil import (
        render_sec1, render_sec2_chap, render_sec21, render_sec22, render_sec22theme,
        render_sec22res, render_sec3, render_sec31, render_sec32, render_sec33,
        render_sec4, render_sec42, render_sec43, render_sec44, render_sec5map, render_sec6
    )
    
    ctx = PdfContext(
        builder=builder,
        profile=profile,
        presentation_cfg=presentation_cfg,
        behavior_cfg=behavior_cfg,
        show_placeholder=show_placeholder,
        date_deb=date_deb,
        date_fin=date_fin,
        dept_code=cfg.code,
        dept_name_typo=perimetre_typo,
        diffusion=diffusion,
        ventilation_mode=ventilation_mode,
        out_dir=out_dir,
        avail_w=avail_w,
        tmp_dir=tmp_dir,
        chart_bar_w=chart_bar_w,
        legend_fontsize=legend_fontsize,
        legend_ncol_max=legend_ncol_max,
        figure_scale=figure_scale,
        ref_pie_w=ref_pie_w,
        ref_pie_fs=ref_pie_fs,
        ref_pie_legend_fs=ref_pie_legend_fs,
        split_by_row=bool(tables_layout.get("split_by_row")),
        tables_layout=tables_layout,
        section_title=section_title,
        nb_localisations=nb_localisations,
        nb_ops=nb_ops,
        nb_pej=nb_pej,
        nb_pa=nb_pa,
        nb_pve=nb_pve,
        tab_resultats=tab_resultats,
        tab_resultats_controles=tab_resultats_controles,
        agg_domaine=agg_domaine,
        agg_theme=agg_theme,
        agg_usager=agg_usager,
        res_usager=res_usager,
        cross_usager_dom=cross_usager_dom,
        usagers_resume=usagers_resume,
        agg_periode=agg_periode,
        pej_dom=None,
        cartes=cartes,
        global_map_paths=global_map_paths,
        global_map_layout=global_map_layout,
        map_captions=map_captions,
        map_id=map_id,
    )

    registry = SectionRegistry()
    registry.register("sec1", render_sec1)
    registry.register("sec2", render_sec2_chap)  # Le YAML utilise l'ID "sec2" pour le titre de chapitre
    registry.register("sec21", render_sec21)
    registry.register("sec22", render_sec22)
    registry.register("sec22theme", render_sec22theme)
    registry.register("sec22res", render_sec22res)
    registry.register("sec3", render_sec3)
    registry.register("sec31", render_sec31)
    registry.register("sec32", render_sec32)
    registry.register("sec33", render_sec33)
    registry.register("sec4", render_sec4)
    registry.register("sec42", render_sec42)
    registry.register("sec43", render_sec43)
    registry.register("sec44", render_sec44)
    registry.register("sec5map", render_sec5map)
    registry.register("sec6", render_sec6)
    
    from bilans.engine.sections_region import render_sec_region_detail
    registry.register("secregion", render_sec_region_detail)
    if echelle == "region":
        # Inject just before sec5map or sec6
        insert_idx = len(sections)
        for i, (sid, _) in enumerate(sections):
            if sid in ("sec5map", "sec6"):
                insert_idx = i
                break
        sections.insert(insert_idx, ("secregion", "7. Détail par département"))
        section_title["secregion"] = "7. Détail par département"

    # Pilotage dynamique : on itère sur les sections résolues depuis le YAML
    for sec_id, _ in sections:
        if registry.get(sec_id):
            registry.render(sec_id, ctx)

    builder.build()