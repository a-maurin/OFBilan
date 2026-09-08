# -*- coding: utf-8 -*-
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
EXTENSION QGIS - INTERFACE DU PLUGIN (`ofbilan_plugin.py`)
========================================================================================
Ce fichier implémente la classe principale `OFBilanPlugin` requise par l'architecture QGIS.

Rôles principaux :
  1. `initGui()` : enregistrement du bouton "Lancer OFBilan Explorer" dans la barre d'outils
     et le menu Extensions de QGIS.
  2. `run()` : démarrage en arrière-plan du serveur Web Python (`serveur.py`) sans bloquer
     l'interface utilisateur QGIS, puis ouverture automatique du navigateur web.
  3. `unload()` : nettoyage des boutons et arrêt propre du serveur web à la fermeture de QGIS.
========================================================================================
"""
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .core.web.lanceur_fenetre import ouvrir_fenetre_app
except ImportError:
    try:
        from core.web.lanceur_fenetre import ouvrir_fenetre_app
    except ImportError:
        def ouvrir_fenetre_app(url: str, maximiser: bool = True) -> bool:
            import webbrowser
            return bool(webbrowser.open(url))

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox


class OFBilanPlugin:
    """Plugin QGIS pour lancer OFBilan."""

    def __init__(self, iface: Any) -> None:
        self.iface = iface
        self.plugin_dir = Path(__file__).resolve().parent
        self.action: QAction | None = None
        self.server_process: subprocess.Popen[bytes] | None = None

    def initGui(self) -> None:
        """Initialise l'interface QGIS (bouton de barre d'outils et menu)."""
        icon_path = ':/images/themes/default/mActionStart.svg'
        local_icon = self.plugin_dir / 'icon.svg'
        if local_icon.is_file():
            icon_path = str(local_icon)

        icon = QIcon(icon_path)
        self.action = QAction(icon, "Lancer OFBilan Explorer", self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&OFBilan", self.action)

    def unload(self) -> None:
        """Nettoyage lors du déchargement du plugin."""
        if self.action:
            self.iface.removePluginMenu("&OFBilan", self.action)
            self.iface.removeToolBarIcon(self.action)

        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()

    def run(self) -> None:
        """Logique exécutée au clic sur le bouton."""
        port = 8000
        try:
            from .core.parametres_utilisateur import lire_parametres
            port = int(lire_parametres().get("tech", {}).get("port_serveur", 8000))
        except (ImportError, ValueError, AttributeError, KeyError):
            pass

        if self.server_process and self.server_process.poll() is None:
            QMessageBox.information(
                self.iface.mainWindow(),
                "OFBilan",
                "Le serveur OFBilan est déjà en cours d'exécution.\nOuverture du navigateur..."
            )
            ouvrir_fenetre_app(f'http://localhost:{port}/explorer.html')
            return

        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.plugin_dir) + os.pathsep + env.get("PYTHONPATH", "")
        serveur_script = self.plugin_dir / 'core' / 'web' / 'serveur.py'

        try:
            python_exe = sys.executable
            if os.name == 'nt' and "qgis" in python_exe.lower():
                bin_dir = Path(python_exe).parent
                if (bin_dir / "python.exe").exists():
                    python_exe = str(bin_dir / "python.exe")
                elif (bin_dir / "python3.exe").exists():
                    python_exe = str(bin_dir / "python3.exe")

            self.server_process = subprocess.Popen(
                [python_exe, str(serveur_script)],
                env=env,
                cwd=str(self.plugin_dir),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            loading_html = self.plugin_dir / 'core' / 'web' / 'loading.html'
            ouvrir_fenetre_app(f"{loading_html.as_uri()}?port={port}")
            self.iface.messageBar().pushMessage("OFBilan", "Démarrage du serveur web...", level=0, duration=3)

        except Exception as e:
            QMessageBox.critical(self.iface.mainWindow(), "Erreur OFBilan", f"Impossible de lancer le serveur :\n{e}")