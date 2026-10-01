# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
# sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
# Voir la Licence Publique Générale GNU pour plus de détails.
#
# CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
# Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
# intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
# clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
# doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
# de l'auteur original (Aguirre MAURIN).

"""
========================================================================================
MODULE : GENERATEUR DES SECTIONS PDF DE PROFIL (`sections_profil.py`)
========================================================================================
Ce module regroupe les fonctions de construction des différentes sections du PDF
d'un profil thématique ou global (sections 1 à 6).

Sections traitées :
  - Section 1 : Introduction et synthèse des chiffres clés.
  - Section 2 : Activité de contrôle (localisations, opérations, conformités, usagers).
  - Section 3 : Activité administrative et judiciaire (PA, PEJ, PVe, NATINF).
  - Section 4 : Analyses croisées et ventilations temporelles (courbes, histogrammes).
  - Section 5 : Cartographie thématique (cartes PNG superposées).
  - Section 6 : Annexes, méthodologie et glossaire.
========================================================================================
"""
from pathlib import Path
import pandas as pd

from core.engine.pdf_context import PdfContext
from core.common.cartographie_config import has_cartography_catalog, expected_map_filenames_for_selection
from core.common.pdf_presentation_config import is_section_enabled, is_block_enabled, get_block_int, format_proc_detail_caption, slice_proc_detail_for_pdf, is_commentaires_auto_enabled
from core.engine.commentaires_auto import build_comment_paragraph
from core.common.pdf_table_sort import (
    PDF_LABEL_CTRL_LOCATIONS,
    PDF_LABEL_CTRL_LOCATIONS_SHORT,
    PDF_LABEL_NON_CONFORME_LOCATIONS,
    PDF_LABEL_PEJ_COUNT,
    pdf_metric_caption,
    sort_dataframe_desc as _sort_desc,
)
from core.common.percent_format import format_pct_int_from_rate, tab_counts_to_pct_strings, int_percents_largest_remainder
from core.engine.engine_pdf_helpers import nb_non_conformes_brut, truncate_with_dash as _truncate_with_dash, pct_table_cell as _pct_table_cell
from core.common.rendus_graphiques import chart_bar_stacked, chart_line_evolution, chart_pie, chart_bar_horizontal_stacked, chart_stackplot_resultats_domaine
from core.common.utilitaires_metier import _load_csv_opt
from core.common.dataframe_rollup import rollup_small_categories
from core.common.pdf_utils import ofb_table, truncate_text_to_width, wrap_plain_text_for_pdf_paragraph
from core.common.pdf_usagers_domaine_table import build_usagers_x_domaine_pdf_rows, resolve_usagers_x_domaine_header_layout, resolve_usagers_x_domaine_header_font_size, resolve_usagers_x_domaine_header_max_lines, usagers_x_domaine_col_widths
from core.common.pdf_shared_sections import add_procedures_par_type_usager_subsection, build_filtered_glossary_rows, build_sec6_methodology_context, build_sec6_methodology_html, load_glossary_config
from core.engine.generation_pdf_profil import _build_rows_resultats_controles_pdf, resolve_ventilation_mode_global
from core.common.carte_helper import expected_map_filenames
from core.common.cartographie_config import expected_map_filenames_for_selection
from PIL import Image as PILImage
_ROOT = Path(__file__).resolve().parents[2]
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage, Paragraph, Spacer

def _chart_pie_compact_legend_kw(
    n_categories: int,
    *,
    legend_fontsize: float,
    legend_ncol_max: int,
) -> dict[str, float | int]:
    ncol = min(n_categories, max(1, legend_ncol_max))
    return {
        "legend_fontsize": legend_fontsize,
        "legend_ncol": max(1, ncol),
    }

