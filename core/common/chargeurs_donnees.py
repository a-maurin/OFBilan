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
MODULE : CHARGEURS DE DONNEES METIER ET GEOSPATIALES (`chargeurs_donnees.py`)
========================================================================================
Ce module constitue le moteur principal d'acquisition, de nettoyage et d'enrichissement
spatial des données de police de l'environnement de l'OFB.

Données traitées :
  1. Points de contrôle OSCEAN (GPKG / Shapefiles issus des contrôles de terrain).
  2. Procédures d'Enquête Judiciaire (PEJ) issues des exports ODS/XLSX d'OSCEAN.
  3. Procédures Administratives (PA) et Procès-Verbaux Électroniques (PVe).
  4. Référentiels géographiques : communes (21 / France), zones PNF (Parc National de
     Forêts) et TUB (Tuberculose Bovine).
  5. Référentiels d'infractions (Codes NATINF et leurs qualifications juridiques).

Fonctionnalités avancées :
  - Mise en cache mémoire de session (`_SESSION_CACHE`) pour accélérer le traitement.
  - Jointures spatiales automatiques via GeoPandas / OGR pour attribuer les communes.
  - Parsing robuste des dates multi-formats (ISO et français DD/MM/YYYY).
  - Coalescence des dates et dédoublonnage intelligent par ID de dossier (`DC_ID`).
