"""Utilitaires partagés pour les tests d'intégration TOC PDF."""
from __future__ import annotations

from pathlib import Path

from PIL import Image


def fake_chart_path(out_dir: Path, filename: str) -> str:
    path = Path(out_dir) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (24, 24), color=(200, 220, 240)).save(path)
    return str(path)


def fake_any_chart(*args, **kwargs) -> str:
    """Stub générique pour chart_pie, chart_bar_*, chart_line_evolution, etc."""
    for a in args:
        if isinstance(a, (str, Path)):
            p = Path(a)
            if p.suffix.lower() == ".png":
                return fake_chart_path(p.parent, p.name)
    if len(args) >= 4 and isinstance(args[2], (str, Path)):
        return fake_chart_path(Path(args[2]), str(args[3]))
    if len(args) >= 6 and isinstance(args[4], (str, Path)):
        return fake_chart_path(Path(args[4]), str(args[5]))
    raise ValueError(f"Impossible de déduire le chemin graphique : args={args!r}")


def patch_pdf_charts(monkeypatch, module) -> None:
    """Neutralise les graphiques matplotlib pour un module moteur PDF."""
    for name in (
        "chart_pie",
        "chart_bar",
        "chart_bar_grouped",
        "chart_bar_horizontal_stacked",
        "chart_bar_stacked",
        "chart_line_evolution",
        "chart_stackplot_resultats_domaine",
    ):
        if hasattr(module, name):
            monkeypatch.setattr(module, name, fake_any_chart)


def patch_thematique_pdf_charts(monkeypatch, orch_module) -> None:
    monkeypatch.setattr(orch_module, "load_communes_noms", lambda *a, **k: {})
    patch_pdf_charts(monkeypatch, orch_module)
