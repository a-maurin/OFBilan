"""Diagnostic: intersection between rech_av airpro dossiers and point_ctrl dc_id."""
import sys
sys.path.insert(0, "src")
import pandas as pd
import geopandas as gpd
import unicodedata

# 1. Load ALL rech_av and find airpro dossiers
try:
    df = pd.read_csv("data/sources/rech_av_20260605.csv", sep=";", encoding="utf-8-sig", dtype=str)
except UnicodeDecodeError:
    df = pd.read_csv("data/sources/rech_av_20260605.csv", sep=";", encoding="latin-1", dtype=str)

clean = [unicodedata.normalize('NFKD', str(c)).encode('ASCII','ignore').decode('ASCII').lower().strip() for c in df.columns]
df.columns = clean
col_id = next((c for c in clean if "num" in c and "dossier" in c), None)
col_mots = next((c for c in clean if "mot" in c and "cl" in c), None)
print(f"rech_av: {len(df)} lignes, col_id={col_id}, col_mots={col_mots}")

mask = df[col_mots].astype(str).str.contains("airpro", case=False, na=False)
airpro_ids = set(df.loc[mask, col_id].dropna().astype(str).str.strip().unique())
print(f"Dossiers airpro: {len(airpro_ids)}")
print(f"  Exemples: {list(sorted(airpro_ids))[:10]}")

# 2. Load point_ctrl GPKG (ALL rows)
gpkg = "data/sources/sig/points_de_ctrl_OSCEAN_2026/point_ctrl_20260505_wgs84.gpkg"
gdf = gpd.read_file(gpkg)
print(f"\npoint_ctrl: {len(gdf)} lignes totales")

dc_ids_all = set(gdf["dc_id"].dropna().astype(str).str.strip().unique())
print(f"  dc_id uniques: {len(dc_ids_all)}")

inter = airpro_ids & dc_ids_all
print(f"\nIntersection airpro ∩ point_ctrl (toutes dates): {len(inter)}")
if inter:
    print(f"  Exemples: {list(sorted(inter))[:10]}")
else:
    print("  AUCUNE correspondance => le GPKG ne contient aucun des dossiers airpro")
    # Dates dans les IDs airpro vs point_ctrl
    import re
    def extract_date(oid):
        m = re.match(r"OF(\d{8})", oid)
        return m.group(1) if m else None
    airpro_dates = sorted(set(filter(None, (extract_date(x) for x in airpro_ids))))
    ctrl_dates = sorted(set(filter(None, (extract_date(x) for x in dc_ids_all))))
    print(f"\n  Plage dates dans airpro IDs: {airpro_dates[0] if airpro_dates else '?'} → {airpro_dates[-1] if airpro_dates else '?'}")
    print(f"  Plage dates dans point_ctrl: {ctrl_dates[0] if ctrl_dates else '?'} → {ctrl_dates[-1] if ctrl_dates else '?'}")
