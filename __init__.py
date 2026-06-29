# -*- coding: utf-8 -*-
import sys
import os
import subprocess
from qgis.PyQt.QtWidgets import QMessageBox, QProgressDialog, QApplication
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsMessageLog, Qgis

def install_dependencies(iface):
    """Vérifie et installe les dépendances requises via pip dans l'environnement QGIS."""
    required_packages = {
        'pandas': 'pandas',
        'reportlab': 'reportlab',
        'fastapi': 'fastapi',
        'uvicorn': 'uvicorn',
        'yaml': 'pyyaml'
    }
    missing_packages = []
    
    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
            
    if missing_packages:
        msg = f"OFBilan a besoin des paquets suivants : {', '.join(missing_packages)}.\n\nVoulez-vous tenter de les installer automatiquement (nécessite une connexion internet et peut-être des droits administrateur) ?"
        reply = QMessageBox.question(iface.mainWindow(), 'Dépendances manquantes', msg, QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            python_exe = sys.executable
            if os.name == 'nt' and "qgis" in python_exe.lower():
                bin_dir = os.path.dirname(python_exe)
                if os.path.exists(os.path.join(bin_dir, "python.exe")):
                    python_exe = os.path.join(bin_dir, "python.exe")
                elif os.path.exists(os.path.join(bin_dir, "python3.exe")):
                    python_exe = os.path.join(bin_dir, "python3.exe")
                    
            progress = QProgressDialog("Préparation de l'installation...", "Annuler", 0, 0, iface.mainWindow())
            progress.setWindowTitle("OFBilan - Installation des dépendances")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()
            
            log_file_path = os.path.join(os.path.dirname(__file__), "install_dependencies.log")
            
            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = 0x08000000  # CREATE_NO_WINDOW
                
            try:
                QgsMessageLog.logMessage(f"Début de l'installation, log: {log_file_path}", "OFBilan", Qgis.Info)
                with open(log_file_path, "w", encoding="utf-8") as log_file:
                    process = subprocess.Popen(
                        [python_exe, "-m", "pip", "install"] + missing_packages,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        startupinfo=startupinfo,
                        creationflags=creationflags
                    )
                    
                    while True:
                        output = process.stdout.readline()
                        if output == '' and process.poll() is not None:
                            break
                        if output:
                            log_file.write(output)
                            progress.setLabelText(f"Installation en cours...\n{output.strip()[:80]}")
                            QApplication.processEvents()
                            
                        if progress.wasCanceled():
                            process.terminate()
                            QgsMessageLog.logMessage("Installation annulée par l'utilisateur.", "OFBilan", Qgis.Warning)
                            return False
                            
                    rc = process.poll()
                    
                if rc == 0:
                    QgsMessageLog.logMessage("Installation des dépendances réussie.", "OFBilan", Qgis.Success)
                    QMessageBox.information(iface.mainWindow(), 'Succès', 'Les dépendances ont été installées avec succès. Veuillez relancer QGIS.')
                    return True
                else:
                    QgsMessageLog.logMessage(f"Erreur d'installation. Voir {log_file_path}", "OFBilan", Qgis.Critical)
                    QMessageBox.critical(iface.mainWindow(), 'Erreur', f"Échec de l'installation.\n\nConsultez le fichier de log : {log_file_path}")
                    return False
                    
            except Exception as e:
                QgsMessageLog.logMessage(f"Exception lors de l'installation: {str(e)}", "OFBilan", Qgis.Critical)
                QMessageBox.critical(iface.mainWindow(), 'Erreur', f"Une erreur inattendue est survenue:\n\n{e}")
                return False
            finally:
                progress.close()
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
