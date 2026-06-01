"""Tests configuration d'affichage des graphiques PDF (ratios, garde-fous)."""

from __future__ import annotations

from bilans.chemins_projet import PROJECT_ROOT
from bilans.common.chart_display_config import (
    DEFAULT_CHART_DISPLAY_CONFIG,
    clamp_uniform_pie_ratio,
    compute_pdf_ratios,
    load_chart_display_config,
    resolve_reference_pie_display,
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


def test_resolve_reference_pie_display_matches_sec22_agrainage_formula() -> None:
    ratios = compute_pdf_ratios(load_chart_display_config(PROJECT_ROOT))
    pie_base = clamp_uniform_pie_ratio(
        ratios,
        uniform_key="thematique_uniform_pie",
        min_key="thematique_uniform_pie_min_ratio",
        max_key="thematique_uniform_pie_max_ratio",
    )
    disp = resolve_reference_pie_display(ratios, pie_base)
    width_mult = ratios["thematique_sec22_resultats_pie_width_ratio_mult"]
    figure_mult = ratios["thematique_sec22_resultats_pie_figure_scale_mult"]
    assert disp["width_ratio"] == min(0.95, pie_base * width_mult)
    assert disp["figure_scale"] == ratios["figure_scale"] * figure_mult
    assert disp["legend_fontsize"] >= 9.0
