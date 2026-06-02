import pandas as pd
from pathlib import Path
from bilans.common.chargeurs_donnees import load_pve, load_point_ctrl
from bilans.engine.orchestrateur_profils import _filter_pve, load_tub_pnf_codes, _apply_restrict_geo_tub
import yaml
import logging

root = Path('.')
tub_codes, _ = load_tub_pnf_codes(root)

with open('config/profils_bilan/tub.yaml', 'r', encoding='utf-8') as f:
    tub_cfg = yaml.safe_load(f)

pve = load_pve(root, dept_code='21', date_deb='2025-07-01', date_fin='2026-06-01')
pve_filtered = _filter_pve(pve, tub_cfg)

import geopandas as gpd
shp = root / 'ref' / 'programme' / 'sig' / 'communes_pnf' / 'communes_PNF_centroides.shp'
cen = gpd.read_file(shp)
cen_insee = cen['INSEE_COM'].astype(str).str.zfill(5).unique()

pve_filtered['_insee_pve'] = pve_filtered['INF-INSEE'].astype(str).str.zfill(5)

pve_tub = _apply_restrict_geo_tub(pve_filtered, pd.DataFrame(), root, tub_codes, 'PVE', log=logging.getLogger())

print('--- PVe forcés au centroïde ---')
count = 0
for _, r in pve_tub.iterrows():
    insee = r.get('_insee_pve')
    is_cen = insee in cen_insee
    if is_cen:
        count += 1
        ident = r.get('INF-ID', r.get('INF-NUM', r.get('DC_ID', 'Inconnu')))
        print(f"ID: {ident} | INSEE: {insee} | NATINF: {r.get('INF-NATINF')}")
print(f'Total: {count}')
