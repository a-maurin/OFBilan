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

"""
========================================================================================
MODULE : CONTEXTE DE GENERATION PDF (`pdf_context.py`)
========================================================================================
Ce module définit la classe dataclass `PdfContext` qui sert de conteneur d'état unique
transmis à l'ensemble des générateurs de sections lors de l'assemblage d'un rapport PDF.

Composants encapsulés :
  1. `builder` : l'instance active du constructeur de PDF (`PDFReportBuilder`).
  2. Configurations et paramètres d'affichage (profil, gabarit, diffusion, thèmes).
  3. Métriques et chiffres clés globaux (localisations, opérations, PEJ, PA, PVe).
  4. DataFrames de données (agrégations par domaine, thème, usager, période).
  5. Chemins et configurations d'agencement des cartes cartographiques.
========================================================================================
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.platypus import Flowable
from core.common.pdf_report_builder import PDFReportBuilder

@dataclass
class PdfContext:
    """Contexte d'exécution transmis aux fonctions de rendu des sections."""
    
    # Instance du constructeur de rapport (gère la charte, l'ajout d'éléments, etc.)
    builder: PDFReportBuilder
    
    # Configuration du profil et présentation
    profile: dict[str, Any]
    presentation_cfg: dict[str, Any]
    behavior_cfg: dict[str, Any]
    show_placeholder: bool
    
    # Dates et métadonnées
    date_deb: pd.Timestamp
    date_fin: pd.Timestamp
    dept_code: str
    dept_name_typo: str
    diffusion: str
    ventilation_mode: str
    
    # Paramètres graphiques et mise en page
    out_dir: Path
    avail_w: float
    tmp_dir: Path
    chart_bar_w: float
    legend_fontsize: float
    legend_ncol_max: int
    figure_scale: float
    ref_pie_w: float
    ref_pie_fs: float
    ref_pie_legend_fs: float
    split_by_row: bool
    tables_layout: dict[str, Any]
    
    # Titres des sections résolus
    section_title: dict[str, str]
    
    # Option annexe régionale
    annexe_detaillee: bool = False
    
    # Chiffres clés / résumé
    nb_localisations: int = 0
    nb_ops: int = 0
    nb_effectifs: int = 0
    nb_pej: int = 0
    nb_pa: int = 0
    nb_pve: int = 0
    
    # Tableaux de données (peuvent être None selon le bilan et les données existantes)
    tab_resultats: pd.DataFrame | None = None
    tab_resultats_controles: pd.DataFrame | None = None
    agg_domaine: pd.DataFrame | None = None
    agg_theme: pd.DataFrame | None = None
    act_theme: pd.DataFrame | None = None
    act_proc: pd.DataFrame | None = None
    pve_natinf: pd.DataFrame | None = None
    pej_top: pd.DataFrame | None = None
    agg_usager: pd.DataFrame | None = None
    res_usager: pd.DataFrame | None = None
    cross_usager_dom: pd.DataFrame | None = None
    usagers_resume: pd.DataFrame | None = None
    agg_periode: pd.DataFrame | None = None
    pej_dom: pd.DataFrame | None = None
    proc_summary: dict[str, Any] | None = field(default_factory=dict)
    categories_controles_df: pd.DataFrame | None = None
    categories_infractions_df: pd.DataFrame | None = None
    categories_controles_donut_path: Path | None = None
    categories_infractions_donut_path: Path | None = None
    
    # Paramètres de cartographie et gabarit
    cartes: bool = True
    global_map_paths: list[Path] = field(default_factory=list)
    global_map_layout: str = "vertical"
    map_captions: list[str] | None = None
    map_id: str = "global"
    gabarit_id: str | None = None
    layout_mode: str = "standard"

    @property
    def profile_id(self) -> str:
        return str(self.profile.get("id", "")).strip()
    
    @property
    def scope(self) -> str:
        return str(self.profile.get("presentation_scope", "global")).strip() or "global"

    def __post_init__(self) -> None:
        """Contrôle de cohérence Fail-Fast au démarrage."""
        if self.map_id and self.map_id != "global":
            from core.chemins_projet import PROJECT_ROOT
            import yaml
            cartes_path = PROJECT_ROOT / "config" / "profils_cartes.yaml"
            if cartes_path.exists():
                try:
                    cartes_cfg = yaml.safe_load(cartes_path.read_text(encoding="utf-8")) or {}
                    if self.map_id not in cartes_cfg:
                        import logging
                        logging.warning("Fail-Fast Warning: map_id '%s' absent de profils_cartes.yaml", self.map_id)
                except Exception:
                    pass

    def safe_df(self, name: str) -> pd.DataFrame:
        """Retourne le DataFrame correspondant au nom d'attribut s'il existe et est non-Nul, sinon un DataFrame vide."""
        val = getattr(self, name, None)
        if isinstance(val, pd.DataFrame) and not val.empty:
            return val
        return pd.DataFrame()