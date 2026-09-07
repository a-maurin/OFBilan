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
# Conformément à la section 7(b) DE LA GPL v3, vous devez expressément conserver
# intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
# clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
# doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
# de l'auteur original (Aguirre MAURIN).

"""
========================================================================================
MODULE : CHARGEUR ET GESTIONNAIRE DE GABARITS DE PRESENTATION (`chargeur_gabarits.py`)
========================================================================================
Ce module gère la découverte, le chargement et l'attribution des gabarits personnalisés (fichiers YAML).

Fonctions assurées :
  1. Découverte des répertoires de gabarits (locaux et globaux).
  2. Chargement et validation de la structure YAML d'un gabarit (gabarit_id, libellés, cibles).
  3. Vérification de la compatibilité d'un gabarit avec un profil de bilan.
  4. Résolution automatique du gabarit approprié selon l'organisation (Région / Service).
  5. Détermination des éléments de carte à masquer (pochoirs cartographiques).
========================================================================================
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import yaml

from core.chemins_projet import PROJECT_ROOT

logger = logging.getLogger(__name__)


# ========================================================================================
# RECHERCHE ET LISTAGE DES DOSSIERS DE GABARITS
# ========================================================================================

def get_gabarits_dirs(root: Path | None = None) -> list[Path]:
    """Retourne la liste des répertoires où sont stockés les fichiers YAML de gabarits.

    Consulte dans l'ordre :
      - Le dossier du projet (`config/presentation/gabarits/`).
      - Le dossier utilisateur local (`~/.ofbilan/gabarits/`).
    """
    base_root = root or PROJECT_ROOT
    dirs = [
        base_root / "config" / "presentation" / "gabarits",
        PROJECT_ROOT / "config" / "presentation" / "gabarits",
        Path.home() / ".ofbilan" / "gabarits",
    ]
    unique_dirs: list[Path] = []
    seen: set[Path] = set()
    for d in dirs:
        try:
            resolved = d.resolve()
        except Exception:
            resolved = d
        if d.exists() and d.is_dir() and resolved not in seen:
            seen.add(resolved)
            unique_dirs.append(d)
    return unique_dirs


ALLOWED_WIDGET_TYPES: set[str] = {
    "map",
    "carte_choroplethe",
    "section_group",
    "stat_kpi_grid",
    "pnf_grand_angle_kpi",
    "theme_breakdown_table",
    "evolution_chart",
    "custom_text_box",
}


def validate_gabarit_schema(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Valide la structure d'un dictionnaire de gabarit selon le schéma de la grille de widgets.

    Retourne un tuple (is_valid, list_of_errors).
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return False, ["Le contenu du gabarit n'est pas un dictionnaire."]

    layout = data.get("layout_grid", data.get("layout"))
    if not isinstance(layout, dict):
        errors.append("La clé 'layout_grid' ou 'layout' doit être un dictionnaire.")
        return False, errors

    pages = layout.get("pages")
    if not isinstance(pages, list) or len(pages) == 0:
        errors.append("La clé 'layout.pages' est obligatoire et doit être une liste non vide.")
        return False, errors

    for p_idx, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            errors.append(f"Page {p_idx} : doit être un dictionnaire.")
            continue
        rows = page.get("rows")
        if not isinstance(rows, list):
            errors.append(f"Page {p_idx} : la clé 'rows' est obligatoire et doit être une liste.")
            continue

        for r_idx, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                errors.append(f"Page {p_idx}, Rangée {r_idx} : doit être un dictionnaire.")
                continue
            cols = row.get("columns")
            if not isinstance(cols, list):
                errors.append(f"Page {p_idx}, Rangée {r_idx} : la clé 'columns' est obligatoire et doit être une liste.")
                continue

            for c_idx, col in enumerate(cols, start=1):
                if not isinstance(col, dict):
                    errors.append(f"Page {p_idx}, Rangée {r_idx}, Colonne {c_idx} : doit être un dictionnaire.")
                    continue
                w_str = col.get("width", "100%")
                if isinstance(w_str, str) and w_str.endswith("%"):
                    try:
                        w_val = float(w_str.rstrip("%"))
                        if w_val <= 0 or w_val > 100:
                            errors.append(f"Page {p_idx}, Rangée {r_idx}, Colonne {c_idx} : largeur '{w_str}' hors limites (0-100%).")
                    except ValueError:
                        errors.append(f"Page {p_idx}, Rangée {r_idx}, Colonne {c_idx} : largeur '{w_str}' invalide.")

                widget = col.get("widget")
                if not isinstance(widget, dict):
                    errors.append(f"Page {p_idx}, Rangée {r_idx}, Colonne {c_idx} : la clé 'widget' est obligatoire.")
                    continue
                w_type = widget.get("type")
                if not w_type or w_type not in ALLOWED_WIDGET_TYPES:
                    errors.append(f"Page {p_idx}, Rangée {r_idx}, Colonne {c_idx} : type de widget '{w_type}' non reconnu (autorisés: {sorted(ALLOWED_WIDGET_TYPES)}).")

    return len(errors) == 0, errors


def load_gabarit_from_path(file_path: Path) -> dict[str, Any] | None:
    """Lit un fichier YAML de gabarit, le valide et complète ses valeurs par défaut."""
    try:
        with file_path.open("r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
        if not isinstance(content, dict):
            logger.warning(f"Fichier de gabarit invalide (non-dictionnaire) : {file_path}")
            return None
        gid = content.get("gabarit_id") or file_path.stem
        content["gabarit_id"] = str(gid).strip()
        content.setdefault("label", content["gabarit_id"])
        content.setdefault("description", "")

        valid, errors = validate_gabarit_schema(content)
        if not valid:
            logger.warning(f"Fichier de gabarit non conforme au schéma : {file_path}. Erreurs: {errors}")
            return None

        content.setdefault("layout", content.get("layout_grid", {}))
        return content
    except Exception as e:
        logger.warning(f"Erreur lors de la lecture du gabarit {file_path} : {e}")
        return None


def list_gabarits(root: Path | None = None, include_aliases: bool = False) -> list[dict[str, Any]]:
    """Scanne tous les dossiers et retourne la liste des gabarits disponibles avec leurs métadonnées."""
    seen: set[str] = set()
    gabarits: list[dict[str, Any]] = []

    for d in get_gabarits_dirs(root):
        for p in sorted(d.glob("*.yaml")):
            data = load_gabarit_from_path(p)
            if not data:
                continue
            if not include_aliases and "alias_of" in data:
                continue
            gid = data["gabarit_id"]
            if gid in seen:
                continue
            seen.add(gid)
            is_sys = is_system_gabarit(gid, root)
            gabarits.append({
                "gabarit_id": gid,
                "label": data.get("label", gid),
                "description": data.get("description", ""),
                "cible": data.get("cible", "les_deux"),
                "profils_compatibles": data.get("profils_compatibles"),
                "organisation": data.get("organisation", {}),
                "is_system": is_sys,
            })

    return gabarits


# ========================================================================================
# GESTION DES GABARITS UTILISATEURS (PERSISTANT & MUTABLE)
# ========================================================================================

def get_user_gabarits_dir() -> Path:
    """Retourne le répertoire de stockage des gabarits utilisateur (~/.ofbilan/gabarits/)."""
    d = Path.home() / ".ofbilan" / "gabarits"
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_system_gabarit(gabarit_id: str, root: Path | None = None) -> bool:
    """Indique si un gabarit est un gabarit système d'origine (lecture seule)."""
    gid_clean = str(gabarit_id).strip()

    base_root = root or PROJECT_ROOT
    sys_dirs = [
        base_root / "config" / "presentation" / "gabarits",
        PROJECT_ROOT / "config" / "presentation" / "gabarits",
    ]
    for sys_dir in sys_dirs:
        try:
            if not sys_dir.exists():
                continue
            candidate = sys_dir / f"{gid_clean}.yaml"
            if candidate.exists():
                return True
            for p in sys_dir.glob("*.yaml"):
                data = load_gabarit_from_path(p)
                if data and data.get("gabarit_id") == gid_clean:
                    return True
        except Exception:
            continue
    return False


