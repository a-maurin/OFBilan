import sys
import os

osgeo4w_root = r"C:\Program Files\QGIS 3.44.8"
sys.path.insert(0, os.path.join(osgeo4w_root, r"apps\qgis-ltr\python"))
sys.path.insert(0, os.path.join(osgeo4w_root, r"apps\Python312\Lib\site-packages"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from qgis.core import QgsApplication, QgsProject, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils, QgsFeatureRequest

app = QgsApplication([], False)
app.initQgis()

project_path = r"C:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\ref\programme\sig\bilans_carte.qgz"

proj = QgsProject.instance()
proj.read(project_path)

layer = proj.mapLayersByName("point_ctrl_20251231_wgs84")[0]

ctx = QgsExpressionContext()
ctx.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))

expr1 = QgsExpression('to_date("date_ctrl") >= to_date(\'2025-01-01\')')
expr2 = QgsExpression('"date_ctrl" >= to_date(\'2025-01-01\')')

req = QgsFeatureRequest()
req.setFilterExpression('"num_depart" = \'21\'')

count1 = 0
count2 = 0
for i, f in enumerate(layer.getFeatures(req)):
    ctx.setFeature(f)
    if expr1.evaluate(ctx): count1 += 1
    if expr2.evaluate(ctx): count2 += 1
    if i >= 100: break

print("Count with to_date(date_ctrl):", count1)
print("Count with date_ctrl >= to_date(...):", count2)

app.exitQgis()
