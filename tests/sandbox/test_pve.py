import sys
from pathlib import Path
sys.path.insert(0, 'src')
import pandas as pd
from core.common.chargeurs_donnees import load_pve, load_pej
from core.engine.agregations_profil import _build_global_proc_detail

root = Path('.')
pve = load_pve(root)
pej = load_pej(root)

print(pve[['INF-DATE-INTG', 'INF-DATE-MIF']].head())

pve_detail = _build_global_proc_detail(
    pve, 'PVe', ['INF-ID'], 
    ['INF-DATE', 'INF-DATE-INTG', 'INF-DATE-MIF', 'INF-DATE-I', 'INF_DATE', 'DATE_FAITS'], 
    ['COMMUNE_LIB', 'INF-LIEU', 'COMMUNE', 'NOM_COM', 'INF-INSEE', 'INSEE_DEP'], 
    ['INF-NATINF'], ['DOMAINE']
)

print("PVE DETAIL:")
print(pve_detail[['date', 'commune']].head())

pej_detail = _build_global_proc_detail(
    pej, 'PEJ', ['DC_ID'], 
    ['DATE_REF'], 
    ['COMMUNE', 'nom_commune', 'INF-LIEU', 'INF-INSEE'], 
    ['THEME'], ['DOMAINE']
)
print("PEJ DETAIL:")
print(pej_detail[['date', 'commune']].head())
