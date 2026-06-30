import logging
import sys
from pathlib import Path


def configure_logging(console_level: int = logging.WARNING) -> None:
    """
    Configure le logging pour les scripts de bilans.

    - Le logger 'ofbilan' est réglé sur DEBUG pour propager tous les messages.
    - Le StreamHandler (console) filtre selon console_level (WARNING par défaut).
    - Sortie console : stderr
    """
    logger = logging.getLogger("ofbilan")
    
    # Si déjà configuré, on ajuste simplement le niveau console existant
    if logger.handlers:
        for h in logger.handlers:
            if not isinstance(h, logging.FileHandler):
                h.setLevel(console_level)
        logger.setLevel(logging.DEBUG)
        return

    logger.setLevel(logging.DEBUG)

    # Handler console
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(console_level)
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    # Empêcher la propagation au root logger pour éviter les doublons si basicConfig est utilisé
    logger.propagate = False


def add_file_handler(out_dir: Path) -> None:
    """
    Ajoute un FileHandler pour enregistrer tous les logs techniques (DEBUG)
    dans un fichier 'debug_run.log' situé dans out_dir.
    """
    logger = logging.getLogger("ofbilan")

    # Éviter d'ajouter plusieurs FileHandlers identiques
    for h in logger.handlers:
        if isinstance(h, logging.FileHandler):
            return

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        log_file = out_dir / "debug_run.log"
        if log_file.exists():
            try:
                log_file.unlink()
            except Exception:
                pass
        
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        # En cas d'erreur de création du dossier ou du fichier, on n'interrompt pas le programme
        logger.warning("Impossible de créer le fichier journal de debug dans %s : %s", out_dir, e)


