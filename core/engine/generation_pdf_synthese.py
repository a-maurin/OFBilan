"""Rendu PDF du profil synthese_activite_PA_PJ."""

from __future__ import annotations

import textwrap
from html import escape
from pathlib import Path

import pandas as pd

from ofbilan.common.carte_helper import (
    expected_map_filenames,
    resolve_map_layout,
    resolve_profile_map_paths,
)
from ofbilan.common.dataframe_rollup import rollup_small_categories as _rollup_small_categories
from ofbilan.common.pdf_presentation_config import (
    apply_diffusion_pdf_suffix,
    build_title_lines_from_cfg,
    is_section_enabled,
    normalize_dept_typography,
    resolve_charte_config,
    resolve_pdf_presentation_config,
    resolve_title_page_config,
    should_show_placeholder,
)
from ofbilan.common.pdf_report_builder import PDFReportBuilder
from ofbilan.common.pdf_utils import truncate_text_to_width
from ofbilan.common.pdf_shared_sections import (
    add_standard_cover_and_toc,
    add_standard_notice_methodology,
    build_filtered_glossary_rows,
    build_sec6_methodology_context,
    build_sec6_methodology_html,
    load_glossary_config,
)
from ofbilan.common.pdf_table_sort import (
    pdf_metric_caption,
    sort_dataframe_desc as _sort_desc,
)
from ofbilan.common.percent_format import format_pct_int_from_rate, tab_counts_to_pct_strings
from ofbilan.common.chart_display_config import (
    clamp_uniform_pie_ratio,
    compute_pdf_ratios,
    load_chart_display_config,
    resolve_reference_pie_display,
)
from ofbilan.common.rendus_graphiques import apply_mpl_style, chart_bar_horizontal_stacked, chart_pie
from ofbilan.common.utilitaires_metier import (
    _load_csv_opt,
    format_type_usager_display,
)
from ofbilan.common.bilan_config import BilanConfig, resolve_perimetre_kwargs

_KEY_FIGURES_GRAIN_NOTE = (
    "Les localisations comptent les points de contrôle, tandis que les effectifs "
    "d'usagers sont comptés par fiche de contrôle ; ils peuvent donc être "
    "inférieurs ou supérieurs."
)


from ofbilan.engine.pdf_utils import (
    truncate_with_dash as _truncate_with_dash,
    nb_non_conformes_brut as _nb_non_conformes_brut,
    pct_table_cell as _pct_table_cell,
)


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
    nb_operations_controle: int,
    nb_localisations: int,
    nb_nc: int,
    nb_pej: int,
    nb_pa: int,
    nb_pve: int,
) -> list[list[tuple[str, str]]]:
    row1: list[tuple[str, str]] = []
    if nb_effectifs > 0:
        row1.append((str(nb_effectifs), "Effectifs d'usagers contrôlés"))
    if nb_operations_controle > 0:
        row1.append((str(nb_operations_controle), "Opérations de contrôle"))
    if nb_localisations > 0:
        row1.append((str(nb_localisations), "Localisations des contrôles"))
        if nb_nc > 0:
            row1.append((str(nb_nc), "Contrôles non-conformes"))
            row1.append(
                (format_pct_int_from_rate(nb_nc / nb_localisations), "Taux de non-conformités")
            )
    row2: list[tuple[str, str]] = []
    if nb_pej > 0:
        row2.append((str(nb_pej), "Procédures judiciaires"))
    row2.append((str(nb_pa), "Nombre de PA"))
    if nb_pve > 0:
        row2.append((str(nb_pve), "Nombre de PVe"))
    rows = [row1]
    if row2:
        rows.append(row2)
    return rows

_ROOT = Path(__file__).resolve().parents[2]
PROFILE_ID = "synthese_activite_PA_PJ"


