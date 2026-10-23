# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
# Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
# intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
# clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
# doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
# de l'auteur original (Aguirre MAURIN).

"""Module de rendu des sections PDF pour les bilans thématiques."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from core.chemins_projet import PROJECT_ROOT
from core.common.chargeurs_donnees import load_natinf_ref
from core.common.dataframe_rollup import rollup_small_categories
from core.common.percent_format import (
    format_pct_int_from_rate,
    int_percents_largest_remainder,
    tab_counts_to_pct_strings,
)
from core.common.pdf_presentation_config import (
    format_proc_detail_caption,
    get_block_int,
    is_block_enabled,
    is_section_enabled,
    resolve_sec2_render_order,
    slice_proc_detail_for_pdf,
)
from core.common.pdf_report_builder import PDFReportBuilder
from core.common.pdf_shared_sections import (
    add_procedures_par_type_usager_subsection,
    summarize_procedures_par_type_usager,
)
from core.common.pdf_table_sort import (
    PDF_LABEL_CTRL_LOCATIONS,
    PDF_LABEL_CTRL_LOCATIONS_SHORT,
    PDF_LABEL_NON_CONFORME_LOCATIONS,
    PDF_LABEL_PEJ,
    PDF_LABEL_PEJ_COUNT,
    build_resultats_par_usager_domaine_pdf_rows,
    pdf_column_label,
    pdf_metric_caption,
    prepare_pdf_results_sec23_sorting,
    resultat_controle_label_for_pdf,
    sort_dataframe_desc,
)
from core.common.pdf_usagers_domaine_table import (
    build_usagers_x_domaine_pdf_rows,
    resolve_usagers_x_domaine_header_font_size,
    resolve_usagers_x_domaine_header_layout,
    resolve_usagers_x_domaine_header_max_lines,
    usagers_x_domaine_col_widths,
)
from core.common.pdf_utils import wrap_plain_text_for_pdf_paragraph
from core.common.rendus_graphiques import (
    chart_bar,
    chart_bar_grouped,
    chart_bar_horizontal_stacked,
    chart_bar_stacked,
    chart_line_evolution,
    chart_pie,
)
from core.common.utilitaires_metier import (
    count_controles_non_conformes_oscean,
    est_chasse_point,
    zone_table_display_label,
)
from core.engine.filtres_profil import _get_insee_col
from core.engine.registre_sections_pdf import SectionRegistry

_log = logging.getLogger(__name__)


def _pct_table_cell(n: int | float, denom: float) -> str:
    if denom is None or denom <= 0:
        return "n.d."
    return format_pct_int_from_rate(float(n) / float(denom))


def _chart_pie_compact_legend_kw(
    n_categories: int,
    *,
    legend_fontsize: float,
    legend_ncol_max: int,
) -> dict[str, float | int]:
    """
    Harmonise le rendu des légendes de camembert entre global et thématique.
    """
    # Colonnes fixes (pilotées par YAML) ; seules les lignes varient.
    ncol = min(n_categories, max(1, legend_ncol_max))
    return {"legend_fontsize": legend_fontsize, "legend_ncol": max(1, ncol)}


def _pdf_section_pression_controle_usagers(
    builder: Any,
    results: dict,
    tmp_dir: Path,
    avail_w: float,
    targets: list[str],
    *,
    presentation_cfg: dict[str, Any],
    pie_ratio: float,
    legend_fontsize: float,
    legend_ncol_max: int,
    figure_scale: float,
) -> None:
    """Section 4 (profil usager ciblé) : effectifs par type d'usager, département entier."""
    df = results.get("pression_controle_tous_usagers")
    if df is None or df.empty:
        return

    targets_s = [str(t) for t in (targets or []) if str(t).strip()]
    if len(targets_s) == 1:
        cible_txt = f"« {targets_s[0]} »"
    elif len(targets_s) > 1:
        cible_txt = (
            ", ".join(f"« {t} »" for t in targets_s[:-1])
            + f" et « {targets_s[-1]} »"
        )
    else:
        cible_txt = "le type d'usager ciblé par ce bilan"

    if is_block_enabled(presentation_cfg, "sec4.show_intro_text", True):
        builder.add_paragraph(
            f"Ce bilan porte sur l'activité de contrôle à l'égard des usagers de type "
            f"{cible_txt}. Le graphique et le tableau ci-dessous situent la pression de "
            f"contrôle exercée sur ce(s) type(s) d'usager au regard de la répartition, sur "
            f"l'ensemble du département pour la période analysée, du nombre d'effectifs par "
            f"type d'usager (et non du seul nombre de localisations de contrôle). Ce total "
            f"d'effectifs est nécessairement supérieur ou égal au nombre de localisations, "
            f"car les contrôles multi-usagers répartissent plusieurs effectifs entre les "
            f"catégories renseignées sur une même fiche."
        )
        builder.add_spacer(2)

    pie_data = {str(r["type_usager"]): int(r["nb"]) for _, r in df.iterrows()}
    if is_block_enabled(presentation_cfg, "sec4.show_pie_usagers", True) and pie_data:
        pie_path = chart_pie(
            pie_data,
            "Répartition des effectifs par type d'usager",
            tmp_dir,
            "pie_pression_controle_usagers.png",
            **_chart_pie_compact_legend_kw(
                len(pie_data),
                legend_fontsize=legend_fontsize,
                legend_ncol_max=legend_ncol_max,
            ),
            figure_scale=figure_scale,
        )
        builder.add_image(Path(pie_path), width_ratio=pie_ratio, spacer_after_mm=0.8)

    if is_block_enabled(presentation_cfg, "sec4.show_table_usagers", True):
        total = int(df["nb"].sum())
        nbs = df["nb"].astype(int).tolist()
        pcts = tab_counts_to_pct_strings(nbs) if total else []
        tbl = [["Type d'usager", "Effectifs", "Part (%)"]]
        for i, (_, row) in enumerate(df.iterrows()):
            tu = str(row["type_usager"])
            suffix = " *" if tu in targets_s else ""
            tbl.append([tu + suffix, str(int(row["nb"])), pcts[i] if pcts else "0 %"])
        caption = (
            "Effectifs d'usagers par catégorie "
            "(ensemble des types, département et période du bilan)."
        )
        if targets_s:
            caption += " * Type(s) faisant l'objet du présent bilan."
        builder.add_table(
            tbl,
            caption=caption,
            col_widths=[avail_w * 0.50, avail_w * 0.28, avail_w * 0.22],
            col_aligns=["LEFT", "RIGHT", "RIGHT"],
            keep_together=True,
        )


def _pdf_section_activite_par_types_usagers(
    builder: Any,
    results: dict,
    tmp_dir: Path,
    avail_w: float,
    *,
    presentation_cfg: dict[str, Any],
    section_title: dict[str, str],
    pie_ratio: float,
    bar_ratio: float,
    legend_fontsize: float,
    legend_ncol_max: int,
    figure_scale: float,
    pie_figure_scale: float | None = None,
) -> None:
    """Section VIII : activité par types d'usagers (camembert, tableaux par type, barres horizontales empilées)."""
    ctrl_ut = results.get("ctrl_par_usager_theme")
    if ctrl_ut is None or ctrl_ut.empty:
        return

    pie_fs = float(pie_figure_scale) if pie_figure_scale is not None else float(figure_scale)

    total_ctrl_lignes = float(ctrl_ut["nb_localisations"].sum()) or 1.0
    sum_par_type = ctrl_ut.groupby("type_usager")["nb_localisations"].sum()

    pie_data = {str(k): int(v) for k, v in sum_par_type.items()}
    show_themes = is_block_enabled(
        presentation_cfg, "sec4.show_table_themes_par_type_usager", True
    )
    # 1) Camembert : même modèle que « Répartition des résultats » (chart_pie par défaut + ratio PDF identique).
    if pie_data:
        pie_path = chart_pie(
            pie_data,
            "Répartition des contrôles par type d'usager",
            tmp_dir,
            "pie_controles_par_type_usager.png",
            **_chart_pie_compact_legend_kw(
                len(pie_data),
                legend_fontsize=legend_fontsize,
                legend_ncol_max=legend_ncol_max,
            ),
            figure_scale=pie_fs,
        )
        builder.add_image(Path(pie_path), width_ratio=pie_ratio, spacer_after_mm=0.8)

    if pie_data or show_themes:
        if is_section_enabled(presentation_cfg, "sec41", True):
            builder.add_section(
                "sec41",
                section_title.get("sec41", "3.1. Thème de contrôle par type d'usager"),
                level=2,
                toc_level=1,
            )

    # 2) Un tableau par type d'usager : thèmes (nb + % du total général + % du sous-total type)
    if show_themes:
        type_order = sum_par_type.sort_values(ascending=False).index
        first_tbl = True
        for tu in type_order:
            tu_s = str(tu)
            sub = ctrl_ut[ctrl_ut["type_usager"].astype(str) == tu_s].copy()
            if sub.empty:
                continue
            sub = sub.sort_values("nb_localisations", ascending=False, kind="stable")
            sub = rollup_small_categories(
                sub,
                label_col="theme",
                other_label="Autres thèmes de contrôle",
                value_col="nb_localisations",
                min_pct=0.01,
                sum_cols=["nb_localisations", "nb_operations"],
            )
            if sub is None or sub.empty:
                continue
            st = float(sum_par_type.loc[tu]) if tu in sum_par_type.index else 1.0
            st = st or 1.0
            tbl_th = [
                ["Thème", "Opérations", "Localisations", "% du total\ngénéral", "% du sous-total\n(type)"],
            ]
            nbs_th = sub["nb_localisations"].astype(int).tolist()
            pct_sous_th = (
                int_percents_largest_remainder(nbs_th) if st > 0 else [0] * len(nbs_th)
            )
            for j, (_, r) in enumerate(sub.iterrows()):
                nb = int(r["nb_localisations"])
                nb_ops = int(r.get("nb_operations", 0))
                tbl_th.append(
                    [
                        str(r["theme"]),
                        str(nb_ops),
                        str(nb),
                        _pct_table_cell(nb, total_ctrl_lignes),
                        f"{pct_sous_th[j]} %",
                    ]
                )
            if not first_tbl:
                builder.add_spacer(1.5)
            first_tbl = False
            builder.add_table(
                tbl_th,
                caption=pdf_metric_caption(f"Thèmes de contrôle — {tu_s}", "ctrl"),
                col_widths=[
                    avail_w * 0.35,
                    avail_w * 0.15,
                    avail_w * 0.18,
                    avail_w * 0.16,
                    avail_w * 0.16,
                ],
                col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"],
                keep_together=True,
                spacer_after_mm=1.0,
            )

    # 3) Sous-partie : résultats des contrôles par type d'usager (titre + graphique + tableau
    #    regroupés pour éviter un saut de page entre le titre et le contenu).
    rb = results.get("res_bilan_par_type_usager")
    if rb is not None and not rb.empty:
        labels = [str(x) for x in rb["type_usager"].tolist()]
        series: dict[str, list[int]] = {
            "Conforme": [int(x) for x in rb["Conforme"].tolist()],
            "Infraction": [int(x) for x in rb["Infraction"].tolist()],
            "Manquement": [int(x) for x in rb["Manquement"].tolist()],
        }
        # « En attente » : résultat OSCEAN hors Conforme/Infraction/Manquement
        # (à ne pas confondre avec le type d'usager « Autre » sur l'axe Y).
        if int(rb["Autre_resultat"].sum()) > 0:
            series["En attente"] = [int(x) for x in rb["Autre_resultat"].tolist()]
        metrique_usagers = presentation_cfg.get("metrique_resultats_usagers", "effectifs")
        axis_label = "Effectifs d'usagers" if str(metrique_usagers).strip().lower() == "effectifs" else "Contrôles"
        bar_path = chart_bar_horizontal_stacked(
            labels,
            series,
            "Résultats des contrôles par type d'usager",
            axis_label,
            tmp_dir,
            "bar_resultats_par_type_usager.png",
            legend_fontsize=legend_fontsize,
            legend_ncol_max=legend_ncol_max,
            figure_scale=max(0.88, float(figure_scale)),
            show_title=False,
        )
        # Tableau chiffré + pourcentages (part de chaque résultat dans le type,
        # et poids du type dans le total de cette sous-partie).
        has_autre = int(rb["Autre_resultat"].sum()) > 0
        total_global = float(
            rb["Conforme"].sum()
            + rb["Infraction"].sum()
            + rb["Manquement"].sum()
            + rb["Autre_resultat"].sum()
        ) or 1.0
        tbl_res = [
            [
                "Type d'usager",
                "Conforme",
                "% conforme",
                "Infraction",
                "% infraction",
                "Manquement",
                "% manquement",
                *(
                    ["En attente", "% en attente"]
                    if has_autre
                    else []
                ),
                "Total",
                "% du total",
            ]
        ]
        for _, row in rb.iterrows():
            c = int(row["Conforme"])
            i = int(row["Infraction"])
            m = int(row["Manquement"])
            a = int(row["Autre_resultat"]) if has_autre else 0
            t = c + i + m + a
            if t > 0:
                parts = [c, i, m]
                if has_autre:
                    parts.append(a)
                pct_row = int_percents_largest_remainder(parts)
                k = 0
                pc_c = f"{pct_row[k]} %"
                k += 1
                pc_i = f"{pct_row[k]} %"
                k += 1
                pc_m = f"{pct_row[k]} %"
                k += 1
                if has_autre:
                    pc_a = f"{pct_row[k]} %"
                else:
                    pc_a = ""
            else:
                pc_c = pc_i = pc_m = "n.d."
                pc_a = ""
            row_cells = [
                str(row["type_usager"]),
                str(c),
                pc_c,
                str(i),
                pc_i,
                str(m),
                pc_m,
            ]
            if has_autre:
                row_cells.extend([str(a), pc_a])
            row_cells.extend([str(t), _pct_table_cell(t, total_global)])
            tbl_res.append(row_cells)
        # Harmonisation visuelle : même largeur pour toutes les colonnes numériques.
        first_col_w = avail_w * 0.20
        n_other_cols = len(tbl_res[0]) - 1
        other_w = (avail_w - first_col_w) / float(max(1, n_other_cols))
        col_widths = [first_col_w] + [other_w] * n_other_cols
        if is_section_enabled(presentation_cfg, "sec42", True):
            builder.add_section(
                "sec42",
                section_title.get("sec42", "3.2. Résultats des contrôles par type d'usager"),
                level=2,
                toc_level=1,
            )
        builder.add_heading_chart_table_keep_together(
            heading_text="",
            heading_style="Heading2",
            chart_path=Path(bar_path),
            chart_width_ratio=bar_ratio,
            table_rows=tbl_res,
            table_caption="Résultats des contrôles par type d'usager",
            col_widths=col_widths,
            col_aligns=["LEFT"] + ["RIGHT"] * (len(tbl_res[0]) - 1),
            header_font_size=7.5,
            trailing_spacer_mm=1.0,
        )
    else:
        if is_section_enabled(presentation_cfg, "sec42", True):
            builder.add_section(
                "sec42",
                section_title.get("sec42", "3.2. Résultats des contrôles par type d'usager"),
                level=2,
                toc_level=1,
            )
            builder.add_paragraph("Aucun résultat de contrôle par type d'usager pour la période.")

    proc_summary = summarize_procedures_par_type_usager(results.get("proc_par_usager_domaine"))
    add_procedures_par_type_usager_subsection(
        builder,
        proc_summary,
        avail_w=avail_w,
        presentation_cfg=presentation_cfg,
        section_title=section_title,
    )




