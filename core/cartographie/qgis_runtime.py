"""
Découverte du Python QGIS et export cartographique en sous-processus.

Permet à ``python -m ofbilan`` (interpréteur standard) de déléguer la génération
des cartes au Python/OSGeo4W lorsque PyQGIS n'est pas importable in-process.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from core.chemins_projet import PROJECT_ROOT

logger = logging.getLogger(__name__)

_QGIS_PYTHON_CACHE: Optional[Path] = None


def _qgis_python_path_candidates() -> list[Path]:
    candidates: list[Path] = []
    env = (os.environ.get("QGIS_PYTHON") or os.environ.get("BILANS_QGIS_PYTHON") or "").strip()
    if env:
        candidates.append(Path(env))
    for rel in (
        PROJECT_ROOT / "scripts" / "windows" / "qgis_python_path.txt",
        PROJECT_ROOT / "src" / "ofbilan" / "cartographie" / "qgis_python_path.txt",
    ):
        if not rel.exists():
            continue
        try:
            content = rel.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = rel.read_text(encoding="utf-16")
        for line in content.splitlines():
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


def get_qgis_env(python_exe: Path) -> dict[str, str]:
    """Calcule l'environnement OSGeo4W/QGIS complet pour l'exécutable python."""
    env = os.environ.copy()
    
    bin_dir = python_exe.parent
    root_dir = bin_dir.parent
    
    python_home = root_dir / "apps" / "Python312"
    if not python_home.exists():
        python_apps = list(root_dir.glob("apps/Python*"))
        if python_apps:
            python_home = python_apps[0]
            
    qgis_apps = root_dir / "apps" / "qgis-ltr"
    if not qgis_apps.exists():
        qgis_apps = root_dir / "apps" / "qgis"
        
    osgeo4w_root = str(root_dir)
    env["OSGEO4W_ROOT"] = osgeo4w_root
    env["PYTHONHOME"] = str(python_home)
    env["QGIS_PREFIX_PATH"] = str(qgis_apps).replace("\\", "/")
    env["GDAL_FILENAME_IS_UTF8"] = "YES"
    env["VSI_CACHE"] = "TRUE"
    env["VSI_CACHE_SIZE"] = "1000000"
    env["PYTHONUTF8"] = "1"
    
    qt_plugins = f"{qgis_apps}\\qtplugins;{root_dir}\\apps\\Qt5\\plugins"
    env["QT_PLUGIN_PATH"] = qt_plugins
    
    paths = [
        str(qgis_apps / "bin"),
        str(python_home / "Scripts"),
        str(root_dir / "apps" / "qt5" / "bin"),
        str(bin_dir),
        env.get("SystemRoot", r"C:\Windows") + r"\system32",
        env.get("SystemRoot", r"C:\Windows"),
        env.get("SystemRoot", r"C:\Windows") + r"\system32\WBem",
    ]
    env["PATH"] = ";".join(paths)
    
    python_paths = [
        str(qgis_apps / "python"),
        str(PROJECT_ROOT / "src"),
        str(PROJECT_ROOT),
    ]
    existing_pythonpath = env.get("PYTHONPATH", "")
    if existing_pythonpath:
        python_paths.append(existing_pythonpath)
    env["PYTHONPATH"] = ";".join(python_paths)
    
    return env


def can_import_pyqgis(python_exe: Path, env: dict[str, str] | None = None) -> bool:
    """Vérifie que l'exécutable peut importer qgis.core."""
    try:
        proc = subprocess.run(
            [str(python_exe), "-c", "from qgis.core import Qgis"],
            env=env,
            capture_output=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _cartography_launcher_bat() -> Path:
    return (
        PROJECT_ROOT
        / "src"
        / "ofbilan"
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
    diffusion: str = "interne",
) -> bool:
    """
    Lance l'export QGIS via Python QGIS direct ou le lanceur Windows historique.
    """
    if not profile_ids:
        return True

    profiles_arg = ",".join(p.strip() for p in profile_ids if p.strip())
    if not profiles_arg:
        return True

    # 1. Essai Direct via Python QGIS (recommandé, contourne cmd.exe /c et les fichiers bat bloqués)
    qgis_python = find_qgis_python_executable()
    if qgis_python is not None:
        qgis_env = get_qgis_env(qgis_python)
        if target_dir:
            qgis_env["CARTO_OUTPUT_DIR"] = str(target_dir)
        if can_import_pyqgis(qgis_python, env=qgis_env):
            script = PROJECT_ROOT / "src" / "ofbilan" / "cartographie" / "production_cartographique.py"
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
                "--diffusion",
                diffusion,
            ]
            logger.info(
                "Génération cartes via QGIS direct (sans batch) : profils=%s dept=%s",
                profiles_arg,
                dept_code,
            )
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(PROJECT_ROOT),
                    env=qgis_env,
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=3600,
                )
                if proc.returncode == 0:
                    return True
                logger.warning(
                    "Génération directe QGIS échouée (code %s).\n--- STDOUT ---\n%s\n--- STDERR ---\n%s",
                    proc.returncode,
                    proc.stdout,
                    proc.stderr,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                logger.warning("Impossible de lancer QGIS direct : %s", exc)

    # 2. Repli historique (batch Windows)
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
            "--diffusion",
            diffusion,
        ]
        logger.info(
            "Génération cartes via QGIS (lanceur batch de secours) : profils=%s dept=%s",
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
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=3600,
            )
            if proc.returncode != 0:
                logger.warning(
                    "Export cartographique sous-processus de secours échoué (code %s).\n--- STDOUT ---\n%s\n--- STDERR ---\n%s",
                    proc.returncode,
                    proc.stdout,
                    proc.stderr,
                )
                return False
            return True
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("Impossible de lancer le sous-processus de secours : %s", exc)
            return False

    return False
