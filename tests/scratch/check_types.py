import os
from pathlib import Path
import pandas as pd
from ofbilan.common.chargeurs_donnees import load_point_ctrl, load_pej

project_root = Path(os.getcwd())
df_pts = load_point_ctrl(project_root, echelle="national", code="FR")
print("Unique type_actio in point_ctrl:")
print(df_pts["type_actio"].dropna().unique())

df_pej = load_pej(project_root, echelle="national", code="FR")
print("\nUnique type_action in PEJ:")
if "TYPE_ACTION" in df_pej.columns:
    print(df_pej["TYPE_ACTION"].dropna().unique())
elif "type_action" in df_pej.columns:
    print(df_pej["type_action"].dropna().unique())
