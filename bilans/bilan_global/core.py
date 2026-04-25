from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pandas as pd

from scripts.common.loaders import load_natinf_ref
from scripts.common.utils import (
    agg_effectifs_usagers,
    agg_effectifs_usagers_par_domaine,
    count_controles_non_conformes_oscean,
)

_ROOT = Path(__file__).resolve().parents[2]


def analyse_controles_global(point: pd.DataFrame, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Contrôles tous domaines/thèmes (point déjà filtré par le loader sur département et période).
    Produit : effectifs par domaine, par thème, résultats (Conforme/Infraction/Manquement).
    """
    pt = point.copy()
    pt["insee_comm"] = pt["insee_comm"].astype(str).str.zfill(5)

    nb_total = len(pt)

    # Résultats
    col_resultat = "resultat" if "resultat" in pt.columns else None
    if col_resultat:
        tab_resultats = (
            pt[col_resultat]
            .value_counts()
            .rename_axis("resultat")
            .to_frame("nb")
            .reset_index()
        )
        tab_resultats["taux"] = tab_resultats["nb"] / float(nb_total or 1)
        tab_resultats.to_csv(out_dir / "controles_global_resultats.csv", sep=";", index=False)
    else:
        tab_resultats = pd.DataFrame(columns=["resultat", "nb", "taux"])
        tab_resultats.to_csv(out_dir / "controles_global_resultats.csv", sep=";", index=False)

    # Par domaine
    col_domaine = "domaine" if "domaine" in pt.columns else None
    if col_domaine:
        agg_domaine = (
            pt[col_domaine]
            .fillna("Hors domaine")
            .value_counts()
            .rename_axis("domaine")
            .to_frame("nb")
            .reset_index()
        )
        agg_domaine["taux"] = agg_domaine["nb"] / float(nb_total or 1)
        agg_domaine.to_csv(out_dir / "controles_global_par_domaine.csv", sep=";", index=False)
    else:
        agg_domaine = pd.DataFrame(columns=["domaine", "nb", "taux"])
        agg_domaine.to_csv(out_dir / "controles_global_par_domaine.csv", sep=";", index=False)

    # Par thème
    col_theme = "theme" if "theme" in pt.columns else "type_actio"
    if col_theme in pt.columns:
        agg_theme = (
            pt[col_theme]
            .fillna("Hors thème")
            .value_counts()
            .rename_axis("theme")
            .to_frame("nb")
            .reset_index()
        )
        agg_theme["taux"] = agg_theme["nb"] / float(nb_total or 1)
        agg_theme.to_csv(out_dir / "controles_global_par_theme.csv", sep=";", index=False)
    else:
        agg_theme = pd.DataFrame(columns=["theme", "nb", "taux"])
        agg_theme.to_csv(out_dir / "controles_global_par_theme.csv", sep=";", index=False)

    # Par type d'usagers (si disponible) — logique par effectifs
    if "type_usager" in pt.columns:
        agg_usager = agg_effectifs_usagers(pt, "point_ctrl", "type_usager")
        total_effectifs = int(agg_usager["nb"].sum()) if not agg_usager.empty else 0
        agg_usager["taux"] = agg_usager["nb"] / float(total_effectifs or 1)
        agg_usager.to_csv(out_dir / "controles_global_par_usager.csv", sep=";", index=False)

        # Tableau croisé Usagers × Domaine (effectifs par catégorie et domaine)
        domaine_col = col_domaine if col_domaine else None
        if domaine_col:
            cross = agg_effectifs_usagers_par_domaine(pt, col_domaine=domaine_col)
        else:
            cross = agg_effectifs_usagers_par_domaine(pt, col_domaine="domaine")
        cross.to_csv(out_dir / "controles_global_usager_par_domaine.csv", sep=";", index=False)

        # Indicateur : localisations multi-usagers (valeur source contient une virgule)
        nb_multi = int(pt["type_usager"].fillna("").astype(str).str.contains(",", regex=False).sum())
        pd.DataFrame([{"nb_controles_multi_usagers": nb_multi}]).to_csv(
            out_dir / "controles_global_usagers_resume.csv", sep=";", index=False
        )
    else:
        pd.DataFrame(columns=["type_usager", "nb", "taux"]).to_csv(
            out_dir / "controles_global_par_usager.csv", sep=";", index=False
        )
        pd.DataFrame(columns=["type_usager"]).to_csv(
            out_dir / "controles_global_usager_par_domaine.csv", sep=";", index=False
        )
        pd.DataFrame([{"nb_controles_multi_usagers": 0}]).to_csv(
            out_dir / "controles_global_usagers_resume.csv", sep=";", index=False
        )

    return tab_resultats, agg_domaine, agg_theme


def analyse_pej_pa_global(
    root: Path,
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    out_dir: Path,
) -> None:
    """PEJ et PA du département (ENTITE_ORIGINE_PROCEDURE == SD{code} pour les PEJ), tous domaines/thèmes."""
    natinf_ref = load_natinf_ref(root)
    dc_ids = set(point["dc_id"].dropna().unique()) if not point.empty and "dc_id" in point.columns else set()

    # PEJ département — filtre uniquement sur ENTITE_ORIGINE_PROCEDURE
    if "ENTITE_ORIGINE_PROCEDURE" in pej.columns:
        pej_dept = pej[pej["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.strip() == f"SD{_get_dept_code()}"].copy()
    else:
        pej_dept = pej.copy()
    if "DATE_REF" in pej_dept.columns:
        pej_dept = pej_dept.sort_values("DATE_REF", ascending=False).drop_duplicates(subset="DC_ID", keep="first").copy()
    else:
        pej_dept = pej_dept.drop_duplicates(subset="DC_ID", keep="first").copy()

    pej_par_domaine = (
        pej_dept.groupby(pej_dept.get("DOMAINE", pd.Series(dtype=object)).fillna("Hors domaine"))
        .size()
        .rename("nb_pej")
        .reset_index()
    )
    pej_par_domaine.columns = ["domaine", "nb_pej"]
    pej_par_domaine.to_csv(out_dir / "pej_global_par_domaine.csv", sep=";", index=False)

    pej_par_theme = (
        pej_dept.groupby(pej_dept.get("THEME", pd.Series(dtype=object)).fillna("Hors thème"))
        .size()
        .rename("nb_pej")
        .reset_index()
    )
    pej_par_theme.columns = ["theme", "nb_pej"]
    pej_par_theme.to_csv(out_dir / "pej_global_par_theme.csv", sep=";", index=False)

    # PEJ par NATINF (libellé depuis ref/liste_natinf.csv)
    if "NATINF_PEJ" in pej_dept.columns and not pej_dept.empty:
        codes = (
            pej_dept["NATINF_PEJ"]
            .fillna("")
            .astype(str)
            .str.split("_")
            .explode()
            .str.extract(r"(\d+)", expand=False)
            .dropna()
            .astype(str)
            .str.strip()
        )
        vc = codes.value_counts().rename_axis("numero_natinf").reset_index(name="nb_pej")
        if not natinf_ref.empty:
            vc = vc.merge(natinf_ref, on="numero_natinf", how="left")
        vc.to_csv(out_dir / "pej_global_par_natinf.csv", sep=";", index=False)

    pd.DataFrame([{"nb_pej_global": len(pej_dept)}]).to_csv(out_dir / "pej_global_resume.csv", sep=";", index=False)

    # PA département
    pa_mask = pa["DC_ID"].isin(dc_ids)
    if "ENTITE_ORIGINE_PROCEDURE" in pa.columns:
        pa_mask = pa_mask | (pa["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.strip() == f"SD{_get_dept_code()}")
    pa_dept = pa[pa_mask].copy()

    pa_par_domaine = (
        pa_dept.groupby(pa_dept.get("DOMAINE", pd.Series(dtype=object)).fillna("Hors domaine"))
        .size()
        .rename("nb_pa")
        .reset_index()
    )
    pa_par_domaine.columns = ["domaine", "nb_pa"]
    pa_par_domaine.to_csv(out_dir / "pa_global_par_domaine.csv", sep=";", index=False)

    pa_par_theme = (
        pa_dept.groupby(pa_dept.get("THEME", pd.Series(dtype=object)).fillna("Hors thème"))
        .size()
        .rename("nb_pa")
        .reset_index()
    )
    pa_par_theme.columns = ["theme", "nb_pa"]
    pa_par_theme.to_csv(out_dir / "pa_global_par_theme.csv", sep=";", index=False)

    nb_pa = pa_dept["DC_ID"].nunique() if "DC_ID" in pa_dept.columns else len(pa_dept)
    pd.DataFrame([{"nb_pa_global": nb_pa}]).to_csv(out_dir / "pa_global_resume.csv", sep=";", index=False)


def analyse_pve_global(pve: pd.DataFrame, out_dir: Path) -> None:
    """PVe du département, tous NATINF."""
    nb_pve = len(pve)
    pd.DataFrame([{"nb_pve_global": nb_pve}]).to_csv(out_dir / "pve_global_resume.csv", sep=";", index=False)
    if "INF-NATINF" in pve.columns:
        pve_par_natinf = (
            pve["INF-NATINF"]
            .astype(str)
            .value_counts()
            .rename_axis("natinf")
            .to_frame("nb")
            .reset_index()
        )
        natinf_ref = load_natinf_ref(_ROOT)
        if not natinf_ref.empty:
            pve_par_natinf["numero_natinf"] = pve_par_natinf["natinf"].astype(str).str.extract(r"(\d+)", expand=False)
            pve_par_natinf = pve_par_natinf.merge(natinf_ref, on="numero_natinf", how="left")
        pve_par_natinf.to_csv(out_dir / "pve_global_par_natinf.csv", sep=";", index=False)


def analyse_annuelle_global(
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Construit les indicateurs annuels globaux pour les périodes multi-annuelles."""
    years: set[int] = set()
    if not point.empty and "date_ctrl" in point.columns:
        years |= set(point["date_ctrl"].dropna().dt.year.astype(int).tolist())
    if not pej.empty and "DATE_REF" in pej.columns:
        years |= set(pej["DATE_REF"].dropna().dt.year.astype(int).tolist())
    if not pa.empty and "DATE_REF" in pa.columns:
        years |= set(pa["DATE_REF"].dropna().dt.year.astype(int).tolist())
    if not pve.empty and "INF-DATE-INTG" in pve.columns:
        years |= set(pve["INF-DATE-INTG"].dropna().dt.year.astype(int).tolist())

    rows = []
    for year in sorted(years):
        nb_ctrl = (
            int((point["date_ctrl"].dt.year == year).sum())
            if not point.empty and "date_ctrl" in point.columns
            else 0
        )
        nb_ctrl_inf = (
            count_controles_non_conformes_oscean(
                point.loc[point["date_ctrl"].dt.year == year, "resultat"]
            )
            if not point.empty and "date_ctrl" in point.columns and "resultat" in point.columns
            else 0
        )
        nb_pej = (
            int((pej["DATE_REF"].dt.year == year).sum())
            if not pej.empty and "DATE_REF" in pej.columns
            else 0
        )
        nb_pa = (
            int((pa["DATE_REF"].dt.year == year).sum())
            if not pa.empty and "DATE_REF" in pa.columns
            else 0
        )
        nb_pve = (
            int((pve["INF-DATE-INTG"].dt.year == year).sum())
            if not pve.empty and "INF-DATE-INTG" in pve.columns
            else 0
        )
        rows.append(
            {
                "periode": str(year),
                "nb_controles": nb_ctrl,
                "nb_controles_non_conformes": nb_ctrl_inf,
                "taux_non_conformite_controles": (nb_ctrl_inf / nb_ctrl) if nb_ctrl > 0 else pd.NA,
                "nb_pej": nb_pej,
                "nb_pa": nb_pa,
                "nb_pve": nb_pve,
            }
        )

    pd.DataFrame(rows).to_csv(
        out_dir / "indicateurs_global_par_annee.csv", sep=";", index=False
    )


def analyse_trimestrielle_global(
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Construit les indicateurs trimestriels globaux (T1=janv-mars, T2=avr-juin, T3=juil-sept, T4=oct-déc)."""
    # Trimestre = (mois - 1) // 3 + 1
    periods: set[tuple[int, int]] = set()

    if not point.empty and "date_ctrl" in point.columns:
        for _, r in point["date_ctrl"].dropna().items():
            t = r
            if hasattr(t, "year") and hasattr(t, "month"):
                q = (t.month - 1) // 3 + 1
                periods.add((int(t.year), q))
    if not pej.empty and "DATE_REF" in pej.columns:
        for _, r in pej["DATE_REF"].dropna().items():
            t = r
            if hasattr(t, "year") and hasattr(t, "month"):
                q = (t.month - 1) // 3 + 1
                periods.add((int(t.year), q))
    if not pa.empty and "DATE_REF" in pa.columns:
        for _, r in pa["DATE_REF"].dropna().items():
            t = r
            if hasattr(t, "year") and hasattr(t, "month"):
                q = (t.month - 1) // 3 + 1
                periods.add((int(t.year), q))
    if not pve.empty and "INF-DATE-INTG" in pve.columns:
        for _, r in pve["INF-DATE-INTG"].dropna().items():
            t = r
            if hasattr(t, "year") and hasattr(t, "month"):
                q = (t.month - 1) // 3 + 1
                periods.add((int(t.year), q))

    rows = []
    for (year, quarter) in sorted(periods):
        # Mois du trimestre : T1=1,2,3 T2=4,5,6 T3=7,8,9 T4=10,11,12
        m1 = (quarter - 1) * 3 + 1
        m2 = quarter * 3

        nb_ctrl = 0
        if not point.empty and "date_ctrl" in point.columns:
            dt = point["date_ctrl"]
            mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
            nb_ctrl = int(mask.sum())
        nb_ctrl_inf = 0
        if not point.empty and "date_ctrl" in point.columns and "resultat" in point.columns:
            dt = point["date_ctrl"]
            mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
            nb_ctrl_inf = count_controles_non_conformes_oscean(point.loc[mask, "resultat"])
        nb_pej = 0
        if not pej.empty and "DATE_REF" in pej.columns:
            dt = pej["DATE_REF"]
            mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
            nb_pej = int(mask.sum())
        nb_pa = 0
        if not pa.empty and "DATE_REF" in pa.columns:
            dt = pa["DATE_REF"]
            mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
            nb_pa = int(mask.sum())
        nb_pve = 0
        if not pve.empty and "INF-DATE-INTG" in pve.columns:
            dt = pve["INF-DATE-INTG"]
            mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
            nb_pve = int(mask.sum())

        rows.append(
            {
                "periode": f"{year}-T{quarter}",
                "nb_controles": nb_ctrl,
                "nb_controles_non_conformes": nb_ctrl_inf,
                "taux_non_conformite_controles": (nb_ctrl_inf / nb_ctrl) if nb_ctrl > 0 else pd.NA,
                "nb_pej": nb_pej,
                "nb_pa": nb_pa,
                "nb_pve": nb_pve,
            }
        )

    pd.DataFrame(rows).to_csv(
        out_dir / "indicateurs_global_par_trimestre.csv", sep=";", index=False
    )


def analyse_mensuelle_global(
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Construit les indicateurs mensuels globaux (YYYY-MM)."""
    periods: set[tuple[int, int]] = set()

    if not point.empty and "date_ctrl" in point.columns:
        for _, r in point["date_ctrl"].dropna().items():
            t = r
            if hasattr(t, "year") and hasattr(t, "month"):
                periods.add((int(t.year), int(t.month)))
    if not pej.empty and "DATE_REF" in pej.columns:
        for _, r in pej["DATE_REF"].dropna().items():
            t = r
            if hasattr(t, "year") and hasattr(t, "month"):
                periods.add((int(t.year), int(t.month)))
    if not pa.empty and "DATE_REF" in pa.columns:
        for _, r in pa["DATE_REF"].dropna().items():
            t = r
            if hasattr(t, "year") and hasattr(t, "month"):
                periods.add((int(t.year), int(t.month)))
    if not pve.empty and "INF-DATE-INTG" in pve.columns:
        for _, r in pve["INF-DATE-INTG"].dropna().items():
            t = r
            if hasattr(t, "year") and hasattr(t, "month"):
                periods.add((int(t.year), int(t.month)))

    rows = []
    for (year, month) in sorted(periods):
        nb_ctrl = 0
        nb_ctrl_nc = 0
        if not point.empty and "date_ctrl" in point.columns:
            dt = point["date_ctrl"]
            mask = (dt.dt.year == year) & (dt.dt.month == month)
            nb_ctrl = int(mask.sum())
            if "resultat" in point.columns:
                nb_ctrl_nc = count_controles_non_conformes_oscean(
                    point.loc[mask, "resultat"]
                )
        nb_pej = 0
        if not pej.empty and "DATE_REF" in pej.columns:
            dt = pej["DATE_REF"]
            mask = (dt.dt.year == year) & (dt.dt.month == month)
            nb_pej = int(mask.sum())
        nb_pa = 0
        if not pa.empty and "DATE_REF" in pa.columns:
            dt = pa["DATE_REF"]
            mask = (dt.dt.year == year) & (dt.dt.month == month)
            nb_pa = int(mask.sum())
        nb_pve = 0
        if not pve.empty and "INF-DATE-INTG" in pve.columns:
            dt = pve["INF-DATE-INTG"]
            mask = (dt.dt.year == year) & (dt.dt.month == month)
            nb_pve = int(mask.sum())

        rows.append(
            {
                "periode": f"{year}-{month:02d}",
                "nb_controles": nb_ctrl,
                "nb_controles_non_conformes": nb_ctrl_nc,
                "taux_non_conformite_controles": (nb_ctrl_nc / nb_ctrl)
                if nb_ctrl > 0
                else pd.NA,
                "nb_pej": nb_pej,
                "nb_pa": nb_pa,
                "nb_pve": nb_pve,
            }
        )

    pd.DataFrame(rows).to_csv(
        out_dir / "indicateurs_global_par_mois.csv", sep=";", index=False
    )


def _get_dept_code() -> str:
    """
    Récupère le code département par défaut pour les filtres PEJ/PA lorsqu'il
    n'est pas injecté explicitement. La logique existante dans le module
    d'origine repose sur une constante DEPT_CODE ; on conserve ici ce
    comportement en lisant la valeur depuis le module principal.
    """
    try:
        from scripts.bilan_global import analyse_global as ag  # type: ignore

        return getattr(ag, "DEPT_CODE", "21")
    except Exception:
        return "21"

