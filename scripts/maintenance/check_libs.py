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

import importlib.util
from pathlib import Path
import sys

# Injection du dossier des bibliothèques portables lib/
_project_root = Path(__file__).resolve().parents[2]
_lib_dir = _project_root / "lib"
if _lib_dir.is_dir() and str(_lib_dir) not in sys.path:
    sys.path.append(str(_lib_dir))

libs = [
    "pyogrio",
    "calamine",
    "pyarrow",
    "fiona",
    "openpyxl",
    "odf",
    "pypdf",
    "geopandas",
    "pandas"
]

print("\n=== Diagnostic des bibliothèques intégrées ===")
for lib in libs:
    spec = importlib.util.find_spec(lib)
    status = "OK" if spec is not None else "MANQUANT"
    print(f"  [{status}] {lib}")
print("===============================================\n")

