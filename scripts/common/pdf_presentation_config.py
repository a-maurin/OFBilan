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
        root / "ref" / "pdf_presentation.yaml",
    ]
    cfg_path = next((p for p in cfg_candidates if p.exists()), None)
    if cfg_path is None:
        return deepcopy(DEFAULT_PDF_PRESENTATION_CONFIG)

    try:
        import yaml  # type: ignore[import]
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

