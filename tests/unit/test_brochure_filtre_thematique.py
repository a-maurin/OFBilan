# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.

from __future__ import annotations

from pathlib import Path
import pandas as pd
import pypdf
import pytest

from core.engine.generation_pdf_synthese_brochure import (
    _brochure_methodology_html,
    _generate_synthese_brochure_pdf,
)
from core.engine.orchestrateur_profils import _message_fin_generation_pdf


def test_brochure_methodology_with_thematic_filter():
    """Vérifie que la mention méthodologique inclut le filtre et exclut le PVe inactif."""
    deb = pd.Timestamp("2026-01-01")
    fin = pd.Timestamp("2026-10-23")
    
    html = _brochure_methodology_html(
        date_deb=deb,
        date_fin=fin,
        ventilation_mode="mensuelle",
        diffusion="externe",
        realisation_label="Service départemental de la Côte-d'Or",
        filter_label="Gestion quantitative de l'eau",
        nb_pve=0,
        analyse_pve=False,
    )
    assert "Données ciblées sur : <b>Gestion quantitative de l'eau</b>" in html
    assert "PVe OFB" not in html
    assert "Sources OSCEAN (points de contrôle, PEJ, PA)" in html


def test_brochure_methodology_global_standard():
    """Vérifie que la mention méthodologique standard conserve le PVe quand il est présent."""
    deb = pd.Timestamp("2026-01-01")
    fin = pd.Timestamp("2026-10-23")
    
    html = _brochure_methodology_html(
        date_deb=deb,
        date_fin=fin,
        ventilation_mode="mensuelle",
        diffusion="externe",
        realisation_label="Service départemental de la Côte-d'Or",
        filter_label=None,
        nb_pve=12,
        analyse_pve=True,
    )
    assert "Données ciblées sur" not in html
    assert "et PVe OFB" in html


def test_message_fin_generation_pdf_thematic_brochure(tmp_path: Path):
    """Vérifie que le message de fin console omet 'global' et utilise le répertoire effectif."""
    profile = {
        "id": "global",
        "label": "Gestion quantitative de l'eau",
        "presentation_scope": "filtre_thematique",
    }
    resolved_opts = {
        "brochure": True,
        "diffusion": "externe",
        "domaines": ["Gestion quantitative de l'eau"],
    }
    out_subdir = "bilan_Gestion_quantitative_de_l_eau_21"
    msg = _message_fin_generation_pdf(
        profile,
        out_subdir,
        resolved_opts=resolved_opts,
        out_dir=tmp_path / out_subdir,
    )
    assert "bilan_Gestion_quantitative_de_l_eau_21_brochure_ext.pdf" in msg
    assert "global" not in msg
    assert str(tmp_path / out_subdir) in msg


def test_message_fin_generation_pdf_thematic_complet(tmp_path: Path):
    """Vérifie que le message pour le rapport complet omet également 'global'."""
    profile = {
        "id": "global",
        "label": "Gestion quantitative de l'eau",
        "presentation_scope": "filtre_thematique",
    }
    resolved_opts = {
        "brochure": False,
        "diffusion": "externe",
        "domaines": ["Gestion quantitative de l'eau"],
    }
    out_subdir = "bilan_Gestion_quantitative_de_l_eau_21"
    msg = _message_fin_generation_pdf(
        profile,
        out_subdir,
        resolved_opts=resolved_opts,
        out_dir=tmp_path / out_subdir,
    )
    assert "bilan_Gestion_quantitative_de_l_eau_21_ext.pdf" in msg
    assert "global" not in msg


def test_brochure_pdf_header_and_title_thematic(tmp_path: Path):
    """Vérifie que la brochure générée intègre le titre thématique en page 1 et page 2."""
    profile = {
        "id": "global",
        "label": "Gestion quantitative de l'eau",
        "title_label": "Gestion quantitative de l'eau",
        "presentation_scope": "filtre_thematique",
        "analyse_PVe": False,
    }
    out_dir = tmp_path / "bilan_Gestion_quantitative_de_l_eau_21"
    out_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame([{"resultat": "Conforme", "nb": 10, "taux": 1.0}]).to_csv(
        out_dir / "controles_global_resultats.csv", sep=";", index=False
    )
    pd.DataFrame([{"theme": "Sécheresse", "nb": 10, "taux": 1.0, "nb_total": 10}]).to_csv(
        out_dir / "controles_global_par_theme.csv", sep=";", index=False
    )
    pd.DataFrame([{"type_usager": "Agriculteur", "nb": 10, "taux": 1.0, "nb_total": 10}]).to_csv(
        out_dir / "controles_global_par_usager.csv", sep=";", index=False
    )
    pd.DataFrame([{"type_usager": "Agriculteur", "Conforme": 10, "Infraction": 0, "Manquement": 0, "Total": 10}]).to_csv(
        out_dir / "controles_global_resultats_par_type_usager.csv", sep=";", index=False
    )

    _generate_synthese_brochure_pdf(
        out_dir,
        profile=profile,
        date_deb=pd.Timestamp("2026-01-01"),
        date_fin=pd.Timestamp("2026-10-23"),
        echelle="departement",
        code="21",
        output_filename="bilan_Gestion_quantitative_de_l_eau_21_brochure.pdf",
        cartes=False,
    )

    pdf_file = out_dir / "bilan_Gestion_quantitative_de_l_eau_21_brochure_ext.pdf"
    assert pdf_file.exists()

    reader = pypdf.PdfReader(str(pdf_file))
    assert len(reader.pages) == 2
    p1 = reader.pages[0].extract_text()
    p2 = reader.pages[1].extract_text()

    assert "Gestion quantitative de l'eau" in p1
    assert "Gestion quantitative de l'eau" in p2
    assert "Données ciblées sur : Gestion quantitative de l'eau" in p2
    assert "PVe OFB" not in p2


def test_resolve_profile_output_dir_thematic_filters():
    """Vérifie que resolve_profile_output_dir résout vers le dossier thématique spécialisé."""
    from core.engine.execution_lots_profils import resolve_profile_output_dir

    # Domaine
    p_dom = resolve_profile_output_dir("global", "21", cli_options={"domaines": ["Gestion quantitative de l'eau"]})
    assert p_dom.name == "bilan_Gestion_quantitative_de_l_eau_21"

    # Thème
    p_thm = resolve_profile_output_dir("global", "21", cli_options={"themes": ["Sécheresse"]})
    assert p_thm.name == "bilan_Secheresse_21"

    # Sans filtre
    p_glob = resolve_profile_output_dir("global", "21")
    assert "bilan_global_21" in p_glob.name

