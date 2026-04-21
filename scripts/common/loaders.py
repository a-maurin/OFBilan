"""Chargement des données OSCEAN (points de contrôle, PEJ, PA, PVe, PNF, TUB, infractions PJ)."""
import logging
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union

import geopandas as gpd
import pandas as pd
import re

from scripts.common.utils import filtre_periode

logger = logging.getLogger(__name__)

# Ordre aligné sur bilan_thematique_engine._get_insee_col
_INSEE_COL_PRIORITY: Tuple[str, ...] = (
    "insee_comm",
    "insee_commun",
    "INSEE_COM",
    "INF-INSEE",
)


def _gpkg_engine() -> str:
    """Detect the best available GPKG engine once (pyogrio > fiona)."""
    try:
        import pyogrio  # noqa: F401
        return "pyogrio"
    except ImportError:
        return "fiona"


_GPKG_ENGINE: str = _gpkg_engine()


def _find_latest_dated_file(directory: Path, prefix: str, exts: Tuple[str, ...]) -> Path:
    """
    Retourne, parmi les fichiers de `directory` commençant par `prefix` et se
    terminant par l'une des extensions de `exts`, celui dont la date suffixe
    (format YYYYMMDD) est la plus récente.
    """
    latest_path: Path | None = None
    latest_date: str | None = None

    for ext in exts:
        pattern = f"{prefix}*{ext}"
        for p in directory.glob(pattern):
            m = re.match(re.escape(prefix) + r"(\d{8})", p.name)
            if not m:
                continue
            date_str = m.group(1)
            if latest_date is None or date_str > latest_date:
                latest_date = date_str
                latest_path = p

    if latest_path is None:
        raise FileNotFoundError(
            f"Aucun fichier trouvé dans {directory} pour le préfixe '{prefix}' "
            f"et les extensions {exts}."
        )
    return latest_path


