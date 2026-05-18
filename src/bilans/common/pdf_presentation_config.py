"""Chargement/fusion de la configuration de présentation PDF (YAML)."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_PDF_PRESENTATION_CONFIG: dict[str, Any] = {
    "version": 1,
    "behavior": {
        "missing_data_policy": "hide_silently",  # hide_silently | show_placeholder
        "unknown_block_policy": "ignore",  # ignore | warn
    },
    "defaults": {
        "title": {
            "model": "three_lines",
            "line1": "Bilan des activites de police administrative et judiciaire",
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
        },
        "sections": {
            "order": ["sec1", "sec2", "sec3", "sec4", "sec5", "sec6"],
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
            "pa_pj_distinction_paragraph": (
                "Il convient de distinguer l'activité de police administrative et l'activité de "
                "police judiciaire. Dans ce document, le terme « contrôle » renvoie exclusivement "
                "à la police administrative. Le sigle « PEJ » (procédure d'enquête judiciaire) "
                "désigne l'activité de police judiciaire, qui ne se limite pas aux infractions "
                "relevées lors des contrôles et peut aussi inclure des saisines extérieures "
                "(infractions constatées hors opération de contrôle au titre de la police "
                "administrative, instruction parquet, signalements, plaintes, etc.)."
            ),
            "multi_usager_paragraph": (
                "Lorsque des tableaux ou graphiques affichent des « effectifs » par type "
                "d'usager, chaque usager renseigné sur une fiche est compté (contrôles "
                "multi-usagers : plusieurs effectifs pour une même localisation). Les totaux "
                "d'effectifs peuvent alors dépasser le nombre de localisations de contrôle. "
                "Les colonnes ou indicateurs PEJ, PA et PVe correspondent à des nombres de "
                "procédures (dossiers), et non à des localisations de contrôle ; ils sont "
                "signalés comme tels dans les légendes des tableaux concernés."
            ),
        },
        "sec6_methodology": {
            "line_period": "<b>Période d'analyse :</b> {period_str}.",
            "line_scope": "<b>Périmètre :</b> département {dept_name} ({dept_code}).",
            "line_profile": "<b>Profil :</b> {profile_label}.",
            "line_sources": "<b>Sources :</b> {sources_text}.",
            "line_ventilation": (
                "<b>Ventilation temporelle :</b> {ventilation_mode} "
                "(seuil {ventilation_threshold_days} jours en mode auto)."
            ),
            "line_filters": "Aucun filtre sur domaine ou thème ; tous NATINF pour PEJ et PVe.",
            "line_types_usagers": (
                "<b>Types d’usagers :</b> issus du champ OSCEAN <i>type_usager</i> des points de contrôle ; "
                "catégorie « dominante » par contrôle via ref/programme/tables_reference/types_usagers.csv."
            ),
            "zone_line_pnf_only": (
                "<b>Analyse par zones :</b> bilan restreint au périmètre du PNF ; "
                "la lecture spatiale distingue le coeur de parc de l'aire d'adhésion hors coeur de parc."
            ),
            "zone_line_pnf_and_tub": (
                "<b>Analyse par zones :</b> la zone « Département » inclut l'ensemble des contrôles, "
                "puis les zones PNF et TUB sont détaillées séparément."
            ),
            "zone_line_pnf_only_department": (
                "<b>Analyse par zones :</b> la zone « Département » inclut l'ensemble des contrôles, "
                "puis la zone PNF est détaillée séparément."
            ),
            "zone_line_tub_only": (
                "<b>Analyse par zones :</b> la zone « Département » inclut l'ensemble des contrôles, "
                "puis la zone TUB est détaillée séparément."
            ),
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
            },
            "usagers_x_domaine": {
                # Nombre maximal de colonnes « domaine » affichées (tri décroissant sur le volume).
                # null ou <= 0 : pas de limite sur les colonnes.
                "max_domain_columns": 14,
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

    return {
        "version": raw.get("version", 1),
        "behavior": raw.get("behavior", {}),
        "feature_registry": raw.get("feature_registry", {}),
        "effective": effective,
    }


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
    val = enabled.get(section_id, default)
    return bool(val)


def is_block_enabled(
    effective_cfg: dict[str, Any],
    block_id: str,
    default: bool = True,
) -> bool:
    """Vrai si le bloc est activé dans effective.blocks (supporte les clés imbriquées via '.')."""
    blocks = effective_cfg.get("blocks", {})
    if not isinstance(blocks, dict):
        return default
    node: Any = blocks
    for part in str(block_id).split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    val = node
    return bool(val)


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
    order_ids = [str(x).strip() for x in order if str(x).strip()]

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
        custom = titles_cfg.get(sid, default_title)
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
    dept_name_typo: str,
) -> tuple[list[str], list[str]]:
    """Construit les lignes de titre de garde + en-tête depuis la config effective.

    Un caractère ``\\n`` présent dans ``line1`` (ou ``line2``/``line3`` en mode
    ``fixed``) provoque un retour à la ligne dans le même paragraphe sur la
    page de garde, mais est aplati en espace dans l'en-tête de page courant.
    """
    default_line1 = "Bilan des activités de police administrative et judiciaire"

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
        line3 = f"Département de la {dept_name_typo}"

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

