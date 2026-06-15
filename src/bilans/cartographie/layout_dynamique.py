# -*- coding: utf-8 -*-
"""
Génération dynamique du layout cartographique QGIS sans dépendance au projet .qgz.
"""

from qgis.core import (
    QgsPrintLayout,
    QgsLayoutItemMap,
    QgsLayoutItemLabel,
    QgsLayoutItemScaleBar,
    QgsLayoutItemPicture,
    QgsUnitTypes,
    QgsLayoutSize,
    QgsLayoutPoint,
    QgsProject,
    QgsTextFormat
)
from qgis.PyQt.QtGui import QFont
def build_dynamic_layout(prof, proj: QgsProject, title_text: str) -> QgsPrintLayout:
    """
    Crée un layout vierge A4 Paysage et y instancie les composants de base.
    """
    layout = QgsPrintLayout(proj)
    layout.initializeDefaults()
    layout.setName(f"Dynamic_Layout_{prof.id}")

    # Configuration de la page (A4 Paysage = 297x210 mm)
    page = layout.pageCollection().page(0)
    page.setPageSize(QgsLayoutSize(297, 210, QgsUnitTypes.LayoutMillimeters))

    # 1. Carte principale (Map)
    map_item = QgsLayoutItemMap(layout)
    map_item.setId("carte_principale")
    # Marge adaptée (remontée car plus de bandeau en haut)
    map_item.attemptMove(QgsLayoutPoint(5, 15))
    map_item.attemptResize(QgsLayoutSize(230, 190))
    map_item.setFrameEnabled(True)
    layout.addLayoutItem(map_item)

    # 2. Titre principal
    title_item = QgsLayoutItemLabel(layout)
    title_item.setId("titre_principal")
    title_item.setText(title_text)
    
    text_format = QgsTextFormat()
    text_format.setFont(QFont("Arial", 16, QFont.Bold))
    title_item.setTextFormat(text_format)
    
    title_item.attemptMove(QgsLayoutPoint(5, 3))
    title_item.attemptResize(QgsLayoutSize(287, 10))
    layout.addLayoutItem(title_item)

    # 3. Échelle (ScaleBar)
    scalebar = QgsLayoutItemScaleBar(layout)
    scalebar.setId("echelle")
    scalebar.setLinkedMap(map_item)
    scalebar.setUnits(QgsUnitTypes.DistanceKilometers)
    scalebar.setNumberOfSegmentsLeft(0)
    scalebar.setNumberOfSegments(2)
    scalebar.setUnitsPerSegment(10.0)
    scalebar.setStyle('Double Box')
    
    # Ajuster la police de l'échelle pour qu'elle soit lisible
    scale_font = QFont("Arial", 12)
    text_format_scale = QgsTextFormat()
    text_format_scale.setFont(scale_font)
    scalebar.setTextFormat(text_format_scale)
    scalebar.update()
    
    # Placement en bas à droite de la CARTE (à l'intérieur du cadre)
    scalebar.attemptMove(QgsLayoutPoint(180, 190))
    layout.addLayoutItem(scalebar)

    return layout
