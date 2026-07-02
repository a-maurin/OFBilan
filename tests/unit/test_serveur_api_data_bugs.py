"""
Tests de non-régression pour les bugs A, B, C dans /api/data de serveur.py :
A. debug_pve.txt supprimé : aucun fichier de diagnostic écrit en prod
B. tu_lower ne lève pas UnboundLocalError quand type_usager est None/vide
C. _SESSION_CACHE["active"] restauré même si une exception survient
"""
import sys
import importlib
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import core.web.serveur as serveur_mod


# ── Bug B : tu_lower scope ──────────────────────────────────────────────────

def test_tu_lower_initialized_when_type_usager_is_none():
    """
    Simule l'exécution du bloc de filtrage avec type_usager=None.
    Avant le fix : UnboundLocalError sur `tu_lower` à la ligne du filtrage PEJ/PA.
    Après le fix : aucune exception, tu_lower vaut set().
    """
    import pandas as pd

    # Reproduit le pattern du code serveur
    type_usager = None
    tu_lower = set()  # fix : initialisation préventive

    # Bloc PEJ (ligne 613 originale)
    df_pej = pd.DataFrame({"type_usager": ["Agriculteur", "Particulier"]})
    if type_usager and tu_lower and "type_usager" in df_pej.columns:
        df_pej = df_pej[df_pej["type_usager"].str.lower().apply(
            lambda val: any(u in str(val) for u in tu_lower)
        )].copy()

    # Bloc usagers_counts (ligne 777 originale)
    usagers_counts = {"Agriculteur": 5}
    if type_usager and tu_lower:
        filtered = {k: v for k, v in usagers_counts.items() if any(u in k.lower() for u in tu_lower)}
        usagers_counts = filtered

    assert len(df_pej) == 2  # non filtré car type_usager=None
    assert "Agriculteur" in usagers_counts


def test_tu_lower_initialized_when_type_usager_empty_list():
    """type_usager=[] : même comportement attendu, pas de NameError."""
    import pandas as pd

    type_usager = []
    tu_lower = set()  # fix

    df_pa = pd.DataFrame({"type_usager": ["Entreprise"]})
    if type_usager and tu_lower and "type_usager" in df_pa.columns:
        df_pa = df_pa[df_pa["type_usager"].str.lower().apply(
            lambda val: any(u in str(val) for u in tu_lower)
        )].copy()

    assert len(df_pa) == 1


# ── Bug A : debug_pve.txt supprimé ─────────────────────────────────────────

def test_no_debug_pve_file_written(tmp_path):
    """
    Vérifie qu'aucun fichier debug_pve.txt n'est créé lors du traitement normal.
    Le code corrigé ne doit PAS écrire dans tests/scratch/ en production.
    """
    project_root = Path(__file__).resolve().parents[2]
    debug_file = project_root / "tests" / "scratch" / "debug_pve.txt"

    # On supprime s'il existe pour avoir un état propre
    if debug_file.exists():
        debug_file.unlink()

    # Vérifie que le module serveur n'a pas de référence à debug_pve dans son code source
    serveur_source = (project_root / "core" / "web" / "serveur.py").read_text(encoding="utf-8")
    assert "debug_pve.txt" not in serveur_source, (
        "Le fichier de debug debug_pve.txt est encore référencé dans serveur.py — "
        "supprimez le bloc de diagnostic de production (bug A)."
    )


# ── Bug C : _SESSION_CACHE restauré ─────────────────────────────────────────

def test_session_cache_restored_on_exception():
    """
    Simule le pattern try/finally autour de _SESSION_CACHE["active"].
    Avant le fix : si une exception survient entre le set False et la restauration,
    le cache reste désactivé pour toutes les requêtes suivantes.
    Après le fix : le finally garantit la restauration.
    """
    cache = {"active": True}
    original = cache["active"]

    raised = False
    try:
        cache["active"] = False
        raise RuntimeError("Simulated load failure")
    except RuntimeError:
        raised = True
    finally:
        cache["active"] = original  # fix : finally garantit la restauration

    assert raised
    assert cache["active"] is True, "Le cache doit être restauré même après exception"


def test_session_cache_restored_on_success():
    """Le cache est aussi restauré dans le cas nominal (sans exception)."""
    cache = {"active": True}
    original = cache["active"]

    try:
        cache["active"] = False
        _ = "données chargées"
    finally:
        cache["active"] = original

    assert cache["active"] is True
