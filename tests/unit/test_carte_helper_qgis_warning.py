"""Tests — avertissements cartes lorsque QGIS est absent."""
from __future__ import annotations

import logging

from ofbilan.common import carte_helper


def test_generate_maps_warns_when_qgis_unavailable(monkeypatch, caplog) -> None:
    monkeypatch.setattr(carte_helper, "qgis_available", lambda: False)
    monkeypatch.setattr(
        "bilans.cartographie.qgis_runtime.run_cartography_export_subprocess",
        lambda *a, **k: False,
    )
    with caplog.at_level(logging.WARNING):
        result = carte_helper.generate_maps(
            ["global"],
            echelle="departement",
            code="25",
        )
    assert result == []
    assert any("échouée" in r.message or "sous-processus" in r.message for r in caplog.records)


def test_ensure_maps_warns_unresolved_without_qgis(monkeypatch, caplog, tmp_path) -> None:
    cartes = tmp_path / "cartes"
    cartes.mkdir()
    monkeypatch.setattr(carte_helper, "get_cartes_dir", lambda: cartes)
    monkeypatch.setattr(carte_helper, "qgis_available", lambda: False)
    monkeypatch.setattr(carte_helper, "find_map", lambda _pid: None)

    with caplog.at_level(logging.WARNING):
        out = carte_helper.ensure_maps_for_profiles(
            ["global"],
            echelle="departement",
            code="25",
        )
    assert out == []
    assert any("Cartes absentes" in r.message or "non valides" in r.message for r in caplog.records)
