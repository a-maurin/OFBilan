import sys
import os

osgeo4w_root = r"C:\Program Files\QGIS 3.44.8"
sys.path.insert(0, os.path.join(osgeo4w_root, r"apps\qgis-ltr\python"))
sys.path.insert(0, os.path.join(osgeo4w_root, r"apps\Python312\Lib\site-packages"))

from qgis.core import QgsApplication, QgsVectorLayer, QgsFeatureRequest

qgs = QgsApplication([], False)
qgs.initQgis()

layer = QgsVectorLayer(r"C:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\data\sources\sig\points_infractions_pj\localisation_infrac_FAITS_20260505.gpkg", "test", "ogr")
req = QgsFeatureRequest()
for i, f in enumerate(layer.getFeatures(req)):
    print(list(f.fields().names()))
    break
qgs.exitQgis()
