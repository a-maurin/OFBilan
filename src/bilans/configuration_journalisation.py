from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure un logging simple pour les scripts de bilans.

    - Format : niveau + message
    - Sortie : stderr
    """
    if logging.getLogger("bilans").handlers:
        return
    logging.basicConfig(
        level=level,
        format="%(levelname)s - %(message)s",
    )

