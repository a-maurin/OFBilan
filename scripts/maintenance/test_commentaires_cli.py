# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.

"""
========================================================================================
SCRIPT DE TEST EN CONSOLE DES COMMENTAIRES AUTOMATIQUES (`test_commentaires_cli.py`)
========================================================================================
Ce script permet de prévisualiser directement dans la console les textes de commentaires
générés par `commentaires_auto.py` pour un dossier de bilan donné, sans produire de PDF.

Usage :
  python scripts/test_commentaires_cli.py --out-dir data/out/bilan_global_21
========================================================================================
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Ajustement du PATH Python si besoin
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
from core.engine.commentaires_auto import get_comment_text
from core.common.utilitaires_metier import _load_csv_opt


def _find_load_csv(out_dir: Path, patterns: list[str]) -> pd.DataFrame | None:
    for name in patterns:
        df = _load_csv_opt(out_dir, name)
        if df is not None and not df.empty:
            return df
    for p in out_dir.glob("*.csv"):
        for pat in patterns:
            key = pat.replace(".csv", "")
            if key in p.name:
                df = _load_csv_opt(out_dir, p.name)
                if df is not None and not df.empty:
                    return df
    return None


class MockPdfContext:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.presentation_cfg = {}
        self.act_theme = _find_load_csv(out_dir, ["synthese_activite_theme.csv", "par_theme.csv", "activite_theme.csv"])
        self.tab_resultats = _find_load_csv(out_dir, ["resultats_controles.csv", "resultats.csv"])
        self.agg_usager = _find_load_csv(out_dir, ["synthese_activite_usager.csv", "par_usager.csv", "activite_usager.csv"])
        
        col_nb = "nb_total" if self.act_theme is not None and "nb_total" in self.act_theme.columns else "nb"
        self.nb_localisations = (
            int(self.act_theme[col_nb].astype(float).sum())
            if self.act_theme is not None and not self.act_theme.empty and col_nb in self.act_theme.columns
            else 0
        )


def main():
    parser = argparse.ArgumentParser(description="Prévisualisation des commentaires automatiques")
    parser.add_argument("--out-dir", type=str, required=True, help="Dossier de données de sortie (ex: data/out/bilan_global_21)")
    args = parser.parse_args()

    out_path = Path(args.out_dir)
    if not out_path.is_dir():
        print(f"[ERREUR] Le dossier spécifié n'existe pas : {out_path}")
        sys.path.exit(1)

    print(f"\n=======================================================")
    print(f" PREVISUALISATION DES COMMENTAIRES — {out_path.name}")
    print(f"=======================================================\n")

    ctx = MockPdfContext(out_path)

    sections = [
        ("sec21_themes", "Section 2.1 — Thèmes de contrôle"),
        ("sec22_conformite", "Section 2.2 — Résultats & Conformité"),
        ("sec4_usagers", "Section 3 — Activité par usager"),
    ]

    for sec_id, label in sections:
        comment = get_comment_text(sec_id, ctx)
        print(f"--- {label} ({sec_id}) ---")
        if comment:
            print(f"Rendu : {comment}\n")
        else:
            print("Rendu : [Aucun commentaire généré]\n")


if __name__ == "__main__":
    main()
