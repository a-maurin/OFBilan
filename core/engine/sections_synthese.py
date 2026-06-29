"""Fonctions de rendu des sections pour le profil synthèse globale."""

from pathlib import Path
import pandas as pd
from reportlab.platypus import Spacer, Paragraph

from ofbilan.engine.pdf_context import PdfContext
from ofbilan.common.pdf_presentation_config import is_section_enabled, is_block_enabled
from ofbilan.common.pdf_table_sort import (
    PDF_LABEL_CTRL_LOCATIONS,
    PDF_LABEL_CTRL_LOCATIONS_SHORT,
    PDF_LABEL_NON_CONFORME_LOCATIONS,
    PDF_LABEL_PEJ_COUNT,
    pdf_metric_caption,
    sort_dataframe_desc as _sort_desc,
)
from ofbilan.common.percent_format import format_pct_int_from_rate
from ofbilan.engine.pdf_utils import (
    nb_non_conformes_brut,
    truncate_with_dash,
    pct_table_cell as _pct_table_cell,
    truncate_with_dash as _truncate_with_dash,
)
from ofbilan.common.pdf_utils import truncate_text_to_width
from ofbilan.common.rendus_graphiques import (
    chart_bar_stacked, chart_line_evolution, chart_pie, chart_stackplot_resultats_domaine,
    chart_bar_horizontal_stacked
)
from ofbilan.common.utilitaires_metier import _load_csv_opt
from ofbilan.engine.generation_pdf_synthese import (
    _nb_non_conformes_brut, _build_synthese_key_figure_rows, _rollup_small_categories,
    _wrap_table_label, _resultats_controles_pie_data, _pie_data_controles_par_type_usager,
    _display_type_usager, _chart_pie_compact_legend_kw, _format_pve_natinf_label,
    _build_pve_natinf_table_rows, _KEY_FIGURES_GRAIN_NOTE, _SEC3_1_TABLE_NOTE,
    _build_rows_resultats_controles_pdf, _build_usager_theme_table_rows
)
from xml.sax.saxutils import escape
from ofbilan.common.pdf_shared_sections import (
    build_sec6_methodology_html,
    build_sec6_methodology_context,
    load_glossary_config,
    build_filtered_glossary_rows,
)

_ROOT = Path(__file__).resolve().parents[2]

