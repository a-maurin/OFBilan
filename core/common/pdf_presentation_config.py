# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# Ce programme est distribué dans l'espoir qu'il sera utile, me SANS AUCUNE GARANTIE ;
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
MODULE : CONFIGURATION ET RÈGLES DE PRÉSENTATION PDF (`pdf_presentation_config.py`)
========================================================================================
Ce module orchestre le chargement, la fusion et la résolution des options de présentation PDF.

Règles de fusion hiérarchique :
  1. Configuration de base (`DEFAULT_PDF_PRESENTATION_CONFIG`).
  2. Surcharge par le scope du document (`global`, `thematique`, `synthese_regionale`).
  3. Surcharge par le profil métier spécifique (`agrainage`, `chasse`, etc.).
  4. Surcharge par le gabarit de rapport YAML sélectionné.

Fonctions associées :
  - Normalisation des identifiants et titres de sections/sous-sections.
  - Masquage des blocs sans données ou hors périmètre de diffusion.
========================================================================================
"""
from __future__ import annotations

import warnings
import yaml
from core.chemins_projet import PROJECT_ROOT

# Chargement du fichier d'identité de l'auteur
_IDENTITE_PATH = PROJECT_ROOT / "config" / "identite.yaml"
if _IDENTITE_PATH.exists():
    _IDENTITE = yaml.safe_load(_IDENTITE_PATH.read_text(encoding="utf-8")) or {}
else:
    _IDENTITE = {}
_user_dict = _IDENTITE.get("utilisateur", {}) if isinstance(_IDENTITE.get("utilisateur"), dict) else _IDENTITE
_NOM = _user_dict.get("nom", _IDENTITE.get("nom", "Aguirre MAURIN"))
_SERVICE = _user_dict.get("service", _IDENTITE.get("service", "OFB"))
REALISATION = f"<b>Réalisation :</b> {_NOM} — {_SERVICE}"
from copy import deepcopy
from pathlib import Path
from typing import Any

# Identifiants de sections avec leurs alias historiques pour la rétrocompatibilité
SECTION_ID_ALIASES: dict[str, str] = {
    "sec_usagers": "sec4",
    "sec_procedures": "sec3",
}

# Sous-sections du chapitre "Activité par type d'usager"
SEC4_SUBSECTION_DEFAULTS: tuple[tuple[str, str], ...] = (
    ("sec41", "3.1. Thème de contrôle par type d'usager"),
    ("sec42", "3.2. Résultats des contrôles par type d'usager"),
    ("sec43", "3.3. Procédures d'enquête judiciaire (PEJ) par type d'usager"),
    ("sec44", "3.4. Procédures administratives (PA) par type d'usager"),
)


# Configuration de présentation par défaut pour l'ensemble du système
DEFAULT_PDF_PRESENTATION_CONFIG: dict[str, Any] = {
    "version": 1,
    "behavior": {
        "missing_data_policy": "hide_silently",
        "unknown_block_policy": "ignore",
    },
    "defaults": {
        "title": {
            "model": "three_lines",
            "line1": "Bilan des activités de police\nde l'environnement de l'OFB",
            "line2_mode": "profile_label",
            "line2_fixed": "",
            "line3_mode": "department",
            "line3_fixed": "",
            "typography": {
                "normalize_department_name": True,
                "apostrophe_style": "typographic",
            },
        },
        "title_page": {
            "alignment": "right",
            "right_indent_mm": 25,
            "paragraph_space_after": 8,
            "main_title_font_size": 24,
            "profile_department_font_size": 20,
            "meta_font_size": 12,
            "top_spacer_ratio": 0.30,
            "meta_block_space_before": 12,
            "meta_block_space_between": 8,
            "internal_diffusion_notice": {
                "logo_banner_top_ratio": 0.86,
                "gap_below_logo_banner_mm": 10,
                "font_size": 8,
                "pad_x_mm": 4,
                "pad_y_mm": 2,
                "text": "",
            },
        },
        "sections": {
            "order": ["sec1", "sec2", "sec4", "sec3", "sec5", "sec6"],
            "enabled": {},
            "titles": {
                "sec22dom": "2.2. Nombre de localisations de contrôles par domaines",
            },
        },
        "notice_methodology": {
            "title": "Notice méthodologique",
            "data_source_paragraph": (
                "Les données relatives aux contrôles et aux procédures présentées dans ce document "
                "sont extraites de la base du logiciel OSCEAN, outil de rapportage des activités "
                "de police administrative et judiciaire des agents de l'OFB."
            ),
            "unit_measure_paragraph": (
                "Sauf mention contraire, l'unité de mesure du nombre de contrôles utilisée dans "
                "la suite du document est la localisation de contrôle : une unité correspond à "
                "une localisation renseignée."
            ),
            "control_operation_paragraph": (
                "La notion de localisation de contrôle diffère de celle d'opération de contrôle. "
                "L'opération de contrôle qualifie l'événement ou l'intervention dans son ensemble, "
                "tel qu'il a été mené par les agents sur le terrain. Une seule opération de contrôle "
                "peut générer plusieurs localisations géographiques ou concerner plusieurs usagers."
            ),
            "pa_pj_distinction_paragraph": (
                "Par ailleurs, une distinction stricte s'impose entre la police administrative et la police judiciaire. "
                "Dans ce document, le terme « contrôle » renvoie exclusivement "
                "à la police administrative. Le sigle « PEJ » (procédure d'enquête judiciaire) "
                "désigne l'activité de police judiciaire, qui ne se limite pas aux infractions "
                "relevées lors des contrôles et peut aussi inclure des saisines extérieures "
                "(infractions constatées hors opération de contrôle au titre de la police "
                "administrative, instruction parquet, signalements, plaintes, etc.)."
            ),
            "multi_usager_paragraph": (
                "Lorsque des tableaux ou graphiques affichent des « effectifs » par type "
                "d'usager, chaque usager renseigné sur une fiche est compté (contrôles "
                "multi-usagers : plusieurs effectifs pour une même fiche de contrôle). Les "
                "effectifs d'usagers sont ainsi comptés au niveau des fiches de contrôle, "
                "tandis que les localisations correspondent aux points de contrôle ; selon les "
                "cas, les effectifs peuvent donc être inférieurs ou supérieurs au nombre de "
                "localisations. Les colonnes ou indicateurs PEJ, PA et PVe correspondent à des "
                "nombres de procédures (dossiers), et non à des localisations de contrôle ; "
                "ils sont signalés comme tels dans les légendes des tableaux concernés."
            ),
        },
        "sec6_methodology": {
            "items": [
                {
                    "when": "always",
                    "text": "<b>Période :</b> {period_str}.",
                },
                {
                    "when": "always",
                    "text": "<b>Périmètre :</b> {perimetre_name} ({perimetre_code}).",
                },
                {
                    "when": "has_profile",
                    "text": "<b>Objet du bilan :</b> {profile_label}.",
                },
                {
                    "when": "always",
                    "text": "<b>Données utilisées :</b> {sources_phrase}.",
                },
                {
                    "when": "has_controls",
                    "text": (
                        "Les chiffres de <b>contrôle</b> correspondent à des localisations "
                        "enregistrées sur la période (un lieu contrôlé compte pour une localisation)."
                    ),
                },
                {
                    "when": "has_pej",
                    "text": (
                        "Les <b>PEJ</b> (procédures d'enquête judiciaire) sont comptées en nombre "
                        "de dossiers sur la période."
                    ),
                },
                {
                    "when": "has_pa",
                    "text": (
                        "Les <b>procédures administratives (PA)</b> sont comptées en nombre de "
                        "dossiers sur la période."
                    ),
                },
                {
                    "when": "has_pve",
                    "text": (
                        "Les <b>procès-verbaux électroniques (PVe)</b> sont comptés en nombre de "
                        "dossiers sur la période."
                    ),
                },
                {
                    "when": "has_ventilation",
                    "text": "<b>Lecture dans le temps :</b> {ventilation_label}.",
                },
                {
                    "when": "show_usagers",
                    "text": (
                        "Les effectifs par type d'usager décomptent chaque usager renseigné ; "
                        "ils peuvent dépasser le nombre de localisations lorsque plusieurs usagers "
                        "sont associés au même contrôle."
                    ),
                },
                {
                    "when": "zone_pnf_only",
                    "text": (
                        "Les comparaisons spatiales distinguent le <b>cœur</b> du parc et "
                        "l'<b>aire d'adhésion</b> du parc national de forêts."
                    ),
                },
                {
                    "when": "zone_pnf_and_tub",
                    "text": (
                        "Des tableaux comparent le département, le périmètre PNF et les zones "
                        "de lutte contre la tuberculose bovine (TUB)."
                    ),
                },
                {
                    "when": "zone_pnf_dept",
                    "text": (
                        "Des tableaux comparent l'ensemble du département et le périmètre du "
                        "parc national de forêts (PNF)."
                    ),
                },
                {
                    "when": "zone_tub_only",
                    "text": (
                        "Des tableaux comparent l'ensemble du département et les zones TUB "
                        "(tuberculose bovine)."
                    ),
                },
                {
                    "when": "diffusion_externe",
                    "text": (
                        "Ce document est une <b>version de synthèse</b> : les listes nominatives "
                        "de procédures (numéros de dossier, localisations détaillées) ne sont pas "
                        "reproduites."
                    ),
                },
                {
                    "when": "always",
                    "text": REALISATION,
                },
                {
                    "when": "always",
                    "text": (
                        "Créé avec OFBilan – Auteur : Aguirre MAURIN (OFB, Service départemental de la Côte d’Or)"
                    ),
                    "section": "annex"
                },
            ],
        },
        "tables": {
            "split_by_row": False,
            "max_rows_keep_together": 8,
            "max_cell_chars_before_split": 100,
            "vertical_header": {
                "pad_x_pt": 0.0,
                "max_lines": 6,
                "font_size": 7.0,
                "row_padding_pt": 8.0,
            },
            "usagers_x_domaine": {
                "max_domain_columns": 14,
                "header_layout": "horizontal_wrap",
                "header_font_size": 7.0,
                "header_wrap_max_lines": 5,
                "first_column_width_ratio": 0.20,
                "max_usager_rows": 15,
                "overflow_note_separator": " ",
                "overflow_note_column_part": (
                    "Domaines : {shown} colonnes affichées sur {total} "
                    "(ordre décroissant du volume de contrôles par domaine)."
                ),
                "overflow_note_row_part": (
                    "Types d’usagers : {rows_shown} lignes affichées sur {rows_total} "
                    "(ordre décroissant du volume de contrôles sur les colonnes affichées)."
                ),
                "overflow_note_wrap": "<i>{note}</i>",
            },
        },
        "charte": {
            "assets": {
                "banner": "image5.jpg",
                "title_page_deco": "image6.jpeg",
                "watermark": "image3.jpeg",
                "footer_deco": "image4.jpeg",
            },
            "title_page": {
                "banner_height_mm": 42.0,
                "deco_height_ratio": 0.50,
                "deco_align": "bottom_right",
            },
            "content_page": {
                "watermark_enabled": True,
                "filigrane_height_ratio": 0.50,
                "filigrane_align": "bottom_right",
                "watermark_height_mm": None,
                "footer_deco_enabled": False,
                "footer_deco_width_mm": 96.7,
                "footer_deco_height_mm": 104.5,
                "footer_deco_margin_left_mm": 0.0,
                "footer_deco_margin_bottom_mm": 18.0,
            },
            "typography": {
                "subsections_italic": True,
            },
            "charts": {
                "pie_width_ratio_base": 0.34,
            },
        },
        "blocks": {},
    },
    "scopes": {
        "global": {
            "title": {"line2_mode": "none"},
        },
        "thematique": {
            "title": {"line2_mode": "profile_label"},
        },
    },
    "profiles": {},
    "feature_registry": {},
}


# ========================================================================================
# FONCTIONS DE FUSION RECURSIVE ET RESOLUTION CONFIGURATION
# ========================================================================================

def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Fusionne récursivement deux dictionnaires de configuration (les clés d'override sont prioritaires)."""
    out = deepcopy(base)
    for key, value in (override or {}).items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _normalize_config(data: dict[str, Any]) -> dict[str, Any]:
    """Garantit la présence des sous-arbres essentiels dans la configuration."""
    out = deepcopy(data)
    out.setdefault("version", 1)
    out.setdefault("behavior", {})
    out["behavior"].setdefault("missing_data_policy", "hide_silently")
    out["behavior"].setdefault("unknown_block_policy", "ignore")
    out["behavior"].setdefault("commentaires_auto", True)
    out.setdefault("defaults", {})
    out.setdefault("scopes", {})
    out.setdefault("profiles", {})
    out.setdefault("feature_registry", {})
    return out


