"""Utilitaires partagés pour les bilans (filtrage, résumés, détection colonnes)."""
import functools
import logging
import re
from pathlib import Path
from typing import Any, List

import geopandas as gpd
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_TYPES_USAGERS_PATH = _PROJECT_ROOT / "ref" / "programme" / "tables_reference" / "types_usagers.csv"
logger = logging.getLogger(__name__)


def _norm_key(s: str) -> str:
    return (s or "").strip().lower()


def series_as_python_str(series: pd.Series) -> pd.Series:
    """
    Série texte en dtype object (hors backend PyArrow).

    Sous le Python QGIS, ``astype(str)`` peut produire ``string[pyarrow]`` et faire
    échouer ``str.contains`` (RE2 / ``match_substring_regex`` absent).
    """
    return series.fillna("").map(str).astype(object)


def series_str_contains(
    series: pd.Series,
    pat: str,
    *,
    regex: bool = False,
) -> pd.Series:
    """Recherche insensible à la casse via ``re`` (compatible Python QGIS / PyArrow)."""
    s = series_as_python_str(series)
    if regex:
        cre = re.compile(pat, re.IGNORECASE)
        return s.map(lambda val: bool(cre.search(val)))
    needle = pat.lower()
    return s.map(lambda val: needle in val.lower())


def count_operations_controle(df: pd.DataFrame, mask: pd.Series | None = None) -> int:
    """
    Nombre d'opérations de contrôle (fiches d'intervention uniques).
    
    Identifié par la colonne `fc_id`.
    """
    if "fc_id" not in df.columns or df.empty:
        return 0
    if mask is not None:
        return int(len(df.loc[mask, "fc_id"].dropna().unique()))
    return int(len(df["fc_id"].dropna().unique()))


def extract_insee_code_series(series: pd.Series) -> pd.Series:
    """Code INSEE 5 chiffres par valeur, ou ``pd.NA`` (sans ``str.extract`` / PyArrow)."""
    return series_as_python_str(series).map(lambda val: _normalize_insee_code(val) or pd.NA)


@functools.lru_cache(maxsize=1)
def _load_types_usagers_mapping() -> dict[tuple[str, str, str], str]:
    """Charge ref/programme/tables_reference/types_usagers.csv (mapping type_usager)."""
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
    """
    Libellés déjà au format catégorie cible (référentiel), pour PEJ/PA (champ USAGER).
    """
    aliases: dict[str, str] = {}
    for (_, _, _), tu in _load_types_usagers_mapping().items():
        aliases[_norm_key(tu)] = tu
    for (_, _, vs), tu in _load_types_usagers_mapping().items():
        aliases.setdefault(_norm_key(vs), tu)
    return aliases


def format_type_usager_display(label: str) -> str:
    """Libellé affiché dans les PDF (ex. « Autre » → « Autre usager »)."""
    s = str(label or "").strip()
    if s == "Autre":
        return "Autre usager"
    return s


def _parse_type_usager_tokens(valeur_source: str) -> list[tuple[str, int]]:
    """
    Parse une valeur OSCEAN de type_usager.

    Format observé :
    - \"Collectivité\" (sans effectif explicite)
    - \"Particulier (...) 6\"
    - \"Agriculteur ... 1, Collectivité 1, Particulier ... 1\"

    Renvoie une liste de (valeur_source_sans_effectif, effectif_int).
    """
    if pd.isna(valeur_source):
        return []
    s = str(valeur_source).strip()
    if not s or s == "(vide)":
        return []
    parts = [p.strip() for p in s.split(",") if p.strip()]
    out: list[tuple[str, int]] = []
    for p in parts:
        m = re.match(r"^(.*?)(?:\s+(\d+))?$", p)
        if not m:
            continue
        label = (m.group(1) or "").strip()
        n = int(m.group(2)) if m.group(2) and m.group(2).isdigit() else 1
        if label:
            out.append((label, n))
    return out


def _is_missing_effectif_value(value: Any) -> bool:
    """Vrai si la valeur est absente pour une consolidation d'effectifs."""
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
    """Liste stable de valeurs distinctes non vides observées dans un groupe."""
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
    """Score de récence d'une date pour arbitrer un conflit intra-fc_id."""
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
    """Score de sélection d'une ligne représentative du groupe."""
    has_date, date_value = _date_score_for_effectif_row(row.get("date_ctrl"))
    row_order = int(row.get(order_col, 0) or 0)
    return (has_date, date_value, -row_order)


