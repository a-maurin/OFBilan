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
MODULE : RESOLUTION ET INITIALISATION DE L'ENVIRONNEMENT PYQGIS (`qgis_runtime.py`)
========================================================================================
Ce module est chargé de détecter dynamiquement l'emplacement de l'interpréteur Python QGIS
(OSGeo4W) sur le système de l'utilisateur (Windows, Linux, macOS).

Rôle stratégique :
  Lorsque OFBilan est exécuté depuis un Python standard (ex. environnement virtuel `.venv`),
  `qgis_runtime.py` localise l'exécutable `python.exe` propre à QGIS pour sous-traiter
  la génération cartographique en sous-processus sans nécessiter l'installation complète
  de PyQGIS dans le Python système.
========================================================================================
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


def _scan_program_files_qgis() -> list[Path]:
    """Scanne les répertoires Program Files et retourne les exécutables Python triés par version décroissante."""
    candidates: list[Path] = []
    pfs = [Path(os.environ.get("ProgramFiles", r"C:\Program Files"))]
    pf86 = os.environ.get("ProgramFiles(x86)")
    if pf86:
        pfs.append(Path(pf86))

    qgis_dirs: list[Path] = []
    for pf in pfs:
        if pf.exists():
            try:
                qgis_dirs.extend([d for d in pf.glob("QGIS*") if d.is_dir()])
            except OSError:
                pass

    import re
    def _ver_sort(p: Path) -> tuple[int, ...]:
        nums = re.findall(r"\d+", p.name)
        return tuple(int(n) for n in nums) if nums else (0,)

    qgis_dirs.sort(key=_ver_sort, reverse=True)

    for qdir in qgis_dirs:
        for sub in ("bin/python.exe", "bin/python3.exe", "bin/python-qgis-ltr.bat"):
            cand = qdir / sub
            if cand.exists():
                candidates.append(cand)
    return candidates


def _scan_registry_qgis() -> list[Path]:
    """Scanne le registre Windows pour détecter les chemins QGIS / OSGeo4W."""
    candidates: list[Path] = []
    if sys.platform != "win32":
        return candidates
    try:
        import winreg
        keys_to_check = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\QGIS\QGIS3", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\OSGeo4W", ""),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\QGIS\QGIS3", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\QGIS\QGIS3", "InstallPath"),
        ]
        for root_key, subkey, valname in keys_to_check:
            try:
                with winreg.OpenKey(root_key, subkey) as k:
                    val, _ = winreg.QueryValueEx(k, valname)
                    if val:
                        p = Path(val)
                        for sub in ("bin/python.exe", "bin/python3.exe", "bin/python-qgis-ltr.bat", "python.exe"):
                            cand = p / sub
                            if cand.exists():
                                candidates.append(cand)
            except OSError:
                pass
    except Exception:
        pass
    return candidates


def prompt_user_for_qgis_path() -> Optional[Path]:
    """Ouvre une boîte de sélection native de dossier si QGIS est introuvable."""
    if os.environ.get("CI") or os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    selected_path: Optional[str] = None
    if sys.platform == "win32":
        try:
            ps_cmd = (
                "[System.Reflection.Assembly]::LoadWithPartialName('System.windows.forms') | Out-Null; "
                "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
                "$dialog.Description = 'Veuillez sélectionner le dossier d installation de QGIS'; "
                "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $dialog.SelectedPath }"
            )
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, check=False)
            out = res.stdout.strip()
            if out:
                selected_path = out
        except Exception:
            pass

    if not selected_path:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            selected_path = filedialog.askdirectory(title="Sélectionner le dossier d'installation de QGIS")
            root.destroy()
        except Exception:
            pass

    if selected_path:
        p = Path(selected_path)
        candidates = [
            p if p.is_file() and p.name.lower() in ("python.exe", "python-qgis-ltr.bat") else None,
            p / "bin" / "python.exe",
            p / "bin" / "python-qgis-ltr.bat",
            p / "python.exe",
        ]
        for c in candidates:
            if c and c.exists():
                try:
                    from core.parametres_utilisateur import lire_parametres, sauvegarder_parametres
                    params = lire_parametres()
                    params.setdefault("tech", {})["qgis_path"] = str(c)
                    sauvegarder_parametres(params)
                except Exception:
                    pass
                return c
    return None


