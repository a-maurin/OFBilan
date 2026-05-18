"""Option PNF et distinction cœur / hors-cœur."""

from __future__ import annotations

from bilans.chemins_projet import PROJECT_ROOT
from bilans.engine.orchestrateur_profils import load_profile_config, resolve_options


def test_types_usager_cible_pnf_desactive_par_defaut() -> None:
    profile = load_profile_config(PROJECT_ROOT, "types_usager_cible")
    opts = resolve_options(profile, {})
    assert opts.get("pnf") is False
    assert profile.get("options", {}).get("pnf", {}).get("ask") is True


def test_chasse_pnf_active_par_defaut_sans_question() -> None:
    profile = load_profile_config(PROJECT_ROOT, "chasse")
    opts = resolve_options(profile, {})
    assert opts.get("pnf") is True
    assert profile.get("options", {}).get("pnf", {}).get("ask") is False
