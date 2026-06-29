# -*- coding: utf-8 -*-
import sys
import subprocess
from qgis.PyQt.QtWidgets import QMessageBox

def install_dependencies(iface):
    """Vérifie et installe les dépendances requises via pip dans l'environnement QGIS."""
    required_packages = ['pandas', 'reportlab', 'fastapi', 'uvicorn', 'pyyaml']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
            
    if missing_packages:
        msg = f"OFBilan a besoin des paquets suivants : {', '.join(missing_packages)}.\n\nVoulez-vous tenter de les installer automatiquement (nécessite une connexion internet et peut-être des droits administrateur) ?"
        reply = QMessageBox.question(iface.mainWindow(), 'Dépendances manquantes', msg, QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                import os
                python_exe = sys.executable
                if os.name == 'nt' and "qgis" in python_exe.lower():
                    # Sur Windows, sys.executable pointe souvent vers qgis-bin.exe
                    bin_dir = os.path.dirname(python_exe)
                    if os.path.exists(os.path.join(bin_dir, "python.exe")):
                        python_exe = os.path.join(bin_dir, "python.exe")
                    elif os.path.exists(os.path.join(bin_dir, "python3.exe")):
                        python_exe = os.path.join(bin_dir, "python3.exe")
                        
                subprocess.check_call([python_exe, "-m", "pip", "install"] + missing_packages)
                QMessageBox.information(iface.mainWindow(), 'Succès', 'Les dépendances ont été installées avec succès. Veuillez relancer le plugin.')
                return True
            except subprocess.CalledProcessError as e:
                QMessageBox.critical(iface.mainWindow(), 'Erreur', f"Échec de l'installation des dépendances.\n\nErreur: {e}")
                return False
        else:
            return False
            
    return True

def classFactory(iface):
    """Point d'entrée du plugin pour QGIS."""
    from .ofbilan_plugin import OFBilanPlugin
    
    # On vérifie les dépendances avant d'instancier le plugin
    if not install_dependencies(iface):
        # Si on échoue, on renvoie un plugin "vide" ou factice pour ne pas crasher QGIS
        class DummyPlugin:
            def __init__(self, iface):
                self.iface = iface
            def initGui(self):
                pass
            def unload(self):
                pass
        return DummyPlugin(iface)
        
    return OFBilanPlugin(iface)