def render_thematic_profil_sections(ctx: Any, curr_results: dict, title_suffix: str = ""):
    """Rendu des sections modulaires sec1 à sec6 pour un profil thématique."""
    builder = ctx.builder
    presentation_cfg = ctx.presentation_cfg
    section_title = ctx.section_title
    profil_id = ctx.profil_id
    cfg = ctx.cfg
    options = ctx.options
    ventilation_mode = ctx.ventilation_mode
    profile = ctx.profile
    sources = ctx.sources
    diffusion = ctx.diffusion
    is_single_usager = ctx.is_single_usager
    single_label = ctx.single_label
    dept_name = ctx.dept_name
    dept_name_typo = ctx.dept_name_typo
    period_str = ctx.period_str
    tmp_dir = ctx.tmp_dir
    sections_toc = ctx.sections_toc
    tables_layout = ctx.tables_layout
    ref_pie_w = ctx.ref_pie_w
    ref_pie_fs = ctx.ref_pie_fs
    ref_pie_legend_fs = ctx.ref_pie_legend_fs
    figure_scale = ctx.figure_scale
    figure_scale_sec21 = getattr(ctx, 'figure_scale_sec21', figure_scale)
    legend_fontsize_sec21 = getattr(ctx, 'legend_fontsize_sec21', 8)
    legend_ncol_max = ctx.legend_ncol_max
    avail_w = ctx.avail_w
    show_placeholder = ctx.show_placeholder
    is_type_usager = ctx.is_type_usager
    is_procedures = ctx.is_procedures
    _nom_commune = getattr(ctx, '_nom_commune', lambda c: str(c))
    chart_ratio_base = getattr(ctx, 'chart_ratio_base', 0.95)
    out_dir = getattr(ctx, 'out_dir', None)

    # --- Compteurs locaux du sous-profil ---
    nb_localisations = curr_results.get("_nb_localisations", curr_results.get("nb_localisations", 0))
    nb_operations_controle = curr_results.get("nb_operations_controle", 0)
    nb_pej = curr_results.get("_nb_pej", curr_results.get("nb_pej", 0))
    nb_pa = curr_results.get("_nb_pa", curr_results.get("nb_pa", 0))
    nb_pve = curr_results.get("_nb_pve", curr_results.get("nb_pve", 0))
    tab_resultats = curr_results.get("tab_resultats")
    show_coeur_hors_pdf = bool(curr_results.get("_pdf_show_coeur_hors_coeur", True))
    zone_lecteur_4_zones_pdf = bool(curr_results.get("_zone_lecteur_4_zones", False))
    # ── CHIFFRES CLÉS ──
    builder.add_section("sec1", section_title["sec1"] + title_suffix)
    kf = []

    if profil_id == "ppp":
        # Pour les PPP, uniquement PEJ et communes concernées
        if nb_pej > 0:
            kf.append((str(nb_pej), "Procédures d'enquête judiciaire (PEJ)"))
        pej_detail_df = curr_results.get("pej_detail")
        if isinstance(pej_detail_df, pd.DataFrame) and not pej_detail_df.empty and "commune" in pej_detail_df.columns:
            nb_communes = pej_detail_df["commune"].nunique()
            kf.append((str(nb_communes), "Communes concernées par un fait"))
    else:
        nb_operations_controle = curr_results.get("nb_operations_controle", 0)
        if nb_operations_controle > 0:
            kf.append((str(nb_operations_controle), "Opérations de contrôle"))
        if nb_localisations > 0:
            kf.append((str(nb_localisations), "Localisations de contrôle"))
        if tab_resultats is not None:
            nb_nc = 0
            for _lbl in ("Infraction", "Manquement"):
                sub = tab_resultats[tab_resultats["resultat"] == _lbl]
                if not sub.empty and "nb" in sub.columns:
                    nb_nc += int(sub["nb"].sum())
            if nb_nc > 0:
                taux_nc = nb_nc / nb_localisations if nb_localisations else 0
                kf.append((str(nb_nc), PDF_LABEL_NON_CONFORME_LOCATIONS))
                kf.append((format_pct_int_from_rate(taux_nc), "Taux de non-conformité"))
        if nb_pej > 0:
            kf.append((str(nb_pej), PDF_LABEL_PEJ_COUNT))
        kf.append((str(nb_pa), "Nombre de PA"))
        if nb_pve > 0:
            kf.append((str(nb_pve), "Nombre de PVe"))
        if is_type_usager:
            ue = curr_results.get("usager_effectifs")
            if ue is not None and not ue.empty and "nb" in ue.columns:
                total_usagers = int(ue["nb"].sum())
                if is_single_usager and single_label:
                    kf.append((str(total_usagers), f"Effectifs – {single_label}"))
                else:
                    kf.append((str(total_usagers), "Effectifs d'usagers contrôlés"))
        if is_procedures and "pej_duree_resume" in curr_results:
            dr = curr_results["pej_duree_resume"]
            kf.append((str(dr["nb_pej"]), "PEJ"))
            kf.append((f"{dr['duree_moy_j']} j", "Durée moyenne"))
            kf.append((f"{dr['duree_mediane_j']} j", "Durée médiane"))

    builder.add_key_figures(kf)

    # Rendu du visuel cartographique communal et tableau thématique en Section 1 (Page 1)
    sec_enr = (presentation_cfg or {}).get("sections_enrichies", {}).get("synthese_regionale", {})
    carto_cfg = sec_enr.get("carte_choroplethe", {})

    if carto_cfg or is_section_enabled(presentation_cfg, "sec1_carte", True):
        try:
            from core.engine.sections_region import _generate_region_choropleth, _create_proportional_rl_image

            dept_counts: dict[str, int] = {}
            commune_counts: dict[str, int] = {}

            for df_key in ("point", "pej", "pve"):
                df_src = curr_results.get(df_key)
                if isinstance(df_src, pd.DataFrame) and not df_src.empty:
                    col_insee = next((c for c in ("insee_comm", "insee_com", "code_insee", "INSEE_COM", "insee", "INF-INSEE") if c in df_src.columns), None)
                    if col_insee:
                        s_counts = df_src[col_insee].astype(str).str.strip().str.zfill(5).value_counts()
                        for c_code, val in s_counts.items():
                            if c_code and len(c_code) == 5 and c_code.isdigit():
                                commune_counts[c_code] = commune_counts.get(c_code, 0) + int(val)
                    col_dep = next((c for c in ("departement", "num_depart", "code_dept", "insee_dep") if c in df_src.columns), None)
                    if col_dep:
                        s_dep = df_src[col_dep].astype(str).str.strip().str.upper().str[:2].value_counts()
                        for d_code, val in s_dep.items():
                            dept_counts[d_code] = dept_counts.get(d_code, 0) + int(val)

            code = cfg.code
            tmp_dir = out_dir or (PROJECT_ROOT / "data" / "out" / f"bilan_{profil_id}_{code}")
            tmp_dir.mkdir(parents=True, exist_ok=True)

            sec_enr = (presentation_cfg or {}).get("sections_enrichies", {}).get("synthese_regionale", {})
            palette_sr = sec_enr.get("palette", {})
            carto_path = _generate_region_choropleth(
                dept_counts=dept_counts,
                dept_code=str(code or "21"),
                tmp_dir=tmp_dir,
                img_name="choropleth_sec1.png",
                out_dir=out_dir,
                profile_id=profil_id,
                total_unique_ops=nb_operations_controle or nb_localisations,
                commune_counts=commune_counts,
                carto_cfg=carto_cfg,
                palette=sec_enr.get("palette"),
                styles=sec_enr.get("styles"),
            )

            if carto_path and carto_path.exists():
                max_h = float(carto_cfg.get("max_h", 260.0))
                col_w = builder.avail_w * 0.48
                img_carto = _create_proportional_rl_image(carto_path, col_w, "Carte de la pression de contrôle", builder.styles, max_h=max_h)

                # Tableau thématique pour la colonne de droite
                right_element = None
                df_theme = curr_results.get("tab_par_theme")
                from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
                from reportlab.lib import colors as rl_colors

                if isinstance(df_theme, pd.DataFrame) and not df_theme.empty:
                    t_rows = []
                    t_rows.append([
                        Paragraph("<b>Thématique</b>", builder.styles.get("BodyText")),
                        Paragraph("<b>Localisations</b>", builder.styles.get("BodyText")),
                    ])
                    top_theme = df_theme.head(7)
                    for _, r in top_theme.iterrows():
                        th_lbl = str(r.get("theme", r.get("thematique", "")))
                        th_nb = str(r.get("nb", r.get("nb_localisations", r.get("nb_operations", ""))))
                        t_rows.append([
                            Paragraph(th_lbl[:35], builder.styles.get("BodyText")),
                            Paragraph(f"<b>{th_nb}</b>", builder.styles.get("BodyText")),
                        ])
                    tbl_th = Table(t_rows, colWidths=[col_w * 0.70, col_w * 0.30])
                    line_hdr = rl_colors.HexColor(palette_sr.get("ligne_tableau_entete", "#003366"))
                    line_body = rl_colors.HexColor(palette_sr.get("ligne_tableau_corps", "#e2e8f0"))
                    tbl_th.setStyle(TableStyle([
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                        ('TOPPADDING', (0, 0), (-1, -1), 2),
                        ('LINEBELOW', (0, 0), (-1, 0), 0.8, line_hdr),
                        ('LINEBELOW', (0, 1), (-1, -1), 0.3, line_body),
                    ]))
                    right_element = tbl_th
                else:
                    body_st = builder.styles.get("BodyText", builder.styles.get("Normal"))
                    right_element = Paragraph("<i>Données par thématique indisponibles</i>", body_st)

                tbl_sec1 = Table([[img_carto, right_element]], colWidths=[col_w, col_w])
                tbl_sec1.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                builder.story.append(Spacer(1, 6))
                builder.story.append(tbl_sec1)
                builder.story.append(Spacer(1, 6))
        except Exception as e_sec1:
            logging.getLogger(__name__).warning(f"Erreur lors du rendu cartographique sec1 : {e_sec1}")

    # 2. Contrôles (chapitre)
    builder.add_section("sec2", section_title["sec2"] + title_suffix)

    if is_block_enabled(presentation_cfg, "sec2.show_intro_text", True):
        if profil_id == "ppp":
            builder.add_paragraph(
                "Cette section présente l'évolution temporelle de l'activité répressive liée aux procédures "
                "d'enquête judiciaire (PEJ) sur la période du bilan."
            )
        else:
            builder.add_paragraph(
                "Cette section présente l'évolution temporelle de l'activité de contrôle et des procédures "
                "(judiciaires et administratives) sur la période du bilan, ainsi que les résultats "
                "détaillés des contrôles réalisés au titre de la police administrative."
            )

    # ── ANALYSE DE L'ENSEMBLE DE LA PÉRIODE DU BILAN / RÉSULTATS ──
    agg_annuelle = curr_results.get("agg_annuelle")
    vent_temp_type = curr_results.get("ventilation_temporelle_type", "annuelle")

    def _render_sec21() -> None:
        builder.add_section("sec21", section_title["sec21"] + title_suffix, toc_level=1)
        if isinstance(agg_annuelle, pd.DataFrame) and not agg_annuelle.empty:
            is_month = vent_temp_type == "mensuelle"
            is_trim = vent_temp_type == "trimestrielle"
            is_week = vent_temp_type == "hebdomadaire"
            texte_vent = (
                "par mois "
                if is_month
                else (
                    "par trimestre "
                    if is_trim
                    else ("par semaine " if is_week else "par année ")
                )
            )
            builder.add_paragraph(
                "Ventilation des principaux indicateurs " + texte_vent
                + "sur l'ensemble de la période du bilan."
            )
            label_col = (
                "Mois"
                if is_month
                else ("Trimestre" if is_trim else ("Semaine" if is_week else "Année"))
            )
            if profil_id == "ppp":
                tbl = [[
                    label_col,
                    "Procédures d'enquête judiciaire (PEJ)"
                ]]
                for _, row in agg_annuelle.iterrows():
                    tbl.append([
                        str(row["periode"]),
                        str(int(row.get("nb_pej", 0)))
                    ])
            else:
                tbl = [[
                    label_col,
                    "Opérations de contrôle",
                    PDF_LABEL_CTRL_LOCATIONS_SHORT,
                    PDF_LABEL_NON_CONFORME_LOCATIONS,
                    "Taux de non-conformité",
                    PDF_LABEL_PEJ,
                    "PA",
                    "Nombre de verbalisations au titre\nde la police judiciaire",
                ]]
                for _, row in agg_annuelle.iterrows():
                    taux = (
                        format_pct_int_from_rate(row.get("taux_non_conformite_controles"))
                        if pd.notna(row.get("taux_non_conformite_controles"))
                        else "n.d."
                    )
                    tbl.append([
                        str(row["periode"]),
                        str(int(row.get("nb_operations_controle", 0))),
                        str(int(row["nb_localisations"])),
                        str(int(row["nb_localisations_non_conformes"])),
                        taux,
                        str(int(row["nb_pej"])),
                        str(int(row["nb_pa"])),
                        str(int(row["nb_pve"])),
                    ])
            if is_block_enabled(presentation_cfg, "sec21.show_table", True):
                cap_vent = (
                    "mensuels"
                    if is_month
                    else (
                        "trimestriels"
                        if is_trim
                        else ("hebdomadaires" if is_week else "annuels")
                    )
                )
                if profil_id == "ppp":
                    caption_sec21_tbl = f"Nombre de procédures d'enquête judiciaire (PEJ) {cap_vent}"
                    col_w_sec21 = [avail_w * 0.40, avail_w * 0.60]
                    col_a_sec21 = ["RIGHT", "RIGHT"]
                else:
                    caption_sec21_tbl = f"Indicateurs {cap_vent} ({PDF_LABEL_CTRL_LOCATIONS_SHORT}, PVe, PEJ, et PA)"
                    col_w_sec21 = [
                        avail_w * 0.12,
                        avail_w * 0.13,
                        avail_w * 0.13,
                        avail_w * 0.16,
                        avail_w * 0.16,
                        avail_w * 0.10,
                        avail_w * 0.10,
                        avail_w * 0.10,
                    ]
                    col_a_sec21 = ["RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"]

                builder.add_table(
                    tbl,
                    caption=caption_sec21_tbl,
                    col_widths=col_w_sec21,
                    col_aligns=col_a_sec21,
                )
            period_labels = [str(v) for v in agg_annuelle["periode"].tolist()]

            titre_ctrl = "Résultats des contrôles" if not is_month else "Résultats des contrôles par mois"
            if is_trim:
                titre_ctrl = "Résultats des contrôles par trimestre"
            elif is_week:
                titre_ctrl = "Résultats des contrôles par semaine"

            if profil_id == "ppp":
                titre_proc = "Nombre de PEJ" if not is_month else "Nombre de PEJ par mois"
                if is_trim:
                    titre_proc = "Nombre de PEJ par trimestre"
                elif is_week:
                    titre_proc = "Nombre de PEJ par semaine"
                series_proc = {
                    "PEJ": [int(v) for v in agg_annuelle["nb_pej"].tolist()],
                }
            else:
                titre_proc = "Nombre de procédures" if not is_month else "Nombre de procédures par mois"
                if is_trim:
                    titre_proc = "Nombre de procédures par trimestre"
                elif is_week:
                    titre_proc = "Nombre de procédures par semaine"

                series_proc = {
                    "PEJ": [int(v) for v in agg_annuelle["nb_pej"].tolist()],
                    "PA": [int(v) for v in agg_annuelle["nb_pa"].tolist()],
                    "PVe": [int(v) for v in agg_annuelle["nb_pve"].tolist()],
                }

            if not is_block_enabled(presentation_cfg, "sec21.show_chart_controles", True) or profil_id == "ppp":
                pass
            else:
                conformes = [
                    int(row["nb_localisations"]) - int(row["nb_localisations_non_conformes"])
                    for _, row in agg_annuelle.iterrows()
                ]
                non_conformes = [int(v) for v in agg_annuelle["nb_localisations_non_conformes"].tolist()]
                stacked_ctrl = {"Conformes": conformes, "Non-conformes": non_conformes}
                stacked_path = chart_bar_stacked(
                    period_labels,
                    stacked_ctrl,
                    titre_ctrl,
                    PDF_LABEL_CTRL_LOCATIONS,
                    tmp_dir,
                    "bar_annuel_ctrl_stacked.png",
                    legend_fontsize=legend_fontsize_sec21,
                    legend_ncol_max=legend_ncol_max,
                    figure_scale=figure_scale_sec21,
                )
                builder.add_image(Path(stacked_path), width_ratio=chart_ratio_base)

            has_proc = any(sum(vals) > 0 for vals in series_proc.values())
            if has_proc and is_block_enabled(presentation_cfg, "sec21.show_chart_procedures", True):
                stacked_proc_path = chart_bar_stacked(
                    period_labels, series_proc, titre_proc, "Nombre", tmp_dir, "bar_annuel_proc_stacked.png",
                    legend_fontsize=legend_fontsize_sec21,
                    legend_ncol_max=legend_ncol_max,
                    figure_scale=figure_scale_sec21,
                )
                builder.add_image(Path(stacked_proc_path), width_ratio=chart_ratio_base)
            if vent_temp_type not in ("mensuelle", "hebdomadaire") and is_block_enabled(
                presentation_cfg, "sec21.show_chart_taux_line", True
            ):
                taux_values = []
                for _, row in agg_annuelle.iterrows():
                    val = row.get("taux_non_conformite_controles")
                    taux_values.append(int(round(float(val) * 100)) if pd.notna(val) else 0)
                if any(v > 0 for v in taux_values):
                    line_path = chart_line_evolution(
                        period_labels,
                        {"Taux de non-conformité (%)": taux_values},
                        "Évolution du taux de non-conformité",
                        "Taux (%)",
                        tmp_dir, "line_annuel_taux_inf.png",
                        legend_fontsize=legend_fontsize_sec21,
                        legend_ncol_max=legend_ncol_max,
                        figure_scale=figure_scale_sec21,
                    )
                    builder.add_image(Path(line_path), width_ratio=chart_ratio_base)
        elif show_placeholder:
            builder.add_paragraph("Aucun indicateur disponible sur la période pour la ventilation retenue.")

    def _proc_domaine_theme_table_specs(
        metric_cols: tuple[str, ...],
        *,
        caption_domaine: str,
        caption_theme: str,
        max_lignes: int = 15,
    ) -> list[dict]:
        """Spécifications tableaux procédures par domaine / thème (pour PDF ou regroupement bandeau)."""
        metric_cols = tuple(c for c in metric_cols if c in ("nb_pej", "nb_pa", "nb_pve"))
        tables: list[dict] = []

        def _append_spec(df_src: pd.DataFrame | None, dim_col: str, caption: str) -> None:
            if df_src is None or df_src.empty or dim_col not in df_src.columns:
                return
            present_metrics = [c for c in metric_cols if c in df_src.columns]
            if not present_metrics:
                return
            if int(df_src[present_metrics].fillna(0).sum().sum()) <= 0:
                return
            df_all = df_src.copy()
            df_proc = df_all.head(max_lignes).copy()
            cap = caption
            if is_single_usager and "type_usager" in df_proc.columns and df_proc["type_usager"].nunique() == 1:
                df_proc = df_proc.drop(columns=["type_usager"])
            elif "type_usager" in df_proc.columns:
                cap = pdf_metric_caption(
                    f"Procédures par type d'usager et par {dim_col}", "proc"
                )
            if len(df_all) > len(df_proc):
                cap = f"{cap} (top {len(df_proc)})"
            cols = [dim_col, *present_metrics]
            tbl = [[pdf_column_label(c) for c in cols]]
            for _, row in df_proc.iterrows():
                tbl.append([
                    str(int(row[c])) if c in present_metrics else str(row.get(c, ""))
                    for c in cols
                ])
            col_aligns = ["LEFT"] + ["RIGHT"] * len(present_metrics)
            tables.append({
                "data_rows": tbl,
                "caption": cap,
                "col_widths": None,
                "col_aligns": col_aligns,
            })

        _append_spec(curr_results.get("proc_par_usager_domaine"), "domaine", caption_domaine)
        _append_spec(curr_results.get("proc_par_usager_theme"), "theme", caption_theme)
        return tables

    def _render_proc_par_domaine_theme(
        metric_cols: tuple[str, ...],
        *,
        caption_domaine: str,
        caption_theme: str,
        max_lignes: int = 15,
    ) -> None:
        """Tableaux procédures par domaine / thème (colonnes nb_pej, nb_pa, etc.)."""
        for spec in _proc_domaine_theme_table_specs(
            metric_cols,
            caption_domaine=caption_domaine,
            caption_theme=caption_theme,
            max_lignes=max_lignes,
        ):
            builder.add_table(
                spec["data_rows"],
                caption=spec.get("caption", ""),
                col_aligns=spec.get("col_aligns"),
                keep_together=True,
            )

    def _render_type_usager_sec23_content() -> None:
        """Section 2.3 : contrôles et résultats pour le(s) type(s) d'usager ciblé(s)."""
        if not is_single_usager:
            ue = curr_results.get("usager_effectifs")
            if ue is not None and not ue.empty:
                tbl = [["Type d'usager", "Effectifs"]]
                for _, row in ue.iterrows():
                    tbl.append([str(row["type_usager"]), str(int(row["nb"]))])
                builder.add_table(
                    tbl,
                    caption=pdf_metric_caption("Effectifs d'usagers par catégorie", "effectifs"),
                    col_widths=[avail_w * 0.65, avail_w * 0.35],
                    col_aligns=["LEFT", "RIGHT"],
                )
                pie_data = {str(r["type_usager"]): int(r["nb"]) for _, r in ue.iterrows()}
                if pie_data:
                    pie_path = chart_pie(
                        pie_data,
                        "Usagers contrôlés par type",
                        tmp_dir,
                        "pie_usagers.png",
                        **_chart_pie_compact_legend_kw(
                            len(pie_data),
                            legend_fontsize=ref_pie_legend_fs,
                            legend_ncol_max=legend_ncol_max,
                        ),
                        figure_scale=ref_pie_fs,
                    )
                    builder.add_image(Path(pie_path), width_ratio=ref_pie_w)

        if not is_single_usager:
            ud = curr_results.get("usager_par_domaine")
            if ud is not None and not ud.empty:
                df_ud = ud.copy()
                tbl, overflow_html = build_usagers_x_domaine_pdf_rows(
                    df_ud,
                    tables_layout=tables_layout,
                )
                if tbl:
                    n_dom = len(tbl[0]) - 1
                    col_widths = usagers_x_domaine_col_widths(avail_w, n_dom, tables_layout)
                    col_aligns = ["LEFT"] + ["RIGHT"] * n_dom
                    cap = pdf_metric_caption("Usagers × Domaine", "effectifs")
                    if overflow_html:
                        cap = f"{cap}<br/><br/>{overflow_html}"
                    builder.add_table(
                        tbl,
                        caption=cap,
                        col_widths=col_widths,
                        col_aligns=col_aligns,
                        wide_headers=True,
                        wide_header_layout=resolve_usagers_x_domaine_header_layout(
                            tables_layout
                        ),
                        wide_header_font_size=resolve_usagers_x_domaine_header_font_size(
                            tables_layout
                        ),
                        wide_header_max_lines=resolve_usagers_x_domaine_header_max_lines(
                            tables_layout
                        ),
                    )

        tab_res_ctrl = curr_results.get("tab_resultats_controles")
        if tab_res_ctrl is not None and not tab_res_ctrl.empty:
            cap_res = pdf_metric_caption("Résultats des contrôles", "ctrl")
            if is_single_usager and single_label:
                cap_res = f"{cap_res} – {single_label}"
            else:
                cap_res = f"{cap_res} (usager ciblé)"
            tr_u = tab_res_ctrl
            show_coeur_col = (
                bool(curr_results.get("_pdf_show_coeur_hors_coeur", True))
                and "aoa" in tr_u.columns
            )
            if show_coeur_col:
                hdr = ["Résultat", "AOA", "Cœur", "Total PNF", "Taux"]
            else:
                hdr = ["Résultat", "Nombre", "Taux"]
            tbl = [hdr]
            top_mask = tr_u["resultat"].isin(["Conforme", "Non-conforme", "En attente"])
            top_counts = tr_u.loc[top_mask, "nb"].astype(int).tolist()
            top_rates = tab_counts_to_pct_strings(top_counts) if top_counts else []
            j = 0
            nb_nc = int(tr_u.loc[tr_u["resultat"] == "Non-conforme", "nb"].sum())
            for _, row in tr_u.iterrows():
                rlib = str(row["resultat"])
                nbv = int(row["nb"])
                if rlib.strip() in ("Dont infraction", "Dont manquement"):
                    t = format_pct_int_from_rate((nbv / nb_nc) if nb_nc > 0 else None)
                elif rlib in ("Conforme", "Non-conforme", "En attente"):
                    t = top_rates[j] if j < len(top_rates) else "n.d."
                    j += 1
                else:
                    t = "n.d."
                if show_coeur_col:
                    row_cells = [resultat_controle_label_for_pdf(rlib), str(row.get("aoa", 0)), str(row.get("coeur", 0)), str(nbv), t]
                else:
                    row_cells = [resultat_controle_label_for_pdf(rlib), str(nbv), t]
                tbl.append(row_cells)
            if show_coeur_col:
                cw_res = [avail_w * 0.35, avail_w * 0.12, avail_w * 0.12, avail_w * 0.20, avail_w * 0.21]
                ca_res = ["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"]
            else:
                cw_res = [avail_w * 0.50, avail_w * 0.22, avail_w * 0.28]
                ca_res = ["LEFT", "RIGHT", "RIGHT"]
            cap_res_tbl = cap_res
            pie_data = {
                str(r["resultat"]): int(r["nb"])
                for _, r in tr_u.iterrows()
                if str(r["resultat"]) in ("Conforme", "Non-conforme", "En attente")
            }
            pie_path: Path | None = None
            if pie_data:
                pie_path = Path(
                    chart_pie(
                        pie_data,
                        "Répartition des résultats",
                        tmp_dir,
                        "pie_resultats_usager.png",
                        **_chart_pie_compact_legend_kw(
                            len(pie_data),
                            legend_fontsize=ref_pie_legend_fs,
                            legend_ncol_max=legend_ncol_max,
                        ),
                        figure_scale=ref_pie_fs,
                    )
                )
            if pie_path is not None and pie_path.exists():
                builder.add_table_and_image_keep_together(
                    tbl,
                    table_caption=cap_res_tbl,
                    col_widths=cw_res,
                    col_aligns=ca_res,
                    image_path=pie_path,
                    image_width_ratio=ref_pie_w,
                )
            else:
                builder.add_table(
                    tbl,
                    caption=cap_res_tbl,
                    col_widths=cw_res,
                    col_aligns=ca_res,
                )

        res_ud = curr_results.get("res_par_usager_domaine")
        if res_ud is not None and not res_ud.empty:
            hdr, body, with_type_col = build_resultats_par_usager_domaine_pdf_rows(
                res_ud,
                is_single_usager=is_single_usager,
            )
            if hdr and body:
                if with_type_col:
                    caption = "Résultats des contrôles par type d'usager et par domaine"
                else:
                    caption = pdf_metric_caption("Résultats des contrôles par domaine", "ctrl")
                if len(res_ud) > len(body):
                    caption = f"{caption} (top {len(body)})"
                n_num = len(hdr) - (2 if with_type_col else 1)
                if with_type_col:
                    cw = [avail_w * 0.28] + [avail_w * 0.18] * (n_num + 1)
                    ca = ["LEFT", "LEFT"] + ["RIGHT"] * n_num
                else:
                    cw = [avail_w * 0.40] + [avail_w * (0.60 / n_num)] * n_num
                    ca = ["LEFT"] + ["RIGHT"] * n_num
                builder.add_table(
                    [hdr, *body],
                    caption=caption,
                    col_widths=cw,
                    col_aligns=ca,
                    keep_together=True,
                )

    def _render_sec22() -> None:
        if not is_section_enabled(presentation_cfg, "sec22", True):
            return
        builder.add_section("sec22", section_title["sec22"] + title_suffix, toc_level=1)

        point_filtered = curr_results.get("_raw_point_filtered", pd.DataFrame())
        pej_filtered = curr_results.get("_raw_pej_filtered", pd.DataFrame())

        # Pilotage YAML pour le groupement (domaine ou thème)
        group_by = presentation_cfg.get("blocks", {}).get("sec22", {}).get("group_by", "domaine")
        if group_by == "theme":
            group_col_point = "theme"
            group_col_pej = "THEME"
            title_pie = "Répartition de l'activité par thèmes (contrôles + PEJ)"
            col_header = "Thème"
        elif group_by == "type_action":
            group_col_point = "type_action" if "type_action" in point_filtered.columns else "type_actio"
            group_col_pej = "TYPE_ACTION"
            title_pie = "Répartition de l'activité par types d'action (contrôles + PEJ)"
            col_header = "Type d'action"
        else:
            group_col_point = "domaine"
            group_col_pej = "DOMAINE"
            title_pie = "Répartition de l'activité par domaines (contrôles + PEJ)"
            col_header = "Domaine"

        # Build group data from available point_filtered and pej_filtered
        df_dom = pd.DataFrame()
        if not point_filtered.empty and group_col_point in point_filtered.columns:
            df_dom = point_filtered[group_col_point].fillna("Non renseigné").astype(str).value_counts().rename_axis("domaine").to_frame("nb").reset_index()
            if "fc_id" in point_filtered.columns:
                ops_df = point_filtered.copy()
                ops_df[group_col_point] = ops_df[group_col_point].fillna("Non renseigné").astype(str)
                ops_df = ops_df.groupby(group_col_point)["fc_id"].nunique().reset_index()
                ops_df.columns = ["domaine", "nb_operations"]
                df_dom = df_dom.merge(ops_df, on="domaine", how="left")
            else:
                df_dom["nb_operations"] = 0

        pej_dom = pd.DataFrame()
        if not pej_filtered.empty and group_col_pej in pej_filtered.columns:
            pej_dom = pej_filtered[group_col_pej].fillna("Non renseigné").astype(str).value_counts().rename_axis("domaine").to_frame("nb_pej").reset_index()

        if not df_dom.empty and not pej_dom.empty:
            df_dom = pd.merge(df_dom, pej_dom, on="domaine", how="outer").fillna(0)
        elif df_dom.empty and not pej_dom.empty:
            df_dom = pej_dom.copy()
            df_dom["nb"] = 0
        elif not df_dom.empty and pej_dom.empty:
            df_dom["nb_pej"] = 0

        if not df_dom.empty:
            for col_name in ["nb", "nb_pej", "nb_operations"]:
                if col_name in df_dom.columns:
                    df_dom[col_name] = df_dom[col_name].fillna(0)
                else:
                    df_dom[col_name] = 0
            df_dom["total_act"] = df_dom["nb"] + df_dom["nb_pej"]
            df_dom = df_dom.sort_values(by="total_act", ascending=False)

            tbl = [[col_header, "Opérations", "Localisations", "PEJ"]]
            for _, row in df_dom.head(25).iterrows():
                nb_ops = int(row.get("nb_operations", 0))
                tbl.append([str(row["domaine"]), str(nb_ops), str(int(row["nb"])), str(int(row["nb_pej"]))])
            builder.add_table(
                tbl,
                caption=title_pie,
                col_widths=[avail_w * 0.44, avail_w * 0.18, avail_w * 0.19, avail_w * 0.19],
                col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"],
            )
            if is_block_enabled(presentation_cfg, "sec22.show_overflow_note", True) and len(df_dom) > 25:
                builder.add_paragraph(
                    f"... et {len(df_dom) - 25} autres {group_by}s.",
                    style="BodySmall",
                )
            if not df_dom.empty:
                pie_data = {str(row["domaine"])[:34]: int(row["total_act"]) for _, row in df_dom.iterrows() if int(row["total_act"]) > 0}
                if is_block_enabled(presentation_cfg, "sec22.show_pie", True) and pie_data:
                    pie_path = chart_pie(
                        pie_data,
                        title_pie,
                        tmp_dir,
                        "pie_domaine.png",
                        **_chart_pie_compact_legend_kw(
                            len(pie_data),
                            legend_fontsize=ref_pie_legend_fs,
                            legend_ncol_max=legend_ncol_max,
                        ),
                        figure_scale=ref_pie_fs,
                    )
                    builder.add_image(Path(pie_path), width_ratio=ref_pie_w)
        elif show_placeholder:
            builder.add_paragraph("Aucune donnée domaine disponible.")
        builder.add_spacer(4)

    def _render_categories_controles_block(df_cat: pd.DataFrame) -> None:
        if df_cat is None or df_cat.empty:
            return
        hdr = ["Catégorie", "Contrôles", "Conformes", "Non conformes", "% Non-conforme"]
        tbl = [hdr]
        tot_ctrl, tot_conf, tot_nc = 0, 0, 0
        for _, r in df_cat.iterrows():
            c_tot = int(r.get("total", 0))
            c_conf = int(r.get("conforme", 0))
            c_nc = int(r.get("non_conforme", 0))
            t_nc = r.get("taux_non_conforme", 0.0)
            tot_ctrl += c_tot
            tot_conf += c_conf
            tot_nc += c_nc
            tbl.append([str(r.get("libelle", r.get("categorie", ""))), str(c_tot), str(c_conf), str(c_nc), f"{t_nc} %"])
        taux_tot = round((tot_nc / tot_ctrl) * 100, 1) if tot_ctrl > 0 else 0.0
        tbl.append(["Total", str(tot_ctrl), str(tot_conf), str(tot_nc), f"{taux_tot} %"])

        cw = [avail_w * 0.36, avail_w * 0.16, avail_w * 0.16, avail_w * 0.16, avail_w * 0.16]
        ca = ["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"]
        cap = pdf_metric_caption("Répartition des contrôles par catégorie", "ctrl")

        donut_data = curr_results.get("categories_chasse_controles_donut_data") or {}
        donut_path: Path | None = None
        if donut_data and sum(donut_data.values()) > 0:
            donut_path = Path(chart_pie(
                donut_data,
                "",
                tmp_dir,
                "categories_chasse_controles_donut.png",
                **_chart_pie_compact_legend_kw(
                    len(donut_data),
                    legend_fontsize=ref_pie_legend_fs,
                    legend_ncol_max=legend_ncol_max,
                ),
                figure_scale=ref_pie_fs,
                donut=True,
            ))
        if donut_path is not None and donut_path.exists():
            builder.add_table_and_image_keep_together(
                tbl,
                table_caption=cap,
                col_widths=cw,
                col_aligns=ca,
                image_path=donut_path,
                image_width_ratio=ref_pie_w,
            )
        else:
            builder.add_table(tbl, caption=cap, col_widths=cw, col_aligns=ca)
        builder.add_spacer(3)

    def _render_sec23() -> None:
        builder.add_section("sec23", section_title["sec23"] + title_suffix, toc_level=1)
        if is_type_usager and nb_localisations > 0:
            _render_type_usager_sec23_content()
            return
        if not (nb_localisations > 0 and not is_type_usager and not is_procedures):
            if show_placeholder:
                builder.add_paragraph("Aucune donnée de résultat disponible sur la période.")
            return
        # Pour le profil agrainage, expliciter la source et le filtrage des contrôles.
        if profil_id == "agrainage" and is_block_enabled(presentation_cfg, "sec23.show_intro_text", True):
            builder.append_pending_paragraph(
                "Contrôles liés à l’agrainage identifiés dans les points de contrôle OSCEAN "
                "(champ « nom_dossie » ou « nom_dossier » contenant « agrain »)."
            )
        tab_res_ctrl = curr_results.get("tab_resultats_controles")
        if tab_res_ctrl is not None and not tab_res_ctrl.empty and is_block_enabled(presentation_cfg, "sec23.show_table", True):
            tr = tab_res_ctrl
            show_coeur_col = bool(curr_results.get("_pdf_show_coeur_hors_coeur", True)) and "aoa" in tr.columns
            if show_coeur_col:
                hdr = ["Résultat", "AOA", "Cœur", "Total PNF", "Taux"]
            else:
                hdr = ["Résultat", "Nombre", "Taux"]
            tbl = [hdr]
            top_mask = tr["resultat"].isin(["Conforme", "Non-conforme", "En attente"])
            top_counts = tr.loc[top_mask, "nb"].astype(int).tolist()
            top_rates = tab_counts_to_pct_strings(top_counts) if top_counts else []
            j = 0
            nb_nc = int(tr.loc[tr["resultat"] == "Non-conforme", "nb"].sum())
            for _, row in tr.iterrows():
                rlib = str(row["resultat"])
                nbv = int(row["nb"])
                if rlib.strip() in ("Dont infraction", "Dont manquement"):
                    t = format_pct_int_from_rate((nbv / nb_nc) if nb_nc > 0 else None)
                elif rlib in ("Conforme", "Non-conforme", "En attente"):
                    t = top_rates[j] if j < len(top_rates) else "n.d."
                    j += 1
                else:
                    t = "n.d."
                if show_coeur_col:
                    row_cells = [resultat_controle_label_for_pdf(rlib), str(row.get("aoa", 0)), str(row.get("coeur", 0)), str(nbv), t]
                else:
                    row_cells = [resultat_controle_label_for_pdf(rlib), str(nbv), t]
                tbl.append(row_cells)
            if show_coeur_col:
                cw = [avail_w * 0.35, avail_w * 0.12, avail_w * 0.12, avail_w * 0.20, avail_w * 0.21]
                ca = ["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"]
            else:
                cw = [avail_w * 0.50, avail_w * 0.22, avail_w * 0.28]
                ca = ["LEFT", "RIGHT", "RIGHT"]
            cap_res_ctrl = pdf_metric_caption("Résultats des contrôles", "ctrl")
            pie_data = {
                str(r["resultat"]): int(r["nb"])
                for _, r in tr.iterrows()
                if str(r["resultat"]) in ("Conforme", "Non-conforme", "En attente")
            }
            pie_path: Path | None = None
            if pie_data and is_block_enabled(presentation_cfg, "sec23.show_pie", True):
                pie_path = Path(
                    chart_pie(
                        pie_data,
                        "Répartition des résultats",
                        tmp_dir,
                        "pie_resultats.png",
                        **_chart_pie_compact_legend_kw(
                            len(pie_data),
                            legend_fontsize=ref_pie_legend_fs,
                            legend_ncol_max=legend_ncol_max,
                        ),
                        figure_scale=ref_pie_fs,
                    )
                )
            if pie_path is not None and pie_path.exists():
                builder.add_table_and_image_keep_together(
                    tbl,
                    table_caption=cap_res_ctrl,
                    col_widths=cw,
                    col_aligns=ca,
                    image_path=pie_path,
                    image_width_ratio=ref_pie_w,
                )
            else:
                builder.add_table(
                    tbl,
                    caption=cap_res_ctrl,
                    col_widths=cw,
                    col_aligns=ca,
                )
        elif show_placeholder:
            builder.add_paragraph("Aucune donnée de résultat disponible sur la période.")
        # On ne force pas systématiquement un saut de page ici.
        if profil_id == "agrainage":
            _render_zone_tub_block()
        if is_block_enabled(presentation_cfg, "sec23.show_categories_controles", False):
            df_cat_ctrl = curr_results.get("categories_chasse_controles")
            if df_cat_ctrl is not None and not df_cat_ctrl.empty:
                _render_categories_controles_block(df_cat_ctrl)

    def _render_zone_tub_block() -> None:
        """Bloc Zone TUB / hors zone TUB (sans entrée TOC dédiée)."""
        if not options.get("tub", False):
            return
        pt = curr_results.get("point_with_pnf")
        tub_codes = curr_results.get("tub_codes") or set()
        if pt is None or pt.empty or not tub_codes:
            return
        insee_col = _get_insee_col(pt)
        if not insee_col:
            return
        insee = pt[insee_col].astype(str).str.zfill(5)
        mask_tub = insee.isin(tub_codes)
        sub_tub = pt[mask_tub]
        sub_hors = pt[~mask_tub]
        if sub_tub.empty:
            return

        def _nc_non_conf(sub: pd.DataFrame) -> int:
            if "resultat" in sub.columns and not sub.empty:
                return count_controles_non_conformes_oscean(sub["resultat"])
            return 0

        total_tub = len(sub_tub)
        nc_tub = _nc_non_conf(sub_tub)
        total_hors_tub = len(sub_hors)
        nc_hors_tub = _nc_non_conf(sub_hors)
        data_tub = [
            {
                "zone": "Zone TUB",
                "nb_localisations": total_tub,
                "nb_non_conforme": nc_tub,
                "taux_non_conformite": nc_tub / total_tub if total_tub > 0 else pd.NA,
            },
            {
                "zone": "Hors zone TUB",
                "nb_localisations": total_hors_tub,
                "nb_non_conforme": nc_hors_tub,
                "taux_non_conformite": (
                    nc_hors_tub / total_hors_tub if total_hors_tub > 0 else pd.NA
                ),
            },
        ]
        agg_tub = sort_dataframe_desc(pd.DataFrame(data_tub), ["nb_localisations"])
        if profil_id != "agrainage":
            builder.add_section("sec_tub", "Zone TUB / Hors zone TUB")
        tbl = [["Zone", "Nb contrôles", "Contrôles non-conformes", "Taux de non-conformité"]]
        grp_labels, series_ctrl_tub = [], {"Contrôles": [], "Non conformes": []}
        for _, row in agg_tub.iterrows():
            t = format_pct_int_from_rate(row.get("taux_non_conformite"))
            tbl.append(
                [
                    str(row["zone"]),
                    str(int(row["nb_localisations"])),
                    str(int(row["nb_non_conforme"])),
                    t,
                ]
            )
            grp_labels.append(str(row["zone"]))
            series_ctrl_tub["Contrôles"].append(int(row["nb_localisations"]))
            series_ctrl_tub["Non conformes"].append(int(row["nb_non_conforme"]))
        builder.add_table(
            tbl,
            caption=pdf_metric_caption("Contrôles – Zone TUB vs Hors zone TUB", "ctrl"),
            col_widths=[
                avail_w * 0.30,
                avail_w * 0.23,
                avail_w * 0.23,
                avail_w * 0.24,
            ],
            col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"],
        )
        if grp_labels:
            bar_tub_path = chart_bar_grouped(
                grp_labels,
                series_ctrl_tub,
                "Contrôles : Zone TUB vs Hors zone TUB",
                "Nombre",
                tmp_dir,
                "bar_tub.png",
            )
            builder.add_image(Path(bar_tub_path), width_ratio=chart_ratio_base)

    def _render_sec22theme() -> None:
        if profil_id != "agrainage":
            return
        if not is_section_enabled(presentation_cfg, "sec22theme", True):
            return
        zone_ctrl_local = curr_results.get("zone_ctrl")
        if zone_ctrl_local is None or not options.get("tub", False):
            return
        builder.add_section(
            "sec22theme",
            section_title.get("sec22theme", "2.3. Analyse par zone"),
            level=2,
            toc_level=1,
        )
        tbl = [
            [
                "Zone",
                "Nb total",
                "Nb conforme",
                "Contrôles non-conformes",
                "Taux de non-conformité",
            ]
        ]
        for _, row in zone_ctrl_local.iterrows():
            t = format_pct_int_from_rate(row.get("taux_non_conformite"))
            tbl.append(
                [
                    zone_table_display_label(str(row["zone"])),
                    str(int(row["nb_total"])),
                    str(int(row["nb_conforme"])),
                    str(int(row["nb_non_conforme"])),
                    t,
                ]
            )
        builder.add_table(
            tbl,
            caption=pdf_metric_caption(
                "Contrôles par zone (Département hors zone TUB/PNF, TUB, PNF)", "ctrl"
            ),
            col_widths=[
                avail_w * 0.25,
                avail_w * 0.18,
                avail_w * 0.19,
                avail_w * 0.19,
                avail_w * 0.19,
            ],
            col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"],
        )

    def _render_sec22res() -> None:
        if profil_id != "agrainage":
            return
        if not is_section_enabled(presentation_cfg, "sec22res", True):
            return
        synth_local = curr_results.get("synthese_zone")
        if synth_local is None:
            return
        builder.add_section(
            "sec22res",
            section_title.get("sec22res", "2.4. Synthèse croisée par zone"),
            level=2,
            toc_level=1,
        )
        col_labels = []
        for c in synth_local.columns:
            if c == "ctrl_total":
                col_labels.append(PDF_LABEL_CTRL_LOCATIONS)
            elif c == "ctrl_infraction":
                col_labels.append("Contrôles non-conformes")
            elif c == "pve_nb":
                col_labels.append("Nombre d'infractions relevées par PVe")
            elif c == "pej_nb":
                col_labels.append(PDF_LABEL_PEJ_COUNT)
            else:
                col_labels.append(str(c))
        tbl = [col_labels]
        for _, row in synth_local.iterrows():
            cells = []
            for col_name, v in row.items():
                if col_name == "zone":
                    cells.append(zone_table_display_label(str(v)))
                elif isinstance(v, (int, float)) and pd.notna(v):
                    cells.append(str(int(v)))
                else:
                    cells.append(str(v))
            tbl.append(cells)
        builder.add_table(
            tbl,
            caption=(
                "Synthèse croisée par zone : contrôles non-conformes, "
                "PEJ et infractions relevées par PVe."
            ),
        )

    sec2_registry = SectionRegistry()
    sec2_registry.register("sec21", lambda _ctx: _render_sec21())
    sec2_registry.register("sec22", lambda _ctx: _render_sec22())
    sec2_registry.register("sec23", lambda _ctx: _render_sec23())
    sec2_registry.register("sec22theme", lambda _ctx: _render_sec22theme())
    sec2_registry.register("sec22res", lambda _ctx: _render_sec22res())

    sec2_order = resolve_sec2_render_order(
        sections_toc,
        include_zone_subsections=(profil_id == "agrainage"),
    )
    sec2_registry.render_many(sec2_order, {})

    sec3_order = [sid for sid, _ in sections_toc if sid in {"sec31", "sec32", "sec33"}]
    if not sec3_order:
        sec3_order = ["sec31", "sec32", "sec33"]

    def _render_categories_infractions_block(df_cat: pd.DataFrame) -> None:
        if df_cat is None or df_cat.empty:
            return
        hdr = ["Catégorie", "PVe", "PEJ", "Total", "Part %"]
        tbl = [hdr]
        tot_pve, tot_pej, tot_all = 0, 0, 0
        for _, r in df_cat.iterrows():
            pv = int(r.get("nb_pve", 0))
            pj = int(r.get("nb_pej", 0))
            tot = int(r.get("total", 0))
            pct = r.get("pct", 0.0)
            tot_pve += pv
            tot_pej += pj
            tot_all += tot
            tbl.append([str(r.get("libelle", r.get("categorie", ""))), str(pv), str(pj), str(tot), f"{pct} %"])
        tbl.append(["Total", str(tot_pve), str(tot_pej), str(tot_all), "100 %"])

        cw = [avail_w * 0.40, avail_w * 0.15, avail_w * 0.15, avail_w * 0.15, avail_w * 0.15]
        ca = ["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"]
        cap = pdf_metric_caption("Répartition des infractions par catégorie", "proc")

        donut_data = curr_results.get("categories_chasse_infractions_donut_data") or {}
        donut_path: Path | None = None
        if donut_data and sum(donut_data.values()) > 0:
            donut_path = Path(chart_pie(
                donut_data,
                "",
                tmp_dir,
                "categories_chasse_infractions_donut.png",
                **_chart_pie_compact_legend_kw(
                    len(donut_data),
                    legend_fontsize=ref_pie_legend_fs,
                    legend_ncol_max=legend_ncol_max,
                ),
                figure_scale=ref_pie_fs,
                donut=True,
            ))
        if donut_path is not None and donut_path.exists():
            builder.add_table_and_image_keep_together(
                tbl,
                table_caption=cap,
                col_widths=cw,
                col_aligns=ca,
                image_path=donut_path,
                image_width_ratio=ref_pie_w,
            )
        else:
            builder.add_table(tbl, caption=cap, col_widths=cw, col_aligns=ca)
        builder.add_spacer(3)

    def _begin_sec3_subsection(subsection_id: str) -> bool:
        """Ouvre le chapitre 3 sur la première sous-section (titre + contenu groupés)."""
        if not sec3_order or sec3_order[0] != subsection_id:
            return False
        builder.add_section("sec3", section_title["sec3"] + title_suffix, start_on_new_page=is_block_enabled(presentation_cfg, "sec3.start_on_new_page", False))
        if is_block_enabled(presentation_cfg, "sec3.show_categories_infractions", False):
            df_cat_inf = curr_results.get("categories_chasse_infractions")
            if df_cat_inf is not None and not df_cat_inf.empty:
                _render_categories_infractions_block(df_cat_inf)
        return True

    def _render_sec31() -> None:
        builder.add_section(
            "sec31",
            section_title["sec31"] + title_suffix,
            compact=True,
            toc_level=1,
            append_to_pending=_begin_sec3_subsection("sec31"),
        )
        if nb_pve > 0:
            pve_detail = curr_results.get("pve_detail")
            pve_top = curr_results.get("pve_top_infractions")
            intro_table: dict | None = None
            if (
                nb_pve >= 10
                and pve_top is not None
                and not pve_top.empty
                and is_block_enabled(presentation_cfg, "sec31.show_top_infractions", True)
            ):
                natinf_ref = load_natinf_ref(PROJECT_ROOT)
                top_df = pve_top.copy()
                top_df["numero_natinf"] = top_df["natinf"].astype(str).str.extract(r"(\d+)", expand=False)
                if not natinf_ref.empty:
                    top_df = top_df.merge(natinf_ref, on="numero_natinf", how="left")

                def _fmt_natinf_row(r):
                    qualif = str(r.get("qualification_infraction") or "").strip()
                    nature_raw = str(r.get("nature_infraction") or "").strip()
                    nature = nature_raw
                    if nature_raw.lower().startswith("contravention de classe "):
                        num = nature_raw[len("contravention de classe "):].strip()
                        nature = f"C{num}" if num else nature_raw
                    if qualif and nature:
                        return f"{qualif} ({nature})"
                    if qualif:
                        return qualif
                    if nature:
                        return nature
                    lib = str(r.get("libelle_natinf") or "").strip()
                    return lib if lib else str(r["natinf"])

                top_df["libelle_affich"] = top_df.apply(_fmt_natinf_row, axis=1)
                tbl_infractions = [["Infraction (qualification et nature)", "Nombre"]]
                for _, row in top_df.iterrows():
                    tbl_infractions.append([str(row["libelle_affich"]), str(int(row["nb"]))])
                intro_table = {
                    "data_rows": tbl_infractions,
                    "caption": "Infractions les plus relevées",
                    "col_widths": [avail_w * 0.75, avail_w * 0.25],
                    "col_aligns": ["LEFT", "RIGHT"],
                }
            pve_table_specs: list[dict] = []
            if (
                is_block_enabled(presentation_cfg, "sec31.show_detail_table", True)
                and isinstance(pve_detail, pd.DataFrame)
                and not pve_detail.empty
            ):
                base_cols = ["Numéro", "Date", "Commune", "Thématique"]
                hdr_det = base_cols + (["Zone"] if show_coeur_hors_pdf else [])
                tbl_det = [hdr_det]
                pve_det_show, pve_det_total = slice_proc_detail_for_pdf(
                    pve_detail, presentation_cfg, "sec31"
                )
                pve_det_cap = get_block_int(
                    presentation_cfg, "sec31.max_detail_rows", default=0
                )
                for _, r in pve_det_show.iterrows():
                    c_raw = str(r.get("commune", "")).strip()
                    if c_raw.isdigit():
                        c_val = _nom_commune(c_raw)
                    else:
                        c_val = c_raw
                    row_det = [
                        str(r.get("numero", "")),
                        str(r.get("date", "")),
                        c_val,
                        wrap_plain_text_for_pdf_paragraph(r.get("thematique", "")),
                    ]
                    if show_coeur_hors_pdf:
                        row_det.append(str(r.get("coeur_hors_coeur", "")))
                    tbl_det.append(row_det)
                cap_det = pdf_metric_caption("Détail des PVe", "proc")
                cap_det = format_proc_detail_caption(
                    cap_det,
                    shown=len(pve_det_show),
                    total=pve_det_total,
                    cap=pve_det_cap,
                )
                pve_table_specs.append(
                    {
                        "data_rows": tbl_det,
                        "caption": cap_det,
                        "col_aligns": ["LEFT"] * len(hdr_det),
                    }
                )
            pve_nat = curr_results.get("pve_natinf_analysis")
            if (
                is_block_enabled(presentation_cfg, "sec31.show_natinf_analysis", True)
                and isinstance(pve_nat, pd.DataFrame)
                and not pve_nat.empty
            ):
                tbl_nat = [["Thématique", "Libellé NATINF", "Nature d'infraction", "Nombre"]]
                for _, r in pve_nat.head(20).iterrows():
                    tbl_nat.append([
                        wrap_plain_text_for_pdf_paragraph(r.get("thematique", "")),
                        wrap_plain_text_for_pdf_paragraph(r.get("libelle_natinf", "")),
                        wrap_plain_text_for_pdf_paragraph(r.get("nature_infraction", "")),
                        str(int(r.get("nb", 0))),
                    ])
                pve_table_specs.append(
                    {
                        "data_rows": tbl_nat,
                        "caption": "Analyse des NATINF relevées (PVe)",
                        "col_widths": [
                            avail_w * 0.26,
                            avail_w * 0.34,
                            avail_w * 0.30,
                            avail_w * 0.10,
                        ],
                        "col_aligns": ["LEFT", "LEFT", "LEFT", "RIGHT"],
                    }
                )
            zone_table: dict | None = None
            zone_pve = curr_results.get("zone_pve")
            if is_block_enabled(presentation_cfg, "sec31.show_zone_table", True) and zone_pve is not None:
                tbl = [["Zone", "Nombre"]]
                for _, row in zone_pve.iterrows():
                    tbl.append(
                        [
                            zone_table_display_label(str(row["zone"])),
                            str(int(row["nb"])),
                        ]
                    )
                zone_table = {
                    "data_rows": tbl,
                    "caption": "PVe par zone",
                    "col_widths": [avail_w * 0.62, avail_w * 0.38],
                    "col_aligns": ["LEFT", "RIGHT"],
                }
            builder.add_key_figures_section_keep_together(
                [],
                intro_table=intro_table,
                table_specs=pve_table_specs,
                zone_table=zone_table,
                compact=True,
            )
        elif show_placeholder:
            builder.add_key_figures([])
            builder.add_paragraph("Aucun procès-verbal électronique sur la période.")

    def _render_sec32() -> None:
        builder.add_section(
            "sec32",
            section_title["sec32"] + title_suffix,
            compact=True,
            toc_level=1,
            append_to_pending=_begin_sec3_subsection("sec32"),
        )
        pej_detail = curr_results.get("pej_detail")
        merge_pej_detail_next = (
            is_block_enabled(presentation_cfg, "sec32.show_detail_table", True)
            and isinstance(pej_detail, pd.DataFrame)
            and not pej_detail.empty
        )
        pej_top = curr_results.get("pej_top_infractions")
        has_infractions = pej_top is not None and not pej_top.empty

        if has_infractions and is_block_enabled(presentation_cfg, "sec32.show_top_infractions", True):
            # Bandeau + infractions relevées (sans tableau « PEJ par thème » : voir procédures par domaine/thème).
            natinf_ref = load_natinf_ref(PROJECT_ROOT)
            top_cap = len(pej_top) if (nb_pej < 10 or profil_id == "ppp") else 6
            top_df = pej_top.head(top_cap).copy()
            top_df["numero_natinf"] = top_df["natinf"].astype(str).str.extract(r"(\d+)", expand=False)
            if not natinf_ref.empty:
                top_df = top_df.merge(natinf_ref, on="numero_natinf", how="left")
            def _fmt_natinf_row_pej(r):
                qualif = str(r.get("qualification_infraction") or "").strip()
                nature_raw = str(r.get("nature_infraction") or "").strip()
                nature = nature_raw
                if nature_raw.lower().startswith("contravention de classe "):
                    num = nature_raw[len("contravention de classe "):].strip()
                    nature = f"C{num}" if num else nature_raw
                if qualif and nature:
                    return f"{qualif} ({nature})"
                if qualif:
                    return qualif
                if nature:
                    return nature
                lib = str(r.get("libelle_natinf") or "").strip()
                return lib if lib else str(r["natinf"])
            top_df["libelle_affich"] = top_df.apply(_fmt_natinf_row_pej, axis=1)
            if profil_id == "ppp":
                tbl_infractions = [["Infraction (qualification uniquement)", "Nature d'infraction", "Nombre"]]
                for _, r in top_df.iterrows():
                    qualif = str(r.get("qualification_infraction") or "").strip()
                    if not qualif:
                        qualif = str(r.get("libelle_natinf") or "").strip()
                    if not qualif:
                        qualif = str(r["natinf"])

                    nature_raw = str(r.get("nature_infraction") or "").strip()
                    nature = nature_raw
                    if nature_raw.lower().startswith("contravention de classe "):
                        num = nature_raw[len("contravention de classe "):].strip()
                        nature = f"C{num}" if num else nature_raw

                    tbl_infractions.append([qualif, nature, str(int(r["nb"]))])

                col_w_infra = [avail_w * 0.55, avail_w * 0.30, avail_w * 0.15]
                col_a_infra = ["LEFT", "LEFT", "RIGHT"]
            else:
                tbl_infractions = [["Infraction (qualification et nature)", "Nombre"]]
                for _, row in top_df.iterrows():
                    tbl_infractions.append([str(row["libelle_affich"]), str(int(row["nb"]))])
                col_w_infra = [avail_w * 0.75, avail_w * 0.25]
                col_a_infra = ["LEFT", "RIGHT"]

            caption_infra_pej = (
                "Infractions relevées"
                if (nb_pej < 10 or profil_id == "ppp")
                else "Infractions les plus relevées"
            )
            builder.add_key_figures_and_table(
                [],
                tbl_infractions,
                caption=caption_infra_pej,
                col_widths=col_w_infra,
                col_aligns=col_a_infra,
                merge_with_next=merge_pej_detail_next,
            )
        else:
            builder.add_key_figures(
                [],
                merge_with_next=merge_pej_detail_next,
            )
        if (
            is_block_enabled(presentation_cfg, "sec32.show_detail_table", True)
            and isinstance(pej_detail, pd.DataFrame)
            and not pej_detail.empty
        ):
            hdr_pej = ["Numéro", "Date", "Commune", "Thématique"] + (
                ["Zone"] if show_coeur_hors_pdf else []
            )
            tbl_det = [hdr_pej]
            pej_det_show, pej_det_total = slice_proc_detail_for_pdf(
                pej_detail, presentation_cfg, "sec32"
            )
            pej_det_cap = get_block_int(presentation_cfg, "sec32.max_detail_rows", default=0)
            for _, r in pej_det_show.iterrows():
                row_pej = [
                    str(r.get("numero", "")),
                    str(r.get("date", "")),
                    str(r.get("commune", "")),
                    wrap_plain_text_for_pdf_paragraph(r.get("thematique", "")),
                ]
                if show_coeur_hors_pdf:
                    row_pej.append(str(r.get("coeur_hors_coeur", "")))
                tbl_det.append(row_pej)
            cap_pej = pdf_metric_caption("Détail des PEJ", "proc")
            cap_pej = format_proc_detail_caption(
                cap_pej,
                shown=len(pej_det_show),
                total=pej_det_total,
                cap=pej_det_cap,
            )
            builder.add_table(
                tbl_det,
                caption=cap_pej,
                col_aligns=["LEFT"] * len(hdr_pej),
            )
        zone_pej = curr_results.get("zone_pej")
        if is_block_enabled(presentation_cfg, "sec32.show_zone_table", True) and zone_pej is not None:
            tbl_z = [["Zone", "Nombre"]]
            for _, row in zone_pej.iterrows():
                tbl_z.append(
                    [
                        zone_table_display_label(str(row["zone"])),
                        str(int(row["nb"])),
                    ]
                )
            builder.add_table(
                tbl_z,
                caption=pdf_metric_caption("PEJ par zone", "proc"),
                col_widths=[avail_w * 0.62, avail_w * 0.38],
                col_aligns=["LEFT", "RIGHT"],
            )
        if is_block_enabled(presentation_cfg, "sec32.show_cloture_table", True) and "pej_clotur" in curr_results:
            tbl = [["Clôture PEJ", "Nombre"]]
            for _, row in curr_results["pej_clotur"].head(10).iterrows():
                tbl.append([str(row["cloture"]), str(int(row["nb"]))])
            builder.add_table(
                tbl,
                caption=pdf_metric_caption("PEJ par type de clôture", "proc"),
                              col_widths=[avail_w * 0.6, avail_w * 0.4],
                              col_aligns=["LEFT", "RIGHT"])
        if is_block_enabled(presentation_cfg, "sec32.show_suite_table", True) and "pej_suite" in curr_results:
            tbl = [["Suite", "Nombre"]]
            for _, row in curr_results["pej_suite"].head(10).iterrows():
                tbl.append([str(row["suite"]), str(int(row["nb"]))])
            builder.add_table(
                tbl,
                caption=pdf_metric_caption("PEJ par suite donnée", "proc"),
                              col_widths=[avail_w * 0.6, avail_w * 0.4],
                              col_aligns=["LEFT", "RIGHT"])
        pej_nat = curr_results.get("pej_natinf_analysis")
        if (
            is_block_enabled(presentation_cfg, "sec32.show_natinf_analysis", True)
            and isinstance(pej_nat, pd.DataFrame)
            and not pej_nat.empty
        ):
            tbl_nat = [["Thématique", "Libellé NATINF", "Nature d'infraction", "Nombre"]]
            for _, r in pej_nat.head(20).iterrows():
                tbl_nat.append([
                    wrap_plain_text_for_pdf_paragraph(r.get("thematique", "")),
                    wrap_plain_text_for_pdf_paragraph(r.get("libelle_natinf", "")),
                    wrap_plain_text_for_pdf_paragraph(r.get("nature_infraction", "")),
                    str(int(r.get("nb", 0))),
                ])
            builder.add_table(
                tbl_nat,
                caption="Analyse des NATINF relevées (PEJ)",
                col_widths=[
                    avail_w * 0.26,
                    avail_w * 0.34,
                    avail_w * 0.30,
                    avail_w * 0.10,
                ],
                col_aligns=["LEFT", "LEFT", "LEFT", "RIGHT"],
                keep_together=True,
            )

    def _render_sec33() -> None:
        builder.add_section(
            "sec33",
            section_title["sec33"] + title_suffix,
            toc_level=1,
            append_to_pending=_begin_sec3_subsection("sec33"),
        )
        if nb_pa <= 0:
            if show_placeholder:
                builder.add_paragraph("Aucune procédure administrative sur la période.")
            return
        proc_tables: list[dict] = []
        pa_theme = curr_results.get("pa_par_theme")
        if (
            pa_theme is not None
            and not pa_theme.empty
            and is_block_enabled(presentation_cfg, "sec33.show_theme_table", True)
        ):
                df = pa_theme.head(10).copy()
                tbl = [list(df.columns)]
                for _, row in df.iterrows():
                    tbl.append([str(v) for v in row.values])
                col_aligns = ["LEFT"] * len(df.columns)
                if "nb_pa" in df.columns:
                    idx = list(df.columns).index("nb_pa")
                    col_aligns[idx] = "RIGHT"
                proc_tables.append({
                    "data_rows": tbl,
                    "caption": pdf_metric_caption("PA par thème", "proc"),
                    "col_widths": None,
                    "col_aligns": col_aligns,
                })
        pa_detail = curr_results.get("pa_detail")
        merge_pa_detail_next = (
            is_block_enabled(presentation_cfg, "sec33.show_detail_table", True)
            and isinstance(pa_detail, pd.DataFrame)
            and not pa_detail.empty
        )
        show_kf = is_block_enabled(presentation_cfg, "sec33.show_key_figures", True)
        if show_kf and proc_tables:
            builder.add_key_figures_and_tables(
                [],
                proc_tables,
                compact=True,
                merge_with_next=merge_pa_detail_next,
            )
        elif show_kf:
            builder.add_key_figures(
                [],
                merge_with_next=merge_pa_detail_next,
            )
        elif proc_tables:
            for spec in proc_tables:
                builder.add_table(
                    spec["data_rows"],
                    caption=spec.get("caption", ""),
                    col_aligns=spec.get("col_aligns"),
                    keep_together=True,
                )
        if (
            is_block_enabled(presentation_cfg, "sec33.show_detail_table", True)
            and isinstance(pa_detail, pd.DataFrame)
            and not pa_detail.empty
        ):
            hdr_pa = ["Numéro", "Date", "Commune", "Thématique"] + (
                ["Zone"] if show_coeur_hors_pdf else []
            )
            tbl_det = [hdr_pa]
            pa_det_show, pa_det_total = slice_proc_detail_for_pdf(
                pa_detail, presentation_cfg, "sec33"
            )
            pa_det_cap = get_block_int(presentation_cfg, "sec33.max_detail_rows", default=0)
            for _, r in pa_det_show.iterrows():
                row_pa = [
                    str(r.get("numero", "")),
                    str(r.get("date", "")),
                    str(r.get("commune", "")),
                    wrap_plain_text_for_pdf_paragraph(r.get("thematique", "")),
                ]
                if show_coeur_hors_pdf:
                    row_pa.append(str(r.get("coeur_hors_coeur", "")))
                tbl_det.append(row_pa)
            cap_pa = pdf_metric_caption("Détail des PA", "proc")
            cap_pa = format_proc_detail_caption(
                cap_pa,
                shown=len(pa_det_show),
                total=pa_det_total,
                cap=pa_det_cap,
            )
            builder.add_table(
                tbl_det,
                caption=cap_pa,
                col_aligns=["LEFT"] * len(hdr_pa),
            )

    def _render_sec3_bundle() -> None:
        sec3_registry = SectionRegistry()
        sec3_registry.register("sec31", lambda _ctx: _render_sec31())
        sec3_registry.register("sec32", lambda _ctx: _render_sec32())
        sec3_registry.register("sec33", lambda _ctx: _render_sec33())
        sec3_registry.render_many(sec3_order, {})

    # Profils à zones hors agrainage (PNF, etc.) : bloc zone unique.
    if profil_id != "agrainage":
        _render_zone_tub_block()

    # ── ACTIVITÉ PAR TYPES D'USAGERS (hors profil dédié « analyses.type_usager ») ──
    def _render_sec4() -> None:
        if not is_section_enabled(presentation_cfg, "sec4", True):
            return
        builder.add_section(
            "sec4",
            section_title["sec4"] + title_suffix,
            start_on_new_page=is_block_enabled(presentation_cfg, "sec4.start_on_new_page", False),
            compact=True,
        )
        builder.add_paragraph(
            "<i>Note importante : Le décompte des effectifs selon le type d'usager suit des règles spécifiques qui sont détaillées dans la notice méthodologique.</i>",
        )
        if profil_id == "ppp":
            # Analyse spécifique PPP : répartition des PEJ par types d'usagers
            pej_df = curr_results.get("_raw_pej_filtered", pd.DataFrame())
            if not pej_df.empty and "type_usager" in pej_df.columns:
                # 1. Répartition des PEJ par type d'usager
                pej_usagers = pej_df["type_usager"].fillna("Non renseigné").astype(str).value_counts().rename_axis("type_usager").reset_index(name="nb")
                total_pej_usagers = pej_usagers["nb"].sum()
                tbl_pej_usagers = [["Type d'usager", "Nombre de PEJ", "Part (%)"]]
                for _, r in pej_usagers.iterrows():
                    pct = f"{int(round(r['nb'] * 100 / total_pej_usagers))}%" if total_pej_usagers > 0 else "0%"
                    tbl_pej_usagers.append([str(r["type_usager"]), str(int(r["nb"])), pct])

                builder.add_section(
                    "sec43",
                    section_title.get("sec43", "3.1. Procédures d'enquête judiciaire (PEJ) par type d'usager"),
                    level=2,
                    toc_level=1,
                    append_to_pending=False,
                )
                builder.add_table(
                    tbl_pej_usagers,
                    caption="Répartition des procédures d'enquête judiciaire (PEJ) par type d'usager",
                    col_widths=[avail_w * 0.50, avail_w * 0.25, avail_w * 0.25],
                    col_aligns=["LEFT", "RIGHT", "RIGHT"],
                    keep_together=True,
                )
                builder.add_spacer(4)

                # 2. Répartition croisée NATINF / Type d'usager
                natinf_col = "NATINF_PEJ" if "NATINF_PEJ" in pej_df.columns else "NATINF"
                if natinf_col in pej_df.columns:
                    pej_cross = pej_df.groupby([natinf_col, "type_usager"]).size().rename("nb").reset_index()
                    # Charger les libellés de NATINF pour enrichir
                    natinf_ref = load_natinf_ref(PROJECT_ROOT)
                    pej_cross["numero_natinf"] = pej_cross[natinf_col].astype(str).str.extract(r"(\d+)", expand=False)
                    if not natinf_ref.empty:
                        pej_cross = pej_cross.merge(natinf_ref, on="numero_natinf", how="left")

                    tbl_cross = [["Libellé NATINF", "Type d'usager", "Nombre"]]
                    for _, r in pej_cross.sort_values(by="nb", ascending=False).iterrows():
                        qualif = str(r.get("qualification_infraction") or "").strip()
                        if not qualif:
                            qualif = str(r.get("libelle_natinf") or "").strip()
                        if not qualif:
                            qualif = str(r[natinf_col])

                        tbl_cross.append([qualif, str(r["type_usager"]), str(int(r["nb"]))])

                    builder.add_table(
                        tbl_cross,
                        caption="Répartition des infractions (NATINF) par type d'usager",
                        col_widths=[avail_w * 0.50, avail_w * 0.35, avail_w * 0.15],
                        col_aligns=["LEFT", "LEFT", "RIGHT"],
                        keep_together=False,
                        max_rows_keep_together=15,
                    )
                    builder.add_spacer(4)
            else:
                builder.add_paragraph("Aucune donnée d'activité par type d'usager pour la période.")
        elif curr_results.get("_pdf_show_pression_controle_usagers"):
            _pdf_section_pression_controle_usagers(
                builder,
                curr_results,
                tmp_dir,
                avail_w,
                (profile.get("filter") or {}).get("type_usager_target") or [],
                presentation_cfg=presentation_cfg,
                pie_ratio=ref_pie_w,
                legend_fontsize=ref_pie_legend_fs,
                legend_ncol_max=legend_ncol_max,
                figure_scale=ref_pie_fs,
            )
            builder.add_spacer(4)
        elif curr_results.get("_pdf_show_activite_usagers"):
            base_sec4_fs = max(0.88, float(figure_scale) * 0.88)
            _pdf_section_activite_par_types_usagers(
                builder,
                curr_results,
                tmp_dir,
                avail_w,
                presentation_cfg=presentation_cfg,
                section_title=section_title,
                pie_ratio=ref_pie_w,
                bar_ratio=chart_ratio_base * 0.88,
                legend_fontsize=ref_pie_legend_fs,
                legend_ncol_max=legend_ncol_max,
                figure_scale=base_sec4_fs,
                pie_figure_scale=ref_pie_fs,
            )
            builder.add_spacer(4)
        elif show_placeholder:
            builder.add_paragraph("Aucune donnée d'activité par type d'usager pour la période.")

    sec34_registry = SectionRegistry()
    sec34_registry.register("sec3", lambda _ctx: _render_sec3_bundle())
    sec34_registry.register("sec4", lambda _ctx: _render_sec4())
    sec34_order = [sid for sid, _ in sections_toc if sid in {"sec3", "sec4"}]
    if not sec34_order:
        sec34_order = ["sec3", "sec4"]
    sec34_registry.render_many(sec34_order, {})



_render_profil_sections = render_thematic_profil_sections
