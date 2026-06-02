import pandas as pd
from pathlib import Path
from bilans.common.chargeurs_donnees import load_pej, load_point_ctrl
from bilans.engine.orchestrateur_profils import _filter_pej, load_tub_pnf_codes, _apply_restrict_geo_tub, ensure_insee_from_communes_shp, coalesced_insee_series, _filter_tub
import yaml
import logging
import sys

root = Path('.')
tub_codes, _ = load_tub_pnf_codes(root)

with open('config/profils_bilan/tub.yaml', 'r', encoding='utf-8') as f:
    tub_cfg = yaml.safe_load(f)

pej_all = load_pej(root, dept_code='21', date_deb=None, date_fin=None)

dossiers_cibles = ['OF20240926-62', 'OF20251219-37']
print('--- Analyse brute ODS ---')
for dc in dossiers_cibles:
    matches = pej_all[pej_all['DC_ID'].str.contains(dc, na=False, case=False)]
    if matches.empty:
        print(f'Dossier {dc} introuvable dans le fichier ODS !')
    else:
        for _, r in matches.iterrows():
            print(f"Dossier: {r['DC_ID']} | NATINF: {r.get('NATINF_PEJ', r.get('NATINF'))} | DATE_REF: {r['DATE_REF']} | DATE_CONSTATATION: {r.get('DATE_CONSTATATION')}")

print('\n--- Simulation du filtre temporel + NATINF (pej_filtered) ---')
pej_time = load_pej(root, dept_code='21', date_deb='2025-07-01', date_fin='2026-06-01')
pej_filtered = _filter_pej(pej_time, tub_cfg, type('Config', (), {'entity_sd': 'SD21'}))

for dc in dossiers_cibles:
    if dc in pej_filtered['DC_ID'].values:
        print(f'{dc}: SURVIVANT au filtre temps + NATINF')
    else:
        print(f'{dc}: RECALÉ au filtre temps + NATINF')

print('\n--- Simulation restriction géo TUB ---')
point = load_point_ctrl(root, dept_code='21', date_deb='2025-07-01', date_fin='2026-06-01')
point = ensure_insee_from_communes_shp(point, root, context='test', log=logging.getLogger())
s = coalesced_insee_series(point)
mask_tub = s.notna() & s.astype(str).isin(tub_codes)
point_tub = point.loc[mask_tub]
point_tub = _filter_tub(point_tub)

pej_tub = _apply_restrict_geo_tub(pej_filtered, point_tub, root, tub_codes, 'PEJ', log=logging.getLogger())

for dc in dossiers_cibles:
    if dc in pej_tub['DC_ID'].values:
        print(f'{dc}: SURVIVANT à la restriction géo (Dans la zone TUB ou match control)')
    else:
        if dc in pej_filtered['DC_ID'].values:
            print(f'{dc}: RECALÉ par la restriction géo (Hors TUB et pas de controle agrainage lié)')