def save_user_gabarit(data: dict[str, Any], file_stem: str | None = None) -> tuple[bool, str, list[str]]:
    """Sauvegarde un dictionnaire de gabarit sous forme de fichier YAML dans le répertoire utilisateur."""
    valid, errors = validate_gabarit_schema(data)
    if not valid:
        return False, "Données de gabarit non conformes au schéma.", errors

    gid = str(data.get("gabarit_id") or file_stem or "gabarit_custom").strip()
    clean_id = "".join(c for c in gid if c.isalnum() or c in ("_", "-")).lower()
    if not clean_id:
        clean_id = "gabarit_custom"

    # Si c'est un gabarit système, créer une déclinaison utilisateur avec le suffixe _custom
    if is_system_gabarit(clean_id):
        clean_id = f"{clean_id}_custom"

    data["gabarit_id"] = clean_id
    user_dir = get_user_gabarits_dir()
    target_path = user_dir / f"{clean_id}.yaml"

    try:
        with target_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        return True, clean_id, []
    except Exception as e:
        logger.error(f"Erreur d'écriture du gabarit utilisateur {target_path} : {e}")
        return False, f"Impossible d'enregistrer le fichier : {e}", [str(e)]


def delete_user_gabarit(gabarit_id: str, root: Path | None = None) -> tuple[bool, str]:
    """Supprime un gabarit personnalisé du dossier utilisateur. Interdit la suppression des gabarits système."""
    if is_system_gabarit(gabarit_id, root):
        return False, "Les gabarits système d'origine sont en lecture seule et ne peuvent pas être supprimés."

    user_dir = get_user_gabarits_dir()
    gid_clean = str(gabarit_id).strip()
    target = user_dir / f"{gid_clean}.yaml"

    if not target.exists():
        found = None
        if user_dir.exists():
            for p in user_dir.glob("*.yaml"):
                data = load_gabarit_from_path(p)
                if data and data.get("gabarit_id") == gid_clean:
                    found = p
                    break
        if found:
            target = found
        else:
            return False, f"Gabarit utilisateur '{gabarit_id}' introuvable."

    try:
        target.unlink()
        return True, f"Le gabarit '{gid_clean}' a été supprimé avec succès."
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du gabarit {target} : {e}")
        return False, f"Échec de la suppression : {e}"


