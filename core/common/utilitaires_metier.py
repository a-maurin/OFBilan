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
========================================================================================
MODULE : UTILITAIRES ET REGLES METIERS DU PLUGIN (`utilitaires_metier.py`)
========================================================================================
Ce module rassemble la logique métier principale du traitement des données de police OFB.

Domaines couverts :
  1. Résolution des périmètres administratifs (Départements, Régions, BMI, Parc National).
  2. Traitement et consolidation des catégories d'usagers contrôlés (parsing des effectifs multi-usagers).
  3. Consolidation au niveau fiche de contrôle (`fc_id`) pour éviter les doublons d'effectifs.
  4. Fonctions d'agrégation statistique (Domaines, Thèmes, Résultats, PEJ, PA, PVe).
  5. Classification et filtrage des résultats de contrôles et zonages réglementaires (PNF, TUB).
========================================================================================
"""
import functools
import logging
import re
import yaml

logger = logging.getLogger(__name__)
from pathlib import Path
from typing import Any, List

import pandas as pd
from core import configurer_pandas_si_present
configurer_pandas_si_present()

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TYPES_USAGERS_PATH = _PROJECT_ROOT / "ref" / "programme" / "tables_reference" / "types_usagers.csv"
_REGIONS_YAML_PATH = _PROJECT_ROOT / "config" / "regions_referentiel.yaml"
_BMI_YAML_PATH = _PROJECT_ROOT / "config" / "referentiel_bmi.yaml"
logger = logging.getLogger(__name__)


# ========================================================================================
# CHARGEMENT DES REFERENTIELS TERRITORIAUX (REGIONS ET BMI)
# ========================================================================================

@functools.lru_cache(maxsize=1)
def _load_regions_config() -> dict:
    """Charge le référentiel des régions et départements associés."""
    if not _REGIONS_YAML_PATH.exists():
        return {}
    with open(_REGIONS_YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

@functools.lru_cache(maxsize=1)
def _load_bmi_config() -> dict:
    """Charge le référentiel des Brigades de Lespaces Maritimes et Interdépartementales (BMI)."""
    if not _BMI_YAML_PATH.exists():
        return {}
    with open(_BMI_YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def get_bmi_filters(code: str) -> dict:
    """Retourne les paramètres de filtrage pour une BMI donnée."""
    cfg = _load_bmi_config()
    return cfg.get("BMI_CONFIG", {}).get(code, {})


def get_departements_pour_perimetre(echelle: str, code: str) -> list[str]:
    """Retourne la liste des départements rattachés au périmètre choisi (Département, Région, BMI, National)."""
    echelle_norm = str(echelle).strip().lower()
    code_norm = str(code).strip()
    if code_norm.upper() == "PNF" or echelle_norm == "pnf":
        return ["21", "52"]
    if echelle_norm == "departement":
        return [c.strip() for c in code_norm.replace(",", " ").replace("_", " ").split() if c.strip()]
    if echelle_norm == "region":
        cfg = _load_regions_config()
        region_deps = cfg.get("REGION_DEPARTEMENTS", {})
        if code_norm not in region_deps and f"r{code_norm}" in region_deps:
            code_norm = f"r{code_norm}"
        return list(region_deps.get(code_norm, []))
    if echelle_norm == "bmi":
        filters = get_bmi_filters(code_norm)
        return list(filters.get("departements", []))
    if echelle_norm == "national":
        return ["FR"]
    return []



def get_pnf_departements(profile: dict) -> list[str]:
    """Retourne la liste des codes départementaux couverts par un profil à restrict_geo=pnf.

    Lit la clé ``departements`` du profil YAML (ex: ``["21", "52"]``).
    Fallback sur ``["21", "52"]`` (PNF historique) si la clé est absente.
    """
    depts = profile.get("departements") if isinstance(profile, dict) else None
    if depts and isinstance(depts, list):
        return [str(d).strip() for d in depts if str(d).strip()]
    return ["21", "52"]


def resolve_code_subdir_suffix(profile: dict | None, code: str) -> str:
    """
    Assainit la chaîne du code géographique pour la génération des sous-dossiers de sortie.
    Remplace les virgules et espaces par des tirets bas (_).
    Pour les profils PNF (restrict_geo=pnf), si le code est 'PNF' ou non renseigné,
    utilise les départements du profil (ex: '21_52').
    """
    code_norm = str(code or "").strip()
    tokens = [c.strip() for c in code_norm.replace(",", " ").split() if c.strip()]

    is_pnf = False
    if profile and isinstance(profile, dict):
        is_pnf = str(profile.get("restrict_geo") or "").strip().lower() == "pnf"

    if is_pnf:
        if not tokens or tokens == ["PNF"]:
            pnf_depts = get_pnf_departements(profile)
            return "_".join(pnf_depts)

    return "_".join(tokens)



def get_region_name(code: str) -> str:
    """Retourne le nom officiel d'une région depuis son code."""
    cfg = _load_regions_config()
    names = cfg.get("REGION_NAMES", {})
    code_norm = str(code).strip()
    if code_norm not in names and f"r{code_norm}" in names:
        code_norm = f"r{code_norm}"
    return str(names.get(code_norm, f"Région {code_norm}"))


def get_perimetre_name(echelle: str, code: str) -> str:
    """Retourne le nom complet d'un périmètre d'étude."""
    echelle_norm = str(echelle).strip().lower()
    code_norm = str(code).strip()
    if echelle_norm == "departement":
        return get_dept_name(code_norm)
    if echelle_norm == "region":
        return get_region_name(code_norm)
    if echelle_norm == "bmi":
        return code_norm
    if echelle_norm == "national":
        return "France"
    return f"{echelle_norm} {code_norm}"


def resolve_carto_dept_code(echelle: str, code: str, *, default: str = "21") -> str:
    """Détermine le code départemental principal pour le chargement des couches cartographiques."""
    echelle_norm = str(echelle).strip().lower()
    code_norm = str(code).strip()
    if echelle_norm == "departement":
        return code_norm or default
    if echelle_norm in ("bmi", "region"):
        return code_norm
    dept_codes = get_departements_pour_perimetre(echelle_norm, code_norm)
    if dept_codes and dept_codes[0] != "FR":
        return dept_codes[0]
    return default


def _norm_key(s: str) -> str:
    return (s or "").strip().lower()


# ========================================================================================
# MANIPULATION ROBUSTE DES SERIES ET CODES INSEE
# ========================================================================================

def series_as_python_str(series: pd.Series) -> pd.Series:
    """Convertit une série Pandas en chaîne de caractères classique Python (compatible PyArrow QGIS)."""
    def _clean_str(v):
        if pd.isna(v): return ""
        if isinstance(v, float) and v.is_integer(): return str(int(v))
        return str(v)
    return series.map(_clean_str).astype(object)


def series_str_contains(
    series: pd.Series,
    pat: str,
    *,
    regex: bool = False,
) -> pd.Series:
    """Effectue une recherche textuelle insensible à la casse."""
    s = series_as_python_str(series)
    if regex:
        cre = re.compile(pat, re.IGNORECASE)
        return s.map(lambda val: bool(cre.search(val)))
    needle = pat.lower()
    return s.map(lambda val: needle in val.lower())


def count_operations_controle(df: pd.DataFrame, mask: pd.Series | None = None) -> int:
    """Compte le nombre d'opérations uniques de contrôle (`fc_id`)."""
    if "fc_id" not in df.columns or df.empty:
        return 0
    if mask is not None:
        return int(len(df.loc[mask, "fc_id"].dropna().unique()))
    return int(len(df["fc_id"].dropna().unique()))


def extract_insee_code_series(series: pd.Series) -> pd.Series:
    """Extrait et normalise les codes INSEE à 5 chiffres depuis une série Pandas."""
    return series_as_python_str(series).map(lambda val: _normalize_insee_code(val) or pd.NA)


# ========================================================================================
# MAPPING ET NORMALISATION DES TYPES D'USAGERS CONTROLES
# ========================================================================================

