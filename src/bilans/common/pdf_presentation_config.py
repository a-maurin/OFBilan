"""Chargement/fusion de la configuration de présentation PDF (YAML)."""
from __future__ import annotations

import warnings
from copy import deepcopy
from pathlib import Path
from typing import Any

# Alias sémantiques (migration progressive) → identifiants historiques internes.
SECTION_ID_ALIASES: dict[str, str] = {
    "sec_usagers": "sec4",
    "sec_procedures": "sec3",
}

# Sous-sections du chapitre « Activité par type d'usager » (ID interne sec4, numérotation PDF 3.x).
SEC4_SUBSECTION_DEFAULTS: tuple[tuple[str, str], ...] = (
    ("sec41", "3.1. Thème de contrôle par type d'usager"),
    ("sec42", "3.2. Résultats des contrôles par type d'usager"),
    ("sec43", "3.3. Procédures d'enquête judiciaire (PEJ) par type d'usager"),
    ("sec44", "3.4. Procédures administratives (PA) par type d'usager"),
)


DEFAULT_PDF_PRESENTATION_CONFIG: dict[str, Any] = {
    "version": 1,
    "behavior": {
        "missing_data_policy": "hide_silently",  # hide_silently | show_placeholder
        "unknown_block_policy": "ignore",  # ignore | warn
    },
    "defaults": {
        "title": {
            "model": "three_lines",
            "line1": "Bilan des activités de police\nde l'environnement de l'OFB",
            "line2_mode": "profile_label",  # profile_label | fixed | none
            "line2_fixed": "",
            "line3_mode": "department",  # department | fixed
            "line3_fixed": "",
            "typography": {
                "normalize_department_name": True,
                "apostrophe_style": "typographic",  # typographic | ascii
            },
        },
        "title_page": {
            "alignment": "right",  # left | center | right
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
                    "text": (
                        "<b>Réalisation :</b> service départemental de la Côte d'Or."
                    ),
                },
            ],
        },
        # Mise en page des tableaux PDF (ReportLab) — préférer le pilotage YAML.
        "tables": {
            # Si false : pas de coupure entre pages sauf si le tableau dépasse max_rows_keep_together
            # (dans ce cas add_table force split_by_row et désactive KeepTogether).
            "split_by_row": False,
            "max_rows_keep_together": 8,
            "max_cell_chars_before_split": 100,
            "vertical_header": {
                # Décalage horizontal fin (pt) après centrage des libellés verticaux.
                "pad_x_pt": 0.0,
                # Segments empilés pour libellés longs (ex. domaines) ; hauteur de ligne d'en-tête adaptée.
                "max_lines": 6,
                "font_size": 7.0,
                "row_padding_pt": 8.0,
            },
            "usagers_x_domaine": {
                # Nombre maximal de colonnes « domaine » affichées (tri décroissant sur le volume).
                # null ou <= 0 : pas de limite sur les colonnes.
                "max_domain_columns": 14,
                # horizontal_wrap (défaut) ou vertical pour les en-têtes de colonnes domaine.
                "header_layout": "horizontal_wrap",
                "header_font_size": 7.0,
                "header_wrap_max_lines": 5,
                # Part de largeur pour la colonne type_usager (reste réparti entre les domaines).
                "first_column_width_ratio": 0.20,
                # Nombre maximal de lignes « type d'usager » (tri décroissant sur le volume).
                # null ou <= 0 : pas de limite sur les lignes.
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
                # Enveloppe HTML ; {note} = parties concaténées (colonnes / lignes).
                "overflow_note_wrap": "<i>{note}</i>",
            },
        },
        # Éléments visuels OFB (filigranes, bandeaux) — calibrés sur le modèle Word dotx.
        # Le texte de pied de page (coordonnées SD départemental) reste géré par PDFReportBuilder.
        "charte": {
            "assets": {
                "banner": "image5.jpg",
                "title_page_deco": "image6.jpeg",
                "watermark": "image3.jpeg",
                "footer_deco": "image4.jpeg",
            },
            "title_page": {
                # Bandeau Marianne + OFB en haut (header2 dotx ≈ 42 mm).
                "banner_height_mm": 42.0,
                # Fond décoratif bleu bas de page de garde (footer2 dotx, image6).
                "deco_height_ratio": 0.50,
                "deco_align": "bottom_right",
            },
            "content_page": {
                "watermark_enabled": True,
                # Filigrane courbes : une seule instance, ancrée bas-droite (comme visuel page de garde).
                "filigrane_height_ratio": 0.50,
                "filigrane_align": "bottom_right",
                # Conservé pour compatibilité ; ignoré si filigrane_height_ratio est défini.
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


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge récursif de dictionnaires (override prioritaire)."""
    out = deepcopy(base)
    for key, value in (override or {}).items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _hoist_legacy_section_titles(node: dict[str, Any]) -> None:
    """
    Compatibilité : ``titles`` au même niveau que ``sections`` (ancien YAML)
    → fusion dans ``sections.titles``.
    """
    legacy = node.get("titles")
    if not isinstance(legacy, dict):
        return
    sections = node.get("sections")
    if not isinstance(sections, dict):
        return
    nested = sections.get("titles")
    if isinstance(nested, dict):
        sections["titles"] = _deep_merge(legacy, nested)
    else:
        sections["titles"] = deepcopy(legacy)
    del node["titles"]


def _normalize_config(data: dict[str, Any]) -> dict[str, Any]:
    """Normalisation minimale des clés attendues."""
    out = deepcopy(data)
    out.setdefault("version", 1)
    out.setdefault("behavior", {})
    out["behavior"].setdefault("missing_data_policy", "hide_silently")
    out["behavior"].setdefault("unknown_block_policy", "ignore")
    out.setdefault("defaults", {})
    out.setdefault("scopes", {})
    out.setdefault("profiles", {})
    out.setdefault("feature_registry", {})
    for scope_cfg in out.get("scopes", {}).values():
        if isinstance(scope_cfg, dict):
            _hoist_legacy_section_titles(scope_cfg)
    for profile_cfg in out.get("profiles", {}).values():
        if isinstance(profile_cfg, dict):
            _hoist_legacy_section_titles(profile_cfg)
    return out


def load_pdf_presentation_raw_config(root: Path) -> dict[str, Any]:
    """
    Charge la configuration brute depuis config/presentation/pdf_presentation.yaml
    puis, en fallback de compatibilite, depuis ref/pdf_presentation.yaml.

    Retourne toujours une config valide (fallback sur DEFAULT).
    """
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
    diffusion: str | None = "interne",
) -> dict[str, Any]:
    """
    Résout la config effective :
    defaults -> scopes[scope] -> profiles[profile_id] (si scope compatible).
    """
    raw = load_pdf_presentation_raw_config(root)

    defaults = raw.get("defaults", {})
    effective = deepcopy(defaults if isinstance(defaults, dict) else {})

    scopes = raw.get("scopes", {})
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
            # Overlay hors scope profil : règles communes de diffusion externe.
            overlay = {k: v for k, v in ext_cfg.items() if k != "scope"}
            effective = _deep_merge(effective, overlay)

    registry = raw.get("feature_registry", {})
    if isinstance(registry, dict):
        apply_feature_registry_to_effective(effective, scope, registry)

    return {
        "version": raw.get("version", 1),
        "behavior": raw.get("behavior", {}),
        "feature_registry": raw.get("feature_registry", {}),
        "effective": effective,
        "diffusion": diffusion_norm,
    }


INTERNAL_DIFFUSION_TITLE_NOTICE = (
    "Diffusion restreinte – Document contenant des données sensibles – "
    "Réservé aux services autorisés."
)


def normalize_diffusion(value: str | None) -> str:
    """Retourne ``interne`` ou ``externe`` (défaut : interne)."""
    s = str(value or "interne").strip().lower()
    if s in ("externe", "external", "ext"):
        return "externe"
    return "interne"


def should_show_internal_diffusion_title_notice(diffusion: str | None) -> bool:
    """Afficher la mention de diffusion restreinte sur la page de garde."""
    return normalize_diffusion(diffusion) == "interne"


def diffusion_pdf_suffix(diffusion: str | None) -> str:
    """Suffixe de nom de fichier PDF selon le périmètre de diffusion."""
    return "_ext" if normalize_diffusion(diffusion) == "externe" else "_int"


def apply_diffusion_pdf_suffix(path: Path | str, diffusion: str | None) -> Path:
    """Ajoute ``_int`` ou ``_ext`` avant l'extension ``.pdf``."""
    p = Path(path)
    tag = diffusion_pdf_suffix(diffusion)
    if p.suffix.lower() == ".pdf":
        return p.with_name(f"{p.stem}{tag}{p.suffix}")
    return p.with_name(f"{p.name}{tag}.pdf")


def resolve_title_page_config(
    root: Path,
    *,
    scope: str,
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Retourne la configuration effective de la page de garde."""
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
    """
    Mise en page de la mention « diffusion restreinte » sur la page de garde.

    ``text`` vide dans le YAML : texte par défaut ``INTERNAL_DIFFUSION_TITLE_NOTICE``.
    """
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
    """Retourne la configuration effective de la notice méthodologique."""
    default_notice = DEFAULT_PDF_PRESENTATION_CONFIG["defaults"]["notice_methodology"]
    if not isinstance(effective_cfg, dict):
        return deepcopy(default_notice)
    notice = effective_cfg.get("notice_methodology", {})
    if not isinstance(notice, dict):
        return deepcopy(default_notice)
    return _deep_merge(default_notice, notice)


def resolve_tables_layout(effective_cfg: dict[str, Any] | None) -> dict[str, Any]:
    """Fusionne la section ``tables`` de la config effective avec les valeurs par défaut."""
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
    """Fusionne la section ``charte`` (filigranes, bandeaux) avec les valeurs par défaut."""
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
    """Retourne la configuration effective de la charte graphique PDF."""
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
    """Retourne la configuration effective de la méthodologie d'annexe (sec6)."""
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
    """Retourne uniquement la config effective fusionnée."""
    resolved = resolve_pdf_presentation_config(root, scope=scope, profile_id=profile_id)
    effective = resolved.get("effective", {})
    return effective if isinstance(effective, dict) else {}


def feature_registry_allows_scope(rule: Any, scope: str) -> bool:
    """
    Indique si une entrée ``feature_registry`` autorise la section pour ce moteur.

    Valeurs attendues : ``both``, ``global``, ``thematique`` (insensible à la casse).
    """
    r = str(rule or "both").strip().lower()
    s = str(scope or "").strip().lower()
    if r in ("both", "all", ""):
        return True
    return r == s


def apply_feature_registry_to_effective(
    effective_cfg: dict[str, Any],
    scope: str,
    feature_registry: dict[str, Any],
) -> None:
    """
    Désactive les sections hors périmètre moteur via ``sections.enabled``.

    Une clé déjà présente dans ``sections.enabled`` (profil ou scope) n'est pas écrasée.
    """
    sections = effective_cfg.setdefault("sections", {})
    enabled = sections.setdefault("enabled", {})
    if not isinstance(enabled, dict):
        enabled = {}
        sections["enabled"] = enabled
    for sid, rule in feature_registry.items():
        canonical = normalize_section_id(str(sid), emit_alias_warning=False)
        if canonical in enabled or str(sid) in enabled:
            continue
        if not feature_registry_allows_scope(rule, scope):
            enabled[canonical] = False


def normalize_section_id(section_id: str, *, emit_alias_warning: bool = False) -> str:
    """
    Résout un identifiant de section (alias sémantique → ID historique interne).

    Les alias ``sec_usagers`` / ``sec_procedures`` restent acceptés dans le YAML
    avec un avertissement de dépréciation.
    """
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
    """Vrai si la section est activée dans effective.sections.enabled."""
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
    """Valeur du nœud effective.blocks pour un chemin pointé (ex. sec31.max_detail_rows)."""
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
    """Vrai si le bloc est activé dans effective.blocks (supporte les clés imbriquées via '.')."""
    val = _resolve_blocks_node(effective_cfg, block_id)
    if val is None:
        return default
    return bool(val)


def get_block_int(
    effective_cfg: dict[str, Any],
    block_id: str,
    default: int = 0,
) -> int:
    """
    Entier dans effective.blocks (clés imbriquées via '.').

    Pour ``sec31.max_detail_rows`` : 0 ou absent = pas de plafond sur le tableau détail ;
    entier > 0 = nombre maximal de lignes affichées.
    """
    val = _resolve_blocks_node(effective_cfg, block_id)
    if val is None:
        return int(default)
    try:
        return int(val)
    except (TypeError, ValueError):
        return int(default)


def slice_proc_detail_for_pdf(
    detail_df: Any,
    effective_cfg: dict[str, Any],
    block_prefix: str,
) -> tuple[Any, int]:
    """Retourne (dataframe tronqué selon max_detail_rows, nombre total de lignes)."""
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
    """Suffixe « N premiers sur T » si le plafond YAML tronque le détail."""
    if cap > 0 and shown < total:
        return f"{base_caption} ({shown} premiers sur {total})"
    return base_caption


def inject_sec4_subsections(
    section_defs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Insère les sous-sections 3.x immédiatement après ``sec4`` dans la liste de définition."""
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
    """
    Ordre de rendu des sous-parties du chapitre 2 (piloté par ``sections_toc``).

    ``include_zone_subsections`` : True pour le profil agrainage (sec22theme / sec22res).
    """
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
    """
    Ordre de rendu des chapitres « Activité par type d'usager » (sec4) et
    « Procédures » (sec3), aligné sur la numérotation PDF (3 puis 4).

    Priorité : ``sections.order`` du YAML, puis repli ``sec4`` puis ``sec3``.
    """
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
    """
    Applique sections.order + sections.enabled à la liste des sections.

    - Les sections non listées dans order sont conservées en fin (ordre initial).
    - Les sections désactivées sont retirées.
    """
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

    ordered: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sid in order_ids:
        sec = by_id.get(sid)
        if sec is None:
            continue
        if is_section_enabled(effective_cfg, sid, True):
            ordered.append(sec)
        seen.add(sid)

    for sid, title in section_defs:
        if sid in seen:
            continue
        if is_section_enabled(effective_cfg, sid, True):
            ordered.append((sid, title))

    return ordered


def resolve_section_titles(
    effective_cfg: dict[str, Any],
    section_defs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """
    Surcharge les libellés de sections via effective.sections.titles.<section_id>.

    Ne modifie pas l'ordre : l'ordre reste géré par `resolve_sections_for_toc`.
    """
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
    """
    Politique homogène d'affichage des messages d'absence de données.

    - hide_silently: masque les placeholders
    - show_placeholder: affiche les placeholders
    """
    if not isinstance(behavior_cfg, dict):
        return False
    policy = str(behavior_cfg.get("missing_data_policy", "hide_silently")).strip().lower()
    return policy == "show_placeholder"


def normalize_dept_typography(name: str) -> str:
    """Harmonise la typographie des noms de département (apostrophe/hyphens)."""
    s = str(name or "").strip()
    s = s.replace("-d'", " d’").replace("-D'", " D’")
    s = s.replace("d'", "d’").replace("D'", "D’")
    return " ".join(s.split())


def build_title_lines_from_cfg(
    effective_cfg: dict[str, Any],
    *,
    profile_label: str,
    perimetre_name_typo: str,
    echelle: str = "departement",
) -> tuple[list[str], list[str]]:
    """Construit les lignes de titre de garde + en-tête depuis la config effective.

    Un caractère ``\\n`` présent dans ``line1`` (ou ``line2``/``line3`` en mode
    ``fixed``) provoque un retour à la ligne dans le même paragraphe sur la
    page de garde, mais est aplati en espace dans l'en-tête de page courant.
    """
    default_line1 = "Bilan des activités de police\nde l'environnement de l'OFB"

    title_cfg = effective_cfg.get("title", {}) if isinstance(effective_cfg, dict) else {}
    if not isinstance(title_cfg, dict):
        title_cfg = {}

    line1 = str(title_cfg.get("line1", default_line1)).strip() or default_line1

    line2_mode = str(title_cfg.get("line2_mode", "profile_label")).strip().lower()
    if line2_mode == "none":
        line2 = ""
    elif line2_mode == "fixed":
        line2 = str(title_cfg.get("line2_fixed", "")).strip()
    else:
        line2 = str(profile_label).strip()

    line3_mode = str(title_cfg.get("line3_mode", "department")).strip().lower()
    if line3_mode == "fixed":
        line3 = str(title_cfg.get("line3_fixed", "")).strip()
    else:
        if echelle == "departement":
            from bilans.chemins_projet import PROJECT_ROOT
            import yaml
            
            coord = "de la"
            try:
                cfg_path = PROJECT_ROOT / "config" / "departements.yaml"
                if cfg_path.exists():
                    with cfg_path.open("r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                        coord_map = data.get("coordination_departement", {})
                        dept_key = str(perimetre_name_typo).strip()
                        if dept_key in coord_map:
                            coord = coord_map[dept_key]
            except Exception:
                pass
            
            line3 = f"Département {coord} {perimetre_name_typo}"
        elif echelle == "region":
            line3 = f"Région {perimetre_name_typo}"
        else:
            line3 = f"Périmètre {perimetre_name_typo}"

    def _flatten(text: str) -> str:
        # En-tête courant: une seule ligne. Les "\n" deviennent des espaces.
        return " ".join(part.strip() for part in str(text).splitlines() if part.strip())

    def _split(text: str) -> list[str]:
        # Page de garde: chaque "\n" produit une ligne dans le même paragraphe.
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
    """Résout le sous-titre de page de garde selon la config YAML.

    Modes supportés :
    - none   : pas de sous-titre (défaut)
    - fixed  : texte fixe via `subtitle_fixed`
    """
    del nb_pve  # paramètre conservé pour compat. signature, non utilisé
    mode = str(title_page_cfg.get("subtitle_mode", "none")).strip().lower()
    if mode == "fixed":
        return str(title_page_cfg.get("subtitle_fixed", "")).strip()
    return ""

