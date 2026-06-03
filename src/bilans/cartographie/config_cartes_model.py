"""
Modèle de configuration des cartes bilans agrainage / chasse-agrainage.

Ce module définit les types et dataclasses partagés entre :
- config_cartes.py (fichier de configuration effectif)
- production_cartographique.py (génération / assistant interactif)
- gui_config_cartes.py (interface graphique de configuration)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal


# Types de rendu géométrique pour les polygones
GeometryMode = Literal["polygon_fill", "polygon_centroid"]

# Types de renderer QGIS
RendererType = Literal["graduated", "categorized", "single"]

# Modes de classification pour graduated
ClassificationMode = Literal["equal_interval", "quantile", "jenks", "manual"]

# Formats de sortie
OutputFormat = Literal["png", "jpeg"]

# Source de symbologie : projet QGIS (défaut) ou YAML (legacy / override)
SymbologySource = Literal["qgis", "yaml"]


# Type de filtre attributaire (pour subset string)
FilterType = Literal[
    "pve",
    "pj",
    "point_ctrl_agrainage",
    "point_ctrl_chasse",
    "point_ctrl_piegeage",
    "point_ctrl_global",
    "point_ctrl_manquement",
    "point_ctrl_theme",
    "point_ctrl_keywords",
    "",
]


@dataclass
class LayerSymbologyConfig:
    """Configuration de symbologie pour une couche."""

    layer_name: str
    # Rôle métier pour résolution dynamique dans le projet QGIS (ex. point_controles, pej)
    layer_role: Optional[str] = None
    # qgis | yaml | None (hérite du profil / global)
    symbology_source: Optional[SymbologySource] = None
    legend_label: str = ""
    # Type de filtre (pve, pj, point_ctrl_agrainage, point_ctrl_chasse) ou "" si pas de filtre dynamique
    filter_type: FilterType = ""
    # Pour polygones : choroplèthe (remplissage) ou symboles sur centroïdes
    geometry_mode: GeometryMode = "polygon_fill"
    # Type de renderer
    renderer_type: RendererType = "graduated"
    # Champ attributaire utilisé pour la symbologie
    field: str = ""
    # Classification (pour graduated)
    classification_mode: ClassificationMode = "quantile"
    num_classes: int = 5
    # Seuils manuels si classification_mode == "manual" (ex: [0, 1, 5, 10])
    manual_breaks: Optional[List[float]] = None
    # Palette (nom QGIS ou liste de couleurs hex)
    palette: str = "Blues"  # ex: "Blues", "YlOrRd", "RdYlGn"
    # Couleur unique pour single symbol
    color_rgb: Optional[tuple] = None
    # Taille symbole (mm) pour centroïdes / points
    symbol_size_mm: float = 4.0
    # Forme pour points : circle, square, diamond, etc.
    symbol_shape: str = "circle"
    # Dict {valeur_categorie: couleur_hex} pour renderer_type=categorized — surcharge la palette cyclique
    # Ex: {"Conforme": "#2ECC71", "Infraction": "#E74C3C"}
    categories: Optional[Dict[str, str]] = None
    # Visible ou non
    visible: bool = True


@dataclass
class ProfileConfig:
    """Configuration d'un profil de carte (ex: agrainage, chasse)."""

    id: str  # ex: "agrainage", "chasse"
    title: str  # Titre historique (peut être utilisé comme valeur par défaut)
    layout_name: str  # Nom du layout dans le projet QGIS
    output_filename: str  # ex: "carte_agrainage.png"
    # Dates de période (YYYY-MM-DD) - synchronisées avec les scripts d'analyse
    date_deb: str = "2025-01-01"
    date_fin: str = "2026-02-05"
    layers: Dict[str, LayerSymbologyConfig] = field(default_factory=dict)
    # Titre principal affiché sur la carte (bandeau)
    title_main: str = ""
    # Sous-titre ou description de la période (ex: \"Campagne 2025-2026\")
    subtitle: str = ""
    # Identifiants des éléments texte dans le layout QGIS
    layout_title_item_id: str = "titre_principal"
    layout_subtitle_item_id: str = "sous_titre"
    # Pour profils par défaut : id du thème (ref_themes_ctrl) pour le filtre point_ctrl_theme
    theme_id: Optional[str] = None
    # Mots-clés bilan (filtre point_ctrl_keywords), alignés sur filter.keywords du profil YAML
    keywords: Optional[List[str]] = None
    keyword_columns: Optional[List[str]] = None
    # Source de symbologie par défaut pour les couches du profil (surchargeable par couche)
    symbology_source: SymbologySource = "qgis"
    # True = lister les couches depuis le layout QGIS (YAML layers = surcharges filtres/légende)
    layers_from_layout: bool = False
    # Groupe d'arborescence QGIS si le LayerSet de la carte est vide
    layout_layer_group: Optional[str] = None
    # Template layout_defaults.yaml (ex. carre_210, a4_paysage) ; None = auto depuis la page
    layout_defaults_ref: Optional[str] = None


