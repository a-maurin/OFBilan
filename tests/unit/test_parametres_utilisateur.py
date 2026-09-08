# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL).

"""Tests unitaires pour la gestion et persistance des paramètres utilisateur."""

import json
from pathlib import Path

from core.parametres_utilisateur import (
    get_settings_file_path,
    lire_parametres,
    sauvegarder_parametres,
    charger_parametres,
)


def test_get_settings_file_path_uses_localappdata(tmp_path, monkeypatch):
    """Vérifie que get_settings_file_path cible le dossier LOCALAPPDATA."""
    fake_local = tmp_path / "localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))

    target = get_settings_file_path()
    assert target == fake_local / "OFBilan" / "user_settings.json"
    assert (fake_local / "OFBilan").is_dir()


def test_migration_from_legacy_home(tmp_path, monkeypatch):
    """Vérifie la migration automatique de ~/.ofbilan vers LOCALAPPDATA."""
    fake_home = tmp_path / "home"
    fake_local = tmp_path / "localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(fake_local))
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    legacy_dir = fake_home / ".ofbilan"
    legacy_dir.mkdir(parents=True)
    legacy_file = legacy_dir / "user_settings.json"
    legacy_file.write_text(json.dumps({"tech": {"mode_debug": True}}), encoding="utf-8")

    target = get_settings_file_path()
    assert target == fake_local / "OFBilan" / "user_settings.json"
    assert target.is_file()

    content = json.loads(target.read_text(encoding="utf-8"))
    assert content.get("tech", {}).get("mode_debug") is True


def test_sauvegarder_et_lire_parametres(tmp_path, monkeypatch):
    """Vérifie la sauvegarde atomique et la relecture."""
    fake_file = tmp_path / "custom_settings.json"
    monkeypatch.setattr("core.parametres_utilisateur.get_settings_file_path", lambda: fake_file)

    sauvegarder_parametres({"tech": {"mode_debug": True, "port_serveur": 8888}})
    assert fake_file.is_file()

    read_data = lire_parametres()
    assert read_data["tech"]["mode_debug"] is True
    assert read_data["tech"]["port_serveur"] == 8888


def test_charger_parametres_alias():
    """Vérifie que l'alias de compatibilité charger_parametres fonctionne."""
    assert charger_parametres is lire_parametres
