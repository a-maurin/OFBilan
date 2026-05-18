"""Mise en page de deux cartes sur une même page PDF."""

from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from bilans.common.ofb_charte import MARGIN_BOTTOM, MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP
from bilans.common.pdf_report_builder import compute_stacked_maps_width


def test_stacked_maps_width_reduced_when_too_tall() -> None:
    avail_w = A4[0] - MARGIN_LEFT - MARGIN_RIGHT
    frame_h = A4[1] - MARGIN_TOP - MARGIN_BOTTOM
    # Deux cartes portrait (ratio > 1) : à pleine largeur elles dépasseraient la page.
    ratios = [1.3, 1.3]
    map_w = compute_stacked_maps_width(avail_w, frame_h, ratios)
    assert map_w < avail_w * 0.98
    total_h = map_w * sum(ratios) + 2 * mm
    assert total_h <= frame_h - 28 * mm
