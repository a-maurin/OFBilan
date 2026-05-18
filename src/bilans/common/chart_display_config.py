"""Configuration centralisée d'affichage des graphiques PDF."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bilans.common.pdf_report_builder import (
    THEMATIC_CHART_WIDTH_RATIO,
    THEMATIC_PIE_CHART_WIDTH_RATIO,
)


DEFAULT_CHART_DISPLAY_CONFIG: dict[str, Any] = {
    "pdf": {
        # Ratios "socle" utilisés si aucune surcharge n'est définie.
        "pie_width_ratio_base": float(THEMATIC_PIE_CHART_WIDTH_RATIO),
        "chart_width_ratio_base": float(THEMATIC_CHART_WIDTH_RATIO),
        # Ajustements spécifiques à la section "Activité par types d'usagers".
        "activite_usagers_controles_pie_scale": 3.0,
        "activite_usagers_resultats_bar_scale": 0.70,
        # Ajustements globaux.
        "global_resultats_pie_scale": 1.0,
        "global_usagers_pie_scale": 1.0,
        "global_domaine_pie_scale": 1.0,
        "global_theme_pie_scale": 1.0,
        # Uniformisation optionnelle : base commune pour les camemberts du global.
        "global_uniform_pie_scale": 1.0,
        "global_uniform_pie_min_ratio": 0.70,
        "global_uniform_pie_max_ratio": 0.82,
        "global_type_usager_bar_scale": 1.25,
        # Uniformisation optionnelle du moteur thématique.
        "thematique_uniform_pie_scale": 1.0,
        "thematique_uniform_pie_min_ratio": 0.70,
        "thematique_uniform_pie_max_ratio": 0.82,
        "thematique_uniform_chart_scale": 1.0,
        # Taille matplotlib (avant insertion PDF) et légendes.
        "figure_scale": 1.0,
        "legend_fontsize": 8.0,
        "legend_ncol_max": 4.0,
    }
}

CHART_PRESETS: dict[str, dict[str, float]] = {
    "compact": {
        "pie_width_ratio_base": 0.30,
        "chart_width_ratio_base": 0.62,
        "activite_usagers_controles_pie_scale": 2.0,
        "activite_usagers_resultats_bar_scale": 0.55,
        "global_resultats_pie_scale": 0.90,
        "global_usagers_pie_scale": 0.90,
        "global_domaine_pie_scale": 0.90,
        "global_theme_pie_scale": 0.90,
        "global_uniform_pie_scale": 0.90,
        "global_uniform_pie_min_ratio": 0.60,
        "global_uniform_pie_max_ratio": 0.78,
        "global_type_usager_bar_scale": 1.15,
        "thematique_uniform_pie_scale": 0.90,
        "thematique_uniform_pie_min_ratio": 0.60,
        "thematique_uniform_pie_max_ratio": 0.78,
        "thematique_uniform_chart_scale": 0.90,
        "figure_scale": 0.95,
        "legend_fontsize": 7.0,
        "legend_ncol_max": 3.0,
    },
    "standard": {
        "pie_width_ratio_base": 0.34,
        "chart_width_ratio_base": 0.72,
        "activite_usagers_controles_pie_scale": 3.0,
        "activite_usagers_resultats_bar_scale": 1.20,
        "global_resultats_pie_scale": 1.00,
        "global_usagers_pie_scale": 1.00,
        "global_domaine_pie_scale": 1.00,
        "global_theme_pie_scale": 1.00,
        "global_uniform_pie_scale": 1.00,
        "global_uniform_pie_min_ratio": 0.70,
        "global_uniform_pie_max_ratio": 0.82,
        "global_type_usager_bar_scale": 1.25,
        "thematique_uniform_pie_scale": 1.00,
        "thematique_uniform_pie_min_ratio": 0.70,
        "thematique_uniform_pie_max_ratio": 0.82,
        "thematique_uniform_chart_scale": 1.00,
        "figure_scale": 1.00,
        "legend_fontsize": 8.0,
        "legend_ncol_max": 4.0,
    },
    "large": {
        "pie_width_ratio_base": 0.40,
        "chart_width_ratio_base": 0.85,
        "activite_usagers_controles_pie_scale": 3.0,
        "activite_usagers_resultats_bar_scale": 0.90,
        "global_resultats_pie_scale": 1.10,
        "global_usagers_pie_scale": 1.10,
        "global_domaine_pie_scale": 1.10,
        "global_theme_pie_scale": 1.10,
        "global_uniform_pie_scale": 1.10,
        "global_uniform_pie_min_ratio": 0.74,
        "global_uniform_pie_max_ratio": 0.90,
        "global_type_usager_bar_scale": 1.35,
        "thematique_uniform_pie_scale": 1.10,
        "thematique_uniform_pie_min_ratio": 0.74,
        "thematique_uniform_pie_max_ratio": 0.90,
        "thematique_uniform_chart_scale": 1.10,
        "figure_scale": 1.08,
        "legend_fontsize": 9.0,
        "legend_ncol_max": 4.0,
    },
}


def _clamp_ratio(value: float) -> float:
    return max(0.1, min(1.0, float(value)))


def load_chart_display_config(root: Path, preset: str | None = None) -> dict[str, Any]:
    """
    Charge la config d'affichage des graphiques depuis
    config/charts/charts_config.yaml puis, en fallback, ref/programme/charts_config.yaml.

    Si le fichier est absent (ou invalide), retourne les valeurs par défaut.
    """
    cfg = DEFAULT_CHART_DISPLAY_CONFIG.copy()
    candidates = [
        root / "config" / "charts" / "charts_config.yaml",
        root / "ref" / "programme" / "charts_config.yaml",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return cfg
    try:
        import yaml
    except ImportError:
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return cfg

    pdf_data = data.get("pdf", {}) if isinstance(data, dict) else {}
    if not isinstance(pdf_data, dict):
        return cfg

    out = dict(cfg["pdf"])
    for key in out.keys():
        if key in pdf_data:
            out[key] = pdf_data[key]
    cfg["pdf"] = out
    if preset:
        preset_key = str(preset).strip().lower()
        if preset_key in CHART_PRESETS:
            cfg["pdf"].update(CHART_PRESETS[preset_key])
    return cfg


def compute_pdf_ratios(cfg: dict[str, Any]) -> dict[str, float]:
    """Construit les ratios PDF finaux avec garde-fous."""
    pdf_cfg = cfg.get("pdf", {})
    pie_base = _clamp_ratio(pdf_cfg.get("pie_width_ratio_base", THEMATIC_PIE_CHART_WIDTH_RATIO))
    chart_base = _clamp_ratio(pdf_cfg.get("chart_width_ratio_base", THEMATIC_CHART_WIDTH_RATIO))

    return {
        "pie_base": pie_base,
        "chart_base": chart_base,
        "activite_usagers_controles_pie": _clamp_ratio(
            pie_base * float(pdf_cfg.get("activite_usagers_controles_pie_scale", 3.0))
        ),
        "activite_usagers_resultats_bar": _clamp_ratio(
            chart_base * float(pdf_cfg.get("activite_usagers_resultats_bar_scale", 0.70))
        ),
        "global_resultats_pie": _clamp_ratio(
            pie_base * float(pdf_cfg.get("global_resultats_pie_scale", 1.0))
        ),
        "global_usagers_pie": _clamp_ratio(
            pie_base * float(pdf_cfg.get("global_usagers_pie_scale", 1.0))
        ),
        "global_domaine_pie": _clamp_ratio(
            pie_base * float(pdf_cfg.get("global_domaine_pie_scale", 1.0))
        ),
        "global_theme_pie": _clamp_ratio(
            pie_base * float(pdf_cfg.get("global_theme_pie_scale", 1.0))
        ),
        "global_uniform_pie": _clamp_ratio(
            pie_base * float(pdf_cfg.get("global_uniform_pie_scale", 1.0))
        ),
        "global_uniform_pie_min_ratio": _clamp_ratio(
            float(pdf_cfg.get("global_uniform_pie_min_ratio", 0.70))
        ),
        "global_uniform_pie_max_ratio": _clamp_ratio(
            float(pdf_cfg.get("global_uniform_pie_max_ratio", 0.82))
        ),
        "global_type_usager_bar_ratio": _clamp_ratio(
            chart_base * float(pdf_cfg.get("global_type_usager_bar_scale", 1.25))
        ),
        "thematique_uniform_pie": _clamp_ratio(
            pie_base * float(pdf_cfg.get("thematique_uniform_pie_scale", 1.0))
        ),
        "thematique_uniform_pie_min_ratio": _clamp_ratio(
            float(pdf_cfg.get("thematique_uniform_pie_min_ratio", 0.70))
        ),
        "thematique_uniform_pie_max_ratio": _clamp_ratio(
            float(pdf_cfg.get("thematique_uniform_pie_max_ratio", 0.82))
        ),
        "thematique_uniform_chart": _clamp_ratio(
            chart_base * float(pdf_cfg.get("thematique_uniform_chart_scale", 1.0))
        ),
        "figure_scale": max(0.7, min(1.6, float(pdf_cfg.get("figure_scale", 1.0)))),
        "legend_fontsize": max(6.0, min(12.0, float(pdf_cfg.get("legend_fontsize", 8.0)))),
        "legend_ncol_max": max(1.0, min(6.0, float(pdf_cfg.get("legend_ncol_max", 4.0)))),
    }
