"""
Résolution des couches QGIS par rôle métier.

Permet de retrouver une couche dans le projet même si le nom exact a changé
(ex. renommage `point_ctrl_20260205_wgs84` → `point_ctrl_20260505_wgs84`).
"""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Sequence

from bilans.cartographie.pochoir_helper import normalize_dept_code, pochoir_layer_name

# Rôles métier reconnus dans profils_cartes.yaml
LayerRole = str

_DATE_IN_NAME = re.compile(r"(20\d{2})(\d{2})(\d{2})")


@dataclass(frozen=True)
class LayerRoleSpec:
    """Spécification d'un rôle de couche."""

    role: LayerRole
    patterns: tuple[str, ...]
    prefer_latest_dated: bool = False
    exclude_substrings: tuple[str, ...] = (" copie",)


LAYER_ROLE_SPECS: tuple[LayerRoleSpec, ...] = (
    LayerRoleSpec(
        role="point_controles",
        patterns=("point_ctrl_*_wgs84", "point_ctrl_*"),
        prefer_latest_dated=True,
    ),
    LayerRoleSpec(
        role="pej",
        patterns=("localisation_infrac_FAITS_*", "localisation_infrac_*"),
        prefer_latest_dated=True,
    ),
    LayerRoleSpec(
        role="pochoir",
        patterns=("pochoir_sd*", "pochoir_*"),
        prefer_latest_dated=False,
    ),
    LayerRoleSpec(
        role="zone_interdiction_agrainage",
        patterns=(
            "Zone d'interdiction d'agrainage*",
            "Zone*d'interdiction*d'agrainage*",
        ),
        prefer_latest_dated=True,
    ),
    LayerRoleSpec(
        role="zone_infectee",
        patterns=("Zone Infectee*", "Zone infectée*", "Zone infect*"),
        prefer_latest_dated=True,
    ),
    LayerRoleSpec(
        role="zone_risque",
        patterns=("Zone a Risque*", "Zone à risque*", "Zone*risque*"),
        prefer_latest_dated=True,
    ),
    LayerRoleSpec(
        role="communes_pve",
        patterns=("communes_france",),
    ),
    LayerRoleSpec(
        role="pve",
        patterns=("pve_infractions", "pv_electronique", "communes_france"),
    ),
    LayerRoleSpec(
        role="pve_agrainage_centroides",
        patterns=("pve_agrainage_points_centroides", "pve_agrainage*"),
    ),
)

_ROLE_BY_NAME: dict[str, LayerRoleSpec] = {spec.role: spec for spec in LAYER_ROLE_SPECS}


def _is_excluded(name: str, exclude_substrings: Sequence[str]) -> bool:
    lowered = name.lower()
    return any(ex.lower() in lowered for ex in exclude_substrings)


def _date_sort_key(name: str) -> tuple[int, str]:
    """Clé de tri : date YYYYMMDD extraite du nom, puis nom lexicographique."""
    dates = _DATE_IN_NAME.findall(name)
    if dates:
        y, m, d = dates[-1]
        return int(f"{y}{m}{d}"), name
    # Fallback pour chercher juste une année (ex: 2024)
    years = re.findall(r"(20\d{2})", name)
    if years:
        return int(f"{years[-1]}0000"), name
    return 0, name


