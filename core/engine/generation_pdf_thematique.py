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

"""Module d'orchestration de la génération des rapports PDF thématiques."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from core.chemins_projet import PROJECT_ROOT, get_carto_temp_dir, get_out_dir
from core.common.bilan_config import BilanConfig
from core.common.chargeurs_donnees import load_communes_noms
from core.common.chart_display_config import (
    clamp_uniform_pie_ratio,
    compute_pdf_ratios,
    load_chart_display_config,
    resolve_reference_pie_display,
)
from core.common.pdf_presentation_config import (
    apply_diffusion_pdf_suffix,
    build_title_lines_from_cfg,
    inject_sec4_subsections,
    is_block_enabled,
    is_section_enabled,
    normalize_dept_typography,
    resolve_charte_config,
    resolve_pdf_presentation_config,
    resolve_section_titles,
    resolve_sections_for_toc,
    resolve_tables_layout,
    resolve_title_page_config,
    should_show_placeholder,
)
from core.common.pdf_report_builder import PDFReportBuilder
from core.common.carte_helper import (
    expected_map_filenames,
    resolve_map_layout,
    resolve_profile_map_paths,
)
from core.common.cartographie_config import (
    expected_map_filenames_for_selection,
    has_cartography_catalog,
    resolve_selected_map_paths,
)
from core.common.pdf_shared_sections import (
    add_standard_cover_and_toc,
    add_standard_notice_methodology,
    build_filtered_glossary_rows,
    build_sec6_methodology_context,
    build_sec6_methodology_html,
    load_glossary_config,
)
from core.common.pdf_table_sort import prepare_pdf_results_sec23_sorting
from core.common.utilitaires_metier import (
    get_departements_pour_perimetre,
    resolve_code_subdir_suffix,
    zone_lecteur_counts_for_pdf_cell,
)
from core.engine.orchestration.loader import _deep_merge_dicts
from core.engine.sections_thematiques import render_thematic_profil_sections

_log = logging.getLogger(__name__)


class ThematicRenderContext:
    """Contexte d'exécution transmis au moteur de rendu des sections thématiques."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def get(self, key: str, default: Any = None) -> Any:
        return self.__dict__.get(key, default)

    def __getattr__(self, item: str) -> Any:
        return self.__dict__.get(item, None)

