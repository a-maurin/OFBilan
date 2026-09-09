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
MODULE : GENERATEUR DE COMMENTAIRES AUTOMATIQUES (`commentaires_auto.py`)
========================================================================================
Ce module calcule et résout les textes de commentaires introductifs insérés avant les
tableaux et graphiques des bilans PDF.

Fonctionnalités :
  1. Chargement tolérant du fichier YAML (`config/presentation/commentaires_auto.yaml`).
  2. Calcul automatique des variables métiers (nombres au format FR, pluriels).
  3. Support des surcharges manuelles (`custom_text`).
  4. Génération de paragraphes ReportLab sécurisés avec `keepWithNext=True`.
========================================================================================
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import yaml

import pandas as pd
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

from core.chemins_projet import PROJECT_ROOT

logger = logging.getLogger(__name__)

_YAML_PATH = PROJECT_ROOT / "config" / "presentation" / "commentaires_auto.yaml"
_CONFIG_CACHE: dict[str, Any] | None = None


# ========================================================================================
# OUTILS DE FORMATAGE ET DE PLURIEL
# ========================================================================================

def format_number_fr(val: int | float) -> str:
    """Formate un nombre selon les conventions françaises (ex: 1 250)."""
    try:
        n = int(round(val))
        return f"{n:,}".replace(",", " ")
    except Exception:
        return str(val)


def format_pct_fr(rate: float) -> str:
    """Formate un taux (0.0 - 1.0) en pourcentage (ex: 31 %)."""
    try:
        pct = int(round(rate * 100)) if rate <= 1.0 else int(round(rate))
        return f"{pct} %"
    except Exception:
        return "0 %"


def pluralize(count: int | float, singular: str, plural: str | None = None) -> str:
    """Accorde un nom au singulier ou au pluriel selon la valeur."""
    n = int(round(count))
    if plural is None:
        plural = singular + "s"
    word = singular if n <= 1 else plural
    return f"{format_number_fr(n)} {word}"


# ========================================================================================
# CHARGEMENT DU FICHIER YAML
# ========================================================================================

def _load_yaml_config() -> dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    if not _YAML_PATH.is_file():
        logger.warning("Fichier de gabarits de commentaires introuvable : %s", _YAML_PATH)
        _CONFIG_CACHE = {}
        return _CONFIG_CACHE
    try:
        with open(_YAML_PATH, "r", encoding="utf-8") as f:
            _CONFIG_CACHE = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("Erreur lors de la lecture du YAML de commentaires : %s", e)
        _CONFIG_CACHE = {}
    return _CONFIG_CACHE


# ========================================================================================
# PREPARATION DES VARIABLES PAR SECTION
# ========================================================================================

def _get_nb_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _build_sec21_vars(ctx: Any) -> dict[str, Any] | None:
    df = getattr(ctx, "act_theme", None)
    if df is None or df.empty:
        return None
    col_nb = _get_nb_col(df, ["nb_total", "nb", "nb_localisations"])
    if not col_nb:
        return None
    total = int(df[col_nb].astype(float).sum())
    if total <= 0:
        return None
    top = df.iloc[0]
    top_n = int(top[col_nb])
    top_pct_v = (top_n / total) * 100
    second_theme = df.iloc[1]["theme"] if len(df) > 1 else "-"
    second_n = int(df.iloc[1][col_nb]) if len(df) > 1 else 0
    second_pct_v = (second_n / total) * 100 if len(df) > 1 else 0

    return {
        "top_theme": str(top["theme"]),
        "top_n": format_number_fr(top_n),
        "top_n_label": pluralize(top_n, "localisation"),
        "top_pct_val": top_pct_v,
        "top_pct": f"{int(round(top_pct_v))} %",
        "second_theme": str(second_theme),
        "second_pct": f"{int(round(second_pct_v))} %",
        "total_val": total,
        "total_label": pluralize(total, "localisation"),
    }


