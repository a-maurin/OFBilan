"""Tests configuration d'affichage des graphiques PDF (ratios, garde-fous)."""

from __future__ import annotations

from bilans.common.chart_display_config import (
    DEFAULT_CHART_DISPLAY_CONFIG,
    compute_pdf_ratios,
)


def test_compute_pdf_ratios_sec4_activite_defaults() -> None:
    ratios = compute_pdf_ratios(DEFAULT_CHART_DISPLAY_CONFIG)
    assert ratios["thematique_sec4_activite_pie_width_ratio_mult"] == 1.0
    assert ratios["thematique_sec4_activite_pie_figure_scale_mult"] == 1.0


def test_compute_pdf_ratios_sec4_activite_clamped() -> None:
    cfg = {
        "pdf": {
            "thematique_sec4_activite_pie_width_ratio_mult": 99.0,
            "thematique_sec4_activite_pie_figure_scale_mult": -1.0,
        }
    }
    ratios = compute_pdf_ratios(cfg)
    assert ratios["thematique_sec4_activite_pie_width_ratio_mult"] == 1.5
    assert ratios["thematique_sec4_activite_pie_figure_scale_mult"] == 0.5
