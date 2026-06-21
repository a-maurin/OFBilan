import os
from qgis.core import QgsApplication, QgsProject, QgsVectorLayer, QgsLegendPatchShape, QgsStyle

QgsApplication.setPrefixPath("C:/OSGeo4W/apps/qgis", True)
qgs = QgsApplication([], False)
qgs.initQgis()

print("QGIS Init OK")
layer = QgsVectorLayer("Polygon", "test", "memory")
print("Layer created")

legend = layer.legend()
print(type(legend))

try:
    style = QgsStyle.defaultStyle()
    print("Style default:", style)
    patch = style.legendPatchShape(0, style.legendPatchShapeNames()[0])
    print("Patch shape:", patch)
except Exception as e:
    print("Error:", e)

qgs.exitQgis()