def _build_sec22_vars(ctx: Any) -> dict[str, Any] | None:
    df = getattr(ctx, "tab_resultats", None)
    if df is None or df.empty:
        return None
    col_nb = _get_nb_col(df, ["nb_localisations", "nb", "nb_total"])
    if not col_nb:
        return None
    total = getattr(ctx, "nb_localisations", 0)
    if total <= 0:
        total = int(df[col_nb].astype(float).sum())
    if total <= 0:
        return None
    
    nc_row = df[df["resultat"].astype(str).str.contains("Non-conforme|non_conforme|Infraction|Manquement", case=False, na=False)]
    nc_n = int(nc_row[col_nb].sum()) if not nc_row.empty else 0
    if nc_n <= 0:
        return None
    
    nc_pct_v = (nc_n / total) * 100
    inf_row = df[df["resultat"].astype(str).str.contains("Infraction", case=False, na=False)]
    man_row = df[df["resultat"].astype(str).str.contains("Manquement", case=False, na=False)]
    inf_n = int(inf_row[col_nb].sum()) if not inf_row.empty else 0
    man_n = int(man_row[col_nb].sum()) if not man_row.empty else 0

    return {
        "total_val": total,
        "total_label": pluralize(total, "localisation"),
        "nc_n_val": nc_n,
        "nc_n_label": pluralize(nc_n, "localisation"),
        "nc_pct_val": nc_pct_v,
        "nc_pct": f"{int(round(nc_pct_v))} %",
        "inf_n_label": pluralize(inf_n, "infraction"),
        "man_n_label": pluralize(man_n, "manquement"),
    }


def _build_sec4_vars(ctx: Any) -> dict[str, Any] | None:
    df = getattr(ctx, "agg_usager", None)
    if df is None or df.empty:
        return None
    col_nb = _get_nb_col(df, ["nb_total", "nb", "nb_localisations"])
    if not col_nb:
        return None
    total = int(df[col_nb].astype(float).sum())
    if total <= 0:
        return None
    top = df.iloc[0]
    top_n = int(top[col_nb])
    top_pct_v = (top_n / total) * 100
    second_usager = df.iloc[1]["type_usager"] if len(df) > 1 else "-"
    second_n = int(df.iloc[1][col_nb]) if len(df) > 1 else 0
    second_pct_v = (second_n / total) * 100 if len(df) > 1 else 0

    return {
        "top_usager": str(top["type_usager"]),
        "top_n_label": pluralize(top_n, "effectif"),
        "top_pct_val": top_pct_v,
        "top_pct": f"{int(round(top_pct_v))} %",
        "second_usager": str(second_usager),
        "second_pct": f"{int(round(second_pct_v))} %",
        "total_val": total,
        "total_label": pluralize(total, "effectif"),
    }


# ========================================================================================
# EVALUATION DE LA REGLE ET RENDU DU PARAGRAPHE
# ========================================================================================

def get_comment_text(section_id: str, ctx: Any) -> str | None:
    """Résout et retourne la chaîne de texte pour une section, ou None."""
    try:
        # 1. Vérifier si un custom_text est présent dans la config de présentation
        blocks_cfg = getattr(ctx, "presentation_cfg", {}).get("blocks", {})
        sec_cfg = blocks_cfg.get(section_id, {})
        if isinstance(sec_cfg, dict) and sec_cfg.get("custom_text"):
            return str(sec_cfg["custom_text"]).strip()

        # 2. Charger le YAML
        cfg = _load_yaml_config()
        sec_rule_cfg = cfg.get(section_id)
        if not sec_rule_cfg or not sec_rule_cfg.get("enabled", True):
            return None

        # 3. Calculer les variables selon la section
        vars_builder_map = {
            "sec21_themes": _build_sec21_vars,
            "sec22_conformite": _build_sec22_vars,
            "sec4_usagers": _build_sec4_vars,
        }
        builder_fn = vars_builder_map.get(section_id)
        if not builder_fn:
            return None

        variables = builder_fn(ctx)
        if not variables:
            return None

        # 4. Évaluer la première règle vraie
        rules = sec_rule_cfg.get("rules", [])
        for rule in rules:
            cond = rule.get("condition", "True")
            try:
                if eval(cond, {"__builtins__": {}}, variables):
                    template = rule.get("template", "")
                    return template.format(**variables).strip()
            except Exception as cond_err:
                logger.warning("Erreur lors de l'évaluation de la condition '%s' (%s) : %s", cond, section_id, cond_err)
                continue

    except Exception as e:
        logger.warning("Erreur imprévue lors de la génération du commentaire pour %s : %s", section_id, e)

    return None


def build_comment_paragraph(
    section_id: str,
    ctx: Any,
    style: ParagraphStyle | None = None,
    spacer_after_mm: float = 1.5,
) -> Paragraph | None:
    """Génère un Paragraph ReportLab avec keepWithNext=True si un commentaire existe."""
    text = get_comment_text(section_id, ctx)
    if not text:
        return None
    
    p_style = style or ParagraphStyle(
        name=f"Comment_{section_id}",
        fontName="Helvetica",
        fontSize=9,
        leading=11.5,
        textColor="#222222",
        spaceAfter=spacer_after_mm * 2.83465,  # mm -> pt
        keepWithNext=True,
    )
    return Paragraph(text, p_style)
