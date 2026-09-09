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

from dataclasses import dataclass
from pathlib import Path
import pandas as pd
from core.engine.sections_profil import render_sec1
from core.common.pdf_report_builder import PDFReportBuilder

@dataclass
class DummyCtxH3:
    builder: PDFReportBuilder
    section_title: dict
    presentation_cfg: dict
    nb_localisations: int = 0
    nb_ops: int = 0
    nb_pej: int = 0
    nb_pa: int = 0
    nb_pve: int = 0
    tab_resultats_controles: pd.DataFrame | None = None
    tab_resultats: pd.DataFrame | None = None

def test_null_report_rendering(tmp_path: Path) -> None:
    builder = PDFReportBuilder(tmp_path / "test_null.pdf", "Bilan Test")
    ctx = DummyCtxH3(
        builder=builder,
        section_title={"sec1": "1. Synthèse de l'activité"},
        presentation_cfg={},
    )
    render_sec1(ctx)
    assert len(builder.story) > 0
