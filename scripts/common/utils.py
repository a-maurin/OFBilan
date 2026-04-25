"""Utilitaires partagés pour les bilans (filtrage, résumés, détection colonnes)."""
import functools
import re
from pathlib import Path
from typing import List

import geopandas as gpd
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TYPES_USAGERS_PATH = _PROJECT_ROOT / "ref" / "types_usagers.csv"


def _norm_key(s: str) -> str:
    return (s or "").strip().lower()


@functools.lru_cache(maxsize=1)
def _load_types_usagers_mapping() -> dict[tuple[str, str, str], str]:
    """Charge ref/types_usagers.csv et renvoie un mapping (source_table, source_champ, valeur_source_norm) -> type_usager."""
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


def map_type_usager(source_table: str, source_champ: str, valeur_source: str) -> str:
    """Mappe une valeur source vers un type d’usager (6 catégories cibles). Fallback : 'Autre'."""
    mapping = _load_types_usagers_mapping()
    key = (_norm_key(source_table), _norm_key(source_champ), _norm_key(valeur_source))
    return mapping.get(key, "Autre")


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


def agg_effectifs_usagers(
    df: pd.DataFrame,
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """
    Agrège les effectifs d'usagers par catégorie du référentiel.

    Pour chaque ligne de *df*, le champ *source_champ* est parsé
    (ex. « Particulier 6, Collectivité 1 »).  Chaque libellé est mappé
    vers une catégorie du référentiel et l'effectif associé est sommé.

    Retourne un DataFrame avec colonnes ``type_usager`` et ``nb``.
    Le total de ``nb`` peut dépasser ``len(df)`` (un point peut contribuer
    à plusieurs catégories).
    """
    if source_champ not in df.columns:
        return pd.DataFrame(columns=["type_usager", "nb"])

    agg: dict[str, int] = {}
    for val in df[source_champ]:
        toks = _parse_type_usager_tokens(val)
        if not toks:
            agg["Autre"] = agg.get("Autre", 0) + 1
            continue
        for lab, n in toks:
            cat = map_type_usager(source_table, source_champ, lab)
            agg[cat] = agg.get(cat, 0) + n

    result = (
        pd.DataFrame(list(agg.items()), columns=["type_usager", "nb"])
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
    et ajoute l'effectif dans la cellule (catégorie, domaine du point).

    Retourne un DataFrame en format « long » (type_usager, domaine, nb)
    ou en format « large » (type_usager en index, domaines en colonnes).
    """
    if source_champ not in df.columns:
        return pd.DataFrame(columns=["type_usager"])

    rows: list[tuple[str, str, int]] = []
    for _, row in df.iterrows():
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
    (peu importe l'effectif associé).
    """
    if source_champ not in df.columns:
        return pd.DataFrame(columns=["type_usager", "domaine", "nb_controles"])

    counts: dict[tuple[str, str], int] = {}
    for _, row in df.iterrows():
        dom = str(row.get(col_domaine, "Hors domaine") or "Hors domaine")
        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cats = ["Autre"]
        else:
            cats = {
                map_type_usager(source_table, source_champ, lab)
                for lab, _ in toks
            }
        for cat in cats:
            key = (cat, dom)
            counts[key] = counts.get(key, 0) + 1

    rows: list[dict[str, object]] = []
    for (cat, dom), n in counts.items():
        rows.append({"type_usager": cat, "domaine": dom, "nb_controles": int(n)})
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
        return pd.DataFrame(columns=["type_usager", "theme", "nb_controles"])

    counts: dict[tuple[str, str], int] = {}
    for _, row in df.iterrows():
        theme = str(row.get(col_theme, "Hors thème") or "Hors thème")
        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cats = ["Autre"]
        else:
            cats = {
                map_type_usager(source_table, source_champ, lab)
                for lab, _ in toks
            }
        for cat in cats:
            key = (cat, theme)
            counts[key] = counts.get(key, 0) + 1

    rows: list[dict[str, object]] = []
    for (cat, theme), n in counts.items():
        rows.append({"type_usager": cat, "theme": theme, "nb_controles": int(n)})
    return pd.DataFrame(rows)


def agg_resultats_par_type_usager_domaine(
    df: pd.DataFrame,
    col_domaine: str = "domaine",
    col_resultat: str = "resultat",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """
    Résultats des contrôles (Infraction / Manquement / PVe) par type d'usager × domaine.

    - Infraction / Manquement sont déterminés à partir de la chaîne *resultat*
      (présence des mots-clés, insensible à la casse).
    - PVe nécessite idéalement un lien explicite avec les données PVe ; en l'absence
      de colonne dédiée dans point_ctrl, nb_pve restera à 0 par (type_usager, domaine).
    """
    if source_champ not in df.columns or col_resultat not in df.columns:
        return pd.DataFrame(
            columns=[
                "type_usager",
                "domaine",
                "nb_controles",
                "nb_infraction",
                "nb_manquement",
                "nb_pve",
            ]
        )

    counts: dict[tuple[str, str], dict[str, int]] = {}
    for _, row in df.iterrows():
        dom = str(row.get(col_domaine, "Hors domaine") or "Hors domaine")
        res = str(row.get(col_resultat, "") or "")
        s = res.lower()
        is_inf = "infraction" in s
        is_manq = "manquement" in s
        is_pve = "pve" in s  # très conservateur ; la plupart du temps ce sera 0

        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cats = ["Autre"]
        else:
            cats = {
                map_type_usager(source_table, source_champ, lab)
                for lab, _ in toks
            }

        for cat in cats:
            key = (cat, dom)
            d = counts.setdefault(
                key,
                {
                    "nb_controles": 0,
                    "nb_infraction": 0,
                    "nb_manquement": 0,
                    "nb_pve": 0,
                },
            )
            d["nb_controles"] += 1
            if is_inf:
                d["nb_infraction"] += 1
            if is_manq:
                d["nb_manquement"] += 1
            if is_pve:
                d["nb_pve"] += 1

    rows: list[dict[str, object]] = []
    for (cat, dom), d in counts.items():
        rows.append(
            {
                "type_usager": cat,
                "domaine": dom,
                "nb_controles": int(d["nb_controles"]),
                "nb_infraction": int(d["nb_infraction"]),
                "nb_manquement": int(d["nb_manquement"]),
                "nb_pve": int(d["nb_pve"]),
            }
        )
    return pd.DataFrame(rows)


def agg_resultats_par_type_usager_theme(
    df: pd.DataFrame,
    col_theme: str = "theme",
    col_resultat: str = "resultat",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """
    Résultats des contrôles (Infraction / Manquement / PVe) par type d'usager × thème.
    """
    if source_champ not in df.columns or col_resultat not in df.columns:
        return pd.DataFrame(
            columns=[
                "type_usager",
                "theme",
                "nb_controles",
                "nb_infraction",
                "nb_manquement",
                "nb_pve",
            ]
        )

    counts: dict[tuple[str, str], dict[str, int]] = {}
    for _, row in df.iterrows():
        theme = str(row.get(col_theme, "Hors thème") or "Hors thème")
        res = str(row.get(col_resultat, "") or "")
        s = res.lower()
        is_inf = "infraction" in s
        is_manq = "manquement" in s
        is_pve = "pve" in s

        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cats = ["Autre"]
        else:
            cats = {
                map_type_usager(source_table, source_champ, lab)
                for lab, _ in toks
            }

        for cat in cats:
            key = (cat, theme)
            d = counts.setdefault(
                key,
                {
                    "nb_controles": 0,
                    "nb_infraction": 0,
                    "nb_manquement": 0,
                    "nb_pve": 0,
                },
            )
            d["nb_controles"] += 1
            if is_inf:
                d["nb_infraction"] += 1
            if is_manq:
                d["nb_manquement"] += 1
            if is_pve:
                d["nb_pve"] += 1

    rows: list[dict[str, object]] = []
    for (cat, theme), d in counts.items():
        rows.append(
            {
                "type_usager": cat,
                "theme": theme,
                "nb_controles": int(d["nb_controles"]),
                "nb_infraction": int(d["nb_infraction"]),
                "nb_manquement": int(d["nb_manquement"]),
                "nb_pve": int(d["nb_pve"]),
            }
        )
    return pd.DataFrame(rows)


def agg_resultat_counts_par_type_usager(
    df: pd.DataFrame,
    col_resultat: str = "resultat",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """
    Compte les contrôles par type d'usager et par résultat explicite
    (Conforme / Infraction / Manquement ; le reste → colonne ``Autre_resultat``,
    distinct du libellé de type d'usager « Autre » lorsque le champ est vide).

    Une ligne de point peut contribuer à plusieurs types d'usager si le champ
    source est multi-catégories (même logique que les autres ``agg_*_par_type_usager``).
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

    for _, row in df.iterrows():
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
            cats = ["Autre"]
        else:
            cats = list(
                {map_type_usager(source_table, source_champ, lab) for lab, _ in toks}
            )

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


def agg_procedures_par_type_usager_domaine(
    df: pd.DataFrame,
    col_domaine: str = "domaine",
    col_code_pej: str = "code_pej",
    col_code_pa: str = "code_pa",
    source_table: str = "point_ctrl",
    source_champ: str = "type_usager",
) -> pd.DataFrame:
    """
    Procédures (PJ / PA / PVe) par type d'usager × domaine.

    - PJ : une procédure est comptée si col_code_pej est non vide pour le point.
    - PA : idem pour col_code_pa.
    - PVe : sans lien explicite PVe dans point_ctrl, nb_pve reste à 0.
    """
    if source_champ not in df.columns:
        return pd.DataFrame(
            columns=["type_usager", "domaine", "nb_pj", "nb_pa", "nb_pve"]
        )

    counts: dict[tuple[str, str], dict[str, int]] = {}
    for _, row in df.iterrows():
        dom = str(row.get(col_domaine, "Hors domaine") or "Hors domaine")
        has_pej = bool(str(row.get(col_code_pej, "") or "").strip())
        has_pa = bool(str(row.get(col_code_pa, "") or "").strip())
        has_pve = False  # nécessite les données PVe jointes ; 0 par défaut

        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cats = ["Autre"]
        else:
            cats = {
                map_type_usager(source_table, source_champ, lab)
                for lab, _ in toks
            }

        for cat in cats:
            key = (cat, dom)
            d = counts.setdefault(
                key,
                {
                    "nb_pj": 0,
                    "nb_pa": 0,
                    "nb_pve": 0,
                },
            )
            if has_pej:
                d["nb_pj"] += 1
            if has_pa:
                d["nb_pa"] += 1
            if has_pve:
                d["nb_pve"] += 1

    rows: list[dict[str, object]] = []
    for (cat, dom), d in counts.items():
        rows.append(
            {
                "type_usager": cat,
                "domaine": dom,
                "nb_pj": int(d["nb_pj"]),
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
    Procédures (PJ / PA / PVe) par type d'usager × thème.
    """
    if source_champ not in df.columns:
        return pd.DataFrame(
            columns=["type_usager", "theme", "nb_pj", "nb_pa", "nb_pve"]
        )

    counts: dict[tuple[str, str], dict[str, int]] = {}
    for _, row in df.iterrows():
        theme = str(row.get(col_theme, "Hors thème") or "Hors thème")
        has_pej = bool(str(row.get(col_code_pej, "") or "").strip())
        has_pa = bool(str(row.get(col_code_pa, "") or "").strip())
        has_pve = False

        toks = _parse_type_usager_tokens(row.get(source_champ))
        if not toks:
            cats = ["Autre"]
        else:
            cats = {
                map_type_usager(source_table, source_champ, lab)
                for lab, _ in toks
            }

        for cat in cats:
            key = (cat, theme)
            d = counts.setdefault(
                key,
                {
                    "nb_pj": 0,
                    "nb_pa": 0,
                    "nb_pve": 0,
                },
            )
            if has_pej:
                d["nb_pj"] += 1
            if has_pa:
                d["nb_pa"] += 1
            if has_pve:
                d["nb_pve"] += 1

    rows: list[dict[str, object]] = []
    for (cat, theme), d in counts.items():
        rows.append(
            {
                "type_usager": cat,
                "theme": theme,
                "nb_pj": int(d["nb_pj"]),
                "nb_pa": int(d["nb_pa"]),
                "nb_pve": int(d["nb_pve"]),
            }
        )
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
    r = resultat.astype(str).str.strip().str.lower()
    return int(r.isin(("infraction", "manquement")).sum())


def _zone_summary(
    df: pd.DataFrame,
    col_insee: str,
    tub_codes: set,
    pnf_codes: set,
) -> pd.DataFrame:
    """Calcule nb_total, nb_conforme, nb_non_conforme pour dept / TUB / PNF."""
    insee = df[col_insee].astype(str).str.zfill(5)
    rows = []

    total = len(df)
    if "resultat" in df.columns:
        nb_nc_dept = count_controles_non_conformes_oscean(df["resultat"])
    else:
        nb_nc_dept = 0
    nb_conf_dept = total - nb_nc_dept
    rows.append(
        {
            "zone": "Département",
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
        {"zone": "Département", "nb": len(df)},
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
