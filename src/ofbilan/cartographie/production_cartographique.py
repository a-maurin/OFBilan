#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Génération des cartes bilans agrainage / chasse-agrainage.
À exécuter avec l'interpréteur Python de QGIS (pyqgis).

Référence de présentation : la carte dans data/out/bilan_agrainage/bilan_agrainage_Cote_dOr.pdf (section V. Cartographie).
Le layout QGIS doit reproduire cette présentation (bandeau titre, carte, légende, échelle, pied de page).

Usage:
  # Interface graphique : sélectionner les couches et paramétrer la symbologie
  python production_cartographique.py --gui

  # Mode interactif (CLI) : configurer la symbologie puis l'enregistrer
  python production_cartographique.py --interactive [agrainage|chasse|tous]

  # Mode non interactif : générer les cartes avec la config enregistrée
  python production_cartographique.py [agrainage|chasse|piegeage|tous]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Dossier du module cartographie (src/ofbilan/cartographie)
SCRIPT_DIR = Path(__file__).resolve().parent
PARAM_DIR = SCRIPT_DIR / "param"
PROFILS_CARTES_YAML = PARAM_DIR / "profils_cartes.yaml"
SYMBOLOGIES_YAML = PARAM_DIR / "symbologies.yaml"

# Logger principal du module
logger = logging.getLogger(__name__)
if not logger.handlers:
    _log_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=_log_fmt, datefmt="%H:%M:%S")

PROJECT_ROOT = SCRIPT_DIR.parents[2]
OUT_DIR_CARTES = PROJECT_ROOT / "data" / "out" / "generateur_de_cartes"
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from ofbilan.chemins_projet import get_qgis_project_path

_DEFAULT_QGIS_PROJECT = get_qgis_project_path()


def _load_ref_themes_ctrl_safe(root: Path) -> list:
    """Charge ref_themes_ctrl (bilans ou contexte QGIS legacy)."""
    try:
        from ofbilan.common.chargeurs_donnees import load_ref_themes_ctrl

        return load_ref_themes_ctrl(root)
    except Exception as exc:
        logger.debug("Chargeur bilans ref_themes_ctrl : %s", exc)
    try:
        from common.loaders import load_ref_themes_ctrl

        return load_ref_themes_ctrl(root)
    except Exception as exc:
        logger.warning("ref_themes_ctrl indisponible : %s", exc)
        return []


def _resolve_qgis_project_path(configured: str) -> str:
    """Return a valid QGIS project path, checking env var > configured > default."""
    env = os.getenv("CARTO_PROJECT_QGIS_PATH", "").strip()
    if env:
        return env
    if configured and Path(configured).exists():
        return configured
    if _DEFAULT_QGIS_PROJECT.exists():
        return str(_DEFAULT_QGIS_PROJECT)
    return configured or str(_DEFAULT_QGIS_PROJECT)

try:
    from qgis.core import (
        Qgis,
        QgsApplication,
        QgsProject,
        QgsVectorLayer,
        QgsFeatureRequest,
        QgsFillSymbol,
        QgsMarkerSymbol,
        QgsSingleSymbolRenderer,
        QgsGraduatedSymbolRenderer,
        QgsCategorizedSymbolRenderer,
        QgsRendererCategory,
        QgsLayoutExporter,
        QgsLayoutItemLabel,
        QgsLayoutItemLegend,
        QgsLayoutItemMap,
        QgsLayoutItemPicture,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsStyle,
        QgsWkbTypes,
        QgsCentroidFillSymbolLayer,
        QgsField,
        QgsPointClusterRenderer,
        QgsProperty,
        QgsFontMarkerSymbolLayer,
        QgsSymbolLayer,
    )
    from qgis.core import QgsLayerTreeLayer, QgsLayerTreeGroup
    from qgis.PyQt.QtGui import QColor
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False


def _check_qgis() -> None:
    if not HAS_QGIS:
        logger.error(
            "PyQGIS non disponible. Ce script doit être exécuté avec l'interpréteur Python de QGIS.\n"
            "Solutions recommandées (Windows OSGeo4W):\n"
            "  1. Lancer scripts/windows/generer_cartes.bat\n"
            "  2. Ouvrir le shell OSGeo4W (menu Démarrer), puis:\n"
            "     set PYTHONPATH=%OSGEO4W_ROOT%\\apps\\qgis-ltr\\python\n"
            "     python src\\bilans\\cartographie\\production_cartographique.py --interactive\n"
            "  3. Depuis QGIS : Outils > Console Python > coller et exécuter le script\n"
        )
        sys.exit(1)


def _load_profiles_from_param() -> Optional[tuple[Dict[str, "ProfileConfig"], str]]:
    """
    Charge les profils depuis param/profils_cartes.yaml (et param/symbologies.yaml si présent).
    Retourne (dict id_profil -> ProfileConfig, symbology_source_global) ou None.
    """
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML non installé : profils_cartes.yaml ignoré, utilisation de config_cartes.py.")
        return None

    # Chargement du socle commun par défaut (contient le bloc default)
    data_defaults = {}
    if PROFILS_CARTES_YAML.exists():
        try:
            with open(PROFILS_CARTES_YAML, "r", encoding="utf-8") as f:
                data_defaults = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Erreur lecture param/profils_cartes.yaml : %s", e)

    # Chargement de la configuration utilisateur facultative (config/profils_cartes.yaml)
    user_yaml = PROJECT_ROOT / "config" / "profils_cartes.yaml"
    data_user = {}
    if user_yaml.exists():
        try:
            with open(user_yaml, "r", encoding="utf-8") as f:
                data_user = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Erreur lecture config/profils_cartes.yaml : %s", e)

    if not data_defaults and not data_user:
        return None

    # Fusion des dictionnaires
    data = {**data_defaults, **data_user}

    symbologies: Dict[str, Dict[str, Any]] = {}
    if SYMBOLOGIES_YAML.exists():
        try:
            with open(SYMBOLOGIES_YAML, "r", encoding="utf-8") as f:
                symbologies = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Erreur lecture param/symbologies.yaml : %s", e)

    default_data = data.get("default") if isinstance(data, dict) else None
    if not default_data:
        logger.warning("Bloc 'default' introuvable dans profils_cartes.yaml")
        return None

    from config_cartes_model import (
        ProfileConfig,
        LayerSymbologyConfig,
        MapDefinition,
    )
    from typing import get_args
    from config_cartes_model import FilterType

    valid_filter_types = set(get_args(FilterType))

    def _layer_config_from_dict(
        layer_name: str, d: Dict[str, Any], symbologies_map: Dict[str, Dict[str, Any]]
    ) -> LayerSymbologyConfig:
        base: Dict[str, Any] = {}
        ref = d.get("symbology_ref")
        if ref and ref in symbologies_map:
            base = dict(symbologies_map[ref])
        for k, v in d.items():
            if k != "symbology_ref" and v is not None:
                base[k] = v
        base["layer_name"] = d.get("layer_name", layer_name)
        legend = base.get("legend_label", layer_name)
        filter_type = base.get("filter_type", "")
        if filter_type not in valid_filter_types:
            filter_type = ""
        sym_src = str(base.get("symbology_source", "")).strip().lower()
        symbology_source: Optional[str] = sym_src if sym_src in ("qgis", "yaml") else None
        raw_categories = base.get("categories")
        categories_dict: Optional[Dict[str, str]] = None
        if isinstance(raw_categories, dict):
            categories_dict = {str(k): str(v) for k, v in raw_categories.items()}
        return LayerSymbologyConfig(
            layer_name=base["layer_name"],
            layer_role=base.get("layer_role") or None,
            symbology_source=symbology_source,
            legend_label=str(legend),
            filter_type=filter_type,
            geometry_mode=base.get("geometry_mode", "polygon_fill"),
            renderer_type=base.get("renderer_type", "graduated"),
            field=base.get("field", ""),
            classification_mode=base.get("classification_mode", "quantile"),
            num_classes=int(base.get("num_classes", 5)),
            manual_breaks=base.get("manual_breaks"),
            palette=str(base.get("palette", "Blues")),
            color_rgb=tuple(base["color_rgb"]) if isinstance(base.get("color_rgb"), (list, tuple)) else None,
            symbol_size_mm=float(base.get("symbol_size_mm", 4.0)),
            symbol_shape=str(base.get("symbol_shape", "circle")),
            categories=categories_dict,
            visible=bool(base.get("visible", True)),
        )

    result: Dict[str, ProfileConfig] = {}
    global_symbology_source = "qgis"
    global_layers_from_layout = False
    global_extra_texts = {}
    if isinstance(data, dict):
        raw_default = str(data.get("symbology_source", "qgis")).strip().lower()
        if raw_default in ("qgis", "yaml"):
            global_symbology_source = raw_default
        if "layers_from_layout" in data:
            global_layers_from_layout = bool(data.get("layers_from_layout"))
        if "extra_texts" in data:
            global_extra_texts = dict(data.get("extra_texts", {}))

    # Parsing du bloc default pour la refonte (Lot 2)
    default_cartes_actives = default_data.get("cartes_actives", [])
    default_pochoir = default_data.get("pochoir", "departement")
    default_couches_vecteurs = default_data.get("couches_vecteurs_extra", [])
    
    cartes_definitions: Dict[str, MapDefinition] = {}
    defs_raw = default_data.get("cartes_definitions", {})
    for def_id, def_data in defs_raw.items():
        layers: Dict[str, LayerSymbologyConfig] = {}
        layers_raw = def_data.get("layers", {})
        for lname, lval in layers_raw.items():
            if isinstance(lval, dict):
                layers[lname] = _layer_config_from_dict(lname, lval, symbologies)
            else:
                layers[lname] = LayerSymbologyConfig(layer_name=lname, legend_label=lname)
        cartes_definitions[def_id] = MapDefinition(
            suffixe_nom=def_data.get("suffixe_nom", f"_{def_id}"),
            title_main=def_data.get("title_main", ""),
            layers=layers,
        )

    # Chargement dynamique des profils bilan pour créer les ProfileConfig fusionnés
    from ofbilan.engine.catalogue_profils import list_profiles
    from ofbilan.engine.orchestrateur_profils import load_profile_config
    
    bilan_profiles = {}
    for pid in list_profiles():
        try:
            bilan_profiles[pid] = load_profile_config(PROJECT_ROOT, pid)
        except Exception:
            pass

    for pid, pdata in bilan_profiles.items():
        if not isinstance(pdata, dict):
            continue
            
        carto_cfg = pdata.get("cartographie", {})
        
        # Sur-charges spécifiques au profil
        cartes_actives = carto_cfg.get("cartes_actives", default_cartes_actives)
        pochoir = carto_cfg.get("pochoir", default_pochoir)
        emprise = carto_cfg.get("emprise", pochoir)
        couches_extra = carto_cfg.get("couches_vecteurs_extra", default_couches_vecteurs)
        
        prof_sym_src = str(carto_cfg.get("symbology_source", global_symbology_source)).strip().lower()
        if prof_sym_src not in ("qgis", "yaml"):
            prof_sym_src = global_symbology_source
            
        prof_extra_texts = {**global_extra_texts}
        if "extra_texts" in carto_cfg and isinstance(carto_cfg["extra_texts"], dict):
            prof_extra_texts.update(carto_cfg["extra_texts"])
            
        titre_bilan = str(pdata.get("titre_bilan", pid))
        layout_name = str(carto_cfg.get("layout_name", titre_bilan))

        # Convert values to list of ints
        def _to_int_list(val) -> Optional[List[int]]:
            if val is None:
                return None
            if isinstance(val, (list, tuple)):
                out = []
                for x in val:
                    try:
                        out.append(int(x))
                    except (ValueError, TypeError):
                        pass
                return out
            if isinstance(val, (int, float)):
                return [int(val)]
            if isinstance(val, str):
                out = []
                for x in val.split(","):
                    try:
                        out.append(int(x.strip()))
                    except (ValueError, TypeError):
                        pass
                return out
            return None

        n_pve = _to_int_list(pdata.get("natinf_pve"))
        n_pj = _to_int_list(pdata.get("natinf_pj") or pdata.get("natinf_pej"))

        result[pid] = ProfileConfig(
            id=pid,
            title=titre_bilan,
            layout_name=layout_name,
            output_filename=f"carte_{pid}.png", # Será surchargé par boucle
            date_deb="2025-01-01",
            date_fin="2026-02-05",
            layers={}, # Déplacé dans cartes_definitions
            title_main="", # Déplacé dans cartes_definitions
            subtitle="",
            layout_title_item_id=str(carto_cfg.get("layout_title_item_id", "titre_principal")),
            layout_subtitle_item_id=str(carto_cfg.get("layout_subtitle_item_id", "sous_titre")),
            theme_id=pdata.get("filter", {}).get("theme_id", pid) if isinstance(pdata.get("filter"), dict) else pid,
            symbology_source=prof_sym_src,
            layers_from_layout=bool(carto_cfg.get("layers_from_layout", global_layers_from_layout)),
            layout_layer_group=carto_cfg.get("layout_layer_group") or None,
            layout_defaults_ref=carto_cfg.get("layout_defaults_ref") or None,
            extra_texts=prof_extra_texts,
            cartes_actives=cartes_actives,
            cartes_definitions=cartes_definitions,
            pochoir=pochoir,
            emprise=emprise,
            couches_vecteurs_extra=couches_extra,
            natinf_pve=n_pve,
            natinf_pj=n_pj,
        )


    # Chargement des profils définis explicitement dans les YAML (config/profils_cartes.yaml)
    _RESERVED_KEYS = {"symbology_source", "layers_from_layout", "extra_texts", "default"}
    for yaml_pid, yaml_pdata in data.items():
        if yaml_pid in _RESERVED_KEYS or not isinstance(yaml_pdata, dict) or "layers" not in yaml_pdata:
            continue
        if yaml_pid in result:
            continue  # Profil bilan déjà chargé, ne pas écraser

        yaml_layers: Dict[str, LayerSymbologyConfig] = {}
        for lname, lval in yaml_pdata.get("layers", {}).items():
            if isinstance(lval, dict):
                yaml_layers[lname] = _layer_config_from_dict(lname, lval, symbologies)
            else:
                yaml_layers[lname] = LayerSymbologyConfig(layer_name=lname, legend_label=lname)

        yaml_sym_src = str(yaml_pdata.get("symbology_source", global_symbology_source)).strip().lower()
        if yaml_sym_src not in ("qgis", "yaml"):
            yaml_sym_src = global_symbology_source

        n_pve = _to_int_list(yaml_pdata.get("natinf_pve"))
        n_pj = _to_int_list(yaml_pdata.get("natinf_pj") or yaml_pdata.get("natinf_pej"))

        result[yaml_pid] = ProfileConfig(
            id=yaml_pid,
            title=str(yaml_pdata.get("title", yaml_pid)),
            layout_name=str(yaml_pdata.get("layout_name", "")),
            output_filename=str(yaml_pdata.get("output_filename", f"carte_{yaml_pid}.png")),
            date_deb=str(yaml_pdata.get("date_deb", "2025-01-01")),
            date_fin=str(yaml_pdata.get("date_fin", "2026-02-05")),
            layers=yaml_layers,
            title_main=str(yaml_pdata.get("title_main", "")),
            subtitle=str(yaml_pdata.get("subtitle", "")),
            layout_title_item_id=str(yaml_pdata.get("layout_title_item_id", "titre_principal")),
            layout_subtitle_item_id=str(yaml_pdata.get("layout_subtitle_item_id", "sous_titre")),
            pochoir=str(yaml_pdata.get("pochoir", "departement")),
            emprise=str(yaml_pdata.get("emprise", yaml_pdata.get("pochoir", "departement"))),
            couches_vecteurs_extra=yaml_pdata.get("couches_vecteurs_extra", []),
            symbology_source=yaml_sym_src,
            natinf_pve=n_pve,
            natinf_pj=n_pj,
        )

    logger.info("Profils cartographiques fusionnés : %s", list(result.keys()))
    return result, global_symbology_source


