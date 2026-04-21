"""
Moteur thématique unifié — remplace tous les scripts de bilan spécifiques.

Toute la logique (chasse, agrainage, procédures, types d'usagers, mots-clés
génériques, etc.) est centralisée ici. Le profil YAML pilote le comportement :
filtres, sources de données, options utilisateur, analyses, PDF.

Usage interne (appelé par run_bilan_thematique.py) :
    from scripts.bilan_thematique.bilan_thematique_engine import run_engine
    run_engine("chasse", "2025-09-01", "2026-03-01", "21", options={})
"""
from __future__ import annotations

import logging
import re
import sys
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.paths import get_out_dir, get_cartes_dir, PROJECT_ROOT
from scripts.common.bilan_config import BilanConfig
from scripts.common.loaders import (
    load_point_ctrl,
    load_pej,
    merge_pej_faits_locations,
    load_pa,
    load_pve,
    load_pnf,
    load_tub,
    load_natinf_ref,
    load_tub_pnf_codes,
    load_communes_noms,
    ensure_insee_from_communes_shp,
    enrich_with_pnforet_sig_zones,
    pnf_sig_union_membership_mask,
)
from scripts.common.utils import (
    est_chasse_point,
    contient_natinf,
    get_dept_name,
    _zone_summary,
    _zone_count,
    agg_effectifs_usagers,
    agg_effectifs_usagers_par_domaine,
    agg_controles_par_type_usager_domaine,
    agg_controles_par_type_usager_theme,
    agg_resultats_par_type_usager_domaine,
    agg_resultats_par_type_usager_theme,
    agg_procedures_par_type_usager_domaine,
    agg_procedures_par_type_usager_theme,
    agg_resultat_counts_par_type_usager,
    serie_type_usager,
)
from scripts.common.ofb_charte import Spinner
from scripts.common.pdf_report_builder import (
    PDFReportBuilder,
)
from scripts.common.chart_display_config import load_chart_display_config, compute_pdf_ratios
from scripts.common.charts import (
    chart_pie,
    chart_bar,
    chart_bar_grouped,
    chart_bar_horizontal_stacked,
    chart_bar_stacked,
    chart_line_evolution,
)
from scripts.common.carte_helper import find_map


# ═══════════════════════════════════════════════════════════════════════════
# 1. Chargement du profil YAML
# ═══════════════════════════════════════════════════════════════════════════

def load_profile_config(root: Path, profil_id: str) -> dict:
    """Charge et normalise un profil depuis ref/profils_bilan/<id>.yaml."""
    try:
        import yaml
    except ImportError:
        yaml = None

    path = root / "ref" / "profils_bilan" / f"{profil_id}.yaml"
    if not path.exists():
        return _default_profile(profil_id)

    if yaml is not None:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        # Sans PyYAML, l'ancien parseur minimal écrase des clés (ex. plusieurs « label »
        # dans le fichier) et ignore les blocs imbriqués (restrict_geo, filter…).
        raise ImportError(
            "PyYAML est requis pour lire les profils bilan (ref/profils_bilan/*.yaml). "
            "Installez les dépendances du projet, par exemple : "
            "pip install -r tools/requirements.txt"
        ) from None

    return _normalize_profile(data, profil_id)


def _default_profile(profil_id: str) -> dict:
    return _normalize_profile({"id": profil_id}, profil_id)


def _normalize_profile(data: dict, profil_id: str) -> dict:
    """Assure la présence de toutes les clés attendues par le moteur."""
    data.setdefault("id", profil_id)
    data.setdefault("label", profil_id)
    data.setdefault("out_subdir", f"bilan_{profil_id}")
    # Activation par défaut de l'analyse PVe (comportement historique).
    # Peut être désactivée par profil via analyse_PVe: false dans le YAML.
    data.setdefault("analyse_PVe", True)

    # --- filter ---
    if "filter" not in data:
        data["filter"] = {
            "type": data.pop("filter_type", "keywords"),
            "keywords": data.get("keywords", []),
            "columns": ["theme", "type_actio", "nom_dossie"],
            "exclude_patterns": [],
            "type_usager_target": [],
        }
    filt = data["filter"]
    filt.setdefault("type", "keywords")
    filt.setdefault("keywords", data.get("keywords", []))
    filt.setdefault("columns", ["theme", "type_actio", "nom_dossie"])
    filt.setdefault("exclude_patterns", [])
    filt.setdefault("type_usager_target", [])

    # --- natinf ---
    data.setdefault("natinf_pve", [])
    data.setdefault("natinf_pej", [])
    if isinstance(data["natinf_pve"], str):
        data["natinf_pve"] = [x.strip() for x in data["natinf_pve"].split(",") if x.strip()]
    if isinstance(data["natinf_pej"], str):
        data["natinf_pej"] = [x.strip() for x in data["natinf_pej"].split(",") if x.strip()]

    # --- sources ---
    if "sources" not in data:
        ft = filt["type"]
        if ft == "procedures":
            data["sources"] = {"point_ctrl": False, "pej": True, "pa": False, "pve": False}
        else:
            data["sources"] = {"point_ctrl": True, "pej": True, "pa": True, "pve": True}
    for key in ("point_ctrl", "pej", "pa", "pve"):
        data["sources"].setdefault(key, True)

    # --- période d'analyse / ventilation ---
    period_cfg = data.setdefault("periode_analyse", {})
    if not isinstance(period_cfg, dict):
        period_cfg = {}
        data["periode_analyse"] = period_cfg
    vent_cfg = period_cfg.setdefault("ventilation", {})
    if not isinstance(vent_cfg, dict):
        vent_cfg = {}
        period_cfg["ventilation"] = vent_cfg
    vent_cfg.setdefault("type", "auto")  # auto | globale | annuelle
    vent_cfg.setdefault("seuil_jours", 366)

    # --- restriction géographique (ex. périmètre PNF sur codes INSEE) ---
    data.setdefault("restrict_geo", None)

    # --- options ---
    data.setdefault("options", {})

    return data


def _load_glossary_config(root: Path) -> dict:
    """
    Charge la configuration du glossaire depuis ref/glossaire.yaml.

    Si le fichier n'existe pas ou si PyYAML n'est pas disponible, on
    retourne une configuration par défaut équivalente à l'ancien
    glossaire codé en dur.
    """
    cfg_path = root / "ref" / "glossaire.yaml"

    default_cfg: dict = {
        "header": {
            "abbr_label": "Abréviation",
            "definition_label": "Signification",
        },
        "abbreviations": [
            {"id": "DC", "label": "DC", "definition": "Dossier de contrôle"},
            {
                "id": "NATINF",
                "label": "NATINF",
                "definition": "Nature d'infraction (nomenclature nationale)",
            },
            {
                "id": "OSCEAN",
                "label": "OSCEAN",
                "definition": "Outil de suivi des contrôles en environnement",
            },
            {"id": "PA", "label": "PA", "definition": "Procédure administrative"},
            {"id": "PEJ", "label": "PEJ", "definition": "Procédure d'enquête judiciaire"},
            {"id": "PNF", "label": "PNF", "definition": "Parc national de forêts"},
            {
                "id": "PVe",
                "label": "PVe",
                "definition": "Procès-verbal électronique",
            },
            {
                "id": "TUB",
                "label": "TUB",
                "definition": "Zone tuberculose bovine",
            },
        ],
    }

    if not cfg_path.exists():
        return default_cfg

    try:
        import yaml  # type: ignore[import]
    except ImportError:
        return default_cfg

    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return default_cfg

    # Normalisation minimale
    if not isinstance(data, dict):
        return default_cfg
    header = data.get("header") or {}
    if not isinstance(header, dict):
        header = {}
    abbrs = data.get("abbreviations") or []
    if not isinstance(abbrs, list):
        abbrs = []

    result = {
        "header": {
            "abbr_label": header.get("abbr_label", "Abréviation"),
            "definition_label": header.get("definition_label", "Signification"),
        },
        "abbreviations": [],
    }

    for item in abbrs:
        if not isinstance(item, dict):
            continue
        id_ = str(item.get("id", "")).strip()
        if not id_:
            continue
        label = str(item.get("label", id_)).strip() or id_
        definition = str(item.get("definition", "")).strip()
        if not definition:
            continue
        result["abbreviations"].append(
            {
                "id": id_,
                "label": label,
                "definition": definition,
            }
        )

    # Si aucune abréviation valide, fallback sur le défaut
    if not result["abbreviations"]:
        return default_cfg

    return result


# ═══════════════════════════════════════════════════════════════════════════
# 2. Résolution et interaction des options
# ═══════════════════════════════════════════════════════════════════════════


def _copy_to_clipboard(text: str) -> None:
    """Copie une chaîne dans le presse-papiers (Windows uniquement, mode interactif)."""
    try:
        if sys.platform.startswith("win") and sys.stdin.isatty():
            # Utilisation de l'utilitaire système 'clip' (présent par défaut sur Windows).
            subprocess.run(
                "clip",
                input=text,
                text=True,
                check=False,
                shell=True,
            )
    except Exception:
        # En cas d'échec (clip absent, droits, etc.), on ne bloque pas le bilan.
        pass


def resolve_options(profile: dict, cli_opts: dict | None = None) -> dict:
    """Fusionne les valeurs par défaut du profil avec les surcharges CLI."""
    cli_opts = cli_opts or {}
    options_config = profile.get("options", {})
    resolved: dict[str, Any] = {}

    for key, config in options_config.items():
        if isinstance(config, dict):
            default_val = config.get("default", False)
        else:
            default_val = config
        resolved[key] = cli_opts.get(key, default_val)

    for key, val in cli_opts.items():
        if key not in resolved:
            resolved[key] = val

    return resolved


