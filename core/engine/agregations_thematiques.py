# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
# Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
# intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
# clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
# doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
# de l'auteur original (Aguirre MAURIN).

"""Module d'agrégations et d'exports CSV pour le pipeline thématique."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from core.chemins_projet import PROJECT_ROOT, get_carto_temp_dir
from core.common.chargeurs_donnees import (
    get_communes_centroids_dicts,
    load_natinf_ref,
    load_pnf_commune_zone_maps,
    load_tub_pnf_codes,
)
from core.common.utilitaires_metier import (
    agg_controles_par_type_usager_domaine,
    agg_controles_par_type_usager_theme,
    agg_effectifs_usagers,
    agg_effectifs_usagers_par_domaine,
    agg_procedures_dossiers_par_domaine,
    agg_procedures_dossiers_par_theme,
    agg_resultat_counts_par_type_usager,
    agg_resultat_effectifs_par_type_usager,
    agg_resultats_par_type_usager_domaine,
    agg_resultats_par_type_usager_theme,
    build_tab_resultats,
    build_tab_resultats_controles,
    build_zone_pej_from_proc_detail_lecteur,
    coalesced_insee_series,
    count_controles_non_conformes_oscean,
    count_operations_controle,
    count_pa_induites_par_controles,
    extract_insee_code_series,
    filter_points_induisant_pa,
    points_as_pa_lignes,
    zone_lecteur_label,
)
from core.engine.agregations_profil import analyse_categories_chasse
from core.engine.filtres_profil import (
    _coalesced_insee_for_pnf_mask,
    _filter_by_type_usager,
    _get_insee_col,
)

_log = logging.getLogger(__name__)


def _sanitize_gdf_for_gpkg(gdf: Any) -> Any:
    """Assainit un GeoDataFrame pour l'export GeoPackage (dédoublonnage insensible à la casse et typage)."""
    if gdf is None or getattr(gdf, 'empty', True):
        return gdf
    seen_lower = set()
    cols_to_keep = []
    geom_col = gdf.geometry.name if hasattr(gdf, 'geometry') else 'geometry'
    for col in gdf.columns:
        c_low = str(col).lower()
        if col == geom_col or c_low == "fid":
            continue
        if c_low not in seen_lower:
            seen_lower.add(c_low)
            cols_to_keep.append(col)
    cols_to_keep.append(geom_col)
    cleaned = gdf[cols_to_keep].copy()
    for col in cleaned.select_dtypes(include=['datetime64[ns, UTC]', 'datetime64[ns]', 'datetime64']).columns:
        cleaned[col] = cleaned[col].astype(str)
    return cleaned

