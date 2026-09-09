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

import pandas as pd
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
excel_path = root / "ref" / "programme" / "tables_reference" / "231222 Plans de contrôle OSCEAN 2024.xlsx"
csv_path = root / "ref" / "programme" / "tables_reference" / "concordance_natinf_snc.csv"

# 1. Charger l'ensemble des actions/thèmes/domaines du Plan de Contrôle 2024
xl = pd.ExcelFile(excel_path)
snc_entries = []

for sheet in xl.sheet_names:
    df = pd.read_excel(excel_path, sheet_name=sheet, dtype=str)
    # Chercher colonnes Domaine, Thème, Action
    dom_col = next((c for c in df.columns if "DOMAINE" in str(c).upper()), None)
    thm_col = next((c for c in df.columns if "THEME" in str(c).upper() or "THÉMATIQUE" in str(c).upper() or "THEMATIQUE" in str(c).upper()), None)
    act_col = next((c for c in df.columns if "ACTION" in str(c).upper()), None)
    
    if dom_col and thm_col and act_col:
        for _, r in df.iterrows():
            d = str(r[dom_col]).strip() if pd.notna(r[dom_col]) else ""
            t = str(r[thm_col]).strip() if pd.notna(r[thm_col]) else ""
            a = str(r[act_col]).strip() if pd.notna(r[act_col]) else ""
            if d and d.lower() != "nan":
                snc_entries.append({'domaine': d, 'theme': t, 'action': a, 'sheet': sheet})

df_snc = pd.DataFrame(snc_entries).drop_duplicates()
print(f"Nombre de trios SNC uniques chargés depuis l'Excel : {len(df_snc)}")

# Imprimer les domaines et thèmes uniques trouvés dans l'Excel
print("\nDomaines uniques SNC 2024 :")
print(df_snc['domaine'].unique())
print("\nThèmes uniques SNC 2024 :")
print(df_snc['theme'].unique())

# 2. Charger la concordance NATINF CSV
df_csv = pd.read_csv(csv_path, sep=";", dtype=str)