def import_gabarit_content(yaml_str: str, file_stem: str | None = None) -> tuple[bool, str, list[str]]:
    """Importe et valide une chaîne YAML pour créer un gabarit personnalisé dans le profil utilisateur."""
    try:
        data = yaml.safe_load(yaml_str)
        if not isinstance(data, dict):
            return False, "Le contenu importé n'est pas un objet dictionnaire YAML.", ["Format YAML non conforme."]
        return save_user_gabarit(data, file_stem=file_stem)
    except Exception as e:
        return False, f"Erreur de syntaxe YAML : {e}", [str(e)]


# ========================================================================================
# CHARGEMENT ET VERIFICATION DE COMPATIBILITE DES GABARITS
# ========================================================================================

def load_gabarit(gabarit_id: str, root: Path | None = None, *, warn_if_missing: bool = True) -> dict[str, Any] | None:
    """Charge la configuration complète d'un gabarit spécifique par son identifiant."""
    gid_clean = str(gabarit_id).strip()
    if not gid_clean or gid_clean.lower() in ("none", "null", "standard", "default"):
        return None

    for d in get_gabarits_dirs(root):
        candidate = d / f"{gid_clean}.yaml"
        if candidate.exists():
            data = load_gabarit_from_path(candidate)
            if data:
                if "alias_of" in data:
                    target_id = str(data["alias_of"]).strip()
                    return load_gabarit(target_id, root, warn_if_missing=warn_if_missing)
                if data.get("gabarit_id") == gid_clean:
                    return data

        # Recherche par parcours de tous les fichiers YAML si le nom de fichier diffère
        for p in d.glob("*.yaml"):
            data = load_gabarit_from_path(p)
            if data:
                if data.get("gabarit_id") == gid_clean:
                    if "alias_of" in data:
                        target_id = str(data["alias_of"]).strip()
                        return load_gabarit(target_id, root, warn_if_missing=warn_if_missing)
                    return data

    if warn_if_missing:
        logger.warning(f"Gabarit de présentation introuvable : '{gabarit_id}'. Bascule sur le profil standard.")
    return None


