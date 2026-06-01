import sys
import os

osgeo4w_root = r"C:\Program Files\QGIS 3.44.8"
sys.path.insert(0, os.path.join(osgeo4w_root, r"apps\qgis-ltr\python"))
sys.path.insert(0, os.path.join(osgeo4w_root, r"apps\Python312\Lib\site-packages"))
sys.path.insert(0, r"C:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\src\bilans\cartographie")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from qgis.core import QgsApplication, QgsProject, QgsFeatureRequest

app = QgsApplication([], False)
app.initQgis()

project_path = r"C:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\ref\programme\sig\bilans_carte.qgz"

proj = QgsProject.instance()
proj.read(project_path)

layer = proj.mapLayersByName("point_ctrl_20251231_wgs84")[0]

req = QgsFeatureRequest()
req.setFilterExpression('"num_depart" = \'21\'')
for i, f in enumerate(layer.getFeatures(req)):
    print(f["date_ctrl"])
    if i >= 10:
        break

app.exitQgis()
