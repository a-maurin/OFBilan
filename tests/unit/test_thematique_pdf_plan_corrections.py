"""Non-régression : correctifs PDF thématiques (config graphiques, zone PVe, couleurs)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from matplotlib.axes import Axes

from core.chemins_projet import PROJECT_ROOT
from core.common.chart_display_config import compute_pdf_ratios, load_chart_display_config
from core.common.ofb_charte import COLOR_CHART_AUTRE_RESULTAT


def test_compute_pdf_ratios_includes_thematique_sec21_sec22_mults() -> None:
    cfg = load_chart_display_config(PROJECT_ROOT, preset=None)
    ratios = compute_pdf_ratios(cfg)
    assert "thematique_sec21_figure_scale_mult" in ratios
    assert "thematique_sec22_resultats_pie_figure_scale_mult" in ratios
    assert "thematique_sec22_resultats_pie_width_ratio_mult" in ratios
    assert "thematique_sec4_activite_pie_width_ratio_mult" in ratios
    assert "thematique_sec4_activite_pie_figure_scale_mult" in ratios
    assert 0.5 <= ratios["thematique_sec21_figure_scale_mult"] <= 2.5


def test_zone_pve_departement_nb_ensemble_hors_tub_et_pnf() -> None:
    """Aligné sur orchestrateur : nb « Département » = lignes ni TUB ni PNF (union, pas soustraction)."""
    tub_codes = {"01001", "01002"}
    pnf_codes = {"01002", "01003"}  # 01002 = chevauchement TUB ∩ PNF
    df = pd.DataFrame(
        {
            "INF-INSEE": [
                "01001",  # TUB seul
                "01003",  # PNF seul
                "01002",  # TUB et PNF
                "99999",  # hors les deux
                "01004",  # hors les deux
            ]
        }
    )
    col = "INF-INSEE"
    insee = df[col].astype(str).str.zfill(5)
    in_tub = insee.isin(tub_codes)
    in_pnf = insee.isin(pnf_codes)
    nb_hors_tub_pnf = int((~in_tub & ~in_pnf).sum())
    assert nb_hors_tub_pnf == 2  # 99999, 01004
    # Soustraction stricte sur les totaux par zone ferait 5 - 2 - 2 = 1 (faux).
    assert len(df) - int(in_tub.sum()) - int(in_pnf.sum()) == 1


def test_chart_bar_horizontal_stacked_en_attente_color(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """La série « En attente » doit utiliser le gris foncé charte (avant heuristique infraction)."""
    from core.common import rendus_graphiques as rg

    barh_colors: list = []
    orig_barh = Axes.barh

    def wrapped_barh(self, y, width, height=0.8, left=None, **kwargs):
        barh_colors.append(kwargs.get("color"))
        return orig_barh(self, y, width, height=height, left=left, **kwargs)

    monkeypatch.setattr(Axes, "barh", wrapped_barh)
    rg.chart_bar_horizontal_stacked(
        ["Usager A"],
        {"En attente": [4], "Conformes": [2]},
        "Titre",
        "Effectif",
        tmp_path,
        "hstack_test.png",
        figure_scale=0.5,
    )
    assert barh_colors, "barh n'a pas été appelé"
    assert barh_colors[0] == COLOR_CHART_AUTRE_RESULTAT
