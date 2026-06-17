"""Sections PDF partagées entre profils global et thématiques."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ofbilan.common.pdf_presentation_config import (
    DEFAULT_PDF_PRESENTATION_CONFIG,
    is_block_enabled,
    is_section_enabled,
    normalize_diffusion,
    resolve_cover_subtitle,
    resolve_notice_methodology_config,
    resolve_sec6_methodology_config,
    resolve_title_page_config,
)
from ofbilan.common.pdf_table_sort import pdf_metric_caption

_VENTILATION_READER_LABELS: dict[str, str] = {
    "hebdomadaire": "indicateurs regroupés par semaine",
    "mensuelle": "indicateurs regroupés par mois",
    "trimestrielle": "indicateurs regroupés par trimestre",
    "annuelle": "indicateurs regroupés par année",
    "globale": "vue d'ensemble sur toute la période, sans découpage dans le temps",
}


def add_standard_notice_methodology(
    builder,
    *,
    period_sentence: str,
    effective_cfg: dict | None = None,
    diffusion: str | None = "interne",
) -> None:
    """
    Ajoute une notice méthodologique standardisée (début du PDF, avant le sommaire).

    N'affecte pas la mention « diffusion restreinte » sur la page de garde, gérée
    séparément par ``PDFReportBuilder`` lorsque ``--diffusion interne``.

    `period_sentence` doit être déjà formatée, par ex:
    - "Pour ce bilan, les extractions portent sur la période du 01/01/2025 au 05/02/2026."
    """
    notice_cfg = resolve_notice_methodology_config(effective_cfg or {})
    title = str(notice_cfg.get("title", "Notice méthodologique")).strip() or "Notice méthodologique"
    data_source = str(notice_cfg.get("data_source_paragraph", "")).strip()
    unit_measure = str(notice_cfg.get("unit_measure_paragraph", "")).strip()
    control_op = str(notice_cfg.get("control_operation_paragraph", "")).strip()
    pa_pj = str(notice_cfg.get("pa_pj_distinction_paragraph", "")).strip()
    multi_usager = str(notice_cfg.get("multi_usager_paragraph", "")).strip()

    builder.add_section("notice_methodo", title)
    if data_source:
        builder.add_paragraph(data_source)
    builder.add_paragraph(period_sentence)
    if unit_measure:
        builder.add_paragraph(unit_measure)
    if control_op:
        builder.add_paragraph(control_op)
    if pa_pj:
        builder.add_callout_box(
            pa_pj,
            title="Contrôle : définition et suites possibles",
        )
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


def _sources_phrase_for_methodology(
    *,
    source_point_ctrl: bool,
    source_pej: bool,
    source_pa: bool,
    source_pve: bool,
) -> str:
    labels: list[str] = []
    if source_point_ctrl:
        labels.append("contrôles (OSCEAN)")
    if source_pej:
        labels.append("PEJ")
    if source_pa:
        labels.append("PA")
    if source_pve:
        labels.append("PVe")
    if not labels:
        return "activités suivies dans les outils de suivi de l'OFB"
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} et {labels[1]}"
    return ", ".join(labels[:-1]) + f" et {labels[-1]}"


def _resolve_zone_mode(
    *,
    has_pnf: bool,
    has_tub: bool,
    is_pnf_profile: bool,
) -> str:
    if is_pnf_profile and has_pnf:
        return "pnf_only"
    if has_pnf and has_tub:
        return "pnf_and_tub"
    if has_pnf:
        return "pnf_dept"
    if has_tub:
        return "tub_only"
    return "none"


def build_sec6_methodology_context(
    *,
    period_str: str,
    perimetre_name: str,
    perimetre_code: str,
    profile_label: str = "",
    profile_id: str = "",
    diffusion: str | None = "interne",
    nb_localisations: int = 0,
    nb_pej: int = 0,
    nb_pa: int = 0,
    nb_pve: int = 0,
    source_point_ctrl: bool = True,
    source_pej: bool = True,
    source_pa: bool = True,
    source_pve: bool = True,
    ventilation_mode: str | None = None,
    has_pnf: bool = False,
    has_tub: bool = False,
    is_pnf_profile: bool = False,
    show_usagers: bool = False,
) -> dict[str, Any]:
    """Contexte de formatage pour les paragraphes YAML de la méthodologie d'annexe."""
    diffusion_norm = normalize_diffusion(diffusion)
    zone_mode = _resolve_zone_mode(
        has_pnf=has_pnf,
        has_tub=has_tub,
        is_pnf_profile=is_pnf_profile,
    )
    vent_key = str(ventilation_mode or "").strip().lower()
    ventilation_label = _VENTILATION_READER_LABELS.get(vent_key, "") if vent_key else ""

    return {
        "period_str": period_str,
        "dept_name": perimetre_name,
        "dept_code": str(perimetre_code),
        "profile_label": str(profile_label or "").strip(),
        "profile_id": str(profile_id or "").strip(),
        "sources_phrase": _sources_phrase_for_methodology(
            source_point_ctrl=source_point_ctrl,
            source_pej=source_pej,
            source_pa=source_pa,
            source_pve=source_pve,
        ),
        "diffusion": diffusion_norm,
        "nb_localisations": int(nb_localisations or 0),
        "nb_pej": int(nb_pej or 0),
        "nb_pa": int(nb_pa or 0),
        "nb_pve": int(nb_pve or 0),
        "ventilation_label": ventilation_label,
        "zone_mode": zone_mode,
        "show_usagers": bool(show_usagers),
        "has_profile": bool(str(profile_label or "").strip()),
        "has_controls": int(nb_localisations or 0) > 0,
        "has_pej": int(nb_pej or 0) > 0,
        "has_pa": int(nb_pa or 0) > 0,
        "has_pve": int(nb_pve or 0) > 0,
        "has_procedures": int(nb_pej or 0) + int(nb_pa or 0) + int(nb_pve or 0) > 0,
        "has_ventilation": bool(ventilation_label),
        "diffusion_externe": diffusion_norm == "externe",
        "diffusion_interne": diffusion_norm == "interne",
        "zone_pnf_only": zone_mode == "pnf_only",
        "zone_pnf_and_tub": zone_mode == "pnf_and_tub",
        "zone_pnf_dept": zone_mode == "pnf_dept",
        "zone_tub_only": zone_mode == "tub_only",
    }


