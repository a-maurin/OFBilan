"""
Saisie commune département et période pour les scripts de bilan.

Utilisé par les programmes d'analyse (agrainage, chasse, cartes) lorsque
les paramètres --date-deb, --date-fin, --dept-code ne sont pas fournis en CLI.
"""
from __future__ import annotations

import sys
from datetime import datetime
from typing import Tuple


def _is_interactive() -> bool:
    """Retourne True si stdin est un terminal (saisie interactive possible)."""
    return hasattr(sys.stdin, "isatty") and sys.stdin.isatty()


def _validate_date(s: str) -> bool:
    """Vérifie que *s* est une date valide au format YYYY-MM-DD."""
    if not s:
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def ask_periode_dept(
    date_deb_default: str | None = None,
    date_fin_default: str | None = None,
    dept_default: str = "21",
) -> Tuple[str, str, str]:
    """
    Demande à l'utilisateur la date de début, la date de fin et le code département.

    - En mode interactif (stdin = tty) : affiche des invites et lit les réponses.
      Une entrée vide pour un champ utilise la valeur par défaut.
    - En mode non interactif : utilise les valeurs par défaut et les retourne
      (évite de bloquer en batch). Si une valeur obligatoire manque, lève ValueError.

    Returns:
        (date_deb_str, date_fin_str, dept_code_str) au format attendu (YYYY-MM-DD, YYYY-MM-DD, code).
    """
    if not _is_interactive():
        deb = date_deb_default or ""
        fin = date_fin_default or ""
        dept = (dept_default or "21").strip()
        if not deb or not fin:
            raise ValueError(
                "En mode non interactif, --date-deb et --date-fin doivent être fournis en ligne de commande."
            )
        if not _validate_date(deb) or not _validate_date(fin):
            raise ValueError("Format de date invalide (attendu YYYY-MM-DD).")
        return (deb, fin, dept)

    def _prompt(label: str, default: str | None, validator=None):
        default_str = default or ""
        hint = f" [{default_str}]" if default_str else ""
        while True:
            try:
                val = input(f"{label}{hint} : ").strip() or default_str
            except EOFError:
                val = default_str
            if not val and default_str:
                return default_str
            if validator and not validator(val):
                print("  Format invalide, réessayez.")
                continue
            return val

    print("Période et département d'analyse (Entrée = valeur par défaut)")
    print("-" * 50)
    date_deb = _prompt("Date de début (YYYY-MM-DD)", date_deb_default, _validate_date)
    date_fin = _prompt("Date de fin (YYYY-MM-DD)", date_fin_default, _validate_date)
    dept = _prompt("Code département", dept_default or "21")
    if not dept:
        dept = "21"
    print()
    return (date_deb, date_fin, dept)
