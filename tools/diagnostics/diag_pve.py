import pandas as pd
from pathlib import Path
from ofbilan.common.chargeurs_donnees import load_pve, load_point_ctrl
from ofbilan.engine.orchestrateur_profils import _filter_pve, load_tub_pnf_codes, _apply_restrict_geo_tub
import yaml
import logging

root = Path('.')
tub_codes, _ = load_tub_pnf_codes(root)

with open('config/profils_bilan/tub.yaml', 'r', encoding='utf-8') as f:
    tub_cfg = yaml.safe_load(f)

pve = load_pve(root, dept_code='21', date_deb='2025-07-01', date_fin='2026-06-01')
print('Total PVe après filtre période (INF-DATE-MIF):', len(pve))

pve_filtered = _filter_pve(pve, tub_cfg)
print('Total PVe après filtre NATINF:', len(pve_filtered))

pve_tub = _apply_restrict_geo_tub(pve_filtered, pd.DataFrame(), root, tub_codes, 'PVE', log=logging.getLogger())
print('Total PVe dans zone TUB (ou match contrôle):', len(pve_tub))

if not pve_tub.empty:
    for _, r in pve_tub.iterrows():
        natinf = r.get('INF-NATINF')
        date_mif = r.get('INF-DATE-MIF')
        insee = r.get('INF-INSEE')
        print(f"INSEE: {insee} | NATINF: {natinf} | DATE_MIF: {date_mif}")
