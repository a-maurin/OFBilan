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

#
import os
from pathlib import Path

def generer_logo_blanc():
    root = Path(__file__).resolve().parents[2]
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


def generer_favicon_ico() -> bool:
    """Génère favicon.ico avec résolutions multi-tailles à partir de icon.png si absent."""
    web_dir = Path(__file__).resolve().parent
    png_path = web_dir / "icon.png"
    ico_path = web_dir / "favicon.ico"

    if not png_path.exists():
        return False

    try:
        from PIL import Image
        img = Image.open(png_path)
        img.save(
            ico_path,
            format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        )
        return True
    except Exception as e:
        print(f"Erreur lors de la génération du favicon : {e}")
        return False


if __name__ == "__main__":
    generer_logo_blanc()
    generer_favicon_ico()