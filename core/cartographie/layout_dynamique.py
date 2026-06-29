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
    QgsLayoutItemShape,
    QgsUnitTypes,
    QgsLayoutSize,
    QgsLayoutPoint,
    QgsProject,
    QgsTextFormat,
    QgsFillSymbol
)
from qgis.PyQt.QtGui import QFont, QColor
from qgis.PyQt.QtCore import Qt

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

    # Bandeau Titre (Haut)
    bandeau_titre = QgsLayoutItemShape(layout)
    bandeau_titre.setId("bandeau_titre")
    bandeau_titre.setShapeType(QgsLayoutItemShape.Rectangle)
    sym_haut = QgsFillSymbol.createSimple({'color': '0,61,165,255', 'outline_style': 'no'})
    bandeau_titre.setSymbol(sym_haut)
    bandeau_titre.attemptMove(QgsLayoutPoint(0, 0))
    bandeau_titre.attemptResize(QgsLayoutSize(297, 10))
    layout.addLayoutItem(bandeau_titre)

    # Titre principal (Centré sur le bandeau bleu)
    title_item = QgsLayoutItemLabel(layout)
    title_item.setId("titre_principal")
    title_item.setText(title_text)
    title_item.setVAlign(Qt.AlignVCenter)
    title_item.setHAlign(Qt.AlignHCenter)
    text_format = QgsTextFormat()
    text_format.setFont(QFont("Arial", 16, QFont.Bold))
    text_format.setColor(QColor(255, 255, 255))
    title_item.setTextFormat(text_format)
    title_item.attemptMove(QgsLayoutPoint(0, 0))
    title_item.attemptResize(QgsLayoutSize(297, 10))
    layout.addLayoutItem(title_item)

    # Bandeau Source (Bas)
    bandeau_source = QgsLayoutItemShape(layout)
    bandeau_source.setId("bandeau_source")
    bandeau_source.setShapeType(QgsLayoutItemShape.Rectangle)
    sym_bas = QgsFillSymbol.createSimple({'color': '0,61,165,255', 'outline_style': 'no'})
    bandeau_source.setSymbol(sym_bas)
    bandeau_source.attemptMove(QgsLayoutPoint(0, 200))
    bandeau_source.attemptResize(QgsLayoutSize(232, 10))
    layout.addLayoutItem(bandeau_source)

    # 1. Carte principale (Map)
    map_item = QgsLayoutItemMap(layout)
    map_item.setId("carte_principale")
    map_item.attemptMove(QgsLayoutPoint(0, 10))
    map_item.attemptResize(QgsLayoutSize(232, 190))
    map_item.setFrameEnabled(False)
    layout.addLayoutItem(map_item)

    # 3. Échelle (ScaleBar)
    scalebar = QgsLayoutItemScaleBar(layout)
    scalebar.setId("echelle")
    scalebar.setLinkedMap(map_item)
    scalebar.setUnits(QgsUnitTypes.DistanceKilometers)
    scalebar.setNumberOfSegmentsLeft(0)
    try:
        from qgis.core import QgsScaleBarSettings
        scalebar.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeFitWidth)
        scalebar.setMinimumBarWidth(30)
        scalebar.setMaximumBarWidth(80)
    except Exception:
        scalebar.applyDefaultSize()
    scalebar.setStyle('Double Box')
    
    scale_font = QFont("Arial", 12)
    text_format_scale = QgsTextFormat()
    text_format_scale.setFont(scale_font)
    scalebar.setTextFormat(text_format_scale)
    scalebar.update()
    
    # Placement en bas à gauche sur la carte
    scalebar.attemptMove(QgsLayoutPoint(5, 185))
    layout.addLayoutItem(scalebar)

    # 4. Flèche du nord (North Arrow)
    north_arrow = QgsLayoutItemPicture(layout)
    north_arrow.setId("fleche_du_nord")
    north_arrow.setPicturePath(":/images/north_arrows/layout_default_north_arrow.svg")
    north_arrow.attemptMove(QgsLayoutPoint(9.53, 158.09))
    north_arrow.attemptResize(QgsLayoutSize(11.3, 18.0))
    layout.addLayoutItem(north_arrow)

    return layout
