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

"""Tests unitaires pour le lot 3 : lanceurs blindés et installeur de poste."""

import json
from pathlib import Path
from core.chemins_projet import PROJECT_ROOT


def test_launchers_files_exist():
    ps1_launcher = PROJECT_ROOT / "scripts" / "lancement" / "demarrer_serveur_OFBilan.ps1"
    bat_launcher = PROJECT_ROOT / "scripts" / "lancement" / "demarrer_serveur_OFBilan.bat"
    ps1_installer = PROJECT_ROOT / "scripts" / "deploiement" / "installer_sur_ce_poste.ps1"
    bat_installer = PROJECT_ROOT / "scripts" / "deploiement" / "installer_sur_ce_poste.bat"

    assert ps1_launcher.exists()
    assert bat_launcher.exists()
    assert ps1_installer.exists()
    assert bat_installer.exists()


def test_no_pip_install_in_launchers():
    bat_content = (PROJECT_ROOT / "scripts" / "lancement" / "demarrer_serveur_OFBilan.bat").read_text(encoding="utf-8")
    ps1_content = (PROJECT_ROOT / "scripts" / "lancement" / "demarrer_serveur_OFBilan.ps1").read_text(encoding="utf-8")

    assert "pip install" not in bat_content
    assert "pip install" not in ps1_content


def test_no_mklink_junction_in_installer():
    ps1_installer = (PROJECT_ROOT / "scripts" / "deploiement" / "installer_sur_ce_poste.ps1").read_text(encoding="utf-8")
    bat_installer = (PROJECT_ROOT / "scripts" / "deploiement" / "installer_sur_ce_poste.bat").read_text(encoding="utf-8")

    assert "mklink" not in ps1_installer
    assert "/J" not in ps1_installer
    assert "mklink" not in bat_installer


def test_stub_config_and_resolver_logic(tmp_path):
    stub_dir = tmp_path / "OFBilan_stub"
    stub_dir.mkdir()

    cfg_file = stub_dir / "stub_config.json"
    cfg_file.write_text(json.dumps({"source_path": str(PROJECT_ROOT)}), encoding="utf-8")

    # Vérifie la lecture du stub
    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    resolved = Path(data["source_path"])
    assert resolved.exists()
    assert (resolved / "metadata.txt").exists()
