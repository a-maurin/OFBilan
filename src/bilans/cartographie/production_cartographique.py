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

# Dossier du module cartographie (src/bilans/cartographie)
SCRIPT_DIR = Path(__file__).resolve().parent
PARAM_DIR = SCRIPT_DIR / "param"
PROFILS_CARTES_YAML = PARAM_DIR / "profils_cartes.yaml"
SYMBOLOGIES_YAML = PARAM_DIR / "symbologies.yaml"

# Logger principal du module
logger = logging.getLogger(__name__)
if not logger.handlers:
    _log_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=_log_fmt, datefmt="%H:%M:%S")

PROJECT_ROOT = SCRIPT_DIR.parents[3]
OUT_DIR_CARTES = PROJECT_ROOT / "data" / "out" / "generateur_de_cartes"
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from bilans.chemins_projet import get_qgis_project_path

_DEFAULT_QGIS_PROJECT = get_qgis_project_path()


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
        QgsLayoutItemPicture,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsStyle,
        QgsWkbTypes,
        QgsCentroidFillSymbolLayer,
        QgsField,
    )
    from qgis.core import QgsLayerTreeLayer
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


def _load_profiles_from_param() -> Optional[Dict[str, "ProfileConfig"]]:
    """
    Charge les profils depuis param/profils_cartes.yaml (et param/symbologies.yaml si présent).
    Retourne un dict id_profil -> ProfileConfig ou None si les fichiers de paramétrage sont absents.
    """
    if not PROFILS_CARTES_YAML.exists():
        return None
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML non installé : param/profils_cartes.yaml ignoré, utilisation de config_cartes.py.")
        return None

    symbologies: Dict[str, Dict[str, Any]] = {}
    if SYMBOLOGIES_YAML.exists():
        try:
            with open(SYMBOLOGIES_YAML, "r", encoding="utf-8") as f:
                symbologies = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Erreur lecture param/symbologies.yaml : %s", e)

    try:
        with open(PROFILS_CARTES_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.warning("Erreur lecture param/profils_cartes.yaml : %s", e)
        return None

    profiles_data = data.get("profiles") if isinstance(data, dict) else None
    if not profiles_data:
        return None

    from config_cartes_model import (
        ProfileConfig,
        LayerSymbologyConfig,
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
        base["layer_name"] = layer_name
        legend = base.get("legend_label", layer_name)
        filter_type = base.get("filter_type", "")
        if filter_type not in valid_filter_types:
            filter_type = ""
        return LayerSymbologyConfig(
            layer_name=base["layer_name"],
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
            visible=bool(base.get("visible", True)),
        )

    result: Dict[str, ProfileConfig] = {}
    for pid, pdata in profiles_data.items():
        if not isinstance(pdata, dict):
            continue
        layers_raw = pdata.get("layers") or {}
        layers: Dict[str, LayerSymbologyConfig] = {}
        for lname, lval in layers_raw.items():
            if isinstance(lval, dict):
                lcfg = _layer_config_from_dict(lname, lval, symbologies)
            else:
                lcfg = LayerSymbologyConfig(layer_name=lname, legend_label=lname)
            layers[lname] = lcfg
        result[pid] = ProfileConfig(
            id=str(pdata.get("id", pid)),
            title=str(pdata.get("title", pid)),
            layout_name=str(pdata.get("layout_name", "")),
            output_filename=str(pdata.get("output_filename", f"carte_{pid}.png")),
            date_deb=str(pdata.get("date_deb", "2025-01-01")),
            date_fin=str(pdata.get("date_fin", "2026-02-05")),
            layers=layers,
            title_main=str(pdata.get("title_main", "")),
            subtitle=str(pdata.get("subtitle", "")),
            layout_title_item_id=str(pdata.get("layout_title_item_id", "titre_principal")),
            layout_subtitle_item_id=str(pdata.get("layout_subtitle_item_id", "sous_titre")),
            theme_id=pdata.get("theme_id") or None,
        )

    # Profils cartes par défaut : thèmes de ref_themes_ctrl sans entrée dans le YAML
    try:
        from common.loaders import load_ref_themes_ctrl
        themes = load_ref_themes_ctrl(PROJECT_ROOT)
        point_ctrl_layer = "point_ctrl_20260205_wgs84"
        layout_default = "Bilan 2025 / 2026 - Agrainage illicite - Côte d'Or"
        for t in themes:
            tid = t.get("id", "")
            if not tid or tid in result:
                continue
            label = t.get("label", tid.replace("_", " "))
            points_cfg = _layer_config_from_dict(
                point_ctrl_layer,
                {"symbology_ref": "points_default", "layer_name": point_ctrl_layer, "filter_type": "point_ctrl_theme"},
                symbologies,
            )
            result[tid] = ProfileConfig(
                id=tid,
                title=f"Bilan {label} — Côte-d'Or",
                layout_name=layout_default,
                output_filename=f"carte_{tid}.png",
                date_deb="2025-01-01",
                date_fin="2026-02-05",
                layers={
                    "pochoir_sd21": _layer_config_from_dict(
                        "pochoir_sd21",
                        {"symbology_ref": "pochoir", "layer_name": "pochoir_sd21"},
                        symbologies,
                    ),
                    point_ctrl_layer: points_cfg,
                },
                title_main=f"{label} — Côte-d'Or",
                subtitle="",
                layout_title_item_id="titre_principal",
                layout_subtitle_item_id="sous_titre",
                theme_id=tid,
            )
        if themes:
            logger.info("Profils cartes (YAML + défaut) : %s", list(result.keys()))
    except Exception as e:
        logger.warning("Impossible d'ajouter les profils cartes par défaut : %s", e)

    logger.info("Profils chargés depuis param/profils_cartes.yaml : %s", list(result.keys()))
    return result


def get_effective_config():
    """Retourne la config globale à utiliser : paramètres YAML si présents, sinon config_cartes.CONFIG.
    Les profils définis dans config_cartes (édités via la GUI) priment sur ceux du YAML."""
    from config_cartes import CONFIG
    from config_cartes_model import GlobalConfig

    param_profiles = _load_profiles_from_param()
    if param_profiles is not None:
        # Les profils édités dans la GUI (config_cartes) priment sur le YAML.
        for pid, prof in CONFIG.profiles.items():
            param_profiles[pid] = prof
        return GlobalConfig(
            project_qgis_path=CONFIG.project_qgis_path,
            kit_ofb_path=CONFIG.kit_ofb_path,
            output_dir=CONFIG.output_dir,
            basemap=CONFIG.basemap,
            output=CONFIG.output,
            profiles=param_profiles,
            natinf_pve=CONFIG.natinf_pve,
            natinf_pj=CONFIG.natinf_pj,
            departement_code=CONFIG.departement_code,
            chasse_theme_value=CONFIG.chasse_theme_value,
            piegeage_keywords=CONFIG.piegeage_keywords,
        )
    return CONFIG


class _ConfigDeptOverride:
    """Wrapper autour de CONFIG pour surcharger uniquement departement_code (export cartes)."""
    def __init__(self, base_config, departement_code_override: str):
        self._base = base_config
        self._dept = departement_code_override

    def __getattr__(self, name: str):
        if name == "departement_code":
            return self._dept
        return getattr(self._base, name)


def init_qgis_headless() -> None:
    """Initialise QGIS en mode headless (sans interface graphique)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QgsApplication([], False)
    app.initQgis()
    return app


def init_qgis_gui():
    """Initialise QGIS avec interface graphique (pour la GUI de configuration)."""
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


def apply_layer_symbology(layer, config: "LayerSymbologyConfig", geometry_mode_override: Optional[str] = None) -> None:
    """Applique la symbologie définie dans config à la couche."""
    from config_cartes import LayerSymbologyConfig

    geom_mode = geometry_mode_override or config.geometry_mode
    geom_type = layer.geometryType() if hasattr(layer, "geometryType") else None

    is_polygon = geom_type == QgsWkbTypes.PolygonGeometry if geom_type is not None else False

    if config.renderer_type == "single":
        if config.color_rgb:
            color = QColor(*config.color_rgb)
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
            layer.setRenderer(QgsSingleSymbolRenderer(marker))

    elif config.renderer_type == "graduated" and config.field:
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
        else:
            base_symbol = QgsFillSymbol.createSimple({"color": "31,120,180", "outline_color": "35,35,35"})

        if config.classification_mode == "quantile":
            mode = QgsGraduatedSymbolRenderer.Quantile
        elif config.classification_mode == "equal_interval":
            mode = QgsGraduatedSymbolRenderer.EqualInterval
        elif config.classification_mode == "jenks":
            mode = QgsGraduatedSymbolRenderer.Jenks
        else:
            mode = QgsGraduatedSymbolRenderer.EqualInterval

        renderer = QgsGraduatedSymbolRenderer.createRenderer(
            layer, config.field, config.num_classes, mode, base_symbol
        )
        style = QgsStyle.defaultStyle()
        color_ramp = style.colorRamp(config.palette) if style.colorRamp(config.palette) else style.colorRamp("Blues")
        if color_ramp:
            renderer.setSourceColorRamp(color_ramp)
        layer.setRenderer(renderer)

    elif config.renderer_type == "categorized" and config.field:
        # Palette : si palette contient des hex séparés par virgule, on les utilise ; sinon fallback.
        palette_colors: list[str] = []
        if isinstance(config.palette, str) and "#" in config.palette:
            palette_colors = [p.strip() for p in config.palette.split(",") if p.strip()]
        if not palette_colors:
            palette_colors = ["#003A76", "#53AB60", "#F4A261", "#E76F51", "#90BF83", "#4296CE"]

        # Récupérer les valeurs distinctes : champ réel ou expression
        values = []
        field_names = [f.name() for f in layer.fields()]
        if config.field in field_names:
            try:
                idx = layer.fields().indexFromName(config.field)
                values = sorted(list(layer.uniqueValues(idx)))
            except Exception:
                values = []
        else:
            # Expression (ex. CASE WHEN...) : évaluer sur un échantillon de features
            try:
                from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils

                expr = QgsExpression(config.field)
                ctx = QgsExpressionContext()
                ctx.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
                vals = set()
                req = QgsFeatureRequest().setNoAttributes(False)
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

        # Construire les catégories
        categories = []
        for i, v in enumerate(values):
            color = QColor(palette_colors[i % len(palette_colors)])
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
            categories.append(QgsRendererCategory(v, sym, str(v)))

        renderer = QgsCategorizedSymbolRenderer(config.field, categories)
        layer.setRenderer(renderer)

    layer.triggerRepaint()


def _build_pve_expression(field_names: set, date_deb: str, date_fin: str, config) -> Optional[str]:
    required = {"INF-NATINF", "INF-DEPART", "INF-DATE-I"}
    if not required.issubset(field_names):
        return None

    natinf_values = getattr(config, "natinf_pve", [27742])
    natinf_list = ", ".join(str(x) for x in natinf_values)
    depart = getattr(config, "departement_code", "21")
    return (
        f'"INF-NATINF" IN ({natinf_list}) AND "INF-DEPART" = {repr(depart)} '
        f"AND to_date(substr(\"INF-DATE-I\", 7, 4) || '-' || substr(\"INF-DATE-I\", 4, 2) || '-' || substr(\"INF-DATE-I\", 1, 2)) "
        f">= to_date('{date_deb}') AND "
        f"to_date(substr(\"INF-DATE-I\", 7, 4) || '-' || substr(\"INF-DATE-I\", 4, 2) || '-' || substr(\"INF-DATE-I\", 1, 2)) "
        f"<= to_date('{date_fin}')"
    )


def _build_pj_expression(field_names: set, date_deb: str, date_fin: str, config) -> Optional[str]:
    required = {"entite", "natinf", "date_saisine"}
    if not required.issubset(field_names):
        return None

    natinf_values = getattr(config, "natinf_pj", [27742, 25001])
    natinf_list = ", ".join(str(x) for x in natinf_values)
    depart = getattr(config, "departement_code", "21")
    return (
        f"\"entite\" = 'SD{depart}' AND \"natinf\" IN ({natinf_list}) "
        f"AND \"date_saisine\" >= '{date_deb}' AND \"date_saisine\" <= '{date_fin}'"
    )


def _build_point_ctrl_agrainage_expression(field_names: set, date_deb: str, date_fin: str, config) -> Optional[str]:
    nom_col = None
    if "nom_dossier" in field_names:
        nom_col = "nom_dossier"
    elif "nom_dossie" in field_names:
        nom_col = "nom_dossie"

    required = {"date_ctrl", "num_depart", "resultat"}
    if not nom_col or not required.issubset(field_names):
        return None

    deb_ymd = date_deb.replace("-", "")
    fin_ymd = date_fin.replace("-", "")
    depart = getattr(config, "departement_code", "21")
    return (
        f'"{nom_col}" LIKE \'%agrain%\' AND '
        f'"num_depart" = {repr(depart)} AND "resultat" = \'Conforme\' AND '
        f'(substr("date_ctrl", 7, 4) || substr("date_ctrl", 4, 2) || substr("date_ctrl", 1, 2)) >= \'{deb_ymd}\' AND '
        f'(substr("date_ctrl", 7, 4) || substr("date_ctrl", 4, 2) || substr("date_ctrl", 1, 2)) <= \'{fin_ymd}\''
    )


def _build_point_ctrl_chasse_expression(field_names: set, date_deb: str, date_fin: str, config) -> Optional[str]:
    required = {"date_ctrl", "num_depart", "resultat"}
    if not required.issubset(field_names):
        return None

    deb_ymd = date_deb.replace("-", "")
    fin_ymd = date_fin.replace("-", "")
    depart = getattr(config, "departement_code", "21")
    expr = (
        f'"num_depart" = {repr(depart)} AND "resultat" = \'Conforme\' AND '
        f'(substr("date_ctrl", 7, 4) || substr("date_ctrl", 4, 2) || substr("date_ctrl", 1, 2)) >= \'{deb_ymd}\' AND '
        f'(substr("date_ctrl", 7, 4) || substr("date_ctrl", 4, 2) || substr("date_ctrl", 1, 2)) <= \'{fin_ymd}\''
    )
    if "theme" in field_names:
        theme_val = getattr(config, "chasse_theme_value", "Chasse")
        expr = f'"theme" = {repr(theme_val)} AND ' + expr
    return expr


def _build_point_ctrl_global_expression(field_names: set, date_deb: str, date_fin: str, config) -> Optional[str]:
    """Filtre points de contrôle global : département + période (sans filtre thème, sans filtre résultat)."""
    required = {"date_ctrl", "num_depart"}
    if not required.issubset(field_names):
        return None

    deb_ymd = date_deb.replace("-", "")
    fin_ymd = date_fin.replace("-", "")
    depart = getattr(config, "departement_code", "21")
    return (
        f'"num_depart" = {repr(depart)} AND '
        f'(substr("date_ctrl", 7, 4) || substr("date_ctrl", 4, 2) || substr("date_ctrl", 1, 2)) >= \'{deb_ymd}\' AND '
        f'(substr("date_ctrl", 7, 4) || substr("date_ctrl", 4, 2) || substr("date_ctrl", 1, 2)) <= \'{fin_ymd}\''
    )


def _build_point_ctrl_theme_expression(
    field_names: set, date_deb: str, date_fin: str, config, theme_label: str
) -> Optional[str]:
    """Filtre points de contrôle par thème : theme/type_actio/nom_dossie contient le label du thème."""
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

    deb_ymd = date_deb.replace("-", "")
    fin_ymd = date_fin.replace("-", "")
    depart = getattr(config, "departement_code", "21")
    label_esc = (theme_label or "").replace("'", "''")

    like_parts = []
    if theme_col and label_esc:
        like_parts.append(f'"{theme_col}" LIKE \'%{label_esc}%\'')
    if type_col and label_esc:
        like_parts.append(f'"{type_col}" LIKE \'%{label_esc}%\'')
    if nom_col and label_esc:
        like_parts.append(f'"{nom_col}" LIKE \'%{label_esc}%\'')
    if not like_parts:
        return None
    text_cond = "(" + " OR ".join(like_parts) + ")"
    return (
        f'{text_cond} AND "num_depart" = {repr(depart)} AND '
        f'(substr("date_ctrl", 7, 4) || substr("date_ctrl", 4, 2) || substr("date_ctrl", 1, 2)) >= \'{deb_ymd}\' AND '
        f'(substr("date_ctrl", 7, 4) || substr("date_ctrl", 4, 2) || substr("date_ctrl", 1, 2)) <= \'{fin_ymd}\''
    )


def _build_point_ctrl_piegeage_expression(field_names: set, date_deb: str, date_fin: str, config) -> Optional[str]:
    """Filtre points de contrôle piégeage : nom_dossie/theme/type_actio contient un mot-clé piégeage."""
    nom_col = None
    if "nom_dossier" in field_names:
        nom_col = "nom_dossier"
    elif "nom_dossie" in field_names:
        nom_col = "nom_dossie"

    required = {"date_ctrl", "num_depart"}
    if not required.issubset(field_names):
        return None

    deb_ymd = date_deb.replace("-", "")
    fin_ymd = date_fin.replace("-", "")
    depart = getattr(config, "departement_code", "21")
    keywords = getattr(config, "piegeage_keywords", ["piégeage", "piège"])
    # Condition texte : (nom LIKE '%piégeage%' OR nom LIKE '%piège%' OR theme LIKE '%...' OR type_actio LIKE '%...')
    type_col = "type_action" if "type_action" in field_names else "type_actio" if "type_actio" in field_names else None
    theme_col = "theme" if "theme" in field_names else None

    like_parts = []
    for kw in keywords:
        kw_esc = kw.replace("'", "''")
        if nom_col:
            like_parts.append(f'"{nom_col}" LIKE \'%{kw_esc}%\'')
        if theme_col:
            like_parts.append(f'"{theme_col}" LIKE \'%{kw_esc}%\'')
        if type_col:
            like_parts.append(f'"{type_col}" LIKE \'%{kw_esc}%\'')
    if not like_parts:
        return None
    text_cond = "(" + " OR ".join(like_parts) + ")"
    return (
        f'{text_cond} AND "num_depart" = {repr(depart)} AND '
        f'(substr("date_ctrl", 7, 4) || substr("date_ctrl", 4, 2) || substr("date_ctrl", 1, 2)) >= \'{deb_ymd}\' AND '
        f'(substr("date_ctrl", 7, 4) || substr("date_ctrl", 4, 2) || substr("date_ctrl", 1, 2)) <= \'{fin_ymd}\''
    )


def _build_point_ctrl_theme_expression(
    field_names: set,
    date_deb: str,
    date_fin: str,
    config,
    theme_label: str,
) -> Optional[str]:
    """Filtre points de contrôle par thème : theme/type_actio/nom_dossie contient le label du thème."""
    nom_col = "nom_dossier" if "nom_dossier" in field_names else ("nom_dossie" if "nom_dossie" in field_names else None)
    type_col = "type_action" if "type_action" in field_names else ("type_actio" if "type_actio" in field_names else None)
    theme_col = "theme" if "theme" in field_names else None

    required = {"date_ctrl", "num_depart"}
    if not required.issubset(field_names):
        return None

    deb_ymd = date_deb.replace("-", "")
    fin_ymd = date_fin.replace("-", "")
    depart = getattr(config, "departement_code", "21")
    label_esc = theme_label.replace("'", "''")

    like_parts = []
    if nom_col:
        like_parts.append(f'"{nom_col}" LIKE \'%{label_esc}%\'')
    if theme_col:
        like_parts.append(f'"{theme_col}" LIKE \'%{label_esc}%\'')
    if type_col:
        like_parts.append(f'"{type_col}" LIKE \'%{label_esc}%\'')
    if not like_parts:
        return None

    text_cond = "(" + " OR ".join(like_parts) + ")"
    return (
        f'{text_cond} AND "num_depart" = {repr(depart)} AND '
        f'(substr("date_ctrl", 7, 4) || substr("date_ctrl", 4, 2) || substr("date_ctrl", 1, 2)) >= \'{deb_ymd}\' AND '
        f'(substr("date_ctrl", 7, 4) || substr("date_ctrl", 4, 2) || substr("date_ctrl", 1, 2)) <= \'{fin_ymd}\''
    )


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
    field_names = set(fields)

    expr: Optional[str] = None

    if filter_type == "pve":
        expr = _build_pve_expression(field_names, date_deb, date_fin, use_config)
    elif filter_type == "pj":
        expr = _build_pj_expression(field_names, date_deb, date_fin, use_config)
    elif filter_type == "point_ctrl_agrainage":
        expr = _build_point_ctrl_agrainage_expression(field_names, date_deb, date_fin, use_config)
    elif filter_type == "point_ctrl_chasse":
        expr = _build_point_ctrl_chasse_expression(field_names, date_deb, date_fin, use_config)
    elif filter_type == "point_ctrl_piegeage":
        expr = _build_point_ctrl_piegeage_expression(field_names, date_deb, date_fin, use_config)
    elif filter_type == "point_ctrl_global":
        expr = _build_point_ctrl_global_expression(field_names, date_deb, date_fin, use_config)
    elif filter_type == "point_ctrl_theme" and profile and getattr(profile, "theme_id", None):
        try:
            from common.loaders import load_ref_themes_ctrl
            themes = load_ref_themes_ctrl(PROJECT_ROOT)
            theme_entry = next((t for t in themes if t["id"] == profile.theme_id), None)
            theme_label = theme_entry["label"] if theme_entry else profile.theme_id.replace("_", " ")
            expr = _build_point_ctrl_theme_expression(
                field_names, date_deb, date_fin, use_config, theme_label
            )
        except Exception as e:
            logger.warning("Filtre point_ctrl_theme : impossible de charger le label pour %s : %s", profile.theme_id, e)

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
    """Active ou désactive les couches fond (XYZ, WMS)."""
    proj = QgsProject.instance()
    root = proj.layerTreeRoot()
    for layer in proj.mapLayers().values():
        lname = layer.name().lower()
        if any(x in lname for x in ["esri", "osm", "xyz", "wms", "wmts", "cartes ign", "plan ign"]):
            node = root.findLayer(layer.id())
            if node:
                node.setItemVisibilityChecked(enabled)


def _apply_legend_labels(layout, prof: "ProfileConfig") -> None:
    """Met à jour les libellés de la légende du layout avec les legend_label du profil."""
    legend_labels_map = {lc.layer_name: (lc.legend_label or lc.layer_name) for lc in prof.layers.values()}
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
LOGO_OFB_BAS_DROITE_ID = "logo_ofb_bas_droite"
# Taille affichée du logo (x2 par rapport à la référence)
LOGO_OFB_BAS_DROITE_HAUTEUR_MM = 24.0
LOGO_OFB_BAS_DROITE_LARGEUR_FRACTION = 0.36
# Position d'ancrage du coin supérieur gauche (référence : logo à 18 % × 12 mm)
LOGO_OFB_ANCRAGE_LARGEUR_FRACTION = 0.18
LOGO_OFB_ANCRAGE_HAUTEUR_MM = 12.0
LOGO_OFB_MARGE_DROITE_MM = 5.0
LOGO_OFB_MARGE_BAS_MM = 16.0
# Décalage du point d'ancrage vers la gauche (en mm) ; réduire pour décaler à droite
LOGO_OFB_DECALAGE_ANCRAGE_GAUCHE_MM = 4.0


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
    """Place le logo RF-OFB horizontal dans le coin inférieur droit de la carte (taille adaptée)."""
    logo_path = _get_logo_ofb_horizontal_path()
    if not logo_path:
        logger.warning(
            "Logo OFB horizontal introuvable (ref/programme/modele_ofb/%s). "
            "Placez le fichier pour l'afficher en bas à droite des cartes.",
            LOGO_OFB_HORIZONTAL_FILENAME,
        )
        return

    picture_item = None
    for item in layout.items():
        if isinstance(item, QgsLayoutItemPicture):
            try:
                if item.id() == LOGO_OFB_BAS_DROITE_ID:
                    picture_item = item
                    break
            except Exception as exc:
                logger.debug("Recherche logo bas droite (id layout): %s", exc)

    if picture_item is None:
        picture_item = QgsLayoutItemPicture(layout)
        picture_item.setId(LOGO_OFB_BAS_DROITE_ID)
        layout.addLayoutItem(picture_item)

    if hasattr(picture_item, "setPicturePath"):
        picture_item.setPicturePath(str(logo_path))
    else:
        picture_item.setPath(str(logo_path))
    picture_item.setResizeMode(QgsLayoutItemPicture.Zoom)

    layout_size = layout.pageCollection().page(0).pageSize()
    w_mm = layout_size.width()
    h_mm = layout_size.height()

    logo_w = w_mm * LOGO_OFB_BAS_DROITE_LARGEUR_FRACTION
    logo_h = LOGO_OFB_BAS_DROITE_HAUTEUR_MM
    try:
        size_mm = QgsLayoutSize(logo_w, logo_h)
        if hasattr(picture_item, "attemptResize"):
            picture_item.attemptResize(size_mm)
    except Exception as e:
        logger.debug("Dimensionnement logo bas droite: %s", e)

    # Ancrage au coin supérieur gauche : position fixe (celle du logo de référence), légèrement décalée vers la gauche
    x_pos = w_mm - (w_mm * LOGO_OFB_ANCRAGE_LARGEUR_FRACTION) - LOGO_OFB_MARGE_DROITE_MM - LOGO_OFB_DECALAGE_ANCRAGE_GAUCHE_MM
    y_pos = h_mm - LOGO_OFB_ANCRAGE_HAUTEUR_MM - LOGO_OFB_MARGE_BAS_MM
    try:
        if hasattr(picture_item, "attemptMove"):
            picture_item.attemptMove(QgsLayoutPoint(x_pos, y_pos))
        elif hasattr(picture_item, "setPosition"):
            picture_item.setPosition(QgsLayoutPoint(x_pos, y_pos))
    except Exception as e:
        logger.debug("Positionnement logo bas droite: %s", e)


def _ensure_logo_bandeau(layout, prof: "ProfileConfig") -> None:
    """Ajoute ou met à jour le bandeau logos (République française + OFB) en haut du layout."""
    logo_path = _get_logo_bandeau_path()
    if not logo_path:
        logger.warning(
            "Bandeau logos OFB introuvable (ref/programme/modele_ofb/word/media/image5.jpg ou .png). "
            "Placez le fichier pour l'afficher sur les cartes."
        )
        return

    # Chercher un élément picture existant avec l'id dédié
    bandeau_id = "bandeau_logos_ofb"
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
    # Positionner en haut au centre, hauteur ~15 % de la page
    layout_size = layout.pageCollection().page(0).pageSize()
    w_mm = layout_size.width()
    h_mm = layout_size.height()
    bandeau_h = min(25.0, h_mm * 0.15)
    # Taille : attemptResize(QgsLayoutSize) selon l'API QgsLayoutItem (unité mm par défaut)
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
    # Position
    try:
        if hasattr(picture_item, "attemptMove"):
            picture_item.attemptMove(QgsLayoutPoint(0, 0))
        elif hasattr(picture_item, "setPosition"):
            picture_item.setPosition(QgsLayoutPoint(0, 0))
    except Exception as e:
        logger.exception("Erreur lors du positionnement du bandeau logo: %s", e)


def export_layout(prof: "ProfileConfig", output_path: Path, dpi: int = 300, fmt: str = "png") -> bool:
    """Exporte le layout du profil vers un fichier image."""
    from config_cartes import ProfileConfig, CONFIG

    proj = QgsProject.instance()
    manager = proj.layoutManager()
    layout = manager.layoutByName(prof.layout_name)

    if not layout:
        logger.error("Layout '%s' introuvable dans le projet.", prof.layout_name)
        return False

    # Mettre à jour les textes (titre / sous-titre) du layout à partir de la configuration du profil.
    # On recherche des éléments de type QgsLayoutItemLabel dont l'identifiant correspond
    # aux champs layout_title_item_id et layout_subtitle_item_id de ProfileConfig.
    title_text = getattr(prof, "title_main", "") or prof.title
    subtitle_text = getattr(prof, "subtitle", "") or f"Période du {prof.date_deb} au {prof.date_fin}"
    title_id = getattr(prof, "layout_title_item_id", "titre_principal")
    subtitle_id = getattr(prof, "layout_subtitle_item_id", "sous_titre")

    for item in layout.items():
        if isinstance(item, QgsLayoutItemLabel):
            try:
                item_id = item.id()
            except AttributeError:
                item_id = ""
            if item_id == title_id:
                item.setText(title_text)
            elif item_id == subtitle_id:
                item.setText(subtitle_text)

    # Légende : appliquer les libellés définis dans la config (legend_label)
    _apply_legend_labels(layout, prof)
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

    settings = QgsLayoutExporter.ImageExportSettings()
    settings.dpi = dpi

    ext = fmt.lower()
    if ext in ("jpg", "jpeg"):
        path_str = str(output_path.with_suffix(".jpg"))
        settings.imageFormat = "jpg"
    else:
        path_str = str(output_path.with_suffix(".png"))

    # Supprimer le fichier existant (le pilote PNG ne permet pas l'accès en écriture sur fichier existant)
    if Path(path_str).exists():
        try:
            Path(path_str).unlink()
        except OSError:
            pass

    exporter = QgsLayoutExporter(layout)
    res = exporter.exportToImage(path_str, settings)

    if res == QgsLayoutExporter.Success:
        logger.info("Carte exportée pour le profil '%s' → %s", prof.id, path_str)
        return True
    else:
        logger.error("Échec de l'export du layout '%s' vers %s", prof.layout_name, path_str)
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
                layout_name="Bilan 2025 / 2026 - Agrainage illicite - Côte d'Or",
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
        "Configuration enregistrée dans src/bilans/cartographie/config_cartes.py "
        "(profils: %s)",
        ", ".join(profile_ids),
    )


def _save_config_to_file(cfg: "GlobalConfig") -> None:
    """Écrit la configuration dans config_cartes.py (via le writer partagé)."""
    from config_cartes_writer import write_config_file

    cfg_path = SCRIPT_DIR / "config_cartes.py"
    write_config_file(cfg, cfg_path)


def run_export(
    profile_ids: List[str],
    date_deb: Optional[str] = None,
    date_fin: Optional[str] = None,
    dept_code: Optional[str] = None,
) -> None:
    """Génère les cartes en mode non interactif à partir de la config."""
    CONFIG = get_effective_config()

    project_path = _resolve_qgis_project_path(CONFIG.project_qgis_path)
    if not load_project(project_path):
        return

    set_basemap_visibility(CONFIG.basemap.enabled)

    env_out_dir = os.getenv("CARTO_OUTPUT_DIR")
    if env_out_dir:
        out_dir = Path(env_out_dir)
    else:
        out_dir = Path(CONFIG.output_dir) if CONFIG.output_dir else OUT_DIR_CARTES
    out_dir.mkdir(parents=True, exist_ok=True)
    dpi = CONFIG.output.dpi
    fmt = CONFIG.output.format

    carto_config = _ConfigDeptOverride(CONFIG, dept_code) if dept_code else CONFIG

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
        if not prof:
            logger.warning("Profil '%s' inconnu. Ignoré.", pid)
            continue

        # Surcharge éventuelle des dates de période par la ligne de commande
        if date_deb:
            prof.date_deb = date_deb
        if date_fin:
            prof.date_fin = date_fin

        logger.info("Profil: %s (période %s → %s)", pid, prof.date_deb, prof.date_fin)

        proj = QgsProject.instance()
        for lname, lcfg in prof.layers.items():
            layer = get_layer_by_name(lcfg.layer_name)
            if not layer:
                all_names = [lyr.name() for lyr in proj.mapLayers().values()]
                logger.warning(
                    "Couche '%s' introuvable pour le profil '%s' (ignorée). Couches du projet: %s",
                    lcfg.layer_name,
                    pid,
                    all_names,
                )
                continue
            logger.info("  → Couche: %s (config: %s)", lname, lcfg.layer_name)
            apply_layer_symbology(layer, lcfg)
            apply_date_filter(layer, lcfg, prof.date_deb, prof.date_fin, config=carto_config, profile=prof)

        out_path = out_dir / prof.output_filename
        export_layout(prof, out_path, dpi=dpi, fmt=fmt)


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
            from common.loaders import load_ref_themes_ctrl
            themes = load_ref_themes_ctrl(Path(PROJECT_ROOT))
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
            )
    except Exception as e:
        logger.exception("Erreur lors de la génération des cartes: %s", e)
        raise
    finally:
        app.exitQgis()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Erreur fatale: %s", e)
        sys.exit(1)
