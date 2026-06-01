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
        # Multiplicateurs matplotlib (hauteur) — section 2.1 barres / courbe ; camembert §2.2.
        "thematique_sec21_figure_scale_mult": 1.55,
        "thematique_sec22_resultats_pie_figure_scale_mult": 1.22,
        "thematique_sec22_resultats_pie_width_ratio_mult": 1.12,
        # Section 4 thématique — camembert « contrôles par type d'usager » (avant tableaux thèmes).
        # width_ratio_mult : appliqué à pie_ratio_base * 0.80 (1.0 = comportement historique).
        # figure_scale_mult : multiplicateur matplotlib dédié au seul camembert §4 activité usagers.
        "thematique_sec4_activite_pie_width_ratio_mult": 1.0,
        "thematique_sec4_activite_pie_figure_scale_mult": 1.0,
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
        "thematique_sec21_figure_scale_mult": max(
            0.5, min(2.5, float(pdf_cfg.get("thematique_sec21_figure_scale_mult", 1.55)))
        ),
        "thematique_sec22_resultats_pie_figure_scale_mult": max(
            0.5, min(2.5, float(pdf_cfg.get("thematique_sec22_resultats_pie_figure_scale_mult", 1.22)))
        ),
        "thematique_sec22_resultats_pie_width_ratio_mult": max(
            0.5, min(1.5, float(pdf_cfg.get("thematique_sec22_resultats_pie_width_ratio_mult", 1.12)))
        ),
        "thematique_sec4_activite_pie_width_ratio_mult": max(
            0.5, min(1.5, float(pdf_cfg.get("thematique_sec4_activite_pie_width_ratio_mult", 1.0)))
        ),
        "thematique_sec4_activite_pie_figure_scale_mult": max(
            0.5, min(2.0, float(pdf_cfg.get("thematique_sec4_activite_pie_figure_scale_mult", 1.0)))
        ),
        "figure_scale": max(0.7, min(1.6, float(pdf_cfg.get("figure_scale", 1.0)))),
        "legend_fontsize": max(6.0, min(12.0, float(pdf_cfg.get("legend_fontsize", 8.0)))),
        "legend_ncol_max": max(1.0, min(6.0, float(pdf_cfg.get("legend_ncol_max", 4.0)))),
    }


def clamp_uniform_pie_ratio(
    chart_ratios: dict[str, float],
    *,
    uniform_key: str,
    min_key: str,
    max_key: str,
    fallback_key: str = "pie_base",
) -> float:
    """Ratio PDF de base des camemberts, borné par min/max (global ou thématique)."""
    pie_min = float(chart_ratios.get(min_key, 0.70))
    pie_max = float(chart_ratios.get(max_key, 0.82))
    if pie_min > pie_max:
        pie_min, pie_max = pie_max, pie_min
    raw = float(chart_ratios.get(uniform_key, chart_ratios.get(fallback_key, pie_min)))
    return min(pie_max, max(pie_min, raw))


def resolve_reference_pie_display(
    chart_ratios: dict[str, float],
    pie_ratio_base: float,
) -> dict[str, float]:
    """
    Dimensions du camembert de référence (§2.2 « Résultats des contrôles », profil agrainage).

    Utilisé pour harmoniser tous les camemberts des bilans détaillés (hors brochure).
    """
    width_mult = float(
        chart_ratios.get("thematique_sec22_resultats_pie_width_ratio_mult", 1.12)
    )
    figure_mult = float(
        chart_ratios.get("thematique_sec22_resultats_pie_figure_scale_mult", 1.22)
    )
    base_fs = float(chart_ratios.get("figure_scale", 1.0))
    return {
        "width_ratio": min(0.95, float(pie_ratio_base) * width_mult),
        "figure_scale": base_fs * figure_mult,
        "legend_fontsize": float(chart_ratios.get("legend_fontsize", 8.0)),
    }
