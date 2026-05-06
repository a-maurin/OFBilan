from bilans.common.pdf_shared_sections import (
    build_filtered_glossary_rows,
    build_sec6_methodology_html,
)


def test_build_sec6_methodology_html_includes_zone_line() -> None:
    html = build_sec6_methodology_html(
        effective_cfg={},
        period_str="du 01/01/2025 au 31/12/2025",
        dept_name="Côte-d'Or",
        dept_code="21",
        profile_label="PNF",
        sources_text="OSCEAN",
        has_pnf=True,
        has_tub=False,
        is_pnf_profile=True,
    )
    assert "Profil" in html
    assert "Analyse par zones" in html


def test_build_filtered_glossary_rows_filters_expected_ids() -> None:
    gloss_cfg = {
        "header": {"abbr_label": "Abréviation", "definition_label": "Signification"},
        "abbreviations": [
            {"id": "OSCEAN", "label": "OSCEAN", "definition": "Outil"},
            {"id": "DC", "label": "DC", "definition": "Dossier de contrôle"},
            {"id": "PA", "label": "PA", "definition": "Procédure administrative"},
            {"id": "PVe", "label": "PVe", "definition": "PV électronique"},
            {"id": "PNF", "label": "PNF", "definition": "Parc national"},
        ],
    }
    rows = build_filtered_glossary_rows(
        gloss_cfg=gloss_cfg,
        nb_ctrl=10,
        nb_pej=0,
        nb_pa=1,
        nb_pve=0,
        include_pnf=True,
        include_tub=False,
    )
    labels = [row[0] for row in rows[1:]]
    assert labels == ["OSCEAN", "DC", "PA", "PNF"]
