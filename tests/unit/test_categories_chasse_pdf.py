import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from core.engine.pdf_context import PdfContext
from core.engine.sections_profil import render_sec22res, render_sec3


@pytest.fixture
def mock_pdf_context(tmp_path):
    builder = MagicMock()
    builder.avail_w = 500.0
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TableCaption", parent=styles["Normal"], fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="FigureCaption", parent=styles["Normal"], fontName="Helvetica-Oblique"))
    builder.styles = styles
    builder.append_pending_paragraph = MagicMock()
    builder.add_section = MagicMock()
    builder.add_paragraph = MagicMock()
    builder.add_table = MagicMock()
    builder.add_table_and_image_keep_together = MagicMock()
    builder.add_keep_together_block = MagicMock()
    builder.add_spacer = MagicMock()

    df_ctrl = pd.DataFrame([
        {"categorie": "agrainage", "libelle": "Agrainage", "total": 10, "conforme": 8, "non_conforme": 2, "taux_non_conforme": 20.0},
        {"categorie": "securite", "libelle": "Sécurité à la chasse", "total": 20, "conforme": 15, "non_conforme": 5, "taux_non_conforme": 25.0},
        {"categorie": "autres", "libelle": "Autres infractions", "total": 30, "conforme": 25, "non_conforme": 5, "taux_non_conforme": 16.7},
    ])

    df_inf = pd.DataFrame([
        {"categorie": "agrainage", "libelle": "Agrainage", "nb_pve": 3, "nb_pej": 1, "total": 4, "pct": 20.0},
        {"categorie": "securite", "libelle": "Sécurité à la chasse", "nb_pve": 6, "nb_pej": 4, "total": 10, "pct": 50.0},
        {"categorie": "autres", "libelle": "Autres infractions", "nb_pve": 2, "nb_pej": 4, "total": 6, "pct": 30.0},
    ])

    ctx = PdfContext(
        builder=builder,
        profile={"id": "chasse", "label": "Contrôles chasse"},
        presentation_cfg={
            "blocks": {
                "sec23": {"show_categories_controles": True},
                "sec3": {"show_categories_infractions": True},
            }
        },
        behavior_cfg={},
        show_placeholder=False,
        date_deb=pd.Timestamp("2025-01-01"),
        date_fin=pd.Timestamp("2026-02-28"),
        dept_code="21",
        dept_name_typo="Côte-d'Or",
        diffusion="externe",
        ventilation_mode="globale",
        out_dir=tmp_path,
        avail_w=500.0,
        tmp_dir=tmp_path,
        chart_bar_w=400.0,
        legend_fontsize=8.0,
        legend_ncol_max=3,
        figure_scale=1.0,
        ref_pie_w=0.45,
        ref_pie_fs=1.0,
        ref_pie_legend_fs=8.0,
        split_by_row=False,
        tables_layout={},
        section_title={"sec22res": "2.3 Résultats", "sec3": "3. Procédures"},
        nb_pej=9,
        nb_pa=0,
        nb_pve=11,
        categories_controles_df=df_ctrl,
        categories_infractions_df=df_inf,
    )
    return ctx


def test_render_sec22res_with_categories(mock_pdf_context):
    render_sec22res(mock_pdf_context)
    # Vérifier que add_keep_together_block a été appelé avec le tableau des catégories
    mock_pdf_context.builder.add_keep_together_block.assert_called_once()
    block = mock_pdf_context.builder.add_keep_together_block.call_args[0][0]
    # Au moins un élément est le tableau
    assert len(block) >= 3


def test_render_sec3_with_categories(mock_pdf_context):
    render_sec3(mock_pdf_context)
    # Vérifier que add_table a été appelé pour la répartition des infractions par catégorie
    mock_pdf_context.builder.add_table.assert_called()
    found = False
    for call in mock_pdf_context.builder.add_table.call_args_list:
        args, kwargs = call
        caption = kwargs.get("caption", "")
        if "infractions par catégorie" in str(caption):
            found = True
            rows = args[0]
            assert rows[0] == ["Catégorie", "PVe", "PEJ", "Total", "Part %"]
            assert rows[-1][0] == "Total"
            break
    assert found, "Tableau de répartition des infractions non trouvé"


