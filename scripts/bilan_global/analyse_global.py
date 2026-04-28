"""Bilan global — activité du service départemental (tous domaines/thèmes, PA, PEJ, PVe)."""
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# Bootstrap : exécution indépendante
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.paths import get_cartes_dir, get_out_dir
from scripts.common.loaders import (
    load_natinf_ref,
    load_pa,
    load_pej,
    load_point_ctrl,
    load_pve,
    ensure_insee_from_communes_shp,
)
from scripts.common.prompt_periode import ask_periode_dept
from scripts.common.utils import _load_csv_opt, serie_type_usager, agg_effectifs_usagers, agg_effectifs_usagers_par_domaine
from scripts.common.ofb_charte import Spinner
from scripts.common.pdf_report_builder import PDFReportBuilder
from scripts.common.pdf_presentation_config import (
    resolve_title_page_config,
    resolve_pdf_presentation_config,
    is_section_enabled,
    is_block_enabled,
    resolve_sections_for_toc,
    should_show_placeholder,
)
from scripts.common.chart_display_config import load_chart_display_config, compute_pdf_ratios
from scripts.common.charts import chart_pie, chart_bar_stacked, chart_line_evolution, chart_bar_horizontal_stacked
from scripts.common.percent_format import format_pct_int_from_rate, tab_counts_to_pct_strings, int_percents_largest_remainder


def _nb_non_conformes_brut(tab_resultats: pd.DataFrame | None) -> int:
    """Somme Infraction + Manquement (aligné OSCEAN / bilan thématique)."""
    if tab_resultats is None or tab_resultats.empty:
        return 0
    m = tab_resultats["resultat"].astype(str).str.strip()
    return int(tab_resultats.loc[m.isin(["Infraction", "Manquement"]), "nb"].sum())


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
        tbl.append([rlib, str(nbv), t])
    return tbl


def _pct_table_cell(n: int | float, denom: float) -> str:
    if denom is None or denom <= 0:
        return "n.d."
    return format_pct_int_from_rate(float(n) / float(denom))
from bilans.bilan_global.core import (
    analyse_controles_global,
    analyse_pej_pa_global,
    analyse_pve_global,
    analyse_annuelle_global,
    analyse_mensuelle_global,
    analyse_trimestrielle_global,
)


ASCII_LOGO_OFB = r"""
  OOOOOOO   FFFFFFF   BBBBBBB 
  OOOOOOO   FFFFFFF   BBBBBBB 
  OO   OO   FF        BB   BB
  OO   OO   FFFFFF    BBBBBBB
  OO   OO   FFFFFF    BBBBBBB
  OO   OO   FF        BB   BB
  OOOOOOO   FF        BBBBBBB
  OOOOOOO   FF        BBBBBBB

   OFFICE FRANÇAIS
 DE LA BIODIVERSITÉ
"""


def print_ascii_logo_ofb() -> None:
    print(ASCII_LOGO_OFB)

# ---------------------------------------------------------------------------
# Période et paramètres
# ---------------------------------------------------------------------------
DATE_DEB = pd.Timestamp("2025-01-01")
DATE_FIN = pd.Timestamp("2026-02-05")
DEPT_CODE = "21"
VENTILATION_TYPE_GLOBAL = "auto"  # auto | globale | annuelle
VENTILATION_SEUIL_JOURS_GLOBAL = 366


def resolve_ventilation_mode_global(date_deb: pd.Timestamp, date_fin: pd.Timestamp) -> str:
    """Détermine le mode global de ventilation temporelle."""
    vent_type = str(VENTILATION_TYPE_GLOBAL).strip().lower()
    duree_jours = int((date_fin - date_deb).days)
    if duree_jours < 183:
        return "mensuelle"
    if vent_type == "annuelle":
        return "annuelle"
    if vent_type == "globale":
        return "globale"
    if duree_jours > int(VENTILATION_SEUIL_JOURS_GLOBAL):
        return "annuelle"
    return "trimestrielle"


def _chart_pie_compact_legend_kw(n_categories: int) -> dict[str, float | int]:
    """
    Légende sous le camembert plus compacte lorsqu'il y a plusieurs parts —
    même principe que bilan_thematique (legend_fontsize=6, legend_ncol≤4).
    """
    if n_categories <= 4:
        return {}
    return {"legend_fontsize": 6, "legend_ncol": min(n_categories, 4)}


def _normalize_dept_typography(name: str) -> str:
    """Harmonise la typographie des noms de département (apostrophe/hyphens)."""
    s = str(name or "").strip()
    s = s.replace("-d'", " d’").replace("-D'", " D’")
    s = s.replace("d'", "d’").replace("D'", "D’")
    return " ".join(s.split())


def _build_title_lines_from_cfg(
    effective_cfg: dict,
    *,
    profile_label: str,
    dept_name_typo: str,
) -> tuple[list[str], list[str]]:
    """Construit les lignes de titre (page de garde + en-tête) via la config YAML."""
    title_cfg = effective_cfg.get("title", {}) if isinstance(effective_cfg, dict) else {}
    if not isinstance(title_cfg, dict):
        title_cfg = {}

    line1 = str(
        title_cfg.get(
            "line1",
            "Bilan des activités de police administrative et judiciaire",
        )
    ).strip() or "Bilan des activités de police administrative et judiciaire"

    line2_mode = str(title_cfg.get("line2_mode", "none")).strip().lower()
    if line2_mode == "profile_label":
        line2 = str(profile_label).strip()
    elif line2_mode == "fixed":
        line2 = str(title_cfg.get("line2_fixed", "")).strip()
    else:
        line2 = ""

    line3_mode = str(title_cfg.get("line3_mode", "department")).strip().lower()
    if line3_mode == "fixed":
        line3 = str(title_cfg.get("line3_fixed", "")).strip()
    else:
        line3 = f"Département de la {dept_name_typo}"

    header_lines = [x for x in [line1, line2, line3] if x]
    cover_lines = [line1, "", *([line2] if line2 else []), line3]
    return cover_lines, header_lines