def _resolve_departement_code(config) -> str:
    """Code département effectif : attribut direct ou perimetre.code."""
    dept = getattr(config, "departement_code", None)
    if dept:
        return str(dept).strip()
    perimetre = getattr(config, "perimetre", None)
    if perimetre is not None:
        code = getattr(perimetre, "code", None)
        if code:
            return str(code).strip()
    return "21"


def get_effective_config():
    """Retourne la config globale à utiliser : paramètres YAML si présents, sinon config_cartes.CONFIG.
    Les profils définis dans le YAML (param/profils_cartes.yaml) priment sur config_cartes.py."""
    from config_cartes import CONFIG
    from config_cartes_model import GlobalConfig

    loaded = _load_profiles_from_param()
    if loaded is not None:
        param_profiles, yaml_symbology_source = loaded
        # Le YAML est la source de vérité. config_cartes.py ne comble que les profils absents du YAML.
        for pid, prof in CONFIG.profiles.items():
            if pid not in param_profiles:
                param_profiles[pid] = prof
        sym_src = yaml_symbology_source
        if getattr(CONFIG, "symbology_source", "qgis") == "yaml":
            sym_src = "yaml"
        return GlobalConfig(
            project_qgis_path=CONFIG.project_qgis_path,
            kit_ofb_path=CONFIG.kit_ofb_path,
            output_dir=CONFIG.output_dir,
            basemap=CONFIG.basemap,
            output=CONFIG.output,
            profiles=param_profiles,
            natinf_pve=CONFIG.natinf_pve,
            natinf_pj=CONFIG.natinf_pj,
            perimetre=CONFIG.perimetre,
            departement_code=_resolve_departement_code(CONFIG),
            chasse_theme_value=CONFIG.chasse_theme_value,
            piegeage_keywords=CONFIG.piegeage_keywords,
            symbology_source=sym_src,
        )
    return CONFIG


class _ConfigExportOverride:
    """Wrapper autour de CONFIG pour surcharger departement_code et diffusion (export cartes)."""
    def __init__(self, base_config, departement_code_override: str, diffusion: str = "interne"):
        self._base = base_config
        self._dept = departement_code_override
        self._diffusion = diffusion

    def __getattr__(self, name: str):
        if name == "departement_code":
            return self._dept
        if name == "diffusion":
            return self._diffusion
        return getattr(self._base, name)


_ConfigDeptOverride = _ConfigExportOverride



def init_qgis_headless() -> None:
    """Initialise QGIS en mode headless (sans interface graphique)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
    app = QgsApplication([], False)
    app.initQgis()
    return app


def init_qgis_gui():
    """Initialise QGIS avec interface graphique (pour la GUI de configuration)."""
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
    app = QgsApplication([], True)
    app.initQgis()
    return app


def load_project(project_path: str) -> bool:
    """Charge le projet QGIS. Retourne True si succès."""
    proj = QgsProject.instance()
    res = proj.read(project_path)
    if not res:
        logger.error("Impossible de charger le projet QGIS '%s'", project_path)
        return False
    return True


def get_layer_by_name(name: str):
    """Retourne la première couche dont le nom correspond."""
    proj = QgsProject.instance()
    layers = proj.mapLayersByName(name)
    return layers[0] if layers else None


def get_project_layer_names() -> List[str]:
    """Noms des couches vectorielles/raster chargées dans le projet QGIS."""
    proj = QgsProject.instance()
    return [lyr.name() for lyr in proj.mapLayers().values()]


def resolve_layers_for_config(
    layer_key: str,
    lcfg: "LayerSymbologyConfig",
    available_names: Optional[List[str]] = None,
    date_deb: Optional[str] = None,
    date_fin: Optional[str] = None,
    dept_code: Optional[str] = None,
    profil_prefix: Optional[str] = None,
) -> list[tuple[Optional[Any], str, str]]:
    """
    Résout une couche de configuration vers une ou plusieurs couches QGIS du projet.

    Retourne une liste de (couche, nom_résolu, source_résolution).
    """
    from layer_resolver import resolve_layer_names

    names = available_names if available_names is not None else get_project_layer_names()
    from layer_resolver import infer_layer_role
    layer_role = getattr(lcfg, "layer_role", None)
    effective_role = layer_role or infer_layer_role(layer_key, lcfg.layer_name)

    resolved_infos = resolve_layer_names(
        configured_name=lcfg.layer_name,
        layer_role=layer_role,
        layer_key=layer_key,
        available_names=names,
        date_deb=date_deb,
        date_fin=date_fin,
        dept_code=dept_code,
    )

    results = []
    if not resolved_infos:
        resolved_infos = []

    for resolved_name, source in resolved_infos:
        layer = get_layer_by_name(resolved_name) if resolved_name else None
        
        # Override data source if an automatic GPKG export exists for this profile (Lot 3 - Filtrage Spatial)
        if layer and profil_prefix and layer_role != "pochoir" and layer_role != "contexte":
            from ofbilan.chemins_projet import PROJECT_ROOT
            from layer_resolver import infer_layer_role
            carto_dir = PROJECT_ROOT / "data" / "sources" / "sig" / "CARTO"
            role = layer_role or infer_layer_role(layer_key, layer.name())
            
            gpkg_path = None
            if role == "pej":
                prefixes_candidats = [profil_prefix]
                parts = profil_prefix.split('_') if profil_prefix else []
                if len(parts) >= 3:
                    prefixes_candidats.append(f"{parts[0]}_{parts[-1]}")
                if len(parts) >= 2:
                    prefixes_candidats.append(parts[0])
                
                for pref in prefixes_candidats:
                    path_cand = carto_dir / f"pej_{pref}_export_automatique.gpkg"
                    if path_cand.exists():
                        gpkg_path = path_cand
                        break
                if gpkg_path is None:
                    from ofbilan.common.chargeurs_donnees import get_points_infrac_pj_path
                    gpkg_path = get_points_infrac_pj_path(PROJECT_ROOT)
            else:
                is_pve = "pve" in layer_key.lower() or (role and "pve" in role.lower())
                is_ctrl = "controle" in layer_key.lower() or "ctrl" in layer_key.lower() or "donnees" in layer_key.lower() or (role and "controle" in role.lower())
                
                if is_pve or is_ctrl:
                    prefix_type = "pve" if is_pve else "controles"
                    # Essayer plusieurs niveaux de préfixes (spécifique -> intermédiaire -> racine)
                    prefixes_candidats = [profil_prefix]
                    parts = profil_prefix.split('_') if profil_prefix else []
                    if len(parts) >= 3:
                        prefixes_candidats.append(f"{parts[0]}_{parts[-1]}")
                    if len(parts) >= 2:
                        prefixes_candidats.append(parts[0])
                    
                    for pref in prefixes_candidats:
                        path_cand = carto_dir / f"{prefix_type}_{pref}_export_automatique.gpkg"
                        if path_cand.exists():
                            gpkg_path = path_cand
                            break

            if gpkg_path and gpkg_path.exists():
                if gpkg_path.suffix.lower() == ".gpkg":
                    uri = f"{gpkg_path}|layername={gpkg_path.stem}"
                else:
                    uri = str(gpkg_path)
                layer.setDataSource(uri, layer.name(), "ogr")
                logger.info("Source de données '%s' substituée par : %s", layer.name(), gpkg_path.name)
        
        results.append((layer, resolved_name, source))

    if (
        dept_code
        and effective_role == "pochoir"
        and (not results or not results[0][0])
    ):
        pochoir_id = "departement"
        if lcfg.layer_name and lcfg.layer_name.startswith("pochoir_"):
            if not lcfg.layer_name.startswith("pochoir_sd"):
                pochoir_id = lcfg.layer_name.replace("pochoir_", "", 1)
                
        layer, layer_name = ensure_pochoir_layer_in_project(dept_code, pochoir_id=pochoir_id)
        if layer and layer_name:
            return [(layer, layer_name, "generated")]

    if not results or not results[0][0]:
        if lcfg.layer_name == "coeur_parc" or layer_key == "coeur_parc":
            from ofbilan.common.chargeurs_donnees import get_pnf_coeur_shp_path
            from ofbilan.chemins_projet import PROJECT_ROOT
            coeur_path = get_pnf_coeur_shp_path(PROJECT_ROOT)
            if coeur_path.exists():
                layer = QgsVectorLayer(str(coeur_path), "coeur_parc", "ogr")
                if layer.isValid():
                    from qgis.core import QgsFillSymbol, QgsSingleSymbolRenderer
                    sym = QgsFillSymbol.createSimple({'color': '0,0,0,0', 'outline_color': '34,139,34', 'outline_width': '0.8'})
                    layer.setRenderer(QgsSingleSymbolRenderer(sym))
                    QgsProject.instance().addMapLayer(layer, True)
                    return [(layer, "coeur_parc", "generated")]
                else:
                    logger.error("Couche coeur_parc invalide : %s", coeur_path)
            else:
                logger.warning("Fichier coeur_parc introuvable : %s", coeur_path)

    if not results:
        return [(None, "", "missing")]

    return results


def _clone_pochoir_renderer_from_template():
    """Reprend le renderer invertedPolygon du pochoir_sd21 du projet si présent."""
    template = get_layer_by_name("pochoir_sd21")
    if template is None:
        template = get_layer_by_name("pochoir_sd21 copie")
    if template is None or not template.renderer():
        return None
    return template.renderer().clone()


def apply_pochoir_inverted_symbology(layer) -> None:
    """Symbologie masque blanc hors département (polygone inversé)."""
    renderer = _clone_pochoir_renderer_from_template()
    if renderer is not None:
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        return

    from qgis.core import QgsFillSymbol, QgsSingleSymbolRenderer, QgsInvertedPolygonRenderer
    fill_sym = QgsFillSymbol.createSimple(
        {"color": "255,255,255,255", "outline_color": "35,35,35", "outline_width": "0.26"}
    )
    inner = QgsSingleSymbolRenderer(fill_sym)
    layer.setRenderer(QgsInvertedPolygonRenderer(inner))
    layer.triggerRepaint()


def ensure_pochoir_layer_in_project(dept_code: str, pochoir_id: str = "departement") -> tuple[Optional[Any], str]:
    """
    Crée ou met à jour la couche pochoir_sd{dept} à partir de la géométrie appropriée.
    """
    if not HAS_QGIS:
        return None, ""

    from ofbilan.cartographie.pochoir_helper import (
        pochoir_cache_path,
        pochoir_layer_name,
        write_pochoir_gpkg,
        normalize_dept_code,
    )

    if pochoir_id in ("departement", "aucun"):
        layer_name = pochoir_layer_name(dept_code)
    else:
        norm_id = pochoir_id.replace("pochoir_", "", 1) if pochoir_id.startswith("pochoir_") else pochoir_id
        layer_name = f"pochoir_{norm_id}_sd{normalize_dept_code(dept_code)}"
        
    existing = get_layer_by_name(layer_name)
    cache_dir = OUT_DIR_CARTES / ".pochoir_cache"
    
    gpkg_path = cache_dir / f"{layer_name}.gpkg"
    
    if not existing or not gpkg_path.exists():
        write_pochoir_gpkg(dept_code, gpkg_path, pochoir_id=pochoir_id, project_root=PROJECT_ROOT)

    uri = f"{gpkg_path}|layername={layer_name}"
    if existing is not None:
        existing.setDataSource(uri, layer_name, "ogr")
        apply_pochoir_inverted_symbology(existing)
        existing.triggerRepaint()
        return existing, layer_name

    layer = QgsVectorLayer(uri, layer_name, "ogr")
    if not layer.isValid():
        logger.error("Couche pochoir invalide pour %s : %s", dept_code, uri)
        return None, ""

    apply_pochoir_inverted_symbology(layer)
    QgsProject.instance().addMapLayer(layer, True)
    return layer, layer_name


def apply_map_extent(layout, dept_code: str, pochoir_id: str = "departement", *, margin_ratio: float = 0.05) -> bool:
    """Ajuste l'emprise des QgsLayoutItemMap sur l'emprise demandée (département, aoa...)."""
    if not HAS_QGIS or not dept_code:
        return False
    from ofbilan.cartographie.pochoir_helper import load_pochoir_gdf
    from qgis.core import QgsRectangle

    try:
        gdf = load_pochoir_gdf(pochoir_id, dept_code, project_root=PROJECT_ROOT)
        xmin, ymin, xmax, ymax = gdf.total_bounds
        dx = xmax - xmin
        dy = ymax - ymin
        xmin -= dx * margin_ratio
        xmax += dx * margin_ratio
        ymin -= dy * margin_ratio
        ymax += dy * margin_ratio
    except (FileNotFoundError, ValueError) as exc:
        logger.warning("Emprise carte non ajustée (pochoir %s, département %s) : %s", pochoir_id, dept_code, exc)
        return False

    from qgis.core import QgsRectangle, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject
    
    rect = QgsRectangle(xmin, ymin, xmax, ymax)
    updated = False
    
    crs_src = QgsCoordinateReferenceSystem("EPSG:2154")
    
    for item in layout.items():
        if isinstance(item, QgsLayoutItemMap):
            crs_map = item.crs()
            if crs_src != crs_map:
                transform = QgsCoordinateTransform(crs_src, crs_map, QgsProject.instance())
                rect_transformed = transform.transformBoundingBox(rect)
                item.zoomToExtent(rect_transformed)
            else:
                item.zoomToExtent(rect)
            updated = True
    if updated:
        logger.info("Emprise carte ajustée au département %s", dept_code)
    return updated


def adapt_profile_texts_for_department(prof: "ProfileConfig", dept_code: str) -> "ProfileConfig":
    """Substitue Côte-d'Or / SD21 dans les titres par le département courant."""
    from dataclasses import replace

    from ofbilan.cartographie.pochoir_helper import adapt_text_for_department
    from ofbilan.common.utilitaires_metier import get_dept_name

    dept_name = get_dept_name(dept_code)
    title = adapt_text_for_department(getattr(prof, "title", "") or "", dept_code, dept_name)
    title_main = adapt_text_for_department(
        getattr(prof, "title_main", "") or "", dept_code, dept_name
    )
    subtitle = adapt_text_for_department(getattr(prof, "subtitle", "") or "", dept_code, dept_name)
    if title == prof.title and title_main == prof.title_main and subtitle == prof.subtitle:
        return prof
    return replace(prof, title=title, title_main=title_main, subtitle=subtitle)