========================================================================================
"""
from __future__ import annotations
import gzip
import hashlib
import json
import logging
import os
import pickle
import sys
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple, Union

# Optimisation de lecture pour l'accès réseau distant (évite les scans récursifs SMB)
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")

try:
    import geopandas as gpd
except ImportError:
    gpd = None

import pandas as pd
import numpy as np
import re

from core.chemins_projet import ref_programme
from core.common.utilitaires_metier import (
    coalesced_insee_series,
    extract_insee_code_series,
    filtre_periode,
    series_as_python_str,
)

logger = logging.getLogger(__name__)

def read_vector_attributes(path: Path) -> pd.DataFrame:
    """Lit les attributs d'une couche vecteur (sans géométrie). Fallback OGR si geopandas absent.

    Les coordonnées WGS84 (x_wgs84, y_wgs84) sont extraites de la géométrie
    avant sa suppression si elles ne sont pas déjà présentes comme attributs.
    Cela permet aux exports cartographiques de construire des GeoDataFrames
    même quand les fichiers sources ne stockent pas les coordonnées en attributs.
    """
    try:
        import geopandas as gpd
        gdf = gpd.read_file(path)
        # Extraire coordonnées WGS84 depuis la géométrie si pas déjà en attributs
        try:
            if hasattr(gdf, "geometry") and getattr(gdf, "_geometry_column_name", None) in gdf.columns:
                if gdf.geometry is not None and not gdf.geometry.isna().all():
                    has_x = any(c in gdf.columns for c in ("x_wgs84", "longitude", "lon", "x"))
                    has_y = any(c in gdf.columns for c in ("y_wgs84", "latitude", "lat", "y"))
                    if not has_x or not has_y:
                        gdf_wgs84 = gdf.to_crs("EPSG:4326") if (gdf.crs and gdf.crs.to_epsg() != 4326) else gdf
                        if not has_x:
                            gdf["x_wgs84"] = gdf_wgs84.geometry.x
                        if not has_y:
                            gdf["y_wgs84"] = gdf_wgs84.geometry.y
        except Exception:
            pass
        return pd.DataFrame(gdf.drop(columns=["geometry"], errors="ignore"))
    except ImportError:
        from osgeo import ogr
        ds = ogr.Open(str(path))
        if not ds:
            raise RuntimeError(f"Impossible d'ouvrir {path} avec ogr")
        layer = ds.GetLayer()
        layer_def = layer.GetLayerDefn()
        fields = [layer_def.GetFieldDefn(i).GetName() for i in range(layer_def.GetFieldCount())]
        data = []
        for feature in layer:
            data.append([feature.GetField(f) for f in fields])
        ds = None
        return pd.DataFrame(data, columns=fields)

# ========================================================================================
# 1. UTILITAIRES DE LECTURE VECTEUR ET GESTION DU CACHE MEMOIRE
# ========================================================================================

# Ordre d'évaluation prioritaire des colonnes INSEE pour l'unification des jeux de données
_INSEE_COL_PRIORITY: Tuple[str, ...] = (
    "insee_comm",
    "insee_commun",
    "INSEE_COM",
    "INF-INSEE",
)

# Structure du cache global de session (évite de relire plusieurs fois les fichiers volumineux)
_SESSION_CACHE = {
    "active": False,
    "point_ctrl": None,
    "pej": None,
    "pa": None,
    "pve": None,
}

_POINT_CTRL_RAW_CACHE = {}
_PEJ_RAW_CACHE = {}
_PA_RAW_CACHE = {}
_PVE_RAW_CACHE = {}
_FAITS_RAW_CACHE = {}


def _get_cache_dir(root: Optional[Path] = None) -> Path:
    """Dossier du cache disque des données (déporté localement dans %LOCALAPPDATA%/OFBilan/cache)."""
    try:
        from core.chemins_projet import PROJECT_ROOT, get_app_data_dir
        if root is not None and root.resolve() != PROJECT_ROOT.resolve():
            cache_dir = root / "data" / "cache"
        else:
            cache_dir = get_app_data_dir() / "cache"
    except Exception:
        cache_dir = (root if root is not None else Path.home()) / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def clear_disk_cache() -> int:
    """Supprime tous les fichiers du cache disque et renvoie le nombre de fichiers supprimés."""
    cache_dir = _get_cache_dir()
    deleted = 0
    if cache_dir.exists():
        for p in cache_dir.glob("*"):
            if p.is_file():
                try:
                    p.unlink(missing_ok=True)
                    deleted += 1
                except OSError:
                    pass
    return deleted


def _compute_files_signature(files: List[Path]) -> str:
    items = []
    for f in sorted(files, key=lambda p: str(p)):
        try:
            stat = f.stat()
            items.append(f"{f.name}:{stat.st_size}:{stat.st_mtime}")
        except OSError:
            items.append(f"{f.name}:missing")
    raw = "|".join(items)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_source_files_metadata(root: Path) -> List[Dict[str, str]]:
    """Retourne la liste des métadonnées des fichiers sources sous data/sources/ (y compris sous-dossiers récursifs SIG) pour la traçabilité en annexe."""
    from datetime import datetime
    sources_dir = root / "data" / "sources"
    if not sources_dir.exists():
        return []

    # 1. Parcours récursif des seuls fichiers ayant une extension de données métiers
    allowed_exts = {".xlsx", ".ods", ".csv", ".gpkg", ".shp", ".geojson", ".parquet"}
    all_files: List[Path] = [
        p for p in sources_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in allowed_exts
        and not p.name.startswith(".")
        and not p.name.startswith("~$")
    ]

    # 2. Filtrage des sidecars Shapefile (.shx, .dbf, .prj...) si un fichier .shp principal existe
    shp_stems = {p.with_suffix("").as_posix() for p in all_files if p.suffix.lower() == ".shp"}
    sidecar_exts = {".shx", ".dbf", ".prj", ".cpg", ".qpj", ".sbn", ".sbx"}

    filtered_files: List[Path] = []
    for p in all_files:
        ext = p.suffix.lower()
        posix_stem = p.with_suffix("").as_posix()
        if ext in sidecar_exts and posix_stem in shp_stems:
            continue
        filtered_files.append(p)


    # 3. Construction des métadonnées avec chemins relatifs POSIX
    results: List[Dict[str, str]] = []
    for p in filtered_files:
        try:
            rel_path = p.relative_to(sources_dir).as_posix()
            st = p.stat()
            mtime_str = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M")
            size_str = f"{st.st_size / 1024:.1f} Ko" if st.st_size < 1024 * 1024 else f"{st.st_size / (1024 * 1024):.2f} Mo"
            h = hashlib.sha256()
            with open(p, "rb") as f:
                h.update(f.read(8 * 1024 * 1024))
            sig = h.hexdigest()[:12]
            results.append({
                "nom": rel_path,
                "taille": size_str,
                "date": mtime_str,
                "empreinte": sig,
            })
        except Exception as e:
            logger.debug("Impossible d'extraire la signature de %s: %s", p, e)

    results.sort(key=lambda x: x["nom"].lower())
    return results



def _load_disk_cache(root: Path, cache_key: str, files_sig: str) -> Optional[pd.DataFrame]:
    try:
        cache_dir = _get_cache_dir(root)
        meta_file = cache_dir / f"{cache_key}.meta.json"
        data_file = cache_dir / f"{cache_key}.pkl.gz"
        
        if not meta_file.exists() or not data_file.exists():
            return None
            
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
            
        if meta.get("files_sig") != files_sig:
            logger.info("Cache disque '%s' obsolète (fichiers sources modifiés).", cache_key)
            return None
            
        logger.info("Chargement rapide depuis le cache disque : %s", cache_key)
        with gzip.open(data_file, "rb") as f:
            df = pickle.load(f)
        return df
    except Exception as e:
        logger.warning("Échec de la lecture du cache disque '%s' (corrompu ?) : %s", cache_key, e)
        try:
            cache_dir = _get_cache_dir(root)
            (cache_dir / f"{cache_key}.meta.json").unlink(missing_ok=True)
            (cache_dir / f"{cache_key}.pkl.gz").unlink(missing_ok=True)
        except Exception:
            pass
        return None


def _save_disk_cache(root: Path, cache_key: str, files_sig: str, df: pd.DataFrame) -> None:
    try:
        cache_dir = _get_cache_dir(root)
        meta_file = cache_dir / f"{cache_key}.meta.json"
        data_file = cache_dir / f"{cache_key}.pkl.gz"
        tmp_data_file = cache_dir / f"{cache_key}.pkl.gz.tmp"
        
        with gzip.open(tmp_data_file, "wb") as f:
            pickle.dump(df, f, protocol=pickle.HIGHEST_PROTOCOL)
            
        tmp_data_file.replace(data_file)
        
        meta = {
            "files_sig": files_sig,
            "rows": len(df),
            "cols": len(df.columns)
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
            
        logger.info("Cache disque sauvegardé : %s (%d lignes)", cache_key, len(df))
    except Exception as e:
        logger.warning("Impossible d'écrire le cache disque '%s' : %s", cache_key, e)


def init_session_cache(
    root: Path,
    echelle: str = "national",
    codes: Optional[list[str]] = None,
    date_deb: Optional[Union[str, pd.Timestamp]] = None,
    date_fin: Optional[Union[str, pd.Timestamp]] = None,
) -> None:
    """Charge en mémoire toutes les données pour les départements concernés et active le cache."""
    global _SESSION_CACHE
    _SESSION_CACHE["active"] = False  # Désactiver temporairement pour forcer la lecture réelle
    
    if codes is None:
        codes = ["FR"]
    codes_str = ",".join(codes)
    logger.info("Pré-chargement des données pour la session globale (codes: %s)...", codes_str)
    
    try:
        _SESSION_CACHE["point_ctrl"] = load_point_ctrl(
            root, echelle=echelle, code=codes_str, date_deb=date_deb, date_fin=date_fin
        )
    except Exception as e:
        logger.warning("Impossible de pré-charger point_ctrl : %s", e)
        _SESSION_CACHE["point_ctrl"] = pd.DataFrame()

    try:
        _SESSION_CACHE["pej"] = load_pej(
            root, echelle=echelle, code=codes_str, date_deb=date_deb, date_fin=date_fin
        )
    except Exception as e:
        logger.warning("Impossible de pré-charger pej : %s", e)
        _SESSION_CACHE["pej"] = pd.DataFrame()

    try:
        _SESSION_CACHE["pa"] = load_pa(
            root, echelle=echelle, code=codes_str, date_deb=date_deb, date_fin=date_fin
        )
    except Exception as e:
        logger.warning("Impossible de pré-charger pa : %s", e)
        _SESSION_CACHE["pa"] = pd.DataFrame()

    try:
        _SESSION_CACHE["pve"] = load_pve(
            root, echelle=echelle, code=codes_str, date_deb=date_deb, date_fin=date_fin
        )
    except Exception as e:
        logger.warning("Impossible de pré-charger pve : %s", e)
        _SESSION_CACHE["pve"] = pd.DataFrame()

    _SESSION_CACHE["active"] = True


def clear_session_cache() -> None:
    """Vide et désactive le cache global de session."""
    global _SESSION_CACHE
    _SESSION_CACHE["active"] = False
    _SESSION_CACHE["point_ctrl"] = None
    _SESSION_CACHE["pej"] = None
    _SESSION_CACHE["pa"] = None
    _SESSION_CACHE["pve"] = None
    _FAITS_RAW_CACHE.clear()


def safe_to_datetime(series: pd.Series) -> pd.Series:
    """
    Parse les dates de manière sécurisée en gérant le format français (DD/MM/YYYY)
    et le format ISO (YYYY-MM-DD) pour éviter les inversions jour/mois et les NaT.
    """
    if series.empty:
        return pd.to_datetime(series)
    s_str = series.astype(str).str.strip()
    res = pd.Series(pd.NaT, index=series.index)
    
    import re
    iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}")
    fr_pattern = re.compile(r"^\d{2}/\d{2}/\d{4}")
    
    # Utilisation de .apply pour contourner l'incompatibilité de pyarrow dans l'environnement QGIS
    iso_mask = s_str.apply(lambda val: bool(iso_pattern.match(val)) if isinstance(val, str) else False)
    fr_mask = s_str.apply(lambda val: bool(fr_pattern.match(val)) if isinstance(val, str) else False)
    
    # 1. Format ISO (YYYY-MM-DD)
    if iso_mask.any():
        years = pd.to_numeric(s_str[iso_mask].str.slice(0, 4), errors="coerce")
        valid_years = (years >= 1678) & (years <= 2262)
        actual_iso_mask = iso_mask.copy()
        actual_iso_mask[iso_mask] = valid_years.fillna(False)
        if actual_iso_mask.any():
            res[actual_iso_mask] = pd.to_datetime(
                s_str[actual_iso_mask].str.slice(0, 10), format="%Y-%m-%d", errors="coerce"
            )
        
    # 2. Format français (DD/MM/YYYY)
    if fr_mask.any():
        years = pd.to_numeric(s_str[fr_mask].str.slice(6, 10), errors="coerce")
        valid_years = (years >= 1678) & (years <= 2262)
        actual_fr_mask = fr_mask.copy()
        actual_fr_mask[fr_mask] = valid_years.fillna(False)
        if actual_fr_mask.any():
            res[actual_fr_mask] = pd.to_datetime(
                s_str[actual_fr_mask].str.slice(0, 10), format="%d/%m/%Y", errors="coerce"
            )
        
    # 3. Fallback pour les autres formats/datetimes
    other_mask = ~(iso_mask | fr_mask) & series.notna()
    if other_mask.any():
        try:
            res[other_mask] = pd.to_datetime(
                series[other_mask], errors="coerce", format="mixed"
            )
        except Exception:
            for idx, val in series[other_mask].items():
                try:
                    res.loc[idx] = pd.to_datetime(val, errors="coerce")
                except Exception:
                    res.loc[idx] = pd.NaT
    return res


def _filter_dept_series(df: pd.DataFrame, col: str, target_depts: Sequence[str]) -> pd.DataFrame:
    """Filtre un DataFrame en gérant la normalisation des codes départements (ex: 21, 21.0, 021)."""
    if df.empty or col not in df.columns or not target_depts or "FR" in target_depts:
        return df
    clean_s = df[col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    targets = set()
    for d in target_depts:
        d_str = str(d).strip().upper()
        targets.add(d_str)
        if d_str.isdigit():
            targets.add(str(int(d_str)))
            targets.add(d_str.zfill(2))
    return df[clean_s.isin(targets)].copy()


def _find_latest_dated_file(directory: Path, prefix: str, exts: Tuple[str, ...]) -> Path:
    """
    Retourne, parmi les fichiers de `directory` commençant par `prefix` et se
    terminant par l'une des extensions de `exts`, celui dont la date suffixe
    (format YYYYMMDD) est la plus récente.
    """
    latest_path: Path | None = None
    latest_date: str | None = None

    for ext in exts:
        pattern = f"{prefix}*{ext}"
        for p in directory.glob(pattern):
            m = re.match(re.escape(prefix) + r"(\d{8})", p.name)
            if not m:
                continue
            date_str = m.group(1)
            if latest_date is None or date_str > latest_date:
                latest_date = date_str
                latest_path = p

    if latest_path is None:
        raise FileNotFoundError(
            f"Aucun fichier trouvé dans {directory} pour le préfixe '{prefix}' "
            f"et les extensions {exts}."
        )
    return latest_path


def _read_spreadsheet(path: Path, *, dtype=str) -> pd.DataFrame:
    """
    Lit un classeur ODS / XLSX.

    Priorité : ``calamine`` (rapide sur gros ODS) ; repli ``odf`` / ``openpyxl``.
    """
    suffix = path.suffix.lower()
    if suffix == ".ods":
        try:
            return pd.read_excel(path, dtype=dtype, engine="calamine")
        except ImportError:
            logger.info(
                "python-calamine absent : lecture ODS lente (%s). "
                "Installez python-calamine pour accélérer.",
                path.name,
            )
        except Exception as exc:
            logger.warning(
                "Lecture ODS via calamine impossible (%s) : %s — repli odf.",
                path.name,
                exc,
            )
        logger.info("Lecture ODS en cours (peut prendre ~1 min) : %s", path.name)
        return pd.read_excel(path, dtype=dtype, engine="odf")
    if suffix == ".xlsx":
        return pd.read_excel(path, dtype=dtype, engine="openpyxl")
    raise ValueError(f"Format de classeur non pris en charge : {path}")


# ========================================================================================
# 2. CHARGEMENT ET FILTRAGE DES DONNEES METIER OSCEAN (POINTS CTRL, PEJ, PA, PVE)
# ========================================================================================

def load_point_ctrl(
    root: Path,
    echelle: Optional[str] = None,
    code: Optional[str] = None,
    date_deb: Optional[Union[str, pd.Timestamp]] = None,
    date_fin: Optional[Union[str, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """
    Charge les points de contrôle OSCEAN à partir des fichiers
    point_ctrl_YYYYMMDD_wgs84.gpkg présents dans sources/sig.

    Pour chaque année, seul le GPKG le plus récent (date suffixe la plus élevée)
    est utilisé, afin d'éviter les doublons liés aux extractions mensuelles.

    Si dept_code, date_deb et date_fin sont fournis, seules les années
    recouvrant la période sont chargées et les lignes sont filtrées par
    département et période (accélère l'analyse sur sources nationales).
    """
    global _SESSION_CACHE
    if _SESSION_CACHE["active"] and _SESSION_CACHE["point_ctrl"] is not None:
        df_all = _SESSION_CACHE["point_ctrl"].copy()
        if echelle is not None and code is not None:
            from core.common.utilitaires_metier import get_departements_pour_perimetre, get_bmi_filters
            echelle_norm = str(echelle).strip().lower()
            if echelle_norm == "bmi" and "entit_ctrl" in df_all.columns:
                bmi_filters = get_bmi_filters(code)
                entit_ctrl_val = str(bmi_filters.get("entit_ctrl", code)).upper()
                df_all = df_all[df_all["entit_ctrl"].astype(str).str.upper().str.contains(entit_ctrl_val, case=True, na=False, regex=False)].copy()
            elif echelle_norm != "bmi" and "num_depart" in df_all.columns:
                dept_codes = get_departements_pour_perimetre(echelle, code)
                if dept_codes and "FR" not in dept_codes:
                    df_all = _filter_dept_series(df_all, "num_depart", dept_codes)
        if date_deb is not None and date_fin is not None:
            try:
                deb_ts = pd.to_datetime(date_deb)
                fin_ts = pd.to_datetime(date_fin)
            except ValueError as e:
                raise ValueError(f"Format de date invalide : {e}")
            df_all = filtre_periode(df_all, "date_ctrl", deb_ts, fin_ts)
        return df_all

    sources_sig = root / "data" / "sources" / "sig"
    if not sources_sig.exists():
        raise FileNotFoundError(
            f"Le dossier des données SIG sources n'existe pas : {sources_sig}"
        )

    # Nouvelle organisation : les fichiers de points de contrôle sont rangés par année
    # dans des sous-dossiers de type points_de_ctrl_OSCEAN_YYYY sous sources/sig.
    # Les couches peuvent être au format GPKG ou SHP et le nommage peut varier
    # (point/pts/pt, controle/ctrl, etc.). On doit donc rechercher de manière
    # plus souple que le strict pattern point_ctrl_YYYYMMDD_wgs84.*
    candidates: List[Path] = []
    year_dirs = [
        d
        for d in sources_sig.glob("points_de_ctrl_OSCEAN_*")
        if d.is_dir()
    ]
    for d in year_dirs:
        for ext in (".gpkg", ".shp"):
            # Noms usuels : point_ctrl_..., pts_ctrl_..., pt_controle_..., etc.
            for pat in ("*point*ctrl*",
                        "*pts*ctrl*",
                        "*pt*ctrl*",
                        "*ctrl*"):
                candidates.extend(d.glob(f"{pat}{ext}"))

    # Rétrocompatibilité : si aucun sous-dossier n'est trouvé (ancienne arborescence
    # ou environnement non migré), on cherche encore à la racine de sources/sig.
    if not candidates:
        candidates = []
        for ext in (".gpkg", ".shp"):
            for pat in ("*point*ctrl*",
                        "*pts*ctrl*",
                        "*pt*ctrl*",
                        "*ctrl*"):
                candidates.extend(sources_sig.glob(f"{pat}{ext}"))

    if not candidates:
        raise FileNotFoundError(
            f"Aucun fichier de points de contrôle (formats GPKG/SHP) trouvé dans {sources_sig} "
            f"(attendus dans des sous-dossiers points_de_ctrl_OSCEAN_YYYY ou à la racine, "
            f"avec un nom contenant 'ctrl')."
        )

    # Vérification des chemins et fichiers
    for candidate in candidates:
        if not candidate.is_file():
            raise FileNotFoundError(f"Le fichier {candidate} n'est pas un fichier valide.")

    # Sélectionner, pour chaque année, le fichier au suffixe de date le plus récent.
    per_year: dict[str, tuple[str, Path]] = {}
    for p in candidates:
        # Extraire une date au format YYYYMMDD à partir du nom de fichier, même si
        # elle est écrite sous la forme YYYY_MM_DD ou similaire. On concatène
        # tous les chiffres présents et on prend les 8 premiers si possible.
        digits = "".join(ch for ch in p.stem if ch.isdigit())
        if len(digits) >= 8:
            date_str = digits[:8]
            year = date_str[:4]
        elif len(digits) >= 4:
            # Fallback : le nom de fichier ne contient pas de date YYYYMMDD
            # complète (ex. point_ctrl_2024_wgs84 → "202484", 6 chiffres).
            # On tente d'extraire l'année depuis le nom du dossier parent
            # (points_de_ctrl_OSCEAN_YYYY) puis, à défaut, depuis les 4
            # premiers chiffres du nom de fichier.
            parent_digits = re.findall(r"\d{4}", p.parent.name)
            if parent_digits:
                year = parent_digits[-1]
            else:
                year = digits[:4]
            date_str = f"{year}0101"
        else:
            continue
        cur = per_year.get(year)
        if cur is None or date_str > cur[0]:
            per_year[year] = (date_str, p)

    # Restreindre aux années couvrant la période demandée si date_deb/date_fin fournis
    if date_deb is not None and date_fin is not None:
        try:
            deb_ts = pd.to_datetime(date_deb)
            fin_ts = pd.to_datetime(date_fin)
            year_min, year_max = deb_ts.year, fin_ts.year
            filtered = {y: t for y, t in per_year.items() if year_min <= int(y) <= year_max}
            if filtered:
                per_year = filtered
        except Exception as e:
            raise ValueError(f"Erreur de conversion des dates : {e}")

    selected_paths = [tpl[1] for tpl in per_year.values()]
    sig = _compute_files_signature(selected_paths)
    is_national_full = (echelle is None or str(echelle).lower() == "national") and (code is None or code == "FR") and date_deb is None and date_fin is None
    if is_national_full:
        cached_df = _load_disk_cache(root, "point_ctrl_national", sig)
        if cached_df is not None:
            return cached_df.copy()

    frames: List[pd.DataFrame] = []
    from core.common.utilitaires_metier import get_departements_pour_perimetre
    target_depts = get_departements_pour_perimetre(echelle, code)
    
    for path in selected_paths:
        if path in _POINT_CTRL_RAW_CACHE:
            df = _POINT_CTRL_RAW_CACHE[path].copy()
        else:
            path_sig = _compute_files_signature([path])
            raw_key = f"point_ctrl_raw_{path.stem}"
            cached_df = _load_disk_cache(root, raw_key, path_sig)
            if cached_df is not None:
                df = cached_df.copy()
            else:
                try:
                    df = read_vector_attributes(path)
                except Exception as e:
                    raise RuntimeError(f"Erreur de lecture du fichier SIG : {e}")
                df.columns = [str(c).split(",")[0].strip() for c in df.columns]
            
            # Validation des colonnes requises
            required_columns = ["date_ctrl", "dc_id", "num_depart"]
            for col in required_columns:
                if col not in df.columns:
                    raise KeyError(f"La colonne '{col}' est absente des données point_ctrl_*")
            
            if "date_ctrl" in df.columns:
                df["date_ctrl"] = safe_to_datetime(df["date_ctrl"])
    
            # Nom du dossier
            if "nom_dossier" in df.columns and "nom_dossie" not in df.columns:
                df["nom_dossie"] = df["nom_dossier"]
    
            # Type d'action
            if "type_action" in df.columns and "type_actio" not in df.columns:
                df["type_actio"] = df["type_action"]
    
            # Normalisation robuste (insensible à la casse) des colonnes clés
            new_cols = {}
            for col in df.columns:
                col_upper = str(col).upper()
                if col_upper == "DOMAINE" and col != "domaine" and "domaine" not in df.columns:
                    new_cols[col] = "domaine"
                elif col_upper == "THEME" and col != "theme" and "theme" not in df.columns:
                    new_cols[col] = "theme"
                elif col_upper in ("RESULTAT", "RÉSULTAT") and col != "resultat" and "resultat" not in df.columns:
                    new_cols[col] = "resultat"
                elif col_upper == "RESULTAT_CONTROLE" and col != "resultat_controle" and "resultat_controle" not in df.columns:
                    new_cols[col] = "resultat_controle"
                elif col_upper in ("ENTITE_CTRL", "ENTIT_CTRL", "ENTITE") and col != "entite_ctrl" and "entite_ctrl" not in df.columns:
                    new_cols[col] = "entite_ctrl"
            
            if new_cols:
                df.rename(columns=new_cols, inplace=True)
            
            if "entite_ctrl" in df.columns and "entit_ctrl" not in df.columns:
                df["entit_ctrl"] = df["entite_ctrl"]
            elif "entit_ctrl" in df.columns and "entite_ctrl" not in df.columns:
                df["entite_ctrl"] = df["entit_ctrl"]
    
            # Nom de commune
            if "nom_commune" in df.columns and "nom_commun" not in df.columns:
                df["nom_commun"] = df["nom_commune"]
    
            # Type d'usager / usage
            if "type_usager" in df.columns and "type_usage" not in df.columns:
                df["type_usage"] = df["type_usager"]
            if "type_usage" in df.columns and "type_usager" not in df.columns:
                df["type_usager"] = df["type_usage"]
    
            # Nature du contrôle
            if "nature_controle" in df.columns and "nature_con" not in df.columns:
                df["nature_con"] = df["nature_controle"]
            if "nature_con" in df.columns and "nature_controle" not in df.columns:
                df["nature_controle"] = df["nature_con"]
    
            # Plan de contrôle
            if "plan_controle" in df.columns and "plan_contr" not in df.columns:
                df["plan_contr"] = df["plan_controle"]
            if "plan_contr" in df.columns and "plan_controle" not in df.columns:
                df["plan_controle"] = df["plan_contr"]
    
            # Avis patrimoine / biodiversité
            avis_src = None
            for cand in ("avis_patbiodiv", "avis_patbi", "avis_pasbi"):
                if cand in df.columns:
                    avis_src = cand
                    break
            if avis_src is not None:
                if "avis_patbiodiv" not in df.columns:
                    df["avis_patbiodiv"] = df[avis_src]
                if "avis_patbi" not in df.columns:
                    df["avis_patbi"] = df[avis_src]
                if "avis_pasbi" not in df.columns:
                    df["avis_pasbi"] = df[avis_src]
            
                _save_disk_cache(root, raw_key, path_sig, df)
            _POINT_CTRL_RAW_CACHE[path] = df.copy()

        # Filtre à posteriori par département
        if target_depts is not None and "FR" not in target_depts:
            if "num_depart" in df.columns:
                df = _filter_dept_series(df, "num_depart", target_depts)
        
        frames.append(df)

    if not frames:
        raise FileNotFoundError(
            f"Aucun enregistrement valide trouvé dans les GPKG point_ctrl de {sources_sig}"
        )

    df_all = pd.concat(frames, ignore_index=True)
    dedup_cols = [c for c in ["dc_id", "date_ctrl", "x", "y"] if c in df_all.columns]
    if dedup_cols:
        df_all.drop_duplicates(subset=dedup_cols, keep="first", inplace=True)
    if "date_ctrl" not in df_all.columns:
        raise KeyError("La colonne 'date_ctrl' est absente des données point_ctrl_*")

    if is_national_full:
        _save_disk_cache(root, "point_ctrl_national", sig, df_all)

    # Filtrage optionnel par périmètre et période
    if echelle is not None and code is not None:
        from core.common.utilitaires_metier import get_departements_pour_perimetre, get_bmi_filters
        echelle_norm = str(echelle).strip().lower()
        if echelle_norm == "bmi" and "entit_ctrl" in df_all.columns:
            bmi_filters = get_bmi_filters(code)
            entit_ctrl_val = str(bmi_filters.get("entit_ctrl", code)).upper()
            df_all = df_all[df_all["entit_ctrl"].astype(str).str.upper().str.contains(entit_ctrl_val, case=True, na=False, regex=False)].copy()
        elif echelle_norm != "bmi" and "num_depart" in df_all.columns:
            dept_codes = get_departements_pour_perimetre(echelle, code)
            if dept_codes and "FR" not in dept_codes:
                df_all = _filter_dept_series(df_all, "num_depart", dept_codes)
    if date_deb is not None and date_fin is not None:
        try:
            deb_ts = pd.to_datetime(date_deb)
            fin_ts = pd.to_datetime(date_fin)
        except ValueError as e:
            raise ValueError(f"Format de date invalide : {e}")
        df_all = filtre_periode(df_all, "date_ctrl", deb_ts, fin_ts)

    return df_all


def load_pej(
    root: Path,
    echelle: Optional[str] = None,
    code: Optional[str] = None,
    date_deb: Optional[Union[str, pd.Timestamp]] = None,
    date_fin: Optional[Union[str, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """
    Charge le classeur ODS des procédures d'enquête judiciaire le plus récent
    (suivi_procedure_enq_judiciaire_YYYYMMDD.ods dans sources/) et prépare
    ``DATE_REF`` (affichages / tris) ainsi que ``RECAP_DATE_INIT_PJ``.

    Le **décompte et le filtre de période** s'appuient sur la coalescence ``DATE_REF``
    (qui priorise la date des faits, puis l'ouverture de procédure, puis la date d'initialisation).

    Si *dept_code* est fourni, les lignes sont restreintes à
    ``ENTITE_ORIGINE_PROCEDURE == SD{dept_code}``, puis dédoublonnées par ``DC_ID``
    (ligne la plus récente selon ``DATE_REF``).

    Les localisations ne sont pas dans l'ODS : les joindre via
    ``merge_pej_faits_locations`` sur la couche ``localisation_infrac_FAITS_*``.
    Voir ref/README_sources.md § 2.2.
    """
    global _SESSION_CACHE
    if _SESSION_CACHE["active"] and _SESSION_CACHE["pej"] is not None:
        df = _SESSION_CACHE["pej"].copy()
        if df.empty or "DATE_REF" not in df.columns:
            # Le préchargement a échoué (ex. odfpy absent) — retour propre sans crash
            return pd.DataFrame()
        if date_deb is not None and date_fin is not None:
            deb_ts = pd.to_datetime(date_deb)
            fin_ts = pd.to_datetime(date_fin)
            df = filtre_periode(df, "DATE_REF", deb_ts, fin_ts)
        if echelle is not None and code is not None:
            from core.common.utilitaires_metier import get_departements_pour_perimetre, get_bmi_filters
            echelle_norm = str(echelle).strip().lower()
            if echelle_norm == "bmi" and "ENTITE_ORIGINE_PROCEDURE" in df.columns:
                bmi_filters = get_bmi_filters(code)
                entite_pej_val = str(bmi_filters.get("entite_pej", code)).upper()
                df = df[df["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.upper().str.contains(entite_pej_val, case=True, na=False, regex=False)].copy()
            elif echelle_norm != "bmi" and "ENTITE_ORIGINE_PROCEDURE" in df.columns:
                dept_codes = get_departements_pour_perimetre(echelle, code)
                if dept_codes and "FR" not in dept_codes:
                    dept_extracted = df["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.extract(r'(\d+)')[0]
                    pnf_mask = df["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.upper().str.contains(r'PNF|PARC|FORET', regex=True, na=False)
                    df = df[dept_extracted.isin(dept_codes) | pnf_mask].copy()
        if not df.empty and "DC_ID" in df.columns:
            if "DATE_REF" in df.columns:
                df = df.sort_values("DATE_REF", ascending=False)
                df = df[df["DC_ID"].isna() | ~df.duplicated(subset=["DC_ID"], keep="first")]
            else:
                df = df[df["DC_ID"].isna() | ~df.duplicated(subset=["DC_ID"], keep="first")]
        return df

    sources = root / "data" / "sources"
    prefix = "suivi_procedure_enq_judiciaire_"
    path = _find_latest_dated_file(sources, prefix, (".ods",))
    
    sig = _compute_files_signature([path])
    is_national_full = (echelle is None or str(echelle).lower() == "national") and (code is None or code == "FR") and date_deb is None and date_fin is None
    if is_national_full:
        cached_df = _load_disk_cache(root, "pej_national", sig)
        if cached_df is not None:
            return cached_df.copy()

    if path in _PEJ_RAW_CACHE:
        df = _PEJ_RAW_CACHE[path].copy()
    else:
        raw_key = f"pej_raw_{path.stem}"
        cached_df = _load_disk_cache(root, raw_key, sig)
        if cached_df is not None:
            df = cached_df.copy()
        else:
            df = _read_spreadsheet(path)
            df.columns = pd.Index([str(c).strip().upper() for c in df.columns])
            # Alias pour compatibilité si le classeur utilise "NATINF" au lieu de "NATINF_PEJ"
            if "NATINF" in df.columns and "NATINF_PEJ" not in df.columns:
                df["NATINF_PEJ"] = df["NATINF"]
            # Alias "type_usager" pour filtrage des bilans usagers ciblés
            if "type_usager" not in df.columns:
                for cand in ("TYPE_USAGER", "TYPE USAGER", "USAGER", "USGAER"):
                    if cand in df.columns:
                        df["type_usager"] = df[cand]
                        break
            df["DATE_CONSTATATION"] = safe_to_datetime(df["DATE_CONSTATATION"])
            df["DATE_OUVERTURE_PROCEDURE"] = safe_to_datetime(df["DATE_OUVERTURE_PROCEDURE"])
            
            has_recap_date = "RECAP_DATE_INIT_PJ" in df.columns
            if not has_recap_date:
                df["RECAP_DATE_INIT_PJ"] = pd.NaT
            else:
                df["RECAP_DATE_INIT_PJ"] = safe_to_datetime(df["RECAP_DATE_INIT_PJ"])
                
            df["DATE_REF"] = (
                df["DATE_CONSTATATION"]
                .fillna(df["DATE_OUVERTURE_PROCEDURE"])
                .fillna(df["RECAP_DATE_INIT_PJ"])
            )
            df.attrs["missing_recap_date"] = not has_recap_date
            _save_disk_cache(root, raw_key, sig, df)
        _PEJ_RAW_CACHE[path] = df.copy()
        if is_national_full:
            _save_disk_cache(root, "pej_national", sig, df)

    if df.attrs.get("missing_recap_date") and date_deb is not None and date_fin is not None:
        raise KeyError(
            "Colonne RECAP_DATE_INIT_PJ absente du classeur PEJ — "
            "obligatoire pour le filtre de période."
        )
    if date_deb is not None and date_fin is not None:
        deb_ts = pd.to_datetime(date_deb)
        fin_ts = pd.to_datetime(date_fin)
        df = filtre_periode(df, "DATE_REF", deb_ts, fin_ts)

    if echelle is not None and code is not None:
        from core.common.utilitaires_metier import get_departements_pour_perimetre, get_bmi_filters
        echelle_norm = str(echelle).strip().lower()
        if echelle_norm == "bmi" and "ENTITE_ORIGINE_PROCEDURE" in df.columns:
            bmi_filters = get_bmi_filters(code)
            entite_pej_val = str(bmi_filters.get("entite_pej", code)).upper()
            df = df[df["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.upper().str.contains(entite_pej_val, case=True, na=False, regex=False)].copy()
        elif echelle_norm != "bmi" and "ENTITE_ORIGINE_PROCEDURE" in df.columns:
            dept_codes = get_departements_pour_perimetre(echelle, code)
            if dept_codes and "FR" not in dept_codes:
                dept_extracted = df["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.extract(r'(\d+)')[0]
                df = df[dept_extracted.isin(dept_codes)].copy()

    if not df.empty and "DC_ID" in df.columns:
        if "DATE_REF" in df.columns:
            df = df.sort_values("DATE_REF", ascending=False)
            df = df[df["DC_ID"].isna() | ~df.duplicated(subset=["DC_ID"], keep="first")]
        else:
            df = df[df["DC_ID"].isna() | ~df.duplicated(subset=["DC_ID"], keep="first")]

    return df


def load_pa(
    root: Path,
    echelle: Optional[str] = None,
    code: Optional[str] = None,
    date_deb: Optional[Union[str, pd.Timestamp]] = None,
    date_fin: Optional[Union[str, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """
    Charge le classeur ODS des procédures administratives le plus récent
    (suivi_procedure_administrative_YYYYMMDD.ods dans sources/) et prépare
    la colonne DATE_REF.

    Si date_deb et date_fin sont fournis, filtre les lignes sur cette période.

    Localisation spatiale : ce classeur ne sert pas de référence pour placer
    une PA dans le PNF. Pour un critère géographique, s'appuyer sur les
    points de contrôle OSCEAN (load_point_ctrl) : effectifs et localisations
    des PA alignés sur les contrôles dont resultat == « Manquement »
    (voir ref/README_sources.md § 2.5bis).
    """
    global _SESSION_CACHE
    if _SESSION_CACHE["active"] and _SESSION_CACHE["pa"] is not None:
        df = _SESSION_CACHE["pa"].copy()
        if df.empty or "DATE_REF" not in df.columns:
            # Le préchargement a échoué (ex. odfpy absent) — retour propre sans crash
            return pd.DataFrame()
        if date_deb is not None and date_fin is not None:
            deb_ts = pd.to_datetime(date_deb)
            fin_ts = pd.to_datetime(date_fin)
            df = filtre_periode(df, "DATE_REF", deb_ts, fin_ts)
        if echelle is not None and code is not None:
            from core.common.utilitaires_metier import get_departements_pour_perimetre, get_bmi_filters
            echelle_norm = str(echelle).strip().lower()
            if echelle_norm == "bmi" and "ENTITE_ORIGINE_PROCEDURE" in df.columns:
                bmi_filters = get_bmi_filters(code)
                entite_pej_val = str(bmi_filters.get("entite_pej", code)).upper()
                df = df[df["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.upper().str.contains(entite_pej_val, case=True, na=False, regex=False)].copy()
            elif echelle_norm != "bmi" and "ENTITE_ORIGINE_PROCEDURE" in df.columns:
                dept_codes = get_departements_pour_perimetre(echelle, code)
                if dept_codes and "FR" not in dept_codes:
                    entity_sds = [f"SD{d}" for d in dept_codes]
                    pnf_mask = df["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.upper().str.contains(r'PNF|PARC|FORET', regex=True, na=False)
                    df = df[df["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.strip().isin(entity_sds) | pnf_mask].copy()
        return df

    sources = root / "data" / "sources"
    path = _find_latest_dated_file(
        sources, "suivi_procedure_administrative_", (".ods",)
    )
    sig = _compute_files_signature([path])
    is_national_full = (echelle is None or str(echelle).lower() == "national") and (code is None or code == "FR") and date_deb is None and date_fin is None
    if is_national_full:
        cached_df = _load_disk_cache(root, "pa_national", sig)
        if cached_df is not None:
            return cached_df.copy()

    if path in _PA_RAW_CACHE:
        df = _PA_RAW_CACHE[path].copy()
    else:
        raw_key = f"pa_raw_{path.stem}"
        cached_df = _load_disk_cache(root, raw_key, sig)
        if cached_df is not None:
            df = cached_df.copy()
        else:
            df = _read_spreadsheet(path)
            df.columns = pd.Index([str(c).strip().upper() for c in df.columns])
            df["DATE_CONTROLE"] = safe_to_datetime(df["DATE_CONTROLE"])
            df["DATE_DOSSIER"] = safe_to_datetime(df["DATE_DOSSIER"])
            df["DATE_REF"] = df["DATE_CONTROLE"].fillna(df["DATE_DOSSIER"])
            _save_disk_cache(root, raw_key, sig, df)
        _PA_RAW_CACHE[path] = df.copy()
        if is_national_full:
            _save_disk_cache(root, "pa_national", sig, df)
    if date_deb is not None and date_fin is not None:
        deb_ts = pd.to_datetime(date_deb)
        fin_ts = pd.to_datetime(date_fin)
        df = filtre_periode(df, "DATE_REF", deb_ts, fin_ts)
    return df


def load_rech_av(root: Path) -> pd.DataFrame:
    """Charge le fichier d'export de recherche avancée pour récupérer les mots-clés."""
    sources = root / "data" / "sources"
    try:
        path = _find_latest_dated_file(sources, "rech_av_", (".csv",))
        if not path:
            return pd.DataFrame(columns=["num_dossier", "mots_cles"])
            
        try:
            df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)
        except UnicodeDecodeError:
            df = pd.read_csv(path, sep=";", encoding="latin-1", dtype=str)
            
        import unicodedata
        def clean_col(c):
            return unicodedata.normalize('NFKD', str(c)).encode('ASCII', 'ignore').decode('ASCII').lower().strip()
            
        df.columns = [clean_col(c) for c in df.columns]
        
        col_id = next((c for c in df.columns if "num" in c and "dossier" in c), None)
        col_mots = next((c for c in df.columns if "mot" in c and "cl" in c), None)
        
        if col_id and col_mots:
            return df[[col_id, col_mots]].rename(columns={
                col_id: "num_dossier", 
                col_mots: "mots_cles"
            })
    except Exception as e:
        logger.warning("Lecture de rech_av_*.csv impossible : %s", e)
    return pd.DataFrame(columns=["num_dossier", "mots_cles"])


