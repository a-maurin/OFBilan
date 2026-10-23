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

"""Module de filtrage métier et spatial des profils de bilan."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd

from core.common.chargeurs_donnees import (
    load_natinf_ref,
    load_pnf,
    load_rech_av,
    load_tub,
    load_tub_pnf_codes,
)
from core.common.chargeurs_donnees import (
    pnf_sig_union_membership_mask,
    tub_sig_union_membership_mask,
)
from core.common.chargeurs_donnees import ensure_insee_from_communes_shp
from core.common.utilitaires_metier import (
    coalesced_insee_series,
    contient_natinf,
    count_controles_non_conformes_oscean,
    count_pa_induites_par_controles,
    get_departements_pour_perimetre,
    mask_resultat_induit_pa,
    series_str_contains,
)
from core.common.bilan_config import BilanConfig

_log = logging.getLogger(__name__)
import sys

def _get_loader(name: str, fallback: Any) -> Any:
    orch = sys.modules.get("core.engine.orchestrateur_profils")
    if orch and hasattr(orch, name):
        return getattr(orch, name)
    return fallback


def _profile_sans_cible_type_usager(profile: dict) -> dict:
    """Copie du profil sans filtre sur le(s) type(s) d'usager ciblé(s)."""
    filt = dict(profile.get("filter") or {})
    return {**profile, "filter": {**filt, "type_usager_target": []}}


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
        
    if ft == "tub":
        return _filter_tub(point)

    if ft == "type_action_list":
        type_actions = filt.get("type_actions", [])
        if not type_actions:
            return point.copy()
        
        columns = filt.get("columns", ["type_actio", "type_action"])
        mask = pd.Series(False, index=point.index)
        
        for col in columns:
            if col in point.columns:
                col_series = point[col].fillna("").astype(str)
                for act in type_actions:
                    # Match partiel ("contient") pour être robuste face aux troncatures
                    mask |= col_series.str.lower().str.contains(act.lower(), regex=False)
        return point[mask].copy()

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
    """Filtre agrainage : nom_dossie « agrain » ou « tub » OU type_actio sanitaire (hors tuberculose/grippe/piégeage)."""
    mask_nom = pd.Series(False, index=point.index)
    if "nom_dossie" in point.columns:
        mask_nom = series_str_contains(point["nom_dossie"], r"agrain|tub", regex=True)

    mask_type = pd.Series(False, index=point.index)
    type_col = "type_actio" if "type_actio" in point.columns else "type_action"
    if type_col in point.columns:
        col = point[type_col]
        mask_type = series_str_contains(col, "police sanitaire", regex=False)
        mask_excl = series_str_contains(col, r"tubercul|grippe|pi[eé]geage", regex=True)
        mask_type = mask_type & ~mask_excl

    return point[mask_nom | mask_type].copy()


def _filter_tub(point: pd.DataFrame) -> pd.DataFrame:
    """Filtre spécifique TUB strict sur le nom du dossier (logique identique à la symbologie QGIS)."""
    mask_nom = pd.Series(False, index=point.index)
    if "nom_dossie" in point.columns:
        # La symbologie QGIS utilise '%grainage%' ou '%tub%'
        mask_nom = series_str_contains(point["nom_dossie"], r"grainage|tub", regex=True)
    return point[mask_nom].copy()


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
                mask |= series_str_contains(pt[col], kw_esc, regex=True)

    filtered = pt[mask].copy()

    if exclude_patterns:
        for pattern in exclude_patterns:
            for col in columns:
                if col in filtered.columns:
                    excl = series_str_contains(filtered[col], pattern, regex=True)
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


