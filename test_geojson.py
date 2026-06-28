import sys
import json
import traceback
import os
from pathlib import Path

project_root = r"c:\Users\aguirre.maurin\Documents\GitHub\OFBilan"
sys.path.insert(0, str(Path(project_root) / "src"))

out_path = Path(project_root) / "test_output.txt"
with open(out_path, "w", encoding="utf-8") as f:
    try:
        from ofbilan.common.chargeurs_donnees import load_pnf_aoa_gdf
        gdf_boundary = load_pnf_aoa_gdf(Path(project_root))
        if not gdf_boundary.empty:
            if gdf_boundary.crs is None:
                gdf_boundary.set_crs(epsg=2154, inplace=True)
            gdf_boundary_wgs84 = gdf_boundary.to_crs("EPSG:4326")
            geojson_data = json.loads(gdf_boundary_wgs84.to_json())
            f.write(f"SUCCESS! Length of features: {len(geojson_data.get('features', []))}\n")
        else:
            f.write("EMPTY GDF\n")
    except Exception as e:
        f.write("ERROR:\n")
        traceback.print_exc(file=f)
