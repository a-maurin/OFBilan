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
    # 1) Recherche de la signature (..., tmp_dir: Path, name: str, ...)
    for i in range(len(args) - 1):
        if isinstance(args[i], Path) and isinstance(args[i+1], str) and args[i+1].lower().endswith(".png"):
            return fake_chart_path(args[i], args[i+1])
            
    # 2) Fallback si un chemin complet est passé en un seul argument
    for a in args:
        if isinstance(a, (str, Path)):
            p = Path(a)
            if p.suffix.lower() == ".png" and p.parent != Path("."):
                return fake_chart_path(p.parent, p.name)
                
    # 3) Fallbacks historiques indexés
    if len(args) >= 4 and isinstance(args[2], Path):
        return fake_chart_path(args[2], str(args[3]))
    if len(args) >= 6 and isinstance(args[4], Path):
        return fake_chart_path(args[4], str(args[5]))
        
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
    try:
        from core.engine import sections_thematiques, generation_pdf_thematique
        monkeypatch.setattr(generation_pdf_thematique, "load_communes_noms", lambda *a, **k: {}, raising=False)
        patch_pdf_charts(monkeypatch, sections_thematiques)
        patch_pdf_charts(monkeypatch, generation_pdf_thematique)
    except Exception:
        pass