@functools.lru_cache(maxsize=1)
def _load_types_usagers_mapping() -> dict[tuple[str, str, str], str]:
    """Charge la table de correspondance `types_usagers.csv`."""
    if not _TYPES_USAGERS_PATH.exists():
        return {}
    df = pd.read_csv(_TYPES_USAGERS_PATH, sep=";", dtype=str, encoding="utf-8")
    df = df.fillna("")
    mapping: dict[tuple[str, str, str], str] = {}
    for _, r in df.iterrows():
        st = _norm_key(r.get("source_table", ""))
        sc = _norm_key(r.get("source_champ", ""))
        vs = _norm_key(r.get("valeur_source", ""))
        tu = (r.get("type_usager", "") or "").strip()
        if not st or not sc or not vs or not tu:
            continue
        mapping[(st, sc, vs)] = tu
    return mapping


@functools.lru_cache(maxsize=1)
def _canonical_type_usager_aliases() -> dict[str, str]:
    """Indexe les sous-catégories vers les 6 types usagers cibles."""
    aliases: dict[str, str] = {}
    for (_, _, _), tu in _load_types_usagers_mapping().items():
        aliases[_norm_key(tu)] = tu
    for (_, _, vs), tu in _load_types_usagers_mapping().items():
        aliases.setdefault(_norm_key(vs), tu)
    return aliases


def format_type_usager_display(label: str) -> str:
    """Formatage propre des intitulés d'usagers pour les tableaux PDF."""
    s = str(label or "").strip()
    if s == "Autre":
        return "Autre usager"
    return s


def _parse_type_usager_tokens(valeur_source: str) -> list[tuple[str, int]]:
    """Décompose une chaîne d'effectifs multi-usagers (ex: 'Agriculteur 2, Particulier 1')."""
    if pd.isna(valeur_source):
        return []
    s = str(valeur_source).strip()
    if not s or s == "(vide)":
        return []
    parts = [p.strip() for p in s.split(",") if p.strip()]
    out: list[tuple[str, int]] = []
    for p in parts:
        m = re.match(r"^(.*?)(?:[\s_]+(\d+))?$", p)
        if not m:
            continue
        label = (m.group(1) or "").strip()
        n = int(m.group(2)) if m.group(2) and m.group(2).isdigit() else 1
        if label:
            out.append((label, n))
    return out



# ========================================================================================
# CONSOLIDATION INTRA-FC_ID POUR LES EFFECTIFS ET INDICATEURS USAGERS
# ========================================================================================

def _is_missing_effectif_value(value: Any) -> bool:
    """Vérifie si une donnée d'effectif est vide ou absente."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except TypeError:
        pass
    if isinstance(value, str):
        return value.strip() in ("", "(vide)")
    return False


def _stable_non_empty_group_values(values: pd.Series) -> list[Any]:
    """Retourne la liste ordonnée des valeurs non vides observées."""
    out: list[Any] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        if _is_missing_effectif_value(value):
            continue
        normalized = value.strip() if isinstance(value, str) else value
        key = (type(normalized).__name__, str(normalized))
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _date_score_for_effectif_row(value: Any) -> tuple[int, int]:
    """Arbitre les conflits de données en privilégiant la ligne la plus récente."""
    if _is_missing_effectif_value(value):
        return (0, 0)
    try:
        dt = pd.to_datetime(value, errors="coerce")
    except (TypeError, ValueError):
        return (0, 0)
    if pd.isna(dt):
        return (0, 0)
    return (1, int(dt.value))


def _score_effectif_group_row(row: pd.Series, order_col: str) -> tuple[int, int, int]:
    """Calcule le score de priorité d'une ligne dans le groupe."""
    has_date, date_value = _date_score_for_effectif_row(row.get("date_ctrl"))
    row_order = int(row.get(order_col, 0) or 0)
    return (has_date, date_value, -row_order)


def _score_effectif_group_value(
    row: pd.Series,
    col: str,
    source_table: str,
    order_col: str,
) -> tuple[int, int, int, int]:
    """Donne la priorité aux valeurs usagers qualifiées par rapport aux catégories 'Autre'."""
    value = row.get(col)
    normalized = value.strip() if isinstance(value, str) else value
    informative = 0
    if col == "type_usager" and not _is_missing_effectif_value(normalized):
        informative = int(map_type_usager(source_table, col, str(normalized)) != "Autre")
    has_date, date_value = _date_score_for_effectif_row(row.get("date_ctrl"))
    row_order = int(row.get(order_col, 0) or 0)
    return (informative, has_date, date_value, -row_order)


def _pick_effectif_group_value(
    group: pd.DataFrame,
    col: str,
    source_table: str,
    order_col: str,
) -> Any:
    """Sélectionne la valeur la plus pertinente d'un groupe."""
    candidates = group.loc[~group[col].map(_is_missing_effectif_value)].copy()
    if candidates.empty:
        return None
    best_index = max(
        candidates.index,
        key=lambda idx: _score_effectif_group_value(
            candidates.loc[idx],
            col,
            source_table,
            order_col,
        ),
    )
    best_value = candidates.loc[best_index, col]
    return best_value.strip() if isinstance(best_value, str) else best_value


def _consolide_lignes_effectifs_par_fc_id(
    df: pd.DataFrame,
    colonnes_metier: list[str],
    source_table: str = "point_ctrl",
) -> pd.DataFrame:
    """Consolide les contrôles par `fc_id` pour éviter les doublons lors des agrégations d'effectifs."""
    if df.empty or _norm_key(source_table) != "point_ctrl" or "fc_id" not in df.columns:
        return df

    work = df.copy()
    order_col = "__effectif_row_order__"
    work[order_col] = range(len(work))
    fc_values = work["fc_id"].astype("string").str.strip()
    has_fc_id = fc_values.notna() & (fc_values != "")
    if not has_fc_id.any() or not fc_values[has_fc_id].duplicated().any():
        return df

    grouped = work.loc[has_fc_id].copy()
    standalone = work.loc[~has_fc_id].copy()
    merged_rows: list[pd.Series] = []
    target_columns = [col for col in dict.fromkeys(colonnes_metier) if col in grouped.columns]

    for fc_id, group in grouped.groupby("fc_id", sort=False, dropna=False):
        if len(group) == 1:
            merged_rows.append(group.iloc[0])
            continue
        base_index = max(group.index, key=lambda idx: _score_effectif_group_row(group.loc[idx], order_col))
        merged = group.loc[base_index].copy()
        merged[order_col] = int(group[order_col].min())
        for col in target_columns:
            values = _stable_non_empty_group_values(group[col])
            if not values:
                continue
            if len(values) > 1:
                logger.warning(
                    "Conflit intra-fc_id sur %s pour fc_id=%s ; valeur la plus informative/récente conservée.",
                    col,
                    fc_id,
                )
            merged[col] = _pick_effectif_group_value(group, col, source_table, order_col)
        merged_rows.append(merged)

    consolidated = pd.DataFrame(merged_rows, columns=work.columns)
    if not standalone.empty:
        consolidated = pd.concat([consolidated, standalone], ignore_index=True, sort=False)
    return (
        consolidated.sort_values(order_col, kind="stable")
        .drop(columns=[order_col])
        .reset_index(drop=True)
    )


def map_type_usager(source_table: str, source_champ: str, valeur_source: str) -> str:
    """Mappe une valeur source vers l'une des 6 catégories du référentiel usagers."""
    mapping = _load_types_usagers_mapping()
    key = (_norm_key(source_table), _norm_key(source_champ), _norm_key(valeur_source))
    if key in mapping:
        return mapping[key]
    hit = _canonical_type_usager_aliases().get(_norm_key(valeur_source))
    if hit:
        return hit
    return "Autre"


def resolve_type_usager_champ(df: pd.DataFrame) -> str | None:
    """Recherche le nom réel de la colonne contenant le type d'usager."""
    for name in ("type_usager", "USAGER", "TYPE_USAGER", "TYPE USAGER"):
        if name in df.columns:
            return name
    return None


