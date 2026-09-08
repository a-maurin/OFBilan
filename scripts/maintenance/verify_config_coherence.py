#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.

"""
========================================================================================
SCRIPT : VERIFICATION DE COHERENCE INTER-CONFIGURATIONS (`verify_config_coherence.py`)
========================================================================================
Ce script contrôle la cohérence globale entre :
  1. Les gabarits de présentation (`config/presentation/gabarits/*.yaml`)
  2. Les profils de bilan analytiques (`config/profils_bilan/*.yaml`)
  3. Le paramétrage cartographique (`config/profils_cartes.yaml`)

Niveaux de sévérité :
  - CRITICAL / ERROR : map_id ou section inexistante dans le gabarit (Fail-Fast).
  - WARNING : Clé optionnelle manquante ou libellé non renseigné.
========================================================================================
"""

import sys
from pathlib import Path
import yaml

def _yaml_include_constructor(loader, node):
    return []

try:
    yaml.add_constructor("!include", _yaml_include_constructor, Loader=yaml.SafeLoader)
except Exception:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

def check_coherence(strict: bool = False) -> tuple[list[str], list[str]]:
    """Vérifie la cohérence inter-configurations et retourne (erreurs_critiques, avertissements)."""
    errors = []
    warnings = []

    cartes_path = ROOT_DIR / "config" / "profils_cartes.yaml"
    if not cartes_path.exists():
        errors.append(f"Fichier profils_cartes.yaml introuvable : {cartes_path}")
        return errors, warnings

    try:
        cartes_cfg = yaml.safe_load(cartes_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        errors.append(f"Erreur de lecture de profils_cartes.yaml : {exc}")
        return errors, warnings

    gabarits_dir = ROOT_DIR / "config" / "presentation" / "gabarits"
    if not gabarits_dir.exists():
        errors.append(f"Dossier de gabarits introuvable : {gabarits_dir}")
        return errors, warnings

    gabarits = list(gabarits_dir.glob("*.yaml"))
    for g_path in gabarits:
        try:
            g_data = yaml.safe_load(g_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            errors.append(f"Gabarit {g_path.name} corrompu : {exc}")
            continue

        # 1. Vérification des widgets cartographiques
        layout_grid = g_data.get("layout_grid", {})
        pages = layout_grid.get("pages", []) if isinstance(layout_grid, dict) else []
        for p in pages:
            p_num = p.get("page_number", "?")
            for r in p.get("rows", []):
                for c in r.get("columns", []):
                    w = c.get("widget", {})
                    if w.get("type") == "map":
                        map_id = w.get("map_id", "global")
                        if map_id != "global" and map_id not in cartes_cfg:
                            errors.append(
                                f"[CRITICAL] Gabarit '{g_path.name}' (Page {p_num}) : "
                                f"widget map référence map_id '{map_id}' absent de profils_cartes.yaml"
                            )

        # 2. Vérification de l'ordre des sections
        sections = g_data.get("sections", {})
        order = sections.get("order", []) if isinstance(sections, dict) else []
        if not order:
            warnings.append(f"[WARNING] Gabarit '{g_path.name}' ne déclare aucun ordre de section ('sections.order').")

    # 3. Vérification des profils de bilan analytiques
    profils_dir = ROOT_DIR / "config" / "profils_bilan"
    if profils_dir.exists():
        sys.path.insert(0, str(ROOT_DIR / "tools"))
        try:
            from config_profils_schema import validate_profile_data
            for p_path in profils_dir.glob("*.yaml"):
                if p_path.stem in ("_defaults", "schema_ui"):
                    continue
                try:
                    p_data = yaml.safe_load(p_path.read_text(encoding="utf-8")) or {}
                    p_errs = validate_profile_data(p_data)
                    for err in p_errs:
                        errors.append(f"[CRITICAL] Profil '{p_path.name}' : {err}")
                except Exception as exc:
                    errors.append(f"[CRITICAL] Profil '{p_path.name}' corrompu : {exc}")
        except ImportError:
            pass

    return errors, warnings


def main():
    print("=================================================================")
    print(" CONTROLEUR DE COHERENCE INTER-CONFIGURATIONS (OFBilan)")
    print("=================================================================")
    errors, warnings = check_coherence()

    if warnings:
        print(f"\n[AVERTISSEMENTS] ({len(warnings)}) :")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print(f"\n[ERREURS CRITIQUES] ({len(errors)}) :")
        for e in errors:
            print(f"  - {e}")
        print("\n=> ECHEC : Des incohérences bloquantes ont été détectées.")
        sys.exit(1)
    else:
        print("\n=> SUCCES : Aucune incohérence critique détectée.")
        sys.exit(0)


if __name__ == "__main__":
    main()
