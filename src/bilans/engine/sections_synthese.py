"""Fonctions de rendu des sections pour le profil synthèse globale."""

from pathlib import Path
import pandas as pd
from reportlab.platypus import Spacer, Paragraph

from bilans.engine.pdf_context import PdfContext
from bilans.common.pdf_presentation_config import is_section_enabled, is_block_enabled
from bilans.common.pdf_table_sort import (
    PDF_LABEL_CTRL_LOCATIONS,
    PDF_LABEL_CTRL_LOCATIONS_SHORT,
    PDF_LABEL_NON_CONFORME_LOCATIONS,
    PDF_LABEL_PEJ_COUNT,
)
from bilans.common.percent_format import format_pct_int_from_rate
from bilans.engine.pdf_utils import nb_non_conformes_brut, truncate_with_dash
from bilans.common.rendus_graphiques import (
    chart_bar_stacked, chart_line_evolution, chart_pie, chart_stackplot_resultats_domaine,
    chart_bar_horizontal_stacked
)
from bilans.common.utilitaires_metier import _load_csv_opt
from bilans.engine.generation_pdf_synthese import (
    _nb_non_conformes_brut, _build_synthese_key_figure_rows, _rollup_small_categories,
    _wrap_table_label, _resultats_controles_pie_data, _pie_data_controles_par_type_usager,
    _display_type_usager, _chart_pie_compact_legend_kw, _format_pve_natinf_label,
    _build_pve_natinf_table_rows, _KEY_FIGURES_GRAIN_NOTE, _SEC3_1_TABLE_NOTE
)
from bilans.common.pdf_blocks import _mk_centered_image, pdf_metric_caption, ofb_table
from xml.sax.saxutils import escape

