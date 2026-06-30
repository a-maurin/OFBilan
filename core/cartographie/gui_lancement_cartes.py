#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Petite interface graphique de lancement pour la production cartographique.

Cette fenêtre sert uniquement à ouvrir l'interface de paramétrage des cartes.
La génération des cartes se fait ensuite en mode batch (scripts ou .bat),
sans interaction, à partir des réglages enregistrés.

À exécuter avec le Python de QGIS (OSGeo4W), par exemple via lancer_osgeo4w.bat.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from production_cartographique import init_qgis_gui
from gui_config_cartes import run_gui as run_config_gui


SCRIPT_DIR = Path(__file__).resolve().parent


class LauncherDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Production cartographique – Paramétrage")
        self.setMinimumWidth(420)

        main_layout = QVBoxLayout(self)

        info_label = QLabel(
            "Cette fenêtre permet d'ouvrir l'interface de configuration des cartes.\n\n"
            "La génération des cartes s'appuie uniquement sur ces réglages et se fait "
            "ensuite en mode automatisé (scripts ou fichiers .bat), sans saisie "
            "supplémentaire lors de l'export."
        )
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)

        btn_box = QDialogButtonBox()
        self.config_btn = QPushButton("Ouvrir la configuration des cartes")
        self.close_btn = QPushButton("Fermer")
        btn_box.addButton(self.config_btn, QDialogButtonBox.AcceptRole)
        btn_box.addButton(self.close_btn, QDialogButtonBox.RejectRole)
        main_layout.addWidget(btn_box)

        self.config_btn.clicked.connect(self._on_config_clicked)
        self.close_btn.clicked.connect(self.reject)

    def _on_config_clicked(self) -> None:
        # QGIS est déjà initialisé en amont par init_qgis_gui().
        run_config_gui(init_qgis=False)


def main() -> None:
    # S'assurer que l'on n'est pas en mode offscreen pour l'interface
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        del os.environ["QT_QPA_PLATFORM"]

    # Initialisation de QGIS avec support GUI (mais sans ouvrir QGIS lui-même)
    qgs_app = init_qgis_gui()
    app = QApplication.instance() or QApplication(sys.argv)

    dlg = LauncherDialog()
    dlg.exec_()

    qgs_app.exitQgis()


if __name__ == "__main__":
    main()

