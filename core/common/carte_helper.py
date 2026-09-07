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
MODULE : ASSISTANT ET GESTIONNAIRE DE CARTOGRAPHIE (`carte_helper.py`)
========================================================================================
Ce module s'occupe de la localisation, de la vérification et de la génération des cartes QGIS
destinées à être insérées dans les bilans et brochures PDF.

Fonctionnalités principales :
  1. Détection de la disponibilité de QGIS dans l'environnement Python.
  2. Recherche et résolution des chemins des images PNG de cartes pré-générées.
  3. Lancement de la génération de cartes via QGIS (en direct ou via un sous-processus).
  4. Validation de la correspondance entre une carte et le territoire/département cible.
========================================================================================
"""

from __future__ import annotations

# --- IMPORTS STANDARDS PYTHON ---
import logging  # Pour journaliser les avertissements et informations de cartographie
from pathlib import Path  # Manipulation des chemins de fichiers de cartes PNG
from typing import Any, List, Optional  # Annotations de types Python

# --- IMPORTS INTERNES DE L'APPLICATION ---
from core.chemins_projet import PROJECT_ROOT, get_cartes_dir  # Accès aux dossiers racines et cartes
from core.common.chargeur_gabarits import resolve_items_masques_carte  # Récupération des filtres de masquage des cartes

logger = logging.getLogger(__name__)  # Journaliseur du module

# Variable globale mémorisant si QGIS est disponible (évite d'importer QGIS inutilement plusieurs fois)
_QGIS_AVAILABLE: Optional[bool] = None


# ========================================================================================
# DETECTEUR DE DISPONIBILITE DE QGIS
# ========================================================================================

def qgis_available() -> bool:
    """Vérifie si les bibliothèques Python de QGIS (`qgis.core`) peuvent être chargées.

    Retourne `True` si QGIS est utilisable directement dans cet interpréteur Python, `False` sinon.
    """
    global _QGIS_AVAILABLE
    if _QGIS_AVAILABLE is None:
        try:
            from qgis.core import Qgis  # noqa: F401
            _QGIS_AVAILABLE = True
        except ImportError:
            _QGIS_AVAILABLE = False
    return _QGIS_AVAILABLE


# ========================================================================================
# RECHERCHE ET RESOLUTION DES CHEMINS DES IMAGES DE CARTES (PNG)
# ========================================================================================

def _find_single_map_legacy(profile_id: str) -> Optional[Path]:
    """Recherche historique d'une carte unique selon le nom du profil (fallback rétrocompatible)."""
    cartes = get_cartes_dir()
    candidates = [
        cartes / f"carte_{profile_id}.png",
        cartes / f"{profile_id}.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    for p in sorted(cartes.glob(f"*{profile_id}*.png")):
        return p
    return None


def find_map(
    profile_id: str,
    *,
    bilan_profiles: dict[str, dict] | None = None,
    target_dir: Path | None = None,
) -> Optional[Path]:
    """Retourne le chemin d'accès au fichier PNG de carte pour le profil donné, ou `None` si introuvable."""
    return resolve_map_png_path(profile_id, bilan_profiles=bilan_profiles, target_dir=target_dir)


def resolve_map_png_path(
    profile_id: str,
    *,
    bilan_profiles: dict[str, dict] | None = None,
    target_dir: Path | None = None,
    is_brochure: bool = False,
    items_a_masquer: list[str] | None = None,
) -> Optional[Path]:
    """Résout le chemin d'accès exact vers le fichier PNG de carte correspondant à un profil.

    Consulte le catalogue cartographique des profils et teste la présence des variantes (brochure, etc.).
    """
    pid = str(profile_id).strip()
    if not pid:
        return None

    # Si l'identifiant transmis est déjà un chemin de fichier valide qui existe sur le disque
    try:
        p = Path(pid)
        if p.exists() and p.is_file():
            return p.resolve()
    except Exception:
        pass

    from core.common.cartographie_config import parse_cartography_catalog

    # Cas particulier des cartes adaptées au format brochure
    if is_brochure or items_a_masquer:
        for prof in (bilan_profiles or {}).values():
            if not isinstance(prof, dict):
                continue
            for entry in parse_cartography_catalog(prof):
                if str(entry.get("id", "")).strip() == pid:
                    file_name = str(entry.get("fichier", "")).strip()
                    stem = Path(file_name).stem
                    ext = Path(file_name).suffix or ".png"
                    brochure_file = f"{stem}_brochure{ext}" if not stem.endswith("_brochure") else file_name
                    if target_dir and (target_dir / brochure_file).exists():
                        return target_dir / brochure_file
                    cand = get_cartes_dir() / brochure_file
                    if cand.exists():
                        return cand

        # Recherche fallback sur les noms de fichiers brochure historiques
        brochure_legacy_names = [f"carte_{pid}_resultats_brochure.png", f"carte_{pid}_domaines_brochure.png", f"carte_{pid}_brochure.png"]
        for b_name in brochure_legacy_names:
            if target_dir and (target_dir / b_name).exists():
                return target_dir / b_name
            if (get_cartes_dir() / b_name).exists():
                return get_cartes_dir() / b_name
        return None

    # Recherche standard dans le catalogue des profils de bilan
    for prof in (bilan_profiles or {}).values():
        if not isinstance(prof, dict):
            continue
        for entry in parse_cartography_catalog(prof):
            if str(entry.get("id", "")).strip() == pid:
                file_name = str(entry.get("fichier", "")).strip()
                if not file_name.lower().endswith(".png"):
                    file_name = f"{file_name}.png"
                candidate = get_cartes_dir() / file_name
                if candidate.exists():
                    return candidate
                if target_dir:
                    candidate_target = target_dir / file_name
                    if candidate_target.exists():
                        return candidate_target

    # Fallback via la résolution classique des chemins de cartes
    bilan_profile = (bilan_profiles or {}).get(pid)
    paths = resolve_profile_map_paths(
        pid,
        profile=bilan_profile if isinstance(bilan_profile, dict) else None,
        target_dir=target_dir,
    )
    if paths:
        return paths[0]
    return _find_single_map_legacy(pid)


# ========================================================================================
# FONCTIONS DE CONFIGURATION DE LA DISPOSITION ET DES MOTIFS DE CARTES
# ========================================================================================

def _format_map_pattern(pattern: str, map_id: str) -> str:
    """Remplace le marqueur `{map_id}` dans un motif de nom de fichier par l'identifiant réel."""
    return str(pattern).replace("{map_id}", map_id).strip()


def _patterns_from_profile_and_presentation(
    map_id: str,
    *,
    profile: dict | None,
    presentation_cfg: dict | None,
) -> list[str]:
    """Extrait la liste des motifs de noms de fichiers de cartes à partir des fichiers YAML de configuration."""
    patterns: list[str] = []
    carto = (profile or {}).get("cartographie") or {}
    if isinstance(carto, dict):
        raw = carto.get("fichiers") or carto.get("files")
        if isinstance(raw, list):
            patterns.extend(str(p).strip() for p in raw if str(p).strip())

    if presentation_cfg:
        blocks = presentation_cfg.get("blocks") or {}
        sec5 = blocks.get("sec5") if isinstance(blocks, dict) else {}
        if isinstance(sec5, dict):
            raw = sec5.get("map_files")
            if isinstance(raw, list) and raw:
                patterns = [str(p).strip() for p in raw if str(p).strip()]

    # Motifs par défaut si aucune configuration explicite n'est fournie
    if not patterns:
        patterns = [f"carte_{map_id}.png", f"carte_{map_id}_2.png"]
    return patterns


def resolve_map_layout(
    *,
    profile: dict | None = None,
    presentation_cfg: dict | None = None,
) -> str:
    """Détermine la disposition demandée pour l'affichage des cartes : 'horizontal' ou 'vertical'."""
    carto = (profile or {}).get("cartographie") or {}
    if isinstance(carto, dict):
        mode = str(carto.get("disposition") or carto.get("layout") or "").strip().lower()
        if mode in ("horizontal", "horizontale", "cote_a_cote", "side_by_side"):
            return "horizontal"
        if mode in ("vertical", "verticale", "empilees", "stacked"):
            return "vertical"

    if presentation_cfg:
        blocks = presentation_cfg.get("blocks") or {}
        sec5 = blocks.get("sec5") if isinstance(blocks, dict) else {}
        if isinstance(sec5, dict):
            mode = str(sec5.get("map_layout") or "").strip().lower()
            if mode in ("horizontal", "horizontale", "cote_a_cote", "side_by_side"):
                return "horizontal"
            if mode in ("vertical", "verticale", "empilees", "stacked"):
                return "vertical"
    return "vertical"


def resolve_profile_map_paths(
    map_id: str,
    *,
    profile: dict | None = None,
    presentation_cfg: dict | None = None,
    target_dir: Path | None = None,
) -> list[Path]:
    """Retourne la liste ordonnée des fichiers PNG de cartes existants pour un profil donné."""
    cartes_dir = get_cartes_dir()
    mid = str(map_id).strip()
    if not mid:
        return []

    patterns = _patterns_from_profile_and_presentation(
        mid, profile=profile, presentation_cfg=presentation_cfg
    )
    dirs_to_check = [get_cartes_dir()]
    if target_dir:
        dirs_to_check.append(target_dir)

    found: list[Path] = []
    seen: set[str] = set()
    for pattern in patterns:
        name = _format_map_pattern(pattern, mid)
        if not name.lower().endswith(".png"):
            name = f"{name}.png"
        for d in dirs_to_check:
            candidate = d / name
            if candidate.exists() and name not in seen:
                seen.add(name)
                found.append(candidate)
                break

    if found:
        return found

    legacy = _find_single_map_legacy(mid)
    return [legacy] if legacy else []


def expected_map_filenames(
    map_id: str,
    *,
    profile: dict | None = None,
    presentation_cfg: dict | None = None,
) -> list[str]:
    """Construit la liste des noms de fichiers de cartes attendus (pour la documentation ou la CLI)."""
    mid = str(map_id).strip()
    patterns = _patterns_from_profile_and_presentation(
        mid, profile=profile, presentation_cfg=presentation_cfg
    )
    names: list[str] = []
    for pattern in patterns:
        name = _format_map_pattern(pattern, mid)
        if not name.lower().endswith(".png"):
            name = f"{name}.png"
        if name not in names:
            names.append(name)
    return names


# Variable de mémorisation de l'instance de l'application QGIS en mode sans tête (Headless)
_qgis_app = None


def get_qgis_app():
    """Initialise et mémorise l'application QGIS en mode sans interface graphique (Headless)."""
    global _qgis_app
    if _qgis_app is None:
        from core.cartographie.production_cartographique import init_qgis_headless
        _qgis_app = init_qgis_headless()
    return _qgis_app


def _resolve_carto_dept(
    echelle: Optional[str],
    code: Optional[str],
    dept_code: Optional[str],
) -> str:
    """Détermine le code du département concerné par la cartographie."""
    from core.common.utilitaires_metier import resolve_carto_dept_code

    echelle_eff = echelle or "departement"
    code_eff = code or dept_code or "21"
    return resolve_carto_dept_code(echelle_eff, code_eff)


def _warn_qgis_unavailable_for_cartes(carto_dept: str, *, subprocess_failed: bool = False) -> None:
    """Émet un avertissement dans la console si QGIS n'est pas disponible pour la génération de cartes."""
    if subprocess_failed:
        logger.warning(
            "Génération cartes échouée (QGIS introuvable et générateur Matplotlib en erreur) "
            "pour le département %s. Vérifiez l'installation QGIS ou les logs, puis : "
            "scripts\\windows\\lancer_bilans_qgis.bat --profil global --cartes "
            "--echelle departement --code %s ...",
            carto_dept,
            carto_dept,
        )
        return
    logger.warning(
        "PyQGIS non importable dans cet interpréteur : tentative via sous-processus QGIS "
        "(ou générateur Matplotlib en secours, voir logs). Sinon : scripts\\windows\\lancer_bilans_qgis.bat --profil global --cartes "
        "--echelle departement --code %s",
        carto_dept,
    )


def _warn_unresolved_cartes(
    profile_ids: list[str],
    carto_dept: str,
    *,
    qgis_was_available: bool,
) -> None:
    """Émet un avertissement si des cartes demandées restent introuvables."""
    if not profile_ids:
        return
    cartes_dir = get_cartes_dir()
    if qgis_was_available:
        logger.warning(
            "Cartes non produites pour le département %s (profils : %s). "
            "Vérifiez les logs QGIS et le dossier %s.",
            carto_dept,
            ", ".join(profile_ids),
            cartes_dir,
        )
        return
    logger.warning(
        "Cartes absentes ou non valides pour le département %s (profils : %s). "
        "Sans QGIS, seules des cartes pré-générées avec marqueur .%s.dept sont acceptées "
        "(rétrocompatibilité : département 21 sans marqueur). Dossier : %s.",
        carto_dept,
        ", ".join(profile_ids),
        carto_dept,
        cartes_dir,
    )


# ========================================================================================
# FONCTIONS PRINCIPALES DE GÉNERATION AUTOMATIQUE DE CARTES VIA QGIS
# ========================================================================================

def generate_maps(
    profile_ids: List[str],
    date_deb: Optional[str] = None,
    date_fin: Optional[str] = None,
    echelle: Optional[str] = None,
    code: Optional[str] = None,
    *,
    dept_code: Optional[str] = None,
    bilan_profiles: dict[str, dict] | None = None,
    target_dir: Path | None = None,
    diffusion: str = "externe",
    items_a_masquer: Optional[List[str]] = None,
    is_brochure: bool = False,
) -> List[Path]:
    """Exécute l'exportation des cartes QGIS pour les profils spécifiés.

    Si QGIS est disponible dans l'environnement courant, exécute l'export directement.
    Sinon, lance un sous-processus dédié. Retourne la liste des chemins des cartes produites.
    """
    carto_dept = _resolve_carto_dept(echelle, code, dept_code)
    from datetime import datetime
    curr_year = datetime.now().year
    date_deb_eff = date_deb or f"{curr_year}-01-01"
    date_fin_eff = date_fin or datetime.now().strftime("%Y-%m-%d")

    import os
    os.environ["BILANS_CARTO_ECHELLE"] = echelle or "departement"
    try:
        if qgis_available():
            try:
                from core.cartographie.production_cartographique import run_export
                from core.common.cartographie_config import build_qgis_overrides_from_bilan_profiles

                qgis_overrides = build_qgis_overrides_from_bilan_profiles(bilan_profiles)
                logger.info(
                    "Génération cartes QGIS (in-process) : profils=%s, département=%s, période %s → %s",
                    ", ".join(profile_ids),
                    carto_dept,
                    date_deb_eff,
                    date_fin_eff,
                )
                get_qgis_app()
                if target_dir:
                    os.environ["CARTO_OUTPUT_DIR"] = str(target_dir)
                run_export(
                    profile_ids,
                    date_deb=date_deb_eff,
                    date_fin=date_fin_eff,
                    dept_code=carto_dept,
                    qgis_overrides=qgis_overrides,
                    diffusion=diffusion,
                    items_a_masquer=items_a_masquer,
                )
                if target_dir and "CARTO_OUTPUT_DIR" in os.environ:
                    del os.environ["CARTO_OUTPUT_DIR"]
            except Exception:
                logger.exception(
                    "Échec génération cartes QGIS in-process (département %s, profils : %s)",
                    carto_dept,
                    ", ".join(profile_ids),
                )
                return []
        else:
            # Lancement via un sous-processus Python disposant de l'environnement QGIS
            from core.cartographie.qgis_runtime import run_cartography_export_subprocess

            logger.info(
                "PyQGIS absent de l'interpréteur courant — délégation export QGIS (sous-processus)."
            )
            ok = run_cartography_export_subprocess(
                profile_ids,
                date_deb=date_deb_eff,
                date_fin=date_fin_eff,
                dept_code=carto_dept,
                target_dir=target_dir,
                diffusion=diffusion,
            )
            if not ok:
                _warn_qgis_unavailable_for_cartes(carto_dept, subprocess_failed=True)
                return []
    finally:
        if "BILANS_CARTO_ECHELLE" in os.environ:
            del os.environ["BILANS_CARTO_ECHELLE"]

    from core.cartographie.pochoir_helper import (
        is_map_valid_for_dept,
        read_map_dept_marker,
    )

    # Vérification et filtrage des cartes réellement générées et valides
    generated = []
    for pid in profile_ids:
        m = resolve_map_png_path(
            pid,
            bilan_profiles=bilan_profiles,
            target_dir=target_dir,
            is_brochure=is_brochure,
            items_a_masquer=items_a_masquer,
        )
        if m and is_map_valid_for_dept(m, carto_dept):
            generated.append(m)
            marker = read_map_dept_marker(m) or "n/a"
            logger.info(
                "Carte OK pour le département %s : %s (marqueur=%s, profil=%s)",
                carto_dept,
                m,
                marker,
                pid,
            )
        elif m:
            logger.warning(
                "Carte non retenue après export QGIS : %s (marqueur=%s, attendu dept. %s, profil=%s)",
                m,
                read_map_dept_marker(m) or "absent",
                carto_dept,
                pid,
            )
    if profile_ids and not generated:
        logger.warning(
            "Aucune carte valide produite pour le département %s (profils demandés : %s). "
            "Dossier : %s",
            carto_dept,
            ", ".join(profile_ids),
            get_cartes_dir(),
        )
    return generated


def ensure_maps_for_profiles(
    profile_ids: List[str],
    date_deb: Optional[str] = None,
    date_fin: Optional[str] = None,
    echelle: Optional[str] = None,
    code: Optional[str] = None,
    *,
    dept_code: Optional[str] = None,
    bilan_profiles: dict[str, dict] | None = None,
    target_dir: Path | None = None,
    diffusion: str = "externe",
    force_regen: bool = False,
    items_a_masquer: Optional[List[str]] = None,
    is_brochure: bool = False,
    gabarit_data: dict[str, Any] | None = None,
) -> List[Path]:
    """Garantit que des cartes valides existent pour une liste de profils.

    1. Vérifie la présence des cartes existantes (sauf si `force_regen=True`).
    2. Génère uniquement les cartes manquantes.
    3. Retourne la liste complète des cartes utilisables pour le document PDF.
    """
    if not profile_ids:
        return []

    if items_a_masquer is None:
        primary_profile = None
        if bilan_profiles and isinstance(bilan_profiles, dict):
            primary_profile = next(iter(bilan_profiles.values()), None)
        items_a_masquer = resolve_items_masques_carte(primary_profile, gabarit_data, is_brochure=is_brochure)

    # Dédoublonnage des identifiants de profils
    unique_ids: List[str] = []
    for pid in profile_ids:
        p = (pid or "").strip()
        if not p:
            continue
        if p not in unique_ids:
            unique_ids.append(p)

    from core.cartographie.pochoir_helper import (
        is_map_valid_for_dept,
        read_map_dept_marker,
        warn_if_unknown_carto_dept,
    )

    carto_dept = _resolve_carto_dept(echelle, code, dept_code)
    try:
        warn_if_unknown_carto_dept(carto_dept, echelle=echelle)
    except TypeError:
        warn_if_unknown_carto_dept(carto_dept)
    qgis_ok = qgis_available()

    existing: List[Path] = []
    missing: List[str] = []
    for pid in unique_ids:
        m = resolve_map_png_path(
            pid,
            bilan_profiles=bilan_profiles,
            target_dir=target_dir,
            is_brochure=is_brochure,
            items_a_masquer=items_a_masquer,
        )
        if m and is_map_valid_for_dept(m, carto_dept) and not force_regen:
            existing.append(m)
        elif m:
            marker = read_map_dept_marker(m)
            logger.info(
                "Carte %s ignorée/forcée pour le département %s (marqueur=%s, profil=%s) — régénération QGIS prévue",
                m.name,
                carto_dept,
                marker or "absent",
                pid,
            )
            missing.append(pid)
        else:
            missing.append(pid)

    # Génère les cartes absentes
    generated: List[Path] = []
    if missing:
        generated = generate_maps(
            missing,
            date_deb=date_deb,
            date_fin=date_fin,
            echelle=echelle,
            code=code,
            dept_code=dept_code,
            bilan_profiles=bilan_profiles,
            target_dir=target_dir,
            diffusion=diffusion,
            items_a_masquer=items_a_masquer,
            is_brochure=is_brochure,
        )

    # Fusionne et dédoublonne la liste des cartes finales
    result: List[Path] = []
    seen: set[Path] = set()
    for p in existing + generated:
        if p not in seen:
            seen.add(p)
            result.append(p)

    resolved_ids: set[str] = set()
    for pid in unique_ids:
        m = resolve_map_png_path(
            pid,
            bilan_profiles=bilan_profiles,
            target_dir=target_dir,
            is_brochure=is_brochure,
            items_a_masquer=items_a_masquer,
        )
        if m and is_map_valid_for_dept(m, carto_dept):
            resolved_ids.add(pid)
    unresolved = [p for p in unique_ids if p not in resolved_ids]
    if unresolved:
        _warn_unresolved_cartes(unresolved, carto_dept, qgis_was_available=qgis_ok)

    return result