# ========================================================================================
# 3. REFERENTIELS GEOGRAPHIQUES ET ZONAGES SPATIAUX (PNF, TUB)
# ========================================================================================

def _load_pnf_from_127_communes_shp(root: Path) -> Optional[pd.DataFrame]:
    """
    Liste INSEE (+ nom) des communes PNF depuis
    ``127_communes_AOA_et_statuts_adhesion.shp``.
    """
    gdf = _load_pnf_127_communes_df(root)
    if gdf.empty:
        return None

    insee_col = _pick_gdf_column(
        gdf,
        ("INSEE_COM", "CODE_INSEE", "insee_comm", "INSEE", "code_insee", "INSEE_COM_M"),
    )
    if insee_col is None:
        raise KeyError(
            f"Aucune colonne INSEE reconnue dans {get_pnf_127_communes_aoa_shp_path(root)} "
            f"(colonnes : {list(gdf.columns)})."
        )
    nom_col = _pick_gdf_column(
        gdf,
        ("NOM_COM", "NOM", "nom_commune", "nom_commun", "LIBELLE", "libelle"),
    )

    insee_series = gdf[insee_col].map(_normalize_insee_code)
    out = pd.DataFrame({"CODE_INSEE": insee_series})
    if nom_col is not None:
        out["NOM"] = gdf[nom_col].astype(str).str.strip()
    out = out.dropna(subset=["CODE_INSEE"]).drop_duplicates(subset=["CODE_INSEE"]).reset_index(drop=True)
    return out if not out.empty else None


def _load_pnf_from_shp(root: Path) -> Optional[pd.DataFrame]:
    """
    Lit ref/programme/sig/communes_pnf/communes_pnf.shp et renvoie un DataFrame au format attendu
    par load_tub_pnf_codes / merge PNF (colonne CODE_INSEE, optionnellement NOM).

    Retourne None si le fichier est absent ; lève une erreur explicite si le fichier
    existe mais qu'aucune colonne INSEE n'est reconnue.
    """
    shp = ref_programme(root) / "sig" / "communes_pnf" / "communes_pnf.shp"
    if not shp.exists():
        return None

    gdf = read_vector_attributes(shp)
    if gdf.empty:
        return pd.DataFrame(columns=["CODE_INSEE"])

    insee_col = next(
        (
            c
            for c in (
                "INSEE_COM",
                "CODE_INSEE",
                "insee_comm",
                "INSEE",
                "code_insee",
                "INSEE_COM_M",
            )
            if c in gdf.columns
        ),
        None,
    )
    if insee_col is None:
        raise KeyError(
            f"Aucune colonne INSEE reconnue dans {shp} "
            f"(colonnes : {list(gdf.columns)} ; attendu p.ex. INSEE_COM ou CODE_INSEE)."
        )

    nom_col = next(
        (
            c
            for c in (
                "NOM_COM",
                "NOM",
                "nom_commune",
                "nom_commun",
                "LIBELLE",
                "libelle",
            )
            if c in gdf.columns
        ),
        None,
    )

    insee_series = extract_insee_code_series(gdf[insee_col])
    out = pd.DataFrame({"CODE_INSEE": insee_series})
    if nom_col is not None:
        out["NOM"] = series_as_python_str(gdf[nom_col]).map(str.strip)

    out = out.drop_duplicates(subset=["CODE_INSEE"]).reset_index(drop=True)
    out = out[out["CODE_INSEE"].notna()]
    out = out[out["CODE_INSEE"].ne("00000")]
    return out


def load_pnf(root: Path) -> pd.DataFrame:
    """
    Charge la liste des communes PNF (référentiel).

    Ordre de priorité :
    1. Shapefile ref/programme/sig/PNF/127_communes/127_communes_AOA_et_statuts_adhesion.shp ;
    2. Shapefile ref/programme/sig/communes_pnf/communes_pnf.shp ;
    3. Fichier communes_PNF.csv dans ref/programme/tables_reference ou data/sources/.
    """
    try:
        from_127 = _load_pnf_from_127_communes_shp(root)
    except KeyError:
        raise
    except Exception as e:
        path_127 = get_pnf_127_communes_aoa_shp_path(root)
        if path_127.exists():
            raise RuntimeError(f"Lecture du shapefile PNF 127 communes impossible ({path_127}) : {e}") from e
        from_127 = None

    if from_127 is not None and not from_127.empty:
        return from_127

    try:
        from_shp = _load_pnf_from_shp(root)
    except KeyError:
        raise
    except Exception as e:
        shp = ref_programme(root) / "sig" / "communes_pnf" / "communes_pnf.shp"
        if shp.exists():
            raise RuntimeError(f"Lecture du shapefile PNF impossible ({shp}) : {e}") from e
        from_shp = None

    if from_shp is not None and not from_shp.empty:
        return from_shp

    for path in (
        ref_programme(root) / "tables_reference" / "communes_PNF.csv",
        root / "data" / "sources" / "communes_PNF.csv",
    ):
        if path.exists():
            # index_col=False : pandas 3.x peut sinon prendre « NOM » comme index et décaler les colonnes.
            df = pd.read_csv(path, sep=",", dtype=str, index_col=False)
            df["CODE_INSEE"] = df["CODE_INSEE"].astype(str).str.zfill(5)
            return df

    raise FileNotFoundError(
        "Référentiel PNF introuvable : ni ref/programme/sig/PNF/127_communes/"
        "127_communes_AOA_et_statuts_adhesion.shp, ni ref/programme/sig/communes_pnf/"
        "communes_pnf.shp (non vide), ni communes_PNF.csv dans ref/programme/tables_reference "
        "ni data/sources/."
    )


def load_tub(root: Path) -> pd.DataFrame:
    """Charge la liste des communes TUB (référentiel)."""
    for path in (
        ref_programme(root) / "tables_reference" / "tub_communes.csv",
        root / "data" / "sources" / "tub_communes.csv",
    ):
        if path.exists():
            df = pd.read_csv(path, sep=";", dtype=str, encoding="latin-1")
            df["INSEE_COM"] = df["INSEE_COM"].astype(str).str.zfill(5)
            return df
    raise FileNotFoundError(
        "Aucun fichier tub_communes.csv trouvé dans ref/programme/tables_reference ni data/sources/."
    )


