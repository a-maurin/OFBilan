"""
Pochoir cartographique : géométrie départementale depuis limites_admin_dep uniquement.

Source obligatoire :
  ref/programme/sig/limites_admin_dep/DEPARTEMENT_ADMIN_Express_200207.shp
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd

from core.chemins_projet import PROJECT_ROOT, get_sig_dir

logger = logging.getLogger(__name__)

DEPARTEMENTS_ADMIN_SHP = (
    get_sig_dir() / "limites_admin_dep" / "DEPARTEMENT_ADMIN_Express_200207.shp"
)

from core.common.chargeurs_donnees import load_pnf_aoa_gdf, load_zone_tub_gdf

_INSEE_DEP_COL = "INSEE_DEP"


def normalize_dept_code(code: str) -> str:
    """Normalise un code département INSEE (ex. '21', '2A', '971')."""
    return str(code or "").strip().upper()


def pochoir_layer_name(dept_code: str) -> str:
    """Nom de couche QGIS attendu pour le pochoir d'un département."""
    return f"pochoir_sd{normalize_dept_code(dept_code)}"


def get_departements_admin_shp(project_root: Optional[Path] = None) -> Path:
    """Chemin vers le shapefile admin express (seule source pochoir)."""
    if project_root is None:
        return DEPARTEMENTS_ADMIN_SHP
    return project_root / "ref" / "programme" / "sig" / "limites_admin_dep" / "DEPARTEMENT_ADMIN_Express_200207.shp"


def _match_insee_dep(series: pd.Series, dept_code: str) -> pd.Series:
    target = normalize_dept_code(dept_code)
    normalized = series.astype(str).str.strip().str.upper()
    return normalized == target


@lru_cache(maxsize=32)
def _load_all_departements(shp_path: str) -> gpd.GeoDataFrame:
    path = Path(shp_path)
    if not path.exists():
        raise FileNotFoundError(f"Shapefile départements introuvable : {path}")
    gdf = gpd.read_file(path)
    if gdf.empty:
        raise ValueError(f"Aucune entité dans {path}")
    if _INSEE_DEP_COL not in gdf.columns:
        raise KeyError(
            f"Colonne {_INSEE_DEP_COL} absente dans {path.name} (colonnes : {list(gdf.columns)})"
        )
    return gdf


def load_department_gdf(
    dept_code: str,
    *,
    project_root: Optional[Path] = None,
    dissolve: bool = True,
) -> gpd.GeoDataFrame:
    """
    Extrait le polygone du département cible depuis DEPARTEMENT_ADMIN_Express_200207.shp.
    Gère également la fusion des départements si le code correspond à une région (commençant par R) ou une BMI.
    """
    shp = get_departements_admin_shp(project_root)
    gdf = _load_all_departements(str(shp.resolve()))
    
    # Gestion BMI et Régions
    import os
    from core.common.utilitaires_metier import get_departements_pour_perimetre
    
    code_upper = dept_code.upper()
    echelle = os.environ.get("BILANS_CARTO_ECHELLE", "departement").lower()
    
    if code_upper.startswith("R") or echelle == "region":
        # region prefix/detection
        target_depts = get_departements_pour_perimetre("region", dept_code.lower())
    elif code_upper.startswith("BMI-") or echelle == "bmi":
        target_depts = get_departements_pour_perimetre("bmi", dept_code)
    else:
        target_depts = [normalize_dept_code(dept_code)]
    
    mask = gdf[_INSEE_DEP_COL].astype(str).str.strip().str.upper().isin(target_depts)
    subset = gdf.loc[mask].copy()
    if subset.empty:
        raise ValueError(
            f"Département(s) {target_depts} introuvable(s) dans {shp.name}"
        )
    if len(subset) > 1 and dissolve:
        subset = subset.dissolve()
        
    if len(subset) > 1 and not dissolve:
        out = gpd.GeoDataFrame(
            {
                "id": [f"DEPARTEM_{row.get(_INSEE_DEP_COL, '')}" for _, row in subset.iterrows()],
                "nom": [str(row.get("NOM_DEP", "")) for _, row in subset.iterrows()],
                "insee_dep": [str(row.get(_INSEE_DEP_COL, "")) for _, row in subset.iterrows()],
                "insee_reg": [str(row.get("INSEE_REG", "")) for _, row in subset.iterrows()],
            },
            geometry=subset.geometry.values,
            crs=subset.crs,
        )
    else:
        nom = f"Zone {dept_code}" if len(target_depts) > 1 else str(subset.iloc[0].get("NOM_DEP", ""))
        insee = dept_code if len(target_depts) > 1 else normalize_dept_code(dept_code)
        
        out = gpd.GeoDataFrame(
            {
                "id": [f"DEPARTEM_{insee}"],
                "nom": [nom],
                "insee_dep": [insee],
                "insee_reg": [str(subset.iloc[0].get("INSEE_REG", ""))],
            },
            geometry=subset.geometry.values,
            crs=subset.crs,
        )
    return out


