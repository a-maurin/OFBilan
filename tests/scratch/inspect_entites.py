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

import pandas as pd
import geopandas as gpd
from pathlib import Path

root = Path(r"c:\Users\aguirre.maurin\Documents\GitHub\OFBilan-Plugin-QGIS")
sources = root / "data" / "sources"

# 1. PVe
pve_files = list(sources.glob("Stats_PVe_OFB*.xlsx")) + list(sources.glob("Stats_PVe_OFB*.ods")) + list(sources.glob("Stats_PVe_OFB*.csv"))
if pve_files:
    latest_pve = sorted(pve_files, key=lambda f: f.stat().st_mtime)[-1]
    print("PVe file:", latest_pve.name)
    df_pve = pd.read_excel(latest_pve) if latest_pve.suffix == ".xlsx" else pd.read_csv(latest_pve, sep=";")
    cols = [c for c in df_pve.columns if "UNITE" in c.upper() or "ENTITE" in c.upper() or "SERVICE" in c.upper() or "AGENT" in c.upper()]
    print("PVe columns matching UNITE/ENTITE:", cols)
    if "UNITE_libelle" in df_pve.columns:
        print("PVe UNITE_libelle sample values:")
        print(df_pve["UNITE_libelle"].dropna().value_counts().head(20))

# 2. PEJ (localisation_infrac_FAITS_*.gpkg)
pej_files = list((sources / "sig" / "point_infraction_PJ").glob("localisation_infrac_FAITS_*.gpkg"))
if pej_files:
    latest_pej = sorted(pej_files, key=lambda f: f.stat().st_mtime)[-1]
    print("\nPEJ file:", latest_pej.name)
    gdf_pej = gpd.read_file(latest_pej)
    print("PEJ columns matching entite:", [c for c in gdf_pej.columns if "entite" in c.lower()])
    if "entite" in gdf_pej.columns:
        print("PEJ entite sample values:")
        print(gdf_pej["entite"].dropna().value_counts().head(20))

# 3. Points ctrl (point_ctrl_*_wgs84.gpkg)
ctrl_dirs = list((sources / "sig").glob("points_de_ctrl_OSCEAN_*"))
ctrl_files = []
for d in ctrl_dirs:
    ctrl_files.extend(d.glob("point_ctrl_*_wgs84.gpkg"))
if ctrl_files:
    latest_ctrl = sorted(ctrl_files, key=lambda f: f.stat().st_mtime)[-1]
    print("\nCtrl file:", latest_ctrl.name)
    gdf_ctrl = gpd.read_file(latest_ctrl)
    print("Ctrl columns matching entite:", [c for c in gdf_ctrl.columns if "entite" in c.lower() or "entit" in c.lower()])
    for col in [c for c in gdf_ctrl.columns if "entit" in c.lower()]:
        print(f"Ctrl {col} sample values:")
        print(gdf_ctrl[col].dropna().value_counts().head(20))