def load_zone_tub_gdf(root: Path):
    """
    Charge la couche polygonale de la zone TUB en combinant les sous-zones:
    - Zone a Risque
    - Zone Infectee
    - COMMUNE_InterdAgrain
    Recherche dans ref/programme/sig/TUB/ les shapefiles les plus récents.
    """
    if gpd is None:
        return None
    import glob
    tub_dir = ref_programme(root) / "sig" / "TUB"
    if not tub_dir.exists():
        return gpd.GeoDataFrame(columns=["geometry", "zone_type"], geometry="geometry", crs=None)
        
    gdfs = []

    def _load_newest(pattern, z_type):
        matches = glob.glob(str(tub_dir / "**" / pattern), recursive=True)
        if matches:
            matches.sort(reverse=True)
            gdf = gpd.read_file(matches[0])
            gdf["zone_type"] = z_type
            return gdf
        return None

    gdf_risque = _load_newest("Zone a Risque*.shp", "risque")
    if gdf_risque is not None: gdfs.append(gdf_risque)
        
    gdf_infectee = _load_newest("Zone Infectee*.shp", "infectee")
    if gdf_infectee is not None: gdfs.append(gdf_infectee)
        
    gdf_interd = _load_newest("COMMUNE_InterdAgrain*.shp", "interdiction")
    if gdf_interd is not None: gdfs.append(gdf_interd)

    if not gdfs:
        return gpd.GeoDataFrame(columns=["geometry", "zone_type"], geometry="geometry", crs=None)
        
    # S'assurer qu'ils ont le même CRS avant concaténation
    base_crs = gdfs[0].crs
    for i in range(1, len(gdfs)):
        if gdfs[i].crs != base_crs and base_crs is not None:
            gdfs[i] = gdfs[i].to_crs(base_crs)
            
    combined = pd.concat(gdfs, ignore_index=True)
    # Dissolve pour ne garder que l'enveloppe extérieure de chaque zone
    # et éviter que la carte Leaflet dessine toutes les limites internes
    return combined.dissolve(by="zone_type", as_index=False)


def tub_sig_union_membership_mask(
    df: pd.DataFrame,
    root: Path,
    *,
    log: Optional[logging.Logger] = None,
) -> pd.Series:
    """
    Pour chaque ligne avec coordonnées (x/y WGS84, inf_gps_*, ou geometry),
    indique si le point intersecte l'une des zones TUB (Risque, Infectée, Interdiction).
    Retourne une série booléenne alignée sur ``df.index``.
    """
    lg = log or logger
    if df is None or df.empty:
        return pd.Series(False, index=df.index if df is not None else pd.RangeIndex(0))

    tub_gdf = load_zone_tub_gdf(root)
    if tub_gdf is None or tub_gdf.empty:
        return pd.Series(False, index=df.index)

    gdf_pts = _dataframe_with_xy_geometry(df)
    if gdf_pts is None:
        return pd.Series(False, index=df.index)

    tub_u = _union_perimeter_geometry(tub_gdf)
    if tub_u is None:
        return pd.Series(False, index=df.index)

    ref_crs = tub_gdf.crs

    if gdf_pts.crs is None:
        gdf_pts = gdf_pts.set_crs(4326)
    if ref_crs is not None and gdf_pts.crs != ref_crs:
        gdf_pts = gdf_pts.to_crs(ref_crs)

    mask = gdf_pts.geometry.intersects(tub_u)
    return mask


def load_ref_themes_ctrl(root: Path) -> List[dict]:
    """
    Charge le référentiel des thèmes des contrôles.
    Retourne une liste de dictionnaires {"id": ..., "label": ..., "ordre": ...}
    triée par ordre. Si le fichier est absent ou invalide, retourne une liste vide.
    """
    path = ref_programme(root) / "tables_reference" / "ref_themes_ctrl.csv"
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
        if df.empty:
            return []
        # Colonnes attendues : id, label, ordre
        if "id" not in df.columns:
            return []
        out = []
        for _, row in df.iterrows():
            id_val = str(row.get("id", "")).strip()
            if not id_val:
                continue
            label_val = str(row.get("label", id_val)).strip()
            ordre_val = row.get("ordre", "999")
            try:
                ordre_int = int(ordre_val) if ordre_val else 999
            except (ValueError, TypeError):
                ordre_int = 999
            out.append({"id": id_val, "label": label_val, "ordre": ordre_int})
        out.sort(key=lambda x: x["ordre"])
        return out
    except Exception:
        return []


def load_tub_pnf_codes(root: Path) -> Tuple[set, set]:
    """
    Charge les référentiels TUB et PNF et retourne les ensembles de codes INSEE
    (tub_codes, pnf_codes) pour les agrégations par zone. Utile pour réutiliser
    la même logique dans plusieurs bilans.
    """
    tub = load_tub(root)
    pnf = load_pnf(root)
    return set(tub["INSEE_COM"].unique()), set(pnf["CODE_INSEE"].unique())


def get_pnf_coeur_shp_path(root: Path) -> Path:
    """Chemin du shapefile « cœur de parc » PNF (Parc national de forêts)."""
    return ref_programme(root) / "sig" / "PNF" / "coeur_pnforets" / "Coeur_data_gouv_PNForets.shp"


def get_pnf_aoa_shp_path(root: Path) -> Path:
    """Chemin du shapefile de l'aire d'adhésion PNF (millésime 2021)."""
    return ref_programme(root) / "sig" / "PNF" / "aoa_2021_pnforets" / "AOA_2021_PNForets.shp"


def get_pnf_127_communes_aoa_shp_path(root: Path) -> Path:
    """Communes PNF (127) : statut cœur / hors-cœur par commune (champ ``coeur``)."""
    return (
        ref_programme(root)
        / "sig"
        / "PNF"
        / "127_communes"
        / "127_communes_AOA_et_statuts_adhesion.shp"
    )


def _pnf_zone_from_coeur_value(value: object) -> str | None:
    """
    Statut commune dans le périmètre PNF (shapefile 127 communes ou CSV).

    - ``oui`` → cœur de parc ;
    - ``non``, vide ou null → aire d'adhésion (hors-cœur) : toute commune du
      périmètre qui n'est pas explicitement en cœur est hors-cœur.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Aire_adhesion_PNF"
    s = str(value).strip().lower()
    if not s or s in {"nan", "none", "<na>", "<na>"}:
        return "Aire_adhesion_PNF"
    if s == "oui":
        return "Coeur_PNF"
    if s == "non":
        return "Aire_adhesion_PNF"
    return "Aire_adhesion_PNF"


def _normalize_insee_code(raw: object) -> str | None:
    m = re.search(r"(\d{1,5})", str(raw or "").strip())
    if not m:
        return None
    code = m.group(1).zfill(5)
    if not re.fullmatch(r"\d{5}", code):
        return None
    return code


def _pick_gdf_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    lower_map = {str(c).lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return str(lower_map[cand.lower()])
    return None


def _load_pnf_127_communes_df(root: Path) -> pd.DataFrame:
    path = get_pnf_127_communes_aoa_shp_path(root)
    if not path.exists():
        return pd.DataFrame()
    try:
        return read_vector_attributes(path)
    except Exception as exc:
        raise RuntimeError(f"Lecture du shapefile PNF 127 communes impossible ({path}) : {exc}") from exc


def load_pnf_commune_zone_maps(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    """
    Cartes commune → zone PNF depuis ``127_communes_AOA_et_statuts_adhesion.shp``.

    Retourne (by_insee, by_commune_nom_lower). Repli sur communes_PNF.csv si le shapefile
    est absent.
    """
    gdf = _load_pnf_127_communes_df(root)
    if gdf.empty:
        by_insee = _load_pnf_commune_zone_by_insee_from_csv(root)
        return by_insee, {}

    insee_col = _pick_gdf_column(
        gdf,
        ("INSEE_COM", "CODE_INSEE", "insee_comm", "INSEE", "code_insee", "INSEE_COM_M"),
    )
    coeur_col = _pick_gdf_column(gdf, ("coeur", "Coeur", "COEUR"))
    nom_col = _pick_gdf_column(
        gdf,
        ("NOM_COM", "NOM", "nom_commune", "nom_commun", "LIBELLE", "libelle"),
    )
    if coeur_col is None:
        raise KeyError(
            f"Aucune colonne « coeur » reconnue dans {get_pnf_127_communes_aoa_shp_path(root)} "
            f"(colonnes : {list(gdf.columns)})."
        )

    by_insee: dict[str, str] = {}
    by_nom: dict[str, str] = {}
    for _, row in gdf.iterrows():
        zone = _pnf_zone_from_coeur_value(row.get(coeur_col))
        if zone is None:
            continue
        if insee_col is not None:
            code = _normalize_insee_code(row.get(insee_col))
            if code:
                by_insee[code] = zone
        if nom_col is not None:
            nom = str(row.get(nom_col, "")).strip().lower()
            if nom:
                by_nom[nom] = zone
    return by_insee, by_nom


def load_pnf_coeur_gdf(root: Path):
    """Charge la couche polygonale du cœur de parc. None si geopandas absent ou GeoDataFrame vide si fichier absent."""
    if gpd is None:
        return None
    path = get_pnf_coeur_shp_path(root)
    if not path.exists():
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=None)
    return gpd.read_file(path)


def load_pnf_aoa_gdf(root: Path):
    """Charge la couche polygonale de l'aire d'adhésion. None si geopandas absent ou GeoDataFrame vide si fichier absent."""
    if gpd is None:
        return None
    path = get_pnf_aoa_shp_path(root)
    if not path.exists():
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=None)
    return gpd.read_file(path)


def pnf_sig_union_membership_mask(
    df: pd.DataFrame,
    root: Path,
    *,
    log: Optional[logging.Logger] = None,
) -> pd.Series:
    """
    Pour chaque ligne avec coordonnées (x/y WGS84, inf_gps_*, ou geometry),
    indique si le point intersecte le cœur PNForêts et/ou l'aire d'adhésion SIG.

    Complète le filtre par liste de communes INSEE : une localisation peut être
    dans le parc sans que son code commune figure au référentiel tabulaire PNF.
    Retourne une série booléenne alignée sur ``df.index`` (False si SIG ou points absents).
    """
    lg = log or logger
    if df is None or df.empty:
        return pd.Series(False, index=df.index if df is not None else pd.RangeIndex(0))

    coeur = load_pnf_coeur_gdf(root)
    aoa = load_pnf_aoa_gdf(root)
    if (coeur is None or coeur.empty) and (aoa is None or aoa.empty):
        return pd.Series(False, index=df.index)

    gdf_pts = _dataframe_with_xy_geometry(df)
    if gdf_pts is None:
        return pd.Series(False, index=df.index)

    coeur_u = _union_perimeter_geometry(coeur)
    aoa_u = _union_perimeter_geometry(aoa)
    if coeur_u is None and aoa_u is None:
        return pd.Series(False, index=df.index)

    ref_crs = None
    if coeur_u is not None and not coeur.empty and coeur.crs is not None:
        ref_crs = coeur.crs
    if ref_crs is None and aoa_u is not None and not aoa.empty and aoa.crs is not None:
        ref_crs = aoa.crs

    if gdf_pts.crs is None:
        gdf_pts = gdf_pts.set_crs(4326)
    if ref_crs is not None and gdf_pts.crs != ref_crs:
        gdf_pts = gdf_pts.to_crs(ref_crs)

    geom = gdf_pts.geometry
    valid = geom.notna() & ~geom.is_empty

    in_coeur = pd.Series(False, index=gdf_pts.index)
    if coeur_u is not None:
        in_coeur = geom.within(coeur_u) | geom.intersects(coeur_u)

    in_aoa = pd.Series(False, index=gdf_pts.index)
    if aoa_u is not None:
        in_aoa = geom.within(aoa_u) | geom.intersects(aoa_u)

    inside = valid & (in_coeur | in_aoa)
    n_in = int(inside.sum())
    if n_in:
        lg.info(
            "Périmètre PNF SIG : %s localisations dans cœur ou aire d'adhésion (hors filtre INSEE seul).",
            n_in,
        )
    return inside.reindex(df.index, fill_value=False)


def _union_perimeter_geometry(gdf: gpd.GeoDataFrame):
    """Fusionne les géométries d'une couche périmètre (MultiPolygon / Polygon)."""
    if gdf.empty:
        return None
    geoms = gdf.geometry.dropna()
    if geoms.empty:
        return None
    try:
        return geoms.union_all()
    except Exception:
        try:
            return geoms.unary_union
        except Exception:
            from shapely.ops import unary_union

            return unary_union(list(geoms))


def enrich_with_pnforet_sig_zones(
    df: pd.DataFrame,
    root: Path,
    *,
    context: str = "jeu de données",
    log: Optional[logging.Logger] = None,
    out_col: str = "pnf_zone_sig",
) -> pd.DataFrame:
    """
    Ajoute une colonne (par défaut `pnf_zone_sig`) : « Coeur_PNF », « Aire_adhesion_PNF »,
    « Hors_perimetres_sig » selon la position des points par rapport aux couches
    `ref/programme/sig/PNF/coeur_pnforets/` et `ref/programme/sig/PNF/aoa_2021_pnforets/`.

    Nécessite des coordonnées (`x`/`y` en WGS84, ou `geometry`, ou GPS PVe).
    Si les shapefiles sont absents ou sans géométrie exploitable, retourne `df` inchangé.
    """
    lg = log or logger
    if df is None or df.empty:
        return df

    coeur = load_pnf_coeur_gdf(root)
    aoa = load_pnf_aoa_gdf(root)
    if (coeur is None or coeur.empty) and (aoa is None or aoa.empty):
        return df

    gdf_pts = _dataframe_with_xy_geometry(df)
    if gdf_pts is None:
        lg.info(
            "Périmètres PNF SIG : pas de coordonnées pour %s — %s non renseignée.",
            context,
            out_col,
        )
        return df

    coeur_u = _union_perimeter_geometry(coeur)
    aoa_u = _union_perimeter_geometry(aoa)
    if coeur_u is None and aoa_u is None:
        return df

    ref_crs = None
    if coeur_u is not None and not coeur.empty and coeur.crs is not None:
        ref_crs = coeur.crs
    if ref_crs is None and aoa_u is not None and not aoa.empty and aoa.crs is not None:
        ref_crs = aoa.crs

    if gdf_pts.crs is None:
        gdf_pts = gdf_pts.set_crs(4326)
    if ref_crs is not None and gdf_pts.crs != ref_crs:
        gdf_pts = gdf_pts.to_crs(ref_crs)

    geom = gdf_pts.geometry
    valid = geom.notna() & ~geom.is_empty

    in_coeur = pd.Series(False, index=gdf_pts.index)
    if coeur_u is not None:
        in_coeur = geom.within(coeur_u) | geom.intersects(coeur_u)

    in_aoa = pd.Series(False, index=gdf_pts.index)
    if aoa_u is not None:
        in_aoa = geom.within(aoa_u) | geom.intersects(aoa_u)

    zone = pd.Series(pd.NA, index=gdf_pts.index, dtype="string")
    zone = zone.mask(~valid, pd.NA)
    zone = zone.mask(valid & in_coeur, "Coeur_PNF")
    adhesion = valid & ~in_coeur & in_aoa
    zone = zone.mask(adhesion, "Aire_adhesion_PNF")
    hors = valid & ~in_coeur & ~in_aoa
    zone = zone.mask(hors, "Hors_perimetres_sig")

    out = df.copy()
    out[out_col] = zone.values
    n_tagged = int(zone.notna().sum())
    lg.info(
        "Périmètres PNF SIG : %s — %s lignes classées (%s).",
        context,
        n_tagged,
        out_col,
    )
    return out


def _coalesced_insee_for_pnf_overlay(df: pd.DataFrame) -> pd.Series:
    """Code INSEE normalisé (5 chiffres) par ligne — délègue à ``coalesced_insee_series``."""
    return coalesced_insee_series(df)


def _load_pnf_commune_zone_by_insee_from_csv(root: Path) -> dict[str, str]:
    """Source PNF basée sur le référentiel officiel."""
    path = ref_programme(root) / "tables_reference" / "communes_PNF.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str, index_col=False).fillna("")
    if "CODE_INSEE" not in df.columns:
        return {}
    out: dict[str, str] = {}
    for _, r in df.iterrows():
        code = _normalize_insee_code(r.get("CODE_INSEE"))
        if not code:
            continue
        coeur_val = r.get("Coeur", r.get("coeur", ""))
        zone = _pnf_zone_from_coeur_value(coeur_val)
        if zone is not None:
            out[code] = zone
            continue
        in_perimetre = str(r.get("perimetre_parc", "")).strip().lower() == "oui"
        if in_perimetre:
            out[code] = "Aire_adhesion_PNF"
    return out


def load_pnf_commune_zone_by_insee(root: Path) -> dict[str, str]:
    """
    {code INSEE} → « Coeur_PNF » ou « Aire_adhesion_PNF ».

    Source prioritaire : ``127_communes_AOA_et_statuts_adhesion.shp`` (champ ``coeur``).
    Repli : ``communes_PNF.csv``.
    """
    by_insee, _ = load_pnf_commune_zone_maps(root)
    return by_insee