def get_layout_by_name(layout_name: str):
    """Retourne le layout QGIS ou None."""
    if not HAS_QGIS:
        return None
    return QgsProject.instance().layoutManager().layoutByName(layout_name)


def _collect_layer_names_from_tree_group(group_name: str) -> List[str]:
    root = QgsProject.instance().layerTreeRoot()
    group = None
    for node in root.findGroups():
        if isinstance(node, QgsLayerTreeGroup) and node.name().lower() == group_name.lower():
            group = node
            break
    if group is None:
        return []
    names: List[str] = []
    for node in group.findLayers():
        if not node.isVisible():
            continue
        lyr = node.layer()
        if lyr:
            names.append(lyr.name())
    return names


def _collect_layer_names_from_legend(layout) -> List[str]:
    names: List[str] = []

    def _walk(node):
        if isinstance(node, QgsLayerTreeLayer):
            lyr = node.layer()
            if lyr and node.isVisible():
                names.append(lyr.name())
        elif hasattr(node, "children"):
            for child in node.children():
                _walk(child)

    for item in layout.items():
        if not isinstance(item, QgsLayoutItemLegend):
            continue
        model = item.model()
        if model is None:
            continue
        root_group = model.rootGroup()
        if root_group is not None:
            _walk(root_group)
    return names


def discover_layout_layer_names(prof: "ProfileConfig", layout=None) -> List[str]:
    """
    Découvre les noms de couches associés au layout du profil.

    Ordre : LayerSet carte → légende layout → layout_layer_group → visibles métier.
    """
    from layout_layers import filter_operational_layer_names, is_operational_layer

    if layout is None:
        layout = get_layout_by_name(prof.layout_name)
    if layout is None:
        logger.warning("Layout '%s' introuvable pour la découverte des couches.", prof.layout_name)
        return []

    discovered: List[str] = []

    for item in layout.items():
        if isinstance(item, QgsLayoutItemMap):
            try:
                if item.keepLayerSet() and item.layers():
                    discovered.extend(lyr.name() for lyr in item.layers() if lyr)
            except Exception as exc:
                logger.debug("Lecture LayerSet layout '%s': %s", prof.layout_name, exc)

    if not discovered:
        discovered.extend(_collect_layer_names_from_legend(layout))

    group_name = getattr(prof, "layout_layer_group", None)
    if not discovered and group_name:
        discovered.extend(_collect_layer_names_from_tree_group(group_name))

    if not discovered:
        proj = QgsProject.instance()
        root = proj.layerTreeRoot()
        for node in root.findLayers():
            if not node.isVisible():
                continue
            lyr = node.layer()
            if lyr and is_operational_layer(lyr.name()):
                discovered.append(lyr.name())

    operational = filter_operational_layer_names(discovered)
    logger.info(
        "Layout '%s' : %d couche(s) métier découverte(s)%s",
        prof.layout_name,
        len(operational),
        f" (groupe '{group_name}')" if group_name and operational else "",
    )
    return operational


def resolve_profile_layers(prof: "ProfileConfig", layout=None) -> Dict[str, "LayerSymbologyConfig"]:
    """Couches à traiter pour un profil (liste YAML ou découverte layout)."""
    from layout_layers import build_layer_configs_from_names

    if getattr(prof, "layers_from_layout", False):
        names = discover_layout_layer_names(prof, layout=layout)
        if not names:
            logger.warning(
                "Mode layout-driven : aucune couche découverte pour '%s', repli sur YAML.",
                prof.id,
            )
            return dict(prof.layers)
        return build_layer_configs_from_names(names, prof, prof.layers)
    return dict(prof.layers)


def get_layer_fields(layer) -> List[Dict[str, Any]]:
    """Retourne la liste des champs de la couche avec nom et type."""
    if not layer:
        return []
    fields = layer.fields()
    return [
        {"name": f.name(), "type": f.typeName(), "type_id": f.type()}
        for f in fields
    ]


def get_numeric_fields(layer) -> List[str]:
    """Retourne les noms des champs numériques (int, long, double)."""
    if not layer:
        return []
    numeric_types = (QgsField.Int, QgsField.LongLong, QgsField.Double)
    return [
        f.name() for f in layer.fields()
        if f.type() in numeric_types
    ]


def apply_layer_symbology(layer, config: "LayerSymbologyConfig", geometry_mode_override: Optional[str] = None, diffusion: str = "interne") -> None:
    """Applique la symbologie définie dans config à la couche."""
    from config_cartes import LayerSymbologyConfig

    geom_mode = geometry_mode_override or config.geometry_mode
    geom_type = layer.geometryType() if hasattr(layer, "geometryType") else None

    is_polygon = geom_type == QgsWkbTypes.PolygonGeometry if geom_type is not None else False

    actual_renderer = config.renderer_type
    if actual_renderer in ("graduated", "categorized") and not config.field:
        actual_renderer = "single"

    if actual_renderer == "single":
        if config.color_rgb:
            color = QColor(*config.color_rgb)
        elif config.palette and config.palette.startswith("#"):
            color = QColor(config.palette)
        else:
            color = QColor(100, 100, 100)

        if is_polygon and geom_mode == "polygon_centroid":
            fill_sym = QgsFillSymbol()
            while fill_sym.symbolLayerCount() > 0:
                fill_sym.deleteSymbolLayer(0)
            marker_sym = QgsMarkerSymbol.createSimple({
                "name": config.symbol_shape,
                "color": color.name(),
                "size": str(config.symbol_size_mm),
                "outline_color": "35,35,35",
            })
            marker_sym.setOutputUnit(Qgis.RenderUnit.Millimeters)
            centroid_layer = QgsCentroidFillSymbolLayer.create({})
            centroid_layer.setSubSymbol(marker_sym)
            fill_sym.appendSymbolLayer(centroid_layer)
            layer.setRenderer(QgsSingleSymbolRenderer(fill_sym))
        elif is_polygon and geom_mode == "polygon_fill":
            fill_sym = QgsFillSymbol.createSimple({"color": color.name(), "outline_color": "35,35,35"})
            layer.setRenderer(QgsSingleSymbolRenderer(fill_sym))
        else:
            marker = QgsMarkerSymbol.createSimple({
                "name": config.symbol_shape,
                "color": color.name(),
                "size": str(config.symbol_size_mm),
                "outline_color": "128,17,25" if config.symbol_shape == "diamond" else "35,35,35",
            })
            marker.setOutputUnit(Qgis.RenderUnit.Millimeters)
            single_renderer = QgsSingleSymbolRenderer(marker)
            layer.setRenderer(single_renderer)

    elif actual_renderer == "graduated" and config.field:
        if is_polygon and geom_mode == "polygon_centroid":
            base_symbol = QgsFillSymbol()
            while base_symbol.symbolLayerCount() > 0:
                base_symbol.deleteSymbolLayer(0)
            marker_sym = QgsMarkerSymbol.createSimple({
                "name": config.symbol_shape,
                "color": "31,120,180",
                "size": str(config.symbol_size_mm),
                "outline_color": "35,35,35",
            })
            marker_sym.setOutputUnit(Qgis.RenderUnit.Millimeters)
            centroid_layer = QgsCentroidFillSymbolLayer.create({})
            centroid_layer.setSubSymbol(marker_sym)
            base_symbol.appendSymbolLayer(centroid_layer)
        elif is_polygon and geom_mode == "polygon_fill":
            base_symbol = QgsFillSymbol.createSimple({"color": "31,120,180", "outline_color": "35,35,35"})
        else:
            base_symbol = QgsMarkerSymbol.createSimple({
                "name": config.symbol_shape,
                "color": "31,120,180",
                "size": str(config.symbol_size_mm),
                "outline_color": "35,35,35",
            })
            base_symbol.setOutputUnit(Qgis.RenderUnit.Millimeters)

        if config.classification_mode == "quantile":
            mode = QgsGraduatedSymbolRenderer.Quantile
        elif config.classification_mode == "equal_interval":
            mode = QgsGraduatedSymbolRenderer.EqualInterval
        elif config.classification_mode == "jenks":
            mode = QgsGraduatedSymbolRenderer.Jenks
        else:
            mode = QgsGraduatedSymbolRenderer.EqualInterval

        style = QgsStyle.defaultStyle()
        color_ramp = style.colorRamp(config.palette) if style.colorRamp(config.palette) else style.colorRamp("Blues")

        renderer = QgsGraduatedSymbolRenderer.createRenderer(
            layer, config.field, getattr(config, "num_classes", 5), mode, base_symbol, color_ramp
        )
        if color_ramp:
            renderer.setSourceColorRamp(color_ramp)
        layer.setRenderer(renderer)

    elif actual_renderer == "categorized" and config.field:
        # Palette cyclique ou générée
        palette_colors: list[str] = []
        if isinstance(config.palette, str) and "#" in config.palette:
            palette_colors = [p.strip() for p in config.palette.split(",") if p.strip()]
        if not palette_colors:
            palette_colors = ["#003A76", "#53AB60", "#F4A261", "#E76F51", "#90BF83", "#4296CE"]

        # Dictionnaire {valeur → couleur} explicite (priorité sur palette cyclique)
        categories_map: dict[str, str] = getattr(config, "categories", None) or {}

        # Récupérer les valeurs distinctes
        values = []
        field_names = [f.name() for f in layer.fields()]
        if config.field in field_names:
            try:
                idx = layer.fields().indexFromName(config.field)
                values = sorted(list(layer.uniqueValues(idx)))
            except Exception:
                values = []
        else:
            try:
                from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils, QgsFeatureRequest
                expr = QgsExpression(config.field)
                ctx = QgsExpressionContext()
                for scope in QgsExpressionContextUtils.globalProjectLayerScopes(layer):
                    ctx.appendScope(scope)
                ctx.setFields(layer.fields())
                expr.prepare(ctx)
                vals = set()
                req = QgsFeatureRequest()
                for i, f in enumerate(layer.getFeatures(req)):
                    ctx.setFeature(f)
                    v = expr.evaluate(ctx)
                    if v is None:
                        continue
                    vals.add(str(v))
                    if i >= 5000:
                        break
                values = sorted(vals)
            except Exception:
                values = []

        if categories_map:
            ordered_values = list(categories_map.keys())
            extra = [str(v) for v in values if str(v) not in categories_map]
            values = ordered_values + sorted(extra)
        else:
            values = [str(v) for v in values]

        # Exclure systématiquement les fiches en attente ou non renseignées des catégories de symbologie
        excluded = {"non renseigné", "en attente", "en_attente"}
        values = [v for v in values if str(v).strip().lower() not in excluded]

        # Si le nombre de valeurs dépasse la palette fournie, on génère une palette dynamique (hue spread)
        def _get_color_for_idx(idx: int, total: int) -> QColor:
            if idx < len(palette_colors):
                return QColor(palette_colors[idx])
            hue = int(360 * (idx / max(1, total)))
            return QColor.fromHsv(hue, 180, 220)

        qgs_categories = []
        for i, v in enumerate(values):
            v_str = str(v)
            if v_str in categories_map:
                color = QColor(categories_map[v_str])
            else:
                color = _get_color_for_idx(i, len(values))
                
            if is_polygon and geom_mode == "polygon_fill":
                sym = QgsFillSymbol.createSimple({"color": color.name(), "outline_color": "35,35,35"})
            elif is_polygon and geom_mode == "polygon_centroid":
                fill_sym = QgsFillSymbol()
                while fill_sym.symbolLayerCount() > 0:
                    fill_sym.deleteSymbolLayer(0)
                marker_sym = QgsMarkerSymbol.createSimple({
                    "name": config.symbol_shape,
                    "color": color.name(),
                    "size": str(config.symbol_size_mm),
                    "outline_color": "35,35,35",
                })
                marker_sym.setOutputUnit(Qgis.RenderUnit.Millimeters)
                centroid_layer = QgsCentroidFillSymbolLayer.create({})
                centroid_layer.setSubSymbol(marker_sym)
                fill_sym.appendSymbolLayer(centroid_layer)
                sym = fill_sym
            else:
                sym = QgsMarkerSymbol.createSimple({
                    "name": config.symbol_shape,
                    "color": color.name(),
                    "size": str(config.symbol_size_mm),
                    "outline_color": "35,35,35",
                })
                sym.setOutputUnit(Qgis.RenderUnit.Millimeters)
            qgs_categories.append(QgsRendererCategory(v_str, sym, v_str))

        renderer = QgsCategorizedSymbolRenderer(config.field, qgs_categories)
        layer.setRenderer(renderer)
        if "resultat" in config.field.lower():
            try:
                from qgis.core import QgsFeatureRequest
                expr_str = f"CASE WHEN lower({config.field}) = 'conforme' THEN 0 WHEN lower({config.field}) = 'manquement' THEN 1 ELSE 2 END"
                clause = QgsFeatureRequest.OrderByClause(expr_str, True)
                orderby = QgsFeatureRequest.OrderBy([clause])
                renderer.setOrderBy(orderby)
                renderer.setOrderByEnabled(True)
                logger.info("Tri de rendu appliqué pour la couche '%s' (Conforme < Manquement < Infraction)", layer.name())
            except Exception as e:
                logger.warning("Impossible d'appliquer le tri de rendu pour '%s' : %s", layer.name(), e)
    else:
        if config.renderer_type in ("graduated", "categorized") and not config.field:
            logger.warning(
                "Rendu '%s' demandé pour la couche '%s' mais le paramètre 'field' est manquant ou vide. "
                "Fallback sur un rendu à symbole unique (single).",
                config.renderer_type,
                layer.name(),
            )
            from dataclasses import replace
            fallback_cfg = replace(config, renderer_type="single")
            apply_layer_symbology(layer, fallback_cfg, geometry_mode_override, diffusion=diffusion)
            return

    # Forcer la forme du patch de légende pour qu'il corresponde au marqueur
    try:
        from qgis.core import QgsLegendPatchShape, QgsGeometry, QgsPointXY
        patch_shape = None
        if not is_polygon or geom_mode == "polygon_centroid":
            geom = QgsGeometry.fromPointXY(QgsPointXY(0, 0))
            
            # Résolution robuste du type de symbole pour QgsLegendPatchShape
            try:
                from qgis.core import Qgis
                symbol_type = Qgis.SymbolType.Marker
            except (ImportError, AttributeError):
                try:
                    from qgis.core import QgsSymbol
                    symbol_type = QgsSymbol.Marker
                except (ImportError, AttributeError):
                    symbol_type = None

            if symbol_type is not None:
                patch_shape = QgsLegendPatchShape(symbol_type, geom, False)
            else:
                patch_shape = QgsLegendPatchShape(geom, False)
        
        if patch_shape and hasattr(layer, "legend") and layer.legend():
            if hasattr(layer.legend(), "setLegendPatchShape"):
                layer.legend().setLegendPatchShape(patch_shape)
    except Exception as e:
        logger.debug("Impossible de forcer le patch de légende : %s", e)

    layer.triggerRepaint()


