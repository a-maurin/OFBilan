from pathlib import Path

import pandas as pd

from bilans.common.pdf_presentation_config import (
    is_block_enabled,
    resolve_pdf_presentation_config,
    resolve_notice_methodology_config,
    resolve_sec6_methodology_config,
    resolve_section_titles,
    resolve_sections_for_toc,
    resolve_tables_layout,
    should_show_placeholder,
)
from bilans.common.pdf_usagers_domaine_table import build_usagers_x_domaine_pdf_rows


def _write_yaml(root: Path, content: str) -> None:
    presentation = root / "config" / "presentation"
    presentation.mkdir(parents=True, exist_ok=True)
    (presentation / "pdf_presentation.yaml").write_text(content, encoding="utf-8")


def test_resolve_config_merges_defaults_scope_and_profile(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path,
        """
version: 1
defaults:
  sections:
    order: [sec1, sec2, sec3]
  blocks:
    sec22res:
      show_table: true
      show_pie: true
scopes:
  global:
    sections:
      order: [sec1, sec3, sec2]
    blocks:
      sec22res:
        show_pie: false
profiles:
  demo:
    scope: global
    blocks:
      sec22res:
        show_table: false
""".strip(),
    )

    resolved = resolve_pdf_presentation_config(tmp_path, scope="global", profile_id="demo")
    effective = resolved["effective"]

    assert effective["sections"]["order"] == ["sec1", "sec3", "sec2"]
    assert effective["blocks"]["sec22res"]["show_table"] is False
    assert effective["blocks"]["sec22res"]["show_pie"] is False


def test_nested_block_lookup_supports_dotted_path() -> None:
    cfg = {"blocks": {"sec22res": {"show_table": True, "show_pie": False}}}
    assert is_block_enabled(cfg, "sec22res.show_table", default=False) is True
    assert is_block_enabled(cfg, "sec22res.show_pie", default=True) is False
    assert is_block_enabled(cfg, "sec22res.unknown_flag", default=True) is True


def test_sections_order_and_enabled_resolution() -> None:
    effective = {
        "sections": {
            "order": ["sec2", "sec1"],
            "enabled": {"sec1": True, "sec2": False, "sec3": True},
        }
    }
    defs = [("sec1", "S1"), ("sec2", "S2"), ("sec3", "S3")]
    assert resolve_sections_for_toc(effective, defs) == [("sec1", "S1"), ("sec3", "S3")]


def test_section_titles_override_resolution() -> None:
    effective = {
        "sections": {
            "titles": {
                "sec1": "1. Chiffres-clés",
                "sec3": "3. Annexes et définitions",
            }
        }
    }
    defs = [("sec1", "1. Chiffres clés"), ("sec2", "2. Contrôles"), ("sec3", "3. Annexes")]
    assert resolve_section_titles(effective, defs) == [
        ("sec1", "1. Chiffres-clés"),
        ("sec2", "2. Contrôles"),
        ("sec3", "3. Annexes et définitions"),
    ]


def test_should_show_placeholder_policy() -> None:
    assert should_show_placeholder({"missing_data_policy": "show_placeholder"}) is True
    assert should_show_placeholder({"missing_data_policy": "hide_silently"}) is False
    assert should_show_placeholder(None) is False


def test_notice_methodology_config_resolution() -> None:
    effective = {
        "notice_methodology": {
            "title": "Notice personnalisée",
            "multi_usager_paragraph": "Texte personnalisé.",
        }
    }
    resolved = resolve_notice_methodology_config(effective)
    assert resolved["title"] == "Notice personnalisée"
    assert resolved["multi_usager_paragraph"] == "Texte personnalisé."
    assert "data_source_paragraph" in resolved


def test_resolve_tables_layout_merges_yaml_over_defaults() -> None:
    effective = {
        "tables": {
            "split_by_row": True,
            "usagers_x_domaine": {"max_domain_columns": 2},
        }
    }
    resolved = resolve_tables_layout(effective)
    assert resolved["split_by_row"] is True
    assert resolved["usagers_x_domaine"]["max_domain_columns"] == 2
    assert "vertical_header" in resolved


def test_build_usagers_x_domaine_truncates_columns_and_note() -> None:
    df = pd.DataFrame(
        [
            {"type_usager": "A", "dom1": 1, "dom2": 100, "dom3": 2},
            {"type_usager": "B", "dom1": 0, "dom2": 1, "dom3": 50},
        ]
    )
    layout = resolve_tables_layout(
        {
            "tables": {
                "usagers_x_domaine": {
                    "max_domain_columns": 1,
                    "max_usager_rows": 10,
                }
            }
        }
    )
    tbl, note = build_usagers_x_domaine_pdf_rows(df, tables_layout=layout)
    assert tbl[0] == ["type_usager", "dom2"]
    assert note is not None
    assert "sur 3" in note


def test_sec6_methodology_config_resolution() -> None:
    effective = {
        "sec6_methodology": {
            "line_profile": "<b>Profil :</b> {profile_label} (personnalisé).",
        }
    }
    resolved = resolve_sec6_methodology_config(effective)
    assert resolved["line_profile"] == "<b>Profil :</b> {profile_label} (personnalisé)."
    assert "line_sources" in resolved