@dataclass
class LayoutItemRectConfig:
    """Rectangle d'un composant layout (mm)."""

    x_mm: float = 0.0
    y_mm: float = 0.0
    width_mm: float = 0.0
    height_mm: float = 0.0


@dataclass
class LayoutLegendDefaultsConfig:
    """Légende unique alignée à droite."""

    single: bool = True
    hide_extra: bool = True
    x_mm: float = 0.0
    y_mm: float = 0.0
    width_mm: float = 0.0
    height_mm: float = 0.0


@dataclass
class LayoutLogoDefaultsConfig:
    x_mm: float = 0.0
    y_mm: float = 0.0
    width_mm: float = 0.0
    height_mm: float = 0.0
    picture_id: str = "logo_ofb_bas_droite"
    skip_if_qgis_picture: bool = True


@dataclass
class LayoutBandeauDefaultsConfig:
    y_mm: float = 0.0
    height_mm: float = 25.0
    height_max_fraction: float = 0.15
    picture_id: str = "bandeau_logos_ofb"


@dataclass
class LayoutTemplateConfig:
    """Gabarit de mise en page (page carrée agrainage ou A4 paysage SD21)."""

    page: LayoutItemRectConfig = field(default_factory=LayoutItemRectConfig)
    map: LayoutItemRectConfig = field(default_factory=LayoutItemRectConfig)
    legend: LayoutLegendDefaultsConfig = field(default_factory=LayoutLegendDefaultsConfig)
    scalebar: LayoutItemRectConfig = field(default_factory=LayoutItemRectConfig)
    logo_bas_droite: LayoutLogoDefaultsConfig = field(default_factory=LayoutLogoDefaultsConfig)
    bandeau_haut: LayoutBandeauDefaultsConfig = field(default_factory=LayoutBandeauDefaultsConfig)


@dataclass
class LayoutTitleIdsConfig:
    title_item_id: str = "titre_principal"
    subtitle_item_id: Optional[str] = "sous_titre"


@dataclass
class LayoutDefaultsRootConfig:
    """Racine layout_defaults.yaml."""

    enabled: bool = True
    default_template: str = "carre_210"
    auto_template_from_page: bool = True
    layout_title_ids: Dict[str, LayoutTitleIdsConfig] = field(default_factory=dict)
    templates: Dict[str, LayoutTemplateConfig] = field(default_factory=dict)


@dataclass
class OutputConfig:
    """Configuration des fichiers de sortie."""

    format: OutputFormat = "png"
    dpi: int = 300
    page_size: str = "A4"
    orientation: Literal["landscape", "portrait"] = "landscape"


@dataclass
class BasemapConfig:
    """Configuration du fond de carte (tuiles XYZ/WMS)."""

    enabled: bool = True  # False = uniquement couches vectorielles


@dataclass
class PerimetreConfig:
    echelle: Literal["departement", "region", "national"] = "departement"
    code: str = "21"


@dataclass
class GlobalConfig:
    """Configuration globale du script de production cartographique."""

    # Chemin du projet QGIS utilisé pour la production cartographique.
    # Vide par défaut : résolution vers ref/programme/sig/bilans_carte.qgz.
    # Surchargeable par la variable d'environnement CARTO_PROJECT_QGIS_PATH.
    project_qgis_path: str = ""
    kit_ofb_path: str = ""
    output_dir: str = ""  # Vide = même dossier que le script (ref/)
    basemap: BasemapConfig = field(default_factory=BasemapConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    profiles: Dict[str, ProfileConfig] = field(default_factory=dict)
    # qgis = symbologies du projet ; yaml = écraser via symbologies.yaml (mode legacy)
    symbology_source: SymbologySource = "qgis"
    # Paramètres métier pour les filtres attributaires
    natinf_pve: List[int] = field(default_factory=lambda: [27742])
    natinf_pj: List[int] = field(default_factory=lambda: [27742, 25001])
    perimetre: PerimetreConfig = field(default_factory=PerimetreConfig)
    chasse_theme_value: str = "Chasse"
    # Mots-clés pour le filtre contrôles piégeage (nom_dossie / theme / type_actio)
    piegeage_keywords: List[str] = field(default_factory=lambda: ["piégeage", "piège"])