def _qgis_python_path_candidates() -> list[Path]:
    candidates: list[Path] = []

    # 1. Paramètres utilisateur mémorisés
    try:
        from core.parametres_utilisateur import lire_parametres
        saved = lire_parametres().get("tech", {}).get("qgis_path", "").strip()
        if saved:
            sp = Path(saved)
            if sp.is_file():
                candidates.append(sp)
            elif sp.is_dir():
                for sub in ("bin/python.exe", "bin/python-qgis-ltr.bat", "python.exe"):
                    cand = sp / sub
                    if cand.exists():
                        candidates.append(cand)
    except Exception:
        pass

    # 2. Variables d'environnement
    env = (os.environ.get("QGIS_PYTHON") or os.environ.get("BILANS_QGIS_PYTHON") or os.environ.get("OSGEO4W_ROOT") or "").strip()
    if env:
        ep = Path(env)
        if ep.is_file():
            candidates.append(ep)
        elif ep.is_dir():
            for sub in ("bin/python.exe", "bin/python-qgis-ltr.bat", "python.exe"):
                if (ep / sub).exists():
                    candidates.append(ep / sub)

    # 3. Fichier de configuration explicite
    for rel in (
        PROJECT_ROOT / "scripts" / "lancement" / "qgis_python_path.txt",
        PROJECT_ROOT / "scripts" / "windows" / "qgis_python_path.txt",
        PROJECT_ROOT / "core" / "cartographie" / "qgis_python_path.txt",
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

    # 4. Registre Windows
    candidates.extend(_scan_registry_qgis())

    # 5. Scan Program Files par version décroissante
    candidates.extend(_scan_program_files_qgis())

    # 6. Emplacements OSGeo4W / LocalAppData
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidates.append(Path(local_app_data) / "Programs" / "OSGeo4W" / "bin" / "python.exe")
    candidates.append(Path(r"C:\OSGeo4W64\bin\python.exe"))
    candidates.append(Path(r"C:\OSGeo4W\bin\python.exe"))

    return candidates


def find_qgis_python_executable(*, refresh: bool = False, prompt_if_missing: bool = False) -> Optional[Path]:
    """Retourne le chemin vers python.exe QGIS/OSGeo4W, ou None."""
    global _QGIS_PYTHON_CACHE
    if _QGIS_PYTHON_CACHE is not None and not refresh:
        return _QGIS_PYTHON_CACHE if _QGIS_PYTHON_CACHE.exists() else None

    for path in _qgis_python_path_candidates():
        if path.is_file():
            _QGIS_PYTHON_CACHE = path.resolve()
            return _QGIS_PYTHON_CACHE

    if prompt_if_missing:
        prompted = prompt_user_for_qgis_path()
        if prompted and prompted.is_file():
            _QGIS_PYTHON_CACHE = prompted.resolve()
            return _QGIS_PYTHON_CACHE

    _QGIS_PYTHON_CACHE = None
    return None


def get_qgis_env(python_exe: Path) -> dict[str, str]:
    """Calcule l'environnement OSGeo4W/QGIS complet pour l'exécutable python."""
    env = os.environ.copy()

    # Nettoyage des variables parasites Anaconda / environnements hérités
    for k in list(env.keys()):
        if k.startswith("CONDA_") or k in ("PYTHONHOME", "PYTHONPATH", "_CONDA_ROOT", "_CONDA_EXE"):
            del env[k]
    
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
        str(PROJECT_ROOT / "core"),
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
        / "core"
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
    diffusion: str = "externe",
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
            script = PROJECT_ROOT / "core" / "cartographie" / "production_cartographique.py"
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