def load_point_ctrl(
    root: Path,
    dept_code: Optional[str] = None,
    date_deb: Optional[Union[str, pd.Timestamp]] = None,
    date_fin: Optional[Union[str, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """
    Charge les points de contrôle OSCEAN à partir des fichiers
    point_ctrl_YYYYMMDD_wgs84.gpkg présents dans sources/sig.

    Pour chaque année, seul le GPKG le plus récent (date suffixe la plus élevée)
    est utilisé, afin d'éviter les doublons liés aux extractions mensuelles.

    Si dept_code, date_deb et date_fin sont fournis, seules les années
    recouvrant la période sont chargées et les lignes sont filtrées par
    département et période (accélère l'analyse sur sources nationales).
    """
    sources_sig = root / "sources" / "sig"
    if not sources_sig.exists():
        raise FileNotFoundError(
            f"Le dossier des données SIG sources n'existe pas : {sources_sig}"
        )

    # Nouvelle organisation : les fichiers de points de contrôle sont rangés par année
    # dans des sous-dossiers de type points_de_ctrl_OSCEAN_YYYY sous sources/sig.
    # Les couches peuvent être au format GPKG ou SHP et le nommage peut varier
    # (point/pts/pt, controle/ctrl, etc.). On doit donc rechercher de manière
    # plus souple que le strict pattern point_ctrl_YYYYMMDD_wgs84.*
    candidates: List[Path] = []
    year_dirs = [
        d
        for d in sources_sig.glob("points_de_ctrl_OSCEAN_*")
        if d.is_dir()
    ]
    for d in year_dirs:
        for ext in (".gpkg", ".shp"):
            # Noms usuels : point_ctrl_..., pts_ctrl_..., pt_controle_..., etc.
            for pat in ("*point*ctrl*",
                        "*pts*ctrl*",
                        "*pt*ctrl*",
                        "*ctrl*"):
                candidates.extend(d.glob(f"{pat}{ext}"))

    # Rétrocompatibilité : si aucun sous-dossier n'est trouvé (ancienne arborescence
    # ou environnement non migré), on cherche encore à la racine de sources/sig.
    if not candidates:
        candidates = []
        for ext in (".gpkg", ".shp"):
            for pat in ("*point*ctrl*",
                        "*pts*ctrl*",
                        "*pt*ctrl*",
                        "*ctrl*"):
                candidates.extend(sources_sig.glob(f"{pat}{ext}"))

    if not candidates:
        raise FileNotFoundError(
            f"Aucun fichier de points de contrôle (formats GPKG/SHP) trouvé dans {sources_sig} "
            f"(attendus dans des sous-dossiers points_de_ctrl_OSCEAN_YYYY ou à la racine, "
            f"avec un nom contenant 'ctrl')."
        )

    # Vérification des chemins et fichiers
    for candidate in candidates:
        if not candidate.is_file():
            raise FileNotFoundError(f"Le fichier {candidate} n'est pas un fichier valide.")

    # Sélectionner, pour chaque année, le fichier au suffixe de date le plus récent.
    per_year: dict[str, tuple[str, Path]] = {}
    for p in candidates:
        # Extraire une date au format YYYYMMDD à partir du nom de fichier, même si
        # elle est écrite sous la forme YYYY_MM_DD ou similaire. On concatène
        # tous les chiffres présents et on prend les 8 premiers si possible.
        digits = "".join(ch for ch in p.stem if ch.isdigit())
        if len(digits) >= 8:
            date_str = digits[:8]
            year = date_str[:4]
        elif len(digits) >= 4:
            # Fallback : le nom de fichier ne contient pas de date YYYYMMDD
            # complète (ex. point_ctrl_2024_wgs84 → "202484", 6 chiffres).
            # On tente d'extraire l'année depuis le nom du dossier parent
            # (points_de_ctrl_OSCEAN_YYYY) puis, à défaut, depuis les 4
            # premiers chiffres du nom de fichier.
            parent_digits = re.findall(r"\d{4}", p.parent.name)
            if parent_digits:
                year = parent_digits[-1]
            else:
                year = digits[:4]
            date_str = f"{year}0101"
        else:
            continue
        cur = per_year.get(year)
        if cur is None or date_str > cur[0]:
            per_year[year] = (date_str, p)

    # Restreindre aux années couvrant la période demandée si date_deb/date_fin fournis
    if date_deb is not None and date_fin is not None:
        try:
            deb_ts = pd.to_datetime(date_deb)
            fin_ts = pd.to_datetime(date_fin)
            year_min, year_max = deb_ts.year, fin_ts.year
            filtered = {y: t for y, t in per_year.items() if year_min <= int(y) <= year_max}
            if filtered:
                per_year = filtered
        except Exception as e:
            raise ValueError(f"Erreur de conversion des dates : {e}")

    selected_paths = [tpl[1] for tpl in per_year.values()]
    frames: List[pd.DataFrame] = []
    for path in selected_paths:
        engine = _GPKG_ENGINE
        
        # Filtre à la lecture par département si possible (réduit le volume chargé)
        if dept_code is not None:
            try:
                gdf = gpd.read_file(
                    path,
                    engine=engine,
                    where=f"num_depart = '{str(dept_code).strip()}'",
                )
            except Exception as e:
                raise RuntimeError(f"Erreur de lecture du fichier GPKG avec filtre : {e}")
        else:
            try:
                gdf = gpd.read_file(path, engine=engine)
            except Exception as e:
                raise RuntimeError(f"Erreur de lecture du fichier GPKG : {e}")
        df = pd.DataFrame(gdf.drop(columns=["geometry"], errors="ignore"))
        df.columns = [str(c).split(",")[0].strip() for c in df.columns]
        
        # Validation des colonnes requises
        required_columns = ["date_ctrl", "dc_id", "num_depart"]
        for col in required_columns:
            if col not in df.columns:
                raise KeyError(f"La colonne '{col}' est absente des données point_ctrl_*")
        
        if "date_ctrl" in df.columns:
            df["date_ctrl"] = pd.to_datetime(
                df["date_ctrl"], dayfirst=True, errors="coerce", format="mixed"
            )

        # Alias de colonnes : le reste du code travaille avec des noms
        # uniformisés, malgré les variations entre GPKG/SHP et les versions.
        # - nom_dossier / nom_dossie
        # - type_action / type_actio
        # - Résultat / RESULTAT / resultat
        # - nom_commun / nom_commune
        # - type_usage / type_usager
        # - nature_con / nature_controle
        # - plan_contr / plan_controle
        # - avis_pasbi / avis_patbi / avis_patbiodiv

        # Nom du dossier
        if "nom_dossier" in df.columns and "nom_dossie" not in df.columns:
            df["nom_dossie"] = df["nom_dossier"]

        # Type d'action
        if "type_action" in df.columns and "type_actio" not in df.columns:
            df["type_actio"] = df["type_action"]

        # Variantes du champ résultat
        if "resultat" not in df.columns:
            if "Résultat" in df.columns:
                df["resultat"] = df["Résultat"]
            elif "RESULTAT" in df.columns:
                df["resultat"] = df["RESULTAT"]

        # Nom de commune : harmoniser vers nom_commun
        if "nom_commune" in df.columns and "nom_commun" not in df.columns:
            df["nom_commun"] = df["nom_commune"]

        # Type d'usager / usage : créer les deux alias pour faciliter les usages
        if "type_usager" in df.columns and "type_usage" not in df.columns:
            df["type_usage"] = df["type_usager"]
        if "type_usage" in df.columns and "type_usager" not in df.columns:
            df["type_usager"] = df["type_usage"]

        # Nature du contrôle : nature_con (tronqué) / nature_controle (complet)
        if "nature_controle" in df.columns and "nature_con" not in df.columns:
            df["nature_con"] = df["nature_controle"]
        if "nature_con" in df.columns and "nature_controle" not in df.columns:
            df["nature_controle"] = df["nature_con"]

        # Plan de contrôle : plan_contr / plan_controle
        if "plan_controle" in df.columns and "plan_contr" not in df.columns:
            df["plan_contr"] = df["plan_controle"]
        if "plan_contr" in df.columns and "plan_controle" not in df.columns:
            df["plan_controle"] = df["plan_contr"]

        # Avis patrimoine / biodiversité
        avis_src = None
        for cand in ("avis_patbiodiv", "avis_patbi", "avis_pasbi"):
            if cand in df.columns:
                avis_src = cand
                break
        if avis_src is not None:
            if "avis_patbiodiv" not in df.columns:
                df["avis_patbiodiv"] = df[avis_src]
            if "avis_patbi" not in df.columns:
                df["avis_patbi"] = df[avis_src]
            if "avis_pasbi" not in df.columns:
                df["avis_pasbi"] = df[avis_src]

        frames.append(df)

    if not frames:
        raise FileNotFoundError(
            f"Aucun enregistrement valide trouvé dans les GPKG point_ctrl de {sources_sig}"
        )

    df_all = pd.concat(frames, ignore_index=True)
    dedup_cols = [c for c in ["dc_id", "date_ctrl", "x", "y"] if c in df_all.columns]
    if dedup_cols:
        df_all.drop_duplicates(subset=dedup_cols, keep="first", inplace=True)
    if "date_ctrl" not in df_all.columns:
        raise KeyError("La colonne 'date_ctrl' est absente des données point_ctrl_*")

    # Filtrage optionnel par département et période
    if dept_code is not None and "num_depart" in df_all.columns:
        df_all = df_all[df_all["num_depart"].astype(str).str.strip() == str(dept_code).strip()].copy()
    if date_deb is not None and date_fin is not None:
        try:
            deb_ts = pd.to_datetime(date_deb)
            fin_ts = pd.to_datetime(date_fin)
        except ValueError as e:
            raise ValueError(f"Format de date invalide : {e}")
        df_all = filtre_periode(df_all, "date_ctrl", deb_ts, fin_ts)

    return df_all


def load_pej(
    root: Path,
    dept_code: Optional[str] = None,
    date_deb: Optional[Union[str, pd.Timestamp]] = None,
    date_fin: Optional[Union[str, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """
    Charge le classeur ODS des procédures d'enquête judiciaire le plus récent
    (suivi_procedure_enq_judiciaire_YYYYMMDD.ods dans sources/) et prépare
    ``DATE_REF`` (affichages / tris) ainsi que ``RECAP_DATE_INIT_PJ``.

    Le **décompte et le filtre de période** s'appuient uniquement sur le classeur
    ODS, sur ``RECAP_DATE_INIT_PJ`` (et non plus sur la coalescence DATE_REF).

    Les localisations ne sont pas dans l'ODS : les joindre via
    ``merge_pej_faits_locations`` sur la couche ``localisation_infrac_FAITS_*``.
    Voir ref/README_sources.md § 2.2.
    """
    sources = root / "sources"
    prefix = "suivi_procedure_enq_judiciaire_"
    path = _find_latest_dated_file(sources, prefix, (".ods",))
    df = pd.read_excel(path, dtype=str, engine="odf")
    # Alias pour compatibilité si le classeur utilise "NATINF" au lieu de "NATINF_PEJ"
    if "NATINF" in df.columns and "NATINF_PEJ" not in df.columns:
        df["NATINF_PEJ"] = df["NATINF"]
    # Alias "type_usager" pour filtrage des bilans usagers ciblés
    # (dans le classeur PEJ, la colonne s'appelle typiquement "USAGER").
    if "type_usager" not in df.columns:
        for cand in ("USAGER", "USGAER", "TYPE_USAGER", "Type usager", "type_usager"):
            if cand in df.columns:
                df["type_usager"] = df[cand]
                break
    df["DATE_CONSTATATION"] = pd.to_datetime(df["DATE_CONSTATATION"], errors="coerce")
    df["DATE_OUVERTURE_PROCEDURE"] = pd.to_datetime(
        df["DATE_OUVERTURE_PROCEDURE"], errors="coerce"
    )
    if "RECAP_DATE_INIT_PJ" not in df.columns:
        if date_deb is not None and date_fin is not None:
            raise KeyError(
                "Colonne RECAP_DATE_INIT_PJ absente du classeur PEJ — "
                "obligatoire pour le filtre de période."
            )
        df["RECAP_DATE_INIT_PJ"] = pd.NaT
    else:
        df["RECAP_DATE_INIT_PJ"] = pd.to_datetime(df["RECAP_DATE_INIT_PJ"], errors="coerce")
    df["DATE_REF"] = (
        df["DATE_CONSTATATION"]
        .fillna(df["DATE_OUVERTURE_PROCEDURE"])
        .fillna(df["RECAP_DATE_INIT_PJ"])
    )
    if date_deb is not None and date_fin is not None:
        deb_ts = pd.to_datetime(date_deb)
        fin_ts = pd.to_datetime(date_fin)
        df = filtre_periode(df, "RECAP_DATE_INIT_PJ", deb_ts, fin_ts)
    return df


def load_pa(
    root: Path,
    dept_code: Optional[str] = None,
    date_deb: Optional[Union[str, pd.Timestamp]] = None,
    date_fin: Optional[Union[str, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """
    Charge le classeur ODS des procédures administratives le plus récent
    (suivi_procedure_administrative_YYYYMMDD.ods dans sources/) et prépare
    la colonne DATE_REF.

    Si date_deb et date_fin sont fournis, filtre les lignes sur cette période.

    Localisation spatiale : ce classeur ne sert pas de référence pour placer
    une PA dans le PNF. Pour un critère géographique, s'appuyer sur les
    points de contrôle OSCEAN (load_point_ctrl) : effectifs et localisations
    des PA alignés sur les contrôles dont resultat == « Manquement »
    (voir ref/README_sources.md § 2.5bis).
    """
    sources = root / "sources"
    path = _find_latest_dated_file(
        sources, "suivi_procedure_administrative_", (".ods",)
    )
    df = pd.read_excel(path, dtype=str, engine="odf")
    df["DATE_CONTROLE"] = pd.to_datetime(df["DATE_CONTROLE"], errors="coerce")
    df["DATE_DOSSIER"] = pd.to_datetime(df["DATE_DOSSIER"], errors="coerce")
    df["DATE_REF"] = df["DATE_CONTROLE"].fillna(df["DATE_DOSSIER"])
    if date_deb is not None and date_fin is not None:
        deb_ts = pd.to_datetime(date_deb)
        fin_ts = pd.to_datetime(date_fin)
        df = filtre_periode(df, "DATE_REF", deb_ts, fin_ts)
    return df


def _load_pnf_from_shp(root: Path) -> Optional[pd.DataFrame]:
    """
    Lit ref/sig/communes_pnf/communes_pnf.shp et renvoie un DataFrame au format attendu
    par load_tub_pnf_codes / merge PNF (colonne CODE_INSEE, optionnellement NOM).

    Retourne None si le fichier est absent ; lève une erreur explicite si le fichier
    existe mais qu'aucune colonne INSEE n'est reconnue.
    """
    shp = root / "ref" / "sig" / "communes_pnf" / "communes_pnf.shp"
    if not shp.exists():
        return None

    gdf = gpd.read_file(shp)
    if gdf.empty:
        return pd.DataFrame(columns=["CODE_INSEE"])

    insee_col = next(
        (
            c
            for c in (
                "INSEE_COM",
                "CODE_INSEE",
                "insee_comm",
                "INSEE",
                "code_insee",
                "INSEE_COM_M",
            )
            if c in gdf.columns
        ),
        None,
    )
    if insee_col is None:
        raise KeyError(
            f"Aucune colonne INSEE reconnue dans {shp} "
            f"(colonnes : {list(gdf.columns)} ; attendu p.ex. INSEE_COM ou CODE_INSEE)."
        )

    nom_col = next(
        (
            c
            for c in (
                "NOM_COM",
                "NOM",
                "nom_commune",
                "nom_commun",
                "LIBELLE",
                "libelle",
            )
            if c in gdf.columns
        ),
        None,
    )

    insee_series = (
        gdf[insee_col]
        .astype(str)
        .str.strip()
        .str.extract(r"(\d{1,5})", expand=False)
        .fillna("")
        .str.zfill(5)
    )
    out = pd.DataFrame({"CODE_INSEE": insee_series})
    if nom_col is not None:
        out["NOM"] = gdf[nom_col].astype(str).str.strip()

    out = out.drop_duplicates(subset=["CODE_INSEE"]).reset_index(drop=True)
    out = out[out["CODE_INSEE"].str.match(r"^[0-9]{5}$", na=False)]
    out = out[out["CODE_INSEE"].ne("00000")]
    return out


def load_pnf(root: Path) -> pd.DataFrame:
    """
    Charge la liste des communes PNF (référentiel).

    Ordre de priorité :
    1. Shapefile ref/sig/communes_pnf/communes_pnf.shp (attributs INSEE + optionnellement nom) ;
    2. Fichier communes_PNF.csv dans ref/ ou sources/.
    """
    try:
        from_shp = _load_pnf_from_shp(root)
    except KeyError:
        raise
    except Exception as e:
        shp = root / "ref" / "sig" / "communes_pnf" / "communes_pnf.shp"
        if shp.exists():
            raise RuntimeError(f"Lecture du shapefile PNF impossible ({shp}) : {e}") from e
        from_shp = None

    if from_shp is not None and not from_shp.empty:
        return from_shp

    for base in ("ref", "sources"):
        path = root / base / "communes_PNF.csv"
        if path.exists():
            df = pd.read_csv(path, sep=",", dtype=str)
            df["CODE_INSEE"] = df["CODE_INSEE"].astype(str).str.zfill(5)
            return df

    raise FileNotFoundError(
        "Référentiel PNF introuvable : ni ref/sig/communes_pnf/communes_pnf.shp (non vide), "
        "ni communes_PNF.csv dans ref/ ou sources/."
    )


def load_tub(root: Path) -> pd.DataFrame:
    """Charge la liste des communes TUB (référentiel). Cherche dans ref/ puis sources/."""
    for base in ("ref", "sources"):
        path = root / base / "tub_communes.csv"
        if path.exists():
            df = pd.read_csv(path, sep=";", dtype=str, encoding="latin-1")
            df["INSEE_COM"] = df["INSEE_COM"].astype(str).str.zfill(5)
            return df
    raise FileNotFoundError(
        "Aucun fichier tub_communes.csv trouvé dans ref/ ni sources/."
    )


def load_ref_themes_ctrl(root: Path) -> List[dict]:
    """
    Charge le référentiel des thèmes des contrôles (ref/ref_themes_ctrl.csv).
    Retourne une liste de dictionnaires {"id": ..., "label": ..., "ordre": ...}
    triée par ordre. Si le fichier est absent ou invalide, retourne une liste vide.
    """
    path = root / "ref" / "ref_themes_ctrl.csv"
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
        if df.empty:
            return []
        # Colonnes attendues : id, label, ordre
        if "id" not in df.columns:
            return []
        out = []
        for _, row in df.iterrows():
            id_val = str(row.get("id", "")).strip()
            if not id_val:
                continue
            label_val = str(row.get("label", id_val)).strip()
            ordre_val = row.get("ordre", "999")
            try:
                ordre_int = int(ordre_val) if ordre_val else 999
            except (ValueError, TypeError):
                ordre_int = 999
            out.append({"id": id_val, "label": label_val, "ordre": ordre_int})
        out.sort(key=lambda x: x["ordre"])
        return out
    except Exception:
        return []


def load_tub_pnf_codes(root: Path) -> Tuple[set, set]:
    """
    Charge les référentiels TUB et PNF et retourne les ensembles de codes INSEE
    (tub_codes, pnf_codes) pour les agrégations par zone. Utile pour réutiliser
    la même logique dans plusieurs bilans.
    """
    tub = load_tub(root)
    pnf = load_pnf(root)
    return set(tub["INSEE_COM"].unique()), set(pnf["CODE_INSEE"].unique())


def get_pnf_coeur_shp_path(root: Path) -> Path:
    """Chemin du shapefile « cœur de parc » PNF (Parc national de forêts)."""
    return root / "ref" / "sig" / "PNF" / "coeur_pnforets" / "Coeur_data_gouv_PNForets.shp"


def get_pnf_aoa_shp_path(root: Path) -> Path:
    """Chemin du shapefile de l'aire d'adhésion PNF (millésime 2021)."""
    return root / "ref" / "sig" / "PNF" / "aoa_2021_pnforets" / "AOA_2021_PNForets.shp"


def load_pnf_coeur_gdf(root: Path) -> gpd.GeoDataFrame:
    """Charge la couche polygonale du cœur de parc. GeoDataFrame vide si fichier absent."""
    path = get_pnf_coeur_shp_path(root)
    if not path.exists():
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=None)
    return gpd.read_file(path)


def load_pnf_aoa_gdf(root: Path) -> gpd.GeoDataFrame:
    """Charge la couche polygonale de l'aire d'adhésion. GeoDataFrame vide si fichier absent."""
    path = get_pnf_aoa_shp_path(root)
    if not path.exists():
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=None)
    return gpd.read_file(path)


def pnf_sig_union_membership_mask(
    df: pd.DataFrame,
    root: Path,
    *,
    log: Optional[logging.Logger] = None,
) -> pd.Series:
    """
    Pour chaque ligne avec coordonnées (x/y WGS84, inf_gps_*, ou geometry),
    indique si le point intersecte le cœur PNForêts et/ou l'aire d'adhésion SIG.

    Complète le filtre par liste de communes INSEE : une localisation peut être
    dans le parc sans que son code commune figure au référentiel tabulaire PNF.
    Retourne une série booléenne alignée sur ``df.index`` (False si SIG ou points absents).
    """
    lg = log or logger
    if df is None or df.empty:
        return pd.Series(False, index=df.index if df is not None else pd.RangeIndex(0))

    coeur = load_pnf_coeur_gdf(root)
    aoa = load_pnf_aoa_gdf(root)
    if coeur.empty and aoa.empty:
        return pd.Series(False, index=df.index)

    gdf_pts = _dataframe_with_xy_geometry(df)
    if gdf_pts is None:
        return pd.Series(False, index=df.index)

    coeur_u = _union_perimeter_geometry(coeur)
    aoa_u = _union_perimeter_geometry(aoa)
    if coeur_u is None and aoa_u is None:
        return pd.Series(False, index=df.index)

    ref_crs = None
    if coeur_u is not None and not coeur.empty and coeur.crs is not None:
        ref_crs = coeur.crs
    if ref_crs is None and aoa_u is not None and not aoa.empty and aoa.crs is not None:
        ref_crs = aoa.crs

    if gdf_pts.crs is None:
        gdf_pts = gdf_pts.set_crs(4326)
    if ref_crs is not None and gdf_pts.crs != ref_crs:
        gdf_pts = gdf_pts.to_crs(ref_crs)

    geom = gdf_pts.geometry
    valid = geom.notna() & ~geom.is_empty

    in_coeur = pd.Series(False, index=gdf_pts.index)
    if coeur_u is not None:
        in_coeur = geom.within(coeur_u) | geom.intersects(coeur_u)

    in_aoa = pd.Series(False, index=gdf_pts.index)
    if aoa_u is not None:
        in_aoa = geom.within(aoa_u) | geom.intersects(aoa_u)

    inside = valid & (in_coeur | in_aoa)
    n_in = int(inside.sum())
    if n_in:
        lg.info(
            "Périmètre PNF SIG : %s localisations dans cœur ou aire d'adhésion (hors filtre INSEE seul).",
            n_in,
        )
    return inside.reindex(df.index, fill_value=False)


def _union_perimeter_geometry(gdf: gpd.GeoDataFrame):
    """Fusionne les géométries d'une couche périmètre (MultiPolygon / Polygon)."""
    if gdf.empty:
        return None
    geoms = gdf.geometry.dropna()
    if geoms.empty:
        return None
    try:
        return geoms.union_all()
    except Exception:
        try:
            return geoms.unary_union
        except Exception:
            from shapely.ops import unary_union

            return unary_union(list(geoms))


def enrich_with_pnforet_sig_zones(
    df: pd.DataFrame,
    root: Path,
    *,
    context: str = "jeu de données",
    log: Optional[logging.Logger] = None,
    out_col: str = "pnf_zone_sig",
) -> pd.DataFrame:
    """
    Ajoute une colonne (par défaut `pnf_zone_sig`) : « Coeur_PNF », « Aire_adhesion_PNF »,
    « Hors_perimetres_sig » selon la position des points par rapport aux couches
    `ref/sig/PNF/coeur_pnforets/` et `ref/sig/PNF/aoa_2021_pnforets/`.

    Nécessite des coordonnées (`x`/`y` en WGS84, ou `geometry`, ou GPS PVe).
    Si les shapefiles sont absents ou sans géométrie exploitable, retourne `df` inchangé.
    """
    lg = log or logger
    if df is None or df.empty:
        return df

    coeur = load_pnf_coeur_gdf(root)
    aoa = load_pnf_aoa_gdf(root)
    if coeur.empty and aoa.empty:
        return df

    gdf_pts = _dataframe_with_xy_geometry(df)
    if gdf_pts is None:
        lg.info(
            "Périmètres PNF SIG : pas de coordonnées pour %s — %s non renseignée.",
            context,
            out_col,
        )
        return df

    coeur_u = _union_perimeter_geometry(coeur)
    aoa_u = _union_perimeter_geometry(aoa)
    if coeur_u is None and aoa_u is None:
        return df

    ref_crs = None
    if coeur_u is not None and not coeur.empty and coeur.crs is not None:
        ref_crs = coeur.crs
    if ref_crs is None and aoa_u is not None and not aoa.empty and aoa.crs is not None:
        ref_crs = aoa.crs

    if gdf_pts.crs is None:
        gdf_pts = gdf_pts.set_crs(4326)
    if ref_crs is not None and gdf_pts.crs != ref_crs:
        gdf_pts = gdf_pts.to_crs(ref_crs)

    geom = gdf_pts.geometry
    valid = geom.notna() & ~geom.is_empty

    in_coeur = pd.Series(False, index=gdf_pts.index)
    if coeur_u is not None:
        in_coeur = geom.within(coeur_u) | geom.intersects(coeur_u)

    in_aoa = pd.Series(False, index=gdf_pts.index)
    if aoa_u is not None:
        in_aoa = geom.within(aoa_u) | geom.intersects(aoa_u)

    zone = pd.Series(pd.NA, index=gdf_pts.index, dtype="string")
    zone = zone.mask(~valid, pd.NA)
    zone = zone.mask(valid & in_coeur, "Coeur_PNF")
    adhesion = valid & ~in_coeur & in_aoa
    zone = zone.mask(adhesion, "Aire_adhesion_PNF")
    hors = valid & ~in_coeur & ~in_aoa
    zone = zone.mask(hors, "Hors_perimetres_sig")

    out = df.copy()
    out[out_col] = zone.values
    n_tagged = int(zone.notna().sum())
    lg.info(
        "Périmètres PNF SIG : %s — %s lignes classées (%s).",
        context,
        n_tagged,
        out_col,
    )
    return out


def load_communes_noms(root: Path) -> dict:
    """
    Charge la table de correspondance code INSEE → nom de commune.

    Source : ref/sig/communes_21/communes.csv (INSEE_COM, NOM_COM).
    Retourne un dictionnaire {code_insee_5chars: nom_commune}.
    Si le fichier est absent, retourne un dict vide (les PDF afficheront le code).
    """
    path = root / "ref" / "sig" / "communes_21" / "communes.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path, sep=";", dtype=str)
    # Colonnes possibles : première ligne = en-tête type "INSEE_COM,C,5" et "NOM_COM,C,50"
    code_col = next((c for c in df.columns if c.strip().startswith("INSEE_COM")), None)
    nom_col = next((c for c in df.columns if c.strip().startswith("NOM_COM")), None)
    if code_col is None or nom_col is None:
        code_col, nom_col = df.columns[0], df.columns[1]
    df[code_col] = df[code_col].astype(str).str.strip().str.zfill(5)
    return dict(zip(df[code_col], df[nom_col].astype(str).str.strip()))


def _load_communes_21_gdf(root: Path) -> gpd.GeoDataFrame:
    """
    Charge la couche des communes 21 et harmonise les colonnes de sortie:
    - insee_comm (code INSEE sur 5 caractères)
    - nom_commune (nom de la commune)
    """
    shp_path = root / "ref" / "sig" / "communes_21" / "communes.shp"
    if not shp_path.exists():
        raise FileNotFoundError(
            f"Le shapefile des communes est introuvable : {shp_path}"
        )

    gdf = gpd.read_file(shp_path)
    if gdf.empty:
        return gpd.GeoDataFrame(columns=["insee_comm", "nom_commune", "geometry"], geometry="geometry", crs=gdf.crs)

    insee_col = next(
        (c for c in ("INSEE_COM", "insee_comm", "INSEE", "code_insee", "CODE_INSEE") if c in gdf.columns),
        None,
    )
    nom_col = next(
        (c for c in ("NOM_COM", "nom_commune", "nom_commun", "NOM_COMMUNE", "NOM") if c in gdf.columns),
        None,
    )
    if insee_col is None or nom_col is None:
        raise KeyError(
            "Colonnes INSEE/nom introuvables dans communes.shp "
            "(attendues: INSEE_COM et NOM_COM ou équivalents)."
        )
    if "geometry" not in gdf.columns:
        raise KeyError("Aucune colonne 'geometry' dans la couche communes.shp.")

    out = gdf[[insee_col, nom_col, "geometry"]].copy()
    out = out.rename(columns={insee_col: "insee_comm", nom_col: "nom_commune"})
    out["insee_comm"] = out["insee_comm"].astype(str).str.strip().str.zfill(5)
    out["nom_commune"] = out["nom_commune"].astype(str).str.strip()
    out = out.dropna(subset=["geometry"])
    return gpd.GeoDataFrame(out, geometry="geometry", crs=gdf.crs)


def enrich_with_commune_from_geometry(
    df: Union[pd.DataFrame, gpd.GeoDataFrame],
    root: Path,
    geometry_col: str = "geometry",
    insee_col: str = "insee_comm",
    nom_col: str = "nom_commune",
    fill_only_missing: bool = True,
) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
    """
    Enrichit un jeu d'entités avec le code INSEE et le nom de commune via jointure spatiale.

    Règles:
    - si `insee_col`/`nom_col` existent déjà et `fill_only_missing=True`, seules les valeurs
      manquantes sont complétées;
    - sinon, les colonnes sont (re)calculées à partir de `ref/sig/communes_21/communes.shp`.
    """
    if geometry_col not in df.columns:
        raise KeyError(
            f"La colonne de géométrie '{geometry_col}' est absente des entités à enrichir."
        )

    communes = _load_communes_21_gdf(root)
    if communes.empty:
        enriched = df.copy()
        if insee_col not in enriched.columns:
            enriched[insee_col] = pd.NA
        if nom_col not in enriched.columns:
            enriched[nom_col] = pd.NA
        return enriched

    # Convertit en GeoDataFrame si nécessaire tout en conservant les colonnes initiales.
    gdf = df if isinstance(df, gpd.GeoDataFrame) else gpd.GeoDataFrame(df.copy(), geometry=geometry_col)

    if gdf.crs is None:
        # Hypothèse par défaut cohérente avec les autres chargeurs SIG.
        gdf = gdf.set_crs(epsg=4326)
    if communes.crs is None:
        communes = communes.set_crs(gdf.crs)
    elif gdf.crs != communes.crs:
        gdf = gdf.to_crs(communes.crs)

    left = gdf.copy()
    if insee_col not in left.columns:
        left[insee_col] = pd.NA
    if nom_col not in left.columns:
        left[nom_col] = pd.NA
    left["_row_id_tmp"] = range(len(left))

    # Évite les collisions de noms de colonnes pendant la jointure.
    join_left = left.drop(columns=[insee_col, nom_col], errors="ignore")
    joined = gpd.sjoin(
        join_left,
        communes[["insee_comm", "nom_commune", "geometry"]],
        how="left",
        predicate="within",
    )
    joined = joined.sort_values("_row_id_tmp").drop_duplicates(subset=["_row_id_tmp"], keep="first")
    joined = joined.set_index("_row_id_tmp")
    left = left.set_index("_row_id_tmp")

    if fill_only_missing:
        insee_join = joined["insee_comm"] if "insee_comm" in joined.columns else pd.Series(index=left.index, dtype="object")
        nom_join = joined["nom_commune"] if "nom_commune" in joined.columns else pd.Series(index=left.index, dtype="object")
        left[insee_col] = left[insee_col].where(left[insee_col].notna(), insee_join)
        left[nom_col] = left[nom_col].where(left[nom_col].notna(), nom_join)
    else:
        left[insee_col] = joined["insee_comm"] if "insee_comm" in joined.columns else pd.NA
        left[nom_col] = joined["nom_commune"] if "nom_commune" in joined.columns else pd.NA

    left[insee_col] = left[insee_col].astype("string").str.strip().str.zfill(5)
    left[nom_col] = left[nom_col].astype("string").str.strip()

    left = left.reset_index(drop=True)
    if isinstance(df, gpd.GeoDataFrame):
        return gpd.GeoDataFrame(left, geometry=geometry_col, crs=gdf.crs)
    return pd.DataFrame(left)


def _insee_cell_missing(v) -> bool:
    """True si la valeur n'est pas un code INSEE communal exploitable (5 chiffres)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return True
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "<na>"):
        return True
    digits = re.sub(r"\D", "", s)
    if len(digits) < 5:
        return True
    if digits == "00000":
        return True
    return False


def _first_insee_column(df: pd.DataFrame) -> Optional[str]:
    for c in _INSEE_COL_PRIORITY:
        if c in df.columns:
            return c
    return None


def _all_insee_filled(df: pd.DataFrame, col: str) -> bool:
    if col not in df.columns or df.empty:
        return False
    return not df[col].map(_insee_cell_missing).any()


def _dataframe_with_xy_geometry(df: pd.DataFrame) -> Optional[gpd.GeoDataFrame]:
    """Construit un GeoDataFrame (WGS84) depuis x/y ou lat/lon PVe si possible."""
    if "geometry" in df.columns:
        try:
            gdf = gpd.GeoDataFrame(df.copy(), geometry="geometry", crs=None)
            if gdf.crs is None:
                gdf = gdf.set_crs(epsg=4326)
            return gdf
        except Exception:
            return None

    if "x" in df.columns and "y" in df.columns:
        x = pd.to_numeric(df["x"], errors="coerce")
        y = pd.to_numeric(df["y"], errors="coerce")
        if x.notna().any() and y.notna().any():
            return gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(x, y), crs="EPSG:4326")

    if "inf_gps_lat" in df.columns and "inf_gps_long" in df.columns:
        lat = pd.to_numeric(df["inf_gps_lat"], errors="coerce")
        lon = pd.to_numeric(df["inf_gps_long"], errors="coerce")
        if lat.notna().any() and lon.notna().any():
            return gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(lon, lat), crs="EPSG:4326")

    return None


def ensure_insee_from_communes_shp(
    df: pd.DataFrame,
    root: Path,
    *,
    context: str = "jeu de données",
    log: Optional[logging.Logger] = None,
) -> pd.DataFrame:
    """
    Garantit une colonne `insee_comm` (et `nom_commune`) pour les analyses par commune
    (PNF, TUB, etc.) : normalise un code INSEE déjà présent ou complète via jointure spatiale
    avec `ref/sig/communes_21/communes.shp`.

    Les points de contrôle sans géométrie mais avec `x`/`y` sont convertis en points WGS84.
    Les PVe peuvent utiliser `inf_gps_lat` / `inf_gps_long` si `INF-INSEE` est absent ou incomplet.
    """
    lg = log or logger
    if df is None or df.empty:
        return df

    out = df.copy()
    if "insee_comm" not in out.columns:
        alt = _first_insee_column(out)
        if alt:
            out["insee_comm"] = out[alt]
        else:
            out["insee_comm"] = pd.NA

    if _all_insee_filled(out, "insee_comm"):
        out["insee_comm"] = (
            out["insee_comm"]
            .astype(str)
            .str.extract(r"(\d{1,5})", expand=False)
            .fillna("")
            .str.zfill(5)
        )
        out.loc[out["insee_comm"].isin(("", "00000")), "insee_comm"] = pd.NA
        return out

    gdf_try = _dataframe_with_xy_geometry(out)
    if gdf_try is None:
        lg.warning(
            "Impossible d'enrichir le code INSEE (%s) : pas de géométrie ni de x/y ou GPS exploitables.",
            context,
        )
        return out

    n_before = int(out["insee_comm"].map(_insee_cell_missing).sum())

    try:
        enriched = enrich_with_commune_from_geometry(
            gdf_try,
            root,
            geometry_col="geometry",
            insee_col="insee_comm",
            nom_col="nom_commune",
            fill_only_missing=True,
        )
    except FileNotFoundError as e:
        lg.warning("Couche communes indisponible pour %s : %s", context, e)
        return out
    except Exception as e:  # pragma: no cover - dépend des données SIG
        lg.warning("Échec jointure spatiale communes (%s) : %s", context, e)
        return out

    if isinstance(enriched, gpd.GeoDataFrame):
        drop_geom = enriched.drop(columns=["geometry"], errors="ignore")
        out = pd.DataFrame(drop_geom)
    else:
        out = enriched.drop(columns=["geometry"], errors="ignore") if "geometry" in enriched.columns else enriched

    n_after = int(out["insee_comm"].map(_insee_cell_missing).sum()) if "insee_comm" in out.columns else n_before
    lg.info(
        "Communes (shp) : %s — lignes sans INSEE : %s -> %s (jointure spatiale).",
        context,
        n_before,
        n_after,
    )
    return out


def load_communes_centroides(root: Path) -> pd.DataFrame:
    """
    Charge la table des communes de France avec centroïdes et renvoie un
    DataFrame minimal (code_insee, lat, lon) pour les jointures.

    Source par défaut : ref/sig/communes-france-2025.csv
    - code_insee : code INSEE commune (5 caractères, zfill(5))
    - lat / lon : coordonnées du centroïde (colonnes latitude_centre / longitude_centre)
    """
    ref_dir = root / "ref" / "sig"
    csv_path = ref_dir / "communes-france-2025.csv"

    if csv_path.exists():
        df = pd.read_csv(csv_path, sep=",", dtype=str)
        # Harmonisation du code INSEE
        insee_col = None
        for cand in ["code_insee", "CODE_INSEE", "insee"]:
            if cand in df.columns:
                insee_col = cand
                break
        if insee_col is None:
            raise KeyError(
                "Aucune colonne de code INSEE trouvée dans communes-france-2025.csv "
                "(attendu: code_insee / CODE_INSEE / insee)"
            )

        lat_col = None
        lon_col = None
        for cand in ["latitude_centre", "LATITUDE_CENTRE", "lat_centre"]:
            if cand in df.columns:
                lat_col = cand
                break
        for cand in ["longitude_centre", "LONGITUDE_CENTRE", "lon_centre"]:
            if cand in df.columns:
                lon_col = cand
                break

        if lat_col is None or lon_col is None:
            raise KeyError(
                "Colonnes de centroïdes manquantes dans communes-france-2025.csv "
                "(attendu: latitude_centre / longitude_centre ou équivalents)"
            )

        out = pd.DataFrame(
            {
                "code_insee": df[insee_col].astype(str).str.zfill(5),
                "lat": pd.to_numeric(df[lat_col], errors="coerce"),
                "lon": pd.to_numeric(df[lon_col], errors="coerce"),
            }
        )
        # On élimine les lignes sans coordonnées valides
        out = out.dropna(subset=["lat", "lon"])
        return out

    # Fallback possible : shapefile / gpkg de communes avec géométrie, si disponible.
    # On extrait alors le centroïde de chaque polygone.
    for base_name in ["communes-france-2025", "communes_france_2025"]:
        for ext in (".gpkg", ".shp"):
            vec_path = ref_dir / f"{base_name}{ext}"
            if vec_path.exists():
                gdf = gpd.read_file(vec_path)
                insee_col = None
                for cand in ["code_insee", "CODE_INSEE", "insee", "INSEE_COM"]:
                    if cand in gdf.columns:
                        insee_col = cand
                        break
                if insee_col is None:
                    raise KeyError(
                        f"Aucune colonne de code INSEE trouvée dans {vec_path} "
                        "(attendu: code_insee / CODE_INSEE / insee / INSEE_COM)"
                    )
                # S'assurer que la géométrie est présente
                if "geometry" not in gdf.columns:
                    raise KeyError(f"Aucune colonne 'geometry' dans {vec_path}")

                # Centroïdes géométriques
                gdf = gdf.set_geometry("geometry")
                centroids = gdf.geometry.centroid
                out = pd.DataFrame(
                    {
                        "code_insee": gdf[insee_col].astype(str).str.zfill(5),
                        "lat": centroids.y,
                        "lon": centroids.x,
                    }
                )
                out = out.dropna(subset=["lat", "lon"])
                return out

    raise FileNotFoundError(
        "Impossible de trouver une table de centroïdes communes : "
        "ni ref/sig/communes-france-2025.csv ni shapefile/GeoPackage équivalent."
    )


def load_natinf_ref(root: Path) -> pd.DataFrame:
    """Charge le référentiel NATINF (ref/liste_natinf.csv) pour libeller les exports."""
    for base in ("ref", "sources"):
        for name in ("liste_natinf.csv", "liste-natinf-avril2023.csv"):
            path = root / base / name
            if not path.exists():
                continue
            try:
                raw = path.read_text(encoding="utf-8", errors="ignore")
                sep = ";" if ";" in raw.split("\n")[0] else ","
                df = pd.read_csv(path, sep=sep, dtype=str, encoding="utf-8", on_bad_lines="skip")
                for c in ("Numéro NATINF", "numero_natinf", "NATINF", "natinf"):
                    if c in df.columns:
                        df = df.rename(columns={c: "numero_natinf"})
                        break
                if "numero_natinf" not in df.columns:
                    continue
                # Colonnes spécifiques du fichier standard OFB :
                #   - « Nature de l'infraction » (ex. Délit, Contravention de classe 5)
                #   - « Qualification de l'infraction » (nom de l'infraction)
                nature_col = None
                qualif_col = None
                for c in df.columns:
                    cl = c.lower()
                    if c == "numero_natinf":
                        continue
                    if "nature de l'infraction" in cl:
                        nature_col = c
                    elif "qualification de l'infraction" in cl:
                        qualif_col = c
                # Renommer d'abord les colonnes détaillées (avant tout autre rename)
                if nature_col:
                    df = df.rename(columns={nature_col: "nature_infraction"})
                if qualif_col:
                    df = df.rename(columns={qualif_col: "qualification_infraction"})
                # Fallback libelle_natinf pour les usages existants : privilégier la qualification
                lib_col = None
                if "qualification_infraction" in df.columns:
                    df["libelle_natinf"] = df["qualification_infraction"].fillna("")
                else:
                    for c in df.columns:
                        if c == "numero_natinf":
                            continue
                        if "nature" in c.lower() or "infraction" in c.lower():
                            lib_col = c
                            break
                    if lib_col:
                        df = df.rename(columns={lib_col: "libelle_natinf"})
                if "libelle_natinf" not in df.columns:
                    df["libelle_natinf"] = ""
                out_cols = ["numero_natinf", "libelle_natinf"]
                if "nature_infraction" in df.columns:
                    out_cols.append("nature_infraction")
                if "qualification_infraction" in df.columns:
                    out_cols.append("qualification_infraction")
                return df[out_cols].drop_duplicates()
            except Exception:
                continue
    return pd.DataFrame(columns=["numero_natinf", "libelle_natinf"])


def enrich_pve_positions_from_pnf_commune_centroids(
    root: Path,
    df: pd.DataFrame,
    *,
    log: Optional[logging.Logger] = None,
) -> pd.DataFrame:
    """
    Attache des coordonnées WGS84 fiables aux PVe : jointure ``INF-INSEE`` avec
    ``ref/sig/communes_pnf/communes_PNF_centroides.shp`` (colonnes ``long_centr`` /
    ``lat_centro`` en degrés).

    Les coordonnées ``x`` (longitude) et ``y`` (latitude) sont renseignées ou
    écrasées pour les lignes appariées, afin d'aligner la localisation sur le
    centroïde communal du périmètre PNF (cohérent avec les masques SIG et la liste
    INSEE du référentiel).
    """
    lg = log or logger
    if df is None or df.empty or "INF-INSEE" not in df.columns:
        return df

    shp = root / "ref" / "sig" / "communes_pnf" / "communes_PNF_centroides.shp"
    if not shp.exists():
        lg.debug(
            "Centroïdes communes PNF absents (%s) — coordonnées PVe non dérivées du référentiel.",
            shp,
        )
        return df

    try:
        cen = gpd.read_file(shp)
    except Exception as e:
        lg.warning("Lecture centroïdes PNF impossible (%s) : %s", shp, e)
        return df

    if cen.empty or "INSEE_COM" not in cen.columns:
        return df

    lon_col = "long_centr" if "long_centr" in cen.columns else None
    lat_col = "lat_centro" if "lat_centro" in cen.columns else None
    if lon_col is None or lat_col is None:
        lg.warning(
            "Shapefile centroïdes PNF : colonnes long_centr / lat_centro introuvables."
        )
        return df

    cen_small = cen[["INSEE_COM", lon_col, lat_col]].copy()
    cen_small["INSEE_COM"] = (
        cen_small["INSEE_COM"]
        .astype(str)
        .str.extract(r"(\d{1,5})", expand=False)
        .fillna("")
        .str.zfill(5)
    )
    cen_small = cen_small.drop_duplicates(subset=["INSEE_COM"], keep="first")
    cen_small = cen_small.rename(columns={lon_col: "_lon_cent", lat_col: "_lat_cent"})

    out = df.copy()
    out["_insee_pve"] = (
        out["INF-INSEE"]
        .astype(str)
        .str.extract(r"(\d{1,5})", expand=False)
        .fillna("")
        .str.zfill(5)
    )
    merged = out.merge(cen_small, left_on="_insee_pve", right_on="INSEE_COM", how="left")
    ok = merged["_lon_cent"].notna() & merged["_lat_cent"].notna()
    n = int(ok.sum())
    if n:
        lon = pd.to_numeric(merged.loc[ok, "_lon_cent"], errors="coerce")
        lat = pd.to_numeric(merged.loc[ok, "_lat_cent"], errors="coerce")
        # Stats_PVe en dtype=str / StringDtype : convertir les colonnes coords en float
        # avant assignation (sinon TypeError sur inf_gps_*).
        for col in ("x", "y", "inf_gps_long", "inf_gps_lat"):
            if col in merged.columns:
                merged[col] = pd.to_numeric(merged[col], errors="coerce")
            else:
                merged[col] = pd.Series(float("nan"), index=merged.index, dtype="float64")
        merged.loc[ok, "x"] = lon
        merged.loc[ok, "y"] = lat
        # Compatibilité chemins qui lisent encore le couple GPS PVe
        merged.loc[ok, "inf_gps_long"] = lon
        merged.loc[ok, "inf_gps_lat"] = lat
        lg.info(
            "PVe : %s ligne(s) géolocalisées au centroïde commune PNF (jointure INF-INSEE).",
            n,
        )
    drop_cols = [c for c in ("_insee_pve", "INSEE_COM", "_lon_cent", "_lat_cent") if c in merged.columns]
    merged = merged.drop(columns=drop_cols, errors="ignore")
    return merged


def load_pve(
    root: Path,
    dept_code: Optional[str] = None,
    date_deb: Optional[Union[str, pd.Timestamp]] = None,
    date_fin: Optional[Union[str, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """
    Charge le tableau Stats_PVe_OFB (format .csv, .ods ou .xlsx) et homogénéise
    les principales colonnes utilisées dans les analyses/cartes.

    Le fichier est recherché dynamiquement dans sources/ : on prend le plus récent
    parmi les fichiers dont le nom commence par "Stats_PVe_OFB"
    (extensions .csv, .ods ou .xlsx),
    en se basant sur la date de modification du fichier.

    Colonnes normalisées :
      * INF-INSEE : chaîne à 5 chiffres (zfill(5)) si présente
      * INF-DEPARTEMENT / INF-DEPART : alias réciproques
      * INF-DATE-INTG : datetime (date d'intégration, jour/mois/année)

    Si dept_code et/ou date_deb/date_fin sont fournis, filtre les lignes en conséquence.

    **Période :** le filtre sur ``INF-DATE-INTG`` réduit le nombre de PVe par rapport à une
    simple jointure spatiale (ex. QGIS Excel × centroïdes PNF sans critère de date) : seules
    les infractions dont la date d'intégration tombe dans l'intervalle du bilan sont comptées.
    """
    sources = root / "sources"
    if not sources.exists():
        raise FileNotFoundError(f"Le dossier sources n'existe pas : {sources}")

    candidates: List[Path] = []
    for ext in (".csv", ".ods", ".xlsx"):
        candidates.extend(sources.glob(f"Stats_PVe_OFB*{ext}"))
    if not candidates:
        raise FileNotFoundError(
            f"Aucun fichier Stats_PVe_OFB*.csv, *.ods ou *.xlsx trouvé dans {sources}."
        )
    # Fichier le plus récent (date de modification)
    path = max(candidates, key=lambda p: p.stat().st_mtime)

    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path, sep=";", dtype=str, encoding="latin1")
    elif suffix == ".ods":
        df = pd.read_excel(path, dtype=str, engine="odf")
    else:
        # .xlsx : moteur openpyxl requis côté environnement Python
        df = pd.read_excel(path, dtype=str, engine="openpyxl")

    # Normalisation du code commune
    if "INF-INSEE" in df.columns:
        df["INF-INSEE"] = (
            df["INF-INSEE"]
            .astype(str)
            .str.extract(r"(\d{1,5})", expand=False)
            .fillna("")
            .str.zfill(5)
        )

    # Alias de département INF-DEPART / INF-DEPARTEMENT
    if "INF-DEPARTEMENT" in df.columns and "INF-DEPART" not in df.columns:
        df["INF-DEPART"] = df["INF-DEPARTEMENT"]
    elif "INF-DEPART" in df.columns and "INF-DEPARTEMENT" not in df.columns:
        df["INF-DEPARTEMENT"] = df["INF-DEPART"]

    # Date d'intégration
    if "INF-DATE-INTG" in df.columns:
        df["INF-DATE-INTG"] = pd.to_datetime(
            df["INF-DATE-INTG"], dayfirst=True, errors="coerce"
        )

    if dept_code is not None:
        dept_col = "INF-DEPART" if "INF-DEPART" in df.columns else "INF-DEPARTEMENT"
        if dept_col in df.columns:
            df = df[df[dept_col].astype(str).str.strip() == str(dept_code).strip()].copy()
    if date_deb is not None and date_fin is not None and "INF-DATE-INTG" in df.columns:
        n_before_period = len(df)
        deb_ts = pd.to_datetime(date_deb)
        fin_ts = pd.to_datetime(date_fin)
        df = filtre_periode(df, "INF-DATE-INTG", deb_ts, fin_ts)
        n_after_period = len(df)
        if n_before_period > n_after_period:
            logger.info(
                "PVe : %s ligne(s) retenues sur %s après filtre période INF-DATE-INTG "
                "(%s → %s) ; %s ligne(s) hors période exclues. "
                "(Une jointure QGIS sans filtre date sur les mêmes communes PNF peut compter plus de lignes.)",
                n_after_period,
                n_before_period,
                date_deb,
                date_fin,
                n_before_period - n_after_period,
            )

    df = enrich_pve_positions_from_pnf_commune_centroids(root, df, log=logger)
    return df


def get_points_infrac_pj_path(root: Path) -> Path:
    """
    Chemin du fichier des points infractions PJ (GPKG ou shapefile) le plus récent.

    On recherche en priorité les GeoPackage dans sources/sig/points_infractions_pj/,
    avec un nom du type localisation_infrac_FAITS_YYYYMMDD.gpkg, puis, à défaut,
    un shapefile localisation_infrac_FAITS_YYYYMMDD.shp.
    """
    base_dir = root / "sources" / "sig" / "points_infractions_pj"
    if not base_dir.exists():
        # Compatibilité ancienne arborescence : sources/points_infractions_pj
        base_dir = root / "sources" / "points_infractions_pj"

    try:
        return _find_latest_dated_file(
            base_dir, "localisation_infrac_FAITS_", (".gpkg", ".shp")
        )
    except FileNotFoundError:
        # On laisse l'appelant gérer l'absence de fichier
        return base_dir / "localisation_infrac_FAITS_00000000.gpkg"


def merge_pej_faits_locations(
    pej: pd.DataFrame,
    root: Path,
    dept_code: str,
    *,
    log: Optional[logging.Logger] = None,
) -> pd.DataFrame:
    """
    Enrichit le tableau PEJ (ODS) avec les coordonnées WGS84 issues de la couche
    ``localisation_infrac_FAITS_*`` (jointure ``DC_ID`` = ``dossier``).

    L'ODS ne contient pas de géométrie : cette étape est nécessaire pour les
    analyses spatiales (ex. restriction PNF sur les faits localisés).
    """
    lg = log or logger
    if pej is None or pej.empty or "DC_ID" not in pej.columns:
        return pej

    path = get_points_infrac_pj_path(root)
    if not path.exists():
        lg.info("Couche FAITS PJ absente (%s) — PEJ sans coordonnées SIG.", path)
        return pej.copy()

    try:
        gdf = gpd.read_file(path)
    except Exception as e:
        lg.warning("Lecture FAITS pour localisations PEJ impossible (%s) : %s", path, e)
        return pej.copy()

    if gdf.empty:
        return pej.copy()

    ent_col = next((c for c in ("entite", "ENTITE", "Entite") if c in gdf.columns), None)
    if ent_col is None:
        lg.warning("Couche FAITS : pas de colonne entite — jointure PEJ ignorée.")
        return pej.copy()
    sd = f"SD{str(dept_code).strip()}"
    gdf = gdf[gdf[ent_col].astype(str).str.strip().eq(sd)].copy()
    if gdf.empty:
        lg.info("Couche FAITS : aucune entité %s — pas de localisations jointes.", sd)
        return pej.copy()

    doss_col = next((c for c in ("dossier", "DOSSIER") if c in gdf.columns), None)
    if doss_col is None:
        lg.warning("Couche FAITS : colonne dossier introuvable.")
        return pej.copy()

    xcol = "x_infrac" if "x_infrac" in gdf.columns else ("x" if "x" in gdf.columns else None)
    ycol = "y_infrac" if "y_infrac" in gdf.columns else ("y" if "y" in gdf.columns else None)
    if xcol is None or ycol is None:
        lg.warning("Couche FAITS : colonnes de coordonnées introuvables.")
        return pej.copy()

    loc = gdf[[doss_col, xcol, ycol]].copy()
    loc["_doss"] = loc[doss_col].astype(str).str.strip()
    loc = loc.drop_duplicates(subset="_doss", keep="first")
    loc = loc.rename(columns={xcol: "x_faits", ycol: "y_faits"}).drop(columns=[doss_col], errors="ignore")

    out = pej.copy()
    out["_dc"] = out["DC_ID"].astype(str).str.strip()
    out = out.merge(loc, left_on="_dc", right_on="_doss", how="left")
    out = out.drop(columns=["_dc", "_doss"], errors="ignore")
    n = int(out["x_faits"].notna().sum())
    if n:
        lg.info("PEJ : %s ligne(s) avec localisation FAITS (jointure dossier).", n)
    return out


def load_points_infrac_pj(
    root: Path, natinf_list: List[str], dept_code: str
) -> gpd.GeoDataFrame:
    """Charge le shapefile/gpkg des points d'infractions PJ, filtre SD + NATINF."""
    path = get_points_infrac_pj_path(root)
    if not path.exists():
        raise FileNotFoundError(path)
    natinf_vals = [int(n) for n in natinf_list]
    # Filtre à la lecture si possible (pyogrio) pour éviter de charger tout le GPKG
    try:
        where_clause = f"entite = 'SD{dept_code}' AND natinf IN ({','.join(map(str, natinf_vals))})"
        gdf = gpd.read_file(path, engine=_GPKG_ENGINE, where=where_clause)
    except Exception:
        gdf = gpd.read_file(path)
        gdf["natinf"] = pd.to_numeric(gdf["natinf"], errors="coerce")
        mask = (gdf["entite"] == f"SD{dept_code}") & (gdf["natinf"].isin(natinf_vals))
        gdf = gdf.loc[mask].copy()

    # Harmonisation du CRS : si absent, on considère que les coordonnées sont en WGS84.
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)

    if "natinf" in gdf.columns and gdf["natinf"].dtype == object:
        gdf["natinf"] = pd.to_numeric(gdf["natinf"], errors="coerce")

    # Colonne de commune : le schéma réel utilise "commune_fait" (et non "commune_fa").
    commune_col = None
    if "commune_fait" in gdf.columns:
        commune_col = "commune_fait"
    elif "commune_fa" in gdf.columns:
        commune_col = "commune_fa"

    cols = ["dossier", "natinf", "x_infrac", "y_infrac", "geometry"]
    if commune_col is not None:
        cols.insert(2, commune_col)
    cols = [c for c in cols if c in gdf.columns]
    return gdf[cols].copy()


def load_pj_with_geometry(
    root: Path,
    natinf_list: List[str],
    dept_code: str,
    date_deb: Optional[Union[str, pd.Timestamp]] = None,
    date_fin: Optional[Union[str, pd.Timestamp]] = None,
    pej_df: Optional[pd.DataFrame] = None,
) -> gpd.GeoDataFrame:
    """
    Charge les procédures judiciaires (ODS) et les associe à la géométrie des faits
    (GPKG points PJ). Ne conserve que les dossiers présents dans le GPKG (SD + NATINF).

    Retourne un GeoDataFrame avec les colonnes PJ utiles + geometry.
    Si date_deb/date_fin sont fournis, le PEJ est filtré sur cette période avant jointure.
    Si pej_df est fourni, il est utilisé à la place de recharger l'ODS (évite double lecture).
    """
    if pej_df is not None:
        pej = pej_df
    else:
        pej = load_pej(root, date_deb=date_deb, date_fin=date_fin)
    pts_pj = load_points_infrac_pj(root, natinf_list, dept_code)
    dossiers_geom = set(pts_pj["dossier"].unique())
    pej_with_geom = pej[pej["DC_ID"].isin(dossiers_geom)].copy()
    if pej_with_geom.empty:
        return gpd.GeoDataFrame(columns=list(pej.columns) + ["geometry"], crs=pts_pj.crs)

    pts_dedup = pts_pj.drop_duplicates(subset="dossier", keep="first")
    merged = pej_with_geom.merge(
        pts_dedup[["dossier", "geometry"]],
        left_on="DC_ID",
        right_on="dossier",
        how="left",
    )
    if "dossier" in merged.columns:
        merged = merged.drop(columns=["dossier"])
    return gpd.GeoDataFrame(merged, geometry="geometry", crs=pts_pj.crs)
