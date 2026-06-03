"""Modélisation du contexte de génération PDF."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.platypus import Flowable
from bilans.common.pdf_report_builder import PDFReportBuilder

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
    
    # Paramètres de cartographie
    cartes: bool = True
    global_map_paths: list[Path] = field(default_factory=list)
    global_map_layout: str = "vertical"
    map_captions: list[str] | None = None
    map_id: str = "global"

    @property
    def profile_id(self) -> str:
        return str(self.profile.get("id", "")).strip()
    
    @property
    def scope(self) -> str:
        return str(self.profile.get("presentation_scope", "global")).strip() or "global"
