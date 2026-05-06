"""
Point d'entrée unique pour la génération des bilans par profils YAML.
"""

from __future__ import annotations

import argparse
import logging
import sys

from bilans.configuration_journalisation import configure_logging
from bilans.common.prompt_periode import ask_periode_dept

_DEPS_CHECKED = False


def _check_deps() -> None:
    """Vérifie la disponibilité des dépendances lourdes."""
    global _DEPS_CHECKED
    if _DEPS_CHECKED:
        return
    try:
        import pandas  # noqa: F401
        import geopandas  # noqa: F401
        from reportlab.lib import colors  # noqa: F401
        from reportlab.lib.pagesizes import A4  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as e:
        print(f"Erreur : Une dépendance requise est manquante : {e}", file=sys.stderr)
        print("Veuillez installer les dépendances avec : pip install -e .", file=sys.stderr)
        print("(Alternative legacy : pip install -r tools/requirements.txt)", file=sys.stderr)
        sys.exit(1)
    _DEPS_CHECKED = True


def _list_themes() -> list[str]:
    """Liste les identifiants de profils disponibles."""
    from bilans.engine.catalogue_profils import list_profiles

    return list_profiles()


def _ask_profils_interactive() -> list[str]:
    """Demande les profils à exécuter en mode interactif."""
    profils = _list_themes()
    if not profils:
        print("Aucun profil disponible.", file=sys.stderr)
        return []
    print("Profils disponibles :")
    for i, p in enumerate(profils, 1):
        print(f"{i}. {p}")
    raw = input("Profil(s) à lancer (numéro(s) ou id, séparés par des espaces) [1] > ").strip()
    if not raw:
        raw = "1"
    return [tok for tok in raw.split() if tok.strip()]


def main() -> int:
    configure_logging()
    logger = logging.getLogger("bilans")

    parser = argparse.ArgumentParser(
        description="Génération des bilans : un ou plusieurs profils YAML (--profil <id>)."
    )
    parser.add_argument(
        "--list-themes",
        action="store_true",
        help="Afficher la liste des profils disponibles (un par ligne, numérotés) et quitter.",
    )
    parser.add_argument(
        "--profil",
        action="append",
        dest="profils",
        metavar="ID",
        help="Profil à exécuter (répétable). Ex. --profil global ou --profil chasse --profil agrainage.",
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help="Enchaîner plusieurs profils avec récapitulatif combiné (si autorisé par les capacités de profil).",
    )
    parser.add_argument("--date-deb", type=str, default=None, help="Date début (YYYY-MM-DD).")
    parser.add_argument("--date-fin", type=str, default=None, help="Date fin (YYYY-MM-DD).")
    parser.add_argument("--dept-code", type=str, default=None, help="Code département (ex. 21).")
    parser.add_argument(
        "--preset",
        choices=("compact", "standard", "large"),
        default=None,
        help="Preset de taille des graphiques PDF.",
    )
    args = parser.parse_args()

    if args.list_themes:
        themes = _list_themes()
        for i, t in enumerate(themes, 1):
            print(f"{i}. {t}")
        return 0

    profils_raw = args.profils or []
    if not profils_raw:
        profils_raw = _ask_profils_interactive()
        if not profils_raw:
            return 1

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
            logger.error("Erreur de saisie période/département : %s", e)
            print(e, file=sys.stderr)
            return 1

    _check_deps()

    from bilans.engine.catalogue_profils import resolve_profile_ids
    from bilans.engine.execution_lots_profils import run_profiles_batch

    profils_resolus = resolve_profile_ids(profils_raw)
    cli_options: dict = {}
    if args.preset:
        cli_options["chart_preset"] = args.preset

    return run_profiles_batch(
        profils_resolus,
        date_deb,
        date_fin,
        dept_code,
        combine=args.combine,
        cli_options=cli_options or None,
    )


if __name__ == "__main__":
    sys.exit(main())
