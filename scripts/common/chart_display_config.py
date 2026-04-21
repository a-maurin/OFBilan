"""Configuration centralisée d'affichage des graphiques PDF."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.common.pdf_report_builder import (
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
    },
    "standard": {
        "pie_width_ratio_base": 0.34,
        "chart_width_ratio_base": 0.72,
        "activite_usagers_controles_pie_scale": 3.0,
        "activite_usagers_resultats_bar_scale": 1.20,
        "global_resultats_pie_scale": 1.00,
        "global_usagers_pie_scale": 1.00,
    },
    "large": {
        "pie_width_ratio_base": 0.40,
        "chart_width_ratio_base": 0.85,
        "activite_usagers_controles_pie_scale": 3.0,
        "activite_usagers_resultats_bar_scale": 0.90,
        "global_resultats_pie_scale": 1.10,
        "global_usagers_pie_scale": 1.10,
    },
}


def _clamp_ratio(value: float) -> float:
    return max(0.1, min(1.0, float(value)))


def load_chart_display_config(root: Path, preset: str | None = None) -> dict[str, Any]:
    """
    Charge la config d'affichage des graphiques depuis ref/charts_config.yaml.

    Si le fichier est absent (ou invalide), retourne les valeurs par défaut.
    """
    cfg = DEFAULT_CHART_DISPLAY_CONFIG.copy()
    path = root / "ref" / "charts_config.yaml"
    if not path.exists():
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
    }
