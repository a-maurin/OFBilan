#!/usr/bin/env python3
"""
Empaquette ref/programme/ pour transmission à un autre poste (hors Git).

Crée : distribution/Bilans_ref_<AAAAMMJJ>/ref/  + LISEZMOI_REF.md

Usage :
    python scripts/pack_ref_distribution.py
    python scripts/pack_ref_distribution.py --output "D:\\Transfert\\Bilans_ref"
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
        shutil.rmtree(out_root)

    out_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_prog, dest_ref / "programme")

    root_readme = repo / "ref" / "README.md"
    if root_readme.is_file():
        shutil.copy2(root_readme, dest_ref / "README.md")

    if guide.is_file():
        shutil.copy2(guide, out_root / "LISEZMOI_REF.md")
        shutil.copy2(guide, dest_ref / "LISEZMOI_fichiers.md")

    n_files = sum(1 for _ in dest_ref.rglob("*") if _.is_file())
    print(f"Paquet créé : {out_root}")
    print(f"  - {n_files} fichiers sous ref/")
    print(f"  - Guide : {out_root / 'LISEZMOI_REF.md'}")
    print()
    print("Transmettre le dossier complet au destinataire ; il copie 'ref/' à la racine de Bilans_production.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