def generate_synthese_pdf_report(
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
    brochure: bool = False,
) -> None:
    del chart_preset, brochure
    apply_mpl_style()
    profile = profile or {"id": PROFILE_ID}
    date_deb_ts = pd.to_datetime(date_deb) if date_deb is not None else pd.Timestamp("2025-01-01")
    date_fin_ts = pd.to_datetime(date_fin) if date_fin is not None else pd.Timestamp("2026-02-05")
    echelle_res, code_res = resolve_perimetre_kwargs(
        echelle=echelle, code=code, dept_code=dept_code
    )
    _generate_synthese_pdf(
        out_dir,
        profile=profile,
        date_deb=date_deb_ts,
        date_fin=date_fin_ts,
        echelle=echelle_res,
        code=code_res,
        output_filename=output_filename,
        diffusion=diffusion,
        cartes=cartes,
    )
    from ofbilan.engine.generation_pdf_synthese_brochure import (
        generate_synthese_brochure_pdf_report,
    )

    generate_synthese_brochure_pdf_report(
        out_dir,
        profile=profile,
        date_deb=date_deb_ts,
        date_fin=date_fin_ts,
        echelle=echelle_res,
        code=code_res,
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
    echelle: str,
    code: str,
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
    chart_bar_w = chart_ratios["chart_base"]
    legend_fontsize = float(chart_ratios.get("legend_fontsize", 8.0))
    legend_ncol_max = int(chart_ratios.get("legend_ncol_max", 4.0))
    figure_scale = float(chart_ratios.get("figure_scale", 1.0))

    cfg = BilanConfig.from_strings(
        str(date_deb.date()),
        str(date_fin.date()),
        echelle=echelle,
        code=code,
        root=_ROOT,
    )
    dept_name = cfg.perimetre_name
    dept_name_typo = (
        normalize_dept_typography(dept_name)
        if cfg.echelle == "departement"
        else dept_name
    )
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
    pve_natinf = _sort_desc(_load_csv_opt(out_dir, "pve_global_par_natinf.csv"), ["nb"])
    agg_domaine = _load_csv_opt(out_dir, "controles_global_par_domaine.csv")
    cross_usager_dom = _load_csv_opt(out_dir, "controles_global_usager_par_domaine.csv")
    usagers_resume = _load_csv_opt(out_dir, "controles_global_usagers_resume.csv")

    nb_localisations = int(resume.iloc[0]["nb_localisations"]) if resume is not None and not resume.empty else 0
    nb_operations_controle = int(resume.iloc[0]["nb_operations_controle"]) if resume is not None and not resume.empty and "nb_operations_controle" in resume.columns else 0
    nb_ops = nb_operations_controle
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
        ("sec4", "3. Activité de police par type d'usager"),
        ("sec4_1", "3.1. Thème de contrôle par type d'usager"),
        ("sec4_2", "3.2. Résultat des contrôles par type d'usager"),
        ("sec43", "3.3. Activité procédurale par type d'usager"),
        ("sec3", "4. Procédures (PEJ, PA, PVe)"),
        ("sec5map", "5. Cartographie"),
        ("sec6", "6. Annexes"),
    ]
    from ofbilan.common.pdf_presentation_config import resolve_sections_for_toc
    sections_toc = resolve_sections_for_toc(presentation_cfg, section_defs)
    cover_title_lines, header_title_lines = build_title_lines_from_cfg(
        presentation_cfg,
        profile_label="",
        perimetre_name_typo=dept_name_typo,
        echelle=cfg.echelle,
    )
    report_header = " — ".join(line.strip() for line in header_title_lines if line.strip())

    safe_name = dept_name.replace(" ", "_").replace("'", "")
    pdf_name = output_filename or f"{profil_id}_{safe_name}.pdf"
    pdf_path = apply_diffusion_pdf_suffix(out_dir / pdf_name, diffusion)
    charte_cfg = resolve_charte_config(presentation_cfg)
    
    from ofbilan.common.pdf_presentation_config import resolve_tables_layout
    tables_layout = resolve_tables_layout(presentation_cfg)
    
    map_captions: list[str] = []
    if cartes:
        from ofbilan.common.carte_helper import resolve_profile_map_paths, resolve_map_layout
        map_id = str(profile.get("_map_id") or "global").strip() or "global"
        global_map_paths = resolve_profile_map_paths(
            map_id, profile=profile, presentation_cfg=presentation_cfg, target_dir=out_dir
        )
        global_map_layout = resolve_map_layout(profile=profile, presentation_cfg=presentation_cfg)
    else:
        map_id = str(profile.get("_map_id") or "global").strip() or "global"
        global_map_paths = []
        global_map_layout = "vertical"
    title_page_cfg = resolve_title_page_config(_ROOT, scope=scope, profile_id=profil_id)
    
    from reportlab.lib.pagesizes import A4
    pagesize = A4
    
    builder = PDFReportBuilder(
        pdf_path=pdf_path,
        header_title=report_header,
        title=report_header,
        author="Office français de la biodiversité",
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


    from ofbilan.engine.pdf_context import PdfContext
    from ofbilan.engine.sections_synthese import (
        render_sec1, render_sec4_usagers, render_sec43, render_sec3_procedures, render_sec5, render_sec6
    )
    from ofbilan.engine.registre_sections_pdf import SectionRegistry
    
    ctx = PdfContext(
        builder=builder,
        profile=profile,
        presentation_cfg=presentation_cfg,
        behavior_cfg=behavior_cfg,
        show_placeholder=show_placeholder,
        date_deb=date_deb,
        date_fin=date_fin,
        dept_code=cfg.code,
        dept_name_typo=dept_name_typo,
        diffusion=diffusion,
        ventilation_mode="",
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
        section_title={},
        nb_localisations=nb_localisations,
        nb_ops=nb_ops,
        nb_effectifs=nb_effectifs,
        nb_pej=nb_pej,
        nb_pa=nb_pa,
        nb_pve=nb_pve,
        tab_resultats=tab_resultats,
        tab_resultats_controles=tab_res_ctrl,
        agg_domaine=agg_domaine,
        act_theme=act_theme,
        act_proc=proc_theme,
        pve_natinf=pve_natinf,
        pej_top=None,
        agg_usager=None,
        res_usager=res_usager,
        cross_usager_dom=cross_usager_dom,
        usagers_resume=usagers_resume,
        cartes=cartes,
        global_map_paths=global_map_paths,
        global_map_layout=global_map_layout,
        map_captions=map_captions,
        map_id="global",
    )

    registry = SectionRegistry()
    registry.register("sec1", render_sec1)
    registry.register("sec4", render_sec4_usagers)
    registry.register("sec43", render_sec43)
    registry.register("sec3", render_sec3_procedures)
    registry.register("sec5map", render_sec5)
    registry.register("sec6", render_sec6)
    
    from ofbilan.engine.sections_region import render_sec_region_detail
    registry.register("secregion", render_sec_region_detail)
    if cfg.echelle == "region":
        # Inject just before sec5map (cartographie) or sec6
        insert_idx = len(sections_toc)
        for i, (sid, _) in enumerate(sections_toc):
            if sid in ("sec5map", "sec6"):
                insert_idx = i
                break
        sections_toc.insert(insert_idx, ("secregion", "Détail par département"))
        ctx.section_title["secregion"] = "Détail par département"

    # Pilotage dynamique : on itère sur les sections résolues depuis le YAML
    for sec_id, _ in sections_toc:
        if registry.get(sec_id):
            registry.render(sec_id, ctx)
    builder.build()
