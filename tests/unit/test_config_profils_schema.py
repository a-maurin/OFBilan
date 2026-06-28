"""Tests du schéma UI config profils."""
from pathlib import Path

from config_profils_schema import (
    SCHEMA_UI_PATH,
    _match_visible,
    dump_profile_yaml,
    expand_dynamic_options,
    fields_for_section,
    get_by_path,
    is_field_inherited,
    list_sections_for_profile,
    load_defaults_data,
    load_schema,
    merge_profile_with_defaults,
    parse_profile_yaml,
    set_by_path,
)


def test_schema_ui_file_exists() -> None:
    assert SCHEMA_UI_PATH.is_file()


def test_load_schema_has_sections() -> None:
    sections, pdf_catalog = load_schema()
    assert len(sections) >= 5
    assert len(pdf_catalog) >= 3


def test_visible_when_profile_id() -> None:
    profile = {"pipeline": "global"}
    assert _match_visible({"profile_id": "global"}, profile, profile_id="global")
    assert not _match_visible({"profile_id": "global"}, profile, profile_id="chasse")


def test_set_get_path() -> None:
    data: dict = {"filter": {"type": "keywords", "keywords": ["a"]}}
    set_by_path(data, "filter.keywords", ["x", "y"])
    assert get_by_path(data, "filter.keywords") == ["x", "y"]


def test_expand_options_from_secheresse_profile() -> None:
    root = Path(__file__).resolve().parents[2]
    import yaml

    path = root / "config" / "profils_bilan" / "controles_secheresse.yaml.disabled"
    profile = yaml.safe_load(path.read_text(encoding="utf-8"))
    fields = expand_dynamic_options(profile)
    paths = {f.path for f in fields}
    assert "options.pnf.default" in paths
    assert "options.cartes.default" in paths


def test_pdf_section_for_thematique_profile() -> None:
    sections, pdf_catalog = load_schema()
    pdf_sec = next(s for s in sections if s.id == "pdf")
    profile = {"id": "controles_secheresse", "pipeline": "thematic"}
    fields = fields_for_section(
        pdf_sec,
        profile=profile,
        profile_id="controles_secheresse",
        pdf_catalog=pdf_catalog,
    )
    paths = {f.path for f in fields}
    assert "blocks.sec22.show_pie" in paths


def test_list_sections_excludes_defaults_from_filtre() -> None:
    sections, pdf_catalog = load_schema()
    profile = {"id": "_defaults", "options": {"pnf": {"default": False, "ask": True}}}
    views = list_sections_for_profile(
        sections,
        profile=profile,
        profile_id="_defaults",
        pdf_catalog=pdf_catalog,
    )
    section_ids = [s.id for s, _ in views]
    assert "identite" in section_ids
    assert "filtre" not in section_ids
    assert "avance" in section_ids


def test_inherited_option_detected() -> None:
    defaults = load_defaults_data()
    if not defaults:
        return
    profile = {
        "id": "test_prof",
        "options": {"cartes": {"default": True, "ask": False}},
    }
    assert is_field_inherited(
        profile, "options.pnf.default", profile_id="test_prof", defaults=defaults
    )
    assert not is_field_inherited(
        profile, "options.cartes.default", profile_id="test_prof", defaults=defaults
    )


def test_yaml_roundtrip() -> None:
    data = {"id": "x", "label": "Test", "filter": {"type": "all"}}
    text = dump_profile_yaml(data)
    back = parse_profile_yaml(text)
    assert back["id"] == "x"
    assert merge_profile_with_defaults({"label": "A"}, {"pipeline": "thematic"})["pipeline"] == "thematic"