def render_sec1(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec1", "1. Chiffres clés")
    nb_nc= _nb_non_conformes_brut(ctx.tab_resultats) if ctx.nb_localisations > 0 else 0
    kf_rows = _build_synthese_key_figure_rows(
        nb_effectifs=ctx.nb_effectifs,
        nb_operations_controle=ctx.nb_operations_controle,
        nb_localisations=ctx.nb_localisations,
        nb_nc=ctx.nb_nc,
        nb_pej=ctx.nb_pej,
        nb_pa=ctx.nb_pa,
        nb_pve=ctx.nb_pve,
    )
    ctx.builder.add_key_figures_rows(kf_rows)

    ctx.builder.add_section(
        "sec2",
        "2. Activité de police administrative et judiciaire",
        append_to_pending=True,
    )
    ctx.builder.append_pending_paragraph(_KEY_FIGURES_GRAIN_NOTE)
    ctx.builder.append_pending_callout_box(
        "Comme indiqué dans la notice méthodologique, le terme contrôle désigne ici "
        "exclusivement une mesure de police administrative.",
        title="Rappel",
        spacer_after_mm=1.5,
    )
    ctx.builder.append_pending_paragraph(
        "Sauf mention contraire, les tableaux de cette partie cumulent les localisations de "
        "contrôle (points de contrôle OSCEAN) et les procédures d'enquêtes judiciaires (PEJ) "
        "non rattachées à une fiche contrôle (i.e. saisines judiciaires hors opérations de "
        "contrôle)."
    )

    ctx.builder.add_section(
        "sec2_1",
        "2.1. Activité de police par thème du plan de contrôle",
        level=2,
        toc_level=1,
        append_to_pending=True,
    )
    act_theme_display = _rollup_small_categories(
        ctx.act_theme,
        label_col="theme",
        other_label="Autres thèmes de contrôle",
        value_col="nb_total",
        min_pct=0.01,
        sum_cols=["ctx.nb_localisations", "nb_pej_hors_controle", "nb_total"],
    )
    act_theme_total= (
        int(ctx.act_theme["nb_total"].astype(float).sum())
        if ctx.act_theme is not None and not ctx.act_theme.empty
        else 0
    )
    if act_theme_display is not None and not act_theme_display.empty:
        tbl = [["Thème", "Contrôles PA", "PEJ hors contrôle PA", "Total"]]
        for _, row in act_theme_display.iterrows():
            nb_row = int(row["nb_total"])
            pct = format_pct_int_from_rate(nb_row / ctx.act_theme_total) if ctx.act_theme_total > 0 else "n.d."
            tbl.append(
                [
                    _wrap_table_label(row["theme"]),
                    str(int(row.get("ctx.nb_localisations", 0))),
                    str(int(row.get("nb_pej_hors_controle", 0))),
                    f"{nb_row} ({pct})",
                ]
            )
        ctx.builder.add_table(
            tbl,
            caption="Activité de police par thème (contrôles + PEJ hors fiche contrôle)",
            col_widths=[ctx.avail_w * 0.44, ctx.avail_w * 0.18, ctx.avail_w * 0.18, ctx.avail_w * 0.20],
            col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"],
            keep_together=True,
        )
    elif ctx.show_placeholder:
        ctx.builder.append_pending_paragraph("Aucune donnée disponible pour l'activité par thème.")
        ctx.builder.add_keep_together_block([])

    ctx.builder.add_section(
        "sec2_2",
        "2.2. Résultat des contrôles au titre de la police administrative",
        level=2,
        toc_level=1,
    )
    if tab_res_ctrl is not None and not tab_res_ctrl.empty:
        tbl_pdf = _build_rows_resultats_controles_pdf(tab_res_ctrl)
        pie_data = _resultats_controles_pie_data(ctx.tab_resultats)
        pie_path = None
        if pie_data:
            pie_path = chart_pie(
                pie_data,
                "",
                ctx.tmp_dir,
                "pie_synthese_resultats_controles.png",
                figure_scale=ctx.ref_pie_fs,
                legend_fontsize=ctx.ref_pie_legend_fs,
            )
        ctx.builder.add_table_and_image_keep_together(
            tbl_pdf,
            table_caption="Résultats des contrôles",
            col_widths=[ctx.avail_w * 0.44, ctx.avail_w * 0.28, ctx.avail_w * 0.28],
            col_aligns=["LEFT", "RIGHT", "RIGHT"],
            image_path=Path(pie_path) if pie_path else None,
            image_width_ratio=ctx.ref_pie_w,
        )
    elif ctx.show_placeholder:
        ctx.builder.add_paragraph("Aucune donnée de résultat de contrôle sur la période.")

    ctx.builder.add_section("sec2_3", "2.3. Activité procédurale", level=2, toc_level=1)
    ctx.builder.append_pending_paragraph(
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
                    str(int(row.get("ctx.nb_pej", 0))),
                    str(int(row.get("ctx.nb_pa", 0))),
                ]
            )
        ctx.builder.add_table(
            tbl,
            caption=pdf_metric_caption("Procédures par thème", "proc"),
            col_widths=[ctx.avail_w * 0.52, ctx.avail_w * 0.24, ctx.avail_w * 0.24],
            col_aligns=["LEFT", "RIGHT", "RIGHT"],
        )
    elif ctx.show_placeholder:
        ctx.builder.append_pending_paragraph("Aucune procédure sur la période.")
        ctx.builder.add_keep_together_block([])

    # ── 3. Activité par type d'usager ──


