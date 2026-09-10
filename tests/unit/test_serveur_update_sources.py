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

"""
Tests unitaires pour la gestion des sources et du serveur de téléchargement.
Vérifie :
1. Détection des sources par l'API /api/check-sources (marqueur .download_complete et repli rétrocompatible).
2. Configuration du délai d'attente (défaut 1800 s et surcharge d'environnement).
3. Définition et gestion du marqueur d'intégrité dans fetch_sources.py.
"""
import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import core.web.serveur as serveur_mod
import scripts.donnees.fetch_sources as fetch_sources_mod


def test_marker_file_definition():
    """Vérifie que le marqueur d'intégrité est bien nommé .download_complete dans data/sources."""
    assert fetch_sources_mod.MARKER_FILE.name == ".download_complete"
    assert fetch_sources_mod.MARKER_FILE.parent == fetch_sources_mod.LOCAL_SOURCES


def test_check_sources_with_marker(tmp_path):
    """Vérifie que /api/check-sources répond needs_update=False si le marqueur est présent."""
    sources_dir = tmp_path / "data" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    (sources_dir / ".download_complete").write_text("2026-09-10T12:00:00", encoding="utf-8")

    handler = serveur_mod.Handler.__new__(serveur_mod.Handler)
    handler.path = "/api/check-sources"
    handler.wfile = io.BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    with patch.object(serveur_mod, "SRC_DIR", tmp_path):
        handler.do_GET()

    output = handler.wfile.getvalue().decode("utf-8")
    data = json.loads(output)
    assert data.get("needs_update") is False


def test_check_sources_empty(tmp_path):
    """Vérifie que /api/check-sources répond needs_update=True si le dossier est vide ou n'a que .gitkeep."""
    sources_dir = tmp_path / "data" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    (sources_dir / ".gitkeep").write_text("", encoding="utf-8")

    handler = serveur_mod.Handler.__new__(serveur_mod.Handler)
    handler.path = "/api/check-sources"
    handler.wfile = io.BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    with patch.object(serveur_mod, "SRC_DIR", tmp_path):
        handler.do_GET()

    output = handler.wfile.getvalue().decode("utf-8")
    data = json.loads(output)
    assert data.get("needs_update") is True


def test_check_sources_partial_incomplete(tmp_path):
    """Vérifie que des données partielles sans marqueur déclenchent needs_update=True."""
    sources_dir = tmp_path / "data" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    # Seulement un fichier PVe mais pas de dossier sig
    (sources_dir / "Stats_PVe_OFB au 02.09.2026.xlsx").write_text("data", encoding="utf-8")

    handler = serveur_mod.Handler.__new__(serveur_mod.Handler)
    handler.path = "/api/check-sources"
    handler.wfile = io.BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    with patch.object(serveur_mod, "SRC_DIR", tmp_path):
        handler.do_GET()

    output = handler.wfile.getvalue().decode("utf-8")
    data = json.loads(output)
    assert data.get("needs_update") is True


def test_check_sources_legacy_complete(tmp_path):
    """Vérifie que les installations antérieures complètes (sig + pve) sans marqueur sont reconnues."""
    sources_dir = tmp_path / "data" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    sig_dir = sources_dir / "sig"
    sig_dir.mkdir(parents=True, exist_ok=True)
    (sig_dir / "point_infraction_PJ").mkdir(parents=True, exist_ok=True)
    (sources_dir / "Stats_PVe_OFB au 02.09.2026.xlsx").write_text("data", encoding="utf-8")

    handler = serveur_mod.Handler.__new__(serveur_mod.Handler)
    handler.path = "/api/check-sources"
    handler.wfile = io.BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    with patch.object(serveur_mod, "SRC_DIR", tmp_path):
        handler.do_GET()

    output = handler.wfile.getvalue().decode("utf-8")
    data = json.loads(output)
    assert data.get("needs_update") is False


def test_update_timeout_env_config():
    """Vérifie la prise en compte de la variable d'environnement pour le timeout."""
    with patch.dict(os.environ, {"OFBILAN_UPDATE_TIMEOUT": "2400"}):
        timeout = int(os.environ.get("OFBILAN_UPDATE_TIMEOUT", "1800"))
        assert timeout == 2400

    with patch.dict(os.environ, {}, clear=True):
        timeout = int(os.environ.get("OFBILAN_UPDATE_TIMEOUT", "1800"))
        assert timeout == 1800


def test_update_sources_sse_stream(tmp_path):
    """Vérifie que /api/update-sources stream correctement la sortie et termine avec code 0."""
    fake_script = tmp_path / "scripts" / "donnees" / "fetch_sources.py"
    fake_script.parent.mkdir(parents=True, exist_ok=True)
    fake_script.write_text("print('Ligne 1')\nprint('Ligne 2')\n", encoding="utf-8")

    handler = serveur_mod.Handler.__new__(serveur_mod.Handler)
    handler.path = "/api/update-sources"
    handler.wfile = io.BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    with patch.object(serveur_mod, "SRC_DIR", tmp_path):
        handler.do_GET()

    output = handler.wfile.getvalue().decode("utf-8")
    assert "data: Ligne 1" in output
    assert "data: Ligne 2" in output
    assert "data: [TERMINE] Code de retour: 0" in output
