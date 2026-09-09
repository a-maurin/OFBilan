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

import pandas as pd
from reportlab.platypus import Table
from core.common.pdf_report_builder import PDFReportBuilder
from core.engine.generation_pdf_synthese_brochure import (
    _build_treemap_placeholder_banner,
    _build_matrice_themes_table,
)


def test_build_treemap_placeholder_banner(tmp_path):
    pdf_file = tmp_path / "test.pdf"
    builder = PDFReportBuilder(pdf_path=pdf_file, header_title="Test Header", title="Test Treemap Banner")
    banner = _build_treemap_placeholder_banner(builder, 200.0)
    assert banner is not None
    assert banner.box_width == 200.0


def test_build_matrice_themes_table_empty():
    tbl = _build_matrice_themes_table(None, 200.0)
    assert isinstance(tbl, Table)


def test_build_matrice_themes_table_with_data():
    df = pd.DataFrame([
        {"theme": "Police de la chasse", "nb_pa": 0, "nb_pej": 8, "nb_pve": 18, "nb_total": 26},
        {"theme": "Qualité de l'eau", "nb_pa": 8, "nb_pej": 21, "nb_pve": 0, "nb_total": 29},
        {"theme": "Faune sauvage captive", "nb_pa": 0, "nb_pej": 0, "nb_pve": 0, "nb_total": 0},
    ])
    tbl = _build_matrice_themes_table(df, 200.0)
    assert isinstance(tbl, Table)


def test_generate_synthese_brochure_pdf_report_gabarit_srp_r27(tmp_path):
    from core.engine.generation_pdf_synthese_brochure import generate_synthese_brochure_pdf_report
    generate_synthese_brochure_pdf_report(
        tmp_path,
        gabarit="srp_r27",
        cartes=False,
    )
    generated_pdf = tmp_path / "synthese_activite_PA_PJ_brochure_ext.pdf"
    assert generated_pdf.exists()
    assert generated_pdf.stat().st_size > 0


def test_generate_profile_pdf_report_brochure_routing(tmp_path):
    from core.engine.generation_pdf_profil import generate_profile_pdf_report
    profile = {"id": "global", "presentation_scope": "global"}
    date_deb = pd.Timestamp("2025-01-01")
    date_fin = pd.Timestamp("2025-12-31")
    generate_profile_pdf_report(
        tmp_path,
        profile=profile,
        date_deb=date_deb,
        date_fin=date_fin,
        echelle="departement",
        code="21",
        cartes=False,
        diffusion="interne",
        cli_options={"gabarit": "srp_r27"},
    )
    generated_pdf = tmp_path / "global_brochure_int.pdf"
    assert generated_pdf.exists()
    assert generated_pdf.stat().st_size > 0


def test_brochure_resultat_pastilles():
    from core.engine.generation_pdf_synthese_brochure import BrochureResultatPastilles
    widget = BrochureResultatPastilles(200.0, 549, 90, 3, 7)
    assert widget.height == 70.0


def test_brochure_badges_suites():
    from core.engine.generation_pdf_synthese_brochure import BrochureBadgesSuites
    widget = BrochureBadgesSuites(200.0, 11, 37, 44)
    assert widget.height == 100.0


def test_load_annuaire_contact():
    from core.engine.generation_pdf_synthese_brochure import _load_annuaire_contact
    line1, line2 = _load_annuaire_contact("region", "27")
    assert "Office français de la biodiversité" in line1
    assert "Bourgogne-Franche-Comté" in line1
    assert "Dijon" in line2


def test_build_matrice_themes_table_srp_other_row():
    from core.engine.generation_pdf_synthese_brochure import _build_matrice_themes_table_srp
    data = [{"theme": f"Thème {i}", "nb_pa": 1, "nb_pej": 2, "nb_pve": 3, "nb_total": 6} for i in range(15)]
    df = pd.DataFrame(data)
    tbl = _build_matrice_themes_table_srp(df, 200.0, max_top_rows=10)
    assert isinstance(tbl, Table)


def test_format_perimetre_and_title_lines_srp_r27():
    from core.common.pdf_presentation_config import format_perimetre_title_label, build_title_lines_from_cfg

    # 1. Échelle Département (21 -> Côte-d'Or)
    lbl_dept = format_perimetre_title_label("departement", "Côte-d'Or")
    assert lbl_dept == "Département de la Côte-d'Or"

    effective_cfg_srp = {"gabarit_id": "srp_r27", "title": {"line2_mode": "fixed", "line2_fixed": "Service Régional Police – BFC"}}
    cover_lines, header_lines = build_title_lines_from_cfg(
        effective_cfg_srp,
        profile_label="global",
        perimetre_name_typo="Côte-d'Or",
        echelle="departement",
    )
    assert "Département de la Côte-d'Or" in header_lines
    assert "Service départemental de la Côte-d'Or — Service Régional Police" in header_lines

    # 2. Échelle Région (r27 -> Bourgogne-Franche-Comté)
    lbl_reg = format_perimetre_title_label("region", "Bourgogne-Franche-Comté")
    assert lbl_reg == "Région Bourgogne-Franche-Comté"

    cover_lines_reg, header_lines_reg = build_title_lines_from_cfg(
        effective_cfg_srp,
        profile_label="global",
        perimetre_name_typo="Bourgogne-Franche-Comté",
        echelle="region",
    )
    assert "Région Bourgogne-Franche-Comté" in header_lines_reg
    assert "Service Régional Police – BFC" in header_lines_reg




