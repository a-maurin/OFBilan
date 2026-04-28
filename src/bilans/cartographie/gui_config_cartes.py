#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Interface graphique pour configurer les couches des cartes bilans agrainage/chasse-agrainage.
Lance avec : python gui_config_cartes.py (via Python QGIS)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ajouter le dossier parent au path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# Vérifier PyQGIS avant les imports Qt
try:
    from qgis.core import QgsProject, QgsWkbTypes
    from qgis.PyQt.QtWidgets import (
        QApplication,
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QListWidget,
        QListWidgetItem,
        QLabel,
        QLineEdit,
        QComboBox,
        QPushButton,
        QColorDialog,
        QDoubleSpinBox,
        QSpinBox,
        QSplitter,
        QFrame,
        QScrollArea,
        QWidget,
        QFormLayout,
        QMessageBox,
    )
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QColor
    HAS_QT = True
except ImportError:
    HAS_QT = False


FILTER_TYPES = [
    ("", "Aucun"),
    ("pve", "PVe / Intersection"),
    ("pj", "PJ / Procédures judiciaires"),
    ("point_ctrl_agrainage", "Points contrôle agrainage conformes"),
    ("point_ctrl_chasse", "Points contrôle chasse conformes"),
]

SYMBOL_SHAPES = ["circle", "square", "diamond", "triangle", "cross"]


