from __future__ import annotations

from pathlib import Path


def load_profile_config(root: Path, profil_id: str) -> dict:
    """Charge et normalise un profil depuis ref/profils_bilan/<id>.yaml.

    Cette fonction a été extraite de scripts/bilan_thematique/bilan_thematique_engine.py
    pour faciliter les tests et la réutilisation.
    """
    try:
        import yaml
    except ImportError:
        yaml = None

    path = root / "ref" / "profils_bilan" / f"{profil_id}.yaml"
    if not path.exists():
        return _default_profile(profil_id)

    if yaml is not None:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        raise ImportError(
            "PyYAML est requis pour lire les profils bilan (ref/profils_bilan/*.yaml). "
            "Installez les dépendances : pip install -r tools/requirements.txt"
        ) from None

    return _normalize_profile(data, profil_id)


def _default_profile(profil_id: str) -> dict:
    return _normalize_profile({"id": profil_id}, profil_id)


def _normalize_profile(data: dict, profil_id: str) -> dict:
    """Assure la présence de toutes les clés attendues par le moteur."""
    data.setdefault("id", profil_id)
    data.setdefault("label", profil_id)
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

    data.setdefault("restrict_geo", None)

    # --- options ---
    data.setdefault("options", {})

    return data


def _load_glossary_config(root: Path) -> dict:
    """
    Charge la configuration du glossaire depuis ref/glossaire.yaml.

    Si le fichier n'existe pas ou si PyYAML n'est pas disponible, on
    retourne une configuration par défaut équivalente à l'ancien
    glossaire codé en dur.
    """
    cfg_path = root / "ref" / "glossaire.yaml"

    default_cfg: dict = {
        "header": {
            "abbr_label": "Abréviation",
            "definition_label": "Signification",
        },
        "abbreviations": [
            {"id": "DC", "label": "DC", "definition": "Dossier de contrôle"},
            {
                "id": "NATINF",
                "label": "NATINF",
                "definition": "Nature d'infraction (nomenclature nationale)",
            },
            {
                "id": "OSCEAN",
                "label": "OSCEAN",
                "definition": "Outil de suivi des contrôles en environnement",
            },
            {"id": "PA", "label": "PA", "definition": "Procédure administrative"},
            {"id": "PEJ", "label": "PEJ", "definition": "Procédure d'enquête judiciaire"},
            {"id": "PNF", "label": "PNF", "definition": "Parc national de forêts"},
            {
                "id": "PVe",
                "label": "PVe",
                "definition": "Procès-verbal électronique",
            },
            {
                "id": "TUB",
                "label": "TUB",
                "definition": "Zone tuberculose bovine",
            },
        ],
    }

    try:
        import yaml  # type: ignore[import]
    except ImportError:
        return default_cfg

    if not cfg_path.exists():
        return default_cfg

    with cfg_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    header = data.get("header") or default_cfg["header"]
    abbreviations = data.get("abbreviations") or default_cfg["abbreviations"]
    return {"header": header, "abbreviations": abbreviations}