def serie_type_usager(df: pd.DataFrame, source_table: str, source_champ: str) -> pd.Series:
    """Détermine la catégorie d'usager dominante pour chaque ligne du tableau."""
    if source_champ not in df.columns:
        return pd.Series(["Autre"] * len(df), index=df.index, dtype="object")

    def _dominant(val: str) -> str:
        toks = _parse_type_usager_tokens(val)
        if not toks:
            return "Autre"
        mapped = [(map_type_usager(source_table, source_champ, lab), n) for lab, n in toks]
        agg: dict[str, int] = {}
        for cat, n in mapped:
            agg[cat] = agg.get(cat, 0) + int(n or 0)
        if len(agg) == 1:
            return next(iter(agg.keys()))
        max_n = max(agg.values())
        top = [k for k, v in agg.items() if v == max_n]
        return top[0] if len(top) == 1 else "Autre"

    return df[source_champ].apply(_dominant)


# ========================================================================================
# FONCTIONS D'AGREGATION PAR USAGERS, DOMAINES ET THEMES
# ========================================================================================

def agg_nb_localisations_par_type_usager(
    df: pd.DataFrame,
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Calcule le nombre de localisations contrôlées par usager dominant."""
    if source_champ not in df.columns or df.empty:
        return pd.DataFrame(columns=["type_usager", "nb"])

    work_df = _consolide_lignes_effectifs_par_fc_id(df, [source_champ], source_table=source_table)
    cats = serie_type_usager(work_df, source_table, source_champ)
    return (
        cats.value_counts()
        .rename_axis("type_usager")
        .to_frame("nb")
        .reset_index()
        .sort_values("nb", ascending=False, kind="stable")
    )


def agg_effectifs_usagers(
    df: pd.DataFrame,
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Somme les effectifs d'usagers en prenant en compte les contrôles multi-usagers."""
    if source_champ not in df.columns:
        return pd.DataFrame(columns=["type_usager", "nb", "nb_operations"])

    work_df = _consolide_lignes_effectifs_par_fc_id(df, [source_champ], source_table=source_table)
    has_fc_id = "fc_id" in work_df.columns

    agg: dict[str, int] = {}
    fc_ids: dict[str, set[str]] = {}

    for _, row in work_df.iterrows():
        val = row.get(source_champ, "")
        fc_id = str(row.get("fc_id", "")) if has_fc_id else ""
        toks = _parse_type_usager_tokens(val)
        if not toks:
            cat = "Autre"
            agg[cat] = agg.get(cat, 0) + 1
            if has_fc_id and fc_id:
                fc_ids.setdefault(cat, set()).add(fc_id)
            continue
        for lab, n in toks:
            cat = map_type_usager(source_table, source_champ, lab)
            agg[cat] = agg.get(cat, 0) + n
            if has_fc_id and fc_id:
                fc_ids.setdefault(cat, set()).add(fc_id)

    rows = []
    for cat, nb in agg.items():
        nb_ops = len(fc_ids.get(cat, set())) if has_fc_id else 0
        rows.append({"type_usager": cat, "nb": nb, "nb_operations": nb_ops})

    if not rows:
        return pd.DataFrame(columns=["type_usager", "nb", "nb_operations"])

    result = (
        pd.DataFrame(rows)
        .sort_values("nb", ascending=False)
        .reset_index(drop=True)
    )
    return result


def agg_effectifs_usagers_par_domaine(
    df: pd.DataFrame,
    col_domaine: str = "domaine",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Construit la matrice (Type usager × Domaine) pour les effectifs d'usagers."""
    if source_champ not in df.columns:
        return pd.DataFrame(columns=["type_usager"])

    work_df = _consolide_lignes_effectifs_par_fc_id(
        df,
        [source_champ, col_domaine],
        source_table=source_table,
    )

    rows: list[tuple[str, str, int]] = []
    for _, row in work_df.iterrows():
        dom = str(row.get(col_domaine, "Hors domaine") or "Hors domaine")
        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            rows.append(("Autre", dom, 1))
            continue
        for lab, n in toks:
            cat = map_type_usager(source_table, source_champ, lab)
            rows.append((cat, dom, n))

    if not rows:
        return pd.DataFrame(columns=["type_usager"])

    long = pd.DataFrame(rows, columns=["type_usager", "domaine", "nb"])
    cross = long.groupby(["type_usager", "domaine"])["nb"].sum().unstack(fill_value=0)
    cross.index.name = "type_usager"
    return cross.reset_index()


def agg_effectifs_usagers_par_theme(
    df: pd.DataFrame,
    col_theme: str = "theme",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Construit la matrice (Type usager × Thème) pour les effectifs d'usagers."""
    if source_champ not in df.columns:
        return pd.DataFrame(columns=["type_usager", "theme", "nb"])
    theme_col = col_theme if col_theme in df.columns else None
    if theme_col is None and "type_actio" in df.columns:
        theme_col = "type_actio"
    if theme_col is None:
        return pd.DataFrame(columns=["type_usager", "theme", "nb"])

    work_df = _consolide_lignes_effectifs_par_fc_id(
        df,
        [source_champ, theme_col],
        source_table=source_table,
    )

    rows: list[tuple[str, str, int]] = []
    for _, row in work_df.iterrows():
        theme = str(row.get(theme_col, "Hors thème") or "Hors thème")
        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            rows.append(("Autre", theme, 1))
            continue
        for lab, n in toks:
            cat = map_type_usager(source_table, source_champ, lab)
            rows.append((cat, theme, int(n)))

    if not rows:
        return pd.DataFrame(columns=["type_usager", "theme", "nb"])

    long = pd.DataFrame(rows, columns=["type_usager", "theme", "nb"])
    return (
        long.groupby(["type_usager", "theme"], as_index=False)["nb"]
        .sum()
        .sort_values(["type_usager", "nb"], ascending=[True, False], kind="stable")
    )


def agg_controles_par_type_usager_domaine(
    df: pd.DataFrame,
    col_domaine: str = "domaine",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Calcule le nombre de localisations par (type_usager × domaine)."""
    if source_champ not in df.columns:
        return pd.DataFrame(columns=["type_usager", "domaine", "nb_localisations"])

    work_df = _consolide_lignes_effectifs_par_fc_id(
        df,
        [source_champ, col_domaine, "fc_id"] if "fc_id" in df.columns else [source_champ, col_domaine],
        source_table=source_table,
    )

    counts: dict[tuple[str, str], int] = {}
    ops_counts: dict[tuple[str, str], set[str]] = {}
    for _, row in work_df.iterrows():
        dom = str(row.get(col_domaine, "Hors domaine") or "Hors domaine")
        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cats_counts = {"Autre": 1}
        else:
            cats_counts = {}
            for lab, n in toks:
                cat = map_type_usager(source_table, source_champ, lab)
                cats_counts[cat] = 1
        for cat, n in cats_counts.items():
            key = (cat, dom)
            counts[key] = counts.get(key, 0) + n
            if "dc_id" in row and pd.notna(row["dc_id"]):
                if key not in ops_counts:
                    ops_counts[key] = set()
                ops_counts[key].add(str(row["dc_id"]))

    rows: list[dict[str, object]] = []
    for (cat, dom), n in counts.items():
        rows.append({
            "type_usager": cat,
            "domaine": dom,
            "nb_localisations": int(n),
            "nb_operations": len(ops_counts.get((cat, dom), set())),
        })
    return pd.DataFrame(rows)


def agg_controles_par_type_usager_theme(
    df: pd.DataFrame,
    col_theme: str = "theme",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Calcule le nombre de localisations par (type_usager × thème)."""
    if source_champ not in df.columns:
        return pd.DataFrame(columns=["type_usager", "theme", "nb_localisations"])

    work_df = _consolide_lignes_effectifs_par_fc_id(
        df,
        [source_champ, col_theme, "fc_id"] if "fc_id" in df.columns else [source_champ, col_theme],
        source_table=source_table,
    )

    counts: dict[tuple[str, str], int] = {}
    ops_counts: dict[tuple[str, str], set[str]] = {}
    for _, row in work_df.iterrows():
        theme = str(row.get(col_theme, "Hors thème") or "Hors thème")
        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cats_counts = {"Autre": 1}
        else:
            cats_counts = {}
            for lab, n in toks:
                cat = map_type_usager(source_table, source_champ, lab)
                cats_counts[cat] = 1
        for cat, n in cats_counts.items():
            key = (cat, theme)
            counts[key] = counts.get(key, 0) + n
            if "dc_id" in row and pd.notna(row["dc_id"]):
                if key not in ops_counts:
                    ops_counts[key] = set()
                ops_counts[key].add(str(row["dc_id"]))

    rows: list[dict[str, object]] = []
    for (cat, theme), n in counts.items():
        rows.append({
            "type_usager": cat,
            "theme": theme,
            "nb_localisations": int(n),
            "nb_operations": len(ops_counts.get((cat, theme), set())),
        })
    return pd.DataFrame(rows)


def _agg_resultats_par_type_usager_dimension(
    df: pd.DataFrame,
    col_dim: str,
    col_dim_default: str,
    col_resultat: str = "resultat",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Croise les résultats (Conforme/Infraction/Manquement) par type d'usager et dimension géographique ou thématique."""
    base_cols = [
        "type_usager",
        col_dim,
        "nb_conforme",
        "nb_manquement",
        "nb_infraction",
        "nb_en_attente",
        "nb_localisations",
    ]
    if source_champ not in df.columns or col_resultat not in df.columns:
        return pd.DataFrame(columns=base_cols)

    work_df = _consolide_lignes_effectifs_par_fc_id(
        df,
        [source_champ, col_resultat, col_dim],
        source_table=source_table,
    )

    counts: dict[tuple[str, str], dict[str, int]] = {}
    for _, row in work_df.iterrows():
        dim_val = str(row.get(col_dim, col_dim_default) or col_dim_default)
        res_cls = classify_resultat_controle(row.get(col_resultat, ""))

        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cats_counts = {"Autre": 1}
        else:
            cats_counts = {}
            for lab, n in toks:
                cat = map_type_usager(source_table, source_champ, lab)
                cats_counts[cat] = 1

        for cat, n in cats_counts.items():
            key = (cat, dim_val)
            d = counts.setdefault(
                key,
                {
                    "nb_conforme": 0,
                    "nb_manquement": 0,
                    "nb_infraction": 0,
                    "nb_en_attente": 0,
                    "nb_localisations": 0,
                },
            )
            d["nb_localisations"] += n
            if res_cls == "Conforme":
                d["nb_conforme"] += n
            elif res_cls == "Manquement":
                d["nb_manquement"] += n
            elif res_cls == "Infraction":
                d["nb_infraction"] += n
            else:
                d["nb_en_attente"] += n

    rows: list[dict[str, object]] = []
    for (cat, dim_val), d in counts.items():
        rows.append(
            {
                "type_usager": cat,
                col_dim: dim_val,
                "nb_conforme": int(d["nb_conforme"]),
                "nb_manquement": int(d["nb_manquement"]),
                "nb_infraction": int(d["nb_infraction"]),
                "nb_en_attente": int(d["nb_en_attente"]),
                "nb_localisations": int(d["nb_localisations"]),
            }
        )
    return pd.DataFrame(rows)


def agg_resultats_par_type_usager_domaine(
    df: pd.DataFrame,
    col_domaine: str = "domaine",
    col_resultat: str = "resultat",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Ventile les résultats de contrôle par type d'usager et domaine."""
    return _agg_resultats_par_type_usager_dimension(
        df,
        col_domaine,
        "Hors domaine",
        col_resultat=col_resultat,
        source_table=source_table,
        source_champ=source_champ,
    )


def agg_resultats_par_type_usager_theme(
    df: pd.DataFrame,
    col_theme: str = "theme",
    col_resultat: str = "resultat",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Ventile les résultats de contrôle par type d'usager et thème."""
    return _agg_resultats_par_type_usager_dimension(
        df,
        col_theme,
        "Hors thème",
        col_resultat=col_resultat,
        source_table=source_table,
        source_champ=source_champ,
    )


def agg_resultat_counts_par_type_usager(
    df: pd.DataFrame,
    col_resultat: str = "resultat",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Nombre de contrôles par catégorie de résultat et type d'usager."""
    if source_champ not in df.columns or col_resultat not in df.columns:
        return pd.DataFrame(
            columns=[
                "type_usager",
                "Conforme",
                "Infraction",
                "Manquement",
                "Autre_resultat",
                "Total",
            ]
        )

    buckets = ("Conforme", "Infraction", "Manquement", "Autre_resultat")
    counts: dict[str, dict[str, int]] = {}

    work_df = _consolide_lignes_effectifs_par_fc_id(
        df,
        [source_champ, col_resultat],
        source_table=source_table,
    )

    for _, row in work_df.iterrows():
        res = str(row.get(col_resultat, "") or "").strip()
        if res == "Infraction":
            b = "Infraction"
        elif res == "Manquement":
            b = "Manquement"
        elif res == "Conforme":
            b = "Conforme"
        else:
            b = "Autre_resultat"

        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cat = "Autre"
            d = counts.setdefault(cat, {k: 0 for k in buckets})
            d[b] += 1
            continue

        cats = set()
        for lab, n in toks:
            cats.add(map_type_usager(source_table, source_champ, lab))

        for cat in cats:
            d = counts.setdefault(cat, {k: 0 for k in buckets})
            d[b] += 1

    rows: list[dict[str, object]] = []
    for cat in sorted(counts.keys(), key=lambda x: (-sum(counts[x].values()), x)):
        d = counts[cat]
        tot = sum(d.values())
        row = {"type_usager": cat, "Total": tot}
        for k in buckets:
            row[k] = int(d[k])
        rows.append(row)
    return pd.DataFrame(rows)


def count_multi_usager_controles(
    df: pd.DataFrame,
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> int:
    """Compte le nombre de fiches de contrôle impliquant au moins deux catégories d'usagers."""
    if source_champ not in df.columns or df.empty:
        return 0
    work_df = _consolide_lignes_effectifs_par_fc_id(df, [source_champ], source_table=source_table)
    return int(
        sum(1 for val in work_df[source_champ] if len(_parse_type_usager_tokens(val)) > 1)
    )


def agg_resultat_effectifs_par_type_usager(
    df: pd.DataFrame,
    col_resultat: str = "resultat",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Ventilation des effectifs d'usagers selon le résultat du contrôle."""
    if source_champ not in df.columns or col_resultat not in df.columns:
        return pd.DataFrame(
            columns=[
                "type_usager",
                "Conforme",
                "Infraction",
                "Manquement",
                "Autre_resultat",
                "Total",
            ]
        )

    buckets = ("Conforme", "Infraction", "Manquement", "Autre_resultat")
    counts: dict[str, dict[str, int]] = {}

    work_df = _consolide_lignes_effectifs_par_fc_id(
        df,
        [source_champ, col_resultat],
        source_table=source_table,
    )

    for _, row in work_df.iterrows():
        res = str(row.get(col_resultat, "") or "").strip()
        if res == "Infraction":
            b = "Infraction"
        elif res == "Manquement":
            b = "Manquement"
        elif res == "Conforme":
            b = "Conforme"
        else:
            b = "Autre_resultat"

        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cat = "Autre"
            d = counts.setdefault(cat, {k: 0 for k in buckets})
            d[b] += 1
            continue
        for lab, n in toks:
            cat = map_type_usager(source_table, source_champ, lab)
            d = counts.setdefault(cat, {k: 0 for k in buckets})
            d[b] += int(n)

    rows: list[dict[str, object]] = []
    for cat in sorted(counts.keys(), key=lambda x: (-sum(counts[x].values()), x)):
        d = counts[cat]
        tot = sum(d.values())
        row = {"type_usager": cat, "Total": tot}
        for k in buckets:
            row[k] = int(d[k])
        rows.append(row)
    return pd.DataFrame(rows)


# ========================================================================================
# PROCEDURES D'ENQUETE ET SUITES ADMINISTRATIVES (PEJ ET PA)
# ========================================================================================

def is_filled_procedure_code(value: Any) -> bool:
    """Vérifie si un identifiant de procédure judiciaire ou administrative est renseigné."""
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    if pd.isna(value):
        return False
    s = str(value).strip()
    if not s:
        return False
    if s.lower() in ("nan", "none", "<na>", "nat"):
        return False
    return True


def resultat_induit_pa(value: Any) -> bool:
    """Détermine si un résultat de contrôle implique l'ouverture d'une procédure administrative (Manquement)."""
    s = str(value or "").strip().lower()
    if not s or s in ("nan", "none", "<na>"):
        return False
    return "manquement" in s


def mask_resultat_induit_pa(resultat: pd.Series) -> pd.Series:
    """Masque booléen des contrôles générant une procédure administrative."""
    return resultat.map(resultat_induit_pa)


def filter_points_induisant_pa(point: pd.DataFrame) -> pd.DataFrame:
    """Filtre les contrôles assortis d'un code de procédure administrative."""
    if point is None or point.empty or "code_pa" not in point.columns:
        return point.iloc[0:0].copy() if point is not None and not point.empty else pd.DataFrame()
    return point.loc[point["code_pa"].map(is_filled_procedure_code)].copy()


def count_pa_induites_par_controles(
    point: pd.DataFrame,
    *,
    mask: pd.Series | None = None,
) -> int:
    """Compte le nombre de procédures administratives issues des contrôles."""
    if point is None or point.empty or "code_pa" not in point.columns:
        return 0
    sub = point.loc[mask] if mask is not None else point
    if sub.empty:
        return 0
    return int(sub["code_pa"].map(is_filled_procedure_code).sum())


def points_as_pa_lignes(point: pd.DataFrame) -> pd.DataFrame:
    """Extrait les caractéristiques des contrôles générant une PA pour les intégrer au chapitre Procédures."""
    sub = filter_points_induisant_pa(point)
    cols = ["DOMAINE", "THEME", "type_usager", "DC_ID", "DATE_REF"]
    if sub.empty:
        return pd.DataFrame(columns=cols)

    out = pd.DataFrame(index=sub.index)
    if "domaine" in sub.columns:
        out["DOMAINE"] = sub["domaine"].fillna("Hors domaine").astype(str)
    elif "DOMAINE" in sub.columns:
        out["DOMAINE"] = sub["DOMAINE"].fillna("Hors domaine").astype(str)
    else:
        out["DOMAINE"] = "Hors domaine"

    if "theme" in sub.columns:
        out["THEME"] = sub["theme"].fillna("Hors thème").astype(str)
    elif "THEME" in sub.columns:
        out["THEME"] = sub["THEME"].fillna("Hors thème").astype(str)
    else:
        out["THEME"] = "Hors thème"

    if "type_usager" in sub.columns:
        out["type_usager"] = sub["type_usager"]

    if "dc_id" in sub.columns:
        out["DC_ID"] = sub["dc_id"]
    elif "DC_ID" in sub.columns:
        out["DC_ID"] = sub["DC_ID"]

    if "date_ctrl" in sub.columns:
        out["DATE_REF"] = sub["date_ctrl"]
    elif "DATE_REF" in sub.columns:
        out["DATE_REF"] = sub["DATE_REF"]

    return out.loc[:, [c for c in cols if c in out.columns]].reset_index(drop=True)


def agg_procedures_par_type_usager_domaine(
    df: pd.DataFrame,
    col_domaine: str = "domaine",
    col_code_pej: str = "code_pej",
    col_code_pa: str = "code_pa",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Ventile l'ensemble des procédures (PEJ/PA/PVe) par type d'usager et domaine."""
    if source_champ not in df.columns:
        return pd.DataFrame(
            columns=["type_usager", "domaine", "nb_pej", "nb_pa", "nb_pve"]
        )

    counts: dict[tuple[str, str], dict[str, int]] = {}
    for _, row in df.iterrows():
        dom = str(row.get(col_domaine, "Hors domaine") or "Hors domaine")
        has_pej = is_filled_procedure_code(row.get(col_code_pej))
        has_pa = is_filled_procedure_code(row.get(col_code_pa))
        has_pve = False

        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cats_counts = {"Autre": 1}
        else:
            cats_counts = {}
            for lab, n in toks:
                cat = map_type_usager(source_table, source_champ, lab)
                cats_counts[cat] = cats_counts.get(cat, 0) + n

        for cat, n in cats_counts.items():
            key = (cat, dom)
            d = counts.setdefault(
                key,
                {
                    "nb_pej": 0,
                    "nb_pa": 0,
                    "nb_pve": 0,
                },
            )
            if has_pej:
                d["nb_pej"] += n
            if has_pa:
                d["nb_pa"] += n
            if has_pve:
                d["nb_pve"] += n

    rows: list[dict[str, object]] = []
    for (cat, dom), d in counts.items():
        rows.append(
            {
                "type_usager": cat,
                "domaine": dom,
                "nb_pej": int(d["nb_pej"]),
                "nb_pa": int(d["nb_pa"]),
                "nb_pve": int(d["nb_pve"]),
            }
        )
    return pd.DataFrame(rows)


def agg_procedures_par_type_usager_theme(
    df: pd.DataFrame,
    col_theme: str = "theme",
    col_code_pej: str = "code_pej",
    col_code_pa: str = "code_pa",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Ventile l'ensemble des procédures (PEJ/PA/PVe) par type d'usager et thème."""
    if source_champ not in df.columns:
        return pd.DataFrame(
            columns=["type_usager", "theme", "nb_pej", "nb_pa", "nb_pve"]
        )

    counts: dict[tuple[str, str], dict[str, int]] = {}
    for _, row in df.iterrows():
        theme = str(row.get(col_theme, "Hors thème") or "Hors thème")
        has_pej = is_filled_procedure_code(row.get(col_code_pej))
        has_pa = is_filled_procedure_code(row.get(col_code_pa))
        has_pve = False

        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cats_counts = {"Autre": 1}
        else:
            cats_counts = {}
            for lab, n in toks:
                cat = map_type_usager(source_table, source_champ, lab)
                cats_counts[cat] = cats_counts.get(cat, 0) + n

        for cat, n in cats_counts.items():
            key = (cat, theme)
            d = counts.setdefault(
                key,
                {
                    "nb_pej": 0,
                    "nb_pa": 0,
                    "nb_pve": 0,
                },
            )
            if has_pej:
                d["nb_pej"] += n
            if has_pa:
                d["nb_pa"] += n
            if has_pve:
                d["nb_pve"] += n

    rows: list[dict[str, object]] = []
    for (cat, theme), d in counts.items():
        rows.append(
            {
                "type_usager": cat,
                "theme": theme,
                "nb_pej": int(d["nb_pej"]),
                "nb_pa": int(d["nb_pa"]),
                "nb_pve": int(d["nb_pve"]),
            }
        )
    return pd.DataFrame(rows)


def count_procedures_liees_controle_sur_points(
    point: pd.DataFrame,
    *,
    mask: pd.Series | None = None,
) -> tuple[int, int]:
    """Compte séparément les PEJ et PA engagées directement après un contrôle."""
    if point is None or point.empty:
        return 0, 0
    sub = point.loc[mask] if mask is not None else point
    if sub.empty:
        return 0, 0
    nb_pej = 0
    if "code_pej" in sub.columns:
        nb_pej = int(sub["code_pej"].map(is_filled_procedure_code).sum())
    nb_pa = count_pa_induites_par_controles(sub)
    return nb_pej, nb_pa


def _col_domaine_procedure(df: pd.DataFrame) -> str | None:
    for name in ("DOMAINE", "domaine"):
        if name in df.columns:
            return name
    return None


def _col_theme_procedure(df: pd.DataFrame) -> str | None:
    for name in ("THEME", "theme"):
        if name in df.columns:
            return name
    return None


def _iter_type_usager_domaine_keys(
    row: pd.Series,
    dim_value: str,
    *,
    with_type_usager: bool,
    source_table: str,
    source_champ: str,
) -> list[tuple[str | None, str]]:
    if with_type_usager and source_champ in row.index:
        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cats = ["Autre"]
        else:
            cats = list(
                {map_type_usager(source_table, source_champ, lab) for lab, _ in toks}
            )
        return [(cat, dim_value) for cat in cats]
    return [(None, dim_value)]


def agg_procedures_dossiers_par_domaine(
    pej: pd.DataFrame,
    pa: pd.DataFrame,
    *,
    with_type_usager: bool = False,
    source_table: str = "pej",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Agrège l'intégralité des dossiers de procédures (PEJ et PA) par domaine d'intervention."""
    counts: dict[tuple[str | None, str], dict[str, int]] = {}

    def _add_rows(df: pd.DataFrame, field: str) -> None:
        if df is None or df.empty:
            return
        dom_col = _col_domaine_procedure(df)
        if dom_col is None:
            return
        for _, row in df.iterrows():
            dom = str(row.get(dom_col) or "Hors domaine")
            for key in _iter_type_usager_domaine_keys(
                row,
                dom,
                with_type_usager=with_type_usager,
                source_table=source_table,
                source_champ=source_champ,
            ):
                bucket = counts.setdefault(key, {"nb_pej": 0, "nb_pa": 0, "nb_pve": 0})
                bucket[field] += 1

    _add_rows(pej, "nb_pej")
    _add_rows(pa, "nb_pa")

    if not counts:
        cols = (
            ["type_usager", "domaine", "nb_pej", "nb_pa", "nb_pve"]
            if with_type_usager
            else ["domaine", "nb_pej", "nb_pa", "nb_pve"]
        )
        return pd.DataFrame(columns=cols)

    rows: list[dict[str, object]] = []
    for (cat, dom), d in sorted(counts.items(), key=lambda x: (-(x[1]["nb_pej"] + x[1]["nb_pa"]), x[0][1])):
        row: dict[str, object] = {
            "domaine": dom,
            "nb_pej": int(d["nb_pej"]),
            "nb_pa": int(d["nb_pa"]),
            "nb_pve": int(d["nb_pve"]),
        }
        if cat is not None:
            row = {"type_usager": cat, **row}
        rows.append(row)
    return pd.DataFrame(rows)


def agg_procedures_dossiers_par_theme(
    pej: pd.DataFrame,
    pa: pd.DataFrame,
    *,
    with_type_usager: bool = False,
    source_table: str = "pej",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """Agrège l'intégralité des dossiers de procédures (PEJ et PA) par thème d'intervention."""
    counts: dict[tuple[str | None, str], dict[str, int]] = {}

    def _add_rows(df: pd.DataFrame, field: str) -> None:
        if df is None or df.empty:
            return
        th_col = _col_theme_procedure(df)
        if th_col is None:
            return
        for _, row in df.iterrows():
            theme = str(row.get(th_col) or "Hors thème")
            for key in _iter_type_usager_domaine_keys(
                row,
                theme,
                with_type_usager=with_type_usager,
                source_table=source_table,
                source_champ=source_champ,
            ):
                bucket = counts.setdefault(key, {"nb_pej": 0, "nb_pa": 0, "nb_pve": 0})
                bucket[field] += 1

    _add_rows(pej, "nb_pej")
    _add_rows(pa, "nb_pa")

    if not counts:
        cols = (
            ["type_usager", "theme", "nb_pej", "nb_pa", "nb_pve"]
            if with_type_usager
            else ["theme", "nb_pej", "nb_pa", "nb_pve"]
        )
        return pd.DataFrame(columns=cols)

    rows: list[dict[str, object]] = []
    for (cat, theme), d in sorted(
        counts.items(), key=lambda x: (-(x[1]["nb_pej"] + x[1]["nb_pa"]), x[0][1])
    ):
        row: dict[str, object] = {
            "theme": theme,
            "nb_pej": int(d["nb_pej"]),
            "nb_pa": int(d["nb_pa"]),
            "nb_pve": int(d["nb_pve"]),
        }
        if cat is not None:
            row = {"type_usager": cat, **row}
        rows.append(row)
    return pd.DataFrame(rows)


# ========================================================================================
# FILTRAGE PAR DATE ET REGLES METIERS SPECIFIQUES (CHASSE, NATINF)
# ========================================================================================

def filtre_periode(
    df: pd.DataFrame, col_date: str, date_deb: pd.Timestamp, date_fin: pd.Timestamp
) -> pd.DataFrame:
    """Filtre les données sur la plage temporelle du bilan."""
    return df[(df[col_date] >= date_deb) & (df[col_date] <= date_fin)].copy()


def resume_resultat(s: pd.Series) -> str:
    """Synthétise le résultat global d'une opération à partir des résultats de ses localisations."""
    vals = s.dropna()
    if vals.empty:
        return "Inconnu"
    if "Infraction" in vals.values:
        return "Infraction"
    if "Manquement" in vals.values:
        return "Manquement"
    mode = vals.mode()
    return mode.iloc[0] if not mode.empty else "Conforme"


def est_chasse_thematique(theme: str, type_action: str) -> bool:
    """Détecte les actions relatives à la police de la chasse."""
    t = (theme or "").lower()
    a = (type_action or "").lower()
    return ("chasse" in t) or ("chasse" in a) or ("police de la chasse" in t)


def est_chasse_point(row: pd.Series) -> bool:
    """Indique si un point de contrôle relève du thème Chasse."""
    return est_chasse_thematique(row.get("theme"), row.get("type_actio"))


def contient_natinf(s: str, natinf_list: List[str]) -> bool:
    """Vérifie si une chaîne contient l'un des codes d'infractions NATINF cibles."""
    s = str(s) if pd.notna(s) else ""
    for code in natinf_list:
        pattern = rf"\b{code}\b"
        if re.search(pattern, s):
            return True
    return False


def count_controles_non_conformes_oscean(resultat: pd.Series) -> int:
    """Compte les contrôles non conformes (Infraction ou Manquement)."""
    r = classify_resultat_controle_series(resultat)
    return int(r.isin(("Infraction", "Manquement")).sum())


def classify_resultat_controle(value: Any) -> str:
    """Normalise un libellé de résultat vers l'un des 4 statuts : Conforme, Infraction, Manquement, En attente."""
    s = str(value or "").strip()
    if not s or s.lower() in ("nan", "none", "<na>"):
        return "En attente"
    key = s.lower()
    if key == "conforme":
        return "Conforme"
    if key == "infraction":
        return "Infraction"
    if key == "manquement":
        return "Manquement"
    return "En attente"


def classify_resultat_controle_series(resultat: pd.Series) -> pd.Series:
    """Applique `classify_resultat_controle` sur une série Pandas."""
    return resultat.map(classify_resultat_controle)


def build_tab_resultats(point: pd.DataFrame) -> pd.DataFrame:
    """Génère le tableau de synthèse des résultats de contrôles (Effectifs et Taux %)."""
    nb_total = len(point)
    if nb_total == 0 or "resultat" not in point.columns:
        return pd.DataFrame(columns=["resultat", "nb", "taux"])

    r_norm = classify_resultat_controle_series(point["resultat"])
    rows: list[dict[str, object]] = []
    for label in ("Conforme", "Manquement", "Infraction", "En attente"):
        nb = int((r_norm == label).sum())
        if nb > 0:
            rows.append(
                {
                    "resultat": label,
                    "nb": nb,
                    "taux": nb / float(nb_total),
                }
            )
    return pd.DataFrame(rows)


# ========================================================================================
# CLASSIFICATION ZONAGE SPATIAL (PNF, TUB, COEUR / AIRE)
# ========================================================================================

ZONE_LECTEUR_COEUR = "Coeur de parc"
ZONE_LECTEUR_AIRE = "Aire d'adhésion"
ZONE_LECTEUR_TUB = "Zone TUB"
ZONE_LECTEUR_HORS = "Hors PNF/TUB"
ZONE_LECTEUR_ORDER: tuple[str, ...] = (
    ZONE_LECTEUR_COEUR,
    ZONE_LECTEUR_AIRE,
    ZONE_LECTEUR_TUB,
    ZONE_LECTEUR_HORS,
)
ZONE_PEJ_LOCALISATION_ATTENTE = "Localisation en attente"
ZONE_PEJ_LECTEUR_TABLE_ORDER: tuple[str, ...] = (
    *ZONE_LECTEUR_ORDER,
    ZONE_PEJ_LOCALISATION_ATTENTE,
)


def coalesced_insee_series(df: pd.DataFrame) -> pd.Series:
    """Combines les différentes colonnes INSEE possibles pour extraire le code commune à 5 chiffres."""
    if df is None or df.empty:
        return pd.Series(pd.NA, index=df.index, dtype="string")
    out = pd.Series(pd.NA, index=df.index, dtype="string")
    for col in ("insee_comm", "insee_commun", "INSEE_COM", "INF-INSEE"):
        if col not in df.columns:
            continue
        out = out.fillna(extract_insee_code_series(df[col]))
    return out


def _normalize_insee_code(insee: Any) -> str | None:
    """Normalise un code INSEE au format strict 5 chiffres."""
    if insee is None or (isinstance(insee, float) and pd.isna(insee)):
        return None
    s = str(insee).strip()
    if not s or s.lower() in {"nan", "none", "<na>"}:
        return None
    m = re.search(r"(\d{1,5})", s)
    if not m:
        return None
    code = m.group(1).zfill(5)
    if code == "00000":
        return None
    return code if re.fullmatch(r"\d{5}", code) else None


def zone_lecteur_label(
    pnf_zone_sig: Any,
    insee: Any,
    tub_codes: set[str] | set,
) -> str:
    """Retourne la zone réglementaire exclusive (Cœur PNF, Aire d'adhésion, Zone TUB, Hors PNF/TUB)."""
    if pnf_zone_sig is not None and not (isinstance(pnf_zone_sig, float) and pd.isna(pnf_zone_sig)):
        sig = str(pnf_zone_sig).strip()
        if sig == "Coeur_PNF":
            return ZONE_LECTEUR_COEUR
        if sig == "Aire_adhesion_PNF":
            return ZONE_LECTEUR_AIRE
    code = _normalize_insee_code(insee)
    if not code:
        return "n.d."
    tub = {str(c).zfill(5) for c in tub_codes}
    if code in tub:
        return ZONE_LECTEUR_TUB
    return ZONE_LECTEUR_HORS


def classify_zone_lecteur_series(
    df: pd.DataFrame,
    tub_codes: set[str] | set,
    *,
    pnf_zone_col: str = "pnf_zone_sig",
) -> pd.Series:
    """Associe à chaque ligne d'un DataFrame sa zone réglementaire exclusive."""
    tub = {str(c).zfill(5) for c in tub_codes}
    insee = coalesced_insee_series(df)
    out = pd.Series(ZONE_LECTEUR_HORS, index=df.index, dtype="string")
    if pnf_zone_col in df.columns:
        z = df[pnf_zone_col].astype("string")
        out = out.mask(z.eq("Coeur_PNF"), ZONE_LECTEUR_COEUR)
        out = out.mask(z.eq("Aire_adhesion_PNF"), ZONE_LECTEUR_AIRE)
        hors_sig = ~z.isin(["Coeur_PNF", "Aire_adhesion_PNF"])
    else:
        hors_sig = pd.Series(True, index=df.index)
    in_tub = insee.astype("string").isin(tub)
    out = out.mask(hors_sig & in_tub, ZONE_LECTEUR_TUB)
    return out


def format_zone_lecteur_counts(zones: pd.Series, mask: pd.Series) -> str:
    """Formate les comptes de contrôles par zone sous forme de texte 'Zone : n, ...'."""
    sub = zones.loc[mask]
    parts: list[str] = []
    for label in ZONE_LECTEUR_ORDER:
        n = int((sub == label).sum())
        if n > 0:
            parts.append(f"{label} : {n}")
    return ", ".join(parts)


def zone_lecteur_counts_for_pdf_cell(text: str) -> str:
    """Formate le texte de zone pour insertion dans une cellule de tableau PDF (`<br/>`)."""
    from xml.sax.saxutils import escape

    raw = str(text or "").strip()
    if not raw or raw == "n.d.":
        return raw
    if ", " not in raw:
        return escape(raw)
    parts = [p.strip() for p in raw.split(", ") if p.strip()]
    return "<br/>".join(escape(p) for p in parts)


def build_tab_resultats_controles(
    point: pd.DataFrame,
    *,
    distinction_coeur_hors_coeur: bool = False,
    zone_lecteur_4_zones: bool = False,
    tub_codes: set[str] | set | None = None,
) -> pd.DataFrame:
    """Construit le tableau détaillé des résultats de contrôles avec répartition spatiale."""
    nb_total = len(point)
    if nb_total == 0 or "resultat" not in point.columns:
        return pd.DataFrame(columns=["resultat", "nb", "taux"])

    r_norm = classify_resultat_controle_series(point["resultat"])
    nb_conf = int((r_norm == "Conforme").sum())
    nb_inf = int((r_norm == "Infraction").sum())
    nb_manq = int((r_norm == "Manquement").sum())
    nb_en_attente = int((r_norm == "En attente").sum())
    nb_nc = nb_inf + nb_manq

    show_zone_col = distinction_coeur_hors_coeur or zone_lecteur_4_zones
    tub_set = tub_codes if isinstance(tub_codes, set) else set()

    if show_zone_col and zone_lecteur_4_zones:
        zones = classify_zone_lecteur_series(point, tub_set)

        def _zone_txt(mask: pd.Series) -> str:
            return format_zone_lecteur_counts(zones, mask)

        details_rows: list[dict[str, Any]] = [
            {
                "resultat": "Conforme",
                "nb": nb_conf,
                "coeur_hors_coeur": _zone_txt(r_norm.eq("Conforme")),
            },
            {
                "resultat": "Non-conforme",
                "nb": nb_nc,
                "coeur_hors_coeur": _zone_txt(r_norm.isin(["Infraction", "Manquement"])),
            },
            {
                "resultat": "    Dont manquement",
                "nb": nb_manq,
                "coeur_hors_coeur": _zone_txt(r_norm.eq("Manquement")),
            },
            {
                "resultat": "    Dont infraction",
                "nb": nb_inf,
                "coeur_hors_coeur": _zone_txt(r_norm.eq("Infraction")),
            },
        ]
        if nb_en_attente > 0:
            details_rows.append(
                {"resultat": "En attente", "nb": nb_en_attente, "coeur_hors_coeur": "n.d."}
            )
    elif show_zone_col and distinction_coeur_hors_coeur:
        z = (
            point["pnf_zone_sig"].astype(str)
            if "pnf_zone_sig" in point.columns
            else pd.Series([""] * nb_total, index=point.index)
        )
        is_coeur = z.eq("Coeur_PNF")
        is_hors = ~is_coeur

        def _coeur_hors_row(mask: pd.Series) -> dict[str, int]:
            c = int((mask & is_coeur).sum())
            h = int((mask & is_hors).sum())
            return {"coeur": c, "aoa": h}

        details_rows = [
            {
                "resultat": "Conforme",
                "nb": nb_conf,
                **_coeur_hors_row(r_norm.eq("Conforme")),
            },
            {
                "resultat": "Non-conforme",
                "nb": nb_nc,
                **_coeur_hors_row(r_norm.isin(["Infraction", "Manquement"])),
            },
            {
                "resultat": "    Dont manquement",
                "nb": nb_manq,
                **_coeur_hors_row(r_norm.eq("Manquement")),
            },
            {
                "resultat": "    Dont infraction",
                "nb": nb_inf,
                **_coeur_hors_row(r_norm.eq("Infraction")),
            },
        ]
        if nb_en_attente > 0:
            details_rows.append(
                {"resultat": "En attente", "nb": nb_en_attente, "coeur": 0, "aoa": 0}
            )
    else:
        details_rows = [
            {"resultat": "Conforme", "nb": nb_conf},
            {"resultat": "Non-conforme", "nb": nb_nc},
            {"resultat": "    Dont manquement", "nb": nb_manq},
            {"resultat": "    Dont infraction", "nb": nb_inf},
        ]
        if nb_en_attente > 0:
            details_rows.append({"resultat": "En attente", "nb": nb_en_attente})

    res_ctrl = pd.DataFrame(details_rows)
    if not res_ctrl.empty:
        res_ctrl["taux"] = res_ctrl["nb"] / float(nb_total or 1)
    return res_ctrl


ZONE_KEY_DEPARTEMENT = "Département"
ZONE_LABEL_DEPARTEMENT_HORS = "Département (hors zone TUB/PNF)"


def build_zone_pej_from_proc_detail_lecteur(pej_detail: pd.DataFrame) -> pd.DataFrame:
    """Agrège les PEJ par zone réglementaire à partir du tableau détaillé des procédures."""
    if pej_detail is None or pej_detail.empty or "coeur_hors_coeur" not in pej_detail.columns:
        return pd.DataFrame(columns=["zone", "nb"])
    ch = pej_detail["coeur_hors_coeur"].astype(str).str.strip()
    pending = ch.isin(["n.d.", "nan", "None", "", "<na>"])
    rows: list[dict[str, int | str]] = []
    for label in ZONE_LECTEUR_ORDER:
        rows.append({"zone": label, "nb": int((ch == label).sum())})
    rows.append({"zone": ZONE_PEJ_LOCALISATION_ATTENTE, "nb": int(pending.sum())})
    return pd.DataFrame(rows)


def zone_table_display_label(zone: str) -> str:
    """Formate l'intitulé des zones d'étude pour la restitution PDF."""
    if str(zone).strip() == ZONE_KEY_DEPARTEMENT:
        return ZONE_LABEL_DEPARTEMENT_HORS
    return str(zone)


def _mask_hors_tub_pnf(insee: pd.Series, tub_codes: set, pnf_codes: set) -> pd.Series:
    """Masque des communes n'appartenant ni au périmètre TUB ni au périmètre PNF."""
    return ~insee.isin(tub_codes) & ~insee.isin(pnf_codes)


def _zone_summary(
    df: pd.DataFrame,
    col_insee: str,
    tub_codes: set,
    pnf_codes: set,
) -> pd.DataFrame:
    """Synthétise les contrôles et les taux de non-conformité par zone (Hors PNF/TUB, TUB, PNF)."""
    insee = df[col_insee].astype(str).str.zfill(5)
    rows = []

    sub_dep = df[_mask_hors_tub_pnf(insee, tub_codes, pnf_codes)]
    total = len(sub_dep)
    if "resultat" in sub_dep.columns and not sub_dep.empty:
        nb_nc_dept = count_controles_non_conformes_oscean(sub_dep["resultat"])
    else:
        nb_nc_dept = 0
    nb_conf_dept = total - nb_nc_dept
    rows.append(
        {
            "zone": ZONE_KEY_DEPARTEMENT,
            "nb_total": total,
            "nb_conforme": nb_conf_dept,
            "nb_non_conforme": nb_nc_dept,
        }
    )

    mask_tub = insee.isin(tub_codes)
    sub_tub = df[mask_tub]
    if "resultat" in sub_tub.columns and not sub_tub.empty:
        nb_nc_tub = count_controles_non_conformes_oscean(sub_tub["resultat"])
    else:
        nb_nc_tub = 0
    rows.append(
        {
            "zone": "Zone TUB",
            "nb_total": len(sub_tub),
            "nb_conforme": len(sub_tub) - nb_nc_tub,
            "nb_non_conforme": nb_nc_tub,
        }
    )

    mask_pnf = insee.isin(pnf_codes)
    sub_pnf = df[mask_pnf]
    if "resultat" in sub_pnf.columns and not sub_pnf.empty:
        nb_nc_pnf = count_controles_non_conformes_oscean(sub_pnf["resultat"])
    else:
        nb_nc_pnf = 0
    rows.append(
        {
            "zone": "PNF",
            "nb_total": len(sub_pnf),
            "nb_conforme": len(sub_pnf) - nb_nc_pnf,
            "nb_non_conforme": nb_nc_pnf,
        }
    )

    summary = pd.DataFrame(rows)
    summary["taux_non_conformite"] = (
        summary["nb_non_conforme"] / summary["nb_total"].replace(0, pd.NA)
    )
    return summary


def _zone_count(
    df: pd.DataFrame,
    col_insee: str,
    tub_codes: set,
    pnf_codes: set,
) -> pd.DataFrame:
    """Compte le nombre de dossiers par zone (pour les procédures PVe ou PEJ)."""
    insee = df[col_insee].astype(str).str.zfill(5)
    rows = [
        {
            "zone": ZONE_KEY_DEPARTEMENT,
            "nb": int(_mask_hors_tub_pnf(insee, tub_codes, pnf_codes).sum()),
        },
        {"zone": "Zone TUB", "nb": int(insee.isin(tub_codes).sum())},
        {"zone": "PNF", "nb": int(insee.isin(pnf_codes).sum())},
    ]
    return pd.DataFrame(rows)


def _load_csv_opt(out_dir: Path, name: str) -> pd.DataFrame | None:
    """Charge un fichier CSV optionnel s'il existe dans le répertoire de sortie."""
    p = out_dir / name
    if not p.exists():
        return None
    try:
        return pd.read_csv(p, sep=";", encoding="utf-8")
    except pd.errors.EmptyDataError:
        return None
    except UnicodeDecodeError:
        return pd.read_csv(p, sep=";", encoding="latin-1")


# Dictionnaire statique des noms de départements français
DEPT_NAMES: dict[str, str] = {
    "01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes", "06": "Alpes-Maritimes", "07": "Ardèche", "08": "Ardennes",
    "09": "Ariège", "10": "Aube", "11": "Aude", "12": "Aveyron",
    "13": "Bouches-du-Rhône", "14": "Calvados", "15": "Cantal", "16": "Charente",
    "17": "Charente-Maritime", "18": "Cher", "19": "Corrèze", "2A": "Corse-du-Sud",
    "2B": "Haute-Corse", "21": "Côte-d'Or", "22": "Côtes-d'Armor", "23": "Creuse",
    "24": "Dordogne", "25": "Doubs", "26": "Drôme", "27": "Eure",
    "28": "Eure-et-Loir", "29": "Finistère", "30": "Gard", "31": "Haute-Garonne",
    "32": "Gers", "33": "Gironde", "34": "Hérault", "35": "Ille-et-Vilaine",
    "36": "Indre", "37": "Indre-et-Loire", "38": "Isère", "39": "Jura",
    "40": "Landes", "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire",
    "44": "Loire-Atlantique", "45": "Loiret", "46": "Lot", "47": "Lot-et-Garonne",
    "48": "Lozère", "49": "Maine-et-Loire", "50": "Manche", "51": "Marne",
    "52": "Haute-Marne", "53": "Mayenne", "54": "Meurthe-et-Moselle", "55": "Meuse",
    "56": "Morbihan", "57": "Moselle", "58": "Nièvre", "59": "Nord",
    "60": "Oise", "61": "Orne", "62": "Pas-de-Calais", "63": "Puy-de-Dôme",
    "64": "Pyrénées-Atlantiques", "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales",
    "67": "Bas-Rhin", "68": "Haut-Rhin", "69": "Rhône", "70": "Haute-Saône",
    "71": "Saône-et-Loire", "72": "Sarthe", "73": "Savoie", "74": "Haute-Savoie",
    "75": "Paris", "76": "Seine-Maritime", "77": "Seine-et-Marne", "78": "Yvelines",
    "79": "Deux-Sèvres", "80": "Somme", "81": "Tarn", "82": "Tarn-et-Garonne",
    "83": "Var", "84": "Vaucluse", "85": "Vendée", "86": "Vienne",
    "87": "Haute-Vienne", "88": "Vosges", "89": "Yonne", "90": "Territoire de Belfort",
    "91": "Essonne", "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne", "95": "Val-d'Oise",
    "971": "Guadeloupe", "972": "Martinique", "973": "Guyane",
    "974": "La Réunion", "976": "Mayotte",
}


def get_dept_name(code: str) -> str:
    """Retourne le nom d'un département à partir de son numéro d'INSEE."""
    c = str(code).strip()
    if c in DEPT_NAMES:
        return DEPT_NAMES[c]
    tokens = [t.strip() for t in c.replace("_", ",").split(",") if t.strip()]
    if len(tokens) > 1 and all(t in DEPT_NAMES or t.isdigit() for t in tokens):
        names = [DEPT_NAMES.get(t, t) for t in tokens]
        if len(names) == 2:
            return f"{names[0]} et {names[1]}"
        return f"{', '.join(names[:-1])} et {names[-1]}"
    reg_name = get_region_name(c)
    if reg_name != f"Région {c}":
        return reg_name
    return f"Département {c}"


def _detect_insee_column(communes: Any) -> str:
    """Détecte le nom de la colonne INSEE dans un GeoDataFrame de communes."""
    candidats = ["INSEE", "INSEE_COM", "CODE_INSEE", "INSEE_COMM", "INSEECO"]
    for col in candidats:
        if col in communes.columns:
            return col
    raise ValueError(
        "Impossible de trouver une colonne INSEE dans la couche communes."
    )