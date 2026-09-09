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

"""Tests unitaires pour le lot 1 : déport des écritures, isolation réseau, cache et verrous."""

import os
import sys
from pathlib import Path

from core.chemins_projet import (
    is_writable,
    is_network_path,
    get_app_data_dir,
    get_out_dir,
    get_cartes_dir,
    get_carto_temp_dir,
)
from core.common.chargeurs_donnees import (
    _get_cache_dir,
    clear_disk_cache,
)
from core.common.verifier_dependances import (
    injecter_lib_portable,
    verifier_et_installer_accelerateurs,
)
from core.web.serveur import (
    _get_pid_file,
    _register_server_pid,
    _cleanup_server_pid,
    _is_pid_alive,
    touch_watchdog,
)


def test_is_writable_and_get_app_data_dir(tmp_path):
    assert is_writable(tmp_path) is True
    app_data = get_app_data_dir()
    assert isinstance(app_data, Path)
    assert app_data.exists()


def test_get_out_dir_systematically_exports_to_user_directory(monkeypatch, tmp_path):
    # Les exports vont systématiquement dans Documents/OFBilan_Exports par défaut
    monkeypatch.delenv("OFBILAN_EXPORT_DIR", raising=False)
    out = get_out_dir("test_prog")
    assert "OFBilan_Exports" in str(out)
    assert out.name == "test_prog"

    # Et respectent la configuration personnalisée
    custom_export = tmp_path / "custom_exports"
    monkeypatch.setenv("OFBILAN_EXPORT_DIR", str(custom_export))
    out_custom = get_out_dir("test_prog")
    assert str(custom_export) in str(out_custom)


def test_is_network_path():
    assert is_network_path(Path("//serveur/partage/projet")) is True
    assert is_network_path(Path(r"\\serveur\partage\projet")) is True
    assert is_network_path(Path("C:/local/projet")) is False


def test_get_cartes_and_carto_temp_dir_points_to_local_appdata():
    cartes_dir = get_cartes_dir()
    assert isinstance(cartes_dir, Path)
    assert cartes_dir.exists()
    assert cartes_dir.name == "cartes"

    carto_temp = get_carto_temp_dir()
    assert isinstance(carto_temp, Path)
    assert carto_temp.exists()


def test_cache_dir_and_clear_disk_cache():
    cache_dir = _get_cache_dir()
    assert cache_dir.exists()
    assert cache_dir.name == "cache"

    # Créer un fichier temporaire dans le cache et le vider
    dummy_file = cache_dir / "dummy_test.pkl"
    dummy_file.write_text("test", encoding="utf-8")
    assert dummy_file.exists()

    deleted = clear_disk_cache()
    assert deleted >= 1
    assert not dummy_file.exists()


def test_verifier_dependances_lib_injection(tmp_path, monkeypatch):
    # Crée un faux dossier lib
    fake_root = tmp_path / "proj"
    fake_lib = fake_root / "lib"
    fake_lib.mkdir(parents=True)

    monkeypatch.setattr(Path, "resolve", lambda self: fake_root / "core" / "common" / "verifier_dependances.py")
    res = injecter_lib_portable()
    # Si le chemin a été résolu
    if str(fake_lib) in sys.path:
        sys.path.remove(str(fake_lib))


def test_pid_sentinel_lifecycle():
    pid_file = _get_pid_file()
    _register_server_pid()
    assert pid_file.exists()
    assert pid_file.read_text(encoding="utf-8").strip() == str(os.getpid())

    assert _is_pid_alive(os.getpid()) is True
    assert _is_pid_alive(99999999) is False

    _cleanup_server_pid()
    assert not pid_file.exists()


def test_touch_watchdog():
    touch_watchdog()
