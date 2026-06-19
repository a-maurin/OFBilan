"""
Saisie commune département et période pour les scripts de bilan.

Utilisé par les programmes d'analyse (agrainage, chasse, cartes) lorsque
les paramètres --date-deb, --date-fin, --echelle, --code ne sont pas fournis en CLI.
"""
from __future__ import annotations

import datetime as dt
import sys
from typing import Tuple


def _is_interactive() -> bool:
    """Retourne True si stdin est un terminal (saisie interactive possible)."""
    return hasattr(sys.stdin, "isatty") and sys.stdin.isatty()


def _validate_date(s: str) -> bool:
    """Vérifie que *s* est une date valide au format YYYY-MM-DD."""
    if not s:
        return False
    try:
        dt.datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _default_date_deb() -> str:
    """1er janvier de l'année en cours (mode interactif)."""
    return f"{dt.datetime.now().year}-01-01"


def _default_date_fin() -> str:
    """Date du jour (mode interactif)."""
    return dt.datetime.now().strftime("%Y-%m-%d")


def ask_periode_perimetre(
    date_deb_default: str | None = None,
    date_fin_default: str | None = None,
    echelle_default: str = "departement",
    code_default: str = "21",
) -> Tuple[str, str, str, str]:
    """
    Demande à l'utilisateur la date de début, la date de fin et le périmètre (échelle + code).

    Returns:
        (date_deb_str, date_fin_str, echelle_str, code_str)
    """
    if not _is_interactive():
        deb = date_deb_default or ""
        fin = date_fin_default or ""
        echelle = (echelle_default or "departement").strip()
        code = (code_default or "21").strip()
        if not deb or not fin:
            raise ValueError(
                "En mode non interactif, --date-deb et --date-fin doivent être fournis en ligne de commande."
            )
        if not _validate_date(deb) or not _validate_date(fin):
            raise ValueError("Format de date invalide (attendu YYYY-MM-DD).")
        return (deb, fin, echelle, code)

    if not date_deb_default:
        date_deb_default = _default_date_deb()
    if not date_fin_default:
        date_fin_default = _default_date_fin()

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

    print("Période et périmètre géographique d'analyse (Entrée = valeur par défaut)")
    print("-" * 50)
    date_deb = _prompt("Date de début (YYYY-MM-DD)", date_deb_default, _validate_date)
    date_fin = _prompt("Date de fin (YYYY-MM-DD)", date_fin_default, _validate_date)
    
    echelle_choices = [
        ("departement", "Département"),
        ("region", "Région"),
        ("bmi", "Façade maritime (BMI)"),
        ("national", "National"),
    ]
    echelle = ask_choice_list("Échelle spatiale", echelle_choices, echelle_default)
    
    code = "FR"
    if echelle != "national":
        code = _prompt("Code (ex: 21 pour département, 27 pour région BFC)", code_default)
    print()
    return (date_deb, date_fin, echelle, code)


def ask_choice_list(label: str, choices: list[Tuple[str, str]], default_val: str | None = None) -> str:
    """Affiche une liste de choix numérotés et retourne la valeur sélectionnée."""
    if not _is_interactive():
        return default_val or (choices[0][0] if choices else "")

    print(f"{label} :")
    default_idx = None
    for i, (val, desc) in enumerate(choices, 1):
        if val == default_val:
            default_idx = i
        print(f"  [{i}] {desc}")
    
    hint = f" [{default_idx}]" if default_idx else ""
    while True:
        try:
            raw = input(f"Votre choix (numéro){hint} : ").strip()
        except EOFError:
            raw = ""
        
        if not raw and default_idx is not None:
            return default_val
            
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(choices):
                return choices[idx - 1][0]
        print("Saisie invalide, veuillez entrer le numéro correspondant.")
