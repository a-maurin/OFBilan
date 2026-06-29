"""Agrégations dédiées au profil synthese_activite_PA_PJ."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ofbilan.common.utilitaires_metier import (
    agg_effectifs_usagers,
    agg_effectifs_usagers_par_theme,
    agg_procedures_dossiers_par_theme,
    agg_resultat_effectifs_par_type_usager,
    count_pa_induites_par_controles,
    points_as_pa_lignes,
    get_departements_pour_perimetre,
)
from ofbilan.engine.agregations_profil import (
    analyse_controles_global,
    analyse_pej_pa_global,
    analyse_pve_global,
)

_PREFIX = "synthese"


def _col_theme(df: pd.DataFrame) -> str | None:
    for name in ("THEME", "theme"):
        if name in df.columns:
            return name
    return None


def _dc_ids_controles(point: pd.DataFrame) -> set[str]:
    if point is None or point.empty or "dc_id" not in point.columns:
        return set()
    return set(point["dc_id"].dropna().astype(str).str.strip())


def _pej_perimetre(pej: pd.DataFrame, echelle: str, code: str) -> pd.DataFrame:
    """
    PEJ du périmètre (ex: SD21, ou liste de SD), un enregistrement par DC_ID.

    Si *pej* provient de ``load_pej``, filtre et dédoublonnage
    sont déjà appliqués au chargement ; ce passage reste idempotent.
    """
    if pej is None or pej.empty:
        return pd.DataFrame()
    out = pej.copy()
    if "ENTITE_ORIGINE_PROCEDURE" in out.columns:
        if str(echelle).strip().lower() != "bmi":
            dept_codes = get_departements_pour_perimetre(echelle, code)
            if dept_codes and "FR" not in dept_codes:
                sd_list = [f"SD{d}" for d in dept_codes]
                out = out[out["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.strip().isin(sd_list)].copy()
    if out.empty or "DC_ID" not in out.columns:
        return out
    if "DATE_REF" in out.columns:
        out = out.sort_values("DATE_REF", ascending=False).drop_duplicates(
            subset="DC_ID", keep="first"
        )
    else:
        out = out.drop_duplicates(subset="DC_ID", keep="first")
    return out


def pej_hors_fiche_controle(pej: pd.DataFrame, point: pd.DataFrame, echelle: str, code: str) -> pd.DataFrame:
    """PEJ dont le DC_ID n'apparaît pas parmi les dc_id des points de contrôle."""
    pej_d = _pej_perimetre(pej, echelle, code)
    if pej_d.empty:
        return pej_d
    dc_ctrl = _dc_ids_controles(point)
    ids = pej_d["DC_ID"].astype(str).str.strip()
    if not dc_ctrl:
        return pej_d.copy()
    return pej_d.loc[~ids.isin(dc_ctrl)].copy()


def pej_sur_fiche_controle(pej: pd.DataFrame, point: pd.DataFrame, echelle: str, code: str) -> pd.DataFrame:
    """PEJ dont le DC_ID figure parmi les dc_id des points de contrôle (suite à contrôle)."""
    pej_d = _pej_perimetre(pej, echelle, code)
    if pej_d.empty:
        return pej_d
    dc_ctrl = _dc_ids_controles(point)
    ids = pej_d["DC_ID"].astype(str).str.strip()
    if not dc_ctrl:
        return pej_d.iloc[0:0].copy()
    return pej_d.loc[ids.isin(dc_ctrl)].copy()


def _counts_par_theme(df: pd.DataFrame, value_col: str = "nb") -> pd.DataFrame:
    th = _col_theme(df)
    if th is None or df.empty:
        return pd.DataFrame(columns=["theme", value_col])
    grouped = (
        df[th]
        .fillna("Hors thème")
        .astype(str)
        .value_counts()
        .rename_axis("theme")
        .to_frame(value_col)
        .reset_index()
    )
    return grouped


