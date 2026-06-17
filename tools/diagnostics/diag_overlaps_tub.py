import geopandas as gpd
import pandas as pd
from pathlib import Path
import sys

# Charger les codes INSEE de la zone TUB
sys.path.append(r'c:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\src')
from ofbilan.engine.orchestrateur_profils import load_tub_pnf_codes
tub_codes, _ = load_tub_pnf_codes(Path(r'c:\Users\aguirre.maurin\Documents\GitHub\Bilans_production'))

path = r'c:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\data\sources\sig\CARTO\pve_infractions.gpkg'
gdf = gpd.read_file(path)

# Simulate QGIS filter
gdf['mif_date'] = pd.to_datetime(gdf['PVe_INF-DATE-MIF'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
mask_date = (gdf['mif_date'] >= '2025-07-01') & (gdf['mif_date'] <= '2026-06-30')
gdf_filtered = gdf[mask_date].copy()

natinf_str = gdf_filtered['PVe_INF-NATINF'].astype(str)
mask_natinf = natinf_str.str.contains('27742|25001', regex=True)
gdf_filtered = gdf_filtered[mask_natinf]

# Ne garder que ceux dont le code INSEE est dans la zone TUB (pour simuler ce qui se passe géographiquement dans la zone)
if 'INSEE_COM' in gdf_filtered.columns:
    insee = gdf_filtered['INSEE_COM'].str.zfill(5)
    gdf_tub = gdf_filtered[insee.isin(tub_codes)]
    print(f'Total PVe in TUB zone (via INSEE): {len(gdf_tub)}')
    unique = gdf_tub.geometry.apply(lambda g: g.wkt).nunique()
    print(f'Unique spatial points in TUB zone: {unique}')
    
    # Detail overlaps
    counts = gdf_tub.geometry.apply(lambda g: g.wkt).value_counts()
    for wkt, count in counts[counts > 1].items():
        print(f'OVERLAP: {count} PVe au point {wkt}')
else:
    print('Pas de colonne INSEE_COM')
