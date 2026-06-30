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