def _load_glossary_config(root: Path) -> dict:
    """
    Charge la configuration du glossaire depuis config/presentation/glossaire.yaml
    puis, en fallback, depuis ref/glossaire.yaml.

    Aligne le moteur global sur la logique du moteur thématique, tout en
    excluant explicitement les entrées PNF/TUB (non pertinentes pour le bilan global).
    """
    cfg_candidates = [
        root / "config" / "presentation" / "glossaire.yaml",
        root / "ref" / "glossaire.yaml",
    ]
    cfg_path = next((p for p in cfg_candidates if p.exists()), None)
    default_cfg: dict = {
        "header": {
            "abbr_label": "Abréviation",
            "definition_label": "Signification",
        },
        "abbreviations": [
            {"id": "DC", "label": "DC", "definition": "Dossier de contrôle"},
            {
                "id": "NATINF",
                "label": "NATINF",
                "definition": "Nature d'infraction (nomenclature nationale)",
            },
            {
                "id": "OSCEAN",
                "label": "OSCEAN",
                "definition": "Outil de suivi des contrôles en environnement",
            },
            {"id": "PA", "label": "PA", "definition": "Procédure administrative"},
            {"id": "PEJ", "label": "PEJ", "definition": "Procédure d'enquête judiciaire"},
            {"id": "PVe", "label": "PVe", "definition": "Procès-verbal électronique"},
        ],
    }
    if cfg_path is None:
        return default_cfg
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        return default_cfg
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return default_cfg
    if not isinstance(data, dict):
        return default_cfg
    header = data.get("header") or {}
    if not isinstance(header, dict):
        header = {}
    abbrs = data.get("abbreviations") or []
    if not isinstance(abbrs, list):
        abbrs = []
    result = {
        "header": {
            "abbr_label": header.get("abbr_label", "Abréviation"),
            "definition_label": header.get("definition_label", "Signification"),
        },
        "abbreviations": [],
    }
    excluded_ids = {"PNF", "TUB"}
    for item in abbrs:
        if not isinstance(item, dict):
            continue
        id_ = str(item.get("id", "")).strip()
        if not id_ or id_.upper() in excluded_ids:
            continue
        label = str(item.get("label", id_)).strip() or id_
        definition = str(item.get("definition", "")).strip()
        if not definition:
            continue
        result["abbreviations"].append(
            {
                "id": id_,
                "label": label,
                "definition": definition,
            }
        )
    if not result["abbreviations"]:
        return default_cfg
    return result


def generate_pdf_report(
    out_dir: Path,
    ventilation_mode: str = "globale",
    chart_preset: str | None = None,
) -> None:
    """Génère le PDF du bilan global (page de garde, sommaire, chiffres clés, contrôles par domaine/thème, résultats, PEJ/PA/PVe)."""
    from scripts.common.charts import apply_mpl_style

    apply_mpl_style()
    _generate_pdf_content(
        out_dir,
        ventilation_mode,
        chart_preset=chart_preset,
    )


