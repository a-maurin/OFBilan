"""Sections PDF partagées entre profils global et thématiques."""

from __future__ import annotations

from pathlib import Path

from bilans.common.pdf_presentation_config import (
    resolve_cover_subtitle,
    resolve_notice_methodology_config,
    resolve_sec6_methodology_config,
    resolve_title_page_config,
)

def add_standard_notice_methodology(
    builder,
    *,
    period_sentence: str,
    effective_cfg: dict | None = None,
) -> None:
    """
    Ajoute une notice méthodologique standardisée.

    `period_sentence` doit être déjà formatée, par ex:
    - "Pour ce bilan, les extractions portent sur la période du 01/01/2025 au 05/02/2026."
    - "Pour ce bilan, les extractions portent sur la période du 01/01/2025 au 05/02/2026."
    """
    notice_cfg = resolve_notice_methodology_config(effective_cfg or {})
    title = str(notice_cfg.get("title", "Notice méthodologique")).strip() or "Notice méthodologique"
    data_source = str(notice_cfg.get("data_source_paragraph", "")).strip()
    unit_measure = str(notice_cfg.get("unit_measure_paragraph", "")).strip()
    pa_pj = str(notice_cfg.get("pa_pj_distinction_paragraph", "")).strip()
    multi_usager = str(notice_cfg.get("multi_usager_paragraph", "")).strip()

    builder.add_section("notice_methodo", title)
    if data_source:
        builder.add_paragraph(data_source)
    builder.add_paragraph(period_sentence)
    if unit_measure:
        builder.add_paragraph(unit_measure)
    if pa_pj:
        builder.add_paragraph(pa_pj)
    if multi_usager:
        builder.add_paragraph(multi_usager)
    builder.add_page_break()


def add_standard_cover_and_toc(
    builder,
    *,
    project_root: Path,
    scope: str,
    cover_title_lines: list[str],
    period_str: str,
    sections_toc: list[tuple[str, str]],
    nb_pve: int = 0,
    profile_id: str | None = None,
) -> dict:
    """
    Ajoute une page de garde standardisée suivie du sommaire.

    Retourne la configuration effective de page de garde utilisée.
    """
    title_page_cfg = resolve_title_page_config(
        project_root,
        scope=scope,
        profile_id=profile_id,
    )
    cover_subtitle = resolve_cover_subtitle(title_page_cfg, nb_pve=nb_pve)
    builder.add_title_page(
        title_lines=cover_title_lines,
        period_str=period_str,
        subtitle=cover_subtitle,
        title_page_config=title_page_cfg,
    )
    builder.add_toc(sections_toc)
    return title_page_cfg


def build_sec6_methodology_html(
    *,
    effective_cfg: dict | None = None,
    period_str: str,
    dept_name: str,
    dept_code: str,
    profile_label: str,
    sources_text: str,
    ventilation_mode: str | None = None,
    ventilation_threshold_days: int | None = None,
    include_filters_line: bool = False,
    include_types_usagers_line: bool = False,
    has_pnf: bool = False,
    has_tub: bool = False,
    is_pnf_profile: bool = False,
) -> str:
    """
    Construit le HTML de méthodologie sec6 à partir de la config YAML.
    """
    cfg = resolve_sec6_methodology_config(effective_cfg or {})
    fmt = {
        "period_str": period_str,
        "dept_name": dept_name,
        "dept_code": dept_code,
        "profile_label": profile_label,
        "sources_text": sources_text,
        "ventilation_mode": ventilation_mode or "",
        "ventilation_threshold_days": str(ventilation_threshold_days or ""),
    }

    def _line(key: str) -> str:
        raw = str(cfg.get(key, "")).strip()
        if not raw:
            return ""
        try:
            return raw.format(**fmt).strip()
        except Exception:
            return raw

    lines: list[str] = []
    for key in ("line_period", "line_scope", "line_profile", "line_sources"):
        ln = _line(key)
        if ln:
            lines.append(ln)

    if ventilation_mode:
        ln = _line("line_ventilation")
        if ln:
            lines.append(ln)
    if include_filters_line:
        ln = _line("line_filters")
        if ln:
            lines.append(ln)
    if include_types_usagers_line:
        ln = _line("line_types_usagers")
        if ln:
            lines.append(ln)

    zone_key = ""
    if is_pnf_profile and has_pnf:
        zone_key = "zone_line_pnf_only"
    elif has_pnf and has_tub:
        zone_key = "zone_line_pnf_and_tub"
    elif has_pnf:
        zone_key = "zone_line_pnf_only_department"
    elif has_tub:
        zone_key = "zone_line_tub_only"
    if zone_key:
        ln = _line(zone_key)
        if ln:
            lines.append(ln)

    return "<br/>".join(lines) + ("<br/>" if lines else "")


