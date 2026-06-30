# -*- coding: utf-8 -*-
"""Gestion de la persistance des paramètres utilisateur du plugin OFBilan."""

import os
import json
from pathlib import Path
from typing import Dict, Any

# Valeurs par défaut globales
DEFAUT_PARAMETRES: Dict[str, Any] = {
    "profil": {
        "nom": "",
        "prenom": "",
        "service": ""
    },
    "geo": {
        "code_geo_defaut": "",
        "annee_reference": 2024
    },
    "ui": {
        "vue_lancement": "explorer",
        "theme": "clair",
        "zoom_defaut": 8
    },
    "carto": {
        "fond_plan": "OSM",
        "options_infobulles": {}
    },
    "export": {
        "dpi": 300,
        "inclure_donnees_brutes": False
    },
    "systeme": {
        "dossier_export": str(Path.home() / "Documents" / "OFBilan_Exports"),
        "proxy": ""
    },
    "tech": {
        "port_serveur": 5000,
        "mode_debug": False
    }
}

def get_settings_file_path() -> Path:
    """Retourne le chemin absolu vers le fichier de paramètres utilisateur."""
    # Stockage dans le profil utilisateur Windows (~/.ofbilan/user_settings.json)
    base_dir = Path.home() / ".ofbilan"
    # Création du dossier s'il n'existe pas
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "user_settings.json"

def _fusion_recursif(dict_base: Dict[str, Any], dict_mise_a_jour: Dict[str, Any]) -> Dict[str, Any]:
    """Fusionne récursivement deux dictionnaires."""
    resultat = dict_base.copy()
    for cle, valeur in dict_mise_a_jour.items():
        if isinstance(valeur, dict) and cle in resultat and isinstance(resultat[cle], dict):
            resultat[cle] = _fusion_recursif(resultat[cle], valeur)
        else:
            resultat[cle] = valeur
    return resultat

def lire_parametres() -> Dict[str, Any]:
    """Lit les paramètres depuis le fichier JSON. Renvoie les valeurs par défaut si absent."""
    fichier = get_settings_file_path()
    parametres = DEFAUT_PARAMETRES.copy()

    if fichier.exists():
        try:
            with open(fichier, 'r', encoding='utf-8') as f:
                donnees_json = json.load(f)
                parametres = _fusion_recursif(parametres, donnees_json)
        except Exception as e:
            print(f"Erreur lors de la lecture des paramètres : {e}")

    return parametres

def sauvegarder_parametres(nouveaux_parametres: Dict[str, Any]) -> None:
    """Sauvegarde les paramètres fournis dans le fichier JSON."""
    fichier = get_settings_file_path()
    
    parametres_actuels = lire_parametres()
    parametres_fusionnes = _fusion_recursif(parametres_actuels, nouveaux_parametres)
    
    try:
        with open(fichier, 'w', encoding='utf-8') as f:
            json.dump(parametres_fusionnes, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erreur lors de la sauvegarde des paramètres : {e}")
