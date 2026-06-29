"""Utilitaires transverses pour les moteurs PDF (global, profil, etc.)."""

import pandas as pd
import yaml
from pathlib import Path
from ofbilan.chemins_projet import PROJECT_ROOT
from ofbilan.common.percent_format import format_pct_int_from_rate

def truncate_with_dash(value: str, max_len: int) -> str:
    txt = str(value or "")
    if len(txt) <= max_len:
        return txt
    if max_len <= 1:
        return "-"
    return txt[: max_len - 1].rstrip() + "-"

def nb_non_conformes_brut(tab_resultats: pd.DataFrame | None) -> int:
    """Somme Infraction + Manquement (aligné OSCEAN / bilan thématique)."""
    if tab_resultats is None or tab_resultats.empty:
        return 0
    m = tab_resultats["resultat"].astype(str).str.strip()
    return int(tab_resultats.loc[m.isin(["Infraction", "Manquement"]), "nb"].sum())

def pct_table_cell(n: int | float, denom: float) -> str:
    if denom is None or denom <= 0:
        return "n.d."
    return format_pct_int_from_rate(float(n) / float(denom))

def get_region_name_for_footer(echelle: str, code: str) -> str | None:
    """Récupère le nom de la Direction régionale depuis annuaire_ofb.yaml."""
    if echelle != "region" or not code:
        return None
    # Enlever le 'r' éventuel (ex: 'r27' -> '27')
    code_num = code.lstrip('r')
    yaml_path = PROJECT_ROOT / "config" / "annuaire_ofb.yaml"
    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as f:
            annuaire = yaml.safe_load(f) or {}
            regions = annuaire.get("regions", {})
            region_info = regions.get(code_num, {})
            nom = region_info.get("nom")
            if nom:
                return f"Office français de la biodiversité – {nom}"
    return None