def load_pdf_presentation_raw_config(root: Path) -> dict[str, Any]:
    """Lit le fichier YAML `pdf_presentation.yaml` sur le disque et retourne sa configuration."""
    cfg_candidates = [
        root / "config" / "presentation" / "pdf_presentation.yaml",
        root / "ref" / "programme" / "pdf_presentation.yaml",
    ]
    cfg_path = next((p for p in cfg_candidates if p.exists()), None)
    if cfg_path is None:
        return deepcopy(DEFAULT_PDF_PRESENTATION_CONFIG)

    try:
        import yaml  # type: ignore[import-untyped]
    except Exception:
        return deepcopy(DEFAULT_PDF_PRESENTATION_CONFIG)

    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return deepcopy(DEFAULT_PDF_PRESENTATION_CONFIG)

    if not isinstance(data, dict):
        return deepcopy(DEFAULT_PDF_PRESENTATION_CONFIG)

    merged = _deep_merge(DEFAULT_PDF_PRESENTATION_CONFIG, data)
    return _normalize_config(merged)


def resolve_pdf_presentation_config(
    root: Path,
    *,
    scope: str,
    profile_id: str | None = None,
    diffusion: str | None = "externe",
    gabarit_id: str | None = None,
    is_brochure: bool = False,
) -> dict[str, Any]:
    """Calcule la configuration finale effective après empilement des surcharges (scope, profil, gabarit)."""
    raw = load_pdf_presentation_raw_config(root)

    defaults = raw.get("defaults", {})
    effective = deepcopy(defaults if isinstance(defaults, dict) else {})

    scopes = raw.get("scopes", {})
    if scope == "filtre_thematique":
        global_cfg = scopes.get("global", {}) if isinstance(scopes, dict) else {}
        if isinstance(global_cfg, dict):
            effective = _deep_merge(effective, global_cfg)
    scope_cfg = scopes.get(scope, {}) if isinstance(scopes, dict) else {}
    if isinstance(scope_cfg, dict):
        effective = _deep_merge(effective, scope_cfg)

    if profile_id:
        profiles = raw.get("profiles", {})
        profile_cfg = profiles.get(profile_id, {}) if isinstance(profiles, dict) else {}
        if isinstance(profile_cfg, dict) and profile_cfg:
            target_scope = str(profile_cfg.get("scope", "")).strip().lower()
            if not target_scope or target_scope == str(scope).strip().lower():
                effective = _deep_merge(effective, profile_cfg)

    diffusion_norm = normalize_diffusion(diffusion)
    if diffusion_norm == "externe":
        profiles = raw.get("profiles", {})
        ext_cfg = profiles.get("_diffusion_externe", {}) if isinstance(profiles, dict) else {}
        if isinstance(ext_cfg, dict) and ext_cfg:
            overlay = {k: v for k, v in ext_cfg.items() if k != "scope"}
            effective = _deep_merge(effective, overlay)

    if not gabarit_id:
        from core.common.chargeur_gabarits import load_gabarit
        if profile_id and load_gabarit(profile_id, root, warn_if_missing=False):
            gabarit_id = profile_id
        else:
            gabarit_id = "brochure_defaut" if is_brochure else "gabarit_defaut"

    layout_mode = "standard"
    if gabarit_id:
        from core.common.chargeur_gabarits import load_gabarit, is_gabarit_compatible
        gabarit_data = load_gabarit(gabarit_id, root)
        target_cible = "brochure" if is_brochure else "bilan"
        if gabarit_data and is_gabarit_compatible(gabarit_data, profile_id=profile_id, cible=target_cible):
            if "layout_mode" in gabarit_data:
                layout_mode = str(gabarit_data["layout_mode"]).strip()
            else:
                raw_layout = gabarit_data.get("layout_grid", gabarit_data.get("layout", "standard"))
                if isinstance(raw_layout, dict):
                    layout_mode = "standard"
                else:
                    layout_mode = str(raw_layout).strip()
            gabarit_overrides = {
                k: v for k, v in gabarit_data.items()
                if k not in (
                    "version", "gabarit_id", "label", "description",
                    "cible", "organisation", "profils_compatibles", "layout", "layout_grid"
                )
            }
            if gabarit_overrides:
                effective = _deep_merge(effective, gabarit_overrides)

    registry = raw.get("feature_registry", {})
    if isinstance(registry, dict):
        apply_feature_registry_to_effective(effective, scope, registry)

    return {
        "version": raw.get("version", 1),
        "behavior": raw.get("behavior", {}),
        "feature_registry": raw.get("feature_registry", {}),
        "effective": effective,
        "diffusion": diffusion_norm,
        "gabarit_id": gabarit_id,
        "layout_mode": layout_mode,
    }