def is_gabarit_compatible(
    gabarit: dict[str, Any],
    profile_id: str | None = None,
    cible: str = "bilan",
) -> bool:
    """Vérifie si un gabarit peut s'appliquer au type de document (bilan ou brochure) et au profil choisi."""
    g_cible = str(gabarit.get("cible", "les_deux")).strip().lower()
    if g_cible not in ("les_deux", cible.lower()):
        return False

    compat_profiles = gabarit.get("profils_compatibles")
    if compat_profiles and isinstance(compat_profiles, list):
        if profile_id and profile_id not in compat_profiles:
            return False

    return True


def resolve_gabarit_for_service(
    code_region: str | None = None,
    code_service: str | None = None,
    root: Path | None = None,
) -> str | None:
    """Détermine automatiquement le gabarit à utiliser selon la région et le service demandeur.

    1. Priorité 1 : Gabarit spécifique au service dans la région.
    2. Priorité 2 : Gabarit régional général.
    """
    reg = str(code_region or "").strip().lower()
    srv = str(code_service or "").strip().lower()
    if not reg and not srv:
        return None

    available = list_gabarits(root)
    match_region_service: str | None = None
    match_region_only: str | None = None

    for g in available:
        org = g.get("organisation", {})
        if not isinstance(org, dict):
            continue
        g_reg = str(org.get("code_region", "")).strip().lower()
        g_srv = str(org.get("service", "")).strip().lower()

        if reg and srv and g_reg == reg and g_srv == srv:
            match_region_service = g["gabarit_id"]
            break
        if reg and g_reg == reg and not g_srv:
            match_region_only = g["gabarit_id"]

    return match_region_service or match_region_only


def resolve_items_masques_carte(
    profil_data: dict[str, Any] | None = None,
    gabarit_data: dict[str, Any] | None = None,
    *,
    is_brochure: bool = False,
) -> list[str]:
    """Détermine la liste des éléments de la carte à masquer (fusion additive Gabarit + Profil)."""
    masques: list[str] = []

    # 1. Éléments masqués par le profil de bilan
    p_carto = (profil_data or {}).get("cartographie", {}) if isinstance(profil_data, dict) else {}
    if isinstance(p_carto, dict):
        if is_brochure and "items_masques_brochure" in p_carto:
            res = p_carto.get("items_masques_brochure")
            if isinstance(res, list):
                masques.extend(str(x) for x in res)
        else:
            p_def = p_carto.get("items_masques_defaut", p_carto.get("items_masques", []))
            if isinstance(p_def, list):
                masques.extend(str(x) for x in p_def)

    # 2. Additif : Éléments masqués par le gabarit (pochoir cartographique gabarit)
    g_carto = (gabarit_data or {}).get("cartographie", {}) if isinstance(gabarit_data, dict) else {}
    if isinstance(g_carto, dict):
        if is_brochure and "items_masques_brochure" in g_carto:
            res = g_carto.get("items_masques_brochure")
            if isinstance(res, list):
                masques.extend(str(x) for x in res)
        else:
            g_def = g_carto.get("items_masques_defaut", g_carto.get("items_masques", []))
            if isinstance(g_def, list):
                masques.extend(str(x) for x in g_def)

    # Conserver l'ordre d'apparition sans doublons
    seen: set[str] = set()
    result: list[str] = []
    for item in masques:
        if item not in seen:
            seen.add(item)
            result.append(item)

    return result
