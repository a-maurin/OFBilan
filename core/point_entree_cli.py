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

#
"""
Point d'entrée unique pour la génération des bilans par profils YAML.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_PROJECT_ROOT_CLI = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT_CLI) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT_CLI))

from core.configuration_journalisation import configure_logging
from core.chemins_projet import PROJECT_ROOT
from core.common.prompt_periode import ask_periode_perimetre

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
    from core.engine.catalogue_profils import list_profiles

    return list_profiles()


def _load_type_usager_labels() -> list[str]:
    from core.engine.orchestrateur_profils import _load_types_usagers_labels

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
    logger = logging.getLogger("ofbilan")

    try:
        from core.common.utilitaires_metier import _load_bmi_config
        bmi_codes = sorted(_load_bmi_config().get("BMI_CONFIG", {}).keys())
    except Exception:
        bmi_codes = []

    try:
        user_types = _load_type_usager_labels()
    except Exception:
        user_types = []

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
    # Identity configuration options
    parser.add_argument(
        "--set-identite",
        action="store_true",
        help="Enregistrer le nom et le service de l'utilisateur dans config/identite.yaml",
    )
    parser.add_argument(
        "--nom",
        type=str,
        help="Nom de l'utilisateur (ex. 'Aguirre MAURIN')",
    )
    parser.add_argument(
        "--service",
        type=str,
        help="Service de l'utilisateur (ex. 'OFB — Service départemental de la Côte d'Or')",
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help="Enchaîner plusieurs profils avec récapitulatif combiné (si autorisé par les capacités de profil).",
    )
    parser.add_argument("--date-deb", type=str, default=None, help="Date début (YYYY-MM-DD).")
    parser.add_argument("--date-fin", type=str, default=None, help="Date fin (YYYY-MM-DD).")
    parser.add_argument("--echelle", type=str.lower, choices=["departement", "region", "bmi", "national"], default=None, help="Échelle spatiale (departement, region, bmi, national).")
    
    code_help = "Code géographique (ex. 21, 27)."
    if bmi_codes:
        code_help += f" Codes BMI possibles : {', '.join(bmi_codes)}."
    parser.add_argument("--code", type=str, default=None, help=code_help)
    
    parser.add_argument(
        "--dept-code",
        type=str,
        default=None,
        help="(Déprécié) Alias de --code avec --echelle departement.",
    )
    parser.add_argument(
        "--preset",
        type=str.lower,
        choices=("compact", "standard", "large"),
        default=None,
        help="Preset de taille des graphiques PDF.",
    )
    
    type_usager_help = (
        "Type d'usager cible pour le profil types_usager_cible "
        "(libellé exact ou numéro, voir --list-type-usagers). Répétable. "
        "Ex. --type-usager 2 ou --type-usager \"Agriculteur et autres acteurs agricoles\"."
    )
    if user_types:
        type_usager_help += " Valeurs possibles : " + ", ".join(f"{i}: {ut}" for i, ut in enumerate(user_types, 1)) + "."
    parser.add_argument(
        "--type-usager",
        action="append",
        dest="type_usager",
        metavar="LIBELLE_OU_NUMERO",
        help=type_usager_help,
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
        "--domaine",
        action="append",
        dest="domaines",
        metavar="DOMAINE",
        help="Domaine(s) de la SNC à filtrer (répétable).",
    )
    parser.add_argument(
        "--theme",
        action="append",
        dest="themes",
        metavar="THEME",
        help="Thème(s) de la SNC à filtrer (répétable).",
    )
    parser.add_argument(
        "--type-action",
        action="append",
        dest="types_action",
        metavar="TYPE_ACTION",
        help="Type(s) d'action à filtrer (répétable).",
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
        "--cartes-seules",
        action="store_true",
        help="Générer uniquement les cartes du profil cartographique et quitter avant la génération du PDF.",
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
        "--annexe-detaillee",
        action="store_true",
        default=False,
        help="Inclure l'annexe technique détaillée par domaine/thème dans les bilans régionaux.",
    )
    parser.add_argument(
        "--diffusion",
        choices=("interne", "externe"),
        default=None,
        help=(
            "Périmètre de diffusion du PDF : interne (détail nominatif des procédures) "
            "ou externe (sans listes PEJ/PA/PVe avec numéro de dossier ni localisation). "
            "Par défaut : valeur du profil YAML (sinon externe). "
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
            "(*_brochure_ext.pdf or *_brochure_int.pdf) à chaque exécution. "
            "--no-brochure permet de désactiver la question interactive."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Afficher tous les messages de débogage techniques sur la console.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Ne pas ouvrir automatiquement le fichier PDF généré.",
    )
    parser.add_argument(
        "--gabarit",
        type=str,
        default=None,
        help="Identifiant du gabarit de présentation PDF à appliquer (ex: srp_r27).",
    )
    parser.add_argument(
        "--list-gabarits",
        action="store_true",
        help="Lister les gabarits de présentation disponibles.",
    )
    parser.add_argument(
        "--commentaires-auto",
        action="store_true",
        default=None,
        help="Activer la génération des commentaires automatiques dans le PDF.",
    )
    parser.add_argument(
        "--no-commentaires-auto",
        action="store_true",
        default=None,
        help="Désactiver la génération des commentaires automatiques dans le PDF.",
    )
    parser.add_argument(
        "--excel",
        action="store_true",
        default=False,
        help="Générer un classeur Excel (.xlsx) multi-onglets contenant les données calculées.",
    )
    args = parser.parse_args()

    # Configuration du logging selon l'option --debug
    console_level = logging.DEBUG if args.debug else logging.INFO
    configure_logging(console_level)

    if args.list_gabarits:
        from core.common.chargeur_gabarits import list_gabarits
        gabarits = list_gabarits()
        if not gabarits:
            print("Aucun gabarit de présentation trouvé.", file=sys.stderr)
            return 0
        for g in gabarits:
            print(f"- {g['gabarit_id']} : {g['label']}")
        return 0

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

    from core.engine.catalogue_profils import resolve_profile_ids
    profils_resolus = resolve_profile_ids(profils_raw)

    is_fixed_geo = any(p in ("pnf", "pnf_v2") for p in profils_resolus)

    date_deb = args.date_deb
    date_fin = args.date_fin
    if args.dept_code and not args.code:
        echelle = args.echelle or "departement"
        code = args.dept_code
        if args.echelle and args.echelle != "departement":
            logger.warning(
                "--dept-code ignoré : utiliser --echelle departement --code %s", args.dept_code
            )
    elif is_fixed_geo:
        echelle = args.echelle or "national"
        code = args.code or "PNF"
    else:
        echelle = args.echelle or "departement"
        code = args.code or "21"

    if (not date_deb or not date_fin or (not args.echelle and not is_fixed_geo) or (not args.code and not args.dept_code and not is_fixed_geo)):
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

    if is_fixed_geo:
        raw_tokens = [c.strip() for c in code.replace(",", " ").split() if c.strip()]
        if not raw_tokens or raw_tokens == ["PNF"]:
            codes_list = ["21_52"]
        else:
            codes_list = ["_".join(raw_tokens)]
    else:
        codes_list = [c.strip() for c in code.replace(",", " ").split() if c.strip()]
        if not codes_list:
            codes_list = ["21"]


    if date_fin and len(date_fin.strip()) == 10:
        date_fin = f"{date_fin.strip()} 23:59:59"

    from core.engine.execution_lots_profils import run_profiles_batch
    from core.common.prompt_periode import ask_choice_list, _is_interactive

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

    if args.domaines:
        cli_options["domaines"] = args.domaines
    if args.themes:
        cli_options["themes"] = args.themes
    if args.types_action:
        cli_options["types_action"] = args.types_action

    cartes = args.cartes
    if args.cartes_seules:
        cartes = True
        cli_options["cartes_seules"] = True

    if cartes is None and _is_interactive():
        cartes_rep = ask_choice_list("Génération des cartes", [(True, "Oui"), (False, "Non")], True)
        cartes = bool(cartes_rep)
    if cartes is not None:
        cli_options["cartes"] = cartes

    if args.cartes_profil:
        cli_options["cartes_profil"] = args.cartes_profil

    pnf = args.pnf
    # Forcer pnf=True pour les profils à restrict_geo=pnf, sauf si --no-pnf explicite
    if pnf is None and is_fixed_geo:
        pnf = True
    if pnf is not None:
        cli_options["pnf"] = pnf
    if args.annexe_detaillee:
        cli_options["annexe_detaillee"] = True

    diffusion = args.diffusion
    if not diffusion and _is_interactive():
        diffusion = ask_choice_list(
            "Périmètre de diffusion",
            [("externe", "Externe"), ("interne", "Interne")],
            "externe"
        )
    if diffusion:
        cli_options["diffusion"] = diffusion

    brochure = args.brochure
    if brochure is None and _is_interactive():
        brochure_rep = ask_choice_list("Activation du mode brochure", [(True, "Oui"), (False, "Non")], False)
        brochure = bool(brochure_rep)
    if brochure is not None:
        cli_options["brochure"] = brochure

    if args.mots_cles:
        cli_options["mots_cles"] = args.mots_cles

    if args.no_open:
        cli_options["no_open"] = True

    if args.commentaires_auto:
        cli_options["commentaires_auto"] = True
    elif args.no_commentaires_auto:
        cli_options["commentaires_auto"] = False

    if args.gabarit:
        cli_options["gabarit"] = args.gabarit

    if args.excel:
        cli_options["excel"] = True

    from core.common.chargeurs_donnees import init_session_cache, clear_session_cache

    exit_code = 0
    init_session_cache(PROJECT_ROOT, echelle, codes_list, date_deb, date_fin)
    try:
        for current_code in codes_list:
            ret = run_profiles_batch(
                profils_resolus,
                date_deb,
                date_fin,
                echelle,
                current_code,
                combine=args.combine,
                cli_options=cli_options,
            )
            if ret != 0:
                if exit_code == 0:
                    exit_code = ret
    except Exception as e:
        logger.exception("Erreur critique survenue lors de l'exécution : %s", e)
        print(f"\nErreur : Une erreur critique est survenue lors de la génération : {e}", file=sys.stderr)
        
        has_file_handler = any(isinstance(h, logging.FileHandler) for h in logger.handlers)
        if has_file_handler:
            print("Veuillez consulter le fichier 'debug_run.log' dans le dossier de sortie pour plus de détails.", file=sys.stderr)
        else:
            print("Relancer la commande avec l'option --debug pour obtenir plus de détails.", file=sys.stderr)
        return 1
    finally:
        clear_session_cache()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())