# ========================================================================================
# RÈGLES ET MENTIONS DE DIFFUSION
# ========================================================================================

INTERNAL_DIFFUSION_TITLE_NOTICE = (
    "Diffusion restreinte – Document contenant des données sensibles – "
    "Réservé aux services autorisés."
)


def normalize_diffusion(value: str | None) -> str:
    """Valide le mode de diffusion du rapport (`interne` ou `externe`)."""
    s = str(value or "externe").strip().lower()
    if s in ("interne", "internal", "int"):
        return "interne"
    return "externe"


def should_show_internal_diffusion_title_notice(diffusion: str | None) -> bool:
    """Indique si l'avertissement de diffusion restreinte doit apparaître sur la couverture."""
    return normalize_diffusion(diffusion) == "interne"


def diffusion_pdf_suffix(diffusion: str | None) -> str:
    """Génère le suffixe du nom de fichier PDF (`_int` pour interne, `_ext` pour externe)."""
    return "_ext" if normalize_diffusion(diffusion) == "externe" else "_int"


def apply_diffusion_pdf_suffix(path: Path | str, diffusion: str | None) -> Path:
    """Ajoute le suffixe de diffusion avant l'extension `.pdf` du fichier."""
    p = Path(path)
    tag = diffusion_pdf_suffix(diffusion)
    if p.suffix.lower() == ".pdf":
        return p.with_name(f"{p.stem}{tag}{p.suffix}")
    return p.with_name(f"{p.name}{tag}.pdf")


