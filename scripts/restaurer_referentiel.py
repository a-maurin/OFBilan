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
