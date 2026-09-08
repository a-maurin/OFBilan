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
SCRIPT DE RESTAURATION : DECOMPRESSION DES REFERENTIELS (`restaurer_referentiel.py`)
========================================================================================
Ce script décompresse l'archive `pack_configuration_referentiels.zip` directement à la racine
du projet pour rétablir ou mettre à jour les dossiers `ref/` et `data/`.
========================================================================================
"""
import zipfile
from pathlib import Path

def restaurer():
    root = Path(__file__).resolve().parents[1]
    zip_path = root / "pack_configuration_referentiels.zip"
    
    if not zip_path.exists():
        print("Erreur : pack_configuration_referentiels.zip introuvable à la racine.")
        return

    print("Décompression de pack_configuration_referentiels.zip en cours...")
    with zipfile.ZipFile(zip_path, 'r') as z:
        # Extraire tout à la racine (les chemins dans le zip devraient commencer par ref/ ou data/)
        z.extractall(root)
    
    print("Décompression terminée ! Le dossier ref/ devrait être complet.")

if __name__ == "__main__":
    restaurer()