# Dictionnaire de règles par mots-clés de libellés NATINF vers (Domaine, Thème, Action)
rules = [
    # Parcs Nationaux
    (r"\bCOEUR D'UN PARC NATIONAL\b|\bPARC NATIONAL\b", 
     "Espaces protégés et protection des milieux et du cadre de vie", "Contrôles aires protégées (SNC 5.1)", "Parcs nationaux (SNC 5.1)"),
    
    # Réserves naturelles
    (r"\bRESERVE NATURELLE\b|\bRÉSERVE NATURELLE\b", 
     "Espaces protégés et protection des milieux et du cadre de vie", "Contrôles aires protégées (SNC 5.1)", "Réglementation réserves naturelles (SNC 5.1)"),
    
    # Conservatoire du littoral
    (r"\bCONSERVATOIRE DE L'ESPACE LITTORAL\b|\bCONSERVATOIRE DU LITTORAL\b", 
     "Espaces protégés et protection des milieux et du cadre de vie", "Contrôles aires protégées (SNC 5.1)", "Terrains conservatoire du littoral (SNC 5.1)"),

    # Réserves de chasse
    (r"\bRESERVES DE CHASSE\b|\bRÉSERVES DE CHASSE\b", 
     "Espaces protégés et protection des milieux et du cadre de vie", "Contrôles aires protégées (SNC 5.1)", "Autres aires protégées (SNC 5.1)"),

    # Forêt / Incendie / Bois
    (r"\bFORET\b|\bFORÊT\b|\bBOIS\b|\bINCENDIE DE FORET\b", 
     "Espaces protégés et protection des milieux et du cadre de vie", "Contrôles espaces protégés et protection des milieux et du cadre de vie (hors SNC)", "Protection des milieux forestiers (dont lutte contre les incendies)"),

    # Chasse / Gibier
    (r"\bCHASSE\b|\bCHASSER\b|\bGIBIER\b|\bCYNEGETIQUE\b|\bCYNÉGÉTIQUE\b|\bAGRAINAGE\b|\bAFFOURAGEMENT\b", 
     "Assurer la protection des espèces animales et végétales", "Chasse", "Actions contrôles chasse (SNC 4.5)"),

    # Pêche / Poisson
    (r"\bPECHE\b|\bPÊCHE\b|\bCARPE\b|\bPOISSON\b|\bENGIN DE PECHE\b", 
     "Assurer la protection des espèces animales et végétales", "Pêche", "Actions contrôles pêche (SNC 4.4)"),

    # Espèces protégées / Animaux / Végétaux non domestiques
    (r"\bESPECE PROTEGEE\b|\bESPÈCE PROTÉGÉE\b|\bANIMAL NON DOMESTIQUE\b|\bVEGETAL NON CULTIVE\b|\bVÉGÉTAL NON CULTIVÉ\b|\bMINERAUX OU FOSSILES\b", 
     "Assurer la protection des espèces animales et végétales", "Espèces protégées", "Espèces protégées : destructions ou perturbations d'espèces protégées, altération, dégradation et destruction d'habitat (SNC 4.3)"),

    # Déchets / Dépôts insalubres / Ordures
    (r"\bDEPOT\b|\bDÉPÔT\b|\bABANDON\b|\bORDURE\b|\bDECHET\b|\bDÉCHET\b|\bDEJECTION\b|\bDÉJECTION\b|\bLIQUIDE INSALUBRE\b", 
     "Hors domaine", "Hors thème", "[2025] Activités humaines réglementées dans les espaces ordinaires (déchets dans le milieu naturel au titre du code pénal)"),

    # Publicité / Enseignes
    (r"\bPUBLICITE\b|\bPUBLICITÉ\b|\bENSEIGNE\b|\bPREENSEIGNE\b|\bPRÉENSEIGNE\b", 
     "Espaces protégés et protection des milieux et du cadre de vie", "Contrôles espaces protégés et protection des milieux et du cadre de vie (hors SNC)", "Réglementation publicité, enseignes et préenseignes"),

    # Bruits
    (r"\bBRUIT\b|\bTRANQUILLITE\b|\bTRANQUILLITÉ\b", 
     "Espaces protégés et protection des milieux et du cadre de vie", "Contrôles espaces protégés et protection des milieux et du cadre de vie (hors SNC)", "Nuisances sonores dans la nature"),

    # Effluents / Épandage / Pollutions agricoles
    (r"\bEPANDAGE\b|\bÉPANDAGE\b|\bEFFLUENT\b|\bNITRATE\b", 
     "Gestion qualitative de la ressource en eau", "Pollutions diffuses", "Pollutions diffuses / Nitrates (SNC 2.1)"),
     
    # Digues / Ouvrages d'eau
    (r"\bDIGUE\b|\bOUVRAGE\b", 
     "Gestion quantitative de la ressource en eau", "Ouvrages et autorisations de prélèvement (SNC 3.1)", "Sécurité des ouvrages hydrauliques / Digues"),
]

updated_count = 0
doubt_list = []

for idx, row in df_csv.iterrows():
    lib = str(row['libelle_natinf']).upper()
    current_statut = str(row['statut'])
    current_dom = str(row['domaine_snc']) if pd.notna(row['domaine_snc']) else ""
    
    # Si le domaine est vide ou marqué à renseigner ou Hors domaine (à vérifier)
    matched = False
    for pattern, dom, thm, act in rules:
        if re.search(pattern, lib):
            # Si pas de domaine ou si "À renseigner"
            if not current_dom or current_statut == "À renseigner":
                df_csv.at[idx, 'domaine_snc'] = dom
                df_csv.at[idx, 'theme_snc'] = thm
                df_csv.at[idx, 'action_snc'] = act
                df_csv.at[idx, 'statut'] = "Déduit (Excel SNC 2024)"
                updated_count += 1
            matched = True
            break
            
    if not matched and (not current_dom or current_statut == "À renseigner"):
        doubt_list.append((row['numero_natinf'], row['libelle_natinf']))

df_csv.to_csv(csv_path, sep=";", index=False, encoding="utf-8-sig")
print(f"\n--- Mise à jour effectuée ---")
print(f"Nombre de NATINF enrichies automatiquement : {updated_count}")
print(f"Nombre de NATINF restant incertaines/à valider : {len(doubt_list)}")
print("\nListe des NATINF avec doute / à valider avec vous :")
for code, lib in doubt_list:
    print(f" - NATINF {code} : {lib}")
