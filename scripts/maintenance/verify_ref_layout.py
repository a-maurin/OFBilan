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
SCRIPT DE DIAGNOSTIC : VERIFICATION DU LAYOUT DE REFERENTIEL (`verify_ref_layout.py`)
========================================================================================
Ce script d'intégrité contrôle la structure du dossier `ref/` (référentiels obligatoires).

Vérifications effectuées :
  1. Présence de tous les fichiers référentiels indispensables (`types_usagers.csv`, `liste_natinf.csv`).
  2. Présence des couches SIG de base (`bilans_carte.qgz`, `emprise_dep.gpkg`, SHP communes/PNF).
  3. Détection des doublons ou des anciens dossiers déplacés.
========================================================================================
"""
from __future__ import annotations

import sys
from pathlib import Path


def _count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for p in directory.rglob("*") if p.is_file())


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    if len(sys.argv) > 1:
        repo = Path(sys.argv[1]).resolve()

    ref = repo / "ref"
    prog = ref / "programme"
    hp = ref / "hors_programme"

    errors: list[str] = []
    warnings: list[str] = []

    for name in ("sig", "tables_reference", "modele_ofb"):
        if (ref / name).exists():
            errors.append(f"Ancien emplacement encore présent : ref/{name}")

    for nested in (
        "programme/sig/communes_pnf/communes_pnf",
        "programme/sig/PNF/PNF",
        "hors_programme/modele_ofb/modele_ofb",
    ):
        if (ref / nested).exists():
            errors.append(f"Dossier imbriqué en double : ref/{nested}")

    expected = [
        "programme/tables_reference/types_usagers.csv",
        "programme/tables_reference/ref_themes_ctrl.csv",
        "programme/tables_reference/tub_communes.csv",
        "programme/tables_reference/communes_PNF.csv",
        "programme/tables_reference/liste_natinf.csv",
        "programme/sig/bilans_carte.qgz",
        "programme/sig/emprise_dep.gpkg",
        "programme/sig/pve_agrainage_points_centroides.gpkg",
        "programme/sig/communes_pnf/communes_pnf.shp",
        "programme/sig/communes_pnf/communes_PNF_centroides.shp",
        "programme/sig/PNF/coeur_pnforets/Coeur_data_gouv_PNForets.shp",
        "programme/sig/PNF/aoa_2021_pnforets/AOA_2021_PNForets.shp",
        "programme/sig/communes_21/communes.shp",
        "programme/sig/communes_21/communes.csv",
        "programme/modele_ofb/bloc-marque-RF-OFB_horizontal.jpg",
        "programme/modele_ofb/word/media/image3.jpeg",
        "programme/modele_ofb/word/media/image4.png",
        "programme/modele_ofb/word/media/image4.jpeg",
        "programme/modele_ofb/word/media/image5.jpg",
        "programme/modele_ofb/word/media/image6.jpeg",
    ]
    for rel in expected:
        if not (ref / rel).exists():
            errors.append(f"Manquant : ref/{rel}")

    for name in (
        "types_usagers.csv",
        "ref_themes_ctrl.csv",
        "tub_communes.csv",
        "communes_PNF.csv",
        "liste_natinf.csv",
    ):
        dup = hp / "tables_reference" / name
        if dup.exists():
            warnings.append(
                f"Doublon actif dans hors_programme (à retirer) : tables_reference/{name}"
            )

    for rel in ("README.md", "programme/README.md", "hors_programme/README.md"):
        if not (ref / rel).exists():
            warnings.append(f"Documentation absente : ref/{rel}")

    n_prog = _count_files(prog)
    n_hp = _count_files(hp)

    print(f"Vérification ref/ — racine : {repo}")
    print(f"Fichiers : programme={n_prog}  hors_programme={n_hp}")

    if warnings:
        print("\nAvertissements :")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print("\nErreurs :")
        for e in errors:
            print(f"  - {e}")
        print("\nÉchec.")
        return 1

    print("\nOK — arborescence ref/ conforme.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())