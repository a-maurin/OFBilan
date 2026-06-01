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
res = proj.read(project_path)
print("Project loaded:", res)

layer = None
for l in proj.mapLayers().values():
    if l.name() == "point_ctrl_20251231_wgs84":
        layer = l
        break

if not layer:
    for l in proj.mapLayers().values():
        if "point_ctrl" in l.name():
            layer = l
            break

print("Layer found:", layer.name() if layer else "None")
if layer:
    print("Fields:", [f.name() for f in layer.fields()])

    config_field = "coalesce(\"domaine\", 'Hors domaine')"
    expr = QgsExpression(config_field)
    ctx = QgsExpressionContext()
    ctx.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))

    vals = set()
    req = QgsFeatureRequest()
    req.setFilterExpression('"num_depart" = \'21\'')

    count = 0
    for i, f in enumerate(layer.getFeatures(req)):
        ctx.setFeature(f)
        v = expr.evaluate(ctx)
        if v is not None:
            vals.add(str(v))
        count += 1
        if i >= 500:
            break

    print("Evaluated categories:", vals)
    print("Checked features:", count)

app.exitQgis()
