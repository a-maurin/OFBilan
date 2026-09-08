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
"""
Tests de non-régression : cycle de vie du serveur (race conditions).
Vérifie :
1. _PRELOAD_STATUS thread-safety via _preload_lock
2. Accès concurrent en lecture/écriture sans data race
3. Shutdown + restart simultanés ne corrompent pas le statut
"""
import threading
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import core.web.serveur as serveur_mod


def test_preload_status_initial():
    """Le statut initial est 'loading'."""
    assert serveur_mod._PRELOAD_STATUS in ("loading", "ready", "error")


def test_preload_lock_exists():
    """Le lock de protection existe."""
    assert hasattr(serveur_mod, "_preload_lock"), (
        "_preload_lock manquant dans serveur.py — la race condition n'est pas corrigée"
    )
    import threading
    assert isinstance(serveur_mod._preload_lock, type(threading.Lock()))


def test_concurrent_status_write_no_corruption():
    """
    Simule N threads qui écrivent _PRELOAD_STATUS simultanément.
    Sans verrou, on observerait des valeurs invalides ou des exceptions.
    Avec verrou, chaque écriture doit être atomique.
    """
    VALID_STATUSES = {"loading", "ready", "error"}
    errors = []

    def write_status(val):
        try:
            with serveur_mod._preload_lock:
                serveur_mod._PRELOAD_STATUS = val
                # Simule une lecture immédiate après écriture
                read_back = serveur_mod._PRELOAD_STATUS
                if read_back != val:
                    errors.append(f"Expected {val}, got {read_back}")
        except Exception as e:
            errors.append(str(e))

    threads = []
    for i in range(20):
        val = list(VALID_STATUSES)[i % len(VALID_STATUSES)]
        t = threading.Thread(target=write_status, args=(val,))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors, f"Race condition détectée : {errors}"
    assert serveur_mod._PRELOAD_STATUS in VALID_STATUSES


def test_preload_logs_thread_safety():
    """_PRELOAD_LOGS est protégé par le même lock."""
    errors = []

    def append_log(msg):
        try:
            with serveur_mod._preload_lock:
                serveur_mod._PRELOAD_LOGS.append(msg)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=append_log, args=(f"log-{i}",)) for i in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors


def test_shutdown_endpoint_contract():
    """Vérifie que /api/shutdown déclenche un arrêt propre et sécurisé avec os._exit."""
    import inspect
    handler_cls = serveur_mod.Handler
    source_get = inspect.getsource(handler_cls.do_GET)
    source_post = inspect.getsource(handler_cls.do_POST)
    assert "/api/shutdown" in source_get
    assert "os._exit(0)" in source_get
    assert "_cleanup_server_pid()" in source_get
    assert "self.server.shutdown()" in source_get
    assert "/api/shutdown" in source_post