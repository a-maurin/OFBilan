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
MODULE : ORCHESTRATEUR PRINCIPAL DES PROFILS DE BILAN (`orchestrateur_profils.py`)
========================================================================================
Ce module constitue le cœur névralgique du moteur de bilan. Il régit la totalité du
pipeline de traitement, du filtrage initial des données jusqu'à la génération PDF finale.

Fonctionnalités majeures :
  1. Chargement et validation des fichiers de configuration YAML de profils.
  2. Filtrage multicritères des points de contrôle, PEJ, PA et PVe (par période,
     périmètre géographique, thématique, NATINF, mots-clés ou types d'usagers).
  3. Orchestration des analyses statistiques et calcul des agrégations métier.
  4. Déclenchement de la génération des cartes cartographiques et des rapports PDF.
========================================================================================
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

from core.chemins_projet import get_out_dir, get_cartes_dir, get_carto_temp_dir, PROJECT_ROOT, ref_programme
from core.common.bilan_config import BilanConfig
from core.common.chargeurs_donnees import (
    ensure_insee_from_communes_shp,
    load_communes_noms,
    load_natinf_ref,
    load_pa,
    load_pej,
    load_pnf,
    load_point_ctrl,
    load_pve,
    load_rech_av,
    load_tub,
    load_tub_pnf_codes,
    merge_pej_faits_locations,
    enrich_pej_commune_from_faits_coordinates,
    pnf_sig_union_membership_mask,
    tub_sig_union_membership_mask,
)
from core.common.rendus_graphiques import (
    chart_pie,
    chart_bar,
    chart_bar_grouped,
    chart_bar_stacked,
    chart_line_evolution,
)
from core.common.utilitaires_metier import (
    resolve_code_subdir_suffix,
    coalesced_insee_series,
)
from core.common.ofb_charte import Spinner
from core.common.pdf_presentation_config import (
    normalize_dept_typography,
    apply_diffusion_pdf_suffix,
)
from core.common.carte_helper import (
    ensure_maps_for_profiles,
    resolve_profile_map_paths,
)
from core.common.cartographie_config import (
    ask_cartes_selection,
    expected_map_filenames_for_selection,
    has_cartography_catalog,
    resolve_cartes_selection,
)

_log = logging.getLogger(__name__)


def _sanitize_gdf_for_gpkg(gdf: Any) -> Any:
    """Assainit un GeoDataFrame pour l'export GeoPackage (dédoublonnage insensible à la casse et typage)."""
    if gdf is None or getattr(gdf, "empty", True):
        return gdf
    seen_lower = set()
    cols_to_keep = []
    geom_col = gdf.geometry.name if hasattr(gdf, "geometry") else "geometry"
    for col in gdf.columns:
        if col == geom_col:
            continue
        c_low = str(col).lower()
        if c_low not in seen_lower:
            seen_lower.add(c_low)
            cols_to_keep.append(col)
    cols_to_keep.append(geom_col)
    cleaned = gdf[cols_to_keep].copy()
    for col in cleaned.select_dtypes(include=['datetime64[ns, UTC]', 'datetime64[ns]', 'datetime64']).columns:
        cleaned[col] = cleaned[col].astype(str)
    return cleaned
# ═══════════════════════════════════════════════════════════════════════════
# 1. Chargement du profil YAML (délégué à core.engine.orchestration)
# ═══════════════════════════════════════════════════════════════════════════

from core.engine.orchestration.loader import (
    load_profile_config,
    _deep_merge_dicts,
    _normalize_profile,
)


def _normalize_profile(data: dict, profil_id: str) -> dict:
    """Assure la présence de toutes les clés attendues par le moteur."""
    data.setdefault("id", profil_id)
    data.setdefault("label", profil_id)
    data.setdefault("title_label", data.get("label", profil_id))
    pipeline = str(data.get("pipeline", "")).strip().lower()
    if not pipeline:
        raise ValueError(f"Profil {profil_id}: clé YAML requise manquante: pipeline")
    data["pipeline"] = pipeline
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
    filt.setdefault("type_actions", [])
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
    aggregation = data.get("aggregation")
    if not isinstance(aggregation, dict) or not str(aggregation.get("adapter", "")).strip():
        raise ValueError(f"Profil {profil_id}: clé YAML requise manquante: aggregation.adapter")
    pdf = data.get("pdf")
    if not isinstance(pdf, dict) or not str(pdf.get("adapter", "")).strip():
        raise ValueError(f"Profil {profil_id}: clé YAML requise manquante: pdf.adapter")
    if not str(data.get("presentation_scope", "")).strip():
        raise ValueError(f"Profil {profil_id}: clé YAML requise manquante: presentation_scope")
    capabilities = data.setdefault("capabilities", {})
    if not isinstance(capabilities, dict):
        capabilities = {}
        data["capabilities"] = capabilities
    capabilities.setdefault("combine", True)
    capabilities.setdefault("mix_batch", True)
    default_map_profiles: list[str] = [] if profil_id == "types_usager_cible" else [profil_id]
    capabilities.setdefault("map_profiles", default_map_profiles)

    return data


def _resolve_ventilation_mode_from_profile(
    profile: dict,
    *,
    date_deb_ts: pd.Timestamp,
    date_fin_ts: pd.Timestamp,
) -> tuple[str, str, int, int]:
    """Résout la ventilation temporelle depuis le profil YAML."""
    from core.engine.ventilation_temporelle import resolve_ventilation_auto

    period_cfg = profile.get("periode_analyse", {}) or {}
    vent_cfg = period_cfg.get("ventilation", {}) or {}
    vent_type = str(vent_cfg.get("type", "auto")).strip().lower()
    try:
        seuil_jours = int(vent_cfg.get("seuil_jours", 366))
    except (TypeError, ValueError):
        seuil_jours = 366
    duree_jours = int((date_fin_ts - date_deb_ts).days)
    if vent_type == "annuelle":
        ventilation_mode = "annuelle"
    elif vent_type == "globale":
        ventilation_mode = "globale"
    elif vent_type in ("hebdomadaire", "mensuelle", "trimestrielle"):
        ventilation_mode = vent_type
    else:
        ventilation_mode = resolve_ventilation_auto(duree_jours, seuil_jours=seuil_jours)
    return ventilation_mode, vent_type, seuil_jours, duree_jours


def _message_fin_generation_pdf(
    profile: dict,
    out_subdir: str,
    *,
    resolved_opts: dict,
    out_dir: Path | None = None,
) -> str:
    """Message console indiquant le dossier et le nom du PDF produit."""
    diffusion = str(resolved_opts.get("diffusion", "externe"))
    clean_sub = out_subdir if str(out_subdir).startswith("bilan_") else f"bilan_{out_subdir}"
    base = str(profile.get("output_filename", "")).strip() or f"{clean_sub}.pdf"
    if str(profile.get("id", "global")).strip() == "global":
        base = f"{clean_sub}.pdf"
    stem = Path(base).stem
    display_dir = str(out_dir) if out_dir is not None else f"data/out/{out_subdir}"
    if str(profile.get("id", "")).strip() == "synthese_activite_PA_PJ" or resolved_opts.get("format_sortie") == "les_deux":
        detailed_name = apply_diffusion_pdf_suffix(base, diffusion).name
        brochure_stem = stem if stem.endswith("_brochure") else f"{stem}_brochure"
        brochure_name = apply_diffusion_pdf_suffix(f"{brochure_stem}.pdf", diffusion).name
        return (
            f"Bilans générés : {display_dir}/{detailed_name} "
            f"et {display_dir}/{brochure_name}"
        )
    if resolved_opts.get("brochure"):
        stem = f"{clean_sub}_brochure" if not clean_sub.endswith("_brochure") else clean_sub
        pdf_name = apply_diffusion_pdf_suffix(f"{stem}.pdf", diffusion).name
        return f"Brochure générée : {display_dir}/{pdf_name}"
    pdf_name = apply_diffusion_pdf_suffix(base, diffusion).name
    return f"Bilan généré : {display_dir}/{pdf_name}"


def _run_global_profile_via_yaml(
    profile: dict,
    date_deb: str,
    date_fin: str,
    echelle: str,
    code: str,
    options: dict,
) -> int:
    """Exécute le profil global via le moteur unifié orienté profils (sans délégation backend)."""
    try:
        aggregations_mod = __import__("ofbilan.engine.agregations_profil", fromlist=["_dummy"])
    except ModuleNotFoundError:
        aggregations_mod = __import__("core.engine.agregations_profil", fromlist=["_dummy"])
    try:
        pdf_mod = __import__("ofbilan.engine.generation_pdf_profil", fromlist=["_dummy"])
    except ModuleNotFoundError:
        pdf_mod = __import__("core.engine.generation_pdf_profil", fromlist=["_dummy"])
    agg_adapter_name = str((profile.get("aggregation", {}) or {}).get("adapter", "run_profile_aggregations")).strip()
    pdf_adapter_name = str((profile.get("pdf", {}) or {}).get("adapter", "generate_profile_pdf_report")).strip()
    run_aggregations = getattr(aggregations_mod, agg_adapter_name, None)
    if run_aggregations is None:
        try:
            synthese_agg = __import__("ofbilan.engine.synthese_aggregations", fromlist=[agg_adapter_name])
        except ModuleNotFoundError:
            synthese_agg = __import__("core.engine.synthese_aggregations", fromlist=[agg_adapter_name])
        run_aggregations = getattr(synthese_agg, agg_adapter_name)
    generate_pdf_impl = getattr(pdf_mod, pdf_adapter_name, None)
    if generate_pdf_impl is None:
        try:
            synthese_pdf = __import__("ofbilan.engine.generation_pdf_synthese", fromlist=[pdf_adapter_name])
        except ModuleNotFoundError:
            synthese_pdf = __import__("core.engine.generation_pdf_synthese", fromlist=[pdf_adapter_name])
        generate_pdf_impl = getattr(synthese_pdf, pdf_adapter_name)

    resolved_opts = resolve_options(profile, options)
    chart_preset = resolved_opts.get("chart_preset")
    if options.get("chart_preset") and not chart_preset:
        chart_preset = options.get("chart_preset")
    resolved_opts = ask_interactive_options(profile, resolved_opts)

    # Override dynamique pour filtre thématique / domaine
    from copy import deepcopy
    filter_label = None
    if resolved_opts.get("themes"):
        filter_label = ", ".join(resolved_opts["themes"])
    elif resolved_opts.get("domaines"):
        filter_label = ", ".join(resolved_opts["domaines"])
    elif resolved_opts.get("types_action"):
        filter_label = ", ".join(resolved_opts["types_action"])

    if filter_label:
        profile = deepcopy(profile)
        profile["label"] = filter_label
        profile["title_label"] = filter_label
        profile["presentation_scope"] = "filtre_thematique"
        
        safe_filter = _safe_type_usager_for_filename(filter_label) or "filtre"
        profile["out_subdir"] = f"bilan_{safe_filter}"

    if profile.get("id") == "global" and (resolved_opts.get("themes") or resolved_opts.get("domaines") or resolved_opts.get("types_action")):
        profile = deepcopy(profile)
        profile["analyse_PVe"] = False

    root = PROJECT_ROOT
    date_deb_ts = pd.to_datetime(date_deb)
    date_fin_ts = pd.to_datetime(date_fin)
    echelle_norm = str(echelle).strip()
    code_norm = str(code).strip()
    
    out_subdir = str(profile.get("out_subdir", f"bilan_{profile.get('id', 'global')}")).strip()
    if not out_subdir:
        out_subdir = "bilan_global"
    code_suffix = resolve_code_subdir_suffix(profile, code)
    if code_suffix:
        out_subdir = f"{out_subdir}_{code_suffix}"

        
    out_dir = get_out_dir(out_subdir)

    from core.configuration_journalisation import add_file_handler
    add_file_handler(out_dir)

    print(f"Bilan « {profile.get('label', 'global')} »")
    print(f"Période : du {date_deb_ts.date():%d/%m/%Y} au {date_fin_ts.date():%d/%m/%Y}")
    
    ventilation_mode, vent_type, seuil_jours, duree_jours = _resolve_ventilation_mode_from_profile(
        profile,
        date_deb_ts=date_deb_ts,
        date_fin_ts=date_fin_ts,
    )

    print("[1/5] Chargement des données...")
    with Spinner():
        point = load_point_ctrl(root, echelle=echelle_norm, code=code_norm, date_deb=date_deb_ts, date_fin=date_fin_ts)
        pa = load_pa(root, date_deb=date_deb_ts, date_fin=date_fin_ts)
        pej = load_pej(
            root,
            echelle=echelle_norm, code=code_norm,
            date_deb=date_deb_ts,
            date_fin=date_fin_ts,
        )
        pve = (
            load_pve(root, echelle=echelle_norm, code=code_norm, date_deb=date_deb_ts, date_fin=date_fin_ts)
            if profile.get("analyse_PVe", True)
            else pd.DataFrame()
        )
        
        mots_cles = resolved_opts.get("mots_cles")
        if mots_cles:
            point, pej, pa, pve = _apply_rech_av_filter(point, pej, pa, pve, root, mots_cles)

        # Fusion des faits/localisations pour pej pour disposer des colonnes DOMAINE et THEME avant filtrage
        if not pej.empty:
            from core.common.chargeurs_donnees import merge_pej_faits_locations
            pej = merge_pej_faits_locations(pej, root, echelle_norm, code_norm, natinf_list=profile.get("natinf_pej", []), log=logging.getLogger("ofbilan.spatial"))

        # Filtrage par domaine et thème SNC (Options utilisateur / GUI)
        target_domains = resolved_opts.get("domaines")
        if target_domains:
            td_lower = {d.strip().lower() for d in target_domains if d.strip()}
            if td_lower:
                if not point.empty and "domaine" in point.columns:
                    point = point[point["domaine"].astype(str).str.strip().str.lower().isin(td_lower)].copy()
                if not pej.empty and "DOMAINE" in pej.columns:
                    pej = pej[pej["DOMAINE"].astype(str).str.strip().str.lower().isin(td_lower)].copy()
                if not pa.empty and "DOMAINE" in pa.columns:
                    pa = pa[pa["DOMAINE"].astype(str).str.strip().str.lower().isin(td_lower)].copy()

        target_themes = resolved_opts.get("themes")
        if target_themes:
            tt_lower = {t.strip().lower() for t in target_themes if t.strip()}
            if tt_lower:
                if not point.empty:
                    col_pt_theme = "theme" if "theme" in point.columns else ("type_actio" if "type_actio" in point.columns else None)
                    if col_pt_theme:
                        point = point[point[col_pt_theme].astype(str).str.strip().str.lower().apply(
                            lambda val: any(t in str(val) for t in tt_lower) if val else False
                        )].copy()
                if not pej.empty:
                    col_pej_theme = "THEME" if "THEME" in pej.columns else ("TYPE_ACTION" if "TYPE_ACTION" in pej.columns else None)
                    if col_pej_theme:
                        pej = pej[pej[col_pej_theme].astype(str).str.strip().str.lower().apply(
                            lambda val: any(t in str(val) for t in tt_lower) if val else False
                        )].copy()
                if not pa.empty:
                    col_pa_theme = "THEME" if "THEME" in pa.columns else ("TYPE_ACTION" if "TYPE_ACTION" in pa.columns else None)
                    if col_pa_theme:
                        pa = pa[pa[col_pa_theme].astype(str).str.strip().str.lower().apply(
                            lambda val: any(t in str(val) for t in tt_lower) if val else False
                        )].copy()
                if not pve.empty:
                    col_pve_theme = "theme" if "theme" in pve.columns else ("THEME" if "THEME" in pve.columns else None)
                    if col_pve_theme:
                        pve = pve[pve[col_pve_theme].astype(str).str.strip().str.lower().apply(
                            lambda val: any(t in str(val) for t in tt_lower) if val else False
                        )].copy()

        target_types_action = resolved_opts.get("types_action")
        if target_types_action:
            ta_lower = {ta.strip().lower() for ta in target_types_action if ta.strip()}
            if ta_lower:
                if not point.empty:
                    col_pt_ta = "type_actio" if "type_actio" in point.columns else ("type_action" if "type_action" in point.columns else None)
                    if col_pt_ta:
                        point = point[point[col_pt_ta].astype(str).str.strip().str.lower().apply(
                            lambda val: any(ta in str(val) for ta in ta_lower) if val else False
                        )].copy()
                if not pej.empty:
                    col_pej_ta = "TYPE_ACTION" if "TYPE_ACTION" in pej.columns else ("TYPE_ACTIO" if "TYPE_ACTIO" in pej.columns else None)
                    if col_pej_ta:
                        pej = pej[pej[col_pej_ta].astype(str).str.strip().str.lower().apply(
                            lambda val: any(ta in str(val) for ta in ta_lower) if val else False
                        )].copy()
                if not pa.empty:
                    col_pa_ta = "TYPE_ACTION" if "TYPE_ACTION" in pa.columns else ("TYPE_ACTIO" if "TYPE_ACTIO" in pa.columns else None)
                    if col_pa_ta:
                        pa = pa[pa[col_pa_ta].astype(str).str.strip().str.lower().apply(
                            lambda val: any(ta in str(val) for ta in ta_lower) if val else False
                        )].copy()
                if not pve.empty:
                    col_pve_ta = "type_actio" if "type_actio" in pve.columns else ("TYPE_ACTION" if "TYPE_ACTION" in pve.columns else None)
                    if col_pve_ta:
                        pve = pve[pve[col_pve_ta].astype(str).str.strip().str.lower().apply(
                            lambda val: any(ta in str(val) for ta in ta_lower) if val else False
                        )].copy()

    spatial_log = logging.getLogger("ofbilan.spatial")
    if not point.empty:
        point = ensure_insee_from_communes_shp(
            point, root, context="bilan global — points de contrôle", log=spatial_log
        )
    if not pve.empty:
        pve = ensure_insee_from_communes_shp(
            pve, root, context="bilan global — PVe", log=spatial_log
        )

    print(f"[2/5] Regroupement et calcul des indicateurs (Période : {ventilation_mode})...")
    with Spinner():
        gdf_faits = None
        try:
            from core.common.chargeurs_donnees import get_points_infrac_pj_path, read_vector_attributes
            path_faits = get_points_infrac_pj_path(root)
            if path_faits.exists():
                try:
                    import geopandas as _gpd
                    gdf_raw = _gpd.read_file(path_faits)
                    if "x_infrac" not in gdf_raw.columns and "geometry" in gdf_raw.columns:
                        gdf_raw["x_infrac"] = gdf_raw.geometry.x
                        gdf_raw["y_infrac"] = gdf_raw.geometry.y
                    gdf_faits = pd.DataFrame(gdf_raw.drop(columns=["geometry"], errors="ignore"))
                except Exception:
                    gdf_faits = read_vector_attributes(path_faits)
        except Exception:
            gdf_faits = None

        def _run_agg_for_context(pts, pjs, pas, pvs, out):
            import inspect
            agg_kwargs = dict(
                profile=profile,
                root=root,
                point=pts,
                pa=pas,
                pej=pjs,
                pve=pvs,
                out_dir=out,
                echelle=echelle_norm, code=code_norm,
                ventilation_mode=ventilation_mode,
                date_deb=date_deb_ts,
                date_fin=date_fin_ts,
            )
            sig = inspect.signature(run_aggregations)
            if "gdf_faits" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                agg_kwargs["gdf_faits"] = gdf_faits
            run_aggregations(**agg_kwargs)

        if echelle_norm == "pnf":
            point_f, pej_f, pa_f, pve_f = _apply_restrict_geo_pnf(point, pej, pa, pve, root, spatial_log)
            _run_agg_for_context(point_f, pej_f, pa_f, pve_f, out_dir)

            def _filter_by_dept(df, d):
                if df.empty: return df
                insee_s = _coalesced_insee_for_pnf_mask(df)
                return df[insee_s.notna() & insee_s.astype(str).str.startswith(d)].copy()

            out_dir_21 = out_dir / "21"
            out_dir_21.mkdir(exist_ok=True, parents=True)
            _run_agg_for_context(
                _filter_by_dept(point_f, "21"), _filter_by_dept(pej_f, "21"),
                _filter_by_dept(pa_f, "21"), _filter_by_dept(pve_f, "21"), out_dir_21
            )

            out_dir_52 = out_dir / "52"
            out_dir_52.mkdir(exist_ok=True, parents=True)
            _run_agg_for_context(
                _filter_by_dept(point_f, "52"), _filter_by_dept(pej_f, "52"),
                _filter_by_dept(pa_f, "52"), _filter_by_dept(pve_f, "52"), out_dir_52
            )
        else:
            _run_agg_for_context(point, pej, pa, pve, out_dir)

    # Export GeoPackage local au pipeline global (Lot 3 - Filtrage Spatial)
    try:
        import geopandas as gpd
        gpkg_logger = logging.getLogger(__name__)
        
        prefix = f"{profile.get('id', 'global')}_{code_norm}"
        carto_dir = get_carto_temp_dir()
        carto_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. GPKG pour point_ctrl
        if not point.empty:
            df_pts = point.copy()
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
                        gpkg_logger.warning(f"Impossible de centrer les points de contrôle orphelins : {e_geom}")
                mask_geo = df_pts["_lon"].notna() & df_pts["_lat"].notna() & (df_pts["_lon"] != 0) & (df_pts["_lat"] != 0)
                if mask_geo.any():
                    gdf_pts = gpd.GeoDataFrame(
                        df_pts[mask_geo],
                        geometry=gpd.points_from_xy(df_pts.loc[mask_geo, "_lon"], df_pts.loc[mask_geo, "_lat"]),
                        crs="EPSG:4326"
                    )
                    gdf_pts.columns = [str(c).lower() for c in gdf_pts.columns]
                    gdf_pts = gdf_pts.loc[:, ~gdf_pts.columns.duplicated()].copy()
                    for col in gdf_pts.select_dtypes(include=['datetime64[ns, UTC]', 'datetime64[ns]', 'datetime64']).columns:
                        gdf_pts[col] = gdf_pts[col].astype(str)
                    if "num_depart" in gdf_pts.columns:
                        gdf_pts["num_depart"] = gdf_pts["num_depart"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
                    if "domaine" not in gdf_pts.columns:
                        gdf_pts["domaine"] = "Hors domaine"
                    else:
                        gdf_pts["domaine"] = gdf_pts["domaine"].fillna("Hors domaine")
                    if "type_usager" not in gdf_pts.columns:
                        alt_col = next((c for c in ["usager", "type_usager_cible", "types_usager_cible", "cat_usager"] if c in gdf_pts.columns), None)
                        gdf_pts["type_usager"] = gdf_pts[alt_col] if alt_col else "Autre"
                    gpkg_path_pts = carto_dir / f"controles_{prefix}_export_automatique.gpkg"
                    gdf_pts = _sanitize_gdf_for_gpkg(gdf_pts)
                    gdf_pts.to_file(gpkg_path_pts, driver="GPKG")
                    gpkg_logger.info(f"Couche géographique Contrôles générée pour QGIS : {gpkg_path_pts} ({mask_geo.sum()} points)")
        
        # 2. GPKG pour PVe
        if not pve.empty:
            df_geo = pve.copy()
            if "inf_gps_long" in df_geo.columns and "inf_gps_lat" in df_geo.columns:
                df_geo["_lon"] = pd.to_numeric(df_geo["inf_gps_long"], errors="coerce")
                df_geo["_lat"] = pd.to_numeric(df_geo["inf_gps_lat"], errors="coerce")
                
                missing = df_geo["_lon"].isna() | df_geo["_lat"].isna() | (df_geo["_lon"] == 0) | (df_geo["_lat"] == 0)
                if missing.any():
                    try:
                        dict_x, dict_y = get_communes_centroids_dicts(root)
                        df_geo["insee_str"] = df_geo.get("INF-INSEE", pd.Series(dtype=str)).astype(str).str.zfill(5)
                        df_geo.loc[missing, "_lon"] = df_geo.loc[missing, "insee_str"].map(dict_x)
                        df_geo.loc[missing, "_lat"] = df_geo.loc[missing, "insee_str"].map(dict_y)
                    except Exception as e_geom:
                        gpkg_logger.warning(f"Impossible de centrer les PVe orphelins : {e_geom}")
                
                mask_geo = df_geo["_lon"].notna() & df_geo["_lat"].notna() & (df_geo["_lon"] != 0) & (df_geo["_lat"] != 0)
                if mask_geo.any():
                    gdf = gpd.GeoDataFrame(
                        df_geo[mask_geo],
                        geometry=gpd.points_from_xy(df_geo.loc[mask_geo, "_lon"], df_geo.loc[mask_geo, "_lat"]),
                        crs="EPSG:4326"
                    )
                    gdf = _sanitize_gdf_for_gpkg(gdf)
                    gpkg_path = carto_dir / f"pve_{prefix}_export_automatique.gpkg"
                    gdf.to_file(gpkg_path, driver="GPKG")
                    gpkg_logger.info(f"Couche géographique PVe générée pour QGIS : {gpkg_path} ({mask_geo.sum()} points)")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Impossible d'exporter les couches QGIS (global) : {e}")

    # ── Cartographie ──
    resolved_opts = _finalize_cartes_selection(
        profile,
        resolved_opts,
        options,
        date_deb=date_deb,
        date_fin=date_fin,
        echelle=echelle, code=code,
        target_dir=out_dir,
    )

    from core.common.carte_helper import ensure_maps_for_profiles
    from core.common.cartographie_config import resolve_qgis_profile_ids

    profil_id = str(profile.get("id", "global"))
    map_profiles = resolve_qgis_profile_ids(profile, profil_id, resolved_opts)
    
    # Injection des mots-clés dans la définition du profil pour transmission au moteur QGIS
    mots_cles = resolved_opts.get("mots_cles")
    if mots_cles:
        if "filter" not in profile or not isinstance(profile["filter"], dict):
            profile["filter"] = {}
        profile["filter"]["keywords"] = mots_cles

    if resolved_opts.get("cartes", False) and map_profiles:
        print("[3/5] Préparation des cartes de localisation...")
        try:
            if not resolved_opts.get("_maps_already_generated"):
                gabarit_id_opt = options.get("gabarit")
                from core.common.chargeur_gabarits import load_gabarit
                g_data = load_gabarit(gabarit_id_opt) if gabarit_id_opt else None
                brochure_opt = options.get("brochure")
                if brochure_opt is True:
                    is_brochure_mode = True
                elif brochure_opt is False:
                    is_brochure_mode = False
                else:
                    layout_mode = (profile or {}).get("layout_mode") or "standard"
                    is_brochure_mode = layout_mode in ("brochure", "brochure_custom") or gabarit_id_opt in ("srp_r27", "brochure_defaut")
                ensure_maps_for_profiles(
                    map_profiles,
                    date_deb=date_deb,
                    date_fin=date_fin,
                    echelle=echelle, code=code,
                    bilan_profiles={profil_id: profile},
                    target_dir=out_dir,
                    diffusion=str(resolved_opts.get("diffusion", "externe")),
                    force_regen=False,
                    is_brochure=is_brochure_mode,
                    gabarit_data=g_data,
                )
        except Exception as e:
            logger = logging.getLogger("ofbilan.engine")
            logger.warning("Cartes profils : %s", e)
    else:
        print("[3/5] Préparation des cartes de localisation (Désactivé)...")

    prompt_cartography_integration(
        root=root,
        profile=profile,
        profil_id=profil_id,
        resolved_opts=resolved_opts,
        echelle=echelle,
        code=code,
        target_dir=out_dir,
    )

    if resolved_opts.get("cartes_seules"):
        print("Option --cartes-seules active : arrêt avant la génération du PDF.")
        return 0

    print("[4/5] Exportation des tableaux de résultats (CSV / Excel)...")
    if resolved_opts.get("excel") or options.get("excel"):
        try:
            from core.common.excel_exporter import export_bilan_excel
            excel_prefix = str(profile.get("id", "global")).strip()
            code_suffix = f"_{code_norm}" if code_norm else ""
            excel_filename = f"bilan_{excel_prefix}_{echelle_norm}{code_suffix}_{date_deb_ts.year}.xlsx"
            
            depts_target = [code_norm] if echelle_norm == "departement" else None
            excel_path = export_bilan_excel(
                out_dir=out_dir,
                df_detail=point,
                echelle=echelle_norm,
                code=code_norm,
                depts=depts_target,
                filename=excel_filename
            )
            if excel_path:
                print(f"  ✅ Classeur Excel disponible : {excel_path}")
        except Exception as e_excel:
            logger.warning("Échec de la génération Excel moteur : %s", e_excel)
    print("  Tableaux exportés.")

    print("[5/5] Mise en page et création du rapport PDF...")
    with Spinner():
        pdf_prefix = str(profile.get("id", "global")).strip()
        filter_label = None
        if resolved_opts.get("themes"):
            filter_label = ", ".join(resolved_opts["themes"])
        elif resolved_opts.get("domaines"):
            filter_label = ", ".join(resolved_opts["domaines"])
        elif resolved_opts.get("types_action"):
            filter_label = ", ".join(resolved_opts["types_action"])
        if filter_label:
            safe_filter = _safe_type_usager_for_filename(filter_label) or "filtre"
            pdf_prefix = safe_filter

        format_sortie = (options or {}).get("format_sortie") or resolved_opts.get("format_sortie")
        if not format_sortie:
            if bool(resolved_opts.get("brochure")) or (options and bool(options.get("brochure"))):
                format_sortie = "brochure"
            else:
                format_sortie = "complet"

        base_kwargs: dict = {
            "profile": profile,
            "date_deb": date_deb_ts,
            "date_fin": date_fin_ts,
            "echelle": echelle_norm,
            "code": code_norm,
            "ventilation_mode": ventilation_mode,
            "chart_preset": chart_preset,
            "diffusion": str(resolved_opts.get("diffusion", "externe")),
            "cartes": bool(resolved_opts.get("cartes", False)),
        }
        import inspect

        def _call_pdf(is_broch: bool, out_fname: str) -> None:
            kw = dict(base_kwargs)
            kw["output_filename"] = out_fname
            opts_copy = dict(resolved_opts)
            opts_copy["brochure"] = is_broch
            if "brochure" in inspect.signature(generate_pdf_impl).parameters:
                kw["brochure"] = is_broch
            if "cli_options" in inspect.signature(generate_pdf_impl).parameters:
                kw["cli_options"] = opts_copy
            if "gabarit" in inspect.signature(generate_pdf_impl).parameters:
                kw["gabarit"] = resolved_opts.get("gabarit")
            generate_pdf_impl(out_dir, **kw)

        fn_complet = f"bilan_{pdf_prefix}_{code_norm}.pdf" if code_norm else f"bilan_{pdf_prefix}.pdf"
        fn_brochure = f"bilan_{pdf_prefix}_{code_norm}_brochure.pdf" if code_norm else f"bilan_{pdf_prefix}_brochure.pdf"

        if format_sortie == "brochure":
            _call_pdf(True, fn_brochure)
        elif format_sortie == "les_deux":
            _call_pdf(False, fn_complet)
            _call_pdf(True, fn_brochure)
        else:
            _call_pdf(False, fn_complet)

    print(f"\nTerminé ! Rapport disponible dans : {out_dir}")
    print(_message_fin_generation_pdf(profile, out_subdir, resolved_opts=resolved_opts, out_dir=out_dir))
    return 0


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
    except Exception as exc:
        # En cas d'échec (clip absent, droits, etc.), on ne bloque pas le bilan.
        _log.debug("Copie presse-papiers (clip) indisponible: %s", exc)


def _finalize_cartes_selection(
    profile: dict,
    resolved_opts: dict,
    cli_options: dict | None,
    *,
    date_deb: str | None = None,
    date_fin: str | None = None,
    echelle: str | None = None,
    code: str | None = None,
    target_dir: Path | None = None,
) -> dict:
    """Résout la sélection de cartes (catalogue) et tente de générer les PNG manquants."""
    if not resolved_opts.get("cartes", False) or not has_cartography_catalog(profile):
        profile.pop("_cartes_selection", None)
        return resolved_opts

    selection = resolve_cartes_selection(profile, resolved_opts)
    sel_cfg = (profile.get("options") or {}).get("cartes_selection") or {}
    cli = cli_options or {}
    if (
        isinstance(sel_cfg, dict)
        and sel_cfg.get("ask", False)
        and "cartes_profil" not in cli
        and "cartes_selection" not in cli
        and sys.stdin.isatty()
    ):
        selection = ask_cartes_selection(profile, selection)
        if cli_options is not None:
            cli_options["cartes_selection"] = selection

    profile["_cartes_selection"] = selection
    resolved_opts["cartes_selection"] = selection
    if selection:
        profil_id = str(profile.get("id", "")).strip()
        bilan_key = profil_id or "global"
        gabarit_id_opt = (cli_options or {}).get("gabarit") or resolved_opts.get("gabarit")
        from core.common.chargeur_gabarits import load_gabarit
        g_data = load_gabarit(gabarit_id_opt) if gabarit_id_opt else None
        is_brochure_mode = (
            bool((cli_options or {}).get("brochure"))
            or bool(resolved_opts.get("brochure"))
        )
        maps_to_gen = selection
        if is_brochure_mode:
            # En mode brochure, seule la carte des résultats (ou la 1re compatible) est nécessaire
            brochure_maps = [s for s in selection if "resultat" in s]
            maps_to_gen = brochure_maps[:1] if brochure_maps else selection[:1]
            resolved_opts["cartes_selection"] = maps_to_gen
            profile["_cartes_selection"] = maps_to_gen

        ensure_maps_for_profiles(
            maps_to_gen,
            date_deb=date_deb,
            date_fin=date_fin,
            echelle=echelle, code=code,
            bilan_profiles={bilan_key: profile},
            target_dir=target_dir,
            diffusion=str(resolved_opts.get("diffusion", "externe")),
            force_regen=True,
            is_brochure=is_brochure_mode,
            gabarit_data=g_data,
        )
        resolved_opts["_maps_already_generated"] = True
    return resolved_opts


def resolve_profile_map_id(profile: dict, profil_id: str) -> str:
    """Identifiant cartographique pour retrouver les PNG (profil global, thématique, usager ciblé)."""
    existing = profile.get("_map_id")
    if existing:
        return str(existing).strip()
    if str(profile.get("pipeline", "")).strip().lower() == "global":
        return str(profil_id).strip() or "global"
    targets = (profile.get("filter", {}) or {}).get("type_usager_target") or []
    if profil_id == "types_usager_cible" and targets:
        codes = [_short_type_usager_code(t) for t in targets]
        return "_".join([c for c in codes if c]) or profil_id
    return profil_id


def prompt_cartography_integration(
    *,
    root: Path,
    profile: dict,
    profil_id: str,
    resolved_opts: dict,
    map_id: str | None = None,
    echelle: str | None = None,
    code: str | None = None,
    target_dir: Path | None = None,
) -> None:
    """
    Pause interactive : dossier et noms de fichiers attendus pour les cartes du PDF.

    Même comportement pour tous les profils (global et thématiques) si ``--cartes``
    et terminal interactif.
    """
    if not resolved_opts.get("cartes", False) or not sys.stdin.isatty():
        return

    cartes_dir = target_dir if target_dir else get_cartes_dir()
    scope = str(profile.get("presentation_scope", "thematique")).strip() or "thematique"
    pres_cfg = resolve_pdf_presentation_config(
        root, scope=scope, profile_id=profil_id
    ).get("effective", {})

    if has_cartography_catalog(profile):
        selection = profile.get("_cartes_selection") or resolve_cartes_selection(profile, resolved_opts)
        from core.cartographie.pochoir_helper import is_map_valid_for_dept
        from core.common.carte_helper import qgis_available
        from core.common.utilitaires_metier import resolve_carto_dept_code

        carto_dept = resolve_carto_dept_code(
            echelle or "departement",
            code or "21",
        )

        expected_names = expected_map_filenames_for_selection(profile, selection)

        def _carte_ready(name: str) -> bool:
            path = cartes_dir / name
            if path.exists() and is_map_valid_for_dept(path, carto_dept):
                return True
            p = Path(name)
            brochure_path = cartes_dir / f"{p.stem}_brochure{p.suffix}"
            return brochure_path.exists() and is_map_valid_for_dept(brochure_path, carto_dept)

        all_exist = all(_carte_ready(name) for name in expected_names) if expected_names else False
        if all_exist:
            return

        section_hint = "section 5 (localisation cartographique — une carte par page)"
        print("\n--- Cartographie ---")
        print(f"Pour intégrer les cartes dans le bilan PDF ({section_hint}) :")
        print(f"  - dossier : {cartes_dir}")
        print(f"  - département attendu : {carto_dept}")
        if not qgis_available():
            print(
                "  - QGIS (PyQGIS) non détecté dans cet interpréteur Python : "
                "génération automatique impossible. Utilisez scripts/lancement/generer_cartes.bat "
                f"avec --echelle departement --code {carto_dept}, ou déposez les PNG avec "
                f"marqueur .{carto_dept}.dept (rétrocompat. : dept. 21 sans marqueur)."
            )
        for name in expected_names:
            print(f"  - fichier : {name}")
        if len(expected_names) >= 2:
            print("  - les cartes sélectionnées seront affichées une par page.")
        if expected_names:
            _copy_to_clipboard(expected_names[0])
            print("(Le premier nom de fichier attendu a été copié dans le presse-papiers si possible.)")
        try:
            input("Appuyez sur Entrée une fois les cartes prêtes (renommées et placées au bon endroit)... ")
        except (EOFError, KeyboardInterrupt):
            pass
        return

    map_id = (map_id or resolve_profile_map_id(profile, profil_id)).strip() or profil_id
    profile["_map_id"] = map_id
    expected_names = expected_map_filenames(
        map_id,
        profile=profile,
        presentation_cfg=pres_cfg if isinstance(pres_cfg, dict) else None,
    )
    
    # If no specific patterns are found, expected_map_filenames defaults to [carte_..., carte_..._2]
    # We can check if at least the first one exists.
    actual_paths = resolve_profile_map_paths(
        map_id,
        profile=profile,
        presentation_cfg=pres_cfg if isinstance(pres_cfg, dict) else None,
        target_dir=cartes_dir,
    )
    # Ignorer le cache pour forcer la régénération systématique à chaque execution
    pass

    if not expected_names:
        expected_names = [f"carte_{map_id}.png", f"carte_{map_id}_2.png"]

    if str(profile.get("id", "")).strip() == "synthese_activite_PA_PJ":
        section_hint = (
            "section 5 du bilan détaillé et page 1 de la brochure "
            "(encadré « Cartographie de l'activité »)"
        )
    elif resolved_opts.get("brochure"):
        section_hint = "page 1 de la brochure (encadré « Cartographie de l'activité »)"
    elif scope == "global":
        section_hint = "section 5 (localisation cartographique)"
    else:
        section_hint = "section 5 du bilan (une carte par page)"
    print("\n--- Cartographie ---")
    print(f"Pour intégrer les cartes dans le bilan PDF ({section_hint}) :")
    print(f"  - dossier : {cartes_dir}")
    for name in expected_names:
        print(f"  - fichier : {name}")
    layout_hint = resolve_map_layout(
        profile=profile,
        presentation_cfg=pres_cfg if isinstance(pres_cfg, dict) else None,
    )
    if len(expected_names) >= 2:
        if str(profile.get("id", "")).strip() == "synthese_activite_PA_PJ":
            dispo = "côte à côte dans la brochure"
        elif resolved_opts.get("brochure"):
            dispo = "côte à côte"
        else:
            dispo = "une carte par page (PDF standard)"
        print(f"  - si les deux PNG sont présents, elles seront affichées {dispo}.")

    _copy_to_clipboard(expected_names[0])
    print("(Le premier nom de fichier attendu a été copié dans le presse-papiers si possible.)")

    try:
        input("Appuyez sur Entrée une fois la carte prête (renommée et placée au bon endroit)... ")
    except (EOFError, KeyboardInterrupt):
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
    from core.common.prompt_periode import ask_choice_list
    options_config = profile.get("options", {})
    result = dict(current_opts)

    askable = [
        (key, cfg)
        for key, cfg in options_config.items()
        if isinstance(cfg, dict)
        and cfg.get("ask", False)
        and key not in current_opts
        and cfg.get("type") != "multi_choice"
        and not isinstance(cfg.get("default"), list)
    ]
    if not askable:
        return result

    print("\n--- Options du bilan ---")
    for key, cfg in askable:
        label = cfg.get("label", key)
        default = cfg.get("default", False)
        
        # Option de type booléen
        if isinstance(default, bool):
            choices = [(True, "Oui"), (False, "Non")]
            result[key] = ask_choice_list(label, choices, default_val=default)
        else:
            # Fallback pour d'autres types potentiels
            default_hint = f" [{default}]" if default else ""
            try:
                answer = input(f"  {label} ?{default_hint} : ").strip()
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if answer == "":
                result[key] = default
            else:
                result[key] = answer

    return result


# ═══════════════════════════════════════════════════════════════════════════
# 2bis. Sélection interactive des types d'usagers cibles
# ═══════════════════════════════════════════════════════════════════════════


def _load_types_usagers_labels(root: Path) -> list[str]:
    """Charge la liste des catégories de type d'usager (ref/programme/tables_reference/types_usagers.csv)."""
    csv_path = ref_programme(root) / "tables_reference" / "types_usagers.csv"
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


# ═══════════════════════════════════════════════════════════════════════════
# 4. Filtrage métier et spatial (délégué à core.engine.filtres_profil)
# ═══════════════════════════════════════════════════════════════════════════

from core.engine.filtres_profil import (
    _apply_rech_av_filter,
    _apply_restrict_geo_pnf,
    _apply_restrict_geo_tub,
    _coalesced_insee_for_pnf_mask,
    _derive_keywords,
    _filter_agrainage,
    _filter_by_keywords,
    _filter_by_type_usager,
    _filter_pa,
    _filter_pej,
    _filter_point_ctrl,
    _filter_pve,
    _filter_tub,
    _get_insee_col,
    _mask_insee_in_pnf_codes,
    _profile_sans_cible_type_usager,
    _run_spatial_analyses,
    _safe_type_usager_for_filename,
    _short_type_usager_code,
    filter_by_agent_service,
)

# ═══════════════════════════════════════════════════════════════════════════
# 5. Agrégations et exports CSV (délégué à core.engine.agregations_thematiques)
# ═══════════════════════════════════════════════════════════════════════════

from core.engine.agregations_thematiques import (
    _export_csv,
    _run_aggregations,
    run_thematic_aggregations,
)


# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
# 6. Génération PDF thématique (déléguée à core.engine.generation_pdf_thematique)
# ═══════════════════════════════════════════════════════════════════════════

from core.engine.sections_thematiques import (
    _chart_pie_compact_legend_kw,
    _pct_table_cell,
    _pdf_section_activite_par_types_usagers,
    _pdf_section_pression_controle_usagers,
    render_thematic_profil_sections,
)
from core.engine.generation_pdf_thematique import (
    _generate_pdf,
    _roman,
    generate_thematic_pdf_report,
)


# ═══════════════════════════════════════════════════════════════════════════
# 7. Point d'entrée principal
# ═══════════════════════════════════════════════════════════════════════════

def run_engine(
    profil_id: str,
    date_deb: str,
    date_fin: str,
    echelle: str,
    code: str,
    options: dict | None = None,
) -> int:
    """Point d'entrée unique du moteur thématique unifié."""
    options = options or {}
    root = PROJECT_ROOT
    profile = load_profile_config(root, profil_id)
    pipeline = str(profile.get("pipeline", "thematic")).strip().lower()
    pipeline_handlers = {
        "global": _run_global_profile_via_yaml,
        "thematic": lambda p, d0, d1, ec, co, opts: _run_engine_thematic_pipeline(
            str(p.get("id", profil_id)), d0, d1, ec, co, opts
        ),
    }
    if pipeline not in pipeline_handlers:
        raise ValueError(f"Pipeline inconnu dans le profil '{profil_id}': {pipeline}")
    return pipeline_handlers[pipeline](profile, date_deb, date_fin, echelle, code, options)


def _run_engine_thematic_pipeline(
    profil_id: str,
    date_deb: str,
    date_fin: str,
    echelle: str,
    code: str,
    options: dict | None = None,
) -> int:
    options = options or {}
    root = PROJECT_ROOT
    profile = load_profile_config(root, profil_id)
    chart_preset = options.pop("chart_preset", None)
    cfg = BilanConfig.from_strings(date_deb, date_fin, echelle=echelle, code=code, root=root)
    
    out_subdir = str(profile.get("out_subdir", f"bilan_{profil_id}")).strip()
    if not out_subdir:
        out_subdir = "bilan_global"
    code_suffix = resolve_code_subdir_suffix(profile, code)
    if code_suffix:
        out_subdir = f"{out_subdir}_{code_suffix}"

        
    out_dir = cfg.get_out(out_subdir)

    from core.configuration_journalisation import add_file_handler
    add_file_handler(out_dir)

    label = profile["label"]
    sources = profile["sources"]

    # Le paramètre de profil analyse_PVe permet de désactiver complètement
    # l'analyse et l'affichage liés aux PVe (chargement, agrégations, PDF).
    analyse_pve = bool(profile.get("analyse_PVe", True))
    if not analyse_pve:
        sources["pve"] = False

    print(f"Bilan « {label} » — {cfg.perimetre_name}")
    print(f"Période : du {cfg.date_deb.date():%d/%m/%Y} au {cfg.date_fin.date():%d/%m/%Y}")

    # Déterminer le mode de ventilation temporelle depuis le profil YAML
    ventilation_mode, vent_type, seuil_jours, duree_jours = _resolve_ventilation_mode_from_profile(
        profile,
        date_deb_ts=cfg.date_deb,
        date_fin_ts=cfg.date_fin,
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
    map_id = resolve_profile_map_id(profile, profil_id)
    profile["_map_id"] = map_id


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
    print("[1/6] Chargement des données...")
    with Spinner():
        point = (
            load_point_ctrl(root, echelle=echelle, code=code, date_deb=date_deb, date_fin=date_fin)
            if sources.get("point_ctrl", True)
            else pd.DataFrame()
        )
        pej = (
            load_pej(
                root,
                echelle=echelle, code=code,
                date_deb=date_deb,
                date_fin=date_fin,
            )
            if sources.get("pej", True)
            else pd.DataFrame()
        )
        pa = (
            load_pa(root, date_deb=date_deb, date_fin=date_fin)
            if sources.get("pa", True)
            else pd.DataFrame()
        )
        pve = (
            load_pve(root, echelle=echelle, code=code, date_deb=date_deb, date_fin=date_fin)
            if sources.get("pve", True)
            else pd.DataFrame()
        )
        
        mots_cles = resolved_opts.get("mots_cles")
        if mots_cles:
            point, pej, pa, pve = _apply_rech_av_filter(point, pej, pa, pve, root, mots_cles)

    # ── Filtrage ──
    point_ctrl_perimetre: pd.DataFrame | None = None
    if profil_id == "types_usager_cible" and not point.empty:
        point_ctrl_perimetre = _filter_point_ctrl(
            point, _profile_sans_cible_type_usager(profile)
        )

    print("[2/6] Filtrage thématique...")
    with Spinner():
        point_filtered = _filter_point_ctrl(point, profile) if not point.empty else point
        pej_filtered = _filter_pej(pej, profile, cfg, point_filtered) if not pej.empty else pej
        if not pej_filtered.empty and sources.get("pej", True):
            pej_filtered = merge_pej_faits_locations(
                pej_filtered, root, echelle, code, natinf_list=profile.get("natinf_pej", []), log=logging.getLogger("ofbilan.spatial")
            )
        pa_filtered = _filter_pa(pa, profile, cfg, point_filtered) if not pa.empty else pa
        pve_filtered = _filter_pve(pve, profile) if not pve.empty else pve

        # Filtrage par domaine et thème SNC (Options utilisateur)
        target_domains = resolved_opts.get("domaines")
        if target_domains:
            # Normaliser la recherche
            td_lower = {d.strip().lower() for d in target_domains if d.strip()}
            if td_lower:
                if not point_filtered.empty and "domaine" in point_filtered.columns:
                    point_filtered = point_filtered[point_filtered["domaine"].astype(str).str.strip().str.lower().isin(td_lower)].copy()
                if not pej_filtered.empty and "DOMAINE" in pej_filtered.columns:
                    pej_filtered = pej_filtered[pej_filtered["DOMAINE"].astype(str).str.strip().str.lower().isin(td_lower)].copy()
                if not pa_filtered.empty and "DOMAINE" in pa_filtered.columns:
                    pa_filtered = pa_filtered[pa_filtered["DOMAINE"].astype(str).str.strip().str.lower().isin(td_lower)].copy()

        target_themes = resolved_opts.get("themes")
        if target_themes:
            tt_lower = {t.strip().lower() for t in target_themes if t.strip()}
            if tt_lower:
                if not point_filtered.empty:
                    col_pt_theme = "theme" if "theme" in point_filtered.columns else ("type_actio" if "type_actio" in point_filtered.columns else None)
                    if col_pt_theme:
                        point_filtered = point_filtered[point_filtered[col_pt_theme].astype(str).str.strip().str.lower().apply(
                            lambda val: any(val in t or t in val for t in tt_lower) if val else False
                        )].copy()
                if not pej_filtered.empty:
                    col_pej_theme = "THEME" if "THEME" in pej_filtered.columns else ("TYPE_ACTION" if "TYPE_ACTION" in pej_filtered.columns else None)
                    if col_pej_theme:
                        pej_filtered = pej_filtered[pej_filtered[col_pej_theme].astype(str).str.strip().str.lower().apply(
                            lambda val: any(val in t or t in val for t in tt_lower) if val else False
                        )].copy()
                if not pa_filtered.empty:
                    col_pa_theme = "THEME" if "THEME" in pa_filtered.columns else ("TYPE_ACTION" if "TYPE_ACTION" in pa_filtered.columns else None)
                    if col_pa_theme:
                        pa_filtered = pa_filtered[pa_filtered[col_pa_theme].astype(str).str.strip().str.lower().apply(
                            lambda val: any(val in t or t in val for t in tt_lower) if val else False
                        )].copy()
                if not pve_filtered.empty:
                    col_pve_theme = "theme" if "theme" in pve_filtered.columns else ("THEME" if "THEME" in pve_filtered.columns else None)
                    if col_pve_theme:
                        pve_filtered = pve_filtered[pve_filtered[col_pve_theme].astype(str).str.strip().str.lower().apply(
                            lambda val: any(val in t or t in val for t in tt_lower) if val else False
                        )].copy()

    spatial_log = logging.getLogger("ofbilan.spatial")
    restrict_geo_val = str(profile.get("restrict_geo") or "").strip().lower()
    if restrict_geo_val == "pnf":
        with Spinner():
            point_filtered, pej_filtered, pa_filtered, pve_filtered = _apply_restrict_geo_pnf(
                point_filtered, pej_filtered, pa_filtered, pve_filtered, root, spatial_log
            )
            if point_ctrl_perimetre is not None and not point_ctrl_perimetre.empty:
                point_ctrl_perimetre, _, _, _ = _apply_restrict_geo_pnf(
                    point_ctrl_perimetre,
                    pej_filtered,
                    pa_filtered,
                    pve_filtered,
                    root,
                    spatial_log,
                )
    elif restrict_geo_val == "tub":
        with Spinner():
            point_filtered, pej_filtered, pa_filtered, pve_filtered = _apply_restrict_geo_tub(
                point_filtered, pej_filtered, pa_filtered, pve_filtered, root, spatial_log
            )
            if point_ctrl_perimetre is not None and not point_ctrl_perimetre.empty:
                point_ctrl_perimetre, _, _, _ = _apply_restrict_geo_tub(
                    point_ctrl_perimetre,
                    pd.DataFrame(),
                    pd.DataFrame(),
                    pd.DataFrame(),
                    root,
                    spatial_log,
                )

    if not pej_filtered.empty and sources.get("pej", True):
        pej_filtered = enrich_pej_commune_from_faits_coordinates(
            pej_filtered, root, log=spatial_log
        )
        if (
            resolved_opts.get("pnf")
            or resolved_opts.get("tub")
            or str(profile.get("restrict_geo") or "").strip().lower() == "pnf"
        ):
            pej_filtered = enrich_with_pnforet_sig_zones(
                pej_filtered, root, context="PEJ (coordonnées FAITS)", log=spatial_log
            )
            pej_filtered = overlay_pnf_zone_from_communes_pnf_csv(
                pej_filtered, root, log=spatial_log
            )

    # ── INSEE commune (jointure communes.shp si besoin) ──
    if resolved_opts.get("pnf") or resolved_opts.get("tub"):
        if not point_filtered.empty:
            point_filtered = ensure_insee_from_communes_shp(
                point_filtered, root, context="points de contrôle", log=spatial_log
            )
        if point_ctrl_perimetre is not None and not point_ctrl_perimetre.empty:
            point_ctrl_perimetre = ensure_insee_from_communes_shp(
                point_ctrl_perimetre,
                root,
                context="points de contrôle",
                log=spatial_log,
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
        point_filtered = overlay_pnf_zone_from_communes_pnf_csv(
            point_filtered, root, log=spatial_log
        )
    if point_ctrl_perimetre is not None and not point_ctrl_perimetre.empty and (
        resolved_opts.get("pnf")
        or resolved_opts.get("tub")
        or str(profile.get("restrict_geo") or "").strip().lower() == "pnf"
    ):
        point_ctrl_perimetre = enrich_with_pnforet_sig_zones(
            point_ctrl_perimetre, root, context="points de contrôle", log=spatial_log
        )
        point_ctrl_perimetre = overlay_pnf_zone_from_communes_pnf_csv(
            point_ctrl_perimetre, root, log=spatial_log
        )
    if not pve_filtered.empty and (
        resolved_opts.get("pnf")
        or resolved_opts.get("tub")
        or str(profile.get("restrict_geo") or "").strip().lower() == "pnf"
    ):
        pve_filtered = enrich_with_pnforet_sig_zones(
            pve_filtered, root, context="PVe", log=spatial_log
        )
        pve_filtered = overlay_pnf_zone_from_communes_pnf_csv(
            pve_filtered, root, log=spatial_log
        )

    # ── Analyses spatiales ──
    print(f"[3/6] Regroupement et calcul des indicateurs (Période : {ventilation_mode})...")
    with Spinner():
        spatial, point_filtered = _run_spatial_analyses(
            point_filtered, pej_filtered, pve_filtered,
            resolved_opts, cfg, profil_id=profil_id,
            restrict_geo=str(profile.get("restrict_geo") or "").strip().lower(),
        )

    # ── Agrégations ──
    with Spinner():
        results = _run_aggregations(
            point_filtered, pej_filtered, pa_filtered, pve_filtered,
            profile, resolved_opts, spatial, ventilation_mode=ventilation_mode,
            point_ctrl_perimetre=point_ctrl_perimetre,
        )

        restrict_geo_val = str(profile.get("restrict_geo") or "").strip().lower()
        if restrict_geo_val == "pnf":
            from core.engine.orchestrateur_profils import _coalesced_insee_for_pnf_mask
            def _filter_by_dept(df, d):
                if df.empty: return df
                insee_s = _coalesced_insee_for_pnf_mask(df)
                return df[insee_s.notna() & insee_s.astype(str).str.startswith(d)].copy()

            # 21
            pt_21 = _filter_by_dept(point_filtered, "21")
            pej_21 = _filter_by_dept(pej_filtered, "21")
            pa_21 = _filter_by_dept(pa_filtered, "21")
            pve_21 = _filter_by_dept(pve_filtered, "21")
            res_21 = _run_aggregations(
                pt_21, pej_21, pa_21, pve_21,
                profile, resolved_opts, spatial, ventilation_mode=ventilation_mode,
                point_ctrl_perimetre=_filter_by_dept(point_ctrl_perimetre, "21") if point_ctrl_perimetre is not None else None,
            )
            # Re-calculer les counts globaux car _run_aggregations ne retourne pas les counts initiaux (ils sont dans _run_spatial_analyses ou au-dessus)
            res_21["_nb_localisations"] = len(pt_21)
            res_21["_nb_pej"] = len(pej_21)
            res_21["_nb_pa"] = len(pa_21)
            res_21["_nb_pve"] = len(pve_21)

            # 52
            pt_52 = _filter_by_dept(point_filtered, "52")
            pej_52 = _filter_by_dept(pej_filtered, "52")
            pa_52 = _filter_by_dept(pa_filtered, "52")
            pve_52 = _filter_by_dept(pve_filtered, "52")
            res_52 = _run_aggregations(
                pt_52, pej_52, pa_52, pve_52,
                profile, resolved_opts, spatial, ventilation_mode=ventilation_mode,
                point_ctrl_perimetre=_filter_by_dept(point_ctrl_perimetre, "52") if point_ctrl_perimetre is not None else None,
            )
            res_52["_nb_localisations"] = len(pt_52)
            res_52["_nb_pej"] = len(pej_52)
            res_52["_nb_pa"] = len(pa_52)
            res_52["_nb_pve"] = len(pve_52)

            results["results_21"] = res_21
            results["results_52"] = res_52

    if str(echelle).strip().lower() == "region":
        from core.engine.agregations_region import analyse_region_par_departement
        analyse_region_par_departement(
            point_filtered, pa_filtered, pej_filtered, pve_filtered,
            echelle, code, out_dir, pej_global=pej, profil_id=profil_id
        )

    # ── Export CSV ──
    print("[4/6] Exportation des tableaux de résultats (CSV)...")
    with Spinner():
        _export_csv(
            results, point_filtered, pej_filtered, pa_filtered, pve_filtered,
            out_dir, profile, code_norm=str(code).strip(),
        )
        if str(profile.get("restrict_geo") or "").strip().lower() == "pnf":
            if "results_21" in results:
                out_dir_21 = out_dir / "21"
                out_dir_21.mkdir(exist_ok=True, parents=True)
                _export_csv(
                    results["results_21"], pt_21, pej_21, pa_21, pve_21,
                    out_dir_21, profile, code_norm="21",
                )
            if "results_52" in results:
                out_dir_52 = out_dir / "52"
                out_dir_52.mkdir(exist_ok=True, parents=True)
                _export_csv(
                    results["results_52"], pt_52, pej_52, pa_52, pve_52,
                    out_dir_52, profile, code_norm="52",
                )

    # ── Cartographie ──
    if resolved_opts.get("cartes", False):
        print("[5/6] Préparation des cartes de localisation...")
    else:
        print("[5/6] Préparation des cartes de localisation (Désactivé)...")

    resolved_opts = _finalize_cartes_selection(
        profile,
        resolved_opts,
        options,
        date_deb=date_deb,
        date_fin=date_fin,
        echelle=echelle, code=code,
        target_dir=out_dir,
    )

    from core.common.carte_helper import ensure_maps_for_profiles
    from core.common.cartographie_config import resolve_qgis_profile_ids

    map_profiles = resolve_qgis_profile_ids(profile, profil_id, resolved_opts)

    if resolved_opts.get("cartes", False) and map_profiles and not resolved_opts.get("_maps_already_generated"):
        try:
            gabarit_id_opt = (options or {}).get("gabarit") or resolved_opts.get("gabarit")
            from core.common.chargeur_gabarits import load_gabarit
            g_data = load_gabarit(gabarit_id_opt) if gabarit_id_opt else None
            is_brochure_mode = (
                bool((options or {}).get("brochure"))
                or bool(resolved_opts.get("brochure"))
            )
            ensure_maps_for_profiles(
                map_profiles,
                date_deb=date_deb,
                date_fin=date_fin,
                echelle=echelle, code=code,
                bilan_profiles={profil_id: profile},
                target_dir=out_dir,
                diffusion=str(resolved_opts.get("diffusion", "externe")),
                force_regen=False,
                is_brochure=is_brochure_mode,
                gabarit_data=g_data,
            )
        except Exception as e:
            logger = logging.getLogger("ofbilan.engine")
            logger.warning("Cartes profils : %s", e)

    prompt_cartography_integration(
        root=root,
        profile=profile,
        profil_id=profil_id,
        resolved_opts=resolved_opts,
        map_id=map_id,
        echelle=echelle,
        code=code,
        target_dir=out_dir,
    )

    if resolved_opts.get("cartes_seules"):
        print("  Option --cartes-seules active : arrêt avant la génération du PDF.")
        return 0

    # ── PDF ──
    print("[6/6] Mise en page et création du rapport PDF...")
    with Spinner():
        format_sortie = (options or {}).get("format_sortie") or resolved_opts.get("format_sortie")
        if not format_sortie:
            if bool((options or {}).get("brochure")) or bool(resolved_opts.get("brochure")):
                format_sortie = "brochure"
            else:
                format_sortie = "complet"

        code_norm = str(cfg.code).strip()
        gabarit_id_opt = (options or {}).get("gabarit") or resolved_opts.get("gabarit")

        def _do_generate_brochure() -> None:
            from core.engine.generation_pdf_synthese_brochure import (
                generate_synthese_brochure_pdf_report,
            )
            out_filename = (
                f"bilan_{profil_id}_{code_norm}_brochure.pdf"
                if code_norm
                else f"bilan_{profil_id}_brochure.pdf"
            )
            generate_synthese_brochure_pdf_report(
                out_dir,
                profile=profile,
                date_deb=pd.to_datetime(date_deb),
                date_fin=pd.to_datetime(date_fin),
                echelle=echelle,
                code=code,
                ventilation_mode=ventilation_mode,
                output_filename=out_filename,
                diffusion=str(resolved_opts.get("diffusion", "externe")),
                cartes=bool(resolved_opts.get("cartes", True)),
                gabarit=gabarit_id_opt or "gabarit_defaut",
                results=results,
            )

        if format_sortie == "brochure":
            _do_generate_brochure()
        elif format_sortie == "les_deux":
            _generate_pdf(results, out_dir, profile, cfg, resolved_opts, ventilation_mode=ventilation_mode)
            _do_generate_brochure()
        else:
            _generate_pdf(results, out_dir, profile, cfg, resolved_opts, ventilation_mode=ventilation_mode)

    print(f"\nTerminé ! Rapport disponible dans : {out_dir}")
    return 0