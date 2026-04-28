"""
Helper pour intégrer les cartes dans les bilans PDF.

Fournit des fonctions pour :
- Vérifier si des cartes pré-générées existent
- Tenter de générer des cartes via QGIS (si disponible)
- Lister les cartes disponibles pour un profil donné
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from bilans.paths import PROJECT_ROOT, get_cartes_dir

logger = logging.getLogger(__name__)

_QGIS_AVAILABLE: Optional[bool] = None


def qgis_available() -> bool:
    """Check if QGIS Python bindings are importable."""
    global _QGIS_AVAILABLE
    if _QGIS_AVAILABLE is None:
        try:
            from qgis.core import Qgis  # noqa: F401
            _QGIS_AVAILABLE = True
        except ImportError:
            _QGIS_AVAILABLE = False
    return _QGIS_AVAILABLE


def find_map(profile_id: str) -> Optional[Path]:
    """Return the path to a pre-generated map PNG for the given profile, or None."""
    cartes = get_cartes_dir()
    candidates = [
        cartes / f"carte_{profile_id}.png",
        cartes / f"{profile_id}.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    for p in cartes.glob(f"*{profile_id}*.png"):
        return p
    return None


def find_maps_for_bilan(bilan_type: str) -> List[Path]:
    """Return all pre-generated map PNGs relevant to a bilan type."""
    profile_map = {
        "bilan_global": ["agrainage", "chasse", "global_usagers", "procedures_pve"],
        "bilan_agrainage": ["agrainage"],
        "bilan_chasse": ["chasse"],
        "bilan_procedures": ["procedures_pve"],
    }
    profile_ids = profile_map.get(bilan_type, [bilan_type])
    result = []
    for pid in profile_ids:
        m = find_map(pid)
        if m:
            result.append(m)
    return result


def generate_maps(
    profile_ids: List[str],
    date_deb: Optional[str] = None,
    date_fin: Optional[str] = None,
    dept_code: Optional[str] = None,
) -> List[Path]:
    """
    Try to generate maps via QGIS. Returns list of generated map paths.
    If QGIS is not available, returns empty list silently.
    """
    if not qgis_available():
        logger.info("QGIS non disponible — utilisation des cartes pré-générées.")
        return []

    try:
        from bilans.cartographie.production_cartographique import run_export
        run_export(profile_ids, date_deb=date_deb, date_fin=date_fin, dept_code=dept_code)
    except Exception as e:
        logger.warning("Échec génération cartes QGIS : %s", e)
        return []

    generated = []
    for pid in profile_ids:
        m = find_map(pid)
        if m:
            generated.append(m)
    return generated


def ensure_maps(
    bilan_type: str,
    date_deb: Optional[str] = None,
    date_fin: Optional[str] = None,
    dept_code: Optional[str] = None,
) -> List[Path]:
    """
    Return map paths for a bilan. Generates them if missing and QGIS is available.
    Bilans can call this and integrate the returned paths into their PDF.
    """
    existing = find_maps_for_bilan(bilan_type)
    if existing:
        return existing

    profile_map = {
        "bilan_global": ["agrainage", "chasse", "global_usagers", "procedures_pve"],
        "bilan_agrainage": ["agrainage"],
        "bilan_chasse": ["chasse"],
        "bilan_procedures": ["procedures_pve"],
    }
    profile_ids = profile_map.get(bilan_type, [bilan_type])
    generated = generate_maps(profile_ids, date_deb, date_fin, dept_code)
    if generated:
        return generated

    return find_maps_for_bilan(bilan_type)


def ensure_maps_for_profiles(
    profile_ids: List[str],
    date_deb: Optional[str] = None,
    date_fin: Optional[str] = None,
    dept_code: Optional[str] = None,
) -> List[Path]:
    """
    Ensure that maps exist for a list of cartographic profiles.

    - Utilise les cartes pré-générées si elles existent déjà.
    - Tente de générer les cartes manquantes via QGIS (run_export) si disponible.
    - Ne lève pas d'erreur en cas d'échec de génération : retourne simplement
      les cartes trouvées.
    """
    if not profile_ids:
        return []

    # Normalisation / dédoublonnage des identifiants de profils
    unique_ids: List[str] = []
    for pid in profile_ids:
        p = (pid or "").strip()
        if not p:
            continue
        if p not in unique_ids:
            unique_ids.append(p)

    existing: List[Path] = []
    missing: List[str] = []
    for pid in unique_ids:
        m = find_map(pid)
        if m:
            existing.append(m)
        else:
            missing.append(pid)

    generated: List[Path] = []
    if missing:
        generated = generate_maps(missing, date_deb=date_deb, date_fin=date_fin, dept_code=dept_code)

    # Retourne l'ensemble des cartes trouvées / générées, sans doublons
    result: List[Path] = []
    seen: set[Path] = set()
    for p in existing + generated:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result
