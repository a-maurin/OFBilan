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
SCRIPT DE MAINTENANCE : VERIFICATION DES EN-TETES DE COPYRIGHT (`ajouter_entetes_copyright.py`)
========================================================================================
Ce script utilitaire parcourt de manière récursive l'ensemble du projet pour s'assurer
que tous les fichiers source Python comportent la notice de licence GNU GPL v3 ainsi que
la clause obligatoire d'attribution (Section 7b).
========================================================================================
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FULL_HEADER = """# Copyright (C) 2026 Aguirre MAURIN
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

REQUIRED_MARKER = "CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3)"

def fix_header(py_file: Path) -> bool:
    content = py_file.read_text(encoding="utf-8")
    
    # Si le fichier a déjà l'en-tête complet avec la section 7(b)
    if REQUIRED_MARKER in content:
        return False
    
    # Traitement des fichiers avec shebang (#!/usr/bin/env python)
    lines = content.splitlines(True)
    shebang = ""
    start_idx = 0
    if lines and lines[0].startswith("#!"):
        shebang = lines[0]
        start_idx = 1

    # Supprimer l'ancien en-tête court s'il est au début
    remaining = lines[start_idx:]
    while remaining and (remaining[0].strip().startswith("# Copyright") or remaining[0].strip() == "#"):
        remaining.pop(0)

    new_content = shebang + FULL_HEADER + "".join(remaining)
    py_file.write_text(new_content, encoding="utf-8")
    return True

def main():
    fixed_count = 0
    total_count = 0
    
    # Scanner tous les fichiers .py du projet en ignorant les dossiers virtuels et dist
    for py_file in ROOT.rglob("*.py"):
        # Ignorer .venv, venv, build, dist, egg-info, temp
        rel_str = str(py_file.relative_to(ROOT))
        if any(ignored in rel_str for ignored in (".venv", "venv", "distribution", "egg-info", ".pytest_cache", ".git")):
            continue
            
        total_count += 1
        if fix_header(py_file):
            print(f"En-tête mis à jour : {rel_str}")
            fixed_count += 1
            
    print(f"\nVérification terminée : {fixed_count}/{total_count} fichier(s) mis à jour avec l'en-tête complet GPL v3 + Section 7(b).")

if __name__ == "__main__":
    main()