def _generate_pdf_content(
    out_dir: Path,
    ventilation_mode: str = "globale",
    *,
    chart_preset: str | None = None,
) -> None:
    """Construit le PDF du bilan global via PDFReportBuilder (aligné sur le bilan thématique)."""
    chart_ratios = compute_pdf_ratios(load_chart_display_config(_ROOT, preset=chart_preset))
    resolved_presentation_cfg = resolve_pdf_presentation_config(_ROOT, scope="global")
    presentation_cfg = (
        resolved_presentation_cfg.get("effective", {})
        if isinstance(resolved_presentation_cfg, dict)
        else {}
    )
    behavior_cfg = (
        resolved_presentation_cfg.get("behavior", {})
        if isinstance(resolved_presentation_cfg, dict)
        else {}
    )
    show_placeholder = should_show_placeholder(
        behavior_cfg if isinstance(behavior_cfg, dict) else None
    )

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
    else:
        agg_periode = _load_csv_opt(out_dir, "indicateurs_global_par_annee.csv")
    pej_resume = _load_csv_opt(out_dir, "pej_global_resume.csv")
    pa_resume = _load_csv_opt(out_dir, "pa_global_resume.csv")
    pve_resume = _load_csv_opt(out_dir, "pve_global_resume.csv")

    nb_ctrl = 0
    if agg_domaine is not None and not agg_domaine.empty:
        nb_ctrl = int(agg_domaine["nb"].sum())
    nb_pej = int(pej_resume["nb_pej_global"].iloc[0]) if pej_resume is not None and not pej_resume.empty else 0
    nb_pa = int(pa_resume["nb_pa_global"].iloc[0]) if pa_resume is not None and not pa_resume.empty else 0
    nb_pve = int(pve_resume["nb_pve_global"].iloc[0]) if pve_resume is not None and not pve_resume.empty else 0

    dept_name_typo = _normalize_dept_typography("Côte-d'Or")
    carte_usagers_path = get_cartes_dir() / "carte_global_usagers.png"
    has_carte_usagers = carte_usagers_path.exists()

    pdf_path = out_dir / "bilan_global_Cote_dOr.pdf"
    chart_bar_w = chart_ratios["chart_base"]

    # Structure du sommaire alignée sur le bilan thématique (1., 2., 2.x, 3. …).
    section_defs = [
        ("sec1", "1. Chiffres clés"),
        ("sec2_chap", "2. Contrôles"),
        ("sec21", "2.1. Indicateurs de la période"),
        ("sec22dom", "2.2. Localisations de contrôle par domaine"),
        ("sec22theme", "2.3. Localisations de contrôle par thème"),
        ("sec22res", "2.4. Résultats des contrôles"),
        ("sec3", "3. Procédures (PEJ, PA, PVe)"),
        ("sec31", "3.1 Procès-verbaux électroniques (PVe)"),
        ("sec32", "3.2 Procédures d’enquête judiciaire (PEJ)"),
        ("sec33", "3.3 Procédures administratives (PA)"),
        ("sec4", "4. Activité de contrôle par type d’usager"),
        ("sec5map", "5. Localisation cartographique des contrôles"),
        ("sec6", "6. Annexes"),
    ]
    sections = resolve_sections_for_toc(presentation_cfg, section_defs)

    cover_title_lines, header_title_lines = _build_title_lines_from_cfg(
        presentation_cfg,
        profile_label="",
        dept_name_typo=dept_name_typo,
    )
    report_header = " — ".join(line.strip() for line in header_title_lines if line.strip())

    builder = PDFReportBuilder(
        pdf_path=pdf_path,
        header_title=report_header,
        title=" — ".join(header_title_lines),
        author="Office français de la biodiversité",
    )
    avail_w = builder.avail_w
    tmp_dir = builder.tmp_dir

    subtitle_sources = "Sources des données : OFB/OSCEAN"
    if nb_pve > 0:
        subtitle_sources += " – MININT/AGC-PVe"

    title_page_cfg = resolve_title_page_config(_ROOT, scope="global")
    builder.add_title_page(
        title_lines=cover_title_lines,
        period_str=f"Période : du {DATE_DEB.date():%d/%m/%Y} au {DATE_FIN.date():%d/%m/%Y}",
        subtitle=subtitle_sources,
        title_page_config=title_page_cfg,
    )
    builder.add_toc(sections)

    builder.add_section("notice_methodo", "Notice méthodologique")
    builder.add_paragraph(
        "Les données relatives aux contrôles et aux procédures présentées dans ce document "
        "sont extraites de la base du logiciel OSCEAN, outil de rapportage des activités "
        "de police administrative et judiciaire des agents de l'OFB."
    )
    builder.add_paragraph(
        f"Pour ce bilan, les extractions portent sur la période du {DATE_DEB.date():%d/%m/%Y} "
        f"au {DATE_FIN.date():%d/%m/%Y}."
    )
    builder.add_paragraph(
        "Sauf mention contraire, l'unité de mesure du nombre de contrôles utilisée dans "
        "la suite du document est la localisation de contrôle : une unité correspond à "
        "une localisation renseignée."
    )
    builder.add_paragraph(
        "Il convient de distinguer l'activité de police administrative et l'activité de "
        "police judiciaire. Dans ce document, le terme « contrôle » renvoie exclusivement "
        "à la police administrative. Le terme « procédure judiciaire » désigne l'activité "
        "de police judiciaire, qui ne se limite pas aux infractions relevées lors des "
        "contrôles et peut aussi inclure des saisines extérieures (instruction parquet, "
        "signalements, plaintes, etc.)."
    )
    builder.add_paragraph(
        "Le total des contrôles par type d'usager peut être supérieur au total des "
        "contrôles, car une même fiche de contrôle peut renseigner plusieurs types "
        "d'usagers (contrôle multi-usager). L'analyse par type d'usager comptabilise "
        "chaque type renseigné afin de refléter au mieux les usagers effectivement "
        "concernés par l'action de contrôle."
    )
    builder.add_page_break()

    if is_section_enabled(presentation_cfg, "sec1", True):
        builder.add_section("sec1", "1. Chiffres clés")
    kf: list[tuple[str, str]] = []
    if nb_ctrl > 0:
        kf.append((str(nb_ctrl), "Localisations de contrôle"))
    tab_nc = tab_resultats_controles
    if tab_nc is not None and not tab_nc.empty and "resultat" in tab_nc.columns:
        nb_nc_row = tab_nc.loc[tab_nc["resultat"].astype(str).str.strip() == "Non-conforme", "nb"]
        nb_nc = int(nb_nc_row.sum()) if not nb_nc_row.empty else 0
        if nb_nc > 0:
            taux_nc = nb_nc / nb_ctrl if nb_ctrl else 0
            kf.append((str(nb_nc), "Contrôles non-conformes"))
            kf.append((format_pct_int_from_rate(taux_nc), "Taux de non-conformité"))
    elif tab_resultats is not None:
        nb_nc = _nb_non_conformes_brut(tab_resultats)
        if nb_nc > 0:
            taux_nc = nb_nc / nb_ctrl if nb_ctrl else 0
            kf.append((str(nb_nc), "Contrôles non-conformes"))
            kf.append((format_pct_int_from_rate(taux_nc), "Taux de non-conformité"))
    if nb_pej > 0:
        kf.append((str(nb_pej), "Nombre de procédures judiciaires"))
    kf.append((str(nb_pa), "Procédure administrative"))
    if nb_pve > 0:
        kf.append((str(nb_pve), "Nombre d'infractions relevées par PVe"))
    builder.add_key_figures(kf)
    builder.add_spacer(2)

    if is_section_enabled(presentation_cfg, "sec2_chap", True):
        builder.add_section("sec2_chap", "2. Contrôles")

    # 2.1 — Analyse de l’ensemble de la période du bilan
    if is_section_enabled(presentation_cfg, "sec21", True) and agg_periode is not None and not agg_periode.empty:
        is_mensuel = ventilation_mode == "mensuelle"
        is_trimestriel = ventilation_mode == "trimestrielle"
        label_periode = "Mois" if is_mensuel else ("Trimestre" if is_trimestriel else "Année")
        texte_ventilation = (
            "par mois "
            if is_mensuel
            else ("par trimestre " if is_trimestriel else "par année ")
        )
        builder.add_section(
            "sec21",
            "2.1. Indicateurs de la période",
            toc_level=1,
        )
        builder.add_paragraph(
            "Ventilation des principaux indicateurs globaux " + texte_ventilation
            + "sur l'ensemble de la période du bilan.",
        )
        tbl = [[
            label_periode,
            "Nb contrôles",
            "Contrôles non-conformes",
            "Taux de non-conformité",
            "PEJ",
            "PA",
            "PVe",
        ]]
        for _, row in agg_periode.iterrows():
            taux_str = (
                format_pct_int_from_rate(row.get("taux_non_conformite_controles"))
                if pd.notna(row.get("taux_non_conformite_controles"))
                else "n.d."
            )
            tbl.append([
                str(row["periode"]),
                str(int(row["nb_controles"])),
                str(int(row["nb_controles_non_conformes"])),
                taux_str,
                str(int(row["nb_pej"])),
                str(int(row["nb_pa"])),
                str(int(row["nb_pve"])),
            ])
        cap = (
            "Indicateurs mensuels" if is_mensuel else (
                "Indicateurs trimestriels" if is_trimestriel else "Indicateurs annuels"
            )
        )
        if is_block_enabled(presentation_cfg, "sec21.show_table", True):
            builder.add_table(
                tbl,
                caption=cap,
                col_widths=[
                    avail_w * 0.12,
                    avail_w * 0.14,
                    avail_w * 0.18,
                    avail_w * 0.14,
                    avail_w * 0.14,
                    avail_w * 0.14,
                    avail_w * 0.14,
                ],
                col_aligns=["RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"],
            )

        period_labels = [str(v) for v in agg_periode["periode"].tolist()]
        if ventilation_mode == "mensuelle":
            titre_ctrl = "Contrôles par mois (conformes / non-conformes)"
            titre_proc = "Procédures et PVe par mois"
        elif ventilation_mode == "trimestrielle":
            titre_ctrl = "Contrôles par trimestre (conformes / non-conformes)"
            titre_proc = "Procédures et PVe par trimestre"
        else:
            titre_ctrl = "Contrôles par année (conformes / non-conformes)"
            titre_proc = "Procédures et PVe par année"

        conformes = [
            int(row["nb_controles"]) - int(row["nb_controles_non_conformes"])
            for _, row in agg_periode.iterrows()
        ]
        non_conformes = [int(v) for v in agg_periode["nb_controles_non_conformes"].tolist()]
        stacked_ctrl_path = chart_bar_stacked(
            period_labels,
            {"Conformes": conformes, "Non-conformes": non_conformes},
            titre_ctrl,
            "Nombre de contrôles",
            tmp_dir,
            "bar_global_ctrl_stacked.png",
        )
        if is_block_enabled(presentation_cfg, "sec21.show_chart_controles", True):
            builder.add_image(Path(stacked_ctrl_path), width_ratio=chart_bar_w)

        series_proc = {
            "PEJ": [int(v) for v in agg_periode["nb_pej"].tolist()],
            "PA": [int(v) for v in agg_periode["nb_pa"].tolist()],
            "PVe": [int(v) for v in agg_periode["nb_pve"].tolist()],
        }
        if any(sum(vals) > 0 for vals in series_proc.values()) and is_block_enabled(presentation_cfg, "sec21.show_chart_procedures", True):
            stacked_proc_path = chart_bar_stacked(
                period_labels,
                series_proc,
                titre_proc,
                "Nombre",
                tmp_dir,
                "bar_global_proc_stacked.png",
            )
            builder.add_image(Path(stacked_proc_path), width_ratio=chart_bar_w)

        if ventilation_mode != "mensuelle" and is_block_enabled(presentation_cfg, "sec21.show_chart_taux_line", True):
            taux_values = []
            for _, row in agg_periode.iterrows():
                val = row.get("taux_non_conformite_controles")
                taux_values.append(int(round(float(val) * 100)) if pd.notna(val) else 0)
            if any(v > 0 for v in taux_values):
                line_path = chart_line_evolution(
                    period_labels,
                    {"Taux de non-conformité (%)": taux_values},
                    "Évolution du taux de non-conformité",
                    "Taux (%)",
                    tmp_dir,
                    "line_global_taux_inf.png",
                )
                builder.add_image(Path(line_path), width_ratio=chart_bar_w)

        builder.add_spacer(4)

    elif is_section_enabled(presentation_cfg, "sec21", True) and show_placeholder:
        builder.add_section(
            "sec21",
            "2.1. Indicateurs de la période",
            toc_level=1,
        )
        builder.add_paragraph("Aucun indicateur disponible sur la période.")

    def _render_sec22dom() -> None:
        if not is_section_enabled(presentation_cfg, "sec22dom", True):
            return
        builder.add_section(
            "sec22dom",
            "2.2. Localisations de contrôle par domaine",
            toc_level=1,
        )
        if agg_domaine is not None and not agg_domaine.empty:
            tbl = [["Domaine", "Nombre", "Taux"]]
            for _, row in agg_domaine.head(25).iterrows():
                taux_str = format_pct_int_from_rate(row.get("taux"))
                tbl.append([str(row["domaine"]), str(int(row["nb"])), taux_str])
            builder.add_table(
                tbl,
                caption="Localisations de contrôle par domaine",
                col_widths=[avail_w * 0.55, avail_w * 0.22, avail_w * 0.23],
                col_aligns=["LEFT", "RIGHT", "RIGHT"],
            )
            if is_block_enabled(presentation_cfg, "sec22dom.show_overflow_note", True) and len(agg_domaine) > 25:
                builder.add_paragraph(
                    f"... et {len(agg_domaine) - 25} autres domaines.",
                    style="BodySmall",
                )
            top_dom = agg_domaine.head(12)
            if not top_dom.empty:
                pie_data = {str(row["domaine"])[:30]: int(row["nb"]) for _, row in top_dom.iterrows()}
                if is_block_enabled(presentation_cfg, "sec22dom.show_pie", True) and pie_data:
                    pie_path = chart_pie(
                        pie_data,
                        "Localisations de contrôle par domaine (top 12)",
                        tmp_dir,
                        "pie_domaine.png",
                        **_chart_pie_compact_legend_kw(len(pie_data)),
                    )
                    builder.add_image(Path(pie_path), width_ratio=chart_ratios["global_resultats_pie"])
        elif show_placeholder:
            builder.add_paragraph("Aucune donnée domaine disponible.")
        builder.add_spacer(4)

    def _render_sec22theme() -> None:
        if not is_section_enabled(presentation_cfg, "sec22theme", True):
            return
        builder.add_section(
            "sec22theme",
            "2.3. Localisations de contrôle par thème",
            toc_level=1,
        )
        if agg_theme is not None and not agg_theme.empty:
            tbl = [["Thème", "Nombre", "Taux"]]
            for _, row in agg_theme.head(20).iterrows():
                taux_str = format_pct_int_from_rate(row.get("taux"))
                tbl.append([str(row["theme"])[:45], str(int(row["nb"])), taux_str])
            builder.add_table(
                tbl,
                caption="Localisations de contrôle par thème (extrait)",
                col_widths=[avail_w * 0.55, avail_w * 0.22, avail_w * 0.23],
                col_aligns=["LEFT", "RIGHT", "RIGHT"],
            )
        elif show_placeholder:
            builder.add_paragraph("Aucune donnée thème disponible.")
        builder.add_spacer(4)

    def _render_sec22res() -> None:
        if not is_section_enabled(presentation_cfg, "sec22res", True):
            return
        builder.add_section(
            "sec22res",
            "2.4. Résultats des contrôles",
            toc_level=1,
        )
        use_detail = tab_resultats_controles is not None and not tab_resultats_controles.empty
        show_res_table = is_block_enabled(presentation_cfg, "sec22res.show_table", True)
        show_res_pie = is_block_enabled(presentation_cfg, "sec22res.show_pie", True)
        if use_detail and show_res_table:
            tbl_pdf = _build_rows_resultats_controles_pdf(tab_resultats_controles)
            builder.add_table(
                tbl_pdf,
                caption="Résultats des contrôles",
                col_widths=[avail_w * 0.44, avail_w * 0.18, avail_w * 0.38],
                col_aligns=["LEFT", "RIGHT", "RIGHT"],
            )
            strip_res = tab_resultats_controles["resultat"].astype(str).str.strip()
            pie_mask = strip_res.isin(["Conforme", "Non-conforme", "En attente"])
            pie_res: dict[str, int] = {}
            for _, row in tab_resultats_controles.loc[pie_mask].iterrows():
                pie_res[str(row["resultat"]).strip()] = int(row["nb"])
            if show_res_pie and pie_res:
                pie_path = chart_pie(
                    pie_res,
                    "Répartition des résultats",
                    tmp_dir,
                    "pie_global_resultats.png",
                    **_chart_pie_compact_legend_kw(len(pie_res)),
                )
                builder.add_image(Path(pie_path), width_ratio=chart_ratios["global_resultats_pie"])
        elif tab_resultats is not None and not tab_resultats.empty and show_res_table:
            tbl = [["Résultat", "Nombre", "Taux"]]
            tr_pct = tab_counts_to_pct_strings(tab_resultats["nb"].astype(int).tolist())
            for i, (_, row) in enumerate(tab_resultats.iterrows()):
                tbl.append([str(row["resultat"]), str(int(row["nb"])), tr_pct[i]])
            builder.add_table(
                tbl,
                caption="Résultats des contrôles (libellés OSCEAN)",
                col_widths=[avail_w * 0.50, avail_w * 0.25, avail_w * 0.25],
                col_aligns=["LEFT", "RIGHT", "RIGHT"],
            )
            pie_res = {str(r["resultat"]): int(r["nb"]) for _, r in tab_resultats.iterrows()}
            if show_res_pie and pie_res:
                pie_path = chart_pie(
                    pie_res,
                    "Répartition des résultats",
                    tmp_dir,
                    "pie_global_resultats.png",
                    **_chart_pie_compact_legend_kw(len(pie_res)),
                )
                builder.add_image(Path(pie_path), width_ratio=chart_ratios["global_resultats_pie"])
        elif show_placeholder:
            builder.add_paragraph("Aucune donnée de résultat disponible.")
        builder.add_spacer(4)

    sec2_order = [sid for sid, _ in sections if sid in {"sec22dom", "sec22theme", "sec22res"}]
    if not sec2_order:
        sec2_order = ["sec22dom", "sec22theme", "sec22res"]
    for sid in sec2_order:
        if sid == "sec22dom":
            _render_sec22dom()
        elif sid == "sec22theme":
            _render_sec22theme()
        elif sid == "sec22res":
            _render_sec22res()

    if is_section_enabled(presentation_cfg, "sec3", True):
        builder.add_section("sec3", "3. Procédures (PEJ, PA, PVe)", start_on_new_page=True)
        builder.add_paragraph(
        f"Sur la période : {nb_pej} procédure(s) d'enquête judiciaire (PEJ), "
        f"{nb_pa} procédure(s) administrative(s) (PA), {nb_pve} procès-verbal(aux) électronique(s) (PVe).",
    )

    # 3.1 PVe
    def _render_sec31() -> None:
        if not is_section_enabled(presentation_cfg, "sec31", True):
            return
        builder.add_section(
            "sec31",
            "3.1 Procès-verbaux électroniques (PVe)",
            level=2,
            toc_level=1,
        )
        pve_natinf = _load_csv_opt(out_dir, "pve_global_par_natinf.csv")
        if (
            pve_natinf is not None
            and not pve_natinf.empty
            and is_block_enabled(presentation_cfg, "sec31.show_table", True)
        ):
            tbl = [["Nature d'infraction (NATINF)", "Nombre PVe"]]
            for _, row in pve_natinf.head(15).iterrows():
                libelle = (
                    row.get("libelle_natinf")
                    or row.get("LIBELLE_NATINF")
                    or ""
                )
                code = str(
                    row.get("numero_natinf")
                    or row.get("natinf")
                    or ""
                ).strip()
                if libelle:
                    nature = f"{code} – {libelle}" if code else libelle
                else:
                    nature = code or "-"
                tbl.append([nature, str(int(row["nb"]))])
            builder.add_table(
                tbl,
                caption="Analyse des NATINF relevées (PVe)",
                col_widths=[avail_w * 0.60, avail_w * 0.40],
                col_aligns=["LEFT", "RIGHT"],
            )
        elif show_placeholder:
            builder.add_paragraph("Aucune infraction PVe sur la période.")

    def _render_sec32() -> None:
        if not is_section_enabled(presentation_cfg, "sec32", True):
            return
        builder.add_section(
            "sec32",
            "3.2 Procédures d’enquête judiciaire (PEJ)",
            level=2,
            toc_level=1,
        )
        pej_dom = _load_csv_opt(out_dir, "pej_global_par_domaine.csv")
        if (
            pej_dom is not None
            and not pej_dom.empty
            and is_block_enabled(presentation_cfg, "sec32.show_table", True)
        ):
            tbl = [["Domaine", "Nombre PEJ"]]
            for _, row in pej_dom.head(15).iterrows():
                tbl.append([str(row["domaine"]), str(int(row["nb_pej"]))])
            builder.add_table(
                tbl,
                caption="PEJ par domaine",
                col_widths=[avail_w * 0.60, avail_w * 0.40],
                col_aligns=["LEFT", "RIGHT"],
            )
        elif show_placeholder:
            builder.add_paragraph("Aucune procédure d'enquête judiciaire sur la période.")

    def _render_sec33() -> None:
        if not is_section_enabled(presentation_cfg, "sec33", True):
            return
        builder.add_section(
            "sec33",
            "3.3 Procédures administratives (PA)",
            level=2,
            toc_level=1,
        )
        pa_dom = _load_csv_opt(out_dir, "pa_global_par_domaine.csv")
        if (
            pa_dom is not None
            and not pa_dom.empty
            and is_block_enabled(presentation_cfg, "sec33.show_table", True)
        ):
            tbl = [["Domaine", "Nombre PA"]]
            for _, row in pa_dom.head(15).iterrows():
                tbl.append([str(row["domaine"]), str(int(row["nb_pa"]))])
            builder.add_table(
                tbl,
                caption="PA par domaine",
                col_widths=[avail_w * 0.60, avail_w * 0.40],
                col_aligns=["LEFT", "RIGHT"],
            )
        elif show_placeholder:
            builder.add_paragraph("Aucune procédure administrative sur la période.")

    sec3_order = [sid for sid, _ in sections if sid in {"sec31", "sec32", "sec33"}]
    if not sec3_order:
        sec3_order = ["sec31", "sec32", "sec33"]
    for sid in sec3_order:
        if sid == "sec31":
            _render_sec31()
        elif sid == "sec32":
            _render_sec32()
        elif sid == "sec33":
            _render_sec33()

    if is_section_enabled(presentation_cfg, "sec4", True):
        builder.add_section(
        "sec4",
        "4. Activité de contrôle par type d’usager",
        start_on_new_page=True,
    )
    if is_section_enabled(presentation_cfg, "sec4", True) and (agg_usager is None or agg_usager.empty):
        if show_placeholder:
            builder.add_paragraph(
                "Aucune donnée « type d’usagers » n’est disponible dans les points de contrôle OSCEAN pour la période.",
            )
    elif is_section_enabled(presentation_cfg, "sec4", True):
        total_usagers = sum(int(row["nb"]) for _, row in agg_usager.iterrows())
        nb_multi = (
            int(usagers_resume["nb_controles_multi_usagers"].iloc[0])
            if usagers_resume is not None and not usagers_resume.empty and "nb_controles_multi_usagers" in usagers_resume.columns
            else 0
        )
        if is_block_enabled(presentation_cfg, "sec4.show_intro_text", True):
            builder.add_paragraph(
                "Répartition des usagers contrôlés par type (chaque type d’usager est compté avec son effectif).",
            )
        if is_block_enabled(presentation_cfg, "sec4.show_key_figures", True):
            builder.add_key_figures([
                (str(total_usagers), "Total effectifs usagers"),
                (str(nb_multi), "Localisations multi-usagers"),
            ])
        if is_block_enabled(presentation_cfg, "sec4.show_table_usagers", True):
            tbl_u = [["Type d’usagers", "Nombre", "Taux"]]
            nbs_ug = [int(row["nb"]) for _, row in agg_usager.iterrows()]
            pct_ug = tab_counts_to_pct_strings(nbs_ug)
            for i, (_, row) in enumerate(agg_usager.iterrows()):
                tbl_u.append([str(row["type_usager"]), str(int(row["nb"])), pct_ug[i]])
            builder.add_table(
                tbl_u,
                caption="Usagers contrôlés par type",
                col_widths=[avail_w * 0.58, avail_w * 0.21, avail_w * 0.21],
                col_aligns=["LEFT", "RIGHT", "RIGHT"],
            )

        if is_block_enabled(presentation_cfg, "sec4.show_pie_usagers", True):
            pie_data = {str(r["type_usager"])[:40]: int(r["nb"]) for _, r in agg_usager.iterrows()}
            if pie_data:
                pie_path = chart_pie(
                    pie_data,
                    "Usagers contrôlés par type",
                    tmp_dir,
                    "pie_usagers.png",
                    **_chart_pie_compact_legend_kw(len(pie_data)),
                )
                builder.add_image(Path(pie_path), width_ratio=chart_ratios["global_usagers_pie"])

        if (
            is_block_enabled(presentation_cfg, "sec4.show_table_usagers_x_domaine", True)
            and cross_usager_dom is not None
            and not cross_usager_dom.empty
        ):
            domain_cols = [c for c in cross_usager_dom.columns if c != "type_usager"]
            header = ["Type d’usagers"] + [str(c)[:22] for c in domain_cols]
            tbl_cross = [header]
            for _, row in cross_usager_dom.iterrows():
                tbl_cross.append([str(row["type_usager"])] + [str(int(row[c])) for c in domain_cols])
            other_w = (avail_w * 0.72) / max(1, len(domain_cols))
            col_widths = [avail_w * 0.28] + [other_w] * len(domain_cols)
            col_aligns = ["LEFT"] + ["RIGHT"] * len(domain_cols)
            builder.add_table(
                tbl_cross,
                caption="Usagers × Domaine (contrôles)",
                col_widths=col_widths,
                col_aligns=col_aligns,
                wide_headers=True,
            )

        # Résultats des contrôles par type d'usager (alignement visuel avec le thématique).
        if (
            (
                is_block_enabled(presentation_cfg, "sec4.show_resultats_par_type_usager_chart", True)
                or is_block_enabled(presentation_cfg, "sec4.show_resultats_par_type_usager_table", True)
            )
            and res_usager is not None
            and not res_usager.empty
        ):
            df_ru = res_usager.copy()
            required_cols = {"type_usager", "Conforme", "Infraction", "Manquement"}
            if required_cols.issubset(set(df_ru.columns)):
                labels = [str(x) for x in df_ru["type_usager"].tolist()]
                series: dict[str, list[int]] = {
                    "Conforme": [int(x) for x in df_ru["Conforme"].tolist()],
                    "Infraction": [int(x) for x in df_ru["Infraction"].tolist()],
                    "Manquement": [int(x) for x in df_ru["Manquement"].tolist()],
                }
                has_autre = "Autre_resultat" in df_ru.columns and int(df_ru["Autre_resultat"].sum()) > 0
                if has_autre:
                    series["Autre résultat"] = [int(x) for x in df_ru["Autre_resultat"].tolist()]

                if is_block_enabled(presentation_cfg, "sec4.show_resultats_par_type_usager_chart", True):
                    bar_path = chart_bar_horizontal_stacked(
                        labels,
                        series,
                        "Résultats des contrôles par type d'usager",
                        "Nombre",
                        tmp_dir,
                        "bar_resultats_par_type_usager_global.png",
                    )
                    builder.add_image(Path(bar_path), width_ratio=chart_bar_w)

                total_global = float(
                    df_ru["Conforme"].sum()
                    + df_ru["Infraction"].sum()
                    + df_ru["Manquement"].sum()
                    + (df_ru["Autre_resultat"].sum() if "Autre_resultat" in df_ru.columns else 0)
                ) or 1.0
                tbl_res = [[
                    "Type d'usager",
                    "Conforme",
                    "% conforme",
                    "Infraction",
                    "% infraction",
                    "Manquement",
                    "% manquement",
                    *(["Autre résultat", "% autre résultat"] if has_autre else []),
                    "Total",
                    "% du total",
                ]]
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
                        str(row.get("type_usager", "")),
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

                first_col_w = avail_w * 0.20
                n_other_cols = len(tbl_res[0]) - 1
                other_w = (avail_w - first_col_w) / float(max(1, n_other_cols))
                col_widths = [first_col_w] + [other_w] * n_other_cols
                if is_block_enabled(presentation_cfg, "sec4.show_resultats_par_type_usager_table", True):
                    builder.add_table(
                        tbl_res,
                        caption="Résultats des contrôles par type d'usager",
                        col_widths=col_widths,
                        col_aligns=["LEFT"] + ["RIGHT"] * (len(tbl_res[0]) - 1),
                        keep_together=True,
                        header_font_size=8,
                        wide_headers=False,
                    )

    if is_section_enabled(presentation_cfg, "sec5map", True):
        builder.add_section(
        "sec5map",
        "5. Localisation cartographique des contrôles",
        start_on_new_page=True,
    )
    show_map_block = is_block_enabled(presentation_cfg, "sec5.show_map", True)
    show_map_fallback = is_block_enabled(presentation_cfg, "sec5.show_map_fallback_message", True)
    if is_section_enabled(presentation_cfg, "sec5map", True) and has_carte_usagers and show_map_block:
        builder.add_paragraph(
            "Répartition spatiale des usagers contrôlés par types (générateur cartographique).",
        )
        builder.add_map(Path(carte_usagers_path))
    elif is_section_enabled(presentation_cfg, "sec5map", True) and show_map_fallback and show_placeholder:
        builder.add_paragraph(
            "<i>Carte non disponible. Déposez le fichier "
            "<b>carte_global_usagers.png</b> dans le dossier des cartes pour "
            "l'intégrer au bilan.</i>"
        )

    if is_section_enabled(presentation_cfg, "sec6", True):
        builder.add_section("sec6", "6. Annexes", start_on_new_page=True)
        methodo = (
            f"<b>Période :</b> du {DATE_DEB.date():%d/%m/%Y} au {DATE_FIN.date():%d/%m/%Y}.<br/>"
            f"<b>Périmètre :</b> département de la {dept_name_typo} (21).<br/>"
            "<b>Sources :</b> OSCEAN (points de contrôle, PEJ, PA) et PVe OFB.<br/>"
            f"<b>Ventilation temporelle :</b> {resolve_ventilation_mode_global(DATE_DEB, DATE_FIN)} "
            f"(seuil {VENTILATION_SEUIL_JOURS_GLOBAL} jours en mode auto).<br/>"
            "Aucun filtre sur domaine ou thème ; tous NATINF pour PEJ et PVe.<br/>"
            "<b>Types d’usagers :</b> issus du champ OSCEAN <i>type_usager</i> des points de contrôle ; "
            "catégorie « dominante » par contrôle via le mapping ref/types_usagers.csv."
        )
        if is_block_enabled(presentation_cfg, "sec6.show_methodology", True):
            builder.add_methodology(methodo)

    gloss_cfg = _load_glossary_config(_ROOT)
    header_cfg = gloss_cfg.get("header", {}) or {}
    abbr_list = gloss_cfg.get("abbreviations", []) or []
    abbr_by_id: dict[str, dict] = {}
    for item in abbr_list:
        if not isinstance(item, dict):
            continue
        id_ = str(item.get("id", "")).strip()
        if not id_:
            continue
        abbr_by_id[id_] = item

    used_ids: list[str] = []

    def _add_if_available(abbr_id: str, condition: bool) -> None:
        if condition and abbr_id in abbr_by_id and abbr_id not in used_ids:
            used_ids.append(abbr_id)

    _add_if_available("OSCEAN", True)
    _add_if_available("DC", nb_ctrl > 0)
    _add_if_available("NATINF", nb_pve > 0 or nb_pej > 0)
    _add_if_available("PA", nb_pa > 0)
    _add_if_available("PEJ", nb_pej > 0)
    _add_if_available("PVe", nb_pve > 0)

    if (
        is_section_enabled(presentation_cfg, "sec6", True)
        and is_block_enabled(presentation_cfg, "sec6.show_glossary", True)
        and used_ids
    ):
        glossaire_rows: list[list[str]] = [
            [
                str(header_cfg.get("abbr_label", "Abréviation")),
                str(header_cfg.get("definition_label", "Signification")),
            ]
        ]
        for abbr_id in used_ids:
            item = abbr_by_id[abbr_id]
            glossaire_rows.append(
                [
                    str(item.get("label", abbr_id)),
                    str(item.get("definition", "")),
                ]
            )
        builder.add_glossary(
            glossaire_rows,
            col_widths=[avail_w * 0.25, avail_w * 0.75],
            col_aligns=["LEFT", "LEFT"],
        )

    builder.build()