def _match_patterns(name: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def candidates_for_pochoir(
    available_names: Iterable[str],
    dept_code: Optional[str] = None,
) -> list[str]:
    """Couches pochoir : uniquement pochoir_sd{code} (pas un autre département)."""
    names = list(available_names)
    if not dept_code:
        return candidates_for_role("pochoir", names)
    target = pochoir_layer_name(dept_code)
    exact = [n for n in names if n == target and not _is_excluded(n, (" copie",))]
    if exact:
        return exact
    code = normalize_dept_code(dept_code)
    prefixed = [
        n
        for n in names
        if n.lower() == f"pochoir_sd{code}".lower() and not _is_excluded(n, (" copie",))
    ]
    return sorted(prefixed)


def candidates_for_role(
    role: LayerRole,
    available_names: Iterable[str],
    *,
    dept_code: Optional[str] = None,
) -> list[str]:
    """Liste les noms de couches correspondant à un rôle."""
    if role == "pochoir" and dept_code:
        return candidates_for_pochoir(available_names, dept_code)
    spec = _ROLE_BY_NAME.get(role)
    if spec is None:
        return []
    matched = [
        n
        for n in available_names
        if _match_patterns(n, spec.patterns) and not _is_excluded(n, spec.exclude_substrings)
    ]
    if spec.prefer_latest_dated:
        return sorted(matched, key=_date_sort_key)
    return sorted(matched)


def infer_layer_role(layer_key: str, layer_name_hint: str = "") -> Optional[LayerRole]:
    """Infère un rôle à partir de la clé YAML ou du nom de couche configuré."""
    hints = f"{layer_key} {layer_name_hint}".lower()
    if "point_ctrl" in hints:
        return "point_controles"
    if "localisation_infrac" in hints or "faits" in hints:
        return "pej"
    if "pochoir" in hints:
        return "pochoir"
    if "interdiction" in hints and "agrainage" in hints:
        return "zone_interdiction_agrainage"
    if "infect" in hints:
        return "zone_infectee"
    if "risque" in hints:
        return "zone_risque"
    if "communes_france" in hints or "pve" in hints and "commune" in hints:
        return "communes_pve"
    if "pve_agrainage" in hints:
        return "pve_agrainage_centroides"
    return None


def resolve_layer_names(
    *,
    configured_name: str,
    layer_role: Optional[LayerRole] = None,
    layer_key: str = "",
    available_names: Sequence[str],
    date_deb: Optional[str] = None,
    date_fin: Optional[str] = None,
    dept_code: Optional[str] = None,
) -> list[tuple[str, str]]:
    """
    Résout les noms effectifs d'une ou plusieurs couches dans le projet QGIS.
    Retourne une liste de (nom_résolu, source).
    """
    names = list(available_names)
    if not names:
        return []

    role = layer_role or infer_layer_role(layer_key, configured_name)
    if role == "pochoir" and dept_code:
        target = pochoir_layer_name(dept_code)
        if target in names:
            return [(target, "dept")]
        pochoir_candidates = candidates_for_pochoir(names, dept_code)
        if pochoir_candidates:
            return [(pochoir_candidates[0], "dept")]
        return []

    if configured_name and configured_name in names:
        return [(configured_name, "exact")]

    if role:
        candidates = candidates_for_role(role, names, dept_code=dept_code)
        if candidates:
            spec = _ROLE_BY_NAME[role]
            
            if role == "point_controles" and spec.prefer_latest_dated and date_deb and date_fin:
                try:
                    y_start = int(date_deb.split('-')[0])
                    y_end = int(date_fin.split('-')[0])
                    years = range(y_start, y_end + 1)
                    
                    results = []
                    for y in years:
                        year_candidates = []
                        for c in candidates:
                            dates = _DATE_IN_NAME.findall(c)
                            if dates:
                                cy = int(dates[-1][0])
                                if cy == y:
                                    year_candidates.append(c)
                            else:
                                y_only = re.findall(r"(20\d{2})", c)
                                if y_only and int(y_only[-1]) == y:
                                    year_candidates.append(c)
                        
                        if year_candidates:
                            # candidates est déjà trié par date, donc le dernier de year_candidates est le plus récent
                            results.append((year_candidates[-1], "role"))
                    
                    if results:
                        return results
                except ValueError:
                    pass

            chosen = candidates[-1] if spec.prefer_latest_dated else candidates[0]
            return [(chosen, "role")]

    if configured_name:
        fuzzy = [
            n
            for n in names
            if configured_name.lower() in n.lower() or n.lower() in configured_name.lower()
        ]
        fuzzy = [n for n in fuzzy if not _is_excluded(n, (" copie",))]
        if fuzzy:
            return [(sorted(fuzzy, key=_date_sort_key)[-1], "inferred")]

    return []

def resolve_layer_name(
    *,
    configured_name: str,
    layer_role: Optional[LayerRole] = None,
    layer_key: str = "",
    available_names: Sequence[str],
    dept_code: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """
    Rétrocompatibilité : retourne la première couche résolue, ou None.
    """
    results = resolve_layer_names(
        configured_name=configured_name,
        layer_role=layer_role,
        layer_key=layer_key,
        available_names=available_names,
        dept_code=dept_code,
    )
    if results:
        # Pour une compatibilité absolue avec l'ancien comportement qui prenait le "latest" (-1), 
        # on retourne le dernier de la liste si multi.
        return results[-1]
    return None, "missing"


def should_apply_yaml_symbology(
    layer_symbology_source: Optional[str],
    profile_symbology_source: Optional[str] = None,
    global_symbology_source: str = "yaml",
) -> bool:
    """True si la symbologie YAML doit écraser celle du projet QGIS."""
    for src in (layer_symbology_source, profile_symbology_source, global_symbology_source):
        if not src:
            continue
        if src == "qgis":
            return False
        if src == "yaml":
            return True
    return True