def _score_effectif_group_value(
    row: pd.Series,
    col: str,
    source_table: str,
    order_col: str,
) -> tuple[int, int, int, int]:
    """Score de sélection d'une valeur métier au sein d'un groupe ``fc_id``."""
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
    """Choisit la meilleure valeur non vide pour une colonne d'un groupe ``fc_id``."""
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
    """
    Consolide les lignes OSCEAN au niveau ``fc_id`` pour les seules métriques d'effectifs.

    Quand plusieurs localisations portent la même fiche, les champs d'effectifs
    (``type_usager`` et dimensions associées) ne doivent être lus qu'une seule
    fois. En cas de valeurs contradictoires dans un groupe ``fc_id``, la
    première valeur non vide est conservée et un avertissement est journalisé.
    """
    if df.empty or _norm_key(source_table) != "point_ctrl" or "fc_id" not in df.columns:
        return df

    work = df.copy()
    order_col = "__effectif_row_order__"
    work[order_col] = range(len(work))
    fc_values = work["fc_id"].astype("string").str.strip()
    has_fc_id = fc_values.notna() & (fc_values != "")
    if not has_fc_id.any():
        return work.drop(columns=[order_col])

    grouped = work.loc[has_fc_id].copy()
    standalone = work.loc[~has_fc_id].copy()
    merged_rows: list[pd.Series] = []
    target_columns = [col for col in dict.fromkeys(colonnes_metier) if col in grouped.columns]

    for fc_id, group in grouped.groupby("fc_id", sort=False, dropna=False):
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
    """Mappe une valeur source vers un type d’usager (6 catégories cibles). Fallback : 'Autre'."""
    mapping = _load_types_usagers_mapping()
    key = (_norm_key(source_table), _norm_key(source_champ), _norm_key(valeur_source))
    if key in mapping:
        return mapping[key]
    hit = _canonical_type_usager_aliases().get(_norm_key(valeur_source))
    if hit:
        return hit
    return "Autre"


def resolve_type_usager_champ(df: pd.DataFrame) -> str | None:
    """Colonne type d'usager dans un jeu PEJ/PA/contrôles (casse et alias OSCEAN)."""
    for name in ("type_usager", "USAGER", "TYPE_USAGER", "TYPE USAGER"):
        if name in df.columns:
            return name
    return None


def serie_type_usager(df: pd.DataFrame, source_table: str, source_champ: str) -> pd.Series:
    """
    Déduit un type d’usager \"dominant\" par ligne à partir d’un champ source (ex. point_ctrl.type_usager).

    Règle :
    - si la ligne contient une seule catégorie → cette catégorie mappée ;
    - si plusieurs catégories → celle avec l'effectif max ; en cas d'égalité → 'Autre' ;
    - si vide → 'Autre'.
    """
    if source_champ not in df.columns:
        return pd.Series(["Autre"] * len(df), index=df.index, dtype="object")

    def _dominant(val: str) -> str:
        toks = _parse_type_usager_tokens(val)
        if not toks:
            return "Autre"
        # mapper chaque libellé vers une des 6 catégories
        mapped = [(map_type_usager(source_table, source_champ, lab), n) for lab, n in toks]
        # regrouper par catégorie (si doublons)
        agg: dict[str, int] = {}
        for cat, n in mapped:
            agg[cat] = agg.get(cat, 0) + int(n or 0)
        if len(agg) == 1:
            return next(iter(agg.keys()))
        # dominant
        max_n = max(agg.values())
        top = [k for k, v in agg.items() if v == max_n]
        return top[0] if len(top) == 1 else "Autre"

    return df[source_champ].apply(_dominant)