def render_sec3(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec3", "3. Activité de police par type d'usager")
    ctx.builder.append_pending_paragraph(
        "⚠️ <i>Note importante : Le décompte des effectifs selon le type d'usager suit des règles spécifiques qui sont détaillées dans la notice méthodologique.</i>",
    )
    ctx.builder.add_spacer(2)
    ctx.builder.append_pending_paragraph(
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
            ctx.tmp_dir,
            "pie_synthese_controles_par_type_usager.png",
            legend_percent_only=True,
            figure_scale=ctx.ref_pie_fs,
            **_chart_pie_compact_legend_kw(
                len(pie_data),
                legend_fontsize=ctx.ref_pie_legend_fs,
            ),
        )
        ctx.builder.append_pending_image(
            Path(pie_path),
            width_ratio=ctx.ref_pie_w,
            spacer_after_mm=0.4,
        )

    ctx.builder.add_section(
        "sec3_1",
        "3.1. Thème de contrôle par type d'usager",
        level=2,
        toc_level=1,
    )
    col_w_ut = [
        ctx.avail_w * 0.36,
        ctx.avail_w * 0.14,
        ctx.avail_w * 0.14,
        ctx.avail_w * 0.14,
        ctx.avail_w * 0.22,
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
            ctx.builder.add_table(
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
        ctx.builder.add_paragraph(_SEC3_1_TABLE_NOTE)
    elif ctx.show_placeholder:
        ctx.builder.append_pending_paragraph("Aucune donnée type d'usager disponible.")
        ctx.builder.add_keep_together_block([])

    ctx.builder.add_section(
        "sec3_2",
        "3.2. Résultat des contrôles par type d'usager",
        level=2,
        toc_level=1,
    )
    if ctx.res_usager is not None and not ctx.res_usager.empty:
        labels = [_display_type_usager(x) for x in ctx.res_usager["type_usager"].tolist()]
        series: dict[str, list[int]] = {
            "Conforme": [int(x) for x in ctx.res_usager["Conforme"].tolist()],
            "Infraction": [int(x) for x in ctx.res_usager["Infraction"].tolist()],
            "Manquement": [int(x) for x in ctx.res_usager["Manquement"].tolist()],
        }
        if "Autre_resultat" in ctx.res_usager.columns and int(ctx.res_usager["Autre_resultat"].sum()) > 0:
            series["En attente"] = [int(x) for x in ctx.res_usager["Autre_resultat"].tolist()]
        bar_path = chart_bar_horizontal_stacked(
            labels,
            series,
            pdf_metric_caption("Résultats des contrôles par type d'usager", "effectifs"),
            "Effectifs",
            ctx.tmp_dir,
            "bar_synthese_resultats_usager.png",
            figure_scale=0.88,
        )
        ctx.builder.add_image(Path(bar_path), width_ratio=0.88, spacer_after_mm=1.0)

        has_autre = "Autre_resultat" in ctx.res_usager.columns and int(ctx.res_usager["Autre_resultat"].sum()) > 0
        total_global = float(
            ctx.res_usager["Conforme"].sum()
            + ctx.res_usager["Infraction"].sum()
            + ctx.res_usager["Manquement"].sum()
            + (ctx.res_usager["Autre_resultat"].sum() if has_autre else 0)
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
        for _, row in ctx.res_usager.iterrows():
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
        ctx.builder.add_table(
            tbl_res,
            caption=pdf_metric_caption("Résultats des contrôles par type d'usager", "effectifs"),
            keep_together=True,
        )
    elif ctx.show_placeholder:
        ctx.builder.add_paragraph("Aucun résultat par type d'usager.")



def render_sec33(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec3_3", "3.3. Activité procédurale par type d'usager", level=2, toc_level=1)
    if proc_ut is not None and not proc_ut.empty:
        types = proc_ut["type_usager"].dropna().astype(str).unique().tolist()
        first = True
        for tu in types:
            sub = proc_ut[proc_ut["type_usager"].astype(str) == tu].copy()
            sub = sub.sort_values(["ctx.nb_pej", "ctx.nb_pa"], ascending=False, kind="stable")
            if sub.empty:
                continue
            if not first:
                ctx.builder.add_spacer(1.5)
            first = False
            tbl = [["Thème", "PEJ", "PA"]]
            for _, row in sub.head(15).iterrows():
                tbl.append(
                    [
                        str(row["theme"])[:40],
                        str(int(row.get("ctx.nb_pej", 0))),
                        str(int(row.get("ctx.nb_pa", 0))),
                    ]
                )
            ctx.builder.add_table(
                tbl,
                caption=pdf_metric_caption(
                    f"Procédures par thème — {_display_type_usager(tu)}", "proc"
                ),
                col_widths=[ctx.avail_w * 0.52, ctx.avail_w * 0.24, ctx.avail_w * 0.24],
                col_aligns=["LEFT", "RIGHT", "RIGHT"],
                keep_together=True,
            )
    elif ctx.show_placeholder:
        ctx.builder.add_paragraph("Aucune procédure ventilée par type d'usager.")

    # ── 4. PVe (source OFB, hors périmètre type d'usager OSCEAN) ──


def render_sec4(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec4", "4. Procès-verbaux électroniques (PVe)")
    ctx.builder.add_paragraph(
        "Les procès-verbaux électroniques (PVe) proviennent du fichier national OFB "
        "(<i>Stats_PVe_OFB</i>). Ils recensent des infractions constatées et intégrées sur la "
        f"période du {ctx.date_deb.date():%d/%m/%Y} au {ctx.date_fin.date():%d/%m/%Y} "
        "(date d'intégration <i>INF-DATE-INTG</i>). Ils ne sont pas rattachés aux fiches de "
        "contrôle OSCEAN ni ventilés par type d'usager : cette section les présente "
        "selon leur propre nomenclature (NATINF et classe d'infraction)."
    )
    pve_natinf= _sort_desc(_load_csv_opt(ctx.out_dir, "pve_global_par_natinf.csv"), ["nb"])
    pve_classe = _sort_desc(_load_csv_opt(ctx.out_dir, "synthese_pve_par_classe.csv"), ["nb"])

    if ctx.nb_pve > 0:
        if ctx.pve_natinf is not None and not ctx.pve_natinf.empty:
            natinf_label_w = ctx.avail_w * 0.72
            ctx.builder.add_table(
                _build_pve_natinf_table_rows(
                    ctx.pve_natinf,
                    label_col_width_pt=natinf_label_w,
                ),
                caption=pdf_metric_caption("Principales natures d'infraction (NATINF)", "proc"),
                col_widths=[natinf_label_w, ctx.avail_w * 0.28],
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
            ctx.builder.add_table(
                tbl_cl,
                caption=pdf_metric_caption("PVe par classe d'infraction", "proc"),
                col_widths=[ctx.avail_w * 0.60, ctx.avail_w * 0.40],
                col_aligns=["LEFT", "RIGHT"],
                keep_together=True,
            )
    elif ctx.show_placeholder:
        ctx.builder.add_paragraph("Aucun procès-verbal électronique sur la période.")

    # ── 5. Cartographie ──


def render_sec5(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec5", "5. Cartographie")
    if ctx.cartes:
        map_id= str(ctx.profile.get("_map_id") or profil_id)
        map_paths = resolve_profile_map_paths(ctx.map_id, profile=ctx.profile, presentation_cfg=ctx.presentation_cfg)
        map_layout = resolve_map_layout(profile=ctx.profile, presentation_cfg=ctx.presentation_cfg)
        if map_paths:
            ctx.builder.add_maps(map_paths, layout=map_layout)
        elif ctx.show_placeholder:
            expected = expected_map_filenames(ctx.map_id, profile=ctx.profile, presentation_cfg=ctx.presentation_cfg)
            files_hint = ", ".join(f"<b>{n}</b>" for n in expected) or f"<b>carte_{ctx.map_id}.png</b>"
            ctx.builder.add_paragraph(
                f"<i>Carte(s) non disponible(s). Déposez {files_hint} dans le dossier des ctx.cartes.</i>"
            )
    elif ctx.show_placeholder:
        ctx.builder.add_paragraph("<i>Cartographie désactivée pour ce bilan.</i>")

    # ── 6. Annexes ──


def render_sec6(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec6", "6. Annexes")
    methodo = build_sec6_methodology_html(
        effective_cfg=ctx.presentation_cfg,
        context=build_sec6_methodology_context(
            period_str=f"du {ctx.date_deb.date():%d/%m/%Y} au {ctx.date_fin.date():%d/%m/%Y}",
            dept_name=f"de la {ctx.dept_name_typo}",
            dept_code=str(ctx.dept_code),
            profile_label=profile_label or "Synthèse PA / PJ",
            profile_id=profil_id,
            diffusion=ctx.diffusion,
            nb_localisations=ctx.nb_localisations,
            nb_pej=ctx.nb_pej,
            nb_pa=ctx.nb_pa,
            nb_pve=ctx.nb_pve,
            ventilation_mode="globale",
            show_usagers=is_section_enabled(ctx.presentation_cfg, "sec3", True),
        ),
    )
    ctx.builder.add_methodology(methodo)
    gloss_cfg = load_glossary_config(_ROOT)
    glossaire_rows = build_filtered_glossary_rows(
        gloss_cfg=gloss_cfg,
        nb_localisations=ctx.nb_localisations,
        nb_pej=ctx.nb_pej,
        nb_pa=ctx.nb_pa,
        nb_pve=ctx.nb_pve,
    )
    if glossaire_rows:
        ctx.builder.add_glossary(
            glossaire_rows,
            col_widths=[ctx.avail_w * 0.25, ctx.avail_w * 0.75],
            col_aligns=["LEFT", "LEFT"],
        )



