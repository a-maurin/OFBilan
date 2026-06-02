import sys
from pathlib import Path
import pandas as pd
import logging

PROJECT_ROOT = Path("c:/Users/aguirre.maurin/Documents/GitHub/Bilans_production")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bilans.common.chargeurs_donnees import (
    load_point_ctrl,
    load_tub_pnf_codes,
    ensure_insee_from_communes_shp,
    pnf_sig_union_membership_mask
)
from bilans.engine.orchestrateur_profils import _mask_insee_in_pnf_codes

def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("debug_pnf")
    
    date_deb = pd.to_datetime("2026-01-01")
    date_fin = pd.to_datetime("2026-05-05")
    
    print("Loading point_ctrl...")
    # Charger sans filtre dept
    df = load_point_ctrl(PROJECT_ROOT, date_deb=date_deb, date_fin=date_fin)
    print(f"Total points loaded for period: {len(df)}")
    
    _, pnf_codes = load_tub_pnf_codes(PROJECT_ROOT)
    
    df = ensure_insee_from_communes_shp(df, PROJECT_ROOT, context="debug", log=logger)
    
    mask_insee = _mask_insee_in_pnf_codes(df, pnf_codes)
    mask_sig = pnf_sig_union_membership_mask(df, PROJECT_ROOT, log=logger)
    
    print(f"Points with mask_insee = True: {mask_insee.sum()}")
    print(f"Points with mask_sig = True: {mask_sig.sum()}")
    
    mask_both = mask_insee & mask_sig
    print(f"Points with BOTH true: {mask_both.sum()}")
    
    mask_any = mask_insee | mask_sig
    print(f"Total points kept (mask_any): {mask_any.sum()}")
    
    df_kept = df[mask_any]
    print("\nBreakdown by department for kept points:")
    if 'num_depart' in df_kept.columns:
        print(df_kept['num_depart'].value_counts())
    
    print("\nBreakdown by mask:")
    print(f"Only INSEE: {(mask_insee & ~mask_sig).sum()}")
    print(f"Only SIG: {(mask_sig & ~mask_insee).sum()}")
    
    # Analyze the ones that are ONLY INSEE
    # Check coeur vs AOA
    import geopandas as gpd
    from bilans.common.chargeurs_donnees import load_pnf_coeur_gdf, load_pnf_aoa_gdf
    
    coeur = load_pnf_coeur_gdf(PROJECT_ROOT)
    aoa = load_pnf_aoa_gdf(PROJECT_ROOT)
    
    df_21 = df_kept[df_kept['num_depart'] == '21'].copy()
    print(f"\nAnalyzing {len(df_21)} points for dept 21:")
    
    # Needs geometry to do spatial join
    from shapely.geometry import Point
    
    def create_geom(row):
        try:
            x = float(row.get('x', row.get('x_wgs84', 0)))
            y = float(row.get('y', row.get('y_wgs84', 0)))
            if pd.isna(x) or pd.isna(y): return None
            return Point(x, y)
        except: return None
        
    df_21['geometry'] = df_21.apply(create_geom, axis=1)
    gdf_21 = gpd.GeoDataFrame(df_21, geometry='geometry', crs="EPSG:4326")
    
    if not coeur.empty:
        coeur = coeur.to_crs("EPSG:4326")
        in_coeur = gpd.sjoin(gdf_21, coeur, predicate='intersects')
        print(f"Points in Coeur (dept 21): {len(in_coeur.index.unique())}")
    
    if not aoa.empty:
        aoa = aoa.to_crs("EPSG:4326")
        in_aoa = gpd.sjoin(gdf_21, aoa, predicate='intersects')
        print(f"Points in AOA (dept 21): {len(in_aoa.index.unique())}")
        
    print("\nBreakdown of the 44 points by resultat:")
    if 'resultat' in df_21.columns:
        print(df_21['resultat'].value_counts(dropna=False))
        
    print("\nBreakdown of the 44 points by theme:")
    if 'theme' in df_21.columns:
        print(df_21['theme'].value_counts(dropna=False))
        
    unique_geoms = df_21[['x', 'y']].drop_duplicates()
    print(f"\nNumber of visually distinct points (unique coordinates) for dept 21: {len(unique_geoms)}")

if __name__ == "__main__":
    main()



