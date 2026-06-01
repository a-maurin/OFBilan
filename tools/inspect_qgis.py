import sys
import os
from pathlib import Path

# Add QGIS to path based on OSGeo4W setup
osgeo4w_root = r"C:\Program Files\QGIS 3.44.8"
sys.path.insert(0, os.path.join(osgeo4w_root, r"apps\qgis-ltr\python"))
sys.path.insert(0, os.path.join(osgeo4w_root, r"apps\Python312\Lib\site-packages"))

os.environ['PATH'] = os.path.join(osgeo4w_root, r"apps\qgis-ltr\bin") + ";" + os.environ['PATH']
os.environ['QGIS_PREFIX_PATH'] = os.path.join(osgeo4w_root, r"apps\qgis-ltr")

from qgis.core import QgsProject, QgsApplication
qgs = QgsApplication([], False)
qgs.initQgis()
p = QgsProject.instance()
p.read(r'C:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\data\sources\sig\bilans_carte.qgz')
for l in p.mapLayers().values():
    if 'point_ctrl' in l.name():
        print(l.name(), [f.name() for f in l.fields()])
qgs.exitQgis()