def _merge_theme_counts(parts: list[tuple[pd.DataFrame, str]]) -> pd.DataFrame:
    merged: pd.DataFrame | None = None
    for frame, col in parts:
        if frame is None or frame.empty:
            continue
        sub = frame[["theme", col]].copy()
        merged = sub if merged is None else merged.merge(sub, on="theme", how="outer")
    if merged is None:
        return pd.DataFrame(columns=["theme"])
    for c in merged.columns:
        if c != "theme":
            merged[c] = merged[c].fillna(0).astype(int)
    total_cols = [c for c in merged.columns if c != "theme"]
    if total_cols:
        merged["nb_total"] = merged[total_cols].sum(axis=1)
        merged = merged.sort_values("nb_total", ascending=False, kind="stable")
    return merged.reset_index(drop=True)


def activite_police_par_theme(point: pd.DataFrame, pej: pd.DataFrame, echelle: str, code: str) -> pd.DataFrame:
    """§ 2.1 : localisations de contrôle + PEJ hors fiche contrôle, par thème."""
    col = "theme" if "theme" in point.columns else ("type_actio" if "type_actio" in point.columns else None)
    if col and not point.empty:
        ctrl = (
            point[col]
            .fillna("Hors thème")
            .astype(str)
            .value_counts()
            .rename_axis("theme")
            .to_frame("nb_localisations")
            .reset_index()
        )
        if "dc_id" in point.columns:
            pts = point.dropna(subset=["dc_id"]).copy()
            ops = (
                pts.groupby(pts[col].fillna("Hors thème").astype(str))["dc_id"]
                .nunique()
                .rename_axis("theme")
                .to_frame("nb_operations_controle")
                .reset_index()
            )
            ctrl = ctrl.merge(ops, on="theme", how="outer")
            ctrl["nb_localisations"] = ctrl["nb_localisations"].fillna(0).astype(int)
            ctrl["nb_operations_controle"] = ctrl["nb_operations_controle"].fillna(0).astype(int)
        else:
            ctrl["nb_operations_controle"] = 0
    else:
        ctrl = pd.DataFrame(columns=["theme", "nb_localisations", "nb_operations_controle"])
    hors = pej_hors_fiche_controle(pej, point, echelle, code)
    pej_h = _counts_par_theme(hors, "nb_pej_hors_controle")
    out = _merge_theme_counts([(ctrl, "nb_localisations"), (ctrl, "nb_operations_controle"), (pej_h, "nb_pej_hors_controle")])
    if not out.empty:
        out["nb_total"] = out["nb_localisations"] + out["nb_pej_hors_controle"]
        out = out.sort_values("nb_total", ascending=False, kind="stable")
    return out


def _pa_par_theme_depuis_controles(point: pd.DataFrame) -> pd.DataFrame:
    """
    PA par thème : uniquement les manquements issus des fiches contrôle.

    Les lignes du classeur PA ODS ne sont pas additionnées ici (elles recoupent
    les mêmes DC_ID et gonflaient artificiellement les totaux § 2.3).
    """
    pa_lignes = points_as_pa_lignes(point)
    if pa_lignes.empty:
        return pd.DataFrame(columns=["theme", "nb_pa"])
    return _counts_par_theme(pa_lignes, "nb_pa")


def procedures_par_theme(
    pej: pd.DataFrame,
    pa: pd.DataFrame,
    point: pd.DataFrame,
    echelle: str,
    code: str,
) -> pd.DataFrame:
    """§ 2.3 : PEJ et PA par thème OSCEAN (les PVe sont traités au § 4)."""
    del pa  # PA : dérivées des fiches contrôle uniquement (voir _pa_par_theme_depuis_controles)
    pej_d = _pej_perimetre(pej, echelle, code)
    pej_t = _counts_par_theme(pej_d, "nb_pej")
    pa_t = _pa_par_theme_depuis_controles(point)
    out = _merge_theme_counts([(pej_t, "nb_pej"), (pa_t, "nb_pa")])
    for col in ("nb_pej", "nb_pa"):
        if col not in out.columns:
            out[col] = 0
        else:
            out[col] = out[col].fillna(0).astype(int)
    if not out.empty:
        out = out.sort_values(["nb_pej", "nb_pa"], ascending=False, kind="stable")
    return out.reset_index(drop=True)


