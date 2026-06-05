"""
Découverte du Python QGIS et export cartographique en sous-processus.

Permet à ``python -m bilans`` (interpréteur standard) de déléguer la génération
des cartes au Python/OSGeo4W lorsque PyQGIS n'est pas importable in-process.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from bilans.chemins_projet import PROJECT_ROOT

logger = logging.getLogger(__name__)

_QGIS_PYTHON_CACHE: Optional[Path] = None


def _qgis_python_path_candidates() -> list[Path]:
    candidates: list[Path] = []
    env = (os.environ.get("QGIS_PYTHON") or os.environ.get("BILANS_QGIS_PYTHON") or "").strip()
    if env:
        candidates.append(Path(env))
    for rel in (
        PROJECT_ROOT / "scripts" / "windows" / "qgis_python_path.txt",
        PROJECT_ROOT / "src" / "bilans" / "cartographie" / "qgis_python_path.txt",
    ):
        if not rel.exists():
            continue
        for line in rel.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                candidates.append(Path(line))
                break
    pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    for pattern in (
        pf / "QGIS 3.40.15" / "bin" / "python.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "OSGeo4W" / "bin" / "python.exe",
        Path(r"C:\OSGeo4W64\bin\python.exe"),
        Path(r"C:\OSGeo4W\bin\python.exe"),
    ):
        if str(pattern):
            candidates.append(pattern)
    return candidates


def find_qgis_python_executable(*, refresh: bool = False) -> Optional[Path]:
    """Retourne le chemin vers python.exe QGIS/OSGeo4W, ou None."""
    global _QGIS_PYTHON_CACHE
    if _QGIS_PYTHON_CACHE is not None and not refresh:
        return _QGIS_PYTHON_CACHE if _QGIS_PYTHON_CACHE.exists() else None

    for path in _qgis_python_path_candidates():
        if path.is_file():
            _QGIS_PYTHON_CACHE = path.resolve()
            return _QGIS_PYTHON_CACHE
    _QGIS_PYTHON_CACHE = None
    return None


def can_import_pyqgis(python_exe: Path) -> bool:
    """Vérifie que l'exécutable peut importer qgis.core."""
    try:
        proc = subprocess.run(
            [str(python_exe), "-c", "from qgis.core import Qgis"],
            capture_output=True,
            timeout=120,
            text=True,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _cartography_launcher_bat() -> Path:
    return (
        PROJECT_ROOT
        / "src"
        / "bilans"
        / "cartographie"
        / "lancer_production_cartographique.bat"
    )


def run_cartography_export_subprocess(
    profile_ids: list[str],
    *,
    date_deb: str,
    date_fin: str,
    dept_code: str,
    target_dir: Optional[Path] = None,
) -> bool:
    """
    Lance l'export QGIS via le lanceur Windows (environnement OSGeo4W) ou Python QGIS direct.

    Retourne True si le sous-processus se termine avec le code 0.
    """
    if not profile_ids:
        return True

    profiles_arg = ",".join(p.strip() for p in profile_ids if p.strip())
    if not profiles_arg:
        return True

    bat = _cartography_launcher_bat()
    if sys.platform.startswith("win") and bat.is_file():
        cmd = [
            "cmd.exe",
            "/c",
            str(bat),
            profiles_arg,
            "--date-deb",
            date_deb,
            "--date-fin",
            date_fin,
            "--dept-code",
            dept_code,
        ]
        logger.info(
            "Génération cartes via QGIS (sous-processus) : profils=%s dept=%s",
            profiles_arg,
            dept_code,
        )
        env = os.environ.copy()
        env["BILANS_CARTO_HEADLESS"] = "1"
        if target_dir:
            env["CARTO_OUTPUT_DIR"] = str(target_dir)
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=3600,
            )
            if proc.returncode != 0:
                stderr_tail = (proc.stderr or proc.stdout or "")[-2000:]
                logger.warning(
                    "Export cartographique sous-processus échoué (code %s). %s",
                    proc.returncode,
                    stderr_tail.strip() or "(pas de sortie)",
                )
                return False
            return True
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("Impossible de lancer le sous-processus QGIS : %s", exc)
            return False

    qgis_python = find_qgis_python_executable()
    if qgis_python is None or not can_import_pyqgis(qgis_python):
        return False

    script = PROJECT_ROOT / "src" / "bilans" / "cartographie" / "production_cartographique.py"
    env = os.environ.copy()
    if target_dir:
        env["CARTO_OUTPUT_DIR"] = str(target_dir)
    src = str(PROJECT_ROOT / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [
        str(qgis_python),
        str(script),
        profiles_arg,
        "--date-deb",
        date_deb,
        "--date-fin",
        date_fin,
        "--dept-code",
        dept_code,
    ]
    logger.info("Génération cartes via %s (profils=%s)", qgis_python.name, profiles_arg)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=3600,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Export QGIS direct échoué : %s", exc)
        return False
