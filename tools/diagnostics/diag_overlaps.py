import geopandas as gpd
import pandas as pd

path = r'c:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\data\sources\sig\CARTO\pve_infractions.gpkg'
gdf = gpd.read_file(path)

# Print columns to know what we have
print('Columns:', gdf.columns.tolist())

# Simulate the user's QGIS filter exactly
if 'PVe_INF-DATE-MIF' in gdf.columns:
    gdf['mif_date'] = pd.to_datetime(gdf['PVe_INF-DATE-MIF'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    # Filter 2025-07-01 to 2026-06-30
    mask_date = (gdf['mif_date'] >= '2025-07-01') & (gdf['mif_date'] <= '2026-06-30')
    gdf_filtered = gdf[mask_date]
    
    if 'PVe_INF-NATINF' in gdf_filtered.columns:
        # Convert to string to safely check for '27742' or '25001'
        natinf_str = gdf_filtered['PVe_INF-NATINF'].astype(str)
        mask_natinf = natinf_str.str.contains('27742|25001', regex=True)
        gdf_filtered = gdf_filtered[mask_natinf]
        
        print(f'\nTotal features matching QGIS filter: {len(gdf_filtered)}')
        
        # Check for empty geometries
        empty_geoms = gdf_filtered.geometry.is_empty | gdf_filtered.geometry.isna()
        print(f'Features with empty/null geometry: {empty_geoms.sum()}')
        
        # Check for overlapping points (exact same coordinates)
        valid_geoms = gdf_filtered[~empty_geoms]
        # Get unique geometries by converting to WKT
        unique_geoms = valid_geoms.geometry.apply(lambda g: g.wkt).nunique()
        print(f'Unique spatial points: {unique_geoms}')
        
        # Detail the duplicates
        counts = valid_geoms.geometry.apply(lambda g: g.wkt).value_counts()
        overlapping = counts[counts > 1]
        if not overlapping.empty:
            print('\nOverlap summary:')
            for wkt, count in overlapping.items():
                print(f'- Point at {wkt} has {count} PVe superposés')
                # Let's list the infractions at this point
                overlapping_features = valid_geoms[valid_geoms.geometry.apply(lambda g: g.wkt) == wkt]
                print(f"  NATINF correspondants : {overlapping_features['PVe_INF-NATINF'].tolist()}")
else:
    print('Column PVe_INF-DATE-MIF not found.')
