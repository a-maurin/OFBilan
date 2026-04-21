"""
Point d'entrée unique pour les bilans thématiques (objectif 2).

Tous les profils sont désormais exécutés par le moteur unifié
(bilan_thematique_engine.py). Les anciens scripts dédiés (analyse_chasse,
analyse_agrainage, etc.) ne sont plus appelés.

Usage :
  python scripts/bilan_thematique/run_bilan_thematique.py --profil chasse --date-deb 2025-09-01 --date-fin 2026-03-01 --dept-code 21
  python scripts/bilan_thematique/run_bilan_thematique.py --profil agrainage --profil chasse
  python scripts/bilan_thematique/run_bilan_thematique.py --profil agrainage --profil chasse --combine
  python scripts/bilan_thematique/run_bilan_thematique.py --profil chasse --with-pnf --no-tub
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.common.loaders import load_ref_themes_ctrl
from scripts.common.prompt_periode import ask_periode_dept


_HIDDEN_PROFILES: set[str] = {"pnf_foret"}


def _list_profiles() -> list[str]:
    """
    Liste les identifiants de profils disponibles avec un ordre adapté à la
    console :

    1. chasse
    2. agrainage
    3. types_usager
    4. types_usager_cible
    puis tous les autres par ordre alphabétique, et hors_theme en dernier.
    """

    # Charge le référentiel principal si disponible
    themes = load_ref_themes_ctrl(_ROOT)

    # Construction d'un mapping id -> label pour l'ordonnancement
    id_to_label: dict[str, str] = {}
    if themes:
        for t in themes:
            pid = str(t.get("id", "")).strip()
            if not pid or pid in _HIDDEN_PROFILES:
                continue
            label = str(t.get("label", pid)).strip() or pid
            id_to_label[pid] = label
    else:
        # Fallback : liste basée sur les fichiers YAML disponibles
        # Nouvelle organisation : d'abord `config/profils_bilan`, puis `ref/profils_bilan`
        candidates = [
            _ROOT / "config" / "profils_bilan",
            _ROOT / "ref" / "profils_bilan",
        ]
        for ref_dir in candidates:
            if not ref_dir.exists():
                continue
            for p in ref_dir.glob("*.yaml"):
                pid = p.stem
                if pid in _HIDDEN_PROFILES:
                    continue
                id_to_label[pid] = pid

    if not id_to_label:
        return []

    # Forcer la présence du profil ciblé dans la liste si le YAML existe,
    # même s'il n'est pas déclaré dans ref_themes_ctrl.csv.
    types_usager_cible_id = "types_usager_cible"
    if types_usager_cible_id not in id_to_label:
        yaml_paths = [
            _ROOT / "config" / "profils_bilan" / f"{types_usager_cible_id}.yaml",
            _ROOT / "ref" / "profils_bilan" / f"{types_usager_cible_id}.yaml",
        ]
        if any(p.exists() for p in yaml_paths) and types_usager_cible_id not in _HIDDEN_PROFILES:
            id_to_label[types_usager_cible_id] = "Types d'usagers – ciblé"

    # Ordre prioritaire imposé
    priority_order: dict[str, int] = {
        "chasse": 0,
        "agrainage": 1,
        "types_usager": 2,
        "types_usager_cible": 3,
    }

    def _sort_key(pid: str) -> tuple[int, str]:
        # Profils cachés exclus en amont
        if pid == "hors_theme":
            # Toujours en dernier
            return (1000, "")
        base_rank = priority_order.get(pid, 10)
        label = id_to_label.get(pid, pid)
        return (base_rank, label.lower())

    all_ids = list(id_to_label.keys())
    all_ids.sort(key=_sort_key)
    return all_ids


def _resolve_profils(profils: list[str]) -> list[str]:
    """Résout les numéros (1, 2, …) en identifiants de thèmes."""
    themes = _list_profiles()
    if not themes:
        return profils
    resolved = []
    for p in profils:
        p = str(p).strip()
        if not p:
            continue
        if p.isdigit():
            n = int(p)
            if 1 <= n <= len(themes):
                resolved.append(themes[n - 1])
            else:
                resolved.append(p)
        else:
            resolved.append(p)
    return resolved


def _parse_cli_options(args: argparse.Namespace) -> dict:
    """Construit un dict d'options à partir des flags CLI."""
    opts: dict = {}
    if args.with_pnf:
        opts["pnf"] = True
    if args.no_pnf:
        opts["pnf"] = False
    if args.with_tub:
        opts["tub"] = True
    if args.no_tub:
        opts["tub"] = False
    if args.with_cartes:
        opts["cartes"] = True
    if args.no_cartes:
        opts["cartes"] = False
    if args.with_synthese:
        opts["synthese_croisee"] = True
    if args.no_synthese:
        opts["synthese_croisee"] = False

    # Options génériques KEY=VALUE (répétables). Si une clé est fournie
    # plusieurs fois, on accumule les valeurs dans une liste, ce qui permet
    # par exemple :
    #   --option type_usager_target="Agriculteur..." --option type_usager_target="Collectivité"
    for raw in (args.option or []):
        if "=" not in raw:
            continue
        k, v = raw.split("=", 1)
        k, v = k.strip(), v.strip()
        # Normalisation de la valeur
        if v.lower() in ("true", "oui", "o", "1", "yes"):
            parsed: object = True
        elif v.lower() in ("false", "non", "n", "0", "no"):
            parsed = False
        else:
            parsed = v

        if k in opts:
            existing = opts[k]
            if isinstance(existing, list):
                existing.append(parsed)
                opts[k] = existing
            else:
                opts[k] = [existing, parsed]
        else:
            opts[k] = parsed

    if getattr(args, "preset", None):
        opts["chart_preset"] = str(args.preset).strip().lower()

    return opts


