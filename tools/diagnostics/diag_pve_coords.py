import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import math

pve_tub_path = r'data\out\bilan_tub\pve_tub.csv'
pve_tub = pd.read_csv(pve_tub_path, sep=';', dtype=str, encoding='utf-8')
kept_ids = pve_tub['INF-ID'].dropna().unique().tolist()

try:
    raw_pve = pd.read_csv(r'data\sources\Stats_PVe_OFB au 07.04.2026.csv', sep=';', encoding='cp1252', dtype=str)
except:
    raw_pve = pd.read_csv(r'data\sources\Stats_PVe_OFB au 07.04.2026.csv', sep=';', encoding='iso-8859-1', dtype=str)

df = raw_pve[raw_pve['INF-ID'].isin(kept_ids)]
for _, row in df.iterrows():
    try:
        lat = float(str(row.get('inf_gps_lat')).replace(',', '.'))
        lon = float(str(row.get('inf_gps_long')).replace(',', '.'))
        if lat != 0 and lon != 0 and not math.isnan(lat) and not math.isnan(lon):
            pt = gpd.GeoSeries([Point(lon, lat)], crs='EPSG:4326').to_crs('EPSG:2154').iloc[0]
            print(f"ID {row['INF-ID']}: {pt.x}, {pt.y}")
    except Exception as e:
        pass