def overlay_pnf_zone_from_communes_pnf_csv(
    df: pd.DataFrame,
    root: Path,
    *,
    out_col: str = "pnf_zone_sig",
    log: Optional[logging.Logger] = None,
) -> pd.DataFrame:
    """
    Recale ``pnf_zone_sig`` à partir de l'INSEE commune lorsque le référentiel PNF
    (shapefile 127 communes ou CSV) définit Cœur / Hors-cœur. Conserve la valeur SIG
    existante si aucune correspondance INSEE.
    """
    lg = log or logger
    if df is None or df.empty:
        return df
    zone_map = load_pnf_commune_zone_by_insee(root)
    if not zone_map:
        return df
    insee = _coalesced_insee_for_pnf_overlay(df)
    if insee.isna().all():
        return df
    mapped = insee.map(zone_map)
    has = mapped.notna()
    if not bool(has.any()):
        return df
    out = df.copy()
    if out_col not in out.columns:
        out[out_col] = pd.NA
        
    # On applique le fallback INSEE uniquement aux entités sans localisation spatiale précise
    needs_fallback = out[out_col].isna() | (out[out_col] == "Hors_perimetres_sig")
    to_update = has & needs_fallback
    
    if not bool(to_update.any()):
        return out
        
    out.loc[to_update, out_col] = mapped[to_update]
    n = int(to_update.sum())
    lg.info(
        "Réf. communes PNF (127 communes / CSV) : %s ligne(s) — zone INSEE (fallback) appliquée pour %s ligne(s) (%s).",
        len(df),
        n,
        out_col,
    )
    return out


# ========================================================================================
# 4. COMMUNES, CENTROIDES ET JOINTURES SPATIALES AUTOMATIQUES
# ========================================================================================

def load_communes_noms(root: Path) -> dict:
    """
    Charge la table de correspondance code INSEE → nom de commune.

    Source : ref/programme/sig/communes_21/communes.csv (INSEE_COM, NOM_COM).
    Retourne un dictionnaire {code_insee_5chars: nom_commune}.
    Si le fichier est absent, retourne un dict vide (les PDF afficheront le code).
    """
    path = ref_programme(root) / "sig" / "communes_21" / "communes.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path, sep=";", dtype=str)
    # Colonnes possibles : première ligne = en-tête type "INSEE_COM,C,5" et "NOM_COM,C,50"
    code_col = next((c for c in df.columns if c.strip().startswith("INSEE_COM")), None)
    nom_col = next((c for c in df.columns if c.strip().startswith("NOM_COM")), None)
    if code_col is None or nom_col is None:
        code_col, nom_col = df.columns[0], df.columns[1]
    df[code_col] = df[code_col].astype(str).str.strip().str.zfill(5)
    return dict(zip(df[code_col], df[nom_col].astype(str).str.strip()))


def _load_communes_21_gdf(root: Path) -> gpd.GeoDataFrame:
    """
    Charge la couche des communes 21 et harmonise les colonnes de sortie:
    - insee_comm (code INSEE sur 5 caractères)
    - nom_commune (nom de la commune)
    """
    shp_path = ref_programme(root) / "sig" / "communes_21" / "communes.shp"
    if not shp_path.exists():
        raise FileNotFoundError(
            f"Le shapefile des communes est introuvable : {shp_path}"
        )

    gdf = gpd.read_file(shp_path)
    if gdf.empty:
        return gpd.GeoDataFrame(columns=["insee_comm", "nom_commune", "geometry"], geometry="geometry", crs=gdf.crs)

    insee_col = next(
        (c for c in ("INSEE_COM", "insee_comm", "INSEE", "code_insee", "CODE_INSEE") if c in gdf.columns),
        None,
    )
    nom_col = next(
        (c for c in ("NOM_COM", "nom_commune", "nom_commun", "NOM_COMMUNE", "NOM") if c in gdf.columns),
        None,
    )
    if insee_col is None or nom_col is None:
        raise KeyError(
            "Colonnes INSEE/nom introuvables dans communes.shp "
            "(attendues: INSEE_COM et NOM_COM ou équivalents)."
        )
    if "geometry" not in gdf.columns:
        raise KeyError("Aucune colonne 'geometry' dans la couche communes.shp.")

    out = gdf[[insee_col, nom_col, "geometry"]].copy()
    out = out.rename(columns={insee_col: "insee_comm", nom_col: "nom_commune"})
    out["insee_comm"] = out["insee_comm"].astype(str).str.strip().str.zfill(5)
    out["nom_commune"] = out["nom_commune"].astype(str).str.strip()
    out = out.dropna(subset=["geometry"])
    return gpd.GeoDataFrame(out, geometry="geometry", crs=gdf.crs)


def enrich_with_commune_from_geometry(
    df: Union[pd.DataFrame, gpd.GeoDataFrame],
    root: Path,
    geometry_col: str = "geometry",
    insee_col: str = "insee_comm",
    nom_col: str = "nom_commune",
    fill_only_missing: bool = True,
) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
    """
    Enrichit un jeu d'entités avec le code INSEE et le nom de commune via jointure spatiale.

    Règles:
    - si `insee_col`/`nom_col` existent déjà et `fill_only_missing=True`, seules les valeurs
      manquantes sont complétées;
    - sinon, les colonnes sont (re)calculées à partir de `ref/programme/sig/communes_21/communes.shp`.
    """
    if geometry_col not in df.columns:
        raise KeyError(
            f"La colonne de géométrie '{geometry_col}' est absente des entités à enrichir."
        )

    communes = _load_communes_21_gdf(root)
    if communes.empty:
        enriched = df.copy()
        if insee_col not in enriched.columns:
            enriched[insee_col] = pd.NA
        if nom_col not in enriched.columns:
            enriched[nom_col] = pd.NA
        return enriched

    left = df.copy()
    if insee_col not in left.columns:
        left[insee_col] = pd.NA
    if nom_col not in left.columns:
        left[nom_col] = pd.NA

    if fill_only_missing:
        missing_mask = left[insee_col].map(_insee_cell_missing)
        if not missing_mask.any():
            left[insee_col] = left[insee_col].astype("string").str.strip().str.zfill(5)
            return left
        sub_df = left.loc[missing_mask].copy()
    else:
        missing_mask = pd.Series([True] * len(left), index=left.index)
        sub_df = left.copy()

    # Convertit en GeoDataFrame uniquement les lignes sans INSEE
    gdf_sub = sub_df if isinstance(sub_df, gpd.GeoDataFrame) else gpd.GeoDataFrame(sub_df, geometry=geometry_col)
    if gdf_sub.crs is None:
        gdf_sub = gdf_sub.set_crs(epsg=4326)
    if communes.crs is None:
        communes = communes.set_crs(gdf_sub.crs)
    elif gdf_sub.crs != communes.crs:
        gdf_sub = gdf_sub.to_crs(communes.crs)

    sub_left = gdf_sub.copy()
    sub_left["_row_id_tmp"] = range(len(sub_left))

    join_left = sub_left.drop(columns=[insee_col, nom_col], errors="ignore")
    joined = gpd.sjoin(
        join_left,
        communes[["insee_comm", "nom_commune", "geometry"]],
        how="left",
        predicate="within",
    )
    joined = joined.sort_values("_row_id_tmp").drop_duplicates(subset=["_row_id_tmp"], keep="first")
    joined.index = sub_df.index

    insee_join = joined["insee_comm"] if "insee_comm" in joined.columns else pd.Series(index=sub_df.index, dtype="object")
    nom_join = joined["nom_commune"] if "nom_commune" in joined.columns else pd.Series(index=sub_df.index, dtype="object")

    left.loc[missing_mask, insee_col] = insee_join
    left.loc[missing_mask, nom_col] = nom_join

    left[insee_col] = left[insee_col].astype("string").str.strip().str.zfill(5)
    left[nom_col] = left[nom_col].astype("string").str.strip()

    if isinstance(df, gpd.GeoDataFrame):
        return gpd.GeoDataFrame(left, geometry=geometry_col, crs=df.crs)
    return left


