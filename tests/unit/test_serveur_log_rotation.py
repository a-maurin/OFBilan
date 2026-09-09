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
Tests unitaires : Journalisation et rotation du log serveur web sur 3 runs max.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.web.serveur import (
    init_server_logger,
    log_server,
    finalize_server_logger,
)


def test_init_server_logger_creates_file_and_header(tmp_path):
    """Vérifie la création du fichier et l'écriture de l'en-tête de démarrage."""
    log_file = tmp_path / "logs" / "test_serveur.log"
    init_server_logger(log_file)
    
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "=== START RUN [" in content
    assert "(PID:" in content


def test_finalize_server_logger_appends_footer(tmp_path):
    """Vérifie l'écriture du footer d'extinction."""
    log_file = tmp_path / "test_serveur.log"
    init_server_logger(log_file)
    log_server("Action test", log_file=log_file)
    finalize_server_logger(reason="Stopped by test", log_file=log_file)
    
    content = log_file.read_text(encoding="utf-8")
    assert "Action test" in content
    assert "=== END RUN [" in content
    assert "(Status: Stopped by test)" in content


def test_server_log_rotation_keeps_max_3_runs(tmp_path):
    """
    Simule 5 démarrages successifs du serveur.
    Le fichier doit contenir exactement 3 balises === START RUN === à la fin.
    """
    log_file = tmp_path / "test_rotation.log"
    
    for i in range(1, 6):
        init_server_logger(log_file)
        log_server(f"Événement du Run #{i}", log_file=log_file)
        finalize_server_logger(reason=f"Fin Run #{i}", log_file=log_file)
    
    content = log_file.read_text(encoding="utf-8")
    start_count = content.count("=== START RUN ")
    end_count = content.count("=== END RUN ")
    
    # 3 runs max conservés
    assert start_count == 3, f"Attendu 3 marqueurs START RUN, obtenu {start_count}"
    assert end_count == 3, f"Attendu 3 marqueurs END RUN, obtenu {end_count}"
    
    # Vérifier que les runs les plus récents (3, 4, 5) sont présents et que les anciens (1, 2) sont purgés
    assert "Événement du Run #1" not in content
    assert "Événement du Run #2" not in content
    assert "Événement du Run #3" in content
    assert "Événement du Run #4" in content
    assert "Événement du Run #5" in content


def test_crash_recovery_preserves_rotation(tmp_path):
    """
    Simule un run interrompu violemment (sans END RUN) suivi de nouveaux runs.
    La rotation par balise START RUN doit quand même fonctionner correctement.
    """
    log_file = tmp_path / "test_crash.log"
    
    # Run 1 : complet
    init_server_logger(log_file)
    log_server("Run 1 normal", log_file=log_file)
    finalize_server_logger("Completed", log_file=log_file)
    
    # Run 2 : crash (pas de finalize)
    init_server_logger(log_file)
    log_server("Run 2 crash imminent", log_file=log_file)
    
    # Run 3 : complet
    init_server_logger(log_file)
    log_server("Run 3 normal", log_file=log_file)
    finalize_server_logger("Completed", log_file=log_file)
    
    # Run 4 : complet
    init_server_logger(log_file)
    log_server("Run 4 normal", log_file=log_file)
    finalize_server_logger("Completed", log_file=log_file)
    
    content = log_file.read_text(encoding="utf-8")
    start_count = content.count("=== START RUN ")
    
    assert start_count == 3
    assert "Run 1 normal" not in content
    assert "Run 2 crash imminent" in content
    assert "Run 3 normal" in content
    assert "Run 4 normal" in content


def test_client_log_formatting(tmp_path):
    """Vérifie le formatage des journaux transmis par le client JS."""
    log_file = tmp_path / "test_client.log"
    init_server_logger(log_file)
    
    log_server("[CLIENT_JS] [explorer.js:1820] Diagnostic Choroplèthe: 12 entités", level="INFO", log_file=log_file)
    log_server("[CLIENT_JS] [explorer.js:45] Erreur JS capturée: Cannot read property 'map'", level="ERROR", log_file=log_file)
    
    content = log_file.read_text(encoding="utf-8")
    assert "[CLIENT_JS] [explorer.js:1820] Diagnostic Choroplèthe: 12 entités" in content
    assert "[CLIENT_JS] [explorer.js:45] Erreur JS capturée" in content

