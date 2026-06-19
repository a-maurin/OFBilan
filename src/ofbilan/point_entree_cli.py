"""
Point d'entrée unique pour la génération des bilans par profils YAML.
"""

from __future__ import annotations

import argparse
import logging
import sys

from ofbilan.configuration_journalisation import configure_logging
from ofbilan.chemins_projet import PROJECT_ROOT
from ofbilan.common.prompt_periode import ask_periode_perimetre

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
    from ofbilan.engine.catalogue_profils import list_profiles

    return list_profiles()


def _load_type_usager_labels() -> list[str]:
    from ofbilan.engine.orchestrateur_profils import _load_types_usagers_labels

    return _load_types_usagers_labels(PROJECT_ROOT)


def _resolve_type_usager_targets(raw_values: list[str]) -> list[str]:
    """
    Convertit des libellés ou numéros (1..n) en libellés types_usagers.csv.
    La valeur « * » sélectionne tous les types.
    """
    labels = _load_type_usager_labels()
    if not raw_values:
        return []

    resolved: list[str] = []
    for raw in raw_values:
        token = str(raw).strip()
        if not token:
            continue
        if token == "*":
            return list(labels)
        if token.isdigit() and labels:
            idx = int(token)
            if 1 <= idx <= len(labels):
                label = labels[idx - 1]
                if label not in resolved:
                    resolved.append(label)
                continue
            raise ValueError(
                f"Numéro de type d'usager invalide : {idx} (attendu entre 1 et {len(labels)})."
            )
        if token not in resolved:
            resolved.append(token)
    return resolved


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
    logger = logging.getLogger("ofbilan")

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
    parser.add_argument("--echelle", choices=["departement", "region", "bmi", "national"], default=None, help="Échelle spatiale (departement, region, bmi, national).")
    parser.add_argument("--code", type=str, default=None, help="Code géographique (ex. 21, 27).")
    parser.add_argument(
        "--dept-code",
        type=str,
        default=None,
        help="(Déprécié) Alias de --code avec --echelle departement.",
    )
    parser.add_argument(
        "--preset",
        choices=("compact", "standard", "large"),
        default=None,
        help="Preset de taille des graphiques PDF.",
    )
    parser.add_argument(
        "--type-usager",
        action="append",
        dest="type_usager",
        metavar="LIBELLE_OU_NUMERO",
        help=(
            "Type d'usager cible pour le profil types_usager_cible "
            "(libellé exact ou numéro, voir --list-type-usagers). Répétable. "
            "Ex. --type-usager 2 ou --type-usager \"Agriculteur et autres acteurs agricoles\"."
        ),
    )
    parser.add_argument(
        "--mot-cle",
        action="append",
        dest="mots_cles",
        metavar="MOT_CLE",
        help="Mot-clé pour filtrer les données via la recherche avancée (répétable).",
    )
    parser.add_argument(
        "--list-type-usagers",
        action="store_true",
        help="Afficher les types d'usagers du référentiel (types_usagers.csv) et quitter.",
    )
    parser.add_argument(
        "--carte",
        action="append",
        dest="cartes_profil",
        metavar="ID",
        help=(
            "Profil cartographique à intégrer (profil global à catalogue). "
            "Répétable ; utiliser « all » pour toutes les cartes du catalogue."
        ),
    )
    parser.add_argument(
        "--cartes",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Intégrer les cartes dans le PDF (--no-cartes pour désactiver, sans question interactive).",
    )
    parser.add_argument(
        "--pnf",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Activer l'analyse PNF (cœur / hors-cœur, zonage parc). "
            "--no-pnf pour désactiver sans question interactive."
        ),
    )
    parser.add_argument(
        "--diffusion",
        choices=("interne", "externe"),
        default=None,
        help=(
            "Périmètre de diffusion du PDF : interne (détail nominatif des procédures) "
            "ou externe (sans listes PEJ/PA/PVe avec numéro de dossier ni localisation). "
            "Par défaut : valeur du profil YAML (sinon interne). "
            "Les cartes sont conservées dans les deux cas."
        ),
    )
    parser.add_argument(
        "--brochure",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Option conservée pour compatibilité. Le profil synthese_activite_PA_PJ génère "
            "désormais systématiquement le PDF détaillé et la brochure "
            "(*_brochure_ext.pdf ou *_brochure_int.pdf) à chaque exécution. "
            "--no-brochure permet de désactiver la question interactive."
        ),
    )
    args = parser.parse_args()

    if args.list_type_usagers:
        labels = _load_type_usager_labels()
        if not labels:
            print(
                "Aucun type d'usager trouvé (ref/programme/tables_reference/types_usagers.csv).",
                file=sys.stderr,
            )
            return 1
        for i, lab in enumerate(labels, 1):
            print(f"{i}. {lab}")
        return 0

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
    if args.dept_code and not args.code:
        echelle = args.echelle or "departement"
        code = args.dept_code
        if args.echelle and args.echelle != "departement":
            logger.warning(
                "--dept-code ignoré : utiliser --echelle departement --code %s", args.dept_code
            )
    else:
        echelle = args.echelle or "departement"
        code = args.code or "21"
    if not date_deb or not date_fin or not args.echelle or (not args.code and not args.dept_code):
        try:
            date_deb_str, date_fin_str, echelle_str, code_str = ask_periode_perimetre(
                date_deb_default=date_deb,
                date_fin_default=date_fin,
                echelle_default=echelle,
                code_default=code,
            )
            date_deb, date_fin, echelle, code = date_deb_str, date_fin_str, echelle_str, code_str
        except ValueError as e:
            logger.error("Erreur de saisie période/périmètre : %s", e)
            print(e, file=sys.stderr)
            return 1

    _check_deps()

    if date_fin and len(date_fin.strip()) == 10:
        date_fin = f"{date_fin.strip()} 23:59:59"

    from ofbilan.engine.catalogue_profils import resolve_profile_ids
    from ofbilan.engine.execution_lots_profils import run_profiles_batch

    profils_resolus = resolve_profile_ids(profils_raw)
    from ofbilan.common.prompt_periode import ask_choice_list, _is_interactive

    cli_options: dict = {}
    
    preset = args.preset
    if not preset and _is_interactive():
        preset = ask_choice_list(
            "Preset de la taille des graphiques",
            [("compact", "Compact"), ("standard", "Standard"), ("large", "Large")],
            "standard"
        )
    if preset:
        cli_options["chart_preset"] = preset

    if args.type_usager:
        try:
            cli_options["type_usager_target"] = _resolve_type_usager_targets(args.type_usager)
        except ValueError as e:
            logger.error("%s", e)
            print(e, file=sys.stderr)
            return 1

    cartes = args.cartes
    if cartes is None and _is_interactive():
        cartes_rep = ask_choice_list("Génération des cartes", [(True, "Oui"), (False, "Non")], True)
        cartes = bool(cartes_rep)
    if cartes is not None:
        cli_options["cartes"] = cartes

    if args.cartes_profil:
        cli_options["cartes_profil"] = args.cartes_profil

    pnf = args.pnf
    if pnf is None and _is_interactive():
        pnf_rep = ask_choice_list("Analyse PNF (cœur / hors-cœur)", [(True, "Oui"), (False, "Non")], False)
        pnf = bool(pnf_rep)
    if pnf is not None:
        cli_options["pnf"] = pnf

    diffusion = args.diffusion
    if not diffusion and _is_interactive():
        diffusion = ask_choice_list(
            "Périmètre de diffusion",
            [("interne", "Interne"), ("externe", "Externe")],
            "interne"
        )
    if diffusion:
        cli_options["diffusion"] = diffusion

    brochure = args.brochure
    if brochure is None and _is_interactive():
        brochure_rep = ask_choice_list("Activation du mode brochure", [(True, "Oui"), (False, "Non")], False)
        brochure = bool(brochure_rep)
    if brochure:
        cli_options["brochure"] = True

    if args.mots_cles:
        cli_options["mots_cles"] = args.mots_cles

    return run_profiles_batch(
        profils_resolus,
        date_deb,
        date_fin,
        echelle,
        code,
        combine=args.combine,
        cli_options=cli_options or None,
    )


if __name__ == "__main__":
    sys.exit(main())