def ask_interactive_options(profile: dict, current_opts: dict) -> dict:
    """Pose des questions interactives pour les options marquées ask: true."""
    options_config = profile.get("options", {})
    result = dict(current_opts)

    askable = [
        (key, cfg)
        for key, cfg in options_config.items()
        if isinstance(cfg, dict) and cfg.get("ask", False) and key not in current_opts
    ]
    if not askable:
        return result

    print("\n--- Options du bilan ---")
    for key, cfg in askable:
        label = cfg.get("label", key)
        default = cfg.get("default", False)
        default_hint = "O/n" if default else "o/N"
        try:
            answer = input(f"  {label} ? ({default_hint}) : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer == "":
            result[key] = default
        elif answer in ("o", "oui", "y", "yes"):
            result[key] = True
        else:
            result[key] = False

    return result


# ═══════════════════════════════════════════════════════════════════════════
# 2bis. Sélection interactive des types d'usagers cibles
# ═══════════════════════════════════════════════════════════════════════════


def _load_types_usagers_labels(root: Path) -> list[str]:
    """Charge la liste des catégories de type d'usager (ref/types_usagers.csv)."""
    csv_path = root / "ref" / "types_usagers.csv"
    if not csv_path.exists():
        return []
    try:
        df = pd.read_csv(csv_path, sep=";", dtype=str, encoding="utf-8")
    except Exception:
        return []
    if "type_usager" not in df.columns:
        return []
    labels: list[str] = []
    for val in df["type_usager"].dropna().astype(str):
        s = val.strip()
        if s and s not in labels:
            labels.append(s)
    return labels


def ask_type_usager_targets(
    root: Path,
    profil_id: str,
    current_targets: Optional[list[str]] = None,
) -> list[str]:
    """
    Demande à l'utilisateur de sélectionner un ou plusieurs types d'usagers cibles.

    - Si l'entrée standard n'est pas interactive, on retourne current_targets
      ou, à défaut, la liste complète des catégories.
    """
    labels = _load_types_usagers_labels(root)
    if not labels:
        return current_targets or []

    # En contexte non interactif (batch/tests), ne pas bloquer : fallback silencieux.
    if not sys.stdin.isatty():
        return current_targets or labels

    print("\nSélection des types d'usagers cibles :")
    for i, lab in enumerate(labels, 1):
        print(f"  {i}. {lab}")
    print("  *  Tous les types")

    # Tentatives limitées pour éviter les boucles infinies.
    for _ in range(3):
        try:
            raw = input(
                "Entrez un ou plusieurs numéros séparés par des virgules (ex: 1,3,5) "
                "ou * pour tous : "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return current_targets or []

        if not raw:
            # Entrée vide : on garde les cibles actuelles si présentes, sinon tous.
            return current_targets or labels

        if raw == "*":
            return labels

        parts = [p.strip() for p in raw.split(",") if p.strip()]
        idxs: list[int] = []
        ok = True
        for p in parts:
            if not p.isdigit():
                ok = False
                break
            n = int(p)
            if not (1 <= n <= len(labels)):
                ok = False
                break
            idxs.append(n)

        if ok and idxs:
            seen: set[int] = set()
            selected: list[str] = []
            for n in idxs:
                if n in seen:
                    continue
                seen.add(n)
                selected.append(labels[n - 1])
            return selected

        print("Saisie invalide. Merci de réessayer.")

    # Fallback : si toujours rien de valide, utiliser current_targets ou tous.
    return current_targets or labels


# ═══════════════════════════════════════════════════════════════════════════
# 3. Filtrage des données
# ═══════════════════════════════════════════════════════════════════════════

def _filter_point_ctrl(point: pd.DataFrame, profile: dict) -> pd.DataFrame:
    """Filtre les points de contrôle selon la configuration du profil."""
    filt = profile["filter"]
    ft = filt["type"]

    if ft == "all" or ft == "procedures":
        return point.copy()

    if ft == "chasse":
        mask = point.apply(est_chasse_point, axis=1)
        return point[mask].copy()

    if ft == "agrainage":
        return _filter_agrainage(point)

    if ft == "type_usager":
        targets = filt.get("type_usager_target", [])
        if targets:
            return _filter_by_type_usager(point, targets)
        return point.copy()

    # Défaut : filtre par mots-clés
    keywords = filt.get("keywords", [])
    if not keywords:
        keywords = _derive_keywords(profile.get("label", ""))
    if not keywords:
        return point.copy()

    columns = filt.get("columns", ["theme", "type_actio", "nom_dossie"])
    exclude = filt.get("exclude_patterns", [])
    return _filter_by_keywords(point, keywords, columns, exclude)


def _filter_agrainage(point: pd.DataFrame) -> pd.DataFrame:
    """Filtre agrainage : nom_dossie « agrain » OU type_actio sanitaire (hors tuberculose/grippe/piégeage)."""
    mask_nom = pd.Series(False, index=point.index)
    if "nom_dossie" in point.columns:
        mask_nom = point["nom_dossie"].fillna("").astype(str).str.contains(
            "agrain", case=False, regex=False
        )

    mask_type = pd.Series(False, index=point.index)
    type_col = "type_actio" if "type_actio" in point.columns else "type_action"
    if type_col in point.columns:
        col_lower = point[type_col].fillna("").astype(str).str.lower()
        mask_type = col_lower.str.contains("police sanitaire", regex=False)
        mask_excl = col_lower.str.contains(r"tubercul|grippe|pi[eé]geage", regex=True)
        mask_type = mask_type & ~mask_excl

    return point[mask_nom | mask_type].copy()


def _filter_by_keywords(
    pt: pd.DataFrame,
    keywords: list[str],
    columns: list[str],
    exclude_patterns: list[str] | None = None,
) -> pd.DataFrame:
    """Filtre générique par mots-clés sur un ensemble de colonnes."""
    if not keywords:
        return pt
    mask = pd.Series(False, index=pt.index)
    for kw in keywords:
        kw_esc = re.escape(kw)
        for col in columns:
            if col in pt.columns:
                mask |= pt[col].astype(str).str.contains(kw_esc, case=False, na=False, regex=True)

    filtered = pt[mask].copy()

    if exclude_patterns:
        for pattern in exclude_patterns:
            for col in columns:
                if col in filtered.columns:
                    excl = filtered[col].astype(str).str.contains(pattern, case=False, na=False, regex=True)
                    filtered = filtered[~excl]

    return filtered


def _filter_by_type_usager(pt: pd.DataFrame, targets: list[str]) -> pd.DataFrame:
    """Filtre par catégorie de type d'usager."""
    if "type_usager" not in pt.columns or not targets:
        return pt.copy()

    col = pt["type_usager"].fillna("").astype(str)
    targets_lower = {t.lower() for t in targets}
    mask = col.str.lower().apply(
        lambda val: any(t in val for t in targets_lower)
    )
    return pt[mask].copy()


def _safe_type_usager_for_filename(label: str) -> str:
    """Retourne une version du libellé type usager sûre pour les noms de fichiers."""
    if not label or not isinstance(label, str):
        return "type_usager"
    import hashlib
    import unicodedata

    s = label.strip()
    # Normaliser en ASCII pour éviter les caractères illégaux/encodages (ex. "propriété" → "propriete")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[\s'\-]+", "_", s)
    s = "".join(c if (c.isalnum() or c == "_") else "" for c in s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        return "type_usager"

    # Sécuriser la longueur des chemins Windows (et éviter des noms de fichiers énormes)
    if len(s) > 120:
        h = hashlib.md5(label.encode("utf-8", errors="ignore")).hexdigest()[:8]
        s = f"{s[:100]}_{h}"
    return s


def _short_type_usager_code(label: str) -> str:
    """Code court et lisible pour un type d'usager (pour noms de fichiers/cartes)."""
    if not isinstance(label, str):
        return "AUT"
    txt = label.lower()
    # Codes explicites pour les types usuels
    if "agriculteur" in txt:
        return "AGR"
    if "particulier" in txt:
        return "PAR"
    if "collectivit" in txt:
        return "COLL"
    if "entreprise" in txt:
        return "ENTR"
    if "sylvicole" in txt:
        return "SYLV"
    if "autre" in txt:
        return "AUTR"
    # Fallback : dériver un code court à partir du libellé normalisé
    base = _safe_type_usager_for_filename(label)
    return (base[:8] or "AUT").upper()


def _derive_keywords(label: str) -> list[str]:
    """Déduit des mots-clés depuis le label du profil."""
    stop_words = {"de", "du", "des", "la", "le", "les", "et", "ou", "en", "au", "aux",
                  "à", "par", "pour", "sur", "dans", "un", "une", "hors", "snc"}
    if not label:
        return []
    words = re.findall(r"[a-zA-ZÀ-ÿ]+", label)
    return list(dict.fromkeys(
        w.lower() for w in words if len(w) > 2 and w.lower() not in stop_words
    ))


def _filter_pej(
    pej: pd.DataFrame,
    profile: dict,
    cfg: BilanConfig,
    point_filtered: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Filtre les PEJ selon le profil (NATINF, mots-clés ou tout)."""
    natinf_pej = profile.get("natinf_pej", [])
    ft = profile["filter"]["type"]

    # Restriction au département par entité
    entity_sd = cfg.entity_sd
    if "ENTITE_ORIGINE_PROCEDURE" in pej.columns:
        pej = pej[pej["ENTITE_ORIGINE_PROCEDURE"] == entity_sd].copy()

    # Déduplication par DC_ID
    if "DC_ID" in pej.columns:
        if "DATE_REF" in pej.columns:
            pej = pej.sort_values("DATE_REF", ascending=False).drop_duplicates(
                subset="DC_ID", keep="first"
            )
        else:
            pej = pej.drop_duplicates(subset="DC_ID", keep="first")

    if natinf_pej:
        pattern = "|".join(rf"(?:^|_){re.escape(c)}(?:_|$)" for c in natinf_pej)
        natinf_col = "NATINF_PEJ" if "NATINF_PEJ" in pej.columns else "NATINF"
        if natinf_col in pej.columns:
            return pej[
                pej[natinf_col].fillna("").astype(str).str.contains(pattern, regex=True)
            ].copy()

    if ft == "procedures":
        return pej.copy()

    if ft == "type_usager":
        targets = (profile.get("filter", {}) or {}).get("type_usager_target") or []
        if targets and "type_usager" in pej.columns:
            return _filter_by_type_usager(pej, targets)
        return pej.copy()

    # Filtre par mots-clés
    keywords = profile["filter"].get("keywords", [])
    if keywords:
        cols = [c for c in ["DOMAINE", "THEME", "TYPE_ACTION"] if c in pej.columns]
        return _filter_by_keywords(pej, keywords, cols) if cols else pej
    return pej


def _filter_pa(
    pa: pd.DataFrame,
    profile: dict,
    cfg: BilanConfig,
    point_filtered: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Filtre les PA selon le profil."""
    ft = profile["filter"]["type"]
    entity_sd = cfg.entity_sd

    # Restreindre systématiquement aux procédures de l'entité SD concernée
    if "ENTITE_ORIGINE_PROCEDURE" in pa.columns:
        pa = pa[pa["ENTITE_ORIGINE_PROCEDURE"] == entity_sd].copy()

    dc_ids_dept: Set[str] = set()
    if (
        point_filtered is not None
        and not point_filtered.empty
        and "dc_id" in point_filtered.columns
    ):
        dc_ids_dept = set(point_filtered["dc_id"].dropna().unique())

    # Profils chasse / agrainage : logique historique conservée, mais appliquée
    # sur le sous-ensemble déjà restreint à l'entité SD.
    if ft in ("chasse", "agrainage"):
        if "DC_ID" in pa.columns and dc_ids_dept:
            mask = pa["DC_ID"].isin(dc_ids_dept)
        else:
            mask = pd.Series(False, index=pa.index)
        pa_dept = pa[mask].copy()

        keywords = profile["filter"].get("keywords", [])
        if not keywords:
            if ft == "chasse":
                keywords = ["chasse"]
            elif ft == "agrainage":
                keywords = ["agrainage", "agrain"]
        cols = [c for c in ["THEME", "TYPE_ACTION"] if c in pa_dept.columns]
        if keywords and cols:
            pa_dept = _filter_by_keywords(pa_dept, keywords, cols)
        pa_filtered = pa_dept
    else:
        # Profils génériques (dont types_usager_cible) :
        # - si des DC_ID de contrôles filtrés sont disponibles, on ne retient
        #   que les PA liées à ces contrôles ;
        # - sinon, on reste sur le sous-ensemble SD uniquement.
        if "DC_ID" in pa.columns and dc_ids_dept:
            pa = pa[pa["DC_ID"].isin(dc_ids_dept)].copy()

        keywords = profile["filter"].get("keywords", [])
        if keywords:
            cols = [c for c in ["THEME", "TYPE_ACTION", "DOMAINE"] if c in pa.columns]
            pa = _filter_by_keywords(pa, keywords, cols) if cols else pa
        pa_filtered = pa

    # Déduplication : une seule ligne par DC_ID lorsque cet identifiant est présent.
    if "DC_ID" in pa_filtered.columns:
        if "DATE_REF" in pa_filtered.columns:
            pa_filtered = (
                pa_filtered.sort_values("DATE_REF", ascending=False)
                .drop_duplicates(subset="DC_ID", keep="first")
            )
        else:
            pa_filtered = pa_filtered.drop_duplicates(subset="DC_ID", keep="first")

    return pa_filtered


def _filter_pve(
    pve: pd.DataFrame,
    profile: dict,
) -> pd.DataFrame:
    """Filtre les PVe selon le profil (NATINF ou mots-clés)."""
    natinf_pve = profile.get("natinf_pve", [])

    if natinf_pve:
        natinf_col = "INF-NATINF" if "INF-NATINF" in pve.columns else "NATINF"
        if natinf_col in pve.columns:
            return pve[
                pve[natinf_col].apply(lambda x: contient_natinf(x, natinf_pve))
            ].copy()

    keywords = profile["filter"].get("keywords", [])
    if keywords:
        cols = [c for c in ["INF-NATINF", "NATINF", "theme", "THEME"] if c in pve.columns]
        return _filter_by_keywords(pve, keywords, cols) if cols else pve
    return pve


# ═══════════════════════════════════════════════════════════════════════════
# 4. Analyses spatiales
# ═══════════════════════════════════════════════════════════════════════════

def _get_insee_col(df: pd.DataFrame) -> str | None:
    for c in ("insee_comm", "insee_commun", "INSEE_COM", "INF-INSEE"):
        if c in df.columns:
            return c
    return None


def _coalesced_insee_for_pnf_mask(df: pd.DataFrame) -> pd.Series:
    """
    Code INSEE normalisé (5 chiffres) par ligne, en combinant les colonnes usuelles
    (première valeur exploitable). Évite de n'utiliser qu'une colonne vide alors
    qu'une autre source est renseignée.
    """
    if df.empty:
        return pd.Series(pd.NA, index=df.index, dtype="string")
    out = pd.Series(pd.NA, index=df.index, dtype="string")
    for col in ("insee_comm", "insee_commun", "INSEE_COM", "INF-INSEE"):
        if col not in df.columns:
            continue
        raw = df[col]
        cand = (
            raw.astype(str)
            .str.extract(r"(\d{1,5})", expand=False)
            .fillna("")
            .str.zfill(5)
        )
        cand = cand.mask(~cand.str.fullmatch(r"\d{5}", na=False), pd.NA)
        out = out.fillna(cand)
    return out


def _mask_insee_in_pnf_codes(df: pd.DataFrame, pnf_codes: set) -> pd.Series:
    if df.empty:
        return pd.Series([], dtype=bool)
    s = _coalesced_insee_for_pnf_mask(df)
    return s.notna() & s.astype(str).isin(pnf_codes)


def _apply_restrict_geo_pnf(
    point_filtered: pd.DataFrame,
    pej_filtered: pd.DataFrame,
    pa_filtered: pd.DataFrame,
    pve_filtered: pd.DataFrame,
    root: Path,
    log: logging.Logger,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Restreint les jeux de données au périmètre PNF : communes listées dans le
    référentiel (INSEE) **ou** localisation dans les polygones SIG (cœur +
    aire d'adhésion), pour pallier les écarts entre liste de communes et périmètre réel.
    """
    _, pnf_codes = load_tub_pnf_codes(root)

    if not point_filtered.empty:
        point_filtered = ensure_insee_from_communes_shp(
            point_filtered,
            root,
            context="restriction PNF — points de contrôle",
            log=log,
        )
        mask_insee = _mask_insee_in_pnf_codes(point_filtered, pnf_codes)
        mask_sig = pnf_sig_union_membership_mask(point_filtered, root, log=log)
        mask = mask_insee | mask_sig
        if not mask.any():
            log.warning(
                "Restriction PNF : aucun point ne correspond à la liste INSEE du référentiel "
                "ni aux couches SIG (cœur / adhésion) ; vérifiez communes_pnf, les coordonnées "
                "et ref/sig/PNF."
            )
        point_filtered = point_filtered.loc[mask].copy()
    # Règle métier PA : seules les localisations de contrôles "Manquement" portent
    # l'assiette spatiale des PA.
    point_manq = point_filtered
    if "resultat" in point_filtered.columns:
        point_manq = point_filtered[
            point_filtered["resultat"].astype(str).str.strip().str.lower() == "manquement"
        ].copy()

    dc_ids: Set[str] = set()
    if not point_filtered.empty and "dc_id" in point_filtered.columns:
        dc_ids = set(point_filtered["dc_id"].dropna().astype(str).unique())
    dc_ids_pa: Set[str] = set()
    if not point_manq.empty and "dc_id" in point_manq.columns:
        dc_ids_pa = set(point_manq["dc_id"].dropna().astype(str).unique())

    if not pej_filtered.empty and "DC_ID" in pej_filtered.columns:
        # Les PEJ ne sont pas toutes liées à un contrôle : on conserve celles qui
        # suivent un contrôle dans le périmètre OU dont la localisation FAITS
        # (x_faits / y_faits) est dans le parc (polygones SIG et/ou communes PNF).
        mask_pej = pd.Series(False, index=pej_filtered.index)
        if dc_ids:
            mask_pej = mask_pej | pej_filtered["DC_ID"].astype(str).str.strip().isin(dc_ids)
        if "x_faits" in pej_filtered.columns and "y_faits" in pej_filtered.columns:
            xy_ok = pej_filtered["x_faits"].notna() & pej_filtered["y_faits"].notna()
            if bool(xy_ok.any()):
                loc_df = pd.DataFrame(
                    {
                        "x": pd.to_numeric(pej_filtered.loc[xy_ok, "x_faits"], errors="coerce"),
                        "y": pd.to_numeric(pej_filtered.loc[xy_ok, "y_faits"], errors="coerce"),
                    },
                    index=pej_filtered.index[xy_ok],
                )
                sig_m = pnf_sig_union_membership_mask(loc_df, root, log=log).reindex(
                    pej_filtered.index, fill_value=False
                )
                mask_pej = mask_pej | sig_m
                sub = pej_filtered.loc[xy_ok].copy()
                sub["x"] = pd.to_numeric(sub["x_faits"], errors="coerce")
                sub["y"] = pd.to_numeric(sub["y_faits"], errors="coerce")
                sub_insee = ensure_insee_from_communes_shp(
                    sub,
                    root,
                    context="restriction PNF — PEJ (coordonnées FAITS)",
                    log=log,
                )
                m_insee = _mask_insee_in_pnf_codes(sub_insee, pnf_codes)
                mask_pej = mask_pej | m_insee.reindex(pej_filtered.index, fill_value=False)
        if not mask_pej.any():
            log.warning(
                "Restriction PNF : aucune PEJ ne correspond à un contrôle du périmètre "
                "ni à une localisation FAITS dans le parc."
            )
        pej_filtered = pej_filtered.loc[mask_pej].copy()

    if not pa_filtered.empty and "DC_ID" in pa_filtered.columns:
        if dc_ids_pa:
            pa_filtered = pa_filtered[
                pa_filtered["DC_ID"].dropna().astype(str).isin(dc_ids_pa)
            ].copy()
        else:
            pa_filtered = pa_filtered.iloc[0:0].copy()

    if not pve_filtered.empty:
        pve_filtered = ensure_insee_from_communes_shp(
            pve_filtered,
            root,
            context="restriction PNF — PVe",
            log=log,
        )
        mask_pi = _mask_insee_in_pnf_codes(pve_filtered, pnf_codes)
        mask_pg = pnf_sig_union_membership_mask(pve_filtered, root, log=log)
        mask_p = mask_pi | mask_pg
        if not mask_p.any():
            log.warning(
                "Restriction PNF : aucune PVe ne correspond au périmètre INSEE ni SIG."
            )
            pve_filtered = pve_filtered.iloc[0:0].copy()
        else:
            pve_filtered = pve_filtered.loc[mask_p].copy()

    return point_filtered, pej_filtered, pa_filtered, pve_filtered


def _run_spatial_analyses(
    point_filtered: pd.DataFrame,
    pej_filtered: pd.DataFrame,
    pve_filtered: pd.DataFrame,
    options: dict,
    cfg: BilanConfig,
    profil_id: str | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Calcule les découpages spatiaux (PNF, TUB) si les options le demandent."""
    results: dict[str, Any] = {}
    need_pnf = options.get("pnf", False)
    need_tub = options.get("tub", False)

    if not need_pnf and not need_tub:
        return results, point_filtered

    tub_codes, pnf_codes = load_tub_pnf_codes(cfg.root)
    results["tub_codes"] = tub_codes
    results["pnf_codes"] = pnf_codes

    pt = point_filtered.copy()
    insee_col = _get_insee_col(pt)

    if need_pnf and not pt.empty and insee_col:
        pt[insee_col] = pt[insee_col].astype(str).str.zfill(5)
        pnf_df = load_pnf(cfg.root)
        pt = pt.merge(
            pnf_df[["CODE_INSEE"]],
            left_on=insee_col,
            right_on="CODE_INSEE",
            how="left",
        )
        pt["PNF"] = pt["CODE_INSEE"].notna().map(
            {True: "PNF", False: "Hors PNF"}
        )
        pt = pt.drop(columns=["CODE_INSEE"], errors="ignore")

        agg_pnf = (
            pt.groupby("PNF")
            .agg(
                nb_controles=("dc_id", "count"),
                nb_inf=("resultat", lambda s: (s == "Infraction").sum()),
            )
            .reset_index()
        )
        agg_pnf["taux_inf"] = agg_pnf["nb_inf"] / agg_pnf["nb_controles"].replace(0, pd.NA)
        results["agg_pnf"] = agg_pnf
        results["point_with_pnf"] = pt
        # Bilan thématique PNF : présenter "Ensemble PNF" + "Cœur de parc"
        # (sur périmètre déjà restreint au PNF : aire d'adhésion + cœur).
        if str(profil_id or "").strip().lower() in {"pnf", "pnf_foret"}:
            nb_total = int(len(pt))
            nb_inf_total = int((pt["resultat"] == "Infraction").sum()) if "resultat" in pt.columns else 0
            rows = [
                {
                    "PNF": "Ensemble PNF",
                    "nb_controles": nb_total,
                    "nb_inf": nb_inf_total,
                    "taux_inf": (nb_inf_total / nb_total) if nb_total > 0 else pd.NA,
                }
            ]
            if "pnf_zone_sig" in pt.columns:
                coeur = pt[pt["pnf_zone_sig"] == "Coeur_PNF"].copy()
                nb_c = int(len(coeur))
                nb_inf_c = int((coeur["resultat"] == "Infraction").sum()) if "resultat" in coeur.columns else 0
                rows.append(
                    {
                        "PNF": "Cœur de parc",
                        "nb_controles": nb_c,
                        "nb_inf": nb_inf_c,
                        "taux_inf": (nb_inf_c / nb_c) if nb_c > 0 else pd.NA,
                    }
                )
            results["agg_pnf_detail"] = pd.DataFrame(rows)

    if (need_pnf or need_tub) and not pt.empty and insee_col:
        results["zone_ctrl"] = _zone_summary(pt, insee_col, tub_codes, pnf_codes)

    if (need_pnf or need_tub) and not pve_filtered.empty:
        pve_insee = _get_insee_col(pve_filtered)
        if pve_insee:
            base_z = _zone_count(pve_filtered, pve_insee, tub_codes, pnf_codes)
            pid = str(profil_id or "").strip().lower()
            if pid in {"pnf", "pnf_foret"}:
                insee = pve_filtered[pve_insee].astype(str).str.zfill(5)
                mask_pnf = insee.isin(pnf_codes)
                nb_ensemble = int(mask_pnf.sum())
                if "pnf_zone_sig" in pve_filtered.columns:
                    zs = pve_filtered["pnf_zone_sig"]
                    nb_coeur = int((zs == "Coeur_PNF").sum())
                    nb_aire = int((zs == "Aire_adhesion_PNF").sum())
                else:
                    nb_coeur = 0
                    nb_aire = 0
                # PDF / exports : uniquement le découpage PNF (pas département ni TUB).
                results["zone_pve"] = pd.DataFrame(
                    [
                        {"zone": "Ensemble PNF", "nb": nb_ensemble},
                        {"zone": "Cœur de parc", "nb": nb_coeur},
                        {"zone": "Aire d'adhésion", "nb": nb_aire},
                    ]
                )
            else:
                results["zone_pve"] = base_z

    if (need_pnf or need_tub) and not pej_filtered.empty:
        pej_insee = _get_insee_col(pej_filtered)
        if not pej_insee and "DC_ID" in pej_filtered.columns and not pt.empty and insee_col:
            pej_with_insee = pej_filtered.merge(
                pt[["dc_id", insee_col]].drop_duplicates("dc_id"),
                left_on="DC_ID",
                right_on="dc_id",
                how="left",
            )
            pej_insee = insee_col
            results["zone_pej"] = _zone_count(
                pej_with_insee.dropna(subset=[pej_insee]), pej_insee, tub_codes, pnf_codes
            )
        elif pej_insee:
            results["zone_pej"] = _zone_count(pej_filtered, pej_insee, tub_codes, pnf_codes)

    return results, pt


# ═══════════════════════════════════════════════════════════════════════════
# 5. Agrégations et exports CSV
# ═══════════════════════════════════════════════════════════════════════════

def _run_aggregations(
    point_filtered: pd.DataFrame,
    pej_filtered: pd.DataFrame,
    pa_filtered: pd.DataFrame,
    pve_filtered: pd.DataFrame,
    profile: dict,
    options: dict,
    spatial: dict,
    ventilation_mode: str = "globale",
) -> dict:
    """Calcule toutes les agrégations et retourne un dict de DataFrames."""
    results: dict[str, Any] = {}
    profil_id = profile["id"]

    nb_ctrl = len(point_filtered)
    nb_pej = len(pej_filtered)
    nb_pa = len(pa_filtered)
    nb_pve = len(pve_filtered)
    results["nb_ctrl"] = nb_ctrl
    results["nb_pej"] = nb_pej
    results["nb_pa"] = nb_pa
    results["nb_pve"] = nb_pve

    # Résultats des contrôles
    if not point_filtered.empty and "resultat" in point_filtered.columns:
        tab = (
            point_filtered["resultat"]
            .value_counts()
            .rename_axis("resultat")
            .to_frame("nb")
            .reset_index()
        )
        tab["taux"] = tab["nb"] / float(nb_ctrl or 1)
        results["tab_resultats"] = tab

    # Par thème
    if not point_filtered.empty and "theme" in point_filtered.columns:
        agg = (
            point_filtered["theme"]
            .fillna("")
            .astype(str)
            .value_counts()
            .rename_axis("theme")
            .to_frame("nb")
            .reset_index()
        )
        agg["taux"] = agg["nb"] / float(nb_ctrl or 1)
        results["agg_theme"] = agg

    # Par commune
    insee_col = _get_insee_col(point_filtered)
    if options.get("par_commune", True) and not point_filtered.empty and insee_col:
        agg_c = (
            point_filtered.groupby(insee_col)
            .agg(
                nb_controles=("dc_id", "count"),
                nb_infractions=("resultat", lambda s: (s == "Infraction").sum()),
            )
            .reset_index()
        )
        agg_c["taux_infraction"] = agg_c["nb_infractions"] / agg_c["nb_controles"].replace(0, pd.NA)
        results["agg_commune"] = agg_c

    # PEJ par thème/domaine
    if not pej_filtered.empty:
        for col in ("THEME", "DOMAINE"):
            if col in pej_filtered.columns:
                agg_pej = (
                    pej_filtered.groupby([c for c in ["DOMAINE", "THEME"] if c in pej_filtered.columns])
                    .size()
                    .rename("nb_pej")
                    .reset_index()
                )
                results["pej_par_theme"] = agg_pej
                break

    # PA par thème/domaine
    if not pa_filtered.empty:
        for col in ("THEME", "DOMAINE"):
            if col in pa_filtered.columns:
                agg_pa = (
                    pa_filtered.groupby([c for c in ["DOMAINE", "THEME"] if c in pa_filtered.columns])
                    .size()
                    .rename("nb_pa")
                    .reset_index()
                )
                results["pa_par_theme"] = agg_pa
                break

    # PEJ : statistiques de durée (pour profil procedures)
    ft = profile["filter"]["type"]
    if ft == "procedures" and not pej_filtered.empty and "DUREE_PEJ" in pej_filtered.columns:
        duree = pd.to_numeric(pej_filtered["DUREE_PEJ"], errors="coerce").dropna()
        if len(duree) > 0:
            results["pej_duree_resume"] = {
                "nb_pej": nb_pej,
                "duree_moy_j": round(duree.mean(), 1),
                "duree_mediane_j": round(duree.median(), 1),
                "duree_p25_j": round(duree.quantile(0.25), 1),
                "duree_p75_j": round(duree.quantile(0.75), 1),
            }
        if "CLOTUR_PEJ" in pej_filtered.columns:
            results["pej_clotur"] = (
                pej_filtered["CLOTUR_PEJ"].fillna("(vide)").astype(str)
                .value_counts()
                .rename_axis("cloture")
                .to_frame("nb")
                .reset_index()
            )
        if "SUITE" in pej_filtered.columns:
            results["pej_suite"] = (
                pej_filtered["SUITE"].fillna("(vide)").astype(str)
                .value_counts()
                .rename_axis("suite")
                .to_frame("nb")
                .reset_index()
            )
        for grp_col in ("THEME", "DOMAINE"):
            if grp_col in pej_filtered.columns:
                grp = pej_filtered.groupby(grp_col).agg(
                    nb_pej=("DC_ID", "count"),
                    duree_moy=(
                        "DUREE_PEJ",
                        lambda s: pd.to_numeric(s, errors="coerce").mean(),
                    ),
                    duree_med=(
                        "DUREE_PEJ",
                        lambda s: pd.to_numeric(s, errors="coerce").median(),
                    ),
                ).reset_index()
                results[f"pej_par_{grp_col.lower()}"] = grp

    # Types d'usagers : profil dédié (analyses.type_usager) et/ou section PDF
    # « Activité par types d'usagers » (tous profils avec colonne type_usager).
    have_type_usager_col = (
        not point_filtered.empty and "type_usager" in point_filtered.columns
    )
    type_usager_profile = profile.get("analyses", {}).get("type_usager", False)
    targets = (profile.get("filter", {}) or {}).get("type_usager_target") or []
    pt_us = point_filtered
    if have_type_usager_col and targets:
        pt_us = _filter_by_type_usager(point_filtered, targets)

    if have_type_usager_col:
        ue = agg_effectifs_usagers(pt_us)
        if targets and not ue.empty:
            ue = ue[ue["type_usager"].isin(targets)]
        results["usager_effectifs"] = ue

        ud = agg_effectifs_usagers_par_domaine(pt_us)
        if targets and not ud.empty and "type_usager" in ud.columns:
            ud = ud[ud["type_usager"].isin(targets)]
        results["usager_par_domaine"] = ud

        ctrl_ud = agg_controles_par_type_usager_domaine(pt_us)
        if targets and not ctrl_ud.empty:
            ctrl_ud = ctrl_ud[ctrl_ud["type_usager"].isin(targets)]
        results["ctrl_par_usager_domaine"] = ctrl_ud

        ctrl_ut = agg_controles_par_type_usager_theme(pt_us)
        if targets and not ctrl_ut.empty:
            ctrl_ut = ctrl_ut[ctrl_ut["type_usager"].isin(targets)]
        results["ctrl_par_usager_theme"] = ctrl_ut

        res_ud = agg_resultats_par_type_usager_domaine(pt_us)
        if targets and not res_ud.empty:
            res_ud = res_ud[res_ud["type_usager"].isin(targets)]
        results["res_par_usager_domaine"] = res_ud

        res_ut = agg_resultats_par_type_usager_theme(pt_us)
        if targets and not res_ut.empty:
            res_ut = res_ut[res_ut["type_usager"].isin(targets)]
        results["res_par_usager_theme"] = res_ut

        proc_ud = agg_procedures_par_type_usager_domaine(pt_us)
        if targets and not proc_ud.empty:
            proc_ud = proc_ud[proc_ud["type_usager"].isin(targets)]
        results["proc_par_usager_domaine"] = proc_ud

        proc_ut = agg_procedures_par_type_usager_theme(pt_us)
        if targets and not proc_ut.empty:
            proc_ut = proc_ut[proc_ut["type_usager"].isin(targets)]
        results["proc_par_usager_theme"] = proc_ut

        results["res_bilan_par_type_usager"] = agg_resultat_counts_par_type_usager(
            pt_us
        )

        # Section PDF dédiée : pas de doublon avec le profil « types d'usagers » (sommaire séparé).
        results["_pdf_show_activite_usagers"] = bool(
            not type_usager_profile
            and not results["ctrl_par_usager_theme"].empty
        )
    else:
        results["_pdf_show_activite_usagers"] = False

    # Synthèse croisée par zone
    if options.get("synthese_croisee", False):
        zone_ctrl = spatial.get("zone_ctrl")
        zone_pve = spatial.get("zone_pve")
        zone_pej = spatial.get("zone_pej")
        if zone_ctrl is not None:
            synth = zone_ctrl[["zone", "nb_total", "nb_infraction"]].rename(
                columns={"nb_total": "ctrl_total", "nb_infraction": "ctrl_infraction"}
            )
            if zone_pve is not None:
                synth = synth.merge(zone_pve.rename(columns={"nb": "pve_nb"}), on="zone", how="left")
            if zone_pej is not None:
                synth = synth.merge(zone_pej.rename(columns={"nb": "pej_nb"}), on="zone", how="left")
            synth = synth.fillna(0)
            results["synthese_zone"] = synth

    # Copier les résultats spatiaux dans le dict principal
    for k in ("agg_pnf", "agg_pnf_detail", "zone_ctrl", "zone_pve", "zone_pej"):
        if k in spatial:
            results[k] = spatial[k]

    # PVe : top infractions (par NATINF) pour le tableau « Infractions les plus relevées »
    if not pve_filtered.empty:
        natinf_col = "INF-NATINF" if "INF-NATINF" in pve_filtered.columns else "NATINF"
        if natinf_col in pve_filtered.columns:
            top_pve = (
                pve_filtered[natinf_col]
                .astype(str)
                .str.strip()
                .replace("", pd.NA)
                .dropna()
                .value_counts()
                .head(10)
                .rename_axis("natinf")
                .reset_index(name="nb")
            )
            if not top_pve.empty:
                results["pve_top_infractions"] = top_pve

    # PEJ : top infractions (par NATINF) pour le tableau « Infractions les plus relevées »
    if not pej_filtered.empty:
        natinf_col = "NATINF_PEJ" if "NATINF_PEJ" in pej_filtered.columns else "NATINF"
        if natinf_col in pej_filtered.columns:
            top_pej = (
                pej_filtered[natinf_col]
                .astype(str)
                .str.strip()
                .replace("", pd.NA)
                .dropna()
                .value_counts()
                .head(10)
                .rename_axis("natinf")
                .reset_index(name="nb")
            )
            if not top_pej.empty:
                results["pej_top_infractions"] = top_pej

    # Agrégation annuelle ou trimestrielle (selon la durée de la période)
    if ventilation_mode == "annuelle":
        years: set[int] = set()
        if not point_filtered.empty and "date_ctrl" in point_filtered.columns:
            years |= set(
                point_filtered["date_ctrl"].dropna().dt.year.astype(int).tolist()
            )
        if not pej_filtered.empty and "DATE_REF" in pej_filtered.columns:
            years |= set(
                pej_filtered["DATE_REF"].dropna().dt.year.astype(int).tolist()
            )
        if not pa_filtered.empty and "DATE_REF" in pa_filtered.columns:
            years |= set(
                pa_filtered["DATE_REF"].dropna().dt.year.astype(int).tolist()
            )
        if not pve_filtered.empty and "INF-DATE-INTG" in pve_filtered.columns:
            years |= set(
                pve_filtered["INF-DATE-INTG"].dropna().dt.year.astype(int).tolist()
            )

        rows: list[dict[str, Any]] = []
        for year in sorted(years):
            year_row: dict[str, Any] = {"periode": str(year)}

            if not point_filtered.empty and "date_ctrl" in point_filtered.columns:
                p_year = point_filtered[point_filtered["date_ctrl"].dt.year == year]
                year_row["nb_controles"] = int(len(p_year))
                if "resultat" in p_year.columns:
                    year_row["nb_controles_non_conformes"] = int(
                        (p_year["resultat"] == "Infraction").sum()
                    )
                else:
                    year_row["nb_controles_non_conformes"] = 0
            else:
                year_row["nb_controles"] = 0
                year_row["nb_controles_non_conformes"] = 0

            if not pej_filtered.empty and "DATE_REF" in pej_filtered.columns:
                year_row["nb_pej"] = int(
                    (pej_filtered["DATE_REF"].dt.year == year).sum()
                )
            else:
                year_row["nb_pej"] = 0

            if not pa_filtered.empty and "DATE_REF" in pa_filtered.columns:
                year_row["nb_pa"] = int(
                    (pa_filtered["DATE_REF"].dt.year == year).sum()
                )
            else:
                year_row["nb_pa"] = 0

            if not pve_filtered.empty and "INF-DATE-INTG" in pve_filtered.columns:
                year_row["nb_pve"] = int(
                    (pve_filtered["INF-DATE-INTG"].dt.year == year).sum()
                )
            else:
                year_row["nb_pve"] = 0

            rows.append(year_row)

        if rows:
            yearly = pd.DataFrame(rows)
            yearly["taux_infraction_controles"] = yearly.apply(
                lambda r: (
                    (r["nb_controles_non_conformes"] / r["nb_controles"])
                    if r["nb_controles"] > 0
                    else pd.NA
                ),
                axis=1,
            )
            results["agg_annuelle"] = yearly
            results["ventilation_temporelle_type"] = "annuelle"

    elif ventilation_mode == "trimestrielle":
        # Trimestres : T1=janv-mars, T2=avr-juin, T3=juil-sept, T4=oct-déc
        periods: set[tuple[int, int]] = set()
        if not point_filtered.empty and "date_ctrl" in point_filtered.columns:
            for _, r in point_filtered["date_ctrl"].dropna().items():
                t = r
                if hasattr(t, "year") and hasattr(t, "month"):
                    q = (t.month - 1) // 3 + 1
                    periods.add((int(t.year), q))
        if not pej_filtered.empty and "DATE_REF" in pej_filtered.columns:
            for _, r in pej_filtered["DATE_REF"].dropna().items():
                t = r
                if hasattr(t, "year") and hasattr(t, "month"):
                    q = (t.month - 1) // 3 + 1
                    periods.add((int(t.year), q))
        if not pa_filtered.empty and "DATE_REF" in pa_filtered.columns:
            for _, r in pa_filtered["DATE_REF"].dropna().items():
                t = r
                if hasattr(t, "year") and hasattr(t, "month"):
                    q = (t.month - 1) // 3 + 1
                    periods.add((int(t.year), q))
        if not pve_filtered.empty and "INF-DATE-INTG" in pve_filtered.columns:
            for _, r in pve_filtered["INF-DATE-INTG"].dropna().items():
                t = r
                if hasattr(t, "year") and hasattr(t, "month"):
                    q = (t.month - 1) // 3 + 1
                    periods.add((int(t.year), q))

        rows_trim: list[dict[str, Any]] = []
        for (year, quarter) in sorted(periods):
            m1 = (quarter - 1) * 3 + 1
            m2 = quarter * 3
            row_t: dict[str, Any] = {"periode": f"{year}-T{quarter}"}

            if not point_filtered.empty and "date_ctrl" in point_filtered.columns:
                dt = point_filtered["date_ctrl"]
                mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
                row_t["nb_controles"] = int(mask.sum())
                if "resultat" in point_filtered.columns:
                    mask_inf = mask & (point_filtered["resultat"] == "Infraction")
                    row_t["nb_controles_non_conformes"] = int(mask_inf.sum())
                else:
                    row_t["nb_controles_non_conformes"] = 0
            else:
                row_t["nb_controles"] = 0
                row_t["nb_controles_non_conformes"] = 0

            if not pej_filtered.empty and "DATE_REF" in pej_filtered.columns:
                dt = pej_filtered["DATE_REF"]
                mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
                row_t["nb_pej"] = int(mask.sum())
            else:
                row_t["nb_pej"] = 0

            if not pa_filtered.empty and "DATE_REF" in pa_filtered.columns:
                dt = pa_filtered["DATE_REF"]
                mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
                row_t["nb_pa"] = int(mask.sum())
            else:
                row_t["nb_pa"] = 0

            if not pve_filtered.empty and "INF-DATE-INTG" in pve_filtered.columns:
                dt = pve_filtered["INF-DATE-INTG"]
                mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
                row_t["nb_pve"] = int(mask.sum())
            else:
                row_t["nb_pve"] = 0

            rows_trim.append(row_t)

        if rows_trim:
            trimestriel = pd.DataFrame(rows_trim)
            trimestriel["taux_infraction_controles"] = trimestriel.apply(
                lambda r: (
                    (r["nb_controles_non_conformes"] / r["nb_controles"])
                    if r["nb_controles"] > 0
                    else pd.NA
                ),
                axis=1,
            )
            results["agg_annuelle"] = trimestriel
            results["ventilation_temporelle_type"] = "trimestrielle"

    return results


def _export_csv(
    results: dict,
    point_filtered: pd.DataFrame,
    pej_filtered: pd.DataFrame,
    pa_filtered: pd.DataFrame,
    pve_filtered: pd.DataFrame,
    out_dir: Path,
    profile: dict,
) -> None:
    """Exporte tous les CSV dans le dossier de sortie."""
    profil_id = profile["id"]
    prefix = profile.get("_export_prefix") or profil_id
    # Points filtrés
    if not point_filtered.empty:
        cols = [c for c in [
            "fid", "dc_id", "nom_dossie", "nom_dossier", "date_ctrl", "num_depart",
            "nom_commun", "insee_comm", "dr", "entit_ctrl",
            "type_usage", "domaine", "theme", "type_actio", "type_action",
            "fc_type", "resultat", "code_pej", "code_pa", "natinf_pej", "x", "y", "PNF",
            "pnf_zone_sig",
        ] if c in point_filtered.columns]
        point_filtered[cols].to_csv(
            out_dir / f"controles_{prefix}_points.csv", sep=";", index=False
        )

    # Résultats
    if "tab_resultats" in results:
        results["tab_resultats"].to_csv(
            out_dir / f"controles_{prefix}_resultats.csv", sep=";", index=False
        )

    # Par thème
    if "agg_theme" in results:
        results["agg_theme"].to_csv(
            out_dir / f"controles_{prefix}_par_theme.csv", sep=";", index=False
        )

    # Par commune
    if "agg_commune" in results:
        results["agg_commune"].to_csv(
            out_dir / f"indicateurs_{prefix}_par_commune.csv", sep=";", index=False
        )

    # Zones
    for key, name in [
        ("zone_ctrl", f"controles_{prefix}_par_zone.csv"),
        ("zone_pve", f"pve_{prefix}_par_zone.csv"),
        ("zone_pej", f"pej_{prefix}_par_zone.csv"),
    ]:
        if key in results:
            results[key].to_csv(out_dir / name, sep=";", index=False)

    # PNF
    if "agg_pnf" in results:
        results["agg_pnf"].to_csv(
            out_dir / f"indicateurs_{prefix}_par_pnf.csv", sep=";", index=False
        )
    if "agg_pnf_detail" in results:
        results["agg_pnf_detail"].to_csv(
            out_dir / f"indicateurs_{prefix}_pnf_ensemble_coeur.csv", sep=";", index=False
        )

    # PEJ
    if not pej_filtered.empty:
        cols = [c for c in [
            "DC_ID", "DATE_REF", "NATINF_PEJ", "DOMAINE", "THEME",
            "TYPE_ACTION", "DUREE_PEJ", "CLOTUR_PEJ", "SUITE",
            "ENTITE_ORIGINE_PROCEDURE",
        ] if c in pej_filtered.columns]
        if cols:
            pej_filtered[cols].to_csv(
                out_dir / f"pej_{prefix}.csv", sep=";", index=False
            )
    if "pej_par_theme" in results:
        results["pej_par_theme"].to_csv(
            out_dir / f"pej_{prefix}_par_theme.csv", sep=";", index=False
        )

    # PA
    if not pa_filtered.empty:
        pa_filtered.to_csv(out_dir / f"pa_{prefix}.csv", sep=";", index=False)
    if "pa_par_theme" in results:
        results["pa_par_theme"].to_csv(
            out_dir / f"pa_{prefix}_par_theme.csv", sep=";", index=False
        )

    # PVe
    if not pve_filtered.empty:
        pve_filtered.to_csv(out_dir / f"pve_{prefix}.csv", sep=";", index=False)

    # Synthèse croisée
    if "synthese_zone" in results:
        results["synthese_zone"].to_csv(
            out_dir / f"synthese_{prefix}_par_zone.csv", sep=";", index=False
        )

    # Agrégation temporelle (annuelle ou trimestrielle)
    vent_type = results.get("ventilation_temporelle_type")
    if "agg_annuelle" in results and isinstance(results["agg_annuelle"], pd.DataFrame):
        if vent_type == "trimestrielle":
            results["agg_annuelle"].to_csv(
                out_dir / f"indicateurs_{prefix}_par_trimestre.csv", sep=";", index=False
            )
        else:
            results["agg_annuelle"].to_csv(
                out_dir / f"indicateurs_{prefix}_par_annee.csv", sep=";", index=False
            )

    # PEJ durée (procedures)
    if "pej_duree_resume" in results:
        pd.DataFrame([results["pej_duree_resume"]]).to_csv(
            out_dir / "pej_duree_resume.csv", sep=";", index=False
        )
    if "pej_clotur" in results:
        results["pej_clotur"].to_csv(out_dir / "pej_clotur_global.csv", sep=";", index=False)
    if "pej_suite" in results:
        results["pej_suite"].to_csv(out_dir / "pej_suite_global.csv", sep=";", index=False)
    for grp in ("theme", "domaine"):
        k = f"pej_par_{grp}"
        if k in results:
            results[k].to_csv(out_dir / f"pej_duree_par_{grp}.csv", sep=";", index=False)

    # Types d'usagers
    for key, name in [
        ("usager_effectifs", f"controles_global_par_usager.csv"),
        ("usager_par_domaine", f"controles_global_usager_par_domaine.csv"),
        ("ctrl_par_usager_domaine", f"controles_par_type_usager_domaine.csv"),
        ("ctrl_par_usager_theme", f"controles_par_type_usager_theme.csv"),
        ("res_par_usager_domaine", f"resultats_par_type_usager_domaine.csv"),
        ("res_par_usager_theme", f"resultats_par_type_usager_theme.csv"),
        ("res_bilan_par_type_usager", f"resultats_bilan_par_type_usager.csv"),
        ("proc_par_usager_domaine", f"procedures_par_type_usager_domaine.csv"),
        ("proc_par_usager_theme", f"procedures_par_type_usager_theme.csv"),
    ]:
        if key in results and isinstance(results[key], pd.DataFrame) and not results[key].empty:
            results[key].to_csv(out_dir / name, sep=";", index=False)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Génération PDF
# ═══════════════════════════════════════════════════════════════════════════


def _pct_table_cell(n: int | float, denom: float) -> str:
    if denom is None or denom <= 0:
        return "n.d."
    return f"{100.0 * float(n) / float(denom):.1f} %"


def _pdf_section_activite_par_types_usagers(
    builder: Any,
    results: dict,
    tmp_dir: Path,
    avail_w: float,
    *,
    pie_ratio: float,
    bar_ratio: float,
) -> None:
    """Section VIII : activité par types d'usagers (camembert, tableaux par type, barres horizontales empilées)."""
    ctrl_ut = results.get("ctrl_par_usager_theme")
    if ctrl_ut is None or ctrl_ut.empty:
        return

    total_ctrl_lignes = float(ctrl_ut["nb_controles"].sum()) or 1.0
    sum_par_type = ctrl_ut.groupby("type_usager")["nb_controles"].sum()

    # 1) Camembert : même modèle que « Répartition des résultats » (chart_pie par défaut + ratio PDF identique).
    pie_data = {str(k): int(v) for k, v in sum_par_type.items()}
    if pie_data:
        pie_path = chart_pie(
            pie_data,
            "Répartition des contrôles par type d'usager",
            tmp_dir,
            "pie_controles_par_type_usager.png",
        )
        builder.add_image(Path(pie_path), width_ratio=pie_ratio)

    # 2) Un tableau par type d'usager : thèmes (nb + % du total général + % du sous-total type)
    type_order = sum_par_type.sort_values(ascending=False).index
    first_tbl = True
    for tu in type_order:
        tu_s = str(tu)
        sub = ctrl_ut[ctrl_ut["type_usager"].astype(str) == tu_s].copy()
        if sub.empty:
            continue
        sub = sub.sort_values("nb_controles", ascending=False, kind="stable")
        st = float(sum_par_type.loc[tu]) if tu in sum_par_type.index else 1.0
        st = st or 1.0
        tbl_th = [
            ["Thème", "Nombre", "% du total général", "% du sous-total (type)"],
        ]
        for _, r in sub.iterrows():
            nb = int(r["nb_controles"])
            tbl_th.append(
                [
                    str(r["theme"]),
                    str(nb),
                    _pct_table_cell(nb, total_ctrl_lignes),
                    _pct_table_cell(nb, st),
                ]
            )
        if not first_tbl:
            builder.add_spacer(4)
        first_tbl = False
        builder.add_table(
            tbl_th,
            caption=f"Thèmes de contrôle — {tu_s}",
            col_widths=[
                avail_w * 0.40,
                avail_w * 0.14,
                avail_w * 0.23,
                avail_w * 0.23,
            ],
            col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"],
            keep_together=True,
        )

    # 3) Sous-partie : résultats des contrôles par type d'usager (graphique + tableau)
    rb = results.get("res_bilan_par_type_usager")
    if rb is not None and not rb.empty:
        builder.add_paragraph("Résultats des contrôles par type d'usager", style="Heading2")
        labels = [str(x) for x in rb["type_usager"].tolist()]
        series: dict[str, list[int]] = {
            "Conforme": [int(x) for x in rb["Conforme"].tolist()],
            "Infraction": [int(x) for x in rb["Infraction"].tolist()],
            "Manquement": [int(x) for x in rb["Manquement"].tolist()],
        }
        if int(rb["Autre"].sum()) > 0:
            series["Autre"] = [int(x) for x in rb["Autre"].tolist()]
        bar_path = chart_bar_horizontal_stacked(
            labels,
            series,
            "Résultats des contrôles par type d'usager",
            "Nombre",
            tmp_dir,
            "bar_resultats_par_type_usager.png",
        )
        builder.add_image(Path(bar_path), width_ratio=bar_ratio)
        # Tableau chiffré + pourcentages (part de chaque résultat dans le type,
        # et poids du type dans le total de cette sous-partie).
        has_autre = int(rb["Autre"].sum()) > 0
        total_global = float(
            rb["Conforme"].sum() + rb["Infraction"].sum() + rb["Manquement"].sum() + rb["Autre"].sum()
        ) or 1.0
        tbl_res = [
            [
                "Type d'usager",
                "Conforme",
                "% conforme",
                "Infraction",
                "% infraction",
                "Manquement",
                "% manquement",
                *(
                    ["Autre", "% autre"]
                    if has_autre
                    else []
                ),
                "Total",
                "% du total",
            ]
        ]
        for _, row in rb.iterrows():
            c = int(row["Conforme"])
            i = int(row["Infraction"])
            m = int(row["Manquement"])
            a = int(row["Autre"]) if has_autre else 0
            t = c + i + m + a
            row_cells = [
                str(row["type_usager"]),
                str(c),
                _pct_table_cell(c, t),
                str(i),
                _pct_table_cell(i, t),
                str(m),
                _pct_table_cell(m, t),
            ]
            if has_autre:
                row_cells.extend([str(a), _pct_table_cell(a, t)])
            row_cells.extend([str(t), _pct_table_cell(t, total_global)])
            tbl_res.append(row_cells)
        if has_autre:
            col_widths = [
                avail_w * 0.20,
                avail_w * 0.08, avail_w * 0.10,
                avail_w * 0.08, avail_w * 0.10,
                avail_w * 0.08, avail_w * 0.10,
                avail_w * 0.07, avail_w * 0.08,
                avail_w * 0.06, avail_w * 0.05,
            ]
        else:
            col_widths = [
                avail_w * 0.21,
                avail_w * 0.09, avail_w * 0.11,
                avail_w * 0.09, avail_w * 0.11,
                avail_w * 0.09, avail_w * 0.11,
                avail_w * 0.09, avail_w * 0.10,
            ]
        builder.add_table(
            tbl_res,
            caption="Résultats des contrôles par type d'usager (chiffres et pourcentages)",
            col_widths=col_widths,
            col_aligns=["LEFT"] + ["RIGHT"] * (len(tbl_res[0]) - 1),
            keep_together=True,
        )


def _generate_pdf(
    results: dict,
    out_dir: Path,
    profile: dict,
    cfg: BilanConfig,
    options: dict,
) -> None:
    """Génère le PDF du bilan avec des sections modulaires."""
    profil_id = profile["id"]
    label = profile["label"]
    sources = profile.get("sources", {}) or {}
    dept_name = cfg.dept_name
    period_str = f"du {cfg.date_deb.date():%d/%m/%Y} au {cfg.date_fin.date():%d/%m/%Y}"

    # Pour le bilan usager ciblé (mono-usager), nommage Bilan_{type_usager} et titres avec le libellé
    single_cfg = profile.get("_single_usager") or {}
    is_single_usager = bool(single_cfg.get("enabled"))
    single_label = str(single_cfg.get("label", "")).strip()
    export_prefix = profile.get("_export_prefix") or profil_id
    display_label = single_label if (is_single_usager and single_label) else label

    safe_name = dept_name.replace(" ", "_").replace("'", "")
    pdf_path = out_dir / f"{export_prefix}_{safe_name}.pdf"
    builder = PDFReportBuilder(
        pdf_path=pdf_path,
        header_title=f"Bilan thématique – {display_label}",
        title=f"Bilan thématique – {display_label}",
        author="Office français de la biodiversité",
    )
    avail_w = builder.avail_w
    tmp_dir = builder.tmp_dir
    chart_preset = options.get("chart_preset")
    chart_ratios = compute_pdf_ratios(load_chart_display_config(PROJECT_ROOT, preset=chart_preset))
    chart_ratio_base = chart_ratios["chart_base"]

    # Correspondance code INSEE → nom de commune pour les tableaux PDF
    insee_to_nom = load_communes_noms(PROJECT_ROOT)

    def _nom_commune(code) -> str:
        return insee_to_nom.get(str(code).strip().zfill(5), str(code))

    # Compteurs
    nb_ctrl = results.get("nb_ctrl", 0)
    nb_pej = results.get("nb_pej", 0)
    nb_pa = results.get("nb_pa", 0)
    nb_pve = results.get("nb_pve", 0)
    tab_resultats = results.get("tab_resultats")
    is_type_usager = profile.get("analyses", {}).get("type_usager", False)
    is_procedures = profile["filter"]["type"] == "procedures"
    # single_cfg / is_single_usager / single_label déjà définis plus haut

    # Sommaire dynamique
    sections = []
    sec_num = 0

    def _next_sec(title: str) -> tuple[str, str]:
        nonlocal sec_num
        sec_num += 1
        anchor = f"sec{sec_num}"
        sections.append((anchor, f"{_roman(sec_num)}. {title}"))
        return anchor, f"{_roman(sec_num)}. {title}"

    # Organisation spécifique du sommaire pour le profil agrainage,
    # afin de se rapprocher de l'ancien modèle dédié.
    #
    # Remarque : l'analyse par zone est une sous-partie logique des contrôles
    # agrainage, elle ne crée donc pas de section de niveau I/II/III propre
    # dans le sommaire. Elle apparaît comme sous-titre dans le corps du texte.
    if profil_id == "agrainage":
        if nb_ctrl > 0 or not is_procedures:
            _next_sec("Chiffres clés")
        if nb_ctrl > 0 and not is_type_usager and not is_procedures:
            _next_sec("Contrôles agrainage")
        if results.get("agg_annuelle") is not None:
            _next_sec("Analyse de l'ensemble de la période du bilan")
        if is_type_usager and nb_ctrl > 0:
            _next_sec("Contrôles par type d'usager")
        if nb_pve > 0:
            _next_sec("Infractions PVe")
        if nb_pej > 0:
            _next_sec("Procédures judiciaires (PEJ)")
        if nb_pa > 0:
            _next_sec("Procédures administratives (PA)")
        if results.get("agg_pnf") is not None:
            # Pour l'agrainage, la section regroupe les zones PNF et TUB
            _next_sec("Zones d'intérêt")
        # Pas de _next_sec(\"Analyse par zone\") ici : l'analyse par zone est
        # intégrée dans la section \"Contrôles agrainage\".
        if results.get("synthese_zone") is not None:
            _next_sec("Synthèse par zone")
        if results.get("_pdf_show_activite_usagers"):
            _next_sec("Activité par types d'usagers")
        if options.get("cartes", False):
            _next_sec("Cartographie")
        _next_sec("Annexes")
    else:
        if nb_ctrl > 0 or not is_procedures:
            _next_sec("Chiffres clés")
        if results.get("agg_annuelle") is not None:
            _next_sec("Analyse de l'ensemble de la période du bilan")
        if nb_ctrl > 0 and not is_type_usager and not is_procedures:
            _next_sec("Résultats des contrôles")
        if is_type_usager and nb_ctrl > 0:
            _next_sec("Contrôles par type d'usager")
        if nb_pve > 0:
            _next_sec("Procès-verbaux électroniques (PVe)")
        if nb_pej > 0:
            _next_sec("Procédures d'enquête judiciaire (PEJ)")
        if nb_pa > 0:
            _next_sec("Procédures administratives (PA)")
        if results.get("agg_pnf") is not None:
            # Bilan thématique PNF : périmètre déjà restreint au parc — pas de « Hors PNF ».
            if str(profil_id).strip().lower() in {"pnf", "pnf_foret"}:
                _next_sec("Contrôles – Ensemble PNF et Cœur de parc")
            else:
                _next_sec("PNF / Hors PNF")
        if results.get("zone_ctrl") is not None and options.get("tub", False):
            _next_sec("Analyse par zone")
        if results.get("synthese_zone") is not None:
            _next_sec("Synthèse croisée par zone")
        if results.get("_pdf_show_activite_usagers"):
            _next_sec("Activité par types d'usagers")
        if options.get("cartes", False):
            _next_sec("Cartographie")
        _next_sec("Annexes")

    # Page de garde + sommaire
    # Préparer un libellé de thème sans doublon "Bilan "
    main_label = label
    if main_label.lower().startswith("bilan "):
        main_label = main_label[6:].strip()

    # Pour le profil "types_usager_cible", la page de garde doit afficher
    # les types d'usagers sélectionnés par l'utilisateur.
    if profil_id == "types_usager_cible":
        targets = (profile.get("filter", {}) or {}).get("type_usager_target") or []
        targets = [str(t).strip() for t in targets if str(t).strip()]
        if targets:
            if len(targets) == 1:
                main_label = targets[0]
            elif len(targets) == 2:
                main_label = f"{targets[0]} et {targets[1]}"
            else:
                main_label = ", ".join(targets[:-1]) + f" et {targets[-1]}"

    subtitle_sources = "Sources des données : OFB/OSCEAN"
    if nb_pve > 0:
        subtitle_sources += " – MININT/AGC-PVe"

    builder.add_title_page(
        title_lines=[f"Bilan thématique : {main_label}", f"pour la {dept_name}"],
        period_str=f"Période : {period_str}",
        subtitle=subtitle_sources,
    )
    builder.add_toc(sections)

    # ── CHIFFRES CLÉS ──
    sec_idx = 0
    if nb_ctrl > 0 or not is_procedures:
        anchor, title = sections[sec_idx]; sec_idx += 1
        builder.add_section(anchor, title)
        kf = []
        if nb_ctrl > 0:
            kf.append((str(nb_ctrl), "Localisations de contrôle"))
        if tab_resultats is not None and "Infraction" in tab_resultats["resultat"].values:
            nb_inf = int(tab_resultats.loc[tab_resultats["resultat"] == "Infraction", "nb"].sum())
            taux = nb_inf / nb_ctrl if nb_ctrl else 0
            # Nombre de contrôles dont le résultat est "Infraction"
            kf.append((str(nb_inf), "Contrôles non-conformes"))
            kf.append((f"{taux:.1%}", "Taux d'infraction"))
        if nb_pej > 0:
            # Procédures judiciaires issues des contrôles
            kf.append((str(nb_pej), "Nombre de procédures judiciaires"))
        if nb_pa > 0:
            kf.append((str(nb_pa), "PA"))
        if nb_pve > 0:
            # Infractions relevées par procès-verbal électronique
            kf.append((str(nb_pve), "Nombre d'infractions relevées par PVe"))
        # En mode \"types d'usagers\", ajouter un indicateur complémentaire :
        # somme des effectifs d'usagers contrôlés (peut dépasser nb_ctrl).
        if is_type_usager:
            ue = results.get("usager_effectifs")
            if ue is not None and not ue.empty and "nb" in ue.columns:
                total_usagers = int(ue["nb"].sum())
                if is_single_usager and single_label:
                    kf.append((str(total_usagers), f"Effectifs – {single_label}"))
                else:
                    kf.append((str(total_usagers), "Effectifs d'usagers contrôlés"))
        if is_procedures and "pej_duree_resume" in results:
            dr = results["pej_duree_resume"]
            kf.append((str(dr["nb_pej"]), "PEJ"))
            kf.append((f"{dr['duree_moy_j']} j", "Durée moyenne"))
            kf.append((f"{dr['duree_mediane_j']} j", "Durée médiane"))
        builder.add_key_figures(kf)

    # ── ANALYSE DE L'ENSEMBLE DE LA PÉRIODE DU BILAN ──
    agg_annuelle = results.get("agg_annuelle")
    vent_temp_type = results.get("ventilation_temporelle_type", "annuelle")
    if isinstance(agg_annuelle, pd.DataFrame) and not agg_annuelle.empty:
        anchor, title = sections[sec_idx]; sec_idx += 1
        builder.add_section(anchor, title)
        is_trim = vent_temp_type == "trimestrielle"
        texte_vent = "par trimestre " if is_trim else "par année "
        builder.add_paragraph(
            "Ventilation des principaux indicateurs " + texte_vent
            + "sur l'ensemble de la période du bilan."
        )
        label_col = "Trimestre" if is_trim else "Année"
        tbl = [[
            label_col,
            "Nb contrôles",
            "Contrôles non-conformes",
            "Taux d'infraction",
            "PEJ",
            "PA",
            "PVe",
        ]]
        for _, row in agg_annuelle.iterrows():
            taux = (
                f"{row['taux_infraction_controles']:.1%}"
                if pd.notna(row.get("taux_infraction_controles"))
                else "n.d."
            )
            tbl.append([
                str(row["periode"]),
                str(int(row["nb_controles"])),
                str(int(row["nb_controles_non_conformes"])),
                taux,
                str(int(row["nb_pej"])),
                str(int(row["nb_pa"])),
                str(int(row["nb_pve"])),
            ])
        builder.add_table(
            tbl,
            caption="Indicateurs " + ("trimestriels" if is_trim else "annuels"),
            col_widths=[
                avail_w * 0.12,
                avail_w * 0.14,
                avail_w * 0.18,
                avail_w * 0.14,
                avail_w * 0.14,
                avail_w * 0.14,
                avail_w * 0.14,
            ],
            col_aligns=["RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"],
        )

        period_labels = [str(v) for v in agg_annuelle["periode"].tolist()]
        titre_ctrl = "Contrôles par trimestre (conformes / non-conformes)" if is_trim else "Contrôles par année (conformes / non-conformes)"
        titre_proc = "Procédures et PVe par trimestre" if is_trim else "Procédures et PVe par année"

        # Graphique 1 : barres empilées — contrôles conformes vs non-conformes
        conformes = [
            int(row["nb_controles"]) - int(row["nb_controles_non_conformes"])
            for _, row in agg_annuelle.iterrows()
        ]
        non_conformes = [int(v) for v in agg_annuelle["nb_controles_non_conformes"].tolist()]
        stacked_ctrl = {
            "Conformes": conformes,
            "Non-conformes": non_conformes,
        }
        stacked_path = chart_bar_stacked(
            period_labels, stacked_ctrl,
            titre_ctrl,
            "Nombre de contrôles",
            tmp_dir, "bar_annuel_ctrl_stacked.png",
        )
        builder.add_image(Path(stacked_path), width_ratio=chart_ratio_base)

        # Graphique 2 : barres empilées — procédures et PVe par période
        series_proc = {
            "PEJ": [int(v) for v in agg_annuelle["nb_pej"].tolist()],
            "PA": [int(v) for v in agg_annuelle["nb_pa"].tolist()],
            "PVe": [int(v) for v in agg_annuelle["nb_pve"].tolist()],
        }
        has_proc = any(sum(vals) > 0 for vals in series_proc.values())
        if has_proc:
            stacked_proc_path = chart_bar_stacked(
                period_labels, series_proc,
                titre_proc,
                "Nombre",
                tmp_dir, "bar_annuel_proc_stacked.png",
            )
            builder.add_image(Path(stacked_proc_path), width_ratio=chart_ratio_base)

        # Graphique 3 : courbe d'évolution — taux d'infraction
        taux_values = []
        for _, row in agg_annuelle.iterrows():
            val = row.get("taux_infraction_controles")
            taux_values.append(round(float(val) * 100, 1) if pd.notna(val) else 0)
        if any(v > 0 for v in taux_values):
            line_path = chart_line_evolution(
                period_labels,
                {"Taux d'infraction (%)": taux_values},
                "Évolution du taux d'infraction",
                "Taux (%)",
                tmp_dir, "line_annuel_taux_inf.png",
            )
            # Graphique plus compact pour libérer de la place pour le tableau
            # et le camembert des résultats sur la même page.
            builder.add_image(Path(line_path), width_ratio=chart_ratio_base)

    # ── RÉSULTATS DES CONTRÔLES ──
    if nb_ctrl > 0 and not is_type_usager and not is_procedures:
        anchor, title = sections[sec_idx]; sec_idx += 1
        builder.add_section(anchor, title)
        # Pour le profil agrainage, expliciter la source et le filtrage des contrôles.
        if profil_id == "agrainage":
            builder.add_paragraph(
                "Contrôles liés à l’agrainage identifiés dans les points de contrôle OSCEAN "
                "(champ « nom_dossie » ou « nom_dossier » contenant « agrain »)."
            )
        if tab_resultats is not None:
            tbl = [["Résultat", "Nombre", "Taux"]]
            for _, row in tab_resultats.iterrows():
                t = f"{row['taux']:.1%}" if pd.notna(row.get("taux")) else "n.d."
                tbl.append([str(row["resultat"]), str(int(row["nb"])), t])
            builder.add_table(tbl, caption="Résultats des contrôles",
                              col_widths=[avail_w * 0.50, avail_w * 0.25, avail_w * 0.25],
                              col_aligns=["LEFT", "RIGHT", "RIGHT"])
            pie_data = {str(r["resultat"]): int(r["nb"]) for _, r in tab_resultats.iterrows()}
            if pie_data:
                pie_path = chart_pie(
                    pie_data,
                    "Répartition des résultats",
                    tmp_dir,
                    "pie_resultats.png",
                )
                # Légère augmentation pour un meilleur confort de lecture,
                # tout en restant assez compact pour tenir sur la même page.
                builder.add_image(Path(pie_path), width_ratio=chart_ratios["global_resultats_pie"])
        # Tableau des communes : suite directe sous le camembert (même page si place).
        if "agg_commune" in results:
            top = results["agg_commune"].sort_values("nb_controles", ascending=False).head(10)
            tbl = [["Commune", "Nb contrôles", "Contrôles non-conformes", "Taux d'infraction"]]
            for _, row in top.iterrows():
                t = f"{row['taux_infraction']:.1%}" if pd.notna(row.get("taux_infraction")) else "n.d."
                code_insee = row.iloc[0]
                tbl.append([_nom_commune(code_insee), str(int(row["nb_controles"])),
                            str(int(row["nb_infractions"])), t])
            builder.add_table(tbl, caption="Communes avec le plus de contrôles",
                              col_widths=[avail_w * 0.25] * 4,
                              col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"])
        # On ne force pas systématiquement un saut de page ici : la section
        # suivante (types d'usagers ou procédures) pourra commencer sur la
        # même page si l'espace le permet.

    # ── TYPES D'USAGERS ──
    if is_type_usager and nb_ctrl > 0:
        anchor, title = sections[sec_idx]; sec_idx += 1
        builder.add_section(anchor, title)

        # Multi-usagers : architecture complète (tableau + camembert + colonnes type_usager)
        if not is_single_usager:
            ue = results.get("usager_effectifs")
            if ue is not None and not ue.empty:
                tbl = [["Type d'usager", "Effectifs"]]
                for _, row in ue.iterrows():
                    tbl.append([str(row["type_usager"]), str(int(row["nb"]))])
                builder.add_table(tbl, caption="Effectifs d'usagers par catégorie",
                                  col_widths=[avail_w * 0.65, avail_w * 0.35],
                                  col_aligns=["LEFT", "RIGHT"])
                pie_data = {str(r["type_usager"]): int(r["nb"]) for _, r in ue.iterrows()}
                if pie_data:
                    pie_path = chart_pie(pie_data, "Usagers contrôlés par type", tmp_dir, "pie_usagers.png")
                    builder.add_image(Path(pie_path), width_ratio=chart_ratios["global_usagers_pie"])
        else:
            # Mono-usager : l'effectif du type ciblé est déjà mis en avant
            # dans les chiffres clés (tuile \"Effectifs – <type>\").
            # On évite donc un tableau redondant à une seule ligne ici.
            pass

        # Tableau \"Usagers × Domaine\" (multi uniquement).
        # En mono-usager, ce tableau n'est pas pertinent visuellement.
        if not is_single_usager:
            ud = results.get("usager_par_domaine")
            if ud is not None and not ud.empty:
                df_ud = ud.copy()
                tbl = [list(df_ud.columns)]
                for _, row in df_ud.head(20).iterrows():
                    tbl.append([str(v) for v in row.values])
                n_cols = len(df_ud.columns)
                col_aligns = ["LEFT"] + ["RIGHT"] * (n_cols - 1)
                builder.add_table(
                    tbl,
                    caption="Usagers × Domaine",
                    col_aligns=col_aligns,
                    wide_headers=True,
                )

        # Résultats des contrôles pour l'usager ciblé (tableau + camembert)
        # (placés avant les tableaux \"par domaine\")
        tab_resultats = results.get("tab_resultats")
        if tab_resultats is not None and not tab_resultats.empty:
            cap_res = "Résultats des contrôles"
            if is_single_usager and single_label:
                cap_res = f"{cap_res} – {single_label}"
            else:
                cap_res = f"{cap_res} (usager ciblé)"
            tbl = [["Résultat", "Nombre", "Taux"]]
            for _, row in tab_resultats.iterrows():
                t = f"{row['taux']:.1%}" if pd.notna(row.get("taux")) else "n.d."
                tbl.append([str(row["resultat"]), str(int(row["nb"])), t])
            builder.add_table(
                tbl,
                caption=cap_res,
                col_widths=[avail_w * 0.50, avail_w * 0.25, avail_w * 0.25],
                col_aligns=["LEFT", "RIGHT", "RIGHT"],
            )
            pie_data = {str(r["resultat"]): int(r["nb"]) for _, r in tab_resultats.iterrows()}
            if pie_data:
                pie_path = chart_pie(
                    pie_data,
                    "Répartition des résultats",
                    tmp_dir,
                    "pie_resultats_usager.png",
                )
                builder.add_image(Path(pie_path), width_ratio=chart_ratios["global_resultats_pie"])

        # Résultats des contrôles par domaine (top 15)
        res_ud = results.get("res_par_usager_domaine")
        if res_ud is not None and not res_ud.empty:
            # Tableau potentiellement haut : on limite un peu le nombre de lignes
            # et on le garde en un seul bloc sur la page.
            df_res = res_ud.sort_values("nb_controles", ascending=False).head(12).copy()
            if is_single_usager and "type_usager" in df_res.columns and df_res["type_usager"].nunique() == 1:
                df_res = df_res.drop(columns=["type_usager"])
                hdr = ["Domaine", "Nb contrôles", "Infractions", "Manquements"]
                caption = "Résultats des contrôles par domaine (top 15)"
            else:
                hdr = ["Type d'usager", "Domaine", "Nb contrôles", "Infractions", "Manquements"]
                caption = "Résultats des contrôles par type d'usager et par domaine (top 15)"
            tbl = [hdr]
            for _, row in df_res.iterrows():
                base = [
                    str(row.get("domaine", "")),
                    str(int(row.get("nb_controles", 0))),
                    str(int(row.get("nb_infraction", 0))),
                    str(int(row.get("nb_manquement", 0))),
                ]
                if len(hdr) == 5:
                    tbl.append([str(row.get("type_usager", "")), *base])
                else:
                    tbl.append(base)
            cw = (
                [avail_w * 0.30, avail_w * 0.23, avail_w * 0.15, avail_w * 0.16, avail_w * 0.16]
                if len(hdr) == 5
                else [avail_w * 0.34, avail_w * 0.22, avail_w * 0.22, avail_w * 0.22]
            )
            ca = (
                ["LEFT", "LEFT", "RIGHT", "RIGHT", "RIGHT"]
                if len(hdr) == 5
                else ["LEFT", "RIGHT", "RIGHT", "RIGHT"]
            )
            builder.add_table(
                tbl,
                caption=caption,
                col_widths=cw,
                col_aligns=ca,
                keep_together=True,
            )

        # Communes avec le plus de contrôles (usager ciblé)
        if options.get("par_commune", True) and "agg_commune" in results and not results["agg_commune"].empty:
            top = results["agg_commune"].sort_values("nb_controles", ascending=False).head(10)
            cap_comm = "Communes avec le plus de contrôles (usager ciblé)"
            if is_single_usager and single_label:
                cap_comm = f"Communes avec le plus de contrôles – {single_label}"
            tbl = [["Commune", "Nb contrôles", "Contrôles non-conformes", "Taux d'infraction"]]
            for _, row in top.iterrows():
                t = f"{row['taux_infraction']:.1%}" if pd.notna(row.get("taux_infraction")) else "n.d."
                code_insee = row.iloc[0]
                tbl.append([_nom_commune(code_insee), str(int(row["nb_controles"])),
                            str(int(row["nb_infractions"])), t])
            builder.add_table(tbl, caption=cap_comm,
                              col_widths=[avail_w * 0.25] * 4,
                              col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"])

        # Procédures par domaine (PJ, PA, PVe)
        proc_ud = results.get("proc_par_usager_domaine")
        if proc_ud is not None and not proc_ud.empty:
            df_proc = proc_ud.copy()
            cap_proc = "Procédures par type d'usager et par domaine"
            if is_single_usager and "type_usager" in df_proc.columns and df_proc["type_usager"].nunique() == 1:
                df_proc = df_proc.drop(columns=["type_usager"])
                cap_proc = "Procédures par domaine"
            cols = [c for c in ["domaine", "nb_pj", "nb_pa", "nb_pve"] if c in df_proc.columns]
            if cols:
                tbl = [[c.replace("_", " ").title() for c in cols]]
                for _, row in df_proc.head(15).iterrows():
                    tbl.append([str(int(row[c])) if c in ("nb_pj", "nb_pa", "nb_pve") else str(row.get(c, "")) for c in cols])
                builder.add_table(tbl, caption=cap_proc, keep_together=True)

        # Procédures par thème (PJ, PA, PVe)
        proc_ut = results.get("proc_par_usager_theme")
        if proc_ut is not None and not proc_ut.empty:
            df_proc = proc_ut.copy()
            cap_proc = "Procédures par type d'usager et par thème"
            if is_single_usager and "type_usager" in df_proc.columns and df_proc["type_usager"].nunique() == 1:
                df_proc = df_proc.drop(columns=["type_usager"])
                cap_proc = "Procédures par thème"
            cols = [c for c in ["theme", "nb_pj", "nb_pa", "nb_pve"] if c in df_proc.columns]
            if cols:
                tbl = [[c.replace("_", " ").title() for c in cols]]
                for _, row in df_proc.head(15).iterrows():
                    tbl.append([str(int(row[c])) if c in ("nb_pj", "nb_pa", "nb_pve") else str(row.get(c, "")) for c in cols])
                builder.add_table(tbl, caption=cap_proc, keep_together=True)

        # Section dense : on conserve un saut de page dédié.

    # ── PVe ──
    if nb_pve > 0:
        anchor, title = sections[sec_idx]; sec_idx += 1
        builder.add_section(anchor, title, compact=True)
        pve_top = results.get("pve_top_infractions")
        if pve_top is not None and not pve_top.empty:
            natinf_ref = load_natinf_ref(PROJECT_ROOT)
            top_df = pve_top.copy()
            top_df["numero_natinf"] = top_df["natinf"].astype(str).str.extract(r"(\d+)", expand=False)
            if not natinf_ref.empty:
                top_df = top_df.merge(natinf_ref, on="numero_natinf", how="left")
            def _fmt_natinf_row(r):
                qualif = str(r.get("qualification_infraction") or "").strip()
                nature_raw = str(r.get("nature_infraction") or "").strip()
                # Convertir "Contravention de classe X" en "CX"
                nature = nature_raw
                if nature_raw.lower().startswith("contravention de classe "):
                    num = nature_raw[len("contravention de classe "):].strip()
                    nature = f"C{num}" if num else nature_raw
                if qualif and nature:
                    return f"{qualif} ({nature})"
                if qualif:
                    return qualif
                if nature:
                    return nature
                lib = str(r.get("libelle_natinf") or "").strip()
                return lib if lib else str(r["natinf"])
            top_df["libelle_affich"] = top_df.apply(_fmt_natinf_row, axis=1)
            tbl_infractions = [["Infraction (qualification et nature)", "Nombre"]]
            for _, row in top_df.iterrows():
                tbl_infractions.append([str(row["libelle_affich"]), str(int(row["nb"]))])
            builder.add_key_figures_and_table(
                [(str(nb_pve), "PVe")],
                tbl_infractions,
                caption="Infractions les plus relevées",
                col_widths=[avail_w * 0.75, avail_w * 0.25],
                col_aligns=["LEFT", "RIGHT"],
            )
        else:
            builder.add_key_figures([(str(nb_pve), "PVe")])
        zone_pve = results.get("zone_pve")
        if zone_pve is not None:
            tbl = [["Zone", "Nombre"]]
            for _, row in zone_pve.iterrows():
                tbl.append([str(row["zone"]), str(int(row["nb"]))])
            cap_pve_zone = "PVe par zone"
            if str(profil_id).strip().lower() in {"pnf", "pnf_foret"}:
                cap_pve_zone = "PVe par zone (ensemble PNF, cœur de parc, aire d'adhésion)"
            builder.add_table(tbl, caption=cap_pve_zone,
                              col_widths=[avail_w * 0.62, avail_w * 0.38],
                              col_aligns=["LEFT", "RIGHT"])
        # Section dense : on conserve un saut de page dédié.

    # ── PEJ ──
    if nb_pej > 0:
        anchor, title = sections[sec_idx]; sec_idx += 1
        builder.add_section(anchor, title, compact=True)
        pej_top = results.get("pej_top_infractions")
        pej_theme = results.get("pej_par_theme")
        has_infractions = pej_top is not None and not pej_top.empty
        has_theme = pej_theme is not None and not pej_theme.empty

        if has_infractions and has_theme:
            # Bandeau + Infractions les plus relevées + PEJ par thème : espacements compacts
            # et hauteur de tableaux limitée pour tenir sur une page.
            natinf_ref = load_natinf_ref(PROJECT_ROOT)
            top_df = pej_top.head(6).copy()
            top_df["numero_natinf"] = top_df["natinf"].astype(str).str.extract(r"(\d+)", expand=False)
            if not natinf_ref.empty:
                top_df = top_df.merge(natinf_ref, on="numero_natinf", how="left")
            def _fmt_natinf_row_pej(r):
                qualif = str(r.get("qualification_infraction") or "").strip()
                nature_raw = str(r.get("nature_infraction") or "").strip()
                nature = nature_raw
                if nature_raw.lower().startswith("contravention de classe "):
                    num = nature_raw[len("contravention de classe "):].strip()
                    nature = f"C{num}" if num else nature_raw
                if qualif and nature:
                    return f"{qualif} ({nature})"
                if qualif:
                    return qualif
                if nature:
                    return nature
                lib = str(r.get("libelle_natinf") or "").strip()
                return lib if lib else str(r["natinf"])
            top_df["libelle_affich"] = top_df.apply(_fmt_natinf_row_pej, axis=1)
            tbl_infractions = [["Infraction (qualification et nature)", "Nombre"]]
            for _, row in top_df.iterrows():
                tbl_infractions.append([str(row["libelle_affich"]), str(int(row["nb"]))])
            # Limiter le volume pour garantir une section V sur une seule page.
            df_theme = pej_theme.head(8).copy()
            if "nb_pej" in df_theme.columns:
                df_theme = df_theme.rename(columns={"nb_pej": "Nombre de procédures judiciaires"})
            tbl_theme = [list(df_theme.columns)]
            for _, row in df_theme.iterrows():
                tbl_theme.append([str(v) for v in row.values])
            col_aligns_theme = ["LEFT"] * len(df_theme.columns)
            if "Nombre de procédures judiciaires" in df_theme.columns:
                idx = list(df_theme.columns).index("Nombre de procédures judiciaires")
                col_aligns_theme[idx] = "RIGHT"
            builder.add_key_figures_and_tables(
                [(str(nb_pej), "PEJ")],
                [
                    {
                        "data_rows": tbl_infractions,
                        "caption": "Infractions les plus relevées",
                        "col_widths": [avail_w * 0.75, avail_w * 0.25],
                        "col_aligns": ["LEFT", "RIGHT"],
                    },
                    {
                        "data_rows": tbl_theme,
                        "caption": "PEJ par thème",
                        "col_widths": None,
                        "col_aligns": col_aligns_theme,
                    },
                ],
                compact=True,
            )
        elif has_infractions:
            natinf_ref = load_natinf_ref(PROJECT_ROOT)
            top_df = pej_top.copy()
            top_df["numero_natinf"] = top_df["natinf"].astype(str).str.extract(r"(\d+)", expand=False)
            if not natinf_ref.empty:
                top_df = top_df.merge(natinf_ref, on="numero_natinf", how="left")
            def _fmt_natinf_row_pej(r):
                qualif = str(r.get("qualification_infraction") or "").strip()
                nature_raw = str(r.get("nature_infraction") or "").strip()
                nature = nature_raw
                if nature_raw.lower().startswith("contravention de classe "):
                    num = nature_raw[len("contravention de classe "):].strip()
                    nature = f"C{num}" if num else nature_raw
                if qualif and nature:
                    return f"{qualif} ({nature})"
                if qualif:
                    return qualif
                if nature:
                    return nature
                lib = str(r.get("libelle_natinf") or "").strip()
                return lib if lib else str(r["natinf"])
            top_df["libelle_affich"] = top_df.apply(_fmt_natinf_row_pej, axis=1)
            tbl_infractions = [["Infraction (qualification et nature)", "Nombre"]]
            for _, row in top_df.iterrows():
                tbl_infractions.append([str(row["libelle_affich"]), str(int(row["nb"]))])
            builder.add_key_figures_and_table(
                [(str(nb_pej), "PEJ")],
                tbl_infractions,
                caption="Infractions les plus relevées",
                col_widths=[avail_w * 0.75, avail_w * 0.25],
                col_aligns=["LEFT", "RIGHT"],
            )
        elif has_theme:
            builder.add_key_figures([(str(nb_pej), "PEJ")])
            df = pej_theme.head(10).copy()
            if "nb_pej" in df.columns:
                df = df.rename(columns={"nb_pej": "Nombre de procédures judiciaires"})
            tbl = [list(df.columns)]
            for _, row in df.iterrows():
                tbl.append([str(v) for v in row.values])
            col_aligns = ["LEFT"] * len(df.columns)
            if "Nombre de procédures judiciaires" in df.columns:
                idx = list(df.columns).index("Nombre de procédures judiciaires")
                col_aligns[idx] = "RIGHT"
            builder.add_table(
                tbl,
                caption="PEJ par thème",
                col_aligns=col_aligns,
                keep_together=True,
            )
        else:
            builder.add_key_figures([(str(nb_pej), "PEJ")])
        if "pej_clotur" in results:
            tbl = [["Clôture PEJ", "Nombre"]]
            for _, row in results["pej_clotur"].head(10).iterrows():
                tbl.append([str(row["cloture"]), str(int(row["nb"]))])
            builder.add_table(tbl, caption="PEJ par type de clôture",
                              col_widths=[avail_w * 0.6, avail_w * 0.4],
                              col_aligns=["LEFT", "RIGHT"])
        if "pej_suite" in results:
            tbl = [["Suite", "Nombre"]]
            for _, row in results["pej_suite"].head(10).iterrows():
                tbl.append([str(row["suite"]), str(int(row["nb"]))])
            builder.add_table(tbl, caption="PEJ par suite donnée",
                              col_widths=[avail_w * 0.6, avail_w * 0.4],
                              col_aligns=["LEFT", "RIGHT"])
        # On force un saut de page après la partie V. Procédures judiciaires (PEJ)
        # pour que la partie VI. Zones d'intérêt (PNF + TUB) soit regroupée sur
        # la page suivante.
        builder.add_page_break()

    # ── PA ──
    if nb_pa > 0:
        anchor, title = sections[sec_idx]; sec_idx += 1
        builder.add_section(anchor, title)
        builder.add_key_figures([(str(nb_pa), "PA")])
        pa_theme = results.get("pa_par_theme")
        if pa_theme is not None and not pa_theme.empty:
            tbl = [list(pa_theme.columns)]
            for _, row in pa_theme.head(20).iterrows():
                tbl.append([str(v) for v in row.values])
            builder.add_table(tbl, caption="PA par thème")
        # Section dense : on conserve un saut de page dédié.

    # ── Analyse PNF (libellé de section selon le profil, cf. sommaire) ──
    agg_pnf = results.get("agg_pnf_detail")
    if agg_pnf is None:
        agg_pnf = results.get("agg_pnf")
    if agg_pnf is not None:
        anchor, title = sections[sec_idx]; sec_idx += 1
        builder.add_section(anchor, title)
        tbl = [["Zone", "Nb contrôles", "Contrôles non-conformes", "Taux d'infraction"]]
        grp_labels, series_ctrl = [], {"Contrôles": [], "Infractions": []}
        for _, row in agg_pnf.iterrows():
            t = f"{row['taux_inf']:.1%}" if pd.notna(row.get("taux_inf")) else "n.d."
            tbl.append([str(row["PNF"]), str(int(row["nb_controles"])),
                        str(int(row["nb_inf"])), t])
            grp_labels.append(str(row["PNF"]))
            series_ctrl["Contrôles"].append(int(row["nb_controles"]))
            series_ctrl["Infractions"].append(int(row["nb_inf"]))
        caption_pnf = (
            "Contrôles – Ensemble PNF et Cœur de parc"
            if str(profil_id).strip().lower() in {"pnf", "pnf_foret"}
            else "Contrôles – PNF vs Hors PNF"
        )
        col_w_pnf = [avail_w * 0.30, avail_w * 0.23, avail_w * 0.23, avail_w * 0.24]
        col_a_pnf = ["LEFT", "RIGHT", "RIGHT", "RIGHT"]
        if grp_labels:
            bar_path = chart_bar_grouped(
                grp_labels, series_ctrl,
                (
                    "Contrôles : Ensemble PNF et Cœur de parc"
                    if str(profil_id).strip().lower() in {"pnf", "pnf_foret"}
                    else "Contrôles : PNF vs Hors PNF"
                ),
                "Nombre",
                tmp_dir, "bar_pnf.png",
            )
            builder.add_table_and_image_keep_together(
                tbl,
                table_caption=caption_pnf,
                col_widths=col_w_pnf,
                col_aligns=col_a_pnf,
                image_path=Path(bar_path),
                image_width_ratio=chart_ratio_base * 0.88,
            )
        else:
            builder.add_table(
                tbl,
                caption=caption_pnf,
                col_widths=col_w_pnf,
                col_aligns=col_a_pnf,
            )
        # Pour l'agrainage, on laisse la place au bloc Zone TUB
        # sur la même page (pas de saut forcé ici).
        if profil_id != "agrainage":
            builder.add_page_break()

    # ── ZONE TUB / HORS ZONE TUB ─
    # Affichée uniquement si l'option tub est activée dans le profil / YAML.
    zone_ctrl = results.get("zone_ctrl")
    if options.get("tub", False) and zone_ctrl is not None and not zone_ctrl.empty:
        # On dérive Zone TUB / Hors zone TUB à partir du récapitulatif départemental.
        df_zone = zone_ctrl.copy()
        # Ligne départementale
        dep = df_zone[df_zone["zone"] == "Département"].iloc[0]
        total_dep = int(dep["nb_total"])
        inf_dep = int(dep["nb_infraction"])
        conf_dep = int(dep["nb_conforme"])

        # Ligne TUB (peut être absente si aucune commune TUB dans le département)
        tub_rows = df_zone[df_zone["zone"] == "Zone TUB"]
        if not tub_rows.empty:
            tub = tub_rows.iloc[0]
            total_tub = int(tub["nb_total"])
            inf_tub = int(tub["nb_infraction"])
            conf_tub = int(tub["nb_conforme"])

            total_hors_tub = max(total_dep - total_tub, 0)
            inf_hors_tub = max(inf_dep - inf_tub, 0)
            conf_hors_tub = max(conf_dep - conf_tub, 0)

            data_tub = [
                {
                    "zone": "Zone TUB",
                    "nb_controles": total_tub,
                    "nb_inf": inf_tub,
                    "taux_inf": (
                        inf_tub / total_tub if total_tub > 0 else pd.NA
                    ),
                },
                {
                    "zone": "Hors zone TUB",
                    "nb_controles": total_hors_tub,
                    "nb_inf": inf_hors_tub,
                    "taux_inf": (
                        inf_hors_tub / total_hors_tub
                        if total_hors_tub > 0
                        else pd.NA
                    ),
                },
            ]
            agg_tub = pd.DataFrame(data_tub)

            # Pour l'agrainage, on ne crée pas de nouvelle section de niveau I/II :
            # le bloc Zone TUB fait partie de la section « Zones d'intérêt ».
            if profil_id != "agrainage":
                builder.add_section("sec_tub", "Zone TUB / Hors zone TUB")
            tbl = [["Zone", "Nb contrôles", "Contrôles non-conformes", "Taux d'infraction"]]
            grp_labels, series_ctrl_tub = [], {"Contrôles": [], "Infractions": []}
            for _, row in agg_tub.iterrows():
                t = f"{row['taux_inf']:.1%}" if pd.notna(row.get("taux_inf")) else "n.d."
                tbl.append(
                    [
                        str(row["zone"]),
                        str(int(row["nb_controles"])),
                        str(int(row["nb_inf"])),
                        t,
                    ]
                )
                grp_labels.append(str(row["zone"]))
                series_ctrl_tub["Contrôles"].append(int(row["nb_controles"]))
                series_ctrl_tub["Infractions"].append(int(row["nb_inf"]))
            builder.add_table(
                tbl,
                caption="Contrôles – Zone TUB vs Hors zone TUB",
                col_widths=[
                    avail_w * 0.30,
                    avail_w * 0.23,
                    avail_w * 0.23,
                    avail_w * 0.24,
                ],
                col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"],
            )
            if grp_labels:
                bar_tub_path = chart_bar_grouped(
                    grp_labels,
                    series_ctrl_tub,
                    "Contrôles : Zone TUB vs Hors zone TUB",
                    "Nombre",
                    tmp_dir,
                    "bar_tub.png",
                )
                builder.add_image(Path(bar_tub_path), width_ratio=chart_ratio_base)
            # Pour l'agrainage, on place l'ensemble de la section « Zones d'intérêt »
            # (PNF + TUB) sur une seule page. Un saut de page unique est ajouté ici.
            if profil_id == "agrainage":
                builder.add_page_break()
    # ── ANALYSE PAR ZONE ──
    zone_ctrl = results.get("zone_ctrl")
    if zone_ctrl is not None and options.get("tub", False):
        if profil_id == "agrainage":
            # Pour le bilan agrainage, l'analyse par zone est intégrée comme
            # sous-partie de la section "Contrôles agrainage" (niveau 2).
            # On ne consomme donc pas de nouvelle entrée du sommaire.
            builder.add_section(f"{sections[1][0]}_zone", "Analyse par zone", level=2)
        else:
            anchor, title = sections[sec_idx]; sec_idx += 1
            builder.add_section(anchor, title)
        tbl = [["Zone", "Nb total", "Nb conforme", "Contrôles non-conformes", "Taux d'infraction"]]
        for _, row in zone_ctrl.iterrows():
            t = f"{row['taux_infraction']:.1%}" if pd.notna(row.get("taux_infraction")) else "n.d."
            tbl.append(
                [
                    str(row["zone"]),
                    str(int(row["nb_total"])),
                    str(int(row["nb_conforme"])),
                    str(int(row["nb_infraction"])),
                    t,
                ]
            )
        builder.add_table(
            tbl,
            caption="Contrôles par zone (Département, TUB, PNF)",
            col_widths=[
                avail_w * 0.25,
                avail_w * 0.18,
                avail_w * 0.19,
                avail_w * 0.19,
                avail_w * 0.19,
            ],
            col_aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"],
        )
        # Section dense : on conserve un saut de page dédié.

    # ── SYNTHÈSE CROISÉE ──
    synth = results.get("synthese_zone")
    if synth is not None:
        anchor, title = sections[sec_idx]; sec_idx += 1
        builder.add_section(anchor, title)
        # Renommer les colonnes pour expliciter la signification des données
        col_labels = []
        for c in synth.columns:
            if c == "ctrl_total":
                col_labels.append("Nombre de contrôles")
            elif c == "ctrl_infraction":
                col_labels.append("Contrôles non-conformes")
            elif c == "pve_nb":
                col_labels.append("Nombre d'infractions relevées par PVe")
            elif c == "pej_nb":
                col_labels.append("Nombre de procédures judiciaires")
            else:
                col_labels.append(str(c))
        tbl = [col_labels]
        for _, row in synth.iterrows():
            tbl.append([str(int(v)) if isinstance(v, (int, float)) and pd.notna(v)
                        else str(v) for v in row.values])
        builder.add_table(
            tbl,
            caption=(
                "Synthèse croisée par zone : contrôles non-conformes, "
                "procédures judiciaires (PEJ) et infractions relevées par PVe."
            ),
        )
        # Section dense : on conserve un saut de page dédié.

    # ── ACTIVITÉ PAR TYPES D'USAGERS (hors profil dédié « analyses.type_usager ») ──
    if results.get("_pdf_show_activite_usagers"):
        anchor, title = sections[sec_idx]; sec_idx += 1
        builder.add_section(anchor, title)
        _pdf_section_activite_par_types_usagers(
            builder,
            results,
            tmp_dir,
            avail_w,
            pie_ratio=chart_ratios["activite_usagers_controles_pie"],
            bar_ratio=chart_ratios["activite_usagers_resultats_bar"],
        )
        builder.add_spacer(4)

    # ── CARTOGRAPHIE ──
    if options.get("cartes", False):
        anchor, title = sections[sec_idx]; sec_idx += 1
        builder.add_section(anchor, title)
        map_id = profile.get("_map_id") or profil_id
        carte = find_map(str(map_id))
        if carte and carte.exists():
            # Carte sans légende de sources explicite (les sources sont rappelées
            # en première page / méthodologie).
            builder.add_map(carte)
        else:
            builder.add_paragraph(
                f"<i>Carte non disponible. Déposez le fichier "
                f"<b>carte_{map_id}.png</b> dans le dossier des cartes pour "
                f"l'intégrer au bilan.</i>"
            )
        builder.add_page_break()

    # ── ANNEXES ──
    builder.add_section(sections[-1][0], sections[-1][1])
    src_parts: list[str] = []
    if sources.get("point_ctrl", True):
        src_parts.append("OSCEAN (points de contrôle)")
    if sources.get("pej", True):
        src_parts.append("OSCEAN (PEJ)")
    if sources.get("pa", True):
        src_parts.append("OSCEAN (PA)")
    if sources.get("pve", True):
        src_parts.append("PVe OFB")
    src_text = ", ".join(src_parts) if src_parts else "sources spécifiques au profil"

    method_lines: list[str] = [
        f"<b>Période d'analyse :</b> {period_str}.",
        f"<b>Périmètre :</b> département {dept_name} ({cfg.dept_code}).",
        f"<b>Profil :</b> {label}.",
        f"<b>Sources :</b> {src_text}.",
    ]

    has_zone_table = zone_ctrl is not None and not zone_ctrl.empty
    has_pnf = bool(options.get("pnf", False)) and results.get("agg_pnf") is not None
    has_tub = bool(options.get("tub", False)) and has_zone_table
    is_pnf_profile = str(profil_id).strip().lower() in {"pnf", "pnf_foret"}

    if is_pnf_profile and has_pnf:
        method_lines.append(
            "<b>Analyse par zones :</b> bilan restreint au périmètre PNF ; "
            "la lecture spatiale distingue l'ensemble du parc et le cœur de parc."
        )
    elif has_pnf and has_tub:
        method_lines.append(
            "<b>Analyse par zones :</b> la zone « Département » inclut l'ensemble des "
            "contrôles, puis les zones PNF et TUB sont détaillées séparément."
        )
    elif has_pnf:
        method_lines.append(
            "<b>Analyse par zones :</b> la zone « Département » inclut l'ensemble des "
            "contrôles, puis la zone PNF est détaillée séparément."
        )
    elif has_tub:
        method_lines.append(
            "<b>Analyse par zones :</b> la zone « Département » inclut l'ensemble des "
            "contrôles, puis la zone TUB est détaillée séparément."
        )

    builder.add_methodology("<br/>".join(method_lines) + "<br/>")

    # Glossaire dynamique basé sur une configuration YAML exhaustive,
    # filtrée pour ne conserver que les abréviations réellement utiles
    # au PDF courant.
    gloss_cfg = _load_glossary_config(PROJECT_ROOT)
    header_cfg = gloss_cfg.get("header", {}) or {}
    abbr_list = gloss_cfg.get("abbreviations", []) or []

    # Index par id pour un accès rapide
    abbr_by_id: dict[str, dict] = {}
    for item in abbr_list:
        if not isinstance(item, dict):
            continue
        id_ = str(item.get("id", "")).strip()
        if not id_:
            continue
        abbr_by_id[id_] = item

    # Sélection des abréviations en fonction du contenu réel du bilan.
    # On se base sur les sections effectivement présentes : contrôles,
    # procédures, analyses spatiales…
    used_ids: list[str] = []

    def _add_if_available(abbr_id: str, condition: bool) -> None:
        if condition and abbr_id in abbr_by_id and abbr_id not in used_ids:
            used_ids.append(abbr_id)

    # OSCEAN est toujours cité (page de garde + méthodologie)
    _add_if_available("OSCEAN", True)
    # DC : contrôles / dossiers de contrôle présents
    _add_if_available("DC", nb_ctrl > 0)
    # NATINF : utilisé dès que des infractions PVe ou PEJ sont exploitées
    _add_if_available("NATINF", nb_pve > 0 or nb_pej > 0)
    # PA / PEJ / PVe : sections dédiées
    _add_if_available("PA", nb_pa > 0)
    _add_if_available("PEJ", nb_pej > 0)
    _add_if_available("PVe", nb_pve > 0)
    # PNF / TUB : analyses spatiales correspondantes
    _add_if_available("PNF", results.get("agg_pnf") is not None)
    _add_if_available("TUB", options.get("tub", False))

    if used_ids:
        rows: List[List[str]] = [
            [
                str(header_cfg.get("abbr_label", "Abréviation")),
                str(header_cfg.get("definition_label", "Signification")),
            ]
        ]
        for abbr_id in used_ids:
            item = abbr_by_id[abbr_id]
            rows.append(
                [
                    str(item.get("label", abbr_id)),
                    str(item.get("definition", "")),
                ]
            )
        builder.add_glossary(rows)

    builder.build()


def _roman(n: int) -> str:
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    result = ""
    for val, numeral in vals:
        while n >= val:
            result += numeral
            n -= val
    return result


# ═══════════════════════════════════════════════════════════════════════════
# 7. Point d'entrée principal
# ═══════════════════════════════════════════════════════════════════════════

def run_engine(
    profil_id: str,
    date_deb: str,
    date_fin: str,
    dept_code: str,
    options: dict | None = None,
) -> int:
    """Point d'entrée unique du moteur thématique unifié."""
    options = options or {}
    chart_preset = options.pop("chart_preset", None)
    root = PROJECT_ROOT
    profile = load_profile_config(root, profil_id)
    cfg = BilanConfig.from_strings(date_deb, date_fin, dept_code, root=root)
    out_dir = cfg.get_out(profile["out_subdir"])
    label = profile["label"]
    sources = profile["sources"]

    # Le paramètre de profil analyse_PVe permet de désactiver complètement
    # l'analyse et l'affichage liés aux PVe (chargement, agrégations, PDF).
    analyse_pve = bool(profile.get("analyse_PVe", True))
    if not analyse_pve:
        sources["pve"] = False

    print(f"Bilan « {label} » — {cfg.dept_name}")
    print(f"Période : du {cfg.date_deb.date():%d/%m/%Y} au {cfg.date_fin.date():%d/%m/%Y}")

    # Déterminer le mode de ventilation temporelle depuis le profil YAML
    period_cfg = profile.get("periode_analyse", {}) or {}
    vent_cfg = period_cfg.get("ventilation", {}) or {}
    vent_type = str(vent_cfg.get("type", "auto")).strip().lower()
    try:
        seuil_jours = int(vent_cfg.get("seuil_jours", 366))
    except (TypeError, ValueError):
        seuil_jours = 366
    duree_jours = int((cfg.date_fin - cfg.date_deb).days)
    if vent_type == "annuelle":
        ventilation_mode = "annuelle"
    elif vent_type == "globale":
        ventilation_mode = "globale"
    else:
        ventilation_mode = "annuelle" if duree_jours > seuil_jours else "trimestrielle"
    print(
        f"Ventilation temporelle : {ventilation_mode} "
        f"(type={vent_type}, seuil={seuil_jours} j, durée={duree_jours} j)"
    )

    # Extraire d'éventuelles cibles de type d'usager depuis les options CLI
    # (ex. --option type_usager_target="Agriculteur..." répété plusieurs fois).
    cli_type_targets: list[str] = []
    if "type_usager_target" in options:
        raw_targets = options.pop("type_usager_target")
        if isinstance(raw_targets, list):
            raw_list = raw_targets
        else:
            raw_list = [raw_targets]
        for val in raw_list:
            if isinstance(val, str):
                s = val.strip()
                if s:
                    cli_type_targets.append(s)
    if cli_type_targets:
        filt = profile.setdefault("filter", {})
        existing = filt.get("type_usager_target") or []
        if not isinstance(existing, list):
            existing = [existing]
        merged: list[str] = []
        for val in list(existing) + cli_type_targets:
            s = str(val).strip()
            if s and s not in merged:
                merged.append(s)
        filt["type_usager_target"] = merged

    # Résoudre les options (pnf, tub, cartes, synthèse, etc.)
    resolved_opts = resolve_options(profile, options)
    if chart_preset:
        resolved_opts["chart_preset"] = chart_preset
    resolved_opts = ask_interactive_options(profile, resolved_opts)

    # Pour les profils basés sur le type d'usager, si aucune cible n'est
    # définie ni en YAML ni en CLI, proposer un choix interactif (menu).
    filt_cfg = profile.get("filter", {})
    if (
        filt_cfg.get("type") == "type_usager"
        and not (filt_cfg.get("type_usager_target") or [])
        and profil_id == "types_usager_cible"
    ):
        targets = ask_type_usager_targets(root, profil_id, filt_cfg.get("type_usager_target") or [])
        filt_cfg["type_usager_target"] = targets

    # Déterminer l'identifiant cartographique à utiliser pour retrouver la carte.
    # Pour le profil "types_usager_cible", le nom de carte doit dépendre des
    # types d'usagers réellement sélectionnés, via des codes courts lisibles.
    targets = (profile.get("filter", {}) or {}).get("type_usager_target") or []
    if profil_id == "types_usager_cible" and targets:
        codes = [_short_type_usager_code(t) for t in targets]
        map_id = "_".join([c for c in codes if c]) or profil_id
    else:
        map_id = profil_id
    profile["_map_id"] = map_id

    # Si l'utilisateur a activé l'intégration des cartes, indiquer le nommage attendu
    # de la carte et mettre le programme en pause pour lui laisser le temps de préparer
    # le fichier (nom + emplacement).
    #
    # IMPORTANT : pour "types_usager_cible", cette étape doit se faire après la
    # sélection des types d'usagers afin de respecter le nommage carte_{types}.
    if resolved_opts.get("cartes", False) and sys.stdin.isatty():
        cartes_dir = get_cartes_dir()
        expected_name = f"carte_{map_id}.png"
        expected_path = cartes_dir / expected_name

        print("\n--- Cartographie ---")
        print("Pour que la carte soit intégrée dans le bilan PDF :")
        print(f"  - nommez le fichier d'image : {expected_name}")
        print(f"  - placez-le dans le dossier : {expected_path.parent}")

        _copy_to_clipboard(expected_name)
        print("(Le nom de fichier attendu a été copié dans le presse-papiers si possible.)")

        try:
            input("Appuyez sur Entrée une fois la carte prête (renommée et placée au bon endroit)... ")
        except (EOFError, KeyboardInterrupt):
            # En contexte non interactif ou interruption, on continue sans bloquer.
            pass

    # Déterminer si l'on est dans un contexte \"mono-usager\" (un seul type ciblé).
    is_type_usager = profile.get("analyses", {}).get("type_usager", False)
    if is_type_usager and len(targets) == 1:
        profile["_single_usager"] = {"enabled": True, "label": targets[0]}
    else:
        profile.pop("_single_usager", None)

    # Nommage des fichiers de sortie pour le bilan ciblé :
    # - mono-usager : Bilan_{type_usager normalisé}
    # - multi-usagers : Bilan_{codes_courts} (AGR_PAR_COLL_...) limité en longueur.
    if profil_id == "types_usager_cible" and targets:
        if len(targets) == 1:
            safe_join = _safe_type_usager_for_filename(targets[0]) or "type_usager"
            profile["_export_prefix"] = f"Bilan_{safe_join}"
        else:
            codes = [_short_type_usager_code(t) for t in targets]
            joined = "_".join(codes)
            # Si jamais trop long, tronquer proprement.
            if len(joined) > 40:
                joined = "_".join(codes[:5])
            profile["_export_prefix"] = f"Bilan_{joined}"
    else:
        profile.pop("_export_prefix", None)

    # ── Chargement ──
    print("  Chargement des données...")
    with Spinner():
        point = (
            load_point_ctrl(root, dept_code=dept_code, date_deb=date_deb, date_fin=date_fin)
            if sources.get("point_ctrl", True)
            else pd.DataFrame()
        )
        pej = (
            load_pej(root, date_deb=date_deb, date_fin=date_fin)
            if sources.get("pej", True)
            else pd.DataFrame()
        )
        pa = (
            load_pa(root, date_deb=date_deb, date_fin=date_fin)
            if sources.get("pa", True)
            else pd.DataFrame()
        )
        pve = (
            load_pve(root, dept_code=dept_code, date_deb=date_deb, date_fin=date_fin)
            if sources.get("pve", True)
            else pd.DataFrame()
        )

    # ── Filtrage ──
    print("  Filtrage...")
    with Spinner():
        point_filtered = _filter_point_ctrl(point, profile) if not point.empty else point
        pej_filtered = _filter_pej(pej, profile, cfg, point_filtered) if not pej.empty else pej
        if not pej_filtered.empty and sources.get("pej", True):
            pej_filtered = merge_pej_faits_locations(
                pej_filtered, root, dept_code, log=logging.getLogger("bilans.spatial")
            )
        pa_filtered = _filter_pa(pa, profile, cfg, point_filtered) if not pa.empty else pa
        pve_filtered = _filter_pve(pve, profile) if not pve.empty else pve

    spatial_log = logging.getLogger("bilans.spatial")
    if str(profile.get("restrict_geo") or "").strip().lower() == "pnf":
        print("  Restriction géographique PNF...")
        with Spinner():
            point_filtered, pej_filtered, pa_filtered, pve_filtered = _apply_restrict_geo_pnf(
                point_filtered, pej_filtered, pa_filtered, pve_filtered, root, spatial_log
            )

    # ── INSEE commune (jointure communes.shp si besoin) ──
    if resolved_opts.get("pnf") or resolved_opts.get("tub"):
        if not point_filtered.empty:
            point_filtered = ensure_insee_from_communes_shp(
                point_filtered, root, context="points de contrôle", log=spatial_log
            )
        if not pve_filtered.empty:
            pve_filtered = ensure_insee_from_communes_shp(
                pve_filtered, root, context="PVe", log=spatial_log
            )

    if not point_filtered.empty and (
        resolved_opts.get("pnf")
        or resolved_opts.get("tub")
        or str(profile.get("restrict_geo") or "").strip().lower() == "pnf"
    ):
        point_filtered = enrich_with_pnforet_sig_zones(
            point_filtered, root, context="points de contrôle", log=spatial_log
        )
    if not pve_filtered.empty and (
        resolved_opts.get("pnf")
        or resolved_opts.get("tub")
        or str(profile.get("restrict_geo") or "").strip().lower() == "pnf"
    ):
        pve_filtered = enrich_with_pnforet_sig_zones(
            pve_filtered, root, context="PVe", log=spatial_log
        )

    # ── Analyses spatiales ──
    print("  Analyses spatiales...")
    with Spinner():
        spatial, point_filtered = _run_spatial_analyses(
            point_filtered, pej_filtered, pve_filtered,
            resolved_opts, cfg, profil_id=profil_id,
        )

    # ── Agrégations ──
    print("  Agrégations...")
    with Spinner():
        results = _run_aggregations(
            point_filtered, pej_filtered, pa_filtered, pve_filtered,
            profile, resolved_opts, spatial, ventilation_mode=ventilation_mode,
        )

    # ── Export CSV ──
    print("  Export CSV...")
    with Spinner():
        _export_csv(
            results, point_filtered, pej_filtered, pa_filtered, pve_filtered,
            out_dir, profile,
        )

    # ── PDF ──
    print("  Génération du PDF...")
    with Spinner():
        _generate_pdf(results, out_dir, profile, cfg, resolved_opts)

    # Flèche ASCII pour éviter les problèmes d'encodage dans certaines consoles Windows.
    print(f"  Terminé -> {out_dir}")
    return 0
