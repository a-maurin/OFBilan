from pathlib import Path

import pandas as pd

from bilans.common.pdf_presentation_config import (
    INTERNAL_DIFFUSION_TITLE_NOTICE,
    apply_diffusion_pdf_suffix,
    build_title_lines_from_cfg,
    is_block_enabled,
    is_section_enabled,
    normalize_diffusion,
    diffusion_pdf_suffix,
    should_show_internal_diffusion_title_notice,
    resolve_internal_diffusion_notice_config,
    resolve_pdf_presentation_config,
    resolve_notice_methodology_config,
    resolve_sec6_methodology_config,
    resolve_section_titles,
    resolve_sections_for_toc,
    resolve_tables_layout,
    resolve_title_page_config,
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


def test_normalize_diffusion() -> None:
    assert normalize_diffusion(None) == "interne"
    assert normalize_diffusion("externe") == "externe"
    assert normalize_diffusion("EXTERNAL") == "externe"


def test_internal_diffusion_title_notice() -> None:
    assert "Diffusion restreinte" in INTERNAL_DIFFUSION_TITLE_NOTICE
    assert should_show_internal_diffusion_title_notice("interne") is True
    assert should_show_internal_diffusion_title_notice("externe") is False
    assert should_show_internal_diffusion_title_notice(None) is True


def test_resolve_internal_diffusion_notice_config_defaults() -> None:
    cfg = resolve_internal_diffusion_notice_config({})
    assert cfg["gap_below_logo_banner_mm"] == 10
    assert cfg["logo_banner_top_ratio"] == 0.86
    assert "Diffusion restreinte" in cfg["text"]


def test_resolve_internal_diffusion_notice_config_yaml_merge(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path,
        """
version: 1
defaults:
  title_page:
    internal_diffusion_notice:
      gap_below_logo_banner_mm: 14
      text: "Mention personnalisée"
""".strip(),
    )
    title_page = resolve_title_page_config(tmp_path, scope="thematique")
    notice = resolve_internal_diffusion_notice_config(title_page)
    assert notice["gap_below_logo_banner_mm"] == 14
    assert notice["text"] == "Mention personnalisée"
    assert notice["font_size"] == 8


def test_diffusion_pdf_suffix() -> None:
    assert diffusion_pdf_suffix("interne") == "_int"
    assert diffusion_pdf_suffix("externe") == "_ext"
    assert diffusion_pdf_suffix(None) == "_int"


def test_apply_diffusion_pdf_suffix() -> None:
    assert apply_diffusion_pdf_suffix("bilan_global.pdf", "interne").name == "bilan_global_int.pdf"
    assert apply_diffusion_pdf_suffix("bilan_global.pdf", "externe").name == "bilan_global_ext.pdf"
    assert (
        apply_diffusion_pdf_suffix(Path("out/Bilan_agriculteur_Cote_dOr.pdf"), "external").name
        == "Bilan_agriculteur_Cote_dOr_ext.pdf"
    )


def test_diffusion_externe_desactive_tableaux_detail(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path,
        """
version: 1
defaults:
  blocks:
    sec31:
      show_detail_table: true
    sec32:
      show_detail_table: true
profiles:
  _diffusion_externe:
    blocks:
      sec31:
        show_detail_table: false
      sec32:
        show_detail_table: false
      sec33:
        show_detail_table: false
""".strip(),
    )
    interne = resolve_pdf_presentation_config(tmp_path, scope="thematique", diffusion="interne")
    externe = resolve_pdf_presentation_config(tmp_path, scope="thematique", diffusion="externe")
    assert is_block_enabled(interne["effective"], "sec32.show_detail_table", True) is True
    assert is_block_enabled(externe["effective"], "sec32.show_detail_table", True) is False
    assert externe.get("diffusion") == "externe"


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


def test_build_title_lines_from_cfg_supports_line_break_in_same_cover_paragraph() -> None:
    cover_lines, header_lines = build_title_lines_from_cfg(
        {
            "title": {
                "line1": "Synthèse des activités de police\nde l'environnement",
                "line2_mode": "none",
            }
        },
        profile_label="",
        dept_name_typo="Côte-d'Or",
    )

    assert cover_lines[:3] == [
        "Synthèse des activités de police",
        "de l'environnement",
        "",
    ]
    assert header_lines[0] == "Synthèse des activités de police de l'environnement"


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


def test_types_usager_cible_sec4_pression_controle() -> None:
    """Profil usager ciblé : section 4 = pression de contrôle (effectifs, département)."""
    root = Path(__file__).resolve().parents[2]
    resolved = resolve_pdf_presentation_config(
        root, scope="thematique", profile_id="types_usager_cible"
    )
    effective = resolved["effective"]
    assert is_section_enabled(effective, "sec4", True) is True
    titles = effective.get("sections", {}).get("titles", {})
    assert "pression" in str(titles.get("sec4", "")).lower()

    section_defs = [
        ("sec1", "1. Chiffres clés"),
        ("sec4", "4. Pression de contrôle"),
        ("sec5", "5. Localisation cartographique"),
    ]
    toc = resolve_sections_for_toc(effective, section_defs)
    assert [sid for sid, _ in toc] == ["sec1", "sec4", "sec5"]

    resolved_usager = resolve_pdf_presentation_config(
        root, scope="thematique", profile_id="types_usager"
    )
    assert is_section_enabled(resolved_usager["effective"], "sec4", True) is True


def test_sec6_methodology_config_resolution() -> None:
    effective = {
        "sec6_methodology": {
            "items": [
                {"when": "always", "text": "<b>Test :</b> {profile_label}."},
            ],
        }
    }
    resolved = resolve_sec6_methodology_config(effective)
    assert resolved["items"][0]["text"] == "<b>Test :</b> {profile_label}."
    assert len(resolved["items"]) >= 1