def _run_aggregations(
    point_filtered: pd.DataFrame,
    pej_filtered: pd.DataFrame,
    pa_filtered: pd.DataFrame,
    pve_filtered: pd.DataFrame,
    profile: dict,
    options: dict,
    spatial: dict,
    ventilation_mode: str = "globale",
    point_ctrl_perimetre: pd.DataFrame | None = None,
) -> dict:
    """Calcule toutes les agrégations et retourne un dict de DataFrames."""
    results: dict[str, Any] = {}
    profil_id = profile["id"]
    analyses_cfg = profile.get("analyses") or {}
    if "distinction_coeur_hors_coeur" in analyses_cfg:
        distinction_coeur_hors_coeur = bool(analyses_cfg["distinction_coeur_hors_coeur"])
    else:
        distinction_coeur_hors_coeur = bool(options.get("pnf", False))
    zone_lecteur_4_zones = bool(analyses_cfg.get("zone_lecteur_4_zones", False))
    results["_pdf_show_coeur_hors_coeur"] = distinction_coeur_hors_coeur or zone_lecteur_4_zones
    results["_zone_lecteur_4_zones"] = zone_lecteur_4_zones
    tub_codes_lecteur = spatial.get("tub_codes") if isinstance(spatial.get("tub_codes"), set) else set()

    nb_localisations = len(point_filtered)
    nb_operations_controle = count_operations_controle(point_filtered)
    nb_pej = len(pej_filtered)
    nb_pa = count_pa_induites_par_controles(point_filtered)
    nb_pve = len(pve_filtered)
    results["nb_localisations"] = nb_localisations
    results["nb_operations_controle"] = nb_operations_controle
    results["nb_pej"] = nb_pej
    results["nb_pa"] = nb_pa
    results["nb_pve"] = nb_pve
    
    # Store raw dataframes for custom PDF sections
    results["_raw_point_filtered"] = point_filtered
    results["_raw_pej_filtered"] = pej_filtered

    # Résultats des contrôles
    if not point_filtered.empty and "resultat" in point_filtered.columns:
        tab = build_tab_resultats(point_filtered)
        results["tab_resultats"] = tab
        # Référence de cohérence : maximum observé entre totaux de contrôles
        # calculés dans les sections structurantes des contrôles.
        total_from_resultats = int(tab["nb"].sum()) if "nb" in tab.columns else 0
        total_controles_reference = max(int(nb_localisations), total_from_resultats)
        results["total_controles_reference"] = total_controles_reference

        results["tab_resultats_controles"] = build_tab_resultats_controles(
            point_filtered,
            distinction_coeur_hors_coeur=distinction_coeur_hors_coeur,
            zone_lecteur_4_zones=zone_lecteur_4_zones,
            tub_codes=tub_codes_lecteur,
        )
    else:
        results["total_controles_reference"] = int(nb_localisations)

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
        agg["taux"] = agg["nb"] / float(nb_localisations or 1)
        results["agg_theme"] = agg

    # Par commune
    insee_col = _get_insee_col(point_filtered)
    if options.get("par_commune", True) and not point_filtered.empty and insee_col:
        agg_c = (
            point_filtered.groupby(insee_col)
            .agg(
                nb_localisations=("dc_id", "count"),
                nb_non_conformes=(
                    "resultat",
                    lambda s: count_controles_non_conformes_oscean(s),
                ),
            )
            .reset_index()
        )
        agg_c["taux_non_conformite"] = agg_c["nb_non_conformes"] / agg_c[
            "nb_localisations"
        ].replace(0, pd.NA)
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

    # PA par thème/domaine (dérivées des contrôles à manquement)
    pa_lignes = points_as_pa_lignes(point_filtered)
    if not pa_lignes.empty:
        grp_cols = [c for c in ["DOMAINE", "THEME"] if c in pa_lignes.columns]
        if grp_cols:
            agg_pa = (
                pa_lignes.groupby(grp_cols)
                .size()
                .rename("nb_pa")
                .reset_index()
            )
            results["pa_par_theme"] = agg_pa

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

        with_type_proc = bool(
            not (targets and len(targets) == 1)
            and (
                (not pej_filtered.empty and "type_usager" in pej_filtered.columns)
                or (not point_filtered.empty and "type_usager" in point_filtered.columns)
            )
        )
        proc_ud = agg_procedures_dossiers_par_domaine(
            pej_filtered,
            pa_lignes,
            with_type_usager=with_type_proc,
            source_table="point_ctrl",
            source_champ="type_usager",
        )
        if targets and with_type_proc and not proc_ud.empty:
            proc_ud = proc_ud[proc_ud["type_usager"].isin(targets)]
        results["proc_par_usager_domaine"] = proc_ud

        proc_ut = agg_procedures_dossiers_par_theme(
            pej_filtered,
            pa_lignes,
            with_type_usager=with_type_proc,
            source_table="point_ctrl",
            source_champ="type_usager",
        )
        if targets and with_type_proc and not proc_ut.empty:
            proc_ut = proc_ut[proc_ut["type_usager"].isin(targets)]
        results["proc_par_usager_theme"] = proc_ut

        metrique_res = (
            options.get("metrique_resultats_usagers")
            or profile.get("metrique_resultats_usagers")
            or (profile.get("analyses") or {}).get("metrique_resultats_usagers")
            or "effectifs"
        )
        if str(metrique_res).strip().lower() == "controles":
            results["res_bilan_par_type_usager"] = agg_resultat_counts_par_type_usager(
                pt_us
            )
        else:
            results["res_bilan_par_type_usager"] = agg_resultat_effectifs_par_type_usager(
                pt_us
            )

        # Section PDF dédiée : pas de doublon avec le profil « types d'usagers » (sommaire séparé).
        results["_pdf_show_activite_usagers"] = bool(
            not type_usager_profile
            and not results["ctrl_par_usager_theme"].empty
        )
    else:
        results["_pdf_show_activite_usagers"] = False

    # Pression de contrôle (profil usager ciblé) : tous types, hors filtre cible.
    results["_pdf_show_pression_controle_usagers"] = False
    if profil_id == "types_usager_cible" and point_ctrl_perimetre is not None:
        if (
            not point_ctrl_perimetre.empty
            and "type_usager" in point_ctrl_perimetre.columns
        ):
            pc = agg_effectifs_usagers(point_ctrl_perimetre)
            if not pc.empty:
                total_pc = int(pc["nb"].sum())
                pc = pc.copy()
                pc["taux"] = pc["nb"] / float(total_pc or 1)
                results["pression_controle_tous_usagers"] = pc
                results["_pdf_show_pression_controle_usagers"] = True

    # Synthèse croisée par zone
    if options.get("synthese_croisee", False):
        zone_ctrl = spatial.get("zone_ctrl")
        zone_pve = spatial.get("zone_pve")
        zone_pej = spatial.get("zone_pej")
        if zone_ctrl is not None:
            synth = zone_ctrl[["zone", "nb_total", "nb_non_conforme"]].rename(
                columns={"nb_total": "ctrl_total", "nb_non_conforme": "ctrl_infraction"}
            )
            if zone_pve is not None:
                synth = synth.merge(zone_pve.rename(columns={"nb": "pve_nb"}), on="zone", how="left")
            if zone_pej is not None:
                synth = synth.merge(zone_pej.rename(columns={"nb": "pej_nb"}), on="zone", how="left")
            synth = synth.fillna(0)
            results["synthese_zone"] = synth

    # Copier les résultats spatiaux dans le dict principal
    for k in ("agg_pnf", "agg_pnf_detail", "zone_ctrl", "zone_pve", "zone_pej", "tub_codes", "pnf_codes"):
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
                natinf_ref = load_natinf_ref(PROJECT_ROOT)
                ana = top_pve.copy()
                ana["numero_natinf"] = ana["natinf"].astype(str).str.extract(r"(\d+)", expand=False)
                if not natinf_ref.empty:
                    ana = ana.merge(natinf_ref, on="numero_natinf", how="left")
                th_col = "INF-TYP-INF-STAT-LIB" if "INF-TYP-INF-STAT-LIB" in pve_filtered.columns else None
                if th_col:
                    m_theme = (
                        pve_filtered.assign(_n=pve_filtered[natinf_col].astype(str).str.strip())
                        .groupby("_n")[th_col]
                        .agg(lambda s: s.dropna().astype(str).mode().iloc[0] if not s.dropna().empty else "")
                        .to_dict()
                    )
                    ana["thematique"] = ana["natinf"].astype(str).map(m_theme).fillna("")
                else:
                    ana["thematique"] = ""
                ana["nature_infraction"] = ana.get("nature_infraction", "")
                ana["libelle_natinf"] = ana.get("libelle_natinf", ana["natinf"])
                results["pve_natinf_analysis"] = ana[["thematique", "libelle_natinf", "nature_infraction", "nb"]]

    # PEJ : infractions (par NATINF) pour le tableau PDF.
    # Si le volume PEJ est faible (< 10), on conserve toute la liste.
    # Sinon, on limite au top 10 pour garder un tableau lisible.
    if not pej_filtered.empty:
        natinf_col = "NATINF_PEJ" if "NATINF_PEJ" in pej_filtered.columns else "NATINF"
        if natinf_col in pej_filtered.columns:
            pej_counts = (
                pej_filtered[natinf_col]
                .astype(str)
                .str.strip()
                .replace("", pd.NA)
                .dropna()
                .value_counts()
                .rename_axis("natinf")
                .reset_index(name="nb")
            )
            if not pej_counts.empty:
                if len(pej_filtered) < 10 or profil_id == "ppp":
                    results["pej_top_infractions"] = pej_counts
                else:
                    results["pej_top_infractions"] = pej_counts.head(10)
                natinf_ref = load_natinf_ref(PROJECT_ROOT)
                ana = pej_counts.copy()
                ana["numero_natinf"] = ana["natinf"].astype(str).str.extract(r"(\d+)", expand=False)
                if not natinf_ref.empty:
                    ana = ana.merge(natinf_ref, on="numero_natinf", how="left")
                th_col_pej = "theme" if "theme" in pej_filtered.columns else ("THEME" if "THEME" in pej_filtered.columns else None)
                if th_col_pej:
                    m_theme_pej = (
                        pej_filtered.assign(_n=pej_filtered[natinf_col].astype(str).str.strip())
                        .groupby("_n")[th_col_pej]
                        .agg(lambda s: s.dropna().astype(str).mode().iloc[0] if not s.dropna().empty else "")
                        .to_dict()
                    )
                    ana["thematique"] = ana["natinf"].astype(str).map(m_theme_pej).fillna("")
                else:
                    ana["thematique"] = ""
                ana["nature_infraction"] = ana.get("nature_infraction", "")
                ana["libelle_natinf"] = ana.get("libelle_natinf", ana["natinf"])
                results["pej_natinf_analysis"] = ana[["thematique", "libelle_natinf", "nature_infraction", "nb"]]

    # Détails procédures (format unifié PVe/PEJ/PA) + colonne zone (ex-PNF)
    def _coeur_hors_coeur_from_zone(v: Any) -> str:
        if v is None or pd.isna(v):
            return "n.d."
        s = str(v).strip()
        if not s or s.lower() in {"nan", "none", "<na>"}:
            return "n.d."
        if s == "Coeur_PNF":
            return "Cœur"
        if s == "Aire_adhesion_PNF":
            return "Aire d'adhésion"
        if s == "Hors_perimetres_sig":
            return "Hors PNF"
        return "n.d."

    tub_codes_proc = results.get("tub_codes") if isinstance(results.get("tub_codes"), set) else tub_codes_lecteur

    def _resolve_proc_zone_sig_series(
        d: pd.DataFrame,
        out_commune: pd.Series,
        proc_type: str,
        com_col: str | None,
    ) -> pd.Series:
        sig = pd.Series(pd.NA, index=d.index, dtype="string")
        if "pnf_zone_sig" in d.columns:
            sig = d["pnf_zone_sig"].astype("string")
        if proc_type == "PVe" and com_col == "INF-INSEE" and pnf_zone_by_insee:
            from_insee = (
                d[com_col]
                .astype(str)
                .str.strip()
                .str.extract(r"(\d{1,5})", expand=False)
                .fillna("")
                .str.zfill(5)
                .map(pnf_zone_by_insee)
            )
            sig = sig.fillna(from_insee.astype("string"))
        elif "DC_ID" in d.columns and pnf_by_dc:
            sig = sig.fillna(
                d["DC_ID"].astype(str).str.strip().map(pnf_by_dc).astype("string")
            )
        if proc_type in ("PEJ", "PA"):
            if pnf_zone_by_commune_nom:
                zc = (
                    out_commune.astype(str)
                    .str.strip()
                    .str.lower()
                    .replace({"": pd.NA, "nan": pd.NA, "none": pd.NA, "<na>": pd.NA})
                )
                sig = sig.fillna(zc.map(pnf_zone_by_commune_nom).astype("string"))
            insee_s = _coalesced_insee_for_pnf_mask(d)
            if pnf_zone_by_insee and insee_s.notna().any():
                sig = sig.fillna(insee_s.map(pnf_zone_by_insee).astype("string"))
        return sig

    def _apply_zone_lecteur_column(
        d: pd.DataFrame,
        out: pd.DataFrame,
        proc_type: str,
        com_col: str | None,
    ) -> None:
        sig = _resolve_proc_zone_sig_series(d, out["commune"], proc_type, com_col)
        insee_s = _coalesced_insee_for_pnf_mask(d)
        out["coeur_hors_coeur"] = [
            zone_lecteur_label(sig.iat[i], insee_s.iat[i], tub_codes_proc)
            for i in range(len(d))
        ]

    pnf_by_dc: dict[str, str] = {}
    nom_commune_by_dc: dict[str, str] = {}
    dc_col_points = "DC_ID" if "DC_ID" in point_filtered.columns else ("dc_id" if "dc_id" in point_filtered.columns else None)
    if not point_filtered.empty and dc_col_points is not None:
        point_cols = [dc_col_points]
        if "pnf_zone_sig" in point_filtered.columns:
            point_cols.append("pnf_zone_sig")
        for c in ("nom_commune", "nom_commun", "NOM_COM"):
            if c in point_filtered.columns:
                point_cols.append(c)
        tmp_p = point_filtered[point_cols].dropna(subset=[dc_col_points]).copy()
        if not tmp_p.empty:
            tmp_p["DC_ID"] = tmp_p[dc_col_points].astype(str).str.strip()
            commune = pd.Series(pd.NA, index=tmp_p.index, dtype="string")
            for c in ("nom_commune", "nom_commun", "NOM_COM"):
                if c in tmp_p.columns:
                    cand = (
                        tmp_p[c]
                        .astype("string")
                        .str.strip()
                        .replace("", pd.NA)
                    )
                    commune = commune.fillna(cand)
            if commune.notna().any():
                tmp_n = tmp_p[["DC_ID"]].copy()
                tmp_n["commune"] = commune
                nom_commune_by_dc = (
                    tmp_n.dropna(subset=["commune"])
                    .drop_duplicates("DC_ID")
                    .set_index("DC_ID")["commune"]
                    .astype(str)
                    .to_dict()
                )
            if "pnf_zone_sig" in tmp_p.columns:
                tmp_p["_prio"] = (tmp_p["pnf_zone_sig"] == "Coeur_PNF").astype(int)
                tmp_p = tmp_p.sort_values(["DC_ID", "_prio"], ascending=[True, False])
                pnf_by_dc = (
                    tmp_p.drop_duplicates("DC_ID")
                    .set_index("DC_ID")["pnf_zone_sig"]
                    .astype(str)
                    .to_dict()
                )
    pnf_zone_by_insee, pnf_zone_by_commune_nom = load_pnf_commune_zone_maps(PROJECT_ROOT)

    def _build_proc_detail(
        df: pd.DataFrame,
        proc_type: str,
        num_candidates: list[str],
        date_candidates: list[str],
        commune_candidates: list[str],
        theme_candidates: list[str],
    ) -> pd.DataFrame:
        if df is None or df.empty:
            cols = (
                ["numero", "date", "commune", "thematique", "coeur_hors_coeur", "type_procedure"]
                if distinction_coeur_hors_coeur or zone_lecteur_4_zones
                else ["numero", "date", "commune", "thematique", "type_procedure"]
            )
            return pd.DataFrame(columns=cols)
        d = df.copy()
        num_col = next((c for c in num_candidates if c in d.columns), None)
        dt_col = next((c for c in date_candidates if c in d.columns), None)
        com_col = next((c for c in commune_candidates if c in d.columns), None)
        th_col = next((c for c in theme_candidates if c in d.columns), None)
        out = pd.DataFrame(
            {
                "numero": d[num_col].astype(str) if num_col else "",
                "date": d[dt_col].astype(str) if dt_col else "",
                "commune": d[com_col].astype(str) if com_col else "",
                "thematique": d[th_col].astype(str) if th_col else "",
            }
        )
        out["commune"] = out["commune"].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
        if "NOM_COM_FAITS" in d.columns:
            out["commune"] = out["commune"].fillna(
                d["NOM_COM_FAITS"].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
            )
        if "nom_commune" in d.columns:
            out["commune"] = out["commune"].fillna(
                d["nom_commune"].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
            )
        if "DC_ID" in d.columns and nom_commune_by_dc:
            out["commune"] = out["commune"].fillna(
                d["DC_ID"].astype(str).str.strip().map(nom_commune_by_dc)
            )
        if zone_lecteur_4_zones:
            _apply_zone_lecteur_column(d, out, proc_type, com_col)
        elif distinction_coeur_hors_coeur:
            if "pnf_zone_sig" in d.columns:
                out["coeur_hors_coeur"] = d["pnf_zone_sig"].apply(_coeur_hors_coeur_from_zone)
            elif "DC_ID" in d.columns and pnf_by_dc:
                out["coeur_hors_coeur"] = (
                    d["DC_ID"].astype(str).str.strip().map(pnf_by_dc).apply(_coeur_hors_coeur_from_zone)
                )
            else:
                out["coeur_hors_coeur"] = "n.d."

            if proc_type == "PVe" and com_col == "INF-INSEE" and pnf_zone_by_insee:
                from_insee = (
                    d[com_col]
                    .astype(str)
                    .str.strip()
                    .str.extract(r"(\d{1,5})", expand=False)
                    .fillna("")
                    .str.zfill(5)
                    .map(pnf_zone_by_insee)
                    .apply(_coeur_hors_coeur_from_zone)
                )
                out["coeur_hors_coeur"] = out["coeur_hors_coeur"].where(
                    ~out["coeur_hors_coeur"].isin(["n.d.", "Hors PNF"]),
                    from_insee
                )
            # PEJ / PA : la commune affichée peut venir de NOM_COM_FAITS ou des points (DC_ID) alors que
            # NOM_COM reste vide — aligner la zone sur `out["commune"]`, pas sur la seule
            # colonne candidate d'origine.
            if proc_type in ("PEJ", "PA"):
                if pnf_zone_by_commune_nom:
                    zc = (
                        out["commune"]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        .replace({"": pd.NA, "nan": pd.NA, "none": pd.NA, "<na>": pd.NA})
                    )
                    from_nom = zc.map(pnf_zone_by_commune_nom).apply(_coeur_hors_coeur_from_zone)
                    out["coeur_hors_coeur"] = out["coeur_hors_coeur"].where(
                        ~out["coeur_hors_coeur"].isin(["n.d.", "Hors PNF"]),
                        from_nom
                    )
                if pnf_zone_by_insee:
                    insee_s = pd.Series(pd.NA, index=d.index, dtype="string")
                    for col in ("insee_comm", "INSEE_COM", "INF-INSEE"):
                        if col not in d.columns:
                            continue
                        insee_s = insee_s.fillna(extract_insee_code_series(d[col]))
                    if insee_s.notna().any():
                        from_insee = (
                            insee_s.map(pnf_zone_by_insee).apply(_coeur_hors_coeur_from_zone)
                        )
                        out["coeur_hors_coeur"] = out["coeur_hors_coeur"].where(
                            ~out["coeur_hors_coeur"].isin(["n.d.", "Hors PNF"]),
                            from_insee
                        )
            if proc_type in ("PEJ", "PA"):
                pnf_codes_s = results.get("pnf_codes")
                if not isinstance(pnf_codes_s, set):
                    _, pnf_codes_s = load_tub_pnf_codes(PROJECT_ROOT)
                pnf_codes_s = pnf_codes_s or set()
                ch = out["coeur_hors_coeur"].astype(str).str.strip()
                mask_nd = ch.isin(["", "n.d.", "nan", "None", "<na>"])
                insee_detail = pd.Series(pd.NA, index=d.index, dtype="string")
                for col in ("insee_comm", "INSEE_COM", "INF-INSEE"):
                    if col not in d.columns:
                        continue
                    insee_detail = insee_detail.fillna(extract_insee_code_series(d[col]))
                if mask_nd.any() and insee_detail.notna().any():
                    hors_pnf = insee_detail.notna() & ~insee_detail.astype(str).isin(
                        {str(x).zfill(5) for x in pnf_codes_s}
                    )
                    idx = mask_nd & hors_pnf
                    out.loc[idx, "coeur_hors_coeur"] = "Hors PNF"
        commune_missing = out["commune"].isna() | out["commune"].astype(str).str.strip().isin(
            ["", "nan", "None", "<na>"]
        )
        out.loc[commune_missing, "commune"] = "n.d."
        if "coeur_hors_coeur" in out.columns:
            insee_ok = _coalesced_insee_for_pnf_mask(d).notna()
            has_sig_coeur_aire = pd.Series(False, index=d.index)
            if "pnf_zone_sig" in d.columns:
                has_sig_coeur_aire = d["pnf_zone_sig"].astype(str).str.strip().isin(
                    ("Coeur_PNF", "Aire_adhesion_PNF")
                )
            no_geo = commune_missing & ~insee_ok & ~has_sig_coeur_aire
            out.loc[no_geo, "coeur_hors_coeur"] = "n.d."
        out["type_procedure"] = proc_type
        return out.fillna("")

    results["pve_detail"] = _build_proc_detail(
        pve_filtered,
        "PVe",
        ["INF-ID", "id", "numero"],
        ["INF-DATE-MIF", "date", "DATE_REF"],
        ["INF-INSEE", "nom_commun", "nom_comm", "commune", "INSEE_NOM"],
        ["INF-TYP-INF-STAT-LIB", "theme", "THEME", "type_actio", "type_action"],
    )
    results["pej_detail"] = _build_proc_detail(
        pej_filtered,
        "PEJ",
        ["DC_ID", "NUM_DOSSIER", "dossier", "numero"],
        ["DATE_REF", "date_ref", "date"],
        ["NOM_COM", "nom_commun", "commune", "INSEE_NOM"],
        ["THEME", "theme", "DOMAINE", "domaine"],
    )
    results["pa_detail"] = _build_proc_detail(
        filter_points_induisant_pa(point_filtered),
        "PA",
        ["dc_id", "DC_ID", "fid"],
        ["date_ctrl", "DATE_REF"],
        ["nom_commun", "nom_comm", "commune", "NOM_COM"],
        ["theme", "THEME", "domaine", "DOMAINE"],
    )

    # PEJ par zone : dérivé du détail (cohérent avec la colonne Zone du tableau détail).
    pej_det = results.get("pej_detail")
    if (
        zone_lecteur_4_zones
        and isinstance(pej_det, pd.DataFrame)
        and not pej_det.empty
        and "coeur_hors_coeur" in pej_det.columns
    ):
        results["zone_pej"] = build_zone_pej_from_proc_detail_lecteur(pej_det)
    elif str(profil_id or "").strip().lower() == "pnf":
        if isinstance(pej_det, pd.DataFrame) and not pej_det.empty and "coeur_hors_coeur" in pej_det.columns:
            ch = pej_det["coeur_hors_coeur"].astype(str).str.strip()
            nb_coeur = int((ch == "Cœur").sum())
            nb_hors = int((ch == "Aire d'adhésion").sum()) + int((ch == "Hors PNF").sum())
            nb_attente = int(ch.isin(["n.d.", "nan", "None", "", "<na>"]).sum())
            rows_pnf = [
                {"zone": "Cœur", "nb": nb_coeur},
                {"zone": "Aire d'adhésion", "nb": nb_hors},
            ]
            if nb_attente > 0:
                rows_pnf.append({"zone": ZONE_PEJ_LOCALISATION_ATTENTE, "nb": nb_attente})
            results["zone_pej"] = pd.DataFrame(rows_pnf)

    # Agrégation annuelle, trimestrielle ou mensuelle (selon la durée de la période)
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
        if not pa_lignes.empty and "DATE_REF" in pa_lignes.columns:
            years |= set(
                pa_lignes["DATE_REF"].dropna().dt.year.astype(int).tolist()
            )
        elif not point_filtered.empty and "date_ctrl" in point_filtered.columns:
            pa_pts = filter_points_induisant_pa(point_filtered)
            if not pa_pts.empty:
                years |= set(
                    pa_pts["date_ctrl"].dropna().dt.year.astype(int).tolist()
                )
        if not pve_filtered.empty and "INF-DATE-MIF" in pve_filtered.columns:
            years |= set(
                pve_filtered["INF-DATE-MIF"].dropna().dt.year.astype(int).tolist()
            )

        rows: list[dict[str, Any]] = []
        for year in sorted(years):
            year_row: dict[str, Any] = {"periode": str(year)}

            if not point_filtered.empty and "date_ctrl" in point_filtered.columns:
                p_year = point_filtered[point_filtered["date_ctrl"].dt.year == year]
                year_row["nb_localisations"] = int(len(p_year))
                year_row["nb_operations_controle"] = count_operations_controle(p_year)
                if "resultat" in p_year.columns:
                    year_row["nb_localisations_non_conformes"] = (
                        count_controles_non_conformes_oscean(p_year["resultat"])
                    )
                else:
                    year_row["nb_localisations_non_conformes"] = 0
            else:
                year_row["nb_localisations"] = 0
                year_row["nb_operations_controle"] = 0
                year_row["nb_localisations_non_conformes"] = 0

            if not pej_filtered.empty and "DATE_REF" in pej_filtered.columns:
                dt = pej_filtered["DATE_REF"]
                year_row["nb_pej"] = int((dt.dt.year == year).sum())
            else:
                year_row["nb_pej"] = 0

            if not pa_lignes.empty and "DATE_REF" in pa_lignes.columns:
                dt = pa_lignes["DATE_REF"]
                year_row["nb_pa"] = int((dt.dt.year == year).sum())
            else:
                year_row["nb_pa"] = 0

            if not pve_filtered.empty and "INF-DATE-MIF" in pve_filtered.columns:
                year_row["nb_pve"] = int(
                    (pve_filtered["INF-DATE-MIF"].dt.year == year).sum()
                )
            else:
                year_row["nb_pve"] = 0

            rows.append(year_row)

        if rows:
            yearly = pd.DataFrame(rows)
            yearly["taux_non_conformite_controles"] = yearly.apply(
                lambda r: (
                    (r["nb_localisations_non_conformes"] / r["nb_localisations"])
                    if r["nb_localisations"] > 0
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
        pa_pts = filter_points_induisant_pa(point_filtered)
        if not pa_pts.empty and "date_ctrl" in pa_pts.columns:
            for _, r in pa_pts["date_ctrl"].dropna().items():
                t = r
                if hasattr(t, "year") and hasattr(t, "month"):
                    q = (t.month - 1) // 3 + 1
                    periods.add((int(t.year), q))
        if not pve_filtered.empty and "INF-DATE-MIF" in pve_filtered.columns:
            for _, r in pve_filtered["INF-DATE-MIF"].dropna().items():
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
                row_t["nb_localisations"] = int(mask.sum())
                row_t["nb_operations_controle"] = count_operations_controle(point_filtered, mask=mask)
                if "resultat" in point_filtered.columns:
                    rnc = (
                        point_filtered["resultat"]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        .isin(("infraction", "manquement"))
                    )
                    row_t["nb_localisations_non_conformes"] = int((mask & rnc).sum())
                else:
                    row_t["nb_localisations_non_conformes"] = 0
            else:
                row_t["nb_localisations"] = 0
                row_t["nb_operations_controle"] = 0
                row_t["nb_localisations_non_conformes"] = 0

            if not pej_filtered.empty and "DATE_REF" in pej_filtered.columns:
                dt = pej_filtered["DATE_REF"]
                mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
                row_t["nb_pej"] = int(mask.sum())
            else:
                row_t["nb_pej"] = 0

            if not pa_lignes.empty and "DATE_REF" in pa_lignes.columns:
                dt = pa_lignes["DATE_REF"]
                mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
                row_t["nb_pa"] = int(mask.sum())
            else:
                row_t["nb_pa"] = 0

            if not pve_filtered.empty and "INF-DATE-MIF" in pve_filtered.columns:
                dt = pve_filtered["INF-DATE-MIF"]
                mask = (dt.dt.year == year) & (dt.dt.month >= m1) & (dt.dt.month <= m2)
                row_t["nb_pve"] = int(mask.sum())
            else:
                row_t["nb_pve"] = 0

            rows_trim.append(row_t)

        if rows_trim:
            trimestriel = pd.DataFrame(rows_trim)
            trimestriel["taux_non_conformite_controles"] = trimestriel.apply(
                lambda r: (
                    (r["nb_localisations_non_conformes"] / r["nb_localisations"])
                    if r["nb_localisations"] > 0
                    else pd.NA
                ),
                axis=1,
            )
            results["agg_annuelle"] = trimestriel
            results["ventilation_temporelle_type"] = "trimestrielle"

    elif ventilation_mode == "hebdomadaire":
        periods_w: set[tuple[int, int]] = set()

        def _add_iso_weeks(df: pd.DataFrame, col: str) -> None:
            if df is None or df.empty or col not in df.columns:
                return
            dt = pd.to_datetime(df[col], errors="coerce").dropna()
            if dt.empty:
                return
            iso = dt.dt.isocalendar()
            for y, w in zip(iso["year"].tolist(), iso["week"].tolist()):
                periods_w.add((int(y), int(w)))

        _add_iso_weeks(point_filtered, "date_ctrl")
        _add_iso_weeks(pej_filtered, "DATE_REF")
        _add_iso_weeks(filter_points_induisant_pa(point_filtered), "date_ctrl")
        _add_iso_weeks(pve_filtered, "INF-DATE-MIF")

        rows_week: list[dict[str, Any]] = []
        for (year, week) in sorted(periods_w):
            row_w: dict[str, Any] = {"periode": f"{year}-S{week:02d}"}
            if not point_filtered.empty and "date_ctrl" in point_filtered.columns:
                dt = point_filtered["date_ctrl"]
                iso = dt.dt.isocalendar()
                mask = (iso["year"] == year) & (iso["week"] == week)
                row_w["nb_localisations"] = int(mask.sum())
                row_w["nb_operations_controle"] = count_operations_controle(point_filtered, mask=mask)
                if "resultat" in point_filtered.columns:
                    row_w["nb_localisations_non_conformes"] = count_controles_non_conformes_oscean(
                        point_filtered.loc[mask, "resultat"]
                    )
                else:
                    row_w["nb_localisations_non_conformes"] = 0
            else:
                row_w["nb_localisations"] = 0
                row_w["nb_operations_controle"] = 0
                row_w["nb_localisations_non_conformes"] = 0

            if not pej_filtered.empty and "DATE_REF" in pej_filtered.columns:
                dt = pej_filtered["DATE_REF"]
                iso = dt.dt.isocalendar()
                mask = (iso["year"] == year) & (iso["week"] == week)
                row_w["nb_pej"] = int(mask.sum())
            else:
                row_w["nb_pej"] = 0

            if not pa_lignes.empty and "DATE_REF" in pa_lignes.columns:
                dt = pa_lignes["DATE_REF"]
                iso = dt.dt.isocalendar()
                mask = (iso["year"] == year) & (iso["week"] == week)
                row_w["nb_pa"] = int(mask.sum())
            else:
                row_w["nb_pa"] = 0
            if not pve_filtered.empty and "INF-DATE-MIF" in pve_filtered.columns:
                dt = pve_filtered["INF-DATE-MIF"]
                iso = dt.dt.isocalendar()
                row_w["nb_pve"] = int(((iso["year"] == year) & (iso["week"] == week)).sum())
            else:
                row_w["nb_pve"] = 0
            rows_week.append(row_w)

        if rows_week:
            hebdo = pd.DataFrame(rows_week)
            hebdo["taux_non_conformite_controles"] = hebdo.apply(
                lambda r: (
                    (r["nb_localisations_non_conformes"] / r["nb_localisations"])
                    if r["nb_localisations"] > 0
                    else pd.NA
                ),
                axis=1,
            )
            results["agg_annuelle"] = hebdo
            results["ventilation_temporelle_type"] = "hebdomadaire"

    elif ventilation_mode == "mensuelle":
        periods_m: set[tuple[int, int]] = set()
        if not point_filtered.empty and "date_ctrl" in point_filtered.columns:
            for _, r in point_filtered["date_ctrl"].dropna().items():
                t = r
                if hasattr(t, "year") and hasattr(t, "month"):
                    periods_m.add((int(t.year), int(t.month)))
        if not pej_filtered.empty and "DATE_REF" in pej_filtered.columns:
            for _, r in pej_filtered["DATE_REF"].dropna().items():
                t = r
                if hasattr(t, "year") and hasattr(t, "month"):
                    periods_m.add((int(t.year), int(t.month)))
        pa_pts_m = filter_points_induisant_pa(point_filtered)
        if not pa_pts_m.empty and "date_ctrl" in pa_pts_m.columns:
            for _, r in pa_pts_m["date_ctrl"].dropna().items():
                t = r
                if hasattr(t, "year") and hasattr(t, "month"):
                    periods_m.add((int(t.year), int(t.month)))
        if not pve_filtered.empty and "INF-DATE-MIF" in pve_filtered.columns:
            for _, r in pve_filtered["INF-DATE-MIF"].dropna().items():
                t = r
                if hasattr(t, "year") and hasattr(t, "month"):
                    periods_m.add((int(t.year), int(t.month)))

        rows_month: list[dict[str, Any]] = []
        for (year, month) in sorted(periods_m):
            row_m: dict[str, Any] = {"periode": f"{year}-{month:02d}"}
            if not point_filtered.empty and "date_ctrl" in point_filtered.columns:
                dt = point_filtered["date_ctrl"]
                mask = (dt.dt.year == year) & (dt.dt.month == month)
                row_m["nb_localisations"] = int(mask.sum())
                row_m["nb_operations_controle"] = count_operations_controle(point_filtered, mask=mask)
                if "resultat" in point_filtered.columns:
                    row_m["nb_localisations_non_conformes"] = count_controles_non_conformes_oscean(
                        point_filtered.loc[mask, "resultat"]
                    )
                else:
                    row_m["nb_localisations_non_conformes"] = 0
            else:
                row_m["nb_localisations"] = 0
                row_m["nb_operations_controle"] = 0
                row_m["nb_localisations_non_conformes"] = 0

            if not pej_filtered.empty and "DATE_REF" in pej_filtered.columns:
                dt = pd.to_datetime(pej_filtered["DATE_REF"], errors="coerce")
                mask = (dt.dt.year == year) & (dt.dt.month == month)
                row_m["nb_pej"] = int(mask.sum())
            else:
                row_m["nb_pej"] = 0

            if not pa_lignes.empty and "DATE_REF" in pa_lignes.columns:
                dt = pa_lignes["DATE_REF"]
                mask = (dt.dt.year == year) & (dt.dt.month == month)
                row_m["nb_pa"] = int(mask.sum())
            else:
                row_m["nb_pa"] = 0
            if not pve_filtered.empty and "INF-DATE-MIF" in pve_filtered.columns:
                dt = pve_filtered["INF-DATE-MIF"]
                row_m["nb_pve"] = int(((dt.dt.year == year) & (dt.dt.month == month)).sum())
            else:
                row_m["nb_pve"] = 0
            rows_month.append(row_m)

        if rows_month:
            mensuel = pd.DataFrame(rows_month)
            mensuel["taux_non_conformite_controles"] = mensuel.apply(
                lambda r: (
                    (r["nb_localisations_non_conformes"] / r["nb_localisations"])
                    if r["nb_localisations"] > 0
                    else pd.NA
                ),
                axis=1,
            )
            results["agg_annuelle"] = mensuel
            results["ventilation_temporelle_type"] = "mensuelle"

    if "categories_chasse" in profile and profile["categories_chasse"]:
        from core.engine.agregations_profil import analyse_categories_chasse
        res_cat = analyse_categories_chasse(
            point_filtered, pve_filtered, pej_filtered,
            profile["categories_chasse"],
            out_dir=None,
        )
        results["categories_chasse_controles"] = res_cat["controles"]["df"]
        results["categories_chasse_infractions"] = res_cat["infractions"]["df"]
        results["categories_chasse_controles_donut_data"] = res_cat["controles"]["donut_data"]
        results["categories_chasse_infractions_donut_data"] = res_cat["infractions"]["donut_data"]
        results["categories_chasse_unlisted_natinf"] = res_cat["infractions"]["unlisted_natinf"]

    return results


def _export_csv(
    results: dict,
    point_filtered: pd.DataFrame,
    pej_filtered: pd.DataFrame,
    pa_filtered: pd.DataFrame,
    pve_filtered: pd.DataFrame,
    out_dir: Path,
    profile: dict,
    code_norm: str,
) -> None:
    """Exporte tous les CSV dans le dossier de sortie."""
    profil_id = profile["id"]
    base_prefix = profile.get("_export_prefix") or profil_id
    prefix = f"{base_prefix}_{code_norm}" if str(code_norm).strip() else base_prefix
    root = PROJECT_ROOT
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

        # Export GeoPackage pour le moteur cartographique QGIS (Lot 3 - Filtrage Spatial)
        try:
            import geopandas as gpd
            import logging
            from pathlib import Path
            logger = logging.getLogger(__name__)
            
            df_pts = point_filtered.copy()
            if hasattr(df_pts, "geometry") and df_pts.geometry is not None and not df_pts.geometry.isna().all():
                try:
                    df_pts_wgs84 = df_pts.to_crs("EPSG:4326") if (hasattr(df_pts, "crs") and df_pts.crs and df_pts.crs.to_epsg() != 4326) else df_pts
                    df_pts["_lon"] = df_pts_wgs84.geometry.x
                    df_pts["_lat"] = df_pts_wgs84.geometry.y
                except Exception:
                    pass

            if "_lon" not in df_pts.columns or df_pts["_lon"].isna().all():
                lon_col = next((c for c in ("x", "x_wgs84", "longitude", "lon") if c in df_pts.columns), None)
                lat_col = next((c for c in ("y", "y_wgs84", "latitude", "lat") if c in df_pts.columns), None)
                if lon_col and lat_col:
                    df_pts["_lon"] = pd.to_numeric(df_pts[lon_col], errors="coerce")
                    df_pts["_lat"] = pd.to_numeric(df_pts[lat_col], errors="coerce")

            if "_lon" in df_pts.columns and "_lat" in df_pts.columns:
                missing = df_pts["_lon"].isna() | df_pts["_lat"].isna() | (df_pts["_lon"] == 0) | (df_pts["_lat"] == 0)
                if missing.any():
                    try:
                        dict_x, dict_y = get_communes_centroids_dicts(root)
                        insee_s = coalesced_insee_series(df_pts)
                        df_pts["insee_str"] = insee_s.astype(str).str.zfill(5)
                        df_pts.loc[missing, "_lon"] = df_pts.loc[missing, "insee_str"].map(dict_x)
                        df_pts.loc[missing, "_lat"] = df_pts.loc[missing, "insee_str"].map(dict_y)
                    except Exception as e_geom:
                        logger.warning(f"Impossible de centrer les points de contrôle orphelins : {e_geom}")
                mask_geo = df_pts["_lon"].notna() & df_pts["_lat"].notna() & (df_pts["_lon"] != 0) & (df_pts["_lat"] != 0)
                
                if mask_geo.any():
                    # Les coordonnées x,y dans point_ctrl sont généralement en WGS84 ou L93.
                    # On suppose WGS84 (EPSG:4326) et on projette en L93 (EPSG:2154)
                    gdf_pts = gpd.GeoDataFrame(
                        df_pts[mask_geo],
                        geometry=gpd.points_from_xy(df_pts.loc[mask_geo, "_lon"], df_pts.loc[mask_geo, "_lat"]),
                        crs="EPSG:4326"
                    ).to_crs("EPSG:2154")
                    
                    for col in gdf_pts.select_dtypes(include=['datetime64[ns, UTC]', 'datetime64[ns]', 'datetime64']).columns:
                        gdf_pts[col] = gdf_pts[col].astype(str)
                    if "domaine" not in gdf_pts.columns:
                        gdf_pts["domaine"] = "Hors domaine"
                    else:
                        gdf_pts["domaine"] = gdf_pts["domaine"].fillna("Hors domaine")
                    if "type_usager" not in gdf_pts.columns:
                        alt_col = next((c for c in ["usager", "type_usager_cible", "types_usager_cible", "cat_usager"] if c in gdf_pts.columns), None)
                        gdf_pts["type_usager"] = gdf_pts[alt_col] if alt_col else "Autre"
                        
                    carto_dir = get_carto_temp_dir()
                    carto_dir.mkdir(parents=True, exist_ok=True)
                    gpkg_path_pts = carto_dir / f"controles_{prefix}_export_automatique.gpkg"
                    
                    gdf_pts = _sanitize_gdf_for_gpkg(gdf_pts)
                    gdf_pts.to_file(gpkg_path_pts, driver="GPKG")
                    logger.info(f"Couche géographique Contrôles générée pour QGIS : {gpkg_path_pts} ({mask_geo.sum()} points)")
        except Exception as e:
            logger.warning(f"Impossible d'exporter la couche QGIS des Contrôles : {e}")

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
        try:
            import geopandas as gpd
            import logging
            from pathlib import Path
            logger = logging.getLogger(__name__)
            
            lon_col, lat_col = "x_faits", "y_faits"
            if lon_col in pej_filtered.columns and lat_col in pej_filtered.columns:
                df_geo = pej_filtered.copy()
                df_geo["_lon"] = pd.to_numeric(df_geo[lon_col], errors="coerce")
                df_geo["_lat"] = pd.to_numeric(df_geo[lat_col], errors="coerce")
                
                # Gérer les PEJ orphelins (sans coordonnées) en utilisant le centroïde de leur commune si possible
                missing = df_geo["_lon"].isna() | df_geo["_lat"].isna() | (df_geo["_lon"] == 0) | (df_geo["_lat"] == 0)
                if missing.any():
                    try:
                        dict_x, dict_y = get_communes_centroids_dicts(root)
                        insee_s = coalesced_insee_series(df_geo)
                        df_geo["insee_str"] = insee_s.astype(str).str.zfill(5)
                        df_geo.loc[missing, "_lon"] = df_geo.loc[missing, "insee_str"].map(dict_x)
                        df_geo.loc[missing, "_lat"] = df_geo.loc[missing, "insee_str"].map(dict_y)
                    except Exception as e_geom:
                        logger.warning(f"Impossible de centrer les PEJ orphelins : {e_geom}")
                
                # Exporter seulement ceux qui ont des coordonnées finales valides
                mask_geo = df_geo["_lon"].notna() & df_geo["_lat"].notna() & (df_geo["_lon"] != 0) & (df_geo["_lat"] != 0)
                if mask_geo.any():
                    try:
                        from pyproj import Transformer
                        transformer = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
                        x_2154, y_2154 = transformer.transform(
                            df_geo.loc[mask_geo, "_lon"].values,
                            df_geo.loc[mask_geo, "_lat"].values
                        )
                        gdf = gpd.GeoDataFrame(
                            pej_filtered[mask_geo],
                            geometry=gpd.points_from_xy(x_2154, y_2154),
                            crs="EPSG:2154"
                        )
                    except Exception:
                        gdf = gpd.GeoDataFrame(
                            pej_filtered[mask_geo],
                            geometry=gpd.points_from_xy(df_geo.loc[mask_geo, "_lon"], df_geo.loc[mask_geo, "_lat"]),
                            crs="EPSG:4326"
                        ).to_crs("EPSG:2154")
                    
                    carto_dir = get_carto_temp_dir()
                    carto_dir.mkdir(parents=True, exist_ok=True)
                    gpkg_path = carto_dir / f"pej_{prefix}_export_automatique.gpkg"
                    gdf = _sanitize_gdf_for_gpkg(gdf)
                    gdf.to_file(gpkg_path, driver="GPKG")
                    logger.info(f"Couche géographique PEJ générée pour QGIS : {gpkg_path} ({mask_geo.sum()} points)")
        except Exception as e:
            logger.warning(f"Impossible d'exporter la couche QGIS des PEJ : {e}")
    if "pej_par_theme" in results:
        results["pej_par_theme"].to_csv(
            out_dir / f"pej_{prefix}_par_theme.csv", sep=";", index=False
        )

    # PA
    if not pa_filtered.empty:
        pa_filtered.to_csv(out_dir / f"pa_{prefix}.csv", sep=";", index=False)
        try:
            from core.common.utilitaires_metier import filter_points_induisant_pa
            pt_pa = filter_points_induisant_pa(point)
            if not pt_pa.empty and gpd is not None:
                lon_c = next((c for c in ["longitude", "x_lambert93", "x_faits"] if c in pt_pa.columns), None)
                lat_c = next((c for c in ["latitude", "y_lambert93", "y_faits"] if c in pt_pa.columns), None)
                if lon_c and lat_c:
                    df_geo_pa = pt_pa.copy()
                    df_geo_pa["_lon"] = pd.to_numeric(df_geo_pa[lon_c], errors="coerce")
                    df_geo_pa["_lat"] = pd.to_numeric(df_geo_pa[lat_c], errors="coerce")
                    mask_pa = df_geo_pa["_lon"].notna() & df_geo_pa["_lat"].notna() & (df_geo_pa["_lon"] != 0)
                    if mask_pa.any():
                        gdf_pa = gpd.GeoDataFrame(
                            df_geo_pa[mask_pa],
                            geometry=gpd.points_from_xy(df_geo_pa.loc[mask_pa, "_lon"], df_geo_pa.loc[mask_pa, "_lat"]),
                            crs="EPSG:4326" if lon_c == "longitude" else "EPSG:2154"
                        )
                        if gdf_pa.crs.to_epsg() != 2154:
                            gdf_pa = gdf_pa.to_crs("EPSG:2154")
                        carto_dir = get_carto_temp_dir()
                        carto_dir.mkdir(parents=True, exist_ok=True)
                        gpkg_path_pa = carto_dir / f"pa_{prefix}_export_automatique.gpkg"
                        gdf_pa = _sanitize_gdf_for_gpkg(gdf_pa)
                        gdf_pa.to_file(gpkg_path_pa, driver="GPKG")
                        logger.info(f"Couche géographique PA générée pour QGIS : {gpkg_path_pa}")
        except Exception as e_pa_gpkg:
            logger.warning(f"Impossible d'exporter la couche QGIS des PA : {e_pa_gpkg}")
    if "pa_par_theme" in results:
        results["pa_par_theme"].to_csv(
            out_dir / f"pa_{prefix}_par_theme.csv", sep=";", index=False
        )

    # PVe
    if not pve_filtered.empty:
        pve_filtered.to_csv(out_dir / f"pve_{prefix}.csv", sep=";", index=False)
        try:
            import geopandas as gpd
            import logging
            from pathlib import Path
            logger = logging.getLogger(__name__)
            
            lon_col, lat_col = "inf_gps_long", "inf_gps_lat"
            if lon_col in pve_filtered.columns and lat_col in pve_filtered.columns:
                df_geo = pve_filtered.copy()
                df_geo["_lon"] = pd.to_numeric(df_geo[lon_col], errors="coerce")
                df_geo["_lat"] = pd.to_numeric(df_geo[lat_col], errors="coerce")
                
                # Gérer les PVe orphelins (sans coordonnées) en utilisant le centroïde de leur commune
                missing = df_geo["_lon"].isna() | df_geo["_lat"].isna() | (df_geo["_lon"] == 0) | (df_geo["_lat"] == 0)
                if missing.any():
                    try:
                        dict_x, dict_y = get_communes_centroids_dicts(root)
                        df_geo["insee_str"] = df_geo.get("INF-INSEE", pd.Series(dtype=str)).astype(str).str.zfill(5)
                        df_geo.loc[missing, "_lon"] = df_geo.loc[missing, "insee_str"].map(dict_x)
                        df_geo.loc[missing, "_lat"] = df_geo.loc[missing, "insee_str"].map(dict_y)
                    except Exception as e_geom:
                        logger.warning(f"Impossible de centrer les PVe orphelins : {e_geom}")
                
                # Exporter seulement ceux qui ont des coordonnées finales valides
                mask_geo = df_geo["_lon"].notna() & df_geo["_lat"].notna() & (df_geo["_lon"] != 0) & (df_geo["_lat"] != 0)
                if mask_geo.any():
                    try:
                        from pyproj import Transformer
                        transformer = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
                        x_2154, y_2154 = transformer.transform(
                            df_geo.loc[mask_geo, "_lon"].values,
                            df_geo.loc[mask_geo, "_lat"].values
                        )
                        gdf = gpd.GeoDataFrame(
                            pve_filtered[mask_geo],
                            geometry=gpd.points_from_xy(x_2154, y_2154),
                            crs="EPSG:2154"
                        )
                    except Exception:
                        gdf = gpd.GeoDataFrame(
                            pve_filtered[mask_geo],
                            geometry=gpd.points_from_xy(df_geo.loc[mask_geo, "_lon"], df_geo.loc[mask_geo, "_lat"]),
                            crs="EPSG:4326"
                        ).to_crs("EPSG:2154")
                    
                    carto_dir = get_carto_temp_dir()
                    carto_dir.mkdir(parents=True, exist_ok=True)
                    gpkg_path = carto_dir / f"pve_{prefix}_export_automatique.gpkg"
                    gdf = _sanitize_gdf_for_gpkg(gdf)
                    gdf.to_file(gpkg_path, driver="GPKG")
                    logger.info(f"Couche géographique PVe générée pour QGIS : {gpkg_path} ({mask_geo.sum()} points)")
        except Exception as e:
            logger.warning(f"Impossible d'exporter la couche QGIS des PVe : {e}")

    # Synthèse croisée
    if "synthese_zone" in results:
        results["synthese_zone"].to_csv(
            out_dir / f"synthese_{prefix}_par_zone.csv", sep=";", index=False
        )

    # Agrégation temporelle (annuelle, trimestrielle ou mensuelle)
    vent_type = results.get("ventilation_temporelle_type")
    if "agg_annuelle" in results and isinstance(results["agg_annuelle"], pd.DataFrame):
        if vent_type == "mensuelle":
            results["agg_annuelle"].to_csv(
                out_dir / f"indicateurs_{prefix}_par_mois.csv", sep=";", index=False
            )
        elif vent_type == "trimestrielle":
            results["agg_annuelle"].to_csv(
                out_dir / f"indicateurs_{prefix}_par_trimestre.csv", sep=";", index=False
            )
        elif vent_type == "hebdomadaire":
            results["agg_annuelle"].to_csv(
                out_dir / f"indicateurs_{prefix}_par_semaine.csv", sep=";", index=False
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

    if "categories_chasse_controles" in results and isinstance(results["categories_chasse_controles"], pd.DataFrame):
        results["categories_chasse_controles"].to_csv(out_dir / "categories_chasse_controles.csv", sep=";", index=False, encoding="utf-8")
    if "categories_chasse_infractions" in results and isinstance(results["categories_chasse_infractions"], pd.DataFrame):
        results["categories_chasse_infractions"].to_csv(out_dir / "categories_chasse_infractions.csv", sep=";", index=False, encoding="utf-8")

    nb_loc = int(results.get("nb_localisations", len(point_filtered)))
    nb_ops = int(results.get("nb_operations_controle", 0))
    nb_pej = int(results.get("nb_pej", len(pej_filtered)))
    nb_pa = int(results.get("nb_pa", len(pa_filtered)))
    nb_pve = int(results.get("nb_pve", len(pve_filtered)))

    pd.DataFrame([{
        "nb_localisations": nb_loc,
        "nb_operations_controle": nb_ops,
    }]).to_csv(out_dir / f"controles_{prefix}_operations_resume.csv", sep=";", index=False)
    pd.DataFrame([{"nb_pej_global": nb_pej}]).to_csv(out_dir / f"pej_{prefix}_resume.csv", sep=";", index=False)
    pd.DataFrame([{"nb_pa_global": nb_pa}]).to_csv(out_dir / f"pa_{prefix}_resume.csv", sep=";", index=False)
    pd.DataFrame([{"nb_pve_global": nb_pve}]).to_csv(out_dir / f"pve_{prefix}_resume.csv", sep=";", index=False)

    if "pve_top_infractions" in results and isinstance(results["pve_top_infractions"], pd.DataFrame):
        results["pve_top_infractions"].to_csv(out_dir / f"pve_{prefix}_par_natinf.csv", sep=";", index=False)



run_thematic_aggregations = _run_aggregations
