import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

project_path = Path(r"c:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\ref\programme\sig\bilans_carte.qgz")

if not project_path.exists():
    print("Project not found at", project_path)
    exit(1)

with zipfile.ZipFile(project_path) as z:
    for name in z.namelist():
        if name.endswith(".qgs"):
            xml_data = z.read(name)
            root = ET.fromstring(xml_data)
            print("--- Map Layers in QGIS Project ---")
            for maplayer in root.iter("maplayer"):
                layername = maplayer.find("layername")
                type_ = maplayer.get("type")
                provider = maplayer.find("provider")
                datasource = maplayer.find("datasource")
                if layername is not None:
                    p_text = provider.text if provider is not None else ""
                    ds_text = datasource.text if datasource is not None else ""
                    print(f"Name: {layername.text} | Type: {type_} | Provider: {p_text} | DataSource: {ds_text[:120]}")
