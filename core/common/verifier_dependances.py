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
