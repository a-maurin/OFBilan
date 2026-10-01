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
MODULE : CALCULS D'AGREGATION PAR PROFIL DE BILAN (`agregations_profil.py`)
========================================================================================
Ce module regroupe les fonctions de calcul statistique et d'agrégation de données pour
les bilans par profil (SD départemental, Région, thématique spécifique).

Opérations clés :
  1. Comptage des opérations de contrôle et décompte par domaine / thème / usager.
  2. Classification des résultats (Conforme, Manquement, Infraction, En attente).
  3. Construction des tableaux de détails des procédures (PEJ, PA, PVe).
  4. Génération des fichiers CSV de synthèse intermédiaire prêts pour l'injection PDF.
========================================================================================
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Tuple

import pandas as pd

from core.common.chargeurs_donnees import (
    load_natinf_ref,
    load_concordance_natinf_snc,
    load_communes_noms,
)
from core.common.utilitaires_metier import (
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
        agg_usager["nb_total"] = agg_usager["nb"]
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
        pd.DataFrame(columns=["type_usager", "nb", "nb_total", "taux"]).to_csv(
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
    gdf_faits: pd.DataFrame | None = None,
) -> None:
    """PEJ et PA du departement (ENTITE_ORIGINE_PROCEDURE == SD{code} pour les PEJ), tous domaines/themes."""
    natinf_ref = load_natinf_ref(root)
    dc_ids = set(point["dc_id"].dropna().unique()) if not point.empty and "dc_id" in point.columns else set()

    echelle = str(echelle).strip() or "departement"
    code = str(code).strip() or "21"
    from core.common.utilitaires_metier import get_departements_pour_perimetre
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

    from core.common.chargeurs_donnees import merge_pej_faits_locations
    pej_dept = merge_pej_faits_locations(pej_dept, root, echelle, code, gdf_faits=gdf_faits)

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
        pve_par_natinf["numero_natinf"] = pve_par_natinf["natinf"].astype(str).str.extract(r"(\d+)", expand=False)
        if not natinf_ref.empty:
            pve_par_natinf = pve_par_natinf.merge(natinf_ref, on="numero_natinf", how="left")
        df_conc = load_concordance_natinf_snc(_ROOT)
        if not df_conc.empty:
            pve_par_natinf["numero_natinf_clean"] = pve_par_natinf["numero_natinf"].fillna("").astype(str).str.strip().str.lstrip("0")
            pve_par_natinf = pve_par_natinf.merge(
                df_conc[["numero_natinf", "domaine_snc", "theme_snc", "action_snc"]],
                left_on="numero_natinf_clean",
                right_on="numero_natinf",
                how="left",
                suffixes=("", "_conc"),
            )
            fallback_snc = "Infractions hors périmètre SNC"
            invalid_vals = ["", "Non Classé / Hors SNC", "Hors thème", "Hors domaine", "Hors action", "nan", "None"]
            pve_par_natinf["theme_snc"] = pve_par_natinf["theme_snc"].fillna(fallback_snc).astype(str).replace(invalid_vals, fallback_snc)
            pve_par_natinf["domaine_snc"] = pve_par_natinf["domaine_snc"].fillna(fallback_snc).astype(str).replace(invalid_vals, fallback_snc)
        pve_par_natinf.to_csv(out_dir / "pve_global_par_natinf.csv", sep=";", index=False)

    # Agrégation des PVe par Domaine, Thème et Action de contrôle (SNC)
    dom_col = next((c for c in ("domaine", "DOMAINE", "domaine_snc", "DOMAINE_SNC") if c in pve.columns), None)
    theme_col = next((c for c in ("theme", "THEME", "theme_snc", "THEME_SNC") if c in pve.columns), None)
    act_col = next((c for c in ("action", "ACTION", "action_snc", "ACTION_SNC") if c in pve.columns), None)

    fallback_snc = "Infractions hors périmètre SNC"
    invalid_vals = ["", "Non Classé / Hors SNC", "Hors thème", "Hors domaine", "Hors action", "nan", "None"]

    pve_df = pve.copy() if not pve.empty else pd.DataFrame()

    if not pve_df.empty:
        if dom_col:
            pve_df["_dom_clean"] = pve_df[dom_col].fillna(fallback_snc).astype(str).replace(invalid_vals, fallback_snc)
        else:
            pve_df["_dom_clean"] = fallback_snc

        if theme_col:
            pve_df["_theme_clean"] = pve_df[theme_col].fillna(fallback_snc).astype(str).replace(invalid_vals, fallback_snc)
        else:
            pve_df["_theme_clean"] = fallback_snc

        if act_col:
            pve_df["_act_clean"] = pve_df[act_col].fillna(fallback_snc).astype(str).replace(invalid_vals, fallback_snc)
        else:
            pve_df["_act_clean"] = fallback_snc

        # pve_global_par_theme.csv (domaine;theme;nb_pve)
        pve_par_theme = (
            pve_df.groupby(["_dom_clean", "_theme_clean"], as_index=False)
            .size()
            .rename(columns={"_dom_clean": "domaine", "_theme_clean": "theme", "size": "nb_pve"})
            .sort_values(by="nb_pve", ascending=False)
        )

        # pve_global_par_domaine.csv (domaine;nb_pve)
        pve_par_domaine = (
            pve_df["_dom_clean"]
            .value_counts()
            .rename_axis("domaine")
            .to_frame("nb_pve")
            .reset_index()
        )

        # pve_global_par_action.csv (action;nb_pve)
        pve_par_action = (
            pve_df["_act_clean"]
            .value_counts()
            .rename_axis("action")
            .to_frame("nb_pve")
            .reset_index()
        )
    else:
        pve_par_theme = pd.DataFrame(columns=["domaine", "theme", "nb_pve"])
        pve_par_domaine = pd.DataFrame(columns=["domaine", "nb_pve"])
        pve_par_action = pd.DataFrame(columns=["action", "nb_pve"])

    pve_par_theme.to_csv(out_dir / "pve_global_par_theme.csv", sep=";", index=False)
    pve_par_domaine.to_csv(out_dir / "pve_global_par_domaine.csv", sep=";", index=False)
    pve_par_action.to_csv(out_dir / "pve_global_par_action.csv", sep=";", index=False)

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


def _build_temporal_indicators(
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    out_dir: Path,
    period_type: str,
    filename: str,
) -> None:
    """Construit de façon entièrement vectorisée les indicateurs temporels globaux."""
    def _get_period_series(df: pd.DataFrame, col: str) -> pd.Series:
        if df is None or df.empty or col not in df.columns:
            return pd.Series(dtype=object)
        dt = pd.to_datetime(df[col], errors="coerce")
        valid_mask = dt.notna()
        if not valid_mask.any():
            return pd.Series(index=df.index, dtype=object)
        
        res = pd.Series(index=df.index, dtype=object)
        sub_dt = dt[valid_mask]
        if period_type == "annuelle":
            res.loc[valid_mask] = sub_dt.dt.year.astype(str)
        elif period_type == "mensuelle":
            res.loc[valid_mask] = sub_dt.dt.strftime("%Y-%m")
        elif period_type == "trimestrielle":
            q = (sub_dt.dt.month - 1) // 3 + 1
            res.loc[valid_mask] = sub_dt.dt.year.astype(str) + "-T" + q.astype(str)
        elif period_type == "hebdomadaire":
            iso = sub_dt.dt.isocalendar()
            res.loc[valid_mask] = iso["year"].astype(str) + "-S" + iso["week"].astype(str).str.zfill(2)
        return res

    p_period = _get_period_series(point, "date_ctrl")
    pej_period = _get_period_series(pej, "DATE_REF")
    pve_period = _get_period_series(pve, "INF-DATE-INTG")

    periods = set()
    for s in (p_period, pej_period, pve_period):
        if not s.empty:
            periods |= set(s.dropna().unique())
    periods.discard("<NA>")
    periods.discard("nan")
    periods.discard("None")
    periods.discard("")

    if not periods:
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
        ).to_csv(out_dir / filename, sep=";", index=False)
        return

    loc_counts = p_period.value_counts() if not p_period.empty else pd.Series(dtype=int)
    pej_counts = pej_period.value_counts() if not pej_period.empty else pd.Series(dtype=int)
    pve_counts = pve_period.value_counts() if not pve_period.empty else pd.Series(dtype=int)

    ops_counts = {}
    if not point.empty and "fc_id" in point.columns and not p_period.empty:
        valid_pts = point[p_period.notna()]
        ops_counts = valid_pts.groupby(p_period[p_period.notna()])["fc_id"].nunique().to_dict()

    nc_counts = {}
    if not point.empty and "resultat" in point.columns and not p_period.empty:
        from core.common.utilitaires_metier import classify_resultat_controle_series
        is_nc = classify_resultat_controle_series(point["resultat"]).isin(["Infraction", "Manquement"])
        valid_nc = is_nc & p_period.notna()
        nc_counts = point[valid_nc].groupby(p_period[valid_nc]).size().to_dict()

    pa_counts = {}
    if not point.empty and "code_pa" in point.columns and not p_period.empty:
        from core.common.utilitaires_metier import is_filled_procedure_code
        is_pa = point["code_pa"].map(is_filled_procedure_code)
        valid_pa = is_pa & p_period.notna()
        pa_counts = point[valid_pa].groupby(p_period[valid_pa]).size().to_dict()

    rows = []
    for per in sorted(periods):
        nb_loc = int(loc_counts.get(per, 0))
        nb_ops = int(ops_counts.get(per, 0))
        nb_nc = int(nc_counts.get(per, 0))
        nb_pej_val = int(pej_counts.get(per, 0))
        nb_pa_val = int(pa_counts.get(per, 0))
        nb_pve_val = int(pve_counts.get(per, 0))

        rows.append(
            {
                "periode": per,
                "nb_localisations": nb_loc,
                "nb_operations_controle": nb_ops,
                "nb_localisations_non_conformes": nb_nc,
                "taux_non_conformite_localisations": (nb_nc / nb_loc) if nb_loc > 0 else pd.NA,
                "nb_pej": nb_pej_val,
                "nb_pa": nb_pa_val,
                "nb_pve": nb_pve_val,
            }
        )

    pd.DataFrame(rows).to_csv(out_dir / filename, sep=";", index=False)


