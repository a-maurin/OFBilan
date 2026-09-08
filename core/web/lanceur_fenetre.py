"""Module de lancement de l'application web OFBilan en fenêtre dédiée."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import subprocess
import webbrowser

logger = logging.getLogger(__name__)


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
            subprocess.Popen(
                commande,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
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
