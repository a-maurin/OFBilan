# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
# sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
# Voir la Licence Publique Générale GNU pour plus de détails.
#
# CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
# Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
# intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
# clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
# doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
# de l'auteur original (Aguirre MAURIN).

#
import sys
import os
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(r"c:\Users\aguirre.maurin\Documents\GitHub\OFBilan\src\ofbilan\cartographie")
PROJECT_ROOT = Path(r"c:\Users\aguirre.maurin\Documents\GitHub\OFBilan")
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from qgis.core import QgsApplication, QgsProject
os.environ["QT_QPA_PLATFORM"] = "offscreen"
app = QgsApplication([], False)
app.initQgis()

try:
    from ofbilan.cartographie.production_cartographique import get_effective_config, resolve_layers_for_config, resolve_profile_layers
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
                    from ofbilan.cartographie.production_cartographique import apply_date_filter
                    from ofbilan.cartographie.production_cartographique import _ConfigDeptOverride
                    carto_config = _ConfigDeptOverride(CONFIG, dept_code)
                    apply_date_filter(layer, lcfg, prof.date_deb, prof.date_fin, config=carto_config, profile=prof)
                    print(f"     Subset string applied: {layer.subsetString()}")
                    print(f"     Feature count after subset: {layer.featureCount()}")
                else:
                    print(f"  -> NOT resolved (source: {source})")
finally:
    app.exitQgis()