def build_filtered_glossary_rows(
    *,
    gloss_cfg: dict,
    nb_ctrl: int,
    nb_pej: int,
    nb_pa: int,
    nb_pve: int,
    include_pnf: bool = False,
    include_tub: bool = False,
) -> list[list[str]]:
    """
    Construit les lignes du glossaire filtrées selon le contenu réel du bilan.
    """
    header_cfg = gloss_cfg.get("header", {}) if isinstance(gloss_cfg, dict) else {}
    abbr_list = gloss_cfg.get("abbreviations", []) if isinstance(gloss_cfg, dict) else []
    if not isinstance(header_cfg, dict):
        header_cfg = {}
    if not isinstance(abbr_list, list):
        abbr_list = []

    abbr_by_id: dict[str, dict] = {}
    for item in abbr_list:
        if not isinstance(item, dict):
            continue
        id_ = str(item.get("id", "")).strip()
        if id_:
            abbr_by_id[id_] = item

    used_ids: list[str] = []

    def _add_if_available(abbr_id: str, condition: bool) -> None:
        if condition and abbr_id in abbr_by_id and abbr_id not in used_ids:
            used_ids.append(abbr_id)

    _add_if_available("OSCEAN", True)
    _add_if_available("DC", nb_ctrl > 0)
    _add_if_available("NATINF", nb_pve > 0 or nb_pej > 0)
    _add_if_available("PA", nb_pa > 0)
    _add_if_available("PEJ", nb_pej > 0)
    _add_if_available("PVe", nb_pve > 0)
    _add_if_available("PNF", include_pnf)
    _add_if_available("TUB", include_tub)

    if not used_ids:
        return []

    rows: list[list[str]] = [
        [
            str(header_cfg.get("abbr_label", "Abréviation")),
            str(header_cfg.get("definition_label", "Signification")),
        ]
    ]
    for abbr_id in used_ids:
        item = abbr_by_id[abbr_id]
        rows.append([str(item.get("label", abbr_id)), str(item.get("definition", ""))])
    return rows


def load_glossary_config(root: Path) -> dict:
    """
    Charge la configuration du glossaire (config puis fallback ref).

    Retourne un défaut robuste si le YAML est absent ou invalide.
    """
    cfg_candidates = [
        root / "config" / "presentation" / "glossaire.yaml",
        root / "ref" / "glossaire.yaml",
    ]
    cfg_path = next((p for p in cfg_candidates if p.exists()), None)
    default_cfg: dict = {
        "header": {
            "abbr_label": "Abréviation",
            "definition_label": "Signification",
        },
        "abbreviations": [
            {"id": "DC", "label": "DC", "definition": "Dossier de contrôle"},
            {"id": "NATINF", "label": "NATINF", "definition": "Nature d'infraction (nomenclature nationale)"},
            {"id": "OSCEAN", "label": "OSCEAN", "definition": "Outil de suivi des contrôles en environnement"},
            {"id": "PA", "label": "PA", "definition": "Procédure administrative"},
            {"id": "PEJ", "label": "PEJ", "definition": "Procédure d'enquête judiciaire"},
            {"id": "PNF", "label": "PNF", "definition": "Parc national de forêts"},
            {"id": "PVe", "label": "PVe", "definition": "Procès-verbal électronique"},
            {"id": "TUB", "label": "TUB", "definition": "Zone tuberculose bovine"},
        ],
    }
    if cfg_path is None:
        return default_cfg
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        return default_cfg
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return default_cfg
    if not isinstance(data, dict):
        return default_cfg
    header = data.get("header", {})
    abbrs = data.get("abbreviations", [])
    if not isinstance(header, dict) or not isinstance(abbrs, list):
        return default_cfg
    result = {
        "header": {
            "abbr_label": str(header.get("abbr_label", "Abréviation")) or "Abréviation",
            "definition_label": str(header.get("definition_label", "Signification")) or "Signification",
        },
        "abbreviations": [],
    }
    for item in abbrs:
        if not isinstance(item, dict):
            continue
        id_ = str(item.get("id", "")).strip()
        if not id_:
            continue
        label = str(item.get("label", id_)).strip() or id_
        definition = str(item.get("definition", "")).strip()
        if not definition:
            continue
        result["abbreviations"].append({"id": id_, "label": label, "definition": definition})
    return result if result["abbreviations"] else default_cfg
