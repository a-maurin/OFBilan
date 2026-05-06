"""
Moteur unique : exécution orientée profils.

Pipeline logique : résolution du profil -> backend unique `run_engine`.
Les spécificités global/thématiques sont pilotées par le YAML de profil.
"""
from __future__ import annotations

import logging
import sys

from bilans.paths import PROJECT_ROOT, get_out_dir

logger = logging.getLogger("bilans.engine")


def _engine_type_for_profile(profil_id: str) -> str:
    """Retourne 'global' ou 'thematic'."""
    pid = str(profil_id).strip()
    if not pid:
        return "thematic"
    try:
        from bilans.bilan_thematique.bilan_thematique_engine import load_profile_config

        profile = load_profile_config(PROJECT_ROOT, pid)
        et = str(profile.get("engine_type", "thematic")).strip().lower()
        return "global" if et == "global" else "thematic"
    except Exception:
        # Garde-fou : en cas d'échec de chargement profil, on conserve un défaut thématique.
        return "thematic"


def run_unified(
    profil_id: str,
    date_deb: str,
    date_fin: str,
    dept_code: str,
    options: dict | None = None,
) -> int:
    """
    Exécute un bilan pour un identifiant de profil.
    """
    options = options or {}
    from bilans.bilan_thematique.bilan_thematique_engine import run_engine

    return run_engine(profil_id, date_deb, date_fin, dept_code, options=dict(options))


def run_profiles_batch(
    profils: list[str],
    date_deb: str,
    date_fin: str,
    dept_code: str,
    *,
    combine: bool = False,
    cli_options: dict | None = None,
) -> int:
    """
    Exécute un ou plusieurs profils (séquentiellement ou mode combiné pour plusieurs thématiques).

    Le profil ``global`` ne peut pas être mélangé avec ``--combine`` : erreur explicite.
    """
    cli_options = cli_options or {}
    profils = [str(p).strip() for p in profils if str(p).strip()]
    if not profils:
        return 1

    has_global = any(_engine_type_for_profile(p) == "global" for p in profils)

    try:
        from bilans.common.carte_helper import ensure_maps, ensure_maps_for_profiles

        if has_global:
            try:
                ensure_maps("bilan_global", date_deb=date_deb, date_fin=date_fin, dept_code=dept_code)
            except Exception as e:
                logger.warning("Cartes bilan global : %s", e)
                print(f"[WARN] Impossible de générer les cartes pour le bilan global : {e}", file=sys.stderr)

        thematic_for_maps = [p for p in profils if _engine_type_for_profile(p) != "global"]
        thematic_for_maps = [p for p in thematic_for_maps if p != "types_usager_cible"]
        if thematic_for_maps:
            try:
                ensure_maps_for_profiles(
                    thematic_for_maps, date_deb=date_deb, date_fin=date_fin, dept_code=dept_code
                )
            except Exception as e:
                logger.warning("Cartes profils : %s", e)
                print(
                    f"[WARN] Impossible de générer les cartes pour les profils [{', '.join(thematic_for_maps)}] : {e}",
                    file=sys.stderr,
                )
    except Exception as e:
        logger.warning("carte_helper : %s", e)

    if combine:
        if len(profils) < 2:
            print("Erreur : --combine nécessite au moins deux profils.", file=sys.stderr)
            return 1
        if has_global:
            print(
                "Erreur : le profil « global » ne peut pas être utilisé avec --combine. "
                "Lancez le bilan global séparément : python -m bilans --profil global ...",
                file=sys.stderr,
            )
            return 1
        print(f"Bilan combiné : {', '.join(profils)}")
        out_combine = get_out_dir(f"bilan_combine_{'_'.join(profils)}")
        out_combine.mkdir(parents=True, exist_ok=True)
        for pid in profils:
            print(f"  Exécution profil {pid}...")
            ret = run_unified(pid, date_deb, date_fin, dept_code, options=cli_options)
            if ret != 0:
                return ret
        (out_combine / "README.txt").write_text(
            f"Bilan combiné : {', '.join(profils)}\n"
            f"Période : {date_deb} au {date_fin}, département {dept_code}.\n"
            "Les rapports individuels sont dans data/out/bilan_<profil>/.\n",
            encoding="utf-8",
        )
        print(f"Résumé combiné dans {out_combine}")
        return 0

    if has_global and len(profils) > 1:
        print(
            "Erreur : le profil « global » doit être exécuté seul "
            "(sans autre profil dans la même commande).",
            file=sys.stderr,
        )
        return 1

    for pid in profils:
        print(f"Exécution bilan {pid}...")
        ret = run_unified(pid, date_deb, date_fin, dept_code, options=cli_options)
        if ret != 0:
            return ret
    return 0


# Alias attendu par le package bilan_thematique
def run_thematic(
    profils: list[str],
    date_deb: str,
    date_fin: str,
    dept_code: str,
    combine: bool = False,
    cli_options: dict | None = None,
) -> int:
    """Compatibilité : délègue à run_profiles_batch."""
    return run_profiles_batch(
        profils, date_deb, date_fin, dept_code, combine=combine, cli_options=cli_options
    )
