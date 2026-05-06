"""
Moteur unique : exécution orientée profils.

Pipeline logique : résolution du profil -> backend unique `run_engine`.
Les spécificités global/thématiques sont pilotées par le YAML de profil.
"""
from __future__ import annotations

import logging
import sys

from bilans.chemins_projet import PROJECT_ROOT, get_out_dir

logger = logging.getLogger("bilans.engine")


def _load_profiles(profils: list[str]) -> dict[str, dict]:
    """Charge les profils YAML résolus (normalisés) pour la liste fournie."""
    from bilans.engine.orchestrateur_profils import load_profile_config

    out: dict[str, dict] = {}
    for pid in profils:
        p = str(pid).strip()
        if not p or p in out:
            continue
        out[p] = load_profile_config(PROJECT_ROOT, p)
    return out


def run_profile(
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
    from bilans.engine.orchestrateur_profils import run_engine

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
    Exécute un ou plusieurs profils (séquentiellement ou mode combiné).

    Les restrictions d'exécution sont pilotées par les capacités des profils.
    """
    cli_options = cli_options or {}
    profils = [str(p).strip() for p in profils if str(p).strip()]
    if not profils:
        return 1

    profiles_cfg = _load_profiles(profils)

    try:
        from bilans.common.carte_helper import ensure_maps_for_profiles

        map_profiles: list[str] = []
        for pid in profils:
            prof = profiles_cfg.get(pid, {})
            caps = prof.get("capabilities", {}) if isinstance(prof, dict) else {}
            if not isinstance(caps, dict):
                caps = {}
            raw = caps.get("map_profiles", [])
            if isinstance(raw, list):
                for item in raw:
                    s = str(item).strip()
                    if s and s not in map_profiles:
                        map_profiles.append(s)
            elif raw is not None:
                s = str(raw).strip()
                if s and s not in map_profiles:
                    map_profiles.append(s)

        if map_profiles:
            try:
                ensure_maps_for_profiles(
                    map_profiles, date_deb=date_deb, date_fin=date_fin, dept_code=dept_code
                )
            except Exception as e:
                logger.warning("Cartes profils : %s", e)
                print(
                    f"[WARN] Impossible de générer les cartes pour les profils [{', '.join(map_profiles)}] : {e}",
                    file=sys.stderr,
                )
    except Exception as e:
        logger.warning("carte_helper : %s", e)

    if combine:
        if len(profils) < 2:
            print("Erreur : --combine nécessite au moins deux profils.", file=sys.stderr)
            return 1
        non_combinables = []
        for pid in profils:
            caps = profiles_cfg.get(pid, {}).get("capabilities", {})
            can_combine = True
            if isinstance(caps, dict):
                can_combine = bool(caps.get("combine", True))
            if not can_combine:
                non_combinables.append(pid)
        if non_combinables:
            print(
                "Erreur : --combine non autorisé pour le(s) profil(s) : "
                + ", ".join(non_combinables),
                file=sys.stderr,
            )
            return 1
        print(f"Bilan combiné : {', '.join(profils)}")
        out_combine = get_out_dir(f"bilan_combine_{'_'.join(profils)}")
        out_combine.mkdir(parents=True, exist_ok=True)
        for pid in profils:
            print(f"  Exécution profil {pid}...")
            ret = run_profile(pid, date_deb, date_fin, dept_code, options=cli_options)
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

    non_mixable = []
    if len(profils) > 1:
        for pid in profils:
            caps = profiles_cfg.get(pid, {}).get("capabilities", {})
            can_mix = True
            if isinstance(caps, dict):
                can_mix = bool(caps.get("mix_batch", True))
            if not can_mix:
                non_mixable.append(pid)
    if non_mixable:
        print(
            "Erreur : exécution multi-profils non autorisée pour : " + ", ".join(non_mixable),
            file=sys.stderr,
        )
        return 1

    for pid in profils:
        print(f"Exécution bilan {pid}...")
        ret = run_profile(pid, date_deb, date_fin, dept_code, options=cli_options)
        if ret != 0:
            return ret
    return 0
