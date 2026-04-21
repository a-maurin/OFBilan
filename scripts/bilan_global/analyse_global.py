"""Bilan global — activité du service départemental (tous domaines/thèmes, PA, PEJ, PVe)."""
import argparse
import logging
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd
from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)

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
    enrich_with_pnforet_sig_zones,
)
from scripts.common.prompt_periode import ask_periode_dept
from scripts.common.utils import _load_csv_opt, serie_type_usager, agg_effectifs_usagers, agg_effectifs_usagers_par_domaine
from scripts.common.ofb_charte import (
    COLOR_GREY,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    FONT_FAMILY,
    IMG_BACKGROUND,
    IMG_FOOTER_DECO,
    IMG_LOGO_BANNER,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    PAGE_H,
    PAGE_W,
    Spinner,
    _get_styles,
)
from scripts.common.pdf_utils import key_figures_table, ofb_table
from scripts.common.chart_display_config import load_chart_display_config, compute_pdf_ratios
from scripts.common.charts import chart_pie, chart_bar_grouped, chart_bar_stacked, chart_line_evolution
from bilans.bilan_global.core import (
    analyse_controles_global,
    analyse_pej_pa_global,
    analyse_pve_global,
    analyse_annuelle_global,
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
    if vent_type == "annuelle":
        return "annuelle"
    if vent_type == "globale":
        return "globale"
    if duree_jours > int(VENTILATION_SEUIL_JOURS_GLOBAL):
        return "annuelle"
    return "trimestrielle"


def generate_pdf_report(
    out_dir: Path,
    ventilation_mode: str = "globale",
    chart_preset: str | None = None,
) -> None:
    """Génère le PDF du bilan global (page de garde, sommaire, chiffres clés, contrôles par domaine/thème, résultats, PEJ/PA/PVe)."""
    # Appliquer le style matplotlib pour utiliser la police Marianne
    from scripts.common.charts import apply_mpl_style
    apply_mpl_style()
    
    styles = _get_styles()
    tmp_dir = Path(tempfile.mkdtemp(prefix="ofb_global_"))
    try:
        _generate_pdf_content(
            out_dir,
            tmp_dir,
            styles,
            ventilation_mode,
            chart_preset=chart_preset,
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _generate_pdf_content(
    out_dir: Path,
    tmp_dir: Path,
    styles,
    ventilation_mode: str = "globale",
    *,
    chart_preset: str | None = None,
) -> None:
    """Corps de la génération PDF, séparé pour garantir le nettoyage de tmp_dir."""
    avail_w = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT
    chart_ratios = compute_pdf_ratios(load_chart_display_config(_ROOT, preset=chart_preset))

    tab_resultats = _load_csv_opt(out_dir, "controles_global_resultats.csv")
    agg_domaine = _load_csv_opt(out_dir, "controles_global_par_domaine.csv")
    agg_theme = _load_csv_opt(out_dir, "controles_global_par_theme.csv")
    agg_usager = _load_csv_opt(out_dir, "controles_global_par_usager.csv")
    cross_usager_dom = _load_csv_opt(out_dir, "controles_global_usager_par_domaine.csv")
    usagers_resume = _load_csv_opt(out_dir, "controles_global_usagers_resume.csv")
    if ventilation_mode == "trimestrielle":
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

    pdf_path = out_dir / "bilan_global_Cote_dOr.pdf"

    sections = [
        ("sec1", "I. Chiffres clés"),
    ]
    if agg_periode is not None and not agg_periode.empty:
        sections.append(("sec1b", "I bis. Analyse de l'ensemble de la période du bilan"))
    sections.extend([
        ("sec2", "II. Localisations de contrôle par domaine"),
        ("sec3", "III. Localisations de contrôle par thème"),
        ("sec4", "IV. Résultats des contrôles"),
        ("sec5", "V. Procédures (PEJ, PA, PVe)"),
        ("sec6", "VI. Types d’usagers"),
        ("sec7", "VII. Annexes"),
    ])

    content_frame = Frame(
        MARGIN_LEFT, MARGIN_BOTTOM,
        PAGE_W - MARGIN_LEFT - MARGIN_RIGHT,
        PAGE_H - MARGIN_TOP - MARGIN_BOTTOM,
        id="content",
    )

    def _header_footer(canvas, doc):
        canvas.saveState()
        if IMG_FOOTER_DECO.exists():
            canvas.drawImage(
                str(IMG_FOOTER_DECO), PAGE_W - 60 * mm, 0,
                width=60 * mm, height=7 * mm,
                preserveAspectRatio=True, mask="auto",
            )
        canvas.setStrokeColor(rl_colors.HexColor(COLOR_PRIMARY))
        canvas.setLineWidth(2)
        y_header = PAGE_H - 16 * mm
        canvas.line(MARGIN_LEFT, y_header, PAGE_W - MARGIN_RIGHT, y_header)
        canvas.setFont(f"{FONT_FAMILY}-Bold", 8)
        canvas.setFillColor(rl_colors.HexColor(COLOR_PRIMARY))
        canvas.drawString(MARGIN_LEFT, y_header + 3, "Bilan activité SD – Côte-d'Or")
        y_foot = 8 * mm
        canvas.setFont(f"{FONT_FAMILY}-Bold", 7)
        canvas.setFillColor(rl_colors.HexColor(COLOR_SECONDARY))
        canvas.drawString(MARGIN_LEFT, y_foot + 12, "Office français de la biodiversité")
        canvas.setFont(FONT_FAMILY, 7)
        canvas.drawString(MARGIN_LEFT, y_foot + 3,
                         "SD de la Côte-d'Or – 57, rue de Mulhouse – 21000 Dijon – www.ofb.gouv.fr")
        canvas.drawRightString(PAGE_W - MARGIN_RIGHT, y_foot + 3, f"{doc.page}")
        canvas.restoreState()

    def _title_page_template(canvas, doc):
        canvas.saveState()
        if IMG_BACKGROUND.exists():
            canvas.drawImage(str(IMG_BACKGROUND), 0, 0, width=PAGE_W, height=PAGE_H * 0.86,
                            preserveAspectRatio=False, mask="auto")
        if IMG_LOGO_BANNER.exists():
            canvas.drawImage(str(IMG_LOGO_BANNER), 0, PAGE_H * 0.86, width=PAGE_W, height=PAGE_H * 0.14,
                            preserveAspectRatio=False, mask="auto")
        cx = PAGE_W / 2
        canvas.setFont(f"{FONT_FAMILY}-Bold", 26)
        canvas.setFillColor(rl_colors.HexColor(COLOR_PRIMARY))
        canvas.drawCentredString(cx, PAGE_H * 0.62 + 14, "Bilan : global")
        canvas.drawCentredString(cx, PAGE_H * 0.62 - 20, "pour la Côte-d'Or")
        canvas.setFont(FONT_FAMILY, 14)
        canvas.setFillColor(rl_colors.HexColor(COLOR_GREY))
        canvas.drawCentredString(
            cx,
            PAGE_H * 0.50,
            f"Période : {DATE_DEB.date():%d/%m/%Y} au {DATE_FIN.date():%d/%m/%Y}",
        )
        canvas.setFont(FONT_FAMILY, 11)
        subtitle = "Sources des données : OFB/OSCEAN"
        if nb_pve > 0:
            subtitle += " – MININT/AGC-PVe"
        canvas.drawCentredString(
            cx,
            PAGE_H * 0.42,
            subtitle,
        )
        canvas.setFont(f"{FONT_FAMILY}-Bold", 7)
        canvas.setFillColor(rl_colors.HexColor(COLOR_SECONDARY))
        canvas.drawString(MARGIN_LEFT, 30, "Office français de la biodiversité")
        canvas.setFont(FONT_FAMILY, 7)
        canvas.drawString(MARGIN_LEFT, 20, "SD de la Côte-d'Or – www.ofb.gouv.fr")
        canvas.restoreState()

    title_template = PageTemplate(id="TitlePage", frames=[Frame(0, 0, PAGE_W, PAGE_H, id="full")], onPage=_title_page_template)
    normal_template = PageTemplate(id="Normal", frames=[content_frame], onPage=_header_footer)

    doc = BaseDocTemplate(
        str(pdf_path), pagesize=A4,
        title="Bilan activité SD – Côte-d'Or",
        author="Office français de la biodiversité",
    )
    doc.addPageTemplates([title_template, normal_template])

    story = []
    story.append(NextPageTemplate("Normal"))
    story.append(PageBreak())

    story.append(Paragraph("Sommaire", styles["Title"]))
    story.append(Spacer(1, 6 * mm))
    for anchor, sec_title in sections:
        story.append(Paragraph(f'<a href="#{anchor}" color="{COLOR_PRIMARY}">{sec_title}</a>', styles["TOCEntry"]))
    story.append(PageBreak())

    # I. Chiffres clés
    story.append(Paragraph('<a name="sec1"/>I. Chiffres clés', styles["Heading1"]))
    story.append(key_figures_table([
        (str(nb_ctrl), "Localisations de contrôle"),
        (str(nb_pej), "PEJ"),
        (str(nb_pa), "PA"),
        (str(nb_pve), "PVe"),
    ], styles))
    story.append(Spacer(1, 6 * mm))

    # I bis. Analyse de l’ensemble de la période du bilan
    if agg_periode is not None and not agg_periode.empty:
        is_trimestriel = ventilation_mode == "trimestrielle"
        label_periode = "Trimestre" if is_trimestriel else "Ann\u00e9e"
        texte_ventilation = "par trimestre " if is_trimestriel else "par ann\u00e9e "
        story.append(Paragraph(
            '<a name="sec1b"/>I bis. Analyse de l\u2019ensemble de la p\u00e9riode du bilan',
            styles["Heading1"],
        ))
        story.append(Paragraph(
            "Ventilation des principaux indicateurs globaux " + texte_ventilation
            + "sur l\u2019ensemble de la p\u00e9riode du bilan.",
            styles["BodyText"],
        ))
        tbl = [[
            label_periode,
            "Nb contr\u00f4les",
            "Contr\u00f4les non-conformes",
            "Taux d\u2019infraction",
            "PEJ",
            "PA",
            "PVe",
        ]]
        for _, row in agg_periode.iterrows():
            taux_str = (
                f"{float(row['taux_infraction_controles']):.1%}"
                if pd.notna(row.get("taux_infraction_controles"))
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
        story.append(
            ofb_table(
                tbl,
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
        )
        story.append(Spacer(1, 4 * mm))

        from PIL import Image as PILImage
        from reportlab.platypus import Image as RLImage

        year_labels = [str(v) for v in agg_periode["periode"].tolist()]
        titre_ctrl = "Contr\u00f4les par trimestre (conformes / non-conformes)" if ventilation_mode == "trimestrielle" else "Contr\u00f4les par ann\u00e9e (conformes / non-conformes)"
        titre_proc = "Proc\u00e9dures et PVe par trimestre" if ventilation_mode == "trimestrielle" else "Proc\u00e9dures et PVe par ann\u00e9e"

        conformes = [
            int(row["nb_controles"]) - int(row["nb_controles_non_conformes"])
            for _, row in agg_periode.iterrows()
        ]
        non_conformes = [int(v) for v in agg_periode["nb_controles_non_conformes"].tolist()]
        stacked_ctrl_path = chart_bar_stacked(
            year_labels,
            {"Conformes": conformes, "Non-conformes": non_conformes},
            titre_ctrl,
            "Nombre de contr\u00f4les",
            tmp_dir, "bar_global_ctrl_stacked.png",
        )
        _pimg = PILImage.open(stacked_ctrl_path)
        _tw = avail_w * 0.78
        _th = _tw * (_pimg.height / _pimg.width)
        _pimg.close()
        story.append(RLImage(stacked_ctrl_path, width=_tw, height=_th))
        story.append(Spacer(1, 4 * mm))

        series_proc = {
            "PEJ": [int(v) for v in agg_periode["nb_pej"].tolist()],
            "PA": [int(v) for v in agg_periode["nb_pa"].tolist()],
            "PVe": [int(v) for v in agg_periode["nb_pve"].tolist()],
        }
        if any(sum(vals) > 0 for vals in series_proc.values()):
            stacked_proc_path = chart_bar_stacked(
                year_labels, series_proc,
                titre_proc,
                "Nombre",
                tmp_dir, "bar_global_proc_stacked.png",
            )
            _pimg = PILImage.open(stacked_proc_path)
            _tw = avail_w * 0.78
            _th = _tw * (_pimg.height / _pimg.width)
            _pimg.close()
            story.append(RLImage(stacked_proc_path, width=_tw, height=_th))
            story.append(Spacer(1, 4 * mm))

        taux_values = []
        for _, row in agg_periode.iterrows():
            val = row.get("taux_infraction_controles")
            taux_values.append(round(float(val) * 100, 1) if pd.notna(val) else 0)
        if any(v > 0 for v in taux_values):
            line_path = chart_line_evolution(
                year_labels,
                {"Taux d\u2019infraction (%)": taux_values},
                "\u00c9volution du taux d\u2019infraction",
                "Taux (%)",
                tmp_dir, "line_global_taux_inf.png",
            )
            _pimg = PILImage.open(line_path)
            _tw = avail_w * 0.78
            _th = _tw * (_pimg.height / _pimg.width)
            _pimg.close()
            story.append(RLImage(line_path, width=_tw, height=_th))
            story.append(Spacer(1, 6 * mm))

    # II. Localisations de contrôle par domaine
    story.append(Paragraph('<a name="sec2"/>II. Localisations de contrôle par domaine', styles["Heading1"]))
    if agg_domaine is not None and not agg_domaine.empty:
        story.append(Paragraph("Tableau 1 : Localisations de contrôle par domaine", styles["TableCaption"]))
        tbl = [["Domaine", "Nombre", "Taux"]]
        for _, row in agg_domaine.head(25).iterrows():
            taux_str = f"{row['taux']:.1%}" if pd.notna(row.get("taux")) else "n.d."
            tbl.append([str(row["domaine"]), str(int(row["nb"])), taux_str])
        story.append(ofb_table(tbl, col_widths=[avail_w * 0.55, avail_w * 0.22, avail_w * 0.23], col_aligns=["LEFT", "RIGHT", "RIGHT"]))
        if len(agg_domaine) > 25:
            story.append(Paragraph(f"... et {len(agg_domaine) - 25} autres domaines.", styles["BodySmall"]))
        # Graphique
        top_dom = agg_domaine.head(12)
        if not top_dom.empty:
            pie_data = {str(row["domaine"])[:30]: int(row["nb"]) for _, row in top_dom.iterrows()}
            if pie_data:
                pie_path = chart_pie(pie_data, "Localisations de contrôle par domaine (top 12)", tmp_dir, "pie_domaine.png")
                from PIL import Image as PILImage
                from reportlab.platypus import Image as RLImage
                _pimg = PILImage.open(pie_path)
                _target_w = avail_w * chart_ratios["global_resultats_pie"]
                _target_h = _target_w * (_pimg.height / _pimg.width)
                _pimg.close()
                story.append(RLImage(pie_path, width=_target_w, height=_target_h))
    else:
        story.append(Paragraph("Aucune donnée domaine disponible.", styles["BodyText"]))
    story.append(Spacer(1, 6 * mm))

    # III. Localisations de contrôle par thème
    story.append(Paragraph('<a name="sec3"/>III. Localisations de contrôle par thème', styles["Heading1"]))
    if agg_theme is not None and not agg_theme.empty:
        story.append(Paragraph("Tableau 2 : Localisations de contrôle par thème (extrait)", styles["TableCaption"]))
        tbl = [["Thème", "Nombre", "Taux"]]
        for _, row in agg_theme.head(20).iterrows():
            taux_str = f"{row['taux']:.1%}" if pd.notna(row.get("taux")) else "n.d."
            tbl.append([str(row["theme"])[:45], str(int(row["nb"])), taux_str])
        story.append(ofb_table(tbl, col_widths=[avail_w * 0.55, avail_w * 0.22, avail_w * 0.23], col_aligns=["LEFT", "RIGHT", "RIGHT"]))
    else:
        story.append(Paragraph("Aucune donnée thème disponible.", styles["BodyText"]))
    story.append(Spacer(1, 6 * mm))

    # IV. Résultats des contrôles
    story.append(Paragraph('<a name="sec4"/>IV. Résultats des contrôles', styles["Heading1"]))
    if tab_resultats is not None and not tab_resultats.empty:
        story.append(Paragraph("Tableau 3 : Résultats (Conforme / Infraction / Manquement)", styles["TableCaption"]))
        tbl = [["Résultat", "Nombre", "Taux"]]
        for _, row in tab_resultats.iterrows():
            taux_str = f"{row['taux']:.1%}" if pd.notna(row.get("taux")) else "n.d."
            tbl.append([str(row["resultat"]), str(int(row["nb"])), taux_str])
        story.append(ofb_table(tbl, col_widths=[avail_w * 0.50, avail_w * 0.25, avail_w * 0.25], col_aligns=["LEFT", "RIGHT", "RIGHT"]))
    else:
        story.append(Paragraph("Aucune donnée de résultat disponible.", styles["BodyText"]))
    story.append(Spacer(1, 6 * mm))

    # V. Procédures
    story.append(Paragraph('<a name="sec5"/>V. Procédures (PEJ, PA, PVe)', styles["Heading1"]))
    story.append(Paragraph(
        f"Sur la période : {nb_pej} procédure(s) d'enquête judiciaire (PEJ), "
        f"{nb_pa} procédure(s) administrative(s) (PA), {nb_pve} procès-verbal(aux) électronique(s) (PVe).",
        styles["BodyText"],
    ))
    
    # Tableau PEJ par domaine
    pej_dom = _load_csv_opt(out_dir, "pej_global_par_domaine.csv")
    if pej_dom is not None and not pej_dom.empty:
        story.append(Paragraph("Tableau 4 : PEJ par domaine", styles["TableCaption"]))
        tbl = [["Domaine", "Nombre PEJ"]]
        for _, row in pej_dom.head(15).iterrows():
            tbl.append([str(row["domaine"]), str(int(row["nb_pej"]))])
        story.append(ofb_table(tbl, col_widths=[avail_w * 0.60, avail_w * 0.40], col_aligns=["LEFT", "RIGHT"]))
        story.append(Spacer(1, 3 * mm))
    
    # Tableau PA par domaine
    pa_dom = _load_csv_opt(out_dir, "pa_global_par_domaine.csv")
    if pa_dom is not None and not pa_dom.empty:
        story.append(Paragraph("Tableau 5 : PA par domaine", styles["TableCaption"]))
        tbl = [["Domaine", "Nombre PA"]]
        for _, row in pa_dom.head(15).iterrows():
            tbl.append([str(row["domaine"]), str(int(row["nb_pa"]))])
        story.append(ofb_table(tbl, col_widths=[avail_w * 0.60, avail_w * 0.40], col_aligns=["LEFT", "RIGHT"]))
        story.append(Spacer(1, 3 * mm))
    
    # Tableau PVe par NATINF (code + libellé)
    pve_natinf = _load_csv_opt(out_dir, "pve_global_par_natinf.csv")
    if pve_natinf is not None and not pve_natinf.empty:
        story.append(Paragraph(
            "Tableau 6 : PVe par nature d'infraction (code NATINF et libellé)",
            styles["TableCaption"],
        ))
        tbl = [["Nature d'infraction (NATINF)", "Nombre PVe"]]
        for _, row in pve_natinf.head(15).iterrows():
            # On privilégie le libellé issu du référentiel NATINF, avec affichage du code.
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
        story.append(ofb_table(tbl, col_widths=[avail_w * 0.60, avail_w * 0.40], col_aligns=["LEFT", "RIGHT"]))

    story.append(PageBreak())

    # VI. Types d'usagers
    story.append(Paragraph('<a name="sec6"/>VI. Types d’usagers', styles["Heading1"]))
    if agg_usager is None or agg_usager.empty:
        story.append(Paragraph(
            "Aucune donnée « type d’usagers » n’est disponible dans les points de contrôle OSCEAN pour la période.",
            styles["BodyText"],
        ))
    else:
        # Calculer le nombre total d'usagers contrôlés (pas juste les contrôles multi-usagers)
        total_usagers = sum(int(row["nb"]) for _, row in agg_usager.iterrows())
        
        nb_multi = (
            int(usagers_resume["nb_controles_multi_usagers"].iloc[0])
            if usagers_resume is not None and not usagers_resume.empty and "nb_controles_multi_usagers" in usagers_resume.columns
            else 0
        )
        
        story.append(Paragraph(
            "Répartition des usagers contrôlés par type (chaque type d’usager est compté avec son effectif).",
            styles["BodyText"],
        ))
        story.append(key_figures_table([
            (str(total_usagers), "Total effectifs usagers"),
            (str(nb_multi), "Localisations multi-usagers"),
        ], styles))
        story.append(Spacer(1, 5 * mm))

        # Tableau distribution
        story.append(Paragraph("Tableau 7 : Usagers contrôlés par type", styles["TableCaption"]))
        tbl_u = [["Type d’usagers", "Nombre", "Taux"]]
        for _, row in agg_usager.iterrows():
            taux_str = f"{float(row['taux']):.1%}" if pd.notna(row.get("taux")) else "n.d."
            tbl_u.append([str(row["type_usager"]), str(int(row["nb"])), taux_str])
        story.append(ofb_table(
            tbl_u,
            col_widths=[avail_w * 0.58, avail_w * 0.21, avail_w * 0.21],
            col_aligns=["LEFT", "RIGHT", "RIGHT"],
        ))
        story.append(Spacer(1, 5 * mm))

        # Graphique
        pie_data = {str(r["type_usager"])[:40]: int(r["nb"]) for _, r in agg_usager.iterrows()}
        if pie_data:
            pie_path = chart_pie(pie_data, "Usagers contrôlés par type", tmp_dir, "pie_usagers.png")
            from PIL import Image as PILImage
            from reportlab.platypus import Image as RLImage
            _pimg = PILImage.open(pie_path)
            _target_w = avail_w * chart_ratios["global_usagers_pie"]
            _target_h = _target_w * (_pimg.height / _pimg.width)
            _pimg.close()
            story.append(RLImage(pie_path, width=_target_w, height=_target_h))
        story.append(Spacer(1, 4 * mm))

        # Carte (si générée par le générateur cartographique)
        carte_usagers = get_cartes_dir() / "carte_global_usagers.png"
        if carte_usagers.exists():
            story.append(Paragraph("Carte : Usagers contrôlés par types", styles["Heading2"]))
            img = RLImage(str(carte_usagers), width=avail_w, height=avail_w * 0.65)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 3 * mm))

        # Tableau croisé Usagers × Domaine
        if cross_usager_dom is not None and not cross_usager_dom.empty:
            story.append(Paragraph("Tableau 8 : Usagers × Domaine (contrôles)", styles["TableCaption"]))
            domain_cols = [c for c in cross_usager_dom.columns if c != "type_usager"]
            header = ["Type d’usagers"] + [str(c)[:22] for c in domain_cols]
            tbl_cross = [header]
            for _, row in cross_usager_dom.iterrows():
                tbl_cross.append([str(row["type_usager"])] + [str(int(row[c])) for c in domain_cols])
            # Largeur colonnes : 28% pour le libellé, le reste réparti
            other_w = (avail_w * 0.72) / max(1, len(domain_cols))
            col_widths = [avail_w * 0.28] + [other_w] * len(domain_cols)
            col_aligns = ["LEFT"] + ["RIGHT"] * len(domain_cols)
            story.append(ofb_table(tbl_cross, col_widths=col_widths, col_aligns=col_aligns))

    story.append(PageBreak())

    # Annexes
    story.append(Paragraph('<a name="sec7"/>VII. Annexes', styles["Heading1"]))
    story.append(Paragraph("Méthodologie", styles["Heading2"]))
    methodo = (
        f"<b>Période :</b> du {DATE_DEB.date():%d/%m/%Y} au {DATE_FIN.date():%d/%m/%Y}.<br/>"
        f"<b>Périmètre :</b> département de la Côte-d'Or (21).<br/>"
        "<b>Sources :</b> OSCEAN (points de contrôle, PEJ, PA) et PVe OFB.<br/>"
        f"<b>Ventilation temporelle :</b> {resolve_ventilation_mode_global(DATE_DEB, DATE_FIN)} "
        f"(seuil {VENTILATION_SEUIL_JOURS_GLOBAL} jours en mode auto).<br/>"
        "Aucun filtre sur domaine ou thème ; tous NATINF pour PEJ et PVe.<br/>"
        "<b>Types d’usagers :</b> issus du champ OSCEAN <i>type_usager</i> des points de contrôle ; "
        "catégorie « dominante » par contrôle via le mapping ref/types_usagers.csv."
    )
    story.append(Paragraph(methodo, styles["BodyText"]))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Glossaire", styles["Heading2"]))
    glossaire = [
        ["Abr\u00e9viation", "Signification"],
        ["DC", "Dossier de contr\u00f4le"],
        ["NATINF", "Nature d'infraction (nomenclature nationale)"],
        ["OSCEAN", "Outil de suivi des contr\u00f4les en environnement (application nationale)"],
        ["PA", "Proc\u00e9dure administrative"],
        ["PEJ", "Proc\u00e9dure d'enqu\u00eate judiciaire"],
        ["PVe", "Proc\u00e8s-verbal \u00e9lectronique"],
        ["PNF", "Parc national de for\u00eats"],
    ]
    story.append(ofb_table(glossaire, col_widths=[avail_w * 0.25, avail_w * 0.75], col_aligns=["LEFT", "LEFT"]))

    doc.build(story)


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
        if not point.empty:
            point = enrich_with_pnforet_sig_zones(
                point, root, context="bilan global — points de contrôle", log=spatial_log
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
            elif ventilation_mode == "trimestrielle":
                analyse_trimestrielle_global(point, pa, pej, pve, out_dir)
            else:
                # Mode globale : pas de ventilation temporelle
                pd.DataFrame(columns=[
                    "periode",
                    "nb_controles",
                    "nb_controles_non_conformes",
                    "taux_infraction_controles",
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
