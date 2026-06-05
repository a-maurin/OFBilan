import urllib.request
import json
import yaml
import re

url = 'https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/datasets/api-lannuaire-administration/records?limit=100&refine=nom:%22Office+fran%C3%A7ais+de+la+biodiversit%C3%A9%22'

annuaire = {}

def get_dept_from_name(nom, code_postal):
    match = re.search(r'\((.*?)\)', nom)
    if match:
        dept_num = match.group(1).strip()
        if dept_num.isdigit():
            return dept_num.zfill(2)
    # try from code_postal
    if code_postal:
        if code_postal.startswith('97'):
            return code_postal[:3]
        return code_postal[:2]
    return None

try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode('utf-8'))
    results = data.get('results', [])
    
    for r in results:
        nom = r.get('nom', '')
        if "Service départemental" in nom:
            adresses = r.get('adresse', [])
            email = r.get('adresse_courriel', '')
            tel = ''
            if r.get('telephone'):
                tel = r.get('telephone')[0].get('valeur', '')
                
            if adresses:
                addr = adresses[0]
                numero = addr.get('numero_voie', '')
                type_voie = addr.get('type_voie', '')
                nom_voie = addr.get('nom_voie', '')
                cp = addr.get('code_postal', '')
                commune = addr.get('nom_commune', '')
                
                rue = f"{numero} {type_voie} {nom_voie}".strip()
                rue = re.sub(r'\s+', ' ', rue)
                
                dept = get_dept_from_name(nom, cp)
                if dept:
                    annuaire[dept] = {
                        'nom': nom,
                        'adresse': rue,
                        'code_postal': cp,
                        'ville': commune,
                        'email': email,
                        'telephone': tel
                    }

    # Custom overrides
    annuaire['25'] = {
        'nom': "Service départemental de l'Office français de la biodiversité - Doubs (25)",
        'adresse': "7 Clos Noyers",
        'code_postal': "25530",
        'ville': "Vercel-Villedieu-le-Camp",
        'email': "sd25@ofb.gouv.fr",
        'telephone': "03 81 58 39 65"
    }

    with open('config/annuaire_ofb.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(annuaire, f, allow_unicode=True, sort_keys=True)
    
    print(f"Generated annuaire_ofb.yaml with {len(annuaire)} entries.")

except Exception as e:
    print('Error:', e)
