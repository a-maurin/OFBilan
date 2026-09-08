# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
# sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
# Voir la Licence Publique Générale GNU pour plus de détails.
#
# CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
# Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
# intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
# clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
# doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
# de l'auteur original (Aguirre MAURIN).

"""
========================================================================================
MODULE : CALCULS D'AGREGATION A L'ECHELLE REGIONALE (`agregations_region.py`)
========================================================================================
Ce module gère le regroupement et la ventilation des données de police au niveau régional
et interdépartemental (Direction Régionale, Brigade de Mission Interdépartementale BMI).

Rôles :
  1. Association des NATINF PVe aux thèmes de profil via le registre YAML.
  2. Ventilation interdépartementale des contrôles, opérations, PA, PEJ et PVe.
  3. Génération des matrices de répartition départementale pour la cartographie et les
     tableaux comparatifs régionaux dans les PDF.
========================================================================================
"""
import pandas as pd
from pathlib import Path
from typing import Any
from core.common.utilitaires_metier import get_departements_pour_perimetre

def _load_natinf_to_theme_map() -> dict[str, str]:
    """Lit les profils YAML pour associer chaque NATINF PVe à un id de profil (thème)."""
    from core.chemins_projet import PROJECT_ROOT
    import yaml
    
    mapping = {}
    profiles_dir = PROJECT_ROOT / "config" / "profils_bilan"
    if not profiles_dir.exists():
        return mapping
    
    for p in profiles_dir.glob("*.yaml"):
        if p.stem in ("_defaults", "schema_ui"):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    natinfs = data.get("natinf_pve", [])
                    if isinstance(natinfs, list):
                        for n in natinfs:
                            mapping[str(n).strip()] = p.stem
        except Exception:
            continue
    return mapping


