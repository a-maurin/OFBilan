"""
Wrapper Python pour la génération de cartes.

Pour l'instant, ce script délègue au lanceur existant basé sur QGIS
(`src/bilans/cartographie/lancer_production_cartographique.bat`),
ce qui permet d'avoir un point d'entrée CLI stable :

    python src/bilans/cartographie/generer_cartes.py --profil agrainage --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Génération de cartes (wrapper QGIS).")
    parser.add_argument("--profil", type=str, default="tous", help="Profil de carte (agrainage, chasse, ... ou 'tous').")
    parser.add_argument("--date-deb", type=str, required=True, help="Date début (YYYY-MM-DD).")
    parser.add_argument("--date-fin", type=str, required=True, help="Date fin (YYYY-MM-DD).")
    parser.add_argument("--dept-code", type=str, default="21", help="Code département (ex. 21).")
    args = parser.parse_args()

    launcher = Path(__file__).resolve().parent / "lancer_production_cartographique.bat"
    if not launcher.exists():
        print(f"Erreur : lanceur QGIS introuvable : {launcher}", file=sys.stderr)
        return 1

    cmd = [
        str(launcher),
        args.profil,
        "--date-deb",
        args.date-deb,
        "--date-fin",
        args.date-fin,
        "--dept-code",
        args.dept-code,
    ]

    try:
        return subprocess.call(cmd)
    except OSError as e:
        print(f"Erreur lors de l'appel au lanceur QGIS : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

