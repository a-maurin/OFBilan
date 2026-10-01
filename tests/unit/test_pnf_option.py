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
"""Option PNF et distinction cœur / hors-cœur."""

from __future__ import annotations

from core.chemins_projet import PROJECT_ROOT
from core.engine.orchestrateur_profils import load_profile_config, resolve_options


def test_types_usager_cible_pnf_desactive_par_defaut() -> None:
    profile = load_profile_config(PROJECT_ROOT, "types_usager_cible")
    opts = resolve_options(profile, {})
    assert opts.get("pnf") is False
    assert profile.get("options", {}).get("pnf", {}).get("ask") is True


def test_chasse_pnf_desactive_par_defaut_sans_question() -> None:
    profile = load_profile_config(PROJECT_ROOT, "chasse")
    opts = resolve_options(profile, {})
    assert opts.get("pnf") is False
    assert profile.get("options", {}).get("pnf", {}).get("ask") is False