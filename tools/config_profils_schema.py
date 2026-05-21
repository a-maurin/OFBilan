"""Schéma UI et accès aux valeurs YAML (profils + présentation PDF)."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

TOOLS_DIR = Path(__file__).resolve().parent
ROOT_DIR = TOOLS_DIR.parent
PROFILS_DIR = ROOT_DIR / "config" / "profils_bilan"
DEFAULTS_PATH = PROFILS_DIR / "_defaults.yaml"
SCHEMA_UI_PATH = PROFILS_DIR / "schema_ui.yaml"
PDF_PRESENTATION_PATH = ROOT_DIR / "config" / "presentation" / "pdf_presentation.yaml"


@dataclass
class FieldSpec:
    path: str
    label: str
    help: str = ""
    widget: str = "text"
    choices: dict[str, str] = field(default_factory=dict)
    optional: bool = False
    visible_when: dict[str, Any] = field(default_factory=dict)
    profile_exclude: list[str] = field(default_factory=list)
    pdf_scope: str = ""
    target: str = "profile"  # profile | pdf_presentation
    group: str = ""


@dataclass
class SectionSpec:
    id: str
    title: str
    help: str = ""
    fields: list[FieldSpec] = field(default_factory=list)
    dynamic: str = ""
    profile_exclude: list[str] = field(default_factory=list)
    ui_mode: str = ""


@dataclass
class FieldValueState:
    """Valeur affichée + indication d'héritage depuis _defaults.yaml."""

    effective: Any
    inherited: bool


INHERITED_HINT = "Hérité du socle _defaults.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def load_schema() -> tuple[list[SectionSpec], list[FieldSpec]]:
    """Charge schema_ui.yaml → sections + catalogue pdf_block_fields."""
    with SCHEMA_UI_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    sections: list[SectionSpec] = []
    for sec in raw.get("sections", []) or []:
        if not isinstance(sec, dict):
            continue
        fields: list[FieldSpec] = []
        for fd in sec.get("fields", []) or []:
            if not isinstance(fd, dict):
                continue
            fields.append(_field_from_dict(fd, target="profile"))
        sections.append(
            SectionSpec(
                id=str(sec.get("id", "")),
                title=str(sec.get("title", "")),
                help=str(sec.get("help", "")),
                fields=fields,
                dynamic=str(sec.get("dynamic", "")),
                profile_exclude=list(sec.get("profile_exclude", []) or []),
                ui_mode=str(sec.get("ui_mode", "")),
            )
        )
    pdf_catalog: list[FieldSpec] = []
    for fd in raw.get("pdf_block_fields", []) or []:
        if isinstance(fd, dict):
            spec = _field_from_dict(fd, target="pdf_presentation")
            spec.widget = "bool"
            pdf_catalog.append(spec)
    return sections, pdf_catalog


def _field_from_dict(fd: dict, *, target: str) -> FieldSpec:
    choices_raw = fd.get("choices", {}) or {}
    choices = {str(k): str(v) for k, v in choices_raw.items()} if isinstance(choices_raw, dict) else {}
    return FieldSpec(
        path=str(fd.get("path", "")),
        label=str(fd.get("label", "")),
        help=str(fd.get("help", "")),
        widget=str(fd.get("widget", "text")),
        choices=choices,
        optional=bool(fd.get("optional", False)),
        visible_when=dict(fd.get("visible_when", {}) or {}),
        profile_exclude=list(fd.get("profile_exclude", []) or []),
        pdf_scope=str(fd.get("pdf_scope", "")),
        target=target,
    )


