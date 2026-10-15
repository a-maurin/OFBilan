# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
# sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
# Voir la Licence Publique Générale GNU pour plus de détails.
#
# CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
# Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
# intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
# clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
# doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
# de l'auteur original (Aguirre MAURIN).

#
from pathlib import Path

from core.common import rendus_graphiques as rg
from core.common.ofb_charte import COLOR_CHART_4, COLOR_GREY


class _FakeFigure:
    def __init__(self) -> None:
        self.saved = []

    def savefig(self, path: str, **kwargs) -> None:
        self.saved.append((path, kwargs))


def test_save_chart_uses_global_300_dpi_default(tmp_path: Path) -> None:
    fig = _FakeFigure()
    original_close = rg.plt.close
    rg.plt.close = lambda _fig: None

    try:
        out = rg.save_chart(fig, tmp_path, "demo.png")
    finally:
        rg.plt.close = original_close

    assert out == str(tmp_path / "demo.png")
    assert len(fig.saved) == 1
    _, kwargs = fig.saved[0]
    assert kwargs["dpi"] == rg.DEFAULT_RASTER_EXPORT_DPI == 300
    assert kwargs["facecolor"] == "white"


def test_horizontal_stacked_chart_defaults_to_global_300_dpi(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, int] = {}

    def _fake_save_chart(fig, tmp_dir, name, *, dpi=rg.DEFAULT_RASTER_EXPORT_DPI, tight=True, pad_inches=0.1):
        captured["dpi"] = dpi
        return str(tmp_dir / name)

    monkeypatch.setattr(rg, "save_chart", _fake_save_chart)

    out = rg.chart_bar_horizontal_stacked(
        ["A"],
        {"Conforme": [1], "Manquement": [2]},
        "Titre",
        "Nombre",
        tmp_path,
        "stacked.png",
    )

    assert out == str(tmp_path / "stacked.png")
    assert captured["dpi"] == rg.DEFAULT_RASTER_EXPORT_DPI == 300


def test_pie_segment_color_uses_grey_for_en_attente() -> None:
    assert rg._pie_segment_color("En attente", "#ffffff") == COLOR_GREY
    assert rg._pie_segment_color("Infraction", "#ffffff") == COLOR_CHART_4
    assert rg._pie_segment_color("Conforme", "#123456") == "#123456"


def test_prepare_pie_data_autres_usagers() -> None:
    data = {"Chasseur": 95, "Agriculteur": 3, "Pêcheur": 2}
    res = rg._prepare_pie_data(data, group_below_pct=5.0, other_label="Autres usagers")
    assert "Autres usagers" in res
    assert res["Autres usagers"] == 5
    assert "Chasseur" in res