import os
from pathlib import Path

def generer_logo_blanc():
    root = Path(__file__).resolve().parents[3]
    src_path = root / "ref" / "programme" / "logos" / "bandeau_ofbilan.svg"
    dst_path = root / "ref" / "programme" / "logos" / "bandeau_ofbilan_blanc.svg"
    local_dst_path = Path(__file__).resolve().parent / "logo.svg"
    
    if not src_path.exists():
        print(f"Erreur : Le fichier source est introuvable : {src_path}")
        return False
        
    try:
        content = src_path.read_text(encoding="utf-8")
        # Remplacer la couleur du texte (#2c406e) par du blanc (#ffffff)
        modified = content.replace('#2c406e', '#ffffff')
        
        # Écriture dans le dossier logos d'origine
        dst_path.write_text(modified, encoding="utf-8")
        
        # Écriture dans le dossier web local
        local_dst_path.write_text(modified, encoding="utf-8")
        
        return True
    except Exception as e:
        print(f"Erreur lors de la génération du logo : {e}")
        return False

if __name__ == "__main__":
    generer_logo_blanc()