class LayerConfigWidget(QFrame):
    """Panneau de configuration pour une couche sélectionnée."""
    def __init__(self, layer_name: str, geom_type: str, initial_config=None, parent=None):
        super().__init__(parent)
        self.layer_name = layer_name
        self.geom_type = geom_type
        lc = initial_config
        self.setFrameStyle(QFrame.StyledPanel)
        layout = QFormLayout(self)

        self.legend_edit = QLineEdit()
        self.legend_edit.setPlaceholderText("Texte affiché dans la légende")
        self.legend_edit.setText((lc.legend_label or layer_name) if lc else layer_name)
        layout.addRow("Texte de légende :", self.legend_edit)

        self.filter_combo = QComboBox()
        for val, label in FILTER_TYPES:
            self.filter_combo.addItem(label, val)
        if lc and getattr(lc, "filter_type", None):
            idx = self.filter_combo.findData(lc.filter_type)
            if idx >= 0:
                self.filter_combo.setCurrentIndex(idx)
        self.filter_combo.setToolTip(
            "Type de données associées à cette couche.\n"
            "Par exemple :\n"
            "- PVe / Intersection : infractions issues des procès-verbaux\n"
            "- PJ : procédures judiciaires\n"
            "- Points de contrôle : contrôles conformes (agrainage ou chasse)"
        )
        layout.addRow("Type de données :", self.filter_combo)

        if geom_type == "polygone":
            self.geom_combo = QComboBox()
            self.geom_combo.addItem("Couleur par zone (carte thématique)", "polygon_fill")
            self.geom_combo.addItem("Points au centre des zones", "polygon_centroid")
            if lc and getattr(lc, "geometry_mode", None):
                idx = self.geom_combo.findData(lc.geometry_mode)
                if idx >= 0:
                    self.geom_combo.setCurrentIndex(idx)
            self.geom_combo.setToolTip(
                "Façon de représenter les zones :\n"
                "- Couleur par zone : chaque zone est remplie d'une couleur\n"
                "- Points au centre : un symbole ponctuel placé au centre de chaque zone"
            )
            layout.addRow("Type de carte :", self.geom_combo)

        # Type de renderer
        self.renderer_combo = QComboBox()
        self.renderer_combo.addItem("Même symbole pour tous les objets", "single")
        self.renderer_combo.addItem("Couleurs selon une valeur (gradué)", "graduated")
        self.renderer_combo.addItem("Couleurs par catégorie (catégorisé)", "categorized")
        if lc and getattr(lc, "renderer_type", None):
            idx = self.renderer_combo.findData(lc.renderer_type)
            if idx >= 0:
                self.renderer_combo.setCurrentIndex(idx)
        else:
            # Par défaut, on privilégie le symbole unique
            idx = self.renderer_combo.findData("single")
            if idx >= 0:
                self.renderer_combo.setCurrentIndex(idx)
        self.renderer_combo.setToolTip(
            "Choisissez comment la couche doit être représentée :\n"
            "- Même symbole : tous les objets ont la même couleur et la même forme\n"
            "- Gradué : la couleur varie selon une valeur numérique (ex : nombre de faits)\n"
            "- Catégorisé : une couleur par catégorie de valeur"
        )
        layout.addRow("Type de représentation :", self.renderer_combo)

        # Champ attributaire
        self.field_combo = QComboBox()
        self.field_combo.addItem("— Aucun —", "")
        try:
            proj = QgsProject.instance()
            lyr_list = proj.mapLayersByName(layer_name)
            if lyr_list:
                lyr = lyr_list[0]
                for f in lyr.fields():
                    self.field_combo.addItem(f.name(), f.name())
        except Exception:
            pass
        if lc and getattr(lc, "field", None):
            idx = self.field_combo.findData(lc.field)
            if idx >= 0:
                self.field_combo.setCurrentIndex(idx)
        self.field_combo.setToolTip(
            "Champ de la table d'attributs utilisé pour calculer les couleurs.\n"
            "Laissez « Aucun » si vous utilisez un symbole unique."
        )
        layout.addRow("Champ utilisé :", self.field_combo)

        # Mode de classification (pour graduated)
        self.classif_combo = QComboBox()
        self.classif_combo.addItem("Découpage par quantiles", "quantile")
        self.classif_combo.addItem("Intervalles égaux", "equal_interval")
        self.classif_combo.addItem("Méthode de Jenks", "jenks")
        self.classif_combo.addItem("Seuils définis manuellement", "manual")
        if lc and getattr(lc, "classification_mode", None):
            idx = self.classif_combo.findData(lc.classification_mode)
            if idx >= 0:
                self.classif_combo.setCurrentIndex(idx)
        self.classif_combo.setToolTip(
            "Méthode de découpage des classes lorsque vous utilisez un rendu gradué.\n"
            "Pour un usage simple, laissez « Découpage par quantiles »."
        )
        layout.addRow("Méthode de découpage :", self.classif_combo)

        # Nombre de classes
        self.classes_spin = QSpinBox()
        self.classes_spin.setRange(2, 12)
        self.classes_spin.setValue(getattr(lc, "num_classes", 5) if lc else 5)
        self.classes_spin.setToolTip(
            "Nombre de classes de couleur pour un rendu gradué.\n"
            "Plus il y a de classes, plus la légende est détaillée."
        )
        layout.addRow("Nombre de classes :", self.classes_spin)

        # Palette QGIS
        self.palette_edit = QLineEdit()
        self.palette_edit.setPlaceholderText("Nom de palette QGIS (ex: Blues, YlOrRd)")
        self.palette_edit.setText(getattr(lc, "palette", "Blues") if lc else "Blues")
        self.palette_edit.setToolTip(
            "Palette de couleurs QGIS à utiliser pour les cartes graduées.\n"
            "Exemples : Blues, YlOrRd, RdYlGn."
        )
        layout.addRow("Palette de couleurs :", self.palette_edit)

        # Seuils manuels pour classification_mode == manual
        self.manual_breaks_edit = QLineEdit()
        self.manual_breaks_edit.setPlaceholderText("Ex: 0, 1, 5, 10 (laisser vide pour auto)")
        if lc and getattr(lc, "manual_breaks", None):
            self.manual_breaks_edit.setText(
                ", ".join(str(x) for x in lc.manual_breaks)
            )
        self.manual_breaks_edit.setToolTip(
            "Liste de seuils numériques pour définir vous-même les bornes des classes.\n"
            "Utilisé uniquement si la méthode de découpage est « Seuils définis manuellement »."
        )
        layout.addRow("Seuils manuels :", self.manual_breaks_edit)

        rgb = (lc.color_rgb if lc and getattr(lc, "color_rgb", None) else None) or (31, 120, 180)
        self.color_rgb = tuple(rgb) if hasattr(rgb, "__iter__") else (31, 120, 180)
        self.color_btn = QPushButton("Choisir la couleur…")
        self.color_btn.setStyleSheet(f"background-color: rgb({self.color_rgb[0]}, {self.color_rgb[1]}, {self.color_rgb[2]});")
        self.color_btn.clicked.connect(self._pick_color)
        self.color_btn.setToolTip("Couleur principale utilisée pour les symboles de cette couche.")
        layout.addRow("Couleur du symbole :", self.color_btn)

        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(0.5, 20)
        self.size_spin.setValue(getattr(lc, "symbol_size_mm", 4.0) if lc else 4.0)
        self.size_spin.setSuffix(" mm")
        self.size_spin.setToolTip("Taille des symboles (en millimètres sur la carte imprimée).")
        layout.addRow("Taille du symbole :", self.size_spin)

        self.shape_combo = QComboBox()
        for s in SYMBOL_SHAPES:
            self.shape_combo.addItem(s.capitalize(), s)
        if lc and getattr(lc, "symbol_shape", None):
            idx = self.shape_combo.findData(lc.symbol_shape)
            if idx >= 0:
                self.shape_combo.setCurrentIndex(idx)
        self.shape_combo.setToolTip("Forme du symbole ponctuel (rond, carré, losange, etc.).")
        layout.addRow("Forme du symbole :", self.shape_combo)

    def _pick_color(self):
        color = QColorDialog.getColor(
            QColor(*self.color_rgb),
            self,
            "Couleur du symbole",
        )
        if color.isValid():
            self.color_rgb = (color.red(), color.green(), color.blue())
            self.color_btn.setStyleSheet(
                f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});"
            )

    def get_geometry_mode(self) -> str:
        if self.geom_type == "polygone" and hasattr(self, "geom_combo"):
            return self.geom_combo.currentData()
        return "polygon_fill"

    def get_filter_type(self) -> str:
        return self.filter_combo.currentData()

    def to_layer_config_dict(self) -> dict:
        # Nombre de classes
        try:
            num_classes = int(self.classes_spin.value())
        except Exception:
            num_classes = 5

        # Seuils manuels
        manual_breaks = None
        txt = self.manual_breaks_edit.text().strip()
        if txt:
            parts = [p.strip() for p in txt.replace(";", ",").split(",") if p.strip()]
            try:
                manual_breaks = [float(p) for p in parts]
            except ValueError:
                manual_breaks = None

        return {
            "layer_name": self.layer_name,
            "legend_label": self.legend_edit.text().strip() or self.layer_name,
            "filter_type": self.get_filter_type(),
            "geometry_mode": self.get_geometry_mode(),
            "renderer_type": self.renderer_combo.currentData(),
            "field": self.field_combo.currentData(),
            "classification_mode": self.classif_combo.currentData(),
            "num_classes": num_classes,
            "manual_breaks": manual_breaks,
            "palette": self.palette_edit.text().strip() or "Blues",
            "color_rgb": self.color_rgb,
            "symbol_size_mm": self.size_spin.value(),
            "symbol_shape": self.shape_combo.currentData(),
        }