def analyse_region_par_departement(
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    echelle: str,
    code: str,
    out_dir: Path,
    pej_global: pd.DataFrame | None = None,
    profil_id: str = "global",
) -> None:
    if str(echelle).strip().lower() not in ("region", "bmi") and str(profil_id).strip().lower() not in ("pnf_v2", "pnf"):
        return
        
    if str(profil_id).strip().lower() in ("pnf_v2", "pnf"):
        dept_codes = ["21", "52"]
    else:
        dept_codes = get_departements_pour_perimetre(echelle, code)
        if not dept_codes or "FR" in dept_codes:
            return
        
    rows = []
    
    # 1. Traitement des points de contrôle (Localisations et Opérations)
    if not point.empty:
        # Assurer qu'on a un num_depart propre et filtré
        pt = point.copy()
        if "num_depart" not in pt.columns:
            pt["num_depart"] = "Inconnu"
        pt["num_depart"] = pt["num_depart"].astype(str).str.strip().str.split('.').str[0].str.zfill(2)
        pt = pt[pt["num_depart"].isin(dept_codes)]
        
        pt["domaine"] = pt["domaine"].fillna("Hors domaine").astype(str) if "domaine" in pt.columns else "Hors domaine"
        pt["theme"] = pt["theme"].fillna("Hors thème").astype(str) if "theme" in pt.columns else (pt["thematique"].fillna("Hors thème").astype(str) if "thematique" in pt.columns else "Hors thème")
        
        if not pt.empty:
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
            pj["departement"] = pj["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.extract(r'(\d+)')[0]
            pj["departement"] = pj["departement"].fillna("Inconnu").astype(str).str.strip().str.zfill(2)
        pj = pj[pj["departement"].isin(dept_codes)]
            
        if "DATE_REF" in pj.columns and "DC_ID" in pj.columns:
            pj = pj.sort_values("DATE_REF", ascending=False).drop_duplicates("DC_ID")
            
        if not pj.empty:
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
        from core.common.utilitaires_metier import filter_points_induisant_pa
        pt_pa = filter_points_induisant_pa(point)
        if not pt_pa.empty:
            pt_pa = pt_pa.copy()
            if "num_depart" not in pt_pa.columns:
                pt_pa["num_depart"] = "Inconnu"
            pt_pa["num_depart"] = pt_pa["num_depart"].astype(str).str.strip().str.split('.').str[0].str.zfill(2)
            pt_pa = pt_pa[pt_pa["num_depart"].isin(dept_codes)]
            
            if not pt_pa.empty:
                pt_pa["domaine"] = pt_pa["domaine"].fillna("Hors domaine").astype(str) if "domaine" in pt_pa.columns else "Hors domaine"
                pt_pa["theme"] = pt_pa["theme"].fillna("Hors thème").astype(str) if "theme" in pt_pa.columns else (pt_pa["thematique"].fillna("Hors thème").astype(str) if "thematique" in pt_pa.columns else "Hors thème")
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
        # Priorité au thème SNC issu de la concordance NATINF/SNC (load_pve)
        th_col = next((c for c in ["THEME_SNC", "theme_snc", "THEME", "theme"] if c in pv.columns and pv[c].notna().any()), None)
        if th_col:
            pv["theme"] = pv[th_col].fillna("Hors thème").astype(str)
        else:
            natinf_map = _load_natinf_to_theme_map()
            def _get_theme_from_natinf(val):
                if pd.isna(val):
                    return "Hors thème"
                tokens = [t.strip() for t in str(val).replace("_", " ").replace("-", " ").split() if t.strip()]
                for tok in tokens:
                    if tok in natinf_map:
                        return natinf_map[tok]
                return "Hors thème"
                
            natinf_col = "INF-NATINF" if "INF-NATINF" in pv.columns else ("NATINF" if "NATINF" in pv.columns else None)
            if natinf_col:
                pv["theme"] = pv[natinf_col].apply(_get_theme_from_natinf)
            else:
                pv["theme"] = "Hors thème"

            
        pv["departement"] = "Inconnu"
        if "INF-INSEE" in pv.columns:
            s_insee = pv["INF-INSEE"].astype(str).str.strip().str.zfill(5)
            pv["departement"] = s_insee.where(~s_insee.str.startswith("97"), s_insee.str[:3])
            pv["departement"] = pv["departement"].where(s_insee.str.startswith("97"), s_insee.str[:2])
        elif "INSEE_DEP" in pv.columns:
            pv["departement"] = pv["INSEE_DEP"].astype(str)
            
        pv["departement"] = pv["departement"].astype(str).str.strip().str.zfill(2)
        pv = pv[pv["departement"].isin(dept_codes)]

        dom_col = next((c for c in ("domaine", "DOMAINE", "domaine_snc", "DOMAINE_SNC") if c in pv.columns), None)
        if dom_col:
            pv["domaine"] = pv[dom_col].fillna("Hors domaine").astype(str)
        else:
            pv["domaine"] = "Hors domaine"

        if not pv.empty:
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

    if str(profil_id).strip().lower() in ("pnf_v2", "pnf"):
        generer_csv_pnf_coeur_vs_aoa(point, pej, pve, out_dir)

    if pej_global is not None and not pej_global.empty:
        calculer_ratio_pej_departement(pej, pej_global, echelle, code, out_dir, profil_id)

    calculer_enrichissements_regionaux(point, pa, pej, pve, dept_codes, out_dir)


def calculer_enrichissements_regionaux(
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    dept_codes: list[str],
    out_dir: Path,
) -> None:
    """
    Calcule et exporte les CSV d'enrichissement régional et départemental :
    1. saisonnalite_mensuelle.csv (Opérations et infractions par mois)
    2. non_conformite_global_et_dept.csv (Taux de non-conformité par dépt et global)
    3. maillage_communes_dept.csv (Maillage communes contrôlées / total par dépt)
    4. top_infractions_pej_pve.csv (10 lignes : Top 5 PEJ puis Top 5 PVe avec NATINF & Nature)
    5. usagers_par_dept.csv (Typologie d'usagers par dépt et global)
    """
    try:
        from core.chemins_projet import PROJECT_ROOT
        from core.common.chargeurs_donnees import load_natinf_ref, load_concordance_natinf_snc, load_communes_noms

        months_labels = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"]

        # 1. SAISONNALITÉ MENSUELLE
        sais_ops = [0] * 12
        sais_inf = [0] * 12

        if not point.empty:
            pt = point.copy()
            date_col = next((c for c in ["date_ctrl", "date_fin", "date_deb", "date_debut", "DATE_REF", "date"] if c in pt.columns), None)
            if date_col:
                s_dates = pd.to_datetime(pt[date_col], errors="coerce")
                for m in range(1, 13):
                    sais_ops[m - 1] += int((s_dates.dt.month == m).sum())

        # Somme des infractions (PEJ + PVe + PA) par mois
        for df_proc, col_d in [(pej, "DATE_REF"), (pve, "INF-DATE"), (pa, "date_fin")]:
            if df_proc is not None and not df_proc.empty:
                c_date = col_d if col_d in df_proc.columns else next((c for c in df_proc.columns if "date" in c.lower()), None)
                if c_date:
                    s_d = pd.to_datetime(df_proc[c_date], errors="coerce")
                    for m in range(1, 13):
                        sais_inf[m - 1] += int((s_d.dt.month == m).sum())

        df_sais = pd.DataFrame({
            "mois_num": list(range(1, 13)),
            "mois_lib": months_labels,
            "nb_operations": sais_ops,
            "nb_infractions": sais_inf,
        })
        df_sais.to_csv(out_dir / "saisonnalite_mensuelle.csv", sep=";", index=False)

        # 2. MAILLAGE TERRITORIAL DES COMMUNES PAR DÉPARTEMENT
        dict_communes_ref = load_communes_noms(PROJECT_ROOT)
        tot_communes_ref_by_dept = {}
        if dict_communes_ref:
            for insee in dict_communes_ref.keys():
                dept = str(insee)[:2]
                tot_communes_ref_by_dept[dept] = tot_communes_ref_by_dept.get(dept, 0) + 1

        rows_maillage = []
        if not point.empty:
            pt = point.copy()
            if "num_depart" not in pt.columns:
                pt["num_depart"] = "Inconnu"
            pt["num_depart"] = pt["num_depart"].astype(str).str.strip().str.split('.').str[0].str.zfill(2)

            insee_col = next((c for c in ["insee_com", "code_insee", "commune_insee", "INSEE_COM", "num_insee"] if c in pt.columns), None)
            
            for d in dept_codes:
                sub_d = pt[pt["num_depart"] == str(d)]
                if insee_col and not sub_d.empty:
                    nb_ctrl = sub_d[insee_col].dropna().astype(str).str.zfill(5).nunique()
                else:
                    nb_ctrl = len(sub_d)
                
                tot_ref = tot_communes_ref_by_dept.get(str(d), max(nb_ctrl, 1))
                pct = round((nb_ctrl / tot_ref * 100.0), 1) if tot_ref > 0 else 0.0
                rows_maillage.append({
                    "departement": str(d),
                    "communes_controlees": nb_ctrl,
                    "total_communes": tot_ref,
                    "pct_maillage": pct,
                })
        else:
            for d in dept_codes:
                tot_ref = tot_communes_ref_by_dept.get(str(d), 0)
                rows_maillage.append({
                    "departement": str(d),
                    "communes_controlees": 0,
                    "total_communes": tot_ref,
                    "pct_maillage": 0.0,
                })
        pd.DataFrame(rows_maillage).to_csv(out_dir / "maillage_communes_dept.csv", sep=";", index=False)

        # 3. TAUX DE NON-CONFORMITÉ GLOBAL ET DÉPARTEMENTAL
        rows_nc = []
        csv_detail = out_dir / "region_detail_par_dept.csv"
        if csv_detail.exists():
            df_det = pd.read_csv(csv_detail, sep=";", encoding="utf-8")
            if not df_det.empty and "departement" in df_det.columns:
                df_det["departement"] = df_det["departement"].astype(str)
                for d in dept_codes:
                    sub = df_det[df_det["departement"] == str(d)]
                    ops = int(sub["nb_operations"].sum()) if "nb_operations" in sub.columns else 0
                    pej_cnt = int(sub["nb_pej"].sum()) if "nb_pej" in sub.columns else 0
                    pve_cnt = int(sub["nb_pve"].sum()) if "nb_pve" in sub.columns else 0
                    pa_cnt = int(sub["nb_pa"].sum()) if "nb_pa" in sub.columns else 0
                    procs = pej_cnt + pve_cnt + pa_cnt
                    ops_nc = min(ops, procs) if ops > 0 else 0
                    pct_nc = round((ops_nc / ops * 100.0), 1) if ops > 0 else 0.0
                    rows_nc.append({
                        "departement": str(d),
                        "total_operations": ops,
                        "operations_non_conformes": ops_nc,
                        "pct_non_conformite": pct_nc,
                    })
                tot_ops = sum(r["total_operations"] for r in rows_nc)
                tot_nc = sum(r["operations_non_conformes"] for r in rows_nc)
                pct_tot = round((tot_nc / tot_ops * 100.0), 1) if tot_ops > 0 else 0.0
                rows_nc.append({
                    "departement": "Total",
                    "total_operations": tot_ops,
                    "operations_non_conformes": tot_nc,
                    "pct_non_conformite": pct_tot,
                })
        pd.DataFrame(rows_nc).to_csv(out_dir / "non_conformite_global_et_dept.csv", sep=";", index=False)

        # 4. TYPOLOGIE DES USAGERS PAR DÉPARTEMENT
        import re
        rows_usag = []
        if not point.empty and "type_usager" in point.columns:
            pt = point.copy()
            if "num_depart" not in pt.columns:
                pt["num_depart"] = "Inconnu"
            pt["num_depart"] = pt["num_depart"].astype(str).str.strip().str.split('.').str[0].str.zfill(2)
            pt["type_usager_clean"] = pt["type_usager"].apply(lambda u: re.sub(r'[\s_]+\d+$', '', str(u)).strip() if pd.notna(u) else "Non renseigné")

            for (d, usg), sub in pt.groupby(["num_depart", "type_usager_clean"]):
                if str(d) in dept_codes:
                    nb_ops = sub["fc_id"].nunique() if "fc_id" in sub.columns else len(sub)
                    rows_usag.append({
                        "departement": str(d),
                        "type_usager": str(usg),
                        "nb_operations": nb_ops,
                    })
        df_usag = pd.DataFrame(rows_usag)
        if not df_usag.empty:
            df_usag = df_usag.groupby(["departement", "type_usager"])["nb_operations"].sum().reset_index()
        df_usag.to_csv(out_dir / "usagers_par_dept.csv", sep=";", index=False)

        # 5. SYNTHÈSE PAR THÈME SNC PAR DÉPARTEMENT (Pour le tableau de la Fiche Département)
        csv_detail = out_dir / "region_detail_par_dept.csv"
        if csv_detail.exists():
            df_det = pd.read_csv(csv_detail, sep=";", encoding="utf-8")
            if not df_det.empty and "theme" in df_det.columns and "departement" in df_det.columns:
                df_det["departement"] = df_det["departement"].astype(str)
                df_det["theme_snc"] = df_det["theme"].fillna("Hors thème").astype(str)
                cols_sum = [c for c in ["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"] if c in df_det.columns]
                df_td_pivot = df_det.groupby(["departement", "theme_snc"])[cols_sum].sum().reset_index()
                df_td_pivot.to_csv(out_dir / "theme_snc_par_dept.csv", sep=";", index=False)


        # 6. TOP 10 INFRACTIONS FUSIONNÉ (Top 5 PEJ + Top 5 PVe)
        df_natinf_ref = load_natinf_ref(PROJECT_ROOT)
        df_snc_conc = load_concordance_natinf_snc(PROJECT_ROOT)

        ref_map = {}
        if not df_natinf_ref.empty and "numero_natinf" in df_natinf_ref.columns:
            for _, r in df_natinf_ref.iterrows():
                num = str(r["numero_natinf"]).strip().lstrip("0")
                ref_map[num] = {
                    "libelle": str(r.get("libelle_natinf", "") or r.get("qualification_infraction", "")),
                    "nature": str(r.get("nature_infraction", "Délit")),
                }

        snc_map = {}
        if not df_snc_conc.empty and "numero_natinf" in df_snc_conc.columns:
            for _, r in df_snc_conc.iterrows():
                num = str(r["numero_natinf"]).strip().lstrip("0")
                snc_map[num] = str(r.get("theme_snc", "Non catégorisé"))

        top_rows = []

        # Top 5 PEJ
        if pej is not None and not pej.empty:
            nat_col = next((c for c in ["NATINF_PEJ", "NATINF", "NUMERO_NATINF", "natinf"] if c in pej.columns), None)
            theme_fallback_col = next((c for c in ["THEME", "DOMAINE", "thematique"] if c in pej.columns), None)
            if nat_col:
                s_codes = pej[nat_col].dropna().astype(str).str.extract(r'(\d+)', expand=False).dropna()
                counts = s_codes.value_counts().head(5)
                for code_nat, count in counts.items():
                    clean_code = str(code_nat).strip().lstrip("0")
                    ref_info = ref_map.get(clean_code, {"libelle": f"Infraction NATINF {code_nat}", "nature": "Délit"})
                    
                    fallback_val = "Infractions pénales"
                    if theme_fallback_col:
                        sub_pj = pej[pej[nat_col].astype(str).str.contains(str(code_nat), na=False)]
                        if not sub_pj.empty:
                            fallback_val = str(sub_pj[theme_fallback_col].iloc[0])
                    
                    theme = snc_map.get(clean_code, fallback_val)
                    top_rows.append({
                        "procedure": "PEJ",
                        "theme_snc": theme,
                        "numero_natinf": str(code_nat),
                        "libelle_infraction": ref_info["libelle"],
                        "nature_juridique": ref_info["nature"],
                        "nb_infractions": int(count),
                    })

        # Top 5 PVe
        if pve is not None and not pve.empty:
            nat_col = next((c for c in ["INF-NATINF", "NATINF", "numero_natinf", "natinf"] if c in pve.columns), None)
            theme_fallback_col = next((c for c in ["DOMAINE", "THEME", "thematique"] if c in pve.columns), None)
            if nat_col:
                s_codes = pve[nat_col].dropna().astype(str).str.extract(r'(\d+)', expand=False).dropna()
                counts = s_codes.value_counts().head(5)
                for code_nat, count in counts.items():
                    clean_code = str(code_nat).strip().lstrip("0")
                    ref_info = ref_map.get(clean_code, {"libelle": f"Infraction NATINF {code_nat}", "nature": "Contravention C5"})
                    
                    fallback_val = "Infractions forfaitaires"
                    if theme_fallback_col:
                        sub_pv = pve[pve[nat_col].astype(str).str.contains(str(code_nat), na=False)]
                        if not sub_pv.empty:
                            fallback_val = str(sub_pv[theme_fallback_col].iloc[0])

                    theme = snc_map.get(clean_code, fallback_val)
                    top_rows.append({
                        "procedure": "PVe",
                        "theme_snc": theme,
                        "numero_natinf": str(code_nat),
                        "libelle_infraction": ref_info["libelle"],
                        "nature_juridique": ref_info["nature"],
                        "nb_infractions": int(count),
                    })

        pd.DataFrame(top_rows).to_csv(out_dir / "top_infractions_pej_pve.csv", sep=";", index=False)

    except Exception as e_enr:
        logger.warning(f"Calcul des enrichissements régionaux : {e_enr}")



def _extract_gdf(df: pd.DataFrame, out_dir: Path, pattern: str = "controles_*.gpkg") -> Any:
    """Helper pour convertir un DataFrame en GeoDataFrame ou charger le GPKG généré."""
    try:
        import geopandas as gpd
    except ImportError:
        return None

    if df is None or df.empty:
        return None

    # 1. Si c'est déjà un GeoDataFrame avec géométrie valide
    if isinstance(df, gpd.GeoDataFrame) and "geometry" in df.columns and df.geometry.notna().any():
        return df

    # 2. Vérification des colonnes de géométrie explicites ou coordonnées
    if "geometry" in df.columns:
        try:
            return gpd.GeoDataFrame(df.copy(), geometry="geometry")
        except Exception:
            pass

    x_col = next((c for c in ["x", "X", "lon", "longitude", "x_faits", "x_l93", "x_2154", "inf_gps_long"] if c in df.columns), None)
    y_col = next((c for c in ["y", "Y", "lat", "latitude", "y_faits", "y_l93", "y_2154", "inf_gps_lat"] if c in df.columns), None)
    if x_col and y_col:
        try:
            s_x = pd.to_numeric(df[x_col], errors="coerce")
            s_y = pd.to_numeric(df[y_col], errors="coerce")
            valid = s_x.notna() & s_y.notna() & (s_x != 0) & (s_y != 0)
            if valid.any():
                crs = "EPSG:2154" if float(s_x.dropna().iloc[0]) > 1000 else "EPSG:4326"
                return gpd.GeoDataFrame(df[valid].copy(), geometry=gpd.points_from_xy(s_x[valid], s_y[valid]), crs=crs)
        except Exception:
            pass

    # 3. Fallback : Chargement du fichier GPKG de sortie s'il existe
    gpkg_files = list(out_dir.glob(pattern)) + list(out_dir.rglob(pattern))
    from core.chemins_projet import PROJECT_ROOT, get_carto_temp_dir
    gpkg_files += list(get_carto_temp_dir().glob(pattern))
    carto_dir = PROJECT_ROOT / "data" / "sources" / "sig" / "CARTO"
    gpkg_files += list(carto_dir.glob(pattern))
    if gpkg_files:
        try:
            gpkg_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            gdf_gpkg = gpd.read_file(gpkg_files[0])
            if gdf_gpkg is not None and not gdf_gpkg.empty and "geometry" in gdf_gpkg.columns:
                return gdf_gpkg
        except Exception:
            pass

    return None


def generer_csv_pnf_coeur_vs_aoa(
    point: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    out_dir: Path,
) -> None:
    """
    Génère le fichier CSV `pnf_coeur_vs_aoa.csv` ventilé par territoire
    ('Cœur de parc', 'AOA (Hors cœur)', 'Non géolocalisé (AOA)') et par département (21, 52).
    """
    try:
        from core.common.chargeurs_donnees import load_pnf_coeur_gdf
        from core.chemins_projet import PROJECT_ROOT
        try:
            import geopandas as gpd
        except ImportError:
            gpd = None

        gdf_coeur = load_pnf_coeur_gdf(PROJECT_ROOT) if gpd is not None else None
        if gdf_coeur is not None and not gdf_coeur.empty and gdf_coeur.crs is None:
            gdf_coeur = gdf_coeur.set_crs("EPSG:2154")

        dept_codes = ["21", "52"]
        records = []

        # 1. Point (Opérations & Localisations)
        if not point.empty:
            pt = point.copy()
            if "num_depart" not in pt.columns:
                pt["num_depart"] = "Inconnu"
            pt["num_depart"] = pt["num_depart"].astype(str).str.strip().str.split('.').str[0].str.zfill(2)
            pt = pt[pt["num_depart"].isin(dept_codes)].copy()

            if not pt.empty:
                pt["zonage"] = "Non géolocalisé (AOA)"
                if gpd is not None and gdf_coeur is not None and not gdf_coeur.empty:
                    try:
                        gdf_pts = _extract_gdf(pt, out_dir, pattern="controles_*.gpkg")
                        if gdf_pts is not None and not gdf_pts.empty:
                            if gdf_pts.crs is None or gdf_pts.crs.to_epsg() != 2154:
                                if gdf_pts.crs is not None:
                                    gdf_pts = gdf_pts.to_crs("EPSG:2154")
                                else:
                                    gdf_pts = gdf_pts.set_crs("EPSG:2154")
                            sj = gpd.sjoin(gdf_pts, gdf_coeur, predicate="within", how="left")
                            is_in_coeur = sj["index_right"].notna()

                            # If length matches pt:
                            if len(is_in_coeur) == len(pt):
                                pt["zonage"] = "AOA (Hors cœur)"
                                pt.loc[is_in_coeur.values, "zonage"] = "Cœur de parc"
                            else:
                                # Join on fc_id if present
                                if "fc_id" in sj.columns:
                                    coeur_fc_ids = set(sj[sj["index_right"].notna()]["fc_id"].dropna())
                                    aoa_fc_ids = set(sj["fc_id"].dropna())
                                    pt["zonage"] = pt["fc_id"].apply(lambda fid: "Cœur de parc" if fid in coeur_fc_ids else ("AOA (Hors cœur)" if fid in aoa_fc_ids else "Non géolocalisé (AOA)"))
                                else:
                                    pt["zonage"] = "AOA (Hors cœur)"
                                    pt.loc[is_in_coeur, "zonage"] = "Cœur de parc"
                    except Exception:
                        pass

                # Aggregation Localisations & Operations
                for (zonage, dept), sub in pt.groupby(["zonage", "num_depart"]):
                    nb_locs = len(sub)
                    nb_ops = sub["fc_id"].nunique() if "fc_id" in sub.columns else nb_locs
                    records.append({"zonage": zonage, "departement": dept, "metrique": "nb_localisations", "valeur": nb_locs})
                    records.append({"zonage": zonage, "departement": dept, "metrique": "nb_operations", "valeur": nb_ops})

        # 2. PEJ
        if not pej.empty:
            pj = pej.copy()
            pj["departement"] = "Inconnu"
            if "ENTITE_ORIGINE_PROCEDURE" in pj.columns:
                pj["departement"] = pj["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.extract(r'(\d+)')[0]
                pj["departement"] = pj["departement"].fillna("Inconnu").astype(str).str.strip().str.zfill(2)
            pj = pj[pj["departement"].isin(dept_codes)].copy()

            if "DATE_REF" in pj.columns and "DC_ID" in pj.columns:
                pj = pj.sort_values("DATE_REF", ascending=False).drop_duplicates("DC_ID")

            if not pj.empty:
                pj["zonage"] = "AOA (Hors cœur)"
                if gpd is not None and gdf_coeur is not None and not gdf_coeur.empty:
                    try:
                        from core.common.chargeurs_donnees import merge_pej_faits_locations, get_communes_centroids_dicts
                        pj_merged = merge_pej_faits_locations(pj, project_root, echelle, code)
                        dict_x, dict_y = get_communes_centroids_dicts(project_root)
                        
                        lon_col = next((c for c in ["x_faits", "x_infrac", "x_longitude", "longitude", "lon"] if c in pj_merged.columns), None)
                        lat_col = next((c for c in ["y_faits", "y_infrac", "y_latitude", "latitude", "lat"] if c in pj_merged.columns), None)
                        
                        df_geo = pj_merged.copy()
                        df_geo["_lon"] = pd.to_numeric(df_geo[lon_col], errors="coerce") if lon_col else np.nan
                        df_geo["_lat"] = pd.to_numeric(df_geo[lat_col], errors="coerce") if lat_col else np.nan
                        
                        missing = df_geo["_lon"].isna() | df_geo["_lat"].isna() | (df_geo["_lon"] == 0) | (df_geo["_lat"] == 0)
                        if missing.any() and "INSEE_COM" in df_geo.columns:
                            s_insee = df_geo["INSEE_COM"].astype(str).str.zfill(5)
                            df_geo.loc[missing, "_lon"] = s_insee.map(dict_x)
                            df_geo.loc[missing, "_lat"] = s_insee.map(dict_y)
                            
                        valid_geo = df_geo["_lon"].notna() & df_geo["_lat"].notna() & (df_geo["_lon"] != 0)
                        if valid_geo.any():
                            gdf_pj = gpd.GeoDataFrame(
                                df_geo[valid_geo],
                                geometry=gpd.points_from_xy(df_geo.loc[valid_geo, "_lon"], df_geo.loc[valid_geo, "_lat"]),
                                crs="EPSG:4326"
                            ).to_crs("EPSG:2154")
                            sj = gpd.sjoin(gdf_pj, gdf_coeur, predicate="within", how="left")
                            is_in = sj["index_right"].notna()
                            pj_indices = pj.index[valid_geo.values]
                            pj.loc[pj_indices[is_in.values], "zonage"] = "Cœur de parc"
                    except Exception as e_pj:
                        logger.warning(f"Spatial join PEJ Cœur vs AOA : {e_pj}")

                for (zonage, dept), sub in pj.groupby(["zonage", "departement"]):
                    records.append({"zonage": zonage, "departement": dept, "metrique": "nb_pej", "valeur": len(sub)})

        # 3. PA
        if not point.empty and "resultat" in point.columns:
            from core.common.utilitaires_metier import filter_points_induisant_pa
            pt_pa = filter_points_induisant_pa(point)
            if not pt_pa.empty:
                pt_pa = pt_pa.copy()
                if "num_depart" not in pt_pa.columns:
                    pt_pa["num_depart"] = "Inconnu"
                pt_pa["num_depart"] = pt_pa["num_depart"].astype(str).str.strip().str.split('.').str[0].str.zfill(2)
                pt_pa = pt_pa[pt_pa["num_depart"].isin(dept_codes)].copy()

                if not pt_pa.empty:
                    pt_pa["zonage"] = "AOA (Hors cœur)"
                    if gpd is not None and gdf_coeur is not None and not gdf_coeur.empty and not gdf_pts.empty:
                        try:
                            pts_pa_gdf = gdf_pts[gdf_pts.index.isin(pt_pa.index)] if hasattr(gdf_pts, "index") else None
                            if pts_pa_gdf is not None and not pts_pa_gdf.empty:
                                if pts_pa_gdf.crs is None or pts_pa_gdf.crs.to_epsg() != 2154:
                                    pts_pa_gdf = pts_pa_gdf.to_crs("EPSG:2154")
                                sj = gpd.sjoin(pts_pa_gdf, gdf_coeur, predicate="within", how="left")
                                is_in = sj["index_right"].notna()
                                pa_in_indices = pts_pa_gdf.index[is_in.values]
                                pt_pa.loc[pt_pa.index.isin(pa_in_indices), "zonage"] = "Cœur de parc"
                        except Exception as e_pa:
                            logger.warning(f"Spatial join PA Cœur vs AOA : {e_pa}")

                    for (zonage, dept), sub in pt_pa.groupby(["zonage", "num_depart"]):
                        records.append({"zonage": zonage, "departement": dept, "metrique": "nb_pa", "valeur": len(sub)})

        # 4. PVe
        if not pve.empty:
            pv = pve.copy()
            pv["departement"] = "Inconnu"
            if "INF-INSEE" in pv.columns:
                s_insee = pv["INF-INSEE"].astype(str).str.strip().str.zfill(5)
                pv["departement"] = s_insee.where(~s_insee.str.startswith("97"), s_insee.str[:3])
                pv["departement"] = pv["departement"].where(s_insee.str.startswith("97"), s_insee.str[:2])
            elif "INSEE_DEP" in pv.columns:
                pv["departement"] = pv["INSEE_DEP"].astype(str)
            pv["departement"] = pv["departement"].astype(str).str.strip().str.zfill(2)
            pv = pv[pv["departement"].isin(dept_codes)].copy()

            if not pv.empty:
                pv["zonage"] = "AOA (Hors cœur)"
                if gpd is not None and gdf_coeur is not None and not gdf_coeur.empty:
                    try:
                        from core.common.chargeurs_donnees import get_communes_centroids_dicts
                        dict_x, dict_y = get_communes_centroids_dicts(project_root)
                        s_insee = pv["INF-INSEE"].astype(str).str.strip().str.zfill(5) if "INF-INSEE" in pv.columns else pd.Series(dtype=str)
                        pv["_lon"] = s_insee.map(dict_x)
                        pv["_lat"] = s_insee.map(dict_y)
                        
                        valid_pv = pv["_lon"].notna() & pv["_lat"].notna()
                        if valid_pv.any():
                            gdf_pv = gpd.GeoDataFrame(
                                pv[valid_pv],
                                geometry=gpd.points_from_xy(pv.loc[valid_pv, "_lon"], pv.loc[valid_pv, "_lat"]),
                                crs="EPSG:4326"
                            ).to_crs("EPSG:2154")
                            sj = gpd.sjoin(gdf_pv, gdf_coeur, predicate="within", how="left")
                            is_in = sj["index_right"].notna()
                            pv_indices = pv.index[valid_pv.values]
                            pv.loc[pv_indices[is_in.values], "zonage"] = "Cœur de parc"
                    except Exception as e_pv:
                        logger.warning(f"Spatial join PVe Cœur vs AOA : {e_pv}")

                for (zonage, dept), sub in pv.groupby(["zonage", "departement"]):
                    records.append({"zonage": zonage, "departement": dept, "metrique": "nb_pve", "valeur": len(sub)})

        df_res = pd.DataFrame(records)
        if df_res.empty:
            pd.DataFrame(columns=["zonage", "departement", "nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"]).to_csv(out_dir / "pnf_coeur_vs_aoa.csv", sep=";", index=False)
            return

        df_piv = df_res.pivot_table(index=["zonage", "departement"], columns="metrique", values="valeur", aggfunc="sum").fillna(0).reset_index()
        for col in ["nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"]:
            if col not in df_piv.columns:
                df_piv[col] = 0

        df_piv.to_csv(out_dir / "pnf_coeur_vs_aoa.csv", sep=";", index=False)
    except Exception:
        pd.DataFrame(columns=["zonage", "departement", "nb_operations", "nb_localisations", "nb_pej", "nb_pa", "nb_pve"]).to_csv(out_dir / "pnf_coeur_vs_aoa.csv", sep=";", index=False)


def calculer_ratio_pej_departement(
    pej_filtered: pd.DataFrame,
    pej_global: pd.DataFrame,
    echelle: str,
    code: str,
    out_dir: Path,
    profil_id: str,
) -> None:
    """Calcule le ratio d'enquêtes thématiques par rapport au global par département."""
    if str(echelle).strip().lower() not in ("region", "bmi"):
        return
        
    def _prepare_pej(df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        d["departement"] = "Inconnu"
        if "ENTITE_ORIGINE_PROCEDURE" in d.columns:
            d["departement"] = d["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.extract(r'(\d+)')[0]
            d["departement"] = d["departement"].fillna("Inconnu")
        if "DATE_REF" in d.columns and "DC_ID" in d.columns:
            d = d.sort_values("DATE_REF", ascending=False).drop_duplicates("DC_ID")
        return d

    df_glob = _prepare_pej(pej_global)
    df_filt = _prepare_pej(pej_filtered)
    
    glob_counts = df_glob.groupby("departement").size().reset_index(name="total_pej")
    filt_counts = df_filt.groupby("departement").size().reset_index(name="ppp_pej")
    
    merged = pd.merge(glob_counts, filt_counts, on="departement", how="outer").fillna(0)
    merged["total_pej"] = merged["total_pej"].astype(int)
    merged["ppp_pej"] = merged["ppp_pej"].astype(int)
    
    merged = merged[merged["departement"] != "Inconnu"]
    
    merged["ratio_pourcent"] = 0.0
    mask = merged["total_pej"] > 0
    merged.loc[mask, "ratio_pourcent"] = (merged.loc[mask, "ppp_pej"] / merged.loc[mask, "total_pej"]) * 100.0
    merged["ratio_pourcent"] = merged["ratio_pourcent"].round(1)
    
    merged = merged.sort_values("departement")
    
    csv_name = f"{profil_id}_ratio_pej_departement.csv"
    merged.to_csv(out_dir / csv_name, sep=";", index=False)