def _depart_attr_condition(field_name: str, depart: str) -> str:
    """Condition attribut département (chaîne ou entier INSEE)."""
    depart = str(depart or "").strip()
    try:
        depart_int = int(depart)
        return f'"{field_name}" IN ({depart!r}, {depart_int})'
    except ValueError:
        return f'"{field_name}" = {depart!r}'


def _build_date_condition(fields, field_name: str, date_deb: str, date_fin: str) -> str:
    # Text format: handle both YYYY-MM-DD and DD/MM/YYYY using CASE WHEN
    return (
        f'(CASE '
        f'  WHEN "{field_name}" LIKE \'%/%\' THEN '
        f'    substr("{field_name}", 7, 4) || \'-\' || substr("{field_name}", 4, 2) || \'-\' || substr("{field_name}", 1, 2) '
        f'  ELSE '
        f'    substr("{field_name}", 1, 10) '
        f'END) BETWEEN \'{date_deb}\' AND \'{date_fin}\''
    )


def _build_pve_expression(fields, date_deb: str, date_fin: str, config, profile=None) -> Optional[str]:
    field_names = {f.name() for f in fields}

    # Résolution des noms de champs (support préfixe PVe_ ou classique INF-)
    natinf_col = next(
        (c for c in ("PVe_INF-NATINF", "INF-NATINF") if c in field_names), None
    )
    date_col = next(
        (c for c in ("PVe_INF-DATE-MIF", "INF-DATE-I") if c in field_names), None
    )
    depart_col = next(
        (c for c in ("INSEE_DEP", "INF-DEPART") if c in field_names), None
    )

    if not natinf_col or not date_col or not depart_col:
        return None

    natinf_values = None
    if profile and getattr(profile, "id", None) and (profile.id == "global" or profile.id.startswith("global_")):
        natinf_values = None
    elif profile and getattr(profile, "natinf_pve", None) is not None:
        natinf_values = profile.natinf_pve
    else:
        natinf_values = getattr(config, "natinf_pve", [27742])

    depart = getattr(config, "departement_code", "21")

    # INSEE_DEP est un entier (21) ou une chaîne ("21") — les deux cas
    if depart_col == "INSEE_DEP":
        depart_cond = f'"{depart_col}" IN ({depart!r}, {int(depart)})'
    else:
        depart_cond = f'lower("{depart_col}") = {depart.lower()!r}'

    date_cond = _build_date_condition(fields, date_col, date_deb, date_fin)
    
    if not natinf_values:
        # Pas de filtre NATINF pour ce profil
        return f"{depart_cond} AND {date_cond}"

    natinf_list = ", ".join(str(x) for x in natinf_values)
    return f'"{natinf_col}" IN ({natinf_list}) AND {depart_cond} AND {date_cond}'


def _build_pj_expression(fields, date_deb: str, date_fin: str, config, profile=None) -> Optional[str]:
    field_names = {f.name() for f in fields}
    required = {"entite", "natinf", "date_saisine"}
    if not required.issubset(field_names):
        return None

    natinf_values = None
    if profile and getattr(profile, "id", None) and (profile.id == "global" or profile.id.startswith("global_")):
        natinf_values = None
    elif profile and getattr(profile, "natinf_pj", None) is not None:
        natinf_values = profile.natinf_pj
    else:
        natinf_values = getattr(config, "natinf_pj", [27742, 25001])

    depart = str(getattr(config, "departement_code", "21")).strip()
    date_cond = _build_date_condition(fields, "date_saisine", date_deb, date_fin)

    entite_list = []
    if depart.lower().startswith("bmi"):
        from ofbilan.common.utilitaires_metier import get_departements_pour_perimetre, get_bmi_filters
        dept_codes = get_departements_pour_perimetre("bmi", depart)
        if dept_codes and "FR" not in dept_codes:
            entite_list = [f"sd{d.lower()}" for d in dept_codes]
        bmi_filters = get_bmi_filters(depart)
        entite_list.append(str(bmi_filters.get("entite_pej", depart)).lower())
    else:
        entite_list.append(f"sd{depart.lower()}")

    entite_cond = "lower(\"entite\") IN ('" + "', '".join(entite_list) + "')"

    if not natinf_values:
        return f"{entite_cond} AND {date_cond}"

    natinf_list = ", ".join(str(x) for x in natinf_values)
    return f"{entite_cond} AND \"natinf\" IN ({natinf_list}) AND {date_cond}"


def _build_point_ctrl_agrainage_expression(fields, date_deb: str, date_fin: str, config) -> Optional[str]:
    field_names = {f.name() for f in fields}
    nom_col = None
    if "nom_dossier" in field_names:
        nom_col = "nom_dossier"
    elif "nom_dossie" in field_names:
        nom_col = "nom_dossie"

    required = {"date_ctrl", "num_depart", "resultat"}
    if not nom_col or not required.issubset(field_names):
        return None

    depart = getattr(config, "departement_code", "21")
    date_cond = _build_date_condition(fields, "date_ctrl", date_deb, date_fin)
    dept_cond = _depart_attr_condition("num_depart", depart)
    return (
        f'lower("{nom_col}") LIKE \'%agrain%\' AND '
        f'{dept_cond} AND lower("resultat") = \'conforme\' AND '
        f'{date_cond}'
    )


def _build_point_ctrl_chasse_expression(fields, date_deb: str, date_fin: str, config) -> Optional[str]:
    field_names = {f.name() for f in fields}
    required = {"date_ctrl", "num_depart", "resultat"}
    if not required.issubset(field_names):
        return None

    depart = getattr(config, "departement_code", "21")
    date_cond = _build_date_condition(fields, "date_ctrl", date_deb, date_fin)
    expr = (
        f'{_depart_attr_condition("num_depart", depart)} AND lower("resultat") = \'conforme\' AND '
        f'{date_cond}'
    )
    if "theme" in field_names:
        theme_val = str(getattr(config, "chasse_theme_value", "Chasse")).lower()
        expr = f'lower("theme") = {repr(theme_val)} AND ' + expr
    return expr


def _build_point_ctrl_global_expression(fields, date_deb: str, date_fin: str, config) -> Optional[str]:
    """Filtre points de contrôle global : département + période (sans filtre thème, sans filtre résultat)."""
    field_names = {f.name() for f in fields}
    required = {"date_ctrl", "num_depart"}
    if not required.issubset(field_names):
        return None

    depart = getattr(config, "departement_code", "21")
    diffusion = getattr(config, "diffusion", "interne")
    date_cond = _build_date_condition(fields, "date_ctrl", date_deb, date_fin)
    
    expr = f'{_depart_attr_condition("num_depart", depart)} AND {date_cond}'
    res_col = next((c for c in ("resultat", "Resultat", "resultat_controle") if c in field_names), None)
    if res_col:
        expr += f" AND lower(coalesce(\"{res_col}\", '')) != 'en attente'"
    if str(diffusion).strip().lower() == "externe":
        expr += " AND lower(coalesce(\"resultat\", \"Resultat\", \"resultat_controle\", '')) IN ('conforme', 'manquement', 'infraction', 'manquement et infraction')"
    return expr


def _build_point_ctrl_manquement_expression(fields, date_deb: str, date_fin: str, config) -> Optional[str]:
    """Filtre points de contrôle pour proxy PA : contrôles dont le résultat contient 'manquement' (insensible à la casse)."""
    field_names = {f.name() for f in fields}
    required = {"date_ctrl", "num_depart", "resultat"}
    if not required.issubset(field_names):
        return None

    depart = getattr(config, "departement_code", "21")
    date_cond = _build_date_condition(fields, "date_ctrl", date_deb, date_fin)
    return (
        f'{_depart_attr_condition("num_depart", depart)} AND '
        f'lower("resultat") LIKE \'%manquement%\' AND '
        f'{date_cond}'
    )


def _build_point_ctrl_pa_expression(fields, date_deb: str, date_fin: str, config) -> Optional[str]:
    """Filtre points de contrôle pour PA : contrôles dont le champ code_pa est non nul."""
    field_names = {f.name() for f in fields}
    required = {"date_ctrl", "num_depart", "code_pa"}
    if not required.issubset(field_names):
        return None

    depart = getattr(config, "departement_code", "21")
    date_cond = _build_date_condition(fields, "date_ctrl", date_deb, date_fin)
    return (
        f'{_depart_attr_condition("num_depart", depart)} AND '
        f'("code_pa" IS NOT NULL AND "code_pa" != \'\') AND '
        f'{date_cond}'
    )



def _build_point_ctrl_theme_expression(
    fields, date_deb: str, date_fin: str, config, theme_label: str
) -> Optional[str]:
    """Filtre points de contrôle par thème : theme/type_actio/nom_dossie contient le label du thème."""
    field_names = {f.name() for f in fields}
    nom_col = None
    if "nom_dossier" in field_names:
        nom_col = "nom_dossier"
    elif "nom_dossie" in field_names:
        nom_col = "nom_dossie"
    type_col = "type_action" if "type_action" in field_names else "type_actio" if "type_actio" in field_names else None
    theme_col = "theme" if "theme" in field_names else None

    required = {"date_ctrl", "num_depart"}
    if not required.issubset(field_names):
        return None

    depart = getattr(config, "departement_code", "21")
    label_esc = (theme_label or "").replace("'", "''").lower()

    like_parts = []
    if theme_col and label_esc:
        like_parts.append(f'lower("{theme_col}") LIKE \'%{label_esc}%\'')
    if type_col and label_esc:
        like_parts.append(f'lower("{type_col}") LIKE \'%{label_esc}%\'')
    if nom_col and label_esc:
        like_parts.append(f'lower("{nom_col}") LIKE \'%{label_esc}%\'')
    if not like_parts:
        return None
    text_cond = "(" + " OR ".join(like_parts) + ")"
    date_cond = _build_date_condition(fields, "date_ctrl", date_deb, date_fin)
    return f'{text_cond} AND {_depart_attr_condition("num_depart", depart)} AND {date_cond}'


def _build_point_ctrl_keywords_expression(
    fields,
    date_deb: str,
    date_fin: str,
    config,
    keywords: list[str],
    columns: list[str] | None = None,
) -> Optional[str]:
    """Filtre points de contrôle par mots-clés (aligné filtres bilan thématiques)."""
    if not keywords:
        return None

    field_names = {f.name() for f in fields}
    col_map = {
        "theme": "theme" if "theme" in field_names else None,
        "type_actio": "type_action" if "type_action" in field_names else "type_actio" if "type_actio" in field_names else None,
        "type_action": "type_action" if "type_action" in field_names else "type_actio" if "type_actio" in field_names else None,
        "nom_dossie": "nom_dossier" if "nom_dossier" in field_names else "nom_dossie" if "nom_dossie" in field_names else None,
        "nom_dossier": "nom_dossier" if "nom_dossier" in field_names else "nom_dossie" if "nom_dossie" in field_names else None,
    }
    use_columns = columns or ["theme", "type_actio", "nom_dossie"]
    resolved_cols: list[str] = []
    for col in use_columns:
        mapped = col_map.get(col, col if col in field_names else None)
        if mapped and mapped not in resolved_cols:
            resolved_cols.append(mapped)

    required = {"date_ctrl", "num_depart"}
    if not required.issubset(field_names) or not resolved_cols:
        return None

    depart = getattr(config, "departement_code", "21")

    like_parts: list[str] = []
    for kw in keywords:
        kw_esc = str(kw).replace("'", "''").lower()
        for col in resolved_cols:
            like_parts.append(f'lower("{col}") LIKE \'%{kw_esc}%\'')
    if not like_parts:
        return None
    text_cond = "(" + " OR ".join(like_parts) + ")"
    date_cond = _build_date_condition(fields, "date_ctrl", date_deb, date_fin)
    return f'{text_cond} AND {_depart_attr_condition("num_depart", depart)} AND {date_cond}'


def _build_point_ctrl_piegeage_expression(fields, date_deb: str, date_fin: str, config) -> Optional[str]:
    """Filtre points de contrôle piégeage : nom_dossie/theme/type_actio contient un mot-clé piégeage."""
    field_names = {f.name() for f in fields}
    nom_col = None
    if "nom_dossier" in field_names:
        nom_col = "nom_dossier"
    elif "nom_dossie" in field_names:
        nom_col = "nom_dossie"

    required = {"date_ctrl", "num_depart"}
    if not required.issubset(field_names):
        return None

    depart = getattr(config, "departement_code", "21")
    keywords = getattr(config, "piegeage_keywords", ["piégeage", "piège"])
    # Condition texte : (nom LIKE '%piégeage%' OR nom LIKE '%piège%' OR theme LIKE '%...' OR type_actio LIKE '%...')
    type_col = "type_action" if "type_action" in field_names else "type_actio" if "type_actio" in field_names else None
    theme_col = "theme" if "theme" in field_names else None

    like_parts = []
    for kw in keywords:
        kw_esc = kw.replace("'", "''").lower()
        if nom_col:
            like_parts.append(f'lower("{nom_col}") LIKE \'%{kw_esc}%\'')
        if theme_col:
            like_parts.append(f'lower("{theme_col}") LIKE \'%{kw_esc}%\'')
        if type_col:
            like_parts.append(f'lower("{type_col}") LIKE \'%{kw_esc}%\'')
    if not like_parts:
        return None
    text_cond = "(" + " OR ".join(like_parts) + ")"
    date_cond = _build_date_condition(fields, "date_ctrl", date_deb, date_fin)
    return f'{text_cond} AND {_depart_attr_condition("num_depart", depart)} AND {date_cond}'