def get_by_path(data: dict[str, Any], path: str) -> Any:
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def set_by_path(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    node: dict[str, Any] = data
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    node[parts[-1]] = value


def path_exists(data: dict[str, Any], path: str) -> bool:
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _match_visible(
    when: dict[str, Any],
    profile: dict[str, Any],
    *,
    profile_id: str = "",
) -> bool:
    if not when:
        return True
    for key, expected in when.items():
        if key == "path_exists":
            if not path_exists(profile, str(expected)):
                return False
            continue
        if key == "profile_id":
            if str(profile_id) != str(expected):
                return False
            continue
        actual = get_by_path(profile, key)
        if key == "id" and profile_id:
            actual = profile_id
        if str(actual) != str(expected):
            return False
    return True


def profile_pipeline_scope(profile: dict[str, Any], profile_id: str) -> str:
    if profile_id == "global" or profile.get("pipeline") == "global":
        return "global"
    return "thematique"


def load_defaults_data() -> dict[str, Any]:
    if not DEFAULTS_PATH.exists():
        return {}
    return load_yaml_mapping(DEFAULTS_PATH)


def merge_profile_with_defaults(
    profile: dict[str, Any],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    if not defaults:
        return deepcopy(profile)
    return _deep_merge(defaults, profile)


def is_field_inherited(
    profile: dict[str, Any],
    path: str,
    *,
    profile_id: str,
    defaults: dict[str, Any],
) -> bool:
    """Vrai si la valeur effective vient du socle et n'est pas définie dans le fichier profil."""
    if profile_id == "_defaults" or not defaults:
        return False
    if not path_exists(merge_profile_with_defaults(profile, defaults), path):
        return False
    return not path_exists(profile, path)


def resolve_field_state(
    spec: FieldSpec,
    profile: dict[str, Any],
    *,
    profile_id: str,
    defaults: dict[str, Any],
) -> FieldValueState:
    merged = merge_profile_with_defaults(profile, defaults)
    effective = field_display_value(spec, merged, profile_id)
    inherited = is_field_inherited(profile, spec.path, profile_id=profile_id, defaults=defaults)
    return FieldValueState(effective=effective, inherited=inherited)


def dump_profile_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def parse_profile_yaml(text: str) -> dict[str, Any]:
    parsed = yaml.safe_load(text)
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError("Le YAML doit être un document de type mapping (clé: valeur).")
    return parsed


def expand_dynamic_sources(
    profile: dict[str, Any],
    defaults: dict[str, Any] | None = None,
) -> list[FieldSpec]:
    merged = merge_profile_with_defaults(profile, defaults or {})
    sources = merged.get("sources")
    if not isinstance(sources, dict):
        return []
    out: list[FieldSpec] = []
    labels = {
        "point_ctrl": "Points de contrôle",
        "pej": "Procédures d'enquête judiciaire (PEJ)",
        "pa": "Procédures administratives (PA)",
        "pve": "Procès-verbaux électroniques (PVe)",
    }
    for key in sorted(sources.keys()):
        if not isinstance(sources[key], bool):
            continue
        out.append(
            FieldSpec(
                path=f"sources.{key}",
                label=labels.get(key, key.replace("_", " ").capitalize()),
                help="Active ou désactive cette source pour le profil.",
                widget="bool",
                group="Sources",
            )
        )
    return out


def expand_dynamic_options(
    profile: dict[str, Any],
    defaults: dict[str, Any] | None = None,
) -> list[FieldSpec]:
    merged = merge_profile_with_defaults(profile, defaults or {})
    options = merged.get("options")
    if not isinstance(options, dict):
        return []
    out: list[FieldSpec] = []
    for key, opt in sorted(options.items()):
        if not isinstance(opt, dict):
            continue
        opt_label = str(opt.get("label") or key).strip()
        if "default" in opt and isinstance(opt["default"], bool):
            out.append(
                FieldSpec(
                    path=f"options.{key}.default",
                    label=f"Activé par défaut — {opt_label}",
                    help="Valeur proposée si l'option n'est pas demandée à l'utilisateur.",
                    widget="bool",
                    group="Options",
                )
            )
        if "ask" in opt and isinstance(opt["ask"], bool):
            out.append(
                FieldSpec(
                    path=f"options.{key}.ask",
                    label=f"Demander à l'utilisateur — {opt_label}",
                    help="Si oui, la CLI peut poser la question à chaque génération.",
                    widget="bool",
                    group="Options",
                )
            )
    return out


def expand_pdf_block_fields(
    catalog: list[FieldSpec],
    *,
    scope: str,
) -> list[FieldSpec]:
    out: list[FieldSpec] = []
    for spec in catalog:
        ps = spec.pdf_scope or "thematique"
        if ps == scope or ps == "both":
            out.append(spec)
    return out


def fields_for_section(
    section: SectionSpec,
    *,
    profile: dict[str, Any],
    profile_id: str,
    pdf_catalog: list[FieldSpec],
    defaults: dict[str, Any] | None = None,
) -> list[FieldSpec]:
    if profile_id in section.profile_exclude:
        return []
    if section.ui_mode == "yaml_editor":
        return []

    defaults = defaults or {}
    merged = merge_profile_with_defaults(profile, defaults)

    if section.dynamic == "sources":
        return expand_dynamic_sources(profile, defaults)
    if section.dynamic == "options":
        return expand_dynamic_options(profile, defaults)
    if section.dynamic == "pdf_blocks":
        scope = profile_pipeline_scope(profile, profile_id)
        return expand_pdf_block_fields(pdf_catalog, scope=scope)

    out: list[FieldSpec] = []
    for spec in section.fields:
        if profile_id in spec.profile_exclude:
            continue
        if not spec.optional and not path_exists(profile, spec.path) and spec.widget != "readonly":
            # Champ absent du YAML : proposer quand même si section métier standard
            if spec.path.split(".")[0] not in ("title_label", "output_filename", "restrict_geo"):
                if section.id not in ("identite", "filtre", "periode", "analyses", "natinf"):
                    continue
        if not _match_visible(spec.visible_when, merged, profile_id=profile_id):
            continue
        out.append(spec)
    return out


def list_sections_for_profile(
    sections: list[SectionSpec],
    *,
    profile: dict[str, Any],
    profile_id: str,
    pdf_catalog: list[FieldSpec],
    defaults: dict[str, Any] | None = None,
) -> list[tuple[SectionSpec, list[FieldSpec]]]:
    result: list[tuple[SectionSpec, list[FieldSpec]]] = []
    defaults = defaults or {}
    for section in sections:
        fields = fields_for_section(
            section,
            profile=profile,
            profile_id=profile_id,
            pdf_catalog=pdf_catalog,
            defaults=defaults,
        )
        if fields or section.id == "identite" or section.ui_mode == "yaml_editor":
            result.append((section, fields))
    return result


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} doit contenir un document YAML de type mapping.")
    return data


def save_yaml_mapping(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )


def load_pdf_profile_overlay(profile_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """
    Retourne (document pdf_presentation entier, dict profil overlay, blocks effectifs affichés).
    """
    doc = load_yaml_mapping(PDF_PRESENTATION_PATH)
    defaults = doc.get("defaults", {}) if isinstance(doc.get("defaults"), dict) else {}
    default_blocks = defaults.get("blocks", {}) if isinstance(defaults.get("blocks"), dict) else {}
    profiles = doc.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}
        doc["profiles"] = profiles
    prof_cfg = profiles.get(profile_id)
    if not isinstance(prof_cfg, dict):
        prof_cfg = {}
        profiles[profile_id] = prof_cfg
    prof_blocks = prof_cfg.setdefault("blocks", {})
    if not isinstance(prof_blocks, dict):
        prof_blocks = {}
        prof_cfg["blocks"] = prof_blocks
    effective = _deep_merge(default_blocks, prof_blocks)
    return doc, prof_cfg, effective


def get_pdf_field_value(effective_blocks: dict[str, Any], path: str) -> bool:
    """path du type blocks.sec22.show_pie → lit dans effective_blocks."""
    sub = path.removeprefix("blocks.")
    val = get_by_path({"blocks": effective_blocks}, path)
    if val is None:
        val = get_by_path(effective_blocks, sub)
    return bool(val) if val is not None else False


def set_pdf_field_value(prof_blocks: dict[str, Any], path: str, value: bool) -> None:
    sub = path.removeprefix("blocks.")
    set_by_path(prof_blocks, sub, bool(value))


def coerce_field_value(spec: FieldSpec, raw: Any) -> Any:
    if spec.widget == "bool":
        return bool(raw)
    if spec.widget == "int":
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    if spec.widget == "list_lines":
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
        text = str(raw or "")
        return [ln.strip() for ln in text.splitlines() if ln.strip()]
    if spec.widget == "choice":
        s = str(raw or "")
        if s in spec.choices:
            return s
        for k, v in spec.choices.items():
            if v == s:
                return k
        return s if spec.optional else (next(iter(spec.choices), "") if spec.choices else s)
    return str(raw or "").strip()


def field_display_value(spec: FieldSpec, data: dict[str, Any], profile_id: str) -> Any:
    if spec.path == "id":
        return profile_id
    val = get_by_path(data, spec.path)
    if spec.widget == "list_lines":
        if val is None:
            return ""
        if isinstance(val, list):
            return "\n".join(str(x) for x in val)
        return str(val)
    if spec.widget == "bool":
        return bool(val) if val is not None else False
    if spec.widget == "int":
        return int(val) if val is not None else 0
    if spec.widget == "choice" and val is None and "" in spec.choices:
        return ""
    return "" if val is None else val
