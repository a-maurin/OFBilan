"""
Point d'entree unique pour la generation des bilans (global ou thematiques).
"""

from __future__ import annotations

import argparse
import logging
import sys

from bilans.logging_config import configure_logging
from bilans.common.prompt_periode import ask_periode_dept

_DEPS_CHECKED = False


def _check_deps() -> None:
    """Verifie la disponibilite des dependances lourdes."""
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
        print(f"Erreur : Une dependance requise est manquante : {e}", file=sys.stderr)
        print("Veuillez installer les dependances avec : pip install -e .", file=sys.stderr)
        print("(Alternative legacy : pip install -r tools/requirements.txt)", file=sys.stderr)
        sys.exit(1)
    _DEPS_CHECKED = True


def _list_themes() -> list[str]:
    """Liste les identifiants de themes disponibles."""
    from bilans.bilan_thematique.run_bilan_thematique import _list_profiles

    return _list_profiles()


def main() -> int:
    configure_logging()
    logger = logging.getLogger("bilans")

    parser = argparse.ArgumentParser(
        description="Generation des bilans : global ou un/plusieurs bilans thematiques."
    )
    parser.add_argument(
        "--mode",
        choices=("global", "thematique"),
        default=None,
        help="Mode : global (bilan d'activite complet) ou thematique (un ou plusieurs themes).",
    )
    parser.add_argument(
        "--list-themes",
        action="store_true",
        help="Afficher la liste des themes disponibles (un par ligne) et quitter.",
    )
    parser.add_argument(
        "--profil",
        action="append",
        dest="profils",
        metavar="ID",
        help="Theme(s) a executer en mode thematique (repetable).",
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help="En mode thematique : fusionner les themes selectionnes en un seul rapport.",
    )
    parser.add_argument("--date-deb", type=str, default=None, help="Date debut (YYYY-MM-DD).")
    parser.add_argument("--date-fin", type=str, default=None, help="Date fin (YYYY-MM-DD).")
    parser.add_argument("--dept-code", type=str, default=None, help="Code departement (ex. 21).")
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

    if args.mode is None:
        msg = "Indiquez --mode global ou --mode thematique (ou --list-themes pour afficher les themes)."
        logger.error(msg)
        print(msg, file=sys.stderr)
        print("Usage :", file=sys.stderr)
        print(
            "  python -m bilans --mode global [--date-deb YYYY-MM-DD] [--date-fin YYYY-MM-DD] [--dept-code 21]",
            file=sys.stderr,
        )
        print(
            "  python -m bilans --mode thematique --profil <id> [--profil <id> ...] [--combine] [--date-deb ...] [--date-fin ...] [--dept-code 21]",
            file=sys.stderr,
        )
        return 1

    if args.mode == "thematique" and not (args.profils or []):
        themes = _list_themes()
        logger.error("En mode thematique, aucun profil fourni.")
        print("En mode thematique, indiquez au moins un --profil.", file=sys.stderr)
        if themes:
            for i, t in enumerate(themes, 1):
                print(f"{i}. {t}", file=sys.stderr)
        else:
            print("  Aucun theme disponible.", file=sys.stderr)
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
            logger.error("Erreur de saisie periode/departement : %s", e)
            print(e, file=sys.stderr)
            return 1

    _check_deps()

    if args.mode == "global":
        try:
            from bilans.common.carte_helper import ensure_maps

            ensure_maps("bilan_global", date_deb=date_deb, date_fin=date_fin, dept_code=dept_code)
        except Exception as e:  # pragma: no cover
            logger.warning("Impossible de generer les cartes pour le bilan global : %s", e)
            print(f"[WARN] Impossible de generer les cartes pour le bilan global : {e}", file=sys.stderr)

        from bilans.bilan_global.analyse_global import run_global

        return run_global(date_deb, date_fin, dept_code, chart_preset=args.preset)

    from bilans.bilan_thematique.run_bilan_thematique import _resolve_profils, run_thematic

    profils_resolus = _resolve_profils(args.profils or [])

    try:
        from bilans.common.carte_helper import ensure_maps_for_profiles

        ensure_maps_for_profiles(profils_resolus, date_deb=date_deb, date_fin=date_fin, dept_code=dept_code)
    except Exception as e:  # pragma: no cover
        profils_str = ", ".join(profils_resolus) or "(aucun)"
        logger.warning("Impossible de generer les cartes pour les profils [%s] : %s", profils_str, e)
        print(f"[WARN] Impossible de generer les cartes pour les profils [{profils_str}] : {e}", file=sys.stderr)

    cli_options = {}
    if args.preset:
        cli_options["chart_preset"] = args.preset

    return run_thematic(
        profils_resolus,
        date_deb,
        date_fin,
        dept_code,
        combine=args.combine,
        cli_options=cli_options or None,
    )


if __name__ == "__main__":
    sys.exit(main())

