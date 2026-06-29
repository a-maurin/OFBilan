from __future__ import annotations

from pathlib import Path
from typing import Any, Tuple

import pandas as pd

from ofbilan.common.chargeurs_donnees import (
    load_natinf_ref,
    load_communes_noms,
)
from ofbilan.common.utilitaires_metier import (
    agg_effectifs_usagers,
    agg_effectifs_usagers_par_domaine,
    agg_procedures_dossiers_par_domaine,
    agg_resultat_counts_par_type_usager,
    build_tab_resultats,
    build_tab_resultats_controles,
    classify_resultat_controle_series,
    count_multi_usager_controles,
    count_controles_non_conformes_oscean,
    count_pa_induites_par_controles,
    count_operations_controle,
    filter_points_induisant_pa,
    points_as_pa_lignes,
)

_ROOT = Path(__file__).resolve().parents[2]

def _build_global_proc_detail(
    df: pd.DataFrame,
    proc_type: str,
    num_candidates: list[str],
    date_candidates: list[str],
    commune_candidates: list[str],
    theme_candidates: list[str],
    domaine_candidates: list[str] = None
) -> pd.DataFrame:
    if df is None or df.empty:
        cols = ["numero", "date", "commune", "thematique", "domaine", "type_procedure"]
        return pd.DataFrame(columns=cols)
    d = df.copy()
    
    def _coalesce(cols: list[str]) -> pd.Series:
        res = pd.Series([pd.NA] * len(d), index=d.index)
        if not cols:
            return res
        for c in cols:
            if c in d.columns:
                temp = d[c].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "INC": pd.NA, "ND": pd.NA, "n.d.": pd.NA})
                res = res.fillna(temp)
        return res
        
    out = pd.DataFrame({
        "numero": _coalesce(num_candidates),
        "date": _coalesce(date_candidates),
        "commune": _coalesce(commune_candidates),
        "thematique": _coalesce(theme_candidates),
        "domaine": _coalesce(domaine_candidates) if domaine_candidates else "Hors domaine",
        "type_procedure": proc_type
    }, index=d.index)
    
    for col in ["numero", "date", "commune", "thematique", "domaine"]:
        out[col] = out[col].fillna("").astype(str).str.strip().replace({"<NA>": "", "nan": "", "None": "", "n.d.": ""})
    
    out["commune"] = out["commune"].replace({"": pd.NA}).fillna("n.d.")
    
    # Mapping points -> communes (fallback) using DC_ID if present in df
    if "DC_ID" in d.columns and "dc_id" in d.columns:
        pass # To be mapped externally or handled below
        
    out["commune"] = out["commune"].fillna("n.d.")
    
    if "date" in out.columns:
        try:
            dt_s = pd.to_datetime(out["date"], errors="coerce")
            out["date"] = dt_s.dt.strftime("%d/%m/%Y").fillna("n.d.")
        except Exception:
            pass
            
    # Pyarrow safe replace for thematic labels
    if not out.empty and "thematique" in out.columns:
        out["thematique"] = out["thematique"].astype(object).str.replace(r"^.*_.*?_", "", regex=True)
    
    return out


def _tab_resultats_controles_detail(point: pd.DataFrame) -> pd.DataFrame:
    """Synthèse « Résultats des contrôles » pour le bilan global (section 2.2)."""
    return build_tab_resultats_controles(point, distinction_coeur_hors_coeur=False)


