#!/usr/bin/env python3
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
SCRIPT DE DEPLOIEMENT : EMPAQUETAGE DES REFERENTIELS (`build_pack.py`)
========================================================================================
Ce script génère l'archive de déploiement `pack_configuration_referentiels.zip` dans le dossier
`distribution/` pour permettre l'installation des référentiels SIG et configurations OFBilan.

Étapes automatisées :
  1. Contrôle de l'arborescence via `verify_ref_layout.py`.
  2. Empaquetage compressé des dossiers `ref/` et des référentiels cartographiques.
  3. Copie du script d'installation Windows `installer_pack.bat`.
========================================================================================
"""
from __future__ import annotations

import os
import sys
import zipfile
import subprocess
from pathlib import Path


def create_pack() -> int:
    project_root = Path(__file__).resolve().parents[1]
    
    # 1. Vérification
    print("Vérification de l'intégrité des référentiels...")
    verify_script = project_root / "scripts" / "verify_ref_layout.py"
    r = subprocess.run([sys.executable, str(verify_script), str(project_root)], cwd=project_root)
    if r.returncode != 0:
        print("Erreur : La vérification des référentiels a échoué. Corrigez les erreurs avant d'empaqueter.", file=sys.stderr)
        return r.returncode

    # 2. Empaquetage
    dist_dir = project_root / "distribution"
    dist_dir.mkdir(exist_ok=True)
    zip_path = dist_dir / "pack_configuration_referentiels.zip"
    
    print(f"\nCréation de l'archive : {zip_path}")
    
    targets = ["ref"]
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Assurer la structure pour data/sources
        zipf.writestr("data/sources/.gitkeep", "")
        
        for tgt in targets:
            src_dir = project_root / tgt
            if not src_dir.exists():
                print(f"Note : Le dossier {tgt} n'existe pas, ignoré.")
                continue
                
            for root, dirs, files in os.walk(src_dir):
                for file in files:
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(project_root)
                    print(f"Ajout : {rel_path}")
                    zipf.write(file_path, rel_path)

    print("\nArchive ZIP créée avec succès dans le dossier 'distribution'.")
    
    # 3. Copie du script d'installation
    import shutil
    installer_script = project_root / "scripts" / "installer_pack.bat"
    if installer_script.exists():
        shutil.copy2(installer_script, dist_dir / "installer_pack.bat")
        print(f"Script d'installation copié : {dist_dir / 'installer_pack.bat'}")
    
    return 0


if __name__ == "__main__":
    sys.exit(create_pack())