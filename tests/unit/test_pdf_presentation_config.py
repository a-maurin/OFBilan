from pathlib import Path

import pandas as pd

from bilans.common.pdf_presentation_config import (
    INTERNAL_DIFFUSION_TITLE_NOTICE,
    apply_diffusion_pdf_suffix,
    build_title_lines_from_cfg,
    format_proc_detail_caption,
    get_block_int,
    is_block_enabled,
    is_section_enabled,
    slice_proc_detail_for_pdf,
    normalize_diffusion,
    diffusion_pdf_suffix,
    should_show_internal_diffusion_title_notice,
    resolve_internal_diffusion_notice_config,
    resolve_pdf_presentation_config,
    resolve_notice_methodology_config,
    resolve_sec6_methodology_config,
    resolve_section_titles,
    normalize_section_id,
    resolve_sec2_render_order,
    apply_feature_registry_to_effective,
    feature_registry_allows_scope,
    inject_sec4_subsections,
    resolve_sections_for_toc,
    resolve_charte_config,
    resolve_charte_config_from_root,
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


def test_get_block_int_max_detail_rows() -> None:
    cfg = {"blocks": {"sec31": {"max_detail_rows": 25}}}
    assert get_block_int(cfg, "sec31.max_detail_rows", default=0) == 25
    assert get_block_int(cfg, "sec31.missing", default=7) == 7
    assert get_block_int({"blocks": {}}, "sec31.max_detail_rows", default=0) == 0


def test_slice_proc_detail_for_pdf() -> None:
    df = pd.DataFrame({"numero": [str(i) for i in range(29)]})
    cfg_all = {"blocks": {"sec31": {"max_detail_rows": 0}}}
    shown, total = slice_proc_detail_for_pdf(df, cfg_all, "sec31")
    assert len(shown) == 29
    assert total == 29

    cfg_cap = {"blocks": {"sec31": {"max_detail_rows": 25}}}
    shown2, total2 = slice_proc_detail_for_pdf(df, cfg_cap, "sec31")
    assert len(shown2) == 25
    assert total2 == 29


def test_format_proc_detail_caption_truncation() -> None:
    base = "Detail des PVe"
    assert format_proc_detail_caption(base, shown=25, total=29, cap=25) == (
        "Detail des PVe (25 premiers sur 29)"
    )
    assert format_proc_detail_caption(base, shown=29, total=29, cap=0) == base


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


def test_resolve_charte_config_defaults() -> None:
    cfg = resolve_charte_config({})
    assert cfg["assets"]["banner"] == "image5.jpg"
    assert cfg["title_page"]["banner_height_mm"] == 42.0
    assert cfg["content_page"]["filigrane_height_ratio"] == 0.50
    assert cfg["content_page"]["filigrane_align"] == "bottom_right"
    assert cfg["content_page"]["footer_deco_enabled"] is False


def test_resolve_charte_config_merges_yaml_over_defaults() -> None:
    effective = {
        "charte": {
            "title_page": {"banner_height_mm": 38},
            "content_page": {"watermark_enabled": False, "filigrane_height_ratio": 0.40},
        }
    }
    resolved = resolve_charte_config(effective)
    assert resolved["title_page"]["banner_height_mm"] == 38
    assert resolved["title_page"]["deco_height_ratio"] == 0.50
    assert resolved["content_page"]["watermark_enabled"] is False
    assert resolved["content_page"]["filigrane_height_ratio"] == 0.40


def test_resolve_charte_config_from_root(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path,
        """
version: 1
defaults:
  charte:
    content_page:
      footer_deco_width_mm: 80
""".strip(),
    )
    cfg = resolve_charte_config_from_root(tmp_path, scope="thematique")
    assert cfg["content_page"]["footer_deco_width_mm"] == 80
    assert cfg["assets"]["title_page_deco"] == "image6.jpeg"


def test_resolve_charte_config_from_root_project_yaml() -> None:
    root = Path(__file__).resolve().parents[2]
    cfg = resolve_charte_config_from_root(root, scope="thematique", profile_id="chasse")
    assert cfg["title_page"]["banner_height_mm"] == 42
    assert cfg["content_page"]["filigrane_align"] == "bottom_right"
    assert cfg["content_page"]["footer_deco_enabled"] is False


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
    assert resolved["vertical_header"].get("max_lines") == 6


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


def test_agrainage_pdf_sections_order_and_titles() -> None:
    """Profil agrainage : ch.2 contrôles, ch.3 usagers, ch.4 procédures."""
    root = Path(__file__).resolve().parents[2]
    resolved = resolve_pdf_presentation_config(root, scope="thematique", profile_id="agrainage")
    effective = resolved["effective"]

    sections_cfg = effective.get("sections", {})
    order = sections_cfg.get("order", []) if isinstance(sections_cfg, dict) else []
    titles = sections_cfg.get("titles", {}) if isinstance(sections_cfg, dict) else {}

    assert order == [
        "sec1",
        "sec2",
        "sec21",
        "sec22",
        "sec23",
        "sec22theme",
        "sec22res",
        "sec4",
        "sec41",
        "sec42",
        "sec43",
        "sec44",
        "sec3",
        "sec31",
        "sec32",
        "sec33",
        "sec5",
        "sec6",
    ]
    assert titles.get("sec23") == "2.3. Résultats des contrôles"
    assert titles.get("sec4") == "3. Activité par type d’usager"
    assert titles.get("sec3") == "4. Procédures (PEJ, PA, PVe)"

    section_defs = inject_sec4_subsections(
        [
            ("sec1", "1. Chiffres clés"),
            ("sec2", "2. Activité de contrôle"),
            ("sec21", "2.1. Indicateurs mensuels"),
            ("sec22", "2.2. Répartition de l'activité par domaines (contrôles + PEJ)"),
            ("sec23", "2.3. Résultats des contrôles"),
            ("sec22theme", "2.4. Analyse par zone"),
            ("sec22res", "2.5. Synthèse croisée par zone"),
            ("sec4", "3. Activité par type d’usager"),
            ("sec3", "4. Procédures (PEJ, PA, PVe)"),
            ("sec31", "4.1 Procès-verbaux électroniques (PVe)"),
            ("sec32", "4.2 Procédures d’enquête judiciaire (PEJ)"),
            ("sec33", "4.3 Procédures administratives (PA)"),
            ("sec5", "5. Localisation cartographique des contrôles"),
            ("sec6", "6. Annexes"),
        ]
    )
    toc = resolve_sections_for_toc(effective, section_defs)
    assert [sid for sid, _ in toc] == order
    assert titles.get("sec42") == "3.2. Résultats des contrôles par type d'usager"


def test_thematique_default_sections_usagers_before_procedures() -> None:
    root = Path(__file__).resolve().parents[2]
    resolved = resolve_pdf_presentation_config(root, scope="thematique", profile_id="chasse")
    order = resolved["effective"]["sections"]["order"]
    assert order.index("sec4") < order.index("sec3")
    titles = resolved["effective"]["sections"]["titles"]
    assert "3." in str(titles.get("sec4", ""))


def test_feature_registry_disables_cross_scope_sections() -> None:
    root = Path(__file__).resolve().parents[2]
    them = resolve_pdf_presentation_config(root, scope="thematique", profile_id="chasse")
    eff_t = them["effective"]
    assert is_section_enabled(eff_t, "sec23", True) is True
    assert is_section_enabled(eff_t, "sec22dom", True) is False
    assert is_section_enabled(eff_t, "sec5", True) is True
    assert is_section_enabled(eff_t, "sec5map", True) is False

    glob = resolve_pdf_presentation_config(root, scope="global", profile_id=None)
    eff_g = glob["effective"]
    assert is_section_enabled(eff_g, "sec23", True) is False
    assert is_section_enabled(eff_g, "sec22dom", True) is True
    assert is_section_enabled(eff_g, "sec5map", True) is True
    assert is_section_enabled(eff_g, "sec5", True) is False


def test_feature_registry_explicit_enabled_overrides_registry() -> None:
    effective = {"sections": {"enabled": {"sec22dom": True}}}
    apply_feature_registry_to_effective(
        effective,
        "thematique",
        {"sec22dom": "global"},
    )
    assert effective["sections"]["enabled"]["sec22dom"] is True


def test_feature_registry_allows_scope_rules() -> None:
    assert feature_registry_allows_scope("both", "global") is True
    assert feature_registry_allows_scope("global", "global") is True
    assert feature_registry_allows_scope("global", "thematique") is False
    assert feature_registry_allows_scope("thematique", "thematique") is True


def test_hoist_legacy_scope_titles_into_sections_titles(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path,
        """
version: 1
defaults:
  sections:
    order: [sec1]
scopes:
  thematique:
    sections:
      order: [sec4, sec3]
    titles:
      sec4: "3. Usagers"
      sec3: "4. Procédures"
""".strip(),
    )
    resolved = resolve_pdf_presentation_config(
        tmp_path, scope="thematique", profile_id=None, diffusion="interne"
    )
    titles = resolved["effective"]["sections"]["titles"]
    assert titles.get("sec4") == "3. Usagers"
    assert titles.get("sec3") == "4. Procédures"


def test_summarize_procedures_par_type_usager() -> None:
    from bilans.common.pdf_shared_sections import summarize_procedures_par_type_usager

    df = pd.DataFrame(
        [
            {"type_usager": "A", "domaine": "d1", "nb_pej": 2, "nb_pa": 1},
            {"type_usager": "A", "domaine": "d2", "nb_pej": 1, "nb_pa": 0},
            {"type_usager": "B", "domaine": "d1", "nb_pej": 0, "nb_pa": 3},
        ]
    )
    out = summarize_procedures_par_type_usager(df)
    row_a = out.loc[out["type_usager"] == "A"].iloc[0]
    assert int(row_a["nb_pej"]) == 3
    assert int(row_a["nb_pa"]) == 1


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
