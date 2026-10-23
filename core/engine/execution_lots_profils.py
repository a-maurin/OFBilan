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

"""
========================================================================================
MODULE : EXECUTION PAR LOTS DE PROFILS DE BILAN (`execution_lots_profils.py`)
========================================================================================
Ce module orchestre le traitement par lots ("batch") de plusieurs profils de bilan
(ex. enchaînement automatique des bilans Agrainage, Chasse, PNF, etc.).

Fonctionnalités :
  1. Résolution dynamique des dossiers de sortie (`data/out/bilan_<profil>_<code_dept>`).
  2. Gestion du mode combiné (`--combine`) pour générer une séquence consolidée.
  3. Vérification des capacités de mixage (`mix_batch`) pour empêcher des mélanges incompatibles.
  4. Récupération et ouverture automatique dans l'explorateur des fichiers PDF produits.
========================================================================================
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from time import time

from core.chemins_projet import PROJECT_ROOT, get_out_dir
from core.common.reveal_in_file_manager import reveal_path_in_file_manager
from core.common.utilitaires_metier import resolve_code_subdir_suffix

logger = logging.getLogger("ofbilan.engine")


def resolve_profile_output_dir(
    profil_id: str,
    code: str = "",
    *,
    root: Path | None = None,
    cli_options: dict | None = None,
) -> Path:
    """
    Dossier de sortie où le moteur écrit pour ce profil (aligné global / thématique).
    """
    from core.chemins_projet import get_export_base_dir
    from core.engine.orchestrateur_profils import load_profile_config, _safe_type_usager_for_filename

    base = root or PROJECT_ROOT
    profile = load_profile_config(base, profil_id)
    cli_opts = cli_options or {}
    
    if profil_id == "global":
        filter_label = None
        if cli_opts.get("themes"):
            filter_label = ", ".join(cli_opts["themes"]) if isinstance(cli_opts["themes"], list) else str(cli_opts["themes"])
        elif cli_opts.get("domaines"):
            filter_label = ", ".join(cli_opts["domaines"]) if isinstance(cli_opts["domaines"], list) else str(cli_opts["domaines"])
        elif cli_opts.get("types_action"):
            filter_label = ", ".join(cli_opts["types_action"]) if isinstance(cli_opts["types_action"], list) else str(cli_opts["types_action"])

        if filter_label:
            safe_filter = _safe_type_usager_for_filename(filter_label) or "filtre"
            out_subdir = f"bilan_{safe_filter}"
            code_suffix = resolve_code_subdir_suffix(profile, code)
            if code_suffix:
                out_subdir = f"{out_subdir}_{code_suffix}"
            return get_out_dir(out_subdir)

        code_suffix = resolve_code_subdir_suffix(profile, code)
        candidates = []
        for candidate_root in [get_export_base_dir(), base / "data" / "out"]:
            if candidate_root.exists():
                for d in candidate_root.iterdir():
                    if d.is_dir() and d.name.startswith("bilan_global_") and d.name.endswith(f"_{code_suffix}"):
                        candidates.append(d)
        if candidates:
            return max(candidates, key=lambda d: d.stat().st_mtime)

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
            
    code_suffix = resolve_code_subdir_suffix(profile, code)
    if code_suffix:
        out_subdir = f"{out_subdir}_{code_suffix}"
        
    return get_out_dir(out_subdir)


def _list_generated_pdf_files(profil_id: str, started_at_epoch: float, code: str = "", cli_options: dict | None = None) -> list[Path]:
    """Retourne les PDF générés/écrasés pendant le run du profil."""
    cli_opts = cli_options or {}
    out_dir = resolve_profile_output_dir(profil_id, code=code, cli_options=cli_opts)

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
    from core.engine.orchestrateur_profils import load_profile_config

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
    from core.engine.orchestrateur_profils import run_engine

    return run_engine(profil_id, date_deb, date_fin, echelle, code, options=options)


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
        print(f"\nDémarrage du bilan combiné : {', '.join(profils)}")
        out_combine = get_out_dir(f"bilan_combine_{'_'.join(profils)}")
        out_combine.mkdir(parents=True, exist_ok=True)
        generated_pdfs_last_profile: list[Path] = []
        for pid in profils:
            print(f"\nExécution du profil : {pid}...")
            started_at = time()
            ret = run_profile(pid, date_deb, date_fin, echelle, code, options=cli_options)
            if ret != 0:
                return ret
            generated_pdfs_last_profile = _list_generated_pdf_files(pid, started_at, code=code, cli_options=cli_options)
        (out_combine / "README.txt").write_text(
            f"Bilan combiné : {', '.join(profils)}\n"
            f"Période : {date_deb} au {date_fin}, périmètre : {echelle} {code}.\n"
            "Les rapports individuels sont dans data/out/bilan_<profil>/.\n",
            encoding="utf-8",
        )
        print(f"\nRésumé combiné disponible dans : {out_combine}")
        if not (cli_options and cli_options.get("no_open")):
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
        print(f"\nDémarrage du bilan : {pid}...")
        started_at = time()
        ret = run_profile(pid, date_deb, date_fin, echelle, code, options=cli_options)
        if ret != 0:
            return ret
        generated_pdfs_last_profile = _list_generated_pdf_files(pid, started_at, code=code, cli_options=cli_options)
    if not (cli_options and cli_options.get("no_open")):
        _open_generated_pdfs(generated_pdfs_last_profile)
    return 0