def run_global(
    date_deb: str,
    date_fin: str,
    dept_code: str,
    chart_preset: str | None = None,
) -> int:
    """
    Exécute le bilan global (tous domaines/thèmes, PA, PEJ, PVe).
    Utilisable depuis le script unique run_bilan.py.
    Retourne 0 en succès, 1 en erreur.
    """
    global DATE_DEB, DATE_FIN, DEPT_CODE
    try:
        DATE_DEB = pd.to_datetime(date_deb)
        DATE_FIN = pd.to_datetime(date_fin)
    except Exception:
        print("Dates invalides : utiliser YYYY-MM-DD.", file=sys.stderr)
        return 1
    DEPT_CODE = str(dept_code)

    root = _ROOT
    out_dir = get_out_dir("bilan_global")

    try:
        print(f"Période : {DATE_DEB.date():%d/%m/%Y} au {DATE_FIN.date():%d/%m/%Y} – Département {DEPT_CODE}.")
        ventilation_mode = resolve_ventilation_mode_global(DATE_DEB, DATE_FIN)
        print(
            f"Ventilation temporelle : {ventilation_mode} "
            f"(type={VENTILATION_TYPE_GLOBAL}, seuil={VENTILATION_SEUIL_JOURS_GLOBAL} j)"
        )

        print("Étape 1/4 : chargement des données...")
        with Spinner():
            point = load_point_ctrl(root, dept_code=DEPT_CODE, date_deb=DATE_DEB, date_fin=DATE_FIN)
            pa = load_pa(root, date_deb=DATE_DEB, date_fin=DATE_FIN)
            pej = load_pej(root, date_deb=DATE_DEB, date_fin=DATE_FIN)
            pve = load_pve(root, dept_code=DEPT_CODE, date_deb=DATE_DEB, date_fin=DATE_FIN)

        spatial_log = logging.getLogger("bilans.spatial")
        if not point.empty:
            point = ensure_insee_from_communes_shp(
                point, root, context="bilan global — points de contrôle", log=spatial_log
            )
        if not pve.empty:
            pve = ensure_insee_from_communes_shp(
                pve, root, context="bilan global — PVe", log=spatial_log
            )

        print("Étape 2/4 : analyse des contrôles...")
        with Spinner():
            analyse_controles_global(point, out_dir)

        print("Étape 3/4 : analyse PEJ / PA / PVe...")
        with Spinner():
            analyse_pej_pa_global(root, point, pa, pej, out_dir)
            analyse_pve_global(pve, out_dir)
            if ventilation_mode == "annuelle":
                analyse_annuelle_global(point, pa, pej, pve, out_dir)
            elif ventilation_mode == "mensuelle":
                analyse_mensuelle_global(point, pa, pej, pve, out_dir)
            elif ventilation_mode == "trimestrielle":
                analyse_trimestrielle_global(point, pa, pej, pve, out_dir)
            else:
                # Mode globale : pas de ventilation temporelle
                pd.DataFrame(columns=[
                    "periode",
                    "nb_controles",
                    "nb_controles_non_conformes",
                    "taux_non_conformite_controles",
                    "nb_pej",
                    "nb_pa",
                    "nb_pve",
                ]).to_csv(out_dir / "indicateurs_global_par_annee.csv", sep=";", index=False)

        # Assure, si possible, la présence des cartes liées au bilan global
        try:
            from scripts.common.carte_helper import ensure_maps
            ensure_maps("bilan_global", date_deb=str(DATE_DEB.date()), date_fin=str(DATE_FIN.date()), dept_code=DEPT_CODE)
        except Exception:
            # On ne bloque pas le bilan si la cartographie n'est pas disponible
            pass

        print("Étape 4/4 : génération du PDF...")
        with Spinner():
            generate_pdf_report(
                out_dir,
                ventilation_mode=ventilation_mode,
                chart_preset=chart_preset,
            )

        print("Bilan global généré dans out/bilan_global.")
        return 0
    except Exception as e:
        print(f"Erreur bilan global : {e}", file=sys.stderr)
        return 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Génère le bilan global du service départemental (tous domaines/thèmes, PA, PEJ, PVe)."
    )
    parser.add_argument("--date-deb", type=str, default=None, help="Date de début (YYYY-MM-DD).")
    parser.add_argument("--date-fin", type=str, default=None, help="Date de fin (YYYY-MM-DD).")
    parser.add_argument("--dept-code", type=str, default=None, help="Code département (ex: 21).")
    parser.add_argument(
        "--preset",
        choices=("compact", "standard", "large"),
        default=None,
        help="Preset de taille des graphiques PDF.",
    )
    return parser.parse_args()


def main() -> None:
    global DATE_DEB, DATE_FIN, DEPT_CODE

    print_ascii_logo_ofb()

    args = _parse_args()
    if args.date_deb is None or args.date_fin is None or args.dept_code is None:
        date_deb_str, date_fin_str, dept_str = ask_periode_dept(
            date_deb_default=args.date_deb or str(DATE_DEB.date()),
            date_fin_default=args.date_fin or str(DATE_FIN.date()),
            dept_default=args.dept_code or DEPT_CODE,
        )
        args.date_deb = date_deb_str
        args.date_fin = date_fin_str
        args.dept_code = dept_str
    try:
        DATE_DEB = pd.to_datetime(args.date_deb)
        DATE_FIN = pd.to_datetime(args.date_fin)
    except Exception:
        raise SystemExit("Dates invalides : utiliser YYYY-MM-DD.")
    DEPT_CODE = str(args.dept_code)

    exit_code = run_global(
        args.date_deb,
        args.date_fin,
        args.dept_code,
        chart_preset=args.preset,
    )
    if exit_code != 0:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