def analyse_pve_synthese(pve: pd.DataFrame, out_dir: Path) -> None:
    """
    Agrégations PVe pour le § 4 (source OFB, sans type d'usager ni thème OSCEAN).
    """
    classe_cols = ["classe", "libelle_classe", "nb"]

    if pve is None or pve.empty:
        pd.DataFrame(columns=classe_cols).to_csv(out_dir / f"{_PREFIX}_pve_par_classe.csv", sep=";", index=False)
        return

    if "INF-CLASSE" in pve.columns:
        par_classe = (
            pve["INF-CLASSE"]
            .fillna("")
            .astype(str)
            .str.strip()
            .replace("", "Non renseigné")
            .value_counts()
            .rename_axis("classe")
            .to_frame("nb")
            .reset_index()
        )
        par_classe["libelle_classe"] = par_classe["classe"].map(_libelle_classe_pve)
    else:
        par_classe = pd.DataFrame(columns=classe_cols)
    par_classe.to_csv(out_dir / f"{_PREFIX}_pve_par_classe.csv", sep=";", index=False)


def _libelle_classe_pve(classe: str) -> str:
    mapping = {
        "1": "Contravention de 1re classe",
        "2": "Contravention de 2e classe",
        "3": "Contravention de 3e classe",
        "4": "Contravention de 4e classe",
        "5": "Contravention de 5e classe",
    }
    key = str(classe).strip()
    return mapping.get(key, f"Classe {key}" if key and key != "Non renseigné" else "Non renseigné")


def _pej_par_type_usager_theme(pej: pd.DataFrame, value_col: str) -> pd.DataFrame:
    cols = ["type_usager", "theme", value_col]
    if pej is None or pej.empty:
        return pd.DataFrame(columns=cols)
    from ofbilan.common.utilitaires_metier import resolve_type_usager_champ

    usager_col = resolve_type_usager_champ(pej)
    if usager_col is None:
        return pd.DataFrame(columns=cols)
    empty_pa = pej.iloc[0:0].copy()
    out = agg_procedures_dossiers_par_theme(
        pej,
        empty_pa,
        with_type_usager=True,
        source_table="pej",
        source_champ=usager_col,
    )
    if out.empty:
        return pd.DataFrame(columns=cols)
    return out.rename(columns={"nb_pej": value_col})[["type_usager", "theme", value_col]]


def _pej_hors_par_type_usager_theme(pej_hors: pd.DataFrame) -> pd.DataFrame:
    return _pej_par_type_usager_theme(pej_hors, "nb_pej_hors_controle")


def _pej_suite_par_type_usager_theme(pej_lies: pd.DataFrame) -> pd.DataFrame:
    return _pej_par_type_usager_theme(pej_lies, "nb_pej_suite_controle")


def activite_par_type_usager(
    point: pd.DataFrame,
    pej: pd.DataFrame,
    echelle: str,
    code: str,
) -> pd.DataFrame:
    """
    Effectifs d'usagers contrôlés + saisines PEJ hors fiche, par type d'usager (camembert § 3).
    """
    eff = agg_effectifs_usagers(point).rename(columns={"nb": "nb_effectifs"})
    hors = pej_hors_fiche_controle(pej, point, echelle, code)
    pej_ut = _pej_hors_par_type_usager_theme(hors)
    if pej_ut.empty:
        pej_by = pd.DataFrame(columns=["type_usager", "nb_pej_hors_controle"])
    else:
        pej_by = (
            pej_ut.groupby("type_usager", as_index=False)["nb_pej_hors_controle"]
            .sum()
            .astype({"nb_pej_hors_controle": int})
        )
    if eff.empty and pej_by.empty:
        return pd.DataFrame(
            columns=["type_usager", "nb_effectifs", "nb_pej_hors_controle", "nb_total"]
        )
    if eff.empty:
        out = pej_by.copy()
        out["nb_effectifs"] = 0
    elif pej_by.empty:
        out = eff.copy()
        out["nb_pej_hors_controle"] = 0
    else:
        out = eff.merge(pej_by, on="type_usager", how="outer")
    for col in ("nb_effectifs", "nb_pej_hors_controle"):
        out[col] = out.get(col, 0).fillna(0).astype(int)
    out["nb_total"] = out["nb_effectifs"] + out["nb_pej_hors_controle"]
    return out.sort_values("nb_total", ascending=False, kind="stable").reset_index(drop=True)