def _resultats_par_domaine_pour_pdf(pt: pd.DataFrame) -> pd.DataFrame:
    """
    Comptages par domaine : Conforme / Non-conforme (Infraction+Manquement) / En attente (résiduel).

    Aligné sur la logique du tableau « résultats des contrôles » global (pas de ventilation PNF).
    """
    col_d = "domaine" if "domaine" in pt.columns else None
    col_r = "resultat" if "resultat" in pt.columns else None
    if not col_d or not col_r:
        return pd.DataFrame(columns=["domaine", "Conforme", "Non-conforme", "En attente"])
    dom_s = pt[col_d].fillna("Hors domaine").astype(str)
    r_s = classify_resultat_controle_series(pt[col_r])
    gdf = pt.assign(_d=dom_s, _r=r_s)
    rows: list[dict[str, Any]] = []
    for dom, g in gdf.groupby("_d", sort=False):
        m = g["_r"]
        n_c = int(m.eq("Conforme").sum())
        n_nc = int(m.isin(["Infraction", "Manquement"]).sum())
        n_a = int(m.eq("En attente").sum())
        rows.append(
            {
                "domaine": str(dom),
                "Conforme": n_c,
                "Non-conforme": n_nc,
                "En attente": n_a,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["_vol"] = out["Conforme"] + out["Non-conforme"] + out["En attente"]
    out = out.sort_values("_vol", ascending=False, kind="stable").drop(columns=["_vol"])
    return out.reset_index(drop=True)


def analyse_controles_global(point: pd.DataFrame, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Controles tous domaines/themes (point deja filtre par le loader sur departement et periode).
    Produit : effectifs par domaine, par theme, resultats (Conforme/Infraction/Manquement).
    """
    pt = point.copy()
    pt["insee_comm"] = pt["insee_comm"].astype(str).str.zfill(5)

    nb_total = len(pt)
    
    pd.DataFrame([{"nb_operations_controle": count_operations_controle(pt)}]).to_csv(
        out_dir / "controles_global_operations_resume.csv", sep=";", index=False
    )

    col_resultat = "resultat" if "resultat" in pt.columns else None
    if col_resultat:
        tab_resultats = build_tab_resultats(pt)
        tab_resultats.to_csv(out_dir / "controles_global_resultats.csv", sep=";", index=False)
        res_ctrl = _tab_resultats_controles_detail(pt)
        res_ctrl.to_csv(out_dir / "controles_global_resultats_controles.csv", sep=";", index=False)
        res_dom = _resultats_par_domaine_pour_pdf(pt)
        res_dom.to_csv(out_dir / "controles_global_resultats_par_domaine.csv", sep=";", index=False)
    else:
        tab_resultats = pd.DataFrame(columns=["resultat", "nb", "taux"])
        tab_resultats.to_csv(out_dir / "controles_global_resultats.csv", sep=";", index=False)
        pd.DataFrame(columns=["resultat", "nb", "taux"]).to_csv(
            out_dir / "controles_global_resultats_controles.csv", sep=";", index=False
        )
        pd.DataFrame(
            columns=["domaine", "Conforme", "Non-conforme", "En attente"]
        ).to_csv(out_dir / "controles_global_resultats_par_domaine.csv", sep=";", index=False)

    col_domaine = "domaine" if "domaine" in pt.columns else None
    if col_domaine:
        pt_filled = pt.copy()
        pt_filled[col_domaine] = pt_filled[col_domaine].fillna("Hors domaine").astype(str).str.strip()
        agg_domaine = (
            pt_filled[col_domaine]
            .value_counts()
            .rename_axis("domaine")
            .to_frame("nb")
            .reset_index()
        )
        if "fc_id" in pt_filled.columns:
            ops_par_domaine = pt_filled.groupby(col_domaine)["fc_id"].nunique().reset_index(name="nb_operations")
            agg_domaine = pd.merge(agg_domaine, ops_par_domaine, on="domaine", how="left")
        else:
            agg_domaine["nb_operations"] = 0

        agg_domaine["taux"] = agg_domaine["nb"] / float(nb_total or 1)
        agg_domaine.to_csv(out_dir / "controles_global_par_domaine.csv", sep=";", index=False)
    else:
        agg_domaine = pd.DataFrame(columns=["domaine", "nb", "nb_operations", "taux"])
        agg_domaine.to_csv(out_dir / "controles_global_par_domaine.csv", sep=";", index=False)

    col_theme = "theme" if "theme" in pt.columns else "type_actio"
    if col_theme in pt.columns:
        pt_theme_filled = pt.copy()
        pt_theme_filled[col_theme] = pt_theme_filled[col_theme].fillna("Hors theme").astype(str).str.strip()
        agg_theme = (
            pt_theme_filled[col_theme]
            .value_counts()
            .rename_axis("theme")
            .to_frame("nb")
            .reset_index()
        )
        if "fc_id" in pt_theme_filled.columns:
            ops_par_theme = pt_theme_filled.groupby(col_theme)["fc_id"].nunique().reset_index(name="nb_operations")
            agg_theme = pd.merge(agg_theme, ops_par_theme, on="theme", how="left")
        else:
            agg_theme["nb_operations"] = 0

        agg_theme["taux"] = agg_theme["nb"] / float(nb_total or 1)
        agg_theme.to_csv(out_dir / "controles_global_par_theme.csv", sep=";", index=False)
    else:
        agg_theme = pd.DataFrame(columns=["theme", "nb", "taux"])
        agg_theme.to_csv(out_dir / "controles_global_par_theme.csv", sep=";", index=False)

    if "type_usager" in pt.columns:
        agg_usager = agg_effectifs_usagers(pt, "point_ctrl", "type_usager")
        total_effectifs = int(agg_usager["nb"].sum()) if not agg_usager.empty else 0
        agg_usager["taux"] = agg_usager["nb"] / float(total_effectifs or 1)
        agg_usager.to_csv(out_dir / "controles_global_par_usager.csv", sep=";", index=False)

        res_type_usager = agg_resultat_counts_par_type_usager(pt)
        res_type_usager.to_csv(
            out_dir / "controles_global_resultats_par_type_usager.csv",
            sep=";",
            index=False,
        )

        domaine_col = col_domaine if col_domaine else None
        if domaine_col:
            cross = agg_effectifs_usagers_par_domaine(pt, col_domaine=domaine_col)
        else:
            cross = agg_effectifs_usagers_par_domaine(pt, col_domaine="domaine")
        cross.to_csv(out_dir / "controles_global_usager_par_domaine.csv", sep=";", index=False)

        nb_multi = count_multi_usager_controles(pt)
        pd.DataFrame([{"nb_localisations_multi_usagers": nb_multi}]).to_csv(
            out_dir / "controles_global_usagers_resume.csv", sep=";", index=False
        )
    else:
        pd.DataFrame(columns=["type_usager", "nb", "taux"]).to_csv(
            out_dir / "controles_global_par_usager.csv", sep=";", index=False
        )
        pd.DataFrame(
            columns=[
                "type_usager",
                "Conforme",
                "Infraction",
                "Manquement",
                "Autre_resultat",
                "Total",
            ]
        ).to_csv(
            out_dir / "controles_global_resultats_par_type_usager.csv",
            sep=";",
            index=False,
        )
        pd.DataFrame(columns=["type_usager"]).to_csv(
            out_dir / "controles_global_usager_par_domaine.csv", sep=";", index=False
        )
        pd.DataFrame([{"nb_localisations_multi_usagers": 0}]).to_csv(
            out_dir / "controles_global_usagers_resume.csv", sep=";", index=False
        )

    return tab_resultats, agg_domaine, agg_theme


def analyse_pej_pa_global(
    root: Path,
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    out_dir: Path,
    echelle: str = "departement",
    code: str = "21",
) -> None:
    """PEJ et PA du departement (ENTITE_ORIGINE_PROCEDURE == SD{code} pour les PEJ), tous domaines/themes."""
    natinf_ref = load_natinf_ref(root)
    dc_ids = set(point["dc_id"].dropna().unique()) if not point.empty and "dc_id" in point.columns else set()

    echelle = str(echelle).strip() or "departement"
    code = str(code).strip() or "21"
    from ofbilan.common.utilitaires_metier import get_departements_pour_perimetre
    dept_codes = get_departements_pour_perimetre(echelle, code)
    sd_list = [f"SD{c}" for c in dept_codes] if dept_codes and "FR" not in dept_codes else []
    if "ENTITE_ORIGINE_PROCEDURE" in pej.columns:
        if echelle.lower() == "bmi":
            pej_dept = pej.copy()
        else:
            pej_dept = pej[pej["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.strip().isin(sd_list)].copy() if sd_list else pej.copy()
    else:
        pej_dept = pej.copy()
    if "DATE_REF" in pej_dept.columns:
        pej_dept = pej_dept.sort_values("DATE_REF", ascending=False)
        pej_dept = pej_dept[pej_dept["DC_ID"].isna() | ~pej_dept.duplicated(subset=["DC_ID"], keep="first")].copy()
    else:
        pej_dept = pej_dept[pej_dept["DC_ID"].isna() | ~pej_dept.duplicated(subset=["DC_ID"], keep="first")].copy()

    from ofbilan.common.chargeurs_donnees import merge_pej_faits_locations
    pej_dept = merge_pej_faits_locations(pej_dept, root, echelle, code)

    def _col_or_fallback(df: pd.DataFrame, name: str, fallback: str) -> pd.Series:
        if name in df.columns:
            return df[name].fillna(fallback)
        return pd.Series([fallback] * len(df), index=df.index, dtype=object)

    col_commune = "nom_commune" if "nom_commune" in point.columns else ("nom_commun" if "nom_commun" in point.columns else None)
    nom_commune_by_dc = {}
    if not point.empty and "dc_id" in point.columns and col_commune:
        tmp_p = point.dropna(subset=["dc_id"]).copy()
        tmp_p["dc_id_str"] = tmp_p["dc_id"].astype(str).astype(object).str.strip().str.replace(r"\.0$", "", regex=True)
        nom_commune_by_dc = tmp_p.drop_duplicates("dc_id_str").set_index("dc_id_str")[col_commune].astype(str).to_dict()

    pej_par_domaine = (
        pej_dept.groupby(_col_or_fallback(pej_dept, "DOMAINE", "Hors domaine"))
        .size()
        .rename("nb_pej")
        .reset_index()
    )
    pej_par_domaine.columns = ["domaine", "nb_pej"]
    pej_par_domaine.to_csv(out_dir / "pej_global_par_domaine.csv", sep=";", index=False)

    pej_par_theme = (
        pej_dept.groupby(_col_or_fallback(pej_dept, "THEME", "Hors theme"))
        .size()
        .rename("nb_pej")
        .reset_index()
    )
    pej_par_theme.columns = ["theme", "nb_pej"]
    pej_par_theme.to_csv(out_dir / "pej_global_par_theme.csv", sep=";", index=False)

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
        vc = codes.value_counts().rename_axis("natinf").reset_index(name="nb")
        if not natinf_ref.empty:
            vc["numero_natinf"] = vc["natinf"].astype(str).str.extract(r"(\d+)", expand=False)
            vc = vc.merge(natinf_ref, on="numero_natinf", how="left")
        vc.to_csv(out_dir / "pej_global_par_natinf.csv", sep=";", index=False)

    pd.DataFrame([{"nb_pej_global": len(pej_dept)}]).to_csv(out_dir / "pej_global_resume.csv", sep=";", index=False)

    pej_detail = _build_global_proc_detail(
        pej_dept, "PEJ", ["NUM_DOSSIER", "DC_ID"], ["DATE_FAITS", "DATE_REF"], ["NOM_COM", "COMMUNE_LIB", "LIBELLE_COMMUNE_FAITS", "NOM_COM_FAITS", "nom_commune", "COMMUNE"], ["THEME", "NATINF_PEJ"], ["DOMAINE"]
    )
    if not pej_detail.empty and "DC_ID" in pej_dept.columns:
        pej_detail["commune"] = pej_detail["commune"].astype(object)
        pej_dc_str = pej_dept["DC_ID"].astype(str).astype(object).str.strip().str.replace(r"\.0$", "", regex=True)
        mapped_communes = pej_dc_str.map(nom_commune_by_dc)
        mask = pej_detail["commune"].isna() | pej_detail["commune"].isin(["n.d.", "nan", "", "INC", "ND"])
        pej_detail.loc[mask, "commune"] = mapped_communes[mask]
        pej_detail["commune"] = pej_detail["commune"].fillna("n.d.")
    pej_detail.to_csv(out_dir / "pej_detail.csv", sep=";", index=False)

    pa_lignes = points_as_pa_lignes(point)

    pa_par_domaine = (
        pa_lignes.groupby(_col_or_fallback(pa_lignes, "DOMAINE", "Hors domaine"))
        .size()
        .rename("nb_pa")
        .reset_index()
    )
    pa_par_domaine.columns = ["domaine", "nb_pa"]
    pa_par_domaine.to_csv(out_dir / "pa_global_par_domaine.csv", sep=";", index=False)

    pa_par_theme = (
        pa_lignes.groupby(_col_or_fallback(pa_lignes, "THEME", "Hors theme"))
        .size()
        .rename("nb_pa")
        .reset_index()
    )
    pa_par_theme.columns = ["theme", "nb_pa"]
    pa_par_theme.to_csv(out_dir / "pa_global_par_theme.csv", sep=";", index=False)

    nb_pa = count_pa_induites_par_controles(point)
    pd.DataFrame([{"nb_pa_global": nb_pa}]).to_csv(out_dir / "pa_global_resume.csv", sep=";", index=False)

    point_pa = filter_points_induisant_pa(point)
    pa_detail = _build_global_proc_detail(
        point_pa, "PA", ["dc_id", "numero"], ["date_ctrl", "date"], ["nom_commune", "commune", "COMMUNE_LIB", "LIBELLE_COMMUNE_FAITS"], ["theme", "thematique"], ["DOMAINE", "domaine"]
    )
    pa_detail.to_csv(out_dir / "pa_detail.csv", sep=";", index=False)

    if "type_usager" in point.columns:
        proc_ud = agg_procedures_dossiers_par_domaine(
            pej_dept,
            pa_lignes,
            with_type_usager=True,
            source_table="point_ctrl",
            source_champ="type_usager",
        )
        if not proc_ud.empty and "type_usager" in proc_ud.columns:
            metrics = [c for c in ("nb_pej", "nb_pa") if c in proc_ud.columns]
            proc_ut = proc_ud.groupby("type_usager", as_index=False)[metrics].sum()
            if metrics:
                proc_ut["_vol"] = proc_ut[metrics].fillna(0).sum(axis=1)
                proc_ut = proc_ut.sort_values("_vol", ascending=False, kind="stable").drop(
                    columns=["_vol"]
                )
            proc_ut.to_csv(
                out_dir / "procedures_global_par_type_usager.csv",
                sep=";",
                index=False,
            )
        else:
            pd.DataFrame(columns=["type_usager", "nb_pej", "nb_pa"]).to_csv(
                out_dir / "procedures_global_par_type_usager.csv",
                sep=";",
                index=False,
            )


def analyse_pve_global(pve: pd.DataFrame, out_dir: Path) -> None:
    """PVe du departement, tous NATINF."""
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

    pve_detail = _build_global_proc_detail(
        pve, "PVe", ["INF-ID"], ["INF-DATE-MIF", "INF-DATE-INTG", "INF-DATE", "INF-DATE-I", "INF_DATE", "DATE_FAITS"], ["COMMUNE_LIB", "INF-LIEU", "COMMUNE", "NOM_COM", "INF-INSEE", "INSEE_DEP"], ["INF-NATINF"], ["DOMAINE"]
    )
    if not pve_detail.empty and "numero" in pve_detail.columns:
        communes_ref = load_communes_noms(_ROOT)
        if communes_ref:
            mapped_com = pve_detail["commune"].astype(str).str.zfill(5).map(communes_ref)
            pve_detail["commune"] = mapped_com.fillna(pve_detail["commune"])

        natinf_ref = load_natinf_ref(_ROOT)
        if not natinf_ref.empty:
            codes = pve_detail["thematique"].astype(str).str.extract(r"(\d+)", expand=False)
            mapped_th = codes.map(natinf_ref.set_index("numero_natinf")["libelle_natinf"])
            pve_detail["thematique"] = mapped_th.fillna(pve_detail["thematique"])
    pve_detail.to_csv(out_dir / "pve_detail.csv", sep=";", index=False)


def analyse_annuelle_global(
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Construit les indicateurs annuels globaux pour les periodes multi-annuelles."""
    if not point.empty and "date_ctrl" in point.columns:
        point = point.copy()
        point["date_ctrl"] = pd.to_datetime(point["date_ctrl"], errors="coerce")
    if not pej.empty and "DATE_REF" in pej.columns:
        pej = pej.copy()
        pej["DATE_REF"] = pd.to_datetime(pej["DATE_REF"], errors="coerce")
    if not pve.empty and "INF-DATE-INTG" in pve.columns:
        pve = pve.copy()
        pve["INF-DATE-INTG"] = pd.to_datetime(pve["INF-DATE-INTG"], errors="coerce")

    years: set[int] = set()
    if not point.empty and "date_ctrl" in point.columns:
        years |= set(point["date_ctrl"].dropna().dt.year.astype(int).tolist())
    if not pej.empty and "DATE_REF" in pej.columns:
        years |= set(pej["DATE_REF"].dropna().dt.year.astype(int).tolist())
    pa_pts = filter_points_induisant_pa(point)
    if not pa_pts.empty and "date_ctrl" in pa_pts.columns:
        years |= set(pa_pts["date_ctrl"].dropna().dt.year.astype(int).tolist())
    if not pve.empty and "INF-DATE-INTG" in pve.columns:
        years |= set(pve["INF-DATE-INTG"].dropna().dt.year.astype(int).tolist())

    rows = []
    for year in sorted(years):
        nb_localisations = (
            int((point["date_ctrl"].dt.year == year).sum())
            if not point.empty and "date_ctrl" in point.columns
            else 0
        )
        nb_ops = 0
        if not point.empty and "date_ctrl" in point.columns:
            mask = point["date_ctrl"].dt.year == year
            nb_ops = count_operations_controle(point, mask=mask)
        nb_localisations_inf = (
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
        nb_pa = 0
        if not point.empty and "date_ctrl" in point.columns and "resultat" in point.columns:
            dt = point["date_ctrl"]
            mask = dt.dt.year == year
            nb_pa = count_pa_induites_par_controles(point, mask=mask)
        nb_pve = (
            int((pve["INF-DATE-INTG"].dt.year == year).sum())
            if not pve.empty and "INF-DATE-INTG" in pve.columns
            else 0
        )
        rows.append(
            {
                "periode": str(year),
                "nb_localisations": nb_localisations,
                "nb_operations_controle": nb_ops,
                "nb_localisations_non_conformes": nb_localisations_inf,
                "taux_non_conformite_localisations": (nb_localisations_inf / nb_localisations) if nb_localisations > 0 else pd.NA,
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
    """Construit les indicateurs trimestriels globaux (T1=janv-mars, T2=avr-juin, T3=juil-sept, T4=oct-dec)."""
    if not point.empty and "date_ctrl" in point.columns:
        point = point.copy()
        point["date_ctrl"] = pd.to_datetime(point["date_ctrl"], errors="coerce")
    if not pej.empty and "DATE_REF" in pej.columns:
        pej = pej.copy()
        pej["DATE_REF"] = pd.to_datetime(pej["DATE_REF"], errors="coerce")
    if not pve.empty and "INF-DATE-INTG" in pve.columns:
        pve = pve.copy()
        pve["INF-DATE-INTG"] = pd.to_datetime(pve["INF-DATE-INTG"], errors="coerce")

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
    pa_pts = filter_points_induisant_pa(point)
    if not pa_pts.empty and "date_ctrl" in pa_pts.columns:
        for _, r in pa_pts["date_ctrl"].dropna().items():
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
        m1 = (quarter - 1) * 3 + 1
        m2 = quarter * 3

        nb_localisations = 0
        nb_ops = 0
        if not point.empty and "date_ctrl" in point.columns:
            dt = point["date_ctrl"]
            mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
            nb_localisations = int(mask.sum())
            nb_ops = count_operations_controle(point, mask=mask)
        nb_localisations_inf = 0
        if not point.empty and "date_ctrl" in point.columns and "resultat" in point.columns:
            dt = point["date_ctrl"]
            mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
            nb_localisations_inf = count_controles_non_conformes_oscean(point.loc[mask, "resultat"])
        nb_pej = 0
        if not pej.empty and "DATE_REF" in pej.columns:
            dt = pej["DATE_REF"]
            mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
            nb_pej = int(mask.sum())
        nb_pa = 0
        if not point.empty and "date_ctrl" in point.columns and "resultat" in point.columns:
            dt = point["date_ctrl"]
            mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
            nb_pa = count_pa_induites_par_controles(point, mask=mask)
        nb_pve = 0
        if not pve.empty and "INF-DATE-INTG" in pve.columns:
            dt = pve["INF-DATE-INTG"]
            mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
            nb_pve = int(mask.sum())

        rows.append(
            {
                "periode": f"{year}-T{quarter}",
                "nb_localisations": nb_localisations,
                "nb_operations_controle": nb_ops,
                "nb_localisations_non_conformes": nb_localisations_inf,
                "taux_non_conformite_localisations": (nb_localisations_inf / nb_localisations) if nb_localisations > 0 else pd.NA,
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
    if not point.empty and "date_ctrl" in point.columns:
        point = point.copy()
        point["date_ctrl"] = pd.to_datetime(point["date_ctrl"], errors="coerce")
    if not pej.empty and "DATE_REF" in pej.columns:
        pej = pej.copy()
        pej["DATE_REF"] = pd.to_datetime(pej["DATE_REF"], errors="coerce")
    if not pve.empty and "INF-DATE-INTG" in pve.columns:
        pve = pve.copy()
        pve["INF-DATE-INTG"] = pd.to_datetime(pve["INF-DATE-INTG"], errors="coerce")

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
    pa_pts = filter_points_induisant_pa(point)
    if not pa_pts.empty and "date_ctrl" in pa_pts.columns:
        for _, r in pa_pts["date_ctrl"].dropna().items():
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
        nb_localisations = 0
        nb_ops = 0
        nb_localisations_nc = 0
        if not point.empty and "date_ctrl" in point.columns:
            dt = point["date_ctrl"]
            mask = (dt.dt.year == year) & (dt.dt.month == month)
            nb_localisations = int(mask.sum())
            nb_ops = count_operations_controle(point, mask=mask)
            if "resultat" in point.columns:
                nb_localisations_nc = count_controles_non_conformes_oscean(
                    point.loc[mask, "resultat"]
                )
        nb_pej = 0
        if not pej.empty and "DATE_REF" in pej.columns:
            dt = pej["DATE_REF"]
            mask = (dt.dt.year == year) & (dt.dt.month == month)
            nb_pej = int(mask.sum())
        nb_pa = 0
        if not point.empty and "date_ctrl" in point.columns and "resultat" in point.columns:
            dt = point["date_ctrl"]
            mask = (dt.dt.year == year) & (dt.dt.month == month)
            nb_pa = count_pa_induites_par_controles(point, mask=mask)
        nb_pve = 0
        if not pve.empty and "INF-DATE-INTG" in pve.columns:
            dt = pve["INF-DATE-INTG"]
            mask = (dt.dt.year == year) & (dt.dt.month == month)
            nb_pve = int(mask.sum())

        rows.append(
            {
                "periode": f"{year}-{month:02d}",
                "nb_localisations": nb_localisations,
                "nb_operations_controle": nb_ops,
                "nb_localisations_non_conformes": nb_localisations_nc,
                "taux_non_conformite_localisations": (nb_localisations_nc / nb_localisations)
                if nb_localisations > 0
                else pd.NA,
                "nb_pej": nb_pej,
                "nb_pa": nb_pa,
                "nb_pve": nb_pve,
            }
        )

    pd.DataFrame(rows).to_csv(
        out_dir / "indicateurs_global_par_mois.csv", sep=";", index=False
    )


def analyse_hebdomadaire_global(
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Indicateurs par semaine (libellé YYYY-Sww), aligné sur le moteur thématique."""
    if not point.empty and "date_ctrl" in point.columns:
        point = point.copy()
        point["date_ctrl"] = pd.to_datetime(point["date_ctrl"], errors="coerce")
    if not pej.empty and "DATE_REF" in pej.columns:
        pej = pej.copy()
        pej["DATE_REF"] = pd.to_datetime(pej["DATE_REF"], errors="coerce")
    if not pve.empty and "INF-DATE-INTG" in pve.columns:
        pve = pve.copy()
        pve["INF-DATE-INTG"] = pd.to_datetime(pve["INF-DATE-INTG"], errors="coerce")

    periods: set[tuple[int, int]] = set()

    def _collect(df: pd.DataFrame, col: str) -> None:
        if df is None or df.empty or col not in df.columns:
            return
        dt = pd.to_datetime(df[col], errors="coerce").dropna()
        if dt.empty:
            return
        iso = dt.dt.isocalendar()
        for y, w in zip(iso["year"].tolist(), iso["week"].tolist()):
            periods.add((int(y), int(w)))

    _collect(point, "date_ctrl")
    _collect(pej, "DATE_REF")
    _collect(filter_points_induisant_pa(point), "date_ctrl")
    _collect(pve, "INF-DATE-INTG")

    rows = []
    for (year, week) in sorted(periods):
        nb_localisations = 0
        nb_ops = 0
        nb_localisations_nc = 0
        if not point.empty and "date_ctrl" in point.columns:
            dt = point["date_ctrl"]
            iso = dt.dt.isocalendar()
            mask = (iso["year"] == year) & (iso["week"] == week)
            nb_localisations = int(mask.sum())
            nb_ops = count_operations_controle(point, mask=mask)
            if "resultat" in point.columns:
                nb_localisations_nc = count_controles_non_conformes_oscean(point.loc[mask, "resultat"])
        nb_pej = 0
        if not pej.empty and "DATE_REF" in pej.columns:
            dt = pej["DATE_REF"]
            iso = dt.dt.isocalendar()
            nb_pej = int(((iso["year"] == year) & (iso["week"] == week)).sum())
        nb_pa = 0
        if not point.empty and "date_ctrl" in point.columns and "resultat" in point.columns:
            dt = point["date_ctrl"]
            iso = dt.dt.isocalendar()
            mask = (iso["year"] == year) & (iso["week"] == week)
            nb_pa = count_pa_induites_par_controles(point, mask=mask)
        nb_pve = 0
        if not pve.empty and "INF-DATE-INTG" in pve.columns:
            dt = pve["INF-DATE-INTG"]
            iso = dt.dt.isocalendar()
            nb_pve = int(((iso["year"] == year) & (iso["week"] == week)).sum())

        rows.append(
            {
                "periode": f"{year}-S{week:02d}",
                "nb_localisations": nb_localisations,
                "nb_operations_controle": nb_ops,
                "nb_localisations_non_conformes": nb_localisations_nc,
                "taux_non_conformite_localisations": (nb_localisations_nc / nb_localisations) if nb_localisations > 0 else pd.NA,
                "nb_pej": nb_pej,
                "nb_pa": nb_pa,
                "nb_pve": nb_pve,
            }
        )

    pd.DataFrame(rows).to_csv(
        out_dir / "indicateurs_global_par_semaine.csv", sep=";", index=False
    )


__all__ = [
    "analyse_controles_global",
    "analyse_pej_pa_global",
    "analyse_pve_global",
    "analyse_annuelle_global",
    "analyse_trimestrielle_global",
    "analyse_mensuelle_global",
    "analyse_hebdomadaire_global",
    "run_profile_aggregations",
]


def run_profile_aggregations(
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
    pej_global: pd.DataFrame | None = None,
) -> None:
    """Adapter d'agrégations piloté par profil YAML."""
    analyse_controles_global(point, out_dir)
    analyse_pej_pa_global(root, point, pa, pej, out_dir, echelle=echelle, code=code)
    analyse_pve_global(pve, out_dir)
    if ventilation_mode == "annuelle":
        analyse_annuelle_global(point, pa, pej, pve, out_dir)
    elif ventilation_mode == "mensuelle":
        analyse_mensuelle_global(point, pa, pej, pve, out_dir)
    elif ventilation_mode == "hebdomadaire":
        analyse_hebdomadaire_global(point, pa, pej, pve, out_dir)
    elif ventilation_mode == "trimestrielle":
        analyse_trimestrielle_global(point, pa, pej, pve, out_dir)
        if int((date_fin - date_deb).days) < 730:
            analyse_mensuelle_global(point, pa, pej, pve, out_dir)
    else:
        pd.DataFrame(
            columns=[
                "periode",
                "nb_localisations",
                "nb_operations_controle",
                "nb_localisations_non_conformes",
                "taux_non_conformite_localisations",
                "nb_pej",
                "nb_pa",
                "nb_pve",
            ]
        ).to_csv(out_dir / "indicateurs_global_par_annee.csv", sep=";", index=False)
        
    from ofbilan.engine.agregations_region import analyse_region_par_departement
    analyse_region_par_departement(
        point, pa, pej, pve, echelle, code, out_dir,
        pej_global=pej_global, profil_id=str(profile.get("id", "global"))
    )
