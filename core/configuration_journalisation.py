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
import logging
import sys
from pathlib import Path


class OFBConsoleFormatter(logging.Formatter):
    """
    Formateur console harmonisé et élégant pour OFBilan.
    Affiche des badges colorés ([INFO], [DEBUG], [WARN], [ERREUR], [CRITIQUE])
    et inclut l'horodatage ainsi que le nom du module en mode DEBUG.
    """

    RESET = "\033[0m"
    BOLD = "\033[1m"
    GRAY = "\033[90m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD_RED = "\033[1;91m"

    LEVEL_BADGES = {
        logging.DEBUG: ("🔍 [DEBUG]", CYAN, "[DEBUG]"),
        logging.INFO: ("ℹ️  [INFO]", BLUE, "[INFO]"),
        logging.WARNING: ("⚠️  [WARN]", YELLOW, "[WARN]"),
        logging.ERROR: ("❌ [ERREUR]", RED, "[ERREUR]"),
        logging.CRITICAL: ("🚨 [CRITIQUE]", BOLD_RED, "[CRITIQUE]"),
    }

    def __init__(self, is_debug: bool = False, use_colors: bool | None = None) -> None:
        super().__init__()
        self.is_debug = is_debug
        if use_colors is None:
            use_colors = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
            if use_colors and sys.platform == "win32":
                try:
                    from core.common.ofb_charte import _enable_windows_vt100
                    _enable_windows_vt100()
                except Exception:
                    pass
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        badge_info = self.LEVEL_BADGES.get(
            record.levelno,
            (f"[{record.levelname}]", self.RESET, f"[{record.levelname}]"),
        )
        fancy_badge, color, plain_badge = badge_info

        if self.use_colors:
            badge = f"{color}{fancy_badge}{self.RESET}"
        else:
            badge = plain_badge

        msg = record.getMessage()

        if self.is_debug or record.levelno <= logging.DEBUG:
            from datetime import datetime
            time_str = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            time_prefix = f"{self.GRAY}[{time_str}]{self.RESET}" if self.use_colors else f"[{time_str}]"
            name_prefix = f"{self.GRAY}[{record.name}]{self.RESET}" if self.use_colors else f"[{record.name}]"
            res = f"{time_prefix} {badge} {name_prefix} {msg}"
        else:
            res = f"{badge} {msg}"

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if not res.endswith("\n"):
                res += "\n"
            res += record.exc_text
        if record.stack_info:
            if not res.endswith("\n"):
                res += "\n"
            res += self.formatStack(record.stack_info)
        return res


def configure_logging(console_level: int = logging.INFO) -> None:
    """
    Configure le logging pour les scripts de bilans.

    - Les loggers 'ofbilan' et 'core' sont réglés sur DEBUG pour tout enregistrer dans les fichiers.
    - Le StreamHandler (console) filtre selon console_level (INFO par défaut en mode normal).
    - Sortie console : stderr avec formateur harmonisé OFBConsoleFormatter.
    """
    is_debug = console_level <= logging.DEBUG
    formatter = OFBConsoleFormatter(is_debug=is_debug)

    for logger_name in ("ofbilan", "core"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)

        # Ajustement des handlers existants
        for h in list(logger.handlers):
            if not isinstance(h, logging.FileHandler):
                h.setLevel(console_level)
                h.setFormatter(formatter)

        if not any(not isinstance(h, logging.FileHandler) for h in logger.handlers):
            sh = logging.StreamHandler(sys.stderr)
            sh.setLevel(console_level)
            sh.setFormatter(formatter)
            logger.addHandler(sh)

        logger.propagate = False

    # Neutraliser l'affichage console bruyant sur le root logger en mode normal
    root_logger = logging.getLogger()
    if console_level >= logging.WARNING:
        root_logger.setLevel(logging.ERROR)


def add_file_handler(out_dir: Path) -> None:
    """
    Ajoute un FileHandler pour enregistrer tous les logs techniques (DEBUG)
    dans un fichier 'debug_run.log' situé dans out_dir.
    """
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        log_file = out_dir / "debug_run.log"
        if log_file.exists():
            try:
                log_file.unlink()
            except Exception:
                pass

        for logger_name in ("ofbilan", "core"):
            logger = logging.getLogger(logger_name)
            has_fh = any(isinstance(h, logging.FileHandler) for h in logger.handlers)
            if not has_fh:
                fh = logging.FileHandler(log_file, encoding="utf-8")
                fh.setLevel(logging.DEBUG)
                formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                fh.setFormatter(formatter)
                logger.addHandler(fh)
    except Exception as e:
        logger = logging.getLogger("ofbilan")
        logger.warning("Impossible de créer le fichier journal de debug dans %s : %s", out_dir, e)