def _generate_pdf(
    results: dict,
    out_dir: Path,
    profile: dict,
    cfg: BilanConfig,
    options: dict,
    ventilation_mode: str = "globale",
) -> None:
    """Génère le PDF du bilan avec des sections modulaires."""
    profil_id = profile["id"]
    label = profile["label"]
    sources = profile.get("sources", {}) or {}
    dept_name = cfg.perimetre_name
    dept_name_typo = (
        normalize_dept_typography(dept_name)
        if cfg.echelle == "departement"
        else dept_name
    )
    period_str = f"du {cfg.date_deb.date():%d/%m/%Y} au {cfg.date_fin.date():%d/%m/%Y}"

    # Pour le bilan usager ciblé (mono-usager), nommage Bilan_{type_usager} et titres avec le libellé
    single_cfg = profile.get("_single_usager") or {}
    is_single_usager = bool(single_cfg.get("enabled"))
    single_label = str(single_cfg.get("label", "")).strip()
    export_prefix = profile.get("_export_prefix") or profil_id
    display_label = single_label if (is_single_usager and single_label) else label
    diffusion = str(options.get("diffusion", "externe")).strip().lower()
    gabarit_id = options.get("gabarit")
    resolved_presentation_cfg = resolve_pdf_presentation_config(
        PROJECT_ROOT,
        scope="thematique",
        profile_id=profil_id,
        diffusion=diffusion,
        gabarit_id=gabarit_id,
    )
    presentation_cfg = (
        resolved_presentation_cfg.get("effective", {})
        if isinstance(resolved_presentation_cfg, dict)
        else {}
    )
    if "presentation" in profile and isinstance(profile["presentation"], dict):
        presentation_cfg = _deep_merge_dicts(presentation_cfg, profile["presentation"])
    behavior_cfg = (
        resolved_presentation_cfg.get("behavior", {})
        if isinstance(resolved_presentation_cfg, dict)
        else {}
    )
    show_placeholder = should_show_placeholder(
        behavior_cfg if isinstance(behavior_cfg, dict) else None
    )

    prepare_pdf_results_sec23_sorting(results)

    # Alignement du nom de fichier PDF sur la règle de nommage du répertoire
    prefix = profile.get("_export_prefix")
    if not prefix:
        raw_out = profile.get("out_subdir")
        prefix = str(raw_out).strip() if raw_out else f"bilan_{profil_id}"
        
    code_norm = str(cfg.code).strip()
    if code_norm:
        base_name = f"{prefix}_{code_norm}"
    else:
        base_name = prefix

    pdf_path = apply_diffusion_pdf_suffix(
        out_dir / f"{base_name}.pdf",
        diffusion,
    )
    tables_layout = resolve_tables_layout(presentation_cfg)
    charte_cfg = resolve_charte_config(presentation_cfg)
    title_page_cfg = resolve_title_page_config(
        PROJECT_ROOT, scope="thematique", profile_id=profil_id
    )
    from core.engine.pdf_utils import get_region_name_for_footer
    footer_text = get_region_name_for_footer(cfg.echelle, cfg.code)
    
    builder = PDFReportBuilder(
        pdf_path=pdf_path,
        footer_line1=footer_text,
        header_title=f"Bilan thématique – {display_label}",
        title=f"Bilan thématique – {display_label}",
        author="Office français de la biodiversité",
        tables_layout=tables_layout,
        charte_config=charte_cfg,
        diffusion=diffusion,
        title_page_config=title_page_cfg,
    )
    avail_w = builder.avail_w
    tmp_dir = builder.tmp_dir
    chart_preset = options.get("chart_preset")
    chart_ratios = compute_pdf_ratios(load_chart_display_config(PROJECT_ROOT, preset=chart_preset))
    chart_ratio_base = float(chart_ratios.get("thematique_uniform_chart", chart_ratios["chart_base"]))
    pie_ratio_base = clamp_uniform_pie_ratio(
        chart_ratios,
        uniform_key="thematique_uniform_pie",
        min_key="thematique_uniform_pie_min_ratio",
        max_key="thematique_uniform_pie_max_ratio",
    )
    ref_pie = resolve_reference_pie_display(chart_ratios, pie_ratio_base)
    ref_pie_w = ref_pie["width_ratio"]
    ref_pie_fs = ref_pie["figure_scale"]
    ref_pie_legend_fs = ref_pie["legend_fontsize"]
    legend_fontsize = float(chart_ratios.get("legend_fontsize", 8.0))
    legend_ncol_max = int(chart_ratios.get("legend_ncol_max", 4.0))
    figure_scale = float(chart_ratios.get("figure_scale", 1.0))
    figure_scale_sec21 = figure_scale * float(
        chart_ratios.get("thematique_sec21_figure_scale_mult", 1.55)
    )
    legend_fontsize_sec21 = min(12.0, legend_fontsize + 1.25)

    # Correspondance code INSEE → nom de commune pour les tableaux PDF
    insee_to_nom = load_communes_noms(PROJECT_ROOT)

    def _nom_commune(code) -> str:
        return insee_to_nom.get(str(code).strip().zfill(5), str(code))

    # Compteurs
    nb_localisations = results.get("nb_localisations", 0)
    nb_pej = results.get("nb_pej", 0)
    nb_pa = results.get("nb_pa", 0)
    nb_pve = results.get("nb_pve", 0)
    show_coeur_hors_pdf = bool(results.get("_pdf_show_coeur_hors_coeur", True))
    zone_lecteur_4_zones_pdf = bool(results.get("_zone_lecteur_4_zones", False))

    def _zone_cell_for_pdf(raw: object) -> str:
        txt = str(raw or "n.d.")
        if zone_lecteur_4_zones_pdf:
            return zone_lecteur_counts_for_pdf_cell(txt)
        return txt

    tab_resultats = results.get("tab_resultats")
    is_type_usager = profile.get("analyses", {}).get("type_usager", False)
    is_procedures = profile["filter"]["type"] == "procedures"
    # single_cfg / is_single_usager / single_label déjà définis plus haut

    # Sommaire cible (numérotation imposée) — libellé 2.1 aligné sur la ventilation temporelle
    _ventilation_titre_sec21 = str(results.get("ventilation_temporelle_type", "") or "")
    _sec21_titre_defaut = (
        "2.1. Indicateurs hebdomadaires"
        if _ventilation_titre_sec21 == "hebdomadaire"
        else "2.1. Indicateurs mensuels"
    )
    section_defs = [
        ("sec1", "1. Chiffres clés"),
        ("sec2", "2. Contrôles et procédures"),
        ("sec21", _sec21_titre_defaut),
        ("sec22", "2.2. Répartition de l'activité par domaines (contrôles + PEJ)"),
        ("sec23", "2.3. Résultats des contrôles au titre de la police administrative"),
        ("sec4", "3. Activité par type d’usager"),
        ("sec3", "4. Procédures (PEJ, PA, PVe)"),
        ("sec31", "4.1 Procès-verbaux électroniques (PVe)"),
        ("sec32", "4.2 Procédures d’enquête judiciaire (PEJ)"),
        ("sec33", "4.3 Procédures administratives (PA)"),
        ("sec5", "5. Localisation cartographique"),
        ("sec6", "6. Annexes"),
    ]
    if profil_id == "agrainage":
        section_defs = [
            ("sec1", "1. Chiffres clés"),
            ("sec2", "2. Contrôles et procédures"),
            ("sec21", _sec21_titre_defaut),
            ("sec22", "2.2. Répartition de l'activité par domaines (contrôles + PEJ)"),
            ("sec23", "2.3. Résultats des contrôles"),
            ("sec22theme", "2.4. Analyse par zone"),
            ("sec22res", "2.5. Synthèse croisée par zone"),
            ("sec4", "3. Activité par type d’usager"),
            ("sec3", "4. Procédures (PEJ, PA, PVe)"),
            ("sec31", "4.1 Procès-verbaux électroniques (PVe)"),
            ("sec32", "4.2 Procédures d’enquête judiciaire (PEJ)"),
            ("sec33", "4.3 Procédures administratives (PA)"),
            ("sec5", "5. Localisation cartographique"),
            ("sec6", "6. Annexes"),
        ]
    section_defs = inject_sec4_subsections(section_defs)
    resolved_section_defs = resolve_section_titles(presentation_cfg, section_defs)
    sections = resolved_section_defs
    sections_toc = resolve_sections_for_toc(presentation_cfg, resolved_section_defs)
    section_title = {sid: title for sid, title in resolved_section_defs}

    if cfg.echelle == "region":
        import re
        insert_idx = len(sections_toc)
        for i, (sid, _) in enumerate(sections_toc):
            if sid in ("sec5", "sec6"):
                insert_idx = i
                break
        
        # Déterminer le numéro du chapitre à insérer
        num_chap = 5
        if insert_idx > 0:
            prev_title = sections_toc[insert_idx - 1][1]
            m_prev = re.match(r"^(\d+)\.", prev_title)
            if m_prev:
                num_chap = int(m_prev.group(1)) + 1

        secregion_title = f"{num_chap}. Détail comparatif par département"
        sections_toc.insert(insert_idx, ("secregion", secregion_title))
        section_title["secregion"] = secregion_title

        # Renuméroter les chapitres suivants
        for idx in range(insert_idx + 1, len(sections_toc)):
            sid, title = sections_toc[idx]
            m_next = re.match(r"^(\d+)\.(.*)$", title)
            if m_next:
                num = int(m_next.group(1))
                new_title = f"{num + 1}.{m_next.group(2)}"
                sections_toc[idx] = (sid, new_title)
                section_title[sid] = new_title

    # Page de garde + sommaire
    # Préparer un libellé de thème sans doublon "Bilan "
    main_label = label
    if main_label.lower().startswith("bilan "):
        main_label = main_label[6:].strip()

    # Pour le profil "types_usager_cible", la page de garde doit afficher
    # les types d'usagers sélectionnés par l'utilisateur.
    if profil_id == "types_usager_cible":
        targets = (profile.get("filter", {}) or {}).get("type_usager_target") or []
        targets = [str(t).strip() for t in targets if str(t).strip()]
        if targets:
            if len(targets) == 1:
                main_label = targets[0]
            elif len(targets) == 2:
                main_label = f"{targets[0]} et {targets[1]}"
            else:
                main_label = ", ".join(targets[:-1]) + f" et {targets[-1]}"

    cover_profile_label = str(profile.get("title_label", main_label)).strip() or str(main_label)
    if profil_id == "types_usager_cible":
        cover_profile_label = str(main_label).strip()

    cover_title_lines, header_title_lines = build_title_lines_from_cfg(
        presentation_cfg,
        profile_label=cover_profile_label,
        perimetre_name_typo=dept_name_typo, echelle=cfg.echelle,
    )
    report_header = " — ".join(line.strip() for line in header_title_lines if line.strip())
    builder.header_title = report_header
    builder.doc.title = " — ".join(header_title_lines)

    add_standard_cover_and_toc(
        builder,
        project_root=PROJECT_ROOT,
        scope="thematique",
        profile_id=profil_id,
        cover_title_lines=cover_title_lines,
        period_str=f"Période : {period_str}",
        sections_toc=sections_toc,
        nb_pve=nb_pve,
    )

    # Notice méthodologique partagée avec le global.
    add_standard_notice_methodology(
        builder,
        period_sentence=f"Pour ce bilan, les extractions portent sur la période {period_str}.",
        effective_cfg=presentation_cfg,
        diffusion=diffusion,
    )


    ctx = ThematicRenderContext(
        builder=builder,
        presentation_cfg=presentation_cfg,
        section_title=section_title,
        profil_id=profil_id,
        cfg=cfg,
        options=options,
        ventilation_mode=ventilation_mode,
        profile=profile,
        sources=sources,
        diffusion=diffusion,
        is_single_usager=is_single_usager,
        single_label=single_label,
        dept_name=dept_name,
        dept_name_typo=dept_name_typo,
        period_str=period_str,
        tmp_dir=tmp_dir,
        sections_toc=sections_toc,
        tables_layout=tables_layout,
        ref_pie_w=ref_pie_w,
        ref_pie_fs=ref_pie_fs,
        ref_pie_legend_fs=ref_pie_legend_fs,
        figure_scale=figure_scale,
        figure_scale_sec21=figure_scale_sec21,
        legend_fontsize_sec21=legend_fontsize_sec21,
        legend_ncol_max=legend_ncol_max,
        avail_w=avail_w,
        show_placeholder=show_placeholder,
        is_type_usager=is_type_usager,
        is_procedures=is_procedures,
        _nom_commune=_nom_commune,
        chart_ratio_base=chart_ratio_base,
        out_dir=out_dir,
        legend_fontsize=legend_fontsize,
    )

    def _render_profil_sections(curr_results, title_suffix=""):
        render_thematic_profil_sections(ctx, curr_results, title_suffix)

    restrict_geo_val = str(profile.get("restrict_geo") or "").strip().lower()
    if restrict_geo_val == "pnf":
        _render_profil_sections(results, " (Total PNF)")
        if "results_21" in results:
            _render_profil_sections(results["results_21"], " (Côte-d'Or)")
        if "results_52" in results:
            _render_profil_sections(results["results_52"], " (Haute-Marne)")
    else:
        _render_profil_sections(results, "")


    # ── DETAIL REGIONAL PAR DEPARTEMENT ──
    if cfg.echelle == "region":
        from core.engine.sections_region import render_sec_region_detail
        from core.engine.pdf_context import PdfContext
        ctx_region = PdfContext(
            builder=builder,
            profile=profile,
            presentation_cfg=presentation_cfg,
            behavior_cfg=behavior_cfg,
            show_placeholder=show_placeholder,
            date_deb=cfg.date_deb,
            date_fin=cfg.date_fin,
            dept_code=cfg.code,
            dept_name_typo=dept_name_typo,
            diffusion=diffusion,
            ventilation_mode=ventilation_mode,
            out_dir=out_dir,
            avail_w=avail_w,
            tmp_dir=tmp_dir,
            chart_bar_w=chart_ratio_base,
            legend_fontsize=legend_fontsize,
            legend_ncol_max=legend_ncol_max,
            figure_scale=figure_scale,
            ref_pie_w=ref_pie_w,
            ref_pie_fs=ref_pie_fs,
            ref_pie_legend_fs=ref_pie_legend_fs,
            split_by_row=bool(tables_layout.get("split_by_row")),
            tables_layout=tables_layout,
            section_title={"secregion": section_title["secregion"]},
            nb_localisations=nb_localisations,
            nb_ops=results.get("nb_operations_controle", 0),
            nb_pej=nb_pej,
            nb_pa=nb_pa,
            nb_pve=nb_pve,
            tab_resultats=tab_resultats,
            tab_resultats_controles=results.get("tab_resultats_controles"),
            agg_domaine=results.get("agg_domaine"),
            agg_theme=results.get("agg_theme"),
            agg_usager=results.get("agg_usager"),
            res_usager=results.get("res_usager"),
            cross_usager_dom=results.get("cross_usager_dom"),
            usagers_resume=results.get("usagers_resume"),
            cartes=options.get("cartes", False),
            global_map_paths=[],
            global_map_layout="vertical",
            map_captions=[],
            map_id=profil_id,
        )
        render_sec_region_detail(ctx_region)

    if builder._pending_section is not None:
        builder.story.extend(builder._pending_section)
        builder._pending_section = None

    # ── CARTOGRAPHIE ──
    builder.add_section("sec5", section_title["sec5"], start_on_new_page=is_block_enabled(presentation_cfg, "sec5.start_on_new_page", False))
    if options.get("cartes", False):
        map_id = profile.get("_map_id") or profil_id
        
        if cfg.echelle == "region":
            from core.common.utilitaires_metier import get_departements_pour_perimetre
            from core.chemins_projet import get_cartes_dir
            
            # Nom de base configuré ou par défaut
            carto_cfg = profile.get("cartographie", {})
            carto_files = carto_cfg.get("fichiers", [])
            
            base_map_name = None
            if carto_files:
                base_map_name = carto_files[0]
            else:
                if has_cartography_catalog(profile):
                    selected = profile.get("_cartes_selection") or options.get("cartes_profil") or []
                    expected = expected_map_filenames_for_selection(profile, selected)
                    if expected:
                        base_map_name = expected[0]
                        
            if not base_map_name:
                base_map_name = f"carte_{map_id}.png"
            
            # Dériver le nom régional et les noms départementaux
            stem = Path(base_map_name).stem
            ext = Path(base_map_name).suffix
            
            cartes_dir = get_cartes_dir()
            
            region_map_name = f"{stem}_region{ext}"
            region_map_path = out_dir / region_map_name
            if not region_map_path.exists():
                region_map_path = cartes_dir / region_map_name
                
            depts = get_departements_pour_perimetre("region", cfg.code)
            dept_map_paths = []
            expected_names = [region_map_name]
            
            for d in depts:
                d_map_name = f"{stem}_{d}{ext}"
                expected_names.append(d_map_name)
                d_map_path = out_dir / d_map_name
                if not d_map_path.exists():
                    d_map_path = cartes_dir / d_map_name
                if d_map_path.exists():
                    dept_map_paths.append((d, d_map_path))
            
            # Affichage de la carte régionale
            if region_map_path.exists() and is_block_enabled(presentation_cfg, "sec5.show_map", True):
                builder.add_paragraph("<b>Carte de synthèse à l'échelle régionale :</b>")
                builder.add_maps([region_map_path], layout="vertical")
                builder.add_spacer(10)
            elif show_placeholder:
                builder.add_paragraph(f"<i>Carte régionale non disponible ({region_map_name} manquante).</i>")
                
            # Affichage des cartes départementales
            if dept_map_paths and is_block_enabled(presentation_cfg, "sec5.show_map", True):
                builder.add_paragraph("<b>Cartes de détail par département :</b>")
                from core.common.utilitaires_metier import get_dept_name
                for d, path in dept_map_paths:
                    builder.add_paragraph(f"Focus départemental : {d} - {get_dept_name(d)}")
                    builder.add_maps([path], layout="vertical")
                    builder.add_spacer(10)
            
            # Si aucune carte n'est disponible
            if not region_map_path.exists() and not dept_map_paths and show_placeholder:
                files_hint = ", ".join(f"<b>{name}</b>" for name in expected_names)
                builder.add_paragraph(
                    f"<i>Cartes non disponibles. Déposez les fichiers {files_hint} dans le dossier "
                    f"des cartes pour les intégrer au bilan régional.</i>"
                )
        else:
            if has_cartography_catalog(profile):
                selected = list(profile.get("_cartes_selection") or [])
                from core.common.utilitaires_metier import resolve_carto_dept_code
                carto_dept = resolve_carto_dept_code(cfg.echelle, cfg.code)
                map_paths, map_captions = resolve_selected_map_paths(
                    profile, selected, carto_dept=carto_dept, target_dir=out_dir
                )
                map_layout = resolve_map_layout(profile=profile, presentation_cfg=presentation_cfg)
                if map_paths and is_block_enabled(presentation_cfg, "sec5.show_map", True):
                    builder.add_maps(map_paths, layout=map_layout)
                elif show_placeholder and is_block_enabled(presentation_cfg, "sec5.show_map_fallback_message", True):
                    expected = expected_map_filenames_for_selection(profile, selected)
                    files_hint = ", ".join(f"<b>{name}</b>" for name in expected)
                    if not files_hint:
                        files_hint = "les cartes sélectionnées"
                    builder.add_paragraph(
                        f"<i>Carte(s) non disponible(s). Déposez {files_hint} dans le dossier "
                        f"des cartes pour les intégrer au bilan.</i>"
                    )
            else:
                map_paths = resolve_profile_map_paths(
                    str(map_id),
                    profile=profile,
                    presentation_cfg=presentation_cfg,
                    target_dir=out_dir,
                )
                map_layout = resolve_map_layout(profile=profile, presentation_cfg=presentation_cfg)
                if map_paths and is_block_enabled(presentation_cfg, "sec5.show_map", True):
                    builder.add_maps(map_paths, layout=map_layout)
                elif show_placeholder and is_block_enabled(presentation_cfg, "sec5.show_map_fallback_message", True):
                    expected = expected_map_filenames(
                        str(map_id), profile=profile, presentation_cfg=presentation_cfg
                    )
                    files_hint = ", ".join(f"<b>{name}</b>" for name in expected) or f"<b>carte_{map_id}.png</b>"
                    builder.add_paragraph(
                        f"<i>Carte(s) non disponible(s). Déposez {files_hint} dans le dossier "
                        f"des cartes pour les intégrer au bilan.</i>"
                    )
    elif show_placeholder:
        builder.add_paragraph("<i>Cartographie désactivée pour ce bilan.</i>")

    if builder._pending_section is not None:
        builder.story.extend(builder._pending_section)
        builder._pending_section = None

    # ── ANNEXES ──
    builder.add_section("sec6", section_title["sec6"], start_on_new_page=is_block_enabled(presentation_cfg, "sec6.start_on_new_page", False))
    zone_ctrl_annex = results.get("zone_ctrl")
    has_zone_table = zone_ctrl_annex is not None and not zone_ctrl_annex.empty
    has_pnf = bool(options.get("pnf", False)) and results.get("agg_pnf") is not None
    has_tub = bool(options.get("tub", False)) and has_zone_table
    is_pnf_profile = str(profil_id).strip().lower() == "pnf"
    show_usagers_sec = is_type_usager or is_section_enabled(presentation_cfg, "sec4", False)
    methodo = build_sec6_methodology_html(
        effective_cfg=presentation_cfg,
        context=build_sec6_methodology_context(
            period_str=period_str,
            perimetre_name=dept_name,
            perimetre_code=str(cfg.code),
            profile_label=display_label,
            profile_id=profil_id,
            diffusion=diffusion,
            nb_localisations=nb_localisations,
            nb_pej=nb_pej,
            nb_pa=nb_pa,
            nb_pve=nb_pve,
            source_point_ctrl=bool(sources.get("point_ctrl", True)),
            source_pej=bool(sources.get("pej", True)),
            source_pa=bool(sources.get("pa", True)),
            source_pve=bool(sources.get("pve", True)),
            ventilation_mode=str(results.get("ventilation_temporelle_type") or ""),
            has_pnf=has_pnf,
            has_tub=has_tub,
            is_pnf_profile=is_pnf_profile,
            show_usagers=show_usagers_sec,
        ),
    )

    if is_block_enabled(presentation_cfg, "sec6.show_methodology", True):
        builder.add_methodology(methodo)

    # Glossaire dynamique basé sur une configuration YAML exhaustive,
    # filtrée pour ne conserver que les abréviations réellement utiles
    # au PDF courant.
    gloss_cfg = load_glossary_config(PROJECT_ROOT)
    rows = build_filtered_glossary_rows(
        gloss_cfg=gloss_cfg,
        nb_localisations=nb_localisations,
        nb_pej=nb_pej,
        nb_pa=nb_pa,
        nb_pve=nb_pve,
        include_pnf=results.get("agg_pnf") is not None,
        include_tub=bool(options.get("tub", False)),
    )

    if is_block_enabled(presentation_cfg, "sec6.show_glossary", True) and rows:
        builder.add_glossary(rows)

    builder.build()




def _roman(n: int) -> str:
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    result = ""
    for val, numeral in vals:
        while n >= val:
            result += numeral
            n -= val
    return result



generate_thematic_pdf_report = _generate_pdf