def activite_usager_par_theme(
    point: pd.DataFrame,
    pej: pd.DataFrame,
    echelle: str,
    code: str,
) -> pd.DataFrame:
    """§ 3.1 : effectifs contrôles + PEJ suite contrôle + PEJ hors fiche, par type × thème."""
    metric_cols = ("nb_effectifs", "nb_pej_suite_controle", "nb_pej_hors_controle")
    empty_cols = ["type_usager", "theme", *metric_cols, "nb_total"]

    eff = agg_effectifs_usagers_par_theme(point).rename(columns={"nb": "nb_effectifs"})
    lies = pej_sur_fiche_controle(pej, point, echelle, code)
    hors = pej_hors_fiche_controle(pej, point, echelle, code)
    pej_suite = _pej_suite_par_type_usager_theme(lies)
    pej_hors_ut = _pej_hors_par_type_usager_theme(hors)

    parts = [eff, pej_suite, pej_hors_ut]
    if all(p is None or p.empty for p in parts):
        return pd.DataFrame(columns=empty_cols)

    out: pd.DataFrame | None = None
    for part in parts:
        if part is None or part.empty:
            continue
        out = part if out is None else out.merge(part, on=["type_usager", "theme"], how="outer")
    if out is None:
        return pd.DataFrame(columns=empty_cols)
    for col in metric_cols:
        if col not in out.columns:
            out[col] = 0
        else:
            out[col] = out[col].fillna(0).astype(int)
    out["nb_total"] = out[list(metric_cols)].sum(axis=1)
    return out.sort_values(["type_usager", "nb_total"], ascending=[True, False], kind="stable").reset_index(drop=True)


def _merge_proc_usager_theme(parts: list[pd.DataFrame]) -> pd.DataFrame:
    """Fusionne des tableaux procédures (PEJ/PA) par type_usager × thème."""
    cols = ["type_usager", "theme", "nb_pej", "nb_pa"]
    totals: dict[tuple[str, str], dict[str, int]] = {}
    for df in parts:
        if df is None or df.empty or "type_usager" not in df.columns:
            continue
        for _, row in df.iterrows():
            key = (str(row["type_usager"]), str(row.get("theme", "Hors thème")))
            bucket = totals.setdefault(key, {"nb_pej": 0, "nb_pa": 0})
            for metric in ("nb_pej", "nb_pa"):
                bucket[metric] += int(row.get(metric, 0) or 0)
    if not totals:
        return pd.DataFrame(columns=cols)
    rows = [
        {
            "type_usager": cat,
            "theme": theme,
            "nb_pej": int(d["nb_pej"]),
            "nb_pa": int(d["nb_pa"]),
        }
        for (cat, theme), d in totals.items()
    ]
    out = pd.DataFrame(rows)
    return out.sort_values(["type_usager", "nb_pej", "nb_pa"], ascending=[True, False, False], kind="stable")


