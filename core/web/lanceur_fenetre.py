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

"""Module de lancement de l'application web OFBilan en fenêtre dédiée."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import subprocess
import webbrowser

import threading
from typing import Any

logger = logging.getLogger(__name__)


def _maximiser_fenetre_windows(titre_partiel: str = "OFBilan", delai_max_sec: float = 6.0) -> None:
    """Surveille l'apparition de la fenêtre applicative sous Windows pour forcer sa maximisation."""
    if os.name != "nt":
        return

    def _worker() -> None:
        try:
            import ctypes
            from ctypes import wintypes
            import time

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            sw_maximize = 3

            wndenumproc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            nav_exes = ("msedge.exe", "chrome.exe", "chromium.exe", "brave.exe")
            fenetre_trouvee = False

            def enum_cb(hwnd: Any, _lparam: Any) -> bool:
                nonlocal fenetre_trouvee
                try:
                    if not user32.IsWindowVisible(hwnd):
                        return True

                    length = user32.GetWindowTextLengthW(hwnd)
                    if length <= 0:
                        return True

                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    if titre_partiel.lower() not in buf.value.lower():
                        return True

                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value:
                        h_proc = kernel32.OpenProcess(0x1000, False, pid.value)
                        if h_proc:
                            try:
                                proc_buf = ctypes.create_unicode_buffer(1024)
                                size = wintypes.DWORD(1024)
                                if kernel32.QueryFullProcessImageNameW(h_proc, 0, proc_buf, ctypes.byref(size)):
                                    nom_exe = Path(proc_buf.value).name.lower()
                                    if not any(nav in nom_exe for nav in nav_exes):
                                        return True
                            finally:
                                kernel32.CloseHandle(h_proc)

                    user32.ShowWindowAsync(hwnd, sw_maximize)
                    user32.SetForegroundWindow(hwnd)
                    fenetre_trouvee = True
                    return False
                except Exception:
                    return True

            cb = wndenumproc(enum_cb)
            t_debut = time.time()
            while time.time() - t_debut < delai_max_sec and not fenetre_trouvee:
                user32.EnumWindows(cb, 0)
                if fenetre_trouvee:
                    break
                time.sleep(0.2)
        except Exception as e:
            logger.debug("Échec de la maximisation Windows : %s", e)

    threading.Thread(target=_worker, daemon=True).start()


def trouver_navigateur_app() -> str | None:
    """Recherche un exécutable de navigateur Chromium supportant le mode --app."""
    candidats: list[Path | str] = []

    if os.name == "nt":
        pf_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        local_app = os.environ.get("LocalAppData", "")

        # Microsoft Edge (prioritaire car natif Windows 10/11)
        candidats.extend([
            Path(pf_x86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(pf) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(local_app) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        ])

        # Google Chrome (repli Chromium secondaire)
        candidats.extend([
            Path(pf) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(pf_x86) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(local_app) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ])

    # Recherche dans le PATH
    for commande in ("msedge", "chrome", "google-chrome", "chromium", "brave"):
        trouve = shutil.which(commande)
        if trouve:
            candidats.append(trouve)

    for candidat in candidats:
        try:
            p = Path(candidat)
            if p.is_file():
                return str(p)
        except Exception:
            continue

    return None


def ouvrir_fenetre_app(url: str, maximiser: bool = True) -> bool:
    """Ouvre l'URL dans une fenêtre dédiée autonome avec repli vers le navigateur standard.

    Args:
        url: URL à ouvrir (http://... ou file://...).
        maximiser: Indique si la fenêtre doit s'ouvrir maximisée en plein écran.

    Returns:
        True si l'ouverture a été exécutée.
    """
    navigateur = trouver_navigateur_app()

    if navigateur:
        commande = [navigateur, f"--app={url}"]
        if maximiser:
            commande.append("--start-maximized")

        try:
            cwd_arg = os.environ.get("SystemRoot", r"C:\Windows") if os.name == "nt" else None
            subprocess.Popen(
                commande,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=cwd_arg,
            )
            if maximiser and os.name == "nt":
                _maximiser_fenetre_windows()
            return True
        except Exception as e:
            logger.warning("Échec du lancement en mode application (%s), repli sur le navigateur standard.", e)

    # Repli standard si aucun Chromium trouvé ou en cas d'erreur de lancement
    try:
        webbrowser.open(url)
        return True
    except Exception as e:
        logger.error("Impossible d'ouvrir le navigateur : %s", e)
        return False