def department_bounds(
    dept_code: str,
    *,
    margin_top: float = 0.25,
    margin_bottom: float = 0.10,
    margin_left: float = 0.05,
    margin_right: float = 0.45,
    project_root: Optional[Path] = None,
    **kwargs,
) -> tuple[float, float, float, float]:
    """Emprise (xmin, ymin, xmax, ymax) du département avec marges forcées pour le ratio 1.51187."""
    gdf = load_department_gdf(dept_code, project_root=project_root)
    xmin, ymin, xmax, ymax = gdf.total_bounds
    dx = max(xmax - xmin, 1.0)
    dy = max(ymax - ymin, 1.0)
    
    # La taille de la page QGIS est 210.15 x 139.0 (ratio 1.51187)
    target_ratio = 210.15 / 139.0
    
    # "Safe Zone" : espace visuel garanti sans superposition avec l'interface.
    # Exprimé en fractions de l'emprise totale de la carte (qui commence SOUS le bandeau haut).
    pad_top = 0.04     # La carte commence sous le bandeau, petite marge visuelle de 5.5mm
    pad_bottom = 0.22  # Le bandeau bas empiète sur la carte + 5.5mm de marge visuelle
    pad_left = 0.04    # Marge de 8.5mm à gauche
    pad_right = 0.31   # La légende empiète à droite + marge visuelle
    
    safe_w_frac = 1.0 - pad_left - pad_right
    safe_h_frac = 1.0 - pad_top - pad_bottom
    
    # 2. Calcul du facteur d'agrandissement pour que la carte touche les limites de cette Safe Zone
    W = max(dx / safe_w_frac, (dy / safe_h_frac) * target_ratio)
    H = W / target_ratio
    
    # 3. Positionnement absolu pour centrer le département au milieu de la Safe Zone
    X_min = xmin - W * pad_left - (W * safe_w_frac - dx) / 2.0
    X_max = X_min + W
    
    Y_max = ymax + H * pad_top + (H * safe_h_frac - dy) / 2.0
    Y_min = Y_max - H
        
    return (X_min, Y_min, X_max, Y_max)


def load_pochoir_gdf(
    pochoir_id: str,
    dept_code: str,
    *,
    project_root: Optional[Path] = None,
) -> gpd.GeoDataFrame:
    """
    Charge le GeoDataFrame correspondant au pochoir demandé (departement, zone_a_risque, aoa...).
    Si pochoir_id est 'departement' ou 'aucun', on renvoie le département par défaut.
    """
    if not pochoir_id or pochoir_id in ("departement", "aucun", "pochoir_departement"):
        return load_department_gdf(dept_code, project_root=project_root)
    
    if pochoir_id in ("zone_a_risque", "zone_tub", "pochoir_zone_a_risque"):
        root = project_root or PROJECT_ROOT
        gdf = load_zone_tub_gdf(root)
        dep_gdf = load_department_gdf(dept_code, project_root=project_root)
        if not gdf.empty and not dep_gdf.empty:
            gdf = gpd.clip(gdf.to_crs(dep_gdf.crs), dep_gdf)
        return gdf
        
    if pochoir_id in ("aoa", "pnf", "pochoir_aoa"):
        root = project_root or PROJECT_ROOT
        gdf = load_pnf_aoa_gdf(root)
        dep_gdf = load_department_gdf(dept_code, project_root=project_root)
        if not gdf.empty and not dep_gdf.empty:
            gdf = gpd.clip(gdf.to_crs(dep_gdf.crs), dep_gdf)
        return gdf
        
    logger.warning("Pochoir_id inconnu '%s', fallback sur département %s", pochoir_id, dept_code)
    return load_department_gdf(dept_code, project_root=project_root)


def write_pochoir_gpkg(
    dept_code: str,
    output_path: Path,
    *,
    pochoir_id: str = "departement",
    project_root: Optional[Path] = None,
) -> Path:
    """Écrit un GeoPackage pochoir (polygone standard) pour l'emprise demandée."""
    gdf = load_pochoir_gdf(pochoir_id, dept_code, project_root=project_root)
    
    if len(gdf) > 1:
        gdf = gdf.dissolve()
        
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    
    if pochoir_id in ("departement", "aucun"):
        layer_n = pochoir_layer_name(dept_code)
    else:
        norm_id = pochoir_id.replace("pochoir_", "", 1) if pochoir_id.startswith("pochoir_") else pochoir_id
        layer_n = f"pochoir_{norm_id}_sd{normalize_dept_code(dept_code)}"
        
    gdf.to_file(output_path, driver="GPKG", layer=layer_n)
    return output_path