def apply_date_filter(
    layer,
    lcfg: "LayerSymbologyConfig",
    date_deb: str,
    date_fin: str,
    config=None,
    profile: Optional["ProfileConfig"] = None,
) -> None:
    """Applique un filtre attributaire selon le type de couche (pve, pj, point_ctrl_agrainage, point_ctrl_theme)."""
    from config_cartes import CONFIG

    use_config = config if config is not None else CONFIG
    filter_type = getattr(lcfg, "filter_type", "") or ""
    fields = [f.name() for f in layer.fields()]
    
    expr: Optional[str] = None

    if filter_type == "pve":
        expr = _build_pve_expression(layer.fields(), date_deb, date_fin, use_config, profile=profile)
    elif filter_type == "pj":
        expr = _build_pj_expression(layer.fields(), date_deb, date_fin, use_config, profile=profile)
    elif filter_type == "point_ctrl_agrainage":
        expr = _build_point_ctrl_agrainage_expression(layer.fields(), date_deb, date_fin, use_config)
    elif filter_type == "point_ctrl_chasse":
        expr = _build_point_ctrl_chasse_expression(layer.fields(), date_deb, date_fin, use_config)
    elif filter_type == "point_ctrl_piegeage":
        expr = _build_point_ctrl_piegeage_expression(layer.fields(), date_deb, date_fin, use_config)
    elif filter_type == "point_ctrl_global":
        expr = _build_point_ctrl_global_expression(layer.fields(), date_deb, date_fin, use_config)
    elif filter_type == "point_ctrl_manquement":
        expr = _build_point_ctrl_manquement_expression(layer.fields(), date_deb, date_fin, use_config)
    elif filter_type == "point_ctrl_pa":
        expr = _build_point_ctrl_pa_expression(layer.fields(), date_deb, date_fin, use_config)
    elif filter_type == "point_ctrl_theme" and profile and getattr(profile, "theme_id", None):
        try:
            themes = _load_ref_themes_ctrl_safe(PROJECT_ROOT)
            theme_entry = next((t for t in themes if t["id"] == profile.theme_id), None)
            theme_label = theme_entry["label"] if theme_entry else profile.theme_id.replace("_", " ")
            expr = _build_point_ctrl_theme_expression(
                layer.fields(), date_deb, date_fin, use_config, theme_label
            )
        except Exception as e:
            logger.warning("Filtre point_ctrl_theme : impossible de charger le label pour %s : %s", profile.theme_id, e)
    elif filter_type == "point_ctrl_keywords" and profile and getattr(profile, "keywords", None):
        expr = _build_point_ctrl_keywords_expression(
            layer.fields(),
            date_deb,
            date_fin,
            use_config,
            list(profile.keywords or []),
            list(profile.keyword_columns or []) or None,
        )

    if not filter_type:
        return

    if not expr:
        logger.warning(
            "Filtre '%s' non appliqué à la couche '%s' (champs requis manquants, disponibles=%s)",
            filter_type,
            layer.name(),
            fields,
        )
        return

    try:
        layer.setSubsetString(expr)
    except Exception as e:
        logger.warning(
            "Filtre '%s' non appliqué pour la couche '%s' : %s",
            filter_type,
            layer.name(),
            e,
        )


def set_basemap_visibility(enabled: bool) -> None:
    """Active ou désactive les couches fond (XYZ, WMS). Force SCAN 25."""
    proj = QgsProject.instance()
    root = proj.layerTreeRoot()
    for layer in proj.mapLayers().values():
        lname = layer.name().lower()
        if any(x in lname for x in ["esri", "osm", "xyz", "wms", "wmts", "cartes ign", "plan ign", "scan 25", "national geographic", "community map"]):
            node = root.findLayer(layer.id())
            if node:
                if enabled and "scan 25" in lname:
                    node.setItemVisibilityChecked(True)
                else:
                    node.setItemVisibilityChecked(False)


def _apply_legend_labels(
    layout,
    prof: "ProfileConfig",
    legend_labels_map: Optional[Dict[str, str]] = None,
) -> None:
    """Met à jour les libellés de la légende du layout avec les legend_label du profil."""
    if legend_labels_map is None:
        legend_labels_map = {
            lc.layer_name: (lc.legend_label or lc.layer_name) for lc in prof.layers.values()
        }
    if not legend_labels_map:
        return

    for item in layout.items():
        if not isinstance(item, QgsLayoutItemLegend):
            continue
        try:
            item.setAutoUpdateModel(False)
            root = item.model().rootGroup()

            def visit(node):
                if isinstance(node, QgsLayerTreeLayer):
                    layer = node.layer()
                    if layer and layer.name() in legend_labels_map:
                        node.setUseLayerName(False)
                        node.setName(legend_labels_map[layer.name()])
                for child in node.children():
                    visit(child)

            visit(root)
            item.updateLegend()
        except Exception as e:
            logger.warning("Mise à jour légende ignorée: %s", e)


def _get_logo_bandeau_path() -> Optional[Path]:
    """Retourne le chemin du bandeau logos (République française + OFB), ref/programme/modele_ofb/word/media/image5."""
    ref_media = PROJECT_ROOT / "ref" / "modele_ofb" / "word" / "media"
    for ext in ("jpg", "jpeg", "png"):
        p = ref_media / f"image5.{ext}"
        if p.exists():
            return p
    return None


# Logo RF-OFB horizontal en bas à droite des cartes
# Référence taille / position : docs/usage/README_Production_cartes.md
# Taille doublée (+100 %), ancrage au bord supérieur gauche (position du coin supérieur gauche fixe).
LOGO_OFB_HORIZONTAL_FILENAME = "bloc-marque-RF-OFB_horizontal.jpg"


def _get_logo_ofb_horizontal_path() -> Optional[Path]:
    """Retourne le chemin du logo RF-OFB horizontal (ref/programme/modele_ofb/bloc-marque-RF-OFB_horizontal.jpg)."""
    p = PROJECT_ROOT / "ref" / "programme" / "modele_ofb" / LOGO_OFB_HORIZONTAL_FILENAME
    if p.exists():
        return p
    for ext in ("jpeg", "png"):
        alt = PROJECT_ROOT / "ref" / "programme" / "modele_ofb" / f"bloc-marque-RF-OFB_horizontal.{ext}"
        if alt.exists():
            return alt
    return None


def _ensure_logo_ofb_bas_droite(layout, prof: "ProfileConfig") -> None:
    """Place le logo RF-OFB horizontal en bas à droite (YAML layout_defaults ou constantes legacy)."""
    from layout_defaults import (
        apply_existing_qgis_logo_position,
        get_logo_bas_droite_rect,
        load_layout_defaults,
        should_skip_python_logo_bas_droite,
    )
    from config_cartes_model import LayoutItemRectConfig

    logo_path = _get_logo_ofb_horizontal_path()
    if not logo_path:
        logger.warning(
            "Logo OFB horizontal introuvable (ref/programme/modele_ofb/%s). "
            "Placez le fichier pour l'afficher en bas à droite des cartes.",
            LOGO_OFB_HORIZONTAL_FILENAME,
        )
        return

    root = load_layout_defaults()
    logo_cfg = get_logo_bas_droite_rect(prof, layout, root=root)
    if logo_cfg is not None and should_skip_python_logo_bas_droite(layout, logo_cfg):
        if apply_existing_qgis_logo_position(layout, logo_cfg):
            return

    picture_id = logo_cfg.picture_id if logo_cfg else "logo_ofb_bas_droite"
    picture_item = None
    for item in layout.items():
        if isinstance(item, QgsLayoutItemPicture):
            try:
                if item.id() == picture_id:
                    picture_item = item
                    break
            except Exception as exc:
                logger.debug("Recherche logo bas droite (id layout): %s", exc)

    if picture_item is None:
        picture_item = QgsLayoutItemPicture(layout)
        picture_item.setId(picture_id)
        layout.addLayoutItem(picture_item)

    if hasattr(picture_item, "setPicturePath"):
        picture_item.setPicturePath(str(logo_path))
    else:
        picture_item.setPath(str(logo_path))
    picture_item.setResizeMode(QgsLayoutItemPicture.Zoom)

    if logo_cfg is not None and logo_cfg.width_mm > 0:
        from layout_defaults import _layout_item_set_rect

        _layout_item_set_rect(
            picture_item,
            LayoutItemRectConfig(
                x_mm=logo_cfg.x_mm,
                y_mm=logo_cfg.y_mm,
                width_mm=logo_cfg.width_mm,
                height_mm=logo_cfg.height_mm,
            ),
        )


def _ensure_logo_bandeau(layout, prof: "ProfileConfig") -> None:
    """Ajoute ou met à jour le bandeau logos (République française + OFB) en haut du layout."""
    from layout_defaults import get_bandeau_config, load_layout_defaults

    logo_path = _get_logo_bandeau_path()
    if not logo_path:
        logger.warning(
            "Bandeau logos OFB introuvable (ref/programme/modele_ofb/word/media/image5.jpg ou .png). "
            "Placez le fichier pour l'afficher sur les cartes."
        )
        return

    bandeau_cfg = get_bandeau_config(prof, layout, root=load_layout_defaults())
    bandeau_id = bandeau_cfg.picture_id if bandeau_cfg else "bandeau_logos_ofb"
    picture_item = None
    for item in layout.items():
        if isinstance(item, QgsLayoutItemPicture):
            try:
                if item.id() == bandeau_id:
                    picture_item = item
                    break
            except Exception as exc:
                logger.debug("Recherche bandeau logos (id layout): %s", exc)

    if picture_item is None:
        picture_item = QgsLayoutItemPicture(layout)
        picture_item.setId(bandeau_id)
        layout.addLayoutItem(picture_item)

    # Définir le chemin de l'image (API PyQGIS : setPicturePath ; certaines versions ont setPath)
    if hasattr(picture_item, "setPicturePath"):
        picture_item.setPicturePath(str(logo_path))
    else:
        picture_item.setPath(str(logo_path))
    picture_item.setResizeMode(QgsLayoutItemPicture.Zoom)
    
    if bandeau_cfg is not None and bandeau_cfg.height_mm > 0:
        layout_size = layout.pageCollection().page(0).pageSize()
        w_mm = layout_size.width()
        bandeau_h = bandeau_cfg.height_mm
        y_pos = bandeau_cfg.y_mm
        try:
            size_mm = QgsLayoutSize(w_mm, bandeau_h)
            if hasattr(picture_item, "attemptResize"):
                picture_item.attemptResize(size_mm)
            else:
                logger.warning(
                    "QgsLayoutItemPicture: attemptResize non trouvé. Méthodes: %s",
                    [m for m in dir(picture_item) if not m.startswith("_") and "size" in m.lower()],
                )
        except Exception as e:
            logger.exception("Erreur lors du dimensionnement du bandeau logo: %s", e)
        try:
            if hasattr(picture_item, "attemptMove"):
                picture_item.attemptMove(QgsLayoutPoint(0, y_pos))
            elif hasattr(picture_item, "setPosition"):
                picture_item.setPosition(QgsLayoutPoint(0, y_pos))
        except Exception as e:
            logger.exception("Erreur lors du positionnement du bandeau logo: %s", e)


def resolve_map_title(prof: "ProfileConfig", dept_code: Optional[str] = None) -> str:
    """Résout le titre de la carte en gérant le département et la période de manière sécurisée."""
    from ofbilan.common.utilitaires_metier import get_dept_name
    dept_name = get_dept_name(dept_code) if dept_code else ""
    
    base_title = getattr(prof, "title_main", "") or ""
    if not base_title:
        base_title = getattr(prof, "title", "") or ""
        if " - " in base_title:
            base_title = base_title.split(" - ")[0]
        elif " — " in base_title:
            base_title = base_title.split(" — ")[0]
            
    periode = ""
    if hasattr(prof, "date_deb") and hasattr(prof, "date_fin") and prof.date_deb and prof.date_fin:
        clean_date_deb = str(prof.date_deb).split(" ")[0]
        clean_date_fin = str(prof.date_fin).split(" ")[0]
        if clean_date_deb.endswith("-01-01") and clean_date_fin.endswith("-12-31") and clean_date_deb[:4] == clean_date_fin[:4]:
            periode = f"Année {clean_date_deb[:4]}"
        else:
            periode = f"Du {clean_date_deb} au {clean_date_fin}"

    parts = [base_title]
    if dept_name:
        parts.append(dept_name)
    if periode:
        parts.append(periode)
        
    return " — ".join(parts)


