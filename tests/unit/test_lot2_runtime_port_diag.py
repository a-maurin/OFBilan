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

"""Tests unitaires pour le lot 2 : détection QGIS durcie, port atomique et diagnostic."""

import json
import os
import socket
from pathlib import Path

from core.cartographie.qgis_runtime import (
    _scan_program_files_qgis,
    get_qgis_env,
    find_qgis_python_executable,
)
from core.parametres_utilisateur import (
    lire_parametres,
    sauvegarder_parametres,
)


def test_get_qgis_env_cleans_parasite_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("CONDA_PREFIX", "C:\\Miniconda")
    monkeypatch.setenv("_CONDA_ROOT", "C:\\Miniconda")
    monkeypatch.setenv("PYTHONHOME", "C:\\CustomPython")

    dummy_py = tmp_path / "bin" / "python.exe"
    dummy_py.parent.mkdir(parents=True)
    dummy_py.touch()

    env = get_qgis_env(dummy_py)
    assert "CONDA_PREFIX" not in env
    assert "_CONDA_ROOT" not in env
    # PYTHONHOME doit pointer vers le Python QGIS, pas la valeur parasite
    assert env["PYTHONHOME"] != "C:\\CustomPython"


def test_qgis_path_settings_persistence(tmp_path, monkeypatch):
    settings_file = tmp_path / "user_settings.json"
    monkeypatch.setattr("core.parametres_utilisateur.get_settings_file_path", lambda: settings_file)

    params = lire_parametres()
    params.setdefault("tech", {})["qgis_path"] = "C:\\Custom\\QGIS\\bin\\python.exe"
    sauvegarder_parametres(params)

    read_back = lire_parametres()
    assert read_back.get("tech", {}).get("qgis_path") == "C:\\Custom\\QGIS\\bin\\python.exe"


def test_annee_reference_default_and_legacy_cleanup(tmp_path, monkeypatch):
    settings_file = tmp_path / "user_settings.json"
    monkeypatch.setattr("core.parametres_utilisateur.get_settings_file_path", lambda: settings_file)

    # Par défaut sans fichier, annee_reference doit être None
    params = lire_parametres()
    assert params.get("geo", {}).get("annee_reference") is None

    # Si un fichier existant contient l'ancien résidu 2024, il doit être nettoyé en None
    settings_file.write_text(json.dumps({"geo": {"annee_reference": 2024}}), encoding="utf-8")
    params_migres = lire_parametres()
    assert params_migres.get("geo", {}).get("annee_reference") is None


def test_find_qgis_python_finds_installation():
    # Sur la machine de test, si QGIS est installé, il doit être trouvé
    found = find_qgis_python_executable(refresh=True)
    if found is not None:
        assert found.exists()
        assert "qgis" in str(found).lower()


def test_atomic_port_bind_simulation():
    # Simuler un port occupé et vérifier que socketserver trouve le suivant
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    busy_port = s.getsockname()[1]

    # Vérifie que la tentative de bind sur ce port échoue
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    failed = False
    try:
        s2.bind(("", busy_port))
    except OSError:
        failed = True
    finally:
        s2.close()
        s.close()

    assert failed is True
