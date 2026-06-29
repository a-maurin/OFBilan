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
from typing import Any, List, Optional

from core.chemins_projet import PROJECT_ROOT, get_cartes_dir

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


def _find_single_map_legacy(profile_id: str) -> Optional[Path]:
    """Recherche une carte unique (comportement historique, glob partiel)."""
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
    """Return the path to a pre-generated map PNG for the given profile, or None."""
    return resolve_map_png_path(profile_id, bilan_profiles=bilan_profiles, target_dir=target_dir)


def resolve_map_png_path(
    profile_id: str,
    *,
    bilan_profiles: dict[str, dict] | None = None,
    target_dir: Path | None = None,
) -> Optional[Path]:
    """Chemin PNG d'une carte (catalogue bilan ou conventions carte_{id}.png)."""
    pid = str(profile_id).strip()
    if not pid:
        return None

    try:
        p = Path(pid)
        if p.exists() and p.is_file():
            return p.resolve()
    except Exception:
        pass

    from core.common.cartographie_config import parse_cartography_catalog

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

    bilan_profile = (bilan_profiles or {}).get(pid)
    paths = resolve_profile_map_paths(
        pid,
        profile=bilan_profile if isinstance(bilan_profile, dict) else None,
        target_dir=target_dir,
    )
    if paths:
        return paths[0]
    return _find_single_map_legacy(pid)


def _format_map_pattern(pattern: str, map_id: str) -> str:
    return str(pattern).replace("{map_id}", map_id).strip()


def _patterns_from_profile_and_presentation(
    map_id: str,
    *,
    profile: dict | None,
    presentation_cfg: dict | None,
) -> list[str]:
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

    if not patterns:
        patterns = [f"carte_{map_id}.png", f"carte_{map_id}_2.png"]
    return patterns


def resolve_map_layout(
    *,
    profile: dict | None = None,
    presentation_cfg: dict | None = None,
) -> str:
    """
    Disposition demandée pour les cartes : ``horizontal`` ou ``vertical``.

    Note : le rendu PDF standard applique désormais une carte par page ; cette
    information reste utile pour compatibilité de configuration et pour les
    usages spécifiques (ex. brochure).
    """
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
    """
    Chemins des cartes PNG à intégrer (ordre conservé, doublons retirés).

    Fichiers cherchés dans ``data/out/generateur_de_cartes/`` :
    - motifs définis dans le profil ``cartographie.fichiers`` ;
    - ou ``blocks.sec5.map_files`` (présentation PDF) ;
    - sinon ``carte_{map_id}.png`` et ``carte_{map_id}_2.png``.
    """
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
    """Noms de fichiers attendus (pour messages CLI / documentation)."""
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


_qgis_app = None

def get_qgis_app():
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
    from core.common.utilitaires_metier import resolve_carto_dept_code

    echelle_eff = echelle or "departement"
    code_eff = code or dept_code or "21"
    return resolve_carto_dept_code(echelle_eff, code_eff)


def _warn_qgis_unavailable_for_cartes(carto_dept: str, *, subprocess_failed: bool = False) -> None:
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
    diffusion: str = "interne",
) -> List[Path]:
    """
    Try to generate maps via QGIS. Returns list of generated map paths.
    If QGIS is not available, returns empty list (avertissement journalisé).
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

    generated = []
    for pid in profile_ids:
        m = resolve_map_png_path(pid, bilan_profiles=bilan_profiles, target_dir=target_dir)
        if m and is_map_valid_for_dept(m, carto_dept):
            generated.append(m)
            marker = read_map_dept_marker(m) or "(legacy 21)"
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
    diffusion: str = "interne",
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

    from core.cartographie.pochoir_helper import (
        is_map_valid_for_dept,
        read_map_dept_marker,
        warn_if_unknown_carto_dept,
    )

    carto_dept = _resolve_carto_dept(echelle, code, dept_code)
    warn_if_unknown_carto_dept(carto_dept)
    qgis_ok = qgis_available()

    existing: List[Path] = []
    missing: List[str] = []
    for pid in unique_ids:
        m = resolve_map_png_path(pid, bilan_profiles=bilan_profiles, target_dir=target_dir)
        if m and is_map_valid_for_dept(m, carto_dept):
            existing.append(m)
        elif m:
            marker = read_map_dept_marker(m)
            logger.info(
                "Carte %s ignorée pour le département %s (marqueur=%s, profil=%s) — régénération QGIS prévue",
                m.name,
                carto_dept,
                marker or "absent",
                pid,
            )
            missing.append(pid)
        else:
            missing.append(pid)

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
        )

    # Retourne l'ensemble des cartes trouvées / générées, sans doublons
    result: List[Path] = []
    seen: set[Path] = set()
    for p in existing + generated:
        if p not in seen:
            seen.add(p)
            result.append(p)

    resolved_ids: set[str] = set()
    for pid in unique_ids:
        m = resolve_map_png_path(pid, bilan_profiles=bilan_profiles, target_dir=target_dir)
        if m and is_map_valid_for_dept(m, carto_dept):
            resolved_ids.add(pid)
    unresolved = [p for p in unique_ids if p not in resolved_ids]
    if unresolved:
        _warn_unresolved_cartes(unresolved, carto_dept, qgis_was_available=qgis_ok)

    return result