def export_layout(
    prof: "ProfileConfig",
    output_path: Path,
    dpi: int = 300,
    fmt: str = "png",
    legend_labels_map: Optional[Dict[str, str]] = None,
    dept_code: Optional[str] = None,
    layers_to_render: Optional[list] = None,
) -> bool:
    """Exporte le layout du profil vers un fichier image."""
    from config_cartes import ProfileConfig, CONFIG

    proj = QgsProject.instance()
    title_text = resolve_map_title(prof, dept_code)

    # Injection du Layout Dynamique (Lot 1)
    manager = proj.layoutManager()
    if not getattr(prof, "layers_from_layout", False):
        from layout_dynamique import build_dynamic_layout
        layout = build_dynamic_layout(prof, proj, title_text)
        is_dynamic = True
        logger.info("Layout généré 100%% dynamiquement pour le profil '%s'.", prof.id)
    else:
        is_dynamic = False
        layout = manager.layoutByName(prof.layout_name)
        if not layout:
            logger.error("Layout '%s' introuvable dans le projet et fallback désactivé.", prof.layout_name)
            return False

    from layout_defaults import apply_layout_defaults, load_layout_defaults, resolve_title_ids

    layout_defaults_root = load_layout_defaults()
    if not is_dynamic:
        try:
            apply_layout_defaults(layout, prof, root=layout_defaults_root)
        except Exception as e:
            logger.exception("Mise en page layout_defaults (export continué): %s", e)

    subtitle_text = ""
    title_id, subtitle_id = resolve_title_ids(prof, layout_defaults_root)

    from qgis.core import QgsLayoutItemScaleBar, QgsUnitTypes

    for item in layout.items():
        if isinstance(item, QgsLayoutItemMap):
            if layers_to_render is not None:
                item.setLayers(layers_to_render)
                item.setKeepLayerSet(True)
            elif hasattr(item, "setKeepLayerSet"):
                item.setKeepLayerSet(False)
        elif isinstance(item, QgsLayoutItemLabel):
            try:
                item_id = item.id()
            except AttributeError:
                item_id = ""
                
            # Titres natifs (ou heuristique par contenu si ID absent/différent)
            current_text = item.text() if hasattr(item, "text") else ""
            
            known_titles = ["Localisation et", "Localisation et résultats des contrôles PA"]
            if hasattr(prof, 'cartes_definitions'):
                known_titles.extend([m.title_main for m in prof.cartes_definitions.values() if m.title_main])
                
            is_title = item_id == title_id or any(k in current_text for k in known_titles) or "titre" in item_id.lower()
            
            if is_title or (subtitle_id and item_id == subtitle_id):
                if is_title:
                    item.setText(title_text)
                else:
                    item.setText(subtitle_text)
                try:
                    from qgis.PyQt.QtGui import QFont, QColor
                    # Application de la charte OFB
                    font_size = 16 if is_title else 12
                    font = QFont("Marianne", font_size, QFont.Bold if is_title else QFont.Normal)
                    if hasattr(item, "setFont"):
                        item.setFont(font)
                    if hasattr(item, "setFontColor"):
                        item.setFontColor(QColor("#FFFFFF"))
                except Exception:
                    pass
                
            # Textes additionnels dynamiques (Hybride Avancé)
            if item_id and hasattr(prof, "extra_texts") and item_id in prof.extra_texts:
                template_str = prof.extra_texts[item_id]
                
                periode_formatee = ""
                if hasattr(prof, "date_deb") and hasattr(prof, "date_fin") and prof.date_deb and prof.date_fin:
                    if prof.date_deb.endswith("-01-01") and prof.date_fin.endswith("-12-31") and prof.date_deb[:4] == prof.date_fin[:4]:
                        periode_formatee = "Année " + prof.date_deb[:4]
                    else:
                        periode_formatee = f"Période : {prof.date_deb} - {prof.date_fin}"

                try:
                    formatted_text = template_str.format(
                        departement=dept_code or "",
                        date_deb=prof.date_deb,
                        date_fin=prof.date_fin,
                        nom_bilan=prof.title,
                        periode_formatee=periode_formatee
                    )
                    item.setText(formatted_text)
                except Exception as e:
                    logger.warning("Erreur formatage texte dynamique pour '%s': %s", item_id, e)
                    item.setText(template_str)
        elif isinstance(item, QgsLayoutItemScaleBar):
            item.setUnits(QgsUnitTypes.DistanceKilometers)
            item.setNumberOfSegmentsLeft(0)
            item.setNumberOfSegments(2)
            item.setUnitsPerSegment(10.0)
            item.update()
        elif isinstance(item, QgsLayoutItemLegend):
            # Supprimer la légende native QGIS car nous la générons avec Pillow post-export
            layout.removeLayoutItem(item)

    _apply_legend_labels(layout, prof, legend_labels_map=legend_labels_map)
    # Bandeau logos République française + OFB en haut de la carte
    try:
        _ensure_logo_bandeau(layout, prof)
    except Exception as e:
        logger.exception("Erreur bandeau logo (export continué): %s", e)
    # Logo RF-OFB horizontal en bas à droite
    try:
        _ensure_logo_ofb_bas_droite(layout, prof)
    except Exception as e:
        logger.exception("Erreur logo bas droite (export continué): %s", e)

    if dept_code:
        try:
            emprise_id = getattr(prof, "emprise", "departement") or "departement"
            apply_map_extent(layout, dept_code, pochoir_id=emprise_id)
        except Exception as e:
            logger.exception("Erreur ajustement emprise carte (export continué): %s", e)

    settings = QgsLayoutExporter.ImageExportSettings()
    settings.dpi = dpi

    ext = fmt.lower()
    if ext in ("jpg", "jpeg"):
        path_str = str(output_path.with_suffix(".jpg"))
        settings.imageFormat = "jpg"
    else:
        path_str = str(output_path.with_suffix(".png"))

    # Export vers un fichier temporaire : ne pas supprimer le PNG existant avant succès
    final_path = Path(path_str)
    export_path = final_path.with_name(f"{final_path.stem}._export_tmp{final_path.suffix}")
    if export_path.exists():
        try:
            export_path.unlink()
        except OSError:
            pass

    exporter = QgsLayoutExporter(layout)
    res = exporter.exportToImage(str(export_path), settings)

    if res == QgsLayoutExporter.Success:
        try:
            if final_path.exists():
                final_path.unlink()
            export_path.replace(final_path)
        except OSError as exc:
            logger.error(
                "Export réussi mais remplacement du fichier impossible (%s) : %s",
                final_path,
                exc,
            )
            return False
        logger.info("Carte exportée pour le profil '%s' → %s", prof.id, final_path)
        return True
    if export_path.exists():
        try:
            export_path.unlink()
        except OSError:
            pass
    logger.error("Échec de l'export du layout '%s' vers %s", prof.layout_name, final_path)
    return False


def run_interactive_wizard(profile_ids: List[str]) -> None:
    """Assistant interactif pour configurer la symbologie et l'enregistrer dans config_cartes.py."""
    from config_cartes import (
        CONFIG,
        ProfileConfig,
        LayerSymbologyConfig,
        DEFAULT_PROFILES,
        GeometryMode,
        RendererType,
        ClassificationMode,
    )

    proj = QgsProject.instance()
    all_layers = [lyr for lyr in proj.mapLayers().values() if isinstance(lyr, QgsVectorLayer)]

    logger.info("=== Assistant de configuration des cartes ===")
    logger.info("Couches disponibles dans le projet :")
    for i, layer in enumerate(all_layers, 1):
        geom = "polygone" if layer.geometryType() == QgsWkbTypes.PolygonGeometry else "points"
        logger.info("  %d. %s (%s)", i, layer.name(), geom)

    for pid in profile_ids:
        prof = CONFIG.profiles.get(pid)
        if not prof:
            prof = ProfileConfig(
                id=pid,
                title=f"Bilan {pid}",
                layout_name="modele_mise_en_page_carto_bilans",
                output_filename=f"carte_{pid}.png",
                layers={},
            )
            CONFIG.profiles[pid] = prof

        logger.info("--- Profil: %s ---", pid)

        for layer in all_layers:
            lname = layer.name()
            geom_type = layer.geometryType()
            is_polygon = geom_type == QgsWkbTypes.PolygonGeometry

            rep = input(f"  Configurer la couche '{lname}' ? [o/N] ").strip().lower()
            if rep not in ("o", "oui", "y", "yes"):
                continue

            fields = get_layer_fields(layer)
            logger.info("    Champs (%s): %s", lname, [f["name"] for f in fields])

            geom_mode: GeometryMode = "polygon_fill"
            if is_polygon:
                grep = input("    Rendu: [1] Choroplèthe (remplissage)  [2] Symboles sur centroïdes ? [1/2] ").strip() or "1"
                geom_mode = "polygon_centroid" if grep == "2" else "polygon_fill"

            rtype_rep = input("    Type: [1] Single  [2] Graduated  [3] Categorized ? [1/2/3] ").strip() or "1"
            if rtype_rep == "2":
                renderer_type: RendererType = "graduated"
            elif rtype_rep == "3":
                renderer_type = "categorized"
            else:
                renderer_type = "single"

            field = ""
            if renderer_type in ("graduated", "categorized"):
                numerics = get_numeric_fields(layer)
                if numerics:
                    logger.info("    Champs numériques: %s", numerics)
                    field = input(f"    Champ à utiliser ? [{numerics[0]}] ").strip() or numerics[0]
                else:
                    field = input("    Nom du champ ? ").strip()

            classification_mode: ClassificationMode = "quantile"
            num_classes = 5
            manual_breaks = None
            if renderer_type == "graduated":
                cmode_rep = input("    Classification: [1] Quantile  [2] Equal  [3] Jenks  [4] Manuel ? [1/2/3/4] ").strip() or "1"
                if cmode_rep == "2":
                    classification_mode = "equal_interval"
                elif cmode_rep == "3":
                    classification_mode = "jenks"
                elif cmode_rep == "4":
                    classification_mode = "manual"
                else:
                    classification_mode = "quantile"
                try:
                    num_classes = int(input("    Nombre de classes ? [5] ").strip() or "5")
                except ValueError:
                    num_classes = 5
                if classification_mode == "manual":
                    br = input("    Seuils manuels (ex: 0,1,5,10) ? [] ").strip()
                    if br:
                        try:
                            manual_breaks = [float(x) for x in br.replace(";", ",").split(",") if x.strip()]
                        except ValueError:
                            manual_breaks = None

            palette = input("    Palette (ex: Blues, YlOrRd) ? [Blues] ").strip() or "Blues"

            color_rgb = None
            if renderer_type == "single":
                rgb = input("    Couleur RGB (ex: 31,120,180) ? [31,120,180] ").strip() or "31,120,180"
                try:
                    color_rgb = tuple(int(x) for x in rgb.split(","))
                except (ValueError, TypeError):
                    color_rgb = (31, 120, 180)

            symbol_size = 4.0
            symbol_shape = "circle"
            try:
                symbol_size = float(input("    Taille symbole (mm) ? [4] ").strip() or "4")
            except ValueError:
                pass
            if is_polygon and geom_mode == "polygon_centroid":
                symbol_shape = input("    Forme (circle, square, diamond) ? [circle] ").strip() or "circle"

            legend_label = input(f"    Libellé légende ? [{lname}] ").strip() or lname

            # Type de filtre attributaire (facultatif)
            filter_type = ""
            ftype = input("    Filtre attributaire [vide/pve/pj/point_ctrl_agrainage/point_ctrl_chasse/point_ctrl_piegeage] ? [] ").strip()
            if ftype in ("pve", "pj", "point_ctrl_agrainage", "point_ctrl_chasse", "point_ctrl_piegeage"):
                filter_type = ftype

            lc = LayerSymbologyConfig(
                layer_name=lname,
                legend_label=legend_label,
                filter_type=filter_type,
                geometry_mode=geom_mode,
                renderer_type=renderer_type,
                field=field,
                classification_mode=classification_mode,
                num_classes=num_classes,
                manual_breaks=manual_breaks,
                palette=palette,
                color_rgb=color_rgb,
                symbol_size_mm=symbol_size,
                symbol_shape=symbol_shape,
            )
            prof.layers[lname] = lc

    _save_config_to_file(CONFIG)
    logger.info(
        "Configuration enregistrée dans src/ofbilan/cartographie/config_cartes.py "
        "(profils: %s)",
        ", ".join(profile_ids),
    )


def _save_config_to_file(cfg: "GlobalConfig") -> None:
    """Écrit la configuration dans config_cartes.py (via le writer partagé)."""
    from config_cartes_writer import write_config_file

    cfg_path = SCRIPT_DIR / "config_cartes.py"
    write_config_file(cfg, cfg_path)


def _apply_qgis_override_to_profile(prof: "ProfileConfig", override: dict) -> "ProfileConfig":
    """Applique mots-clés et NATINFs sur un profil QGIS (filtres point_ctrl_keywords et natinfs)."""
    if not override or not prof:
        return prof
    from dataclasses import replace

    keywords = override.get("keywords")
    columns = override.get("keyword_columns")
    natinf_pve = override.get("natinf_pve")
    natinf_pj = override.get("natinf_pj")
    updates: dict = {}
    if keywords:
        updates["keywords"] = [str(k).strip() for k in keywords if str(k).strip()]
    if columns:
        updates["keyword_columns"] = [str(c).strip() for c in columns if str(c).strip()]
    if natinf_pve is not None:
        updates["natinf_pve"] = natinf_pve
    if natinf_pj is not None:
        updates["natinf_pj"] = natinf_pj

    prof = replace(prof, **updates)
    new_layers: dict = {}
    for key, lcfg in prof.layers.items():
        layer_name = str(getattr(lcfg, "layer_name", "") or key).lower()
        if "point_ctrl" in layer_name and lcfg.filter_type in (
            "point_ctrl_theme",
            "point_ctrl_global",
            "point_ctrl",
            "",
        ):
            new_layers[key] = replace(lcfg, filter_type="point_ctrl_keywords")
        else:
            new_layers[key] = lcfg
    return replace(prof, layers=new_layers)


