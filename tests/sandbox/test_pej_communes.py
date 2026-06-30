import sys
from pathlib import Path
sys.path.insert(0, 'src')
import pandas as pd
from core.common.chargeurs_donnees import load_pej, load_point_ctrl
from core.engine.agregations_profil import _build_global_proc_detail

root = Path('.')
point = load_point_ctrl(root)
pej = load_pej(root)

print("Total PEJ rows:", len(pej))
print("Total Point rows:", len(point))

# Reproduce PEJ extraction
pej_dept = pej.copy()

col_commune = "nom_commune" if "nom_commune" in point.columns else ("nom_commun" if "nom_commun" in point.columns else None)
nom_commune_by_dc = {}
if not point.empty and "dc_id" in point.columns and col_commune:
    tmp_p = point.dropna(subset=["dc_id"]).copy()
    nom_commune_by_dc = tmp_p.drop_duplicates("dc_id").set_index("dc_id")[col_commune].astype(str).to_dict()

print(f"nom_commune_by_dc has {len(nom_commune_by_dc)} items.")

pej_detail = _build_global_proc_detail(
    pej_dept, "PEJ", ["DC_ID"], ["DATE_REF"], ["COMMUNE", "nom_commune", "INF-LIEU", "INF-INSEE"], ["THEME"], ["DOMAINE"]
)

# Before mapping
initial_nd_mask = pej_detail["commune"].isna() | pej_detail["commune"].isin(["n.d.", "nan", "", "INC", "ND"])
print(f"Rows missing commune before DC_ID mapping: {initial_nd_mask.sum()}")

if not pej_detail.empty and "DC_ID" in pej_dept.columns:
    mapped_communes = pej_dept["DC_ID"].astype(str).map(nom_commune_by_dc)
    print(f"Mapped communes successfully matched: {mapped_communes.notna().sum()}")
    
    pej_detail.loc[initial_nd_mask, "commune"] = mapped_communes[initial_nd_mask]
    
    # Try with stripped DC_ID
    mapped_communes_strip = pej_dept["DC_ID"].astype(str).str.strip().str.replace('.0', '', regex=False).map(nom_commune_by_dc)
    print(f"Mapped communes successfully matched with strip/cleaning: {mapped_communes_strip.notna().sum()}")

    # Are there DC_IDs in PEJ that are missing entirely in points?
    pej_dc_ids = set(pej_dept["DC_ID"].dropna().astype(str).unique())
    point_dc_ids = set(point["dc_id"].dropna().astype(str).unique())
    print(f"Unique PEJ DC_IDs: {len(pej_dc_ids)}")
    print(f"Unique Point DC_IDs: {len(point_dc_ids)}")
    missing = pej_dc_ids - point_dc_ids
    print(f"PEJ DC_IDs completely missing in points: {len(missing)}")
    if missing:
        print(f"Sample of missing DC_IDs in points: {list(missing)[:5]}")

    pej_detail["commune"] = pej_detail["commune"].fillna("n.d.")

final_nd_mask = pej_detail["commune"] == "n.d."
print(f"Rows missing commune after DC_ID mapping: {final_nd_mask.sum()}")

print("Columns in PEJ dataset:", list(pej.columns))
