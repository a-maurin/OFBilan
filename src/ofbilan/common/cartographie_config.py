"""
Résolution catalogue / sélection des cartes à partir des profils YAML.

Le code reste générique ; chaque profil déclare ``cartographie.catalog`` et
``options.cartes_selection`` (liste d'identifiants carto QGIS).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from ofbilan.chemins_projet import get_cartes_dir

logger = logging.getLogger(__name__)
from ofbilan.common.carte_helper import resolve_map_layout


def parse_cartography_catalog(profile: dict | None) -> list[dict[str, str]]:
    """Entrées ``{id, label, fichier}`` générées dynamiquement depuis ``cartes_actives`` (Lot 2)."""
    if not profile:
        return []
    
    # On récupère l'identifiant du profil (ex: 'agrainage')
    pid = str(profile.get("id", profile.get("titre_bilan", ""))).strip().lower()
    if not pid:
        # Fallback heuristique si pas d'ID clair
        pid = "bilan"
        
    carto = profile.get("cartographie")
    if not isinstance(carto, dict):
        return []
        
    if "catalog" in carto and isinstance(carto["catalog"], list) and carto["catalog"]:
        return carto["catalog"]

    # La liste des cartes actives pilote le catalogue. Par défaut les 4 génériques si absent.
    actives = carto.get("cartes_actives", ["domaines", "usagers", "resultats", "procedures"])
    if not isinstance(actives, list):
        return []

    entries: list[dict[str, str]] = []
    
    # Dictionnaire de correspondance générique socle
    labels_map = {
        "domaines": "Contrôles par domaine",
        "usagers": "Contrôles par usager",
        "resultats": "Résultats des contrôles",
        "procedures": "Procédures"
    }

    for map_id in actives:
        if not isinstance(map_id, str) or not map_id.strip():
            continue
        mid = map_id.strip()
        label = labels_map.get(mid, mid.capitalize())
        fichier = f"carte_{pid}_{mid}.png"
        entries.append({"id": f"{pid}_{mid}", "label": label, "fichier": fichier})
        
    return entries


def has_cartography_catalog(profile: dict | None) -> bool:
    return bool(parse_cartography_catalog(profile))


def default_cartes_selection(profile: dict | None) -> list[str]:
    """Valeurs par défaut : ``options.cartes_selection.default`` ou tout le catalogue."""
    catalog = parse_cartography_catalog(profile)
    if not catalog:
        return []
    options_cfg = (profile or {}).get("options") or {}
    sel_cfg = options_cfg.get("cartes_selection") if isinstance(options_cfg, dict) else None
    if isinstance(sel_cfg, dict):
        raw_default = sel_cfg.get("default")
        if isinstance(raw_default, list):
            ids = [str(x).strip() for x in raw_default if str(x).strip()]
            catalog_ids = {e["id"] for e in catalog}
            return [i for i in ids if i in catalog_ids]
        if str(raw_default).strip().lower() == "all":
            return [e["id"] for e in catalog]
    return [e["id"] for e in catalog]


def _catalog_ids(profile: dict | None) -> set[str]:
    return {e["id"] for e in parse_cartography_catalog(profile)}


def _catalog_by_id(profile: dict | None) -> dict[str, dict[str, str]]:
    return {e["id"]: e for e in parse_cartography_catalog(profile)}


def resolve_cartes_selection(profile: dict | None, resolved_opts: dict | None) -> list[str]:
    """
    Liste ordonnée des profils carto QGIS retenus pour le PDF.

    Priorité : ``cartes_profil`` CLI > ``cartes_selection`` résolu > défaut YAML.
    """
    catalog = parse_cartography_catalog(profile)
    if not catalog:
        return []

    opts = resolved_opts or {}
    catalog_ids = _catalog_ids(profile)

    cli_profiles = opts.get("cartes_profil")
    if isinstance(cli_profiles, list) and cli_profiles:
        if any(str(x).strip().lower() == "all" for x in cli_profiles):
            return [e["id"] for e in catalog]
        selected: list[str] = []
        for raw in cli_profiles:
            mid = str(raw).strip()
            if mid and mid in catalog_ids and mid not in selected:
                selected.append(mid)
        if selected:
            return selected

    yaml_sel = opts.get("cartes_selection")
    if isinstance(yaml_sel, list):
        selected = [str(x).strip() for x in yaml_sel if str(x).strip() in catalog_ids]
        if selected:
            return selected

    return default_cartes_selection(profile)


# Profils QGIS dont l'id diffère de l'id bilan
QGIS_PROFILE_ALIASES: dict[str, str] = {
    "types_usager": "global_usagers",
}


def infer_cartographie_mode(profile: dict | None, profil_id: str) -> str:
    """
    Mode cartographique déduit du YAML ou du filtre bilan.

    Valeurs : ``catalog``, ``synthese``, ``dedie``, ``thematique_ref``, ``manuel``, ``none``.
    """
    carto = (profile or {}).get("cartographie") or {}
    if isinstance(carto, dict):
        raw_mode = str(carto.get("mode", "")).strip().lower()
        if raw_mode in ("catalog", "synthese", "dedie", "thematique_ref", "manuel", "none"):
            return raw_mode
        if raw_mode in ("auto", "thematique_keywords"):
            return "thematique_ref"

    if has_cartography_catalog(profile):
        return "catalog"

    pid = str(profil_id).strip()
    if pid == "types_usager_cible":
        return "manuel"

    filt = (profile or {}).get("filter") or {}
    ft = str(filt.get("type", "keywords")).strip().lower()
    pipeline = str((profile or {}).get("pipeline", "thematic")).strip().lower()

    if isinstance(carto, dict) and carto.get("fichiers") and pipeline == "global" and pid != "global":
        return "synthese"

    if ft == "all" and pid == "pnf_foret":
        return "dedie"
    if ft in ("agrainage", "chasse", "piegeage", "procedures", "type_usager"):
        return "dedie"
    if ft == "keywords" or ft == "":
        return "thematique_ref"
    return "none"


def resolve_qgis_profile_id(profile: dict | None, profil_id: str) -> str:
    """Identifiant profil QGIS à générer / rechercher pour un profil bilan."""
    carto = (profile or {}).get("cartographie") or {}
    if isinstance(carto, dict):
        explicit = str(carto.get("profil_qgis", "")).strip()
        if explicit:
            return explicit
    pid = str(profil_id).strip()
    if not pid:
        return ""
    if infer_cartographie_mode(profile, pid) == "manuel":
        return ""
    return QGIS_PROFILE_ALIASES.get(pid, pid)


def collect_bilan_carto_override(profile: dict | None) -> dict[str, Any]:
    """Surcharges QGIS (mots-clés) dérivées du profil bilan."""
    if not profile:
        return {}
    carto = profile.get("cartographie") or {}
    filt = profile.get("filter") or {}
    keywords: list[str] = []
    if isinstance(carto, dict):
        raw = carto.get("keywords")
        if isinstance(raw, list):
            keywords.extend(str(k).strip() for k in raw if str(k).strip())
        elif raw:
            keywords.append(str(raw).strip())
    if isinstance(filt, dict):
        raw_kw = filt.get("keywords") or []
        if isinstance(raw_kw, list):
            for k in raw_kw:
                s = str(k).strip()
                if s and s not in keywords:
                    keywords.append(s)
    override: dict[str, Any] = {}
    if keywords:
        override["keywords"] = keywords
    columns = None
    if isinstance(carto, dict) and carto.get("columns"):
        columns = carto.get("columns")
    elif isinstance(filt, dict) and filt.get("columns"):
        columns = filt.get("columns")
    if isinstance(columns, list) and columns:
        override["keyword_columns"] = [str(c).strip() for c in columns if str(c).strip()]
    return override


def build_qgis_overrides_from_bilan_profiles(
    bilan_profiles: dict[str, dict] | None,
) -> dict[str, dict[str, Any]]:
    """Mappe identifiant profil QGIS → surcharges (keywords, colonnes, natinfs)."""
    if not bilan_profiles:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for bilan_id, profile in bilan_profiles.items():
        if not isinstance(profile, dict):
            continue
        qgis_id = resolve_qgis_profile_id(profile, str(bilan_id))
        if not qgis_id:
            continue
        override = collect_bilan_carto_override(profile)
        # Surcharges NATINFs
        if "natinf_pve" in profile:
            override["natinf_pve"] = profile["natinf_pve"]
        if "natinf_pej" in profile:
            override["natinf_pj"] = profile["natinf_pej"]
        elif "natinf_pj" in profile:
            override["natinf_pj"] = profile["natinf_pj"]

        if override:
            out[qgis_id] = override
            # Propagation aux sous-cartes (ex. global_procedures)
            prefixes = {bilan_id, qgis_id}
            for pref in prefixes:
                if not pref:
                    continue
                for sub in ("domaines", "resultats", "usagers", "procedures"):
                    out[f"{pref}_{sub}"] = dict(override)
    return out


def resolve_qgis_profile_ids(
    profile: dict | None,
    profil_id: str,
    resolved_opts: dict | None,
) -> list[str]:
    """Liste des profils QGIS à générer pour un profil bilan."""
    opts = resolved_opts or {}
    if not opts.get("cartes", False):
        return []

    mode = infer_cartographie_mode(profile, profil_id)
    if mode in ("none", "manuel", "catalog"):
        return []

    if mode == "synthese":
        carto = (profile or {}).get("cartographie") or {}
        caps = (profile or {}).get("capabilities") or {}
        for source in (carto.get("map_profiles"), caps.get("map_profiles")):
            if isinstance(source, list):
                ids = [str(x).strip() for x in source if str(x).strip()]
                if ids:
                    return ids
        return ["synthese_activite_PA_PJ", "synthese_activite_PA_PJ_2"]

    qgis_id = resolve_qgis_profile_id(profile, profil_id)
    return [qgis_id] if qgis_id else []


def resolve_map_profiles_for_batch(
    profile: dict | None,
    profil_id: str,
    cli_options: dict | None,
) -> list[str]:
    """
    Profils QGIS à pré-générer avant le run (defaults CLI/YAML, sans menu interactif).
    """
    prof = profile or {}
    opts: dict[str, Any] = {}
    options_config = prof.get("options") or {}
    if isinstance(options_config, dict):
        for key, config in options_config.items():
            if isinstance(config, dict):
                opts[key] = config.get("default", False)
            else:
                opts[key] = config
    for key, val in (cli_options or {}).items():
        opts[key] = val

    if not opts.get("cartes", False):
        return []

    mode = infer_cartographie_mode(prof, profil_id)
    if mode == "catalog":
        return resolve_cartes_selection(prof, opts)

    return resolve_qgis_profile_ids(prof, profil_id, opts)


def resolve_map_file_for_catalog_entry(entry: dict[str, str], target_dir: Path | None = None) -> Path:
    base = target_dir if target_dir else get_cartes_dir()
    return base / entry["fichier"]


def resolve_selected_map_paths(
    profile: dict | None,
    selected_ids: list[str],
    *,
    carto_dept: str | None = None,
    target_dir: Path | None = None,
) -> tuple[list[Path], list[str]]:
    """
    Chemins PNG existants + légendes, dans l'ordre du catalogue puis de la sélection.

    Si *carto_dept* est fourni, seules les cartes valides pour ce département
    (marqueur ``.XX.dept`` ou rétrocompatibilité département 21) sont retenues.
    """
    from ofbilan.cartographie.pochoir_helper import is_map_valid_for_dept, read_map_dept_marker

    by_id = _catalog_by_id(profile)
    catalog_order = [e["id"] for e in parse_cartography_catalog(profile)]
    order = [i for i in catalog_order if i in selected_ids]
    order.extend(i for i in selected_ids if i not in order)

    cartes_dir = target_dir if target_dir else get_cartes_dir()
    paths: list[Path] = []
    captions: list[str] = []
    for map_id in order:
        entry = by_id.get(map_id)
        if not entry:
            continue
        candidate = resolve_map_file_for_catalog_entry(entry, target_dir)
        if not candidate.exists():
            logger.warning(
                "Carte PDF absente : %s (dossier %s, profil carto %s)",
                entry["fichier"],
                cartes_dir,
                map_id,
            )
            continue
        if carto_dept and not is_map_valid_for_dept(candidate, carto_dept):
            marker = read_map_dept_marker(candidate)
            logger.warning(
                "Carte PDF ignorée : %s — marqueur département %s, attendu %s (profil carto %s)",
                candidate.name,
                marker or "absent",
                carto_dept,
                map_id,
            )
            continue
        paths.append(candidate)
        captions.append(entry["label"])
    return paths, captions


def expected_map_filenames_for_selection(
    profile: dict | None,
    selected_ids: list[str],
) -> list[str]:
    by_id = _catalog_by_id(profile)
    catalog_order = [e["id"] for e in parse_cartography_catalog(profile)]
    order = [i for i in catalog_order if i in selected_ids]
    order.extend(i for i in selected_ids if i not in order)
    names: list[str] = []
    for map_id in order:
        entry = by_id.get(map_id)
        if entry and entry["fichier"] not in names:
            names.append(entry["fichier"])
    return names


def ask_cartes_selection(profile: dict, current: list[str]) -> list[str]:
    """Menu interactif multi-sélection (profil global catalogue)."""
    catalog = parse_cartography_catalog(profile)
    if not catalog or not sys.stdin.isatty():
        return current

    catalog_ids = {e["id"] for e in catalog}
    selection = [i for i in current if i in catalog_ids] or default_cartes_selection(profile)

    print("\n--- Cartes à intégrer au PDF ---")
    for i, entry in enumerate(catalog, 1):
        mark = "x" if entry["id"] in selection else " "
        print(f"  {i}. [{mark}] {entry['label']} ({entry['fichier']})")
    print("  a = toutes | n = aucune | numéros séparés par espaces (ex. 1 3) | Entrée = conserver")

    try:
        raw = input("Votre choix : ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return selection

    if not raw:
        return selection
    if raw in ("a", "all", "toutes", "tous"):
        return [e["id"] for e in catalog]
    if raw in ("n", "none", "aucune", "aucun"):
        return []

    picked: list[str] = []
    for token in raw.replace(",", " ").split():
        if token.isdigit():
            idx = int(token)
            if 1 <= idx <= len(catalog):
                mid = catalog[idx - 1]["id"]
                if mid not in picked:
                    picked.append(mid)
        elif token in catalog_ids and token not in picked:
            picked.append(token)
    return picked or selection


def resolve_map_layout_for_profile(
    profile: dict | None,
    presentation_cfg: dict | None = None,
) -> str:
    return resolve_map_layout(profile=profile, presentation_cfg=presentation_cfg)
