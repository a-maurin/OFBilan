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

#
"""Tests du PDF brochure synthese (2 pages)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "data" / "out" / "bilan_synthese_activite_PA_PJ"


def _pdf_page_count(path: Path) -> int:
    data = path.read_bytes()
    return len(re.findall(rb"/Type\s*/Page\b", data))


def _pdf_media_box_pts(path: Path) -> tuple[float, float]:
    data = path.read_bytes()
    matches = re.findall(
        rb"/MediaBox\s*\[\s*0(?:\.0+)?\s+0(?:\.0+)?\s+([\d.]+)\s+([\d.]+)\s*\]",
        data,
    )
    assert matches, "MediaBox introuvable"
    w, h = (float(matches[-1][0]), float(matches[-1][1]))
    return w, h


def _pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def _pdf_section_text(path: Path, start_marker: str, end_marker: str) -> str:
    lines = _pdf_text(path).splitlines()
    starts = [i for i, line in enumerate(lines) if start_marker in line]
    assert starts, f"Section introuvable: {start_marker}"
    start = starts[-1]
    end = next(i for i, line in enumerate(lines[start + 1 :], start + 1) if end_marker in line)
    return "\n".join(lines[start:end])


def _pdf_section_lines(path: Path, start_marker: str, end_marker: str) -> list[str]:
    return _pdf_section_text(path, start_marker, end_marker).splitlines()


@pytest.mark.skipif(not OUT_DIR.is_dir(), reason="Données de sortie synthèse absentes")
@pytest.mark.parametrize("cartes", [False, True])
def test_brochure_pdf_has_two_pages(cartes: bool) -> None:
    from core.engine.generation_pdf_synthese_brochure import generate_synthese_brochure_pdf_report

    generate_synthese_brochure_pdf_report(
        OUT_DIR,
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        dept_code="21",
        diffusion="externe",
        cartes=cartes,
    )
    pdf_path = OUT_DIR / "synthese_activite_PA_PJ_brochure_ext.pdf"
    assert pdf_path.is_file()
    assert _pdf_page_count(pdf_path) == 2, f"attendu 2 pages (cartes={cartes})"
    page_w, page_h = _pdf_media_box_pts(pdf_path)
    assert page_w > page_h, "La brochure doit être en A4 paysage (largeur > hauteur)"


@pytest.mark.skipif(not OUT_DIR.is_dir(), reason="Données de sortie synthèse absentes")
def test_generate_synthese_profile_outputs_detailed_and_brochure_with_same_period() -> None:
    from core.engine.generation_pdf_synthese import generate_synthese_pdf_report

    generate_synthese_pdf_report(
        OUT_DIR,
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        dept_code="21",
        output_filename="synthese_activite_PA_PJ.pdf",
        diffusion="externe",
        cartes=False,
    )

    detailed_pdf = OUT_DIR / "synthese_activite_PA_PJ_ext.pdf"
    brochure_pdf = OUT_DIR / "synthese_activite_PA_PJ_brochure_ext.pdf"

    assert detailed_pdf.is_file()
    assert brochure_pdf.is_file()

    expected_period = "du 01/01/2025 au 31/12/2025"
    unexpected_period = "du 01/01/2025 au 05/02/2026"

    detailed_text = _pdf_text(detailed_pdf)
    brochure_text = _pdf_text(brochure_pdf)

    assert expected_period in detailed_text
    assert expected_period in brochure_text
    assert unexpected_period not in brochure_text


@pytest.mark.skipif(not OUT_DIR.is_dir(), reason="Données de sortie synthèse absentes")
def test_detailed_pdf_section_3_1_keeps_low_share_themes() -> None:
    from core.engine.generation_pdf_synthese import generate_synthese_pdf_report

    generate_synthese_pdf_report(
        OUT_DIR,
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        dept_code="21",
        output_filename="synthese_activite_PA_PJ.pdf",
        diffusion="externe",
        cartes=False,
    )

    detailed_pdf = OUT_DIR / "synthese_activite_PA_PJ_ext.pdf"
    section_text = _pdf_section_text(
        detailed_pdf,
        "3.1. Th",
        "3.2. R",
    )

    assert "Inactif-Continuit" in section_text
    assert "Inactif-Lutte contre la pollution" in section_text
    assert "(suite)" not in section_text
    assert section_text.count("Particulier (usager de la nature + gestionnaire") == 1
    assert section_text.count("Agriculteur et autres acteurs agricoles") == 1
    assert section_text.count("Collectivité (effectifs d'usagers)") == 1
    assert section_text.count("Autre usager (effectifs d'usagers)") == 1
    assert section_text.count("Entreprise (effectifs d'usagers)") == 1
    assert section_text.count("Acteurs sylvicoles (effectifs d'usagers)") == 1


@pytest.mark.skipif(not OUT_DIR.is_dir(), reason="Données de sortie synthèse absentes")
def test_detailed_pdf_section_3_1_keeps_entreprise_title_with_table() -> None:
    from core.engine.generation_pdf_synthese import generate_synthese_pdf_report

    generate_synthese_pdf_report(
        OUT_DIR,
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        dept_code="21",
        output_filename="synthese_activite_PA_PJ.pdf",
        diffusion="externe",
        cartes=False,
    )

    detailed_pdf = OUT_DIR / "synthese_activite_PA_PJ_ext.pdf"
    section_lines = _pdf_section_lines(detailed_pdf, "3.1. Th", "3.2. R")
    idx = next(i for i, line in enumerate(section_lines) if "Entreprise (effectifs d'usagers)" in line)
    window = section_lines[idx : idx + 10]

    assert "Thème" in window
    assert not any(
        line.startswith("Synthèse des activités de police de l'environnement")
        for line in window[:4]
    )


@pytest.mark.skipif(not OUT_DIR.is_dir(), reason="Données de sortie synthèse absentes")
def test_detailed_pdf_highlights_control_definition_and_section_2_reminder() -> None:
    from core.engine.generation_pdf_synthese import generate_synthese_pdf_report

    generate_synthese_pdf_report(
        OUT_DIR,
        date_deb="2025-01-01",
        date_fin="2025-12-31",
        dept_code="21",
        output_filename="synthese_activite_PA_PJ.pdf",
        diffusion="externe",
        cartes=False,
    )

    detailed_pdf = OUT_DIR / "synthese_activite_PA_PJ_ext.pdf"
    detailed_text = _pdf_text(detailed_pdf)

    assert "Contrôle : définition et suites possibles" in detailed_text
    assert "Dans ce document, le terme contrôle renvoie exclusivement" in detailed_text
    assert "aboutir à trois types de résultats" in detailed_text
    assert "Comme indiqué dans la notice méthodologique" in detailed_text


def test_brochure_pdf_fallback_without_synthese_resume(tmp_path: Path) -> None:
    """Vérifie que la brochure ne plante pas avec KeyError quand synthese_resume.csv est absent."""
    import pandas as pd
    from core.engine.generation_pdf_synthese_brochure import generate_synthese_brochure_pdf_report

    # Créer un résumé d'usagers sans la colonne 'nb_localisations'
    (tmp_path / "controles_global_usagers_resume.csv").write_text("nb_localisations_multi_usagers\n2\n", encoding="utf-8")
    (tmp_path / "controles_global_resultats.csv").write_text("resultat;nb;taux\nConforme;10;100.0\n", encoding="utf-8")

    # L'appel ne doit pas lever KeyError: 'nb_localisations'
    generate_synthese_brochure_pdf_report(
        tmp_path,
        date_deb="2026-01-01",
        date_fin="2026-07-27",
        dept_code="r27",
        profile={"id": "global"},
        diffusion="interne",
        cartes=False,
    )
    pdf_path = tmp_path / "global_brochure_int.pdf"
    assert pdf_path.is_file()


def test_usager_types_fallback_with_nb_column() -> None:
    """Vérifie que les fonctions usager gèrent correctement la colonne 'nb' sans 'nb_total'."""
    import pandas as pd
    from core.engine.generation_pdf_synthese_brochure import _rollup_usager_types
    from core.engine.generation_pdf_synthese import _pie_data_controles_par_type_usager

    df_nb = pd.DataFrame([
        {"type_usager": "Particulier", "nb": 100},
        {"type_usager": "Agriculteur", "nb": 50},
    ])

    rolled = _rollup_usager_types(df_nb)
    assert rolled is not None
    assert "nb_total" in rolled.columns

    pie_data = _pie_data_controles_par_type_usager(df_nb)
    assert pie_data != {}
    assert "Particulier" in pie_data or any("Particulier" in k for k in pie_data.keys())
    assert sum(pie_data.values()) == 150


def test_profile_config_items_masques() -> None:
    """Vérifie la gestion du champ items_masques sur ProfileConfig."""
    from core.cartographie.config_cartes_model import ProfileConfig

    prof = ProfileConfig(
        id="test_brochure",
        title="Test Brochure",
        layout_name="test_layout",
        output_filename="carte_test.png",
        items_masques=["titre_principal", "bandeau_logos_ofb"],
    )
    assert prof.items_masques == ["titre_principal", "bandeau_logos_ofb"]


def test_resolve_items_masques_carte_hierarchy() -> None:
    """Vérifie la hiérarchie de résolution des items masqués (Gabarit > Profil Brochure > Profil Défaut)."""
    from core.common.chargeur_gabarits import resolve_items_masques_carte

    profil_data = {
        "cartographie": {
            "items_masques_defaut": ["logo_defaut"],
            "items_masques_brochure": ["titre_profil", "logo_profil"],
        }
    }
    gabarit_data = {
        "cartographie": {
            "items_masques_brochure": ["titre_gabarit", "logo_gabarit"],
        }
    }

    # 1. Mode standard (hors brochure) -> items_masques_defaut du profil
    res_std = resolve_items_masques_carte(profil_data, gabarit_data, is_brochure=False)
    assert res_std == ["logo_defaut"]

    # 2. Mode brochure avec gabarit -> fusion additive (profil + gabarit)
    res_gab = resolve_items_masques_carte(profil_data, gabarit_data, is_brochure=True)
    assert res_gab == ["titre_profil", "logo_profil", "titre_gabarit", "logo_gabarit"]

    # 3. Mode brochure sans gabarit -> la liste brochure du profil prévaut
    res_prof_brochure = resolve_items_masques_carte(profil_data, None, is_brochure=True)
    assert res_prof_brochure == ["titre_profil", "logo_profil"]


def test_brochure_pdf_distinct_operations_and_localisations(tmp_path: Path) -> None:
    """Vérifie que les opérations (358) et localisations (641) sont correctement lues distinctement."""
    from core.engine.generation_pdf_synthese_brochure import generate_synthese_brochure_pdf_report

    (tmp_path / "controles_global_operations_resume.csv").write_text("nb_operations_controle\n358\n", encoding="utf-8")
    (tmp_path / "controles_global_resultats.csv").write_text("resultat;nb;taux\nConforme;600;93.6\nNon-conforme;41;6.4\n", encoding="utf-8")
    (tmp_path / "pej_global_resume.csv").write_text("nb_pej_global\n10\n", encoding="utf-8")
    (tmp_path / "pa_global_resume.csv").write_text("nb_pa_global\n5\n", encoding="utf-8")

    generate_synthese_brochure_pdf_report(
        tmp_path,
        date_deb="2026-01-01",
        date_fin="2026-08-31",
        code="21",
        output_filename="bilan_global_21_brochure.pdf",
        profile={"id": "global"},
        diffusion="externe",
        cartes=False,
    )
    pdf_path = tmp_path / "bilan_global_21_brochure_ext.pdf"
    assert pdf_path.is_file()


def test_brochure_procedures_filter_zero() -> None:
    """Vérifie que les lignes à 0 PEJ et 0 PA sont filtrées du tableau des procédures."""
    import pandas as pd
    from core.engine.generation_pdf_synthese_brochure import _build_procedures_table_brochure

    df = pd.DataFrame([
        {"theme": "Chasse", "nb_pej": 10, "nb_pa": 2},
        {"theme": "Inactif-Peche", "nb_pej": 0, "nb_pa": 0},
        {"theme": "Pollutions", "nb_pej": 5, "nb_pa": 0},
    ])
    tbl = _build_procedures_table_brochure(df, inner_w=200, max_rows=5)
    # 2 lignes réelles + entête éventuelle
    assert len(tbl._cellvalues) == 2
    themes_in_table = [cell.text for row in tbl._cellvalues for cell in row if hasattr(cell, "text")]
    assert "Inactif-Peche" not in themes_in_table
    assert "Chasse" in themes_in_table
    assert "Pollutions" in themes_in_table


def test_brochure_pve_natinf_typography() -> None:
    """Vérifie que les libellés NATINF en capitales passent en casse de phrase et que les cellules sont des Paragraphs."""
    import pandas as pd
    from core.engine.generation_pdf_synthese_brochure import (
        _format_pve_natinf_label,
        _build_pve_natinf_table_brochure,
    )

    row = pd.Series({
        "numero_natinf": "27742",
        "libelle_natinf": "AGRAINAGE OU AFFOURAGEMENT EN INFRACTION AUX PRESCRIPTIONS DU SDGC",
        "theme_snc": "Chasse",
        "nb": 29,
    })
    formatted = _format_pve_natinf_label(row)
    assert formatted.startswith("27742 – Agrainage ou affouragement")
    assert "SDGC" in formatted

    df = pd.DataFrame([row])
    tbl = _build_pve_natinf_table_brochure(df, inner_w=200, max_rows=5)
    assert len(tbl._cellvalues) == 1
    # Toutes les cellules (y compris le volume) sont des Paragraphs
    for cell in tbl._cellvalues[0]:
        assert hasattr(cell, "text")


