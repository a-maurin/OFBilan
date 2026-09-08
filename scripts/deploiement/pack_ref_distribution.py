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
SCRIPT DE EMBALLAGE DISTRIBUTION : REFERENTIELS PROGRAMME (`pack_ref_distribution.py`)
========================================================================================
Ce script empaquette l'arborescence des référentiels officiels (`ref/programme/`)
pour la distribution autonome ou le transfert inter-postes.

Output :
  Dossier `distribution/Bilans_ref_<AAAAMMJJ>/` contenant les gabarits, le fichier
  `LISEZMOI_REF.md` et les données cartographiques de base.
========================================================================================
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Prépare un dossier ref/ à copier-coller.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Dossier de sortie (défaut : distribution/Bilans_ref_<date> sous la racine projet)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Ne pas exécuter verify_ref_layout avant l'empaquetage",
    )
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    src_prog = repo / "ref" / "programme"
    guide = repo / "docs" / "distribution" / "GUIDE_REF_INSTALLATION.md"

    if not src_prog.is_dir():
        print(f"Erreur : {src_prog} introuvable.", file=sys.stderr)
        return 1

    if not args.no_verify:
        import subprocess

        r = subprocess.run(
            [sys.executable, str(repo / "scripts" / "verify_ref_layout.py"), str(repo)],
            cwd=repo,
        )
        if r.returncode != 0:
            print("Empaquetage annulé : corrigez ref/ puis relancez.", file=sys.stderr)
            return r.returncode

    stamp = date.today().strftime("%Y%m%d")
    out_root = args.output or (repo / "distribution" / f"Bilans_ref_{stamp}")
    out_root = out_root.resolve()
    dest_ref = out_root / "ref"

    if out_root.exists():
        print(f"Suppression de l'ancien paquet : {out_root}")
        try:
            shutil.rmtree(out_root)
        except OSError as err:
            print(f"Erreur lors de la suppression de l'ancien paquet : {err}", file=sys.stderr)
            return 1

    try:
        out_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_prog, dest_ref / "programme")

        root_readme = repo / "ref" / "README.md"
        if root_readme.is_file():
            shutil.copy2(root_readme, dest_ref / "README.md")

        if guide.is_file():
            shutil.copy2(guide, out_root / "LISEZMOI_REF.md")
            shutil.copy2(guide, dest_ref / "LISEZMOI_fichiers.md")
    except OSError as err:
        print(f"Erreur E/S lors de la création du paquet : {err}", file=sys.stderr)
        return 1

    n_files = sum(1 for _ in dest_ref.rglob("*") if _.is_file())
    print(f"Paquet créé : {out_root}")
    print(f"  - {n_files} fichiers sous ref/")
    print(f"  - Guide : {out_root / 'LISEZMOI_REF.md'}")
    print()
    print("Transmettre le dossier complet au destinataire ; il copie 'ref/' à la racine de Bilans_production.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())