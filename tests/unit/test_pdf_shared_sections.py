from bilans.common.pdf_shared_sections import (
    build_filtered_glossary_rows,
    build_sec6_methodology_context,
    build_sec6_methodology_html,
)


def test_build_sec6_methodology_html_includes_zone_line() -> None:
    html = build_sec6_methodology_html(
        effective_cfg={},
        context=build_sec6_methodology_context(
            period_str="du 01/01/2025 au 31/12/2025",
            perimetre_name="Côte-d'Or",
            perimetre_code="21",
            profile_label="PNF",
            has_pnf=True,
            has_tub=False,
            is_pnf_profile=True,
            nb_localisations=10,
        ),
    )
    assert "Période" in html
    assert "cœur" in html or "coeur" in html.lower()
    assert "Réalisation" in html
    assert "service départemental de la Côte d'Or" in html


def test_build_sec6_methodology_html_diffusion_externe() -> None:
    html = build_sec6_methodology_html(
        effective_cfg={},
        context=build_sec6_methodology_context(
            period_str="du 01/01/2025 au 31/12/2025",
            perimetre_name="Côte-d'Or",
            perimetre_code="21",
            diffusion="externe",
            nb_localisations=5,
        ),
    )
    assert "synthèse" in html.lower()


def test_build_sec6_methodology_html_skips_empty_when() -> None:
    html = build_sec6_methodology_html(
        effective_cfg={
            "sec6_methodology": {
                "items": [
                    {"when": "has_pej", "text": "Phrase PEJ."},
                    {"when": "always", "text": "Phrase toujours."},
                ],
            },
        },
        context=build_sec6_methodology_context(
            period_str="période",
            perimetre_name="Test",
            perimetre_code="00",
            nb_pej=0,
        ),
    )
    assert "Phrase PEJ" not in html
    assert "Phrase toujours" in html


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
        nb_localisations=10,
        nb_pej=0,
        nb_pa=1,
        nb_pve=0,
        include_pnf=True,
        include_tub=False,
    )
    labels = [row[0] for row in rows[1:]]
    assert labels == ["OSCEAN", "DC", "PA", "PNF"]