def run_thematic(
    profils: list[str],
    date_deb: str,
    date_fin: str,
    dept_code: str,
    combine: bool = False,
    cli_options: dict | None = None,
) -> int:
    """Exécute un ou plusieurs bilans thématiques via le moteur unifié."""
    from scripts.bilan_thematique.bilan_thematique_engine import run_engine

    try:
        from scripts.common.carte_helper import ensure_maps_for_profiles
        # Le profil "types_usager_cible" dépend d'une sélection interactive :
        # le nom de carte attendu est carte_{types_selectionnes}.png, donc on ne
        # tente pas ici de vérifier/générer une carte générique.
        profils_cartes = [p for p in profils if p != "types_usager_cible"]
        ensure_maps_for_profiles(profils_cartes, date_deb=date_deb, date_fin=date_fin, dept_code=dept_code)
    except Exception as e:
        print(f"[WARN] Impossible de générer les cartes pour {', '.join(profils)} : {e}", file=sys.stderr)

    if combine and len(profils) > 1:
        print(f"Bilan combiné : {', '.join(profils)}")
        out_combine = _ROOT / "out" / f"bilan_combine_{'_'.join(profils)}"
        out_combine.mkdir(parents=True, exist_ok=True)
        for pid in profils:
            print(f"  Exécution profil {pid}...")
            run_engine(pid, date_deb, date_fin, dept_code, options=cli_options)
        (out_combine / "README.txt").write_text(
            f"Bilan combiné : {', '.join(profils)}\n"
            f"Période : {date_deb} au {date_fin}, département {dept_code}.\n"
            "Les rapports individuels sont dans out/bilan_<profil>/.",
            encoding="utf-8",
        )
        print(f"Résumé combiné dans {out_combine}")
        return 0

    for pid in profils:
        print(f"Exécution bilan {pid}...")
        ret = run_engine(pid, date_deb, date_fin, dept_code, options=cli_options)
        if ret != 0:
            return ret
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bilans thématiques : un ou plusieurs profils, optionnellement combinés."
    )
    parser.add_argument(
        "--profil",
        action="append",
        dest="profils",
        metavar="ID",
        help="Profil(s) à exécuter (répétable). Ex. --profil agrainage --profil chasse.",
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help="Fusionner les profils sélectionnés en un seul rapport (bilan combiné).",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="Afficher la liste des profils disponibles et quitter.",
    )
    parser.add_argument("--date-deb", type=str, default=None, help="Date début (YYYY-MM-DD).")
    parser.add_argument("--date-fin", type=str, default=None, help="Date fin (YYYY-MM-DD).")
    parser.add_argument("--dept-code", type=str, default=None, help="Code département (ex. 21).")

    # Options génériques (surcharges)
    parser.add_argument("--with-pnf", action="store_true", default=False, help="Activer analyse PNF.")
    parser.add_argument("--no-pnf", action="store_true", default=False, help="Désactiver analyse PNF.")
    parser.add_argument("--with-tub", action="store_true", default=False, help="Activer analyse TUB.")
    parser.add_argument("--no-tub", action="store_true", default=False, help="Désactiver analyse TUB.")
    parser.add_argument("--with-cartes", action="store_true", default=False, help="Activer cartes.")
    parser.add_argument("--no-cartes", action="store_true", default=False, help="Désactiver cartes.")
    parser.add_argument("--with-synthese", action="store_true", default=False, help="Activer synthèse croisée.")
    parser.add_argument("--no-synthese", action="store_true", default=False, help="Désactiver synthèse croisée.")
    parser.add_argument(
        "--option", action="append", metavar="KEY=VALUE",
        help="Option générique (répétable). Ex. --option pnf=true --option tub=false.",
    )
    parser.add_argument(
        "--preset",
        choices=("compact", "standard", "large"),
        default=None,
        help="Preset de taille des graphiques PDF.",
    )

    args = parser.parse_args()

    profils = args.profils or []
    if args.list_profiles:
        available = _list_profiles()
        for i, p in enumerate(available, 1):
            print(f"{i}. {p}")
        return 0
    if not profils:
        available = _list_profiles()
        if available:
            print("Profils disponibles :")
            for i, p in enumerate(available, 1):
                print(f"{i}. {p}")
        else:
            print("Profils disponibles : aucun (créer ref/profils_bilan/*.yaml)")
        print("Usage : --profil <id> [--profil <id> ...] [--combine] [--date-deb YYYY-MM-DD] [--date-fin YYYY-MM-DD] [--dept-code 21]")
        return 0

    date_deb = args.date_deb
    date_fin = args.date_fin
    dept_code = args.dept_code or "21"
    if not date_deb or not date_fin:
        try:
            date_deb_str, date_fin_str, dept_str = ask_periode_dept(
                date_deb_default=date_deb,
                date_fin_default=date_fin,
                dept_default=dept_code,
            )
            date_deb, date_fin, dept_code = date_deb_str, date_fin_str, dept_str
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1

    profils_resolus = _resolve_profils(profils)
    cli_options = _parse_cli_options(args)

    return run_thematic(
        profils_resolus, date_deb, date_fin, dept_code,
        combine=args.combine, cli_options=cli_options,
    )


if __name__ == "__main__":
    sys.exit(main())
