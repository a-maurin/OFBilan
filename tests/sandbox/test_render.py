import sys
import os

osgeo4w_root = r"C:\Program Files\QGIS 3.44.8"
sys.path.insert(0, os.path.join(osgeo4w_root, r"apps\qgis-ltr\python"))
sys.path.insert(0, os.path.join(osgeo4w_root, r"apps\Python312\Lib\site-packages"))
sys.path.insert(0, r"C:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\src\bilans\cartographie")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from qgis.core import QgsApplication, QgsProject
from production_cartographique import get_effective_config, resolve_profile_layers, apply_layer_symbology, apply_date_filter
from config_cartes import CONFIG

app = QgsApplication([], False)
app.initQgis()

project_path = r"C:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\ref\programme\sig\bilans_carte.qgz"

proj = QgsProject.instance()
proj.read(project_path)

config = get_effective_config()
prof = config.profiles["global_domaines"]

layer = proj.mapLayersByName("point_ctrl_20251231_wgs84")[0]
layer_cfg = prof.layers["point_ctrl_20260205_wgs84"]

apply_layer_symbology(layer, layer_cfg)
apply_date_filter(layer, layer_cfg, prof.date_deb, prof.date_fin, config=config, profile=prof)

renderer = layer.renderer()
print("Renderer type:", renderer.type())
if renderer.type() == "categorizedSymbol":
    print("Expression:", renderer.classAttribute())
    for cat in renderer.categories():
        print("  - Category:", cat.value(), cat.label(), cat.symbol().color().name())

print("Filter:", layer.subsetString())

# Let's count features!
features = [f for f in layer.getFeatures()]
print("Features count:", len(features))

app.exitQgis()
