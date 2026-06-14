"""
Chargement et application des gabarits de mise en page (layout_defaults.yaml).

L'application PyQGIS est optionnelle : les fonctions de parsing sont testables sans QGIS.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

try:
    from config_cartes_model import (
        LayoutBandeauDefaultsConfig,
        LayoutDefaultsRootConfig,
        LayoutItemRectConfig,
        LayoutLegendDefaultsConfig,
        LayoutLogoDefaultsConfig,
        LayoutTemplateConfig,
        LayoutTitleIdsConfig,
        ProfileConfig,
        OutputConfig,
    )
except ImportError:
    from bilans.cartographie.config_cartes_model import (
        LayoutBandeauDefaultsConfig,
        LayoutDefaultsRootConfig,
        LayoutItemRectConfig,
        LayoutLegendDefaultsConfig,
        LayoutLogoDefaultsConfig,
        LayoutTemplateConfig,
        LayoutTitleIdsConfig,
        ProfileConfig,
        OutputConfig,
    )

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

PARAM_DIR = Path(__file__).resolve().parent / "param"
LAYOUT_DEFAULTS_YAML = PARAM_DIR / "layout_defaults.yaml"

_CARRE_210 = (210.0, 210.0)
_A4_PAYSAGE = (297.0, 210.0)
_PAGE_TOLERANCE_MM = 2.0


def _rect_from_dict(d: Optional[Dict[str, Any]]) -> LayoutItemRectConfig:
    if not isinstance(d, dict):
        return LayoutItemRectConfig()
    return LayoutItemRectConfig(
        x_mm=float(d.get("x_mm", 0)),
        y_mm=float(d.get("y_mm", 0)),
        width_mm=float(d.get("width_mm", 0)),
        height_mm=float(d.get("height_mm", 0)),
    )


def _legend_from_dict(d: Optional[Dict[str, Any]]) -> LayoutLegendDefaultsConfig:
    if not isinstance(d, dict):
        return LayoutLegendDefaultsConfig()
    return LayoutLegendDefaultsConfig(
        single=bool(d.get("single", True)),
        hide_extra=bool(d.get("hide_extra", True)),
        x_mm=float(d.get("x_mm", 0)),
        y_mm=float(d.get("y_mm", 0)),
        width_mm=float(d.get("width_mm", 0)),
        height_mm=float(d.get("height_mm", 0)),
    )


def _logo_from_dict(d: Optional[Dict[str, Any]]) -> LayoutLogoDefaultsConfig:
    if not isinstance(d, dict):
        return LayoutLogoDefaultsConfig()
    return LayoutLogoDefaultsConfig(
        x_mm=float(d.get("x_mm", 0)),
        y_mm=float(d.get("y_mm", 0)),
        width_mm=float(d.get("width_mm", 0)),
        height_mm=float(d.get("height_mm", 0)),
        picture_id=str(d.get("picture_id", "logo_ofb_bas_droite")),
        skip_if_qgis_picture=bool(d.get("skip_if_qgis_picture", True)),
    )


def _bandeau_from_dict(d: Optional[Dict[str, Any]]) -> LayoutBandeauDefaultsConfig:
    if not isinstance(d, dict):
        return LayoutBandeauDefaultsConfig()
    return LayoutBandeauDefaultsConfig(
        y_mm=float(d.get("y_mm", 0)),
        height_mm=float(d.get("height_mm", 25)),
        height_max_fraction=float(d.get("height_max_fraction", 0.15)),
        picture_id=str(d.get("picture_id", "bandeau_logos_ofb")),
    )


def _template_from_dict(d: Dict[str, Any]) -> LayoutTemplateConfig:
    page_d = d.get("page") if isinstance(d.get("page"), dict) else {}
    return LayoutTemplateConfig(
        page=LayoutItemRectConfig(
            width_mm=float(page_d.get("width_mm", 0)),
            height_mm=float(page_d.get("height_mm", 0)),
        ),
        map=_rect_from_dict(d.get("map")),
        legend=_legend_from_dict(d.get("legend")),
        scalebar=_rect_from_dict(d.get("scalebar")),
        logo_bas_droite=_logo_from_dict(d.get("logo_bas_droite")),
        bandeau_haut=_bandeau_from_dict(d.get("bandeau_haut")),
    )


def parse_layout_defaults_dict(data: Optional[Dict[str, Any]]) -> LayoutDefaultsRootConfig:
    """Construit LayoutDefaultsRootConfig depuis un dict YAML déjà chargé."""
    if not isinstance(data, dict):
        return LayoutDefaultsRootConfig()

    title_ids: Dict[str, LayoutTitleIdsConfig] = {}
    raw_titles = data.get("layout_title_ids")
    if isinstance(raw_titles, dict):
        for layout_name, spec in raw_titles.items():
            if not isinstance(spec, dict):
                continue
            title_ids[str(layout_name)] = LayoutTitleIdsConfig(
                title_item_id=str(spec.get("title_item_id", "titre_principal")),
                subtitle_item_id=spec.get("subtitle_item_id"),
            )

    templates: Dict[str, LayoutTemplateConfig] = {}
    raw_templates = data.get("templates")
    if isinstance(raw_templates, dict):
        for key, tpl in raw_templates.items():
            if isinstance(tpl, dict):
                templates[str(key)] = _template_from_dict(tpl)

    export_cfg = OutputConfig()
    raw_export = data.get("export")
    if isinstance(raw_export, dict):
        export_cfg = OutputConfig(
            format=str(raw_export.get("format", "png")),
            dpi=int(raw_export.get("dpi", 300)),
            page_size=str(raw_export.get("page_size", "A4")),
            orientation=str(raw_export.get("orientation", "landscape")),
        )

    return LayoutDefaultsRootConfig(
        enabled=bool(data.get("enabled", True)),
        default_template=str(data.get("default_template", "carre_210")),
        auto_template_from_page=bool(data.get("auto_template_from_page", True)),
        layout_title_ids=title_ids,
        templates=templates,
        export=export_cfg,
    )


def load_layout_defaults(path: Optional[Path] = None) -> LayoutDefaultsRootConfig:
    """Charge layout_defaults.yaml ; retourne une config vide si fichier absent."""
    yaml_path = path or LAYOUT_DEFAULTS_YAML
    if not yaml_path.exists():
        return LayoutDefaultsRootConfig()
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML absent : layout_defaults.yaml ignoré.")
        return LayoutDefaultsRootConfig()
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        logger.warning("Erreur lecture %s : %s", yaml_path, exc)
        return LayoutDefaultsRootConfig()
    return parse_layout_defaults_dict(data)


def _page_size_mm(layout: Any) -> tuple[float, float]:
    try:
        page = layout.pageCollection().page(0)
        size = page.pageSize()
        return float(size.width()), float(size.height())
    except Exception:
        return 0.0, 0.0


def _match_page_template(w_mm: float, h_mm: float) -> Optional[str]:
    if abs(w_mm - _CARRE_210[0]) <= _PAGE_TOLERANCE_MM and abs(h_mm - _CARRE_210[1]) <= _PAGE_TOLERANCE_MM:
        return "carre_210"
    if abs(w_mm - _A4_PAYSAGE[0]) <= _PAGE_TOLERANCE_MM and abs(h_mm - _A4_PAYSAGE[1]) <= _PAGE_TOLERANCE_MM:
        return "a4_paysage"
    return None


def resolve_template_name(
    prof: "ProfileConfig",
    root: LayoutDefaultsRootConfig,
    layout: Any = None,
) -> Optional[str]:
    """Résout le nom de template pour un profil (ref explicite, auto page, défaut global)."""
    if not root.enabled:
        return None
    ref = getattr(prof, "layout_defaults_ref", None)
    if ref and ref in root.templates:
        return ref
    if layout is not None and root.auto_template_from_page:
        w_mm, h_mm = _page_size_mm(layout)
        matched = _match_page_template(w_mm, h_mm)
        if matched and matched in root.templates:
            return matched
    default = root.default_template
    if default in root.templates:
        return default
    return None


def resolve_title_ids(
    prof: "ProfileConfig",
    root: LayoutDefaultsRootConfig,
) -> tuple[str, Optional[str]]:
    """Ids titre/sous-titre : mapping layout_name puis champs profil."""
    layout_name = getattr(prof, "layout_name", "") or ""
    mapped = root.layout_title_ids.get(layout_name)
    if mapped is not None:
        sub = mapped.subtitle_item_id
        return mapped.title_item_id, sub
    return (
        getattr(prof, "layout_title_item_id", "titre_principal"),
        getattr(prof, "layout_subtitle_item_id", "sous_titre"),
    )


def get_template_for_profile(
    prof: "ProfileConfig",
    root: Optional[LayoutDefaultsRootConfig] = None,
    layout: Any = None,
) -> Optional[LayoutTemplateConfig]:
    cfg = root if root is not None else load_layout_defaults()
    name = resolve_template_name(prof, cfg, layout=layout)
    if not name:
        return None
    return cfg.templates.get(name)


def _layout_item_set_rect(item: Any, rect: LayoutItemRectConfig) -> None:
    if rect.width_mm <= 0 or rect.height_mm <= 0:
        return
    try:
        from qgis.core import QgsLayoutPoint, QgsLayoutSize, QgsLayoutItemScaleBar
    except ImportError:
        return
    try:
        size_mm = QgsLayoutSize(rect.width_mm, rect.height_mm)
        if hasattr(item, "attemptResize"):
            item.attemptResize(size_mm)
                
        if hasattr(item, "attemptMove"):
            item.attemptMove(QgsLayoutPoint(rect.x_mm, rect.y_mm))
        elif hasattr(item, "setPosition"):
            item.setPosition(QgsLayoutPoint(rect.x_mm, rect.y_mm))
    except Exception as exc:
        logger.debug("Positionnement item layout ignoré : %s", exc)


def _legend_items(layout: Any) -> List[Any]:
    try:
        from qgis.core import QgsLayoutItemLegend
    except ImportError:
        return []
    return [it for it in layout.items() if isinstance(it, QgsLayoutItemLegend)]


def _pick_primary_legend(legends: List[Any]) -> Any:
    """Conserve la légende la plus à droite (colonne droite de la page)."""
    if not legends:
        return None
    if len(legends) == 1:
        return legends[0]

    def _x_pos(leg: Any) -> float:
        try:
            pos = leg.positionWithUnits()
            return float(pos.x())
        except Exception:
            try:
                return float(leg.x())
            except Exception:
                return 0.0

    return max(legends, key=_x_pos)


def _apply_single_legend(layout: Any, legend_cfg: LayoutLegendDefaultsConfig) -> None:
    legends = _legend_items(layout)
    if not legends:
        logger.debug("Aucune légende dans le layout.")
        return
    primary = _pick_primary_legend(legends)
    if primary is None:
        return
    _layout_item_set_rect(
        primary,
        LayoutItemRectConfig(
            x_mm=legend_cfg.x_mm,
            y_mm=legend_cfg.y_mm,
            width_mm=legend_cfg.width_mm,
            height_mm=legend_cfg.height_mm,
        ),
    )
    if legend_cfg.hide_extra:
        for leg in legends:
            if leg is primary:
                try:
                    leg.setVisibility(True)
                except Exception:
                    pass
            else:
                try:
                    leg.setVisibility(False)
                except Exception as exc:
                    logger.debug("Masquage légende secondaire : %s", exc)


def _find_layout_map(layout: Any) -> Any:
    try:
        from qgis.core import QgsLayoutItemMap
    except ImportError:
        return None
    maps = [it for it in layout.items() if isinstance(it, QgsLayoutItemMap)]
    if not maps:
        return None
    return max(maps, key=lambda m: float(m.rect().width()) * float(m.rect().height()))


def _find_scalebar(layout: Any, map_item: Any) -> Any:
    try:
        from qgis.core import QgsLayoutItemScaleBar
    except ImportError:
        return None
    map_uuid = ""
    try:
        map_uuid = map_item.uuid() if map_item else ""
    except Exception:
        pass
    bars = [it for it in layout.items() if isinstance(it, QgsLayoutItemScaleBar)]
    if not bars:
        return None
    if map_uuid:
        for bar in bars:
            try:
                if getattr(bar, "linkedMap", None) and bar.linkedMap() and bar.linkedMap().uuid() == map_uuid:
                    return bar
            except Exception:
                continue
    return bars[0]


def _existing_ofb_horizontal_picture(layout: Any) -> Any:
    """Picture déjà présente dans le .qgz (bloc-marque horizontal), sans id Python."""
    try:
        from qgis.core import QgsLayoutItemPicture
    except ImportError:
        return None
    for item in layout.items():
        if not isinstance(item, QgsLayoutItemPicture):
            continue
        try:
            iid = item.id() or ""
        except Exception:
            iid = ""
        if iid in ("logo_ofb_bas_droite", "bandeau_logos_ofb"):
            continue
        path = ""
        if hasattr(item, "picturePath"):
            path = str(item.picturePath() or "")
        elif hasattr(item, "path"):
            path = str(item.path() or "")
        if "bloc-marque-RF-OFB_horizontal" in path or "OFB_horizontal" in path:
            return item
    return None


def apply_layout_defaults(
    layout: Any,
    prof: "ProfileConfig",
    root: Optional[LayoutDefaultsRootConfig] = None,
) -> Optional[LayoutTemplateConfig]:
    """
    Applique le gabarit (carte, légende unique à droite, échelle).
    Retourne le template appliqué ou None si désactivé / introuvable.
    """
    cfg = root if root is not None else load_layout_defaults()
    if not cfg.enabled:
        return None
    template = get_template_for_profile(prof, cfg, layout=layout)
    if template is None:
        logger.debug("Aucun template layout pour le profil '%s'.", getattr(prof, "id", "?"))
        return None

    if layout is not None and template.page.width_mm > 0 and template.page.height_mm > 0:
        try:
            from qgis.core import QgsLayoutSize, QgsUnitTypes, QgsLayoutPoint
            page = layout.pageCollection().page(0)
            if page:
                original_height = page.pageSize().height()
                new_height = template.page.height_mm
                delta_y = new_height - original_height
                
                # Si on réduit la hauteur de la page (ex: 210 -> 149), 
                # on remonte les éléments ancrés en bas (flèche du nord, bandeau)
                if abs(delta_y) > 0.1:
                    for item in layout.items():
                        if item == page:
                            continue
                        if not hasattr(item, 'positionWithUnits'):
                            continue
                        try:
                            # Ignorer les objets explicitement gérés par extra_items
                            item_id = item.id() if hasattr(item, "id") else ""
                            if item_id and item_id in template.extra_items:
                                continue
                                
                            pos = item.positionWithUnits()
                            if pos.y() > original_height - 70:
                                item.attemptMove(QgsLayoutPoint(pos.x(), pos.y() + delta_y, pos.units()))
                        except Exception:
                            pass

                page.setPageSize(QgsLayoutSize(template.page.width_mm, template.page.height_mm, QgsUnitTypes.LayoutMillimeters))
        except Exception as exc:
            import traceback
            with open("C:/Users/aguirre.maurin/Documents/GitHub/Bilans_production/scratch/qgis_resize_error.txt", "w") as f:
                f.write(traceback.format_exc())
            logger.debug("Redimensionnement page ignoré : %s", exc)

    map_item = _find_layout_map(layout)
    if map_item is not None and template.map.width_mm > 0:
        _layout_item_set_rect(map_item, template.map)
    else:
        logger.warning("Item carte introuvable dans le layout '%s'.", getattr(prof, "layout_name", ""))

    if template.legend.single:
        _apply_single_legend(layout, template.legend)

    scale_item = _find_scalebar(layout, map_item)
    if scale_item is not None and template.scalebar.width_mm > 0:
        _layout_item_set_rect(scale_item, template.scalebar)

    if template.logo_bas_droite.skip_if_qgis_picture:
        logo_item = layout.itemById(template.logo_bas_droite.picture_id)
        if logo_item is not None:
            _layout_item_set_rect(logo_item, template.logo_bas_droite)
            
    # Application des extra_items explicites (Hybride Avancé)
    for item_id, rect_cfg in template.extra_items.items():
        extra_item = layout.itemById(item_id)
        if extra_item is not None:
            _layout_item_set_rect(extra_item, rect_cfg)

    return template


def get_logo_bas_droite_rect(
    prof: "ProfileConfig",
    layout: Any,
    root: Optional[LayoutDefaultsRootConfig] = None,
) -> Optional[LayoutLogoDefaultsConfig]:
    """Rect logo bas droite depuis le template résolu."""
    template = get_template_for_profile(prof, root or load_layout_defaults(), layout=layout)
    if template is None:
        return None
    return template.logo_bas_droite


def get_bandeau_config(
    prof: "ProfileConfig",
    layout: Any,
    root: Optional[LayoutDefaultsRootConfig] = None,
) -> Optional[LayoutBandeauDefaultsConfig]:
    template = get_template_for_profile(prof, root or load_layout_defaults(), layout=layout)
    if template is None:
        return None
    return template.bandeau_haut


def should_skip_python_logo_bas_droite(layout: Any, logo_cfg: LayoutLogoDefaultsConfig) -> bool:
    if not logo_cfg.skip_if_qgis_picture:
        return False
    return _existing_ofb_horizontal_picture(layout) is not None


def apply_existing_qgis_logo_position(layout: Any, logo_cfg: LayoutLogoDefaultsConfig) -> bool:
    """Repositionne le logo horizontal déjà dans le .qgz (évite doublon)."""
    item = _existing_ofb_horizontal_picture(layout)
    if item is None or logo_cfg.width_mm <= 0:
        return False
    _layout_item_set_rect(
        item,
        LayoutItemRectConfig(
            x_mm=logo_cfg.x_mm,
            y_mm=logo_cfg.y_mm,
            width_mm=logo_cfg.width_mm,
            height_mm=logo_cfg.height_mm,
        ),
    )
    return True