def agg_nb_localisations_par_type_usager(
    df: pd.DataFrame,
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """
    Nombre de contrôles par catégorie type d'usager.

    La catégorie retenue est la catégorie dominante (``serie_type_usager``), et
    non la somme des effectifs multi-usagers du champ source. Si ``fc_id`` est
    disponible sur ``point_ctrl``, chaque fiche de contrôle contribue une seule
    fois.
    """
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
    """
    Agrège les effectifs d'usagers par catégorie du référentiel.

    Pour chaque ligne de *df*, le champ *source_champ* est parsé
    (ex. « Particulier 6, Collectivité 1 »).  Chaque libellé est mappé
    vers une catégorie du référentiel et l'effectif associé est sommé. Si
    ``fc_id`` est disponible sur ``point_ctrl``, la somme est consolidée une
    seule fois par fiche de contrôle.

    Retourne un DataFrame avec colonnes ``type_usager``, ``nb`` et ``nb_operations``.
    Le total de ``nb`` peut dépasser ``len(df)`` (un point peut contribuer
    à plusieurs catégories).
    """
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
    """
    Tableau croisé (type_usager, domaine) basé sur les effectifs.

    Pour chaque ligne de *df*, décompose *source_champ* en (catégorie, effectif)
    et ajoute l'effectif dans la cellule (catégorie, domaine du point). Si
    ``fc_id`` est disponible sur ``point_ctrl``, chaque fiche ne contribue
    qu'une seule fois.

    Retourne un DataFrame en format « long » (type_usager, domaine, nb)
    ou en format « large » (type_usager en index, domaines en colonnes).
    """
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
    """
    Effectifs par type d'usager × thème (format long : type_usager, theme, nb).

    Chaque libellé d'usager sur une fiche est compté avec son effectif chiffré
    (contrôles multi-usagers : plusieurs effectifs pour une même localisation).
    """
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
    """
    Nombre de contrôles par type d'usager et par domaine.

    Pour chaque point de contrôle, on identifie les catégories de type_usager
    présentes (via le référentiel) et on incrémente une fois par catégorie
    (peu importe l'effectif associé). Si ``fc_id`` est disponible sur
    ``point_ctrl``, chaque fiche contribue une seule fois.
    """
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
    """
    Nombre de contrôles par type d'usager et par thème.

    Même logique que agg_controles_par_type_usager_domaine mais avec la colonne thème.
    """
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
    """Résultats par type d'usager × dimension (domaine ou thème), via classify_resultat_controle."""
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
    """Résultats des contrôles par type d'usager × domaine (Conforme / Manquement / Infraction / En attente)."""
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
    """Résultats des contrôles par type d'usager × thème (même logique que par domaine)."""
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
        
        # Un compte par catégorie
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
    """Nombre de contrôles multi-usagers, consolidés par ``fc_id`` si disponible."""
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
    """
    Résultats des contrôles par type d'usager, pondérés par effectif.

    Même ventilation que ``agg_resultat_counts_par_type_usager``, mais chaque
    catégorie d'usager reçoit l'effectif chiffré de la fiche (et non +1 par
    localisation).
    """
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


def is_filled_procedure_code(value: Any) -> bool:
    """Vrai si la valeur est un code de procédure renseigné (hors NaN / vide / « nan »)."""
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
    """True si le libellé de résultat implique une PA (contient « manquement »)."""
    s = str(value or "").strip().lower()
    if not s or s in ("nan", "none", "<na>"):
        return False
    return "manquement" in s


def mask_resultat_induit_pa(resultat: pd.Series) -> pd.Series:
    """Masque booléen : une PA est induite pour chaque résultat contenant « manquement »."""
    return resultat.map(resultat_induit_pa)


def filter_points_induisant_pa(point: pd.DataFrame) -> pd.DataFrame:
    """Contrôles dont le résultat induit une procédure administrative."""
    if point is None or point.empty or "resultat" not in point.columns:
        return point.iloc[0:0].copy() if point is not None and not point.empty else pd.DataFrame()
    return point.loc[mask_resultat_induit_pa(point["resultat"])].copy()


def count_pa_induites_par_controles(
    point: pd.DataFrame,
    *,
    mask: pd.Series | None = None,
) -> int:
    """Nombre de PA = contrôles dont le résultat contient « manquement »."""
    if point is None or point.empty or "resultat" not in point.columns:
        return 0
    sub = point.loc[mask] if mask is not None else point
    if sub.empty:
        return 0
    return int(mask_resultat_induit_pa(sub["resultat"]).sum())


def points_as_pa_lignes(point: pd.DataFrame) -> pd.DataFrame:
    """
    Convertit les contrôles à manquement en lignes « procédure PA »
    (domaine / thème / type d'usager) pour les agrégations chapitre Procédures.
    """
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
    """
    Procédures (PEJ / PA / PVe) par type d'usager × domaine.

    - PEJ : une procédure est comptée si col_code_pej est non vide pour le point.
    - PA : contrôle dont le résultat contient « manquement » (ou col_code_pa si pas de résultat).
    - PVe : sans lien explicite PVe dans point_ctrl, nb_pve reste à 0.
    """
    if source_champ not in df.columns:
        return pd.DataFrame(
            columns=["type_usager", "domaine", "nb_pej", "nb_pa", "nb_pve"]
        )

    counts: dict[tuple[str, str], dict[str, int]] = {}
    use_resultat_pa = "resultat" in df.columns
    for _, row in df.iterrows():
        dom = str(row.get(col_domaine, "Hors domaine") or "Hors domaine")
        has_pej = is_filled_procedure_code(row.get(col_code_pej))
        if use_resultat_pa:
            has_pa = resultat_induit_pa(row.get("resultat"))
        else:
            has_pa = is_filled_procedure_code(row.get(col_code_pa))
        has_pve = False  # nécessite les données PVe jointes ; 0 par défaut

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
    """
    Procédures (PEJ / PA / PVe) par type d'usager × thème.
    """
    if source_champ not in df.columns:
        return pd.DataFrame(
            columns=["type_usager", "theme", "nb_pej", "nb_pa", "nb_pve"]
        )

    counts: dict[tuple[str, str], dict[str, int]] = {}
    use_resultat_pa = "resultat" in df.columns
    for _, row in df.iterrows():
        theme = str(row.get(col_theme, "Hors thème") or "Hors thème")
        has_pej = is_filled_procedure_code(row.get(col_code_pej))
        if use_resultat_pa:
            has_pa = resultat_induit_pa(row.get("resultat"))
        else:
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
    """
    Compte les procédures liées aux contrôles sur la période.

    - PEJ : champ ``code_pej`` renseigné sur le point.
    - PA : contrôle dont le résultat contient « manquement » (insensible à la casse).
    """
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
    """
    Toutes les procédures (dossiers PEJ / PA), y compris saisines hors contrôle PA.

    À utiliser pour le chapitre « Procédures » (tableaux par domaine).
    """
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
    """Toutes les procédures (dossiers PEJ / PA) par thème."""
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


def filtre_periode(
    df: pd.DataFrame, col_date: str, date_deb: pd.Timestamp, date_fin: pd.Timestamp
) -> pd.DataFrame:
    """Filtre le DataFrame sur la plage de dates."""
    return df[(df[col_date] >= date_deb) & (df[col_date] <= date_fin)].copy()


def resume_resultat(s: pd.Series) -> str:
    """Consolide le résultat d'un dossier à partir des résultats de ses points."""
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
    """Vérifie si le thème ou l'action concerne la chasse."""
    t = (theme or "").lower()
    a = (type_action or "").lower()
    return ("chasse" in t) or ("chasse" in a) or ("police de la chasse" in t)


def est_chasse_point(row: pd.Series) -> bool:
    """Détermine si un point de contrôle concerne la chasse."""
    return est_chasse_thematique(row.get("theme"), row.get("type_actio"))


def contient_natinf(s: str, natinf_list: List[str]) -> bool:
    """Vérifie si la chaîne contient l'un des codes NATINF (format X_Y ou isolé)."""
    s = str(s) if pd.notna(s) else ""
    for code in natinf_list:
        pattern = rf"(^|_){code}(_|$)"
        if re.search(pattern, s):
            return True
    return False


def count_controles_non_conformes_oscean(resultat: pd.Series) -> int:
    """
    Compte les contrôles non conformes OSCEAN : résultat « Infraction » ou « Manquement ».

    Aligné sur la logique métier : un contrôle non conforme peut révéler l'un ou l'autre ;
    le total des non-conformes est la somme des deux catégories (une ligne = un contrôle).
    """
    r = classify_resultat_controle_series(resultat)
    return int(r.isin(("Infraction", "Manquement")).sum())


def classify_resultat_controle(value: Any) -> str:
    """
    Regroupe le libellé OSCEAN en catégories du tableau « Résultats des contrôles » (2.2).

    Seuls Conforme, Infraction et Manquement sont conservés tels quels ; tout le reste
    (vide, inconnu, autre libellé) est compté comme « En attente ».
    """
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
    """Applique :func:`classify_resultat_controle` ligne à ligne."""
    return resultat.map(classify_resultat_controle)


def build_tab_resultats(point: pd.DataFrame) -> pd.DataFrame:
    """
    Tableau synthétique exporté (resultat, nb, taux) avec catégories normalisées.

    Aligné sur :func:`classify_resultat_controle` (inclut « En attente »).
    """
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
    """Code INSEE normalisé (5 chiffres) par ligne, colonnes usuelles combinées."""
    if df is None or df.empty:
        return pd.Series(pd.NA, index=df.index, dtype="string")
    out = pd.Series(pd.NA, index=df.index, dtype="string")
    for col in ("insee_comm", "insee_commun", "INSEE_COM", "INF-INSEE"):
        if col not in df.columns:
            continue
        out = out.fillna(extract_insee_code_series(df[col]))
    return out


def _normalize_insee_code(insee: Any) -> str | None:
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
    """Libellé lecteur (une zone) : priorité cœur / aire SIG, puis TUB, sinon hors PNF/TUB."""
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
    """Série de libellés lecteur (4 zones exclusives) pour chaque ligne."""
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
    """Format « Label : n, … » pour les zones avec n > 0."""
    sub = zones.loc[mask]
    parts: list[str] = []
    for label in ZONE_LECTEUR_ORDER:
        n = int((sub == label).sum())
        if n > 0:
            parts.append(f"{label} : {n}")
    return ", ".join(parts)


def zone_lecteur_counts_for_pdf_cell(text: str) -> str:
    """Présentation PDF : une zone par ligne (``<br/>``), sans modifier les données agrégées."""
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
    """Construit le tableau synthétique « Résultats des contrôles » (section 2.2)."""
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

        def _coeur_hors_txt(mask: pd.Series) -> str:
            c = int((mask & is_coeur).sum())
            h = int((mask & is_hors).sum())
            return f"Cœur: {c} / Aire d'adhésion: {h}"

        details_rows = [
            {
                "resultat": "Conforme",
                "nb": nb_conf,
                "coeur_hors_coeur": _coeur_hors_txt(r_norm.eq("Conforme")),
            },
            {
                "resultat": "Non-conforme",
                "nb": nb_nc,
                "coeur_hors_coeur": _coeur_hors_txt(r_norm.isin(["Infraction", "Manquement"])),
            },
            {
                "resultat": "    Dont manquement",
                "nb": nb_manq,
                "coeur_hors_coeur": _coeur_hors_txt(r_norm.eq("Manquement")),
            },
            {
                "resultat": "    Dont infraction",
                "nb": nb_inf,
                "coeur_hors_coeur": _coeur_hors_txt(r_norm.eq("Infraction")),
            },
        ]
        if nb_en_attente > 0:
            details_rows.append(
                {"resultat": "En attente", "nb": nb_en_attente, "coeur_hors_coeur": "n.d."}
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
    """
    Tableau « PEJ par zone » (profil lecteur 4 zones) dérivé du détail procédures.
    Les lignes sans localisation exploitable (``n.d.``) sont regroupées sous
    « Localisation en attente ».
    """
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
    """Libellé PDF/affichage pour la colonne zone (clé interne « Département » inchangée)."""
    if str(zone).strip() == ZONE_KEY_DEPARTEMENT:
        return ZONE_LABEL_DEPARTEMENT_HORS
    return str(zone)


def _mask_hors_tub_pnf(insee: pd.Series, tub_codes: set, pnf_codes: set) -> pd.Series:
    """Communes ni en zone TUB ni en zone PNF (décompte ensembliste, sans double soustraction)."""
    return ~insee.isin(tub_codes) & ~insee.isin(pnf_codes)


def _zone_summary(
    df: pd.DataFrame,
    col_insee: str,
    tub_codes: set,
    pnf_codes: set,
) -> pd.DataFrame:
    """Calcule nb_total, nb_conforme, nb_non_conforme pour dept hors TUB/PNF, TUB et PNF."""
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
    """Compte simple par zone (pour PVe / PEJ sans colonne 'resultat')."""
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
    """Charge un CSV optionnel ; retourne None si absent ou illisible."""
    p = out_dir / name
    if not p.exists():
        return None
    try:
        return pd.read_csv(p, sep=";", encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(p, sep=";", encoding="latin-1")


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
    """Renvoie le nom du département pour un code donné, ou 'Département <code>' si inconnu."""
    return DEPT_NAMES.get(str(code).strip(), f"Département {code}")


def _detect_insee_column(communes: gpd.GeoDataFrame) -> str:
    """Détecte la colonne contenant le code INSEE dans une couche communes."""
    candidats = ["INSEE", "INSEE_COM", "CODE_INSEE", "INSEE_COMM", "INSEECO"]
    for col in candidats:
        if col in communes.columns:
            return col
    raise ValueError(
        "Impossible de trouver une colonne INSEE dans la couche communes."
    )