def procedures_usager_par_theme(
    pej: pd.DataFrame,
    pa: pd.DataFrame,
    point: pd.DataFrame,
    echelle: str,
    code: str,
) -> pd.DataFrame:
    """§ 3.3 : procédures PEJ et PA (depuis contrôles) par type d'usager × thème."""
    del pa
    pej_d = _pej_perimetre(pej, echelle, code)
    pa_lignes = points_as_pa_lignes(point)

    empty_pej = pej_d.iloc[0:0].copy() if not pej_d.empty else pd.DataFrame()
    empty_pa = pa_lignes.iloc[0:0].copy() if not pa_lignes.empty else pd.DataFrame()
    parts: list[pd.DataFrame] = []

    from ofbilan.common.utilitaires_metier import resolve_type_usager_champ

    pej_usager_col = resolve_type_usager_champ(pej_d) or "type_usager"
    if not pej_d.empty:
        parts.append(
            agg_procedures_dossiers_par_theme(
                pej_d,
                empty_pa,
                with_type_usager=True,
                source_table="pej",
                source_champ=pej_usager_col,
            )
        )
    if not pa_lignes.empty:
        parts.append(
            agg_procedures_dossiers_par_theme(
                empty_pej,
                pa_lignes,
                with_type_usager=True,
                source_table="point_ctrl",
                source_champ="type_usager",
            )
        )

    return _merge_proc_usager_theme(parts)


def _export_synthese_csv(out_dir: Path, name: str, df: pd.DataFrame) -> None:
    path = out_dir / f"{_PREFIX}_{name}.csv"
    (df if df is not None else pd.DataFrame()).to_csv(path, sep=";", index=False)


def run_synthese_aggregations(
    *,
    profile: dict,
    root: Path,
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    out_dir: Path,
    echelle: str,
    code: str,
    ventilation_mode: str,
    date_deb: pd.Timestamp,
    date_fin: pd.Timestamp,
) -> None:
    """Adapter d'agrégations pour le profil synthese_activite_PA_PJ."""
    del profile, ventilation_mode, date_deb, date_fin
    analyse_controles_global(point, out_dir)
    analyse_pej_pa_global(root, point, pa, pej, out_dir, echelle=echelle, code=code)
    analyse_pve_global(pve, out_dir)
    analyse_pve_synthese(pve, out_dir)

    res_usager = agg_resultat_effectifs_par_type_usager(point)

    act_theme = activite_police_par_theme(point, pej, echelle, code)
    proc_theme = procedures_par_theme(pej, pa, point, echelle, code)
    act_ut = activite_usager_par_theme(point, pej, echelle, code)
    act_u = activite_par_type_usager(point, pej, echelle, code)
    proc_ut = procedures_usager_par_theme(pej, pa, point, echelle, code)

    _export_synthese_csv(out_dir, "activite_par_theme", act_theme)
    _export_synthese_csv(out_dir, "activite_par_type_usager", act_u)
    _export_synthese_csv(out_dir, "procedures_par_theme", proc_theme)
    _export_synthese_csv(out_dir, "activite_usager_theme", act_ut)
    _export_synthese_csv(out_dir, "procedures_usager_theme", proc_ut)
    _export_synthese_csv(out_dir, "resultats_usager_effectifs", res_usager)

    resume = pd.DataFrame(
        [
            {
                "nb_localisations": int(len(point)),
                "nb_operations_controle": int(len(point["dc_id"].dropna().unique())) if "dc_id" in point.columns else 0,
                "nb_pej": int(len(_pej_perimetre(pej, echelle, code))),
                "nb_pej_hors_controle": int(len(pej_hors_fiche_controle(pej, point, echelle, code))),
                "nb_pa": int(count_pa_induites_par_controles(point)),
                "nb_pve": int(len(pve)) if pve is not None else 0,
            }
        ]
    )
    _export_synthese_csv(out_dir, "resume", resume)
    
    from ofbilan.engine.agregations_region import analyse_region_par_departement
    analyse_region_par_departement(point, pa, pej, pve, echelle, code, out_dir)


__all__ = [
    "activite_par_type_usager",
    "activite_police_par_theme",
    "activite_usager_par_theme",
    "analyse_pve_synthese",
    "pej_hors_fiche_controle",
    "pej_sur_fiche_controle",
    "procedures_par_theme",
    "procedures_usager_par_theme",
    "run_synthese_aggregations",
]