def render_sec1(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec1", "1. Chiffres clés")
    nb_nc = _nb_non_conformes_brut(ctx.tab_resultats) if ctx.nb_localisations > 0 else 0
    kf_rows = _build_synthese_key_figure_rows(
        nb_effectifs=ctx.nb_effectifs,
        nb_operations_controle=ctx.nb_ops,
        nb_localisations=ctx.nb_localisations,
        nb_nc=nb_nc,
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
        sum_cols=["nb_localisations", "nb_pej_hors_controle", "nb_total"],
    )
    act_theme_total = (
        int(ctx.act_theme["nb_total"].astype(float).sum())
        if ctx.act_theme is not None and not ctx.act_theme.empty
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
                    str(int(row.get("nb_localisations", 0))),
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
    if ctx.tab_resultats_controles is not None and not ctx.tab_resultats_controles.empty:
        tbl_pdf = _build_rows_resultats_controles_pdf(ctx.tab_resultats_controles)
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
    if ctx.act_proc is not None and not ctx.act_proc.empty:
        tbl = [["Thème", "PEJ", "PA"]]
        for _, row in ctx.act_proc.head(25).iterrows():
            tbl.append(
                [
                    _wrap_table_label(row["theme"]),
                    str(int(row.get("nb_pej", 0))),
                    str(int(row.get("nb_pa", 0))),
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


def render_sec4_usagers(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec4", "3. Activité de police par type d'usager")
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

    act_par_type = _sort_desc(_load_csv_opt(ctx.out_dir, "synthese_activite_par_type_usager.csv"), ["nb_total"])
    act_ut = _sort_desc(_load_csv_opt(ctx.out_dir, "synthese_activite_usager_theme.csv"), ["nb_total"])
    
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
        "sec4_1",
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
        "sec4_2",
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



def render_sec43(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec43", "3.3. Activité procédurale par type d'usager", level=2, toc_level=1)
    proc_ut = _load_csv_opt(ctx.out_dir, "synthese_procedures_usager_theme.csv")
    if proc_ut is not None and not proc_ut.empty:
        types = proc_ut["type_usager"].dropna().astype(str).unique().tolist()
        first = True
        for tu in types:
            sub = proc_ut[proc_ut["type_usager"].astype(str) == tu].copy()
            sub = sub.sort_values(["nb_pej", "nb_pa"], ascending=False, kind="stable")
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
                        str(int(row.get("nb_pej", 0))),
                        str(int(row.get("nb_pa", 0))),
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


def render_sec3_procedures(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec3", "4. Procédures (PEJ, PA, PVe)")
    ctx.builder.add_paragraph(
        f"Sur la période : {ctx.nb_pej} procédure(s) d'enquête judiciaire (PEJ), "
        f"{ctx.nb_pa} procédure(s) administrative(s) (PA), {ctx.nb_pve} procès-verbal(aux) électronique(s) (PVe)."
    )

    ctx.builder.add_section("sec32", "4.1. Procédures d'enquête judiciaire (PEJ)", level=2, toc_level=1)
    pej_top = _load_csv_opt(ctx.out_dir, "pej_global_par_natinf.csv")
    if pej_top is not None and not pej_top.empty:
        pej_top = _sort_desc(pej_top, ["nb"])
        from ofbilan.common.chargeurs_donnees import load_natinf_ref
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

    pej_theme = _load_csv_opt(ctx.out_dir, "synthese_procedures_par_theme.csv")
    if pej_theme is not None and not pej_theme.empty:
        pej_theme = _sort_desc(pej_theme, ["nb_pej"])
        tbl = [["Thème", "Nombre PEJ"]]
        has_data = False
        for _, row in pej_theme.head(15).iterrows():
            if int(row.get("nb_pej", 0)) > 0:
                has_data = True
                tbl.append([str(row["theme"]), str(int(row["nb_pej"]))])
        if has_data:
            ctx.builder.add_table(
                tbl,
                caption="PEJ par thème",
                col_widths=[ctx.avail_w * 0.60, ctx.avail_w * 0.40],
                col_aligns=["LEFT", "RIGHT"],
            )
    if ctx.nb_pej == 0:
        ctx.builder.add_paragraph("Aucune procédure d'enquête judiciaire sur la période.")

    ctx.builder.add_section("sec33", "4.2. Procédures administratives (PA)", level=2, toc_level=1)
    if pej_theme is not None and not pej_theme.empty:
        pa_theme = _sort_desc(pej_theme, ["nb_pa"])
        tbl = [["Thème", "Nombre PA"]]
        has_data = False
        for _, row in pa_theme.head(15).iterrows():
            if int(row.get("nb_pa", 0)) > 0:
                has_data = True
                tbl.append([str(row["theme"]), str(int(row["nb_pa"]))])
        if has_data:
            ctx.builder.add_table(
                tbl,
                caption="PA par thème",
                col_widths=[ctx.avail_w * 0.60, ctx.avail_w * 0.40],
                col_aligns=["LEFT", "RIGHT"],
            )
    if ctx.nb_pa == 0:
        ctx.builder.add_paragraph("Aucune procédure administrative sur la période.")

    ctx.builder.add_section("sec31", "4.3. Procès-verbaux électroniques (PVe)", level=2, toc_level=1)
    ctx.builder.add_paragraph(
        "Les procès-verbaux électroniques (PVe) proviennent du fichier national OFB "
        "(<i>Stats_PVe_OFB</i>). Ils recensent des infractions constatées et intégrées sur la "
        f"période du {ctx.date_deb.date():%d/%m/%Y} au {ctx.date_fin.date():%d/%m/%Y} "
        "(date d'intégration <i>INF-DATE-INTG</i>). Ils ne sont pas rattachés aux fiches de "
        "contrôle OSCEAN ni ventilés par type d'usager : cette section les présente "
        "selon leur propre nomenclature (NATINF et classe d'infraction)."
    )
    pve_natinf = _sort_desc(_load_csv_opt(ctx.out_dir, "pve_global_par_natinf.csv"), ["nb"])
    pve_classe = _sort_desc(_load_csv_opt(ctx.out_dir, "synthese_pve_par_classe.csv"), ["nb"])

    if ctx.nb_pve > 0:
        if pve_natinf is not None and not pve_natinf.empty:
            natinf_label_w = ctx.avail_w * 0.72
            ctx.builder.add_table(
                _build_pve_natinf_table_rows(
                    pve_natinf,
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
    ctx.builder.add_section("sec5map", "5. Cartographie")
    if ctx.cartes:
        if ctx.global_map_paths:
            ctx.builder.add_maps(ctx.global_map_paths, layout=ctx.global_map_layout)
        elif ctx.show_placeholder:
            ctx.builder.add_paragraph("<i>Carte(s) non disponible(s).</i>")
    elif ctx.show_placeholder:
        ctx.builder.add_paragraph("<i>Cartographie désactivée pour ce bilan.</i>")

    # ── 6. Annexes ──


def render_sec6(ctx: PdfContext) -> None:
    ctx.builder.add_section("sec6", "6. Annexes")
    methodo = build_sec6_methodology_html(
        effective_cfg=ctx.presentation_cfg,
        context=build_sec6_methodology_context(
            period_str=f"du {ctx.date_deb.date():%d/%m/%Y} au {ctx.date_fin.date():%d/%m/%Y}",
            perimetre_name=f"de la {ctx.dept_name_typo}",
            perimetre_code=str(ctx.dept_code),
            profile_label=ctx.profile.get("label", "Synthèse PA / PJ"),
            profile_id=ctx.profile.get("id", "synthese_activite_PA_PJ"),
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