def analyse_annuelle_global(
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Construit les indicateurs annuels globaux pour les periodes multi-annuelles."""
    _build_temporal_indicators(point, pa, pej, pve, out_dir, "annuelle", "indicateurs_global_par_annee.csv")


def analyse_trimestrielle_global(
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Construit les indicateurs trimestriels globaux."""
    _build_temporal_indicators(point, pa, pej, pve, out_dir, "trimestrielle", "indicateurs_global_par_trimestre.csv")


def analyse_mensuelle_global(
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Construit les indicateurs mensuels globaux (YYYY-MM)."""
    _build_temporal_indicators(point, pa, pej, pve, out_dir, "mensuelle", "indicateurs_global_par_mois.csv")


def analyse_hebdomadaire_global(
    point: pd.DataFrame,
    pa: pd.DataFrame,
    pej: pd.DataFrame,
    pve: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Indicateurs par semaine (libellé YYYY-Sww), aligné sur le moteur thématique."""
    _build_temporal_indicators(point, pa, pej, pve, out_dir, "hebdomadaire", "indicateurs_global_par_semaine.csv")


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
    gdf_faits: pd.DataFrame | None = None,
) -> None:
    """Adapter d'agrégations piloté par profil YAML."""
    analyse_controles_global(point, out_dir)
    analyse_pej_pa_global(root, point, pa, pej, out_dir, echelle=echelle, code=code, gdf_faits=gdf_faits)
    analyse_pve_global(pve, out_dir)
    if "categories_chasse" in profile and profile["categories_chasse"]:
        analyse_categories_chasse(point, pve, pej, profile["categories_chasse"], out_dir=out_dir)
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
        
    from core.engine.agregations_region import analyse_region_par_departement
    analyse_region_par_departement(
        point, pa, pej, pve, echelle, code, out_dir,
        pej_global=pej_global, profil_id=str(profile.get("id", "global"))
    )


def compute_n1_deltas(
    count_current: int,
    count_previous: int,
    *,
    seuil_alerte_baisse_pct: float = -30.0,
) -> dict[str, Any]:
    """Calcul de la variation N-1 et détection des anomalies de volume de données."""
    if count_previous <= 0:
        return {
            "count_current": count_current,
            "count_previous": count_previous,
            "delta_pct": None,
            "delta_str": "N/A",
            "alerte_baisse": False,
            "message_alerte": None,
        }
    delta_pct = round(((count_current - count_previous) / count_previous) * 100, 1)
    signe = "+" if delta_pct > 0 else ""
    delta_str = f"{signe}{delta_pct}%"
    alerte = delta_pct < seuil_alerte_baisse_pct
    msg = None
    if alerte:
        msg = f"Alerte statistique : Baisse de {abs(delta_pct)}% vs N-1 (vérifier la complétude de la source)."
    return {
        "count_current": count_current,
        "count_previous": count_previous,
        "delta_pct": delta_pct,
        "delta_str": delta_str,
        "alerte_baisse": alerte,
        "message_alerte": msg,
    }


def compute_categories_chasse_controles(
    point: pd.DataFrame,
    categories_cfg: dict[str, Any],
    out_dir: Path | None = None,
    figure_scale: float = 1.0,
) -> dict[str, Any]:
    """Ventile les points de contrôle terrain dans les catégories de chasse."""
    from core.common.utilitaires_metier import (
        classify_resultat_controle_series,
        series_str_contains,
    )
    import re

    rows: list[dict[str, Any]] = []
    donut_data: dict[str, int] = {}

    if point.empty or not categories_cfg:
        for cat_id, cfg in categories_cfg.items():
            lbl = cfg.get("label", cat_id)
            rows.append({
                "categorie": cat_id,
                "libelle": lbl,
                "total": 0,
                "conforme": 0,
                "non_conforme": 0,
                "taux_non_conforme": 0.0,
            })
            donut_data[lbl] = 0
        df_res = pd.DataFrame(rows)
        return {
            "df": df_res,
            "donut_data": donut_data,
            "donut_path": None,
        }

    pt = point.copy()
    pt["_cat"] = "autres"

    col_nom = "nom_dossie" if "nom_dossie" in pt.columns else ("nom_dossier" if "nom_dossier" in pt.columns else None)
    col_act = "type_actio" if "type_actio" in pt.columns else ("type_action" if "type_action" in pt.columns else None)

    for cat_id, cfg in categories_cfg.items():
        if cat_id == "autres":
            continue
        kws = cfg.get("keywords_controles", [])
        if not kws:
            continue
        pattern = "|".join(re.escape(k) for k in kws)
        mask = pd.Series(False, index=pt.index)
        if col_nom:
            mask |= series_str_contains(pt[col_nom], pattern, regex=True)
        if col_act:
            mask |= series_str_contains(pt[col_act], pattern, regex=True)
        pt.loc[mask & (pt["_cat"] == "autres"), "_cat"] = cat_id

    res_col = "resultat_c" if "resultat_c" in pt.columns else ("resultat_controle" if "resultat_controle" in pt.columns else None)
    for cat_id, cfg in categories_cfg.items():
        lbl = cfg.get("label", cat_id)
        sub = pt[pt["_cat"] == cat_id]
        total = len(sub)
        if total > 0 and res_col:
            classified = classify_resultat_controle_series(sub[res_col])
            conf = int((classified == "Conforme").sum())
            non_conf = int(((classified == "Infraction") | (classified == "Manquement")).sum())
        else:
            conf = 0
            non_conf = 0
        taux = round((non_conf / total) * 100, 1) if total > 0 else 0.0

        rows.append({
            "categorie": cat_id,
            "libelle": lbl,
            "total": total,
            "conforme": conf,
            "non_conforme": non_conf,
            "taux_non_conforme": taux,
        })
        donut_data[lbl] = total

    df_res = pd.DataFrame(rows)
    donut_path = None

    if out_dir is not None:
        csv_file = out_dir / "categories_chasse_controles.csv"
        df_res.to_csv(csv_file, sep=";", index=False, encoding="utf-8")
        if sum(donut_data.values()) > 0:
            from core.common.rendus_graphiques import chart_pie
            donut_path = Path(chart_pie(
                donut_data,
                "",
                out_dir,
                "categories_chasse_controles_donut.png",
                donut=True,
                figure_scale=figure_scale,
            ))

    return {
        "df": df_res,
        "donut_data": donut_data,
        "donut_path": donut_path,
    }


def compute_categories_chasse_infractions(
    pve: pd.DataFrame,
    pej: pd.DataFrame,
    categories_cfg: dict[str, Any],
    out_dir: Path | None = None,
    figure_scale: float = 1.0,
) -> dict[str, Any]:
    """Ventile les infractions PVe et PEJ dans les catégories de chasse."""
    import logging
    import re
    from core.common.utilitaires_metier import contient_natinf

    logger = logging.getLogger("ofbilan")
    rows: list[dict[str, Any]] = []
    donut_data: dict[str, int] = {}
    unlisted_set: set[str] = set()

    cat_codes_pve: dict[str, set[str]] = {}
    cat_codes_pej: dict[str, set[str]] = {}
    all_known: set[str] = set()

    for cat_id, cfg in categories_cfg.items():
        cpve = set(str(c).strip() for c in cfg.get("natinf_pve", []) if str(c).strip())
        cpej = set(str(c).strip() for c in cfg.get("natinf_pej", []) if str(c).strip())
        cat_codes_pve[cat_id] = cpve
        cat_codes_pej[cat_id] = cpej
        all_known |= cpve | cpej

    col_pve = "INF-NATINF" if "INF-NATINF" in pve.columns else ("NATINF" if "NATINF" in pve.columns else None)
    pve_cat_counts: dict[str, int] = {cat_id: 0 for cat_id in categories_cfg}

    if not pve.empty and col_pve:
        for val in pve[col_pve].dropna():
            s_val = str(val).strip()
            matched_cat = None
            for cat_id in categories_cfg:
                if cat_id == "autres":
                    continue
                if contient_natinf(s_val, list(cat_codes_pve[cat_id])):
                    matched_cat = cat_id
                    break
            if matched_cat is None:
                if contient_natinf(s_val, list(cat_codes_pve.get("autres", set()))):
                    matched_cat = "autres"
                else:
                    matched_cat = "autres" if "autres" in categories_cfg else list(categories_cfg.keys())[-1]
                    codes_found = re.findall(r"\b\d{3,5}\b", s_val)
                    for c in codes_found:
                        if c not in all_known:
                            unlisted_set.add(c)
            pve_cat_counts[matched_cat] = pve_cat_counts.get(matched_cat, 0) + 1

    col_pej = "NATINF_PEJ" if "NATINF_PEJ" in pej.columns else ("NATINF" if "NATINF" in pej.columns else None)
    pej_cat_counts: dict[str, int] = {cat_id: 0 for cat_id in categories_cfg}

    if not pej.empty and col_pej:
        for val in pej[col_pej].dropna():
            s_val = str(val).strip()
            matched_cat = None
            for cat_id in categories_cfg:
                if cat_id == "autres":
                    continue
                if contient_natinf(s_val, list(cat_codes_pej[cat_id])):
                    matched_cat = cat_id
                    break
            if matched_cat is None:
                if contient_natinf(s_val, list(cat_codes_pej.get("autres", set()))):
                    matched_cat = "autres"
                else:
                    matched_cat = "autres" if "autres" in categories_cfg else list(categories_cfg.keys())[-1]
                    codes_found = re.findall(r"\b\d{3,5}\b", s_val)
                    for c in codes_found:
                        if c not in all_known:
                            unlisted_set.add(c)
            pej_cat_counts[matched_cat] = pej_cat_counts.get(matched_cat, 0) + 1

    unlisted_list = sorted(list(unlisted_set))
    if unlisted_list:
        logger.warning(
            "Codes NATINF chasse non répertoriés dans les listes fermées (versés dans 'Autres infractions') : %s",
            ", ".join(unlisted_list),
        )
        print(f"\n[ALERTE OFBILAN] Codes NATINF chasse non répertoriés dans les listes fermées (classés dans 'Autres infractions') : {', '.join(unlisted_list)}")
        print("Vous pouvez mettre à jour la clé categories_chasse dans config/profils_bilan/chasse.yaml si nécessaire.\n")

    grand_total = sum(pve_cat_counts.values()) + sum(pej_cat_counts.values())

    for cat_id, cfg in categories_cfg.items():
        lbl = cfg.get("label", cat_id)
        nb_pve = pve_cat_counts.get(cat_id, 0)
        nb_pej = pej_cat_counts.get(cat_id, 0)
        tot = nb_pve + nb_pej
        pct = round((tot / grand_total) * 100, 1) if grand_total > 0 else 0.0

        rows.append({
            "categorie": cat_id,
            "libelle": lbl,
            "nb_pve": nb_pve,
            "nb_pej": nb_pej,
            "total": tot,
            "pct": pct,
        })
        donut_data[lbl] = tot

    df_res = pd.DataFrame(rows)
    donut_path = None

    if out_dir is not None:
        csv_file = out_dir / "categories_chasse_infractions.csv"
        df_res.to_csv(csv_file, sep=";", index=False, encoding="utf-8")
        if grand_total > 0:
            from core.common.rendus_graphiques import chart_pie
            donut_path = Path(chart_pie(
                donut_data,
                "",
                out_dir,
                "categories_chasse_infractions_donut.png",
                donut=True,
                figure_scale=figure_scale,
            ))

    return {
        "df": df_res,
        "donut_data": donut_data,
        "donut_path": donut_path,
        "unlisted_natinf": unlisted_list,
    }


def analyse_categories_chasse(
    point: pd.DataFrame,
    pve: pd.DataFrame,
    pej: pd.DataFrame,
    categories_cfg: dict[str, Any],
    out_dir: Path | None = None,
    figure_scale: float = 1.0,
) -> dict[str, Any]:
    """Exécute l'analyse conjointe des contrôles et des infractions pour les catégories chasse."""
    res_ctrl = compute_categories_chasse_controles(point, categories_cfg, out_dir=out_dir, figure_scale=figure_scale)
    res_inf = compute_categories_chasse_infractions(pve, pej, categories_cfg, out_dir=out_dir, figure_scale=figure_scale)
    return {
        "controles": res_ctrl,
        "infractions": res_inf,
    }