import pandas as pd
from pathlib import Path
from ofbilan.common.utilitaires_metier import get_departements_pour_perimetre

def analyse_region_par_departement(point: pd.DataFrame, pa: pd.DataFrame, pej: pd.DataFrame, pve: pd.DataFrame, echelle: str, code: str, out_dir: Path) -> None:
    if str(echelle).strip().lower() != "region":
        return
        
    dept_codes = get_departements_pour_perimetre(echelle, code)
    if not dept_codes or "FR" in dept_codes:
        return
        
    rows = []
    
    # 1. Traitement des points de contrôle (Localisations et Opérations)
    if not point.empty:
        # Assurer qu'on a un num_depart
        pt = point.copy()
        if "num_depart" not in pt.columns:
            pt["num_depart"] = "Inconnu"
        pt["domaine"] = pt["domaine"].fillna("Hors domaine").astype(str) if "domaine" in pt.columns else "Hors domaine"
        pt["theme"] = pt["theme"].fillna("Hors thème").astype(str) if "theme" in pt.columns else (pt["thematique"].fillna("Hors thème").astype(str) if "thematique" in pt.columns else "Hors thème")
        
        # Localisations
        locs = pt.groupby(["domaine", "theme", "num_depart"]).size().reset_index(name="nb_localisations")
        
        # Opérations (fc_id uniques)
        if "fc_id" in pt.columns:
            ops = pt.groupby(["domaine", "theme", "num_depart"])["fc_id"].nunique().reset_index(name="nb_operations")
            locs = pd.merge(locs, ops, on=["domaine", "theme", "num_depart"], how="outer")
        else:
            locs["nb_operations"] = 0
            
        for _, r in locs.iterrows():
            rows.append({
                "domaine": r["domaine"],
                "theme": r["theme"],
                "departement": r["num_depart"],
                "metrique": "nb_localisations",
                "valeur": r["nb_localisations"]
            })
            rows.append({
                "domaine": r["domaine"],
                "theme": r["theme"],
                "departement": r["num_depart"],
                "metrique": "nb_operations",
                "valeur": r["nb_operations"]
            })
            
    # 2. PEJ
    if not pej.empty:
        pj = pej.copy()
        pj["domaine"] = pj["DOMAINE"].fillna("Hors domaine").astype(str) if "DOMAINE" in pj.columns else "Hors domaine"
        pj["theme"] = pj["THEME"].fillna("Hors thème").astype(str) if "THEME" in pj.columns else "Hors thème"
        pj["departement"] = "Inconnu"
        if "ENTITE_ORIGINE_PROCEDURE" in pj.columns:
            # Extraction du département de SDXX
            pj["departement"] = pj["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.extract(r'SD(\d+)')[0]
            pj["departement"] = pj["departement"].fillna("Inconnu")
            
        if "DATE_REF" in pj.columns and "DC_ID" in pj.columns:
            pj = pj.sort_values("DATE_REF", ascending=False).drop_duplicates("DC_ID")
            
        pejs = pj.groupby(["domaine", "theme", "departement"]).size().reset_index(name="nb_pej")
        for _, r in pejs.iterrows():
            rows.append({
                "domaine": r["domaine"],
                "theme": r["theme"],
                "departement": r["departement"],
                "metrique": "nb_pej",
                "valeur": r["nb_pej"]
            })
            
    # 3. PA
    if not point.empty and "resultat" in point.columns:
        from ofbilan.common.utilitaires_metier import filter_points_induisant_pa
        pt_pa = filter_points_induisant_pa(point)
        if not pt_pa.empty:
            pt_pa["domaine"] = pt_pa["domaine"].fillna("Hors domaine").astype(str) if "domaine" in pt_pa.columns else "Hors domaine"
            pt_pa["theme"] = pt_pa["theme"].fillna("Hors thème").astype(str) if "theme" in pt_pa.columns else (pt_pa["thematique"].fillna("Hors thème").astype(str) if "thematique" in pt_pa.columns else "Hors thème")
            if "num_depart" not in pt_pa.columns:
                pt_pa["num_depart"] = "Inconnu"
            pas = pt_pa.groupby(["domaine", "theme", "num_depart"]).size().reset_index(name="nb_pa")
            for _, r in pas.iterrows():
                rows.append({
                    "domaine": r["domaine"],
                    "theme": r["theme"],
                    "departement": r["num_depart"],
                    "metrique": "nb_pa",
                    "valeur": r["nb_pa"]
                })
                
    # 4. PVe
    if not pve.empty:
        pv = pve.copy()
        pv["domaine"] = pv["DOMAINE"].fillna("Hors domaine").astype(str) if "DOMAINE" in pv.columns else "Hors domaine"
        # Assuming PVe themes are NATINF or similar, but we might not have 'theme' easily
        pv["theme"] = "Hors thème"
        # We can map NATINF to themes if natinf_ref is loaded, but for now fallback to "Hors thème"
        
        pv["departement"] = "Inconnu"
        if "INF-INSEE" in pv.columns:
            pv["departement"] = pv["INF-INSEE"].astype(str).str[:2]
        elif "INSEE_DEP" in pv.columns:
            pv["departement"] = pv["INSEE_DEP"].astype(str)
            
        pves = pv.groupby(["domaine", "theme", "departement"]).size().reset_index(name="nb_pve")
        for _, r in pves.iterrows():
            rows.append({
                "domaine": r["domaine"],
                "theme": r["theme"],
                "departement": r["departement"],
                "metrique": "nb_pve",
                "valeur": r["nb_pve"]
            })

    if not rows:
        pd.DataFrame(columns=["domaine", "theme", "departement", "metrique", "valeur"]).to_csv(out_dir / "region_detail_par_dept.csv", sep=";", index=False)
        return
        
    df = pd.DataFrame(rows)
    # Pivot
    df_pivot = df.pivot_table(index=["domaine", "theme", "departement"], columns="metrique", values="valeur", aggfunc="sum").fillna(0).reset_index()
    
    # Ensure all columns exist
    for col in ["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"]:
        if col not in df_pivot.columns:
            df_pivot[col] = 0
            
    df_pivot.to_csv(out_dir / "region_detail_par_dept.csv", sep=";", index=False)