# ========================================================================================
# RESOLUTION DES SOUS-ENSEMBLES DE CONFIGURATION (PAGE DE GARDE, TABLES, CHARTE)
# ========================================================================================

def resolve_title_page_config(
    root: Path,
    *,
    scope: str,
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Extrait les paramètres de mise en forme de la page de garde."""
    resolved = resolve_pdf_presentation_config(root, scope=scope, profile_id=profile_id)
    effective = resolved.get("effective", {})
    title_page = (
        effective.get("title_page", {})
        if isinstance(effective, dict)
        else {}
    )
    default_title_page = DEFAULT_PDF_PRESENTATION_CONFIG["defaults"]["title_page"]
    if not isinstance(title_page, dict):
        return deepcopy(default_title_page)
    return _deep_merge(default_title_page, title_page)


def resolve_internal_diffusion_notice_config(
    title_page_cfg: dict[str, Any] | None,
) -> dict[str, Any]:
    """Retourne la configuration du bandeau d'avertissement de diffusion restreinte."""
    default_notice = DEFAULT_PDF_PRESENTATION_CONFIG["defaults"]["title_page"][
        "internal_diffusion_notice"
    ]
    title_page = title_page_cfg if isinstance(title_page_cfg, dict) else {}
    notice = title_page.get("internal_diffusion_notice", {})
    if not isinstance(notice, dict):
        notice = {}
    merged = _deep_merge(deepcopy(default_notice), notice)
    text = str(merged.get("text", "")).strip()
    if not text:
        merged["text"] = INTERNAL_DIFFUSION_TITLE_NOTICE
    return merged


def resolve_notice_methodology_config(effective_cfg: dict[str, Any]) -> dict[str, Any]:
    """Retourne les paragraphes de la notice méthodologique initiale."""
    default_notice = DEFAULT_PDF_PRESENTATION_CONFIG["defaults"]["notice_methodology"]
    if not isinstance(effective_cfg, dict):
        return deepcopy(default_notice)
    notice = effective_cfg.get("notice_methodology", {})
    if not isinstance(notice, dict):
        return deepcopy(default_notice)
    return _deep_merge(default_notice, notice)


def resolve_tables_layout(effective_cfg: dict[str, Any] | None) -> dict[str, Any]:
    """Retourne les contraintes de rendu des tableaux (hauteur max, sécabilité, marges)."""
    base = deepcopy(
        (DEFAULT_PDF_PRESENTATION_CONFIG.get("defaults") or {}).get("tables") or {}
    )
    if not isinstance(effective_cfg, dict):
        return base
    user = effective_cfg.get("tables")
    if isinstance(user, dict) and user:
        return _deep_merge(base, user)
    return base


def resolve_charte_config(effective_cfg: dict[str, Any] | None) -> dict[str, Any]:
    """Retourne la configuration des filigranes et bandeaux institutionnels."""
    base = deepcopy(
        (DEFAULT_PDF_PRESENTATION_CONFIG.get("defaults") or {}).get("charte") or {}
    )
    if not isinstance(effective_cfg, dict):
        return base
    user = effective_cfg.get("charte")
    if isinstance(user, dict) and user:
        return _deep_merge(base, user)
    return base


def resolve_charte_config_from_root(
    root: Path,
    *,
    scope: str,
    profile_id: str | None = None,
    diffusion: str | None = None,
) -> dict[str, Any]:
    """Détermine la charte visuelle effective à appliquer pour un rapport donné."""
    resolved = resolve_pdf_presentation_config(
        root,
        scope=scope,
        profile_id=profile_id,
        diffusion=diffusion,
    )
    effective = resolved.get("effective", {})
    if not isinstance(effective, dict):
        return resolve_charte_config({})
    return resolve_charte_config(effective)


def resolve_sec6_methodology_config(effective_cfg: dict[str, Any]) -> dict[str, Any]:
    """Retourne les paragraphes conditionnels de l'annexe méthodologique (Section 6)."""
    default_cfg = DEFAULT_PDF_PRESENTATION_CONFIG["defaults"]["sec6_methodology"]
    if not isinstance(effective_cfg, dict):
        return deepcopy(default_cfg)
    cfg = effective_cfg.get("sec6_methodology", {})
    if not isinstance(cfg, dict):
        return deepcopy(default_cfg)
    return _deep_merge(default_cfg, cfg)


def get_effective_pdf_presentation(
    root: Path,
    *,
    scope: str,
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Accès direct aux valeurs de configuration fusionnées."""
    resolved = resolve_pdf_presentation_config(root, scope=scope, profile_id=profile_id)
    effective = resolved.get("effective", {})
    return effective if isinstance(effective, dict) else {}


# ========================================================================================
# FILTRAGE ET VALIDATION DES SECTIONS ET BLOCS
# ========================================================================================

def feature_registry_allows_scope(rule: Any, scope: str, section_id: str = "") -> bool:
    """Vérifie si une fonctionnalité est autorisée pour le périmètre courant."""
    r = str(rule or "both").strip().lower()
    s = str(scope or "").strip().lower()
    if r in ("both", "all", ""):
        return True
    if s == "filtre_thematique":
        if str(section_id).lower() in ("sec5", "sec5map", "sec5_map"):
            return True
        return r == "thematique"
    return r == s


def apply_feature_registry_to_effective(
    effective_cfg: dict[str, Any],
    scope: str,
    feature_registry: dict[str, Any],
) -> None:
    """Désactive les chapitres non concernés par le type de bilan généré."""
    sections = effective_cfg.setdefault("sections", {})
    enabled = sections.setdefault("enabled", {})
    if not isinstance(enabled, dict):
        enabled = {}
        sections["enabled"] = enabled
    for sid, rule in feature_registry.items():
        canonical = normalize_section_id(str(sid), emit_alias_warning=False)
        if canonical in enabled or str(sid) in enabled:
            continue
        if not feature_registry_allows_scope(rule, scope, str(sid)):
            enabled[canonical] = False


def normalize_section_id(section_id: str, *, emit_alias_warning: bool = False) -> str:
    """Convertit un identifiant ou alias de section vers sa forme canonique interne."""
    sid = str(section_id or "").strip()
    if not sid:
        return sid
    canonical = SECTION_ID_ALIASES.get(sid, sid)
    if emit_alias_warning and canonical != sid:
        warnings.warn(
            f"Identifiant de section PDF déprécié « {sid} » : utiliser « {canonical} » "
            f"(alias maintenu pour rétrocompatibilité).",
            DeprecationWarning,
            stacklevel=2,
        )
    return canonical


def is_section_enabled(
    effective_cfg: dict[str, Any],
    section_id: str,
    default: bool = True,
) -> bool:
    """Indique si un chapitre doit figurer dans le PDF selon la configuration YAML."""
    sections = effective_cfg.get("sections", {})
    if not isinstance(sections, dict):
        return default
    enabled = sections.get("enabled", {})
    if not isinstance(enabled, dict):
        return default
    sid = normalize_section_id(section_id, emit_alias_warning=False)
    if sid in enabled:
        return bool(enabled[sid])
    for alias, canonical in SECTION_ID_ALIASES.items():
        if canonical == sid and alias in enabled:
            return bool(enabled[alias])
    return default


def _resolve_blocks_node(effective_cfg: dict[str, Any], block_id: str) -> Any:
    """Lit une sous-clé de bloc de configuration sous la forme `nom_section.nom_bloc`."""
    blocks = effective_cfg.get("blocks", {})
    if not isinstance(blocks, dict):
        return None
    node: Any = blocks
    for part in str(block_id).split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def is_block_enabled(
    effective_cfg: dict[str, Any],
    block_id: str,
    default: bool = True,
) -> bool:
    """Vérifie l'activation d'un sous-bloc ou d'un tableau spécifique dans la configuration."""
    val = _resolve_blocks_node(effective_cfg, block_id)
    if val is None:
        return default
    return bool(val)


def is_commentaires_auto_enabled(
    effective_cfg: dict[str, Any],
    default: bool = True,
) -> bool:
    """Vérifie l'activation globale de la génération automatisée des commentaires."""
    if not isinstance(effective_cfg, dict):
        return default
    if "commentaires_auto" in effective_cfg:
        return bool(effective_cfg["commentaires_auto"])
    behavior = effective_cfg.get("behavior", {})
    if isinstance(behavior, dict) and "commentaires_auto" in behavior:
        return bool(behavior["commentaires_auto"])
    return default


def get_block_int(
    effective_cfg: dict[str, Any],
    block_id: str,
    default: int = 0,
) -> int:
    """Lit une contrainte numérique (ex: plafond de lignes dans un tableau)."""
    val = _resolve_blocks_node(effective_cfg, block_id)
    if val is None:
        return int(default)
    try:
        return int(val)
    except (TypeError, ValueError):
        return int(default)


# ========================================================================================
# TRONCATION ET LEGENDES DES TABLEAUX DE PROCEDURES
# ========================================================================================

def slice_proc_detail_for_pdf(
    detail_df: Any,
    effective_cfg: dict[str, Any],
    block_prefix: str,
) -> tuple[Any, int]:
    """Plafonne le nombre de lignes affichées dans un tableau détaillé de procédures."""
    if detail_df is None or getattr(detail_df, "empty", True):
        return detail_df, 0
    total = int(len(detail_df))
    cap = get_block_int(effective_cfg, f"{block_prefix}.max_detail_rows", default=0)
    if cap <= 0:
        return detail_df, total
    return detail_df.head(cap), total


def format_proc_detail_caption(
    base_caption: str,
    *,
    shown: int,
    total: int,
    cap: int,
) -> str:
    """Complète la légende avec le nombre de lignes retenues en cas de troncation."""
    if cap > 0 and shown < total:
        return f"{base_caption} ({shown} premiers sur {total})"
    return base_caption


# ========================================================================================
# AGENCEMENT ET STRUCTURATION DE LA TABLE DES MATIERES
# ========================================================================================

def inject_sec4_subsections(
    section_defs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Injecte les sous-sections d'activité usagers à la suite du chapitre 3."""
    out: list[tuple[str, str]] = []
    for sid, title in section_defs:
        out.append((sid, title))
        if sid == "sec4":
            out.extend(SEC4_SUBSECTION_DEFAULTS)
    return out


def resolve_sec2_render_order(
    sections_toc: list[tuple[str, str]],
    *,
    include_zone_subsections: bool,
) -> list[str]:
    """Retourne l'ordre de rendu des sous-parties de la section 2 (Contrôles)."""
    allowed = (
        {"sec21", "sec22", "sec23", "sec22theme", "sec22res"}
        if include_zone_subsections
        else {"sec21", "sec22", "sec23"}
    )
    order = [sid for sid, _ in sections_toc if sid in allowed]
    if order:
        return order
    fallback = ["sec21", "sec22", "sec23"]
    if include_zone_subsections:
        fallback.extend(["sec22theme", "sec22res"])
    return [sid for sid in fallback if sid in allowed]


def resolve_sec34_render_order(
    effective_cfg: dict[str, Any],
) -> list[str]:
    """Détermine l'ordre de présentation des chapitres Usagers et Procédures."""
    canonical = ("sec4", "sec3")
    sections_cfg = effective_cfg.get("sections", {})
    if not isinstance(sections_cfg, dict):
        sections_cfg = {}
    order_raw = sections_cfg.get("order", [])
    order = order_raw if isinstance(order_raw, list) else []
    order_ids = [
        normalize_section_id(str(x).strip(), emit_alias_warning=False)
        for x in order
        if str(x).strip()
    ]
    picked = [
        sid
        for sid in order_ids
        if sid in canonical and is_section_enabled(effective_cfg, sid, True)
    ]
    if picked:
        return picked
    return [sid for sid in canonical if is_section_enabled(effective_cfg, sid, True)]


def resolve_sections_for_toc(
    effective_cfg: dict[str, Any],
    section_defs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Construit la liste ordonnée des sections actives pour constituer le sommaire."""
    by_id = {sid: (sid, title) for sid, title in section_defs}

    sections_cfg = effective_cfg.get("sections", {})
    if not isinstance(sections_cfg, dict):
        sections_cfg = {}

    order_raw = sections_cfg.get("order", [])
    order = order_raw if isinstance(order_raw, list) else []
    order_ids = [
        normalize_section_id(str(x).strip(), emit_alias_warning=True)
        for x in order
        if str(x).strip()
    ]

    def get_parent_id(sid: str) -> str:
        if sid.startswith("sec2"):
            return "sec2"
        if sid.startswith("sec3"):
            return "sec3"
        if sid.startswith("sec4"):
            return "sec4"
        return sid

    # Construire la liste étendue des order_ids en incluant les sous-sections de section_defs rattachées
    expanded_order_ids: list[str] = []
    seen_ids: set[str] = set()

    for sid in order_ids:
        if sid in by_id and sid not in seen_ids:
            expanded_order_ids.append(sid)
            seen_ids.add(sid)
        
        # Insérer les sous-sections de section_defs rattachées à cette section principale
        for def_sid, _ in section_defs:
            if def_sid not in order_ids and def_sid not in seen_ids:
                if def_sid.startswith(sid) or get_parent_id(def_sid) == sid:
                    expanded_order_ids.append(def_sid)
                    seen_ids.add(def_sid)

    # Récupérer les éléments ordonnés selon l'ordre étendu
    ordered_tuples: list[tuple[str, str]] = []
    seen_in_ordered: set[str] = set()
    for sid in expanded_order_ids:
        sec = by_id.get(sid)
        if sec is None:
            continue
        if is_section_enabled(effective_cfg, sid, True):
            ordered_tuples.append(sec)
            seen_in_ordered.add(sid)

    # Assembler le sommaire final en préservant l'ordre canonique de section_defs pour les reliquats (ex: sec5)
    final_ordered: list[tuple[str, str]] = []
    ordered_dict = {sid: title for sid, title in ordered_tuples}

    for sid, title in section_defs:
        if sid in ordered_dict:
            final_ordered.append((sid, ordered_dict[sid]))
        elif is_section_enabled(effective_cfg, sid, True) and sid not in seen_in_ordered:
            final_ordered.append((sid, title))
            seen_in_ordered.add(sid)

    # Ajouter les éventuels éléments de ordered_tuples non présents dans section_defs
    for sid, title in ordered_tuples:
        if (sid, title) not in final_ordered:
            final_ordered.append((sid, title))

    return final_ordered


def resolve_section_titles(
    effective_cfg: dict[str, Any],
    section_defs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Applique les éventuelles surcharges de titres définies par le profil dans le YAML."""
    sections_cfg = effective_cfg.get("sections", {})
    if not isinstance(sections_cfg, dict):
        return section_defs
    titles_cfg = sections_cfg.get("titles", {})
    if not isinstance(titles_cfg, dict):
        return section_defs

    out: list[tuple[str, str]] = []
    for sid, default_title in section_defs:
        custom = titles_cfg.get(sid)
        if custom is None:
            for alias, canonical in SECTION_ID_ALIASES.items():
                if canonical == sid and alias in titles_cfg:
                    custom = titles_cfg[alias]
                    break
        custom = custom if custom is not None else default_title
        title = str(custom).strip() if custom is not None else ""
        out.append((sid, title or default_title))
    return out


def should_show_placeholder(
    behavior_cfg: dict[str, Any] | None,
) -> bool:
    """Indique si un paragraphe explicatif doit s'afficher en l'absence de données."""
    if not isinstance(behavior_cfg, dict):
        return False
    policy = str(behavior_cfg.get("missing_data_policy", "hide_silently")).strip().lower()
    return policy == "show_placeholder"


# ========================================================================================
# CONSTRUCTEURS TYPOGRAPHIQUES DU TITRE DE COUVERTURE
# ========================================================================================

def normalize_dept_typography(name: str) -> str:
    """Harmonise la typographie des noms de département (apostrophes typographiques `’`)."""
    s = str(name or "").strip()
    s = s.replace("-d'", " d’").replace("-D'", " D’")
    s = s.replace("d'", "d’").replace("D'", "D’")
    return " ".join(s.split())


def get_dept_coord(dept_name: str) -> str:
    """Retourne l'article grammatical du département (ex: 'de la', 'du', 'des', 'd'')."""
    from core.chemins_projet import PROJECT_ROOT
    import yaml

    dept_key = str(dept_name).strip()
    try:
        cfg_path = PROJECT_ROOT / "config" / "departements.yaml"
        if cfg_path.exists():
            with cfg_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                coord_map = data.get("coordination_departement", {})
                if dept_key in coord_map:
                    return coord_map[dept_key]
    except Exception:
        pass
    return "de la"


def format_perimetre_title_label(echelle: str, perimetre_name_typo: str) -> str:
    """Formate l'intitulé du périmètre pour les titres PDF selon l'échelle et la grammaire française."""
    from core.common.utilitaires_metier import DEPT_NAMES, get_dept_name, get_region_name

    e_norm = str(echelle).strip().lower()
    p_name = str(perimetre_name_typo).strip()
    if not p_name:
        return ""

    if p_name.lower().startswith("région"):
        return p_name
    reg_val = get_region_name(p_name)
    if (reg_val != f"Région {p_name}" and reg_val != p_name) or e_norm == "region":
        return f"Région {p_name}"

    # Détection multi-départements (ex: "21_52", "21, 52", "Côte-d'Or et Haute-Marne")
    clean_p = p_name.replace(" et ", ",").replace("_", ",")
    raw_tokens = [t.strip() for t in clean_p.split(",") if t.strip()]
    all_depts = [t for t in raw_tokens if t in DEPT_NAMES or t.isdigit() or t in DEPT_NAMES.values()]

    if len(all_depts) > 1:
        formatted_depts = [get_dept_name(d) for d in all_depts]
        if len(formatted_depts) == 2:
            return f"Départements {formatted_depts[0]} et {formatted_depts[1]}"
        else:
            return f"Départements {', '.join(formatted_depts[:-1])} et {formatted_depts[-1]}"

    if e_norm == "departement":
        if p_name.lower().startswith("département"):
            return p_name
        coord = get_dept_coord(p_name)
        return f"Département {coord} {p_name}"
    else:
        return p_name


def build_title_lines_from_cfg(
    effective_cfg: dict[str, Any],
    *,
    profile_label: str,
    perimetre_name_typo: str,
    echelle: str = "departement",
) -> tuple[list[str], list[str]]:
    """Formate les 3 lignes du titre principal sur la page de couverture et l'en-tête."""
    default_line1 = "Bilan des activités de police\nde l'environnement de l'OFB"

    title_cfg = effective_cfg.get("title", {}) if isinstance(effective_cfg, dict) else {}
    if not isinstance(title_cfg, dict):
        title_cfg = {}

    gabarit_id = effective_cfg.get("gabarit_id") if isinstance(effective_cfg, dict) else None

    line1 = str(title_cfg.get("line1", default_line1)).strip() or default_line1

    line2_mode = str(title_cfg.get("line2_mode", "profile_label")).strip().lower()
    if line2_mode == "none":
        line2 = ""
    elif line2_mode == "fixed":
        fixed_val = str(title_cfg.get("line2_fixed", "")).strip()
        if gabarit_id == "srp_r27" and echelle == "departement" and perimetre_name_typo:
            coord = get_dept_coord(perimetre_name_typo)
            line2 = f"Service départemental {coord} {perimetre_name_typo} — Service Régional Police"
        else:
            line2 = fixed_val
    else:
        line2 = str(profile_label).strip()

    line3_mode = str(title_cfg.get("line3_mode", "department")).strip().lower()
    if line3_mode == "none":
        line3 = ""
    elif line3_mode == "fixed":
        line3 = str(title_cfg.get("line3_fixed", "")).strip()
    else:
        line3 = format_perimetre_title_label(echelle, perimetre_name_typo)

    def _flatten(text: str) -> str:
        return " ".join(part.strip() for part in str(text).splitlines() if part.strip())

    def _split(text: str) -> list[str]:
        return [part.strip() for part in str(text).splitlines() if part.strip()]

    header_lines = [_flatten(x) for x in [line1, line2, line3] if x]

    cover_lines: list[str] = []
    cover_lines.extend(_split(line1))
    cover_lines.append("")
    if line2:
        cover_lines.extend(_split(line2))
    cover_lines.extend(_split(line3))

    return cover_lines, header_lines


def resolve_cover_subtitle(
    title_page_cfg: dict[str, Any],
    *,
    nb_pve: int = 0,
) -> str:
    """Retourne le sous-titre de la page de garde s'il est spécifié dans la configuration."""
    del nb_pve
    mode = str(title_page_cfg.get("subtitle_mode", "none")).strip().lower()
    if mode == "fixed":
        return str(title_page_cfg.get("subtitle_fixed", "")).strip()
    return ""