def _insee_cell_missing(v) -> bool:
    """True si la valeur n'est pas un code INSEE communal exploitable (5 chiffres)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return True
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "<na>"):
        return True
    digits = re.sub(r"\D", "", s)
    if len(digits) < 5:
        return True
    if digits == "00000":
        return True
    return False


def _first_insee_column(df: pd.DataFrame) -> Optional[str]:
    for c in _INSEE_COL_PRIORITY:
        if c in df.columns:
            return c
    return None


def _all_insee_filled(df: pd.DataFrame, col: str) -> bool:
    if col not in df.columns or df.empty:
        return False
    return not df[col].map(_insee_cell_missing).any()


def _dataframe_with_xy_geometry(df: pd.DataFrame) -> Optional[gpd.GeoDataFrame]:
    """Construit un GeoDataFrame (WGS84) depuis x/y ou lat/lon PVe si possible."""
    if "geometry" in df.columns:
        try:
            gdf = gpd.GeoDataFrame(df.copy(), geometry="geometry", crs=None)
            if gdf.crs is None:
                gdf = gdf.set_crs(epsg=4326)
            return gdf
        except Exception:
            return None

    if "x" in df.columns and "y" in df.columns:
        x = pd.to_numeric(df["x"], errors="coerce")
        y = pd.to_numeric(df["y"], errors="coerce")
        if x.notna().any() and y.notna().any():
            return gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(x, y), crs="EPSG:4326")

    if "x_faits" in df.columns and "y_faits" in df.columns:
        x = pd.to_numeric(df["x_faits"], errors="coerce")
        y = pd.to_numeric(df["y_faits"], errors="coerce")
        if x.notna().any() and y.notna().any():
            return gpd.GeoDataFrame(
                df.copy(), geometry=gpd.points_from_xy(x, y), crs="EPSG:4326"
            )

    if "inf_gps_lat" in df.columns and "inf_gps_long" in df.columns:
        lat = pd.to_numeric(df["inf_gps_lat"], errors="coerce")
        lon = pd.to_numeric(df["inf_gps_long"], errors="coerce")
        if lat.notna().any() and lon.notna().any():
            return gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(lon, lat), crs="EPSG:4326")

    return None


def ensure_insee_from_communes_shp(
    df: pd.DataFrame,
    root: Path,
    *,
    context: str = "jeu de données",
    log: Optional[logging.Logger] = None,
) -> pd.DataFrame:
    """
    Garantit une colonne `insee_comm` (et `nom_commune`) pour les analyses par commune
    (PNF, TUB, etc.) : normalise un code INSEE déjà présent ou complète via jointure spatiale
    avec `ref/programme/sig/communes_21/communes.shp`.

    Les points de contrôle sans géométrie mais avec `x`/`y` sont convertis en points WGS84.
    Les PEJ peuvent utiliser `x_faits` / `y_faits` (jointure FAITS) si aucun code INSEE n'est renseigné.
    Les PVe peuvent utiliser `inf_gps_lat` / `inf_gps_long` si `INF-INSEE` est absent ou incomplet.
    """
    lg = log or logger
    if df is None or df.empty:
        return df

    out = df.copy()
    if "insee_comm" not in out.columns:
        alt = _first_insee_column(out)
        if alt:
            out["insee_comm"] = out[alt]
        else:
            out["insee_comm"] = pd.NA

    if _all_insee_filled(out, "insee_comm"):
        out["insee_comm"] = (
            out["insee_comm"]
            .astype(str)
            .str.extract(r"(\d{1,5})", expand=False)
            .fillna("")
            .str.zfill(5)
        )
        out.loc[out["insee_comm"].isin(("", "00000")), "insee_comm"] = pd.NA
        return out

    gdf_try = _dataframe_with_xy_geometry(out)
    if gdf_try is None:
        lg.warning(
            "Impossible d'enrichir le code INSEE (%s) : pas de géométrie ni de x/y ou GPS exploitables.",
            context,
        )
        return out

    n_before = int(out["insee_comm"].map(_insee_cell_missing).sum())

    try:
        enriched = enrich_with_commune_from_geometry(
            gdf_try,
            root,
            geometry_col="geometry",
            insee_col="insee_comm",
            nom_col="nom_commune",
            fill_only_missing=True,
        )
    except FileNotFoundError as e:
        lg.warning("Couche communes indisponible pour %s : %s", context, e)
        return out
    except Exception as e:  # pragma: no cover - dépend des données SIG
        lg.warning("Échec jointure spatiale communes (%s) : %s", context, e)
        return out

    if isinstance(enriched, gpd.GeoDataFrame):
        drop_geom = enriched.drop(columns=["geometry"], errors="ignore")
        out = pd.DataFrame(drop_geom)
    else:
        out = enriched.drop(columns=["geometry"], errors="ignore") if "geometry" in enriched.columns else enriched

    n_after = int(out["insee_comm"].map(_insee_cell_missing).sum()) if "insee_comm" in out.columns else n_before
    lg.info(
        "Communes (shp) : %s — lignes sans INSEE : %s -> %s (jointure spatiale).",
        context,
        n_before,
        n_after,
    )
    return out


def load_communes_centroides(root: Path) -> pd.DataFrame:
    """
    Charge la table des communes de France avec centroïdes et renvoie un
    DataFrame minimal (code_insee, lat, lon) pour les jointures.

    Source par défaut : ref/programme/sig/communes-france-2025.csv
    - code_insee : code INSEE commune (5 caractères, zfill(5))
    - lat / lon : coordonnées du centroïde (colonnes latitude_centre / longitude_centre)
    """
    ref_dir = ref_programme(root) / "sig"
    csv_path = ref_dir / "communes-france-2025.csv"

    if csv_path.exists():
        df = pd.read_csv(csv_path, sep=",", dtype=str)
        # Harmonisation du code INSEE
        insee_col = None
        for cand in ["code_insee", "CODE_INSEE", "insee"]:
            if cand in df.columns:
                insee_col = cand
                break
        if insee_col is None:
            raise KeyError(
                "Aucune colonne de code INSEE trouvée dans communes-france-2025.csv "
                "(attendu: code_insee / CODE_INSEE / insee)"
            )

        lat_col = None
        lon_col = None
        for cand in ["latitude_centre", "LATITUDE_CENTRE", "lat_centre"]:
            if cand in df.columns:
                lat_col = cand
                break
        for cand in ["longitude_centre", "LONGITUDE_CENTRE", "lon_centre"]:
            if cand in df.columns:
                lon_col = cand
                break

        if lat_col is None or lon_col is None:
            raise KeyError(
                "Colonnes de centroïdes manquantes dans communes-france-2025.csv "
                "(attendu: latitude_centre / longitude_centre ou équivalents)"
            )

        out = pd.DataFrame(
            {
                "code_insee": df[insee_col].astype(str).str.zfill(5),
                "lat": pd.to_numeric(df[lat_col], errors="coerce"),
                "lon": pd.to_numeric(df[lon_col], errors="coerce"),
            }
        )
        # On élimine les lignes sans coordonnées valides
        out = out.dropna(subset=["lat", "lon"])
        return out

    # Fallback possible : shapefile / gpkg de communes avec géométrie, si disponible.
    # On extrait alors le centroïde de chaque polygone.
    for base_name in ["communes-france-2025", "communes_france_2025", "communes_21/communes"]:
        for ext in (".gpkg", ".shp"):
            vec_path = ref_dir / f"{base_name}{ext}"
            if vec_path.exists():
                try:
                    import geopandas as gpd
                    if gpd is not None:
                        gdf = gpd.read_file(vec_path)
                        insee_col = next((c for c in ["code_insee", "CODE_INSEE", "insee", "INSEE_COM"] if c in gdf.columns), None)
                        if insee_col is None:
                            raise KeyError(f"Aucune colonne de code INSEE trouvée dans {vec_path}")
                        if "geometry" not in gdf.columns:
                            raise KeyError(f"Aucune colonne 'geometry' dans {vec_path}")
                        gdf = gdf.set_geometry("geometry")
                        if gdf.crs is None:
                            gdf.crs = "EPSG:2154"
                        # Calcul du centroïde en projection métrique (EPSG:2154) pour éviter l'avertissement géométrique et garantir la précision
                        gdf_proj = gdf.to_crs("EPSG:2154") if (hasattr(gdf.crs, "is_geographic") and gdf.crs.is_geographic) else gdf
                        centroids = gdf_proj.geometry.centroid.to_crs("EPSG:4326")
                        out = pd.DataFrame({"code_insee": gdf[insee_col].astype(str).str.zfill(5), "lat": centroids.y, "lon": centroids.x})
                        return out.dropna(subset=["lat", "lon"])
                except Exception:
                    pass

                # Fallback OGR
                from osgeo import ogr, osr
                ds = ogr.Open(str(vec_path))
                if ds:
                    layer = ds.GetLayer()
                    spatial_ref = layer.GetSpatialRef()
                    target_srs = osr.SpatialReference()
                    target_srs.ImportFromEPSG(4326)
                    target_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
                    transform = None
                    if spatial_ref and not spatial_ref.IsSame(target_srs):
                        transform = osr.CoordinateTransformation(spatial_ref, target_srs)
                        
                    layer_def = layer.GetLayerDefn()
                    insee_field_idx = -1
                    for cand in ["code_insee", "CODE_INSEE", "insee", "INSEE_COM"]:
                        idx = layer_def.GetFieldIndex(cand)
                        if idx != -1:
                            insee_field_idx = idx
                            break
                    if insee_field_idx != -1:
                        data = []
                        for feature in layer:
                            geom = feature.GetGeometryRef()
                            if geom:
                                centroid = geom.Centroid()
                                if centroid:
                                    if transform:
                                        centroid.Transform(transform)
                                    code_insee = feature.GetFieldAsString(insee_field_idx)
                                    data.append({"code_insee": str(code_insee).zfill(5), "lat": centroid.GetY(), "lon": centroid.GetX()})
                        if data:
                            out = pd.DataFrame(data)
                            return out.dropna(subset=["lat", "lon"])

    raise FileNotFoundError(
        "Impossible de trouver une table de centroïdes communes : "
        "ni ref/programme/sig/communes-france-2025.csv ni shapefile/GeoPackage équivalent."
    )


@lru_cache(maxsize=4)
def _get_communes_centroids_dicts_cached(root_str: Optional[str]) -> tuple[dict[str, float], dict[str, float]]:
    root = Path(root_str) if root_str else None
    df = load_communes_centroides(root=root)
    dict_x = dict(zip(df["code_insee"], df["lon"].astype(float)))
    dict_y = dict(zip(df["code_insee"], df["lat"].astype(float)))
    return dict_x, dict_y


def get_communes_centroids_dicts(root: Optional[Path] = None) -> tuple[dict[str, float], dict[str, float]]:
    """
    Renvoie un tuple (dict_lon, dict_lat) indexé par code_insee (5 caractères)
    mis en cache mémoire pour le centrage ultra-rapide des entités orphelines.
    """
    root_str = str(root.resolve()) if root else None
    return _get_communes_centroids_dicts_cached(root_str)



# ========================================================================================
# 5. REFERENTIELS D'INFRACTIONS (NOMENCLATURE NATINF)
# ========================================================================================

def load_natinf_ref(root: Path) -> pd.DataFrame:
    """Charge le référentiel NATINF pour libeller les exports."""
    for path in (
        ref_programme(root) / "tables_reference" / "liste_natinf.csv",
        ref_programme(root) / "tables_reference" / "liste-natinf-avril2023.csv",
        root / "data" / "sources" / "liste_natinf.csv",
        root / "data" / "sources" / "liste-natinf-avril2023.csv",
    ):
            if not path.exists():
                continue
            try:
                raw = path.read_text(encoding="utf-8", errors="ignore")
                sep = ";" if ";" in raw.split("\n")[0] else ","
                df = pd.read_csv(path, sep=sep, dtype=str, encoding="utf-8", on_bad_lines="skip")
                for c in ("Numéro NATINF", "numero_natinf", "NATINF", "natinf"):
                    if c in df.columns:
                        df = df.rename(columns={c: "numero_natinf"})
                        break
                if "numero_natinf" not in df.columns:
                    continue
                # Colonnes spécifiques du fichier standard OFB :
                #   - « Nature de l'infraction » (ex. Délit, Contravention de classe 5)
                #   - « Qualification de l'infraction » (nom de l'infraction)
                nature_col = None
                qualif_col = None
                for c in df.columns:
                    cl = c.lower()
                    if c == "numero_natinf":
                        continue
                    if "nature de l'infraction" in cl:
                        nature_col = c
                    elif "qualification de l'infraction" in cl:
                        qualif_col = c
                # Renommer d'abord les colonnes détaillées (avant tout autre rename)
                if nature_col:
                    df = df.rename(columns={nature_col: "nature_infraction"})
                if qualif_col:
                    df = df.rename(columns={qualif_col: "qualification_infraction"})
                # Fallback libelle_natinf pour les usages existants : privilégier la qualification
                lib_col = None
                if "qualification_infraction" in df.columns:
                    df["libelle_natinf"] = df["qualification_infraction"].fillna("")
                else:
                    for c in df.columns:
                        if c == "numero_natinf":
                            continue
                        if "nature" in c.lower() or "infraction" in c.lower():
                            lib_col = c
                            break
                    if lib_col:
                        df = df.rename(columns={lib_col: "libelle_natinf"})
                if "libelle_natinf" not in df.columns:
                    df["libelle_natinf"] = ""
                out_cols = ["numero_natinf", "libelle_natinf"]
                if "nature_infraction" in df.columns:
                    out_cols.append("nature_infraction")
                if "qualification_infraction" in df.columns:
                    out_cols.append("qualification_infraction")
                return df[out_cols].drop_duplicates()
            except Exception:
                continue
    return pd.DataFrame(columns=["numero_natinf", "libelle_natinf"])


def load_concordance_natinf_snc(root: Path) -> pd.DataFrame:
    """
    Charge la table de concordance des NATINF pour la source PVe :
    (numero_natinf -> domaine_snc, theme_snc, action_snc).
    Fichier recherché en priorité dans ref/programme/tables_reference/concordance_natinf_snc.csv.
    """
    for path in (
        ref_programme(root) / "tables_reference" / "concordance_natinf_snc.csv",
        ref_programme(root) / "concordance_natinf_snc.csv",
        root / "data" / "ref" / "concordance_natinf_snc.csv",
    ):
        if not path.exists():
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
            sep = ";" if ";" in raw.split("\n")[0] else ","
            df = pd.read_csv(path, sep=sep, dtype=str, encoding="utf-8", on_bad_lines="skip")
            if "numero_natinf" in df.columns:
                df["numero_natinf"] = df["numero_natinf"].astype(str).str.strip().str.lstrip("0")
                return df
        except Exception:
            continue
    return pd.DataFrame(columns=["numero_natinf", "libelle_natinf", "domaine_snc", "theme_snc", "action_snc", "statut"])



def enrich_pve_positions_from_pnf_commune_centroids(
    root: Path,
    df: pd.DataFrame,
    *,
    log: Optional[logging.Logger] = None,
) -> pd.DataFrame:
    """
    Attache des coordonnées WGS84 fiables aux PVe : jointure ``INF-INSEE`` avec
    ``ref/programme/sig/communes_pnf/communes_PNF_centroides.shp`` (colonnes ``long_centr`` /
    ``lat_centro`` en degrés).

    Les coordonnées ``x`` (longitude) et ``y`` (latitude) sont renseignées ou
    écrasées pour les lignes appariées, afin d'aligner la localisation sur le
    centroïde communal du périmètre PNF (cohérent avec les masques SIG et la liste
    INSEE du référentiel).
    """
    lg = log or logger
    if df is None or df.empty or "INF-INSEE" not in df.columns:
        return df

    shp = ref_programme(root) / "sig" / "communes_pnf" / "communes_PNF_centroides.shp"
    if not shp.exists():
        lg.debug(
            "Centroïdes communes PNF absents (%s) — coordonnées PVe non dérivées du référentiel.",
            shp,
        )
        return df

    try:
        cen = gpd.read_file(shp)
    except Exception as e:
        lg.warning("Lecture centroïdes PNF impossible (%s) : %s", shp, e)
        return df

    if cen.empty or "INSEE_COM" not in cen.columns:
        return df

    lon_col = "long_centr" if "long_centr" in cen.columns else None
    lat_col = "lat_centro" if "lat_centro" in cen.columns else None
    if lon_col is None or lat_col is None:
        lg.warning(
            "Shapefile centroïdes PNF : colonnes long_centr / lat_centro introuvables."
        )
        return df

    cen_small = cen[["INSEE_COM", lon_col, lat_col]].copy()
    cen_small["INSEE_COM"] = (
        cen_small["INSEE_COM"]
        .astype(str)
        .str.extract(r"(\d{1,5})", expand=False)
        .fillna("")
        .str.zfill(5)
    )
    cen_small = cen_small.drop_duplicates(subset=["INSEE_COM"], keep="first")
    cen_small = cen_small.rename(columns={lon_col: "_lon_cent", lat_col: "_lat_cent"})

    out = df.copy()
    out["_insee_pve"] = (
        out["INF-INSEE"]
        .astype(str)
        .str.extract(r"(\d{1,5})", expand=False)
        .fillna("")
        .str.zfill(5)
    )
    merged = out.merge(cen_small, left_on="_insee_pve", right_on="INSEE_COM", how="left")
    ok = merged["_lon_cent"].notna() & merged["_lat_cent"].notna()
    n = int(ok.sum())
    if n:
        lon = pd.to_numeric(merged.loc[ok, "_lon_cent"], errors="coerce")
        lat = pd.to_numeric(merged.loc[ok, "_lat_cent"], errors="coerce")
        # Stats_PVe en dtype=str / StringDtype : convertir les colonnes coords en float
        # avant assignation (sinon TypeError sur inf_gps_*).
        for col in ("x", "y", "inf_gps_long", "inf_gps_lat"):
            if col in merged.columns:
                merged[col] = pd.to_numeric(merged[col], errors="coerce")
            else:
                merged[col] = pd.Series(float("nan"), index=merged.index, dtype="float64")
        merged.loc[ok, "x"] = lon
        merged.loc[ok, "y"] = lat
        # Compatibilité chemins qui lisent encore le couple GPS PVe
        merged.loc[ok, "inf_gps_long"] = lon
        merged.loc[ok, "inf_gps_lat"] = lat
        lg.info(
            "PVe : %s ligne(s) géolocalisées au centroïde commune PNF (jointure INF-INSEE).",
            n,
        )
    drop_cols = [c for c in ("_insee_pve", "INSEE_COM", "_lon_cent", "_lat_cent") if c in merged.columns]
    merged = merged.drop(columns=drop_cols, errors="ignore")
    return merged


def load_pve(
    root: Path,
    echelle: Optional[str] = None,
    code: Optional[str] = None,
    date_deb: Optional[Union[str, pd.Timestamp]] = None,
    date_fin: Optional[Union[str, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """
    Charge le tableau Stats_PVe_OFB (format .csv, .ods ou .xlsx) et homogénéise
    les principales colonnes utilisées dans les analyses/cartes.

    Le fichier est recherché dynamiquement dans sources/ : on prend le plus récent
    parmi les fichiers dont le nom commence par "Stats_PVe_OFB"
    (extensions .csv, .ods ou .xlsx),
    en se basant sur la date de modification du fichier.

    Colonnes normalisées :
      * INF-INSEE : chaîne à 5 chiffres (zfill(5)) si présente
      * INF-DEPARTEMENT / INF-DEPART : alias réciproques
      * INF-DATE-MIF : datetime (date de mise en force, jour/mois/année)

    Si dept_code et/ou date_deb/date_fin sont fournis, filtre les lignes en conséquence.

    **Période :** le filtre sur ``INF-DATE-MIF`` réduit le nombre de PVe par rapport à une
    simple jointure spatiale (ex. QGIS Excel × centroïdes PNF sans critère de date) : seules
    les infractions dont la date de mise en force tombe dans l'intervalle du bilan sont comptées.
    """
    global _SESSION_CACHE
    if _SESSION_CACHE["active"] and _SESSION_CACHE["pve"] is not None:
        df = _SESSION_CACHE["pve"].copy()

        if echelle is not None and code is not None:
            from core.common.utilitaires_metier import get_departements_pour_perimetre, get_bmi_filters
            echelle_norm = str(echelle).strip().lower()
            if echelle_norm == "bmi" and "nom_site" in df.columns:
                bmi_filters = get_bmi_filters(code)
                nom_site_val = str(bmi_filters.get("nom_site_pve", "BMI")).upper()
                import re
                def clean_str(s):
                    if pd.isna(s): return ""
                    s = str(s).upper()
                    s = s.replace("Ô", "O").replace("ô", "o").replace("-", " ")
                    return re.sub(r'\s+', ' ', s).strip()
                
                keywords_pve_yaml = bmi_filters.get("keywords_pve", [])
                if keywords_pve_yaml:
                    keywords_to_find = [str(k).upper() for k in keywords_pve_yaml]
                else:
                    nom_site_val_clean = clean_str(nom_site_val)
                    keywords_to_find = [w for w in nom_site_val_clean.split() if w not in ["POLE", "DE", "ET", "LA", "LE", "DU", "DES"]]
                
                nom_site_col = df["nom_site"].apply(clean_str)
                mask = nom_site_col.apply(lambda x: all(k in x for k in keywords_to_find))
                df = df[mask].copy()
            elif echelle_norm != "bmi":
                dept_codes = get_departements_pour_perimetre(echelle, code)
                dept_col = "INF-DEPART" if "INF-DEPART" in df.columns else "INF-DEPARTEMENT"
                if dept_col in df.columns and dept_codes and "FR" not in dept_codes:
                    df = df[df[dept_col].astype(str).str.strip().isin(dept_codes)].copy()
        
        date_col = "INF-DATE-MIF" if "INF-DATE-MIF" in df.columns else ("INF-DATE-INTG" if "INF-DATE-INTG" in df.columns else None)
        if date_deb is not None and date_fin is not None and date_col is not None:
            deb_ts = pd.to_datetime(date_deb)
            fin_ts = pd.to_datetime(date_fin)
            df = filtre_periode(df, date_col, deb_ts, fin_ts)

        return df

    sources = root / "data" / "sources"
    if not sources.exists():
        raise FileNotFoundError(f"Le dossier sources n'existe pas : {sources}")

    candidates: List[Path] = []
    for ext in (".csv", ".ods", ".xlsx"):
        candidates.extend(sources.glob(f"Stats_PVe_OFB*{ext}"))
    if not candidates:
        raise FileNotFoundError(
            f"Aucun fichier Stats_PVe_OFB*.csv, *.ods ou *.xlsx trouvé dans {sources}."
        )
    # Fichier le plus récent (date de modification)
    path = max(candidates, key=lambda p: p.stat().st_mtime)

    sig = _compute_files_signature([path])
    is_national_full = (echelle is None or str(echelle).lower() == "national") and (code is None or code == "FR") and date_deb is None and date_fin is None
    if is_national_full:
        cached_df = _load_disk_cache(root, "pve_national", sig)
        if cached_df is not None:
            return cached_df.copy()

    if path in _PVE_RAW_CACHE:
        df = _PVE_RAW_CACHE[path].copy()
    else:
        raw_key = f"pve_raw_{path.stem}"
        cached_df = _load_disk_cache(root, raw_key, sig)
        if cached_df is not None:
            df = cached_df.copy()
        else:
            suffix = path.suffix.lower()
            if suffix == ".csv":
                df = pd.read_csv(path, sep=";", dtype=str, encoding="latin1")
            elif suffix == ".ods":
                df = _read_spreadsheet(path)
            else:
                # .xlsx : moteur openpyxl requis côté environnement Python
                df = pd.read_excel(path, dtype=str, engine="openpyxl")

            # Normalisation du code commune
            if "INF-INSEE" in df.columns:
                df["INF-INSEE"] = (
                    df["INF-INSEE"]
                    .astype(str)
                    .str.extract(r"(\d{1,5})", expand=False)
                    .fillna("")
                    .str.zfill(5)
                )

            # Alias de département INF-DEPART / INF-DEPARTEMENT
            if "INF-DEPARTEMENT" in df.columns and "INF-DEPART" not in df.columns:
                df["INF-DEPART"] = df["INF-DEPARTEMENT"]
            elif "INF-DEPART" in df.columns and "INF-DEPARTEMENT" not in df.columns:
                df["INF-DEPARTEMENT"] = df["INF-DEPART"]

            # Alias UNITE_libelle
            unite_col = next((c for c in df.columns if str(c).upper() in ("UNITE_LIBELLE", "UNITE_LIBEL", "UNITE_LIB", "UNITE")), None)
            if unite_col and "UNITE_libelle" not in df.columns:
                df["UNITE_libelle"] = df[unite_col]
            if "UNITE_libelle" in df.columns and "unite_libelle" not in df.columns:
                df["unite_libelle"] = df["UNITE_libelle"]

            # Traitement et déduplication des doublons sur INF-ID
            if "INF-ID" in df.columns:
                nb_dups = int(df["INF-ID"].duplicated().sum())
                if nb_dups > 0:
                    pct_dups = (nb_dups / max(1, len(df))) * 100
                    logger.warning(
                        "PVe : %d doublon(s) détecté(s) sur INF-ID (%.2f%% des lignes). Déduplication automatique sur INF-ID.",
                        nb_dups,
                        pct_dups,
                    )
                    df = df.drop_duplicates(subset=["INF-ID"], keep="first").copy()

            # Date de mise en force (MIF)
            if "INF-DATE-MIF" in df.columns:
                df["INF-DATE-MIF"] = safe_to_datetime(df["INF-DATE-MIF"])
            if "INF-DATE-INTG" in df.columns:
                df["INF-DATE-INTG"] = safe_to_datetime(df["INF-DATE-INTG"])
                
            # Jointure avec la table de concordance NATINF -> Domaine / Thème / Action SNC
            try:
                df_conc = load_concordance_natinf_snc(root)
                if not df_conc.empty:
                    nat_col = next((c for c in df.columns if any(k in c.upper() for k in ["NATINF", "INF-NATINF", "NUMERO_NATINF", "CODE_NATINF"])), None)
                    if nat_col:
                        df["numero_natinf_clean"] = df[nat_col].astype(str).str.extract(r'(\d+)', expand=False).fillna("").str.lstrip("0")
                        df = df.merge(df_conc, left_on="numero_natinf_clean", right_on="numero_natinf", how="left")
                        
                        orig_dom = df["DOMAINE"].fillna("Hors domaine") if "DOMAINE" in df.columns else "Hors domaine"
                        orig_thm = df["THEME"].fillna(orig_dom) if "THEME" in df.columns else orig_dom

                        df["DOMAINE"] = df["domaine_snc"].fillna(orig_dom).replace("", orig_dom)
                        df["THEME"] = df["theme_snc"].fillna(orig_thm).replace("", orig_thm)
                        df["ACTION"] = df["action_snc"].fillna("Non renseigné").replace("", "Non renseigné")
                        df["DOMAINE_SNC"] = df["DOMAINE"]
                        df["THEME_SNC"] = df["THEME"]
                        df["ACTION_SNC"] = df["ACTION"]
                        df["domaine"] = df["DOMAINE"]
                        df["theme"] = df["THEME"]
            except Exception as exc:
                logger.warning("Échec de la jointure concordance NATINF / SNC sur PVe : %s", exc)

            _save_disk_cache(root, raw_key, sig, df)
        _PVE_RAW_CACHE[path] = df.copy()
        if is_national_full:
            _save_disk_cache(root, "pve_national", sig, df)

    if echelle is not None and code is not None:
        from core.common.utilitaires_metier import get_departements_pour_perimetre, get_bmi_filters
        echelle_norm = str(echelle).strip().lower()
        if echelle_norm == "bmi" and "nom_site" in df.columns:
            bmi_filters = get_bmi_filters(code)
            nom_site_val = str(bmi_filters.get("nom_site_pve", "BMI")).upper()
            import re
            def clean_str(s):
                if pd.isna(s): return ""
                s = str(s).upper()
                s = s.replace("Ô", "O").replace("ô", "o").replace("-", " ")
                return re.sub(r'\s+', ' ', s).strip()
            
            keywords_pve_yaml = bmi_filters.get("keywords_pve", [])
            if keywords_pve_yaml:
                keywords_to_find = [str(k).upper() for k in keywords_pve_yaml]
            else:
                nom_site_val_clean = clean_str(nom_site_val)
                keywords_to_find = [w for w in nom_site_val_clean.split() if w not in ["POLE", "DE", "ET", "LA", "LE", "DU", "DES"]]
            
            nom_site_col = df["nom_site"].apply(clean_str)
            mask = nom_site_col.apply(lambda x: all(k in x for k in keywords_to_find))
            df = df[mask].copy()
        elif echelle_norm != "bmi":
            dept_codes = get_departements_pour_perimetre(echelle, code)
            dept_col = "INF-DEPART" if "INF-DEPART" in df.columns else "INF-DEPARTEMENT"
            if dept_col in df.columns and dept_codes and "FR" not in dept_codes:
                df = df[df[dept_col].astype(str).str.strip().isin(dept_codes)].copy()
    date_col = "INF-DATE-MIF" if "INF-DATE-MIF" in df.columns else ("INF-DATE-INTG" if "INF-DATE-INTG" in df.columns else None)
    if date_deb is not None and date_fin is not None and date_col is not None:
        n_before_period = len(df)
        deb_ts = pd.to_datetime(date_deb)
        fin_ts = pd.to_datetime(date_fin)
        df = filtre_periode(df, date_col, deb_ts, fin_ts)
        n_after_period = len(df)
        if n_before_period > n_after_period:
            logger.info(
                "PVe : %s ligne(s) retenues sur %s après filtre période %s "
                "(%s → %s) ; %s ligne(s) hors période exclues. "
                "(Une jointure QGIS sans filtre date sur les mêmes communes PNF peut compter plus de lignes.)",
                n_after_period,
                n_before_period,
                date_col,
                date_deb,
                date_fin,
                n_before_period - n_after_period,
            )

    df = enrich_pve_positions_from_pnf_commune_centroids(root, df, log=logger)

    # Garantie d'enrichissement thématique NATINF -> Domaine / Thème / Action SNC
    if "theme" not in df.columns and "THEME" not in df.columns:
        try:
            df_conc = load_concordance_natinf_snc(root)
            if not df_conc.empty:
                nat_col = next((c for c in df.columns if any(k in c.upper() for k in ["NATINF", "INF-NATINF", "NUMERO_NATINF", "CODE_NATINF"])), None)
                if nat_col:
                    df["numero_natinf_clean"] = df[nat_col].astype(str).str.strip().str.lstrip("0")
                    df = df.merge(df_conc, left_on="numero_natinf_clean", right_on="numero_natinf", how="left")
                    
                    fallback_val = "Non Classé / Hors SNC"
                    df["DOMAINE"] = df["domaine_snc"].fillna(fallback_val).replace("", fallback_val)
                    df["THEME"] = df["theme_snc"].fillna(fallback_val).replace("", fallback_val)
                    df["ACTION"] = df["action_snc"].fillna(fallback_val).replace("", fallback_val)
                    df["DOMAINE_SNC"] = df["DOMAINE"]
                    df["THEME_SNC"] = df["THEME"]
                    df["ACTION_SNC"] = df["ACTION"]
                    df["domaine"] = df["DOMAINE"]
                    df["theme"] = df["THEME"]
        except Exception as exc:
            logger.warning("Échec de la jointure concordance NATINF / SNC sur PVe : %s", exc)

    return df


def get_points_infrac_pj_path(root: Path) -> Path:
    """
    Chemin du fichier des points infractions PJ (GPKG ou shapefile) le plus récent.

    On recherche en priorité les GeoPackage dans sources/sig/points_infractions_pj/
    ou sources/sig/point_infraction_PJ/, avec un nom du type localisation_infrac_FAITS_YYYYMMDD.gpkg,
    puis, à défaut, un shapefile localisation_infrac_FAITS_YYYYMMDD.shp.
    """
    candidates = [
        root / "data" / "sources" / "sig" / "point_infraction_PJ",
        root / "data" / "sources" / "sig" / "points_infractions_pj",
        root / "data" / "sources" / "points_infractions_pj",
    ]
    
    for base_dir in candidates:
        if base_dir.exists():
            try:
                return _find_latest_dated_file(
                    base_dir, "localisation_infrac_FAITS_", (".gpkg", ".shp")
                )
            except FileNotFoundError:
                continue
                
    # On laisse l'appelant gérer l'absence de fichier
    return root / "data" / "sources" / "sig" / "point_infraction_PJ" / "localisation_infrac_FAITS_00000000.gpkg"


def load_pej_non_localises(root: Path) -> pd.DataFrame:
    """
    Charge le CSV des infractions PEJ non localisées (géométrie vide dans OSCEAN)
    pour identifier les dossiers dont la commune est structurellement impossible à déterminer
    par géomatique.
    """
    candidates = [
        root / "data" / "sources" / "sig" / "point_infraction_PJ",
        root / "data" / "sources" / "sig" / "points_infractions_pj",
        root / "data" / "sources" / "points_infractions_pj",
    ]
    for base_dir in candidates:
        if base_dir.exists():
            try:
                path = _find_latest_dated_file(base_dir, "infrac_FAITS_non_localises_", (".csv",))
                df = pd.read_csv(path, sep=";", encoding="latin-1", on_bad_lines="skip")
                return df
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.warning("Erreur lors de la lecture du CSV des PEJ non localisés : %s", e)
                return pd.DataFrame()
    return pd.DataFrame()


def merge_pej_faits_locations(
    pej: pd.DataFrame,
    root: Path,
    echelle: str,
    code: str,
    *,
    natinf_list: list = [],
    log: Optional[logging.Logger] = None,
    gdf_faits: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Enrichit le tableau PEJ (ODS) avec les coordonnées WGS84 issues de la couche
    ``localisation_infrac_FAITS_*`` (jointure ``DC_ID`` = ``dossier``).

    Utilise ``gpd.read_file()`` directement pour lire les colonnes natives du GPKG
    (``x_infrac`` / ``y_infrac`` / ``dossier``). Si ``natinf_list`` est fourni, seules
    les lignes GPKG dont le NATINF correspond sont conservées avant jointure.
    """
    lg = log or logger
    if pej is None or pej.empty or "DC_ID" not in pej.columns:
        return pej

    if "x_faits" in pej.columns and "y_faits" in pej.columns and pej["x_faits"].notna().all() and pej["y_faits"].notna().all():
        return pej.copy()

    if gdf_faits is not None and not gdf_faits.empty:
        gdf = gdf_faits.copy()
    else:
        path = get_points_infrac_pj_path(root)
        gdf = pd.DataFrame()
        if path and path.exists():
            path_str = str(path)
            if path_str in _FAITS_RAW_CACHE:
                gdf = _FAITS_RAW_CACHE[path_str].copy()
            else:
                try:
                    gdf = read_vector_attributes(path)
                    _FAITS_RAW_CACHE[path_str] = gdf.copy()
                except Exception as e:
                    lg.warning("Lecture FAITS pour localisations PEJ impossible (%s) : %s", path, e)
        elif path:
            # Fallback en cas de mock dans les tests ou fichier virtuel
            path_str = str(path)
            if path_str in _FAITS_RAW_CACHE:
                gdf = _FAITS_RAW_CACHE[path_str].copy()
            else:
                try:
                    gdf = read_vector_attributes(path)
                    _FAITS_RAW_CACHE[path_str] = gdf.copy()
                except Exception:
                    gdf = pd.DataFrame()

    out = pej.copy()
    if "x_faits" not in out.columns:
        out["x_faits"] = np.nan
    if "y_faits" not in out.columns:
        out["y_faits"] = np.nan

    def _clean_pej_id(val):
        if pd.isna(val):
            return ""
        s = str(val).strip()
        s = re.sub(r"\.0$", "", s)
        s = re.sub(r"^OF", "", s, flags=re.IGNORECASE).strip()
        s = re.sub(r"^SD\d+[\s_-]*", "", s, flags=re.IGNORECASE).strip()
        return re.sub(r"[\s\-_]", "", s).upper()

    if not gdf.empty:
        # Filtre entité SD souple par numéro de département
        ent_col = next((c for c in ("entite", "ENTITE", "Entite") if c in gdf.columns), None)
        if ent_col is not None:
            from core.common.utilitaires_metier import get_departements_pour_perimetre
            dept_codes = get_departements_pour_perimetre(echelle, code)
            if dept_codes and "FR" not in dept_codes:
                dept_set = {str(d).strip().zfill(2) for d in dept_codes}
                if str(echelle).strip().lower() == "bmi":
                    from core.common.utilitaires_metier import get_bmi_filters
                    bmi_filters = get_bmi_filters(code)
                    dept_set.add(str(bmi_filters.get("entite_pej", code)).upper())

                def _match_sd_entite(val):
                    if pd.isna(val):
                        return False
                    v_str = str(val).strip().upper()
                    for d in dept_set:
                        if d in v_str:
                            return True
                        digits = re.findall(r"\d+", v_str)
                        if any(d == dig.zfill(2) for dig in digits):
                            return True
                    return False

                gdf = gdf[gdf[ent_col].apply(_match_sd_entite)].copy()

        # Filtre NATINF optionnel
        if not gdf.empty and natinf_list:
            natinf_col = next((c for c in ("natinf", "NATINF") if c in gdf.columns), None)
            if natinf_col:
                natinf_vals = {re.sub(r"\.0$", "", str(n)).strip() for n in natinf_list}
                gdf = gdf[gdf[natinf_col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True).isin(natinf_vals)].copy()

        doss_col = next((c for c in ("dossier", "DOSSIER", "code_pej", "NUMERO_PROCEDURE") if c in gdf.columns), None)
        xcol = "x_infrac" if "x_infrac" in gdf.columns else ("x" if "x" in gdf.columns else None)
        ycol = "y_infrac" if "y_infrac" in gdf.columns else ("y" if "y" in gdf.columns else None)

        if doss_col and xcol and ycol:
            commune_col = next(
                (c for c in ("commune_fait", "commune_fa", "NOM_COM", "commune", "COMMUNE") if c in gdf.columns),
                None,
            )
            keep_cols = [doss_col, xcol, ycol] + ([commune_col] if commune_col else [])
            loc = gdf[keep_cols].copy()
            loc["_doss_raw"] = loc[doss_col].astype(str).astype(object).str.strip().apply(lambda val: re.sub(r"\.0$", "", str(val)) if pd.notna(val) else "")
            loc["_doss_clean"] = loc[doss_col].apply(_clean_pej_id)
            rename_map = {xcol: "x_faits", ycol: "y_faits"}
            if commune_col is not None:
                rename_map[commune_col] = "NOM_COM_FAITS"
            loc = loc.rename(columns=rename_map)

            # Passe 1 : jointure brute DC_ID
            out["_dc_raw"] = out["DC_ID"].astype(str).astype(object).str.strip().apply(lambda val: re.sub(r"\.0$", "", str(val)) if pd.notna(val) else "")
            loc_raw = loc.drop_duplicates(subset="_doss_raw", keep="first")
            out = out.drop(columns=["x_faits", "y_faits"], errors="ignore").merge(
                loc_raw[["_doss_raw", "x_faits", "y_faits"] + (["NOM_COM_FAITS"] if commune_col else [])],
                left_on="_dc_raw",
                right_on="_doss_raw",
                how="left",
            )
            out = out.drop(columns=["_dc_raw", "_doss_raw"], errors="ignore")

            # Passe 2 : jointure tolérante DC_ID nettoyé (sans préfixe OF)
            still_missing = out["x_faits"].isna() | out["y_faits"].isna()
            if still_missing.any():
                out["_dc_clean"] = out["DC_ID"].apply(_clean_pej_id)
                loc_clean = loc.drop_duplicates(subset="_doss_clean", keep="first")
                merged_clean = out.loc[still_missing, ["_dc_clean"]].merge(
                    loc_clean[["_doss_clean", "x_faits", "y_faits"] + (["NOM_COM_FAITS"] if commune_col else [])],
                    left_on="_dc_clean",
                    right_on="_doss_clean",
                    how="left",
                )
                idx_m = out[still_missing].index
                out.loc[idx_m, "x_faits"] = merged_clean["x_faits"].values
                out.loc[idx_m, "y_faits"] = merged_clean["y_faits"].values
                if commune_col and "NOM_COM_FAITS" in merged_clean.columns:
                    if "NOM_COM_FAITS" not in out.columns:
                        out["NOM_COM_FAITS"] = pd.NA
                    s_m = pd.Series(merged_clean["NOM_COM_FAITS"].values, index=idx_m)
                    out.loc[idx_m, "NOM_COM_FAITS"] = out.loc[idx_m, "NOM_COM_FAITS"].combine_first(s_m)
                out = out.drop(columns=["_dc_clean"], errors="ignore")

            # Passe 3 : jointure de secours sur NUMERO_PROCEDURE
            still_missing = out["x_faits"].isna() | out["y_faits"].isna()
            if still_missing.any() and "NUMERO_PROCEDURE" in out.columns:
                out["_numproc_clean"] = out["NUMERO_PROCEDURE"].apply(_clean_pej_id)
                loc_clean = loc.drop_duplicates(subset="_doss_clean", keep="first")
                merged_numproc = out.loc[still_missing, ["_numproc_clean"]].merge(
                    loc_clean[["_doss_clean", "x_faits", "y_faits"] + (["NOM_COM_FAITS"] if commune_col else [])],
                    left_on="_numproc_clean",
                    right_on="_doss_clean",
                    how="left",
                )
                idx_m = out[still_missing].index
                out.loc[idx_m, "x_faits"] = merged_numproc["x_faits"].values
                out.loc[idx_m, "y_faits"] = merged_numproc["y_faits"].values
                if commune_col and "NOM_COM_FAITS" in merged_numproc.columns:
                    if "NOM_COM_FAITS" not in out.columns:
                        out["NOM_COM_FAITS"] = pd.NA
                    s_m = pd.Series(merged_numproc["NOM_COM_FAITS"].values, index=idx_m)
                    out.loc[idx_m, "NOM_COM_FAITS"] = out.loc[idx_m, "NOM_COM_FAITS"].combine_first(s_m)
                out = out.drop(columns=["_numproc_clean"], errors="ignore")

            if "NOM_COM_FAITS" in out.columns:
                if "NOM_COM" in out.columns:
                    out["NOM_COM"] = out["NOM_COM"].fillna(out["NOM_COM_FAITS"])
                    out["NOM_COM"] = out["NOM_COM"].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
                else:
                    out["NOM_COM"] = out["NOM_COM_FAITS"].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
            
    # === FALLBACK OSCEAN & CSV NON-LOCALISÉS : Récupération du nom de commune ===
    has_nom_com = "NOM_COM" in out.columns
    missing = out["NOM_COM"].isna() if has_nom_com else pd.Series(True, index=out.index)
    if missing.any():
        try:
            oscean_gdf = load_point_ctrl(root, echelle=echelle, code=code)
            if not oscean_gdf.empty and "dc_id" in oscean_gdf.columns and "nom_commun" in oscean_gdf.columns:
                oscean_dc = oscean_gdf[["dc_id", "nom_commun"]].dropna(subset=["nom_commun"]).copy()
                oscean_dc["dc_id"] = oscean_dc["dc_id"].astype(str).apply(lambda val: re.sub(r"\.0$", "", str(val)) if pd.notna(val) else "")
                oscean_dc = oscean_dc.drop_duplicates(subset=["dc_id"])
                
                oscean_num = pd.DataFrame()
                if "code_pej" in oscean_gdf.columns:
                    oscean_num = oscean_gdf[["code_pej", "nom_commun"]].dropna(subset=["nom_commun"]).copy()
                    oscean_num["code_pej"] = oscean_num["code_pej"].astype(str).apply(lambda val: re.sub(r"\.0$", "", str(val)) if pd.notna(val) else "")
                    oscean_num = oscean_num.drop_duplicates(subset=["code_pej"])
                
                def _recover_commune(row):
                    if pd.notna(row.get("NOM_COM")) and str(row.get("NOM_COM")).strip() not in ("", "nan", "None", "<NA>"):
                        return row.get("NOM_COM")
                    dc_id = str(row.get("DC_ID", "")).replace(".0", "")
                    num_proc = str(row.get("NUMERO_PROCEDURE", "")).replace(".0", "")
                    
                    if dc_id:
                        match = oscean_dc[oscean_dc["dc_id"] == dc_id]
                        if not match.empty:
                            return match.iloc[0]["nom_commun"]
                    if num_proc and not oscean_num.empty:
                        match = oscean_num[oscean_num["code_pej"] == num_proc]
                        if not match.empty:
                            return match.iloc[0]["nom_commun"]
                    return pd.NA

                out["NOM_COM"] = out.apply(_recover_commune, axis=1)
        except Exception as e:
            lg.warning("Impossible de charger les points OSCEAN pour la récupération des communes PEJ manquantes : %s", e)

    # Récupération de secours via le CSV des faits PEJ non localisés
    has_nom_com = "NOM_COM" in out.columns
    missing = (out["NOM_COM"].isna() | out["NOM_COM"].astype(str).str.strip().isin(["", "nan", "None", "<NA>"])) if has_nom_com else pd.Series(True, index=out.index)
    if missing.any():
        try:
            df_nl = load_pej_non_localises(root)
            if not df_nl.empty:
                col_com_nl = next((c for c in ("insee_comm", "nom_com", "NOM_COM", "commune", "COMMUNE") if c in df_nl.columns), None)
                col_dc_nl = next((c for c in ("DC_ID", "dc_id", "dossier", "DOSSIER") if c in df_nl.columns), None)
                col_num_nl = next((c for c in ("NUMERO_PROCEDURE", "numero_procedure", "code_pej") if c in df_nl.columns), None)
                if col_com_nl:
                    dict_dc = {}
                    dict_num = {}
                    if col_dc_nl:
                        dict_dc = df_nl.dropna(subset=[col_com_nl]).set_index(df_nl[col_dc_nl].apply(_clean_pej_id))[col_com_nl].to_dict()
                    if col_num_nl:
                        dict_num = df_nl.dropna(subset=[col_com_nl]).set_index(df_nl[col_num_nl].apply(_clean_pej_id))[col_num_nl].to_dict()
                    
                    if "NOM_COM" not in out.columns:
                        out["NOM_COM"] = pd.NA

                    for idx in out[missing].index:
                        row = out.loc[idx]
                        dc_clean = _clean_pej_id(row.get("DC_ID"))
                        num_clean = _clean_pej_id(row.get("NUMERO_PROCEDURE"))
                        found_com = dict_dc.get(dc_clean) or dict_num.get(num_clean)
                        if found_com and pd.notna(found_com):
                            out.loc[idx, "NOM_COM"] = str(found_com).strip()
        except Exception as e:
            lg.warning("PEJ : échec de la récupération des communes depuis le CSV des non localisées : %s", e)
    # === FIN FALLBACK ===

    # Garantir que DATE_REF reste datetime après le merge (le join Pandas peut en faire un object)
    if "DATE_REF" in out.columns:
        out["DATE_REF"] = pd.to_datetime(out["DATE_REF"], errors="coerce")

    # Initialisation de la colonne de précision de géolocalisation
    if "precision_loc" not in out.columns:
        out["precision_loc"] = pd.Series(pd.NA, index=out.index, dtype="string")

    # Niveau 1 : Marquer les localisations exactes issues du GPKG FAITS
    has_faits_xy = out["x_faits"].notna() & out["y_faits"].notna()
    out.loc[has_faits_xy, "precision_loc"] = "GPS Fait (Exacte)"

    # === CASCADE DE FALLBACKS DE GÉOLOCALISATION ===
    missing_xy = out["x_faits"].isna() | out["y_faits"].isna()
    if missing_xy.any():
        # Fallback Niveau 2 : Point de contrôle rattaché (OSCEAN)
        try:
            oscean_gdf = load_point_ctrl(root, echelle=echelle, code=code)
            if not oscean_gdf.empty and "dc_id" in oscean_gdf.columns and "x" in oscean_gdf.columns and "y" in oscean_gdf.columns:
                osc_valid = oscean_gdf.dropna(subset=["x", "y"]).copy()
                osc_valid["dc_clean"] = osc_valid["dc_id"].astype(str).apply(lambda v: re.sub(r"\.0$", "", str(v)) if pd.notna(v) else "")
                osc_valid = osc_valid.drop_duplicates(subset=["dc_clean"])
                
                dict_osc_x = osc_valid.set_index("dc_clean")["x"].to_dict()
                dict_osc_y = osc_valid.set_index("dc_clean")["y"].to_dict()
                
                dc_series = out.loc[missing_xy, "DC_ID"].astype(str).apply(lambda v: re.sub(r"\.0$", "", str(v)) if pd.notna(v) else "")
                mapped_x = dc_series.map(dict_osc_x)
                mapped_y = dc_series.map(dict_osc_y)
                
                found_osc = mapped_x.notna() & mapped_y.notna()
                if found_osc.any():
                    idx_found = dc_series[found_osc].index
                    out.loc[idx_found, "x_faits"] = mapped_x[found_osc]
                    out.loc[idx_found, "y_faits"] = mapped_y[found_osc]
                    out.loc[idx_found, "precision_loc"] = "Point de contrôle rattaché"
        except Exception as e:
            lg.warning("PEJ : échec du fallback contrôle d'origine : %s", e)

        # Fallback Niveau 3 : Centroïde de la commune (code INSEE ou NOM_COM / COMMUNE)
        missing_xy = out["x_faits"].isna() | out["y_faits"].isna()
        if missing_xy.any():
            try:
                cen_com = load_communes_centroides(root)
                if not cen_com.empty:
                    com_names = load_communes_noms(root)
                    inv_com_names = {str(v).lower().strip(): str(k).zfill(5) for k, v in com_names.items() if v}
                    
                    dict_lat = pd.to_numeric(cen_com.set_index("code_insee")["lat"], errors="coerce").to_dict()
                    dict_lon = pd.to_numeric(cen_com.set_index("code_insee")["lon"], errors="coerce").to_dict()
                    
                    insee_cols = ("INSEE_COMM", "INSEE_COMMUNE", "CODE_INSEE", "INSEE_COM", "INSEE", "INF-INSEE", "insee_comm", "code_insee", "insee_com", "insee")
                    nom_cols = ("NOM_COM", "NOM_COMMUNE", "COMMUNE", "COMMUNE_FAIT", "COMMUNE_FAITS", "NOM_COM_FAITS", "nom_com", "nom_commune", "commune")

                    for idx in out[missing_xy].index:
                        row = out.loc[idx]
                        insee_val = None
                        for c in insee_cols:
                            if c in row and pd.notna(row[c]):
                                candidate = str(row[c]).strip().zfill(5)
                                if len(candidate) == 5 and candidate != "00000":
                                    insee_val = candidate
                                    break
                                    
                        if not insee_val:
                            for c in nom_cols:
                                if c in row and pd.notna(row[c]):
                                    nom_clean = str(row[c]).lower().strip()
                                    if nom_clean in inv_com_names:
                                        insee_val = inv_com_names[nom_clean]
                                        break
                            
                        if insee_val and insee_val in dict_lat and insee_val in dict_lon:
                            out.loc[idx, "x_faits"] = dict_lon[insee_val]
                            out.loc[idx, "y_faits"] = dict_lat[insee_val]
                            out.loc[idx, "precision_loc"] = "Centroïde communal (Approximatif)"
            except Exception as e:
                lg.warning("PEJ : échec du fallback centroïde communal : %s", e)

        # Note: Le fallback niveau 4 (centroïde départemental) a été retiré afin de ne pas fausser les cartes de chaleur.
        # Les PEJ non géolocalisées conservent x_faits/y_faits à NaN.

    n = int(out["x_faits"].notna().sum())
    if n:
        lg.info("PEJ : %s / %s ligne(s) géolocalisée(s) après cascade (exactes + fallbacks).", n, len(out))
    return out


