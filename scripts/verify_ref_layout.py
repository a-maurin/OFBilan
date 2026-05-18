#!/usr/bin/env python3
"""Vérifie la cohérence de ref/programme et ref/hors_programme avec le code."""
from __future__ import annotations

import sys
from pathlib import Path


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
        "programme/sig/sd21_tout.qgz",
        "programme/sig/pochoir_sd21.gpkg",
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
        "programme/modele_ofb/word/media/image5.jpg",
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

    n_prog = sum(1 for _ in prog.rglob("*") if _.is_file()) if prog.exists() else 0
    n_hp = sum(1 for _ in hp.rglob("*") if _.is_file()) if hp.exists() else 0

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
