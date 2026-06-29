# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
import os
import sys
import subprocess
import webbrowser
import threading
import time

class OFBilanPlugin:
    """Plugin QGIS pour lancer OFBilan."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.server_process = None

    def initGui(self):
        """Initialise l'interface QGIS (bouton de barre d'outils et menu)."""
        icon_path = ':/images/themes/default/mActionStart.svg' # Fallback QGIS icon
        
        # Si OFBilan possède un icône, on l'utilise
        local_icon = os.path.join(self.plugin_dir, 'core', 'web', 'static', 'favicon.ico')
        if os.path.exists(local_icon):
            icon_path = local_icon
            
        icon = QIcon(icon_path)
        self.action = QAction(icon, "Lancer OFBilan Explorer", self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&OFBilan", self.action)

    def unload(self):
        """Nettoyage lors du déchargement du plugin."""
        if self.action:
            self.iface.removePluginMenu("&OFBilan", self.action)
            self.iface.removeToolBarIcon(self.action)
        
        # Arrêter le serveur s'il tourne encore
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()

    def run(self):
        """Logique exécutée au clic sur le bouton."""
        if self.server_process and self.server_process.poll() is None:
            QMessageBox.information(self.iface.mainWindow(), "OFBilan", "Le serveur OFBilan est déjà en cours d'exécution.\nOuverture du navigateur...")
            webbrowser.open('http://localhost:8000/explorer.html')
            return

        # Configuration de l'environnement pour importer 'core'
        env = os.environ.copy()
        env["PYTHONPATH"] = self.plugin_dir + os.pathsep + env.get("PYTHONPATH", "")
        
        serveur_script = os.path.join(self.plugin_dir, 'core', 'web', 'serveur.py')
        
        try:
            python_exe = sys.executable
            if os.name == 'nt' and "qgis" in python_exe.lower():
                bin_dir = os.path.dirname(python_exe)
                if os.path.exists(os.path.join(bin_dir, "python.exe")):
                    python_exe = os.path.join(bin_dir, "python.exe")
                elif os.path.exists(os.path.join(bin_dir, "python3.exe")):
                    python_exe = os.path.join(bin_dir, "python3.exe")
                    
            # Lancement en arrière-plan sans bloquer QGIS
            self.server_process = subprocess.Popen(
                [python_exe, serveur_script],
                env=env,
                cwd=self.plugin_dir,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Pause de 2s pour laisser FastAPI démarrer avant d'ouvrir le navigateur
            def open_browser():
                time.sleep(2)
                webbrowser.open('http://localhost:8000/explorer.html')
                
            threading.Thread(target=open_browser, daemon=True).start()
            
            self.iface.messageBar().pushMessage("OFBilan", "Démarrage du serveur web...", level=0, duration=3)
            
        except Exception as e:
            QMessageBox.critical(self.iface.mainWindow(), "Erreur OFBilan", f"Impossible de lancer le serveur :\n{e}")
