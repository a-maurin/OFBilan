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

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from core.common.chargeurs_donnees import get_source_files_metadata

logger = logging.getLogger(__name__)


def validate_post_generation_assertions(ctx: Any) -> list[str]:
    """Effectue des assertions de cohérence post-génération sur le PdfContext."""
    errors: list[str] = []

    if getattr(ctx, "nb_localisations", 0) < 0:
        errors.append("Le nombre de localisations de contrôle est négatif.")
    if getattr(ctx, "nb_pej", 0) < 0:
        errors.append("Le nombre de PEJ est négatif.")
    if getattr(ctx, "nb_pa", 0) < 0:
        errors.append("Le nombre de PA est négatif.")
    if getattr(ctx, "nb_pve", 0) < 0:
        errors.append("Le nombre de PVe est négatif.")

    # Vérification de cohérence des sous-totaux si le DataFrame est présent
    tab_res = getattr(ctx, "tab_resultats", None)
    if tab_res is not None and not tab_res.empty and "nb" in tab_res.columns:
        total_res = int(tab_res["nb"].sum())
        nb_loc = getattr(ctx, "nb_localisations", 0)
        if total_res > nb_loc and nb_loc > 0:
            errors.append(f"Incohérence : total des résultats ({total_res}) > localisations ({nb_loc}).")

    if errors:
        for err in errors:
            logger.warning("Assertion de cohérence échouée : %s", err)
    else:
        logger.info("Validation post-génération réussie : 0 incohérence détectée.")

    return errors


def export_notice_sources(out_dir: Path, ctx: Any, root: Path) -> Path:
    """Génère le fichier de traçabilité d'audit NOTICE_SOURCES.txt dans out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    notice_path = out_dir / "NOTICE_SOURCES.txt"

    sources_meta = get_source_files_metadata(root)
    errors = validate_post_generation_assertions(ctx)

    date_deb_str = ctx.date_deb.strftime("%d/%m/%Y") if hasattr(ctx.date_deb, "strftime") else str(ctx.date_deb)
    date_fin_str = ctx.date_fin.strftime("%d/%m/%Y") if hasattr(ctx.date_fin, "strftime") else str(ctx.date_fin)

    lines = [
        "================================================================================",
        "NOTICE DE TRAÇABILITÉ DES SOURCES ET CONFORMITÉ AUDIT — OFBILAN",
        "================================================================================",
        f"Date de génération : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Profil utilisé      : {getattr(ctx, 'profile_id', 'global')}",
        f"Périmètre géog.    : Département/Zone {getattr(ctx, 'dept_code', 'inconnu')} ({getattr(ctx, 'dept_name_typo', '')})",
        f"Période d'analyse  : du {date_deb_str} au {date_fin_str}",
        f"Mode de diffusion  : {getattr(ctx, 'diffusion', 'interne').upper()}",
        "--------------------------------------------------------------------------------",
        "1. CHIFFRES CLÉS DU RAPPORT",
        "--------------------------------------------------------------------------------",
        f"Localisations de contrôle : {getattr(ctx, 'nb_localisations', 0)}",
        f"Procédures d'enquête (PEJ): {getattr(ctx, 'nb_pej', 0)}",
        f"Procédures admin. (PA)    : {getattr(ctx, 'nb_pa', 0)}",
        f"Procès-verbaux PVe        : {getattr(ctx, 'nb_pve', 0)}",
        "--------------------------------------------------------------------------------",
        "2. FICHIERS SOURCES DE DONNÉES UTILISÉS (data/sources/)",
        "--------------------------------------------------------------------------------",
    ]

    if sources_meta:
        for s in sources_meta:
            lines.append(f"- {s['nom']} | Taille: {s['taille']} | Modifié: {s['date']} | SHA-256: {s['empreinte']}")
    else:
        lines.append("- Aucun fichier source spécifique trouvé.")

    lines.extend([
        "--------------------------------------------------------------------------------",
        "3. VALIDATION CROISÉE ET COHÉRENCE",
        "--------------------------------------------------------------------------------",
    ])

    if errors:
        lines.append("Avertissements de cohérence détectés :")
        for err in errors:
            lines.append(f"  [ATTENTION] {err}")
    else:
        lines.append("✓ Toutes les assertions de cohérence post-génération sont validées (0 erreur).")

    lines.append("================================================================================")

    notice_path.write_text("\n".join(lines), encoding="utf-8")
    return notice_path