def _propagate_nom_commune_to_nom_com(df: pd.DataFrame) -> pd.DataFrame:
    """Recopie ``nom_commune`` vers ``NOM_COM`` lorsque ce dernier est vide."""
    if df is None or df.empty or "nom_commune" not in df.columns:
        return df
    out = df.copy()
    nc = (
        out["nom_commune"]
        .astype(str)
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "<NA>": pd.NA})
    )
    if "NOM_COM" in out.columns:
        nom_com = (
            out["NOM_COM"]
            .astype(str)
            .str.strip()
            .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "<NA>": pd.NA})
        )
        out["NOM_COM"] = nom_com.fillna(nc)
    else:
        out["NOM_COM"] = nc
    return out


def enrich_pej_commune_from_faits_coordinates(
    pej: pd.DataFrame,
    root: Path,
    *,
    log: Optional[logging.Logger] = None,
) -> pd.DataFrame:
    """
    Complète ``insee_comm`` et ``NOM_COM`` pour les PEJ disposant de coordonnées FAITS
    (``x_faits``, ``y_faits``) via ``communes.shp``, lorsque l'ODS ou la couche FAITS
    n'ont pas renseigné la commune.
    """
    if pej is None or pej.empty:
        return pej
    if "x_faits" not in pej.columns or "y_faits" not in pej.columns:
        return pej.copy()
    xy_ok = pej["x_faits"].notna() & pej["y_faits"].notna()
    if not bool(xy_ok.any()):
        return pej.copy()

    out = ensure_insee_from_communes_shp(
        pej, root, context="PEJ (coordonnées FAITS)", log=log
    )
    return _propagate_nom_commune_to_nom_com(out)


