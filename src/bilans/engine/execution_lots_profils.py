"""
Moteur unique : exécution orientée profils.

Pipeline logique : résolution du profil -> backend unique `run_engine`.
Les spécificités global/thématiques sont pilotées par le YAML de profil.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from time import time

from bilans.chemins_projet import PROJECT_ROOT, get_out_dir
from bilans.common.reveal_in_file_manager import reveal_path_in_file_manager

logger = logging.getLogger("bilans.engine")


def resolve_profile_output_dir(profil_id: str, code: str = "", *, root: Path | None = None) -> Path:
    """
    Dossier ``data/out/<out_subdir>/`` où le moteur écrit pour ce profil (aligné global / thématique).
    """
    from bilans.engine.orchestrateur_profils import load_profile_config

    base = root or PROJECT_ROOT
    profile = load_profile_config(base, profil_id)
    pipeline = str(profile.get("pipeline", "thematic")).strip().lower()
    if pipeline == "global":
        out_subdir = str(profile.get("out_subdir", f"bilan_{profile.get('id', 'global')}")).strip()
        if not out_subdir:
            out_subdir = "bilan_global"
    else:
        raw = profile.get("out_subdir")
        if isinstance(raw, str) and raw.strip():
            out_subdir = raw.strip()
        else:
            pid = str(profile.get("id", profil_id)).strip() or profil_id
            out_subdir = f"bilan_{pid}"
            
    code_norm = str(code).strip()
    if code_norm:
        out_subdir = f"{out_subdir}_{code_norm}"
        
    return get_out_dir(out_subdir)


def _list_generated_pdf_files(profil_id: str, started_at_epoch: float, code: str = "") -> list[Path]:
    """Retourne les PDF générés/écrasés pendant le run du profil."""
    out_dir = resolve_profile_output_dir(profil_id, code=code)
    if not out_dir.exists():
        return []
    pdfs: list[Path] = []
    for pdf_path in out_dir.glob("*.pdf"):
        try:
            if pdf_path.stat().st_mtime >= (started_at_epoch - 1.0):
                pdfs.append(pdf_path.resolve())
        except OSError:
            continue
    return sorted(pdfs, key=lambda p: p.name.lower())


def _open_generated_pdfs(pdf_paths: list[Path]) -> None:
    """Après un run CLI réussi : ouvre le(s) PDF généré(s) pour le dernier profil exécuté."""
    for pdf_path in pdf_paths:
        try:
            reveal_path_in_file_manager(pdf_path)
        except Exception as exc:
            logger.warning("Ouverture du PDF %s : %s", pdf_path, exc)


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
    echelle: str,
    code: str,
    options: dict | None = None,
) -> int:
    """
    Exécute un bilan pour un identifiant de profil.
    """
    options = options or {}
    from bilans.engine.orchestrateur_profils import run_engine

    return run_engine(profil_id, date_deb, date_fin, echelle, code, options=dict(options))


def run_profiles_batch(
    profils: list[str],
    date_deb: str,
    date_fin: str,
    echelle: str,
    code: str,
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
        generated_pdfs_last_profile: list[Path] = []
        for pid in profils:
            print(f"  Exécution profil {pid}...")
            started_at = time()
            ret = run_profile(pid, date_deb, date_fin, echelle, code, options=cli_options)
            if ret != 0:
                return ret
            generated_pdfs_last_profile = _list_generated_pdf_files(pid, started_at)
        (out_combine / "README.txt").write_text(
            f"Bilan combiné : {', '.join(profils)}\n"
            f"Période : {date_deb} au {date_fin}, périmètre : {echelle} {code}.\n"
            "Les rapports individuels sont dans data/out/bilan_<profil>/.\n",
            encoding="utf-8",
        )
        print(f"Résumé combiné dans {out_combine}")
        _open_generated_pdfs(generated_pdfs_last_profile)
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

    generated_pdfs_last_profile = []
    for pid in profils:
        print(f"Exécution bilan {pid}...")
        started_at = time()
        ret = run_profile(pid, date_deb, date_fin, echelle, code, options=cli_options)
        if ret != 0:
            return ret
        generated_pdfs_last_profile = _list_generated_pdf_files(pid, started_at, code=code)
    _open_generated_pdfs(generated_pdfs_last_profile)
    return 0