class ConfigCartesDialog(QDialog):
    """Fenêtre principale de configuration des couches."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration des couches – Production cartographique")
        self.setMinimumSize(720, 520)
        self.resize(880, 620)
        layout = QVBoxLayout(self)

        # Profil
        prof_layout = QHBoxLayout()
        prof_layout.addWidget(QLabel("Profil(s) à configurer:"))
        self.profile_combo = QComboBox()
        # Fusionner les profils de la config effective (YAML) dans CONFIG pour afficher
        # tous les profils (ex. global_usagers) et permettre de les éditer.
        self._merge_effective_profiles_into_config()
        self._init_profiles_combo()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        prof_layout.addWidget(self.profile_combo)
        layout.addLayout(prof_layout)

        # Métadonnées du profil
        meta_widget = QWidget()
        meta_layout = QFormLayout(meta_widget)
        self.profile_title_edit = QLineEdit()
        self.profile_title_edit.setPlaceholderText("Titre principal affiché sur la carte (bandeau)")
        meta_layout.addRow("Titre principal du profil :", self.profile_title_edit)

        self.profile_subtitle_edit = QLineEdit()
        self.profile_subtitle_edit.setPlaceholderText("Sous-titre / période (ex : Campagne 2025-2026)")
        meta_layout.addRow("Sous-titre du profil :", self.profile_subtitle_edit)

        self.profile_date_deb_edit = QLineEdit()
        self.profile_date_deb_edit.setPlaceholderText("YYYY-MM-DD")
        meta_layout.addRow("Date de début du profil :", self.profile_date_deb_edit)

        self.profile_date_fin_edit = QLineEdit()
        self.profile_date_fin_edit.setPlaceholderText("YYYY-MM-DD")
        meta_layout.addRow("Date de fin du profil :", self.profile_date_fin_edit)

        self.dept_edit = QLineEdit()
        self.dept_edit.setPlaceholderText("Code département (ex : 21)")
        meta_layout.addRow("Code département (global) :", self.dept_edit)

        layout.addWidget(meta_widget)

        # Splitter: liste des couches | panneau de config
        splitter = QSplitter(Qt.Horizontal)

        # Liste des couches
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Liste des couches disponibles (cochez celles à afficher sur la carte) :"))
        self.layer_list = QListWidget()
        self.layer_list.setSelectionMode(QListWidget.SingleSelection)
        self.layer_list.itemSelectionChanged.connect(self._on_layer_selected)
        left_layout.addWidget(self.layer_list)
        splitter.addWidget(left)

        # Panneau de configuration
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Paramètres d’affichage pour la couche sélectionnée :"))
        self.config_scroll = QScrollArea()
        self.config_scroll.setWidgetResizable(True)
        self.config_widget = QWidget()
        self.config_layout = QVBoxLayout(self.config_widget)
        self.config_layout.addStretch()
        self.config_scroll.setWidget(self.config_widget)
        right_layout.addWidget(self.config_scroll)
        splitter.addWidget(right)

        splitter.setSizes([300, 500])
        layout.addWidget(splitter)

        self._layer_config_widgets: dict[str, LayerConfigWidget] = {}

        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("Enregistrer la configuration")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save_config)
        btn_layout.addWidget(self.save_btn)
        self.close_btn = QPushButton("Fermer")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        # Charger les valeurs initiales (profil par défaut + couches)
        self._load_profile_metadata()
        self._load_layers()

    def _merge_effective_profiles_into_config(self) -> None:
        """Ajoute à CONFIG.profiles les profils présents dans la config effective (ex. YAML)
        mais absents de config_cartes, afin qu'ils soient visibles et éditables dans la GUI."""
        try:
            from production_cartographique import get_effective_config
            from config_cartes import CONFIG
            effective = get_effective_config()
            for pid, prof in effective.profiles.items():
                if pid not in CONFIG.profiles:
                    CONFIG.profiles[pid] = prof
        except Exception:
            pass

    def _init_profiles_combo(self) -> None:
        """Initialise la liste des profils à partir de la configuration."""
        from config_cartes import CONFIG

        self.profile_combo.clear()
        for pid, prof in CONFIG.profiles.items():
            title_main = getattr(prof, "title_main", "") or ""
            label = title_main or getattr(prof, "title", "") or pid
            self.profile_combo.addItem(label, pid)

    def _load_profile_metadata(self):
        """Charge dans la GUI les métadonnées du profil sélectionné et le code département global."""
        from config_cartes import CONFIG

        profile_val = self.profile_combo.currentData()
        prof = CONFIG.profiles.get(profile_val) if profile_val else None
        if prof:
            self.profile_title_edit.setText(getattr(prof, "title_main", "") or "")
            self.profile_subtitle_edit.setText(getattr(prof, "subtitle", "") or "")
            self.profile_date_deb_edit.setText(getattr(prof, "date_deb", "") or "")
            self.profile_date_fin_edit.setText(getattr(prof, "date_fin", "") or "")
        else:
            self.profile_title_edit.clear()
            self.profile_subtitle_edit.clear()
            self.profile_date_deb_edit.clear()
            self.profile_date_fin_edit.clear()

        dept = getattr(CONFIG, "departement_code", "21")
        self.dept_edit.setText(dept)

    def _load_layers(self):
        """Charge la liste des couches du projet QGIS et pré-sélectionne celles en config."""
        self.layer_list.clear()
        self._layer_config_widgets.clear()

        from config_cartes import CONFIG
        profile_val = self.profile_combo.currentData()
        configured = set()
        prof = CONFIG.profiles.get(profile_val) if profile_val else None
        if prof:
            for k, lcfg in prof.layers.items():
                configured.add(getattr(lcfg, "layer_name", k))

        proj = QgsProject.instance()
        for layer in proj.mapLayers().values():
            if layer.type() != 0:
                continue
            geom = layer.geometryType()
            geom_str = "polygone" if geom == QgsWkbTypes.PolygonGeometry else "points"
            item = QListWidgetItem(f"☐ {layer.name()} ({geom_str})")
            item.setData(Qt.UserRole, layer.name())
            item.setData(Qt.UserRole + 1, geom_str)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            state = Qt.Checked if layer.name() in configured else Qt.Unchecked
            item.setCheckState(state)
            self.layer_list.addItem(item)

    def _on_profile_changed(self):
        """Recharge les métadonnées et la liste avec la pré-sélection du nouveau profil."""
        self._load_profile_metadata()
        self._load_layers()

    def _on_layer_selected(self):
        """Affiche le panneau de config pour la couche sélectionnée."""
        while self.config_layout.count() > 1:
            child = self.config_layout.takeAt(0)
            w = child.widget() if child else None
            if w and w not in self._layer_config_widgets.values():
                w.deleteLater()

        items = self.layer_list.selectedItems()
        if not items:
            return

        item = items[0]
        layer_name = item.data(Qt.UserRole)
        geom_type = item.data(Qt.UserRole + 1)

        if layer_name not in self._layer_config_widgets:
            from config_cartes import CONFIG
            initial = None
            for prof in CONFIG.profiles.values():
                if layer_name in prof.layers:
                    initial = prof.layers[layer_name]
                    break
            self._layer_config_widgets[layer_name] = LayerConfigWidget(
                layer_name, geom_type, initial
            )
        w = self._layer_config_widgets[layer_name]
        self.config_layout.insertWidget(0, w)

    def _get_checked_layers(self) -> list[tuple[str, str]]:
        """Retourne [(nom, geom_type), ...] des couches cochées."""
        result = []
        for i in range(self.layer_list.count()):
            item = self.layer_list.item(i)
            if item.checkState() == Qt.Checked:
                result.append((
                    item.data(Qt.UserRole),
                    item.data(Qt.UserRole + 1),
                ))
        return result

    def _save_config(self):
        """Enregistre la configuration dans config_cartes.py."""
        from config_cartes import CONFIG, LayerSymbologyConfig, ProfileConfig
        from config_cartes_writer import write_config_file

        checked = self._get_checked_layers()
        if not checked:
            QMessageBox.warning(
                self,
                "Aucune couche",
                "Cochez au moins une couche à inclure.",
            )
            return

        # Valeurs communes saisies dans la GUI
        title_main = self.profile_title_edit.text().strip()
        subtitle = self.profile_subtitle_edit.text().strip()
        date_deb_gui = self.profile_date_deb_edit.text().strip()
        date_fin_gui = self.profile_date_fin_edit.text().strip()

        profile_id = self.profile_combo.currentData()
        if not profile_id:
            QMessageBox.warning(
                self,
                "Aucun profil",
                "Aucun profil sélectionné.",
            )
            return

        prof = CONFIG.profiles.get(profile_id)
        if not prof:
            prof = ProfileConfig(
                id=profile_id,
                title=f"Bilan {profile_id}",
                layout_name="Bilan 2025 / 2026 - Agrainage illicite - Côte d'Or",
                output_filename=f"carte_{profile_id}.png",
                date_deb="2025-01-01",
                date_fin="2026-02-05",
                layers={},
            )
            CONFIG.profiles[profile_id] = prof

        # Mettre à jour les métadonnées du profil à partir de la GUI
        if title_main:
            prof.title_main = title_main
        if subtitle:
            prof.subtitle = subtitle
        if date_deb_gui:
            prof.date_deb = date_deb_gui
        if date_fin_gui:
            prof.date_fin = date_fin_gui

        prof.layers.clear()
        for layer_name, geom_type in checked:
            if layer_name in self._layer_config_widgets:
                w = self._layer_config_widgets[layer_name]
                d = w.to_layer_config_dict()
                prof.layers[layer_name] = LayerSymbologyConfig(**d)
            else:
                prof.layers[layer_name] = LayerSymbologyConfig(
                    layer_name=layer_name,
                    legend_label=layer_name,
                )

        # Mettre à jour le code département global si renseigné
        dept_txt = self.dept_edit.text().strip()
        if dept_txt:
            CONFIG.departement_code = dept_txt

        cfg_path = SCRIPT_DIR / "config_cartes.py"
        write_config_file(CONFIG, cfg_path)
        QMessageBox.information(
            self,
            "Configuration enregistrée",
            f"Configuration enregistrée dans ref/carto/config_cartes.py\n"
            f"Profil: {profile_id}\n"
            f"Couches: {len(checked)}",
        )

def run_gui(init_qgis: bool = True):
    """Lance l'interface graphique.
    init_qgis: False si QGIS est déjà initialisé (ex: appel depuis production_cartographique --gui).
    """
    if not HAS_QT:
        print("ERREUR: PyQt/PyQGIS non disponible. Exécutez avec le Python de QGIS.")
        sys.exit(1)

    import production_cartographique as prod
    from config_cartes import CONFIG

    if init_qgis:
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            del os.environ["QT_QPA_PLATFORM"]
        prod.init_qgis_gui()
    app = QApplication.instance() or QApplication(sys.argv)

    project_path = os.getenv("CARTO_PROJECT_QGIS_PATH", CONFIG.project_qgis_path)
    if not prod.load_project(project_path):
        QMessageBox.critical(
            None,
            "Erreur",
            f"Impossible de charger le projet:\n{project_path}",
        )
        sys.exit(1)

    dialog = ConfigCartesDialog()
    dialog._load_layers()
    dialog.exec_()


if __name__ == "__main__":
    run_gui()
