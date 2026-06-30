"""
Couches découvertes depuis un layout QGIS (mode layout-driven).

Le projet bilans_carte.qgz peut avoir un LayerSet vide sur les cartes : dans ce cas
on complète via la légende du layout, un groupe d'arborescence (`layout_layer_group`)
ou les couches métier visibles du projet.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Sequence

from core.cartographie.layer_resolver import infer_layer_role

if TYPE_CHECKING:
    from core.cartographie.config_cartes_model import LayerSymbologyConfig, ProfileConfig

# Fonds cartographiques / tuiles — exclus du traitement métier
BASEMAP_KEYWORDS = (
    "esri",
    "osm",
    "openstreetmap",
    "versatiles",
    "wms",
    "wmts",
    "xyz",
    "cartes ign",
    "plan ign",
    "scan 25",
    "national geographic",
    "community map",
)

# Tables sans géométrie — pas de filtre attributaire utile
NON_VECTOR_HINTS = ("stats_pve",)


def is_basemap_layer(name: str) -> bool:
    lowered = name.lower()
    return any(k in lowered for k in BASEMAP_KEYWORDS)


def is_operational_layer(name: str) -> bool:
    """Couche vectorielle métier (hors fonds et tables non géo)."""
    if not name or is_basemap_layer(name):
        return False
    lowered = name.lower()
    if " copie" in lowered:
        return False
    if any(k in lowered for k in NON_VECTOR_HINTS):
        return False
    return True


def filter_operational_layer_names(names: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        n = (name or "").strip()
        if not n or n in seen:
            continue
        if not is_operational_layer(n):
            continue
        seen.add(n)
        out.append(n)
    return out


def infer_filter_type_for_layer(
    layer_name: str,
    profile_id: str,
    profile: Optional["ProfileConfig"] = None,
) -> str:
    """Infère le filtre CLI à appliquer selon le type de couche et le profil bilan."""
    role = infer_layer_role(layer_name, layer_name) or ""
    pid = (profile_id or "").lower()

    if role == "point_controles":
        if profile and getattr(profile, "theme_id", None):
            return "point_ctrl_theme"
        if profile and getattr(profile, "keywords", None):
            return "point_ctrl_keywords"
        if pid in ("agrainage",):
            return "point_ctrl_agrainage"
        if pid in ("chasse", "chasse_agrainage"):
            return "point_ctrl_chasse"
        if pid in ("piegeage",):
            return "point_ctrl_piegeage"
        return "point_ctrl_global"

    if role == "pej":
        if pid in ("procedures_pve", "global", "piegeage") or "synthese_activite_pa_pj" in pid:
            return "pj"
        return ""

    if role == "communes_pve":
        return "pve"

    return ""


def _match_yaml_override(
    layer_name: str,
    yaml_overrides: Dict[str, "LayerSymbologyConfig"],
) -> Optional["LayerSymbologyConfig"]:
    if layer_name in yaml_overrides:
        return yaml_overrides[layer_name]
    role = infer_layer_role(layer_name, layer_name)
    if role:
        for key, cfg in yaml_overrides.items():
            cfg_role = getattr(cfg, "layer_role", None) or infer_layer_role(key, cfg.layer_name)
            if cfg_role == role:
                return cfg
    for key, cfg in yaml_overrides.items():
        hint = cfg.layer_name or key
        if hint.lower() in layer_name.lower() or layer_name.lower() in hint.lower():
            return cfg
    return None


def build_layer_configs_from_names(
    discovered_names: Sequence[str],
    profile: "ProfileConfig",
    yaml_overrides: Optional[Dict[str, "LayerSymbologyConfig"]] = None,
) -> Dict[str, "LayerSymbologyConfig"]:
    """Construit la config de traitement à partir des noms découverts dans le layout."""
    from core.cartographie.config_cartes_model import LayerSymbologyConfig

    overrides = yaml_overrides or {}
    result: Dict[str, LayerSymbologyConfig] = {}
    operational = filter_operational_layer_names(discovered_names)

    for name in operational:
        override = _match_yaml_override(name, overrides)
        role = infer_layer_role(name, name)
        filter_type = infer_filter_type_for_layer(name, profile.id, profile)
        if override and override.filter_type:
            filter_type = override.filter_type

        legend = override.legend_label if override and override.legend_label else ""
        result[name] = LayerSymbologyConfig(
            layer_name=name,
            layer_role=role,
            symbology_source=override.symbology_source if override else None,
            legend_label=legend,
            filter_type=filter_type,
        )
    return result


def parse_qgs_maplayer_id_to_name(qgs_text: str) -> dict[str, str]:
    """Index id QGIS → nom de couche depuis le XML projet."""
    root = ET.fromstring(qgs_text.encode("utf-8") if isinstance(qgs_text, str) else qgs_text)
    mapping: dict[str, str] = {}
    for ml in root.iter("maplayer"):
        ln = ml.find("layername")
        if ln is None or not ln.text:
            continue
        id_el = ml.find("id")
        lid = id_el.text.strip() if id_el is not None and id_el.text else ml.get("id")
        if lid:
            mapping[lid] = ln.text.strip()
    return mapping


def parse_qgs_layout_layerset(qgs_text: str, layout_name: str) -> list[str]:
    """
    Extrait les couches d'un LayerSet explicite sur la carte du layout (si configuré dans QGIS).
    Retourne [] si LayerSet vide ou layout introuvable.
    """
    text = qgs_text.decode("utf-8") if isinstance(qgs_text, bytes) else qgs_text
    marker = f'name="{layout_name}"'
    idx = text.find(marker)
    if idx < 0:
        return []

    chunk = text[idx : idx + 120_000]
    id_map = parse_qgs_maplayer_id_to_name(text)

    layer_ids: list[str] = []
    layerset_match = re.search(r"<LayerSet>(.*?)</LayerSet>", chunk, re.DOTALL)
    if not layerset_match:
        return []
    body = layerset_match.group(1)
    if not body.strip():
        return []

    for m in re.finditer(r'id="([^"]+)"', body):
        lid = m.group(1)
        if lid in id_map:
            layer_ids.append(lid)

    return [id_map[lid] for lid in layer_ids if lid in id_map]


def parse_qgs_layer_tree_group(qgs_text: str, group_name: str) -> list[str]:
    """Couches déclarées sous un groupe d'arborescence QGIS (correspondance exacte insensible à la casse)."""
    text = qgs_text.decode("utf-8") if isinstance(qgs_text, bytes) else qgs_text
    target = group_name.lower()
    names: list[str] = []

    for m in re.finditer(r'layer-tree-group[^>]*name="([^"]+)"', text):
        if m.group(1).lower() != target:
            continue
        seg = text[m.end() : m.end() + 8000]
        depth = 1
        end = 0
        for i, ch in enumerate(seg):
            if seg.startswith("layer-tree-group", i):
                depth += 1
            elif seg.startswith("/layer-tree-group", i):
                depth -= 1
                if depth == 0:
                    end = i
                    break
        body = seg[:end] if end else seg
        names.extend(re.findall(r'layer-tree-layer[^>]*name="([^"]+)"', body))

    return filter_operational_layer_names(names)


