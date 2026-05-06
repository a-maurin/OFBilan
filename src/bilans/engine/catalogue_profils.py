"""
Liste et résolution des profils bilans.

Source de vérité : fichiers YAML dans config/profils_bilan/ et ref_themes_ctrl.
"""
from __future__ import annotations

from bilans.common.chargeurs_donnees import load_ref_themes_ctrl
from bilans.chemins_projet import PROJECT_ROOT

_HIDDEN_PROFILES: frozenset[str] = frozenset({"pnf_foret", "_defaults"})


def list_profiles() -> list[str]:
    """
    Identifiants de profils disponibles, avec ordre console :
    chasse, agrainage, types_usager, types_usager_cible, puis alphabétique, hors_theme en dernier.
    """
    profils_dir = PROJECT_ROOT / "config" / "profils_bilan"
    id_to_label: dict[str, str] = {}

    themes = load_ref_themes_ctrl(PROJECT_ROOT)
    if themes:
        for t in themes:
            pid = str(t.get("id", "")).strip()
            if not pid or pid in _HIDDEN_PROFILES:
                continue
            label = str(t.get("label", pid)).strip() or pid
            id_to_label[pid] = label
    if profils_dir.exists():
        for p in profils_dir.glob("*.yaml"):
            pid = p.stem
            if pid in _HIDDEN_PROFILES:
                continue
            id_to_label.setdefault(pid, pid)

    if not id_to_label:
        return []

    types_usager_cible_id = "types_usager_cible"
    if types_usager_cible_id not in id_to_label:
        yaml_path = profils_dir / f"{types_usager_cible_id}.yaml"
        if yaml_path.exists() and types_usager_cible_id not in _HIDDEN_PROFILES:
            id_to_label[types_usager_cible_id] = "Types d'usagers – ciblé"

    priority_order: dict[str, int] = {
        "chasse": 0,
        "agrainage": 1,
        "types_usager": 2,
        "types_usager_cible": 3,
    }

    def _sort_key(pid: str) -> tuple[int, str]:
        if pid == "hors_theme":
            return (1000, "")
        base_rank = priority_order.get(pid, 10)
        label = id_to_label.get(pid, pid)
        return (base_rank, label.lower())

    all_ids = list(id_to_label.keys())
    all_ids.sort(key=_sort_key)
    return all_ids


def resolve_profile_ids(raw_ids: list[str]) -> list[str]:
    """Résout les numéros (1, 2, …) en identifiants selon list_profiles()."""
    themes = list_profiles()
    if not themes:
        return raw_ids
    resolved: list[str] = []
    for p in raw_ids:
        p = str(p).strip()
        if not p:
            continue
        if p.isdigit():
            n = int(p)
            if 1 <= n <= len(themes):
                resolved.append(themes[n - 1])
            else:
                resolved.append(p)
        else:
            resolved.append(p)
    return resolved