def run_export(
    profile_ids: List[str],
    date_deb: Optional[str] = None,
    date_fin: Optional[str] = None,
    dept_code: Optional[str] = None,
    *,
    qgis_overrides: Optional[Dict[str, dict]] = None,
    diffusion: str = "interne",
) -> None:
    """Génère les cartes en mode non interactif à partir de la config."""
    CONFIG = get_effective_config()

    effective_dept = (
        str(dept_code).strip()
        if dept_code
        else str(getattr(CONFIG, "departement_code", "21")).strip()
    )
    project_path = _resolve_qgis_project_path(CONFIG.project_qgis_path)
    try:
        display_path = Path(project_path).relative_to(PROJECT_ROOT)
    except ValueError:
        display_path = project_path

    logger.info(
        "run_export : profils=%s, département=%s, projet QGIS=%s",
        ", ".join(profile_ids),
        effective_dept,
        display_path,
    )
    if not HAS_QGIS:
        logger.info("QGIS non disponible, basculement vers le générateur Matplotlib.")
        from generateur_matplotlib import exporter_carte_matplotlib
        
        env_out_dir = os.getenv("CARTO_OUTPUT_DIR")
        out_dir = Path(env_out_dir) if env_out_dir else (Path(CONFIG.output_dir) if CONFIG.output_dir else OUT_DIR_CARTES)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        for pid in profile_ids:
            prof = CONFIG.profiles.get(pid)
            if not prof: continue
            out_path = out_dir / getattr(prof, "output_filename", f"carte_{pid}.png")
            try:
                exporter_carte_matplotlib(prof, out_path, effective_dept, [], PROJECT_ROOT)
                from ofbilan.cartographie.pochoir_helper import write_map_dept_marker
                write_map_dept_marker(out_path, effective_dept)
            except Exception as e:
                logger.error(f"Erreur avec le generateur matplotlib pour {pid} : {e}")
        return

    if not load_project(project_path):
        raise RuntimeError(f"Impossible de charger le projet QGIS : {project_path}")

    set_basemap_visibility(CONFIG.basemap.enabled)

    env_out_dir = os.getenv("CARTO_OUTPUT_DIR")
    if env_out_dir:
        out_dir = Path(env_out_dir)
    else:
        out_dir = Path(CONFIG.output_dir) if CONFIG.output_dir else OUT_DIR_CARTES
    out_dir.mkdir(parents=True, exist_ok=True)
    dpi = CONFIG.output.dpi
    fmt = CONFIG.output.format

    carto_config = _ConfigExportOverride(CONFIG, effective_dept, diffusion)
    exported_paths: list[Path] = []

    # Alias ref_themes_ctrl → config cartes : types_usager = global_usagers
    _REF_TO_CARTE = {"types_usager": "global_usagers"}

    for pid in profile_ids:
        config_id = _REF_TO_CARTE.get(pid, pid)
        prof = CONFIG.profiles.get(config_id)

        # Rétrocompatibilité : chasse_agrainage → chasse (ref/carte_chasse.png)
        if not prof and pid == "chasse":
            prof_old = CONFIG.profiles.get("chasse_agrainage")
            if prof_old:
                from dataclasses import replace
                prof = replace(prof_old, id="chasse", output_filename="carte_chasse.png")
        # Résolution si c'est une sous-carte (ex: global_resultats -> profil: global, carte: resultats)
        carte_filtre = None
        if not prof:
            for base_pid, base_prof in CONFIG.profiles.items():
                if pid.lower().startswith(f"{base_pid.lower()}_"):
                    sub_id = pid[len(base_pid)+1:]
                    # Vérifier si sub_id est une carte active ou dans les définitions par défaut
                    cartes_possibles = getattr(base_prof, 'cartes_actives', []) or ["domaines", "usagers", "resultats", "procedures"]
                    if sub_id in cartes_possibles or (hasattr(base_prof, 'cartes_definitions') and sub_id in base_prof.cartes_definitions):
                        prof = base_prof
                        carte_filtre = sub_id
                        break

        if not prof:
            logger.warning("Profil ou sous-carte '%s' inconnu. Ignoré.", pid)
            continue

        if qgis_overrides and config_id in qgis_overrides:
            prof = _apply_qgis_override_to_profile(prof, qgis_overrides[config_id])

        # Surcharge éventuelle des dates de période par la ligne de commande
        if date_deb:
            prof.date_deb = date_deb
        if date_fin:
            prof.date_fin = date_fin

        prof = adapt_profile_texts_for_department(prof, effective_dept)

        logger.info(
            "Profil: %s (période %s → %s, département %s)",
            pid,
            prof.date_deb,
            prof.date_fin,
            effective_dept,
        )

        cartes_a_generer = prof.cartes_actives if hasattr(prof, 'cartes_actives') and prof.cartes_actives else ["defaut"]
        if carte_filtre:
            cartes_a_generer = [carte_filtre]

        for carte_id in cartes_a_generer:
            import copy
            
            # Application de la définition de carte courante
            if hasattr(prof, 'cartes_definitions') and carte_id in prof.cartes_definitions:
                map_def = prof.cartes_definitions[carte_id]
                prof.title_main = map_def.title_main
                prof.output_filename = f"carte_{prof.id}_{carte_id}.png"
                prof.layers = copy.deepcopy(map_def.layers)
            else:
                prof.output_filename = f"carte_{prof.id}.png"
                
            # Intégration dynamique du pochoir (Lot 2)
            if hasattr(prof, 'pochoir') and prof.pochoir and prof.pochoir != "aucun":
                from config_cartes_model import LayerSymbologyConfig
                pochoir_name = prof.pochoir if prof.pochoir.startswith("pochoir_") else f"pochoir_{prof.pochoir}"
                if pochoir_name == "pochoir_departement":
                    pochoir_name = f"pochoir_sd{effective_dept}"
                prof.layers["pochoir"] = LayerSymbologyConfig(
                    layer_name=pochoir_name,
                    layer_role="pochoir"
                )
                
            # Intégration dynamique des couches de contexte (Lot 2)
            if hasattr(prof, 'couches_vecteurs_extra'):
                for extra in prof.couches_vecteurs_extra:
                    if extra not in prof.layers:
                        prof.layers[extra] = LayerSymbologyConfig(layer_name=extra, layer_role="contexte")

            logger.info("  -> Génération : %s", prof.output_filename)

            proj = QgsProject.instance()
            available_names = [lyr.name() for lyr in proj.mapLayers().values()]
            legend_labels_map: Dict[str, str] = {}
            global_sym_src = getattr(CONFIG, "symbology_source", "yaml")
            prof_sym_src = getattr(prof, "symbology_source", global_sym_src)

            from layer_resolver import should_apply_yaml_symbology
            from layout_layers import is_operational_layer

            layout = get_layout_by_name(prof.layout_name) if getattr(prof, "layers_from_layout", False) else None
            layers_to_process = resolve_profile_layers(prof, layout=layout)

            # Cacher toutes les couches métiers et purger les filtres avant d'appliquer celles du profil
            root = proj.layerTreeRoot()
            for layer in proj.mapLayers().values():
                if is_operational_layer(layer.name()):
                    # Purge du filtre
                    try:
                        layer.setSubsetString("")
                    except Exception:
                        pass
                    node = root.findLayer(layer.id())
                    if node:
                        node.setItemVisibilityChecked(False)

            legend_data = []

            # Collecte explicite des couches à rendre dans la carte
            # QgsLayoutItemMap.setLayers dessine le premier élément de la liste au-dessus (TOP).
            # Le YAML listant les polygones (fond) avant les points (premier plan), 
            # il faut inverser l'ordre pour que les points ne soient pas masqués.
            layers_to_render = []
            for lname, lcfg in reversed(list(layers_to_process.items())):
                # Construction du prefix identique à celui de l'orchestrateur
                base_prefix = getattr(prof, "_export_prefix", None) or prof.id
                profil_prefix = f"{base_prefix}_{effective_dept}" if str(effective_dept).strip() else base_prefix

                resolved_infos = resolve_layers_for_config(
                    lname,
                    lcfg,
                    available_names=available_names,
                    date_deb=prof.date_deb,
                    date_fin=prof.date_fin,
                    dept_code=effective_dept,
                    profil_prefix=profil_prefix,
                )
                
                # Si aucune couche n'a été trouvée
                if not resolved_infos or (len(resolved_infos) == 1 and not resolved_infos[0][1]):
                    logger.warning(
                        "Couche '%s' introuvable pour le profil '%s' (rôle=%s, ignorée). Couches du projet: %s",
                        lcfg.layer_name,
                        pid,
                        getattr(lcfg, "layer_role", None),
                        available_names,
                    )
                    continue

                for layer, resolved_name, resolve_source in resolved_infos:
                    if not resolved_name:
                        continue
                        
                    if not layer or not layer.isValid():
                        # Tentative de réparation de la source de données pour les couches PNF
                        if resolved_name in ("Coeur_data_gouv_PNForets", "coeur_parc"):
                            from ofbilan.common.chargeurs_donnees import get_pnf_coeur_shp_path
                            coeur_path = get_pnf_coeur_shp_path(PROJECT_ROOT)
                            if coeur_path.exists():
                                if layer:
                                    try:
                                        QgsProject.instance().removeMapLayer(layer.id())
                                    except Exception:
                                        pass
                                layer = QgsVectorLayer(str(coeur_path), resolved_name, "ogr")
                                if layer.isValid():
                                    from PyQt5.QtGui import QColor
                                    from qgis.core import QgsFillSymbol, QgsSingleSymbolRenderer, QgsSimpleFillSymbolLayer
                                    sl = QgsSimpleFillSymbolLayer()
                                    sl.setFillColor(QColor(34, 139, 34, 128))  # 50% transparency
                                    sl.setStrokeColor(QColor(34, 139, 34, 255))
                                    sl.setStrokeWidth(0.8)
                                    sym = QgsFillSymbol()
                                    sym.changeSymbolLayer(0, sl)
                                    layer.setRenderer(QgsSingleSymbolRenderer(sym))
                                    QgsProject.instance().addMapLayer(layer, True)
                        elif resolved_name in ("AOA_2021_PNForets", "AOA_2021_PNForet_21", "AOA_2021_PNForets.shp"):
                            from ofbilan.common.chargeurs_donnees import get_pnf_aoa_shp_path
                            aoa_path = get_pnf_aoa_shp_path(PROJECT_ROOT)
                            if aoa_path.exists():
                                if layer:
                                    try:
                                        QgsProject.instance().removeMapLayer(layer.id())
                                    except Exception:
                                        pass
                                layer = QgsVectorLayer(str(aoa_path), resolved_name, "ogr")
                                if layer.isValid():
                                    QgsProject.instance().addMapLayer(layer, True)
                                    
                    if not layer or not layer.isValid():
                        continue
                        
                    if resolved_name in ("Coeur_data_gouv_PNForets", "coeur_parc"):
                        try:
                            from PyQt5.QtGui import QColor
                            from qgis.core import QgsFillSymbol, QgsSingleSymbolRenderer, QgsSimpleFillSymbolLayer
                            sl = QgsSimpleFillSymbolLayer()
                            sl.setFillColor(QColor(34, 139, 34, 128))  # 50% transparency
                            sl.setStrokeColor(QColor(34, 139, 34, 255))
                            sl.setStrokeWidth(0.8)
                            sym = QgsFillSymbol()
                            sym.changeSymbolLayer(0, sl)
                            layer.setRenderer(QgsSingleSymbolRenderer(sym))
                            layer.triggerRepaint()
                        except Exception as e:
                            logger.error("Erreur lors de l'application de la symbologie coeur_parc : %s", e)

                    layers_to_render.append(layer)

                    is_pnf = resolved_name in ("Coeur_data_gouv_PNForets", "AOA_2021_PNForet_21", "coeur_parc")
                    if is_pnf and str(effective_dept) not in ("21", "52"):
                        layers_to_render.remove(layer)
                        continue

                    if is_pnf:
                        pass # No need to clip PNF layers manually, the inverted polygon pochoir masks the outside visually

                    if resolve_source != "exact":
                        logger.info(
                            "  → Couche résolue '%s' → '%s' (%s)",
                            lcfg.layer_name,
                            resolved_name,
                            resolve_source,
                        )
                    else:
                        logger.info("  → Couche: %s", resolved_name)

                    # Rendre la couche visible et s'assurer que ses groupes parents le sont aussi
                    node = root.findLayer(layer.id())
                    if node:
                        node.setItemVisibilityChecked(True)
                        parent = node.parent()
                        while parent and parent != root:
                            parent.setItemVisibilityChecked(True)
                            parent = parent.parent()

                    if lcfg.legend_label:
                        legend_labels_map[resolved_name] = lcfg.legend_label

                    is_pochoir = "pochoir" in lcfg.layer_name.lower() or "pochoir" in resolved_name.lower()
                    if is_pochoir:
                        apply_pochoir_inverted_symbology(layer)
                    elif should_apply_yaml_symbology(
                        getattr(lcfg, "symbology_source", None),
                        prof_sym_src,
                        global_sym_src,
                    ):
                        apply_layer_symbology(layer, lcfg, diffusion=getattr(carto_config, "diffusion", "interne"))
                    else:
                        logger.debug("  Symbologie QGIS conservée pour '%s'", resolved_name)

                    # Heuristique pour filter_type si non précisé dans le YAML
                    if not getattr(lcfg, "filter_type", None):
                        from layout_layers import infer_filter_type_for_layer
                        lcfg.filter_type = infer_filter_type_for_layer(resolved_name, pid, prof)

                    apply_date_filter(layer, lcfg, prof.date_deb, prof.date_fin, config=carto_config, profile=prof)

                    # Log et alerte sur le nombre d'entités après filtrage
                    try:
                        f_count = layer.featureCount()
                        logger.info("    -> Couche '%s' : %d entité(s) après filtrage", resolved_name, f_count)
                        if f_count == 0 and getattr(lcfg, "layer_role", None) != "pochoir" and getattr(lcfg, "layer_role", None) != "contexte":
                            logger.warning(
                                "    ⚠️ [VIDE] La couche '%s' ne contient AUCUNE entité avec les filtres actuels "
                                "(département=%s, période=%s à %s) !",
                                resolved_name,
                                effective_dept,
                                prof.date_deb,
                                prof.date_fin,
                            )
                    except Exception as exc:
                        logger.debug("Impossible d'obtenir le nombre d'entités pour '%s': %s", resolved_name, exc)

                    # Extraction pour la légende PIL
                    legend_info = _extract_legend_info(layer, lcfg)
                    if legend_info:
                        legend_data.append(legend_info)

            # Ajouter les fonds de plan explicitement (dessinés en dernier dans la liste QGIS = au fond de la carte)
            from layout_layers import is_basemap_layer
            for layer in proj.mapLayers().values():
                if is_basemap_layer(layer.name()):
                    node = root.findLayer(layer.id())
                    if node and node.isVisible():
                        layers_to_render.append(layer)

            # Ordre de rendu (QGIS : index 0 = premier plan)
            # 1. Pochoirs (doit masquer tout ce qui dépasse)
            # 2. Points (PEJ, PVe, etc.)
            # 3. Contexte (coeur_parc, aoa...)
            # 4. Fonds de carte (déjà à la fin)
            pochoir_layers = [lyr for lyr in layers_to_render if "pochoir" in lyr.name().lower()]
            context_layers = [lyr for lyr in layers_to_render if lyr.name().lower() in ("coeur_parc", "coeur_data_gouv_pnforets", "aoa_2021_pnforet_21")]
            basemap_layers = [lyr for lyr in layers_to_render if is_basemap_layer(lyr.name())]
            other_layers = [
                lyr for lyr in layers_to_render
                if lyr not in pochoir_layers
                and lyr not in context_layers
                and lyr not in basemap_layers
            ]
            
            layers_to_render = pochoir_layers + other_layers + context_layers + basemap_layers

            out_path = out_dir / prof.output_filename

            exported = export_layout(
                prof,
                out_path,
                dpi=dpi,
                fmt=fmt,
                legend_labels_map=legend_labels_map or None,
                dept_code=effective_dept,
                layers_to_render=layers_to_render,
            )

            png_path = out_path.with_suffix(".png")
            if exported and png_path.exists():
                # Dessiner la légende avec Pillow par-dessus l'export
                try:
                    if not legend_data:
                        logger.warning("  Aucune donnée de légende à dessiner pour %s", png_path.name)
                    _draw_legend_on_image(png_path, legend_data)
                    logger.info("  Légende dessinée sur %s", png_path.name)
                except Exception as e:
                    logger.error("  Erreur de dessin de légende sur %s : %s", png_path.name, e)

                # Marqueur département indépendant de la légende (requis hors SD21 legacy)
                from ofbilan.cartographie.pochoir_helper import (
                    map_staleness_marker_path,
                    write_map_dept_marker,
                )

                write_map_dept_marker(png_path, effective_dept)
                marker_path = map_staleness_marker_path(png_path, effective_dept)
                exported_paths.append(png_path)
                logger.info(
                    "SUCCESS carte %s (département %s) → %s ; marqueur %s",
                    pid,
                    effective_dept,
                    png_path.resolve(),
                    marker_path.name,
                )
            elif not exported:
                logger.error("Échec export layout carte %s (département %s)", pid, effective_dept)

    if exported_paths:
        logger.info(
            "run_export terminé : %d carte(s) pour le département %s dans %s",
            len(exported_paths),
            effective_dept,
            out_dir.resolve(),
        )
    else:
        logger.error(
            "run_export terminé sans PNG produit (profils demandés : %s, département %s)",
            ", ".join(profile_ids),
            effective_dept,
        )


def run_from_qgis_console(profile_ids=None, gui=False):
    """À appeler depuis la console Python de QGIS (Ctrl+Alt+P).
    Ne réinitialise pas QGIS — à utiliser uniquement quand QGIS est déjà ouvert.

    Exemples:
        run_from_qgis_console()                    # Génère les cartes (agrainage + chasse)
        run_from_qgis_console(["agrainage"])        # Un seul profil
        run_from_qgis_console(gui=True)             # Ouvre l'interface de config des couches
    """
    _check_qgis()
    CONFIG = get_effective_config()

    project_path = _resolve_qgis_project_path(CONFIG.project_qgis_path)
    if not load_project(project_path):
        return

    if gui:
        from gui_config_cartes import run_gui
        run_gui(init_qgis=False)
        return

    ids = profile_ids or ["agrainage", "chasse", "piegeage"]
    run_export(ids)


