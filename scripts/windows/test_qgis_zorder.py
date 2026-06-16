import sys
import os
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(r"c:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\src\bilans\cartographie")
PROJECT_ROOT = Path(r"c:\Users\aguirre.maurin\Documents\GitHub\Bilans_production")
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from qgis.core import QgsApplication, QgsProject
os.environ["QT_QPA_PLATFORM"] = "offscreen"
app = QgsApplication([], False)
app.initQgis()

try:
    from bilans.cartographie.production_cartographique import get_effective_config, resolve_layers_for_config, resolve_profile_layers
    CONFIG = get_effective_config()
    project_path = CONFIG.project_qgis_path
    print(f"Project QGIS path: {project_path}")
    
    proj = QgsProject.instance()
    if not proj.read(project_path):
        print("Failed to read QGIS project")
        sys.exit(1)
        
    print("\n--- Project Layers ---")
    for layer in proj.mapLayers().values():
        print(f"Name: {layer.name()}, Valid: {layer.isValid()}, Type: {layer.publicSource()}")

    # Check global_domaines profile
    print("\n--- Testing global_domaines profile ---")
    prof = CONFIG.profiles.get("global_domaines")
    if prof:
        prof.date_deb = "2026-01-01"
        prof.date_fin = "2026-06-15"
        dept_code = "39"
        
        # Resolve layers
        available_names = [lyr.name() for lyr in proj.mapLayers().values()]
        layers_to_process = resolve_profile_layers(prof)
        for lname, lcfg in layers_to_process.items():
            base_prefix = getattr(prof, "_export_prefix", None) or prof.id
            profil_prefix = f"{base_prefix}_{dept_code}"
            
            resolved_infos = resolve_layers_for_config(
                lname,
                lcfg,
                available_names=available_names,
                date_deb=prof.date_deb,
                date_fin=prof.date_fin,
                dept_code=dept_code,
                profil_prefix=profil_prefix,
            )
            print(f"Key: {lname}, Configured: {lcfg.layer_name}")
            for layer, rname, source in resolved_infos:
                if layer:
                    print(f"  -> Resolved to: {rname} (source: {source}), valid: {layer.isValid()}")
                    print(f"     URI: {layer.source()}")
                    print(f"     Geometry type: {layer.geometryType()}")
                    print(f"     Feature count: {layer.featureCount()}")
                    # Apply filter
                    from bilans.cartographie.production_cartographique import apply_date_filter
                    from bilans.cartographie.production_cartographique import _ConfigDeptOverride
                    carto_config = _ConfigDeptOverride(CONFIG, dept_code)
                    apply_date_filter(layer, lcfg, prof.date_deb, prof.date_fin, config=carto_config, profile=prof)
                    print(f"     Subset string applied: {layer.subsetString()}")
                    print(f"     Feature count after subset: {layer.featureCount()}")
                else:
                    print(f"  -> NOT resolved (source: {source})")
finally:
    app.exitQgis()