def clip_gdf_to_pochoir(
    gdf_points: gpd.GeoDataFrame,
    pochoir_id: str,
    dept_code: str,
    *,
    project_root: Optional[Path] = None,
) -> gpd.GeoDataFrame:
    """
    Filtre spatialement un GeoDataFrame de points pour ne conserver que
    ceux à l'intérieur du polygone de pochoir.
    """
    if gdf_points.empty:
        return gdf_points

    poly_gdf = load_pochoir_gdf(pochoir_id, dept_code, project_root=project_root)
    if poly_gdf.empty:
        return gdf_points

    if len(poly_gdf) > 1:
        poly_gdf = poly_gdf.dissolve()

    # Uniformisation du CRS
    target_crs = poly_gdf.crs
    if gdf_points.crs and target_crs and gdf_points.crs != target_crs:
        gdf_points = gdf_points.to_crs(target_crs)

    # Intersection (clip)
    clipped = gpd.clip(gdf_points, poly_gdf)
    return clipped


def pochoir_cache_path(dept_code: str, cache_dir: Path) -> Path:
    return cache_dir / f"{pochoir_layer_name(dept_code)}.gpkg"


# Libellés historiques SD21 dans les titres YAML
_TITLE_DEPT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Côte[- ]d['']Or", re.IGNORECASE), "{dept_name}"),
    (re.compile(r"Cote d['']?Or", re.IGNORECASE), "{dept_name}"),
    (re.compile(r"\bSD21\b", re.IGNORECASE), "SD{dept_code}"),
)


def adapt_text_for_department(text: str, dept_code: str, dept_name: str) -> str:
    """Remplace les mentions Côte-d'Or / SD21 par le département courant."""
    if not text:
        return text
    code = normalize_dept_code(dept_code)
    out = text
    for pattern, repl in _TITLE_DEPT_PATTERNS:
        out = pattern.sub(
            repl.format(dept_name=dept_name, dept_code=code),
            out,
        )
    return out


def map_staleness_marker_path(map_png: Path, dept_code: str) -> Path:
    """Fichier sidecar indiquant pour quel département la carte a été générée."""
    return map_png.with_suffix(f".{normalize_dept_code(dept_code)}.dept")


def read_map_dept_marker(map_png: Path) -> Optional[str]:
    """Lit le code département associé à une carte PNG, si présent."""
    parent = map_png.parent
    stem = map_png.stem
    for p in parent.glob(f"{stem}.*.dept"):
        suffix = p.suffixes
        if len(suffix) >= 2:
            return suffix[-2].lstrip(".")
    return None


def write_map_dept_marker(map_png: Path, dept_code: str) -> None:
    """Enregistre le marqueur département et supprime les anciens pour ce PNG."""
    parent = map_png.parent
    stem = map_png.stem
    for old in parent.glob(f"{stem}.*.dept"):
        try:
            old.unlink()
        except OSError:
            pass
    marker = map_staleness_marker_path(map_png, dept_code)
    marker.write_text(normalize_dept_code(dept_code), encoding="utf-8")


def warn_if_unknown_carto_dept(dept_code: str) -> bool:
    """
    Avertit si le département cartographique est absent du référentiel admin.

    Retourne True si le département est connu (pochoir exportable).
    """
    code = normalize_dept_code(dept_code)
    if not code:
        logger.warning("Code département cartographie vide — export pochoir impossible.")
        return False
    shp = get_departements_admin_shp()
    if not shp.exists():
        logger.warning(
            "Shapefile départements introuvable (%s) — impossible de valider le département %s.",
            shp,
            code,
        )
        return False
    try:
        load_department_gdf(code)
        return True
    except ValueError:
        logger.warning(
            "Département %s introuvable dans %s — les cartes ne pourront pas être générées "
            "pour ce périmètre. Vérifiez --code / --echelle.",
            code,
            shp.name,
        )
        return False


def is_map_valid_for_dept(
    map_png: Path,
    dept_code: str,
    *,
    allow_legacy_sd21: bool = True,
) -> bool:
    """
    True si la carte PNG correspond au département demandé.

    Sans fichier ``.XX.dept`` : acceptation rétroactive uniquement pour le 21
    (cartes historiques Côte-d'Or générées avant le marqueur département).
    """
    if not map_png.exists():
        return False

    from core.chemins_projet import get_cartes_dir
    try:
        abs_map = map_png.resolve()
        abs_cartes_dir = get_cartes_dir().resolve()
        if not abs_map.is_relative_to(abs_cartes_dir):
            return True
        if not abs_map.name.startswith("carte_"):
            return True
    except Exception:
        pass
    target = normalize_dept_code(dept_code)
    marker_dept = read_map_dept_marker(map_png)
    if marker_dept is not None:
        return marker_dept == target
    return bool(allow_legacy_sd21 and target == "21")