def discover_layers_from_qgs_file(
    qgs_path_or_bytes,
    layout_name: str,
    layout_layer_group: Optional[str] = None,
) -> list[str]:
    """
    Découverte hors PyQGIS (tests / diagnostic) depuis le .qgs extrait du .qgz.
    Ordre : LayerSet layout → groupe arborescence → couches métier visibles (checked).
    """
    if isinstance(qgs_path_or_bytes, (bytes, str)) and isinstance(qgs_path_or_bytes, str):
        if len(qgs_path_or_bytes) < 500 and "\n" not in qgs_path_or_bytes[:200]:
            text = open(qgs_path_or_bytes, encoding="utf-8").read()
        else:
            text = qgs_path_or_bytes
    else:
        import zipfile
        from pathlib import Path

        path = Path(qgs_path_or_bytes)
        with zipfile.ZipFile(path) as zf:
            text = zf.read("bilans_carte.qgs").decode("utf-8", "replace")

    from_layerset = parse_qgs_layout_layerset(text, layout_name)
    if from_layerset:
        return filter_operational_layer_names(from_layerset)

    if layout_layer_group:
        from_group = parse_qgs_layer_tree_group(text, layout_layer_group)
        if from_group:
            return from_group

    # Fallback : couches cochées visibles dans l'arborescence
    checked = re.findall(
        r'layer-tree-layer[^>]*checked="Qt::Checked"[^>]*name="([^"]+)"',
        text,
    )
    return filter_operational_layer_names(checked)