def load_points_infrac_pj(
    root: Path, natinf_list: List[str], echelle: str, code: str
):
    """Charge le shapefile/gpkg des points d'infractions PJ, filtre SD + NATINF."""
    import geopandas as gpd
    import pandas as pd
    path = get_points_infrac_pj_path(root)
    if not path.exists():
        raise FileNotFoundError(path)
    natinf_vals = [int(n) for n in natinf_list]
    # Filtre à la lecture si possible (pyogrio) pour éviter de charger tout le GPKG
    try:
        from core.common.utilitaires_metier import get_departements_pour_perimetre
        target_depts = get_departements_pour_perimetre(echelle, code)
        if target_depts and "FR" not in target_depts:
            entite_list = [f"SD{d}" for d in target_depts]
            if str(echelle).strip().lower() == "bmi":
                from core.common.utilitaires_metier import get_bmi_filters
                bmi_filters = get_bmi_filters(code)
                entite_list.append(str(bmi_filters.get("entite_pej", code)).upper())
            entite_clause = "entite IN ('" + "', '".join(entite_list) + "')"
        else:
            entite_clause = "1=1"
        where_clause = f"{entite_clause} AND natinf IN ({','.join(map(str, natinf_vals))})"
        gdf = gpd.read_file(path, engine="pyogrio", where=where_clause)
    except Exception:
        gdf = gpd.read_file(path)
        gdf["natinf"] = pd.to_numeric(gdf["natinf"], errors="coerce")
        if target_depts and "FR" not in target_depts:
            entite_list = [f"SD{d}" for d in target_depts]
            if str(echelle).strip().lower() == "bmi":
                from core.common.utilitaires_metier import get_bmi_filters
                bmi_filters = get_bmi_filters(code)
                entite_list.append(str(bmi_filters.get("entite_pej", code)).upper())
            mask = (gdf["entite"].isin(entite_list)) & (gdf["natinf"].isin(natinf_vals))
        else:
            mask = gdf["natinf"].isin(natinf_vals)
        gdf = gdf.loc[mask].copy()

    # Harmonisation du CRS : si absent, on considère que les coordonnées sont en WGS84.
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)

    if "natinf" in gdf.columns and gdf["natinf"].dtype == object:
        gdf["natinf"] = pd.to_numeric(gdf["natinf"], errors="coerce")

    # Colonne de commune : le schéma réel utilise "commune_fait" (et non "commune_fa").
    commune_col = None
    if "commune_fait" in gdf.columns:
        commune_col = "commune_fait"
    elif "commune_fa" in gdf.columns:
        commune_col = "commune_fa"

    cols = ["dossier", "natinf", "entite", "x_infrac", "y_infrac", "geometry"]
    if commune_col is not None:
        cols.insert(2, commune_col)
    cols = [c for c in cols if c in gdf.columns]
    return gdf[cols].copy()


def load_pj_with_geometry(
    root: Path,
    natinf_list: List[str],
    echelle: str,
    code: str,
    date_deb: Optional[Union[str, pd.Timestamp]] = None,
    date_fin: Optional[Union[str, pd.Timestamp]] = None,
    pej_df: Optional[pd.DataFrame] = None,
):
    """
    Charge les procédures judiciaires (ODS) et les associe à la géométrie des faits
    (GPKG points PJ). Ne conserve que les dossiers présents dans le GPKG (SD + NATINF).

    Retourne un GeoDataFrame avec les colonnes PJ utiles + geometry.
    Si date_deb/date_fin sont fournis, le PEJ est filtré sur cette période avant jointure.
    Si pej_df est fourni, il est utilisé à la place de recharger l'ODS (évite double lecture).
    """
    if pej_df is not None:
        pej = pej_df
    else:
        pej = load_pej(root, date_deb=date_deb, date_fin=date_fin)
    pts_pj = load_points_infrac_pj(root, natinf_list, echelle, code)
    dossiers_geom = set(pts_pj["dossier"].unique())
    pej_with_geom = pej[pej["DC_ID"].isin(dossiers_geom)].copy()
    if pej_with_geom.empty:
        return gpd.GeoDataFrame(columns=list(pej.columns) + ["geometry"], crs=pts_pj.crs)

    pts_dedup = pts_pj.drop_duplicates(subset="dossier", keep="first")
    merge_cols = [c for c in ["dossier", "entite", "geometry"] if c in pts_dedup.columns]
    merged = pej_with_geom.merge(
        pts_dedup[merge_cols],
        left_on="DC_ID",
        right_on="dossier",
        how="left",
    )
    if "dossier" in merged.columns:
        merged = merged.drop(columns=["dossier"])
    return gpd.GeoDataFrame(merged, geometry="geometry", crs=pts_pj.crs)


def prepare_pve_communes_gpkg(root: Path) -> Path:
    """Prépare la couche géospatiale des PVe par commune et l'exporte en GPKG."""
    sources = root / "data" / "sources"
    candidates = list(sources.glob("Stats_PVe_OFB au *.xlsx"))
    if not candidates:
        raise FileNotFoundError("Aucun fichier Stats_PVe_OFB au *.xlsx trouvé dans data/sources")
    pve_path = sorted(candidates)[-1]
    
    # Lecture Excel
    df_pve = pd.read_excel(pve_path, dtype=str)
    insee_col = next((c for c in df_pve.columns if "insee" in str(c).lower()), None)
    if not insee_col:
        # Fallback si le nom est complexe
        insee_col = next((c for c in df_pve.columns if "code" in str(c).lower()), df_pve.columns[0])
        
    df_pve["insee_clean"] = df_pve[insee_col].astype(str).str.zfill(5)
    counts = df_pve.groupby("insee_clean").size().reset_index(name="nb_pve")
    
    # Jointure avec communes (sur centroïdes)
    communes_shp = ref_programme(root) / "sig" / "communes_21" / "communes.shp"
    gdf_com = gpd.read_file(communes_shp)
    gdf_com["geometry"] = gdf_com.geometry.centroid
    
    com_insee_col = next((c for c in gdf_com.columns if "insee" in str(c).lower()), "INSEE_COM")
    
    gdf_pve = gdf_com.merge(counts, left_on=com_insee_col, right_on="insee_clean", how="inner")
    
    out_dir = root / "data" / "out" / "couches_sig"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "pve_communes.gpkg"
    
    if out_path.exists():
        out_path.unlink()
        
    gdf_pve.to_file(out_path, driver="GPKG", layer="pve_communes")
    return out_path
