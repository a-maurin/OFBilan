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

"""Script d'annotation automatique des fichiers de tests unitaires."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests" / "unit"

def annotate_test_file(path: Path):
    content = path.read_text(encoding="utf-8")
    if "========================================================================================" in content:
        return False
    
    stem = path.stem
    readable_name = stem.replace("test_", "").replace("_", " ").upper()
    
    header = f'''"""
========================================================================================
TEST UNITAIRE : {readable_name} (`{path.name}`)
========================================================================================
Ce fichier de test Pytest vérifie le bon fonctionnement du composant `{stem.replace("test_", "")}`.

Objectifs de vérification :
  1. Valider la conformité des règles métier et des calculs d'agrégation.
  2. Prévenir toute régression lors des modifications futures du code.
========================================================================================
"""
'''
    # Insérer le header juste après la licence GPL
    lic_marker = "# de l'auteur original (Aguirre MAURIN).\n"
    if lic_marker in content:
        parts = content.split(lic_marker, 1)
        new_content = parts[0] + lic_marker + "\n" + header + parts[1].lstrip("#\n\r ")
        path.write_text(new_content, encoding="utf-8")
        return True
    return False

def main():
    count = 0
    for p in TESTS_DIR.glob("*.py"):
        if annotate_test_file(p):
            count += 1
            print(f"Annoté : {p.name}")
    print(f"Terminé : {count} fichier(s) de test annoté(s).")

if __name__ == "__main__":
    main()