def _sec6_item_matches(when: str, ctx: dict[str, Any]) -> bool:
    key = str(when or "always").strip().lower()
    if not key or key == "always":
        return True
    return bool(ctx.get(key))


def _format_sec6_item_text(template: str, ctx: dict[str, Any]) -> str:
    raw = str(template or "").strip()
    if not raw:
        return ""
    try:
        return raw.format(**ctx).strip()
    except Exception:
        return raw


def _sec6_methodology_items_from_cfg(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    items = cfg.get("items")
    if isinstance(items, list) and items:
        return [x for x in items if isinstance(x, dict)]

    # Rétrocompatibilité : anciennes clés line_* → items synthétiques.
    legacy_map = (
        ("line_period", "always"),
        ("line_scope", "always"),
        ("line_profile", "has_profile"),
        ("line_sources", "always"),
        ("line_ventilation", "has_ventilation"),
        ("line_filters", "always"),
        ("line_types_usagers", "show_usagers"),
        ("zone_line_pnf_only", "zone_pnf_only"),
        ("zone_line_pnf_and_tub", "zone_pnf_and_tub"),
        ("zone_line_pnf_only_department", "zone_pnf_dept"),
        ("zone_line_tub_only", "zone_tub_only"),
    )
    out: list[dict[str, Any]] = []
    for key, when in legacy_map:
        text = str(cfg.get(key, "")).strip()
        if text:
            out.append({"when": when, "text": text})
    if out:
        return out
    default_items = (
        (DEFAULT_PDF_PRESENTATION_CONFIG.get("defaults") or {}).get("sec6_methodology") or {}
    ).get("items", [])
    if isinstance(default_items, list):
        return [x for x in default_items if isinstance(x, dict)]
    return []


def build_sec6_methodology_html(
    *,
    effective_cfg: dict | None = None,
    context: dict[str, Any] | None = None,
    period_str: str = "",
    perimetre_name: str = "",
    perimetre_code: str = "",
    profile_label: str = "",
    sources_text: str = "",
    ventilation_mode: str | None = None,
    ventilation_threshold_days: int | None = None,
    include_filters_line: bool = False,
    include_types_usagers_line: bool = False,
    has_pnf: bool = False,
    has_tub: bool = False,
    is_pnf_profile: bool = False,
    diffusion: str | None = "interne",
    nb_localisations: int = 0,
    nb_pej: int = 0,
    nb_pa: int = 0,
    nb_pve: int = 0,
    source_point_ctrl: bool = True,
    source_pej: bool = True,
    source_pa: bool = True,
    source_pve: bool = True,
    profile_id: str = "",
    show_usagers: bool = False,
) -> str:
    """
    Construit le HTML de la méthodologie d'annexe (section 6) à partir du YAML.

    Les paragraphes sont listés dans ``sec6_methodology.items`` avec une condition
    ``when`` évaluée sur le contenu réel du bilan (volumes, sources, zones, diffusion).
    """
    if context is None:
        ctx = build_sec6_methodology_context(
            period_str=period_str,
            perimetre_name=perimetre_name,
            perimetre_code=perimetre_code,
            profile_label=profile_label,
            profile_id=profile_id,
            diffusion=diffusion,
            nb_localisations=nb_localisations,
            nb_pej=nb_pej,
            nb_pa=nb_pa,
            nb_pve=nb_pve,
            source_point_ctrl=source_point_ctrl,
            source_pej=source_pej,
            source_pa=source_pa,
            source_pve=source_pve,
            ventilation_mode=ventilation_mode,
            has_pnf=has_pnf,
            has_tub=has_tub,
            is_pnf_profile=is_pnf_profile,
            show_usagers=show_usagers or include_types_usagers_line,
        )
    else:
        ctx = dict(context)

    if sources_text and not ctx.get("sources_phrase"):
        ctx["sources_phrase"] = sources_text

    cfg = resolve_sec6_methodology_config(effective_cfg or {})
    items = _sec6_methodology_items_from_cfg(cfg)

    lines: list[str] = []
    for item in items:
        when = str(item.get("when", "always"))
        if not _sec6_item_matches(when, ctx):
            continue
        text = _format_sec6_item_text(str(item.get("text", "")), ctx)
        if text:
            lines.append(text)

    return "<br/>".join(lines) + ("<br/>" if lines else "")


def build_filtered_glossary_rows(
    *,
    gloss_cfg: dict,
    nb_localisations: int,
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
    _add_if_available("DC", nb_localisations > 0)
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
        root / "ref" / "programme" / "glossaire.yaml",
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
        import yaml  # type: ignore[import-untyped]
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


def summarize_procedures_par_type_usager(
    proc_par_domaine: Any,
) -> Any:
    """Agrège PEJ/PA par type d'usager à partir d'un tableau domaine×usager."""
    import pandas as pd

    if proc_par_domaine is None or getattr(proc_par_domaine, "empty", True):
        return pd.DataFrame(columns=["type_usager", "nb_pej", "nb_pa"])
    if "type_usager" not in proc_par_domaine.columns:
        return pd.DataFrame(columns=["type_usager", "nb_pej", "nb_pa"])
    metrics = [c for c in ("nb_pej", "nb_pa") if c in proc_par_domaine.columns]
    if not metrics:
        return pd.DataFrame(columns=["type_usager", "nb_pej", "nb_pa"])
    out = proc_par_domaine.groupby("type_usager", as_index=False)[metrics].sum()
    if metrics:
        out["_sort"] = out[metrics].fillna(0).sum(axis=1)
        out = out.sort_values("_sort", ascending=False, kind="stable").drop(columns=["_sort"])
    return out.reset_index(drop=True)


def add_procedures_par_type_usager_subsection(
    builder: Any,
    summary: Any,
    *,
    avail_w: float,
    presentation_cfg: dict[str, Any] | None,
    section_title: dict[str, str] | None = None,
) -> None:
    """Sous-parties PEJ/PA ventilées par type d'usager (section Activité par type d'usager)."""
    import pandas as pd

    cfg = presentation_cfg if isinstance(presentation_cfg, dict) else {}
    titles = section_title if isinstance(section_title, dict) else {}
    if summary is None or getattr(summary, "empty", True):
        return
    if not isinstance(summary, pd.DataFrame):
        return

    show_pej = is_block_enabled(cfg, "sec4.show_table_pej_par_type_usager", True)
    show_pa = is_block_enabled(cfg, "sec4.show_table_pa_par_type_usager", True)
    if not show_pej and not show_pa:
        return

    if (
        show_pej
        and is_section_enabled(cfg, "sec43", True)
        and "nb_pej" in summary.columns
        and int(summary["nb_pej"].fillna(0).sum()) > 0
    ):
        tbl = [["Type d'usager", "Nombre PEJ"]]
        for _, row in summary.iterrows():
            nb = int(row.get("nb_pej", 0) or 0)
            if nb <= 0:
                continue
            tbl.append([str(row["type_usager"]), str(nb)])
        if len(tbl) > 1:
            builder.add_section(
                "sec43",
                titles.get(
                    "sec43",
                    "3.3. Procédures d'enquête judiciaire (PEJ) par type d'usager",
                ),
                level=2,
                toc_level=1,
            )
            builder.add_table(
                tbl,
                caption=pdf_metric_caption("PEJ par type d'usager", "proc"),
                col_widths=[avail_w * 0.62, avail_w * 0.38],
                col_aligns=["LEFT", "RIGHT"],
                keep_together=True,
                spacer_after_mm=1.0,
            )

    if (
        show_pa
        and is_section_enabled(cfg, "sec44", True)
        and "nb_pa" in summary.columns
        and int(summary["nb_pa"].fillna(0).sum()) > 0
    ):
        tbl = [["Type d'usager", "Nombre PA"]]
        for _, row in summary.iterrows():
            nb = int(row.get("nb_pa", 0) or 0)
            if nb <= 0:
                continue
            tbl.append([str(row["type_usager"]), str(nb)])
        if len(tbl) > 1:
            builder.add_section(
                "sec44",
                titles.get(
                    "sec44",
                    "3.4. Procédures administratives (PA) par type d'usager",
                ),
                level=2,
                toc_level=1,
            )
            builder.add_table(
                tbl,
                caption=pdf_metric_caption("PA par type d'usager", "proc"),
                col_widths=[avail_w * 0.62, avail_w * 0.38],
                col_aligns=["LEFT", "RIGHT"],
                keep_together=True,
                spacer_after_mm=1.0,
            )