def render_sec1(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec1", ctx.section_title["sec1"])
    kf: list[tuple[str, str]] = []
    if ctx.nb_ops > 0:
        kf.append((str(ctx.nb_ops), "Opérations de contrôle"))
    if ctx.nb_localisations > 0:
        kf.append((str(ctx.nb_localisations), "Localisations de contrôle"))
    
    tab_nc = ctx.tab_resultats_controles
    if tab_nc is not None and not tab_nc.empty and "resultat" in tab_nc.columns:
        nb_nc_row = tab_nc.loc[tab_nc["resultat"].astype(str).str.strip() == "Non-conforme", "nb"]
        nb_nc = int(nb_nc_row.sum()) if not nb_nc_row.empty else 0
        if nb_nc > 0:
            taux_nc = nb_nc / ctx.nb_localisations if ctx.nb_localisations else 0
            kf.append((str(nb_nc), PDF_LABEL_NON_CONFORME_LOCATIONS))
            kf.append((format_pct_int_from_rate(taux_nc), "Taux de non-conformité"))
    elif ctx.tab_resultats is not None:
        nb_nc = nb_non_conformes_brut(ctx.tab_resultats)
        if nb_nc > 0:
            taux_nc = nb_nc / ctx.nb_localisations if ctx.nb_localisations else 0
            kf.append((str(nb_nc), PDF_LABEL_NON_CONFORME_LOCATIONS))
            kf.append((format_pct_int_from_rate(taux_nc), "Taux de non-conformité"))
            
    if ctx.nb_pej > 0:
        kf.append((str(ctx.nb_pej), PDF_LABEL_PEJ_COUNT))
    kf.append((str(ctx.nb_pa), "Nombre de PA"))
    if ctx.nb_pve > 0:
        kf.append((str(ctx.nb_pve), "Nombre de PVe"))
    if not kf:
        kf.append(("0", "Aucune activité enregistrée"))
    ctx.builder.add_key_figures(kf)

    if ctx.nb_localisations == 0 and ctx.nb_pve == 0 and ctx.nb_pej == 0 and ctx.nb_pa == 0:
        ctx.builder.add_paragraph(
            "<br/><b>Information Bilan Nul :</b> Aucun point de contrôle ni procédure n'a été enregistré sur la période et le périmètre sélectionnés.",
            style="BodyText",
        )


def render_sec2_chap(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec2_chap", ctx.section_title["sec2_chap"])


def render_sec21(ctx: PdfContext) -> None:
    # 2.1 — Analyse de l’ensemble de la période du bilan
    if (
        is_section_enabled(ctx.presentation_cfg, "sec21", True)
        and ctx.agg_periode is not None
        and not ctx.agg_periode.empty
    ):
        is_mensuel = ctx.ventilation_mode == "mensuelle"
        is_trimestriel = ctx.ventilation_mode == "trimestrielle"
        is_hebdo = ctx.ventilation_mode == "hebdomadaire"
        label_periode = (
            "Mois"
            if is_mensuel
            else ("Trimestre" if is_trimestriel else ("Semaine" if is_hebdo else "Année"))
        )
        texte_ventilation = (
            "par mois "
            if is_mensuel
            else (
                "par trimestre "
                if is_trimestriel
                else ("par semaine " if is_hebdo else "par année ")
            )
        )
        ctx.builder.add_section(
            "sec21",
            ctx.section_title["sec21"],
            level=2,
            toc_level=1,
        )
        ctx.builder.add_paragraph(
            "Ventilation des principaux indicateurs globaux "
            + texte_ventilation
            + "sur l'ensemble de la période du bilan.",
        )
        tbl = [
            [
                label_periode,
                PDF_LABEL_CTRL_LOCATIONS_SHORT,
                PDF_LABEL_NON_CONFORME_LOCATIONS,
                "Taux de non-conformité",
                "PEJ",
                "PA",
                "PVe",
            ]
        ]
        for _, row in ctx.agg_periode.iterrows():
            taux_str = (
                format_pct_int_from_rate(row.get("taux_non_conformite_localisations"))
                if pd.notna(row.get("taux_non_conformite_localisations"))
                else "n.d."
            )
            tbl.append(
                [
                    str(row["periode"]),
                    str(int(row["nb_localisations"])),
                    str(int(row["nb_localisations_non_conformes"])),
                    taux_str,
                    str(int(row["nb_pej"])),
                    str(int(row["nb_pa"])),
                    str(int(row["nb_pve"])),
                ]
            )
        cap = (
            "Indicateurs mensuels"
            if is_mensuel
            else (
                "Indicateurs trimestriels"
                if is_trimestriel
                else ("Indicateurs hebdomadaires" if is_hebdo else "Indicateurs annuels")
            )
        )
        if is_block_enabled(ctx.presentation_cfg, "sec21.show_table", True):
            ctx.builder.add_table(
                tbl,
                caption=(
                    f"{cap} "
                    f"({PDF_LABEL_CTRL_LOCATIONS_SHORT}, PVe, PEJ, et PA)"
                ),
                col_widths=[
                    ctx.avail_w * 0.12,
                    ctx.avail_w * 0.14,
                    ctx.avail_w * 0.18,
                    ctx.avail_w * 0.14,
                    ctx.avail_w * 0.14,
                    ctx.avail_w * 0.14,
                    ctx.avail_w * 0.14,
                ],
                col_aligns=["RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"],
            )

        period_labels = [str(v) for v in ctx.agg_periode["periode"].tolist()]
        if ctx.ventilation_mode == "mensuelle":
            titre_ctrl = "Contrôles par mois (conformes / non-conformes)"
            titre_proc = "Procédures et PVe par mois"
        elif ctx.ventilation_mode == "trimestrielle":
            titre_ctrl = "Contrôles par trimestre (conformes / non-conformes)"
            titre_proc = "Procédures et PVe par trimestre"
        elif ctx.ventilation_mode == "hebdomadaire":
            titre_ctrl = "Contrôles par semaine (conformes / non-conformes)"
            titre_proc = "Procédures et PVe par semaine"
        else:
            titre_ctrl = "Contrôles par année (conformes / non-conformes)"
            titre_proc = "Procédures et PVe par année"

        conformes = [
            int(row["nb_localisations"]) - int(row["nb_localisations_non_conformes"])
            for _, row in ctx.agg_periode.iterrows()
        ]
        non_conformes = [int(v) for v in ctx.agg_periode["nb_localisations_non_conformes"].tolist()]
        stacked_ctrl_path = chart_bar_stacked(
            period_labels,
            {"Conformes": conformes, "Non-conformes": non_conformes},
            titre_ctrl,
            PDF_LABEL_CTRL_LOCATIONS,
            ctx.tmp_dir,
            "bar_global_ctrl_stacked.png",
            legend_fontsize=ctx.legend_fontsize,
            legend_ncol_max=ctx.legend_ncol_max,
            figure_scale=ctx.figure_scale,
        )
        if is_block_enabled(ctx.presentation_cfg, "sec21.show_chart_controles", True):
            ctx.builder.add_image(Path(stacked_ctrl_path), width_ratio=ctx.chart_bar_w)

        series_proc = {
            "PEJ": [int(v) for v in ctx.agg_periode["nb_pej"].tolist()],
            "PA": [int(v) for v in ctx.agg_periode["nb_pa"].tolist()],
            "PVe": [int(v) for v in ctx.agg_periode["nb_pve"].tolist()],
        }
        if any(sum(vals) > 0 for vals in series_proc.values()) and is_block_enabled(
            ctx.presentation_cfg, "sec21.show_chart_procedures", True
        ):
            stacked_proc_path = chart_bar_stacked(
                period_labels,
                series_proc,
                titre_proc,
                "Nombre",
                ctx.tmp_dir,
                "bar_global_proc_stacked.png",
                legend_fontsize=ctx.legend_fontsize,
                legend_ncol_max=ctx.legend_ncol_max,
                figure_scale=ctx.figure_scale,
            )
            ctx.builder.add_image(Path(stacked_proc_path), width_ratio=ctx.chart_bar_w)

        period_days = int((ctx.date_fin - ctx.date_deb).days)
        line_source = ctx.agg_periode
        line_labels = period_labels
        if period_days < 730 and ctx.ventilation_mode != "hebdomadaire":
            agg_line_month = _load_csv_opt(ctx.out_dir, "indicateurs_global_par_mois.csv")
            if agg_line_month is not None and not agg_line_month.empty:
                line_source = agg_line_month
                line_labels = [str(v) for v in agg_line_month["periode"].tolist()]
                
        if (
            line_source is not None
            and not line_source.empty
            and is_block_enabled(ctx.presentation_cfg, "sec21.show_chart_taux_line", True)
        ):
            taux_values = []
            for _, row in line_source.iterrows():
                val = row.get("taux_non_conformite_controles")
                taux_values.append(int(round(float(val) * 100)) if pd.notna(val) else 0)
            if any(v > 0 for v in taux_values):
                line_path = chart_line_evolution(
                    line_labels,
                    {"Taux de non-conformité (%)": taux_values},
                    "Évolution du taux de non-conformité",
                    "Taux (%)",
                    ctx.tmp_dir,
                    "line_global_taux_inf.png",
                    legend_fontsize=ctx.legend_fontsize,
                    legend_ncol_max=ctx.legend_ncol_max,
                    figure_scale=ctx.figure_scale,
                )
                ctx.builder.add_image(Path(line_path), width_ratio=ctx.chart_bar_w)

        ctx.builder.add_spacer(2)

    elif is_section_enabled(ctx.presentation_cfg, "sec21", True) and ctx.show_placeholder:
        ctx.builder.add_section(
            "sec21",
            ctx.section_title["sec21"],
            level=2,
            toc_level=1,
        )
        ctx.builder.add_paragraph("Aucun indicateur disponible sur la période.")


def render_sec22(ctx: PdfContext) -> None:
    ctx.builder.add_section(
        "sec22",
        ctx.section_title["sec22"],
        level=2,
        toc_level=1,
    )
    pej_dom= _load_csv_opt(ctx.out_dir, "pej_global_par_domaine.csv")
    df_dom = pd.DataFrame()
    if ctx.agg_domaine is not None and not ctx.agg_domaine.empty:
        df_dom = ctx.agg_domaine.copy()
        df_dom["domaine"] = df_dom["domaine"].astype(str)
    if pej_dom is not None and not pej_dom.empty:
        pej_dom_clean = pej_dom.copy()
        if "DOMAINE" in pej_dom_clean.columns:
            pej_dom_clean = pej_dom_clean.rename(columns={"DOMAINE": "domaine"})
        pej_dom_clean["domaine"] = pej_dom_clean["domaine"].astype(str)
        if df_dom.empty:
            df_dom = pej_dom_clean
            df_dom["nb"] = 0
        else:
            df_dom = pd.merge(df_dom, pej_dom_clean[["domaine", "nb_pej"]], on="domaine", how="outer")
            df_dom["nb"] = df_dom["nb"].fillna(0)
            
    if not df_dom.empty:
        if "nb_pej" not in df_dom.columns:
            df_dom["nb_pej"] = 0
        df_dom["nb_pej"] = df_dom["nb_pej"].fillna(0)
        df_dom["total_act"] = df_dom["nb"] + df_dom["nb_pej"]
        df_dom = df_dom.sort_values(by="total_act", ascending=False)
        
        tbl = [["Domaine", "Opérations", "Localisations", "PEJ"]]
        for _, row in df_dom.head(25).iterrows():
            nb_ops_val = row.get("nb_operations", 0)
            try:
                nb_ops_str = str(int(nb_ops_val)) if pd.notna(nb_ops_val) else "0"
            except (ValueError, TypeError):
                nb_ops_str = "0"
            tbl.append([str(row["domaine"]), nb_ops_str, str(int(row["nb"])), str(int(row["nb_pej"]))])
        ctx.builder.add_table(
            tbl,
            caption="Répartition de l'activité par domaines (contrôles + PEJ)",
            col_widths=[ctx.avail_w * 0.45, ctx.avail_w * 0.17, ctx.avail_w * 0.19, ctx.avail_w * 0.19],
            col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"],
        )
        if is_block_enabled(ctx.presentation_cfg, "sec22.show_overflow_note", True) and len(df_dom) > 25:
            ctx.builder.add_paragraph(
                f"... et {len(df_dom) - 25} autres domaines.",
                style="BodySmall",
            )
        if not df_dom.empty:
            pie_data = {str(row["domaine"])[:34]: int(row["total_act"]) for _, row in df_dom.iterrows() if int(row["total_act"]) > 0}
            if is_block_enabled(ctx.presentation_cfg, "sec22.show_pie", True) and pie_data:
                pie_path = chart_pie(
                    pie_data,
                    "Répartition de l'activité par domaines (contrôles + PEJ)",
                    ctx.tmp_dir,
                    "pie_domaine.png",
                    **_chart_pie_compact_legend_kw(
                        len(pie_data),
                        legend_fontsize=ctx.ref_pie_legend_fs,
                        legend_ncol_max=ctx.legend_ncol_max,
                    ),
                    figure_scale=ctx.ref_pie_fs,
                )
                ctx.builder.add_image(Path(pie_path), width_ratio=ctx.ref_pie_w)
    elif ctx.show_placeholder:
        ctx.builder.add_paragraph("Aucune donnée domaine disponible.")

def render_sec22theme(ctx: PdfContext) -> None:
    ctx.builder.add_section(
        "sec22theme",
        ctx.section_title["sec22theme"],
        level=2,
        toc_level=1,
    )
    agg_theme_display = rollup_small_categories(
        ctx.agg_theme,
        label_col="theme",
        other_label="Autres thèmes de contrôle",
        value_col="nb",
        min_pct=0.01,
        sum_cols=["nb", "nb_operations", "taux"],
        max_rows=20,
    )
    if agg_theme_display is not None and not agg_theme_display.empty:
        if is_commentaires_auto_enabled(ctx.presentation_cfg):
            p_comm = build_comment_paragraph("sec21_themes", ctx)
            if p_comm:
                ctx.builder.append_pending_paragraph(p_comm)
        tbl = [["Thème", "Opérations", "Localisations", "Taux loc."]]
        for _, row in agg_theme_display.iterrows():
            taux_str = format_pct_int_from_rate(row.get("taux"))
            nb_ops_val = row.get("nb_operations", 0)
            try:
                nb_ops_str = str(int(nb_ops_val)) if pd.notna(nb_ops_val) else "0"
            except (ValueError, TypeError):
                nb_ops_str = "0"
            tbl.append([str(row["theme"])[:45], nb_ops_str, str(int(row["nb"])), taux_str])
        ctx.builder.add_table(
            tbl,
            caption=pdf_metric_caption("Nombre de contrôles par thèmes", "ctrl"),
            col_widths=[ctx.avail_w * 0.44, ctx.avail_w * 0.18, ctx.avail_w * 0.19, ctx.avail_w * 0.19],
            col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"],
        )
    elif ctx.show_placeholder:
        ctx.builder.add_paragraph("Aucune donnée thème disponible.")

def render_sec22res(ctx: PdfContext) -> None:
    ctx.builder.add_section(
        "sec22res",
        ctx.section_title["sec22res"],
        level=2,
        toc_level=1,
    )
    if is_commentaires_auto_enabled(ctx.presentation_cfg):
        p_comm = build_comment_paragraph("sec22_conformite", ctx)
        if p_comm:
            ctx.builder.append_pending_paragraph(p_comm)
    use_detail = ctx.tab_resultats_controles is not None and not ctx.tab_resultats_controles.empty
    show_res_table = is_block_enabled(ctx.presentation_cfg, "sec22res.show_table", True)
    show_res_pie = is_block_enabled(ctx.presentation_cfg, "sec22res.show_pie", True)
    show_chart_domaine = is_block_enabled(
        ctx.presentation_cfg, "sec22res.show_chart_resultats_domaine", True
    )
    res_par_dom = _load_csv_opt(ctx.out_dir, "controles_global_resultats_par_domaine.csv")
    split_by_row = bool(ctx.tables_layout.get("split_by_row"))

    def _mk_centered_image(chart_path: Path, width_ratio: float):
        w = ctx.builder.avail_w * width_ratio
        try:
            with PILImage.open(str(chart_path)) as im:
                width_px, height_px = im.size
            ratio = (height_px / float(width_px)) if width_px > 0 else 0.45
        except OSError:
            ratio = 0.45
        img = RLImage(str(chart_path), width=w, height=w * ratio)
        img.hAlign = "CENTER"
        
        ctx.builder._figure_counter += 1
        fig_text = f"Figure {ctx.builder._figure_counter}"
        fig_para = Paragraph(fig_text, ctx.builder.styles.get("FigureCaption", ctx.builder.styles["BodySmall"]))
        
        from reportlab.platypus import KeepTogether
        return KeepTogether([img, fig_para])

    block: list = []
    pie_res: dict[str, int] | None = None

    if use_detail and show_res_table:
        tbl_pdf = _build_rows_resultats_controles_pdf(ctx.tab_resultats_controles)
        block.append(
            Paragraph(
                pdf_metric_caption("Résultats des contrôles", "ctrl"),
                ctx.builder.styles["TableCaption"],
            )
        )
        block.append(Spacer(1, 1 * mm))
        block.append(
            ofb_table(
                tbl_pdf,
                col_widths=[ctx.avail_w * 0.44, ctx.avail_w * 0.18, ctx.avail_w * 0.38],
                col_aligns=["LEFT", "RIGHT", "RIGHT"],
                split_by_row=ctx.split_by_row,
            )
        )
        strip_res = ctx.tab_resultats_controles["resultat"].astype(str).str.strip()
        dont_sum = int(
            ctx.tab_resultats_controles.loc[
                strip_res.isin(["Dont manquement", "Dont infraction", "    Dont manquement", "    Dont infraction"]),
                "nb",
            ].sum()
        )
        nc_val = (
            int(ctx.tab_resultats_controles.loc[strip_res == "Non-conforme", "nb"].sum())
            if (strip_res == "Non-conforme").any()
            else 0
        )
        if dont_sum > nc_val:
            block.append(Spacer(1, 1 * mm))
            block.append(
                Paragraph(
                    "* Note : le total des résultats détaillés peut excéder le total des contrôles du fait de doubles qualifications possibles (manquement administratif et infraction pénale).",
                    ctx.builder.styles.get("TableNote", ctx.builder.styles.get("FigureCaption", ctx.builder.styles["BodySmall"])),
                )
            )
        block.append(Spacer(1, 2 * mm))
        strip_res = ctx.tab_resultats_controles["resultat"].astype(str).str.strip()
        pie_mask = strip_res.isin(["Conforme", "Non-conforme", "En attente"])
        pie_res = {}
        for _, row in ctx.tab_resultats_controles.loc[pie_mask].iterrows():
            pie_res[str(row["resultat"]).strip()] = int(row["nb"])
    elif ctx.tab_resultats is not None and not ctx.tab_resultats.empty and show_res_table:
        tbl = [["Résultat", "Nombre", "Taux"]]
        tr_pct = tab_counts_to_pct_strings(ctx.tab_resultats["nb"].astype(int).tolist())
        for i, (_, row) in enumerate(ctx.tab_resultats.iterrows()):
            tbl.append([str(row["resultat"]), str(int(row["nb"])), tr_pct[i]])
        block.append(
            Paragraph(
                pdf_metric_caption(
                    "Résultats des contrôles (libellés OSCEAN)", "ctrl"
                ),
                ctx.builder.styles["TableCaption"],
            )
        )
        block.append(Spacer(1, 1 * mm))
        block.append(
            ofb_table(
                tbl,
                col_widths=[ctx.avail_w * 0.50, ctx.avail_w * 0.25, ctx.avail_w * 0.25],
                col_aligns=["LEFT", "RIGHT", "RIGHT"],
                split_by_row=ctx.split_by_row,
            )
        )
        block.append(Spacer(1, 2 * mm))
        pie_res = {str(r["resultat"]): int(r["nb"]) for _, r in ctx.tab_resultats.iterrows()}

    if show_res_pie and pie_res:
        pie_path = chart_pie(
            pie_res,
            "Répartition des résultats",
            ctx.tmp_dir,
            "pie_global_resultats.png",
            **_chart_pie_compact_legend_kw(
                len(pie_res),
                legend_fontsize=ctx.ref_pie_legend_fs,
                legend_ncol_max=ctx.legend_ncol_max,
            ),
            figure_scale=ctx.ref_pie_fs,
        )
        block.append(Spacer(1, 1 * mm))
        block.append(_mk_centered_image(Path(pie_path), ctx.ref_pie_w))
        block.append(Spacer(1, 1.5 * mm))

    if (
        show_chart_domaine
        and res_par_dom is not None
        and not res_par_dom.empty
        and {"Conforme", "Non-conforme", "En attente"}.issubset(res_par_dom.columns)
    ):
        df_dom = res_par_dom.head(10).copy()
        dom_lbl = [str(v)[:34] for v in df_dom["domaine"].tolist()]
        y1 = [float(v) for v in df_dom["Conforme"].tolist()]
        y2 = [float(v) for v in df_dom["Non-conforme"].tolist()]
        y3 = [float(v) for v in df_dom["En attente"].tolist()]
        if sum(y1) + sum(y2) + sum(y3) > 0:
            stack_path = chart_stackplot_resultats_domaine(
                dom_lbl,
                y1,
                y2,
                y3,
                "Résultats des contrôles par domaine",
                "Nombre de localisations",
                ctx.tmp_dir,
                "stack_global_resultats_domaine.png",
                legend_fontsize=max(6.5, ctx.legend_fontsize - 1.0),
                figure_scale=ctx.figure_scale * 0.72,
            )
            block.append(Spacer(1, 1 * mm))
            block.append(_mk_centered_image(Path(stack_path), ctx.chart_bar_w * 0.94))

    show_cat_ctrl = is_block_enabled(ctx.presentation_cfg, "sec23.show_categories_controles", False) or is_block_enabled(ctx.presentation_cfg, "sec22res.show_categories_controles", False)
    if show_cat_ctrl and ctx.categories_controles_df is not None and not ctx.categories_controles_df.empty:
        df_cat = ctx.categories_controles_df
        hdr = ["Catégorie", "Contrôles", "Conformes", "Non conformes", "% Non-conforme"]
        tbl_cat = [hdr]
        tot_c, tot_cf, tot_nc = 0, 0, 0
        for _, r in df_cat.iterrows():
            c_tot = int(r.get("total", 0))
            c_conf = int(r.get("conforme", 0))
            c_nc = int(r.get("non_conforme", 0))
            t_nc = r.get("taux_non_conforme", 0.0)
            tot_c += c_tot
            tot_cf += c_conf
            tot_nc += c_nc
            tbl_cat.append([str(r.get("libelle", r.get("categorie", ""))), str(c_tot), str(c_conf), str(c_nc), f"{t_nc} %"])
        taux_tot = round((tot_nc / tot_c) * 100, 1) if tot_c > 0 else 0.0
        tbl_cat.append(["Total", str(tot_c), str(tot_cf), str(tot_nc), f"{taux_tot} %"])
        
        cw = [ctx.avail_w * 0.36, ctx.avail_w * 0.16, ctx.avail_w * 0.16, ctx.avail_w * 0.16, ctx.avail_w * 0.16]
        ca = ["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"]
        block.append(Spacer(1, 2 * mm))
        block.append(Paragraph(pdf_metric_caption("Répartition des contrôles par catégorie", "ctrl"), ctx.builder.styles["TableCaption"]))
        block.append(Spacer(1, 1 * mm))
        block.append(ofb_table(tbl_cat, col_widths=cw, col_aligns=ca, split_by_row=ctx.split_by_row))
        if ctx.categories_controles_donut_path is not None and ctx.categories_controles_donut_path.exists():
            block.append(Spacer(1, 1 * mm))
            block.append(_mk_centered_image(ctx.categories_controles_donut_path, ctx.ref_pie_w))

    if block:
        ctx.builder.add_keep_together_block(block)
    elif ctx.show_placeholder:
        ctx.builder.add_keep_together_block(
            [
                Paragraph(
                    "Aucune donnée de résultat disponible.",
                    ctx.builder.styles["BodyText"],
                )
            ]
        )


def render_sec3(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec3", ctx.section_title["sec3"])
    ctx.builder.add_paragraph(
        f"Sur la période : {ctx.nb_pej} procédure(s) d'enquête judiciaire (PEJ), "
        f"{ctx.nb_pa} procédure(s) administrative(s) (PA), {ctx.nb_pve} procès-verbal(aux) électronique(s) (PVe).",
    )
    pve_dom = _load_csv_opt(ctx.out_dir, "pve_global_par_domaine.csv")
    pej_dom = _load_csv_opt(ctx.out_dir, "pej_global_par_domaine.csv")
    pa_dom = _load_csv_opt(ctx.out_dir, "pa_global_par_domaine.csv")

    domain_map: dict[str, dict[str, int]] = {}

    def _add_counts(df: pd.DataFrame | None, count_col: str, proc_key: str) -> None:
        if df is None or df.empty:
            return
        d_col = next((c for c in df.columns if "dom" in c.lower()), df.columns[0])
        c_col = next((c for c in df.columns if c.lower() in (count_col.lower(), "nb", "total")), df.columns[-1])
        for _, r in df.iterrows():
            d_name = str(r[d_col]).strip()
            if not d_name or d_name.lower() in ("nan", "none", ""):
                continue
            if d_name not in domain_map:
                domain_map[d_name] = {"pve": 0, "pej": 0, "pa": 0}
            try:
                domain_map[d_name][proc_key] += int(r[c_col])
            except (ValueError, TypeError):
                pass

    _add_counts(pve_dom, "nb_pve", "pve")
    _add_counts(pej_dom, "nb_pej", "pej")
    _add_counts(pa_dom, "nb_pa", "pa")

    if domain_map:
        hdr = ["Domaine d'activité", "PVe", "PEJ", "PA", "Total"]
        tbl_rows = [hdr]
        sorted_domains = sorted(
            domain_map.items(),
            key=lambda item: item[1]["pve"] + item[1]["pej"] + item[1]["pa"],
            reverse=True,
        )
        tot_pve, tot_pej, tot_pa = 0, 0, 0
        for d_name, counts in sorted_domains:
            pv, pj, pa = counts["pve"], counts["pej"], counts["pa"]
            tot = pv + pj + pa
            if tot > 0:
                tot_pve += pv
                tot_pej += pj
                tot_pa += pa
                tbl_rows.append([d_name[:45], str(pv), str(pj), str(pa), str(tot)])

        tot_global = tot_pve + tot_pej + tot_pa
        if tot_global > 0:
            tbl_rows.append(["Total global", str(tot_pve), str(tot_pej), str(tot_pa), str(tot_global)])
            ctx.builder.add_table(
                tbl_rows,
                caption="Synthèse des procédures par domaine d'activité",
                col_widths=[ctx.avail_w * 0.44, ctx.avail_w * 0.14, ctx.avail_w * 0.14, ctx.avail_w * 0.14, ctx.avail_w * 0.14],
                col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"],
            )

    show_cat_inf = is_block_enabled(ctx.presentation_cfg, "sec3.show_categories_infractions", False)
    if show_cat_inf and ctx.categories_infractions_df is not None and not ctx.categories_infractions_df.empty:
        df_cat = ctx.categories_infractions_df
        hdr = ["Catégorie", "PVe", "PEJ", "Total", "Part %"]
        tbl_inf = [hdr]
        tot_pv, tot_pj, tot_all = 0, 0, 0
        for _, r in df_cat.iterrows():
            pv = int(r.get("nb_pve", 0))
            pj = int(r.get("nb_pej", 0))
            tot = int(r.get("total", 0))
            pct = r.get("pct", 0.0)
            tot_pv += pv
            tot_pj += pj
            tot_all += tot
            tbl_inf.append([str(r.get("libelle", r.get("categorie", ""))), str(pv), str(pj), str(tot), f"{pct} %"])
        tbl_inf.append(["Total", str(tot_pv), str(tot_pj), str(tot_all), "100 %"])
        
        cw = [ctx.avail_w * 0.40, ctx.avail_w * 0.15, ctx.avail_w * 0.15, ctx.avail_w * 0.15, ctx.avail_w * 0.15]
        ca = ["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"]
        
        if ctx.categories_infractions_donut_path is not None and ctx.categories_infractions_donut_path.exists():
            ctx.builder.add_table_and_image_keep_together(
                tbl_inf,
                table_caption=pdf_metric_caption("Répartition des infractions par catégorie", "proc"),
                col_widths=cw,
                col_aligns=ca,
                image_path=ctx.categories_infractions_donut_path,
                image_width_ratio=ctx.ref_pie_w,
            )
        else:
            ctx.builder.add_table(
                tbl_inf,
                caption=pdf_metric_caption("Répartition des infractions par catégorie", "proc"),
                col_widths=cw,
                col_aligns=ca,
            )
        ctx.builder.add_spacer(3)

# 3.1 PVe
def render_sec31(ctx: PdfContext) -> None:
    ctx.builder.add_section(
        "sec31",
        ctx.section_title["sec31"],
        level=2,
        toc_level=1,
    )
    pve_natinf = _load_csv_opt(ctx.out_dir, "pve_global_par_natinf.csv")
    pve_natinf = _sort_desc(pve_natinf, ["nb"])

    if (
        pve_natinf is not None
        and not pve_natinf.empty
        and is_block_enabled(ctx.presentation_cfg, "sec31.show_table", True)
    ):
        col_widths = [ctx.avail_w * 0.46, ctx.avail_w * 0.36, ctx.avail_w * 0.18]
        natinf_label_w = col_widths[0]
        theme_label_w = col_widths[1]
        tbl = [["Nature d'infraction (NATINF)", "Thème SNC", "Nombre PVe"]]
        for _, row in pve_natinf.head(15).iterrows():
            libelle = row.get("libelle_natinf") or row.get("LIBELLE_NATINF") or ""
            code = str(row.get("numero_natinf") or row.get("natinf") or "").strip()
            if libelle:
                nature = f"{code} – {libelle}" if code else libelle
            else:
                nature = code or "-"
            theme_val = str(row.get("theme_snc") or row.get("THEME_SNC") or row.get("theme") or "Infractions hors périmètre SNC").strip()
            if theme_val in ["", "Hors thème", "Non Classé / Hors SNC", "nan", "None"]:
                theme_val = "Infractions hors périmètre SNC"
            tbl.append(
                [
                    truncate_text_to_width(str(nature), natinf_label_w),
                    truncate_text_to_width(theme_val, theme_label_w),
                    str(int(row["nb"])),
                ]
            )
        ctx.builder.add_table(
            tbl,
            caption="Analyse des NATINF relevées (PVe)",
            col_widths=col_widths,
            col_aligns=["LEFT", "LEFT", "RIGHT"],
        )
    elif ctx.show_placeholder:
        ctx.builder.add_paragraph("Aucune infraction PVe sur la période.")

    pve_detail = _load_csv_opt(ctx.out_dir, "pve_detail.csv")
    if (
        is_block_enabled(ctx.presentation_cfg, "sec31.show_detail_table", True)
        and pve_detail is not None
        and not pve_detail.empty
    ):
        hdr_pve = ["Numéro", "Date", "Commune", "Nature d'infraction"]
        tbl_det = [hdr_pve]
        pve_det_show, pve_det_total = slice_proc_detail_for_pdf(pve_detail, ctx.presentation_cfg, "sec31")
        pve_det_cap = get_block_int(ctx.presentation_cfg, "sec31.max_detail_rows", default=0)
        for _, r in pve_det_show.iterrows():
            tbl_det.append([
                str(r.get("numero", "")),
                str(r.get("date", "")),
                str(r.get("commune", "")),
                wrap_plain_text_for_pdf_paragraph(r.get("thematique", "")),
            ])
        cap_pve = format_proc_detail_caption(
            "Détail des procès-verbaux électroniques",
            shown=len(pve_det_show),
            total=pve_det_total,
            cap=pve_det_cap,
        )
        ctx.builder.add_table(
            tbl_det,
            caption=cap_pve,
            col_widths=[ctx.avail_w * 0.16, ctx.avail_w * 0.14, ctx.avail_w * 0.25, ctx.avail_w * 0.45],
            col_aligns=["LEFT"] * 4,
        )

def render_sec32(ctx: PdfContext) -> None:
    ctx.builder.add_section(
        "sec32",
        ctx.section_title["sec32"],
        level=2,
        toc_level=1,
    )
    pej_dom= _load_csv_opt(ctx.out_dir, "pej_global_par_domaine.csv")
    pej_dom= _sort_desc(pej_dom, ["nb_pej"])

    pej_top = _load_csv_opt(ctx.out_dir, "pej_global_par_natinf.csv")
    pej_top = _sort_desc(pej_top, ["nb"])
    if (
        pej_top is not None
        and not pej_top.empty
        and is_block_enabled(ctx.presentation_cfg, "sec32.show_top_infractions", True)
    ):
        from core.common.chargeurs_donnees import load_natinf_ref
        natinf_ref = load_natinf_ref(_ROOT)
        top_df = pej_top.copy()
        if "numero_natinf" not in top_df.columns:
            top_df["numero_natinf"] = top_df["natinf"].astype(str).str.extract(r"(\d+)", expand=False)
        if not natinf_ref.empty and "libelle_natinf" not in top_df.columns:
            top_df = top_df.merge(natinf_ref, on="numero_natinf", how="left")

        col_widths = [ctx.avail_w * 0.85, ctx.avail_w * 0.15]
        natinf_label_w = col_widths[0]
        tbl = [["Nature d'infraction (NATINF)", "Nombre PEJ"]]
        for _, row in top_df.head(15).iterrows():
            libelle = row.get("libelle_natinf") or row.get("LIBELLE_NATINF") or ""
            code = str(row.get("numero_natinf") or row.get("natinf") or "").strip()
            if libelle:
                nature = f"{code} – {libelle}" if code else libelle
            else:
                nature = code or "-"
            tbl.append(
                [
                    truncate_text_to_width(str(nature), natinf_label_w),
                    str(int(row["nb"])),
                ]
            )
        ctx.builder.add_table(
            tbl,
            caption="Analyse des NATINF relevées (PEJ)",
            col_widths=col_widths,
            col_aligns=["LEFT", "RIGHT"],
        )

    if (
        pej_dom is not None
        and not pej_dom.empty
        and is_block_enabled(ctx.presentation_cfg, "sec32.show_table", True)
    ):
        tbl = [["Domaine", "Nombre PEJ"]]
        for _, row in pej_dom.head(15).iterrows():
            tbl.append([str(row["domaine"]), str(int(row["nb_pej"]))])
        ctx.builder.add_table(
            tbl,
            caption="PEJ par domaine",
            col_widths=[ctx.avail_w * 0.60, ctx.avail_w * 0.40],
            col_aligns=["LEFT", "RIGHT"],
        )
    elif ctx.show_placeholder:
        ctx.builder.add_paragraph("Aucune procédure d'enquête judiciaire sur la période.")

    pej_detail = _load_csv_opt(ctx.out_dir, "pej_detail.csv")
    if (
        is_block_enabled(ctx.presentation_cfg, "sec32.show_detail_table", True)
        and pej_detail is not None
        and not pej_detail.empty
    ):
        hdr_pej = ["Numéro", "Date", "Commune", "Thématique"]
        tbl_det = [hdr_pej]
        pej_det_show, pej_det_total = slice_proc_detail_for_pdf(pej_detail, ctx.presentation_cfg, "sec32")
        pej_det_cap = get_block_int(ctx.presentation_cfg, "sec32.max_detail_rows", default=0)
        for _, r in pej_det_show.iterrows():
            tbl_det.append([
                str(r.get("numero", "")),
                str(r.get("date", "")),
                str(r.get("commune", "")),
                wrap_plain_text_for_pdf_paragraph(r.get("thematique", "")),
            ])
            
        # --- Note d'information sur les non-localisés structurels ---
        nb_nd = sum(1 for c in pej_det_show["commune"] if str(c).strip() in ("n.d.", "", "nan", "None", "<NA>"))
        if nb_nd > 0:
            ctx.builder.append_pending_paragraph(
                f"<i>À noter : {nb_nd} procédures ci-dessous n'ont pas pu être géolocalisées et apparaissent avec la mention « n.d. » "
                "dans la colonne Commune. Cette absence s'explique majoritairement par un manque d'informations "
                "géographiques renseignées dans la base de données source (OSCEAN).</i>"
            )
        # -------------------------------------------------------------
        # -------------------------------------------------------------

        cap_pej = format_proc_detail_caption(
            "Détail des procédures d'enquête judiciaire",
            shown=len(pej_det_show),
            total=pej_det_total,
            cap=pej_det_cap,
        )
        ctx.builder.add_table(
            tbl_det,
            caption=cap_pej,
            col_widths=[ctx.avail_w * 0.16, ctx.avail_w * 0.14, ctx.avail_w * 0.25, ctx.avail_w * 0.45],
            col_aligns=["LEFT"] * 4,
        )

def render_sec33(ctx: PdfContext) -> None:
    ctx.builder.add_section(
        "sec33",
        ctx.section_title["sec33"],
        level=2,
        toc_level=1,
    )
    pa_dom = _load_csv_opt(ctx.out_dir, "pa_global_par_domaine.csv")
    pa_dom = _sort_desc(pa_dom, ["nb_pa"])
    if (
        pa_dom is not None
        and not pa_dom.empty
        and is_block_enabled(ctx.presentation_cfg, "sec33.show_table", True)
    ):
        tbl = [["Domaine", "Nombre PA"]]
        for _, row in pa_dom.head(15).iterrows():
            tbl.append([str(row["domaine"]), str(int(row["nb_pa"]))])
        ctx.builder.add_table(
            tbl,
            caption="PA par domaine",
            col_widths=[ctx.avail_w * 0.60, ctx.avail_w * 0.40],
            col_aligns=["LEFT", "RIGHT"],
        )
    elif ctx.show_placeholder:
        ctx.builder.add_paragraph("Aucune procédure administrative sur la période.")
    elif ctx.nb_pa > 0:
        ctx.builder.add_paragraph(
            "<i>Ventilation par domaine indisponible pour les procédures administratives "
            f"({ctx.nb_pa} procédure(s) sur la période). Vérifier la présence de la colonne DOMAINE "
            "dans les exports OSCEAN.</i>",
            style="BodySmall",
        )

    pa_detail = _load_csv_opt(ctx.out_dir, "pa_detail.csv")
    if (
        is_block_enabled(ctx.presentation_cfg, "sec33.show_detail_table", True)
        and pa_detail is not None
        and not pa_detail.empty
    ):
        hdr_pa = ["Numéro", "Date", "Commune", "Thématique"]
        tbl_det = [hdr_pa]
        pa_det_show, pa_det_total = slice_proc_detail_for_pdf(pa_detail, ctx.presentation_cfg, "sec33")
        pa_det_cap = get_block_int(ctx.presentation_cfg, "sec33.max_detail_rows", default=0)
        for _, r in pa_det_show.iterrows():
            tbl_det.append([
                str(r.get("numero", "")),
                str(r.get("date", "")),
                str(r.get("commune", "")),
                wrap_plain_text_for_pdf_paragraph(r.get("thematique", "")),
            ])
        cap_pa = format_proc_detail_caption(
            "Détail des procédures administratives",
            shown=len(pa_det_show),
            total=pa_det_total,
            cap=pa_det_cap,
        )
        ctx.builder.add_table(
            tbl_det,
            caption=cap_pa,
            col_widths=[ctx.avail_w * 0.16, ctx.avail_w * 0.14, ctx.avail_w * 0.25, ctx.avail_w * 0.45],
            col_aligns=["LEFT"] * 4,
        )


def render_sec4(ctx: PdfContext) -> None:
    # Gabarit resserré : viser une section 4 sur une page A4 (hors cas extrêmes).
    sec4_tbl_sp = 1.0
    sec4_img_sp = 0.8
    ctx.builder.add_section("sec4", ctx.section_title["sec4"], compact=True)
    ctx.builder.add_paragraph("<i>Note importante : Le décompte des effectifs selon le type d'usager suit des règles spécifiques qui sont détaillées dans la notice méthodologique.</i>")
    
    if is_section_enabled(ctx.presentation_cfg, "sec4", True) and (ctx.agg_usager is None or ctx.agg_usager.empty):
        if ctx.show_placeholder:
            ctx.builder.add_paragraph("Aucune donnée « type d’usagers » n’est disponible dans les points de contrôle OSCEAN pour la période.")
    elif is_section_enabled(ctx.presentation_cfg, "sec4", True):
        total_usagers = sum(int(row["nb"]) for _, row in ctx.agg_usager.iterrows())
        nb_multi = (
            int(ctx.usagers_resume["nb_localisations_multi_usagers"].iloc[0])
            if ctx.usagers_resume is not None and not ctx.usagers_resume.empty and "nb_localisations_multi_usagers" in ctx.usagers_resume.columns
            else 0
        )
        if is_block_enabled(ctx.presentation_cfg, "sec4.show_intro_text", True):
            ctx.builder.add_paragraph("Répartition des usagers contrôlés par type (chaque type d’usager est compté avec son effectif).")
        if is_block_enabled(ctx.presentation_cfg, "sec4.show_key_figures", True):
            ctx.builder.add_key_figures([
                (str(total_usagers), "Total effectifs usagers"),
                (str(nb_multi), "Fiches multi-usagers"),
            ], spacer_after_mm=2.0)
        
        if is_commentaires_auto_enabled(ctx.presentation_cfg):
            p_comm = build_comment_paragraph("sec4_usagers", ctx)
            if p_comm:
                ctx.builder.append_pending_paragraph(p_comm)

        if is_block_enabled(ctx.presentation_cfg, "sec4.show_table_usagers", True):
            tbl_u = [["Type d’usagers", "Opérations", "Localisations", "Taux loc."]]
            nbs_ug = [int(row["nb"]) for _, row in ctx.agg_usager.iterrows()]
            pct_ug = tab_counts_to_pct_strings(nbs_ug)
            for i, (_, row) in enumerate(ctx.agg_usager.iterrows()):
                nb_ops_val = row.get("nb_operations", 0)
                try:
                    nb_ops_str = str(int(nb_ops_val)) if pd.notna(nb_ops_val) else "0"
                except (ValueError, TypeError):
                    nb_ops_str = "0"
                tbl_u.append([str(row["type_usager"]), nb_ops_str, str(int(row["nb"])), pct_ug[i]])
            ctx.builder.add_table(tbl_u, caption="Usagers contrôlés par type", col_widths=[ctx.avail_w * 0.44, ctx.avail_w * 0.18, ctx.avail_w * 0.19, ctx.avail_w * 0.19], col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"], spacer_after_mm=sec4_tbl_sp)

        if is_block_enabled(ctx.presentation_cfg, "sec4.show_pie_usagers", True):
            pie_data = {str(r["type_usager"])[:40]: int(r["nb"]) for _, r in ctx.agg_usager.iterrows()}
            if pie_data:
                pie_path = chart_pie(pie_data, "Usagers contrôlés par type", ctx.tmp_dir, "pie_usagers.png", **_chart_pie_compact_legend_kw(len(pie_data), legend_fontsize=ctx.ref_pie_legend_fs, legend_ncol_max=ctx.legend_ncol_max), figure_scale=ctx.ref_pie_fs)
                ctx.builder.add_image(Path(pie_path), width_ratio=min(0.48, ctx.ref_pie_w), spacer_after_mm=sec4_img_sp)

        if is_block_enabled(ctx.presentation_cfg, "sec4.show_table_usagers_x_domaine", True) and ctx.cross_usager_dom is not None and not ctx.cross_usager_dom.empty:
            temp_cross = ctx.cross_usager_dom.copy()
            domain_cols = [c for c in temp_cross.columns if c not in ("type_usager", "total", "Total")]
            if "total" not in temp_cross.columns and domain_cols:
                temp_cross["total"] = temp_cross[domain_cols].sum(axis=1)
            if "total" in temp_cross.columns:
                temp_cross = temp_cross.sort_values(by="total", ascending=False, kind="stable")
            tbl_cross, overflow_html = build_usagers_x_domaine_pdf_rows(temp_cross, tables_layout=ctx.tables_layout)
            if tbl_cross:
                n_dom = len(tbl_cross[0]) - 1
                col_widths = usagers_x_domaine_col_widths(ctx.avail_w, n_dom, ctx.tables_layout)
                cap = pdf_metric_caption("Usagers × Domaine", "effectifs")
                if overflow_html:
                    cap = f"{cap}<br/><br/>{overflow_html}"
                ctx.builder.add_table(tbl_cross, caption=cap, col_widths=col_widths, col_aligns=["LEFT"] + ["RIGHT"] * n_dom, wide_headers=True, wide_header_layout=resolve_usagers_x_domaine_header_layout(ctx.tables_layout), wide_header_font_size=resolve_usagers_x_domaine_header_font_size(ctx.tables_layout), wide_header_max_lines=resolve_usagers_x_domaine_header_max_lines(ctx.tables_layout), keep_together=True, spacer_after_mm=sec4_tbl_sp)

def render_sec42(ctx: PdfContext) -> None:
    if not is_section_enabled(ctx.presentation_cfg, "sec42", True):
        return
    if not (is_block_enabled(ctx.presentation_cfg, "sec4.show_resultats_par_type_usager_chart", True) or is_block_enabled(ctx.presentation_cfg, "sec4.show_resultats_par_type_usager_table", True)):
        return
    if ctx.res_usager is None or ctx.res_usager.empty:
        ctx.builder.add_section("sec42", ctx.section_title["sec42"], level=2, toc_level=1)
        ctx.builder.add_paragraph("Aucun résultat de contrôle par type d'usager pour la période.")
        return

    sec4_bar_w = ctx.chart_bar_w * 0.86
    sec4_tbl_sp = 1.0
    sec4_img_sp = 0.8

    ctx.builder.add_section("sec42", ctx.section_title["sec42"], level=2, toc_level=1)
    df_ru = ctx.res_usager.copy()
    required_cols = {"type_usager", "Conforme", "Infraction", "Manquement"}
    if required_cols.issubset(set(df_ru.columns)):
        if "Total" not in df_ru.columns:
            df_ru["Total"] = (
                df_ru["Conforme"].fillna(0).astype(int)
                + df_ru["Infraction"].fillna(0).astype(int)
                + df_ru["Manquement"].fillna(0).astype(int)
                + (df_ru["Autre_resultat"].fillna(0).astype(int) if "Autre_resultat" in df_ru.columns else 0)
            )
        df_ru = df_ru.sort_values(by="Total", ascending=False, kind="stable").reset_index(drop=True)
        labels = [str(x) for x in df_ru["type_usager"].tolist()]
        series: dict[str, list[int]] = {
            "Conforme": [int(x) for x in df_ru["Conforme"].tolist()],
            "Infraction": [int(x) for x in df_ru["Infraction"].tolist()],
            "Manquement": [int(x) for x in df_ru["Manquement"].tolist()],
        }
        has_autre = "Autre_resultat" in df_ru.columns and int(df_ru["Autre_resultat"].sum()) > 0
        if has_autre:
            series["En attente"] = [int(x) for x in df_ru["Autre_resultat"].tolist()]

        if is_block_enabled(ctx.presentation_cfg, "sec4.show_resultats_par_type_usager_chart", True):
            bar_path = chart_bar_horizontal_stacked(labels, series, "Résultats des contrôles par type d'usager", "Contrôles", ctx.tmp_dir, "bar_resultats_par_type_usager_global.png", legend_fontsize=max(6.5, ctx.legend_fontsize - 0.5), legend_ncol_max=ctx.legend_ncol_max, figure_scale=max(0.88, float(ctx.figure_scale) * 0.88))
            ctx.builder.add_image(Path(bar_path), width_ratio=sec4_bar_w, spacer_after_mm=sec4_img_sp)

        total_global = float(
            df_ru["Conforme"].sum()
            + df_ru["Infraction"].sum()
            + df_ru["Manquement"].sum()
            + (df_ru["Autre_resultat"].sum() if "Autre_resultat" in df_ru.columns else 0)
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
                *(["En attente", "% en attente"] if has_autre else []),
                "Total",
                "% du total",
            ]
        ]
        for _, row in df_ru.iterrows():
            c = int(row.get("Conforme", 0))
            i = int(row.get("Infraction", 0))
            m = int(row.get("Manquement", 0))
            a = int(row.get("Autre_resultat", 0)) if has_autre else 0
            t = c + i + m + a
            if t > 0:
                parts = [c, i, m] + ([a] if has_autre else [])
                pct_row = int_percents_largest_remainder(parts)
                k = 0
                pc_c = f"{pct_row[k]} %"; k += 1
                pc_i = f"{pct_row[k]} %"; k += 1
                pc_m = f"{pct_row[k]} %"; k += 1
                pc_a = (f"{pct_row[k]} %" if has_autre else "")
            else:
                pc_c = pc_i = pc_m = "n.d."
                pc_a = ""

            row_cells = [
                _truncate_with_dash(str(row.get("type_usager", "")), 34),
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

        first_col_w = ctx.avail_w * 0.20
        n_other_cols = len(tbl_res[0]) - 1
        other_w = (ctx.avail_w - first_col_w) / float(max(1, n_other_cols))
        col_widths = [first_col_w] + [other_w] * n_other_cols
        if is_block_enabled(ctx.presentation_cfg, "sec4.show_resultats_par_type_usager_table", True):
            ctx.builder.add_table(tbl_res, caption="Résultats des contrôles par type d'usager", col_widths=col_widths, col_aligns=["LEFT"] + ["RIGHT"] * (len(tbl_res[0]) - 1), keep_together=True, header_font_size=7.5, wide_headers=False, spacer_after_mm=sec4_tbl_sp)

def _get_proc_summary(ctx: PdfContext):
    proc_precomputed = _load_csv_opt(ctx.out_dir, "procedures_global_par_type_usager.csv")
    if proc_precomputed is not None and "type_usager" in proc_precomputed.columns:
        return proc_precomputed
    proc_by_dom = _load_csv_opt(ctx.out_dir, "procedures_par_type_usager_domaine.csv")
    from core.common.pdf_shared_sections import summarize_procedures_par_type_usager
    return summarize_procedures_par_type_usager(proc_by_dom)

def render_sec43(ctx: PdfContext) -> None:
    if not is_section_enabled(ctx.presentation_cfg, "sec43", True) or not is_block_enabled(ctx.presentation_cfg, "sec4.show_table_pej_par_type_usager", True):
        return
    summary = _get_proc_summary(ctx)
    if summary is None or summary.empty or "nb_pej" not in summary.columns or int(summary["nb_pej"].fillna(0).sum()) <= 0:
        return
    tbl = [["Type d'usager", "Nombre PEJ"]]
    for _, row in summary.iterrows():
        nb = int(row.get("nb_pej", 0) or 0)
        if nb > 0:
            tbl.append([str(row["type_usager"]), str(nb)])
    if len(tbl) > 1:
        ctx.builder.add_section("sec43", ctx.section_title.get("sec43", "3.3. Procédures d'enquête judiciaire (PEJ) par type d'usager"), level=2, toc_level=1)
        ctx.builder.add_table(tbl, caption=pdf_metric_caption("PEJ par type d'usager", "proc"), col_widths=[ctx.avail_w * 0.62, ctx.avail_w * 0.38], col_aligns=["LEFT", "RIGHT"], keep_together=True, spacer_after_mm=1.0)

def render_sec44(ctx: PdfContext) -> None:
    if not is_section_enabled(ctx.presentation_cfg, "sec44", True) or not is_block_enabled(ctx.presentation_cfg, "sec4.show_table_pa_par_type_usager", True):
        return
    summary = _get_proc_summary(ctx)
    if summary is None or summary.empty or "nb_pa" not in summary.columns or int(summary["nb_pa"].fillna(0).sum()) <= 0:
        return
    tbl = [["Type d'usager", "Nombre PA"]]
    for _, row in summary.iterrows():
        nb = int(row.get("nb_pa", 0) or 0)
        if nb > 0:
            tbl.append([str(row["type_usager"]), str(nb)])
    if len(tbl) > 1:
        ctx.builder.add_section("sec44", ctx.section_title.get("sec44", "3.4. Procédures administratives (PA) par type d'usager"), level=2, toc_level=1)
        ctx.builder.add_table(tbl, caption=pdf_metric_caption("PA par type d'usager", "proc"), col_widths=[ctx.avail_w * 0.62, ctx.avail_w * 0.38], col_aligns=["LEFT", "RIGHT"], keep_together=True, spacer_after_mm=1.0)


def render_sec5map(ctx: PdfContext) -> None:
    ctx.builder.add_section(
            "sec5map",
            ctx.section_title["sec5map"],
            toc_level=0,
        )
    show_map_block = is_block_enabled(ctx.presentation_cfg, "sec5.show_map", True)
    show_map_fallback = is_block_enabled(ctx.presentation_cfg, "sec5.show_map_fallback_message", True)
    if not ctx.cartes:
        if is_section_enabled(ctx.presentation_cfg, "sec5map", True) and ctx.show_placeholder:
            ctx.builder.add_paragraph("<i>Cartographie désactivée pour ce bilan.</i>")
    elif is_section_enabled(ctx.presentation_cfg, "sec5map", True) and ctx.global_map_paths and show_map_block:
        echelle_val = getattr(ctx, "echelle", "departement")
        is_reg = echelle_val == "region" or str(getattr(ctx, "dept_name_typo", "")).lower().startswith("région")
        loc_str = "la région" if is_reg else "le département"
        ctx.builder.append_pending_paragraph(
            f"Répartition spatiale des contrôles et procédures sur {loc_str} "
            "(générateur cartographique).",
        )
        ctx.builder.add_maps(
            ctx.global_map_paths,
            layout=ctx.global_map_layout,
        )
    elif is_section_enabled(ctx.presentation_cfg, "sec5map", True) and show_map_fallback and ctx.show_placeholder:
        if has_cartography_catalog(ctx.profile):
            selected = list(ctx.profile.get("_cartes_selection") or [])
            expected = expected_map_filenames_for_selection(ctx.profile, selected)
        else:
            expected = expected_map_filenames(
                ctx.map_id, profile=ctx.profile, presentation_cfg=ctx.presentation_cfg
            )
        from core.chemins_projet import get_cartes_dir

        cartes_dir = get_cartes_dir()
        files_hint = ", ".join(f"<b>{n}</b>" for n in expected) or f"<b>carte_{ctx.map_id}.png</b>"
        ctx.builder.add_paragraph(
            f"<i>Carte(s) non disponible(s). Déposez {files_hint} dans "
            f"<b>{cartes_dir.name}</b> ({cartes_dir}) pour les intégrer au bilan.</i>"
        )

def render_sec6(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec6", ctx.section_title["sec6"])
    vent_mode = resolve_ventilation_mode_global(ctx.date_deb, ctx.date_fin)
    if str(ctx.dept_name_typo).lower().startswith("région"):
        perim_label = ctx.dept_name_typo
    else:
        perim_label = f"du département {ctx.dept_name_typo}"

    methodo = build_sec6_methodology_html(
        effective_cfg=ctx.presentation_cfg,
        context=build_sec6_methodology_context(
            period_str=f"du {ctx.date_deb.date():%d/%m/%Y} au {ctx.date_fin.date():%d/%m/%Y}",
            perimetre_name=perim_label,
            perimetre_code=str(ctx.dept_code),
            profile_label="Bilan global",
            profile_id=ctx.profile_id,
            diffusion=ctx.diffusion,
            nb_localisations=ctx.nb_localisations,
            nb_pej=ctx.nb_pej,
            nb_pa=ctx.nb_pa,
            nb_pve=ctx.nb_pve,
            ventilation_mode=vent_mode,
            show_usagers=is_section_enabled(ctx.presentation_cfg, "sec4", True),
        ),
    )
    if is_block_enabled(ctx.presentation_cfg, "sec6.show_methodology", True):
        ctx.builder.add_methodology(methodo)

    gloss_cfg = load_glossary_config(_ROOT)
    glossaire_rows = build_filtered_glossary_rows(
        gloss_cfg=gloss_cfg,
        nb_localisations=ctx.nb_localisations,
        nb_pej=ctx.nb_pej,
        nb_pa=ctx.nb_pa,
        nb_pve=ctx.nb_pve,
    )

    if is_block_enabled(ctx.presentation_cfg, "sec6.show_glossary", True) and glossaire_rows:
        ctx.builder.add_glossary(
            glossaire_rows,
            col_widths=[ctx.avail_w * 0.25, ctx.avail_w * 0.75],
            col_aligns=["LEFT", "LEFT"],
        )

    from core.common.chargeurs_donnees import get_source_files_metadata
    sources_meta = get_source_files_metadata(_ROOT)
    if sources_meta:
        ctx.builder.add_paragraph("<br/><b>Traçabilité et empreinte des données sources</b>", style="Heading3")
        headers = ["Fichier source", "Taille", "Dernière modification", "Signature"]
        rows = [headers]
        for src in sources_meta:
            rows.append([src["nom"], src["taille"], src["date"], src["empreinte"]])
        ctx.builder.add_table(
            rows,
            col_widths=[ctx.avail_w * 0.40, ctx.avail_w * 0.15, ctx.avail_w * 0.25, ctx.avail_w * 0.20],
            col_aligns=["LEFT", "CENTER", "CENTER", "CENTER"],
        )