def filter_by_agent_service(df: pd.DataFrame, col_candidates: list[str], target_service: str, profile_cfg: dict = None) -> pd.DataFrame:
    """Filtre un DataFrame selon l'organisme / service (OFB vs PNF).

    - target_service: "tous", "ofb", "pnf"
    - NULL / indéterminés sont attribués par défaut à l'OFB lors du filtre OFB.
    """
    if df is None or df.empty or not target_service or str(target_service).strip().lower() == "tous":
        return df

    target_service = str(target_service).strip().lower()
    if target_service not in ("ofb", "pnf"):
        return df

    agent_rules = profile_cfg.get("agent_rules", {}) if isinstance(profile_cfg, dict) else {}
    pnf_keywords = agent_rules.get("pnf_keywords", ["PNF", "P.N.F", "PARC", "FORETS", "FORET", "FORÊTS", "FORÊT"])

    # Étendre la recherche à toutes les colonnes candidates pertinentes
    all_candidates = list(col_candidates) if col_candidates else []
    standard_cols = [
        "entite_ctrl", "entit_ctrl", "entite", "entit", "ENTITE", "ENTITE_CTRL",
        "ENTITE_ORIGINE_PROCEDURE", "entite_origine_procedure",
        "UNITE_libelle", "unite_libelle", "UNITE_LIBELLE", "UNITE", "unite",
        "service", "SERVICE", "service_nom", "service_ctrl", "organisme", "ORGANISME",
        "agent", "AGENT", "libelle_service", "libelle_unite", "partenaire", "partenaires"
    ]
    for sc in standard_cols:
        if sc not in all_candidates:
            all_candidates.append(sc)

    present_cols = [c for c in all_candidates if c in df.columns]

    if not present_cols:
        if target_service == "ofb":
            return df.copy()
        else:
            return df.iloc[0:0].copy()

    pnf_keywords_upper = [str(k).upper() for k in pnf_keywords]
    is_pnf = pd.Series(False, index=df.index)

    for col in present_cols:
        val_series = df[col].fillna("").astype(str).str.upper()
        col_is_pnf = val_series.apply(lambda x: any(k in x for k in pnf_keywords_upper))
        is_pnf = is_pnf | col_is_pnf

    if target_service == "pnf":
        return df[is_pnf].copy()
    else:
        return df[~is_pnf].copy()


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
        h = hashlib.md5(
            label.encode("utf-8", errors="ignore"),
            usedforsecurity=False,
        ).hexdigest()[:8]
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
    from core.common.utilitaires_metier import get_departements_pour_perimetre
    dept_codes = get_departements_pour_perimetre(cfg.echelle, cfg.code)
    if dept_codes and "FR" not in dept_codes and "ENTITE_ORIGINE_PROCEDURE" in pej.columns:
        dept_extracted = pej["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.extract(r'(\d+)')[0]
        pnf_m = pej["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.upper().str.contains(r'PNF|PARC|FORET', regex=True, na=False)
        pej = pej[dept_extracted.isin(dept_codes) | pnf_m].copy()

    # Déduplication par DC_ID
    if "DC_ID" in pej.columns:
        if "DATE_REF" in pej.columns:
            pej = pej.sort_values("DATE_REF", ascending=False).drop_duplicates(
                subset="DC_ID", keep="first"
            )
        else:
            pej = pej.drop_duplicates(subset="DC_ID", keep="first")

    if natinf_pej:
        # On utilise une expression régulière qui gère correctement les séparateurs comme '_' ou '-'
        pattern = "|".join(rf"(?:^|[^a-zA-Z0-9]){re.escape(str(c))}(?:[^a-zA-Z0-9]|$)" for c in natinf_pej)
        natinf_col = "NATINF_PEJ" if "NATINF_PEJ" in pej.columns else "NATINF"
        if natinf_col in pej.columns:
            return pej[series_str_contains(pej[natinf_col], pattern, regex=True)].copy()

    if ft == "procedures":
        return pej.copy()

    if ft == "type_usager":
        targets = (profile.get("filter", {}) or {}) .get("type_usager_target") or []
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
    entity_sds = cfg.entity_sds

    # Restreindre systématiquement aux procédures de l'entité SD concernée
    if entity_sds and "ENTITE_ORIGINE_PROCEDURE" in pa.columns:
        pnf_m = pa["ENTITE_ORIGINE_PROCEDURE"].astype(str).str.upper().str.contains(r'PNF|PARC|FORET', regex=True, na=False)
        pa = pa[pa["ENTITE_ORIGINE_PROCEDURE"].isin(entity_sds) | pnf_m].copy()

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

    # Les thèmes PVe ne correspondent pas aux thèmes SNC pour le moment
    # La recherche par mot-clé est donc désactivée pour cette source (sera gérée via un dictionnaire de concordance)
    return pve


def _apply_rech_av_filter(
    pt: pd.DataFrame,
    pej: pd.DataFrame,
    pa: pd.DataFrame,
    pve: pd.DataFrame,
    root: Path,
    mots_cles: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Applique le filtre par mots-clés de rech_av si demandé."""
    if not mots_cles:
        return pt, pej, pa, pve
        
    df_rech = _get_loader("load_rech_av", load_rech_av)(root)
    if df_rech.empty or "num_dossier" not in df_rech.columns or "mots_cles" not in df_rech.columns:
        return pt.iloc[0:0], pej.iloc[0:0], pa.iloc[0:0], pve.iloc[0:0]
        
    mask_rech = pd.Series(False, index=df_rech.index)
    for mc in mots_cles:
        mask_rech |= df_rech["mots_cles"].astype(str).str.contains(mc, case=False, na=False)
        
    valid_dossiers = set(
        df_rech.loc[mask_rech, "num_dossier"]
        .dropna().astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip().unique()
    )
    
    def _filter_by_possible_id_cols(df: pd.DataFrame, valid_ids: set) -> pd.DataFrame:
        if df.empty:
            return df
        possible_cols = [c for c in df.columns if c.lower() in (
            "nom_dossie", "nom_dossier", "num_dossie", "num_dossier", 
            "dc_id", "dossier_source", "id_dossier"
        )]
        for col in possible_cols:
            col_ids = df[col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
            if col_ids.isin(valid_ids).any():
                return df[col_ids.isin(valid_ids)].copy()
        return df.iloc[0:0].copy()

    pt = _filter_by_possible_id_cols(pt, valid_dossiers)
    pa = _filter_by_possible_id_cols(pa, valid_dossiers)
    pej = _filter_by_possible_id_cols(pej, valid_dossiers)
        
    if not pve.empty:
        pve = pve.iloc[0:0].copy()
        
    return pt, pej, pa, pve



# ═══════════════════════════════════════════════════════════════════════════
# 4. Analyses spatiales
# ═══════════════════════════════════════════════════════════════════════════

def _get_insee_col(df: pd.DataFrame) -> str | None:
    for c in ("insee_comm", "insee_commun", "INSEE_COM", "INF-INSEE"):
        if c in df.columns:
            return c
    return None


def _coalesced_insee_for_pnf_mask(df: pd.DataFrame) -> pd.Series:
    """Code INSEE normalisé (5 chiffres) par ligne — délègue à ``coalesced_insee_series``."""
    return coalesced_insee_series(df)


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
    _, pnf_codes = _get_loader("load_tub_pnf_codes", load_tub_pnf_codes)(root)

    if not point_filtered.empty:
        point_filtered = _get_loader("ensure_insee_from_communes_shp", ensure_insee_from_communes_shp)(
            point_filtered,
            root,
            context="restriction PNF — points de contrôle",
            log=log,
        )
        mask_insee = _mask_insee_in_pnf_codes(point_filtered, pnf_codes)
        mask_sig = _get_loader("pnf_sig_union_membership_mask", pnf_sig_union_membership_mask)(point_filtered, root, log=log)
        mask = mask_insee | mask_sig
        if not mask.any():
            log.warning(
                "Restriction PNF : aucun point ne correspond à la liste INSEE du référentiel "
                "ni aux couches SIG (cœur / adhésion) ; vérifiez les coordonnées "
                "et ref/programme/sig/PNF/127_communes/127_communes_AOA_et_statuts_adhesion.shp."
            )
        point_filtered = point_filtered.loc[mask].copy()
    # Règle métier PA : seules les localisations de contrôles "Manquement" portent
    # l'assiette spatiale des PA.
    point_manq = point_filtered
    if "resultat" in point_filtered.columns:
        point_manq = point_filtered.loc[
            mask_resultat_induit_pa(point_filtered["resultat"])
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
                sig_m = _get_loader("pnf_sig_union_membership_mask", pnf_sig_union_membership_mask)(loc_df, root, log=log).reindex(
                    pej_filtered.index, fill_value=False
                )
                mask_pej = mask_pej | sig_m
                sub = pej_filtered.loc[xy_ok].copy()
                sub["x"] = pd.to_numeric(sub["x_faits"], errors="coerce")
                sub["y"] = pd.to_numeric(sub["y_faits"], errors="coerce")
                sub_insee = _get_loader("ensure_insee_from_communes_shp", ensure_insee_from_communes_shp)(
                    sub,
                    root,
                    context="restriction PNF — PEJ (coordonnées FAITS)",
                    log=log,
                )
                if not sub_insee.empty and "insee_comm" in sub_insee.columns:
                    if "insee_comm" not in pej_filtered.columns:
                        pej_filtered["insee_comm"] = pd.NA
                    pej_filtered.loc[sub_insee.index, "insee_comm"] = sub_insee["insee_comm"]
                m_insee = _mask_insee_in_pnf_codes(sub_insee, pnf_codes)
                mask_pej = mask_pej | m_insee.reindex(pej_filtered.index, fill_value=False)

        if not point_filtered.empty and "dc_id" in point_filtered.columns and "insee_comm" in point_filtered.columns:
            pt_insee_map = point_filtered.dropna(subset=["dc_id", "insee_comm"]).set_index("dc_id")["insee_comm"].to_dict()
            if pt_insee_map:
                if "insee_comm" not in pej_filtered.columns:
                    pej_filtered["insee_comm"] = pd.NA
                dc_series = pej_filtered["DC_ID"].astype(str).str.strip()
                pej_filtered["insee_comm"] = pej_filtered["insee_comm"].fillna(dc_series.map(pt_insee_map))

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
        pve_filtered = _get_loader("ensure_insee_from_communes_shp", ensure_insee_from_communes_shp)(
            pve_filtered,
            root,
            context="restriction PNF — PVe",
            log=log,
        )
        mask_pi = _mask_insee_in_pnf_codes(pve_filtered, pnf_codes)
        mask_pg = _get_loader("pnf_sig_union_membership_mask", pnf_sig_union_membership_mask)(pve_filtered, root, log=log)
        mask_p = mask_pi | mask_pg
        if not mask_p.any():
            log.warning(
                "Restriction PNF : aucune PVe ne correspond au périmètre INSEE ni SIG."
            )
            pve_filtered = pve_filtered.iloc[0:0].copy()
        else:
            pve_filtered = pve_filtered.loc[mask_p].copy()

    return point_filtered, pej_filtered, pa_filtered, pve_filtered


def _apply_restrict_geo_tub(
    point_filtered: pd.DataFrame,
    pej_filtered: pd.DataFrame,
    pa_filtered: pd.DataFrame,
    pve_filtered: pd.DataFrame,
    root: Path,
    log: logging.Logger,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Restreint les jeux de données au périmètre TUB (union INSEE et intersection spatiale SIG)."""
    tub_codes, _ = _get_loader("load_tub_pnf_codes", load_tub_pnf_codes)(root)

    def _has_coords(df):
        m = pd.Series(False, index=df.index)
        if "x" in df.columns and "y" in df.columns:
            m = m | (pd.to_numeric(df["x"], errors="coerce").notna() & pd.to_numeric(df["y"], errors="coerce").notna())
        if "inf_gps_long" in df.columns and "inf_gps_lat" in df.columns:
            lng = pd.to_numeric(df["inf_gps_long"].astype(str).str.replace(",", "."), errors="coerce")
            lat = pd.to_numeric(df["inf_gps_lat"].astype(str).str.replace(",", "."), errors="coerce")
            m = m | (lng.notna() & lat.notna())
        return m

    if not point_filtered.empty:
        point_filtered = _get_loader("ensure_insee_from_communes_shp", ensure_insee_from_communes_shp)(
            point_filtered, root, context="restriction TUB — contrôles", log=log
        )
        s = coalesced_insee_series(point_filtered)
        mask_insee = s.notna() & s.astype(str).isin(tub_codes)
        mask_sig = _get_loader("tub_sig_union_membership_mask", tub_sig_union_membership_mask)(point_filtered, root, log=log)
        
        has_c = _has_coords(point_filtered)
        mask = mask_sig | (mask_insee & ~has_c)
        point_filtered = point_filtered.loc[mask].copy()

    dc_ids: set[str] = set()
    if not point_filtered.empty and "dc_id" in point_filtered.columns:
        dc_ids = set(point_filtered["dc_id"].dropna().astype(str).str.replace(r"\.0$", "", regex=True).unique())

    if not pej_filtered.empty:
        mask_pej = pd.Series(False, index=pej_filtered.index)
        if "DC_ID" in pej_filtered.columns and dc_ids:
            mask_pej = mask_pej | pej_filtered["DC_ID"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().isin(dc_ids)
        
        if "x_faits" in pej_filtered.columns and "y_faits" in pej_filtered.columns:
            xy_ok = pej_filtered["x_faits"].notna() & pej_filtered["y_faits"].notna()
            if bool(xy_ok.any()):
                sub = pej_filtered.loc[xy_ok].copy()
                sub["x"] = pd.to_numeric(sub["x_faits"], errors="coerce")
                sub["y"] = pd.to_numeric(sub["y_faits"], errors="coerce")
                sub_insee = _get_loader("ensure_insee_from_communes_shp", ensure_insee_from_communes_shp)(
                    sub,
                    root,
                    context="restriction TUB — PEJ (coordonnées FAITS)",
                    log=log,
                )
                m_insee = _mask_insee_in_pnf_codes(sub_insee, tub_codes)
                m_sig = _get_loader("tub_sig_union_membership_mask", tub_sig_union_membership_mask)(sub, root, log=log)
                has_c_pej = _has_coords(sub)
                
                m_final = m_sig | (m_insee & ~has_c_pej)
                mask_pej = mask_pej | m_final.reindex(pej_filtered.index, fill_value=False)
        
        if not mask_pej.any():
            log.warning(
                "Restriction TUB : aucune PEJ ne correspond à un contrôle du périmètre "
                "ni à une localisation FAITS dans la zone TUB."
            )
        pej_filtered = pej_filtered.loc[mask_pej].copy()

    if not pa_filtered.empty and "DC_ID" in pa_filtered.columns:
        if dc_ids:
            pa_filtered = pa_filtered[pa_filtered["DC_ID"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().isin(dc_ids)].copy()
        else:
            pa_filtered = pa_filtered.iloc[0:0].copy()

    if not pve_filtered.empty:
        pve_filtered = _get_loader("ensure_insee_from_communes_shp", ensure_insee_from_communes_shp)(
            pve_filtered, root, context="restriction TUB — PVe", log=log
        )
        s_pve = coalesced_insee_series(pve_filtered)
        mask_pve_insee = s_pve.notna() & s_pve.astype(str).isin(tub_codes)
        mask_pve_sig = _get_loader("tub_sig_union_membership_mask", tub_sig_union_membership_mask)(pve_filtered, root, log=log)
        
        has_c_pve = _has_coords(pve_filtered)
        pve_filtered = pve_filtered.loc[mask_pve_sig | (mask_pve_insee & ~has_c_pve)].copy()

    return point_filtered, pej_filtered, pa_filtered, pve_filtered


def _run_spatial_analyses(
    point_filtered: pd.DataFrame,
    pej_filtered: pd.DataFrame,
    pve_filtered: pd.DataFrame,
    options: dict,
    cfg: BilanConfig,
    profil_id: str | None = None,
    restrict_geo: str = "",
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Calcule les découpages spatiaux (PNF, TUB) si les options le demandent."""
    results: dict[str, Any] = {}
    need_pnf = options.get("pnf", False)
    need_tub = options.get("tub", False)

    if not need_pnf and not need_tub:
        return results, point_filtered

    tub_codes, pnf_codes = _get_loader("load_tub_pnf_codes", load_tub_pnf_codes)(cfg.root)
    results["tub_codes"] = tub_codes
    results["pnf_codes"] = pnf_codes

    pt = point_filtered.copy()
    insee_col = _get_insee_col(pt)

    if need_pnf and not pt.empty and insee_col:
        pt[insee_col] = pt[insee_col].astype(str).str.zfill(5)
        pnf_df = _get_loader("load_pnf", load_pnf)(cfg.root)
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
                nb_localisations=("dc_id", "count"),
                nb_non_conforme=(
                    "resultat",
                    lambda s: count_controles_non_conformes_oscean(s),
                ),
            )
            .reset_index()
        )
        agg_pnf["taux_non_conformite"] = agg_pnf["nb_non_conforme"] / agg_pnf[
            "nb_localisations"
        ].replace(0, pd.NA)
        results["agg_pnf"] = agg_pnf
        results["point_with_pnf"] = pt
        # Bilan PNF : détail par zone (cœur vs aire d'adhésion).
        if restrict_geo == "pnf":
            rows = []
            if "pnf_zone_sig" in pt.columns:
                coeur = pt[pt["pnf_zone_sig"] == "Coeur_PNF"].copy()
                hors = pt[pt["pnf_zone_sig"] != "Coeur_PNF"].copy()
                nb_c = int(len(coeur))
                nb_nc_c = (
                    count_controles_non_conformes_oscean(coeur["resultat"])
                    if "resultat" in coeur.columns
                    else 0
                )
                rows.append(
                    {
                        "PNF": "Cœur",
                        "nb_localisations": nb_c,
                        "nb_non_conforme": nb_nc_c,
                        "taux_non_conformite": (nb_nc_c / nb_c) if nb_c > 0 else pd.NA,
                    }
                )
                nb_h = int(len(hors))
                nb_nc_h = (
                    count_controles_non_conformes_oscean(hors["resultat"])
                    if "resultat" in hors.columns
                    else 0
                )
                rows.append(
                    {
                        "PNF": "Aire d'adhésion",
                        "nb_localisations": nb_h,
                        "nb_non_conforme": nb_nc_h,
                        "taux_non_conformite": (nb_nc_h / nb_h) if nb_h > 0 else pd.NA,
                    }
                )
            results["agg_pnf_detail"] = pd.DataFrame(rows)

    if (need_pnf or need_tub) and not pt.empty and insee_col:
        results["zone_ctrl"] = _zone_summary(pt, insee_col, tub_codes, pnf_codes)

    if (need_pnf or need_tub) and not pve_filtered.empty:
        pve_insee = _get_insee_col(pve_filtered)
        if pve_insee:
            base_z = _zone_count(pve_filtered, pve_insee, tub_codes, pnf_codes)
            if restrict_geo == "pnf":
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
                        {"zone": "Cœur", "nb": nb_coeur},
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