def test_render_sec3_without_categories_when_flag_false(mock_pdf_context):
    mock_pdf_context.presentation_cfg["blocks"]["sec3"]["show_categories_infractions"] = False
    render_sec3(mock_pdf_context)
    # Vérifier qu'aucun tableau de catégorie n'est ajouté
    for call in mock_pdf_context.builder.add_table.call_args_list:
        _, kwargs = call
        assert "infractions par catégorie" not in str(kwargs.get("caption", ""))


def test_build_categories_chasse_controles_table_brochure():
    from core.engine.generation_pdf_synthese_brochure import _build_categories_chasse_controles_table_brochure
    df = pd.DataFrame([
        {"categorie": "agrainage", "libelle": "Agrainage", "total": 12, "non_conforme": 3, "taux_non_conforme": 25.0},
        {"categorie": "securite", "libelle": "Sécurité à la chasse", "total": 24, "non_conforme": 6, "taux_non_conforme": 25.0},
    ])
    tbl = _build_categories_chasse_controles_table_brochure(df, 300.0)
    assert tbl is not None
    # Vérifie qu'il y a 2 lignes de données
    assert len(tbl._cellvalues) == 2


def test_build_hierarchical_categories_chasse_table_brochure():
    from core.engine.generation_pdf_synthese_brochure import _build_hierarchical_categories_chasse_table_brochure
    df = pd.DataFrame([
        {"categorie": "agrainage", "libelle": "Agrainage", "nb_pve": 2, "nb_pej": 1, "total": 3, "pct": 20.0},
        {"categorie": "securite", "libelle": "Sécurité à la chasse", "nb_pve": 8, "nb_pej": 4, "total": 12, "pct": 80.0},
    ])
    tbl = _build_hierarchical_categories_chasse_table_brochure(df, 300.0)
    assert tbl is not None
    # 2 catégories * 3 lignes (1 principale + 2 sous-lignes) = 6 lignes
    assert len(tbl._cellvalues) == 6
    # Première ligne = libellé catégorie principale en gras
    assert "Agrainage" in tbl._cellvalues[0][0].text
    # Deuxième ligne = PVe
    assert "PVe" in tbl._cellvalues[1][0].text
    # Troisième ligne = PEJ
    assert "PEJ" in tbl._cellvalues[2][0].text


def test_generate_synthese_brochure_pdf_with_results(tmp_path):
    from core.engine.generation_pdf_synthese_brochure import generate_synthese_brochure_pdf_report
    profile = {
        "id": "chasse",
        "label": "Contrôles chasse",
        "categories_chasse": {
            "agrainage": {"label": "Agrainage"},
            "securite": {"label": "Sécurité à la chasse"},
        },
    }
    df_ctrl = pd.DataFrame([
        {"categorie": "agrainage", "libelle": "Agrainage", "total": 12, "non_conforme": 3, "taux_non_conforme": 25.0},
    ])
    df_inf = pd.DataFrame([
        {"categorie": "agrainage", "libelle": "Agrainage", "nb_pve": 2, "nb_pej": 1, "total": 3, "pct": 100.0},
    ])
    tab_res = pd.DataFrame([
        {"resultat": "Conforme", "nb": 9},
        {"resultat": "Non-conforme", "nb": 3},
    ])
    results = {
        "nb_localisations": 12,
        "nb_operations_controle": 10,
        "nb_pej": 1,
        "nb_pa": 0,
        "nb_pve": 2,
        "tab_resultats": tab_res,
        "categories_chasse_controles": df_ctrl,
        "categories_chasse_infractions": df_inf,
    }
    out_pdf = tmp_path / "test_brochure.pdf"
    generate_synthese_brochure_pdf_report(
        tmp_path,
        profile=profile,
        date_deb="2025-05-01",
        date_fin="2026-05-30",
        echelle="departement",
        code="21",
        output_filename="test_brochure.pdf",
        cartes=False,
        results=results,
    )
    pdfs = list(tmp_path.glob("*.pdf"))
    assert len(pdfs) == 1
    assert pdfs[0].stat().st_size > 1000
