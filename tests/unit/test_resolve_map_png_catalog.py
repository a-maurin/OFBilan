"""Résolution PNG catalogue global."""
from pathlib import Path

from ofbilan.common.carte_helper import resolve_map_png_path


def test_resolve_map_png_from_catalog(tmp_path: Path, monkeypatch) -> None:
    cartes = tmp_path / "cartes"
    cartes.mkdir()
    (cartes / "carte_global_domaines.png").write_bytes(b"x")
    monkeypatch.setattr("ofbilan.common.carte_helper.get_cartes_dir", lambda: cartes)

    profile = {
        "cartographie": {
            "catalog": [
                {"id": "global_domaines", "label": "Domaines", "fichier": "carte_global_domaines.png"},
            ]
        }
    }
    path = resolve_map_png_path("global_domaines", bilan_profiles={"global": profile})
    assert path is not None
    assert path.name == "carte_global_domaines.png"
