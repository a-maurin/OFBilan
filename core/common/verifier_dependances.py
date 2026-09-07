"""
Module de vérification des dépendances et d'injection des bibliothèques portables.
"""

import sys
import logging
import importlib.util
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("OFBilan.Dependances")


def injecter_lib_portable() -> Path | None:
    """Injecte PROJECT_ROOT / 'lib' en queue de sys.path si présent."""
    try:
        project_root = Path(__file__).resolve().parents[2]
        lib_dir = project_root / "lib"
        lib_str = str(lib_dir)
        if lib_dir.is_dir() and lib_str not in sys.path:
            sys.path.append(lib_str)
            return lib_dir
    except Exception:
        pass
    return None


def verifier_et_installer_accelerateurs(log_callback: Optional[Callable[[str], None]] = None) -> None:
    """
    Vérifie la présence des bibliothèques et accélérateurs sans aucune tentative de pip install.
    Injecte lib/ portable en queue de sys.path.
    """
    lib_path = injecter_lib_portable()
    if lib_path and log_callback:
        log_callback(f"  [INFO] Dossier de bibliothèques portables injecté : {lib_path}")

    targets = [
        ("pyogrio", "pyogrio"),
        ("calamine", "python-calamine"),
    ]

    for mod_name, pkg_name in targets:
        if importlib.util.find_spec(mod_name) is None:
            msg = f"  [INFO] Accélérateur optionnel '{pkg_name}' non présent (utilisation du moteur standard)."
            logger.info(msg)
            if log_callback:
                log_callback(msg)
        else:
            msg_ok = f"  [OK] Accélérateur '{pkg_name}' détecté et actif."
            logger.info(msg_ok)
            if log_callback:
                log_callback(msg_ok)
