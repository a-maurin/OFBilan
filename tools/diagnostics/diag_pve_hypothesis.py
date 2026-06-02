import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

pve_tub_path = r'data\out\bilan_tub\pve_tub.csv'
pve_tub = pd.read_csv(pve_tub_path, sep=';', dtype=str, encoding='utf-8')
kept_ids = pve_tub['INF-ID'].dropna().unique().tolist()

try:
    raw_pve = pd.read_csv(r'data\sources\Stats_PVe_OFB au 07.04.2026.csv', sep=';', encoding='cp1252', dtype=str)
except:
    raw_pve = pd.read_csv(r'data\sources\Stats_PVe_OFB au 07.04.2026.csv', sep=';', encoding='iso-8859-1', dtype=str)

# Load all communes shapefile to check GPS intersection
communes_shp = r'ref\programme\sig\communes_21\communes.shp'
communes = gpd.read_file(communes_shp)
if communes.crs is None:
    communes.set_crs(epsg=2154, inplace=True)

df = raw_pve[raw_pve['INF-ID'].isin(kept_ids)].copy()

mismatches = []
for _, row in df.iterrows():
    inf_id = row['INF-ID']
    insee_declare = str(row.get('INF-INSEE')).strip().zfill(5)
    
    lat_str = str(row.get('inf_gps_lat', '')).replace(',', '.')
    lon_str = str(row.get('inf_gps_long', '')).replace(',', '.')
    
    try:
        lat = float(lat_str)
        lon = float(lon_str)
        if lat == 0.0 or lon == 0.0 or pd.isna(lat) or pd.isna(lon):
            continue
    except:
        continue
        
    pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(communes.crs).iloc[0]
    
    # Find which commune the point falls into
    intersected = communes[communes.geometry.contains(pt)]
    
    if not intersected.empty:
        insee_gps = intersected.iloc[0]['INSEE_COM'].strip().zfill(5)
        nom_gps = intersected.iloc[0]['NOM_COM']
        if insee_gps != insee_declare:
            mismatches.append(f"PVe {inf_id}: Commune déclarée = {insee_declare}, mais coordonnées GPS tombent dans la commune = {insee_gps} ({nom_gps})")
    else:
        mismatches.append(f"PVe {inf_id}: Coordonnées GPS tombent hors du département 21 (mais commune déclarée = {insee_declare})")

print("Vérification des incohérences GPS vs Commune déclarée :")
for m in mismatches:
    print(m)
print(f"Total incohérences : {len(mismatches)}")
