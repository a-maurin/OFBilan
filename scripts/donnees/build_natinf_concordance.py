import os
import sys
import glob
import pandas as pd
from pathlib import Path

def find_file(sources_dir: Path, patterns):
    for pat in patterns:
        matches = list(sources_dir.glob(pat))
        if matches:
            # Sort by modification time descending
            return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    return None

def read_file(file_path: Path):
    ext = file_path.suffix.lower()
    if ext == ".csv":
        # Try semicolon then comma
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline()
            sep = ';' if ';' in first_line else ','
            return pd.read_csv(file_path, sep=sep, dtype=str, encoding='utf-8', on_bad_lines='skip')
        except Exception:
            return pd.read_csv(file_path, dtype=str, on_bad_lines='skip')
    elif ext in (".ods", ".xlsx", ".xls"):
        engine = "odf" if ext == ".ods" else None
        return pd.read_excel(file_path, dtype=str, engine=engine)
    elif ext == ".parquet":
        return pd.read_parquet(file_path)
    return pd.DataFrame()

def main():
    root = Path(__file__).resolve().parent.parent
    sources_dir = root / "data" / "sources"
    ref_dir = root / "ref" / "programme" / "tables_reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    output_csv = ref_dir / "concordance_natinf_snc.csv"

    print(f"Racine du projet : {root}")
    print(f"Recherche des fichiers sources dans : {sources_dir}")

    # 1. Charger la liste de référence officielle des NATINF pour les libellés
    ref_natinf_file = (
        find_file(root / "ref" / "programme" / "tables_reference", ["liste_natinf.csv", "liste-natinf-avril2023.csv", "liste_natinf*.csv"])
        or find_file(sources_dir, ["liste_natinf.csv", "liste-natinf-avril2023.csv", "liste_natinf*.csv"])
    )
    natinf_labels = {}
    if ref_natinf_file:
        print(f"Référentiel libellés NATINF trouvé : {ref_natinf_file}")
        df_ref = read_file(ref_natinf_file)
        num_col = next((c for c in df_ref.columns if c.lower().strip() in ("numero_natinf", "numéro natinf", "natinf", "code_natinf")), None)
        lib_col = next((c for c in df_ref.columns if "qualification" in c.lower() or "libelle" in c.lower() or "libellé" in c.lower()), None)
        if num_col and lib_col:
            for _, row in df_ref.iterrows():
                code = str(row[num_col]).strip().lstrip('0')
                lib = str(row[lib_col]).strip() if pd.notna(row[lib_col]) else ""
                if code and lib:
                    natinf_labels[code] = lib
        print(f"Libellés NATINF chargés depuis le référentiel : {len(natinf_labels)}")

    # 2. Extraire les NATINF uniques de la source PVe
    pve_file = find_file(sources_dir, ["Stats_PVe_OFB*.csv", "Stats_PVe_OFB*.ods", "Stats_PVe_OFB*.xlsx"])
    pve_natinf_set = set()
    pve_natinf_labels_local = {}

    if pve_file:
        print(f"Source PVe trouvée : {pve_file.name}")
        df_pve = read_file(pve_file)
        nat_col = next((c for c in df_pve.columns if any(k in c.upper() for k in ["NATINF", "INF-NATINF", "NUMERO_NATINF", "CODE_NATINF"])), None)
        
        # Filtrer strictement la colonne des libellés PVe pour exclure les services/organismes
        lib_pve_col = None
        for c in df_pve.columns:
            cu = c.upper()
            if any(bad in cu for bad in ["SERVICE", "ORGANISME", "UNITE", "UNITÉ", "AGENT", "STRUCTURE", "ENTITE", "ENTITÉ", "DEPARTEMENT", "DÉPARTEMENT"]):
                continue
            if "NATINF" in cu or "QUALIFICATION" in cu or ("LIBELLE" in cu and "INFRACTION" in cu):
                lib_pve_col = c
                break

        if nat_col:
            for _, row in df_pve.iterrows():
                val = row[nat_col]
                if pd.notna(val):
                    c_str = str(val).strip().lstrip('0')
                    if c_str and c_str.isdigit():
                        pve_natinf_set.add(c_str)
                        if lib_pve_col and pd.notna(row[lib_pve_col]):
                            pve_natinf_labels_local[c_str] = str(row[lib_pve_col]).strip()
        print(f"Nombre de NATINF uniques identifiées dans PVe : {len(pve_natinf_set)}")
    else:
        print("ATTENTION : Aucun fichier source PVe trouvé dans data/sources")

    # 3. Analyser la source PEJ pour les correspondances Domaine, Thème, Action
    pej_file = find_file(sources_dir, ["suivi_procedure_enq_judiciaire_*.ods", "suivi_procedure_enq_judiciaire_*.xlsx", "suivi_procedure_enq_judiciaire_*.csv", "*pej*.ods", "*pej*.xlsx", "*pej*.csv"])
    pej_mappings = {}

    if pej_file:
        print(f"Source PEJ trouvée : {pej_file.name}")
        df_pej = read_file(pej_file)
        
        # Chercher colonnes NATINF, DOMAINE, THEME, ACTION
        pej_nat_col = next((c for c in df_pej.columns if "NATINF" in str(c).upper()), None)
        pej_dom_col = next((c for c in df_pej.columns if "DOMAINE" in str(c).upper()), None)
        pej_thm_col = next((c for c in df_pej.columns if "THEME" in str(c).upper() or "THÉMATIQUE" in str(c).upper() or "THEMATIQUE" in str(c).upper()), None)
        pej_act_col = next((c for c in df_pej.columns if "ACTION" in str(c).upper()), None)

        print(f"Colonnes identifiées dans PEJ : NATINF={pej_nat_col}, DOMAINE={pej_dom_col}, THEME={pej_thm_col}, ACTION={pej_act_col}")

        if pej_nat_col and pej_dom_col:
            # Récolter les occurrences (NATINF -> List[(Domaine, Thème, Action)])
            records = []
            for _, row in df_pej.iterrows():
                nat_val = row[pej_nat_col]
                if pd.notna(nat_val):
                    code = str(nat_val).strip().lstrip('0')
                    if code:
                        dom = str(row[pej_dom_col]).strip() if pej_dom_col and pd.notna(row[pej_dom_col]) else ""
                        thm = str(row[pej_thm_col]).strip() if pej_thm_col and pd.notna(row[pej_thm_col]) else ""
                        act = str(row[pej_act_col]).strip() if pej_act_col and pd.notna(row[pej_act_col]) else ""
                        if dom:
                            records.append({'code': code, 'domaine': dom, 'theme': thm, 'action': act})

            if records:
                df_rec = pd.DataFrame(records)
                # Trouver le trio (domaine, theme, action) le plus fréquent par code NATINF
                grouped = df_rec.groupby(['code', 'domaine', 'theme', 'action']).size().reset_index(name='count')
                sorted_grp = grouped.sort_values(['code', 'count'], ascending=[True, False])
                majoritaires = sorted_grp.drop_duplicates(subset=['code'], keep='first')

                for _, row in majoritaires.iterrows():
                    pej_mappings[row['code']] = {
                        'domaine_snc': row['domaine'],
                        'theme_snc': row['theme'],
                        'action_snc': row['action']
                    }
                print(f"NATINF croisées avec succès depuis PEJ : {len(pej_mappings)}")

    # 4. Générer le DataFrame final de concordance uniquement pour les NATINF PVe
    rows = []
    # Trier par numéro NATINF sous forme d'entier si possible
    sorted_pve_natinfs = sorted(list(pve_natinf_set), key=lambda x: int(x) if x.isdigit() else x)

    # Règles de déduction automatique basées sur le classeur 231222 Plans de contrôle OSCEAN 2024.xlsx
    snc_deduction_rules = [
        (r"PARC NATIONAL", 
         "Espaces protégés et protection des milieux et du cadre de vie", 
         "Contrôles aires protégées (SNC 5.1)", 
         "Parcs nationaux (SNC 5.1)"),
        (r"RESERVE NATURELLE|RÉSERVE NATURELLE", 
         "Espaces protégés et protection des milieux et du cadre de vie", 
         "Contrôles aires protégées (SNC 5.1)", 
         "Réglementation réserves naturelles (SNC 5.1)"),
        (r"INCENDIE DE FORET|TERRAIN BOISE|FORET|FORÊT", 
         "Espaces protégés et protection des milieux et du cadre de vie", 
         "Contrôles espaces protégés et protection des milieux et du cadre de vie (hors SNC)", 
         "Protection des milieux forestiers (dont lutte contre les incendies)"),
        (r"PUBLICITE|ENSEIGNE|PREENSEIGNE", 
         "Espaces protégés et protection des milieux et du cadre de vie", 
         "Contrôles espaces protégés et protection des milieux et du cadre de vie (hors SNC)", 
         "Réglementation publicité, enseignes et préenseignes"),
        (r"PECHE|PÊCHE|POISSON|CARPE|ECLUSE|DISPOSITIF ASSURANT LA CIRCULATION", 
         "Assurer la protection des espèces animales et végétales", 
         "Pêche", 
         "Actions de contrôle de la pêche (hors SNC)"),
        (r"PHYTOPHARMACEUTIQUE", 
         "Gestion qualitative de la ressource en eau", 
         "Pollutions diffuses", 
         "Assurer le respect des conditions d'emplois des produits phytopharmaceutiques afin de préserver la qualité de l'eau et des milieux aquatiques (SNC 2.5)"),
        (r"VACCINATION|RAGE|CARNIVORE", 
         "Assurer la protection des espèces animales et végétales", 
         "Faune sauvage captive", 
         "Contrôles sanitaires et faune captive (hors SNC)"),
    ]

    # Dictionnaire de conversion pour remplacer les libellés PEJ historiques 'Inactif-' par les libellés actuels
    inactif_conversions = {
        "3487": ("Assurer la protection des espèces animales et végétales", "Chasse", "Actions contrôles chasse hors priorités SNC"),
        "7384": ("Assurer la protection des espèces animales et végétales", "Pêche", "Actions de contrôle de la pêche (hors SNC)"),
        "7422": ("Assurer la protection des espèces animales et végétales", "Pêche", "Actions de contrôle de la pêche (hors SNC)"),
        "7930": ("Espaces protégés et protection des milieux et du cadre de vie", "Contrôles espaces protégés et protection des milieux et du cadre de vie (hors SNC)", "Protection des milieux forestiers (dont lutte contre les incendies)"),
        "11952": ("Espaces protégés et protection des milieux et du cadre de vie", "Contrôles espaces protégés et protection des milieux et du cadre de vie (hors SNC)", "Contrôle de la circulation des VTM (hors espaces protégés)"),
        "20141": ("Assurer la protection des espèces animales et végétales", "Pêche", "Actions de contrôle de la pêche (hors SNC)"),
        "20148": ("Assurer la protection des espèces animales et végétales", "Pêche", "Actions de contrôle de la pêche (hors SNC)"),
        "20150": ("Assurer la protection des espèces animales et végétales", "Pêche", "Actions de contrôle de la pêche (hors SNC)"),
        "20155": ("Assurer la protection des espèces animales et végétales", "Pêche", "Actions de contrôle de la pêche (hors SNC)"),
        "20156": ("Assurer la protection des espèces animales et végétales", "Pêche", "Actions de contrôle de la pêche (hors SNC)"),
        "20158": ("Assurer la protection des espèces animales et végétales", "Pêche", "Actions de contrôle de la pêche (hors SNC)"),
        "20160": ("Assurer la protection des espèces animales et végétales", "Pêche", "Actions de contrôle de la pêche (hors SNC)"),
        "21322": ("Gestion qualitative de la ressource en eau", "Pollutions diffuses", "Pollutions diffuses / Nitrates (SNC 2.1)"),
        "21468": ("Assurer la protection des espèces animales et végétales", "Pêche", "Actions de contrôle de la pêche (hors SNC)"),
        "25950": ("Espaces protégés et protection des milieux et du cadre de vie", "Contrôles aires protégées (SNC 5.1)", "Réglementation réserves naturelles (SNC 5.1)"),
        "26145": ("Espaces protégés et protection des milieux et du cadre de vie", "Contrôles espaces protégés et protection des milieux et du cadre de vie (hors SNC)", "Protection des milieux forestiers (dont lutte contre les incendies)"),
        "26276": ("Assurer la protection des espèces animales et végétales", "Chasse", "Actions contrôles chasse hors priorités SNC"),
        "26296": ("Assurer la protection des espèces animales et végétales", "Chasse", "Actions contrôles chasse hors priorités SNC"),
        "26298": ("Assurer la protection des espèces animales et végétales", "Chasse", "Contrôle du respect des quotas collectifs et des obligations de déclaration de prélèvement de certaines espèces (SNC 4.5)"),
        "26511": ("Hors domaine", "Hors thème", "[2025] Activités humaines réglementées dans les espaces ordinaires (déchets dans le milieu naturel au titre du code pénal)"),
        "29539": ("Espaces protégés et protection des milieux et du cadre de vie", "Contrôles espaces protégés et protection des milieux et du cadre de vie (hors SNC)", "Protection des milieux forestiers (dont lutte contre les incendies)"),
    }

    for code in sorted_pve_natinfs:
        libelle = natinf_labels.get(code) or pve_natinf_labels_local.get(code) or ""
        mapping = pej_mappings.get(code)

        if code in inactif_conversions:
            dom, thm, act = inactif_conversions[code]
            statut = "Converti (Inactif -> Actuel)"
        elif mapping:
            dom = mapping['domaine_snc']
            thm = mapping['theme_snc']
            act = mapping['action_snc']
            statut = "Proposé (PEJ majoritaire)"
            # Si malgré tout le domaine commence par Inactif-, nettoyer
            if str(dom).startswith("Inactif"):
                dom = dom.replace("Inactif-", "").strip()
            if str(thm).startswith("Inactif"):
                thm = thm.replace("Inactif-", "").strip()
            if str(act).startswith("Inactif"):
                act = act.replace("Inactif-", "").strip()
        else:
            dom, thm, act, statut = "", "", "", "À renseigner"
            # Tenter la déduction via les règles SNC 2024
            lib_upper = libelle.upper()
            import re
            for pat, d_val, t_val, a_val in snc_deduction_rules:
                if re.search(pat, lib_upper):
                    dom, thm, act, statut = d_val, t_val, a_val, "Déduit (SNC 2024)"
                    break

        rows.append({
            'numero_natinf': code,
            'libelle_natinf': libelle,
            'domaine_snc': dom,
            'theme_snc': thm,
            'action_snc': act,
            'statut': statut
        })

    df_out = pd.DataFrame(rows)
    # Exporter en CSV séparateur ';' avec encodage UTF-8 avec BOM pour ouverture directe dans Excel
    df_out.to_csv(output_csv, sep=';', index=False, encoding='utf-8-sig')
    print(f"\n--- Fichier généré avec succès ---")
    print(f"Chemin : {output_csv}")
    print(f"Nombre total de NATINF PVe : {len(df_out)}")
    if not df_out.empty:
        mapped_count = len(df_out[df_out['statut'] == "Proposé (PEJ majoritaire)"])
        missing_count = len(df_out[df_out['statut'] == "À renseigner"])
        print(f"NATINF pré-remplies (PEJ) : {mapped_count} ({mapped_count/len(df_out)*100:.1f}%)")
        print(f"NATINF à renseigner : {missing_count} ({missing_count/len(df_out)*100:.1f}%)")

if __name__ == "__main__":
    main()
