"""
Audit cohérence des totaux PVe pour un profil thématique.

Rejoue load_pve + _filter_pve (+ restriction PNF si restrict_geo: pnf) et compare
au nombre de lignes des exports pve_<prefix>.csv (hors fichiers *_par_zone).

Usage:
  python tools/audit_pve_totaux.py --profil pnf --dept 21 \\
    --date-deb 2025-01-01 --date-fin 2025-12-31 --out-dir data/out/bilan_pnf
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def list_pve_detail_csv_paths(out_dir: Path) -> list[Path]:
    """Fichiers pve_*.csv détail (exclut les agrégations type *_par_zone*)."""
    if not out_dir.is_dir():
        return []
    return sorted(
        p
        for p in out_dir.glob("pve_*.csv")
        if p.is_file() and "_par_" not in p.name
    )


def count_csv_body_rows(path: Path) -> int:
    """Nombre de lignes de données (sans l'en-tête), UTF-8 / latin1 tolérant."""
    encodings = ("utf-8-sig", "utf-8", "latin1")
    for enc in encodings:
        try:
            text = path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = path.read_bytes().decode("latin1", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return max(0, len(lines) - 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit totaux PVe (profil thématique).")
    parser.add_argument("--root", type=Path, default=ROOT, help="Racine du dépôt Bilans_production")
    parser.add_argument("--profil", required=True, help="Identifiant YAML (ex. pnf, procedures_pve)")
    parser.add_argument("--dept", required=True, help="Code département (ex. 21)")
    parser.add_argument("--date-deb", required=True, help="Date début (YYYY-MM-DD)")
    parser.add_argument("--date-fin", required=True, help="Date fin (YYYY-MM-DD)")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Dossier de sortie d'un bilan (pour comparer à pve_*.csv exporté)",
    )
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    sys.path.insert(0, str(root / "src"))

    from ofbilan.common.chargeurs_donnees import load_pve
    from ofbilan.engine.orchestrateur_profils import (
        _apply_restrict_geo_pnf,
        _filter_pve,
        load_profile_config,
    )

    if not (root / "src" / "bilans").is_dir():
        print(f"ERREUR : racine projet invalide (pas de src/bilans) : {root}")
        return 2

    profile = load_profile_config(root, str(args.profil).strip())
    sources = profile.get("sources") or {}
    if not sources.get("pve", True):
        print(
            f"AVERTISSEMENT : le profil {args.profil!r} a sources.pve=false - "
            "le moteur ne charge pas les PVe ; cet audit rejoue quand même load_pve pour comparaison manuelle."
        )

    date_deb = pd.to_datetime(args.date_deb)
    date_fin = pd.to_datetime(args.date_fin)
    dept = str(args.dept).strip()

    print(f"=== Audit PVe - profil={args.profil} dept={dept} periode={args.date_deb} -> {args.date_fin} ===\n")

    try:
        pve = load_pve(root, dept_code=dept, date_deb=date_deb, date_fin=date_fin)
    except FileNotFoundError as e:
        print(f"ERREUR chargement PVe : {e}")
        return 2

    n_load = len(pve)
    print(f"  Après load_pve (dept + INF-DATE-INTG) : {n_load} ligne(s)")

    pve_f = _filter_pve(pve, profile) if not pve.empty else pve.copy()
    n_filt = len(pve_f)
    print(f"  Après _filter_pve (NATINF / mots-clés profil) : {n_filt} ligne(s)")

    restrict = str(profile.get("restrict_geo") or "").strip().lower()
    if restrict == "pnf":
        log = logging.getLogger("ofbilan.audit_pve")
        log.setLevel(logging.WARNING)
        empty = pd.DataFrame()
        _, _, _, pve_f = _apply_restrict_geo_pnf(empty, empty, empty, pve_f, root, log)
        n_geo = len(pve_f)
        print(f"  Après restrict_geo=pnf (_apply_restrict_geo_pnf) : {n_geo} ligne(s)")
    else:
        n_geo = n_filt
        print("  Pas de restrict_geo=pnf - etape geo PNF omise pour le rejoue.")

    print(f"\n  TOTAL rejoué (cohérent nb_pve moteur si enrichissements ne changent pas le nombre de lignes) : {n_geo}")

    if args.out_dir is None:
        print("\n  (--out-dir non fourni : pas de comparaison aux CSV exportés.)")
        return 0

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = (root / out_dir).resolve()
    cands = list_pve_detail_csv_paths(out_dir)
    if not cands:
        print(f"\n  [ECART] Aucun pve_*.csv (détail) dans {out_dir}")
        return 1

    if len(cands) > 1:
        print(f"\n  Plusieurs exports detail : {[p.name for p in cands]} - utilisation de {cands[0].name}")

    csv_path = cands[0]
    n_csv = count_csv_body_rows(csv_path)
    ok = n_csv == n_geo
    mark = "OK" if ok else "ECART"
    print(f"\n  [{mark}] {csv_path.name} : {n_csv} ligne(s) de données vs rejoué={n_geo}")
    if not ok:
        print(
            "  Indices : prefixe d'export different, bilan partiel, ou jeu source modifie "
            "entre deux executions ; verifier aussi point/PEJ vides vs run reel si restrict_geo."
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