def main() -> None:
    _check_qgis()

    parser = argparse.ArgumentParser(description="Génération des cartes bilans agrainage / chasse / piégeage")
    parser.add_argument(
        "profiles",
        nargs="?",
        default="tous",
        help="Profil(s) à traiter: agrainage, chasse, piegeage, ou tous",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Mode interactif: configurer la symbologie puis enregistrer dans config_cartes.py",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Ouvrir l'interface graphique pour configurer les couches.",
    )
    parser.add_argument(
        "--date-deb",
        type=str,
        default=None,
        help="Date de début (YYYY-MM-DD) pour filtrer les couches.",
    )
    parser.add_argument(
        "--date-fin",
        type=str,
        default=None,
        help="Date de fin (YYYY-MM-DD) pour filtrer les couches.",
    )
    parser.add_argument(
        "--dept-code",
        type=str,
        default=None,
        help="Code département (ex: 21). Surcharge la config pour cet export.",
    )
    parser.add_argument(
        "--diffusion",
        type=str,
        default="interne",
        help="Niveau de diffusion (interne, externe).",
    )
    args = parser.parse_args()

    if args.gui:
        from gui_config_cartes import run_gui
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            del os.environ["QT_QPA_PLATFORM"]
        app = init_qgis_gui()
        try:
            run_gui(init_qgis=False)
        finally:
            app.exitQgis()
        return

    prof_arg = args.profiles.strip().lower()
    if prof_arg == "tous":
        # Liste officielle depuis ref/ref_themes_ctrl.csv (aligné avec les bilans)
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            themes = _load_ref_themes_ctrl_safe(Path(PROJECT_ROOT))
            profile_ids = [t["id"] for t in themes] if themes else []
        except Exception as e:
            logger.debug("Chargement ref_themes_ctrl échoué (%s), fallback sur config.", e)
            profile_ids = []
        if not profile_ids:
            CONFIG = get_effective_config()
            profile_ids = list(CONFIG.profiles.keys())
    else:
        profile_ids = [p.strip() for p in prof_arg.split(",") if p.strip()]

    override_date_deb = args.date_deb
    override_date_fin = args.date_fin
    override_dept_code = args.dept_code

    # En mode export, si période ou département non fournis : utiliser uniquement la configuration,
    # sans aucune saisie interactive.
    if not args.interactive:
        CONFIG = get_effective_config()
        first_prof = next(iter(CONFIG.profiles.values()), None)

        if override_date_deb is None:
            override_date_deb = getattr(first_prof, "date_deb", None) if first_prof else None
        if override_date_fin is None:
            override_date_fin = getattr(first_prof, "date_fin", None) if first_prof else None
        if override_dept_code is None:
            override_dept_code = getattr(CONFIG, "departement_code", "21")

        # Si, malgré tout, des valeurs restent manquantes, on ne tente pas de poser de questions :
        # on signale simplement l'erreur pour que la configuration ou la ligne de commande soient complétées.
        if override_date_deb is None or override_date_fin is None or override_dept_code is None:
            logger.error(
                "Dates de période ou code département manquants. "
                "Fournir --date-deb, --date-fin et --dept-code ou compléter la configuration "
                "(profils et departement_code)."
            )
            sys.exit(1)

    app = init_qgis_headless()

    try:
        CONFIG = get_effective_config()
        if args.interactive:
            from config_cartes import CONFIG as CONFIG_CARTES
            if not load_project(_resolve_qgis_project_path(CONFIG_CARTES.project_qgis_path)):
                sys.exit(1)
            run_interactive_wizard(profile_ids)
        else:
            run_export(
                profile_ids,
                date_deb=override_date_deb,
                date_fin=override_date_fin,
                dept_code=override_dept_code,
                diffusion=args.diffusion,
            )
    except Exception as e:
        logger.exception("Erreur lors de la génération des cartes: %s", e)
        raise
    finally:
        app.exitQgis()


def _extract_legend_info(layer, lcfg):
    """Extrait les informations de légende (titre, items) depuis le QgsVectorLayer."""
    is_coeur = "coeur_parc" in layer.name().lower() or "coeur_data_gouv_pnforets" in layer.name().lower()
    if "pochoir" in lcfg.layer_name.lower() or "pochoir" in layer.name().lower() or ("contexte" == getattr(lcfg, "layer_role", "") and not is_coeur):
        return None
        
    title = lcfg.legend_label or lcfg.layer_name
    if is_coeur and (not title or title == "coeur_parc"):
        title = "Cœur de Parc National"
    items = []
    
    renderer = layer.renderer()
    if not renderer:
        return None
        
    rtype = renderer.type()
    
    # Lot 1 : Accès au renderer imbriqué pour les clusters
    if rtype == "pointCluster" and hasattr(renderer, "embeddedRenderer"):
        embedded = renderer.embeddedRenderer()
        if embedded:
            renderer = embedded
            rtype = renderer.type()

    # Extraction des valeurs réelles pour filtrer les catégories vides
    present_values = set()
    features_exist = False
    
    class_field = None
    if hasattr(renderer, "classAttribute") and callable(renderer.classAttribute):
        class_field = renderer.classAttribute()
    if not class_field:
        class_field = getattr(lcfg, "field", None)
    if class_field and not isinstance(class_field, str):
        class_field = str(class_field)
    
    if rtype in ("categorizedSymbol", "graduatedSymbol"):
        field_idx = layer.fields().indexFromName(class_field) if class_field else -1
        from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
        expr = QgsExpression(class_field) if (class_field and field_idx < 0) else None
        context = QgsExpressionContext()
        if expr:
            for scope in QgsExpressionContextUtils.globalProjectLayerScopes(layer):
                context.appendScope(scope)
            context.setFields(layer.fields())
            expr.prepare(context)
            
        for feature in layer.getFeatures():
            features_exist = True
            if field_idx >= 0:
                val = feature.attribute(field_idx)
            elif expr:
                context.setFeature(feature)
                val = expr.evaluate(context)
            else:
                val = None
            if val is not None:
                present_values.add(val)

    base_shape = getattr(lcfg, "symbol_shape", "square") or "square"
    if layer.geometryType() == 2 and getattr(lcfg, "geometry_mode", "") == "polygon_fill":
        base_shape = "square"

    if rtype == "singleSymbol":
        from qgis.core import QgsFeatureRequest
        has_any = False
        for _ in layer.getFeatures(QgsFeatureRequest().setLimit(1)):
            has_any = True
            break
        if not has_any:
            return None
        
        color = "#000000"
        if renderer.symbol() and renderer.symbol().color():
            c = renderer.symbol().color()
            color = f"#{c.red():02x}{c.green():02x}{c.blue():02x}{c.alpha():02x}"
            
        items.append({"label": title, "color": color, "shape": base_shape})
        title = None
    elif rtype == "categorizedSymbol":
        present_str_values = {str(v).lower() for v in present_values}
        for cat in renderer.categories():
            val = cat.value()
            if val == "" or val is None: continue
            if str(val).lower() not in present_str_values: continue
            
            color = "#000000"
            if cat.symbol() and cat.symbol().color():
                c = cat.symbol().color()
                color = f"#{c.red():02x}{c.green():02x}{c.blue():02x}{c.alpha():02x}"
                
            label = cat.label() or str(val)
            items.append({"label": label, "color": color, "shape": base_shape})
    elif rtype == "graduatedSymbol":
        present_numeric_values = []
        for v in present_values:
            try:
                present_numeric_values.append(float(v))
            except (ValueError, TypeError):
                pass
        seen_labels = set()
        for range_ in renderer.ranges():
            has_features = False
            for v in present_numeric_values:
                if range_.lowerValue() <= v <= range_.upperValue():
                    has_features = True
                    break
            if not has_features:
                continue
                
            color = "#000000"
            if range_.symbol() and range_.symbol().color():
                c = range_.symbol().color()
                color = f"#{c.red():02x}{c.green():02x}{c.blue():02x}{c.alpha():02x}"
            lower = range_.lowerValue()
            upper = range_.upperValue()
            if lower.is_integer() and upper.is_integer():
                low_int, upp_int = int(lower), int(upper)
                label = f"{low_int}" if low_int == upp_int else f"{low_int} - {upp_int}"
            else:
                label = f"{lower:.2f} - {upper:.2f}".replace('.', ',') if f"{lower:.2f}" != f"{upper:.2f}" else f"{lower:.2f}".replace('.', ',')
            if label in seen_labels:
                continue
            seen_labels.add(label)
            items.append({"label": label, "color": color, "shape": base_shape})
    elif rtype == "RuleRenderer" or rtype == "ruleRenderer":
        root_rule = renderer.rootRule()
        if root_rule:
            matching_rules = set()
            from qgis.core import QgsExpressionContext, QgsExpressionContextUtils
            context = QgsExpressionContext()
            for scope in QgsExpressionContextUtils.globalProjectLayerScopes(layer):
                context.appendScope(scope)
            context.setFields(layer.fields())
            
            for feature in layer.getFeatures():
                context.setFeature(feature)
                for rule in root_rule.children():
                    if rule.active() and rule.symbol():
                        expr = rule.filter()
                        if not expr or expr.evaluate(context):
                            matching_rules.add(rule.label())
            
            for rule in root_rule.children():
                if not rule.symbol(): continue
                label = rule.label()
                if not label or label.strip() == "": continue
                if label not in matching_rules: continue
                
                label_lower = label.lower()
                if "agri" in label_lower or "sécheresse" in label_lower or "secheresse" in label_lower:
                    continue
                    
                color = rule.symbol().color().name()
                items.append({"label": label, "color": color, "shape": base_shape})
            
    if not items:
        logger.warning("Aucun item de légende extrait pour la couche '%s' (rtype=%s)", title or lcfg.layer_name, rtype)
        return None
        
    return {"title": title, "items": items}


def _draw_legend_on_image(image_path, legend_data):
    """Dessine une légende via Pillow directement sur le PNG exporté."""
    if not legend_data:
        return
        
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow n'est pas installé, la légende ne peut pas être dessinée sur %s", image_path.name)
        return

    try:
        img = Image.open(image_path)
        img = img.convert("RGBA")
    except Exception as e:
        logger.error("Erreur d'ouverture de l'image %s : %s", image_path.name, e)
        return

    padding = 30
    rect_size = 35
    line_spacing = 50
    title_spacing = 55
    section_spacing = 20

    try:
        font_title = ImageFont.truetype("arialbd.ttf", 35)
        font_text = ImageFont.truetype("arial.ttf", 28)
    except IOError:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    import textwrap

    max_w = 0
    total_h = padding * 2
    
    for group in legend_data:
        title = group.get("title")
        if title:
            if hasattr(font_title, "getbbox"):
                w = font_title.getbbox(title)[2] - font_title.getbbox(title)[0]
            else:
                w = font_title.getsize(title)[0]
            max_w = max(max_w, w)
            total_h += title_spacing
        
        for item in group.get("items", []):
            label = item["label"]
            lines = textwrap.wrap(label, width=30) if len(label) > 30 else [label]
            max_item_w = 0
            for line in lines:
                if hasattr(font_text, "getbbox"):
                    w = font_text.getbbox(line)[2] - font_text.getbbox(line)[0]
                else:
                    w = font_text.getsize(line)[0]
                max_item_w = max(max_item_w, w)
            max_w = max(max_w, rect_size + 15 + max_item_w)
            total_h += line_spacing + (len(lines) - 1) * 35
            
        total_h += section_spacing
        
    total_h -= section_spacing
    total_w = max_w + padding * 2

    img_w, img_h = img.size

    # La carte prend 232mm sur 297mm de largeur totale
    # La colonne de droite commence à img_w * (232 / 297)
    col_start = int(img_w * (232 / 297))
    col_center = col_start + (img_w - col_start) // 2
    
    # Centrer la légende sur cet axe et s'assurer qu'elle ne dépasse pas le bord droit
    start_x = col_center - (total_w // 2)
    right_margin = 30
    if start_x + total_w > img_w - right_margin:
        start_x = img_w - total_w - right_margin
    
    # Marge haute sous le bandeau bleu du haut (10mm)
    margin_top = int(img_h * (20 / 210))  # environ 20mm pour laisser de la place
    start_y = margin_top
    
    # Si la légende descend trop bas (sous le logo)
    if start_y + total_h > img_h - int(img_h * (30 / 210)):
        start_y = max(margin_top, img_h - total_h - int(img_h * (30 / 210)))

    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    rect_coords = [start_x, start_y, start_x + total_w, start_y + total_h]
    overlay_draw.rectangle(rect_coords, fill=(255, 255, 255, 220), outline=(100, 100, 100, 255), width=2)
    
    cur_y = start_y + padding
    
    def hex_to_rgb(hex_str):
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 6:
            return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16), 255)
        elif len(hex_str) == 8:
            return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16), int(hex_str[6:8], 16))
        return (0, 0, 0, 255)

    for group in legend_data:
        title = group.get("title")
        if title:
            overlay_draw.text((start_x + padding, cur_y), title, font=font_title, fill=(0, 0, 0, 255))
            cur_y += title_spacing
            
        for item in group.get("items", []):
            rgb = hex_to_rgb(item["color"])
            shape = item.get("shape", "square")
            lines = textwrap.wrap(item["label"], width=30) if len(item["label"]) > 30 else [item["label"]]
            box_coords = [start_x + padding, cur_y, start_x + padding + rect_size, cur_y + rect_size]
            
            if shape == "circle":
                overlay_draw.ellipse(box_coords, fill=rgb, outline=(0, 0, 0, 255), width=1)
            elif shape == "diamond":
                mx = start_x + padding + rect_size / 2
                my = cur_y + rect_size / 2
                overlay_draw.polygon([
                    (mx, cur_y),
                    (start_x + padding + rect_size, my),
                    (mx, cur_y + rect_size),
                    (start_x + padding, my)
                ], fill=rgb, outline=(0, 0, 0, 255))
            elif shape == "triangle":
                mx = start_x + padding + rect_size / 2
                overlay_draw.polygon([
                    (mx, cur_y),
                    (start_x + padding + rect_size, cur_y + rect_size),
                    (start_x + padding, cur_y + rect_size)
                ], fill=rgb, outline=(0, 0, 0, 255))
            else:
                overlay_draw.rectangle(box_coords, fill=rgb, outline=(0, 0, 0, 255), width=1)
            for j, line in enumerate(lines):
                overlay_draw.text((start_x + padding + rect_size + 15, cur_y - 2 + j * 35), line, font=font_text, fill=(0, 0, 0, 255))
            cur_y += line_spacing + (len(lines) - 1) * 35
            
        cur_y += section_spacing

    img = Image.alpha_composite(img, overlay)
    img = img.convert("RGB")
    try:
        img.save(image_path)
    except Exception as e:
        logger.error("Erreur de sauvegarde de la légende sur %s : %s", image_path.name, e)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Erreur fatale: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.exception("Erreur fatale: %s", e)
        sys.exit(1)
